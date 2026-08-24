"""Deterministic outer scheduler for the Primitive-H0 global QRS campaign.

The scheduler owns ordering, checkpointing, cost accounting, parent chaining,
and terminal decisions.  Child execution is injected so the state machine can
be exercised locally without a model, benchmark, or remote runtime.  Official
fitness remains controller-only; the Evolver receives only the trajectory-bank
views built by a separate answer-free packager.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from decimal import Decimal
from math import isfinite
from pathlib import Path
from typing import Any

from qea.frozen_base_harness import (
    FrozenBaseHarnessError,
    inspect_base_harness,
    validate_frozen_worker_tree_read_only,
    validate_selected_runtime,
)
from qea.qrs_candidate_boundary import inspect_qrs_candidate_boundary


ActionRunner = Callable[[Mapping[str, object]], Mapping[str, object]]
TERMINAL_STATUSES = frozenset(
    {
        "COMPLETE",
        "STOP_ADAPTER",
        "STOP_BANK",
        "STOP_PANEL",
        "STOP_MAIN",
        "STOP_CAP",
    }
)


class GlobalSchedulerError(ValueError):
    """The global schedule or an imported child result is not admissible."""


def _json(path: str | Path) -> dict[str, object]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GlobalSchedulerError(f"cannot read JSON object: {source}") from exc
    if not isinstance(value, dict):
        raise GlobalSchedulerError(f"expected JSON object: {source}")
    return value


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _empty_cost() -> dict[str, object]:
    return {
        "provider_cost_usd": "0",
        "completed_requests": 0,
        "total_tokens": 0,
    }


def _normalized_cost(value: object) -> dict[str, object]:
    cost = value if isinstance(value, Mapping) else {}
    request_value = cost.get(
        "completed_requests", cost.get("completed_request_count", 0)
    )
    try:
        provider_cost = Decimal(str(cost.get("provider_cost_usd", "0")))
        completed_requests = int(request_value)
        total_tokens = int(cost.get("total_tokens", 0))
    except (ValueError, TypeError) as exc:
        raise GlobalSchedulerError("child cost fields are not numeric") from exc
    if provider_cost < 0 or completed_requests < 0 or total_tokens < 0:
        raise GlobalSchedulerError("child cost fields must be non-negative")
    return {
        "provider_cost_usd": format(provider_cost, "f"),
        "completed_requests": completed_requests,
        "total_tokens": total_tokens,
    }


def _add_cost(total: dict[str, object], child: Mapping[str, object]) -> None:
    total["provider_cost_usd"] = format(
        Decimal(str(total["provider_cost_usd"]))
        + Decimal(str(child["provider_cost_usd"])),
        "f",
    )
    total["completed_requests"] = int(total["completed_requests"]) + int(
        child["completed_requests"]
    )
    total["total_tokens"] = int(total["total_tokens"]) + int(
        child["total_tokens"]
    )


def _task_panels(method: Mapping[str, object]) -> list[dict[str, object]]:
    values = method.get("development_panels")
    if not isinstance(values, list) or not values:
        raise GlobalSchedulerError("method plan has no development panels")
    panels: list[dict[str, object]] = []
    seen_tasks: set[str] = set()
    for expected_index, value in enumerate(values, start=1):
        if not isinstance(value, Mapping):
            raise GlobalSchedulerError("development panel must be a JSON object")
        index = value.get("panel_index")
        family = value.get("family")
        task_ids = value.get("task_ids")
        if index != expected_index:
            raise GlobalSchedulerError("development panels must be indexed from one")
        if not isinstance(family, str) or not family:
            raise GlobalSchedulerError(f"panel {index} has no family")
        if not isinstance(task_ids, list) or not task_ids:
            raise GlobalSchedulerError(f"panel {index} has no tasks")
        if any(not isinstance(task_id, str) or not task_id for task_id in task_ids):
            raise GlobalSchedulerError(f"panel {index} has an invalid task id")
        if task_ids != sorted(task_ids) or len(task_ids) != len(set(task_ids)):
            raise GlobalSchedulerError(f"panel {index} tasks must be unique and sorted")
        overlap = seen_tasks.intersection(task_ids)
        if overlap:
            raise GlobalSchedulerError(
                f"development tasks occur in multiple panels: {sorted(overlap)}"
            )
        seen_tasks.update(task_ids)
        panels.append(deepcopy(dict(value)))
    expected_n = method.get("public_task_partition_rule", {}).get("development_n")
    if len(seen_tasks) != expected_n:
        raise GlobalSchedulerError(
            f"development universe has {len(seen_tasks)} tasks, expected {expected_n}"
        )
    return panels


def _sealed_tasks(method: Mapping[str, object]) -> list[dict[str, object]]:
    values = method.get("sealed_main_tasks")
    if not isinstance(values, list) or not values:
        raise GlobalSchedulerError("method plan has no sealed tasks")
    tasks: list[dict[str, object]] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, Mapping):
            raise GlobalSchedulerError("sealed task must be a JSON object")
        task_id = value.get("task_id")
        group = value.get("group")
        if not isinstance(task_id, str) or not task_id:
            raise GlobalSchedulerError("sealed task has no task_id")
        if group not in {"a", "b"}:
            raise GlobalSchedulerError(f"sealed task {task_id} has invalid group")
        if task_id in seen:
            raise GlobalSchedulerError(f"duplicate sealed task: {task_id}")
        seen.add(task_id)
        tasks.append(deepcopy(dict(value)))
    development = {
        task_id
        for panel in _task_panels(method)
        for task_id in panel["task_ids"]
    }
    overlap = development.intersection(seen)
    if overlap:
        raise GlobalSchedulerError(
            f"sealed and development tasks overlap: {sorted(overlap)}"
        )
    return tasks


def _validate_method(method: Mapping[str, object]) -> None:
    phases = method.get("phase_order")
    expected = [
        "import_frozen_primitive_h0",
        "phase0_all_n_h0_development_bank",
        "phase1_six_panel_curriculum",
        "phase2_feedback_sealed_main",
        "terminal_report",
    ]
    if phases != expected:
        raise GlobalSchedulerError("method phase order is not the frozen QRS order")
    panels = _task_panels(method)
    sealed = _sealed_tasks(method)
    limits = method.get("limits")
    if not isinstance(limits, Mapping):
        raise GlobalSchedulerError("method plan has no limits")
    expected_cells = sum(len(panel["task_ids"]) for panel in panels)
    expected_cells += sum(
        4 * len(_panel_evaluation_tasks(method, panel)) for panel in panels
    )
    expected_cells += 4 * len(sealed)
    if expected_cells != limits.get("qfbench_primary_cells"):
        raise GlobalSchedulerError(
            f"method schedule has {expected_cells} primary cells, not the frozen cap"
        )


def _validate_launch(
    launch: Mapping[str, object], method: Mapping[str, object]
) -> None:
    run_id = launch.get("scheduler_run_id")
    if not isinstance(run_id, str) or not run_id:
        raise GlobalSchedulerError("launch plan has no scheduler_run_id")
    handoff = launch.get("frozen_h0_handoff")
    if not isinstance(handoff, str) or not handoff:
        raise GlobalSchedulerError("launch plan has no frozen_h0_handoff")
    method_path = launch.get("method_plan_path")
    if not isinstance(method_path, str) or not method_path:
        raise GlobalSchedulerError("launch plan has no method_plan_path")
    panel_plans = launch.get("panel_controller_plans")
    if not isinstance(panel_plans, Mapping):
        raise GlobalSchedulerError("launch plan has no panel_controller_plans")
    for panel in _task_panels(method):
        key = str(panel["panel_index"])
        if not isinstance(panel_plans.get(key), str) or not panel_plans[key]:
            raise GlobalSchedulerError(f"launch plan has no controller plan for panel {key}")
    runtime = launch.get("runtime")
    if not isinstance(runtime, Mapping):
        raise GlobalSchedulerError("launch plan has no runtime")
    for key in (
        "python",
        "source_root",
        "qfbench_root",
        "qfbench_manifest",
        "rootless_config",
        "image_set_manifest",
        "results_dir",
    ):
        if not isinstance(runtime.get(key), str) or not runtime[key]:
            raise GlobalSchedulerError(f"launch runtime has no {key}")
    output_root = launch.get("trajectory_bank_output")
    if not isinstance(output_root, str) or not output_root:
        raise GlobalSchedulerError("launch plan has no trajectory_bank_output")
    for key in (
        "qfbench_public_manifest",
        "trajectory_bank_manifest",
        "public_contracts_root",
    ):
        if not isinstance(launch.get(key), str) or not launch[key]:
            raise GlobalSchedulerError(f"launch plan has no {key}")


def new_scheduler_state(
    method: Mapping[str, object], launch: Mapping[str, object]
) -> dict[str, object]:
    """Create an ordinary-JSON state before importing the frozen H0 handoff."""

    _validate_method(method)
    _validate_launch(launch, method)
    return {
        "schema_version": 1,
        "scheduler_run_id": launch["scheduler_run_id"],
        "method_input": deepcopy(dict(method)),
        "launch_input": deepcopy(dict(launch)),
        "status": "RUNNING",
        "phase": "IMPORT_H0",
        "stop_reason": None,
        "frozen_h0": None,
        "current_parent": None,
        "bank_next_index": 0,
        "bank_results": {},
        "trajectory_bank": None,
        "panel_next_index": 0,
        "panel_stage": "PROPOSAL_REVIEW",
        "panel_results": [],
        "curriculum_handoffs": [],
        "current_panel_review": None,
        "current_panel_repetitions": {},
        "checkpoints": [],
        "sealed_next_index": 0,
        "sealed_results": [],
        "sealed_summary": None,
        "accounted_action_ids": [],
        "qfbench_cells_accounted": 0,
        "cost": _empty_cost(),
    }


def _stop(state: dict[str, object], status: str, reason: str) -> None:
    state["status"] = status
    state["phase"] = "TERMINAL"
    state["stop_reason"] = reason


def _import_handoff(
    state: dict[str, object], launch: Mapping[str, object]
) -> None:
    try:
        handoff = _json(str(launch["frozen_h0_handoff"]))
        if handoff.get("selection_complete") is not True:
            raise GlobalSchedulerError("frozen H0 selection is not complete")
        if handoff.get("frozen_for_qrs_scheduler") is not True:
            raise GlobalSchedulerError("base harness is not frozen for the scheduler")
        worker_dir = handoff.get("selected_worker_root")
        profile_id = handoff.get("selected_profile_id")
        runtime = handoff.get("selected_runtime")
        if not isinstance(worker_dir, str) or not worker_dir:
            raise GlobalSchedulerError("frozen H0 has no selected_worker_root")
        if not isinstance(profile_id, str) or not profile_id:
            raise GlobalSchedulerError("frozen H0 has no selected_profile_id")
        if not isinstance(runtime, Mapping):
            raise GlobalSchedulerError("frozen H0 has no selected_runtime")
        validate_selected_runtime(runtime)
        inspect_base_harness(worker_dir)
        adapter = handoff.get("adapter_contract")
        if (
            not isinstance(adapter, Mapping)
            or adapter.get("selected_worker_tree_read_only") is not True
        ):
            raise GlobalSchedulerError(
                "frozen H0 handoff does not declare a read-only Worker tree"
            )
        validate_frozen_worker_tree_read_only(worker_dir)
        launch_runtime = launch["runtime"]
        if runtime.get("worker_model_route") != launch_runtime.get("worker_route"):
            raise GlobalSchedulerError("launch worker route differs from frozen H0")
        if runtime.get("rootless_config") != launch_runtime.get("rootless_config"):
            raise GlobalSchedulerError("launch rootless config differs from frozen H0")
    except (FrozenBaseHarnessError, GlobalSchedulerError) as exc:
        _stop(state, "STOP_ADAPTER", str(exc))
        return
    frozen = {
        "version": profile_id,
        "worker_dir": str(Path(worker_dir).resolve()),
        "handoff_path": str(Path(str(launch["frozen_h0_handoff"])).resolve()),
        "runtime": deepcopy(dict(runtime)),
        "adapter_contract": deepcopy(dict(handoff.get("adapter_contract", {}))),
    }
    state["frozen_h0"] = frozen
    state["current_parent"] = {
        "version": frozen["version"],
        "worker_dir": frozen["worker_dir"],
    }
    state["phase"] = "H0_BANK"


def _development_tasks(method: Mapping[str, object]) -> list[str]:
    return [
        task_id
        for panel in _task_panels(method)
        for task_id in panel["task_ids"]
    ]


def _development_families(method: Mapping[str, object]) -> list[str]:
    return [str(panel["family"]) for panel in _task_panels(method)]


def _anchor_task_by_family(method: Mapping[str, object]) -> dict[str, str]:
    policy = method.get("cross_family_workflow_evidence")
    anchors = policy.get("anchor_task_by_family") if isinstance(policy, Mapping) else None
    families = _development_families(method)
    if not isinstance(anchors, Mapping) or set(anchors) != set(families):
        raise GlobalSchedulerError(
            "method must declare exactly one development anchor per family"
        )
    normalized: dict[str, str] = {}
    development = set(_development_tasks(method))
    for family in families:
        task_id = anchors.get(family)
        if not isinstance(task_id, str) or not task_id or task_id not in development:
            raise GlobalSchedulerError(f"invalid development anchor for {family}")
        family_panel = next(
            panel for panel in _task_panels(method) if panel["family"] == family
        )
        if task_id not in family_panel["task_ids"]:
            raise GlobalSchedulerError(
                f"development anchor does not belong to family {family}"
            )
        normalized[family] = task_id
    if len(set(normalized.values())) != len(normalized):
        raise GlobalSchedulerError("development anchors must be unique")
    return normalized


def _panel_anchor_tasks(
    method: Mapping[str, object], panel: Mapping[str, object]
) -> list[str]:
    anchors = _anchor_task_by_family(method)
    return sorted(
        task_id for family, task_id in anchors.items() if family != panel["family"]
    )


def _panel_evaluation_tasks(
    method: Mapping[str, object], panel: Mapping[str, object]
) -> list[str]:
    return sorted(list(panel["task_ids"]) + _panel_anchor_tasks(method, panel))


def _sealed_families(method: Mapping[str, object]) -> list[str]:
    return sorted({str(value["domain"]) for value in _sealed_tasks(method)})


def _h0_action(
    state: Mapping[str, object], method: Mapping[str, object], task_id: str
) -> dict[str, object]:
    run_id = str(state["scheduler_run_id"])
    h0 = state["frozen_h0"]
    return {
        "action_id": f"{run_id}-h0-{task_id}",
        "kind": "component_pilot",
        "purpose": "h0_bank",
        "run_id": f"{run_id}-h0-{task_id}",
        "task_ids": [task_id],
        "arms": [{"label": "h0", "worker_dir": h0["worker_dir"]}],
        "seed_worker": h0["worker_dir"],
        "require_protocol": True,
        "sealed": False,
    }


def _bank_action(
    state: Mapping[str, object], method: Mapping[str, object], launch: Mapping[str, object]
) -> dict[str, object]:
    return {
        "action_id": f"{state['scheduler_run_id']}-build-trajectory-bank",
        "kind": "build_trajectory_bank",
        "purpose": "evolver_answer_free_bank",
        "task_ids": _development_tasks(method),
        "controller_reports": [
            value["report_path"] for value in state["bank_results"].values()
        ],
        "output_root": launch["trajectory_bank_output"],
        "sealed_task_ids": [value["task_id"] for value in _sealed_tasks(method)],
    }


def _panel_action(
    state: Mapping[str, object], method: Mapping[str, object], launch: Mapping[str, object]
) -> dict[str, object]:
    panel = _task_panels(method)[int(state["panel_next_index"])]
    plan_path = launch["panel_controller_plans"][str(panel["panel_index"])]
    return {
        "action_id": f"{state['scheduler_run_id']}-panel-{panel['panel_index']}-review",
        "kind": "panel_proposal_review",
        "purpose": "workflow_global_candidate_review",
        "panel_index": panel["panel_index"],
        "family": panel["family"],
        "proposal_version": panel["proposal"],
        "controller_plan_path": plan_path,
        "current_parent": deepcopy(state["current_parent"]),
        "frozen_h0_worker_dir": state["frozen_h0"]["worker_dir"],
        "trajectory_bank": deepcopy(state["trajectory_bank"]),
        "stop_after_stage": "information_set_review",
    }


def _matched_action(
    state: Mapping[str, object], method: Mapping[str, object], repetition: int
) -> dict[str, object]:
    panel = _task_panels(method)[int(state["panel_next_index"])]
    review = state["current_panel_review"]
    parent = state["current_parent"]
    candidate = review["candidate"]
    arms = [
        {"label": "parent", "worker_dir": parent["worker_dir"]},
        {"label": "candidate", "worker_dir": candidate["worker_dir"]},
    ]
    if repetition == 2:
        arms.reverse()
    run_id = (
        f"{state['scheduler_run_id']}-panel-{panel['panel_index']}"
        f"-matched-r{repetition}"
    )
    focus_tasks = list(panel["task_ids"])
    anchor_tasks = _panel_anchor_tasks(method, panel)
    return {
        "action_id": run_id,
        "kind": "component_pilot",
        "purpose": "panel_matched_fitness",
        "run_id": run_id,
        "panel_index": panel["panel_index"],
        "repetition": repetition,
        "task_ids": _panel_evaluation_tasks(method, panel),
        "focus_task_ids": focus_tasks,
        "anchor_task_ids": anchor_tasks,
        "arms": arms,
        "seed_worker": parent["worker_dir"],
        "require_protocol": True,
        "sealed": False,
    }


def _augment_action(
    state: Mapping[str, object], method: Mapping[str, object]
) -> dict[str, object]:
    panel_index = int(state["panel_next_index"])
    panels = _task_panels(method)
    if panel_index >= len(panels) - 1:
        raise GlobalSchedulerError("final panel has no next curriculum evidence view")
    panel = panels[panel_index]
    next_panel = panels[panel_index + 1]
    panel_views = state["trajectory_bank"]["panel_views"]
    repetitions = state["current_panel_repetitions"]
    if set(repetitions) != {"1", "2"}:
        raise GlobalSchedulerError("accepted panel has no two matched reports")
    return {
        "action_id": (
            f"{state['scheduler_run_id']}-panel-{panel['panel_index']}"
            f"-augment-panel-{next_panel['panel_index']}"
        ),
        "kind": "augment_panel_evidence",
        "purpose": "accepted_answer_free_curriculum_handoff",
        "panel_index": panel["panel_index"],
        "family": panel["family"],
        "task_ids": _panel_evaluation_tasks(method, panel),
        "source_evidence_root": panel_views[str(panel["panel_index"])],
        "next_evidence_root": panel_views[str(next_panel["panel_index"])],
        "accepted_claims": deepcopy(
            state["current_panel_review"]["accepted_claims"]
        ),
        "matched_report_paths": [
            repetitions[str(repetition)]["report_path"] for repetition in (1, 2)
        ],
        "sealed": False,
    }


def _carry_action(
    state: Mapping[str, object], method: Mapping[str, object]
) -> dict[str, object]:
    panel_index = int(state["panel_next_index"])
    panels = _task_panels(method)
    if panel_index >= len(panels) - 1:
        raise GlobalSchedulerError("final panel has no next curriculum evidence view")
    panel = panels[panel_index]
    next_panel = panels[panel_index + 1]
    panel_views = state["trajectory_bank"]["panel_views"]
    return {
        "action_id": (
            f"{state['scheduler_run_id']}-panel-{panel['panel_index']}"
            f"-carry-panel-{next_panel['panel_index']}"
        ),
        "kind": "carry_panel_evidence",
        "purpose": "retained_incumbent_curriculum_handoff",
        "panel_index": panel["panel_index"],
        "family": panel["family"],
        "source_evidence_root": panel_views[str(panel["panel_index"])],
        "next_evidence_root": panel_views[str(next_panel["panel_index"])],
        "sealed": False,
    }


def _sealed_action(
    state: Mapping[str, object], method: Mapping[str, object]
) -> dict[str, object]:
    runs = method["phase2_feedback_sealed_main"]["runs"]
    run = runs[int(state["sealed_next_index"])]
    tasks = [
        value["task_id"]
        for value in _sealed_tasks(method)
        if value["group"] == run["group"]
    ]
    h0_label = method["phase2_feedback_sealed_main"]["comparator"]
    candidate_label = method["phase2_feedback_sealed_main"]["final_candidate"]
    worker_by_label = {
        h0_label: state["frozen_h0"]["worker_dir"],
        candidate_label: state["current_parent"]["worker_dir"],
    }
    arms = [
        {"label": "h0" if label == h0_label else "candidate", "worker_dir": worker_by_label[label]}
        for label in run["arm_order"]
    ]
    run_id = (
        f"{state['scheduler_run_id']}-sealed-r{run['repetition']}"
        f"-group-{run['group']}"
    )
    return {
        "action_id": run_id,
        "kind": "component_pilot",
        "purpose": "feedback_sealed_main",
        "run_id": run_id,
        "repetition": run["repetition"],
        "group": run["group"],
        "task_ids": tasks,
        "arms": arms,
        "seed_worker": state["frozen_h0"]["worker_dir"],
        "require_protocol": True,
        "sealed": True,
    }


def next_action(
    state: Mapping[str, object],
    method: Mapping[str, object],
    launch: Mapping[str, object],
) -> dict[str, object] | None:
    """Return the next fixed child action without changing state."""

    if state["status"] in TERMINAL_STATUSES:
        return None
    phase = state["phase"]
    if phase == "H0_BANK":
        tasks = _development_tasks(method)
        index = int(state["bank_next_index"])
        return _h0_action(state, method, tasks[index]) if index < len(tasks) else None
    if phase == "BUILD_BANK":
        return _bank_action(state, method, launch)
    if phase == "PANELS":
        stage = state["panel_stage"]
        if stage == "PROPOSAL_REVIEW":
            return _panel_action(state, method, launch)
        if stage == "MATCHED_R1":
            return _matched_action(state, method, 1)
        if stage == "MATCHED_R2":
            return _matched_action(state, method, 2)
        if stage == "AUGMENT_NEXT_PANEL":
            return _augment_action(state, method)
        if stage == "CARRY_NEXT_PANEL":
            return _carry_action(state, method)
        return None
    if phase == "SEALED":
        runs = method["phase2_feedback_sealed_main"]["runs"]
        if int(state["sealed_next_index"]) < len(runs):
            return _sealed_action(state, method)
    return None


def _component_scores(
    action: Mapping[str, object], result: Mapping[str, object]
) -> dict[str, dict[str, float]]:
    if result.get("status") != "complete":
        raise GlobalSchedulerError(
            f"component child {action['action_id']} did not complete validly"
        )
    if result.get("task_ids") != action.get("task_ids"):
        raise GlobalSchedulerError(
            f"component child {action['action_id']} returned a different task vector"
        )
    arms = action["arms"]
    labels = [value["label"] for value in arms]
    summaries = result.get("summaries")
    executions = result.get("worker_executions")
    protocol = result.get("scheduler_protocol")
    if not isinstance(summaries, Mapping) or set(summaries) != set(labels):
        raise GlobalSchedulerError("component child has incomplete arm summaries")
    if not isinstance(executions, Mapping) or set(executions) != set(labels):
        raise GlobalSchedulerError("component child has incomplete Worker executions")
    if not isinstance(protocol, Mapping) or set(protocol) != set(labels):
        raise GlobalSchedulerError("component child has no complete protocol audit")
    scores: dict[str, dict[str, float]] = {}
    expected_tasks = list(action["task_ids"])
    for label in labels:
        execution = executions[label]
        if not isinstance(execution, Mapping) or execution.get("valid_for_selection") is not True:
            raise GlobalSchedulerError(f"component arm {label} is invalid for selection")
        arm_protocol = protocol[label]
        if not isinstance(arm_protocol, Mapping) or set(arm_protocol) != set(expected_tasks):
            raise GlobalSchedulerError(f"component arm {label} has incomplete protocol tasks")
        if not all(value is True for value in arm_protocol.values()):
            raise GlobalSchedulerError(f"component arm {label} failed S1-S6 protocol")
        summary = summaries[label]
        rewards = summary.get("task_rewards") if isinstance(summary, Mapping) else None
        if not isinstance(rewards, Mapping) or set(rewards) != set(expected_tasks):
            raise GlobalSchedulerError(f"component arm {label} has incomplete rewards")
        arm_scores: dict[str, float] = {}
        for task in expected_tasks:
            raw_reward = rewards[task]
            if isinstance(raw_reward, bool) or not isinstance(
                raw_reward, (int, float)
            ):
                raise GlobalSchedulerError(
                    f"component reward must be numeric for {label}/{task}"
                )
            reward = float(raw_reward)
            if not isfinite(reward):
                raise GlobalSchedulerError(
                    f"component reward is non-finite for {label}/{task}"
                )
            if reward not in {0.0, 1.0}:
                raise GlobalSchedulerError(
                    "component reward must be exact binary 0.0 or 1.0 for "
                    f"{label}/{task}"
                )
            arm_scores[task] = reward
        scores[label] = arm_scores
    return scores


def _component_property_counts(
    action: Mapping[str, object], result: Mapping[str, object]
) -> dict[str, dict[str, dict[str, object]]]:
    """Retain passed/total counts as a secondary controller-only metric."""

    summaries = result.get("summaries")
    if not isinstance(summaries, Mapping):
        return {}
    task_ids = set(str(value) for value in action["task_ids"])
    output: dict[str, dict[str, dict[str, object]]] = {}
    for arm in action["arms"]:
        label = str(arm["label"])
        summary = summaries.get(label)
        rows = summary.get("scores") if isinstance(summary, Mapping) else None
        if not isinstance(rows, list):
            continue
        arm_counts: dict[str, dict[str, object]] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            task_id = row.get("task_id")
            passed = row.get("tests_passed")
            failed = row.get("tests_failed")
            if (
                not isinstance(task_id, str)
                or task_id not in task_ids
                or isinstance(passed, bool)
                or not isinstance(passed, int)
                or isinstance(failed, bool)
                or not isinstance(failed, int)
                or passed < 0
                or failed < 0
                or task_id in arm_counts
            ):
                continue
            total = passed + failed
            arm_counts[task_id] = {
                "passed": passed,
                "failed": failed,
                "total": total,
                "completion": (passed / total if total > 0 else None),
            }
        if arm_counts:
            output[label] = arm_counts
    return output


def _sealed_metric_summary(
    state: Mapping[str, object], method: Mapping[str, object]
) -> dict[str, object]:
    tasks = _sealed_tasks(method)
    task_domains = {str(value["task_id"]): str(value["domain"]) for value in tasks}
    reward_rows: dict[str, dict[str, list[float]]] = {
        task_id: {"h0": [], "candidate": []} for task_id in task_domains
    }
    property_rows: dict[str, dict[str, list[dict[str, object]]]] = {
        task_id: {"h0": [], "candidate": []} for task_id in task_domains
    }
    for result in state["sealed_results"]:
        scores = result["scores"]
        counts = result.get("property_counts", {})
        for arm in ("h0", "candidate"):
            for task_id, reward in scores[arm].items():
                reward_rows[task_id][arm].append(float(reward))
                arm_counts = counts.get(arm) if isinstance(counts, Mapping) else None
                count = arm_counts.get(task_id) if isinstance(arm_counts, Mapping) else None
                if isinstance(count, Mapping):
                    property_rows[task_id][arm].append(deepcopy(dict(count)))
    per_task: list[dict[str, object]] = []
    domain_values: dict[str, dict[str, list[float]]] = {}
    for task_id in sorted(task_domains):
        h0 = reward_rows[task_id]["h0"]
        candidate = reward_rows[task_id]["candidate"]
        if len(h0) != 2 or len(candidate) != 2:
            raise GlobalSchedulerError(
                f"sealed task does not have two paired repetitions: {task_id}"
            )
        h0_mean = sum(h0) / 2
        candidate_mean = sum(candidate) / 2
        deltas = [candidate[index] - h0[index] for index in range(2)]
        domain = task_domains[task_id]
        bucket = domain_values.setdefault(domain, {"h0": [], "candidate": []})
        bucket["h0"].append(h0_mean)
        bucket["candidate"].append(candidate_mean)
        per_task.append(
            {
                "task_id": task_id,
                "domain": domain,
                "h0_repetitions": h0,
                "candidate_repetitions": candidate,
                "h0_mean": h0_mean,
                "candidate_mean": candidate_mean,
                "paired_deltas": deltas,
                "mean_delta": candidate_mean - h0_mean,
                "stable_win": all(value > 0 for value in deltas),
                "any_regression": any(value < 0 for value in deltas),
                "property_counts": property_rows[task_id],
            }
        )
    domain_macro_rows: list[dict[str, object]] = []
    for domain in sorted(domain_values):
        values = domain_values[domain]
        h0_mean = sum(values["h0"]) / len(values["h0"])
        candidate_mean = sum(values["candidate"]) / len(values["candidate"])
        domain_macro_rows.append(
            {
                "domain": domain,
                "task_count": len(values["h0"]),
                "h0_task_mean": h0_mean,
                "candidate_task_mean": candidate_mean,
                "delta": candidate_mean - h0_mean,
            }
        )
    h0_task_mean = sum(value["h0_mean"] for value in per_task) / len(per_task)
    candidate_task_mean = (
        sum(value["candidate_mean"] for value in per_task) / len(per_task)
    )
    h0_domain_macro = (
        sum(value["h0_task_mean"] for value in domain_macro_rows)
        / len(domain_macro_rows)
    )
    candidate_domain_macro = (
        sum(value["candidate_task_mean"] for value in domain_macro_rows)
        / len(domain_macro_rows)
    )
    paired_deltas = [
        delta for value in per_task for delta in value["paired_deltas"]
    ]
    task_mean_deltas = [value["mean_delta"] for value in per_task]
    return {
        "schema_version": 1,
        "primary_metric": "official_binary_task_reward",
        "task_count": len(per_task),
        "repetitions": 2,
        "h0_task_mean": h0_task_mean,
        "candidate_task_mean": candidate_task_mean,
        "task_mean_delta": candidate_task_mean - h0_task_mean,
        "h0_equal_domain_macro": h0_domain_macro,
        "candidate_equal_domain_macro": candidate_domain_macro,
        "equal_domain_macro_delta": candidate_domain_macro - h0_domain_macro,
        "paired_repetition_wtl": {
            "win": sum(value > 0 for value in paired_deltas),
            "tie": sum(value == 0 for value in paired_deltas),
            "loss": sum(value < 0 for value in paired_deltas),
            "pair_count": len(paired_deltas),
        },
        "task_mean_wtl": {
            "win": sum(value > 0 for value in task_mean_deltas),
            "tie": sum(value == 0 for value in task_mean_deltas),
            "loss": sum(value < 0 for value in task_mean_deltas),
            "task_count": len(task_mean_deltas),
        },
        "balanced_design_note": (
            "Each family has exactly two sealed tasks, so the equal-task mean "
            "and equal-family macro are numerically identical by construction."
        ),
        "stable_win_count": sum(bool(value["stable_win"]) for value in per_task),
        "any_regression_count": sum(
            bool(value["any_regression"]) for value in per_task
        ),
        "per_task": per_task,
        "per_domain": domain_macro_rows,
        "secondary_metric": "official_passed_over_total_when_reported",
    }


def _account_once(
    state: dict[str, object], action: Mapping[str, object], result: Mapping[str, object]
) -> None:
    action_id = str(action["action_id"])
    if action_id in state["accounted_action_ids"]:
        return
    if result.get("accounting_complete") is not True:
        raise GlobalSchedulerError(
            f"child accounting is incomplete: {action['action_id']}"
        )
    cost = _normalized_cost(result.get("cost"))
    _add_cost(state["cost"], cost)
    state["accounted_action_ids"].append(action_id)
    if action.get("kind") == "component_pilot":
        state["qfbench_cells_accounted"] = int(
            state["qfbench_cells_accounted"]
        ) + len(action["task_ids"]) * len(action["arms"])


def _caps_ok(
    state: Mapping[str, object], method: Mapping[str, object]
) -> tuple[bool, str | None]:
    limits = method["limits"]
    if int(state["cost"]["total_tokens"]) > int(limits["maximum_total_tokens"]):
        return False, "maximum_total_tokens"
    if Decimal(str(state["cost"]["provider_cost_usd"])) > Decimal(
        str(limits["maximum_provider_cost_usd"])
    ):
        return False, "maximum_provider_cost_usd"
    if int(state["qfbench_cells_accounted"]) > int(
        limits["maximum_qfbench_sessions_including_recovery"]
    ):
        return False, "maximum_qfbench_sessions_including_recovery"
    return True, None


def _review_candidate(result: Mapping[str, object]) -> dict[str, object] | None:
    if result.get("review_verdict") != "PASS":
        return None
    if result.get("coverage") != "PASS":
        return None
    candidate = result.get("candidate")
    if not isinstance(candidate, Mapping):
        raise GlobalSchedulerError("Review PASS has no candidate")
    version = candidate.get("version")
    worker_dir = candidate.get("worker_dir")
    if not isinstance(version, str) or not version:
        raise GlobalSchedulerError("Review PASS candidate has no version")
    if not isinstance(worker_dir, str) or not Path(worker_dir).is_dir():
        raise GlobalSchedulerError("Review PASS candidate Worker is unavailable")
    return {"version": version, "worker_dir": str(Path(worker_dir).resolve())}


def _accepted_claims(result: Mapping[str, object]) -> list[dict[str, object]]:
    raw = result.get("accepted_claims")
    if not isinstance(raw, list) or not raw:
        raise GlobalSchedulerError("Review PASS has no accepted claim inventory")
    claims: list[dict[str, object]] = []
    seen: set[str] = set()
    for value in raw:
        if not isinstance(value, Mapping):
            raise GlobalSchedulerError("accepted claim must be an object")
        claim_id = value.get("claim_id")
        claim = value.get("claim")
        surfaces = value.get("surfaces")
        basis_refs = value.get("basis_refs")
        safe_sources = value.get("safe_sources")
        if (
            not isinstance(claim_id, str)
            or not claim_id
            or claim_id in seen
            or not isinstance(claim, str)
            or not claim
            or not isinstance(surfaces, list)
            or not surfaces
            or not isinstance(basis_refs, list)
            or not basis_refs
            or not isinstance(safe_sources, list)
            or not safe_sources
        ):
            raise GlobalSchedulerError("accepted claim inventory is incomplete")
        seen.add(claim_id)
        claims.append(
            {
                "claim_id": claim_id,
                "claim_scope": value.get(
                    "claim_scope", "task_specific_requirement"
                ),
                "claim": claim,
                "surfaces": list(surfaces),
                "basis_refs": list(basis_refs),
                "safe_sources": deepcopy(list(safe_sources)),
            }
        )
    return claims


def _panel_decision(
    state: Mapping[str, object], method: Mapping[str, object]
) -> dict[str, object]:
    panel = _task_panels(method)[int(state["panel_next_index"])]
    focus_tasks = list(panel["task_ids"])
    anchor_tasks = _panel_anchor_tasks(method, panel)
    evaluated_tasks = _panel_evaluation_tasks(method, panel)
    repetitions = state["current_panel_repetitions"]
    if set(repetitions) != {"1", "2"}:
        raise GlobalSchedulerError("panel does not have two matched repetitions")
    repeated_focus_wins: set[str] | None = None
    vectors: list[dict[str, object]] = []
    for repetition in (1, 2):
        scores = repetitions[str(repetition)]["scores"]
        parent = scores["parent"]
        candidate = scores["candidate"]
        if set(parent) != set(evaluated_tasks) or set(candidate) != set(
            evaluated_tasks
        ):
            raise GlobalSchedulerError(
                "panel fitness result differs from focus-plus-anchor task vector"
            )
        regressions = [
            task for task in evaluated_tasks if candidate[task] < parent[task]
        ]
        focus_wins = {
            task for task in focus_tasks if candidate[task] > parent[task]
        }
        anchor_wins = {
            task for task in anchor_tasks if candidate[task] > parent[task]
        }
        focus_parent_mean = sum(parent[task] for task in focus_tasks) / len(
            focus_tasks
        )
        focus_candidate_mean = sum(candidate[task] for task in focus_tasks) / len(
            focus_tasks
        )
        vectors.append(
            {
                "repetition": repetition,
                "parent": parent,
                "candidate": candidate,
                "focus_parent_mean": focus_parent_mean,
                "focus_candidate_mean": focus_candidate_mean,
                "focus_wins": sorted(focus_wins),
                "anchor_wins": sorted(anchor_wins),
                "regressions": regressions,
                "anchor_regressions": [
                    task for task in regressions if task in anchor_tasks
                ],
            }
        )
        if regressions or focus_candidate_mean <= focus_parent_mean:
            return {
                "decision": "RETAIN_NO_STABLE_GAIN",
                "reason": "regression_or_no_strict_focus_mean_gain",
                "focus_task_ids": focus_tasks,
                "anchor_task_ids": anchor_tasks,
                "vectors": vectors,
            }
        repeated_focus_wins = (
            focus_wins
            if repeated_focus_wins is None
            else repeated_focus_wins.intersection(focus_wins)
        )
    if not repeated_focus_wins:
        return {
            "decision": "RETAIN_NO_STABLE_GAIN",
            "reason": "no_repeated_focus_task_win",
            "focus_task_ids": focus_tasks,
            "anchor_task_ids": anchor_tasks,
            "vectors": vectors,
        }
    return {
        "decision": "PROMOTE",
        "repeated_focus_wins": sorted(repeated_focus_wins),
        "focus_task_ids": focus_tasks,
        "anchor_task_ids": anchor_tasks,
        "vectors": vectors,
    }


def _finish_panel(
    state: dict[str, object],
    method: Mapping[str, object],
    *,
    promoted: bool,
) -> None:
    """Advance after a scientific panel outcome without treating it as infra failure."""

    panel_index = int(state["panel_next_index"])
    panel = _task_panels(method)[panel_index]
    if int(panel["panel_index"]) in {2, 4, 6}:
        state["checkpoints"].append(
            {
                "after_panel": panel["panel_index"],
                "parent": deepcopy(state["current_parent"]),
                "kind": "retained_incumbent_checkpoint",
                "panel_decision": state["panel_results"][-1]["decision"],
            }
        )
    if panel_index == len(_task_panels(method)) - 1:
        state["panel_next_index"] = panel_index + 1
        state["current_panel_review"] = None
        state["current_panel_repetitions"] = {}
        state["phase"] = "SEALED"
        state["panel_stage"] = None
    else:
        state["panel_stage"] = (
            "AUGMENT_NEXT_PANEL" if promoted else "CARRY_NEXT_PANEL"
        )


def import_action_result(
    state: dict[str, object],
    method: Mapping[str, object],
    launch: Mapping[str, object],
    action: Mapping[str, object],
    result: Mapping[str, object],
) -> None:
    """Import one terminal child exactly once and advance the state machine."""

    action_id = str(action["action_id"])
    already_accounted = action_id in state["accounted_action_ids"]
    if already_accounted:
        return
    kind = action["kind"]
    if kind == "component_pilot":
        scores = _component_scores(action, result)
        _account_once(state, action, result)
        if action["purpose"] == "h0_bank":
            task_id = action["task_ids"][0]
            state["bank_results"][task_id] = {
                "action_id": action_id,
                "report_path": result.get("report_path"),
                "scores": scores,
            }
            state["bank_next_index"] = int(state["bank_next_index"]) + 1
            if int(state["bank_next_index"]) == len(_development_tasks(method)):
                state["phase"] = "BUILD_BANK"
        elif action["purpose"] == "panel_matched_fitness":
            repetition = str(action["repetition"])
            state["current_panel_repetitions"][repetition] = {
                "action_id": action_id,
                "report_path": result.get("report_path"),
                "scores": scores,
                "property_counts": _component_property_counts(action, result),
            }
            if repetition == "1":
                state["panel_stage"] = "MATCHED_R2"
            else:
                decision = _panel_decision(state, method)
                panel = _task_panels(method)[int(state["panel_next_index"])]
                decision.update(
                    {
                        "panel_index": panel["panel_index"],
                        "family": panel["family"],
                        "parent": deepcopy(state["current_parent"]),
                        "candidate": deepcopy(state["current_panel_review"]["candidate"]),
                    }
                )
                state["panel_results"].append(decision)
                if decision["decision"] == "PROMOTE":
                    state["current_parent"] = deepcopy(decision["candidate"])
                    _finish_panel(state, method, promoted=True)
                else:
                    _finish_panel(state, method, promoted=False)
        elif action["purpose"] == "feedback_sealed_main":
            state["sealed_results"].append(
                {
                    "action_id": action_id,
                    "repetition": action["repetition"],
                    "group": action["group"],
                    "report_path": result.get("report_path"),
                    "scores": scores,
                    "property_counts": _component_property_counts(action, result),
                }
            )
            state["sealed_next_index"] = int(state["sealed_next_index"]) + 1
            runs = method["phase2_feedback_sealed_main"]["runs"]
            if int(state["sealed_next_index"]) == len(runs):
                state["sealed_summary"] = _sealed_metric_summary(state, method)
                state["phase"] = "TERMINAL"
                state["status"] = "COMPLETE"
    elif kind == "build_trajectory_bank":
        if result.get("status") != "complete":
            raise GlobalSchedulerError("trajectory bank builder did not complete")
        indexed = result.get("indexed_task_ids")
        if indexed != action["task_ids"]:
            raise GlobalSchedulerError("trajectory bank task index is incomplete")
        if result.get("sealed_task_ids_present") not in ([], None):
            raise GlobalSchedulerError("sealed task entered trajectory bank")
        panel_views = result.get("panel_views")
        if not isinstance(panel_views, Mapping):
            raise GlobalSchedulerError("trajectory bank has no panel views")
        state["trajectory_bank"] = {
            "output_root": action["output_root"],
            "panel_views": deepcopy(dict(panel_views)),
        }
        _account_once(state, action, result)
        state["phase"] = "PANELS"
    elif kind == "panel_proposal_review":
        _account_once(state, action, result)
        if result.get("engineering_invalid") is not None:
            if (
                result.get("engineering_invalid") != "review_package_invalid"
                or result.get("review_verdict") != "NOT_RUN"
                or result.get("coverage") != "NOT_RUN"
                or result.get("candidate") is None
            ):
                raise GlobalSchedulerError(
                    "panel Review engineering-invalid result is inconsistent"
                )
            raise GlobalSchedulerError("STOP_PANEL_REVIEW_PACKAGE_INVALID")
        candidate = _review_candidate(result)
        if candidate is None:
            proposal_decision = result.get("proposal_decision")
            verdict = result.get("review_verdict")
            coverage = result.get("coverage")
            if proposal_decision == "ABSTAIN":
                if verdict != "NOT_RUN" or coverage != "NOT_RUN":
                    raise GlobalSchedulerError(
                        "proposal ABSTAIN cannot have a candidate Review verdict"
                    )
                panel = _task_panels(method)[int(state["panel_next_index"])]
                state["panel_results"].append(
                    {
                        "decision": "RETAIN_PROPOSAL_ABSTAIN",
                        "panel_index": panel["panel_index"],
                        "family": panel["family"],
                        "parent": deepcopy(state["current_parent"]),
                        "review_verdict": "NOT_RUN",
                        "coverage": "NOT_RUN",
                        "review_result_path": None,
                    }
                )
                state["current_panel_review"] = None
                state["current_panel_repetitions"] = {}
                _finish_panel(state, method, promoted=False)
            elif verdict not in {"REJECT", "INCONCLUSIVE"} and not (
                verdict == "PASS" and coverage in {"REJECT", "INCONCLUSIVE"}
            ):
                raise GlobalSchedulerError(
                    "candidate Review returned no valid terminal verdict"
                )
            else:
                panel = _task_panels(method)[int(state["panel_next_index"])]
                state["panel_results"].append(
                    {
                        "decision": "RETAIN_REVIEW_NONPASS",
                        "panel_index": panel["panel_index"],
                        "family": panel["family"],
                        "parent": deepcopy(state["current_parent"]),
                        "review_verdict": verdict,
                        "coverage": coverage,
                        "review_result_path": result.get("review_result_path"),
                    }
                )
                state["current_panel_review"] = None
                state["current_panel_repetitions"] = {}
                _finish_panel(state, method, promoted=False)
        else:
            if candidate["version"] != action["proposal_version"]:
                raise GlobalSchedulerError("panel Review returned a different proposal version")
            expected_parent = action["current_parent"]
            if result.get("reviewed_parent") != expected_parent:
                raise GlobalSchedulerError("panel Review used a different parent")
            adapter = state["frozen_h0"].get("adapter_contract")
            mutation_surfaces = (
                adapter.get("mutation_surfaces")
                if isinstance(adapter, Mapping)
                else None
            )
            if not isinstance(mutation_surfaces, list) or not mutation_surfaces:
                raise GlobalSchedulerError(
                    "frozen H0 handoff has no admitted mutation surfaces"
                )
            boundary = inspect_qrs_candidate_boundary(
                frozen_h0_worker=state["frozen_h0"]["worker_dir"],
                reviewed_candidate=candidate["worker_dir"],
                allowed_mutation_surfaces=mutation_surfaces,
                development_task_ids=_development_tasks(method),
                sealed_task_ids=[
                    str(value["task_id"]) for value in _sealed_tasks(method)
                ],
                development_family_labels=_development_families(method),
                sealed_family_labels=_sealed_families(method),
            )
            if boundary.get("verdict") != "PASS":
                raise GlobalSchedulerError(
                    "reviewed candidate violates the QRS mutation boundary"
                )
            state["current_panel_review"] = {
                "action_id": action_id,
                "candidate": candidate,
                "review_result_path": result.get("review_result_path"),
                "accepted_claims": _accepted_claims(result),
                "candidate_boundary": boundary,
            }
            state["panel_stage"] = "MATCHED_R1"
    elif kind == "augment_panel_evidence":
        if result.get("status") != "complete" or result.get("answer_free") is not True:
            raise GlobalSchedulerError("accepted panel evidence handoff did not complete")
        if result.get("panel_index") != action.get("panel_index"):
            raise GlobalSchedulerError("accepted panel evidence has a different panel")
        if result.get("next_evidence_root") != action.get("next_evidence_root"):
            raise GlobalSchedulerError("accepted panel evidence has a different target")
        if result.get("sealed_task_ids_present") not in ([], None):
            raise GlobalSchedulerError("sealed task entered accepted panel history")
        _account_once(state, action, result)
        state["curriculum_handoffs"].append(
            {
                "action_id": action_id,
                "panel_index": action["panel_index"],
                "next_evidence_root": action["next_evidence_root"],
                "accepted_claim_count": result.get("accepted_claim_count"),
                "matched_repetition_count": result.get("matched_repetition_count"),
            }
        )
        state["panel_next_index"] = int(state["panel_next_index"]) + 1
        state["current_panel_review"] = None
        state["current_panel_repetitions"] = {}
        state["panel_stage"] = "PROPOSAL_REVIEW"
    elif kind == "carry_panel_evidence":
        if result.get("status") != "complete" or result.get("answer_free") is not True:
            raise GlobalSchedulerError("retained panel evidence handoff did not complete")
        if result.get("next_evidence_root") != action.get("next_evidence_root"):
            raise GlobalSchedulerError("retained panel evidence has a different target")
        if result.get("sealed_task_ids_present") not in ([], None):
            raise GlobalSchedulerError("sealed task entered retained panel history")
        _account_once(state, action, result)
        state["curriculum_handoffs"].append(
            {
                "action_id": action_id,
                "panel_index": action["panel_index"],
                "next_evidence_root": action["next_evidence_root"],
                "kind": "retained_incumbent_history_carry",
                "carried_entry_count": result.get("carried_entry_count"),
            }
        )
        state["panel_next_index"] = int(state["panel_next_index"]) + 1
        state["current_panel_review"] = None
        state["current_panel_repetitions"] = {}
        state["panel_stage"] = "PROPOSAL_REVIEW"
    else:
        raise GlobalSchedulerError(f"unsupported scheduler action kind: {kind}")

    if state["status"] == "RUNNING":
        caps_ok, cap = _caps_ok(state, method)
        if not caps_ok:
            _stop(state, "STOP_CAP", f"hard cap exceeded: {cap}")


def run_scheduler(
    method_plan: str | Path,
    launch_plan: str | Path,
    state_dir: str | Path,
    *,
    action_runner: ActionRunner,
    stop_after_phase: str | None = None,
    stop_after_panel: int | None = None,
) -> dict[str, object]:
    """Run or resume the scheduler until terminal or an explicit phase pause."""

    method = _json(method_plan)
    launch = _json(launch_plan)
    _validate_method(method)
    _validate_launch(launch, method)
    if stop_after_panel is not None and (
        isinstance(stop_after_panel, bool)
        or not isinstance(stop_after_panel, int)
        or stop_after_panel < 1
        or stop_after_panel > len(_task_panels(method))
    ):
        raise GlobalSchedulerError("stop_after_panel is outside the panel schedule")
    if Path(str(launch["method_plan_path"])).expanduser().resolve() != Path(
        method_plan
    ).expanduser().resolve():
        raise GlobalSchedulerError(
            "launch method_plan_path differs from scheduler method input"
        )
    root = Path(state_dir)
    state_path = root / "scheduler-state.json"
    result_path = root / "SCHEDULER-RESULT.json"
    if state_path.is_file():
        state = _json(state_path)
        if state.get("scheduler_run_id") != launch.get("scheduler_run_id"):
            raise GlobalSchedulerError("state belongs to a different scheduler run")
        if state.get("method_input") != method or state.get("launch_input") != launch:
            raise GlobalSchedulerError(
                "method or launch input changed after scheduler initialization"
            )
        state.pop("stopped_after_phase", None)
        state.pop("stopped_after_panel", None)
    else:
        state = new_scheduler_state(method, launch)
        _write_json(state_path, state)

    if state["phase"] == "IMPORT_H0" and state["status"] == "RUNNING":
        _import_handoff(state, launch)
        _write_json(state_path, state)
        if stop_after_phase == "IMPORT_H0" and state["status"] == "RUNNING":
            state["stopped_after_phase"] = "IMPORT_H0"

    if (
        stop_after_panel is not None
        and state["status"] == "RUNNING"
        and len(state["panel_results"]) >= stop_after_panel
        and (
            state["phase"] != "PANELS"
            or int(state["panel_next_index"]) >= stop_after_panel
        )
    ):
        state["stopped_after_panel"] = stop_after_panel

    while state["status"] == "RUNNING":
        if (
            state.get("stopped_after_phase") is not None
            or state.get("stopped_after_panel") is not None
        ):
            break
        phase = str(state["phase"])
        action = next_action(state, method, launch)
        if action is None:
            if phase == "H0_BANK" and int(state["bank_next_index"]) == len(
                _development_tasks(method)
            ):
                state["phase"] = "BUILD_BANK"
                continue
            raise GlobalSchedulerError(f"phase {phase} has no next action")
        try:
            result = action_runner(action)
            if not isinstance(result, Mapping):
                raise GlobalSchedulerError(
                    f"action {action['action_id']} returned no JSON object"
                )
            import_action_result(state, method, launch, action, result)
        except GlobalSchedulerError as exc:
            status = {
                "H0_BANK": "STOP_BANK",
                "BUILD_BANK": "STOP_BANK",
                "PANELS": "STOP_PANEL",
                "SEALED": "STOP_MAIN",
            }.get(phase, "STOP_MAIN")
            _stop(state, status, str(exc))
        if (
            stop_after_phase == phase
            and state["status"] == "RUNNING"
            and state["phase"] != phase
        ):
            state["stopped_after_phase"] = phase
        if (
            stop_after_panel is not None
            and state["status"] == "RUNNING"
            and len(state["panel_results"]) >= stop_after_panel
            and (
                state["phase"] != "PANELS"
                or int(state["panel_next_index"]) >= stop_after_panel
            )
        ):
            state["stopped_after_panel"] = stop_after_panel
        _write_json(state_path, state)

    _write_json(state_path, state)
    _write_json(result_path, state)
    return state
