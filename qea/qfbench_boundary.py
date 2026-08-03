"""Fail-closed QFBench repetition-boundary inventory and migration guard."""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import re
import select
import signal
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping

from .qfbench_scheduler_epochs import (
    SchedulerEpoch,
    SchedulerEpochError,
    migrate_v1_checkpoint,
    validate_scheduler_epochs,
)
from .sandbox_reaper import reap_sandbox_networks


_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CHECKPOINT = re.compile(
    r"repetition-(?P<repetition>0[1-5])-(?P<panel>primary|diagnostic)\Z"
)
_MAX_METADATA_BYTES = 4 * 1024 * 1024
_PRUNED_METADATA_DIRECTORIES = frozenset(
    {
        "artifacts",
        "evidence",
        "logs",
        "output",
        "references",
        "tests",
        "traces",
        "verifier",
        "workers",
    }
)
_LIFECYCLE_SUFFIXES = (
    "-sandbox-lifecycle-v2.json",
    "network-lifecycle-v1.json",
)


class BoundaryError(RuntimeError):
    """Boundary evidence or guard identity is ambiguous or unsafe."""


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _atomic_json(path: Path, payload: Mapping[str, object], *, mode=0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded = json.dumps(payload, sort_keys=True, indent=2).encode() + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = None
    try:
        descriptor = os.open(temporary, flags, mode)
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as output:
            descriptor = None
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def _read_regular_bytes(path: Path, *, maximum=_MAX_METADATA_BYTES) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise BoundaryError(f"metadata is unavailable: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise BoundaryError(f"symlink metadata is forbidden: {path}")
    if not stat.S_ISREG(metadata.st_mode):
        raise BoundaryError(f"metadata must be a regular file: {path}")
    if metadata.st_size > maximum:
        raise BoundaryError(f"metadata exceeds bounded size: {path}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb", closefd=True) as source:
            opened = os.fstat(source.fileno())
            if not stat.S_ISREG(opened.st_mode):
                raise BoundaryError(f"metadata must be a regular file: {path}")
            payload = source.read(maximum + 1)
    except OSError as exc:
        raise BoundaryError(f"metadata cannot be read safely: {path}") from exc
    if len(payload) > maximum:
        raise BoundaryError(f"metadata exceeds bounded size: {path}")
    return payload


def _read_json(path: Path) -> tuple[object, bytes]:
    payload = _read_regular_bytes(path)
    try:
        return json.loads(payload), payload
    except json.JSONDecodeError as exc:
        raise BoundaryError(f"metadata is not valid JSON: {path}") from exc


def _record(path: Path, root: Path, payload: bytes) -> tuple[str, int, str]:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise BoundaryError(f"metadata escapes the run directory: {path}") from exc
    return relative, len(payload), hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class BoundaryInventory:
    clean: bool
    repetition_one_score_count: int
    repetition_two_evidence: tuple[str, ...]
    active_resource_ids: tuple[str, ...]
    evidence_sha256: str
    evidence_manifest: tuple[tuple[str, int, str], ...]


def _attempt_metadata(run_dir: Path, *, benchmark_commit: str):
    attempts_root = run_dir / "attempts"
    if not attempts_root.exists():
        return {}, [], [], 0
    if attempts_root.is_symlink() or not attempts_root.is_dir():
        raise BoundaryError("attempts metadata root must be a real directory")
    checkpoints: dict[str, tuple[int, str]] = {}
    evidence: list[tuple[str, int, str]] = []
    repetition_two: list[str] = []
    score_count = 0
    for attempt_dir in sorted(attempts_root.iterdir()):
        if attempt_dir.is_symlink() or not attempt_dir.is_dir():
            raise BoundaryError(f"attempt metadata directory is unsafe: {attempt_dir}")
        attempt_path = attempt_dir / "attempt.json"
        if not attempt_path.exists():
            raise BoundaryError(f"attempt has no attempt.json: {attempt_dir}")
        attempt, raw_attempt = _read_json(attempt_path)
        if not isinstance(attempt, dict):
            raise BoundaryError(f"attempt metadata must be an object: {attempt_path}")
        checkpoint = attempt.get("checkpoint")
        match = _CHECKPOINT.fullmatch(checkpoint) if isinstance(checkpoint, str) else None
        if match is None:
            raise BoundaryError(f"attempt checkpoint is unsupported: {checkpoint!r}")
        repetition = int(match.group("repetition"))
        panel = match.group("panel")
        expected_split = f"baseline_{panel}"
        if attempt.get("split") != expected_split:
            raise BoundaryError(f"attempt panel/split mismatch: {attempt_path}")
        attempt_id = attempt.get("attempt_id", attempt_dir.name)
        if not isinstance(attempt_id, str) or not attempt_id:
            raise BoundaryError(f"attempt identity is invalid: {attempt_path}")
        if attempt_id != attempt_dir.name:
            raise BoundaryError(f"attempt identity/path mismatch: {attempt_path}")
        if attempt_id in checkpoints:
            raise BoundaryError(f"duplicate attempt identity: {attempt_id}")
        if (
            attempt.get("run_id") != run_dir.name
            or attempt.get("benchmark_commit") != benchmark_commit
        ):
            raise BoundaryError(f"attempt immutable identity mismatch: {attempt_path}")
        task_id = attempt.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise BoundaryError(f"attempt task identity is invalid: {attempt_path}")
        checkpoints[attempt_id] = (repetition, panel)
        evidence.append(_record(attempt_path, run_dir, raw_attempt))
        if repetition >= 2:
            repetition_two.append(attempt_path.relative_to(run_dir).as_posix())

        score_path = attempt_dir / "completed-score.json"
        if score_path.exists():
            score, raw_score = _read_json(score_path)
            if not isinstance(score, dict) or score.get("task_id") != task_id:
                raise BoundaryError(
                    f"completed score task identity mismatch: {score_path}"
                )
            if not isinstance(score.get("domain"), str) or not score["domain"]:
                raise BoundaryError(f"completed score metadata is invalid: {score_path}")
            reward = score.get("reward")
            if (
                isinstance(reward, bool)
                or not isinstance(reward, (int, float))
                or not math.isfinite(reward)
                or not 0.0 <= reward <= 1.0
            ):
                raise BoundaryError(f"completed score reward is invalid: {score_path}")
            evidence.append(_record(score_path, run_dir, raw_score))
            if repetition == 1:
                score_count += 1
    return checkpoints, evidence, repetition_two, score_count


def _lifecycle_metadata(
    run_dir: Path,
    checkpoints: Mapping[str, tuple[int, str]],
):
    evidence: list[tuple[str, int, str]] = []
    repetition_two: list[str] = []
    unfinished: list[str] = []
    for directory, directory_names, file_names in os.walk(
        run_dir, topdown=True, followlinks=False
    ):
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in _PRUNED_METADATA_DIRECTORIES
        )
        for name in tuple(directory_names):
            path = Path(directory) / name
            if path.is_symlink():
                raise BoundaryError(f"symlink metadata directory is forbidden: {path}")
        for name in sorted(file_names):
            if not name.endswith(_LIFECYCLE_SUFFIXES):
                continue
            path = Path(directory) / name
            lifecycle, raw = _read_json(path)
            if not isinstance(lifecycle, dict):
                raise BoundaryError(f"lifecycle metadata must be an object: {path}")
            if lifecycle.get("run_id") != run_dir.name:
                raise BoundaryError(f"lifecycle run identity mismatch: {path}")
            attempt_id = lifecycle.get("attempt_id")
            if not isinstance(attempt_id, str):
                attempt_id = lifecycle.get("network_scope")
            if not isinstance(attempt_id, str) or attempt_id not in checkpoints:
                raise BoundaryError(f"lifecycle attempt identity is unknown: {path}")
            repetition, _ = checkpoints[attempt_id]
            relative = path.relative_to(run_dir).as_posix()
            if repetition >= 2:
                repetition_two.append(relative)
            if lifecycle.get("cleaned_up") is not True:
                native_id = lifecycle.get("native_id")
                unfinished.append(
                    f"unfinished:{native_id if isinstance(native_id, str) else relative}"
                )
            evidence.append(_record(path, run_dir, raw))
    return evidence, repetition_two, unfinished


def _registry_metadata(run_dir: Path):
    path = run_dir / "proxy-request-registry.json"
    if not path.exists():
        return [], []
    registry, raw = _read_json(path)
    if not isinstance(registry, dict) or registry.get("schema_version") != 1:
        raise BoundaryError("proxy request registry schema is invalid")
    identities = registry.get("request_identities_sha256")
    if not isinstance(identities, list) or any(
        not isinstance(value, str) or _SHA256.fullmatch(value) is None
        for value in identities
    ):
        raise BoundaryError("proxy request registry identities are invalid")
    unsafe = [f"proxy-request-registry:{value}" for value in identities]
    return [_record(path, run_dir, raw)], unsafe


def _active_resources(run_dir: Path, backend) -> tuple[str, ...]:
    if backend is None:
        return ()
    try:
        containers = backend.list(
            {"qea.managed": "true", "qea.run-id": run_dir.name}
        )
        container_ids = [f"container:{state.native_id}" for state in containers]
        networks = reap_sandbox_networks(run_dir, backend=backend)
    except Exception as exc:
        raise BoundaryError(f"active resource inspection failed: {exc}") from exc
    if networks.failed:
        raise BoundaryError(
            f"active network inspection failed: {dict(networks.failed)}"
        )
    network_ids = [f"network:{native_id}" for native_id in networks.pending_ids]
    return tuple(sorted(container_ids + network_ids))


def inspect_boundary(
    run_dir: str | Path,
    *,
    expected_scores: int,
    backend=None,
) -> BoundaryInventory:
    """Inspect only bounded coordinator metadata at a repetition boundary."""

    root = Path(run_dir).resolve()
    if type(expected_scores) is not int or expected_scores < 0:
        raise BoundaryError("expected_scores must be a non-negative integer")
    if not root.is_dir() or Path(run_dir).is_symlink():
        raise BoundaryError("run directory must be a real directory")
    resume_path = root / "resume.json"
    resume, raw_resume = _read_json(resume_path)
    if not isinstance(resume, dict):
        raise BoundaryError("resume checkpoint must be an object")
    if resume.get("run_id") != root.name:
        raise BoundaryError("resume checkpoint run identity mismatch")
    benchmark_commit = resume.get("benchmark_commit")
    if not isinstance(benchmark_commit, str) or not _COMMIT.fullmatch(
        benchmark_commit
    ):
        raise BoundaryError("resume checkpoint benchmark identity is invalid")
    evidence = [_record(resume_path, root, raw_resume)]
    checkpoints, attempts, repetition_two, score_count = _attempt_metadata(
        root, benchmark_commit=benchmark_commit
    )
    evidence.extend(attempts)
    registry_records, registry_evidence = _registry_metadata(root)
    evidence.extend(registry_records)
    repetition_two.extend(registry_evidence)
    lifecycles, lifecycle_rep2, unfinished = _lifecycle_metadata(root, checkpoints)
    evidence.extend(lifecycles)
    repetition_two.extend(lifecycle_rep2)
    active = tuple(sorted(set(unfinished) | set(_active_resources(root, backend))))
    ordered_manifest = tuple(sorted(evidence))
    evidence_digest = hashlib.sha256(
        _canonical_bytes(
            [
                {"path": path, "size": size, "sha256": digest}
                for path, size, digest in ordered_manifest
            ]
        )
    ).hexdigest()
    repetition_two_tuple = tuple(sorted(set(repetition_two)))
    clean = (
        score_count == expected_scores
        and not repetition_two_tuple
        and not active
    )
    return BoundaryInventory(
        clean=clean,
        repetition_one_score_count=score_count,
        repetition_two_evidence=repetition_two_tuple,
        active_resource_ids=active,
        evidence_sha256=evidence_digest,
        evidence_manifest=ordered_manifest,
    )


def freeze_boundary_manifest(
    run_dir: str | Path,
    inventory: BoundaryInventory,
) -> str:
    """Atomically freeze a content-addressed manifest without rewriting evidence."""

    if not isinstance(inventory, BoundaryInventory) or not inventory.clean:
        raise BoundaryError("only a clean boundary inventory can be frozen")
    root = Path(run_dir).resolve()
    body: dict[str, object] = {
        "schema_version": 1,
        "run_id": root.name,
        "repetition_one_score_count": inventory.repetition_one_score_count,
        "repetition_two_evidence": list(inventory.repetition_two_evidence),
        "active_resource_ids": list(inventory.active_resource_ids),
        "evidence_sha256": inventory.evidence_sha256,
        "evidence_manifest": [
            {"path": path, "size": size, "sha256": digest}
            for path, size, digest in inventory.evidence_manifest
        ],
    }
    manifest_sha256 = hashlib.sha256(_canonical_bytes(body)).hexdigest()
    body["manifest_sha256"] = manifest_sha256
    path = root / "boundary-manifest.json"
    if path.exists():
        existing, _ = _read_json(path)
        if existing != body:
            raise BoundaryError("published boundary manifest differs")
        return manifest_sha256
    _atomic_json(path, body)
    return manifest_sha256


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    process_group_id: int
    uid: int
    start_ticks: int
    command_sha256: str

    def __post_init__(self) -> None:
        for name in ("pid", "process_group_id", "start_ticks"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise BoundaryError(f"process {name} must be positive")
        if type(self.uid) is not int or self.uid < 0:
            raise BoundaryError("process uid must be non-negative")
        if not isinstance(self.command_sha256, str) or not _SHA256.fullmatch(
            self.command_sha256
        ):
            raise BoundaryError("process command digest is invalid")

    def to_dict(self) -> dict[str, int | str]:
        return {
            "pid": self.pid,
            "process_group_id": self.process_group_id,
            "uid": self.uid,
            "start_ticks": self.start_ticks,
            "command_sha256": self.command_sha256,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "ProcessIdentity":
        if not isinstance(payload, dict) or set(payload) != {
            "pid",
            "process_group_id",
            "uid",
            "start_ticks",
            "command_sha256",
        }:
            raise BoundaryError("process identity has unknown or missing fields")
        return cls(**payload)


@dataclass(frozen=True)
class ProcessSnapshot:
    identity: ProcessIdentity
    state: str
    argv: tuple[str, ...]


def read_process_snapshot(
    pid: int,
    *,
    proc_root: str | Path = "/proc",
) -> ProcessSnapshot:
    """Read Linux proc identity, handling spaces and parentheses in comm."""

    root = Path(proc_root) / str(pid)
    try:
        stat_text = _read_regular_bytes(root / "stat").decode()
        status_text = _read_regular_bytes(root / "status").decode()
        command = _read_regular_bytes(root / "cmdline")
    except BoundaryError as exc:
        if not root.exists():
            raise ProcessLookupError(pid) from exc
        raise
    closing = stat_text.rfind(")")
    if closing < 0:
        raise BoundaryError("process stat comm field is malformed")
    fields = stat_text[closing + 1 :].strip().split()
    if len(fields) <= 19:
        raise BoundaryError("process stat field count is invalid")
    state = fields[0]
    try:
        process_group_id = int(fields[2])
        start_ticks = int(fields[19])
    except ValueError as exc:
        raise BoundaryError("process stat identity fields are invalid") from exc
    uid_line = next(
        (line for line in status_text.splitlines() if line.startswith("Uid:")),
        None,
    )
    if uid_line is None:
        raise BoundaryError("process status has no UID")
    try:
        uid = int(uid_line.split()[1])
    except (IndexError, ValueError) as exc:
        raise BoundaryError("process status UID is invalid") from exc
    try:
        argv = tuple(
            value.decode("utf-8", errors="strict")
            for value in command.split(b"\0")
            if value
        )
    except UnicodeDecodeError as exc:
        raise BoundaryError("process command line is not UTF-8") from exc
    if not argv:
        raise BoundaryError("process command line is empty")
    return ProcessSnapshot(
        identity=ProcessIdentity(
            pid=pid,
            process_group_id=process_group_id,
            uid=uid,
            start_ticks=start_ticks,
            command_sha256=hashlib.sha256(command).hexdigest(),
        ),
        state=state,
        argv=argv,
    )


def validate_process_snapshot(
    snapshot: ProcessSnapshot,
    *,
    expected: ProcessIdentity,
    command_token: str,
    run_id: str,
    source_commit: str,
    expected_uid: int,
) -> None:
    """Require every configured process field before permitting a signal."""

    actual = snapshot.identity
    comparisons = (
        (actual.pid, expected.pid, "PID"),
        (actual.process_group_id, expected.process_group_id, "process group"),
        (actual.uid, expected.uid, "UID"),
        (actual.start_ticks, expected.start_ticks, "start ticks"),
        (actual.command_sha256, expected.command_sha256, "command digest"),
    )
    for observed, configured, label in comparisons:
        if observed != configured:
            raise BoundaryError(f"process {label} identity mismatch")
    if actual.uid != expected_uid:
        raise BoundaryError("process UID differs from guard UID")
    if not any(
        value == command_token or Path(value).name == command_token
        for value in snapshot.argv
    ):
        raise BoundaryError("process command token is absent")
    if run_id not in snapshot.argv:
        raise BoundaryError("process run ID token is absent")
    if not any(source_commit in value for value in snapshot.argv):
        raise BoundaryError("process source commit token is absent")
    if snapshot.state in {"X", "Z"}:
        raise BoundaryError("process is already dead or zombie")


@dataclass(frozen=True)
class BoundaryGuardConfig:
    run_id: str
    source_commit: str
    run_dir: Path | str
    expected_uid: int
    command_token: str
    process: ProcessIdentity
    scheduler_epochs: tuple[SchedulerEpoch, ...]
    expected_scores: int = 85
    wait_timeout_seconds: int = 3600

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not _RUN_ID.fullmatch(self.run_id):
            raise BoundaryError("guard run_id is invalid")
        if not isinstance(self.source_commit, str) or not _COMMIT.fullmatch(
            self.source_commit
        ):
            raise BoundaryError("guard source_commit is invalid")
        root = Path(self.run_dir).resolve()
        if not root.is_dir() or Path(self.run_dir).is_symlink() or root.name != self.run_id:
            raise BoundaryError("guard run_dir is invalid")
        if type(self.expected_uid) is not int or self.expected_uid < 0:
            raise BoundaryError("guard expected_uid is invalid")
        if not isinstance(self.command_token, str) or not self.command_token:
            raise BoundaryError("guard command_token is invalid")
        if not isinstance(self.process, ProcessIdentity):
            raise BoundaryError("guard process identity is invalid")
        try:
            epochs = validate_scheduler_epochs(
                self.scheduler_epochs, total_repetitions=5
            )
        except SchedulerEpochError as exc:
            raise BoundaryError(str(exc)) from exc
        if type(self.expected_scores) is not int or self.expected_scores < 0:
            raise BoundaryError("guard expected_scores is invalid")
        if (
            type(self.wait_timeout_seconds) is not int
            or self.wait_timeout_seconds < 1
        ):
            raise BoundaryError("guard wait_timeout_seconds is invalid")
        object.__setattr__(self, "run_dir", root)
        object.__setattr__(self, "scheduler_epochs", epochs)


_GUARD_CONFIG_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "source_commit",
        "run_dir",
        "expected_uid",
        "command_token",
        "process",
        "scheduler_epochs",
        "expected_scores",
        "wait_timeout_seconds",
    }
)


def load_boundary_guard_config(path: str | Path) -> BoundaryGuardConfig:
    """Load one owner-only guard config through O_NOFOLLOW."""

    config_path = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(config_path, flags)
    except OSError as exc:
        raise BoundaryError(
            "guard config must be an available regular non-symlink file"
        ) from exc
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise BoundaryError("guard config must be a regular file")
            if (
                metadata.st_uid != os.geteuid()
                or stat.S_IMODE(metadata.st_mode) != 0o600
            ):
                raise BoundaryError(
                    "guard config must be owner-controlled mode 600"
                )
            raw = source.read(_MAX_METADATA_BYTES + 1)
    except OSError as exc:
        raise BoundaryError("guard config cannot be read safely") from exc
    if len(raw) > _MAX_METADATA_BYTES:
        raise BoundaryError("guard config exceeds bounded size")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BoundaryError("guard config is not valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != _GUARD_CONFIG_FIELDS:
        raise BoundaryError("guard config has unknown or missing fields")
    if payload.get("schema_version") != 1:
        raise BoundaryError("guard config schema is unsupported")
    try:
        process = ProcessIdentity.from_dict(payload["process"])
        epochs = tuple(
            SchedulerEpoch.from_dict(value)
            for value in payload["scheduler_epochs"]
        )
        return BoundaryGuardConfig(
            run_id=payload["run_id"],
            source_commit=payload["source_commit"],
            run_dir=payload["run_dir"],
            expected_uid=payload["expected_uid"],
            command_token=payload["command_token"],
            process=process,
            scheduler_epochs=epochs,
            expected_scores=payload["expected_scores"],
            wait_timeout_seconds=payload["wait_timeout_seconds"],
        )
    except (KeyError, TypeError, SchedulerEpochError) as exc:
        raise BoundaryError("guard config field types are invalid") from exc


def _boundary_state(config: BoundaryGuardConfig) -> bool:
    state, _ = _read_json(config.run_dir / "resume.json")
    if not isinstance(state, dict):
        raise BoundaryError("resume checkpoint must be an object")
    if (
        state.get("run_id") != config.run_id
        or state.get("benchmark_commit") != config.source_commit
        or state.get("total_repetitions") != 5
    ):
        raise BoundaryError("resume checkpoint immutable identity mismatch")
    if state.get("schema_version") != 1:
        raise BoundaryError("boundary guard requires schema-v1 checkpoint")
    completed = state.get("completed")
    return bool(
        state.get("phase") == "primary"
        and state.get("next_repetition") == 2
        and state.get("pending_primary") is None
        and isinstance(completed, list)
        and len(completed) == 1
        and isinstance(completed[0], dict)
        and completed[0].get("repetition") == 1
    )


def wait_for_boundary(config: BoundaryGuardConfig) -> None:
    """Observe atomic resume replacement through Linux inotify."""

    if _boundary_state(config):
        return
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        initialize = libc.inotify_init1
        add_watch = libc.inotify_add_watch
    except AttributeError as exc:
        raise BoundaryError("Linux inotify is unavailable") from exc
    initialize.argtypes = [ctypes.c_int]
    initialize.restype = ctypes.c_int
    add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
    add_watch.restype = ctypes.c_int
    descriptor = initialize(os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0))
    if descriptor < 0:
        raise BoundaryError("inotify initialization failed")
    try:
        mask = 0x00000008 | 0x00000080  # IN_CLOSE_WRITE | IN_MOVED_TO
        watched = add_watch(descriptor, os.fsencode(config.run_dir), mask)
        if watched < 0:
            raise BoundaryError("inotify run-directory watch failed")
        poller = select.poll()
        poller.register(descriptor, select.POLLIN)
        deadline = time.monotonic() + config.wait_timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BoundaryError("timed out waiting for repetition boundary")
            events = poller.poll(min(int(remaining * 1000) + 1, 60_000))
            if not events:
                continue
            try:
                os.read(descriptor, 64 * 1024)
            except BlockingIOError:
                pass
            if _boundary_state(config):
                return
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class BoundaryGuardResult:
    status: str
    manifest_sha256: str | None
    reason: str | None


def _claim_guard(config: BoundaryGuardConfig) -> None:
    path = config.run_dir / "boundary-guard-claim.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise BoundaryError("boundary guard was already claimed") from exc
    payload = _canonical_bytes(
        {
            "schema_version": 1,
            "run_id": config.run_id,
            "source_commit": config.source_commit,
            "process": config.process.to_dict(),
        }
    ) + b"\n"
    with os.fdopen(descriptor, "wb", closefd=True) as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())


def _hard_stop(config: BoundaryGuardConfig, reason: str) -> BoundaryGuardResult:
    bounded_reason = " ".join(str(reason).split())[:2000]
    _atomic_json(
        config.run_dir / "boundary-hard-stop.json",
        {
            "schema_version": 1,
            "run_id": config.run_id,
            "source_commit": config.source_commit,
            "process": config.process.to_dict(),
            "reason": bounded_reason,
        },
    )
    return BoundaryGuardResult("hard_stop", None, bounded_reason)


def _validate_snapshot(config: BoundaryGuardConfig, snapshot: ProcessSnapshot) -> None:
    validate_process_snapshot(
        snapshot,
        expected=config.process,
        command_token=config.command_token,
        run_id=config.run_id,
        source_commit=config.source_commit,
        expected_uid=config.expected_uid,
    )


def _wait_for_stopped(
    config: BoundaryGuardConfig,
    process_reader: Callable[[int], ProcessSnapshot],
    sleep: Callable[[float], None],
) -> ProcessSnapshot:
    deadline = time.monotonic() + config.wait_timeout_seconds
    while True:
        snapshot = process_reader(config.process.pid)
        if snapshot.state in {"T", "t"}:
            return snapshot
        if time.monotonic() >= deadline:
            raise BoundaryError("process group did not enter stopped state")
        sleep(0.05)


def _wait_for_absent(
    config: BoundaryGuardConfig,
    process_reader: Callable[[int], ProcessSnapshot],
    sleep: Callable[[float], None],
) -> None:
    deadline = time.monotonic() + config.wait_timeout_seconds
    while True:
        try:
            process_reader(config.process.pid)
        except ProcessLookupError:
            return
        if time.monotonic() >= deadline:
            raise BoundaryError("terminated coordinator PID remains present")
        sleep(0.05)


def run_boundary_guard(
    config: BoundaryGuardConfig,
    *,
    backend=None,
    boundary_waiter: Callable[[BoundaryGuardConfig], None] = wait_for_boundary,
    process_reader: Callable[[int], ProcessSnapshot] = read_process_snapshot,
    signal_group: Callable[[int, int], None] = os.killpg,
    inventory_reader: Callable[[BoundaryGuardConfig], BoundaryInventory] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> BoundaryGuardResult:
    """Stop, revalidate, terminate, inventory, freeze, and migrate exactly once."""

    if not isinstance(config, BoundaryGuardConfig):
        raise BoundaryError("config must be a BoundaryGuardConfig")
    if os.geteuid() != config.expected_uid:
        raise BoundaryError("guard effective UID differs from configured UID")
    _claim_guard(config)
    snapshot = process_reader(config.process.pid)
    _validate_snapshot(config, snapshot)
    boundary_waiter(config)
    snapshot = process_reader(config.process.pid)
    _validate_snapshot(config, snapshot)

    if snapshot.state not in {"T", "t"}:
        signal_group(config.process.process_group_id, signal.SIGSTOP)
        try:
            snapshot = _wait_for_stopped(config, process_reader, sleep)
            _validate_snapshot(config, snapshot)
        except Exception as exc:  # post-stop errors must retain the stopped group.
            return _hard_stop(config, f"post-stop process validation failed: {exc}")

    if inventory_reader is None:
        inventory_reader = lambda current: inspect_boundary(
            current.run_dir,
            expected_scores=current.expected_scores,
            backend=backend,
        )
    try:
        inventory = inventory_reader(config)
    except Exception as exc:
        return _hard_stop(config, f"post-stop boundary inventory failed: {exc}")
    if not inventory.clean:
        return _hard_stop(
            config,
            "boundary inventory is not clean: "
            f"scores={inventory.repetition_one_score_count}, "
            f"rep2={inventory.repetition_two_evidence}, "
            f"resources={inventory.active_resource_ids}",
        )

    signal_group(config.process.process_group_id, signal.SIGKILL)
    try:
        _wait_for_absent(config, process_reader, sleep)
        final_inventory = inventory_reader(config)
        if not final_inventory.clean or final_inventory.active_resource_ids:
            raise BoundaryError("post-kill resource inventory is not clean")
        manifest_sha256 = freeze_boundary_manifest(
            config.run_dir, final_inventory
        )
        migrate_v1_checkpoint(
            config.run_dir / "resume.json",
            scheduler_epochs=config.scheduler_epochs,
            boundary_manifest_sha256=manifest_sha256,
        )
    except Exception as exc:
        return _hard_stop(config, f"post-kill migration failed: {exc}")
    _atomic_json(
        config.run_dir / "boundary-migrated.json",
        {
            "schema_version": 1,
            "run_id": config.run_id,
            "source_commit": config.source_commit,
            "manifest_sha256": manifest_sha256,
        },
    )
    return BoundaryGuardResult("migrated", manifest_sha256, None)


__all__ = [
    "BoundaryError",
    "BoundaryGuardConfig",
    "BoundaryGuardResult",
    "BoundaryInventory",
    "ProcessIdentity",
    "ProcessSnapshot",
    "freeze_boundary_manifest",
    "inspect_boundary",
    "load_boundary_guard_config",
    "read_process_snapshot",
    "run_boundary_guard",
    "validate_process_snapshot",
    "wait_for_boundary",
]
