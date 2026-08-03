#!/usr/bin/env python3
"""Remain in one PID/PGID until an exact owner-only release permits exec."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import time
from pathlib import Path


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
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


def _release(path: Path) -> dict | None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None
    with os.fdopen(descriptor, "rb", closefd=True) as source:
        metadata = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            return None
        raw = source.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = tuple(args.argv[1:] if args.argv[:1] == ["--"] else args.argv)
    if not command or args.timeout_seconds < 1:
        raise ValueError("gate requires an exact command and positive timeout")
    command_sha256 = hashlib.sha256(
        ("\x00".join(command) + "\x00").encode()
    ).hexdigest()
    gate_dir = args.gate_dir.resolve()
    gate_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(gate_dir, 0o700)
    ready = {
        "schema_version": 1,
        "run_id": args.run_id,
        "source_commit": args.source_commit,
        "command_sha256": command_sha256,
        "pid": os.getpid(),
        "process_group_id": os.getpgrp(),
    }
    _atomic_json(gate_dir / "gate-ready.json", ready)
    expected_release = {
        "schema_version": 1,
        "run_id": args.run_id,
        "source_commit": args.source_commit,
        "command_sha256": command_sha256,
    }
    deadline = time.monotonic() + args.timeout_seconds
    release_path = gate_dir / "gate-release.json"
    while time.monotonic() < deadline:
        if _release(release_path) == expected_release:
            os.execve(command[0], command, dict(os.environ))
        time.sleep(0.05)
    raise TimeoutError("pre-exec gate release timed out")


if __name__ == "__main__":
    raise SystemExit(main())
