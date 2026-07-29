"""Pure-standard-library worker directory identity hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path


class WorkerIdentityError(ValueError):
    """A worker directory cannot produce a safe deterministic identity."""


def hash_worker_directory(root: str | Path) -> str:
    """Hash regular worker files while rejecting symlinks and local caches."""

    directory = Path(root).resolve()
    if not directory.is_dir():
        raise WorkerIdentityError(f"worker directory does not exist: {directory}")
    digest = hashlib.sha256()
    members = tuple(directory.rglob("*"))
    symlinks = [path.relative_to(directory) for path in members if path.is_symlink()]
    if symlinks:
        raise WorkerIdentityError(
            f"worker directory contains forbidden symlinks: {symlinks[:3]}"
        )
    files = sorted(
        (
            path
            for path in members
            if path.is_file()
            and ".git" not in path.parts
            and "__pycache__" not in path.parts
        ),
        key=lambda path: path.relative_to(directory).as_posix(),
    )
    for path in files:
        relative = path.relative_to(directory).as_posix().encode()
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()
