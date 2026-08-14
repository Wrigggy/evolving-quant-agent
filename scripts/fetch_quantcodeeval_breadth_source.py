#!/usr/bin/env python3
"""Fetch a pinned allowlist of QuantCodeEval files from the public 4open mirror.

Paths are read from stdin so the allowlist can come directly from a local
`git ls-tree` over the repository's already pinned upstream revision.  The
result is coordinator-only source material; public/trusted task views are made
later by the benchmark adapter.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


BASE_URL = (
    "https://anonymous.4open.science/api/repo/"
    "QuantCodeEval-Anonymous/file/"
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source-label", default="QuantCodeEval public release")
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def _paths() -> list[str]:
    paths = [line.strip() for line in sys.stdin if line.strip()]
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("stdin must contain a non-empty unique path allowlist")
    for path in paths:
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"unsafe source path: {path}")
    return sorted(paths)


def _download(destination: Path, relative: str) -> dict[str, object]:
    url = BASE_URL + quote(relative, safe="/")
    request = Request(url, headers={"User-Agent": "QEA-breadth-canary/1.0"})
    with urlopen(request, timeout=60) as response:
        payload = response.read()
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".partial")
    temporary.write_bytes(payload)
    os.replace(temporary, target)
    target.chmod(0o600)
    return {"path": relative, "size_bytes": len(payload)}


def main() -> int:
    args = _arguments()
    if not 1 <= args.workers <= 16:
        raise ValueError("workers must be between 1 and 16")
    destination = args.destination.expanduser().resolve()
    if destination.exists():
        raise ValueError(f"destination already exists: {destination}")
    destination.mkdir(parents=True, mode=0o700)
    paths = _paths()
    records: list[dict[str, object]] = []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(_download, destination, relative): relative
                for relative in paths
            }
            for future in as_completed(futures):
                records.append(future.result())
        setup = {
            "schema_version": 1,
            "source": args.source_label,
            "retrieved_from": "anonymous.4open.science public mirror",
            "task_ids": ["T26", "T27"],
            "files": sorted(records, key=lambda row: str(row["path"])),
            "file_count": len(records),
            "total_bytes": sum(int(row["size_bytes"]) for row in records),
            "purpose": "coordinator-only breadth-canary source setup",
        }
        setup_path = destination / "SETUP.json"
        setup_path.write_text(
            json.dumps(setup, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        setup_path.chmod(0o600)
        print(json.dumps({key: setup[key] for key in ("file_count", "total_bytes")}))
        return 0
    except Exception:
        (destination / "FETCH-INCOMPLETE").write_text(
            "Download stopped before SETUP.json was complete.\n", encoding="utf-8"
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
