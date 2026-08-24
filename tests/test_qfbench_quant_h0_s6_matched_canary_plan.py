from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data/breadth/QF_QUANT_H0_S6_MATCHED_CANARY_PLAN.json"


def _plan() -> dict[str, object]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _values(argv: list[str], option: str) -> list[str]:
    return [argv[index + 1] for index, item in enumerate(argv) if item == option]


def _keys(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


def test_canary_is_three_tasks_two_repetitions_and_eighteen_worker_cells() -> None:
    plan = _plan()

    assert plan["status"] == "frozen_not_run"
    assert plan["experiment_id"] == (
        "qf-quant-h0-s6-matched-canary-20260824-r1"
    )
    assert [item["task_id"] for item in plan["task_selection"]] == [
        "swap-curve-bootstrap-ois",
        "13f-amendment-aware-crowding",
        "fx-forward-cross-rate",
    ]
    assert len(plan["runs"]) == 2
    assert plan["limits"]["max_worker_sessions"] == 18
    assert plan["limits"]["max_official_verifier_executions"] == 18
    assert plan["selection_boundary"]["sealed_tasks_used"] is False
    assert plan["selection_boundary"][
        "official_selection_values_worker_visible"
    ] is False


def test_canary_reverses_arm_order_with_identical_runtime_and_tasks() -> None:
    plan = _plan()
    first, second = plan["runs"]

    assert first["arm_order"] == [
        "quant-h0",
        "quant-h0-s6-core",
        "quant-h0-s6-full",
    ]
    assert second["arm_order"] == list(reversed(first["arm_order"]))
    assert _values(first["launch_argv"], "--arm") == [
        "quant-h0=" + plan["runtime"]["source_root"] + "/qea/worker_quant_h0",
        "quant-h0-s6-core="
        + plan["runtime"]["source_root"]
        + "/qea/worker_quant_h0_s6_core",
        "quant-h0-s6-full="
        + plan["runtime"]["source_root"]
        + "/qea/worker_quant_h0_s6",
    ]
    assert _values(second["launch_argv"], "--arm") == list(
        reversed(_values(first["launch_argv"], "--arm"))
    )
    assert _values(first["launch_argv"], "--task-id") == _values(
        second["launch_argv"], "--task-id"
    ) == [
        "swap-curve-bootstrap-ois",
        "13f-amendment-aware-crowding",
        "fx-forward-cross-rate",
    ]
    for option in (
        "--qfbench-root",
        "--qfbench-manifest",
        "--rootless-config",
        "--rootless-image-set-manifest",
        "--results-dir",
        "--seed-worker",
        "--worker-concurrency",
        "--verifier-concurrency",
    ):
        assert _values(first["launch_argv"], option) == _values(
            second["launch_argv"], option
        )


def test_canary_launch_argv_is_accepted_by_the_existing_component_runner() -> None:
    from scripts.run_qfbench_component_pilot import build_parser

    plan = _plan()
    local_workers = {
        "quant-h0": ROOT / "qea/worker_quant_h0",
        "quant-h0-s6-core": ROOT / "qea/worker_quant_h0_s6_core",
        "quant-h0-s6-full": ROOT / "qea/worker_quant_h0_s6",
    }
    for run in plan["runs"]:
        argv = list(run["launch_argv"][2:])
        for index, item in enumerate(argv[:-1]):
            if item == "--arm":
                label = argv[index + 1].partition("=")[0]
                argv[index + 1] = f"{label}={local_workers[label]}"
        parsed = build_parser().parse_args(argv)
        assert parsed.task_id == [
            "swap-curve-bootstrap-ois",
            "13f-amendment-aware-crowding",
            "fx-forward-cross-rate",
        ]
        assert [label for label, _ in parsed.arm] == run["arm_order"]
        assert parsed.approve_external_run is True


def test_canary_is_worker_only_and_keeps_answer_surfaces_out() -> None:
    plan = _plan()
    rendered = json.dumps(plan).casefold()

    assert plan["limits"]["no_evolver_reviewer_or_follow_on_dispatch"] is True
    assert "run_qfbench_component_pilot.py" in rendered
    assert "optimization-diagnostic" not in rendered
    assert "expected value" in plan["answer_boundary"].casefold()
    assert "failed-property identities" in plan["answer_boundary"].casefold()
    assert "reviewer feedback" in plan["answer_boundary"].casefold()
    assert all(
        "hash" not in key.casefold() and "digest" not in key.casefold()
        for key in _keys(plan)
    )


def test_canary_reports_vectors_and_has_predeclared_trim_rule() -> None:
    plan = _plan()
    metrics = plan["metrics"]
    interpretations = {
        item["decision"]: item for item in plan["terminal_interpretation"]
    }

    assert metrics["paired_unit"] == "task_id x fresh repetition"
    assert "official tests passed and total" in metrics["primary_vector"]
    assert "core and full minus legacy passed-property deltas for each cell" in metrics[
        "headroom_vector"
    ]
    assert "S1-S6 accounted-stage coverage" in metrics["process_vector"]
    assert set(interpretations) == {
        "INVALID_CANARY",
        "S6_PROTOCOL_NOT_REALIZED",
        "FULL_HUMAN_WORKFLOW_ADVANTAGE",
        "S6_CORE_SUBSTRATE_ACCEPTED",
        "S6_REVISE_OR_REJECT",
    }
    full_advantage = interpretations["FULL_HUMAN_WORKFLOW_ADVANTAGE"]
    assert "three quarters" in full_advantage["when"]
    assert "human-authored workflow engineering" in full_advantage["action"]
    assert "Keep Core" in full_advantage["action"]
    core = interpretations["S6_CORE_SUBSTRATE_ACCEPTED"]
    assert "does not require Core to preserve old task headroom" in core["when"]
    assert "rather than weakening Core" in core["action"]


def test_canary_caps_parallelism_cost_and_hard_wall() -> None:
    plan = _plan()

    assert plan["runtime"]["max_parallel_runs"] == 1
    assert plan["runtime"]["worker_concurrency_per_run"] == 1
    assert plan["limits"]["max_completed_requests_per_run"] == 300
    assert plan["limits"]["max_total_tokens_per_run"] == 18_000_000
    assert plan["limits"]["provider_cost_usd_per_run"] == 0.75
    assert plan["limits"]["campaign_provider_cost_usd"] == 1.50
    assert plan["execution"]["hard_wall"] == (
        "Each systemd unit uses RuntimeMaxSec=18000."
    )
    assert "No automatic third repetition" in plan["execution"][
        "invalid_recovery"
    ]
