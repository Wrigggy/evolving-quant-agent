#!/usr/bin/env python3
"""Preserve the exact coordinator sources named by an H0 preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_root.resolve()
    run = args.run_dir.resolve()
    preflight_path = run / "H0-PREFLIGHT.json"
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    records = preflight.get("coordinator_source_sha256")
    if not isinstance(records, dict) or not records:
        raise ValueError("H0 preflight has no coordinator source identity")
    identity = str(preflight["runtime_identity_sha256"])
    target = run / "runtime-source" / identity
    manifest = {
        "schema_version": 1,
        "runtime_identity_sha256": identity,
        "files": records,
    }
    manifest_bytes = (
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise ValueError("runtime source snapshot target is unsafe")
        if (target / "MANIFEST.json").read_bytes() != manifest_bytes:
            raise ValueError("runtime source snapshot manifest differs")
        for relative, expected in records.items():
            path = target / "qea" / relative
            if (
                path.is_symlink()
                or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected
            ):
                raise ValueError(f"runtime source snapshot drifted: {relative}")
        print(json.dumps(manifest, sort_keys=True))
        return 0
    staging = target.with_name(target.name + ".partial")
    if staging.exists() or staging.is_symlink():
        raise FileExistsError(f"runtime source staging exists: {staging}")
    staging.mkdir(parents=True)
    for relative, expected in sorted(records.items()):
        origin = source / "qea" / relative
        payload = origin.read_bytes()
        if origin.is_symlink() or hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f"active runtime source differs: {relative}")
        destination = staging / "qea" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        destination.chmod(0o600)
    (staging / "MANIFEST.json").write_bytes(manifest_bytes)
    (staging / "MANIFEST.json").chmod(0o600)
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging, target)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
