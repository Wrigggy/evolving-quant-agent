from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2_PLAN_PATH = ROOT / "data/breadth/QF_QUANT_H0_S6_CORE_V2_BREADTH_PLAN.json"
V3_PLAN_PATH = ROOT / "data/breadth/QF_QUANT_H0_S6_CORE_V3_BREADTH_PLAN.json"


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _replace_strings(value: object, old: str, new: str) -> object:
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [_replace_strings(item, old, new) for item in value]
    if isinstance(value, dict):
        return {
            key: _replace_strings(item, old, new)
            for key, item in value.items()
        }
    return value


def test_v3_reuses_exact_v2_selector_tasks_metrics_and_budgets() -> None:
    v2 = _read(V2_PLAN_PATH)
    v3 = _read(V3_PLAN_PATH)

    assert v3["selection_rule"] == v2["selection_rule"]
    assert v3["breadth_tasks"] == v2["breadth_tasks"]
    assert v3["limits"] == v2["limits"]
    assert _replace_strings(v3["metrics"], "Core-v3", "Core-v2") == v2["metrics"]

    assert len(v3["breadth_runs"]) == len(v2["breadth_runs"]) == 4
    for old_run, new_run in zip(v2["breadth_runs"], v3["breadth_runs"], strict=True):
        assert new_run["repetition"] == old_run["repetition"]
        assert new_run["group"] == old_run["group"]
        assert new_run["tasks"] == old_run["tasks"]
        assert _replace_strings(
            new_run["arm_order"], "quant-h0-s6-core-v3", "quant-h0-s6-core-v2"
        ) == old_run["arm_order"]


def test_v3_records_r1_observed_cells_without_using_them_for_selection() -> None:
    plan = _read(V3_PLAN_PATH)
    antecedent = plan["measured_antecedent"]
    cells = {cell["task_id"]: cell for cell in antecedent["cells"]}

    assert antecedent["run_id"] == (
        "qf-quant-h0-s6-core-v2-protocol-gate-20260824-r1"
    )
    assert antecedent["source_result"] == (
        "data/breadth/QF_QUANT_H0_S6_CORE_V2_PROTOCOL_GATE_RESULT.json"
    )
    assert cells["swap-curve-bootstrap-ois"]["protocol"] == "PASS"
    assert "direct assistant-role" in cells["swap-curve-bootstrap-ois"][
        "observed_marker_channel"
    ]
    holdings = cells["13f-amendment-aware-crowding"]
    assert holdings["execution"] == "valid"
    assert holdings["protocol"] == "REJECT"
    assert "run_shell_command echo" in holdings["observed_marker_channel"]
    assert "zero events" in holdings["observed_marker_channel"]
    fx = cells["fx-forward-cross-rate"]
    assert fx["execution"] == "invalid"
    assert fx["protocol"] == "NOT_OBSERVED"
    assert "not evidence about marker realization" in fx["observed_marker_channel"]
    assert "do not select or modify any breadth task" in antecedent["causal_scope"]


def test_r2_protocol_gate_is_new_core_v3_only_and_breadth_is_conditional() -> None:
    plan = _read(V3_PLAN_PATH)
    gate = plan["protocol_gate"]
    rendered_gate = json.dumps(gate)

    assert gate["run_id"] == "qf-quant-h0-s6-core-v3-protocol-gate-20260824-r2"
    assert gate["tasks"] == [
        "swap-curve-bootstrap-ois",
        "13f-amendment-aware-crowding",
        "fx-forward-cross-rate",
    ]
    assert rendered_gate.count("--arm") == 1
    assert "worker_quant_h0_s6_core_v3" in rendered_gate
    assert "non-assistant marker channel" in gate["proceed_only_if"]
    assert "Official score is recorded but cannot authorize" in gate["proceed_only_if"]
    assert plan["execution"]["phase_order"].startswith("Run the protocol gate first")
    assert plan["limits"]["no_evolver_reviewer_candidate_or_follow_on"] is True


def test_r2_plan_is_frozen_but_not_launchable_before_source_resolution() -> None:
    plan = _read(V3_PLAN_PATH)
    freeze = plan["deploy_source_freeze"]

    assert plan["status"] == "frozen_not_run"
    assert freeze["source_revision"].startswith("FUTURE_COMMIT:")
    assert freeze["launch_before_resolution_allowed"] is False
    assert all("core-v3" in run["run_id"] for run in plan["breadth_runs"])
    assert len({run["run_id"] for run in plan["breadth_runs"]}) == 4


def test_r2_protocol_launch_surface_parses_with_existing_runner() -> None:
    from scripts.run_qfbench_component_pilot import build_parser

    plan = _read(V3_PLAN_PATH)
    argv = list(plan["protocol_gate"]["launch_argv"])[2:]
    for index, item in enumerate(argv[:-1]):
        if item == "--seed-worker":
            argv[index + 1] = str(ROOT / "qea/worker_quant_h0")
        elif item == "--arm":
            label = argv[index + 1].partition("=")[0]
            argv[index + 1] = (
                f"{label}={ROOT / 'qea/worker_quant_h0_s6_core_v3'}"
            )

    parsed = build_parser().parse_args(argv)

    assert parsed.task_id == plan["protocol_gate"]["tasks"]
    assert [label for label, _ in parsed.arm] == ["quant-h0-s6-core-v3"]
