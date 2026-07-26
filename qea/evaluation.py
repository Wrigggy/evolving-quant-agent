"""Benchmark-neutral execution identities and official reward aggregation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable


ANSWER_FREE_DIAGNOSTIC_TAGS = frozenset({
    "artifact_limit",
    "invalid_schema",
    "missing_artifact",
    "runtime_error",
    "tests_failed",
    "timeout",
    "verifier_error",
    "worker_error",
})


class EvaluationContractError(ValueError):
    """An evaluation record would violate reproducibility or the firewall."""


def _require_digest(value: str, name: str, length: int) -> str:
    normalized = value.strip().lower()
    if len(normalized) != length or any(char not in "0123456789abcdef" for char in normalized):
        raise EvaluationContractError(f"{name} must be a {length}-character hex digest")
    return normalized


@dataclass(frozen=True)
class TaskAttempt:
    run_id: str
    benchmark_commit: str
    task_id: str
    split: str
    checkpoint: str
    worker_digest: str
    attempt_id: str

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        benchmark_commit: str,
        task_id: str,
        split: str,
        checkpoint: str,
        worker_digest: str,
    ) -> "TaskAttempt":
        fields = {
            "benchmark_commit": _require_digest(benchmark_commit, "benchmark_commit", 40),
            "checkpoint": checkpoint.strip(),
            "run_id": run_id.strip(),
            "split": split.strip(),
            "task_id": task_id.strip(),
            "worker_digest": _require_digest(worker_digest, "worker_digest", 64),
        }
        for key in ("checkpoint", "run_id", "split", "task_id"):
            if not fields[key]:
                raise EvaluationContractError(f"{key} must be non-empty")
        encoded = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
        return cls(attempt_id=hashlib.sha256(encoded).hexdigest(), **fields)


@dataclass(frozen=True)
class ArtifactRecord:
    path: str
    sha256: str
    size_bytes: int

    @classmethod
    def from_file(cls, path: str | Path, *, root: str | Path) -> "ArtifactRecord":
        artifact = Path(path).resolve()
        artifact_root = Path(root).resolve()
        try:
            relative = artifact.relative_to(artifact_root)
        except ValueError as exc:
            raise EvaluationContractError(f"artifact {artifact} is outside artifact root") from exc
        if not artifact.is_file():
            raise EvaluationContractError(f"artifact {artifact} is not a regular file")
        payload = artifact.read_bytes()
        return cls(
            path=relative.as_posix(),
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
        )


@dataclass(frozen=True)
class OfficialTaskScore:
    task_id: str
    domain: str
    reward: float
    diagnostic_tags: tuple[str, ...] = ()
    verifier_exit_code: int | None = None
    tests_passed: int | None = None
    tests_failed: int | None = None
    log_uri: str | None = None

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.domain.strip():
            raise EvaluationContractError("task_id and domain must be non-empty")
        if isinstance(self.reward, bool) or not 0.0 <= float(self.reward) <= 1.0:
            raise EvaluationContractError("official reward must be in [0, 1]")
        unsafe = set(self.diagnostic_tags) - ANSWER_FREE_DIAGNOSTIC_TAGS
        if unsafe:
            raise EvaluationContractError(
                f"diagnostic tags must be answer-free allowlisted values: {sorted(unsafe)}"
            )
        for name in ("tests_passed", "tests_failed"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise EvaluationContractError(f"{name} must be non-negative")


@dataclass(frozen=True)
class EvaluationSummary:
    scores: tuple[OfficialTaskScore, ...]
    task_rewards: dict[str, float]
    domain_scores: dict[str, float]
    task_mean: float
    overall: float


@dataclass(frozen=True)
class BenchmarkSplit:
    name: str
    task_ids: tuple[str, ...]
    lineages: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.task_ids:
            raise EvaluationContractError("split name and task_ids must be non-empty")
        if len(self.task_ids) != len(set(self.task_ids)):
            raise EvaluationContractError(f"duplicate task in {self.name} split")
        if len(self.lineages) != len(self.task_ids):
            raise EvaluationContractError("each task must have exactly one lineage")
        if any(not item.strip() for item in self.task_ids + self.lineages):
            raise EvaluationContractError("task IDs and lineages must be non-empty")


def validate_split_isolation(optimize: BenchmarkSplit, held_out: BenchmarkSplit) -> None:
    task_overlap = set(optimize.task_ids) & set(held_out.task_ids)
    if task_overlap:
        raise EvaluationContractError(f"task overlap between splits: {sorted(task_overlap)}")
    lineage_overlap = set(optimize.lineages) & set(held_out.lineages)
    if lineage_overlap:
        raise EvaluationContractError(f"lineage overlap between splits: {sorted(lineage_overlap)}")


def aggregate_domain_macro(
    scores: Iterable[OfficialTaskScore],
    *,
    expected_domains: set[str] | frozenset[str] | None = None,
) -> EvaluationSummary:
    ordered = tuple(scores)
    if not ordered:
        raise EvaluationContractError("cannot aggregate an empty score set")
    task_ids = [score.task_id for score in ordered]
    if len(task_ids) != len(set(task_ids)):
        raise EvaluationContractError("duplicate task score")

    by_domain: dict[str, list[float]] = {}
    for score in ordered:
        by_domain.setdefault(score.domain, []).append(float(score.reward))
    if expected_domains is not None:
        missing = set(expected_domains) - set(by_domain)
        if missing:
            raise EvaluationContractError(f"missing expected domains: {sorted(missing)}")

    domain_scores = {
        domain: sum(rewards) / len(rewards)
        for domain, rewards in sorted(by_domain.items())
    }
    task_rewards = {score.task_id: float(score.reward) for score in sorted(
        ordered, key=lambda item: item.task_id
    )}
    task_mean = sum(task_rewards.values()) / len(task_rewards)
    overall = sum(domain_scores.values()) / len(domain_scores)
    return EvaluationSummary(
        scores=ordered,
        task_rewards=task_rewards,
        domain_scores=domain_scores,
        task_mean=task_mean,
        overall=overall,
    )


@runtime_checkable
class TaskExecutor(Protocol):
    def execute(self, *args, **kwargs):
        """Run a worker on public task inputs and return produced artifacts."""


@runtime_checkable
class TaskVerifier(Protocol):
    def verify(self, *args, **kwargs) -> OfficialTaskScore:
        """Run the trusted official verifier outside the worker environment."""
