#!/usr/bin/env python3
"""Snapshot exact Docker image identities used by a QuantCodeEval canary."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _inspect(reference: str) -> dict[str, object]:
    completed = subprocess.run(
        ["docker", "image", "inspect", reference],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError(f"docker returned an invalid inspect record for {reference}")
    row = payload[0]
    image_id = row.get("Id")
    if not isinstance(image_id, str) or _IMAGE_ID.fullmatch(image_id) is None:
        raise ValueError(f"docker returned an invalid image ID for {reference}")
    repo_digests = row.get("RepoDigests") or []
    if not isinstance(repo_digests, list) or any(
        not isinstance(value, str) for value in repo_digests
    ):
        raise ValueError(f"docker returned invalid repo digests for {reference}")
    return {
        "architecture": row.get("Architecture"),
        "created": row.get("Created"),
        "id": image_id,
        "os": row.get("Os"),
        "reference": reference,
        "repo_digests": sorted(repo_digests),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-commit", required=True)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--verifier-image", required=True)
    parser.add_argument("--proxy-image", required=True)
    parser.add_argument("--no-model-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    no_model = args.no_model_result.resolve()
    no_model_payload = no_model.read_bytes()
    result = {
        "schema_version": 1,
        "benchmark": "quantcodeeval",
        "benchmark_commit": args.benchmark_commit,
        "kind": "measured-image-set",
        "images": {
            "proxy": _inspect(args.proxy_image),
            "verifier": _inspect(args.verifier_image),
            "worker": _inspect(args.worker_image),
        },
        "no_model_result_sha256": hashlib.sha256(no_model_payload).hexdigest(),
    }
    encoded = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode("utf-8")
    output = args.output.resolve()
    if output.exists() or output.is_symlink():
        if output.is_symlink() or not output.is_file() or output.read_bytes() != encoded:
            raise ValueError(f"immutable image snapshot differs: {output}")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        partial = output.with_name(output.name + ".partial")
        if partial.exists() or partial.is_symlink():
            raise FileExistsError(f"stale image snapshot partial exists: {partial}")
        partial.write_bytes(encoded)
        os.chmod(partial, 0o600)
        os.replace(partial, output)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
