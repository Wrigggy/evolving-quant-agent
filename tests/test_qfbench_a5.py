import json
from pathlib import Path

import pytest

from qea.qfbench_a4 import derive_a4_panel, validate_frozen_panel
from qea.worker_identity import hash_worker_directory


def test_repository_a5_manifest_expands_only_clean_train_failures_and_successes():
    repository = Path(__file__).resolve().parents[1]
    baseline_root = repository / (
        "results/bc-mirror/"
        "qfbench-rootless-base-85x5-official-deepseek-v4-flash-0731-"
        "all12x3-20260804"
    )
    if not baseline_root.is_dir():
        pytest.skip("the mirrored five-repeat baseline is not present")
    baseline = json.loads((baseline_root / "result.json").read_text())
    evolution = json.loads(
        (repository / "data/qfbench/MANIFEST_30_15_40_EVOLUTION.json").read_text()
    )
    manifest = json.loads(
        (
            repository
            / "data/qfbench/MANIFEST_A5_FAILURE_TYPE_DISCOVERY.json"
        ).read_text()
    )

    derived = derive_a4_panel(
        baseline_result=baseline,
        evolution_manifest=evolution,
        target_count=6,
        protection_count=5,
    )

    validate_frozen_panel(frozen=manifest["panel"], derived=derived)
    assert len(derived.targets) == 6
    assert len(derived.protections) == 5
    assert "residual-momentum" not in derived.task_ids
    assert "yield-curve-bond-immunization" not in derived.task_ids
    assert "prediction-markets-cross-venue-dislocation" not in derived.task_ids
    assert set(derived.task_ids).isdisjoint(
        item["task_id"] for item in evolution["evolution"]["validation"]
    )
    assert set(derived.task_ids).isdisjoint(
        item["task_id"] for item in evolution["evolution"]["test"]
    )


def test_a5_worker_setup_matches_the_measured_seed_not_unrelated_worker_defaults():
    repository = Path(__file__).resolve().parents[1]
    baseline_root = repository / (
        "results/bc-mirror/"
        "qfbench-rootless-base-85x5-official-deepseek-v4-flash-0731-"
        "all12x3-20260804"
    )
    if not baseline_root.is_dir():
        pytest.skip("the mirrored five-repeat baseline is not present")
    manifest = json.loads(
        (
            repository
            / "data/qfbench/MANIFEST_A5_FAILURE_TYPE_DISCOVERY.json"
        ).read_text()
    )
    seed = baseline_root / "workers/seed"
    config = (seed / "agent.yaml").read_text()

    assert hash_worker_directory(seed) == manifest["baseline"]["seed_worker_digest"]
    assert "max_iterations: 60" in config
    assert "max_context_tokens: 200000" in config
    assert "max_tokens: 32000" in config
    assert "temperature: 0.2" in config
    assert manifest["experiment"]["worker_setup"] == {
        "max_context_tokens": 200000,
        "max_iterations": 60,
        "max_tokens_per_call": 32000,
        "temperature": 0.2,
    }
    assert manifest["experiment"]["main_model"] == (
        "deepseek/deepseek-v4-flash-0731"
    )


def test_a5_timeout_summary_preserves_missing_trace_as_observed_missingness(
    tmp_path,
):
    from scripts.build_qfbench_a4_evidence import _timeout_execution_summary

    attempt = tmp_path / "attempt"
    attempt.mkdir()
    (attempt / "proxy-audit.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {"request_state": "completed", "total_tokens": 123}
                ),
                json.dumps(
                    {"request_state": "completed", "total_tokens": 456}
                ),
            ]
        )
        + "\n"
    )

    summary = _timeout_execution_summary(
        attempt,
        {"diagnostic_tags": ["timeout"]},
    )

    assert summary["status"] == "worker_timeout"
    assert summary["completed_model_requests_before_timeout"] == 2
    assert summary["observed_total_tokens_before_timeout"] == 579
    assert summary["worker_trace_available"] is False


def test_a5_missing_execution_without_timeout_remains_fail_closed(tmp_path):
    from scripts.build_qfbench_a4_evidence import _timeout_execution_summary

    with pytest.raises(ValueError, match="missing without an explicit timeout"):
        _timeout_execution_summary(tmp_path, {"diagnostic_tags": []})


def test_a5_outcome_delta_keeps_timeout_pass_fraction_unavailable():
    from scripts.audit_qfbench_a5_discovery import _outcome_delta

    delta = _outcome_delta(
        {
            "timed": {"reward": 0.0, "pass_fraction": None},
            "stable": {"reward": 1.0, "pass_fraction": 1.0},
        },
        {
            "timed": {"reward": 0.0, "pass_fraction": 0.0},
            "stable": {"reward": 1.0, "pass_fraction": 1.0},
        },
    )

    assert delta["task_vectors"]["timed"]["pass_fraction"] is None
    assert delta["pass_fraction_comparable_count"] == 1
    assert delta["mean_pass_fraction_delta"] == 0.0
