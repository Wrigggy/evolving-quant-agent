#!/usr/bin/env python3
"""Derive an owner-only rootless config with one exact model/provider route."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


_ROUTE_VALUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")


def derive_route_config(
    source: Path,
    destination: Path,
    *,
    model: str,
    provider: str,
) -> dict[str, object]:
    """Copy one config while replacing only its bound model route."""

    if not _ROUTE_VALUE.fullmatch(model):
        raise ValueError("model route is unsafe")
    if not _ROUTE_VALUE.fullmatch(provider):
        raise ValueError("provider route is unsafe")
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("source config must be a JSON object")
    if payload.get("schema_version") not in {2, 3, 4, 5}:
        raise ValueError("source config must bind a required provider")
    if not isinstance(payload.get("allowed_model"), str) or not isinstance(
        payload.get("required_provider"), str
    ):
        raise ValueError("source config has no exact model/provider route")

    derived = dict(payload)
    derived["allowed_model"] = model
    derived["required_provider"] = provider
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(derived, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        destination.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()
    return derived


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--provider", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    derived = derive_route_config(
        args.source.expanduser().resolve(),
        args.destination.expanduser().resolve(),
        model=args.model,
        provider=args.provider,
    )
    print(
        json.dumps(
            {
                "destination": str(args.destination.expanduser().resolve()),
                "schema_version": derived["schema_version"],
                "allowed_model": derived["allowed_model"],
                "required_provider": derived["required_provider"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
