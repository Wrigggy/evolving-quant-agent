#!/usr/bin/env python3
"""Build and revalidate a canonical manifest for a staged A6 source release."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    # A6 releases are content-addressed and must not be mutated by imports.
    sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.a6_source_release import (  # noqa: E402
    build_a6_source_release_manifest,
    validate_a6_source_release,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release-root",
        type=Path,
        required=True,
        help="Pre-staged allowlisted release tree; no files are copied or deleted.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Output manifest path, which must be outside the release root.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Atomically replace an existing external manifest.",
    )
    args = parser.parse_args(argv)

    build_a6_source_release_manifest(
        args.release_root,
        args.manifest,
        overwrite=args.overwrite,
    )
    report = validate_a6_source_release(args.release_root, args.manifest)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
