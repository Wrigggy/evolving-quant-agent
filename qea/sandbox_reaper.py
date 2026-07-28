"""Exact-ID cleanup for unfinished backend-neutral sandbox lifecycles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from .sandbox_backend import SandboxBackend, SandboxState
from .sandbox_lifecycle import (
    SandboxLifecycle,
    SandboxLifecycleError,
    load_lifecycle,
    mark_cleaned,
)


class SandboxReaperError(RuntimeError):
    """Lifecycle evidence is ambiguous or unsafe to apply."""


@dataclass(frozen=True)
class SandboxReaperReport:
    scanned_manifests: int
    pending_ids: tuple[str, ...]
    killed_ids: tuple[str, ...]
    absent_ids: tuple[str, ...]
    identity_mismatch_ids: tuple[str, ...]
    failed: Mapping[str, str]
    apply: bool


def _owned_identity_matches(
    lifecycle: SandboxLifecycle,
    state: SandboxState,
) -> bool:
    required_labels = {
        "qea.managed": "true",
        "qea.backend": lifecycle.backend,
        "qea.spec-sha256": lifecycle.spec_sha256,
    }
    return (
        state.backend == lifecycle.backend
        and state.native_id == lifecycle.native_id
        and state.immutable_image_ref == lifecycle.immutable_image_ref
        and all(state.labels.get(key) == value for key, value in required_labels.items())
    )


def _load_pending(
    root: Path,
    *,
    backend_name: str,
) -> tuple[int, dict[str, tuple[Path, SandboxLifecycle]]]:
    manifests = tuple(sorted(root.rglob("*-sandbox-lifecycle-v2.json")))
    pending: dict[str, tuple[Path, SandboxLifecycle]] = {}
    for discovered_path in manifests:
        resolved_path = discovered_path.resolve()
        try:
            resolved_path.relative_to(root)
        except ValueError as exc:
            raise SandboxReaperError(
                f"lifecycle path escapes requested root: {discovered_path}"
            ) from exc
        if discovered_path.is_symlink():
            raise SandboxReaperError(
                f"symlink lifecycle documents are forbidden: {discovered_path}"
            )
        try:
            lifecycle = load_lifecycle(resolved_path)
        except SandboxLifecycleError as exc:
            raise SandboxReaperError(str(exc)) from exc
        if lifecycle.backend != backend_name:
            raise SandboxReaperError(
                f"lifecycle backend mismatch at {resolved_path}: "
                f"{lifecycle.backend!r} != {backend_name!r}"
            )
        if lifecycle.cleaned_up:
            continue
        if lifecycle.native_id in pending:
            raise SandboxReaperError(
                f"duplicate native ID {lifecycle.native_id!r} in lifecycle manifests"
            )
        pending[lifecycle.native_id] = (resolved_path, lifecycle)
    return len(manifests), pending


def reap_sandboxes(
    results_root: str | Path,
    *,
    backend: SandboxBackend,
    apply: bool = False,
    at: datetime | None = None,
) -> SandboxReaperReport:
    """Inspect or clean only exact native IDs named by unfinished lifecycles."""

    root = Path(results_root).resolve()
    if not root.is_dir():
        raise SandboxReaperError(f"results root does not exist: {root}")
    backend_name = getattr(backend, "backend_name", None)
    if not isinstance(backend_name, str) or not backend_name:
        raise SandboxReaperError("backend exposes no stable backend_name")
    scanned, pending = _load_pending(root, backend_name=backend_name)

    candidates: list[str] = []
    killed: list[str] = []
    absent: list[str] = []
    mismatched: list[str] = []
    failed: dict[str, str] = {}

    for native_id in sorted(pending):
        path, lifecycle = pending[native_id]
        try:
            state = backend.inspect(native_id)
        except Exception as exc:  # noqa: BLE001 - retain per-ID evidence.
            failed[native_id] = f"inspect {type(exc).__name__}: {exc}"
            continue
        if state is None:
            absent.append(native_id)
            if apply:
                try:
                    mark_cleaned(
                        path,
                        cleanup_method="reaper",
                        cleanup_result="already_absent",
                        at=at,
                    )
                except Exception as exc:  # noqa: BLE001 - retain evidence.
                    failed[native_id] = f"persist {type(exc).__name__}: {exc}"
            continue
        if not _owned_identity_matches(lifecycle, state):
            mismatched.append(native_id)
            continue
        candidates.append(native_id)
        if not apply:
            continue
        try:
            result = backend.kill(native_id)
            if result.native_id != native_id:
                raise SandboxReaperError(
                    f"backend returned a different native ID: {result.native_id!r}"
                )
            if result.outcome == "killed":
                killed.append(native_id)
            elif result.outcome == "already_absent":
                absent.append(native_id)
            else:
                raise SandboxReaperError(
                    f"unsupported kill outcome: {result.outcome!r}"
                )
            mark_cleaned(
                path,
                cleanup_method="reaper",
                cleanup_result=result.outcome,
                at=at,
            )
        except Exception as exc:  # noqa: BLE001 - retain per-ID evidence.
            failed[native_id] = f"kill {type(exc).__name__}: {exc}"

    return SandboxReaperReport(
        scanned_manifests=scanned,
        pending_ids=tuple(candidates),
        killed_ids=tuple(killed),
        absent_ids=tuple(absent),
        identity_mismatch_ids=tuple(mismatched),
        failed=dict(sorted(failed.items())),
        apply=apply,
    )
