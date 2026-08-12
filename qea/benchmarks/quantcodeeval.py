"""Pinned, role-separated QuantCodeEval public-track adapter.

The upstream artifact publishes prompts, papers, reference implementations,
property definitions, checkers, and verdicts in one repository.  QEA must not
mirror that layout into a worker sandbox.  This module creates two disjoint
views: public paper/prompt/data inputs and trusted checker/data inputs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_TASK_ID_RE = re.compile(r"^T(?:0[1-9]|[12][0-9]|30)$")
_PUBLIC_TRACK = (
    "T01", "T12", "T16", "T18", "T19",
    "T24", "T26", "T27", "T28", "T29",
)
_FORBIDDEN_ROLE_PARTS = frozenset({
    "golden_ref_checker_results.json",
    "golden_ref_metrics.json",
    "strategy_digest.md",
    "properties",
    "trade_log.json",
    "traces",
    "results",
})


class QuantCodeEvalConfigError(ValueError):
    """The source release, manifest, or role split is unsafe/inconsistent."""


@dataclass(frozen=True)
class QuantCodeEvalTask:
    task_id: str
    domain: str
    lineage: str
    difficulty: str
    reward_kind: str
    root: Path
    instruction_path: Path
    worker_files: tuple[Path, ...]
    verifier_files: tuple[Path, ...]
    agent_timeout_seconds: int
    verifier_timeout_seconds: int
    build_timeout_seconds: int
    cpus: int
    memory_mb: int
    resource_source: str = "qea_quantcodeeval_adapter"


@dataclass(frozen=True)
class QuantCodeEvalSplit:
    name: str
    tasks: tuple[QuantCodeEvalTask, ...]

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(task.task_id for task in self.tasks)


@dataclass(frozen=True)
class QuantCodeEvalSnapshot:
    root: Path
    repository_url: str
    commit: str
    optimize: QuantCodeEvalSplit
    held_out: QuantCodeEvalSplit

    @property
    def tasks(self) -> tuple[QuantCodeEvalTask, ...]:
        return self.optimize.tasks + self.held_out.tasks

    def task(self, task_id: str) -> QuantCodeEvalTask:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        raise KeyError(task_id)


@dataclass(frozen=True)
class QuantCodeEvalRoleSnapshotResult:
    public_root: Path
    trusted_root: Path
    public_manifest: Path
    trusted_manifest: Path


@dataclass(frozen=True)
class VerifiedQuantCodeEvalRoleRoot:
    root: Path
    role: str
    commit: str
    task_ids: tuple[str, ...]
    records: dict[str, dict[str, object]]
    manifest_sha256: str


def default_manifest_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data" / "quantcodeeval" / "MANIFEST_CANARY.json"
    )


def default_expansion_panel_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data" / "quantcodeeval" / "PANEL_EXPANSION.json"
    )


def public_track_task_ids() -> tuple[str, ...]:
    return _PUBLIC_TRACK


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _source_revision(root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    revision = proc.stdout.strip().lower()
    if proc.returncode != 0 or not _COMMIT_RE.fullmatch(revision):
        detail = proc.stderr.strip() or revision
        raise QuantCodeEvalConfigError(
            f"cannot read QuantCodeEval source revision: {detail}"
        )
    return revision


def _require_pinned_source_paths(root: Path, paths: tuple[Path, ...]) -> None:
    """Require every consumed upstream file to be tracked and equal to HEAD."""

    relative_paths: list[str] = []
    for path in paths:
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise QuantCodeEvalConfigError(
                f"source path escapes pinned checkout: {path}"
            ) from exc
        relative_paths.append(relative)
    relative_paths = sorted(set(relative_paths))
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", *relative_paths],
        check=False,
        capture_output=True,
        text=True,
    )
    if tracked.returncode != 0:
        raise QuantCodeEvalConfigError(
            "consumed QuantCodeEval source contains an untracked path"
        )
    clean = subprocess.run(
        ["git", "-C", str(root), "diff", "--quiet", "HEAD", "--", *relative_paths],
        check=False,
        capture_output=True,
        text=True,
    )
    if clean.returncode != 0:
        raise QuantCodeEvalConfigError(
            "consumed QuantCodeEval source differs from the pinned commit"
        )


def _regular_files(root: Path) -> tuple[Path, ...]:
    if root.is_symlink() or not root.is_dir():
        raise QuantCodeEvalConfigError(f"missing or unsafe directory {root}")
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise QuantCodeEvalConfigError(f"symlink is forbidden: {path}")
        if path.is_file():
            files.append(path.resolve())
        elif not path.is_dir():
            raise QuantCodeEvalConfigError(f"non-regular entry is forbidden: {path}")
    return tuple(sorted(files, key=lambda item: item.relative_to(root).as_posix()))


def _copy_file(
    source: Path,
    destination: Path,
    *,
    trusted: bool,
    expected_sha256: str | None = None,
) -> None:
    if source.is_symlink() or not source.is_file():
        raise QuantCodeEvalConfigError(f"missing or unsafe source file {source}")
    digest = _sha256(source)
    if expected_sha256 is not None and digest != expected_sha256:
        raise QuantCodeEvalConfigError(
            f"source digest mismatch for {source}: "
            f"expected {expected_sha256}, found {digest}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(0o600 if trusted else 0o644)


def _copy_tree(source: Path, destination: Path) -> None:
    for item in _regular_files(source):
        _copy_file(
            item,
            destination / item.relative_to(source),
            trusted=True,
        )


def _load_protocol_manifest(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalConfigError(f"cannot read protocol manifest: {exc}") from exc
    if payload.get("schema_version") != 1:
        raise QuantCodeEvalConfigError("QuantCodeEval manifest schema_version must be 1")
    if not _COMMIT_RE.fullmatch(str(payload.get("commit", ""))):
        raise QuantCodeEvalConfigError("QuantCodeEval manifest needs a full commit SHA")
    return payload


def _task_splits(manifest: dict, task_panel_path: str | Path | None = None) -> dict:
    if task_panel_path is None:
        pilot = manifest.get("pilot")
    else:
        panel_path = Path(task_panel_path).expanduser().resolve()
        try:
            panel = json.loads(panel_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise QuantCodeEvalConfigError(f"cannot read task panel: {exc}") from exc
        if panel.get("schema_version") != 1:
            raise QuantCodeEvalConfigError("task panel schema_version must be 1")
        pilot = {
            "optimize": panel.get("optimize", []),
            "held_out": panel.get("held_out", []),
        }
    if not isinstance(pilot, dict):
        raise QuantCodeEvalConfigError("manifest pilot must be an object")
    return pilot


def _task_entries(
    manifest: dict,
    task_panel_path: str | Path | None = None,
) -> tuple[dict, ...]:
    pilot = _task_splits(manifest, task_panel_path)
    entries: list[dict] = []
    seen: set[str] = set()
    for split in ("optimize", "held_out"):
        rows = pilot.get(split, [])
        if not isinstance(rows, list):
            raise QuantCodeEvalConfigError(f"manifest pilot.{split} must be a list")
        for row in rows:
            if not isinstance(row, dict):
                raise QuantCodeEvalConfigError("pilot entries must be objects")
            task_id = row.get("task_id")
            if not isinstance(task_id, str) or not _TASK_ID_RE.fullmatch(task_id):
                raise QuantCodeEvalConfigError(f"invalid task ID {task_id!r}")
            if task_id not in _PUBLIC_TRACK:
                raise QuantCodeEvalConfigError(
                    f"task {task_id} is not in the credential-free public track"
                )
            if task_id in seen:
                raise QuantCodeEvalConfigError(f"duplicate task {task_id}")
            seen.add(task_id)
            entries.append(row)
    if not entries:
        raise QuantCodeEvalConfigError("pilot must contain at least one task")
    return tuple(entries)


def _load_public_track(source: Path, protocol: dict) -> dict:
    path = source / "public_track_manifest.json"
    expected = protocol.get("public_track_manifest_sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise QuantCodeEvalConfigError("manifest needs public_track_manifest_sha256")
    if _sha256(path) != expected:
        raise QuantCodeEvalConfigError("public_track_manifest.json digest mismatch")
    payload = json.loads(path.read_text())
    if payload.get("status") != "PASS" or payload.get("track") != "fully-public":
        raise QuantCodeEvalConfigError("upstream public track is not a recorded PASS")
    if tuple(payload.get("task_ids", ())) != _PUBLIC_TRACK:
        raise QuantCodeEvalConfigError("upstream public track task identity drifted")
    if not isinstance(payload.get("tasks"), dict):
        raise QuantCodeEvalConfigError("upstream public-track tasks are missing")
    environment = protocol.get("upstream_environment")
    if not isinstance(environment, dict):
        raise QuantCodeEvalConfigError("manifest upstream_environment is missing")
    for filename, key in (
        ("pyproject.toml", "pyproject_sha256"),
        ("uv.lock", "uv_lock_sha256"),
    ):
        expected_digest = environment.get(key)
        if not isinstance(expected_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected_digest
        ):
            raise QuantCodeEvalConfigError(f"manifest needs {key}")
        if _sha256(source / filename) != expected_digest:
            raise QuantCodeEvalConfigError(f"upstream {filename} digest mismatch")
    return payload


def _adapter_instruction(official: str) -> str:
    return (
        "QEA QUANTCODEEVAL RUNTIME ADAPTER:\n"
        "- The source paper is available at /app/data/paper_text.md.\n"
        "- Save the submitted module as /app/output/strategy.py.\n"
        "- Do not inspect checker, reference, property, or verdict files.\n\n"
        + official.rstrip() + "\n"
    )


def _verifier_script(task_id: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail
mkdir -p /logs/verifier
TARGET=/app/output/strategy.py
RESULT=/logs/verifier/ctrf.json
if [[ ! -f \"$TARGET\" ]]; then
  python3 /tests/qea_score_adapter.py \\
    --manifest /tests/checkers/manifest.json --output \"$RESULT\" --missing-target
else
  PYTHONPATH=/tests python3 /tests/run_checker_harness.py \\
    --checker /tests/checkers/run_all.py --target \"$TARGET\" \\
    --data-dir /tests/data --cwd /app/output --output \"$RESULT\"
fi
python3 /tests/qea_score_adapter.py --manifest /tests/checkers/manifest.json \\
  --input \"$RESULT\" --reward /logs/verifier/reward.txt --task-id {task_id}
"""


def _isolated_loader_source(official: Path, task_id: str) -> bytes:
    client = (
        Path(__file__).resolve().parents[1]
        / "verifiers" / "quantcodeeval_rpc.py"
    ).read_text()
    if task_id != "T24":
        return client.encode("utf-8")
    upstream = official.read_text()
    marker = (
        "# ---------------------------------------------------------------------------\n"
        "# Adaptive calling (aligned with M01/P5 signature)\n"
        "# ---------------------------------------------------------------------------\n"
    )
    if marker not in upstream:
        raise QuantCodeEvalConfigError("T24 module loader adapter marker drifted")
    return (client.rstrip() + "\n\n" + marker + upstream.split(marker, 1)[1]).encode(
        "utf-8"
    )


def _isolated_fuzz_harness_source(official: Path) -> bytes:
    source = official.read_text()
    needle = "def _import_from_path(path: Path, module_name: str) -> ModuleType:\n"
    if source.count(needle) != 1:
        raise QuantCodeEvalConfigError("diff-fuzz import hook drifted")
    replacement = needle + (
        "    if path.name == 'strategy.py':\n"
        "        from shared.module_loader import load_module\n"
        "        return load_module(str(path), module_name)\n"
    )
    return source.replace(needle, replacement).encode("utf-8")


def _trusted_run_all_source(official: Path) -> bytes:
    """Retain official semantics while preserving trusted exception types/traces."""

    source = official.read_text()
    if "import traceback\n" not in source:
        source = source.replace("import sys\n", "import sys\nimport traceback\n", 1)
    needle = '"detail": str(e),'
    if source.count(needle) != 1:
        raise QuantCodeEvalConfigError("run_all exception adapter drifted")
    return source.replace(
        needle,
        '"detail": f"{type(e).__name__}: {e}\\n{traceback.format_exc()}",',
    ).encode("utf-8")


def _relocated_checker_source(official: Path, task_id: str) -> bytes:
    source = official.read_text()
    if task_id == "T24" and official.parent.name == "a10_e2e_metric_consistency":
        needle = "RELEASE_ROOT = HERE.parents[3]"
        if source.count(needle) != 1:
            raise QuantCodeEvalConfigError("T24 A10 release-root adapter drifted")
        source = source.replace(needle, "RELEASE_ROOT = Path('/tests')")
    return source.encode("utf-8")


def _record(path: Path, root: Path, *, source_path: str, generated: bool = False) -> dict:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "source_path": source_path,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "git_blob_oid": _git_blob_oid(payload),
        "size_bytes": len(payload),
        "mode": oct(path.stat().st_mode & 0o777),
        "generated_by_adapter": generated,
    }


def _write_role_manifest(
    root: Path,
    *,
    role: str,
    protocol: dict,
    task_ids: tuple[str, ...],
    records: list[dict],
    trusted: bool,
) -> None:
    payload = {
        "schema_version": 1,
        "benchmark": "quantcodeeval",
        "role": role,
        "repository_url": protocol["repository_url"],
        "commit": protocol["commit"],
        "task_ids": list(task_ids),
        "files": sorted(records, key=lambda item: item["path"]),
    }
    metadata = {
        "MANIFEST.json": json.dumps(payload, sort_keys=True, indent=2) + "\n",
        ".quantcodeeval-revision": protocol["commit"] + "\n",
        ".quantcodeeval-task-ids.json": json.dumps(list(task_ids), indent=2) + "\n",
    }
    for name, text in metadata.items():
        path = root / name
        path.write_text(text)
        path.chmod(0o600 if trusted else 0o644)


def _scan_role(root: Path, *, trusted: bool) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            raise QuantCodeEvalConfigError(f"role snapshot contains symlink {path}")
        relative = path.relative_to(root)
        if any(part in _FORBIDDEN_ROLE_PARTS for part in relative.parts):
            raise QuantCodeEvalConfigError(f"forbidden answer artifact in role: {path}")
        if not trusted and "golden_ref.py" in relative.parts:
            raise QuantCodeEvalConfigError(f"golden reference in public role: {path}")
        if trusted and path.is_file() and path.stat().st_mode & 0o077:
            raise QuantCodeEvalConfigError(f"trusted file is not owner-only: {path}")


_ROLE_METADATA = frozenset({
    "MANIFEST.json",
    ".quantcodeeval-revision",
    ".quantcodeeval-task-ids.json",
})


def verify_quantcodeeval_role_root(
    root: str | Path,
    expected_role: str,
) -> VerifiedQuantCodeEvalRoleRoot:
    """Rehash a complete QuantCodeEval role root and reject extra members."""

    if expected_role not in {"public", "trusted-verifier"}:
        raise QuantCodeEvalConfigError(f"unsupported role {expected_role!r}")
    resolved = Path(root).expanduser().resolve()
    manifest_path = resolved / "MANIFEST.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        payload = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalConfigError(f"cannot load role manifest: {exc}") from exc
    if (
        payload.get("schema_version") != 1
        or payload.get("benchmark") != "quantcodeeval"
        or payload.get("role") != expected_role
    ):
        raise QuantCodeEvalConfigError("QuantCodeEval role identity mismatch")
    commit = payload.get("commit")
    task_ids = payload.get("task_ids")
    if not isinstance(commit, str) or not _COMMIT_RE.fullmatch(commit):
        raise QuantCodeEvalConfigError("invalid role commit")
    if (
        not isinstance(task_ids, list)
        or not task_ids
        or task_ids != sorted(task_ids)
        or len(task_ids) != len(set(task_ids))
        or any(not isinstance(item, str) or not _TASK_ID_RE.fullmatch(item)
               for item in task_ids)
    ):
        raise QuantCodeEvalConfigError("invalid canonical task panel")
    raw_records = payload.get("files")
    if not isinstance(raw_records, list) or not raw_records:
        raise QuantCodeEvalConfigError("role manifest has no files")
    records: dict[str, dict[str, object]] = {}
    manifested_tasks: set[str] = set()
    for raw in raw_records:
        if not isinstance(raw, dict):
            raise QuantCodeEvalConfigError("invalid role file record")
        relative = raw.get("path")
        if not isinstance(relative, str):
            raise QuantCodeEvalConfigError("invalid role path")
        posix = Path(relative)
        if posix.is_absolute() or ".." in posix.parts or posix.as_posix() != relative:
            raise QuantCodeEvalConfigError(f"unsafe role path {relative!r}")
        if relative in records:
            raise QuantCodeEvalConfigError(f"duplicate role path {relative}")
        parts = posix.parts
        if len(parts) < 3 or parts[0] != "tasks" or parts[1] not in task_ids:
            raise QuantCodeEvalConfigError(f"role file outside task panel: {relative}")
        if expected_role == "trusted-verifier" and parts[2] != "tests":
            raise QuantCodeEvalConfigError(f"trusted file outside tests: {relative}")
        if expected_role == "public" and "tests" in parts[2:]:
            raise QuantCodeEvalConfigError(f"tests in public role: {relative}")
        if expected_role == "public" and "golden_ref.py" in parts:
            raise QuantCodeEvalConfigError(f"golden reference in public role: {relative}")
        path = resolved / relative
        if path.is_symlink() or not path.is_file():
            raise QuantCodeEvalConfigError(f"unsafe role member: {relative}")
        file_bytes = path.read_bytes()
        observed_mode = oct(path.stat().st_mode & 0o777)
        if (
            raw.get("sha256") != hashlib.sha256(file_bytes).hexdigest()
            or raw.get("git_blob_oid") != _git_blob_oid(file_bytes)
            or raw.get("size_bytes") != len(file_bytes)
            or raw.get("mode") != observed_mode
        ):
            raise QuantCodeEvalConfigError(f"role record mismatch: {relative}")
        if expected_role == "trusted-verifier" and path.stat().st_mode & 0o077:
            raise QuantCodeEvalConfigError(f"trusted member is not owner-only: {relative}")
        records[relative] = raw
        manifested_tasks.add(parts[1])
    if manifested_tasks != set(task_ids):
        raise QuantCodeEvalConfigError("role task membership mismatch")
    discovered: set[str] = set()
    for path in resolved.rglob("*"):
        relative = path.relative_to(resolved).as_posix()
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise QuantCodeEvalConfigError(f"unsafe role entry: {relative}")
        if path.is_file() and relative not in _ROLE_METADATA:
            discovered.add(relative)
    if discovered != set(records):
        raise QuantCodeEvalConfigError(
            "role file membership mismatch; "
            f"extras={sorted(discovered - set(records))}, "
            f"missing={sorted(set(records) - discovered)}"
        )
    revision = resolved / ".quantcodeeval-revision"
    panel = resolved / ".quantcodeeval-task-ids.json"
    try:
        if revision.read_text().strip() != commit or json.loads(panel.read_text()) != task_ids:
            raise QuantCodeEvalConfigError("role metadata identity mismatch")
    except (OSError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalConfigError(f"invalid role metadata: {exc}") from exc
    return VerifiedQuantCodeEvalRoleRoot(
        root=resolved,
        role=expected_role,
        commit=commit,
        task_ids=tuple(task_ids),
        records=records,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    )


def materialize_quantcodeeval_role_snapshot(
    source_root: str | Path,
    public_root: str | Path,
    trusted_root: str | Path,
    *,
    manifest_path: str | Path | None = None,
    trusted_oracle_root: str | Path | None = None,
    task_panel_path: str | Path | None = None,
) -> QuantCodeEvalRoleSnapshotResult:
    """Create disjoint public and verifier-only roots from a pinned checkout."""

    source = Path(source_root).expanduser().resolve()
    protocol = _load_protocol_manifest(
        Path(manifest_path or default_manifest_path()).expanduser().resolve()
    )
    revision = _source_revision(source)
    if revision != protocol["commit"]:
        raise QuantCodeEvalConfigError(
            f"source commit mismatch: expected {protocol['commit']}, found {revision}"
        )
    public_track = _load_public_track(source, protocol)
    entries = _task_entries(protocol, task_panel_path)
    task_ids = tuple(sorted(entry["task_id"] for entry in entries))
    oracle_root = Path(trusted_oracle_root or source).expanduser().resolve()
    oracle_records = protocol.get("trusted_runtime")
    if not isinstance(oracle_records, dict):
        raise QuantCodeEvalConfigError("manifest trusted_runtime is missing")

    consumed_source_paths = [
        source / "public_track_manifest.json",
        source / "pyproject.toml",
        source / "uv.lock",
        source / "scripts" / "run_checker_harness.py",
        *_regular_files(source / "quantcodeeval"),
    ]
    consumed_oracle_paths: list[Path] = []
    for entry in entries:
        task_id = entry["task_id"]
        source_task = source / "tasks" / task_id
        consumed_source_paths.extend((
            source_task / "sample_instruction.md",
            source_task / "paper_text.md",
            *_regular_files(source_task / "checkers"),
        ))
        consumed_oracle_paths.append(
            oracle_root / "tasks" / task_id / "golden_ref.py"
        )
        track_task = public_track["tasks"].get(task_id)
        input_files = track_task.get("input_files") if isinstance(track_task, dict) else None
        if not isinstance(input_files, list) or not input_files:
            raise QuantCodeEvalConfigError(f"task {task_id} has no public input files")
        for item in input_files:
            source_relative = item.get("path") if isinstance(item, dict) else None
            prefix = f"tasks/{task_id}/data/"
            if not isinstance(source_relative, str) or not source_relative.startswith(prefix):
                raise QuantCodeEvalConfigError(f"task {task_id} input path is invalid")
            relative_data = Path(source_relative[len(prefix):])
            if ".." in relative_data.parts or relative_data.is_absolute():
                raise QuantCodeEvalConfigError(
                    f"task {task_id} input path escapes data root"
                )
            consumed_source_paths.append(source / source_relative)
    _require_pinned_source_paths(source, tuple(consumed_source_paths))
    if _source_revision(oracle_root) != revision:
        raise QuantCodeEvalConfigError("trusted oracle checkout revision mismatch")
    _require_pinned_source_paths(oracle_root, tuple(consumed_oracle_paths))

    public_target = Path(public_root).expanduser().resolve()
    trusted_target = Path(trusted_root).expanduser().resolve()
    if (public_target == trusted_target or public_target in trusted_target.parents
            or trusted_target in public_target.parents):
        raise QuantCodeEvalConfigError("public and trusted roots must be disjoint")
    for target in (public_target, trusted_target):
        if target.exists() or target.is_symlink():
            raise QuantCodeEvalConfigError(f"refusing existing destination {target}")
    public_staging = public_target.with_name(public_target.name + ".partial")
    trusted_staging = trusted_target.with_name(trusted_target.name + ".partial")
    for staging in (public_staging, trusted_staging):
        if staging.exists() or staging.is_symlink():
            raise QuantCodeEvalConfigError(f"refusing existing staging path {staging}")
        staging.mkdir(parents=True)
    public_staging.chmod(0o750)
    trusted_staging.chmod(0o700)

    public_records: list[dict] = []
    trusted_records: list[dict] = []
    runtime_source = (
        Path(__file__).resolve().parents[1] / "verifiers" / "quantcodeeval_runtime.py"
    )
    for entry in entries:
        task_id = entry["task_id"]
        source_task = source / "tasks" / task_id
        track_task = public_track["tasks"].get(task_id)
        if not isinstance(track_task, dict):
            raise QuantCodeEvalConfigError(f"missing public-track record for {task_id}")

        instruction = public_staging / "tasks" / task_id / "instruction.md"
        instruction.parent.mkdir(parents=True)
        instruction.write_text(
            _adapter_instruction((source_task / "sample_instruction.md").read_text())
        )
        instruction.chmod(0o644)
        public_records.append(_record(
            instruction, public_staging,
            source_path=f"tasks/{task_id}/sample_instruction.md", generated=True,
        ))
        paper = public_staging / "tasks" / task_id / "environment" / "data" / "paper_text.md"
        _copy_file(source_task / "paper_text.md", paper, trusted=False)
        public_records.append(_record(
            paper, public_staging, source_path=f"tasks/{task_id}/paper_text.md",
        ))

        input_files = track_task.get("input_files")
        if not isinstance(input_files, list) or not input_files:
            raise QuantCodeEvalConfigError(f"task {task_id} has no public input files")
        for item in input_files:
            source_relative = item.get("path") if isinstance(item, dict) else None
            expected_sha = item.get("sha256") if isinstance(item, dict) else None
            prefix = f"tasks/{task_id}/data/"
            if not isinstance(source_relative, str) or not source_relative.startswith(prefix):
                raise QuantCodeEvalConfigError(f"task {task_id} input path is invalid")
            relative_data = Path(source_relative[len(prefix):])
            if ".." in relative_data.parts or relative_data.is_absolute():
                raise QuantCodeEvalConfigError(f"task {task_id} input path escapes data root")
            source_data = source / source_relative
            public_data = (
                public_staging / "tasks" / task_id
                / "environment" / "data" / relative_data
            )
            trusted_data = (
                trusted_staging / "tasks" / task_id
                / "tests" / "data" / relative_data
            )
            _copy_file(source_data, public_data, trusted=False, expected_sha256=expected_sha)
            _copy_file(source_data, trusted_data, trusted=True, expected_sha256=expected_sha)
            public_records.append(_record(
                public_data, public_staging, source_path=source_relative,
            ))
            trusted_records.append(_record(
                trusted_data, trusted_staging, source_path=source_relative,
            ))

        tests_root = trusted_staging / "tasks" / task_id / "tests"
        _copy_tree(source_task / "checkers", tests_root / "checkers")
        official_run_all = source_task / "checkers" / "run_all.py"
        trusted_run_all = tests_root / "checkers" / "run_all.py"
        trusted_run_all.write_bytes(_trusted_run_all_source(official_run_all))
        trusted_run_all.chmod(0o600)
        for official_checker in sorted(source_task.glob("checkers/*/checker.py")):
            relocated = (
                tests_root / "checkers" / official_checker.parent.name / "checker.py"
            )
            relocated.write_bytes(_relocated_checker_source(official_checker, task_id))
            relocated.chmod(0o600)
        official_loader = source_task / "checkers" / "shared" / "module_loader.py"
        isolated_loader = tests_root / "checkers" / "shared" / "module_loader.py"
        isolated_loader.write_bytes(_isolated_loader_source(official_loader, task_id))
        isolated_loader.chmod(0o600)
        for path in _regular_files(tests_root / "checkers"):
            relative = path.relative_to(tests_root / "checkers")
            trusted_records.append(_record(
                path, trusted_staging,
                source_path=f"tasks/{task_id}/checkers/{relative.as_posix()}",
            ))
        runner = tests_root / "run_checker_harness.py"
        _copy_file(source / "scripts" / "run_checker_harness.py", runner, trusted=True)
        trusted_records.append(_record(
            runner, trusted_staging, source_path="scripts/run_checker_harness.py",
        ))
        _copy_tree(source / "quantcodeeval", tests_root / "quantcodeeval")
        official_harness = source / "quantcodeeval" / "diff_fuzz" / "harness.py"
        isolated_harness = tests_root / "quantcodeeval" / "diff_fuzz" / "harness.py"
        isolated_harness.write_bytes(_isolated_fuzz_harness_source(official_harness))
        isolated_harness.chmod(0o600)
        for path in _regular_files(tests_root / "quantcodeeval"):
            relative = path.relative_to(tests_root / "quantcodeeval")
            trusted_records.append(_record(
                path, trusted_staging,
                source_path=f"quantcodeeval/{relative.as_posix()}",
            ))
        score_adapter = tests_root / "qea_score_adapter.py"
        _copy_file(runtime_source, score_adapter, trusted=True)
        trusted_records.append(_record(
            score_adapter, trusted_staging,
            source_path="qea/verifiers/quantcodeeval_runtime.py", generated=True,
        ))
        oracle_entry = oracle_records.get(task_id)
        expected_golden = (
            oracle_entry.get("golden_ref_sha256")
            if isinstance(oracle_entry, dict) else None
        )
        if not isinstance(expected_golden, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected_golden
        ):
            expected_golden = None
        golden = tests_root / "golden_ref.py"
        _copy_file(
            oracle_root / "tasks" / task_id / "golden_ref.py",
            golden,
            trusted=True,
            expected_sha256=expected_golden,
        )
        trusted_records.append(_record(
            golden,
            trusted_staging,
            source_path=f"tasks/{task_id}/golden_ref.py",
        ))
        test_script = tests_root / "test.sh"
        test_script.write_text(_verifier_script(task_id))
        test_script.chmod(0o600)
        trusted_records.append(_record(
            test_script, trusted_staging,
            source_path="qea QuantCodeEval adapter", generated=True,
        ))

    _write_role_manifest(
        public_staging, role="public", protocol=protocol,
        task_ids=task_ids, records=public_records, trusted=False,
    )
    _write_role_manifest(
        trusted_staging, role="trusted-verifier", protocol=protocol,
        task_ids=task_ids, records=trusted_records, trusted=True,
    )
    for path in trusted_staging.rglob("*"):
        path.chmod(0o700 if path.is_dir() else 0o600)
    _scan_role(public_staging, trusted=False)
    _scan_role(trusted_staging, trusted=True)
    verify_quantcodeeval_role_root(public_staging, "public")
    verify_quantcodeeval_role_root(trusted_staging, "trusted-verifier")

    public_target.parent.mkdir(parents=True, exist_ok=True)
    trusted_target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(public_staging, public_target)
    try:
        os.replace(trusted_staging, trusted_target)
    except OSError:
        os.replace(public_target, public_staging)
        raise
    return QuantCodeEvalRoleSnapshotResult(
        public_root=public_target,
        trusted_root=trusted_target,
        public_manifest=public_target / "MANIFEST.json",
        trusted_manifest=trusted_target / "MANIFEST.json",
    )


def _required_string(entry: dict, key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise QuantCodeEvalConfigError(f"task entry has invalid {key!r}")
    return value.strip()


def _positive_int(entry: dict, key: str) -> int:
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise QuantCodeEvalConfigError(f"task entry has invalid {key!r}")
    return value


def _load_task(public_root: Path, entry: dict) -> QuantCodeEvalTask:
    task_id = _required_string(entry, "task_id")
    root = (public_root / "tasks" / task_id).resolve()
    instruction = root / "instruction.md"
    data = root / "environment" / "data"
    if not instruction.is_file() or not data.is_dir():
        raise QuantCodeEvalConfigError(f"public task {task_id} is incomplete")
    worker_files = (*_regular_files(data), instruction.resolve())
    return QuantCodeEvalTask(
        task_id=task_id,
        domain=_required_string(entry, "domain"),
        lineage=_required_string(entry, "lineage"),
        difficulty=_required_string(entry, "difficulty"),
        reward_kind=_required_string(entry, "reward_kind"),
        root=root,
        instruction_path=instruction.resolve(),
        worker_files=tuple(sorted(
            worker_files, key=lambda path: path.relative_to(root).as_posix()
        )),
        verifier_files=(),
        agent_timeout_seconds=_positive_int(entry, "agent_timeout_seconds"),
        verifier_timeout_seconds=_positive_int(entry, "verifier_timeout_seconds"),
        build_timeout_seconds=_positive_int(entry, "build_timeout_seconds"),
        cpus=_positive_int(entry, "cpus"),
        memory_mb=_positive_int(entry, "memory_mb"),
    )


def load_quantcodeeval_snapshot(
    public_root: str | Path,
    *,
    manifest_path: str | Path | None = None,
    task_panel_path: str | Path | None = None,
) -> QuantCodeEvalSnapshot:
    """Load a materialized public role using the QEA canary split."""

    root = Path(public_root).expanduser().resolve()
    protocol = _load_protocol_manifest(
        Path(manifest_path or default_manifest_path()).expanduser().resolve()
    )
    verified = verify_quantcodeeval_role_root(root, "public")
    if verified.commit != protocol["commit"]:
        raise QuantCodeEvalConfigError("materialized revision mismatch")
    role_manifest = json.loads((root / "MANIFEST.json").read_text())
    pilot = _task_splits(protocol, task_panel_path)
    expected_ids = tuple(
        entry["task_id"] for entry in _task_entries(protocol, task_panel_path)
    )
    if role_manifest.get("role") != "public" or tuple(
        role_manifest.get("task_ids", ())
    ) != expected_ids:
        raise QuantCodeEvalConfigError("public role identity mismatch")
    return QuantCodeEvalSnapshot(
        root=root,
        repository_url=protocol["repository_url"],
        commit=protocol["commit"],
        optimize=QuantCodeEvalSplit(
            "optimize",
            tuple(_load_task(root, row) for row in pilot["optimize"]),
        ),
        held_out=QuantCodeEvalSplit(
            "held_out",
            tuple(_load_task(root, row) for row in pilot.get("held_out", [])),
        ),
    )
