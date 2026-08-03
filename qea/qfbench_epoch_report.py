"""Scheduler-epoch metrics and lifecycle gates for QFBench baselines."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from typing import Iterable, Mapping

from .qfbench_baseline import BaselineConfigError, audit_baseline_proxy_costs
from .sandbox_lifecycle import SandboxLifecycleError, load_lifecycle
from .sandbox_network_lifecycle import (
    SandboxNetworkLifecycleError,
    load_network_lifecycle,
)


_CHECKPOINT = re.compile(
    r"repetition-(?P<repetition>0[1-5])-(?P<panel>primary|diagnostic)\Z"
)
_EPOCHS = (
    ("scheduler_epoch_1", (1,), 4, 3),
    ("scheduler_epoch_2", (2, 3, 4, 5), 12, 3),
)


class EpochReportError(RuntimeError):
    """Formal run evidence cannot be summarized without ambiguity."""


def _timestamp(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise EpochReportError(f"{label} timestamp is unavailable")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EpochReportError(f"{label} timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EpochReportError(f"{label} timestamp must be timezone-aware")
    return parsed


def max_worker_overlap(lifecycles: Iterable[Mapping[str, object]]) -> int:
    """Return peak overlap from validated worker start/finish intervals."""

    events: list[tuple[datetime, int]] = []
    count = 0
    for lifecycle in lifecycles:
        if lifecycle.get("role") != "worker":
            continue
        started = _timestamp(lifecycle.get("started_at"), label="worker start")
        finished = _timestamp(
            lifecycle.get("finished_at"), label="worker finish"
        )
        if finished < started:
            raise EpochReportError("worker lifecycle finishes before it starts")
        events.append((started, 1))
        events.append((finished, -1))
        count += 1
    if count == 0:
        return 0
    active = 0
    peak = 0
    for _, change in sorted(events, key=lambda item: (item[0], item[1])):
        active += change
        if active < 0:
            raise EpochReportError("worker lifecycle overlap is inconsistent")
        peak = max(peak, active)
    if active != 0:
        raise EpochReportError("worker lifecycle overlap is unterminated")
    return peak


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise EpochReportError(f"required metadata is unavailable: {path}")
    try:
        payload = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EpochReportError(f"metadata is invalid: {path}") from exc
    if not isinstance(payload, dict):
        raise EpochReportError(f"metadata must be an object: {path}")
    return payload


def _read_audit(path: Path) -> tuple[dict, ...]:
    if path.is_symlink() or not path.is_file():
        return ()
    records: list[dict] = []
    try:
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("record is not an object")
            records.append(record)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise EpochReportError(f"proxy audit is invalid: {path}") from exc
    return tuple(records)


def _decimal(value: object, *, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise EpochReportError(f"{label} is invalid")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise EpochReportError(f"{label} is invalid") from exc
    if not parsed.is_finite() or parsed < 0:
        raise EpochReportError(f"{label} is invalid")
    return parsed


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def _metrics(records: list[dict], repetitions: tuple[int, ...]) -> dict:
    selected = [record for record in records if record["repetition"] in repetitions]
    rewards = [record["reward"] for record in selected]
    latencies = [
        latency for record in selected for latency in record["latencies_ms"]
    ]
    starts = [record["worker_started_at"] for record in selected]
    finishes = [record["worker_finished_at"] for record in selected]
    cost = sum((record["provider_cost_usd"] for record in selected), Decimal("0"))
    lower_bound = any(record["provider_cost_is_lower_bound"] for record in selected)
    return {
        "repetitions": list(repetitions),
        "attempt_count": len(selected),
        "official_reward_mean": (
            sum(rewards) / len(rewards) if rewards else None
        ),
        "timeout_count": sum(record["timeout"] for record in selected),
        "request_count": sum(record["request_count"] for record in selected),
        "provider_latency_ms": {
            "count": len(latencies),
            "mean": sum(latencies) / len(latencies) if latencies else None,
            "median": median(latencies) if latencies else None,
            "p90": _percentile(latencies, 0.90),
        },
        "provider_cost_usd": str(cost),
        "provider_cost_is_lower_bound": lower_bound,
        "wall_time_seconds": (
            (max(finishes) - min(starts)).total_seconds()
            if starts and finishes
            else None
        ),
    }


def _worker_interval(run_dir: Path, attempt_id: str) -> tuple[datetime, datetime]:
    candidates = (
        run_dir
        / "lifecycles"
        / run_dir.name
        / attempt_id
        / "worker-sandbox-lifecycle-v2.json",
        run_dir
        / "lifecycles"
        / attempt_id
        / "worker-sandbox-lifecycle-v2.json",
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise EpochReportError(f"worker lifecycle is missing for {attempt_id}")
    payload = _read_json(path)
    if (
        payload.get("role") != "worker"
        or payload.get("attempt_id") != attempt_id
        or payload.get("run_id") != run_dir.name
    ):
        raise EpochReportError(f"worker lifecycle identity differs for {attempt_id}")
    return (
        _timestamp(payload.get("started_at"), label="worker start"),
        _timestamp(payload.get("finished_at"), label="worker finish"),
    )


def summarize_scheduler_epochs(run_dir: str | Path) -> dict:
    """Summarize official evidence without changing rewards or judging outputs."""

    root = Path(run_dir).resolve()
    attempts = tuple(sorted((root / "attempts").glob("*/attempt.json")))
    if not attempts:
        raise EpochReportError("formal run has no attempts")
    try:
        cost_audit = audit_baseline_proxy_costs(
            root, expected_attempts=len(attempts)
        )
    except BaselineConfigError as exc:
        raise EpochReportError(str(exc)) from exc
    records: list[dict] = []
    for attempt_path in attempts:
        attempt = _read_json(attempt_path)
        attempt_id = attempt_path.parent.name
        match = _CHECKPOINT.fullmatch(str(attempt.get("checkpoint", "")))
        if (
            attempt.get("attempt_id") != attempt_id
            or attempt.get("run_id") != root.name
            or match is None
        ):
            raise EpochReportError(f"attempt identity is invalid: {attempt_id}")
        score = _read_json(attempt_path.parent / "completed-score.json")
        reward = score.get("reward")
        tags = score.get("diagnostic_tags")
        if (
            score.get("task_id") != attempt.get("task_id")
            or isinstance(reward, bool)
            or not isinstance(reward, (int, float))
            or not 0.0 <= float(reward) <= 1.0
            or not isinstance(tags, list)
            or not all(isinstance(tag, str) for tag in tags)
        ):
            raise EpochReportError(f"score identity is invalid: {attempt_id}")
        audits = _read_audit(attempt_path.parent / "proxy-audit.jsonl")
        latencies: list[float] = []
        cost = Decimal("0")
        lower_bound = not audits
        for audit in audits:
            latency = audit.get("latency_ms")
            if isinstance(latency, (int, float)) and not isinstance(latency, bool):
                if latency < 0:
                    raise EpochReportError("provider latency cannot be negative")
                latencies.append(float(latency))
            raw_cost = audit.get("provider_cost_usd")
            if raw_cost is None:
                if audit.get("request_state") == "completed":
                    lower_bound = True
            else:
                cost += _decimal(raw_cost, label="provider cost")
        started, finished = _worker_interval(root, attempt_id)
        records.append(
            {
                "repetition": int(match.group("repetition")),
                "reward": float(reward),
                "timeout": "timeout" in tags,
                "request_count": len(audits),
                "latencies_ms": latencies,
                "provider_cost_usd": cost,
                "provider_cost_is_lower_bound": lower_bound,
                "worker_started_at": started,
                "worker_finished_at": finished,
            }
        )
    epoch_payload = {}
    for label, repetitions, worker_concurrency, verifier_concurrency in _EPOCHS:
        epoch_payload[label] = {
            **_metrics(records, repetitions),
            "worker_concurrency": worker_concurrency,
            "verifier_concurrency": verifier_concurrency,
        }
    combined = _metrics(records, (1, 2, 3, 4, 5))
    combined["cost_audit_complete"] = cost_audit["cost_complete"]
    return {
        "schema_version": 1,
        "run_id": root.name,
        "epochs": epoch_payload,
        "combined": combined,
        "scheduler_epoch_batch_effect_warning": True,
    }


def audit_paid_baseline_lifecycles(
    run_dir: str | Path, *, attempt_ids: Iterable[str]
) -> dict:
    """Require exact cleanup and the worker/verifier network firewall."""

    root = Path(run_dir).resolve()
    identifiers = tuple(attempt_ids)
    if len(identifiers) != 12 or len(set(identifiers)) != 12:
        raise EpochReportError("paid batch needs exactly twelve attempt identities")
    workers: list[dict] = []
    for attempt_id in identifiers:
        sandbox_root = root / "lifecycles" / root.name / attempt_id
        proxy_root = root / "lifecycles" / attempt_id
        if not sandbox_root.is_dir() and proxy_root.is_dir():
            sandbox_root = proxy_root
        if not proxy_root.is_dir() and sandbox_root.is_dir():
            proxy_root = sandbox_root
        try:
            worker = load_lifecycle(
                sandbox_root / "worker-sandbox-lifecycle-v2.json"
            )
            proxy = load_lifecycle(
                proxy_root / "proxy-sandbox-lifecycle-v2.json"
            )
            verifier = load_lifecycle(
                sandbox_root / "verifier-sandbox-lifecycle-v2.json"
            )
            network = load_network_lifecycle(
                proxy_root / "proxy-network-lifecycle-v1.json"
            )
        except (SandboxLifecycleError, SandboxNetworkLifecycleError) as exc:
            raise EpochReportError(
                f"paid batch lifecycle is invalid for {attempt_id}: {exc}"
            ) from exc
        for lifecycle, role in (
            (worker, "worker"),
            (proxy, "proxy"),
            (verifier, "verifier"),
        ):
            if (
                lifecycle.role != role
                or lifecycle.run_id != root.name
                or lifecycle.attempt_id != attempt_id
                or not lifecycle.cleaned_up
                or lifecycle.cleanup_result not in {"killed", "already_absent"}
            ):
                raise EpochReportError(
                    f"paid batch {role} cleanup or identity is invalid"
                )
        if (
            worker.resource_contract.get("network_policy")
            != "worker-proxy-only"
            or verifier.resource_contract.get("network_policy") != "none"
        ):
            raise EpochReportError("paid batch evaluator firewall is invalid")
        if (
            network.run_id != root.name
            or network.network_scope != attempt_id
            or not network.cleaned_up
        ):
            raise EpochReportError("paid batch network cleanup is invalid")
        workers.append(worker.to_payload())
    overlap = max_worker_overlap(workers)
    if overlap != 12:
        raise EpochReportError(
            f"paid batch measured worker overlap {overlap}, expected 12"
        )
    return {
        "worker_overlap": overlap,
        "cleaned_up": True,
        "verifier_networkless": True,
        "worker_proxy_only": True,
    }


__all__ = [
    "EpochReportError",
    "audit_paid_baseline_lifecycles",
    "max_worker_overlap",
    "summarize_scheduler_epochs",
]
