#!/usr/bin/env python3
"""Build and publish the measured QuantCodeEval T16/T24 canary image."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.quantcodeeval_images import prepare_quantcodeeval_canary_image_plan
from qea.rootless_images import execute_rootless_image_build


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public_root", type=Path)
    parser.add_argument("trusted_root", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--base-image", required=True)
    parser.add_argument("--docker-host", required=True)
    parser.add_argument("--expected-uid", required=True, type=int)
    args = parser.parse_args()
    plan = prepare_quantcodeeval_canary_image_plan(
        public_root=args.public_root,
        trusted_root=args.trusted_root,
        base_image_ref=args.base_image,
    )
    result = execute_rootless_image_build(
        plan,
        output_root=args.output_root,
        docker_host=args.docker_host,
        expected_uid=args.expected_uid,
    )
    print(result.manifest_path)
    print(result.image_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
