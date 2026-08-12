"""Durable one-shot model boundary for fail-closed A6 run identities."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Mapping, Sequence


_MARKER_NAME = "pilot-model-boundary.json"
_SHA256_FIELDS = (
    "identity_record_sha256",
    "materialized_launch_identity_sha256",
    "plan_sha256",
)


class A6ModelBoundaryError(ValueError):
    """The exact A6 run identity already crossed or corrupted its model gate."""


def _canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _private_regular_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise A6ModelBoundaryError("A6 model-boundary marker is not a regular file")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != 0o600:
        raise A6ModelBoundaryError("A6 model-boundary marker is not mode 0600")


def _validate_marker_payload(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, dict):
        raise A6ModelBoundaryError("A6 model-boundary marker is not an object")
    expected_keys = {
        "arm_labels",
        "identity_record_sha256",
        "materialized_launch_identity_sha256",
        "plan_sha256",
        "run_id",
        "run_kind",
        "schema_version",
        "stage",
        "status",
    }
    if set(payload) != expected_keys:
        raise A6ModelBoundaryError(
            "A6 model-boundary marker schema is invalid"
        )
    if (
        payload.get("schema_version") != 1
        or payload.get("stage") != "A6"
        or payload.get("status") != "model_boundary_claimed"
    ):
        raise A6ModelBoundaryError(
            "A6 model-boundary marker state is invalid"
        )
    for field in _SHA256_FIELDS:
        value = payload.get(field)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise A6ModelBoundaryError(
                f"A6 model-boundary field {field} is invalid"
            )
    run_id = payload.get("run_id")
    run_kind = payload.get("run_kind")
    arm_labels = payload.get("arm_labels")
    if not isinstance(run_id, str) or not run_id:
        raise A6ModelBoundaryError("A6 model-boundary run ID is invalid")
    if run_kind not in {"seed", "candidate", "discovery"}:
        raise A6ModelBoundaryError("A6 model-boundary run kind is invalid")
    if (
        not isinstance(arm_labels, list)
        or not arm_labels
        or len(arm_labels) != len(set(arm_labels))
        or any(not isinstance(label, str) or not label for label in arm_labels)
    ):
        raise A6ModelBoundaryError("A6 model-boundary arm labels are invalid")
    return payload


def _read_marker(path: Path) -> Mapping[str, object]:
    _private_regular_file(path)
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise A6ModelBoundaryError(
            "A6 model-boundary marker is invalid JSON"
        ) from exc
    if raw != _canonical_bytes(payload):
        raise A6ModelBoundaryError(
            "A6 model-boundary marker bytes are not canonical"
        )
    return _validate_marker_payload(payload)


def assert_a6_model_boundary_unclaimed(run_dir: str | Path) -> None:
    """Reject every same-ID paid restart before runtime/provider construction."""

    root = Path(run_dir).expanduser().resolve()
    marker = root / _MARKER_NAME
    if marker.exists() or marker.is_symlink():
        _read_marker(marker)
        raise A6ModelBoundaryError(
            "A6 model boundary was already claimed; use a fresh run ID"
        )


def claim_a6_model_boundary(
    run_dir: str | Path,
    *,
    plan_path: str | Path,
    run_id: str,
    run_kind: str,
    arm_labels: Sequence[str],
    identity_record_sha256: str,
    materialized_launch_identity_sha256: str,
) -> dict[str, object]:
    """Atomically consume one A6 model boundary and durably bind its identity."""

    root = Path(run_dir).expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise A6ModelBoundaryError("A6 run root is unavailable")
    plan = Path(plan_path).expanduser()
    if plan.is_symlink() or not plan.is_file() or plan.resolve().parent != root:
        raise A6ModelBoundaryError("A6 model-boundary plan is unavailable")
    labels = list(arm_labels)
    payload: dict[str, object] = {
        "arm_labels": labels,
        "identity_record_sha256": identity_record_sha256,
        "materialized_launch_identity_sha256": (
            materialized_launch_identity_sha256
        ),
        "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
        "run_id": run_id,
        "run_kind": run_kind,
        "schema_version": 1,
        "stage": "A6",
        "status": "model_boundary_claimed",
    }
    # Validate before consuming the one-shot path. This rejects unsafe
    # run-kind, arm, and digest values with no partial marker.
    _validate_marker_payload(payload)
    encoded = _canonical_bytes(payload)
    marker = root / _MARKER_NAME
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(marker, flags, 0o600)
    except FileExistsError as exc:
        _read_marker(marker)
        raise A6ModelBoundaryError(
            "A6 model boundary was already claimed; use a fresh run ID"
        ) from exc
    try:
        os.fchmod(descriptor, 0o600)
        written = 0
        while written < len(encoded):
            count = os.write(descriptor, encoded[written:])
            if count <= 0:
                raise A6ModelBoundaryError(
                    "A6 model-boundary marker write was incomplete"
                )
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_descriptor = os.open(root, directory_flags)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)
    observed = _read_marker(marker)
    if observed != payload:
        raise A6ModelBoundaryError(
            "A6 model-boundary marker differs after durable write"
        )
    return {
        **payload,
        "marker_path": str(marker),
        "marker_sha256": hashlib.sha256(encoded).hexdigest(),
    }


__all__ = [
    "A6ModelBoundaryError",
    "assert_a6_model_boundary_unclaimed",
    "claim_a6_model_boundary",
]
