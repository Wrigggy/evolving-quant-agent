#!/usr/bin/env python3
"""Fail-closed audit for the 30/15/32+8 QFBench evolution protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.attempt_recovery import resolve_worker_attempt
from qea.evaluation import TaskAttempt
from qea.qfbench_validation import load_validation_calibration
from qea.rootless_full_harness import rootless_model_route_identity
from qea.sandbox_lifecycle import SandboxLifecycleError, load_lifecycle
from qea.sandbox_network_lifecycle import (
    SandboxNetworkLifecycleError,
    load_network_lifecycle,
)
from scripts.accept_qfbench_evolution_tier import load_tier_acceptance


MODEL = "deepseek/deepseek-v4-flash-0731"
PROVIDER = "deepseek"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REPLACEMENT_SUFFIX = re.compile(r"\+infra-replacement-[0-9]{2}\Z")


class EvolutionAuditError(RuntimeError):
    """Formal evolution evidence is incomplete, inconsistent, or unsafe."""


def _canonical_digest(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            dict(payload),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _read_json(path: Path, *, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise EvolutionAuditError(f"{label} is unavailable: {path}")
    try:
        payload = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvolutionAuditError(f"{label} is invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise EvolutionAuditError(f"{label} must be a JSON object")
    return payload


def _number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvolutionAuditError(f"{label} is invalid")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise EvolutionAuditError(f"{label} is invalid")
    return parsed


def _panels(manifest: Mapping[str, object]) -> dict[str, tuple[dict, ...]]:
    if manifest.get("schema_version") != 2:
        raise EvolutionAuditError("test manifest schema must be version 2")
    evolution = manifest.get("evolution")
    if not isinstance(evolution, Mapping):
        raise EvolutionAuditError("test manifest evolution panels are missing")
    expected_counts = {"train": 30, "validation": 15, "test": 32, "diagnostic": 8}
    panels: dict[str, tuple[dict, ...]] = {}
    seen_ids: set[str] = set()
    seen_lineages: set[str] = set()
    for name, expected_count in expected_counts.items():
        entries = evolution.get(name)
        if not isinstance(entries, list) or len(entries) != expected_count:
            raise EvolutionAuditError(
                f"{name} test panel must contain exactly {expected_count} tasks"
            )
        checked = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise EvolutionAuditError(f"{name} test panel entry is invalid")
            task_id = entry.get("task_id")
            domain = entry.get("domain")
            lineage = entry.get("lineage")
            if not all(isinstance(value, str) and value for value in (task_id, domain, lineage)):
                raise EvolutionAuditError(f"{name} test task identity is invalid")
            if task_id in seen_ids or lineage in seen_lineages:
                raise EvolutionAuditError("train/validation/test panels overlap")
            seen_ids.add(task_id)
            seen_lineages.add(lineage)
            checked.append(entry)
        panels[name] = tuple(checked)
    copy_oracle = manifest.get("copy_oracle_tasks")
    diagnostic_ids = {entry["task_id"] for entry in panels["diagnostic"]}
    if (
        not isinstance(copy_oracle, list)
        or set(copy_oracle) != diagnostic_ids
        or len(copy_oracle) != 8
    ):
        raise EvolutionAuditError("diagnostic test panel differs from copy-oracle tasks")
    return panels


def _task_manifest_digest(
    commit: str, panels: Mapping[str, tuple[dict, ...]]
) -> str:
    payload: dict[str, object] = {
        "benchmark_commit": commit,
        "protocol": "train-validation-test-v1",
    }
    for name in ("train", "validation", "test", "diagnostic"):
        payload[name] = [
            {
                "task_id": entry["task_id"],
                "domain": entry["domain"],
                "lineage": entry["lineage"],
            }
            for entry in panels[name]
        ]
    return _canonical_digest(payload)


def _summary(
    payload: object,
    *,
    entries: tuple[dict, ...],
    label: str,
) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        raise EvolutionAuditError(f"{label} test summary is missing")
    scores = payload.get("scores")
    task_rewards = payload.get("task_rewards")
    domain_scores = payload.get("domain_scores")
    if not isinstance(scores, list) or not isinstance(task_rewards, Mapping):
        raise EvolutionAuditError(f"{label} test summary score schema is invalid")
    if not isinstance(domain_scores, Mapping):
        raise EvolutionAuditError(f"{label} test domain scores are invalid")
    expected = {entry["task_id"]: entry["domain"] for entry in entries}
    observed: dict[str, float] = {}
    by_domain: dict[str, list[float]] = {}
    for score in scores:
        if not isinstance(score, Mapping):
            raise EvolutionAuditError(f"{label} test score is invalid")
        task_id = score.get("task_id")
        domain = score.get("domain")
        if task_id not in expected or expected.get(task_id) != domain:
            raise EvolutionAuditError(f"{label} test score identity differs")
        if task_id in observed:
            raise EvolutionAuditError(f"{label} test score repeats a task")
        reward = _number(score.get("reward"), label=f"{label} test reward")
        if not 0.0 <= reward <= 1.0:
            raise EvolutionAuditError(f"{label} test reward is outside [0, 1]")
        observed[str(task_id)] = reward
        by_domain.setdefault(str(domain), []).append(reward)
    if set(observed) != set(expected) or len(scores) != len(entries):
        raise EvolutionAuditError(f"{label} test summary task set differs")
    if set(task_rewards) != set(expected):
        raise EvolutionAuditError(f"{label} test task rewards differ")
    for task_id, reward in observed.items():
        if not math.isclose(
            _number(task_rewards[task_id], label=f"{label} test task reward"),
            reward,
            abs_tol=1e-12,
        ):
            raise EvolutionAuditError(f"{label} test task reward is inconsistent")
    recomputed_domains = {
        domain: sum(values) / len(values)
        for domain, values in sorted(by_domain.items())
    }
    if set(domain_scores) != set(recomputed_domains):
        raise EvolutionAuditError(f"{label} test domain set differs")
    for domain, value in recomputed_domains.items():
        if not math.isclose(
            _number(domain_scores[domain], label=f"{label} test domain score"),
            value,
            abs_tol=1e-12,
        ):
            raise EvolutionAuditError(f"{label} test domain score is inconsistent")
    task_mean = sum(observed.values()) / len(observed)
    overall = sum(recomputed_domains.values()) / len(recomputed_domains)
    if not math.isclose(
        _number(payload.get("task_mean"), label=f"{label} test task mean"),
        task_mean,
        abs_tol=1e-12,
    ) or not math.isclose(
        _number(payload.get("overall"), label=f"{label} test overall"),
        overall,
        abs_tol=1e-12,
    ):
        raise EvolutionAuditError(f"{label} test aggregate is inconsistent")
    return {
        "task_rewards": observed,
        "domain_scores": recomputed_domains,
        "task_mean": task_mean,
        "overall": overall,
    }


def _expected_attempts(
    panels: Mapping[str, tuple[dict, ...]]
) -> dict[tuple[str, str, str], str]:
    expected: dict[tuple[str, str, str], str] = {}

    def add(split: str, checkpoint: str, panel: str) -> None:
        for entry in panels[panel]:
            expected[(split, checkpoint, entry["task_id"])] = entry["domain"]

    add("optimize", "seed-optimize", "train")
    add("validation", "seed-validation", "validation")
    add("test", "seed-test", "test")
    add("diagnostic", "seed-diagnostic", "diagnostic")
    for iteration in range(1, 11):
        add("optimize", f"iteration-{iteration}-candidate", "train")
        add("validation", f"iteration-{iteration}-validation", "validation")
    add("test", "final-test", "test")
    add("diagnostic", "final-diagnostic", "diagnostic")
    if len(expected) != 575:
        raise AssertionError("internal QFBench schedule is not 575 attempts")
    return expected


def _delta(seed: Mapping[str, object], final: Mapping[str, object]) -> dict[str, object]:
    seed_tasks = seed["task_rewards"]
    final_tasks = final["task_rewards"]
    seed_domains = seed["domain_scores"]
    final_domains = final["domain_scores"]
    assert isinstance(seed_tasks, Mapping) and isinstance(final_tasks, Mapping)
    assert isinstance(seed_domains, Mapping) and isinstance(final_domains, Mapping)
    return {
        "task_count": len(seed_tasks),
        "seed_overall": seed["overall"],
        "final_overall": final["overall"],
        "overall_delta": float(final["overall"]) - float(seed["overall"]),
        "task_deltas": {
            task_id: float(final_tasks[task_id]) - float(seed_tasks[task_id])
            for task_id in sorted(seed_tasks)
        },
        "domain_deltas": {
            domain: float(final_domains[domain]) - float(seed_domains[domain])
            for domain in sorted(seed_domains)
        },
    }


def audit_evolution_payloads(
    *,
    result: Mapping[str, object],
    resume: Mapping[str, object],
    manifest: Mapping[str, object],
    calibration: Mapping[str, object],
    tier_acceptance: Mapping[str, object],
    attempts: Iterable[Mapping[str, object]],
    mirrored_attempt_ids: set[str],
    formal_residual_resource_count: int = 0,
) -> dict[str, object]:
    """Reconcile prevalidated filesystem evidence against the fixed protocol."""

    panels = _panels(manifest)
    run_id = result.get("run_id")
    commit = manifest.get("commit")
    if (
        result.get("schema_version") != 3
        or resume.get("schema_version") != 3
        or resume.get("phase") != "complete"
        or not isinstance(run_id, str)
        or not run_id
        or resume.get("run_id") != run_id
        or resume.get("n_iters") != 10
        or not isinstance(commit, str)
        or re.fullmatch(r"[0-9a-f]{40}", commit) is None
        or resume.get("benchmark_commit") != commit
    ):
        raise EvolutionAuditError("complete schema-v3 run identity is invalid")
    identity = result.get("identity")
    if not isinstance(identity, Mapping) or resume.get("identity") != identity:
        raise EvolutionAuditError("run identity differs between result and resume")
    if identity.get("protocol") != "train-validation-test-v1":
        raise EvolutionAuditError("run protocol identity is invalid")
    expected_manifest_digest = _task_manifest_digest(commit, panels)
    if identity.get("task_manifest_digest") != expected_manifest_digest:
        raise EvolutionAuditError("train/validation/test manifest identity differs")

    calibration_digest = calibration.get("digest")
    validation_ids = [entry["task_id"] for entry in panels["validation"]]
    if (
        not isinstance(calibration_digest, str)
        or _SHA256.fullmatch(calibration_digest) is None
        or calibration.get("validation_task_ids") != validation_ids
        or identity.get("validation_calibration_digest") != calibration_digest
        or identity.get("validation_calibration_source_run_id")
        != calibration.get("source_run_id")
        or not math.isclose(
            _number(
                identity.get("validation_noise_tolerance"),
                label="validation calibration tolerance",
            ),
            _number(calibration.get("tolerance"), label="calibration tolerance"),
            abs_tol=1e-12,
        )
    ):
        raise EvolutionAuditError("validation calibration identity differs")

    workers = tier_acceptance.get("worker_concurrency")
    verifiers = tier_acceptance.get("verifier_concurrency")
    if (
        (workers, verifiers) not in {(20, 3), (16, 3), (12, 3)}
        or identity.get("worker_concurrency") != workers
        or identity.get("verifier_concurrency") != verifiers
        or identity.get("scheduler_identity_digest")
        != tier_acceptance.get("scheduler_identity_digest")
        or tier_acceptance.get("model") != MODEL
        or tier_acceptance.get("provider") != PROVIDER
        or tier_acceptance.get("fallbacks_allowed") is not False
    ):
        raise EvolutionAuditError("accepted scheduler/provider identity differs")
    expected_model_identity = rootless_model_route_identity(
        upstream_base_url=tier_acceptance.get("upstream_base_url"),
        allowed_path_prefix=tier_acceptance.get("allowed_path_prefix"),
        allowed_model=MODEL,
        required_provider=PROVIDER,
    )
    if identity.get("model_identity") != expected_model_identity:
        raise EvolutionAuditError("official model/provider route identity differs")

    records = result.get("records")
    if (
        not isinstance(records, list)
        or records != resume.get("records")
        or len(records) != 10
    ):
        raise EvolutionAuditError("keep/rollback iteration records are incomplete")
    iterations = []
    for number, record in enumerate(records, start=1):
        if (
            not isinstance(record, Mapping)
            or record.get("iteration") != number
            or type(record.get("kept")) is not bool
            or not isinstance(record.get("reason"), str)
            or not record.get("reason")
        ):
            raise EvolutionAuditError("keep/rollback iteration record is invalid")
        iterations.append(
            {
                "iteration": number,
                "decision": "keep" if record["kept"] else "rollback",
                "reason": record["reason"],
            }
        )
    validation_records = result.get("validation_records")
    if (
        not isinstance(validation_records, list)
        or validation_records != resume.get("validation_records")
        or len(validation_records) != 10
    ):
        raise EvolutionAuditError("validation confirm records are incomplete")
    tolerance = _number(calibration.get("tolerance"), label="calibration tolerance")
    for number, record in enumerate(validation_records, start=1):
        if (
            not isinstance(record, Mapping)
            or record.get("iteration") != number
            or type(record.get("confirmed")) is not bool
            or not math.isclose(
                _number(record.get("tolerance"), label="validation tolerance"),
                tolerance,
                abs_tol=1e-12,
            )
        ):
            raise EvolutionAuditError("validation confirm record is invalid")
        _summary(
            record.get("incumbent_before"),
            entries=panels["validation"],
            label=f"iteration {number} incumbent validation",
        )
        _summary(
            record.get("candidate"),
            entries=panels["validation"],
            label=f"iteration {number} candidate validation",
        )

    train_seed = _summary(
        resume.get("seed_optimize"), entries=panels["train"], label="seed train"
    )
    train_final = _summary(
        result.get("optimize_final"), entries=panels["train"], label="final train"
    )
    validation_seed = _summary(
        result.get("validation_seed"),
        entries=panels["validation"],
        label="seed validation",
    )
    validation_final = _summary(
        result.get("validation_final"),
        entries=panels["validation"],
        label="final validation",
    )
    test_seed = _summary(
        result.get("test_seed"), entries=panels["test"], label="seed primary test"
    )
    test_final = _summary(
        result.get("test_final"), entries=panels["test"], label="final primary test"
    )
    diagnostic_seed = _summary(
        result.get("diagnostic_seed"),
        entries=panels["diagnostic"],
        label="seed diagnostic test",
    )
    diagnostic_final = _summary(
        result.get("diagnostic_final"),
        entries=panels["diagnostic"],
        label="final diagnostic test",
    )

    expected_attempts = _expected_attempts(panels)
    evidence = tuple(attempts)
    if len(evidence) != 575:
        raise EvolutionAuditError(
            f"official attempt count is {len(evidence)}, expected 575"
        )
    logical: dict[tuple[str, str, str], str] = {}
    attempt_ids: set[str] = set()
    provider_request_count = 0
    for item in evidence:
        if not isinstance(item, Mapping):
            raise EvolutionAuditError("official attempt evidence is invalid")
        attempt_id = item.get("attempt_id")
        if (
            not isinstance(attempt_id, str)
            or _SHA256.fullmatch(attempt_id) is None
            or attempt_id in attempt_ids
        ):
            raise EvolutionAuditError("official attempt identity is duplicate or invalid")
        attempt_ids.add(attempt_id)
        if item.get("run_id") != run_id or item.get("benchmark_commit") != commit:
            raise EvolutionAuditError("official attempt run identity differs")
        key = (item.get("split"), item.get("checkpoint"), item.get("task_id"))
        if key not in expected_attempts or key in logical:
            raise EvolutionAuditError("official attempt checkpoint schedule differs")
        logical[key] = attempt_id
        score = item.get("score")
        if not isinstance(score, Mapping):
            raise EvolutionAuditError("official completed score is missing")
        if score.get("task_id") != key[2] or score.get("domain") != expected_attempts[key]:
            raise EvolutionAuditError("official completed score identity differs")
        reward = _number(score.get("reward"), label="official reward")
        if not 0.0 <= reward <= 1.0:
            raise EvolutionAuditError("official reward is outside [0, 1]")
        if item.get("provider_ok") is not True:
            raise EvolutionAuditError("official provider request failed")
        request_ids = item.get("provider_request_identities")
        if not isinstance(request_ids, list):
            raise EvolutionAuditError("provider request evidence is invalid")
        if len(request_ids) != len(set(request_ids)):
            raise EvolutionAuditError("provider replay detected within an attempt")
        if any(
            not isinstance(value, str) or _SHA256.fullmatch(value) is None
            for value in request_ids
        ):
            raise EvolutionAuditError("provider request identity is invalid")
        timeout = "timeout" in score.get("diagnostic_tags", ())
        if not request_ids and not timeout:
            raise EvolutionAuditError("provider request evidence is missing")
        provider_request_count += len(request_ids)
        if (
            item.get("worker_cleaned") is not True
            or item.get("worker_proxy_only") is not True
            or item.get("network_cleaned") is not True
        ):
            raise EvolutionAuditError("worker/proxy lifecycle firewall failed")
        if not timeout and (
            item.get("verifier_cleaned") is not True
            or item.get("verifier_networkless") is not True
        ):
            raise EvolutionAuditError("verifier lifecycle firewall failed")
    if set(logical) != set(expected_attempts):
        raise EvolutionAuditError("official 575-attempt checkpoint schedule is incomplete")
    if mirrored_attempt_ids != attempt_ids:
        missing = len(attempt_ids - mirrored_attempt_ids)
        extra = len(mirrored_attempt_ids - attempt_ids)
        raise EvolutionAuditError(
            f"local mirror differs from formal attempts: missing={missing}, extra={extra}"
        )
    if formal_residual_resource_count != 0:
        raise EvolutionAuditError("formal run has residual rootless resources")

    audit: dict[str, object] = {
        "schema_version": 1,
        "run_id": run_id,
        "passed": True,
        "attempts": {
            "total": len(attempt_ids),
            "unique_logical": len(logical),
            "by_split": dict(
                sorted(Counter(key[0] for key in logical).items())
            ),
        },
        "scheduler": {
            "worker_concurrency": workers,
            "verifier_concurrency": verifiers,
            "scheduler_identity_digest": identity["scheduler_identity_digest"],
            "tier_acceptance_digest": tier_acceptance.get("digest"),
        },
        "provider": {
            "passed": True,
            "model": MODEL,
            "required_provider": PROVIDER,
            "fallbacks_allowed": False,
            "request_count": provider_request_count,
            "replay_count": 0,
        },
        "firewall": {
            "passed": True,
            "worker_proxy_only": True,
            "verifier_networkless": True,
            "formal_residual_resource_count": 0,
        },
        "mirror": {"passed": True, "completed_score_count": len(attempt_ids)},
        "calibration": {
            "digest": calibration_digest,
            "source_run_id": calibration.get("source_run_id"),
            "tolerance": tolerance,
        },
        "selection": {
            "iterations": iterations,
            "kept": sum(item["decision"] == "keep" for item in iterations),
            "rolled_back": sum(
                item["decision"] == "rollback" for item in iterations
            ),
        },
        "train": _delta(train_seed, train_final),
        "validation": _delta(validation_seed, validation_final),
        "primary_test": _delta(test_seed, test_final),
        "diagnostic_test": _delta(diagnostic_seed, diagnostic_final),
    }
    audit["digest"] = _canonical_digest(audit)
    return audit


def _lifecycle_root(run_dir: Path, attempt_id: str) -> Path:
    nested = run_dir / "lifecycles" / run_dir.name / attempt_id
    direct = run_dir / "lifecycles" / attempt_id
    if nested.is_dir():
        return nested
    return direct


def _collect_attempts(run_dir: Path, *, model: str) -> tuple[dict, ...]:
    attempts_root = run_dir / "attempts"
    attempt_paths = tuple(sorted(attempts_root.glob("*/attempt.json")))
    if not attempt_paths:
        raise EvolutionAuditError("formal run has no persisted attempts")
    all_attempts: dict[str, dict] = {}
    for path in attempt_paths:
        attempt = _read_json(path, label="attempt metadata")
        attempt_id = path.parent.name
        if attempt.get("attempt_id") != attempt_id:
            raise EvolutionAuditError("attempt directory identity differs")
        all_attempts[attempt_id] = attempt

    completed = []
    logical_groups: dict[tuple[str, str, str], list[str]] = {}
    for attempt_id, attempt in all_attempts.items():
        checkpoint = _REPLACEMENT_SUFFIX.sub("", str(attempt.get("checkpoint", "")))
        key = (str(attempt.get("split")), checkpoint, str(attempt.get("task_id")))
        logical_groups.setdefault(key, []).append(attempt_id)
        score_path = attempts_root / attempt_id / "completed-score.json"
        if not score_path.is_file():
            continue
        score = _read_json(score_path, label="completed official score")
        tags = score.get("diagnostic_tags", [])
        timeout = isinstance(tags, list) and "timeout" in tags
        attempt_dir = score_path.parent
        request_ids: list[str] = []
        provider_ok = True
        audit_path = attempt_dir / "proxy-audit.jsonl"
        if audit_path.is_file():
            try:
                lines = audit_path.read_text().splitlines()
            except OSError as exc:
                raise EvolutionAuditError("proxy audit is unreadable") from exc
            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise EvolutionAuditError("proxy audit is invalid JSON") from exc
                if not isinstance(record, dict):
                    raise EvolutionAuditError("proxy audit record is invalid")
                identity = record.get("request_identity_sha256")
                if not isinstance(identity, str):
                    raise EvolutionAuditError("provider request identity is missing")
                request_ids.append(identity)
                provider_ok = provider_ok and (
                    record.get("model") == model
                    and record.get("request_state") == "completed"
                    and record.get("upstream_status_code") == 200
                    and record.get("failure_class") is None
                )
        elif not timeout:
            provider_ok = False
        if timeout and not (attempt_dir / "timeout-recovery.json").is_file():
            raise EvolutionAuditError("official timeout recovery evidence is missing")

        lifecycle_root = _lifecycle_root(run_dir, attempt_id)
        proxy_root = run_dir / "lifecycles" / attempt_id
        if not proxy_root.is_dir():
            proxy_root = lifecycle_root
        try:
            worker = load_lifecycle(
                lifecycle_root / "worker-sandbox-lifecycle-v2.json"
            )
            proxy = load_lifecycle(
                proxy_root / "proxy-sandbox-lifecycle-v2.json"
            )
            network = load_network_lifecycle(
                proxy_root / "proxy-network-lifecycle-v1.json"
            )
            verifier = None
            verifier_path = lifecycle_root / "verifier-sandbox-lifecycle-v2.json"
            if verifier_path.is_file():
                verifier = load_lifecycle(verifier_path)
        except (SandboxLifecycleError, SandboxNetworkLifecycleError) as exc:
            raise EvolutionAuditError(
                f"sandbox lifecycle is invalid for {attempt_id}: {exc}"
            ) from exc

        def cleaned(lifecycle, role: str) -> bool:
            return bool(
                lifecycle.role == role
                and lifecycle.run_id == run_dir.name
                and lifecycle.attempt_id == attempt_id
                and lifecycle.cleaned_up
                and lifecycle.cleanup_result in {"killed", "already_absent"}
            )

        completed.append(
            {
                **attempt,
                "checkpoint": checkpoint,
                "score": score,
                "provider_ok": provider_ok,
                "provider_request_identities": request_ids,
                "worker_cleaned": cleaned(worker, "worker"),
                "worker_proxy_only": worker.resource_contract.get("network_policy")
                == "worker-proxy-only",
                "verifier_cleaned": timeout
                or (verifier is not None and cleaned(verifier, "verifier")),
                "verifier_networkless": timeout
                or (
                    verifier is not None
                    and verifier.resource_contract.get("network_policy") == "none"
                ),
                "network_cleaned": bool(
                    cleaned(proxy, "proxy")
                    and proxy.resource_contract.get("network_policy")
                    == "proxy-outbound"
                    and network.run_id == run_dir.name
                    and network.network_scope == attempt_id
                    and network.cleaned_up
                ),
            }
        )

    for (split, checkpoint, task_id), attempt_ids in logical_groups.items():
        completed_ids = [
            attempt_id
            for attempt_id in attempt_ids
            if (attempts_root / attempt_id / "completed-score.json").is_file()
        ]
        if len(completed_ids) != 1:
            raise EvolutionAuditError(
                "logical attempt does not have exactly one completed official score"
            )
        if len(attempt_ids) > 1:
            first = all_attempts[attempt_ids[0]]
            logical_attempt = TaskAttempt.create(
                run_id=str(first["run_id"]),
                benchmark_commit=str(first["benchmark_commit"]),
                task_id=task_id,
                split=split,
                checkpoint=checkpoint,
                worker_digest=str(first["worker_digest"]),
            )
            try:
                terminal = resolve_worker_attempt(logical_attempt, run_dir)
            except Exception as exc:
                raise EvolutionAuditError(
                    "attempt replacement chain is invalid"
                ) from exc
            if terminal.attempt_id != completed_ids[0]:
                raise EvolutionAuditError(
                    "attempt replacement terminal score identity differs"
                )
    return tuple(completed)


def _mirror_attempt_ids(mirror_dir: Path) -> set[str]:
    root = mirror_dir.expanduser().resolve()
    identifiers = set()
    for score_path in root.glob("attempts/*/completed-score.json"):
        if score_path.is_symlink() or not score_path.is_file():
            raise EvolutionAuditError("local mirror score is not a regular file")
        identifiers.add(score_path.parent.name)
    return identifiers


def audit_run(
    run_dir: str | Path,
    *,
    manifest_path: str | Path,
    calibration_path: str | Path,
    tier_acceptance_path: str | Path,
    mirror_dir: str | Path,
    cleanup_audit_path: str | Path,
) -> dict[str, object]:
    root = Path(run_dir).expanduser().resolve()
    if root.name == "" or not root.is_dir():
        raise EvolutionAuditError("formal run directory is unavailable")
    result = _read_json(root / "result.json", label="evolution result")
    resume = _read_json(root / "resume.json", label="evolution resume")
    manifest = _read_json(Path(manifest_path).expanduser().resolve(), label="test manifest")
    calibration = load_validation_calibration(calibration_path).to_dict()
    tier = load_tier_acceptance(tier_acceptance_path).to_dict()
    cleanup = _read_json(
        Path(cleanup_audit_path).expanduser().resolve(),
        label="exact-ID cleanup audit",
    )
    if cleanup.get("run_id") != root.name:
        raise EvolutionAuditError("exact-ID cleanup audit run identity differs")
    residual_count = cleanup.get("residual_resource_count")
    if type(residual_count) is not int:
        raise EvolutionAuditError("exact-ID cleanup residual count is invalid")
    attempts = _collect_attempts(root, model=MODEL)
    return audit_evolution_payloads(
        result=result,
        resume=resume,
        manifest=manifest,
        calibration=calibration,
        tier_acceptance=tier,
        attempts=attempts,
        mirrored_attempt_ids=_mirror_attempt_ids(Path(mirror_dir)),
        formal_residual_resource_count=residual_count,
    )


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(dict(payload), sort_keys=True, indent=2) + "\n")
    os.replace(temporary, destination)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit a complete 30/15/32+8 QFBench evolution run"
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--tier-acceptance", type=Path, required=True)
    parser.add_argument("--mirror-dir", type=Path, required=True)
    parser.add_argument("--cleanup-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    audit = audit_run(
        args.run_dir,
        manifest_path=args.manifest,
        calibration_path=args.calibration,
        tier_acceptance_path=args.tier_acceptance,
        mirror_dir=args.mirror_dir,
        cleanup_audit_path=args.cleanup_audit,
    )
    _write_json(args.output, audit)
    print(json.dumps(audit, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
