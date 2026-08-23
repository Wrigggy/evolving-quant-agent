import json
from pathlib import Path

import pytest

from qea.quantcodeeval_lineage_adapter import (
    QuantCodeEvalLineageAdapterError,
    normalize_quantcodeeval_lineage_observation,
    quantcodeeval_lineage_metric,
    quantcodeeval_lineage_score,
)


REAL_RESULT = (
    Path(__file__).resolve().parents[1]
    / "results/bc-mirror/qce-v2-full-candidate-20260812-r2b"
    / "FULL-CANDIDATE-RESULT.json"
)


def test_normalizes_real_completed_property_score_for_target():
    observation = normalize_quantcodeeval_lineage_observation(
        REAL_RESULT,
        task_id="T16",
        stage="target",
    )

    assert observation == {
        "schema_version": 1,
        "benchmark": "quantcodeeval",
        "stage": "target",
        "status": "official_complete",
        "task_id": "T16",
        "reward": 0.0,
        "tests_passed": 12,
        "tests_failed": 6,
        "verifier_exit_code": 0,
        "diagnostic_tags": ["tests_failed"],
        "run_id": "qce-v2-full-candidate-20260812-r2b",
        "cost": {
            "provider_cost_usd": "0.0131630576",
            "completed_request_count": 24,
            "total_tokens": 362946,
            "cost_complete": False,
            "provider_cost_is_lower_bound": True,
        },
        "selection_metric": {
            "official_valid": True,
            "reward": 0.0,
            "selection_passed": 12,
            "selection_failed": 6,
            "official_property_total": 18,
            "verifier_executed": True,
            "verifier_exit_code": 0,
            "source": "official_verifier",
        },
        "lineage_ready": True,
    }
    assert quantcodeeval_lineage_score(observation) == {
        "task_id": "T16",
        "reward": 0.0,
        "tests_passed": 12,
        "tests_failed": 6,
        "verifier_exit_code": 0,
        "selection_source": "official_verifier",
        "official_valid": True,
        "verifier_executed": True,
    }


def test_real_missing_strategy_is_official_zero_not_infrastructure_failure():
    observation = normalize_quantcodeeval_lineage_observation(
        REAL_RESULT,
        task_id="T24",
        stage="protection",
    )

    assert observation["status"] == "official_zero_missing_strategy"
    assert observation["reward"] == 0.0
    assert observation["tests_passed"] is None
    assert observation["tests_failed"] is None
    assert observation["verifier_exit_code"] is None
    assert observation["diagnostic_tags"] == ["missing_artifact"]
    assert observation["selection_metric"] is None
    assert observation["lineage_ready"] is False
    with pytest.raises(QuantCodeEvalLineageAdapterError, match="property_total"):
        quantcodeeval_lineage_score(observation)

    score = quantcodeeval_lineage_score(
        observation,
        official_property_total=18,
    )
    assert score == {
        "task_id": "T24",
        "reward": 0.0,
        "tests_passed": 0,
        "tests_failed": 18,
        "verifier_exit_code": None,
        "selection_source": "official_worker_artifact_contract_zero",
        "official_valid": True,
        "verifier_executed": False,
    }

    wrapped = normalize_quantcodeeval_lineage_observation(
        REAL_RESULT,
        task_id="T24",
        stage="protection",
        official_property_total=18,
    )
    assert wrapped["tests_passed"] is None
    assert wrapped["tests_failed"] is None
    assert wrapped["verifier_exit_code"] is None
    assert wrapped["selection_metric"]["selection_passed"] == 0
    assert wrapped["selection_metric"]["selection_failed"] == 18
    assert wrapped["lineage_ready"] is True


def test_incomplete_evaluation_is_not_converted_to_official_zero():
    payload = {
        "status": "evaluation_failed",
        "official_evaluated": False,
        "benchmark_score_claimed": False,
        "run_id": "qce-infra-failure",
        "partial_cost_and_lifecycle_audit": {
            "provider_cost_usd": 0.012,
            "request_count": 10,
            "total_tokens": 250000,
            "cost_complete": True,
        },
    }

    observation = normalize_quantcodeeval_lineage_observation(
        payload,
        task_id="T26",
        stage="repeat",
    )

    assert observation["status"] == "infra_incomplete"
    assert observation["reward"] is None
    assert observation["tests_passed"] is None
    assert observation["verifier_exit_code"] is None
    assert observation["cost"]["completed_request_count"] is None
    assert observation["selection_metric"] is None
    assert observation["lineage_ready"] is False
    with pytest.raises(QuantCodeEvalLineageAdapterError, match="infrastructure"):
        quantcodeeval_lineage_metric(
            observation,
            official_property_total=17,
        )


def test_explicit_wrapper_supplies_missing_run_and_cost_without_inference():
    payload = {
        "status": "complete",
        "cost_audit": {
            "provider_cost_usd": "0.01",
            "completed_request_count": None,
            "total_tokens": None,
            "cost_complete": False,
        },
        "score_summary": {
            "scores": [
                {
                    "task_id": "T27",
                    "domain": "portfolio",
                    "reward": 1.0,
                    "diagnostic_tags": [],
                    "verifier_exit_code": 0,
                    "tests_passed": 14,
                    "tests_failed": 0,
                    "log_uri": "verifier-command.trusted.json",
                }
            ]
        },
    }

    without_wrapper = normalize_quantcodeeval_lineage_observation(
        payload,
        task_id="T27",
        stage="target",
    )
    assert without_wrapper["run_id"] is None
    assert without_wrapper["cost"]["provider_cost_usd"] == "0.01"
    assert without_wrapper["cost"]["completed_request_count"] is None
    assert without_wrapper["lineage_ready"] is False

    wrapped = normalize_quantcodeeval_lineage_observation(
        payload,
        task_id="T27",
        stage="target",
        run_id="qce-t27-target-r1",
        cost={
            "provider_cost_usd": "0.05",
            "completed_request_count": 12,
            "total_tokens": 345000,
            "cost_complete": True,
        },
    )
    assert wrapped["run_id"] == "qce-t27-target-r1"
    assert wrapped["cost"]["provider_cost_usd"] == "0.05"
    assert wrapped["lineage_ready"] is True


@pytest.mark.parametrize("stage", ["target", "repeat", "protection"])
def test_preserves_supported_lineage_stage(stage):
    payload = {
        "status": "complete",
        "run_id": f"qce-{stage}",
        "cost_audit": {
            "provider_cost_usd": "0",
            "completed_request_count": 0,
            "total_tokens": 0,
            "cost_complete": True,
        },
        "score_summary": {
            "scores": [
                {
                    "task_id": "T19",
                    "domain": "backtest",
                    "reward": 0.0,
                    "diagnostic_tags": ["tests_failed"],
                    "verifier_exit_code": 0,
                    "tests_passed": 17,
                    "tests_failed": 1,
                }
            ]
        },
    }

    observation = normalize_quantcodeeval_lineage_observation(
        payload,
        task_id="T19",
        stage=stage,
    )

    assert observation["stage"] == stage
    assert observation["lineage_ready"] is True


def test_rejects_unsupported_stage_and_mismatched_run_wrapper():
    result = json.loads(REAL_RESULT.read_text())
    with pytest.raises(QuantCodeEvalLineageAdapterError, match="unsupported"):
        normalize_quantcodeeval_lineage_observation(
            result,
            task_id="T16",
            stage="sealed",
        )
    with pytest.raises(QuantCodeEvalLineageAdapterError, match="disagrees"):
        normalize_quantcodeeval_lineage_observation(
            result,
            task_id="T16",
            stage="target",
            run_id="different-run",
        )


def test_rejects_task_outside_credential_free_track():
    with pytest.raises(QuantCodeEvalLineageAdapterError, match="credential-free"):
        normalize_quantcodeeval_lineage_observation(
            {"status": "complete"},
            task_id="T30",
            stage="target",
        )
