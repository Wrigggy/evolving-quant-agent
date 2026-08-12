"""Resumable repeated QFBench evaluation of one immutable base worker."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import statistics
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Mapping, Protocol

from .attempt_recovery import (
    AttemptRecoveryError,
    REPLACEMENT_MANIFEST,
    read_replacement_manifest,
    replacement_attempt_from_manifest,
    validate_replacement_source,
)
from .evaluation import (
    EvaluationSummary,
    OfficialTaskScore,
    TaskAttempt,
    aggregate_domain_macro,
)
from .evolve_runtime import snapshot_dir
from .qfbench_scheduler_epochs import (
    SchedulerEpoch,
    SchedulerEpochError,
    epoch_for_repetition,
    sampling_identity,
    validate_scheduler_epochs,
)
from .model_proxy import model_proxy_wire_request_identity
from .worker_identity import WorkerIdentityError, hash_worker_directory


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_BASELINE_CHECKPOINT_RE = re.compile(
    r"^repetition-(?P<repetition>0[1-5])-(?P<panel>primary|diagnostic)$"
)
_PROXY_AUDIT_KEYS = frozenset({
    "schema_version",
    "request_identity_sha256",
    "model",
    "started_at",
    "finished_at",
    "latency_ms",
    "request_state",
    "upstream_status_code",
    "provider_request_id",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "provider_cost_usd",
    "failure_class",
})
_PROXY_AUDIT_V2_KEYS = _PROXY_AUDIT_KEYS | frozenset(
    {"logical_request_identity_sha256", "retry_index"}
)
_RATE_LIMITED = object()
_T_CRITICAL_95 = {
    2: 12.706204736432095,
    3: 4.302652729696142,
    4: 3.182446305284263,
    5: 2.7764451051977987,
}


class BaselineConfigError(ValueError):
    """A baseline run is unsafe or incompatible with its checkpoint."""


class BaselineEvaluator(Protocol):
    def evaluate(
        self, *, worker_dir, tasks, split, checkpoint, run_dir
    ) -> EvaluationSummary: ...


@dataclass(frozen=True)
class BaselineConfig:
    """Immutable identity and storage configuration for a five-repeat baseline."""

    run_id: str
    repetitions: int
    results_dir: Path | str
    seed_worker_dir: Path | str
    model_identity: str
    task_manifest_digest: str
    runtime_identity_digest: str
    scheduler_identity_digest: str
    template_identity_digest: str
    worker_concurrency: int = 4
    verifier_concurrency: int = 3
    resume: bool = True
    scheduler_epochs: tuple[SchedulerEpoch, ...] | None = None

    def __post_init__(self) -> None:
        if not _RUN_ID_RE.fullmatch(self.run_id):
            raise BaselineConfigError("run_id must be a path-safe identifier")
        if self.repetitions != 5:
            raise BaselineConfigError("QFBench repeated baseline requires five repetitions")
        if not self.model_identity.strip():
            raise BaselineConfigError("model_identity must be non-empty")
        for name in (
            "task_manifest_digest",
            "runtime_identity_digest",
            "scheduler_identity_digest",
            "template_identity_digest",
        ):
            if not _SHA256_RE.fullmatch(getattr(self, name)):
                raise BaselineConfigError(f"{name} must be 64 lowercase hex characters")
        for name in ("worker_concurrency", "verifier_concurrency"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise BaselineConfigError(f"{name} must be positive")
        if self.scheduler_epochs is not None:
            try:
                epochs = validate_scheduler_epochs(
                    self.scheduler_epochs,
                    total_repetitions=self.repetitions,
                )
            except SchedulerEpochError as exc:
                raise BaselineConfigError(str(exc)) from exc
            object.__setattr__(self, "scheduler_epochs", epochs)


@dataclass(frozen=True)
class BaselineRepetition:
    repetition: int
    primary: EvaluationSummary
    diagnostic: EvaluationSummary


@dataclass(frozen=True)
class BaselineResult:
    run_id: str
    run_dir: Path
    complete: bool
    repetitions: tuple[BaselineRepetition, ...]
    aggregate: dict
    seed_worker_dir: Path


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _summary_dict(summary: EvaluationSummary) -> dict:
    return {
        "scores": [asdict(score) for score in summary.scores],
        "task_rewards": summary.task_rewards,
        "domain_scores": summary.domain_scores,
        "task_mean": summary.task_mean,
        "overall": summary.overall,
    }


def _summary_from_dict(payload: Mapping) -> EvaluationSummary:
    scores = tuple(
        OfficialTaskScore(
            **{**item, "diagnostic_tags": tuple(item.get("diagnostic_tags", ()))}
        )
        for item in payload["scores"]
    )
    return EvaluationSummary(
        scores=scores,
        task_rewards={
            str(key): float(value) for key, value in payload["task_rewards"].items()
        },
        domain_scores={
            str(key): float(value) for key, value in payload["domain_scores"].items()
        },
        task_mean=float(payload["task_mean"]),
        overall=float(payload["overall"]),
    )


def _task_contract(tasks: tuple) -> list[dict]:
    return [
        {
            "task_id": task.task_id,
            "domain": task.domain,
            "reward_kind": task.reward_kind,
            "resource_source": task.resource_source,
        }
        for task in tasks
    ]


def _identity(
    config: BaselineConfig,
    *,
    worker_digest: str,
    primary_tasks: tuple,
    diagnostic_tasks: tuple,
) -> dict:
    return {
        "model_identity": config.model_identity,
        "task_manifest_digest": config.task_manifest_digest,
        "runtime_identity_digest": config.runtime_identity_digest,
        "scheduler_identity_digest": config.scheduler_identity_digest,
        "template_identity_digest": config.template_identity_digest,
        "worker_concurrency": config.worker_concurrency,
        "verifier_concurrency": config.verifier_concurrency,
        "seed_worker_digest": worker_digest,
        "primary_tasks": _task_contract(primary_tasks),
        "diagnostic_tasks": _task_contract(diagnostic_tasks),
    }


def _require_active_scheduler_epoch(
    config: BaselineConfig,
    *,
    repetition: int,
) -> SchedulerEpoch:
    """Bind the running process to the declared epoch for one repetition."""

    if config.scheduler_epochs is None:
        raise BaselineConfigError("schema v2 resume requires scheduler epochs")
    try:
        epoch = epoch_for_repetition(config.scheduler_epochs, repetition)
    except SchedulerEpochError as exc:
        raise BaselineConfigError(str(exc)) from exc
    active_identity = {
        "worker_concurrency": config.worker_concurrency,
        "verifier_concurrency": config.verifier_concurrency,
        "scheduler_identity_digest": config.scheduler_identity_digest,
        "runtime_identity_digest": config.runtime_identity_digest,
    }
    expected_identity = {
        name: getattr(epoch, name) for name in active_identity
    }
    if active_identity != expected_identity:
        raise BaselineConfigError(
            "active scheduler epoch identity mismatch: "
            f"expected {expected_identity}, found {active_identity}"
        )
    return epoch


def _is_pristine_runtime_scaffold(run_dir: Path) -> bool:
    """Recognize the exact empty scaffold created by the rootless runtime."""

    try:
        run_metadata = run_dir.lstat()
        entries = {entry.name: entry for entry in run_dir.iterdir()}
        if set(entries) != {".coordinator.lock", "lifecycles"}:
            return False
        lock_metadata = entries[".coordinator.lock"].lstat()
        lifecycle_metadata = entries["lifecycles"].lstat()
        return (
            stat.S_ISDIR(run_metadata.st_mode)
            and run_metadata.st_uid == os.geteuid()
            and stat.S_ISREG(lock_metadata.st_mode)
            and stat.S_IMODE(lock_metadata.st_mode) == 0o600
            and lock_metadata.st_uid == os.geteuid()
            and lock_metadata.st_nlink == 1
            and stat.S_ISDIR(lifecycle_metadata.st_mode)
            and stat.S_IMODE(lifecycle_metadata.st_mode) == 0o700
            and lifecycle_metadata.st_uid == os.geteuid()
            and not any(entries["lifecycles"].iterdir())
        )
    except OSError:
        return False


def _validate_tasks(primary_tasks: tuple, diagnostic_tasks: tuple) -> None:
    if not primary_tasks or not diagnostic_tasks:
        raise BaselineConfigError("primary and diagnostic task panels must be non-empty")
    primary_ids = [task.task_id for task in primary_tasks]
    diagnostic_ids = [task.task_id for task in diagnostic_tasks]
    if len(primary_ids) != len(set(primary_ids)):
        raise BaselineConfigError("primary task IDs must be unique")
    if len(diagnostic_ids) != len(set(diagnostic_ids)):
        raise BaselineConfigError("diagnostic task IDs must be unique")
    overlap = set(primary_ids) & set(diagnostic_ids)
    if overlap:
        raise BaselineConfigError(f"task panels overlap: {sorted(overlap)}")


def _series(values: Iterable[float], *, complete: bool) -> dict:
    ordered = tuple(float(value) for value in values)
    if not ordered:
        raise BaselineConfigError("cannot aggregate an empty repetition series")
    mean = statistics.fmean(ordered)
    if len(ordered) == 1:
        sample_sd = None
        standard_error = None
    else:
        sample_sd = statistics.stdev(ordered)
        standard_error = sample_sd / math.sqrt(len(ordered))
    interval = None
    if complete and standard_error is not None:
        critical = _T_CRITICAL_95.get(len(ordered))
        if critical is not None:
            half_width = critical * standard_error
            interval = [mean - half_width, mean + half_width]
    return {
        "n": len(ordered),
        "mean": mean,
        "sample_sd": sample_sd,
        "standard_error": standard_error,
        "confidence_interval_95": interval,
        "values": list(ordered),
    }


def _panel(
    summaries: tuple[EvaluationSummary, ...],
    tasks: tuple,
    *,
    complete: bool,
) -> dict:
    expected = {task.task_id for task in tasks}
    reward_kinds = {task.task_id: task.reward_kind for task in tasks}
    for summary in summaries:
        if set(summary.task_rewards) != expected:
            raise BaselineConfigError("evaluation summary task panel mismatch")

    domains = sorted({task.domain for task in tasks})
    domain_series = {
        domain: _series(
            (summary.domain_scores[domain] for summary in summaries),
            complete=complete,
        )
        for domain in domains
    }
    task_series = {}
    for task_id in sorted(expected):
        values = tuple(summary.task_rewards[task_id] for summary in summaries)
        stats = _series(values, complete=complete)
        if reward_kinds[task_id] == "binary":
            stats["success_count"] = sum(value == 1.0 for value in values)
        task_series[task_id] = stats
    return {
        "task_count": len(tasks),
        "repeat_domain_macro": _series(
            (summary.overall for summary in summaries), complete=complete
        ),
        "repeat_task_mean": _series(
            (summary.task_mean for summary in summaries), complete=complete
        ),
        "domains": domain_series,
        "tasks": task_series,
    }


def aggregate_repetitions(
    primary_repetitions: Iterable[EvaluationSummary],
    diagnostic_repetitions: Iterable[EvaluationSummary],
    *,
    resource_fallback_task_ids: frozenset[str],
    primary_tasks: Iterable,
    diagnostic_tasks: Iterable,
    expected_repetitions: int,
) -> dict:
    """Aggregate independent repeat-level estimates and keep diagnostics separate."""

    primary = tuple(primary_repetitions)
    diagnostic = tuple(diagnostic_repetitions)
    primary_task_tuple = tuple(primary_tasks)
    diagnostic_task_tuple = tuple(diagnostic_tasks)
    if not primary or len(primary) != len(diagnostic):
        raise BaselineConfigError("primary and diagnostic repetitions must be paired")
    if len(primary) > expected_repetitions:
        raise BaselineConfigError("more repetitions recorded than preregistered")
    complete = len(primary) == expected_repetitions

    declared_tasks = tuple(
        task
        for task in primary_task_tuple
        if task.task_id not in resource_fallback_task_ids
    )
    if not declared_tasks:
        raise BaselineConfigError("resource-declared sensitivity panel is empty")
    declared_ids = {task.task_id for task in declared_tasks}
    declared_summaries = tuple(
        aggregate_domain_macro(
            score for score in summary.scores if score.task_id in declared_ids
        )
        for summary in primary
    )

    return {
        "expected_repetitions": expected_repetitions,
        "completed_repetitions": len(primary),
        "complete": complete,
        "primary": _panel(primary, primary_task_tuple, complete=complete),
        "diagnostic": _panel(
            diagnostic, diagnostic_task_tuple, complete=complete
        ),
        "resource_declared_sensitivity": _panel(
            declared_summaries, declared_tasks, complete=complete
        ),
    }


def _empty_cost_group() -> dict:
    return {
        "attempt_count": 0,
        "request_count": 0,
        "completed_request_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "provider_cost_usd": Decimal("0"),
        "_v2_seen": False,
        "_logical_request_identities": set(),
        "_rate_limited_retry_count": 0,
        "_other_nonaccepted_request_count": 0,
    }


def _add_cost(group: dict, record: Mapping, cost: Decimal | object | None) -> None:
    group["request_count"] += 1
    group["_logical_request_identities"].add(
        record[
            "logical_request_identity_sha256"
            if record.get("schema_version") == 2
            else "request_identity_sha256"
        ]
    )
    if record.get("schema_version") == 2:
        group["_v2_seen"] = True
        if cost is _RATE_LIMITED:
            group["_rate_limited_retry_count"] += 1
        elif record["request_state"] == "not_accepted":
            group["_other_nonaccepted_request_count"] += 1
    if record["request_state"] == "completed":
        group["completed_request_count"] += 1
        if cost is None:
            return
        group["input_tokens"] += record["input_tokens"]
        group["output_tokens"] += record["output_tokens"]
        group["total_tokens"] += record["total_tokens"]
        group["provider_cost_usd"] += cost


def _cost_json(group: dict, *, tasks: dict | None = None) -> dict:
    payload = {
        key: (str(value) if key == "provider_cost_usd" else value)
        for key, value in group.items()
        if not key.startswith("_")
    }
    if group.get("_v2_seen"):
        payload.update(
            {
                "logical_request_count": len(
                    group["_logical_request_identities"]
                ),
                "rate_limited_retry_count": group[
                    "_rate_limited_retry_count"
                ],
                "other_nonaccepted_request_count": group[
                    "_other_nonaccepted_request_count"
                ],
            }
        )
    if tasks is not None:
        payload["tasks"] = {
            task_id: _cost_json(task_group)
            for task_id, task_group in sorted(tasks.items())
        }
    return payload


def _read_audit_records(path: Path) -> tuple[dict, ...]:
    if not path.is_file():
        raise BaselineConfigError(f"cost audit missing proxy ledger: {path}")
    records = []
    try:
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("record is not an object")
            records.append(record)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise BaselineConfigError(f"cost audit malformed ledger {path}: {exc}") from exc
    if not records:
        raise BaselineConfigError(f"cost audit empty proxy ledger: {path}")
    return tuple(records)


def _validated_completed_cost(
    record: Mapping, *, source: Path
) -> Decimal | object | None:
    schema_version = record.get("schema_version")
    expected_keys = (
        _PROXY_AUDIT_KEYS if schema_version == 1 else _PROXY_AUDIT_V2_KEYS
    )
    if set(record) != expected_keys or schema_version not in {1, 2}:
        raise BaselineConfigError(f"cost audit invalid record schema: {source}")
    identity = record.get("request_identity_sha256")
    if not isinstance(identity, str) or not _SHA256_RE.fullmatch(identity):
        raise BaselineConfigError(f"cost audit invalid request identity: {source}")
    if schema_version == 2:
        logical = record.get("logical_request_identity_sha256")
        retry_index = record.get("retry_index")
        if (
            not isinstance(logical, str)
            or not _SHA256_RE.fullmatch(logical)
            or type(retry_index) is not int
            or not 0 <= retry_index < 3
            or identity != model_proxy_wire_request_identity(logical, retry_index)
        ):
            raise BaselineConfigError(
                f"cost audit invalid retry identity: {source}"
            )
    state = record.get("request_state")
    status = record.get("upstream_status_code")
    if status == 200 and state != "completed":
        raise BaselineConfigError(
            f"cost audit HTTP-200 request is not completed: {source}"
        )
    if state == "quarantined":
        raise BaselineConfigError(f"cost audit has ambiguous accepted request: {source}")
    if (
        schema_version == 2
        and state == "not_accepted"
        and record.get("failure_class") == "rate_limited"
    ):
        if status != 429 or any(
            record.get(name) is not None
            for name in (
                "provider_request_id",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "provider_cost_usd",
            )
        ):
            raise BaselineConfigError(
                f"cost audit invalid rate-limit accounting: {source}"
            )
        return _RATE_LIMITED
    if state == "not_accepted":
        if status is not None or any(
            record.get(name) is not None
            for name in (
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "provider_cost_usd",
            )
        ):
            raise BaselineConfigError(
                f"cost audit invalid not-accepted accounting: {source}"
            )
        return Decimal("0")
    if state != "completed" or status != 200:
        raise BaselineConfigError(f"cost audit invalid terminal request state: {source}")
    accounting_names = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "provider_cost_usd",
    )
    accounting = tuple(record.get(name) for name in accounting_names)
    if all(value is None for value in accounting):
        if record.get("failure_class") is not None:
            raise BaselineConfigError(
                f"cost audit invalid successful failure class: {source}"
            )
        return None
    if any(value is None for value in accounting):
        raise BaselineConfigError(
            f"cost audit partially missing successful accounting: {source}"
        )
    tokens = []
    for name in ("input_tokens", "output_tokens", "total_tokens"):
        value = record.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise BaselineConfigError(f"cost audit missing successful usage: {source}")
        tokens.append(value)
    if tokens[0] + tokens[1] != tokens[2]:
        raise BaselineConfigError(f"cost audit inconsistent token usage: {source}")
    raw_cost = record.get("provider_cost_usd")
    if isinstance(raw_cost, bool) or not isinstance(raw_cost, (int, float, str)):
        raise BaselineConfigError(f"cost audit missing successful cost: {source}")
    try:
        cost = Decimal(str(raw_cost))
    except InvalidOperation as exc:
        raise BaselineConfigError(f"cost audit invalid successful cost: {source}") from exc
    if not cost.is_finite() or cost < 0:
        raise BaselineConfigError(f"cost audit invalid successful cost: {source}")
    return cost


def _validate_v2_retry_groups(
    records: tuple[dict, ...], *, source: Path
) -> None:
    groups: dict[str, list[Mapping]] = {}
    for record in records:
        if record.get("schema_version") != 2:
            continue
        groups.setdefault(
            str(record.get("logical_request_identity_sha256")), []
        ).append(record)
    for group in groups.values():
        ordered = sorted(group, key=lambda item: int(item.get("retry_index", -1)))
        if [item.get("retry_index") for item in ordered] != list(range(len(ordered))):
            raise BaselineConfigError(
                f"cost audit retry indexes are not contiguous: {source}"
            )
        rate_limited = [
            item
            for item in ordered
            if item.get("request_state") == "not_accepted"
            and item.get("failure_class") == "rate_limited"
        ]
        completed = [
            item for item in ordered if item.get("request_state") == "completed"
        ]
        if rate_limited and (
            ordered[:-1] != rate_limited
            or ordered[-1].get("request_state") != "completed"
            or ordered[-1].get("failure_class") is not None
            or ordered[-1].get("upstream_status_code") != 200
        ):
            raise BaselineConfigError(
                f"cost audit incomplete rate-limit retry group: {source}"
            )
        if not rate_limited and completed and not (
            len(ordered) == 1
            and len(completed) == 1
            and completed[0].get("retry_index") == 0
            and completed[0].get("failure_class") is None
            and completed[0].get("upstream_status_code") == 200
        ):
            raise BaselineConfigError(
                f"cost audit invalid completed retry group: {source}"
            )


def validate_timeout_quarantine(
    score: Mapping,
    marker: Mapping,
    *,
    source: Path | str,
) -> str:
    """Validate the only supported official-timeout cost lower bound."""

    reward = score.get("reward")
    tags = score.get("diagnostic_tags")
    try:
        validated_score = OfficialTaskScore(
            **{
                **score,
                "diagnostic_tags": tuple(tags) if isinstance(tags, list) else tags,
            }
        )
    except (TypeError, ValueError) as exc:
        raise BaselineConfigError(
            f"cost audit invalid timeout score: {source}"
        ) from exc
    if (
        isinstance(reward, bool)
        or not isinstance(reward, (int, float))
        or float(reward) != 0.0
        or not isinstance(tags, list)
        or "timeout" not in validated_score.diagnostic_tags
    ):
        raise BaselineConfigError(
            f"cost audit missing ledger is not bound to a timeout score: {source}"
        )
    legacy = {
        "schema_version": 1,
        "request_state": "quarantined",
        "reason": "audit_download_or_validation_failed",
    }
    enhanced_keys = {
        "schema_version",
        "request_state",
        "reason",
        "accounting_complete",
        "unsealed_audit_sha256",
        "unsealed_record_count",
    }
    enhanced = (
        set(marker) == enhanced_keys
        and marker.get("schema_version") == 2
        and marker.get("request_state") == "quarantined"
        and marker.get("reason") == "audit_download_or_validation_failed"
        and marker.get("accounting_complete") is False
        and isinstance(marker.get("unsealed_audit_sha256"), str)
        and _SHA256_RE.fullmatch(str(marker["unsealed_audit_sha256"]))
        is not None
        and type(marker.get("unsealed_record_count")) is int
        and 0 <= int(marker["unsealed_record_count"]) <= 10_000
    )
    if marker != legacy and not enhanced:
        raise BaselineConfigError(
            f"cost audit unsupported quarantine marker: {source}"
        )
    return str(marker["reason"])


def _validated_timeout_quarantine(
    score: Mapping,
    marker_path: Path,
    *,
    source: Path,
) -> tuple[str, tuple[dict, ...] | None]:
    try:
        marker = json.loads(marker_path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BaselineConfigError(
            f"cost audit missing or malformed quarantine marker: {source}"
        ) from exc
    if not isinstance(marker, Mapping):
        raise BaselineConfigError(
            f"cost audit missing or malformed quarantine marker: {source}"
        )
    reason = validate_timeout_quarantine(score, marker, source=source)
    unsealed_path = marker_path.with_name("proxy-audit.unsealed.jsonl")
    if marker.get("schema_version") == 1:
        if unsealed_path.exists() or unsealed_path.is_symlink():
            raise BaselineConfigError(
                f"cost audit legacy quarantine has an unbound ledger: {source}"
            )
        return reason, None
    if unsealed_path.is_symlink() or not unsealed_path.is_file():
        raise BaselineConfigError(
            f"cost audit unsealed ledger is unavailable: {source}"
        )
    try:
        payload = unsealed_path.read_bytes()
    except OSError as exc:
        raise BaselineConfigError(
            f"cost audit unsealed ledger is unavailable: {source}"
        ) from exc
    if hashlib.sha256(payload).hexdigest() != marker.get(
        "unsealed_audit_sha256"
    ):
        raise BaselineConfigError(
            f"cost audit unsealed ledger digest differs: {source}"
        )
    expected_records = int(marker["unsealed_record_count"])
    if expected_records == 0:
        if payload != b"":
            raise BaselineConfigError(
                f"cost audit zero-count unsealed ledger is nonempty: {source}"
            )
        records = ()
    else:
        records = _read_audit_records(unsealed_path)
    if len(records) != expected_records:
        raise BaselineConfigError(
            f"cost audit unsealed ledger count differs: {source}"
        )
    return reason, records


def audit_baseline_proxy_costs(
    run_dir: str | Path,
    *,
    expected_attempts: int,
    _fixed_checkpoint: str | None = None,
    _fixed_checkpoints: tuple[str, ...] | None = None,
    _fixed_split: str | None = None,
) -> dict:
    """Strictly reconcile safe proxy ledgers against scored baseline attempts."""

    if isinstance(expected_attempts, bool) or expected_attempts < 1:
        raise BaselineConfigError("cost audit expected_attempts must be positive")
    if _fixed_checkpoint is not None and _fixed_checkpoints is not None:
        raise BaselineConfigError("cost audit fixed identity is ambiguous")
    fixed_checkpoints = (
        (_fixed_checkpoint,) if _fixed_checkpoint is not None else _fixed_checkpoints
    )
    if (fixed_checkpoints is None) != (_fixed_split is None):
        raise BaselineConfigError("cost audit fixed identity is incomplete")
    if fixed_checkpoints is not None and (
        not fixed_checkpoints
        or len(fixed_checkpoints) != len(set(fixed_checkpoints))
        or any(
            not isinstance(checkpoint, str) or not checkpoint.strip()
            for checkpoint in fixed_checkpoints
        )
    ):
        raise BaselineConfigError("cost audit fixed checkpoints are invalid")
    root = Path(run_dir).resolve()
    attempt_paths = tuple(sorted((root / "attempts").glob("*/attempt.json")))
    attempts: dict[str, tuple[Path, dict, TaskAttempt]] = {}
    for attempt_path in attempt_paths:
        attempt_dir = attempt_path.parent
        try:
            payload = json.loads(attempt_path.read_text())
            attempt = TaskAttempt(**payload)
        except (OSError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise BaselineConfigError(
                f"cost audit invalid attempt identity {attempt_dir.name}: {exc}"
            ) from exc
        if asdict(attempt) != payload or attempt.attempt_id != attempt_dir.name:
            raise BaselineConfigError(
                f"cost audit attempt identity mismatch: {attempt_dir}"
            )
        attempts[attempt.attempt_id] = (attempt_path, payload, attempt)

    superseded: dict[str, dict] = {}
    logical_by_attempt: dict[str, TaskAttempt] = {
        attempt_id: record[2] for attempt_id, record in attempts.items()
    }
    replacement_targets: set[str] = set()
    try:
        for attempt_id, (attempt_path, _, _) in attempts.items():
            manifest_path = attempt_path.parent / REPLACEMENT_MANIFEST
            if not manifest_path.exists():
                continue
            manifest = read_replacement_manifest(manifest_path)
            validate_replacement_source(attempt_path.parent, manifest)
            if manifest["superseded_attempt_id"] != attempt_id:
                raise BaselineConfigError(
                    f"cost audit replacement source mismatch: {attempt_path.parent}"
                )
            logical_record = attempts.get(manifest["logical_attempt_id"])
            replacement_record = attempts.get(manifest["replacement_attempt_id"])
            if logical_record is None or replacement_record is None:
                raise BaselineConfigError(
                    f"cost audit replacement lineage is incomplete: {attempt_path.parent}"
                )
            logical_attempt = logical_record[2]
            replacement = replacement_attempt_from_manifest(
                logical_attempt, manifest
            )
            if replacement_record[2] != replacement:
                raise BaselineConfigError(
                    f"cost audit replacement identity mismatch: {attempt_path.parent}"
                )
            audit_path = attempt_path.parent / "proxy-audit.jsonl"
            try:
                raw_audit = audit_path.read_bytes()
            except OSError as exc:
                raise BaselineConfigError(
                    f"cost audit replacement source ledger is unavailable: {attempt_path.parent}"
                ) from exc
            if hashlib.sha256(raw_audit).hexdigest() != manifest[
                "source_audit_sha256"
            ]:
                raise BaselineConfigError(
                    f"cost audit replacement source ledger drifted: {attempt_path.parent}"
                )
            if replacement.attempt_id in replacement_targets:
                raise BaselineConfigError(
                    "cost audit replacement lineage has multiple predecessors"
                )
            replacement_targets.add(replacement.attempt_id)
            superseded[attempt_id] = manifest
            logical_by_attempt[attempt_id] = logical_attempt
            logical_by_attempt[replacement.attempt_id] = logical_attempt
    except AttemptRecoveryError as exc:
        raise BaselineConfigError(str(exc)) from exc

    terminal_attempt_ids = set(attempts) - set(superseded)
    if len(terminal_attempt_ids) != expected_attempts:
        raise BaselineConfigError(
            "cost audit scored attempt count mismatch: "
            f"expected {expected_attempts}, found {len(terminal_attempt_ids)}"
        )

    total = _empty_cost_group()
    repetition_groups: dict[str, dict[str, dict]] = {}
    unreconciled_attempts: list[dict] = []
    unreconciled_requests: list[dict] = []
    for attempt_path in attempt_paths:
        attempt_dir = attempt_path.parent
        attempt_id = attempt_dir.name
        _, attempt, _ = attempts[attempt_id]
        logical_attempt = logical_by_attempt[attempt_id]
        is_superseded = attempt_id in superseded
        try:
            score = (
                None
                if is_superseded
                else json.loads((attempt_dir / "completed-score.json").read_text())
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise BaselineConfigError(
                f"cost audit missing or invalid scored attempt {attempt_dir.name}: {exc}"
            ) from exc
        if (
            not isinstance(attempt, dict)
            or (not is_superseded and not isinstance(score, dict))
            or attempt.get("attempt_id") != attempt_dir.name
        ):
            raise BaselineConfigError(f"cost audit attempt identity mismatch: {attempt_dir}")
        if is_superseded and (attempt_dir / "completed-score.json").exists():
            raise BaselineConfigError(
                f"cost audit superseded attempt must not be scored: {attempt_dir}"
            )
        task_id = logical_attempt.task_id
        if (
            not isinstance(task_id, str)
            or (not is_superseded and score.get("task_id") != task_id)
        ):
            raise BaselineConfigError(f"cost audit score identity mismatch: {attempt_dir}")
        if fixed_checkpoints is not None:
            if (
                logical_attempt.checkpoint not in fixed_checkpoints
                or logical_attempt.split != _fixed_split
            ):
                raise BaselineConfigError(
                    f"cost audit fixed checkpoint/split mismatch: {attempt_dir}"
                )
            repetition = "fixed"
            panel = (
                "fixed"
                if len(fixed_checkpoints) == 1
                else logical_attempt.checkpoint
            )
        else:
            match = _BASELINE_CHECKPOINT_RE.fullmatch(
                logical_attempt.checkpoint
            )
            if match is None:
                raise BaselineConfigError(
                    f"cost audit checkpoint outside baseline: {attempt_dir}"
                )
            repetition = str(int(match.group("repetition")))
            panel = match.group("panel")
            if logical_attempt.split != f"baseline_{panel}":
                raise BaselineConfigError(
                    f"cost audit split/checkpoint mismatch: {attempt_dir}"
                )

        panel_group = repetition_groups.setdefault(repetition, {}).setdefault(
            panel,
            {**_empty_cost_group(), "tasks": {}},
        )
        task_group = panel_group["tasks"].setdefault(task_id, _empty_cost_group())
        if not is_superseded:
            total["attempt_count"] += 1
            panel_group["attempt_count"] += 1
            task_group["attempt_count"] += 1
        audit_path = attempt_dir / "proxy-audit.jsonl"
        quarantine_path = attempt_dir / "proxy-audit.quarantined.json"
        unsealed_path = attempt_dir / "proxy-audit.unsealed.jsonl"
        if audit_path.is_file() and quarantine_path.exists():
            raise BaselineConfigError(
                f"cost audit has both canonical and quarantined ledgers: {attempt_dir}"
            )
        if audit_path.is_file() and unsealed_path.exists():
            raise BaselineConfigError(
                f"cost audit has both canonical and unsealed ledgers: {attempt_dir}"
            )
        audit_records: tuple[dict, ...]
        if not audit_path.is_file():
            if is_superseded:
                raise BaselineConfigError(
                    f"cost audit superseded attempt is missing its ledger: {attempt_dir}"
                )
            reason, unsealed_records = _validated_timeout_quarantine(
                score,
                quarantine_path,
                source=attempt_dir,
            )
            unreconciled_attempt = {
                "attempt_id": attempt_dir.name,
                "checkpoint": str(attempt["checkpoint"]),
                "task_id": task_id,
                "reason": reason,
            }
            if repetition != "fixed":
                unreconciled_attempt.update(
                    {"panel": panel, "repetition": int(repetition)}
            )
            unreconciled_attempts.append(unreconciled_attempt)
            if unsealed_records is None:
                continue
            audit_records = unsealed_records
        else:
            audit_records = _read_audit_records(audit_path)
        _validate_v2_retry_groups(audit_records, source=attempt_dir)
        seen_request_identities: set[str] = set()
        for record_index, record in enumerate(audit_records):
            if is_superseded and record.get("request_state") == "quarantined":
                manifest = superseded[attempt_id]
                if (
                    record_index != len(audit_records) - 1
                    or set(record) != _PROXY_AUDIT_KEYS
                    or record.get("schema_version") != 1
                    or record.get("failure_class") != manifest["reason"]
                ):
                    raise BaselineConfigError(
                        f"cost audit invalid superseded quarantine: {attempt_dir}"
                    )
                request_identity = record.get("request_identity_sha256")
                if (
                    not isinstance(request_identity, str)
                    or not _SHA256_RE.fullmatch(request_identity)
                ):
                    raise BaselineConfigError(
                        f"cost audit invalid request identity: {attempt_dir}"
                    )
                cost = None
            else:
                cost = _validated_completed_cost(record, source=attempt_dir)
            request_identity = record["request_identity_sha256"]
            if request_identity in seen_request_identities:
                raise BaselineConfigError(
                    f"cost audit duplicate request identity: {request_identity}"
                )
            seen_request_identities.add(request_identity)
            if is_superseded and record.get("request_state") == "quarantined":
                unreconciled_request = {
                    "attempt_id": attempt_dir.name,
                    "checkpoint": logical_attempt.checkpoint,
                    "request_identity_sha256": request_identity,
                    "task_id": task_id,
                    "reason": str(record["failure_class"]),
                }
                if repetition != "fixed":
                    unreconciled_request.update(
                        {"panel": panel, "repetition": int(repetition)}
                    )
                unreconciled_requests.append(unreconciled_request)
            elif cost is None:
                unreconciled_request = {
                    "attempt_id": attempt_dir.name,
                    "checkpoint": logical_attempt.checkpoint,
                    "request_identity_sha256": request_identity,
                    "task_id": task_id,
                    "reason": "successful_response_usage_unavailable",
                }
                if repetition != "fixed":
                    unreconciled_request.update(
                        {"panel": panel, "repetition": int(repetition)}
                    )
                unreconciled_requests.append(unreconciled_request)
            _add_cost(total, record, cost)
            _add_cost(panel_group, record, cost)
            _add_cost(task_group, record, cost)

    payload = _cost_json(total)
    payload["superseded_attempt_count"] = len(superseded)
    has_unreconciled = bool(unreconciled_attempts or unreconciled_requests)
    payload["cost_complete"] = not has_unreconciled
    payload["provider_cost_is_lower_bound"] = has_unreconciled
    payload["unreconciled_attempt_count"] = len(unreconciled_attempts)
    payload["unreconciled_attempts"] = unreconciled_attempts
    payload["unreconciled_request_count"] = len(unreconciled_requests)
    payload["unreconciled_requests"] = unreconciled_requests
    payload["by_repetition"] = {
        repetition: {
            panel: _cost_json(group, tasks=group.pop("tasks"))
            for panel, group in sorted(panels.items())
        }
        for repetition, panels in sorted(
            repetition_groups.items(),
            key=lambda item: (
                0 if item[0].isdigit() else 1,
                int(item[0]) if item[0].isdigit() else item[0],
            ),
        )
    }
    return payload


def audit_fixed_checkpoint_proxy_costs(
    run_dir: str | Path,
    *,
    expected_attempts: int,
    checkpoint: str,
    split: str,
) -> dict:
    """Run the canonical proxy-cost audit for one exact non-repetition panel."""

    if not isinstance(checkpoint, str) or not checkpoint.strip():
        raise BaselineConfigError("cost audit fixed checkpoint must be non-empty")
    if not isinstance(split, str) or not split.strip():
        raise BaselineConfigError("cost audit fixed split must be non-empty")
    payload = audit_baseline_proxy_costs(
        run_dir,
        expected_attempts=expected_attempts,
        _fixed_checkpoint=checkpoint,
        _fixed_split=split,
    )
    payload.pop("by_repetition", None)
    payload["checkpoint"] = checkpoint
    payload["split"] = split
    return payload


def audit_fixed_checkpoints_proxy_costs(
    run_dir: str | Path,
    *,
    expected_attempts: int,
    checkpoints: Iterable[str],
    split: str,
) -> dict:
    """Run one canonical cost audit across exact component checkpoints."""

    normalized = tuple(checkpoints)
    if (
        not normalized
        or len(normalized) != len(set(normalized))
        or any(
            not isinstance(checkpoint, str) or not checkpoint.strip()
            for checkpoint in normalized
        )
    ):
        raise BaselineConfigError("cost audit fixed checkpoints are invalid")
    if not isinstance(split, str) or not split.strip():
        raise BaselineConfigError("cost audit fixed split must be non-empty")
    payload = audit_baseline_proxy_costs(
        run_dir,
        expected_attempts=expected_attempts,
        _fixed_checkpoints=normalized,
        _fixed_split=split,
    )
    payload.pop("by_repetition", None)
    payload["checkpoints"] = list(normalized)
    payload["split"] = split
    return payload


def _records_from_state(state: Mapping) -> tuple[BaselineRepetition, ...]:
    return tuple(
        BaselineRepetition(
            repetition=int(record["repetition"]),
            primary=_summary_from_dict(record["primary"]),
            diagnostic=_summary_from_dict(record["diagnostic"]),
        )
        for record in state["completed"]
    )


def _require_seed_worker_digest(seed_worker: Path, expected_digest: str) -> None:
    try:
        actual_digest = hash_worker_directory(seed_worker)
    except WorkerIdentityError as exc:
        raise BaselineConfigError(str(exc)) from exc
    if actual_digest != expected_digest:
        raise BaselineConfigError(
            "seed worker snapshot digest mismatch: "
            f"expected {expected_digest}, found {actual_digest}"
        )


def _result(
    config: BaselineConfig,
    *,
    run_dir: Path,
    seed_worker_dir: Path,
    state: dict,
    primary_tasks: tuple,
    diagnostic_tasks: tuple,
) -> BaselineResult:
    repetitions = _records_from_state(state)
    aggregate = aggregate_repetitions(
        (record.primary for record in repetitions),
        (record.diagnostic for record in repetitions),
        resource_fallback_task_ids=frozenset(
            task.task_id
            for task in primary_tasks
            if task.resource_source == "qea_fallback"
        ),
        primary_tasks=primary_tasks,
        diagnostic_tasks=diagnostic_tasks,
        expected_repetitions=config.repetitions,
    )
    result = BaselineResult(
        run_id=config.run_id,
        run_dir=run_dir,
        complete=aggregate["complete"],
        repetitions=repetitions,
        aggregate=aggregate,
        seed_worker_dir=seed_worker_dir,
    )
    payload = {
        "run_id": result.run_id,
        "complete": result.complete,
        "seed_worker_dir": seed_worker_dir.relative_to(run_dir).as_posix(),
        "repetitions": [
            {
                "repetition": record.repetition,
                "primary": _summary_dict(record.primary),
                "diagnostic": _summary_dict(record.diagnostic),
            }
            for record in repetitions
        ],
        "aggregate": aggregate,
    }
    if state.get("schema_version") == 2:
        payload["scheduler_epochs"] = state["scheduler_epochs"]
        active_epoch = _require_active_scheduler_epoch(
            config,
            repetition=min(
                int(state["next_repetition"]), config.repetitions
            ),
        )
        payload["active_scheduler_epoch_index"] = (
            config.scheduler_epochs.index(active_epoch) + 1
        )
    _atomic_json(run_dir / "result.json", payload)
    return result


def run_qfbench_baseline(
    config: BaselineConfig,
    *,
    primary_tasks: Iterable,
    diagnostic_tasks: Iterable,
    benchmark_commit: str,
    evaluator: BaselineEvaluator,
    stop_after_repetition: int | None = None,
) -> BaselineResult:
    """Evaluate an immutable seed worker, checkpointing after every panel."""

    if not _COMMIT_RE.fullmatch(benchmark_commit):
        raise BaselineConfigError("benchmark_commit must be a full lowercase SHA")
    if stop_after_repetition is not None and not (
        1 <= stop_after_repetition <= config.repetitions
    ):
        raise BaselineConfigError("stop_after_repetition must be between 1 and 5")
    primary = tuple(primary_tasks)
    diagnostic = tuple(diagnostic_tasks)
    _validate_tasks(primary, diagnostic)
    source_worker = Path(config.seed_worker_dir).resolve()
    try:
        worker_digest = hash_worker_directory(source_worker)
    except WorkerIdentityError as exc:
        raise BaselineConfigError(str(exc)) from exc

    run_dir = Path(config.results_dir).resolve() / config.run_id
    resume_path = run_dir / "resume.json"
    seed_worker = run_dir / "workers" / "seed"
    identity = _identity(
        config,
        worker_digest=worker_digest,
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
    )

    pristine_runtime_scaffold = (
        run_dir.exists()
        and not resume_path.exists()
        and _is_pristine_runtime_scaffold(run_dir)
    )
    if run_dir.exists() and not pristine_runtime_scaffold:
        if not config.resume:
            raise BaselineConfigError(f"run directory already exists: {run_dir}")
        if not resume_path.is_file():
            raise BaselineConfigError("existing run has no resume checkpoint")
        try:
            state = json.loads(resume_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise BaselineConfigError(f"invalid resume checkpoint: {exc}") from exc
        expected_checkpoint = {
            "run_id": config.run_id,
            "benchmark_commit": benchmark_commit,
            "total_repetitions": config.repetitions,
        }
        actual_checkpoint = {
            key: state.get(key) for key in expected_checkpoint
        }
        if actual_checkpoint != expected_checkpoint:
            raise BaselineConfigError(
                "resume checkpoint mismatch: "
                f"expected {expected_checkpoint}, found {actual_checkpoint}"
            )
        schema_version = state.get("schema_version")
        if schema_version == 1:
            if state.get("identity") != identity:
                raise BaselineConfigError("resume immutable identity mismatch")
        elif schema_version == 2:
            if config.scheduler_epochs is None:
                raise BaselineConfigError(
                    "schema v2 resume requires scheduler epochs"
                )
            serialized_epochs = [
                epoch.to_dict() for epoch in config.scheduler_epochs
            ]
            if state.get("scheduler_epochs") != serialized_epochs:
                raise BaselineConfigError("resume scheduler epochs mismatch")
            try:
                expected_sampling_identity = sampling_identity(identity)
            except SchedulerEpochError as exc:
                raise BaselineConfigError(str(exc)) from exc
            if state.get("sampling_identity") != expected_sampling_identity:
                raise BaselineConfigError("resume immutable identity mismatch")
            if state.get("phase") == "calibration_stop":
                raise BaselineConfigError(
                    "schema v2 checkpoint cannot use calibration_stop phase"
                )
            next_repetition = min(
                int(state.get("next_repetition", 0)), config.repetitions
            )
            _require_active_scheduler_epoch(
                config,
                repetition=next_repetition,
            )
        else:
            raise BaselineConfigError(
                f"resume checkpoint schema version is unsupported: {schema_version}"
            )
        if not seed_worker.is_dir():
            raise BaselineConfigError("resume seed worker snapshot is missing")
        _require_seed_worker_digest(seed_worker, worker_digest)
        if schema_version == 1 and state.get("phase") == "calibration_stop":
            state["phase"] = "primary"
            _atomic_json(resume_path, state)
    else:
        run_dir.mkdir(parents=True, exist_ok=pristine_runtime_scaffold)
        snapshot_dir(source_worker, seed_worker)
        _require_seed_worker_digest(seed_worker, worker_digest)
        state = {
            "schema_version": 1,
            "run_id": config.run_id,
            "benchmark_commit": benchmark_commit,
            "total_repetitions": config.repetitions,
            "identity": identity,
            "phase": "primary",
            "next_repetition": 1,
            "pending_primary": None,
            "completed": [],
        }
        _atomic_json(resume_path, state)

    while state["next_repetition"] <= config.repetitions:
        repetition = int(state["next_repetition"])
        if state.get("schema_version") == 2:
            _require_active_scheduler_epoch(config, repetition=repetition)
        if state["phase"] == "primary":
            _require_seed_worker_digest(seed_worker, worker_digest)
            primary_summary = evaluator.evaluate(
                worker_dir=seed_worker,
                tasks=primary,
                split="baseline_primary",
                checkpoint=f"repetition-{repetition:02d}-primary",
                run_dir=run_dir,
            )
            state["pending_primary"] = _summary_dict(primary_summary)
            state["phase"] = "diagnostic"
            _atomic_json(resume_path, state)
        if state["phase"] == "diagnostic":
            _require_seed_worker_digest(seed_worker, worker_digest)
            diagnostic_summary = evaluator.evaluate(
                worker_dir=seed_worker,
                tasks=diagnostic,
                split="baseline_diagnostic",
                checkpoint=f"repetition-{repetition:02d}-diagnostic",
                run_dir=run_dir,
            )
            state["completed"].append(
                {
                    "repetition": repetition,
                    "primary": state["pending_primary"],
                    "diagnostic": _summary_dict(diagnostic_summary),
                }
            )
            state["pending_primary"] = None
            state["next_repetition"] = repetition + 1
            if repetition == config.repetitions:
                state["phase"] = "complete"
            elif (
                stop_after_repetition is not None
                and repetition >= stop_after_repetition
            ):
                state["phase"] = "calibration_stop"
            else:
                state["phase"] = "primary"
            _atomic_json(resume_path, state)
        if state["phase"] in {"calibration_stop", "complete"}:
            break

    return _result(
        config,
        run_dir=run_dir,
        seed_worker_dir=seed_worker,
        state=state,
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
    )
