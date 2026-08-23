#!/usr/bin/env python3
"""Run a deterministic sequence of QFBench lineage-controller children."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Callable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.qfbench_lineage import LineageError  # noqa: E402
from scripts.run_qfbench_lineage_controller import run_controller  # noqa: E402


ChildController = Callable[..., dict[str, object]]
TERMINAL_CHILD_PHASES = frozenset({"FROZEN", "HOLD_FOR_REFINE", "BUDGET_STOP"})


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise LineageError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _reference_key(stage_name: str, task_id: str) -> str:
    return f"{stage_name}::{task_id}"


def _reference_map(
    values: object, *, incumbent_version: str
) -> dict[str, dict[str, object]]:
    if not isinstance(values, list) or not values:
        raise LineageError("arm has no initial_selection_references")
    result: dict[str, dict[str, object]] = {}
    for value in values:
        if not isinstance(value, Mapping):
            raise LineageError("selection reference must be a JSON object")
        task_id = value.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise LineageError("selection reference has no task_id")
        stage_name = value.get("stage", value.get("name"))
        key = task_id
        if isinstance(stage_name, str) and stage_name:
            key = _reference_key(stage_name, task_id)
        reference = dict(value)
        reference.setdefault("reference_version", incumbent_version)
        result[key] = reference
    return result


def _new_state(
    plan: Mapping[str, object],
    *,
    selected_arms: frozenset[str] | None = None,
) -> dict[str, object]:
    arms = plan.get("arms")
    if not isinstance(arms, list) or not arms:
        raise LineageError("campaign plan has no arms")
    arm_states: dict[str, object] = {}
    for arm in arms:
        if not isinstance(arm, Mapping):
            raise LineageError("campaign arm must be a JSON object")
        arm_id = arm.get("arm_id")
        incumbent = arm.get("initial_incumbent")
        rounds = arm.get("rounds")
        if not isinstance(arm_id, str) or not arm_id:
            raise LineageError("campaign arm has no arm_id")
        if selected_arms is not None and arm_id not in selected_arms:
            continue
        if arm_id in arm_states:
            raise LineageError(f"duplicate campaign arm {arm_id!r}")
        if not isinstance(incumbent, Mapping):
            raise LineageError(f"arm {arm_id!r} has no initial_incumbent")
        if not isinstance(rounds, list) or not rounds:
            raise LineageError(f"arm {arm_id!r} has no rounds")
        arm_states[arm_id] = {
            "status": "RUNNING",
            "next_round_index": 0,
            "current_incumbent": dict(incumbent),
            "mutation_parent": dict(incumbent),
            "selection_references": _reference_map(
                arm.get("initial_selection_references"),
                incumbent_version=str(incumbent["version"]),
            ),
            "pending_hold": None,
            "refinement_used": False,
            "round_results": [],
        }
    if not arm_states:
        raise LineageError("campaign selection has no matching arms")
    return {
        "schema_version": 1,
        "campaign_run_id": plan.get("campaign_run_id"),
        "status": "RUNNING",
        "arms": arm_states,
    }


def _arm_plan(
    plan: Mapping[str, object], arm_id: str
) -> Mapping[str, object]:
    arms = plan.get("arms")
    if not isinstance(arms, list):
        raise LineageError("campaign plan has no arms")
    matches = [arm for arm in arms if arm.get("arm_id") == arm_id]
    if len(matches) != 1:
        raise LineageError(f"campaign has no unique arm {arm_id!r}")
    return matches[0]


def _fixed_run_id(
    campaign_run_id: str, arm_id: str, round_id: str
) -> str:
    return f"{campaign_run_id}-{arm_id}-{round_id}"


def _build_child_plan(
    plan: Mapping[str, object],
    *,
    arm_id: str,
    arm_state: Mapping[str, object],
    round_spec: Mapping[str, object],
) -> dict[str, object]:
    campaign_run_id = str(plan["campaign_run_id"])
    round_id = str(round_spec["round_id"])
    controller_run_id = _fixed_run_id(campaign_run_id, arm_id, round_id)
    lineage_source = round_spec.get("lineage")
    if not isinstance(lineage_source, Mapping):
        raise LineageError(f"round {round_id!r} has no lineage")
    lineage = deepcopy(dict(lineage_source))
    lineage["lineage_id"] = f"{arm_id}-{round_id}"
    lineage["parent"] = deepcopy(dict(arm_state["mutation_parent"]))

    proposal = lineage.get("proposal")
    if isinstance(proposal, Mapping):
        proposal = deepcopy(dict(proposal))
        proposal["live_run_id"] = f"{controller_run_id}-proposal"
        lineage["proposal"] = proposal

    references = arm_state["selection_references"]
    stages = lineage.get("stages")
    if not isinstance(stages, list):
        raise LineageError(f"round {round_id!r} has no stages")
    prepared_stages: list[dict[str, object]] = []
    for source in stages:
        if not isinstance(source, Mapping):
            raise LineageError("lineage stage must be a JSON object")
        stage = deepcopy(dict(source))
        stage_name = str(stage["name"])
        task_id = str(stage["task_id"])
        stage["live_run_id"] = f"{controller_run_id}-{stage_name}"
        stage["checkpoint_prefix"] = stage["live_run_id"]
        reference = references.get(_reference_key(stage_name, task_id))
        if not isinstance(reference, Mapping):
            reference = references.get(task_id)
        incumbent_version = str(arm_state["current_incumbent"]["version"])
        if (
            isinstance(reference, Mapping)
            and reference.get("reference_version") == incumbent_version
        ):
            stage["parent_arm"] = str(reference["arm"])
            stage["selection_reference"] = {
                "id": str(reference["id"]),
                "report_path": str(reference["report_path"]),
                "reference_version": incumbent_version,
                "task_id": task_id,
                "worker_route": str(plan["runtime"]["worker_route"]),
                "worker_budget": "normal",
            }
            stage.pop("parent_comparator", None)
        else:
            stage["parent_arm"] = "parent"
            stage.pop("selection_reference", None)
            stage.pop("parent_comparator", None)
        prepared_stages.append(stage)
    lineage["stages"] = prepared_stages
    return {
        "schema_version": 1,
        "controller_run_id": controller_run_id,
        "mode": plan.get("mode", "live"),
        "runtime": deepcopy(dict(plan["runtime"])),
        "limits": deepcopy(dict(plan.get("limits", {}))),
        "lineages": [lineage],
    }


def _child_lineage(
    result: Mapping[str, object], lineage_id: str
) -> dict[str, object]:
    lineages = result.get("lineages")
    if not isinstance(lineages, Mapping):
        raise LineageError("child controller returned no lineages")
    child = lineages.get(lineage_id)
    if not isinstance(child, Mapping):
        raise LineageError(f"child controller returned no {lineage_id!r}")
    if child.get("phase") not in TERMINAL_CHILD_PHASES:
        raise LineageError(
            f"child {lineage_id!r} is not terminal: {child.get('phase')}"
        )
    return dict(child)


def _promoted_references(
    child: Mapping[str, object],
    stages: list[Mapping[str, object]],
    *,
    reference_version: str,
) -> dict[str, dict[str, object]]:
    observations = child.get("observations")
    if not isinstance(observations, Mapping):
        raise LineageError("promoted child has no observations")
    result: dict[str, dict[str, object]] = {}
    # Stage order intentionally makes repeat supersede target for one task.
    for stage in stages:
        name = str(stage["name"])
        observation = observations.get(name)
        if not isinstance(observation, Mapping):
            continue
        task_id = str(observation["task_id"])
        result[_reference_key(name, task_id)] = {
            "stage": name,
            "task_id": task_id,
            "id": str(observation["run_id"]),
            "report_path": str(observation["report_path"]),
            "arm": str(stage["candidate_arm"]),
            "reference_version": reference_version,
        }
    if not result:
        raise LineageError("promoted child has no reusable task observations")
    return result


def _candidate_parent(candidate: Mapping[str, object]) -> dict[str, object]:
    parent = {
        "version": candidate["version"],
        "worker_dir": candidate["worker_dir"],
    }
    activation_token = candidate.get("activation_token")
    if isinstance(activation_token, str) and activation_token:
        parent["retained_activation_token"] = activation_token
    return parent


def _apply_terminal_child(
    arm_state: dict[str, object],
    *,
    round_spec: Mapping[str, object],
    child_plan: Mapping[str, object],
    child: Mapping[str, object],
    child_plan_path: Path,
    child_state_dir: Path,
) -> None:
    decision = str(child.get("decision"))
    round_id = str(round_spec["round_id"])
    lineage = child_plan["lineages"][0]
    arm_state["round_results"].append(
        {
            "round_id": round_id,
            "kind": round_spec.get("kind", "candidate"),
            "decision": decision,
            "child_plan_path": str(child_plan_path),
            "child_state_dir": str(child_state_dir),
            "child_controller_run_id": child_plan["controller_run_id"],
            "child_lineage_id": lineage["lineage_id"],
        }
    )
    arm_state["next_round_index"] += 1
    arm_state["pending_hold"] = None

    if decision == "PROMOTE":
        candidate = child.get("candidate")
        if not isinstance(candidate, Mapping):
            raise LineageError("promoted child has no candidate")
        incumbent = _candidate_parent(candidate)
        arm_state["current_incumbent"] = incumbent
        arm_state["mutation_parent"] = deepcopy(incumbent)
        arm_state["selection_references"].update(
            _promoted_references(
                child,
                lineage["stages"],
                reference_version=str(incumbent["version"]),
            )
        )
        return
    if decision in {"ROLLBACK", "ABSTAIN"}:
        arm_state["mutation_parent"] = deepcopy(
            arm_state["current_incumbent"]
        )
        return
    if decision == "HOLD_FOR_REFINE":
        if arm_state["refinement_used"]:
            arm_state["status"] = "HOLD_FOR_REFINE"
            return
        candidate = child.get("candidate")
        if not isinstance(candidate, Mapping):
            raise LineageError("held child has no candidate")
        arm_state["mutation_parent"] = _candidate_parent(candidate)
        arm_state["pending_hold"] = {"round_id": round_id}
        return
    arm_state["status"] = decision or str(child.get("phase"))


def _prepare_round(
    arm_state: dict[str, object], round_spec: Mapping[str, object]
) -> bool:
    kind = str(round_spec.get("kind", "candidate"))
    pending = arm_state.get("pending_hold")
    if kind != "refinement":
        if pending is not None:
            arm_state["status"] = "HOLD_FOR_REFINE"
            return False
        return True
    if pending is None:
        arm_state["round_results"].append(
            {
                "round_id": str(round_spec["round_id"]),
                "kind": "refinement",
                "decision": "SKIPPED_NO_HOLD",
            }
        )
        arm_state["next_round_index"] += 1
        return False
    if arm_state["refinement_used"]:
        arm_state["status"] = "HOLD_FOR_REFINE"
        return False
    if round_spec.get("evidence_from_round") != pending.get("round_id"):
        raise LineageError("refinement does not name the held evidence round")
    lineage = round_spec.get("lineage")
    proposal = lineage.get("proposal") if isinstance(lineage, Mapping) else None
    if not isinstance(proposal, Mapping) or not proposal.get("evidence"):
        raise LineageError("refinement has no evidence-grounded proposal")
    arm_state["refinement_used"] = True
    return True


def run_campaign(
    plan_path: str | Path,
    state_dir: str | Path,
    *,
    approve_external_run: bool = False,
    child_controller: ChildController = run_controller,
    selected_arms: frozenset[str] | None = None,
) -> dict[str, object]:
    """Run fixed campaign rounds, resuming completed children exactly once."""

    plan = _read_json(Path(plan_path))
    state_root = Path(state_dir)
    state_path = state_root / "CAMPAIGN-STATE.json"
    state = (
        _read_json(state_path)
        if state_path.is_file()
        else _new_state(plan, selected_arms=selected_arms)
    )
    _write_json(state_path, state)

    for arm_id, arm_state_value in state["arms"].items():
        if selected_arms is not None and arm_id not in selected_arms:
            continue
        arm_state = arm_state_value
        if arm_state.get("status") != "RUNNING":
            continue
        arm = _arm_plan(plan, arm_id)
        rounds = arm["rounds"]
        while arm_state.get("status") == "RUNNING":
            index = int(arm_state["next_round_index"])
            if index >= len(rounds):
                arm_state["status"] = "COMPLETE"
                break
            round_spec = rounds[index]
            if not _prepare_round(arm_state, round_spec):
                _write_json(state_path, state)
                if arm_state.get("status") != "RUNNING":
                    break
                continue

            round_id = str(round_spec["round_id"])
            child_plan = _build_child_plan(
                plan,
                arm_id=arm_id,
                arm_state=arm_state,
                round_spec=round_spec,
            )
            child_root = state_root / "children" / arm_id / round_id
            child_plan_path = child_root / "plan.json"
            child_state_dir = child_root / "state"
            _write_json(child_plan_path, child_plan)
            cached_path = child_state_dir / "CONTROLLER-RESULT.json"
            if cached_path.is_file():
                child_result = _read_json(cached_path)
                lineage_id = child_plan["lineages"][0]["lineage_id"]
                try:
                    _child_lineage(child_result, lineage_id)
                except LineageError:
                    child_result = child_controller(
                        child_plan_path,
                        child_state_dir,
                        approve_external_run=approve_external_run,
                    )
            else:
                child_result = child_controller(
                    child_plan_path,
                    child_state_dir,
                    approve_external_run=approve_external_run,
                )
            lineage_id = child_plan["lineages"][0]["lineage_id"]
            child = _child_lineage(child_result, lineage_id)
            _apply_terminal_child(
                arm_state,
                round_spec=round_spec,
                child_plan=child_plan,
                child=child,
                child_plan_path=child_plan_path,
                child_state_dir=child_state_dir,
            )
            _write_json(state_path, state)

    statuses = {value["status"] for value in state["arms"].values()}
    if statuses == {"COMPLETE"}:
        state["status"] = "COMPLETE"
    elif any(value != "COMPLETE" for value in statuses):
        state["status"] = "ATTENTION"
    _write_json(state_path, state)
    _write_json(state_root / "CAMPAIGN-RESULT.json", state)
    return state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--arm", action="append")
    parser.add_argument("--approve-external-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_campaign(
        args.plan,
        args.state_dir,
        approve_external_run=args.approve_external_run,
        selected_arms=(frozenset(args.arm) if args.arm else None),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
