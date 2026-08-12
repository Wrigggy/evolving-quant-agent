#!/usr/bin/env python3
"""Publish a local content-addressed QuantCodeEval engineering release."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

if __name__ == "__main__":
    # Importing from a source input must not create bytecode drift in that tree.
    sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.quantcodeeval_release import (  # noqa: E402
    QuantCodeEvalReleaseError,
    build_quantcodeeval_release_manifest,
    publish_quantcodeeval_release,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    parser.add_argument("--image-result", type=Path, required=True)
    parser.add_argument("--no-model-audit-result", type=Path, required=True)
    parser.add_argument("--h0-result", type=Path)
    parser.add_argument("--pgbhs-result", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Print the fully rehashed manifest without creating a release.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    common = {
        "source_root": args.source_root,
        "public_root": args.public_root,
        "trusted_root": args.trusted_root,
        "image_result": args.image_result,
        "no_model_audit_result": args.no_model_audit_result,
        "h0_result": args.h0_result,
        "pgbhs_result": args.pgbhs_result,
    }
    try:
        if args.plan_only:
            payload = build_quantcodeeval_release_manifest(**common)
        else:
            payload = asdict(
                publish_quantcodeeval_release(
                    **common,
                    output_root=args.output_root,
                )
            )
            payload["release_dir"] = str(payload["release_dir"])
            payload["manifest_path"] = str(payload["manifest_path"])
    except QuantCodeEvalReleaseError as exc:
        parser.error(str(exc))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
