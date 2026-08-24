from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data/breadth/QF_QUANT_H0_S6_CORE_V2_BREADTH_PLAN.json"
MANIFEST_PATH = ROOT / "data/qfbench/MANIFEST_85_BASELINE.json"


def _plan() -> dict[str, object]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _selected_from_public_manifest() -> list[dict[str, str]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    excluded = {
        "swap-curve-bootstrap-ois",
        "13f-amendment-aware-crowding",
        "fx-forward-cross-rate",
    }
    rows = [
        row
        for row in manifest["baseline"]["primary"]
        if row["reward_kind"] == "binary"
        and row["resource_source"] == "upstream"
        and row["task_id"] not in excluded
    ]
    by_domain: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_domain[row["domain"]].append(row)

    selected: list[dict[str, str]] = []
    for domain in sorted(by_domain):
        for stratum, difficulties in (
            ("low", {"easy", "medium"}),
            ("high", {"hard", "medium-hard", "very-hard", "very_hard"}),
        ):
            pool = sorted(
                (row for row in by_domain[domain] if row["difficulty"] in difficulties),
                key=lambda row: row["task_id"],
            )
            chosen = random.Random(
                f"20260824:{domain}:{stratum}"
            ).choice(pool)
            selected.append(
                {
                    "domain": domain,
                    "stratum": stratum,
                    "difficulty": chosen["difficulty"],
                    "task_id": chosen["task_id"],
                }
            )
    return selected


def _materialize_breadth_argv(plan: dict[str, object], run: dict[str, object]) -> list[str]:
    runtime = plan["runtime"]
    worker_dirs = {
        "quant-h0": ROOT / "qea/worker_quant_h0",
        "quant-h0-s6-core-v2": ROOT / "qea/worker_quant_h0_s6_core_v2",
    }
    argv = [
        str(runtime["python"]),
        str(Path(runtime["source_root"]) / "scripts/run_qfbench_component_pilot.py"),
        "--qfbench-root", str(runtime["qfbench_root"]),
        "--qfbench-manifest", str(runtime["qfbench_manifest"]),
        "--rootless-config", str(runtime["rootless_config"]),
        "--rootless-image-set-manifest", str(runtime["image_set_manifest"]),
        "--run-id", str(run["run_id"]),
        "--results-dir", str(runtime["results_dir"]),
        "--seed-worker", str(ROOT / "qea/worker_quant_h0"),
    ]
    for label in run["arm_order"]:
        argv.extend(("--arm", f"{label}={worker_dirs[label]}"))
    for task_id in run["tasks"]:
        argv.extend(("--task-id", str(task_id)))
    argv.extend(
        (
            "--checkpoint-prefix", str(run["run_id"]),
            "--worker-concurrency", "1",
            "--verifier-concurrency", "1",
            "--approve-external-run",
        )
    )
    return argv


def test_breadth_tasks_are_exactly_reproducible_from_public_metadata() -> None:
    plan = _plan()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    excluded = {
        "swap-curve-bootstrap-ois",
        "13f-amendment-aware-crowding",
        "fx-forward-cross-rate",
    }
    eligible = sorted(
        row["task_id"]
        for row in manifest["baseline"]["primary"]
        if row["reward_kind"] == "binary"
        and row["resource_source"] == "upstream"
        and row["task_id"] not in excluded
    )

    assert plan["breadth_tasks"] == _selected_from_public_manifest()
    assert plan["selection_rule"]["eligible_pool_count"] == 57
    assert plan["selection_rule"]["eligible_task_ids"] == eligible
    assert len(plan["breadth_tasks"]) == 12
    assert {item["domain"] for item in plan["breadth_tasks"]} == {
        "data_engineering",
        "derivatives",
        "execution_microstructure",
        "rates_fx_macro",
        "risk_credit",
        "systematic_strategy",
    }
    assert all(
        sum(item["domain"] == domain for item in plan["breadth_tasks"]) == 2
        for domain in {item["domain"] for item in plan["breadth_tasks"]}
    )


def test_protocol_gate_is_core_v2_only_and_score_independent() -> None:
    plan = _plan()
    gate = plan["protocol_gate"]
    rendered = json.dumps(gate)

    assert gate["tasks"] == [
        "swap-curve-bootstrap-ois",
        "13f-amendment-aware-crowding",
        "fx-forward-cross-rate",
    ]
    assert rendered.count("--arm") == 1
    assert "worker_quant_h0_s6_core_v2" in rendered
    assert "all three research-state traces" in gate["proceed_only_if"]
    assert "Official score is recorded but cannot authorize" in gate["proceed_only_if"]


def test_breadth_runs_cover_two_matched_repetitions_with_reversed_order() -> None:
    plan = _plan()
    runs = plan["breadth_runs"]

    assert len(runs) == 4
    assert sum(len(run["tasks"]) * len(run["arm_order"]) for run in runs) == 48
    for group in {run["group"] for run in runs}:
        first = next(run for run in runs if run["group"] == group and run["repetition"] == 1)
        second = next(run for run in runs if run["group"] == group and run["repetition"] == 2)
        assert second["tasks"] == first["tasks"]
        assert second["arm_order"] == list(reversed(first["arm_order"]))


def test_plan_keeps_full_evolver_reviewer_and_answer_surfaces_out() -> None:
    plan = _plan()
    rendered = json.dumps(plan).casefold()

    assert "worker_quant_h0_s6_core_v2" in rendered
    assert "worker_quant_h0_s6\"" not in rendered
    assert plan["limits"]["no_evolver_reviewer_candidate_or_follow_on"] is True
    assert "optimization-diagnostic" not in rendered
    assert "failed-property identity" in rendered
    assert "prior reward" in rendered
    assert "expected value" in rendered


def test_plan_has_real_protocol_and_budget_stop_boundaries() -> None:
    plan = _plan()
    decisions = {item["decision"]: item for item in plan["terminal_decisions"]}

    assert decisions["STOP_PROTOCOL_NOT_REALIZED"]["next_dispatch"] is None
    assert decisions["ELIGIBLE_FOR_BREADTH_REP1"]["next_dispatch"] == (
        "both frozen repetition-1 breadth groups"
    )
    assert plan["limits"]["protocol_gate"]["worker_sessions"] == 3
    assert plan["limits"]["per_breadth_run"]["worker_sessions"] == 12
    assert plan["limits"]["breadth_campaign"]["worker_sessions"] == 48
    combined = plan["limits"]["protocol_plus_full_breadth_campaign"]
    assert combined == {
        "worker_sessions": 51,
        "verifier_executions": 51,
        "completed_requests": 1700,
        "total_tokens": 102000000,
        "provider_cost_usd": 4.30,
        "sequential_wall_time_seconds": 122400,
    }
    assert plan["runtime"]["max_parallel_runs"] == 1


def test_metrics_and_historical_exposure_are_frozen_without_broad_claims() -> None:
    plan = _plan()
    selection = plan["selection_rule"]
    metrics = plan["metrics"]

    assert "historically public" in selection["historical_exposure_boundary"]
    assert "not unseen" in selection["historical_exposure_boundary"]
    assert "24 matched task-repetition pairs" in metrics["primary"]
    assert "headroom_closure=" in metrics["secondary"]
    assert "report N/A when Legacy is full" in metrics["secondary"]
    assert "1.50 times" in metrics["overhead_acceptance"]
    assert "not stability" in metrics["interpretation"]


def test_plan_launch_surfaces_parse_with_existing_runner() -> None:
    from scripts.run_qfbench_component_pilot import build_parser

    plan = _plan()
    argv = list(plan["protocol_gate"]["launch_argv"])[2:]
    for index, item in enumerate(argv[:-1]):
        if item == "--seed-worker":
            argv[index + 1] = str(ROOT / "qea/worker_quant_h0")
        elif item == "--arm":
            label = argv[index + 1].partition("=")[0]
            argv[index + 1] = (
                f"{label}={ROOT / 'qea/worker_quant_h0_s6_core_v2'}"
            )
    parsed = build_parser().parse_args(argv)
    assert parsed.task_id == plan["protocol_gate"]["tasks"]
    assert [label for label, _ in parsed.arm] == ["quant-h0-s6-core-v2"]

    for run in plan["breadth_runs"]:
        parsed = build_parser().parse_args(
            _materialize_breadth_argv(plan, run)[2:]
        )
        assert parsed.task_id == run["tasks"]
        assert [label for label, _ in parsed.arm] == run["arm_order"]
