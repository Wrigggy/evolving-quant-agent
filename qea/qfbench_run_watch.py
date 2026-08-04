"""Classify bounded QFBench run evidence and stop only validated child PGIDs."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import select
import signal
import stat
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from .attempt_recovery import (
    AttemptRecoveryError,
    REPLACEMENT_MANIFEST,
    read_replacement_manifest,
    replacement_attempt_from_manifest,
    validate_replacement_source,
)
from .evaluation import TaskAttempt
from .process_supervisor import ChildIdentity, SupervisorError
from .qfbench_baseline import BaselineConfigError, validate_timeout_quarantine
from .qfbench_boundary import (
    BoundaryError,
    ProcessIdentity,
    ProcessSnapshot,
    read_process_snapshot,
    validate_process_snapshot,
)


_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_METADATA = 16 * 1024 * 1024
_AUDIT_FIELDS = frozenset(
    {
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
    }
)
_WATCH_CONFIG_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "source_commit",
        "run_dir",
        "state_dir",
        "child_identity_file",
        "command_token",
    }
)


class RunWatchError(RuntimeError):
    """Run evidence or watch process identity is unsafe."""


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_TRUNC
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(descriptor, "w", closefd=True) as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(payload, output, sort_keys=True, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def _read_bytes_with_stat(
    path: Path, *, maximum=_MAX_METADATA
) -> tuple[bytes, os.stat_result]:
    try:
        path_metadata = path.lstat()
    except OSError as exc:
        raise RunWatchError(f"metadata is unavailable: {path}") from exc
    if stat.S_ISLNK(path_metadata.st_mode) or not stat.S_ISREG(
        path_metadata.st_mode
    ):
        raise RunWatchError(f"metadata must be a regular non-symlink file: {path}")
    if path_metadata.st_size > maximum:
        raise RunWatchError(f"metadata exceeds its byte bound: {path}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RunWatchError(f"metadata cannot be opened safely: {path}") from exc
    with os.fdopen(descriptor, "rb", closefd=True) as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise RunWatchError(f"metadata is not a regular file: {path}")
        if (metadata.st_dev, metadata.st_ino) != (
            path_metadata.st_dev,
            path_metadata.st_ino,
        ):
            raise RunWatchError(f"metadata identity changed during open: {path}")
        if metadata.st_size > maximum:
            raise RunWatchError(f"metadata exceeds its byte bound: {path}")
        payload = source.read(maximum + 1)
    if len(payload) > maximum:
        raise RunWatchError(f"metadata exceeds its byte bound: {path}")
    return payload, metadata


def _read_bytes(path: Path, *, maximum=_MAX_METADATA) -> bytes:
    payload, _ = _read_bytes_with_stat(path, maximum=maximum)
    return payload


def _read_json(path: Path) -> tuple[object, bytes]:
    raw = _read_bytes(path)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as exc:
        raise RunWatchError(f"metadata is not valid JSON: {path}") from exc


def _evidence_digest(records: list[tuple[str, bytes]]) -> str:
    manifest = [
        {
            "path": path,
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        for path, raw in sorted(records)
    ]
    return hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class AttemptWatchResult:
    attempt_id: str
    status: str
    hard_stop: bool
    category: str | None
    evidence_sha256: str


def _fatal(attempt_id: str, category: str, records) -> AttemptWatchResult:
    return AttemptWatchResult(
        attempt_id=attempt_id,
        status="hard_stop",
        hard_stop=True,
        category=category,
        evidence_sha256=_evidence_digest(records),
    )


def _lifecycle_records(run_dir: Path, attempt_id: str):
    roots = (
        run_dir / "lifecycles" / run_dir.name / attempt_id,
        run_dir / "attempts" / attempt_id,
    )
    records: list[tuple[str, bytes]] = []
    cleaned: list[bool] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*lifecycle-v*.json")):
            if path in seen:
                continue
            seen.add(path)
            payload, raw = _read_json(path)
            if not isinstance(payload, dict):
                raise RunWatchError(f"lifecycle is not an object: {path}")
            if payload.get("run_id") != run_dir.name:
                raise RunWatchError(f"lifecycle run identity mismatch: {path}")
            cleaned.append(payload.get("cleaned_up") is True)
            records.append((path.relative_to(run_dir).as_posix(), raw))
    return records, cleaned


def _audit_records(path: Path):
    raw = _read_bytes(path)
    records = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RunWatchError("proxy audit JSONL is malformed") from exc
        if not isinstance(record, dict) or set(record) != _AUDIT_FIELDS:
            raise RunWatchError("proxy audit record schema is invalid")
        records.append(record)
    if not records:
        raise RunWatchError("proxy audit has no records")
    return records, raw


def classify_attempt_evidence(
    attempt_dir: str | Path,
    *,
    run_dir: str | Path,
) -> AttemptWatchResult:
    """Classify one attempt using metadata only, never artifacts or verifier data."""

    attempt_source = Path(attempt_dir)
    root = Path(run_dir).resolve()
    attempt_id = attempt_source.name
    records: list[tuple[str, bytes]] = []
    try:
        metadata = attempt_source.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            return _fatal(
                attempt_id,
                "identity_drift",
                [(f"attempts/{attempt_id}", b"invalid-attempt-entry")],
            )
        attempt_root = attempt_source.resolve()
        if attempt_root.parent != root / "attempts":
            return _fatal(
                attempt_id,
                "identity_drift",
                [(f"attempts/{attempt_id}", b"attempt-root-mismatch")],
            )
        attempt, raw_attempt = _read_json(attempt_root / "attempt.json")
        records.append((f"attempts/{attempt_id}/attempt.json", raw_attempt))
        if (
            not isinstance(attempt, dict)
            or attempt.get("attempt_id") != attempt_id
            or attempt.get("run_id") != root.name
        ):
            return _fatal(attempt_id, "identity_drift", records)
        score_path = attempt_root / "completed-score.json"
        audit_path = attempt_root / "proxy-audit.jsonl"
        marker_path = attempt_root / "proxy-audit.quarantined.json"
        if not score_path.exists():
            replacement_path = attempt_root / REPLACEMENT_MANIFEST
            if audit_path.exists() and replacement_path.exists():
                audits, raw_audit = _audit_records(audit_path)
                records.append(
                    (f"attempts/{attempt_id}/proxy-audit.jsonl", raw_audit)
                )
                manifest, raw_manifest = _read_json(replacement_path)
                records.append(
                    (f"attempts/{attempt_id}/{REPLACEMENT_MANIFEST}", raw_manifest)
                )
                validated_manifest = read_replacement_manifest(replacement_path)
                if manifest != validated_manifest:
                    return _fatal(attempt_id, "identity_drift", records)
                validate_replacement_source(attempt_root, validated_manifest)
                logical_attempt = TaskAttempt(**attempt)
                replacement = replacement_attempt_from_manifest(
                    logical_attempt, validated_manifest
                )
                identities = [
                    record.get("request_identity_sha256") for record in audits
                ]
                reason = validated_manifest.get("reason")
                invalid_source = (
                    validated_manifest.get("superseded_attempt_id") != attempt_id
                    or validated_manifest.get("source_audit_sha256")
                    != hashlib.sha256(raw_audit).hexdigest()
                    or len(identities) != len(set(identities))
                )
                if reason == "post_accept_transport":
                    invalid_source = invalid_source or (
                        audits[-1].get("request_state") != "quarantined"
                        or audits[-1].get("failure_class")
                        != "post_accept_transport"
                        or any(
                            record.get("request_state")
                            not in {"completed", "not_accepted"}
                            for record in audits[:-1]
                        )
                    )
                elif reason == "worker_transport_after_completed_audit":
                    command_path = attempt_root / "worker-command.json"
                    command, raw_command = _read_json(command_path)
                    records.append(
                        (
                            f"attempts/{attempt_id}/worker-command.json",
                            raw_command,
                        )
                    )
                    invalid_source = invalid_source or (
                        validated_manifest.get("source_command_sha256")
                        != hashlib.sha256(raw_command).hexdigest()
                        or any(
                            record.get("request_state") != "completed"
                            or record.get("upstream_status_code") != 200
                            or record.get("failure_class") is not None
                            for record in audits
                        )
                        or not isinstance(command, dict)
                    )
                else:
                    invalid_source = True
                if invalid_source:
                    return _fatal(attempt_id, "identity_drift", records)
                replacement_attempt_path = (
                    root
                    / "attempts"
                    / replacement.attempt_id
                    / "attempt.json"
                )
                if replacement_attempt_path.exists():
                    replacement_payload, raw_replacement = _read_json(
                        replacement_attempt_path
                    )
                    records.append(
                        (
                            "attempts/"
                            f"{replacement.attempt_id}/attempt.json",
                            raw_replacement,
                        )
                    )
                    if replacement_payload != asdict(replacement):
                        return _fatal(attempt_id, "identity_drift", records)
                return AttemptWatchResult(
                    attempt_id,
                    "superseded_infrastructure_attempt",
                    False,
                    None,
                    _evidence_digest(records),
                )
            if audit_path.exists() or marker_path.exists():
                return _fatal(attempt_id, "ambiguous_upstream", records)
            return AttemptWatchResult(
                attempt_id,
                "pending",
                False,
                None,
                _evidence_digest(records),
            )
        score, raw_score = _read_json(score_path)
        records.append((f"attempts/{attempt_id}/completed-score.json", raw_score))
        if not isinstance(score, dict) or score.get("task_id") != attempt.get("task_id"):
            return _fatal(attempt_id, "identity_drift", records)
        if audit_path.exists() and marker_path.exists():
            return _fatal(attempt_id, "ambiguous_upstream", records)
        if audit_path.exists():
            audits, raw_audit = _audit_records(audit_path)
            records.append((f"attempts/{attempt_id}/proxy-audit.jsonl", raw_audit))
            seen: set[str] = set()
            for audit in audits:
                identity = audit.get("request_identity_sha256")
                if not isinstance(identity, str) or not _SHA256.fullmatch(identity):
                    return _fatal(attempt_id, "identity_drift", records)
                if identity in seen:
                    return _fatal(attempt_id, "ambiguous_upstream", records)
                seen.add(identity)
                if audit.get("request_state") != "completed":
                    return _fatal(attempt_id, "ambiguous_upstream", records)
                if audit.get("upstream_status_code") == 200 and audit.get(
                    "failure_class"
                ) is not None:
                    return _fatal(attempt_id, "ambiguous_upstream", records)
            return AttemptWatchResult(
                attempt_id,
                "canonical_ledger",
                False,
                None,
                _evidence_digest(records),
            )
        if not marker_path.exists():
            return _fatal(attempt_id, "unsupported_cost_omission", records)
        marker, raw_marker = _read_json(marker_path)
        records.append(
            (f"attempts/{attempt_id}/proxy-audit.quarantined.json", raw_marker)
        )
        if not isinstance(marker, dict):
            return _fatal(attempt_id, "unsupported_cost_omission", records)
        try:
            validate_timeout_quarantine(score, marker, source=attempt_root)
        except BaselineConfigError:
            category = (
                "ambiguous_upstream"
                if marker.get("reason")
                in {"downstream_delivery", "post_accept_transport"}
                else "unsupported_cost_omission"
            )
            return _fatal(attempt_id, category, records)
        lifecycle_records, cleaned = _lifecycle_records(root, attempt_id)
        records.extend(lifecycle_records)
        if len(cleaned) < 3 or not all(cleaned):
            return _fatal(attempt_id, "cleanup_failure", records)
        return AttemptWatchResult(
            attempt_id,
            "timeout_cost_lower_bound",
            False,
            None,
            _evidence_digest(records),
        )
    except (AttemptRecoveryError, RunWatchError, TypeError, ValueError):
        return _fatal(attempt_id, "identity_drift", records)


@dataclass(frozen=True)
class RunWatchObservation:
    hard_stop: bool
    category: str | None
    timeout_cost_lower_bound_paths: tuple[str, ...]
    evidence_sha256: str
    attempts: tuple[AttemptWatchResult, ...]


def observe_run(run_dir: str | Path) -> RunWatchObservation:
    """Observe bounded attempt metadata and atomically publish sanitized state."""

    root = Path(run_dir).resolve()
    if not root.is_dir():
        raise RunWatchError("run directory is unavailable")
    attempts_root = root / "attempts"
    results = (
        tuple(
            classify_attempt_evidence(path, run_dir=root)
            for path in sorted(attempts_root.iterdir())
        )
        if attempts_root.is_dir()
        else ()
    )
    fatal = next((result for result in results if result.hard_stop), None)
    lower_bounds = tuple(
        f"attempts/{result.attempt_id}"
        for result in results
        if result.status == "timeout_cost_lower_bound"
    )
    digest = hashlib.sha256(
        json.dumps(
            [
                {
                    "attempt_id": result.attempt_id,
                    "status": result.status,
                    "hard_stop": result.hard_stop,
                    "category": result.category,
                    "evidence_sha256": result.evidence_sha256,
                }
                for result in results
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    observation = RunWatchObservation(
        hard_stop=fatal is not None,
        category=fatal.category if fatal else None,
        timeout_cost_lower_bound_paths=lower_bounds,
        evidence_sha256=digest,
        attempts=results,
    )
    _atomic_json(
        root / "watch-state.json",
        {
            "schema_version": 1,
            "run_id": root.name,
            "hard_stop": observation.hard_stop,
            "category": observation.category,
            "timeout_cost_lower_bound_count": len(lower_bounds),
            "timeout_cost_lower_bound_paths": list(lower_bounds),
            "evidence_sha256": digest,
        },
    )
    return observation


@dataclass(frozen=True)
class WatchConfig:
    run_id: str
    source_commit: str
    run_dir: Path | str
    state_dir: Path | str
    child_identity_file: Path | str
    command_token: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not _RUN_ID.fullmatch(self.run_id):
            raise RunWatchError("watch run_id is invalid")
        if not isinstance(self.source_commit, str) or not _COMMIT.fullmatch(
            self.source_commit
        ):
            raise RunWatchError("watch source_commit is invalid")
        run_dir = Path(self.run_dir).resolve()
        state_dir = Path(self.state_dir).resolve()
        child_path = Path(self.child_identity_file).resolve()
        if not run_dir.is_dir() or run_dir.name != self.run_id:
            raise RunWatchError("watch run_dir is invalid")
        if not state_dir.is_dir():
            raise RunWatchError("watch state_dir is unavailable")
        if not isinstance(self.command_token, str) or not self.command_token:
            raise RunWatchError("watch command_token is invalid")
        object.__setattr__(self, "run_dir", run_dir)
        object.__setattr__(self, "state_dir", state_dir)
        object.__setattr__(self, "child_identity_file", child_path)


def _load_child(path: Path) -> ChildIdentity:
    raw, metadata = _read_bytes_with_stat(path)
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise RunWatchError("child identity must be owner mode 600")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RunWatchError("child identity is not valid JSON") from exc
    try:
        return ChildIdentity.from_dict(payload)
    except SupervisorError as exc:
        raise RunWatchError(str(exc)) from exc


def run_watch_once(
    config: WatchConfig,
    *,
    process_reader: Callable[[int], ProcessSnapshot] = read_process_snapshot,
    signal_group: Callable[[int, int], None] = os.killpg,
) -> RunWatchObservation:
    """Observe once and terminate only the validated child process group."""

    child = _load_child(config.child_identity_file)
    if child.run_id != config.run_id or child.source_commit != config.source_commit:
        raise RunWatchError("child identity run/source mismatch")
    try:
        snapshot = process_reader(child.pid)
        validate_process_snapshot(
            snapshot,
            expected=ProcessIdentity(
                child.pid,
                child.process_group_id,
                child.uid,
                child.start_ticks,
                child.command_sha256,
            ),
            command_token=config.command_token,
            run_id=config.run_id,
            source_commit=config.source_commit,
            expected_uid=child.uid,
        )
    except (BoundaryError, ProcessLookupError) as exc:
        raise RunWatchError(f"child process identity mismatch: {exc}") from exc
    observation = observe_run(config.run_dir)
    if observation.hard_stop:
        _atomic_json(
            config.state_dir / "hard-stop.json",
            {
                "schema_version": 1,
                "run_id": config.run_id,
                "source_commit": config.source_commit,
                "category": observation.category,
                "evidence_sha256": observation.evidence_sha256,
                "child_process_group_id": child.process_group_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        signal_group(child.process_group_id, signal.SIGTERM)
    return observation


def load_watch_config(path: str | Path) -> WatchConfig:
    config_path = Path(path)
    raw, metadata = _read_bytes_with_stat(config_path, maximum=64 * 1024)
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise RunWatchError("watch config must be owner mode 600")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RunWatchError("watch config is not valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != _WATCH_CONFIG_FIELDS:
        raise RunWatchError("watch config schema is invalid")
    if payload.get("schema_version") != 1:
        raise RunWatchError("watch config schema is unsupported")
    return WatchConfig(
        run_id=payload["run_id"],
        source_commit=payload["source_commit"],
        run_dir=payload["run_dir"],
        state_dir=payload["state_dir"],
        child_identity_file=payload["child_identity_file"],
        command_token=payload["command_token"],
    )


def wait_for_run_event(run_dir: str | Path, *, timeout_seconds: int) -> None:
    """Wait for bounded Linux metadata events, falling back to timed polling."""

    root = Path(run_dir).resolve()
    libc = ctypes.CDLL(None, use_errno=True)
    initialize = getattr(libc, "inotify_init1", None)
    add_watch = getattr(libc, "inotify_add_watch", None)
    if initialize is None or add_watch is None:
        time.sleep(timeout_seconds)
        return
    descriptor = initialize(os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0))
    if descriptor < 0:
        time.sleep(timeout_seconds)
        return
    try:
        mask = 0x00000008 | 0x00000080 | 0x00000100 | 0x00000200
        watched = 0
        for directory, names, _ in os.walk(root, topdown=True, followlinks=False):
            names[:] = [
                name
                for name in names
                if name not in {"artifacts", "tests", "references", "traces"}
            ]
            if add_watch(descriptor, os.fsencode(directory), mask) >= 0:
                watched += 1
        if not watched:
            time.sleep(timeout_seconds)
            return
        poller = select.poll()
        poller.register(descriptor, select.POLLIN)
        poller.poll(timeout_seconds * 1000)
        try:
            os.read(descriptor, 64 * 1024)
        except BlockingIOError:
            pass
    finally:
        os.close(descriptor)


__all__ = [
    "AttemptWatchResult",
    "RunWatchError",
    "RunWatchObservation",
    "WatchConfig",
    "classify_attempt_evidence",
    "load_watch_config",
    "observe_run",
    "run_watch_once",
    "wait_for_run_event",
]
