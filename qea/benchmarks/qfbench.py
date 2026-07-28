"""Pinned QFBench snapshot loader with an explicit evaluator firewall."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Literal


_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_GITHUB_REPOSITORY_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/"
    r"(?P<repository>[A-Za-z0-9_.-]+?)(?:\.git)?$"
)
_REQUIRED_TASK_PATHS = (
    "instruction.md",
    "task.toml",
    "environment/Dockerfile",
    "tests/test.sh",
)


class QFBenchConfigError(ValueError):
    """The pinned snapshot, manifest, or pilot split is unsafe or inconsistent."""


@dataclass(frozen=True)
class PinnedBlob:
    mode: str
    oid: str
    path: str


QFBenchMaterializationRole = Literal["public", "trusted-verifier", "deny"]


@dataclass(frozen=True)
class QFBenchRoleSnapshotPlan:
    repository_url: str
    commit: str
    task_ids: tuple[str, ...]
    public_blobs: tuple[PinnedBlob, ...]
    trusted_verifier_blobs: tuple[PinnedBlob, ...]
    denied_solution_blobs: tuple[PinnedBlob, ...]


@dataclass(frozen=True)
class QFBenchRoleSnapshotResult:
    public_root: Path
    trusted_root: Path
    public_manifest: Path
    trusted_manifest: Path


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


def git_blob_oid(payload: bytes) -> str:
    """Return the SHA-1 object ID Git assigns to one blob payload."""

    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload).hexdigest()


def list_qfbench_tree_blobs(
    source_repo: str | Path,
    commit: str,
    task_ids: Iterable[str],
) -> tuple[PinnedBlob, ...]:
    """List exact selected blob identities from an already-fetched Git tree."""

    revision = commit.strip().lower()
    if not _COMMIT_RE.fullmatch(revision):
        raise QFBenchConfigError("QFBench commit must be a full 40-character SHA")
    selected = tuple(sorted(set(str(task_id) for task_id in task_ids)))
    if not selected:
        raise QFBenchConfigError("raw QFBench snapshot needs at least one task")
    invalid = [task_id for task_id in selected if not _TASK_ID_RE.fullmatch(task_id)]
    if invalid:
        raise QFBenchConfigError(f"invalid QFBench task IDs for raw fetch: {invalid}")

    repository = Path(source_repo).expanduser().resolve()
    if not (repository / ".git").exists():
        raise QFBenchConfigError(f"QFBench source tree has no Git metadata: {repository}")
    output = _run_git([
        "-C",
        str(repository),
        "ls-tree",
        "-r",
        revision,
        "--",
        "docker",
        *(f"tasks/{task_id}" for task_id in selected),
    ])
    blobs: list[PinnedBlob] = []
    task_hits = {task_id: 0 for task_id in selected}
    for line in output.splitlines():
        identity, separator, path = line.partition("\t")
        fields = identity.split()
        if not separator or len(fields) != 3:
            raise QFBenchConfigError(f"cannot parse QFBench Git tree entry: {line!r}")
        mode, object_type, oid = fields
        if object_type != "blob" or not re.fullmatch(r"[0-9a-f]{40}", oid):
            raise QFBenchConfigError(f"invalid QFBench Git blob entry: {line!r}")
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise QFBenchConfigError(f"unsafe QFBench Git tree path: {path!r}")
        if path.startswith("tasks/"):
            parts = relative.parts
            if len(parts) < 3 or parts[1] not in task_hits:
                raise QFBenchConfigError(f"unexpected QFBench task tree path: {path!r}")
            task_hits[parts[1]] += 1
        elif not path.startswith("docker/"):
            raise QFBenchConfigError(f"unexpected QFBench tree path: {path!r}")
        blobs.append(PinnedBlob(mode=mode, oid=oid, path=relative.as_posix()))
    missing_tasks = [task_id for task_id, count in task_hits.items() if count == 0]
    if missing_tasks:
        raise QFBenchConfigError(
            f"QFBench Git tree is missing selected tasks: {missing_tasks}"
        )
    if not any(blob.path.startswith("docker/") for blob in blobs):
        raise QFBenchConfigError("QFBench Git tree is missing docker files")
    return tuple(sorted(blobs, key=lambda blob: blob.path))


def _github_raw_fetcher(
    repository_url: str,
    commit: str,
) -> Callable[[str], bytes]:
    match = _GITHUB_REPOSITORY_RE.fullmatch(repository_url.strip())
    if match is None:
        raise QFBenchConfigError(
            "raw snapshot materialization requires an official GitHub repository URL"
        )
    base_url = (
        "https://raw.githubusercontent.com/"
        f"{match.group('owner')}/{match.group('repository')}/{commit}/"
    )

    def fetch(path: str) -> bytes:
        request = urllib.request.Request(
            base_url + path,
            headers={"User-Agent": "qea-qfbench-materializer/1"},
        )
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    return response.read()
            except (
                urllib.error.HTTPError,
                urllib.error.URLError,
                TimeoutError,
                OSError,
            ) as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(2 ** attempt)
        raise QFBenchConfigError(
            f"cannot fetch pinned QFBench blob {path!r}: {last_error}"
        )

    return fetch


def materialize_qfbench_raw_snapshot(
    source_repo: str | Path,
    destination: str | Path,
    *,
    repository_url: str,
    commit: str,
    task_ids: Iterable[str],
    fetch_blob: Callable[[str], bytes] | None = None,
) -> Path:
    """Download selected pinned files, verify Git blob IDs, and promote atomically."""

    revision = commit.strip().lower()
    selected = tuple(sorted(set(str(task_id) for task_id in task_ids)))
    blobs = list_qfbench_tree_blobs(source_repo, revision, selected)
    target = Path(destination).expanduser().resolve()
    if target.exists():
        raise QFBenchConfigError(f"refusing existing raw QFBench destination {target}")
    staging = target.with_name(target.name + ".partial")
    staging.mkdir(parents=True, exist_ok=True)
    fetch = fetch_blob or _github_raw_fetcher(repository_url, revision)

    for blob in blobs:
        path = staging / blob.path
        if path.is_file() and git_blob_oid(path.read_bytes()) == blob.oid:
            path.chmod(0o755 if blob.mode == "100755" else 0o644)
            continue
        payload = fetch(blob.path)
        if not isinstance(payload, bytes):
            raise QFBenchConfigError(
                f"raw QFBench fetcher returned non-bytes for {blob.path!r}"
            )
        actual = git_blob_oid(payload)
        if actual != blob.oid:
            raise QFBenchConfigError(
                f"Git blob hash mismatch for {blob.path}: "
                f"expected {blob.oid}, found {actual}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".download")
        temporary.write_bytes(payload)
        temporary.chmod(0o755 if blob.mode == "100755" else 0o644)
        os.replace(temporary, path)

    (staging / ".qfbench-cache").write_text(
        "Dedicated raw QFBench cache; every file verified against the pinned Git tree.\n"
    )
    (staging / ".qfbench-revision").write_text(revision + "\n")
    (staging / ".qfbench-sparse-tasks.json").write_text(
        json.dumps(list(selected), indent=2) + "\n"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging, target)
    return target


def _secret_like_qfbench_path(path: PurePosixPath) -> bool:
    name = path.name.lower()
    return (
        name == ".env"
        or name.startswith(".env.")
        or name.startswith("credentials")
        or name.startswith("secrets")
        or name in {"id_rsa", "id_ed25519"}
        or name.endswith((".pem", ".key"))
    )


def classify_qfbench_path(
    path: str,
    *,
    task_ids: Iterable[str],
) -> QFBenchMaterializationRole:
    """Classify one pinned path without exposing tests or solutions to workers."""

    if not isinstance(path, str):
        return "deny"
    pure = PurePosixPath(path)
    selected = frozenset(str(task_id) for task_id in task_ids)
    if (
        pure.is_absolute()
        or not pure.parts
        or pure.as_posix() != path
        or any(part in {"", ".", ".."} for part in pure.parts)
        or "solution" in pure.parts
        or _secret_like_qfbench_path(pure)
    ):
        return "deny"
    if pure.parts[0] == "docker":
        return "public" if len(pure.parts) >= 2 else "deny"
    if len(pure.parts) < 3 or pure.parts[0] != "tasks":
        return "deny"
    if pure.parts[1] not in selected:
        return "deny"
    task_path = pure.parts[2:]
    if task_path in {("instruction.md",), ("task.toml",)}:
        return "public"
    if task_path[0] == "environment" and len(task_path) >= 2:
        return "public"
    if task_path[0] == "tests" and len(task_path) >= 2:
        return "trusted-verifier"
    return "deny"


def _is_selected_solution(path: str, task_ids: frozenset[str]) -> bool:
    pure = PurePosixPath(path)
    return (
        not pure.is_absolute()
        and len(pure.parts) >= 4
        and pure.parts[0] == "tasks"
        and pure.parts[1] in task_ids
        and pure.parts[2] == "solution"
    )


def plan_qfbench_role_snapshot(
    source_repo: str | Path,
    *,
    repository_url: str,
    commit: str,
    task_ids: Iterable[str],
) -> QFBenchRoleSnapshotPlan:
    """Plan a two-root snapshot and fail closed on unknown selected paths."""

    revision = commit.strip().lower()
    selected = tuple(sorted(set(str(task_id) for task_id in task_ids)))
    selected_set = frozenset(selected)
    if _GITHUB_REPOSITORY_RE.fullmatch(repository_url.strip()) is None:
        raise QFBenchConfigError(
            "role-separated materialization requires an official GitHub repository URL"
        )
    blobs = list_qfbench_tree_blobs(source_repo, revision, selected)
    public: list[PinnedBlob] = []
    trusted: list[PinnedBlob] = []
    denied_solutions: list[PinnedBlob] = []
    for blob in blobs:
        role = classify_qfbench_path(blob.path, task_ids=selected)
        if role == "deny":
            if _is_selected_solution(blob.path, selected_set):
                denied_solutions.append(blob)
                continue
            raise QFBenchConfigError(
                f"unexpected task path is denied by role materializer: {blob.path!r}"
            )
        if blob.mode not in {"100644", "100755"}:
            raise QFBenchConfigError(
                f"role materializer accepts regular files only: "
                f"mode {blob.mode} at {blob.path}"
            )
        (public if role == "public" else trusted).append(blob)

    public_paths = {blob.path for blob in public}
    trusted_paths = {blob.path for blob in trusted}
    for task_id in selected:
        required_public = {
            f"tasks/{task_id}/instruction.md",
            f"tasks/{task_id}/task.toml",
            f"tasks/{task_id}/environment/Dockerfile",
        }
        missing_public = sorted(required_public - public_paths)
        if missing_public:
            raise QFBenchConfigError(
                f"QFBench task {task_id!r} is missing public files: {missing_public}"
            )
        required_test = f"tasks/{task_id}/tests/test.sh"
        if required_test not in trusted_paths:
            raise QFBenchConfigError(
                f"QFBench task {task_id!r} is missing trusted verifier script"
            )
    return QFBenchRoleSnapshotPlan(
        repository_url=repository_url,
        commit=revision,
        task_ids=selected,
        public_blobs=tuple(public),
        trusted_verifier_blobs=tuple(trusted),
        denied_solution_blobs=tuple(denied_solutions),
    )


def _write_verified_role_blobs(
    staging: Path,
    blobs: tuple[PinnedBlob, ...],
    *,
    fetch_blob: Callable[[str], bytes],
    trusted: bool,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for blob in blobs:
        path = staging / blob.path
        payload: bytes
        if path.is_file() and not path.is_symlink():
            payload = path.read_bytes()
            if git_blob_oid(payload) != blob.oid:
                payload = fetch_blob(blob.path)
        else:
            payload = fetch_blob(blob.path)
        if not isinstance(payload, bytes):
            raise QFBenchConfigError(
                f"raw QFBench fetcher returned non-bytes for {blob.path!r}"
            )
        actual_oid = git_blob_oid(payload)
        if actual_oid != blob.oid:
            raise QFBenchConfigError(
                f"Git blob hash mismatch for {blob.path}: "
                f"expected {blob.oid}, found {actual_oid}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".download")
        temporary.write_bytes(payload)
        if trusted:
            temporary.chmod(0o700 if blob.mode == "100755" else 0o600)
        else:
            temporary.chmod(0o755 if blob.mode == "100755" else 0o644)
        os.replace(temporary, path)
        records.append(
            {
                "path": blob.path,
                "mode": blob.mode,
                "git_blob_oid": blob.oid,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    return records


def _role_manifest_payload(
    plan: QFBenchRoleSnapshotPlan,
    *,
    role: Literal["public", "trusted-verifier"],
    records: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "role": role,
        "repository_url": plan.repository_url,
        "commit": plan.commit,
        "task_ids": list(plan.task_ids),
        "files": records,
    }


def _write_role_metadata(
    staging: Path,
    plan: QFBenchRoleSnapshotPlan,
    *,
    role: Literal["public", "trusted-verifier"],
    records: list[dict[str, object]],
    trusted: bool,
) -> None:
    metadata = {
        "MANIFEST.json": json.dumps(
            _role_manifest_payload(plan, role=role, records=records),
            sort_keys=True,
            indent=2,
        )
        + "\n",
        ".qfbench-revision": plan.commit + "\n",
        ".qfbench-sparse-tasks.json": json.dumps(
            list(plan.task_ids), indent=2
        )
        + "\n",
        ".qfbench-cache": (
            "Role-separated QFBench cache; files verified against the pinned Git tree.\n"
        ),
    }
    for name, content in metadata.items():
        path = staging / name
        path.write_text(content)
        path.chmod(0o600 if trusted else 0o644)


def _scan_role_staging(
    staging: Path,
    *,
    expected_paths: set[str],
    role: Literal["public", "trusted-verifier"],
) -> None:
    metadata_paths = {
        "MANIFEST.json",
        ".qfbench-revision",
        ".qfbench-sparse-tasks.json",
        ".qfbench-cache",
    }
    actual_paths: set[str] = set()
    for path in staging.rglob("*"):
        if path.is_symlink():
            raise QFBenchConfigError(
                f"symlink is forbidden in {role} staging: {path}"
            )
        if path.is_file():
            actual_paths.add(path.relative_to(staging).as_posix())
    expected = expected_paths | metadata_paths
    if actual_paths != expected:
        unexpected = sorted(actual_paths - expected)
        missing = sorted(expected - actual_paths)
        raise QFBenchConfigError(
            f"{role} staging membership mismatch; "
            f"unexpected={unexpected}, missing={missing}"
        )
    if any("solution" in PurePosixPath(path).parts for path in actual_paths):
        raise QFBenchConfigError(f"solution path found in {role} staging")


def materialize_qfbench_role_snapshot(
    source_repo: str | Path,
    public_root: str | Path,
    trusted_root: str | Path,
    *,
    repository_url: str,
    commit: str,
    task_ids: Iterable[str],
    fetch_blob: Callable[[str], bytes] | None = None,
) -> QFBenchRoleSnapshotResult:
    """Verify, separate, and promote public and verifier-only snapshot roots."""

    plan = plan_qfbench_role_snapshot(
        source_repo,
        repository_url=repository_url,
        commit=commit,
        task_ids=task_ids,
    )
    public_target = Path(public_root).expanduser().resolve()
    trusted_target = Path(trusted_root).expanduser().resolve()
    if (
        public_target == trusted_target
        or public_target in trusted_target.parents
        or trusted_target in public_target.parents
    ):
        raise QFBenchConfigError("public and trusted roots must be disjoint")
    for target in (public_target, trusted_target):
        if target.exists() or target.is_symlink():
            raise QFBenchConfigError(
                f"refusing existing role-separated QFBench destination {target}"
            )
    public_staging = public_target.with_name(public_target.name + ".partial")
    trusted_staging = trusted_target.with_name(trusted_target.name + ".partial")
    for staging in (public_staging, trusted_staging):
        if staging.is_symlink() or (staging.exists() and not staging.is_dir()):
            raise QFBenchConfigError(f"unsafe QFBench staging path {staging}")
        staging.mkdir(parents=True, exist_ok=True)
    public_staging.chmod(0o750)
    trusted_staging.chmod(0o700)
    fetch = fetch_blob or _github_raw_fetcher(plan.repository_url, plan.commit)

    public_records = _write_verified_role_blobs(
        public_staging,
        plan.public_blobs,
        fetch_blob=fetch,
        trusted=False,
    )
    trusted_records = _write_verified_role_blobs(
        trusted_staging,
        plan.trusted_verifier_blobs,
        fetch_blob=fetch,
        trusted=True,
    )
    _write_role_metadata(
        public_staging,
        plan,
        role="public",
        records=public_records,
        trusted=False,
    )
    _write_role_metadata(
        trusted_staging,
        plan,
        role="trusted-verifier",
        records=trusted_records,
        trusted=True,
    )
    _scan_role_staging(
        public_staging,
        expected_paths={blob.path for blob in plan.public_blobs},
        role="public",
    )
    _scan_role_staging(
        trusted_staging,
        expected_paths={blob.path for blob in plan.trusted_verifier_blobs},
        role="trusted-verifier",
    )

    public_target.parent.mkdir(parents=True, exist_ok=True)
    trusted_target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(public_staging, public_target)
    try:
        os.replace(trusted_staging, trusted_target)
    except OSError:
        os.replace(public_target, public_staging)
        raise
    return QFBenchRoleSnapshotResult(
        public_root=public_target,
        trusted_root=trusted_target,
        public_manifest=public_target / "MANIFEST.json",
        trusted_manifest=trusted_target / "MANIFEST.json",
    )


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
