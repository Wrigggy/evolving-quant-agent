"""Deterministic train-only panel selection for the A4 Evolver canary."""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence


class A4SelectionError(ValueError):
    """The baseline or train split cannot support the frozen A4 policy."""


@dataclass(frozen=True)
class A4TaskStats:
    """Answer-free repeated-baseline facts used to select one A4 task."""

    task_id: str
    domain: str
    role: str
    rewards: tuple[float, ...]
    tests_passed: tuple[int, ...]
    tests_failed: tuple[int, ...]
    verifier_exit_codes: tuple[int, ...]
    min_pass_fraction: float
    mean_pass_fraction: float
    min_test_count: int


@dataclass(frozen=True)
class A4Panel:
    """The selected weak targets and stable protection tasks."""

    targets: tuple[A4TaskStats, ...]
    protections: tuple[A4TaskStats, ...]

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(item.task_id for item in self.targets + self.protections)

    def as_dict(self) -> dict[str, object]:
        def serializable(item: A4TaskStats) -> dict[str, object]:
            payload = asdict(item)
            for field in (
                "rewards",
                "tests_passed",
                "tests_failed",
                "verifier_exit_codes",
            ):
                payload[field] = list(payload[field])
            return payload

        return {
            "targets": [serializable(item) for item in self.targets],
            "protections": [serializable(item) for item in self.protections],
            "task_ids": list(self.task_ids),
        }


def _object(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise A4SelectionError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise A4SelectionError(f"{label} must be an array")
    return value


def _train_tasks(evolution_manifest: Mapping[str, object]) -> dict[str, str]:
    evolution = _object(evolution_manifest.get("evolution"), label="evolution")
    train = _sequence(evolution.get("train"), label="evolution.train")
    result: dict[str, str] = {}
    for index, value in enumerate(train):
        task = _object(value, label=f"evolution.train[{index}]")
        task_id = task.get("task_id")
        domain = task.get("domain")
        if not isinstance(task_id, str) or not task_id:
            raise A4SelectionError("train task has no task_id")
        if not isinstance(domain, str) or not domain:
            raise A4SelectionError(f"train task {task_id!r} has no domain")
        if task_id in result:
            raise A4SelectionError(f"duplicate train task: {task_id}")
        result[task_id] = domain
    if not result:
        raise A4SelectionError("train split is empty")
    return result


def _score_rows(
    baseline_result: Mapping[str, object],
    train_tasks: Mapping[str, str],
) -> dict[str, list[Mapping[str, object]]]:
    if baseline_result.get("complete") is not True:
        raise A4SelectionError("baseline result is not complete")
    repetitions = _sequence(
        baseline_result.get("repetitions"), label="baseline repetitions"
    )
    if len(repetitions) != 5:
        raise A4SelectionError("A4 requires the completed five-repetition baseline")
    rows: dict[str, list[Mapping[str, object]]] = {
        task_id: [] for task_id in train_tasks
    }
    for repetition_index, value in enumerate(repetitions, start=1):
        repetition = _object(value, label=f"repetition {repetition_index}")
        primary = _object(
            repetition.get("primary"), label=f"repetition {repetition_index} primary"
        )
        scores = _sequence(
            primary.get("scores"), label=f"repetition {repetition_index} scores"
        )
        seen: set[str] = set()
        for score_index, score_value in enumerate(scores):
            score = _object(
                score_value,
                label=f"repetition {repetition_index} score {score_index}",
            )
            task_id = score.get("task_id")
            if task_id not in train_tasks:
                continue
            if task_id in seen:
                raise A4SelectionError(
                    f"duplicate primary score for {task_id} in repetition "
                    f"{repetition_index}"
                )
            seen.add(str(task_id))
            rows[str(task_id)].append(score)
        missing = sorted(set(train_tasks) - seen)
        if missing:
            raise A4SelectionError(
                f"repetition {repetition_index} is missing train scores: {missing}"
            )
    return rows


def _valid_counts(rows: Sequence[Mapping[str, object]]) -> bool:
    for row in rows:
        passed = row.get("tests_passed")
        failed = row.get("tests_failed")
        exit_code = row.get("verifier_exit_code")
        if (
            isinstance(passed, bool)
            or not isinstance(passed, int)
            or isinstance(failed, bool)
            or not isinstance(failed, int)
            or passed < 0
            or failed < 0
            or passed + failed <= 0
            or exit_code != 0
        ):
            return False
    return True


def _stats(
    task_id: str,
    domain: str,
    rows: Sequence[Mapping[str, object]],
    *,
    role: str,
) -> A4TaskStats:
    passed = tuple(int(row["tests_passed"]) for row in rows)
    failed = tuple(int(row["tests_failed"]) for row in rows)
    pass_fractions = tuple(
        good / (good + bad) for good, bad in zip(passed, failed)
    )
    return A4TaskStats(
        task_id=task_id,
        domain=domain,
        role=role,
        rewards=tuple(float(row["reward"]) for row in rows),
        tests_passed=passed,
        tests_failed=failed,
        verifier_exit_codes=tuple(int(row["verifier_exit_code"]) for row in rows),
        min_pass_fraction=min(pass_fractions),
        mean_pass_fraction=statistics.fmean(pass_fractions),
        min_test_count=min(good + bad for good, bad in zip(passed, failed)),
    )


def derive_a4_panel(
    *,
    baseline_result: Mapping[str, object],
    evolution_manifest: Mapping[str, object],
    target_count: int = 3,
    protection_count: int = 2,
) -> A4Panel:
    """Select repeatable weak tasks without exposing validation or test tasks.

    Targets must have reward zero in all five repetitions, a normal verifier
    exit, and non-empty answer-free official test counts. They are ranked by
    worst-repetition pass fraction, then mean pass fraction. This avoids using a
    single lucky near-pass as the discovery target.

    Protections must pass all five repetitions. The selector greedily maximizes
    coverage of domains not represented among targets, then prefers tasks with
    more official tests. No validation, authoritative-test, or diagnostic task
    is eligible because membership is derived solely from ``evolution.train``.
    """

    if target_count <= 0 or protection_count <= 0:
        raise A4SelectionError("A4 target and protection counts must be positive")
    train_tasks = _train_tasks(evolution_manifest)
    rows = _score_rows(baseline_result, train_tasks)

    targets: list[A4TaskStats] = []
    stable: list[A4TaskStats] = []
    for task_id, domain in train_tasks.items():
        task_rows = rows[task_id]
        if not _valid_counts(task_rows):
            continue
        rewards = tuple(float(row["reward"]) for row in task_rows)
        if all(reward == 0.0 for reward in rewards):
            targets.append(_stats(task_id, domain, task_rows, role="target"))
        if all(reward == 1.0 for reward in rewards):
            stable.append(_stats(task_id, domain, task_rows, role="protection"))

    targets.sort(
        key=lambda item: (
            -item.min_pass_fraction,
            -item.mean_pass_fraction,
            item.task_id,
        )
    )
    selected_targets = tuple(targets[:target_count])
    if len(selected_targets) != target_count:
        raise A4SelectionError("baseline has too few eligible weak train tasks")

    target_domains = {item.domain for item in selected_targets}
    stable.sort(key=lambda item: (-item.min_test_count, item.task_id))
    selected_protections: list[A4TaskStats] = []
    selected_domains: set[str] = set()
    for item in stable:
        if item.domain in target_domains or item.domain in selected_domains:
            continue
        selected_protections.append(item)
        selected_domains.add(item.domain)
        if len(selected_protections) == protection_count:
            break
    if len(selected_protections) < protection_count:
        for item in stable:
            if item in selected_protections:
                continue
            selected_protections.append(item)
            if len(selected_protections) == protection_count:
                break
    if len(selected_protections) != protection_count:
        raise A4SelectionError("baseline has too few stable train protection tasks")
    return A4Panel(
        targets=selected_targets,
        protections=tuple(selected_protections),
    )


def validate_frozen_panel(
    *,
    frozen: Mapping[str, object],
    derived: A4Panel,
) -> None:
    """Fail closed if a persisted A4 panel no longer matches its source facts."""

    expected = derived.as_dict()
    observed = {
        "targets": frozen.get("targets"),
        "protections": frozen.get("protections"),
        "task_ids": frozen.get("task_ids"),
    }
    if observed != expected:
        raise A4SelectionError("frozen A4 panel differs from deterministic derivation")


__all__ = [
    "A4Panel",
    "A4SelectionError",
    "A4TaskStats",
    "derive_a4_panel",
    "validate_frozen_panel",
]
