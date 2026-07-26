"""Recover exact QEA-owned E2B sandboxes from persisted lifecycle manifests."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


class E2BReaperError(RuntimeError):
    """Lifecycle evidence is ambiguous or unsafe to apply."""


@dataclass(frozen=True)
class E2BReaperReport:
    scanned_manifests: int
    pending_ids: tuple[str, ...]
    killed_ids: tuple[str, ...]
    absent_ids: tuple[str, ...]
    failed: dict[str, str]
    apply: bool


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def reap_e2b_sandboxes(
    results_root: str | Path,
    *,
    kill_sandbox: Callable[[str], bool],
    apply: bool = False,
) -> E2BReaperReport:
    """Dry-run or kill only sandbox IDs named by unfinished QEA lifecycle files."""

    root = Path(results_root).resolve()
    if not root.is_dir():
        raise E2BReaperError(f"results root does not exist: {root}")
    manifests = tuple(sorted(root.rglob("*-sandbox-lifecycle.json")))
    pending: dict[str, tuple[Path, dict]] = {}
    for path in manifests:
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise E2BReaperError(f"invalid lifecycle manifest {path}: {exc}") from exc
        if payload.get("schema_version") != 1:
            raise E2BReaperError(f"unsupported lifecycle manifest {path}")
        sandbox_id = payload.get("sandbox_id")
        if not isinstance(sandbox_id, str) or not sandbox_id:
            raise E2BReaperError(f"lifecycle manifest has no sandbox ID: {path}")
        if payload.get("cleaned_up") is True:
            continue
        if sandbox_id in pending:
            raise E2BReaperError(f"duplicate sandbox ID {sandbox_id!r} in lifecycle manifests")
        pending[sandbox_id] = (path, payload)

    killed: list[str] = []
    absent: list[str] = []
    failed: dict[str, str] = {}
    if apply:
        for sandbox_id in sorted(pending):
            path, payload = pending[sandbox_id]
            try:
                existed = bool(kill_sandbox(sandbox_id))
            except Exception as exc:  # noqa: BLE001 - preserve per-ID failure evidence.
                failed[sandbox_id] = f"{type(exc).__name__}: {exc}"
                continue
            (killed if existed else absent).append(sandbox_id)
            payload.update({
                "cleaned_up": True,
                "cleanup_method": "reaper",
                "cleanup_result": "killed" if existed else "already_absent",
                "cleaned_at": datetime.now(timezone.utc).isoformat(),
            })
            _atomic_json(path, payload)

    return E2BReaperReport(
        scanned_manifests=len(manifests),
        pending_ids=tuple(sorted(pending)),
        killed_ids=tuple(killed),
        absent_ids=tuple(absent),
        failed=failed,
        apply=apply,
    )
