"""Fail-closed QuantCodeEval checker-result parser."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..evaluation import EvaluationContractError, OfficialTaskScore


_PROPERTY_ID_RE = re.compile(r"^[AB][1-9][0-9]*$")
_VERDICTS = frozenset({"PASS", "FAIL", "SKIP", "ERROR"})


def _property_family(property_id: str) -> str:
    # The official release retains the historical A11 identifier but counts it
    # as paper-specific Type B in its published A/B coverage statistics.
    return "B" if property_id == "A11" else property_id[0]


def parse_quantcodeeval_result(path: str | Path) -> dict[str, object]:
    """Validate the trusted property summary without returning diagnostics."""

    try:
        payload = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationContractError(
            f"cannot parse QuantCodeEval checker output: {exc}"
        ) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise EvaluationContractError("QuantCodeEval output needs a results list")
    results = payload["results"]
    if not results:
        raise EvaluationContractError("QuantCodeEval checker output is empty")
    seen: set[str] = set()
    counts = {verdict: 0 for verdict in _VERDICTS}
    type_counts = {
        "A": {verdict: 0 for verdict in _VERDICTS},
        "B": {verdict: 0 for verdict in _VERDICTS},
    }
    for row in results:
        if not isinstance(row, dict):
            raise EvaluationContractError("QuantCodeEval result entries must be objects")
        property_id = row.get("property_id")
        verdict = row.get("verdict")
        if not isinstance(property_id, str) or not _PROPERTY_ID_RE.fullmatch(property_id):
            raise EvaluationContractError("QuantCodeEval property ID is invalid")
        if property_id in seen:
            raise EvaluationContractError(
                f"duplicate QuantCodeEval property ID {property_id}"
            )
        if verdict not in _VERDICTS:
            raise EvaluationContractError(
                f"invalid QuantCodeEval verdict for {property_id}"
            )
        seen.add(property_id)
        counts[verdict] += 1
        type_counts[_property_family(property_id)][verdict] += 1
    total = payload.get("total")
    if isinstance(total, bool) or not isinstance(total, int) or total != len(results):
        raise EvaluationContractError("QuantCodeEval total is inconsistent")
    expected_fields = {
        "pass": counts["PASS"],
        "fail": counts["FAIL"] + counts["ERROR"],
        "skip": counts["SKIP"],
    }
    for key, expected in expected_fields.items():
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value != expected:
            raise EvaluationContractError(
                f"QuantCodeEval {key} count is inconsistent"
            )
    return {
        "total": total,
        "passed": counts["PASS"],
        "failed": counts["FAIL"],
        "skipped": counts["SKIP"],
        "errors": counts["ERROR"],
        "type_a": dict(type_counts["A"]),
        "type_b": dict(type_counts["B"]),
        "all_passed": counts["PASS"] == total,
    }


def quantcodeeval_answer_free_summary(path: str | Path) -> dict[str, object]:
    """Return property-family progress without checker IDs or diagnostics.

    Type A and Type B are part of QuantCodeEval's public evaluation taxonomy.
    Individual property IDs and checker-provided details stay in the trusted
    verifier surface so this object is safe to use as evolver evidence.
    """

    parsed = parse_quantcodeeval_result(path)
    families: dict[str, dict[str, int]] = {}
    for label, key in (("type_a", "type_a"), ("type_b", "type_b")):
        counts = parsed[key]
        assert isinstance(counts, dict)
        passed = int(counts["PASS"])
        failed = int(counts["FAIL"])
        skipped = int(counts["SKIP"])
        errors = int(counts["ERROR"])
        families[label] = {
            "total": passed + failed + skipped + errors,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
        }
    tags: list[str] = []
    if not parsed["all_passed"]:
        tags.append("properties_incomplete")
    if parsed["errors"] or parsed["skipped"]:
        tags.append("verifier_incomplete")
    return {
        "schema_version": 1,
        "benchmark": "quantcodeeval",
        "official_reward": 1.0 if parsed["all_passed"] else 0.0,
        "property_families": families,
        "diagnostic_tags": tags,
    }


def parse_official_quantcodeeval_score(
    *,
    task_id: str,
    domain: str,
    reward_path: str | Path,
    ctrf_path: str | Path | None,
    verifier_exit_code: int,
    log_uri: str | None = None,
    pytest_output: str | None = None,
) -> OfficialTaskScore:
    """Return binary all-properties reward and coarse answer-free tags only."""

    del pytest_output
    if ctrf_path is None:
        raise EvaluationContractError("QuantCodeEval checker output is required")
    summary = parse_quantcodeeval_result(ctrf_path)
    try:
        reward = float(Path(reward_path).read_text().strip())
    except (OSError, ValueError) as exc:
        raise EvaluationContractError(
            f"cannot parse QuantCodeEval reward: {exc}"
        ) from exc
    expected_reward = 1.0 if summary["all_passed"] else 0.0
    if reward != expected_reward:
        raise EvaluationContractError(
            "QuantCodeEval reward disagrees with all-property completion"
        )
    tags: list[str] = []
    if not summary["all_passed"]:
        tags.append("tests_failed")
    if summary["errors"] or summary["skipped"] or verifier_exit_code != 0:
        tags.append("verifier_error")
    return OfficialTaskScore(
        task_id=task_id,
        domain=domain,
        reward=reward,
        diagnostic_tags=tuple(tags),
        verifier_exit_code=verifier_exit_code,
        tests_passed=int(summary["passed"]),
        tests_failed=int(summary["failed"] + summary["skipped"] + summary["errors"]),
        log_uri=log_uri,
    )
