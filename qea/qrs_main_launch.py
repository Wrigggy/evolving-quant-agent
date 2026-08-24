"""Materialize the fixed launch inputs for the global QRS scheduler.

This module is intentionally a pure file builder.  It reads one frozen method
plan and one already-materialized base-harness handoff, then writes the six
proposal-plus-Review controller plans and the small launch manifest consumed by
``qea.qrs_global_scheduler``.  It never invokes an Evolver, Reviewer, Worker,
benchmark, or remote runtime.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from qea.frozen_base_harness import (
    FrozenBaseHarnessError,
    inspect_base_harness,
    validate_frozen_worker_tree_read_only,
    validate_selected_runtime,
)


_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REVIEWER_FIELDS = frozenset(
    {"backend", "model", "dotenv", "token_file", "reasoning_effort"}
)
_REQUIRED_RUNTIME_FIELDS = (
    "python",
    "source_root",
    "qfbench_root",
    "qfbench_manifest",
    "rootless_config",
    "image_set_manifest",
    "results_dir",
    "worker_route",
)


class QRSMainLaunchError(ValueError):
    """The supplied inputs cannot form one deterministic QRS launch."""


def _read_json(path: str | Path, *, label: str) -> dict[str, object]:
    source = Path(path).expanduser().resolve()
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QRSMainLaunchError(f"cannot read {label}: {source}") from exc
    if not isinstance(value, dict):
        raise QRSMainLaunchError(f"{label} must contain a JSON object")
    return value


def _concrete_path(value: object, *, label: str) -> str:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise QRSMainLaunchError(f"{label} must be a non-empty path")
    text = str(value).strip()
    if any(token in text.casefold() for token in ("${", "<replace", "changeme")):
        raise QRSMainLaunchError(f"{label} contains an unresolved placeholder")
    return str(Path(text).expanduser().resolve())


def _runtime(value: Mapping[str, object]) -> dict[str, str]:
    extras = sorted(set(value) - set(_REQUIRED_RUNTIME_FIELDS))
    if extras:
        raise QRSMainLaunchError(
            f"unsupported runtime fields: {', '.join(extras)}"
        )
    runtime = {
        field: _concrete_path(value.get(field), label=f"runtime.{field}")
        for field in _REQUIRED_RUNTIME_FIELDS
        if field != "worker_route"
    }
    route = value.get("worker_route")
    if not isinstance(route, str) or not route.strip():
        raise QRSMainLaunchError("runtime.worker_route must be non-empty")
    runtime["worker_route"] = route.strip()
    return runtime


def _panels(method: Mapping[str, object]) -> list[dict[str, object]]:
    raw = method.get("development_panels")
    if not isinstance(raw, list) or not raw:
        raise QRSMainLaunchError("method plan must contain development panels")
    panels: list[dict[str, object]] = []
    expected_parent: str | None = None
    for expected_index, value in enumerate(raw, start=1):
        if not isinstance(value, Mapping):
            raise QRSMainLaunchError("every development panel must be an object")
        panel_index = value.get("panel_index")
        family = value.get("family")
        parent = value.get("parent")
        proposal = value.get("proposal")
        task_ids = value.get("task_ids")
        if panel_index != expected_index:
            raise QRSMainLaunchError("panels must be indexed consecutively from one")
        if not isinstance(family, str) or not family:
            raise QRSMainLaunchError(f"panel {panel_index} has no family")
        if not isinstance(parent, str) or not parent:
            raise QRSMainLaunchError(f"panel {panel_index} has no parent version")
        if expected_parent is not None and parent != expected_parent:
            raise QRSMainLaunchError(
                f"panel {panel_index} does not continue the proposal chain"
            )
        if not isinstance(proposal, str) or not proposal:
            raise QRSMainLaunchError(f"panel {panel_index} has no proposal version")
        if not isinstance(task_ids, list) or not task_ids or any(
            not isinstance(task_id, str) or not task_id for task_id in task_ids
        ):
            raise QRSMainLaunchError(f"panel {panel_index} has invalid task_ids")
        if task_ids != sorted(task_ids) or len(task_ids) != len(set(task_ids)):
            raise QRSMainLaunchError(
                f"panel {panel_index} task_ids must be sorted and unique"
            )
        panels.append(dict(value))
        expected_parent = proposal
    return panels


def _anchors(method: Mapping[str, object]) -> dict[str, str]:
    workflow = method.get("cross_family_workflow_evidence")
    raw = (
        workflow.get("anchor_task_by_family")
        if isinstance(workflow, Mapping)
        else None
    )
    if not isinstance(raw, Mapping) or not raw:
        raise QRSMainLaunchError("method plan needs cross-family anchors")
    anchors: dict[str, str] = {}
    for family, task_id in raw.items():
        if not isinstance(family, str) or not isinstance(task_id, str):
            raise QRSMainLaunchError("cross-family anchors must be strings")
        anchors[family] = task_id
    return anchors


def _validate_public_partition(
    method: Mapping[str, object],
    panels: list[dict[str, object]],
    anchors: Mapping[str, str],
) -> None:
    development = {
        str(task_id) for panel in panels for task_id in panel["task_ids"]
    }
    raw_sealed = method.get("sealed_main_tasks")
    if not isinstance(raw_sealed, list):
        raise QRSMainLaunchError("method plan has no sealed-main partition")
    sealed: set[str] = set()
    for value in raw_sealed:
        task_id = value.get("task_id") if isinstance(value, Mapping) else None
        if not isinstance(task_id, str) or not task_id:
            raise QRSMainLaunchError("sealed-main task IDs must be non-empty")
        if task_id in sealed:
            raise QRSMainLaunchError("sealed-main task IDs must be unique")
        sealed.add(task_id)
    overlap = development.intersection(sealed)
    if overlap:
        raise QRSMainLaunchError(
            f"development and sealed tasks overlap: {sorted(overlap)}"
        )
    anchor_tasks = set(anchors.values())
    panel_families = {str(panel["family"]) for panel in panels}
    if set(anchors) != panel_families:
        raise QRSMainLaunchError(
            "cross-family anchors must cover every development family"
        )
    if not anchor_tasks.issubset(development):
        raise QRSMainLaunchError(
            "every fixed cross-family anchor must be a development task"
        )
    if anchor_tasks.intersection(sealed):
        raise QRSMainLaunchError("sealed tasks cannot be Review anchors")


def _reviewer(value: Mapping[str, object]) -> dict[str, str]:
    extras = sorted(set(value) - _REVIEWER_FIELDS)
    if extras:
        raise QRSMainLaunchError(
            f"unsupported Reviewer fields: {', '.join(extras)}"
        )
    result: dict[str, str] = {}
    for field in _REVIEWER_FIELDS:
        raw = value.get(field)
        if raw is None:
            continue
        if not isinstance(raw, str) or not raw.strip():
            raise QRSMainLaunchError(f"Reviewer {field} must be non-empty")
        result[field] = raw.strip()
    result.setdefault("backend", "openrouter")
    return result


def _contract_file(root: Path, task_id: str, name: str) -> Path:
    candidates = (
        root / task_id / name,
        root / "tasks" / task_id / name,
        root / "benchmarks" / "qfbench" / "tasks" / task_id / name,
    )
    for candidate in candidates:
        if candidate.is_file() and not candidate.is_symlink():
            return candidate.resolve()
    raise QRSMainLaunchError(
        f"public contract file is unavailable for {task_id}: {name}"
    )


def _public_source_catalog(root: Path, task_ids: list[str]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for task_id in sorted(set(task_ids)):
        instruction = _contract_file(root, task_id, "instruction.md")
        clauses = None
        for name in ("clauses.json", "public_clauses.json"):
            try:
                clauses = _contract_file(root, task_id, name)
                break
            except QRSMainLaunchError:
                continue
        if clauses is None:
            raise QRSMainLaunchError(
                f"public clauses are unavailable for {task_id}"
            )
        sources.extend(
            (
                {
                    "ref": (
                        f"benchmarks/qfbench/tasks/{task_id}/instruction.md"
                    ),
                    "source_type": "public_contract",
                    "source_path": str(instruction),
                },
                {
                    "ref": (
                        f"benchmarks/qfbench/tasks/{task_id}/public_clauses.json"
                    ),
                    "source_type": "public_contract",
                    "source_path": str(clauses),
                },
            )
        )
    return sources


def _write_fixed_json(path: Path, value: Mapping[str, object]) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path.exists():
        if path.is_file() and not path.is_symlink():
            try:
                if path.read_text(encoding="utf-8") == text:
                    return
            except (OSError, UnicodeError):
                pass
        raise QRSMainLaunchError(
            f"refusing to replace a different materialized launch file: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _panel_controller_state_root(
    *, scheduler_state_root: Path, panel_index: int
) -> Path:
    return (scheduler_state_root / f"panel-{panel_index}-controller").resolve()


def _reviewed_candidate_path(
    *, scheduler_state_root: Path, scheduler_run_id: str, panel_index: int
) -> Path:
    lineage_id = f"{scheduler_run_id}-panel-{panel_index:02d}"
    review_id = f"{lineage_id}-review"
    state_root = _panel_controller_state_root(
        scheduler_state_root=scheduler_state_root,
        panel_index=panel_index,
    )
    return (
        state_root / "reviewed-candidates" / lineage_id / review_id
    ).resolve()


def build_qrs_main_launch(
    *,
    method_plan_path: str | Path,
    frozen_h0_handoff_path: str | Path,
    scheduler_run_id: str,
    runtime: Mapping[str, object],
    qfbench_public_manifest: str | Path,
    trajectory_bank_output: str | Path,
    public_contracts_root: str | Path,
    reviewer_config: Mapping[str, object],
    output_root: str | Path,
) -> dict[str, object]:
    """Write one launch manifest and six Review-staged controller plans."""

    if _RUN_ID.fullmatch(scheduler_run_id) is None:
        raise QRSMainLaunchError("scheduler_run_id is not a safe fixed ID")
    method_path = Path(method_plan_path).expanduser().resolve()
    handoff_path = Path(frozen_h0_handoff_path).expanduser().resolve()
    method = _read_json(method_path, label="frozen QRS method plan")
    handoff = _read_json(handoff_path, label="frozen base-harness handoff")
    panels = _panels(method)
    anchors = _anchors(method)
    _validate_public_partition(method, panels, anchors)
    concrete_runtime = _runtime(runtime)
    review_runtime = _reviewer(reviewer_config)
    contracts_root = Path(
        _concrete_path(public_contracts_root, label="public_contracts_root")
    )
    bank_output = Path(
        _concrete_path(trajectory_bank_output, label="trajectory_bank_output")
    )
    public_manifest = _concrete_path(
        qfbench_public_manifest, label="qfbench_public_manifest"
    )
    destination = Path(_concrete_path(output_root, label="output_root"))

    if handoff.get("selection_complete") is not True or handoff.get(
        "frozen_for_qrs_scheduler"
    ) is not True:
        raise QRSMainLaunchError("base-harness handoff is not selected and frozen")
    profile_id = handoff.get("selected_profile_id")
    worker_root = handoff.get("selected_worker_root")
    selected_runtime = handoff.get("selected_runtime")
    if not isinstance(profile_id, str) or not profile_id:
        raise QRSMainLaunchError("base-harness handoff has no selected_profile_id")
    if not isinstance(worker_root, str) or not worker_root:
        raise QRSMainLaunchError("base-harness handoff has no selected_worker_root")
    if not isinstance(selected_runtime, Mapping):
        raise QRSMainLaunchError("base-harness handoff has no selected_runtime")
    try:
        validate_selected_runtime(selected_runtime)
        inspect_base_harness(worker_root)
        adapter = handoff.get("adapter_contract")
        if (
            not isinstance(adapter, Mapping)
            or adapter.get("selected_worker_tree_read_only") is not True
        ):
            raise FrozenBaseHarnessError(
                "base-harness handoff does not declare a read-only frozen Worker"
            )
        validate_frozen_worker_tree_read_only(worker_root)
    except FrozenBaseHarnessError as exc:
        raise QRSMainLaunchError(str(exc)) from exc
    if selected_runtime.get("worker_model_route") != concrete_runtime["worker_route"]:
        raise QRSMainLaunchError("runtime worker route differs from frozen H0")
    if _concrete_path(
        selected_runtime.get("rootless_config"), label="selected_runtime.rootless_config"
    ) != concrete_runtime["rootless_config"]:
        raise QRSMainLaunchError("runtime rootless config differs from frozen H0")

    results_dir = Path(concrete_runtime["results_dir"])
    scheduler_state_root = (
        results_dir / scheduler_run_id / "scheduler-state"
    ).resolve()
    panel_plan_paths: dict[str, str] = {}
    parent_version = profile_id
    parent_worker_dir = str(Path(worker_root).expanduser().resolve())
    cumulative_focus_tasks: set[str] = set()
    for panel in panels:
        panel_index = int(panel["panel_index"])
        family = str(panel["family"])
        proposal_version = str(panel["proposal"])
        lineage_id = f"{scheduler_run_id}-panel-{panel_index:02d}"
        controller_run_id = f"{lineage_id}-controller"
        proposal_run_id = f"{lineage_id}-proposal"
        review_id = f"{lineage_id}-review"
        panel_state_root = _panel_controller_state_root(
            scheduler_state_root=scheduler_state_root,
            panel_index=panel_index,
        )
        panel_evidence_root = (
            bank_output
            / "evolver-answer-free"
            / "panel-evidence"
            / f"panel-{panel_index:02d}-{family}"
        ).resolve()
        cumulative_focus_tasks.update(str(value) for value in panel["task_ids"])
        review_task_ids = sorted(
            cumulative_focus_tasks | set(anchors.values())
        )
        public_source_catalog = _public_source_catalog(
            contracts_root, review_task_ids
        )
        review_spec: dict[str, object] = {
            "enabled": True,
            "feedback_mode": "answer_free",
            "review_id": review_id,
            "arm_blind": True,
            "public_sources": [],
            "public_source_catalog": public_source_catalog,
            "answer_free_development_evidence_root": str(panel_evidence_root),
            "optimize_only_sources": [],
            "candidate_material_baseline_worker_dir": str(
                Path(worker_root).expanduser().resolve()
            ),
            **review_runtime,
        }
        controller_plan: dict[str, object] = {
            "schema_version": 1,
            "record_kind": "qrs_workflow_global_panel_controller_plan",
            "status": "materialized_proposal_review_only_not_dispatched",
            "controller_run_id": controller_run_id,
            "mode": "live",
            "runtime": concrete_runtime,
            "states_root": str(panel_state_root),
            "parent_binding": {
                "mode": "scheduler_current_incumbent_at_dispatch",
                "template_parent_is_nominal": True,
                "resolved_plan_filename": "RESOLVED-CONTROLLER-PLAN.json",
            },
            "dispatch_boundary": {
                "required_stop_after_stage": "information_set_review",
                "proposal_calls": 1,
                "reviewer_calls": 1,
                "worker_calls": 0,
                "builder_dispatched_children": False,
            },
            "lineages": [
                {
                    "lineage_id": lineage_id,
                    "family": family,
                    "treatment": "qrs_workflow_global_six_stage",
                    "parent": {
                        "version": parent_version,
                        "worker_dir": parent_worker_dir,
                    },
                    "proposal": {
                        "live_run_id": proposal_run_id,
                        "candidate_version": proposal_version,
                        "workflow_scope": "workflow_global",
                        "evidence": str(panel_evidence_root),
                        "evolver_dir": str(
                            Path(concrete_runtime["source_root"])
                            / "qea"
                            / "evolve_agent_full"
                        ),
                        "arm": "quant-state",
                        "reasoning_effort": review_runtime.get(
                            "reasoning_effort", "high"
                        ),
                    },
                    "candidate_information_set_review": review_spec,
                    "stages": [
                        {
                            "name": "target",
                            "task_id": str(panel["task_ids"][0]),
                            "conditional_not_authorized": True,
                        },
                        {
                            "name": "protection",
                            "task_id": str(panel["task_ids"][-1]),
                            "conditional_not_authorized": True,
                        },
                    ],
                }
            ],
            "limits": {
                "provider_cost_usd": "1",
                "proposal_calls": 1,
                "reviewer_calls": 1,
                "worker_calls": 0,
            },
        }
        plan_path = (
            destination
            / "panel-controller-plans"
            / f"panel-{panel_index:02d}-{family}.json"
        ).resolve()
        _write_fixed_json(plan_path, controller_plan)
        panel_plan_paths[str(panel_index)] = str(plan_path)
        parent_version = proposal_version
        parent_worker_dir = str(
            _reviewed_candidate_path(
                scheduler_state_root=scheduler_state_root,
                scheduler_run_id=scheduler_run_id,
                panel_index=panel_index,
            )
        )

    launch: dict[str, object] = {
        "schema_version": 1,
        "record_kind": "qrs_global_scheduler_launch",
        "status": "materialized_not_dispatched",
        "scheduler_run_id": scheduler_run_id,
        "method_plan_path": str(method_path),
        "frozen_h0_handoff": str(handoff_path),
        "runtime": concrete_runtime,
        "scheduler_state_root": str(scheduler_state_root),
        "qfbench_public_manifest": public_manifest,
        "trajectory_bank_output": str(bank_output),
        "trajectory_bank_manifest": str((bank_output / "BANK-MANIFEST.json").resolve()),
        "public_contracts_root": str(contracts_root),
        "panel_controller_plans": panel_plan_paths,
        "panel_count": len(panel_plan_paths),
        "builder_dispatched_children": False,
    }
    launch_path = (destination / "QRS-MAIN-LAUNCH.json").resolve()
    _write_fixed_json(launch_path, launch)
    return {**launch, "launch_plan_path": str(launch_path)}


__all__ = ["QRSMainLaunchError", "build_qrs_main_launch"]
