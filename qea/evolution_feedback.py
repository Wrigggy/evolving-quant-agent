"""Proposer-facing QFBench feedback with a fail-closed verifier firewall."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Iterable, Mapping


_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_STATUSES = frozenset({"passed", "failed", "skipped", "pending"})
_EVIDENCE_KINDS = frozenset({
    "missing_output",
    "numeric_or_method_mismatch",
    "requirement_not_satisfied",
    "runtime_failure",
    "schema_or_structure_mismatch",
})
_PUBLIC_MESSAGES = {
    "missing_output": "A required public deliverable was not found.",
    "numeric_or_method_mismatch": (
        "A requested calculation or method did not satisfy the public requirement."
    ),
    "requirement_not_satisfied": "The public requirement was not fully satisfied.",
    "runtime_failure": "The task did not complete successfully.",
    "schema_or_structure_mismatch": (
        "The requested output structure was not fully satisfied."
    ),
}


class FeedbackContractError(ValueError):
    """A feedback payload is incomplete, ambiguous, or crosses the firewall."""


class FeedbackMode(str, Enum):
    CONTROL = "control"
    RICH = "rich"


@dataclass(frozen=True)
class PublicCriterion:
    criterion_id: str
    requirement: str
    evidence_kind: str = "requirement_not_satisfied"

    def __post_init__(self) -> None:
        if not _ID_RE.fullmatch(self.criterion_id):
            raise FeedbackContractError(
                f"invalid public criterion ID {self.criterion_id!r}"
            )
        if not self.requirement.strip():
            raise FeedbackContractError("public criterion requirement must be non-empty")
        if self.evidence_kind not in _EVIDENCE_KINDS:
            raise FeedbackContractError(
                f"unsupported public evidence kind {self.evidence_kind!r}"
            )


@dataclass(frozen=True)
class PublicTaskRubric:
    task_id: str
    criteria: tuple[PublicCriterion, ...]

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.criteria:
            raise FeedbackContractError("task rubric needs an ID and criteria")
        ids = [item.criterion_id for item in self.criteria]
        if len(ids) != len(set(ids)):
            raise FeedbackContractError(
                f"duplicate public criterion in task {self.task_id!r}"
            )


@dataclass(frozen=True)
class PublicCriterionResult:
    criterion_id: str
    status: str
    passed_checks: int
    failed_checks: int
    evidence_kind: str
    public_message: str
    provenance: str = "sanitized_verifier"


@dataclass(frozen=True)
class VerifierCriterionRule:
    pattern: str
    criterion_id: str


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise FeedbackContractError(f"cannot load feedback JSON {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise FeedbackContractError(f"unsupported feedback schema in {path}")
    return payload


def load_feedback_manifest(
    path: str | Path,
    *,
    expected_task_ids: Iterable[str] | None = None,
    forbidden_task_ids: Iterable[str] = (),
) -> dict[str, PublicTaskRubric]:
    """Load instruction-derived public criteria and prove task-set isolation."""

    source = Path(path).resolve()
    payload = _read_json(source)
    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, dict) or not raw_tasks:
        raise FeedbackContractError("feedback manifest tasks must be a non-empty object")
    rubrics: dict[str, PublicTaskRubric] = {}
    for task_id, raw_task in sorted(raw_tasks.items()):
        if not isinstance(task_id, str) or not isinstance(raw_task, dict):
            raise FeedbackContractError("invalid feedback task entry")
        raw_criteria = raw_task.get("criteria")
        if not isinstance(raw_criteria, list) or not raw_criteria:
            raise FeedbackContractError(f"task {task_id!r} needs public criteria")
        criteria: list[PublicCriterion] = []
        for raw in raw_criteria:
            if not isinstance(raw, dict):
                raise FeedbackContractError(
                    f"task {task_id!r} has a non-object criterion"
                )
            allowed = {"criterion_id", "requirement", "evidence_kind"}
            extra = set(raw) - allowed
            if extra:
                raise FeedbackContractError(
                    f"task {task_id!r} criterion has private/unknown fields: {sorted(extra)}"
                )
            criteria.append(PublicCriterion(**raw))
        rubrics[task_id] = PublicTaskRubric(task_id, tuple(criteria))

    actual = set(rubrics)
    if expected_task_ids is not None and actual != set(expected_task_ids):
        raise FeedbackContractError(
            "feedback task set mismatch: "
            f"missing={sorted(set(expected_task_ids) - actual)} "
            f"extra={sorted(actual - set(expected_task_ids))}"
        )
    forbidden = actual & set(forbidden_task_ids)
    if forbidden:
        raise FeedbackContractError(
            f"feedback manifest contains held-out/forbidden tasks: {sorted(forbidden)}"
        )
    return rubrics


def load_verifier_mapping(
    path: str | Path,
    *,
    public_criteria: Mapping[str, frozenset[str] | set[str]],
) -> dict[str, tuple[VerifierCriterionRule, ...]]:
    """Load trusted test-name mappings without returning verifier diagnostics."""

    payload = _read_json(Path(path).resolve())
    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, dict):
        raise FeedbackContractError("verifier mapping tasks must be an object")
    result: dict[str, tuple[VerifierCriterionRule, ...]] = {}
    for task_id, mapping in sorted(raw_tasks.items()):
        known = set(public_criteria.get(task_id, ()))
        if not known:
            raise FeedbackContractError(
                f"verifier mapping task {task_id!r} has no public rubric"
            )
        if isinstance(mapping, dict):
            raw_rules = [
                {"pattern": private_name, "criterion_id": criterion_id}
                for private_name, criterion_id in mapping.items()
            ]
        elif isinstance(mapping, list):
            raw_rules = mapping
        else:
            raise FeedbackContractError(f"invalid verifier mapping for {task_id!r}")
        normalized: list[VerifierCriterionRule] = []
        for raw_rule in raw_rules:
            if not isinstance(raw_rule, dict) or set(raw_rule) != {
                "pattern", "criterion_id"
            }:
                raise FeedbackContractError(
                    f"invalid verifier mapping rule for {task_id!r}"
                )
            pattern = raw_rule["pattern"]
            criterion_id = raw_rule["criterion_id"]
            if not isinstance(pattern, str) or not pattern.strip():
                raise FeedbackContractError("private test mapping pattern must be non-empty")
            if criterion_id not in known:
                raise FeedbackContractError(
                    f"unknown public criterion {criterion_id!r} for task {task_id!r}"
                )
            normalized.append(VerifierCriterionRule(pattern, criterion_id))
        result[task_id] = tuple(normalized)
    return result


def _ctrf_tests(path: Path) -> tuple[dict, ...]:
    try:
        payload = json.loads(path.read_text())
        tests = payload["results"]["tests"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise FeedbackContractError(f"cannot parse trusted CTRF tests: {exc}") from exc
    if not isinstance(tests, list) or any(not isinstance(item, dict) for item in tests):
        raise FeedbackContractError("trusted CTRF tests must be a list of objects")
    return tuple(tests)


def sanitize_ctrf_feedback(
    ctrf_path: str | Path,
    verifier_mapping: Mapping[str, str] | Iterable[VerifierCriterionRule],
    public_criteria: Mapping[str, PublicCriterion],
) -> tuple[PublicCriterionResult, ...]:
    """Aggregate private check statuses into public criteria without raw text."""

    if isinstance(verifier_mapping, Mapping):
        rules = tuple(
            VerifierCriterionRule(name, criterion_id)
            for name, criterion_id in verifier_mapping.items()
        )
    else:
        rules = tuple(verifier_mapping)
    counts: dict[str, list[int]] = {}
    for test in _ctrf_tests(Path(ctrf_path).resolve()):
        private_name = test.get("name")
        if not isinstance(private_name, str):
            continue
        rule = next(
            (candidate for candidate in rules if fnmatchcase(private_name, candidate.pattern)),
            None,
        )
        if rule is None:
            continue
        criterion_id = rule.criterion_id
        if criterion_id not in public_criteria:
            raise FeedbackContractError(
                f"unknown public criterion {criterion_id!r} in verifier mapping"
            )
        status = str(test.get("status", "")).strip().lower()
        if status not in _STATUSES:
            raise FeedbackContractError(f"unsupported trusted CTRF status {status!r}")
        passed, failed = counts.setdefault(criterion_id, [0, 0])
        if status == "passed":
            passed += 1
        elif status == "failed":
            failed += 1
        counts[criterion_id] = [passed, failed]

    output: list[PublicCriterionResult] = []
    for criterion_id in sorted(counts):
        passed, failed = counts[criterion_id]
        criterion = public_criteria[criterion_id]
        status = "failed" if failed else "passed"
        output.append(PublicCriterionResult(
            criterion_id=criterion_id,
            status=status,
            passed_checks=passed,
            failed_checks=failed,
            evidence_kind=criterion.evidence_kind,
            public_message=_PUBLIC_MESSAGES[criterion.evidence_kind],
        ))
    return tuple(output)


def feedback_contract_digest(mode: FeedbackMode, rubric_path: str | Path) -> str:
    rubric = Path(rubric_path).resolve()
    payload = {
        "schema_version": 1,
        "mode": FeedbackMode(mode).value,
        "rubric_sha256": hashlib.sha256(rubric.read_bytes()).hexdigest(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
