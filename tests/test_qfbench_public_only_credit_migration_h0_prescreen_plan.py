from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT
    / "data/breadth/QF_PUBLIC_ONLY_CREDIT_MIGRATION_H0_PRESCREEN_PLAN.json"
)


def _plan() -> dict[str, object]:
    return json.loads(PLAN_PATH.read_text())


def _argument(argv: list[str], name: str) -> str:
    return argv[argv.index(name) + 1]


def _keys(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


def test_credit_migration_prescreen_is_one_fresh_h0_worker_and_verifier() -> None:
    plan = _plan()

    assert plan["status"] == "frozen_not_run"
    assert plan["experiment_id"] == (
        "qf-public-only-credit-migration-h0-prescreen-20260824-r1"
    )
    assert plan["scope"] == {
        "benchmark": "QFBench",
        "task_id": "credit-migration-matrix",
        "arm": "Quant-H0",
        "worker_sessions": 1,
        "official_verifier_executions": 1,
        "sealed_evaluation_used": False,
        "result_role": "adaptive development target pre-screen only",
    }
    assert plan["run"]["seed_worker"] == plan["run"]["arm_worker"]
    assert plan["run"]["expected_attempts"] == 1
    assert plan["selection_evidence"]["worker_visible"] is False
    assert "automatic proposal" in plan["purpose"]
    assert all(
        "hash" not in key.lower() and "digest" not in key.lower()
        for key in _keys(plan)
    )


def test_credit_migration_prescreen_uses_existing_runner_and_exact_ids() -> None:
    plan = _plan()
    runtime = plan["runtime"]
    run = plan["run"]
    argv = plan["launch_argv"]
    experiment_id = plan["experiment_id"]

    assert plan["deploy_source_freeze"]["deploy_id"] == experiment_id
    assert plan["deploy_source_freeze"]["source_revision"] == (
        f"FUTURE_COMMIT:{experiment_id}"
    )
    assert plan["deploy_source_freeze"][
        "launch_before_resolution_allowed"
    ] is False
    assert runtime["source_root"].endswith(f"/{experiment_id}")
    assert run["run_id"] == experiment_id
    assert run["checkpoint_prefix"] == experiment_id
    assert argv[0] == runtime["python"]
    assert argv[1] == f"{runtime['source_root']}/{run['runner']}"
    assert _argument(argv, "--qfbench-root") == runtime["qfbench_root"]
    assert _argument(argv, "--qfbench-manifest") == runtime[
        "qfbench_manifest"
    ]
    assert _argument(argv, "--rootless-config") == runtime[
        "rootless_config"
    ]
    assert _argument(argv, "--rootless-image-set-manifest") == runtime[
        "image_set_manifest"
    ]
    assert _argument(argv, "--run-id") == experiment_id
    assert _argument(argv, "--results-dir") == runtime["results_dir"]
    assert _argument(argv, "--seed-worker") == run["seed_worker"]
    assert _argument(argv, "--arm") == (
        f"{run['arm_label']}={run['arm_worker']}"
    )
    assert _argument(argv, "--task-id") == "credit-migration-matrix"
    assert _argument(argv, "--checkpoint-prefix") == experiment_id
    assert _argument(argv, "--worker-concurrency") == "1"
    assert _argument(argv, "--verifier-concurrency") == "2"
    assert argv.count("--arm") == 1
    assert argv[-1] == "--approve-external-run"


def test_credit_migration_prescreen_has_exact_caps_and_no_follow_on() -> None:
    plan = _plan()

    assert plan["limits"] == {
        "max_worker_sessions": 1,
        "max_official_verifier_executions": 1,
        "max_completed_requests": 40,
        "max_total_tokens": 3000000,
        "provider_cost_usd": 0.15,
        "hard_wall_time_seconds": 5400,
        "no_replacement_model_or_provider": True,
        "no_follow_on_dispatch_in_this_plan": True,
    }
    enforcement = plan["limit_enforcement"]
    assert enforcement["wall_time"] == (
        "systemd RuntimeMaxSec=5400 is the hard 90-minute wall"
    )
    assert enforcement["requests_tokens_and_provider_cost"] == (
        "post-run audit thresholds; the existing Worker call is not "
        "interrupted mid-turn by these accounting thresholds"
    )
    assert enforcement["threshold_breach"] == (
        "retain the completed accounting and stop with no follow-on dispatch"
    )


def test_public_mass_audit_uses_only_exact_current_artifact_relations() -> None:
    plan = _plan()
    audit = plan["post_run_public_audit"]

    assert audit["required_artifacts"] == [
        "artifacts/cohort_sizes.csv",
        "artifacts/cohort_default_rates.csv",
        "artifacts/summary.json",
    ]
    assert audit["count_columns"] == [
        "AAA",
        "AA",
        "A",
        "BBB",
        "BB",
        "B",
        "CCC",
    ]
    mismatch = audit["count_mass_mismatch_present_when"]
    assert "summary.total_transitions differs exactly" in mismatch
    assert "total_issuers differs exactly" in mismatch
    assert "Historical numeric values are not audit constants" in audit[
        "forbidden_inputs"
    ]
    assert "official property identities" in audit["forbidden_inputs"]


def test_terminal_decisions_distinguish_invalid_full_and_public_mass_headroom() -> None:
    plan = _plan()
    decisions = plan["terminal_decisions"]

    assert [item["classification"] for item in decisions] == [
        "invalid",
        "full",
        "public_mass_headroom",
        "below_full_without_public_mass_mismatch",
    ]
    assert [item["decision"] for item in decisions] == [
        "STOP_NO_RESULT",
        "CLOSE_CREDIT_MIGRATION_NO_HEADROOM",
        "ELIGIBLE_FOR_SEPARATE_PUBLIC_ONLY_CREDIT_MIGRATION_PROPOSAL_PLAN",
        "STOP_CREDIT_MIGRATION_NOT_PUBLICLY_LOCALIZED",
    ]
    assert "107/107 with reward 1" in decisions[1]["when"]
    assert "below 107/107" in decisions[2]["when"]
    assert "count_mass_mismatch_present" in decisions[2]["when"]
    assert "no count_mass_mismatch_present or is not evaluable" in decisions[
        3
    ]["when"]
    assert all(item["next_dispatch"] is None for item in decisions)


def test_future_design_is_answer_free_reviewed_and_protection_is_not_run() -> None:
    plan = _plan()
    design = plan["follow_on_clean_evidence_design"]
    allowed = " ".join(design["evolver_allowed_inputs"])
    forbidden = " ".join(design["evolver_forbidden_inputs"])

    assert design["status"] == (
        "future_design_only_not_implemented_not_authorized_by_this_plan"
    )
    assert design["target_task_id"] == "credit-migration-matrix"
    assert design["protection_task_id"] == "historical-var-data-prep"
    assert "no protection Worker" in design["protection_role"]
    assert "fresh Quant-H0 raw-trace.jsonl" in allowed
    assert "official score" not in allowed
    assert "official score" in forbidden
    assert "official property identities" in forbidden
    assert "historical values 22956, 22935, or 21" in forbidden
    assert "mandatory arm-blind" in design["reviewer_requirement"]
    assert "REJECT or INCONCLUSIVE stops with zero Worker" in design[
        "reviewer_requirement"
    ]
    assert "may not hard-code a dataset total" in design[
        "candidate_claim_boundary"
    ]
    assert "Selection evidence" in plan["answer_boundary"]
