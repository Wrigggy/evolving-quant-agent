#!/usr/bin/env python3
"""Observe one QFBench coordinator and freeze a sanitized failure incident."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.repair_supervisor import (  # noqa: E402
    ExpectedIdentity,
    Incident,
    IncidentState,
    IncidentStore,
    SupervisorPolicyError,
)
from qea.process_supervisor import ChildIdentity, SupervisorError  # noqa: E402
from qea.qfbench_boundary import (  # noqa: E402
    BoundaryError,
    ProcessIdentity,
    ProcessSnapshot,
    read_process_snapshot,
    validate_process_snapshot,
)


_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
_MAX_LOG_BYTES = 32 * 1024 * 1024
_MAX_EXCERPT_BYTES = 8192
_REDACT_MARKERS = (
    b"api_key",
    b"api-key",
    b"authorization:",
    b"bearer ",
    b"token=",
    b".env",
    b"credentials",
    b"secret",
)


class SentinelError(RuntimeError):
    """The deterministic sentinel cannot safely observe its configured run."""


@dataclass(frozen=True)
class SentinelConfig:
    run_id: str
    run_dir: Path
    supervisor_dir: Path
    source_commit: str
    expected_identity: ExpectedIdentity
    coordinator_pid_file: Path
    coordinator_command_token: str
    exit_code_file: Path
    failure_log: Path
    completion_marker: Path
    state_dir: Path
    child_identity_file: Path | None = None


def _regular_config_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise SentinelError(f"config path is a symlink: {candidate}")
    try:
        mode = candidate.stat().st_mode
    except OSError as exc:
        raise SentinelError(f"config is unavailable: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise SentinelError("config must be a regular file")
    return candidate.resolve()


def _owned_path(value: object, root: Path, root_label: str, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SentinelError(f"{label} must be a path string")
    candidate = Path(value).expanduser()
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise SentinelError(f"{label} must stay below {root_label}")
    return candidate


def load_config(path: str | Path) -> SentinelConfig:
    """Load an exact sentinel configuration with bounded evidence roots."""

    config_path = _regular_config_path(path)
    try:
        payload = json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SentinelError(f"config is unreadable: {exc}") from exc
    expected_v1 = {
        "schema_version",
        "run_id",
        "run_dir",
        "source_commit",
        "expected_identity",
        "coordinator_pid_file",
        "coordinator_command_token",
        "exit_code_file",
        "failure_log",
        "completion_marker",
        "state_dir",
    }
    expected_v2 = expected_v1 | {"supervisor_dir"}
    expected_v3 = expected_v2 | {"child_identity_file"}
    if not isinstance(payload, dict):
        raise SentinelError("sentinel config schema is invalid")
    version = payload.get("schema_version")
    if (version == 1 and set(payload) != expected_v1) or (
        version == 2 and set(payload) != expected_v2
    ) or (
        version == 3 and set(payload) != expected_v3
    ):
        raise SentinelError("sentinel config schema is invalid")
    if version not in {1, 2, 3}:
        raise SentinelError("sentinel config schema version is unsupported")
    run_id = payload["run_id"]
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise SentinelError("run_id is invalid")
    source_commit = payload["source_commit"]
    if not isinstance(source_commit, str) or not _GIT_SHA.fullmatch(source_commit):
        raise SentinelError("source_commit must be a full lowercase Git SHA")
    run_dir_value = payload["run_dir"]
    if not isinstance(run_dir_value, str):
        raise SentinelError("run_dir must be a path string")
    run_dir = Path(run_dir_value).expanduser().resolve()
    if not run_dir.is_dir():
        raise SentinelError("run_dir is unavailable")
    if version in {2, 3}:
        supervisor_value = payload["supervisor_dir"]
        if not isinstance(supervisor_value, str):
            raise SentinelError("supervisor_dir must be a path string")
        supervisor_candidate = Path(supervisor_value).expanduser()
        if supervisor_candidate.is_symlink():
            raise SentinelError("supervisor_dir must not be a symlink")
        supervisor_dir = supervisor_candidate.resolve()
        if not supervisor_dir.is_dir():
            raise SentinelError("supervisor_dir is unavailable")
    else:
        supervisor_dir = run_dir
    command_token = payload["coordinator_command_token"]
    if (
        not isinstance(command_token, str)
        or not command_token
        or len(command_token) > 128
        or any(ord(character) < 0x21 or ord(character) > 0x7E for character in command_token)
    ):
        raise SentinelError("coordinator command token is invalid")
    state_value = payload["state_dir"]
    if not isinstance(state_value, str) or not state_value:
        raise SentinelError("state_dir must be a path string")
    try:
        expected_identity = ExpectedIdentity.from_dict(payload["expected_identity"])
    except SupervisorPolicyError as exc:
        raise SentinelError(f"expected identity is invalid: {exc}") from exc
    return SentinelConfig(
        run_id=run_id,
        run_dir=run_dir,
        supervisor_dir=supervisor_dir,
        source_commit=source_commit,
        expected_identity=expected_identity,
        coordinator_pid_file=_owned_path(
            payload["coordinator_pid_file"],
            supervisor_dir,
            "supervisor_dir" if version in {2, 3} else "run_dir",
            "coordinator_pid_file",
        ),
        coordinator_command_token=command_token,
        exit_code_file=_owned_path(
            payload["exit_code_file"],
            supervisor_dir,
            "supervisor_dir" if version in {2, 3} else "run_dir",
            "exit_code_file",
        ),
        failure_log=_owned_path(
            payload["failure_log"],
            supervisor_dir,
            "supervisor_dir" if version in {2, 3} else "run_dir",
            "failure_log",
        ),
        completion_marker=_owned_path(
            payload["completion_marker"],
            supervisor_dir,
            "supervisor_dir" if version in {2, 3} else "run_dir",
            "completion_marker",
        ),
        state_dir=Path(state_value).expanduser().resolve(),
        child_identity_file=(
            _owned_path(
                payload["child_identity_file"],
                supervisor_dir,
                "supervisor_dir",
                "child_identity_file",
            )
            if version == 3
            else None
        ),
    )


def _read_regular(path: Path, label: str, *, maximum: int) -> bytes:
    if path.is_symlink():
        raise SentinelError(f"{label} is a symlink")
    try:
        metadata = path.stat()
    except OSError as exc:
        raise SentinelError(f"{label} is unavailable: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise SentinelError(f"{label} must be a regular file")
    if metadata.st_size > maximum:
        raise SentinelError(f"{label} exceeds its byte bound")
    return path.read_bytes()


def _default_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _default_pid_command(pid: int) -> str:
    try:
        payload = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return ""
    return payload.replace(b"\x00", b" ").decode("utf-8", errors="replace")


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    payload = _read_regular(path, "coordinator pid", maximum=32)
    try:
        value = int(payload.decode().strip())
    except (UnicodeDecodeError, ValueError) as exc:
        raise SentinelError("coordinator pid is invalid") from exc
    if value < 2:
        raise SentinelError("coordinator pid is invalid")
    return value


def _read_child_identity(path: Path) -> ChildIdentity:
    payload = _read_regular(path, "child identity", maximum=4096)
    metadata = path.stat()
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise SentinelError("child identity must be owner-controlled mode 600")
    try:
        decoded = json.loads(payload)
        return ChildIdentity.from_dict(decoded)
    except (json.JSONDecodeError, SupervisorError) as exc:
        raise SentinelError(f"child identity is invalid: {exc}") from exc


def _freeze_orphan_incident(config: SentinelConfig, child: ChildIdentity) -> Incident:
    evidence = json.dumps(child.to_dict(), sort_keys=True).encode()
    digest = hashlib.sha256(evidence).hexdigest()
    incident = Incident.create(
        run_id=config.run_id,
        source_commit=config.source_commit,
        exit_code=-1,
        exit_evidence_sha256=digest,
        failure_signature="supervisor wrapper exited while owned child remained live",
        category="supervisor_orphan",
        excerpt="validated child process group remains live after supervisor wrapper exit",
        expected_identity=config.expected_identity,
        evidence_hashes={"child_identity": digest},
    )
    store = IncidentStore(config.state_dir)
    snapshot = store.create(incident)
    if snapshot.state is IncidentState.OBSERVED:
        store.transition(incident.incident_id, IncidentState.FROZEN)
    return incident


def _is_complete(config: SentinelConfig) -> bool:
    path = config.completion_marker
    if not path.exists():
        return False
    payload = _read_regular(path, "completion marker", maximum=4096)
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SentinelError("completion marker is invalid") from exc
    if (
        not isinstance(decoded, dict)
        or set(decoded) != {"run_id", "status"}
        or decoded["run_id"] != config.run_id
        or decoded["status"] != "complete"
    ):
        raise SentinelError("completion marker identity is invalid")
    return True


def _hash_and_sample(path: Path) -> tuple[str, bytes]:
    if path.is_symlink():
        raise SentinelError("failure log is a symlink")
    try:
        metadata = path.stat()
    except OSError as exc:
        raise SentinelError(f"failure log is unavailable: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise SentinelError("failure log must be a regular file")
    if metadata.st_size > _MAX_LOG_BYTES:
        raise SentinelError("failure log exceeds its byte bound")
    digest = hashlib.sha256()
    sample = bytearray()
    with path.open("rb") as handle:
        while chunk := handle.read(64 * 1024):
            digest.update(chunk)
            if len(sample) < _MAX_EXCERPT_BYTES:
                remaining = _MAX_EXCERPT_BYTES - len(sample)
                sample.extend(chunk[:remaining])
    return digest.hexdigest(), bytes(sample)


def _classify(raw: bytes) -> tuple[str, str]:
    lowered = raw.lower()
    if any(marker in lowered for marker in _REDACT_MARKERS):
        return "credential_exposure", "credential-like material in failure log"
    if b"firewall" in lowered or b"network none" in lowered:
        return "verifier_firewall_drift", "verifier firewall drift"
    if b"official test" in lowered or b"reference data" in lowered:
        return "official_data_exposure", "official verifier data exposure"
    if b"identity drift" in lowered or b"config drift" in lowered:
        return "identity_drift", "runtime identity drift"
    if b"historical" in lowered and b"hash" in lowered:
        return "historical_hash_drift", "historical evidence hash drift"
    if (
        b"downstream_delivery" in lowered
        or b"post_accept_transport" in lowered
        or (b"ambiguous" in lowered and b"upstream" in lowered)
    ):
        return "ambiguous_upstream", "ambiguous upstream request acceptance"
    if b"cost" in lowered and b"missing" in lowered:
        return "unsupported_cost_omission", "unsupported cost ledger omission"
    if b"cleanup" in lowered or b"residual" in lowered:
        return "cleanup_failure", "exact resource cleanup failure"
    if b"artifact integrity" in lowered:
        return "artifact_integrity", "verifier artifact integrity mismatch"
    if b"traceback" in lowered or b"error" in lowered or b"failed" in lowered:
        return "harness_bug", "unclassified harness failure"
    return "unknown_failure", "unclassified coordinator termination"


def _redact(raw: bytes) -> str:
    safe_lines: list[bytes] = []
    for line in raw.splitlines():
        lowered = line.lower()
        if any(marker in lowered for marker in _REDACT_MARKERS):
            safe_lines.append(b"[REDACTED]")
        else:
            safe_lines.append(line)
    decoded = b"\n".join(safe_lines).decode("utf-8", errors="replace")
    decoded = "".join(
        character if character in "\n\t" or ord(character) >= 0x20 else "?"
        for character in decoded
    )
    bounded = decoded[:2048].strip()
    return bounded or "[no safe failure excerpt]"


def observe(
    config: SentinelConfig,
    *,
    pid_alive: Callable[[int], bool] = _default_pid_alive,
    pid_command: Callable[[int], str] = _default_pid_command,
    child_snapshot: Callable[[int], ProcessSnapshot] = read_process_snapshot,
) -> Incident | None:
    """Observe once; freeze one incident and perform no repair or cleanup."""

    if _is_complete(config):
        return None
    pid = _read_pid(config.coordinator_pid_file)
    if config.child_identity_file is not None:
        child = _read_child_identity(config.child_identity_file)
        if child.run_id != config.run_id or child.source_commit != config.source_commit:
            raise SentinelError("child identity run/source mismatch")
        wrapper_alive = pid is not None and pid_alive(pid)
        child_alive = pid_alive(child.pid)
        if child_alive:
            try:
                snapshot = child_snapshot(child.pid)
                validate_process_snapshot(
                    snapshot,
                    expected=ProcessIdentity(
                        pid=child.pid,
                        process_group_id=child.process_group_id,
                        uid=child.uid,
                        start_ticks=child.start_ticks,
                        command_sha256=child.command_sha256,
                    ),
                    command_token=config.coordinator_command_token,
                    run_id=config.run_id,
                    source_commit=config.source_commit,
                    expected_uid=child.uid,
                )
            except (BoundaryError, ProcessLookupError) as exc:
                raise SentinelError(f"live child identity mismatch: {exc}") from exc
            if not wrapper_alive:
                return _freeze_orphan_incident(config, child)
            return None
        if wrapper_alive:
            raise SentinelError("live supervisor wrapper has no owned child")
    if pid is not None and pid_alive(pid):
        command = pid_command(pid)
        if config.coordinator_command_token not in command:
            raise SentinelError("live coordinator command identity mismatch")
        return None
    exit_payload = _read_regular(config.exit_code_file, "exit code", maximum=32)
    try:
        exit_code = int(exit_payload.decode().strip())
    except (UnicodeDecodeError, ValueError) as exc:
        raise SentinelError("exit code is invalid") from exc
    log_sha256, sample = _hash_and_sample(config.failure_log)
    category, signature = _classify(sample)
    incident = Incident.create(
        run_id=config.run_id,
        source_commit=config.source_commit,
        exit_code=exit_code,
        exit_evidence_sha256=hashlib.sha256(exit_payload).hexdigest(),
        failure_signature=signature,
        category=category,
        excerpt=_redact(sample),
        expected_identity=config.expected_identity,
        evidence_hashes={
            "exit_code": hashlib.sha256(exit_payload).hexdigest(),
            "failure_log": log_sha256,
        },
    )
    store = IncidentStore(config.state_dir)
    snapshot = store.create(incident)
    if snapshot.state is IncidentState.OBSERVED:
        store.transition(incident.incident_id, IncidentState.FROZEN)
    return incident


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.interval_seconds < 5 or args.interval_seconds > 3600:
        raise SentinelError("interval-seconds must be between 5 and 3600")
    config = load_config(args.config)
    while True:
        incident = observe(config)
        if incident is not None:
            print(json.dumps({"incident_id": incident.incident_id}, sort_keys=True))
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
