#!/usr/bin/env python3
"""Run one bounded Mac-side autonomous QFBench repair-controller poll."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.repair_supervisor import (  # noqa: E402
    ExpectedIdentity,
    Incident,
    IncidentState,
    SupervisorPolicyError,
    classify_incident,
)


_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}\Z")
_GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
_INCIDENT_ID = re.compile(r"[0-9a-f]{64}\Z")
_SHELL_META = frozenset("\n\r\x00;&|`$<>")
_TERMINAL = frozenset(
    {
        IncidentState.RESOLVED.value,
        IncidentState.HARD_STOP.value,
        IncidentState.REPAIR_BUDGET_EXHAUSTED.value,
    }
)


class ControllerConfigError(RuntimeError):
    """The local repair-controller configuration is unsafe or invalid."""


class ControllerPolicyError(RuntimeError):
    """A controller precondition drifted and requires fail-closed handling."""


class TransientSSHError(RuntimeError):
    """The Mac cannot currently reach the bc control plane."""


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class ControllerConfig:
    run_id: str
    ssh_host: str
    remote_state_dir: str
    remote_state_helper: str
    worktree: Path
    branch: str
    max_repairs: int
    expected_identity: ExpectedIdentity
    protected_dirty_paths: tuple[str, ...]
    owned_paths: tuple[str, ...]
    test_argvs: tuple[tuple[str, ...], ...]
    push_argv: tuple[str, ...]
    deploy_argv_prefix: tuple[str, ...]
    canary_argv: tuple[str, ...]
    resume_argv: tuple[str, ...]
    state_dir: Path
    codex_binary: str
    command_timeout_seconds: int


def _exact_dict(payload: object, keys: set[str], label: str) -> dict:
    if not isinstance(payload, dict) or set(payload) != keys:
        raise ControllerConfigError(f"{label} schema is invalid")
    return payload


def _safe_argument(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 4096
        or any(character in _SHELL_META for character in value)
    ):
        raise ControllerConfigError(f"{label} contains an unsafe argument")
    return value


def _argv(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or len(value) > 64:
        raise ControllerConfigError(f"{label} must be a bounded argv array")
    return tuple(_safe_argument(item, label) for item in value)


def _deploy_adapter_argv(value: object) -> tuple[str, ...]:
    argv = _argv(value, "deploy_argv_prefix")
    adapter = Path(argv[0]).expanduser()
    try:
        metadata = adapter.lstat()
    except OSError as exc:
        raise ControllerConfigError(
            f"deploy adapter is unavailable: {exc}"
        ) from exc
    if (
        not adapter.is_absolute()
        or stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or not os.access(adapter, os.X_OK)
    ):
        raise ControllerConfigError(
            "deploy adapter must be an absolute executable regular file"
        )
    return argv


def _repo_path(value: object, label: str) -> str:
    path = PurePosixPath(_safe_argument(value, label))
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ControllerConfigError(f"{label} must be a safe repository path")
    return path.as_posix()


def load_config(path: str | Path) -> ControllerConfig:
    """Load an owner-only exact controller configuration."""

    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise ControllerConfigError("controller config must not be a symlink")
    try:
        metadata = candidate.stat()
    except OSError as exc:
        raise ControllerConfigError(f"controller config is unavailable: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ControllerConfigError("controller config must be a regular file with mode 600")
    try:
        payload = json.loads(candidate.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ControllerConfigError(f"controller config is unreadable: {exc}") from exc
    parsed = _exact_dict(
        payload,
        {
            "schema_version",
            "run_id",
            "ssh_host",
            "remote_state_dir",
            "remote_state_helper",
            "worktree",
            "branch",
            "max_repairs",
            "expected_identity",
            "protected_dirty_paths",
            "owned_paths",
            "test_argvs",
            "push_argv",
            "deploy_argv_prefix",
            "canary_argv",
            "resume_argv",
            "state_dir",
            "codex_binary",
            "command_timeout_seconds",
        },
        "controller config",
    )
    if parsed["schema_version"] != 1:
        raise ControllerConfigError("controller config schema version is unsupported")
    run_id = parsed["run_id"]
    ssh_host = parsed["ssh_host"]
    branch = parsed["branch"]
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise ControllerConfigError("run_id is invalid")
    if not isinstance(ssh_host, str) or not _HOST.fullmatch(ssh_host):
        raise ControllerConfigError("ssh_host is invalid")
    if not isinstance(branch, str) or not _BRANCH.fullmatch(branch):
        raise ControllerConfigError("branch is invalid")
    max_repairs = parsed["max_repairs"]
    if max_repairs != 3:
        raise ControllerConfigError("max_repairs must be exactly 3")
    timeout = parsed["command_timeout_seconds"]
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 60 <= timeout <= 14400:
        raise ControllerConfigError("command_timeout_seconds is invalid")
    worktree = Path(_safe_argument(parsed["worktree"], "worktree")).expanduser().resolve()
    if not worktree.is_dir():
        raise ControllerConfigError("worktree is unavailable")
    state_dir = Path(_safe_argument(parsed["state_dir"], "state_dir")).expanduser().resolve()
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state_dir, 0o700)
    try:
        expected_identity = ExpectedIdentity.from_dict(parsed["expected_identity"])
    except SupervisorPolicyError as exc:
        raise ControllerConfigError(f"expected_identity is invalid: {exc}") from exc
    protected = parsed["protected_dirty_paths"]
    owned = parsed["owned_paths"]
    test_argvs = parsed["test_argvs"]
    if not isinstance(protected, list) or not isinstance(owned, list):
        raise ControllerConfigError("repository path lists are invalid")
    if not isinstance(test_argvs, list) or not test_argvs:
        raise ControllerConfigError("test_argvs must be a non-empty argv list")
    return ControllerConfig(
        run_id=run_id,
        ssh_host=ssh_host,
        remote_state_dir=_safe_argument(parsed["remote_state_dir"], "remote_state_dir"),
        remote_state_helper=_safe_argument(parsed["remote_state_helper"], "remote_state_helper"),
        worktree=worktree,
        branch=branch,
        max_repairs=max_repairs,
        expected_identity=expected_identity,
        protected_dirty_paths=tuple(
            _repo_path(item, "protected_dirty_paths") for item in protected
        ),
        owned_paths=tuple(_repo_path(item, "owned_paths") for item in owned),
        test_argvs=tuple(_argv(item, "test_argvs") for item in test_argvs),
        push_argv=_argv(parsed["push_argv"], "push_argv"),
        deploy_argv_prefix=_deploy_adapter_argv(parsed["deploy_argv_prefix"]),
        canary_argv=_argv(parsed["canary_argv"], "canary_argv"),
        resume_argv=_argv(parsed["resume_argv"], "resume_argv"),
        state_dir=state_dir,
        codex_binary=_safe_argument(parsed["codex_binary"], "codex_binary"),
        command_timeout_seconds=timeout,
    )


def build_codex_argv(config: ControllerConfig) -> tuple[str, ...]:
    """Use the supported unattended workspace sandbox, never yolo mode."""

    return (
        config.codex_binary,
        "exec",
        "--ephemeral",
        "--json",
        "--sandbox",
        "workspace-write",
        "-c",
        'approval_policy="never"',
        "-c",
        "sandbox_workspace_write.network_access=false",
        "-c",
        "agents.enabled=false",
        "-C",
        str(config.worktree),
        "-",
    )


def build_codex_prompt(incident: Incident, config: ControllerConfig) -> str:
    """Build the bounded answer-free prompt supplied to Codex over stdin."""

    prompt = f"""You are repairing QFBench infrastructure on the feature branch only.

Incident id: {incident.incident_id}
Run id: {incident.run_id}
Source commit: {incident.source_commit}
Category: {incident.category}
Failure signature: {incident.failure_signature}
Exit evidence SHA-256: {incident.exit_evidence_sha256}
Sanitized excerpt: {incident.excerpt}

Diagnose the root cause first. Use test-driven development: add one focused
failing regression test, observe RED, implement the smallest infrastructure
fix, then run the focused tests and relevant broader tests. Create at most one scoped commit.
Do not merge, push, deploy, resume an experiment, or invoke a
model worker; the outer controller owns those actions.

Do not read .env, credentials, official tests/reference data, official
solutions, raw verifier verdicts, or held-out outcomes. Do not change the
benchmark, reward, worker behavior, model/provider route, images, scheduler,
formal config, checkpoint identity, firewall, cost policy, or cleanup scope.
Only modify paths under: {', '.join(config.owned_paths)}.
Preserve the existing protected dirty paths exactly.
"""
    if len(prompt) > 8000:
        raise ControllerPolicyError("Codex prompt exceeds its byte bound")
    return prompt


@contextlib.contextmanager
def controller_lock(path: str | Path) -> Iterator[bool]:
    """Acquire one non-blocking advisory lock for the launchd controller."""

    lock_path = Path(path).expanduser().resolve()
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            pass
        yield acquired
    finally:
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _default_runner(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    input_text: str | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    allowed_env = {
        key: value
        for key, value in os.environ.items()
        if key in {"HOME", "USER", "LOGNAME", "PATH", "SHELL", "TMPDIR", "SSH_AUTH_SOCK", "CODEX_HOME"}
    }
    return subprocess.run(
        tuple(argv),
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        shell=False,
        env=allowed_env,
    )


class RepairController:
    """Execute one idempotent, bounded incident-processing poll."""

    def __init__(self, config: ControllerConfig, *, runner: Runner = _default_runner):
        self.config = config
        self.runner = runner

    def _record(self, event: str, **fields: object) -> None:
        payload = {"schema_version": 1, "event": event, **fields}
        path = self.config.state_dir / "events.jsonl"
        descriptor = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        try:
            os.write(descriptor, (json.dumps(payload, sort_keys=True) + "\n").encode())
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.chmod(path, 0o600)

    def _run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        result = self.runner(
            tuple(argv),
            cwd=cwd,
            input_text=input_text,
            timeout=self.config.command_timeout_seconds,
        )
        output_sha256 = hashlib.sha256((result.stdout or "").encode()).hexdigest()
        error_sha256 = hashlib.sha256((result.stderr or "").encode()).hexdigest()
        self._record(
            "command",
            program=Path(argv[0]).name,
            returncode=result.returncode,
            stdout_sha256=output_sha256,
            stderr_sha256=error_sha256,
        )
        return result

    def _remote(self, action: str, *extra: str) -> subprocess.CompletedProcess[str]:
        argv = (
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            self.config.ssh_host,
            "python3",
            self.config.remote_state_helper,
            "--state-dir",
            self.config.remote_state_dir,
            action,
            *extra,
        )
        result = self._run(argv)
        if result.returncode == 255:
            raise TransientSSHError("bc SSH transport is temporarily unavailable")
        return result

    def _transition(self, incident_id: str, state: IncidentState) -> None:
        result = self._remote(
            "transition", "--incident-id", incident_id, "--state", state.value
        )
        if result.returncode != 0:
            raise ControllerPolicyError(f"remote transition to {state.value} failed")

    def _fetch_active(self) -> tuple[Incident | None, dict | None]:
        result = self._remote("show-active")
        if result.returncode != 0:
            raise ControllerPolicyError("remote active incident lookup failed")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ControllerPolicyError("remote incident response is invalid") from exc
        parsed = _exact_dict(payload, {"incident", "snapshot"}, "remote incident")
        if parsed["incident"] is None and parsed["snapshot"] is None:
            return None, None
        try:
            incident = Incident.from_dict(parsed["incident"])
        except SupervisorPolicyError as exc:
            raise ControllerPolicyError(f"remote incident is invalid: {exc}") from exc
        snapshot = parsed["snapshot"]
        if (
            not isinstance(snapshot, dict)
            or set(snapshot) != {"incident_id", "state", "repair_count", "history"}
            or snapshot["incident_id"] != incident.incident_id
            or snapshot["state"] not in {state.value for state in IncidentState}
            or isinstance(snapshot["repair_count"], bool)
            or not isinstance(snapshot["repair_count"], int)
            or not 0 <= snapshot["repair_count"] <= self.config.max_repairs
            or not isinstance(snapshot["history"], list)
        ):
            raise ControllerPolicyError("remote incident state is invalid")
        return incident, snapshot

    def _checked(self, argv: Sequence[str], *, cwd: Path | None = None) -> str:
        result = self._run(argv, cwd=cwd)
        if result.returncode != 0:
            raise ControllerPolicyError(f"command failed: {Path(argv[0]).name}")
        return result.stdout.rstrip("\r\n")

    def _git(self, *argv: str) -> str:
        return self._checked(("git", *argv), cwd=self.config.worktree)

    @staticmethod
    def _status_paths(output: str) -> tuple[str, ...]:
        paths: list[str] = []
        for line in output.splitlines():
            if len(line) < 4:
                raise ControllerPolicyError("git status output is invalid")
            value = line[3:]
            if " -> " in value:
                raise ControllerPolicyError("renamed dirty paths are unsupported")
            paths.append(value)
        return tuple(sorted(paths))

    def _validate_repository(self) -> tuple[str, tuple[str, ...]]:
        branch = self._git("branch", "--show-current")
        if branch != self.config.branch:
            raise ControllerPolicyError("feature branch identity drifted")
        dirty = self._status_paths(
            self._git("status", "--porcelain", "--untracked-files=all")
        )
        if set(dirty) - set(self.config.protected_dirty_paths):
            raise ControllerPolicyError("unexpected dirty worktree paths")
        head = self._git("rev-parse", "HEAD")
        if not _GIT_SHA.fullmatch(head):
            raise ControllerPolicyError("local source commit is invalid")
        return head, dirty

    def _repair(self, incident: Incident, snapshot: dict) -> int:
        if snapshot["state"] == IncidentState.FROZEN.value:
            self._transition(incident.incident_id, IncidentState.CLASSIFIED)
        result = self._remote(
            "record-repair", "--incident-id", incident.incident_id
        )
        if result.returncode == 30:
            self._record("repair_budget_exhausted", incident_id=incident.incident_id)
            return 30
        if result.returncode != 0:
            raise ControllerPolicyError("remote repair counter failed")
        before, protected_dirty = self._validate_repository()
        if before != incident.source_commit and snapshot["repair_count"] == 0:
            raise ControllerPolicyError("incident source commit does not match local HEAD")
        codex = self._run(
            build_codex_argv(self.config),
            cwd=self.config.worktree,
            input_text=build_codex_prompt(incident, self.config),
        )
        if codex.returncode != 0:
            self._record("codex_failed", incident_id=incident.incident_id)
            return 1
        for argv in self.config.test_argvs:
            result = self._run(argv, cwd=self.config.worktree)
            if result.returncode != 0:
                self._record("tests_failed", incident_id=incident.incident_id)
                return 1
        after, after_dirty = self._validate_repository()
        if after == before:
            raise ControllerPolicyError("Codex did not create a repair commit")
        if after_dirty != protected_dirty:
            raise ControllerPolicyError("protected dirty paths changed during repair")
        changed = tuple(
            line
            for line in self._git("diff", "--name-only", f"{before}..{after}").splitlines()
            if line
        )
        for path in changed:
            if not any(path == root or path.startswith(f"{root}/") for root in self.config.owned_paths):
                raise ControllerPolicyError(f"repair changed an unowned path: {path}")
        self._transition(incident.incident_id, IncidentState.TESTED)
        self._checked(self.config.push_argv, cwd=self.config.worktree)
        self._checked((*self.config.deploy_argv_prefix, after))
        self._transition(incident.incident_id, IncidentState.DEPLOYED)
        self._checked(self.config.canary_argv)
        self._transition(incident.incident_id, IncidentState.CANARY_PASSED)
        self._checked(self.config.resume_argv)
        self._transition(incident.incident_id, IncidentState.RESUMED)
        self._transition(incident.incident_id, IncidentState.RESOLVED)
        self._record("resolved", incident_id=incident.incident_id, commit=after)
        return 0

    def run_once(self, *, dry_run: bool = False) -> int:
        """Process at most one active remote incident."""

        try:
            incident, snapshot = self._fetch_active()
            if incident is None:
                self._record("no_incident")
                return 0
            if incident.run_id != self.config.run_id:
                raise ControllerPolicyError("active run identity drifted")
            if incident.expected_identity != self.config.expected_identity:
                raise ControllerPolicyError("expected runtime identity drifted")
            if snapshot["state"] in _TERMINAL:
                return 0
            classification = classify_incident(incident)
            self._record(
                "classified",
                incident_id=incident.incident_id,
                action=classification.action,
            )
            if dry_run:
                return 0
            if classification.action == "hard_stop":
                self._transition(incident.incident_id, IncidentState.HARD_STOP)
                return 20
            if classification.action == "resume":
                if snapshot["state"] == IncidentState.FROZEN.value:
                    self._transition(incident.incident_id, IncidentState.CLASSIFIED)
                self._checked(self.config.canary_argv)
                self._transition(incident.incident_id, IncidentState.CANARY_PASSED)
                self._checked(self.config.resume_argv)
                self._transition(incident.incident_id, IncidentState.RESUMED)
                self._transition(incident.incident_id, IncidentState.RESOLVED)
                return 0
            return self._repair(incident, snapshot)
        except TransientSSHError:
            self._record("ssh_retry", retry_after_seconds=60)
            return 10
        except ControllerPolicyError as exc:
            self._record("hard_stop", reason=str(exc))
            try:
                if "incident" in locals() and incident is not None:
                    self._transition(incident.incident_id, IncidentState.HARD_STOP)
            except (ControllerPolicyError, TransientSSHError):
                pass
            return 20


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    lock_path = config.state_dir / "controller.lock"
    with controller_lock(lock_path) as acquired:
        if not acquired:
            return 0
        return RepairController(config).run_once(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
