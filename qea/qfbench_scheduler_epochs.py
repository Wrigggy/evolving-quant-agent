"""Immutable scheduler epochs for repeated QFBench baseline checkpoints."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SCHEDULER_IDENTITY_FIELDS = frozenset(
    {
        "runtime_identity_digest",
        "scheduler_identity_digest",
        "worker_concurrency",
        "verifier_concurrency",
    }
)
_EPOCH_FIELDS = frozenset(
    {
        "first_repetition",
        "last_repetition",
        "worker_concurrency",
        "verifier_concurrency",
        "scheduler_identity_digest",
        "runtime_identity_digest",
    }
)


class SchedulerEpochError(ValueError):
    """A scheduler epoch or checkpoint migration is unsafe."""


def _positive_integer(name: str, value: object) -> int:
    if type(value) is not int or value < 1:
        raise SchedulerEpochError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class SchedulerEpoch:
    """One immutable scheduler contract covering contiguous repetitions."""

    first_repetition: int
    last_repetition: int
    worker_concurrency: int
    verifier_concurrency: int
    scheduler_identity_digest: str
    runtime_identity_digest: str

    def __post_init__(self) -> None:
        first = _positive_integer("first_repetition", self.first_repetition)
        last = _positive_integer("last_repetition", self.last_repetition)
        if last < first:
            raise SchedulerEpochError(
                "last_repetition must not precede first_repetition"
            )
        _positive_integer("worker_concurrency", self.worker_concurrency)
        _positive_integer("verifier_concurrency", self.verifier_concurrency)
        if not isinstance(self.scheduler_identity_digest, str) or not (
            _SHA256_RE.fullmatch(self.scheduler_identity_digest)
        ):
            raise SchedulerEpochError(
                "scheduler_identity_digest must be 64 lowercase hex characters"
            )
        if not isinstance(self.runtime_identity_digest, str) or not (
            _SHA256_RE.fullmatch(self.runtime_identity_digest)
        ):
            raise SchedulerEpochError(
                "runtime_identity_digest must be 64 lowercase hex characters"
            )

    def to_dict(self) -> dict[str, int | str]:
        """Return the exact JSON representation persisted in a checkpoint."""

        return {
            "first_repetition": self.first_repetition,
            "last_repetition": self.last_repetition,
            "worker_concurrency": self.worker_concurrency,
            "verifier_concurrency": self.verifier_concurrency,
            "scheduler_identity_digest": self.scheduler_identity_digest,
            "runtime_identity_digest": self.runtime_identity_digest,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "SchedulerEpoch":
        """Parse one exact persisted epoch without accepting extra fields."""

        if not isinstance(payload, dict) or set(payload) != _EPOCH_FIELDS:
            raise SchedulerEpochError("scheduler epoch has unknown or missing fields")
        return cls(**payload)


def validate_scheduler_epochs(
    epochs: Iterable[SchedulerEpoch], *, total_repetitions: int
) -> tuple[SchedulerEpoch, ...]:
    """Require ordered, gap-free coverage from repetition one through the total."""

    total = _positive_integer("total_repetitions", total_repetitions)
    normalized = tuple(epochs)
    if not normalized or not all(
        isinstance(epoch, SchedulerEpoch) for epoch in normalized
    ):
        raise SchedulerEpochError(
            "scheduler epochs must cover repetitions 1 through " f"{total} exactly"
        )
    expected = 1
    for epoch in normalized:
        if epoch.first_repetition != expected:
            raise SchedulerEpochError(
                "scheduler epochs must cover repetitions 1 through "
                f"{total} exactly"
            )
        expected = epoch.last_repetition + 1
    if expected != total + 1:
        raise SchedulerEpochError(
            "scheduler epochs must cover repetitions 1 through " f"{total} exactly"
        )
    return normalized


def epoch_for_repetition(
    epochs: Iterable[SchedulerEpoch], repetition: int
) -> SchedulerEpoch:
    """Return the only scheduler epoch that owns one repetition."""

    value = _positive_integer("repetition", repetition)
    matches = tuple(
        epoch
        for epoch in epochs
        if epoch.first_repetition <= value <= epoch.last_repetition
    )
    if len(matches) != 1:
        raise SchedulerEpochError("repetition has no unique scheduler epoch")
    return matches[0]


def sampling_identity(identity: Mapping[str, object]) -> dict[str, object]:
    """Remove only scheduler fields from a schema-v1 immutable identity."""

    if not isinstance(identity, Mapping):
        raise SchedulerEpochError("checkpoint identity must be a mapping")
    missing = _SCHEDULER_IDENTITY_FIELDS - set(identity)
    if missing:
        raise SchedulerEpochError(
            f"checkpoint identity is missing scheduler fields: {sorted(missing)}"
        )
    return {
        key: json.loads(json.dumps(value))
        for key, value in identity.items()
        if key not in _SCHEDULER_IDENTITY_FIELDS
    }


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _require_clean_v1_boundary(state: Mapping[str, object]) -> Mapping[str, object]:
    if state.get("phase") != "primary":
        raise SchedulerEpochError("migration requires phase primary")
    if state.get("next_repetition") != 2:
        raise SchedulerEpochError("migration requires next_repetition 2")
    if state.get("pending_primary") is not None:
        raise SchedulerEpochError("migration requires pending_primary null")
    completed = state.get("completed")
    if (
        not isinstance(completed, list)
        or len(completed) != 1
        or not isinstance(completed[0], dict)
        or completed[0].get("repetition") != 1
    ):
        raise SchedulerEpochError("migration requires completed repetition 1")
    identity = state.get("identity")
    if not isinstance(identity, dict):
        raise SchedulerEpochError("migration checkpoint identity is invalid")
    return identity


def migrate_v1_checkpoint(
    resume_path: str | Path,
    *,
    scheduler_epochs: Iterable[SchedulerEpoch],
    boundary_manifest_sha256: str,
) -> dict[str, object]:
    """Publish one schema-v2 checkpoint at a proven repetition-one boundary."""

    path = Path(resume_path)
    if not isinstance(boundary_manifest_sha256, str) or not _SHA256_RE.fullmatch(
        boundary_manifest_sha256
    ):
        raise SchedulerEpochError(
            "boundary_manifest_sha256 must be 64 lowercase hex characters"
        )
    try:
        state = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SchedulerEpochError(f"checkpoint is unreadable: {exc}") from exc
    if not isinstance(state, dict):
        raise SchedulerEpochError("checkpoint must be a JSON object")
    total = state.get("total_repetitions")
    if type(total) is not int:
        raise SchedulerEpochError("checkpoint total_repetitions is invalid")
    epochs = validate_scheduler_epochs(
        scheduler_epochs, total_repetitions=total
    )
    serialized_epochs = [epoch.to_dict() for epoch in epochs]

    if state.get("schema_version") == 2:
        if (
            state.get("scheduler_epochs") != serialized_epochs
            or state.get("boundary_manifest_sha256") != boundary_manifest_sha256
        ):
            raise SchedulerEpochError("published migration differs from request")
        return state
    if state.get("schema_version") != 1:
        raise SchedulerEpochError("checkpoint schema version cannot be migrated")

    identity = _require_clean_v1_boundary(state)
    epoch_one = epoch_for_repetition(epochs, 1)
    if any(
        identity.get(name) != getattr(epoch_one, name)
        for name in _SCHEDULER_IDENTITY_FIELDS
    ):
        raise SchedulerEpochError("checkpoint epoch 1 identity does not match")

    migrated = json.loads(json.dumps(state))
    migrated["schema_version"] = 2
    migrated.pop("identity")
    migrated["sampling_identity"] = sampling_identity(identity)
    migrated["scheduler_epochs"] = serialized_epochs
    migrated["boundary_manifest_sha256"] = boundary_manifest_sha256
    _atomic_json(path, migrated)
    return migrated


__all__ = [
    "SchedulerEpoch",
    "SchedulerEpochError",
    "epoch_for_repetition",
    "migrate_v1_checkpoint",
    "sampling_identity",
    "validate_scheduler_epochs",
]
