"""Pinned QFBench snapshot loader with an explicit evaluator firewall."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_REQUIRED_TASK_PATHS = (
    "instruction.md",
    "task.toml",
    "environment/Dockerfile",
    "tests/test.sh",
)


class QFBenchConfigError(ValueError):
    """The pinned snapshot, manifest, or pilot split is unsafe or inconsistent."""


@dataclass(frozen=True)
class QFBenchTask:
    task_id: str
    domain: str
    lineage: str
    difficulty: str
    reward_kind: str
    root: Path
    instruction_path: Path
    dockerfile_path: Path
    worker_files: tuple[Path, ...]
    verifier_files: tuple[Path, ...]
    agent_timeout_seconds: int
    verifier_timeout_seconds: int
    build_timeout_seconds: int
    cpus: int
    memory_mb: int
    copy_oracle: bool = False


@dataclass(frozen=True)
class QFBenchSplit:
    name: str
    tasks: tuple[QFBenchTask, ...]

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(task.task_id for task in self.tasks)


@dataclass(frozen=True)
class QFBenchSnapshot:
    root: Path
    repository_url: str
    commit: str
    optimize: QFBenchSplit
    held_out: QFBenchSplit
    copy_oracle_tasks: frozenset[str]
    inoperable_tasks: frozenset[str]

    @property
    def tasks(self) -> tuple[QFBenchTask, ...]:
        return self.optimize.tasks + self.held_out.tasks

    def task(self, task_id: str) -> QFBenchTask:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        raise KeyError(task_id)


def default_manifest_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "qfbench" / "MANIFEST.json"


def _run_git(args: list[str], *, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        raise QFBenchConfigError(f"git command failed: {detail}")
    return proc.stdout.strip()


def materialize_qfbench_snapshot(
    repository_url: str,
    destination: str | Path,
    commit: str,
    *,
    force: bool = False,
    task_ids: Iterable[str] | None = None,
) -> Path:
    """Fetch one exact commit, optionally as a pilot-only sparse snapshot."""

    revision = commit.strip().lower()
    if not _COMMIT_RE.fullmatch(revision):
        raise QFBenchConfigError("QFBench commit must be a full 40-character SHA")
    destination_path = Path(destination).expanduser().resolve()
    sentinel = destination_path / ".qfbench-cache"
    sparse_tasks: tuple[str, ...] | None = None
    if task_ids is not None:
        sparse_tasks = tuple(sorted(set(str(task_id) for task_id in task_ids)))
        if not sparse_tasks:
            raise QFBenchConfigError("sparse QFBench snapshot needs at least one task")
        invalid = [task_id for task_id in sparse_tasks if not _TASK_ID_RE.fullmatch(task_id)]
        if invalid:
            raise QFBenchConfigError(f"invalid QFBench task IDs for sparse fetch: {invalid}")

    if destination_path.exists():
        if not sentinel.is_file() or not (destination_path / ".git").exists():
            raise QFBenchConfigError(
                f"refusing existing non-QFBench-cache destination {destination_path}"
            )
        dirty = _run_git(
            ["-C", str(destination_path), "status", "--porcelain", "--untracked-files=no"]
        )
        if dirty and not force:
            raise QFBenchConfigError(f"QFBench cache {destination_path} is dirty")
        try:
            current = _run_git(["-C", str(destination_path), "rev-parse", "HEAD"]).lower()
        except QFBenchConfigError:
            current = ""
        if current != revision and not force:
            if current:
                raise QFBenchConfigError(
                    f"QFBench cache commit mismatch: expected {revision}, found {current}"
                )
    else:
        destination_path.mkdir(parents=True)
        _run_git(["init", str(destination_path)])
        _run_git(["-C", str(destination_path), "remote", "add", "origin", repository_url])
        sentinel.write_text("Dedicated QFBench cache; safe target for --force refresh.\n")

    current = ""
    try:
        current = _run_git(["-C", str(destination_path), "rev-parse", "HEAD"]).lower()
    except QFBenchConfigError:
        pass
    if current != revision or force:
        _run_git([
            "-C", str(destination_path), "fetch", "--filter=blob:none", "--depth=1",
            "origin", revision,
        ])
    if sparse_tasks is not None:
        _run_git(["-C", str(destination_path), "sparse-checkout", "init", "--cone"])
        _run_git([
            "-C", str(destination_path), "sparse-checkout", "set", "docker",
            *(f"tasks/{task_id}" for task_id in sparse_tasks),
        ])
    elif (destination_path / ".git" / "info" / "sparse-checkout").is_file():
        _run_git(["-C", str(destination_path), "sparse-checkout", "disable"])
    if current != revision or force:
        _run_git([
            "-C", str(destination_path), "checkout", "--detach",
            *( ["--force"] if force else [] ),
            revision,
        ])

    actual = _run_git(["-C", str(destination_path), "rev-parse", "HEAD"]).lower()
    if actual != revision:
        raise QFBenchConfigError(
            f"materialized QFBench commit mismatch: expected {revision}, found {actual}"
        )
    sentinel.write_text("Dedicated QFBench cache; safe target for --force refresh.\n")
    (destination_path / ".qfbench-revision").write_text(revision + "\n")
    sparse_marker = destination_path / ".qfbench-sparse-tasks.json"
    if sparse_tasks is not None:
        sparse_marker.write_text(json.dumps(list(sparse_tasks), indent=2) + "\n")
    elif sparse_marker.exists():
        sparse_marker.unlink()
    return destination_path


def _snapshot_revision(root: Path) -> str:
    marker = root / ".qfbench-revision"
    if marker.is_file():
        revision = marker.read_text().strip().lower()
    elif (root / ".git").exists():
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise QFBenchConfigError(f"cannot read QFBench git revision: {proc.stderr.strip()}")
        revision = proc.stdout.strip().lower()
    else:
        raise QFBenchConfigError(
            f"QFBench snapshot {root} has neither .git nor .qfbench-revision"
        )
    if not _COMMIT_RE.fullmatch(revision):
        raise QFBenchConfigError(f"invalid QFBench revision {revision!r}")
    return revision


def _files_under(root: Path) -> tuple[Path, ...]:
    if not root.exists():
        return ()
    return tuple(sorted((path.resolve() for path in root.rglob("*") if path.is_file()),
                        key=lambda path: path.as_posix()))


def _require_string(entry: dict, key: str, task_id: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise QFBenchConfigError(f"task {task_id!r} has invalid {key!r}")
    return value.strip()


def _task_resource_contract(task_root: Path, task_id: str) -> dict[str, int]:
    """Read the small scalar resource contract from QFBench's task.toml."""

    text = (task_root / "task.toml").read_text()

    def scalar(section: str, key: str) -> str:
        section_match = re.search(
            rf"(?ms)^\[{re.escape(section)}\]\s*(.*?)(?=^\[|\Z)", text
        )
        if section_match is None:
            raise QFBenchConfigError(f"task {task_id!r} is missing [{section}]")
        value_match = re.search(
            rf"(?m)^\s*{re.escape(key)}\s*=\s*([^#\n]+)", section_match.group(1)
        )
        if value_match is None:
            raise QFBenchConfigError(
                f"task {task_id!r} is missing [{section}].{key}"
            )
        return value_match.group(1).strip()

    def positive_integer(section: str, key: str) -> int:
        raw = scalar(section, key)
        try:
            value = float(raw)
        except ValueError as exc:
            raise QFBenchConfigError(
                f"task {task_id!r} has invalid [{section}].{key}: {raw!r}"
            ) from exc
        if value <= 0 or not value.is_integer():
            raise QFBenchConfigError(
                f"task {task_id!r} requires positive integer [{section}].{key}"
            )
        return int(value)

    memory_raw = scalar("environment", "memory").strip('"\'').upper()
    memory_match = re.fullmatch(r"([1-9][0-9]*)(M|G)", memory_raw)
    if memory_match is None:
        raise QFBenchConfigError(
            f"task {task_id!r} has invalid [environment].memory: {memory_raw!r}"
        )
    memory_value = int(memory_match.group(1))
    memory_mb = memory_value * (1024 if memory_match.group(2) == "G" else 1)
    return {
        "agent_timeout_seconds": positive_integer("agent", "timeout_sec"),
        "verifier_timeout_seconds": positive_integer("verifier", "timeout_sec"),
        "build_timeout_seconds": positive_integer("environment", "build_timeout_sec"),
        "cpus": positive_integer("environment", "cpus"),
        "memory_mb": memory_mb,
    }


def _load_task(
    root: Path,
    entry: dict,
    copy_oracles: frozenset[str],
    inoperable: frozenset[str],
) -> QFBenchTask:
    if not isinstance(entry, dict):
        raise QFBenchConfigError("pilot task entries must be objects")
    task_id = _require_string(entry, "task_id", "<unknown>")
    if task_id in copy_oracles:
        raise QFBenchConfigError(f"copy-oracle task {task_id!r} cannot enter a pilot split")
    if task_id in inoperable:
        raise QFBenchConfigError(
            f"inoperable task {task_id!r} cannot enter a pilot split at this commit"
        )

    task_root = (root / "tasks" / task_id).resolve()
    if not task_root.is_dir():
        raise QFBenchConfigError(f"QFBench task {task_id!r} is not present in snapshot")
    for relative in _REQUIRED_TASK_PATHS:
        if not (task_root / relative).is_file():
            raise QFBenchConfigError(f"task {task_id!r} is missing {relative}")

    instruction = (task_root / "instruction.md").resolve()
    resources = _task_resource_contract(task_root, task_id)
    worker_files = _files_under(task_root / "environment" / "data") + (instruction,)
    worker_files = tuple(sorted(worker_files, key=lambda path: path.relative_to(task_root).as_posix()))
    verifier_files = _files_under(task_root / "tests")
    return QFBenchTask(
        task_id=task_id,
        domain=_require_string(entry, "domain", task_id),
        lineage=_require_string(entry, "lineage", task_id),
        difficulty=_require_string(entry, "difficulty", task_id),
        reward_kind=_require_string(entry, "reward_kind", task_id),
        root=task_root,
        instruction_path=instruction,
        dockerfile_path=(task_root / "environment" / "Dockerfile").resolve(),
        worker_files=worker_files,
        verifier_files=verifier_files,
        **resources,
    )


def _load_split(
    root: Path,
    name: str,
    entries: Iterable[dict],
    copy_oracles: frozenset[str],
    inoperable: frozenset[str],
) -> QFBenchSplit:
    tasks = tuple(_load_task(root, entry, copy_oracles, inoperable) for entry in entries)
    task_ids = [task.task_id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise QFBenchConfigError(f"duplicate task in {name} split")
    if not tasks:
        raise QFBenchConfigError(f"{name} split must not be empty")
    return QFBenchSplit(name=name, tasks=tasks)


def _reject_cross_split_input_hash_overlap(
    optimize: QFBenchSplit,
    held_out: QFBenchSplit,
) -> None:
    def by_hash(split: QFBenchSplit) -> dict[str, list[tuple[str, str]]]:
        indexed: dict[str, list[tuple[str, str]]] = {}
        for task in split.tasks:
            data_root = task.root / "environment" / "data"
            for path in _files_under(data_root):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                relative = path.relative_to(data_root).as_posix()
                indexed.setdefault(digest, []).append((task.task_id, relative))
        return indexed

    optimize_hashes = by_hash(optimize)
    held_out_hashes = by_hash(held_out)
    overlap = sorted(set(optimize_hashes) & set(held_out_hashes))
    if not overlap:
        return
    details = []
    for digest in overlap:
        for optimize_item in optimize_hashes[digest]:
            for held_out_item in held_out_hashes[digest]:
                details.append(
                    f"optimize {optimize_item[0]}/{optimize_item[1]} == "
                    f"held_out {held_out_item[0]}/{held_out_item[1]}"
                )
    raise QFBenchConfigError(
        "input data hash overlap between optimize and held_out: "
        + "; ".join(sorted(details))
    )


def load_qfbench_snapshot(
    root: str | Path,
    *,
    manifest_path: str | Path | None = None,
) -> QFBenchSnapshot:
    """Load the preregistered QFBench pilot without exposing solution files."""

    root_path = Path(root).expanduser().resolve()
    manifest_file = Path(manifest_path or default_manifest_path()).expanduser().resolve()
    try:
        manifest = json.loads(manifest_file.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise QFBenchConfigError(f"cannot load QFBench manifest {manifest_file}: {exc}") from exc

    if manifest.get("schema_version") != 1:
        raise QFBenchConfigError("unsupported QFBench manifest schema")
    expected_commit = str(manifest.get("commit", "")).lower()
    if not _COMMIT_RE.fullmatch(expected_commit):
        raise QFBenchConfigError("manifest commit must be a full 40-character SHA")
    actual_commit = _snapshot_revision(root_path)
    if actual_commit != expected_commit:
        raise QFBenchConfigError(
            f"QFBench commit mismatch: expected {expected_commit}, found {actual_commit}"
        )

    copy_oracles = frozenset(str(item) for item in manifest.get("copy_oracle_tasks", ()))
    inoperable_entries = manifest.get("inoperable_tasks", [])
    if not isinstance(inoperable_entries, list):
        raise QFBenchConfigError("manifest inoperable_tasks must be an array")
    inoperable_ids: list[str] = []
    for entry in inoperable_entries:
        if not isinstance(entry, dict):
            raise QFBenchConfigError("inoperable task entries must be objects")
        task_id = _require_string(entry, "task_id", "<inoperable>")
        _require_string(entry, "reason", task_id)
        inoperable_ids.append(task_id)
    inoperable = frozenset(inoperable_ids)
    pilot = manifest.get("pilot")
    if not isinstance(pilot, dict):
        raise QFBenchConfigError("manifest must contain a pilot object")
    optimize = _load_split(
        root_path, "optimize", pilot.get("optimize", ()), copy_oracles, inoperable
    )
    held_out = _load_split(
        root_path, "held_out", pilot.get("held_out", ()), copy_oracles, inoperable
    )

    overlap = set(optimize.task_ids) & set(held_out.task_ids)
    if overlap:
        raise QFBenchConfigError(f"task overlap between optimize and held_out: {sorted(overlap)}")
    lineage_overlap = {task.lineage for task in optimize.tasks} & {
        task.lineage for task in held_out.tasks
    }
    if lineage_overlap:
        raise QFBenchConfigError(
            f"lineage overlap between optimize and held_out: {sorted(lineage_overlap)}"
        )
    _reject_cross_split_input_hash_overlap(optimize, held_out)

    repository_url = manifest.get("repository_url")
    if not isinstance(repository_url, str) or not repository_url:
        raise QFBenchConfigError("manifest repository_url must be non-empty")
    return QFBenchSnapshot(
        root=root_path,
        repository_url=repository_url,
        commit=actual_commit,
        optimize=optimize,
        held_out=held_out,
        copy_oracle_tasks=copy_oracles,
        inoperable_tasks=inoperable,
    )
