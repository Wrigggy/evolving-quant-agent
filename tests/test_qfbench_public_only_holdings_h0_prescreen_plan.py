from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT / "data/breadth/QF_PUBLIC_ONLY_HOLDINGS_H0_PRESCREEN_PLAN.json"
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


def test_holdings_h0_prescreen_is_one_fresh_h0_worker_and_verifier() -> None:
    plan = _plan()

    assert plan["status"] == "frozen_not_run"
    assert plan["experiment_id"] == (
        "qf-public-only-holdings-h0-prescreen-20260824-r1"
    )
    assert plan["scope"] == {
        "benchmark": "QFBench",
        "task_id": "13f-amendment-aware-crowding",
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


def test_holdings_h0_prescreen_uses_existing_runner_and_exact_ids() -> None:
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
    assert _argument(argv, "--task-id") == (
        "13f-amendment-aware-crowding"
    )
    assert _argument(argv, "--checkpoint-prefix") == experiment_id
    assert _argument(argv, "--worker-concurrency") == "1"
    assert _argument(argv, "--verifier-concurrency") == "2"
    assert argv.count("--arm") == 1
    assert argv[-1] == "--approve-external-run"


def test_holdings_h0_prescreen_has_hard_wall_and_honest_audit_limits() -> None:
    plan = _plan()

    assert plan["limits"] == {
        "max_worker_sessions": 1,
        "max_official_verifier_executions": 1,
        "max_completed_requests": 40,
        "max_total_tokens": 3000000,
        "provider_cost_usd": 0.15,
        "wall_time_hours": 1.5,
        "no_replacement_model_or_provider": True,
        "no_follow_on_dispatch_in_this_plan": True,
    }
    enforcement = plan["limit_enforcement"]
    assert enforcement["wall_time"] == (
        "systemd RuntimeMaxSec=5400 is the hard 90-minute wall"
    )
    assert enforcement["worker_and_verifier_count"] == (
        "fixed by the single-arm single-task runner invocation"
    )
    assert enforcement["requests_tokens_and_provider_cost"] == (
        "post-run audit thresholds; the existing Worker call is not "
        "interrupted mid-turn by these accounting thresholds"
    )
    assert enforcement["threshold_breach"] == (
        "retain the completed accounting and stop with no follow-on dispatch"
    )


def test_holdings_h0_prescreen_terminates_only_invalid_full_or_headroom() -> None:
    plan = _plan()
    decisions = plan["terminal_decisions"]

    assert [item["classification"] for item in decisions] == [
        "invalid",
        "full",
        "headroom",
    ]
    assert [item["decision"] for item in decisions] == [
        "STOP_NO_RESULT",
        "CLOSE_HOLDINGS_NO_HEADROOM",
        "HOLDINGS_HEADROOM_FOR_SEPARATE_PUBLIC_ONLY_PLAN",
    ]
    assert "51/51 with reward 1" in decisions[1]["when"]
    assert "below 51/51" in decisions[2]["when"]
    assert all(item["next_dispatch"] is None for item in decisions)
    assert "may be a valid headroom observation" in plan["run"][
        "artifact_missingness_rule"
    ]
    assert plan["follow_on_clean_evidence_design"]["status"] == (
        "proposed_not_implemented_not_authorized_by_this_plan"
    )


def test_follow_on_evolver_evidence_is_fresh_and_answer_free() -> None:
    plan = _plan()
    design = plan["follow_on_clean_evidence_design"]
    allowed = " ".join(design["evolver_allowed_inputs"])
    forbidden = " ".join(design["evolver_forbidden_inputs"])

    assert "fresh Quant-H0 raw-trace.jsonl" in allowed
    assert "fresh Quant-H0 final text and any output artifacts" in allowed
    assert "official score" not in allowed
    assert "official score" in forbidden
    assert "official property identities" in forbidden
    assert "verifier output" in forbidden
    assert "optimization-diagnostic.json" in forbidden
    assert "prior contaminated holdings candidate" in forbidden
    assert "hidden failing property" in design["evolver_boundary"]


def test_follow_on_reviewer_support_is_verbatim_public_text_only() -> None:
    plan = _plan()
    design = plan["follow_on_clean_evidence_design"]
    sources = design["reviewer_support_sources"]
    instruction = (
        ROOT / plan["selection_evidence"]["public_instruction"]
    ).read_text()

    assert len(sources) == 4
    assert all(item["ref"].startswith("public:13f-") for item in sources)
    assert all(item["verbatim_clause"] for item in sources)
    assert all(item["verbatim_clause"] in instruction for item in sources)
    assert all(
        item["source_path"] == plan["selection_evidence"][
            "public_instruction"
        ]
        for item in sources
    )
    assert "only the exact verbatim public clauses" in design[
        "reviewer_source_rule"
    ]
    assert "No trace, artifact value, official outcome, diagnostic" in design[
        "reviewer_source_rule"
    ]
    boundary = design["candidate_claim_boundary"]
    assert "unstated turnover formula" in boundary
    assert "mandatory pair/list representation" in boundary
    assert design["reviewer_authority"].startswith(
        "PASS means eligible for a separately authorized blind Worker only."
    )
