from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT / "data/breadth/QF_PUBLIC_ONLY_FX_H0_PRESCREEN_PLAN.json"
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


def test_fx_h0_prescreen_is_one_answer_free_official_arm() -> None:
    plan = _plan()

    assert plan["status"] == "frozen_not_run"
    assert plan["experiment_id"] == (
        "qf-public-only-fx-h0-prescreen-20260824-r1"
    )
    assert plan["scope"] == {
        "benchmark": "QFBench",
        "task_id": "fx-forward-cross-rate",
        "arm": "Quant-H0",
        "worker_sessions": 1,
        "official_verifier_executions": 1,
        "sealed_evaluation_used": False,
        "result_role": "adaptive development target pre-screen only",
    }
    assert plan["selection_evidence"]["worker_visible"] is False
    assert plan["run"]["seed_worker"] == plan["run"]["arm_worker"]
    assert plan["run"]["expected_attempts"] == 1
    assert "Evolver diagnostic" in plan["answer_boundary"]
    assert "launches no reusable candidate" in plan["answer_boundary"]
    assert all(
        "hash" not in key.lower() and "digest" not in key.lower()
        for key in _keys(plan)
    )


def test_fx_h0_prescreen_launch_argv_uses_existing_runner_and_exact_ids() -> None:
    plan = _plan()
    runtime = plan["runtime"]
    run = plan["run"]
    argv = plan["launch_argv"]

    assert argv[0] == runtime["python"]
    assert argv[1] == f"{runtime['source_root']}/{run['runner']}"
    assert _argument(argv, "--qfbench-root") == runtime["qfbench_root"]
    assert _argument(argv, "--qfbench-manifest") == runtime["qfbench_manifest"]
    assert _argument(argv, "--rootless-config") == runtime["rootless_config"]
    assert _argument(argv, "--rootless-image-set-manifest") == runtime[
        "image_set_manifest"
    ]
    assert _argument(argv, "--run-id") == run["run_id"]
    assert _argument(argv, "--results-dir") == runtime["results_dir"]
    assert _argument(argv, "--seed-worker") == run["seed_worker"]
    assert _argument(argv, "--arm") == (
        f"{run['arm_label']}={run['arm_worker']}"
    )
    assert _argument(argv, "--task-id") == "fx-forward-cross-rate"
    assert _argument(argv, "--checkpoint-prefix") == run[
        "checkpoint_prefix"
    ]
    assert _argument(argv, "--worker-concurrency") == "1"
    assert _argument(argv, "--verifier-concurrency") == "2"
    assert argv.count("--arm") == 1
    assert argv[-1] == "--approve-external-run"


def test_fx_h0_prescreen_budget_and_terminal_stops_are_frozen() -> None:
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
    assert plan["limit_enforcement"] == {
        "wall_time": "systemd RuntimeMaxSec=5400",
        "worker_and_verifier_count": (
            "fixed by the single-arm single-task runner invocation"
        ),
        "requests_tokens_and_provider_cost": (
            "post-run audit thresholds; the existing Worker call is not "
            "interrupted mid-turn by these accounting thresholds"
        ),
        "threshold_breach": (
            "retain the completed accounting and stop with no follow-on dispatch"
        ),
    }
    decisions = plan["terminal_decisions"]
    assert [item["decision"] for item in decisions] == [
        "STOP_NO_RESULT",
        "CLOSE_FX_NO_HEADROOM",
        "ELIGIBLE_FOR_SEPARATE_PUBLIC_ONLY_PROPOSAL_PLAN",
        "STOP_TARGET_NOT_PUBLICLY_LOCALIZED",
    ]
    assert all(item["next_dispatch"] is None for item in decisions)
    assert "differs from the same value rounded to four decimal places" in (
        plan["post_run_public_audit"]["rule"]
    )
    assert "public instruction and Worker artifact only" in (
        plan["post_run_public_audit"]["answer_access"]
    )
