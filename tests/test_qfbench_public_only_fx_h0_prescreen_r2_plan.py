from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R1_PLAN_PATH = (
    ROOT / "data/breadth/QF_PUBLIC_ONLY_FX_H0_PRESCREEN_PLAN.json"
)
R2_PLAN_PATH = (
    ROOT / "data/breadth/QF_PUBLIC_ONLY_FX_H0_PRESCREEN_R2_PLAN.json"
)


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


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


def test_r2_is_separate_setup_recovery_after_r1_stop_no_result() -> None:
    plan = _json(R2_PLAN_PATH)
    recovery = plan["recovery_from"]

    assert plan["status"] == "frozen_not_run"
    assert plan["experiment_id"] == (
        "qf-public-only-fx-h0-prescreen-20260824-r2"
    )
    assert recovery["run_id"] == (
        "qf-public-only-fx-h0-prescreen-20260824-r1"
    )
    assert recovery["terminal_decision"] == "STOP_NO_RESULT"
    assert recovery["observed_outcome"] == "model_empty_response"
    assert [
        recovery["worker_turns"],
        recovery["worker_tool_calls"],
        recovery["worker_files"],
        recovery["worker_artifacts"],
    ] == [0, 0, 0, 0]
    assert recovery["official_empty_output_tests_passed"] == 0
    assert recovery["official_empty_output_tests_total"] == 16
    assert recovery["completed_requests"] == 3
    assert recovery["total_tokens"] == 41821
    assert recovery["provider_cost_usd"] == 0.022160676
    assert recovery["final_request_output_tokens"] == 32000
    assert recovery["cleanup"] == "clean"
    assert "not a Quant-H0 capability observation" in recovery[
        "interpretation"
    ]
    assert plan["recovery_identity"]["classification"] == (
        "separately_frozen_setup_recovery_not_repeat"
    )
    assert plan["recovery_identity"]["automatic_r3_allowed"] is False
    assert all(
        "hash" not in key.lower() and "digest" not in key.lower()
        for key in _keys(plan)
    )


def test_r2_changes_only_run_identity_not_treatment_or_runtime() -> None:
    r1 = _json(R1_PLAN_PATH)
    r2 = _json(R2_PLAN_PATH)

    assert r2["scope"]["benchmark"] == r1["scope"]["benchmark"]
    assert r2["scope"]["task_id"] == r1["scope"]["task_id"]
    assert r2["scope"]["arm"] == r1["scope"]["arm"]
    assert r2["scope"]["worker_sessions"] == 1
    assert r2["scope"]["official_verifier_executions"] == 1
    for key in (
        "python",
        "qfbench_root",
        "rootless_config",
        "image_set_manifest",
        "results_dir",
        "worker_route",
    ):
        assert r2["runtime"][key] == r1["runtime"][key]
    assert r2["run"]["runner"] == r1["run"]["runner"]
    assert r2["run"]["arm_label"] == r1["run"]["arm_label"]
    assert r2["run"]["task_id"] == r1["run"]["task_id"]
    assert r2["run"]["worker_concurrency"] == 1
    assert r2["run"]["verifier_concurrency"] == 2
    assert r2["run"]["expected_attempts"] == 1
    assert r2["run"]["seed_worker"] == r2["run"]["arm_worker"]
    assert r2["runtime"]["source_root"].endswith("-r2")
    assert r2["run"]["run_id"].endswith("-r2")
    assert r2["run"]["checkpoint_prefix"].endswith("-r2")


def test_r2_launch_argv_uses_exact_new_identity_and_one_h0_arm() -> None:
    plan = _json(R2_PLAN_PATH)
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
    assert _argument(argv, "--seed-worker") == run["seed_worker"]
    assert _argument(argv, "--arm") == (
        f"{run['arm_label']}={run['arm_worker']}"
    )
    assert _argument(argv, "--task-id") == "fx-forward-cross-rate"
    assert _argument(argv, "--checkpoint-prefix") == run[
        "checkpoint_prefix"
    ]
    assert argv.count("--arm") == 1
    assert argv[-1] == "--approve-external-run"


def test_r2_preserves_hard_wall_audit_thresholds_and_terminal_rules() -> None:
    r1 = _json(R1_PLAN_PATH)
    r2 = _json(R2_PLAN_PATH)

    assert r2["limits"] == r1["limits"]
    assert r2["limit_enforcement"] == r1["limit_enforcement"]
    assert r2["post_run_public_audit"] == r1["post_run_public_audit"]
    assert r2["terminal_decisions"] == r1["terminal_decisions"]
    assert r2["second_invalid_stop"] == {
        "when": (
            "R2 again ends in model_empty_response or any other incomplete "
            "or invalid Worker/verifier outcome"
        ),
        "decision": "STOP_NO_RESULT",
        "automatic_r3": False,
        "next_dispatch": None,
    }
    assert all(
        item["next_dispatch"] is None for item in r2["terminal_decisions"]
    )
