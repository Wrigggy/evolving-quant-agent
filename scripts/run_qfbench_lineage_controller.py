#!/usr/bin/env python3
"""Run the thin Main-0 candidate lifecycle over retained official results."""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.qfbench_lineage import (  # noqa: E402
    LineageError,
    freeze_lineage,
    hold_candidate_information_set_review,
    import_candidate_information_set_review,
    import_comparison_observation,
    import_pilot_report,
    import_proposal_report,
    import_quantitative_protection_review,
    load_lineage,
    new_lineage,
    new_proposal_lineage,
    save_lineage,
)
from qea.quantcodeeval_lineage_adapter import (  # noqa: E402
    QuantCodeEvalLineageAdapterError,
    normalize_quantcodeeval_lineage_observation,
    quantcodeeval_lineage_score,
)


Runner = Callable[[Sequence[str]], object]


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise LineageError(f"{path} must contain a JSON object")
    return value


def _stage(lineage: Mapping[str, object], name: str) -> Mapping[str, object]:
    stages = lineage.get("stages")
    if not isinstance(stages, list):
        raise LineageError("lineage has no stages")
    matches = [value for value in stages if value.get("name") == name]
    if len(matches) != 1:
        raise LineageError(f"lineage has no unique {name} stage")
    return matches[0]


def build_child_argv(
    plan: Mapping[str, object],
    lineage: Mapping[str, object],
    stage: Mapping[str, object],
    *,
    approve_external_run: bool,
) -> tuple[str, ...]:
    """Build one existing component-pilot invocation."""

    if not approve_external_run:
        raise LineageError("live child execution was not approved")
    runtime = plan["runtime"]
    parent = lineage["parent"]
    candidate = lineage["candidate"]
    run_id = str(
        stage.get("live_run_id")
        or f"{plan['controller_run_id']}-{lineage['lineage_id']}-{stage['name']}"
    )
    checkpoint = str(stage.get("checkpoint_prefix") or run_id)
    parent_arm = str(stage.get("parent_arm", "parent"))
    candidate_arm = str(stage.get("candidate_arm", "candidate"))
    argv = [
        str(runtime["python"]),
        str(Path(str(runtime["source_root"])) / "scripts/run_qfbench_component_pilot.py"),
        "--qfbench-root",
        str(runtime["qfbench_root"]),
        "--qfbench-manifest",
        str(runtime["qfbench_manifest"]),
        "--rootless-config",
        str(runtime["rootless_config"]),
        "--rootless-image-set-manifest",
        str(runtime["image_set_manifest"]),
        "--run-id",
        run_id,
        "--results-dir",
        str(runtime["results_dir"]),
        "--seed-worker",
        str(parent["worker_dir"]),
    ]
    if not isinstance(stage.get("parent_comparator"), Mapping) and not isinstance(
        stage.get("selection_reference"), Mapping
    ):
        argv.extend(("--arm", f"{parent_arm}={parent['worker_dir']}"))
    argv.extend(("--arm", f"{candidate_arm}={candidate['worker_dir']}"))
    argv.extend(
        [
            "--task-id",
            str(stage["task_id"]),
            "--checkpoint-prefix",
            checkpoint,
            "--worker-concurrency",
            str(stage.get("worker_concurrency", 1)),
            "--verifier-concurrency",
            str(stage.get("verifier_concurrency", 2)),
            "--approve-external-run",
        ]
    )
    if "activation_binding" in candidate:
        activation_token = candidate.get("activation_token")
    else:
        activation_token = stage.get("activation_token")
    if activation_token:
        argv.extend(("--activation-token", str(activation_token)))
    return tuple(argv)


def _quantcodeeval_live_run_id(
    plan: Mapping[str, object],
    lineage: Mapping[str, object],
    stage: Mapping[str, object],
) -> str:
    return str(
        stage.get("live_run_id")
        or f"{plan['controller_run_id']}-{lineage['lineage_id']}-{stage['name']}"
    )


def _quantcodeeval_live_result_path(
    plan: Mapping[str, object],
    lineage: Mapping[str, object],
    stage: Mapping[str, object],
) -> Path:
    run_id = _quantcodeeval_live_run_id(plan, lineage, stage)
    return (
        Path(str(plan["runtime"]["results_dir"]))
        / run_id
        / "FULL-CANDIDATE-RESULT.json"
    )


def build_quantcodeeval_child_argv(
    plan: Mapping[str, object],
    lineage: Mapping[str, object],
    stage: Mapping[str, object],
    *,
    approve_external_run: bool,
) -> tuple[str, ...]:
    """Build one existing QuantCodeEval v2 candidate invocation."""

    if not approve_external_run:
        raise LineageError("live QuantCodeEval child execution was not approved")
    runtime = plan["runtime"]
    candidate = lineage["candidate"]
    activation_run = stage.get("activation_run") or candidate.get(
        "activation_run"
    )
    if not isinstance(activation_run, str) or not activation_run:
        raise LineageError("live QuantCodeEval stage has no activation_run")
    image_fields = {
        "quantcodeeval_worker_image": "worker_image_ref",
        "quantcodeeval_verifier_image": "verifier_image_ref",
        "quantcodeeval_proxy_image": "proxy_image_ref",
    }
    image_refs = {
        runtime_name: runtime.get(runtime_name)
        for runtime_name in image_fields
    }
    if any(
        not isinstance(value, str) or not value
        for value in image_refs.values()
    ):
        preflight_path = Path(
            str(
                runtime.get("quantcodeeval_h0_preflight")
                or Path(str(runtime["quantcodeeval_release"]))
                / "h0/H0-PREFLIGHT.json"
            )
        )
        preflight = _json(preflight_path)
        for runtime_name, preflight_name in image_fields.items():
            if not isinstance(image_refs[runtime_name], str) or not image_refs[
                runtime_name
            ]:
                image_refs[runtime_name] = preflight.get(preflight_name)
    if any(
        not isinstance(value, str) or not value
        for value in image_refs.values()
    ):
        raise LineageError("QuantCodeEval H0 preflight has no complete image refs")
    argv = [
        str(runtime["python"]),
        str(
            Path(str(runtime["source_root"]))
            / "scripts/run_quantcodeeval_v2_candidate.py"
        ),
        "--config",
        str(runtime["quantcodeeval_config"]),
        "--release",
        str(runtime["quantcodeeval_release"]),
        "--activation-run",
        activation_run,
        "--run-dir",
        str(_quantcodeeval_live_result_path(plan, lineage, stage).parent),
        "--worker-image",
        str(image_refs["quantcodeeval_worker_image"]),
        "--verifier-image",
        str(image_refs["quantcodeeval_verifier_image"]),
        "--proxy-image",
        str(image_refs["quantcodeeval_proxy_image"]),
        "--task",
        str(stage["task_id"]),
    ]
    task_panel = stage.get("task_panel") or runtime.get(
        "quantcodeeval_task_panel"
    )
    if task_panel:
        argv.extend(("--task-panel", str(task_panel)))
    if stage.get("source_h0_evaluation_id"):
        argv.extend(
            (
                "--source-h0-evaluation-id",
                str(stage["source_h0_evaluation_id"]),
            )
        )
    return tuple(argv)


def build_proposal_argv(
    plan: Mapping[str, object],
    lineage: Mapping[str, object],
    proposal: Mapping[str, object],
    *,
    approve_external_run: bool,
) -> tuple[str, ...]:
    """Build one invocation of the existing QFBench discovery runner."""

    if not approve_external_run:
        raise LineageError("live proposal execution was not approved")
    runtime = plan["runtime"]
    run_id = str(
        proposal.get("live_run_id")
        or f"{plan['controller_run_id']}-{lineage['lineage_id']}-proposal"
    )
    argv = [
        str(runtime["python"]),
        str(Path(str(runtime["source_root"])) / "scripts/run_qfbench_discovery_pilot.py"),
        "--qfbench-root",
        str(runtime["qfbench_root"]),
        "--qfbench-manifest",
        str(runtime["qfbench_manifest"]),
        "--rootless-config",
        str(runtime["rootless_config"]),
        "--rootless-image-set-manifest",
        str(runtime["image_set_manifest"]),
        "--run-id",
        run_id,
        "--results-dir",
        str(runtime["results_dir"]),
        "--backbone",
        str(lineage["parent"]["worker_dir"]),
        "--evidence",
        str(proposal["evidence"]),
        "--evolver-dir",
        str(proposal["evolver_dir"]),
        "--arm",
        str(proposal["arm"]),
        "--reasoning-effort",
        str(proposal.get("reasoning_effort", "none")),
        "--approve-external-run",
    ]
    return tuple(argv)


def _proposal_report_path(
    plan: Mapping[str, object],
    lineage: Mapping[str, object],
    proposal: Mapping[str, object],
) -> Path:
    replay = proposal.get("replay_report")
    if replay:
        return Path(str(replay))
    run_id = str(
        proposal.get("live_run_id")
        or f"{plan['controller_run_id']}-{lineage['lineage_id']}-proposal"
    )
    return Path(str(plan["runtime"]["results_dir"])) / run_id / "proposal-report.json"


def _proposal_run_id(
    plan: Mapping[str, object],
    lineage: Mapping[str, object],
    proposal: Mapping[str, object],
) -> str:
    return str(
        proposal.get("live_run_id")
        or proposal.get("replay_run_id")
        or f"{plan['controller_run_id']}-{lineage['lineage_id']}-proposal"
    )


def _information_set_review_spec(
    lineage: Mapping[str, object],
) -> dict[str, object] | None:
    """Return one trusted opt-in pre-Worker review specification."""

    raw = lineage.get("candidate_information_set_review")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise LineageError(
            "candidate_information_set_review must be a JSON object"
        )
    if raw.get("enabled") is not True:
        return None
    feedback_mode = raw.get("feedback_mode")
    if feedback_mode not in {"answer_free", "answer_rich_evolver"}:
        raise LineageError(
            "candidate information-set review requires answer_free or "
            "answer_rich_evolver"
        )
    review_id = raw.get("review_id")
    if not isinstance(review_id, str) or not review_id:
        raise LineageError("candidate information-set review has no review_id")
    for field in ("public_sources", "optimize_only_sources"):
        if not isinstance(raw.get(field), list):
            raise LineageError(
                f"candidate information-set review {field} must be a list"
            )
    if feedback_mode == "answer_free" and raw["optimize_only_sources"]:
        raise LineageError(
            "answer-free candidate review cannot include optimize-only sources"
        )
    return dict(raw)


def _worker_visible_surface(relative: str) -> str | None:
    """Map one admitted candidate path to a Worker-visible harness surface."""

    if relative == "systemprompt.md":
        return "systemprompt"
    if relative == "agent.yaml":
        return "agent_config"
    head = relative.split("/", 1)[0]
    if head in {
        "tool_descriptions",
        "tools",
        "validator",
        "skills",
        "memory",
        "middleware",
        "routing",
    }:
        return head
    return None


def _worker_visible_candidate_material(
    parent_dir: object,
    candidate_dir: object,
) -> dict[str, object] | None:
    """Build a text diff from the real admitted Worker-visible files."""

    if not isinstance(parent_dir, str) or not isinstance(candidate_dir, str):
        return None
    parent_root = Path(parent_dir)
    candidate_root = Path(candidate_dir)
    if not parent_root.is_dir() or not candidate_root.is_dir():
        return None

    def snapshot(root: Path) -> dict[str, tuple[str, str]]:
        values = {}
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            relative = path.relative_to(root).as_posix()
            surface = _worker_visible_surface(relative)
            if surface is None:
                continue
            values[relative] = (
                surface,
                path.read_text(encoding="utf-8", errors="replace"),
            )
        return values

    parent = snapshot(parent_root)
    candidate = snapshot(candidate_root)
    changed_files = []
    diff_parts = []
    for relative in sorted(set(parent) | set(candidate)):
        old_surface, old_text = parent.get(relative, (None, ""))
        new_surface, new_text = candidate.get(relative, (None, ""))
        if old_text == new_text:
            continue
        surface = new_surface or old_surface
        change_type = (
            "added"
            if relative not in parent
            else "removed"
            if relative not in candidate
            else "modified"
        )
        changed_files.append(
            {
                "ref": f"candidate:file:{relative}",
                "path": relative,
                "surface": surface,
                "change_type": change_type,
                "excerpt": new_text if change_type != "removed" else old_text,
            }
        )
        diff_parts.extend(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"parent/{relative}",
                tofile=f"candidate/{relative}",
            )
        )
    if not changed_files:
        return None
    return {
        "diff_ref": "candidate:diff",
        "diff": "".join(diff_parts),
        "files": changed_files,
    }


def _candidate_information_set_review_package(
    state: Mapping[str, object],
    spec: Mapping[str, object],
) -> tuple[dict[str, object] | None, str | None]:
    """Construct the Reviewer package without trusting Evolver source labels."""

    proposal = state.get("proposal")
    candidate = state.get("candidate")
    parent = state.get("current_parent")
    claims = (
        proposal.get("worker_visible_claims")
        if isinstance(proposal, Mapping)
        else None
    )
    if not isinstance(claims, list) or not claims:
        return None, "information_set_review_missing_worker_visible_claims"

    material_baseline = spec.get("candidate_material_baseline_worker_dir")
    if material_baseline is None:
        material_baseline = (
            parent.get("worker_dir") if isinstance(parent, Mapping) else None
        )
    else:
        if not isinstance(material_baseline, str) or not material_baseline.strip():
            raise LineageError(
                "candidate information-set review "
                "candidate_material_baseline_worker_dir must be a non-empty string"
            )
        if not Path(material_baseline).is_dir():
            raise LineageError(
                "candidate information-set review "
                "candidate_material_baseline_worker_dir is not an existing "
                f"directory: {material_baseline}"
            )
    material = _worker_visible_candidate_material(
        material_baseline,
        candidate.get("worker_dir") if isinstance(candidate, Mapping) else None,
    )
    if material is None:
        return None, "information_set_review_missing_candidate_material"
    package = {
        "schema_version": 1,
        "review_id": spec["review_id"],
        "candidate_id": candidate["version"],
        "candidate": material,
        "worker_visible_claims": claims,
        "public_sources": spec["public_sources"],
        "optimize_only_sources": spec["optimize_only_sources"],
    }
    from qea.candidate_information_set_review import (
        CandidateInformationSetReviewError,
        validate_candidate_information_set_review_package,
    )

    try:
        validate_candidate_information_set_review_package(package)
    except CandidateInformationSetReviewError as exc:
        raise LineageError(f"invalid trusted candidate review package: {exc}") from exc
    return package, None


def _information_set_review_paths(
    plan: Mapping[str, object],
    spec: Mapping[str, object],
    states_root: Path,
) -> tuple[Path, Path, Path]:
    review_id = str(spec["review_id"])
    input_path = states_root / "review-inputs" / f"{review_id}.json"
    result_dir = Path(str(plan["runtime"]["results_dir"])) / review_id
    return input_path, result_dir, result_dir / "RESULT.json"


def build_candidate_information_set_review_argv(
    plan: Mapping[str, object],
    spec: Mapping[str, object],
    *,
    input_path: Path,
    result_dir: Path,
    approve_external_run: bool,
) -> tuple[str, ...]:
    """Build the single external Candidate Reviewer invocation."""

    if not approve_external_run:
        raise LineageError("live candidate information-set review was not approved")
    runtime = plan["runtime"]
    argv = [
        str(runtime["python"]),
        str(
            Path(str(runtime["source_root"]))
            / "scripts/run_candidate_information_set_reviewer_canary.py"
        ),
        "--input",
        str(input_path),
        "--out",
        str(result_dir),
        "--backend",
        str(spec.get("backend", "openrouter")),
    ]
    if spec.get("model"):
        argv.extend(("--model", str(spec["model"])))
    if spec.get("dotenv"):
        argv.extend(("--dotenv", str(spec["dotenv"])))
    if spec.get("token_file"):
        argv.extend(("--token-file", str(spec["token_file"])))
    return tuple(argv)


def _candidate_information_set_review_result(
    plan: Mapping[str, object],
    spec: Mapping[str, object],
    package: Mapping[str, object],
    states_root: Path,
    *,
    approve_external_run: bool,
    runner: Runner,
) -> tuple[Path, dict[str, object], dict[str, object]]:
    """Replay an existing fixed-ID result or run the one approved Reviewer call."""

    input_path, result_dir, result_path = _information_set_review_paths(
        plan, spec, states_root
    )
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(json.dumps(package, indent=2) + "\n")
    if not result_path.is_file():
        if plan.get("mode") == "replay":
            raise LineageError(
                f"replay candidate information-set review is missing: {result_path}"
            )
        argv = build_candidate_information_set_review_argv(
            plan,
            spec,
            input_path=input_path,
            result_dir=result_dir,
            approve_external_run=approve_external_run,
        )
        _run_child(runner, argv)
    if not result_path.is_file():
        raise LineageError(
            f"candidate information-set Reviewer wrote no result: {result_path}"
        )
    wrapper = _json(result_path)
    if wrapper.get("status") != "complete":
        raise LineageError("candidate information-set result is not complete")
    if wrapper.get("worker_visible") is not False:
        raise LineageError(
            "candidate information-set result must remain Worker-hidden"
        )
    if wrapper.get("promotion_authority") is not False:
        raise LineageError(
            "candidate information-set Reviewer must have no promotion authority"
        )
    request = wrapper.get("request")
    if not isinstance(request, Mapping) or request.get("request_count") != 1:
        raise LineageError(
            "candidate information-set result must account for one request"
        )
    payload = wrapper.get("review")
    if not isinstance(payload, Mapping):
        raise LineageError("candidate information-set result has no review")
    accounting = _review_accounting(wrapper)
    if accounting is None:
        raise LineageError(
            "candidate information-set result has no request accounting"
        )
    return result_path, dict(payload), accounting


def _report_path(
    plan: Mapping[str, object],
    lineage: Mapping[str, object],
    stage: Mapping[str, object],
) -> Path:
    replay = stage.get("replay_report")
    if replay:
        return Path(str(replay))
    run_id = str(
        stage.get("live_run_id")
        or f"{plan['controller_run_id']}-{lineage['lineage_id']}-{stage['name']}"
    )
    return Path(str(plan["runtime"]["results_dir"])) / run_id / "pilot-report.json"


def _parent_comparator(
    stage: Mapping[str, object],
    state: Mapping[str, object],
) -> tuple[str, Path, dict[str, object]] | None:
    """Load one explicitly matched reusable parent observation."""

    parent_spec = stage.get("parent_comparator")
    selection_spec = stage.get("selection_reference")
    if parent_spec is not None and selection_spec is not None:
        raise LineageError(
            "stage cannot declare both parent_comparator and selection_reference"
        )
    spec = selection_spec if selection_spec is not None else parent_spec
    if spec is None:
        return None
    if not isinstance(spec, Mapping):
        raise LineageError("comparison reference must be a JSON object")
    comparator_id = spec.get("id")
    report_path = spec.get("report_path")
    if not isinstance(comparator_id, str) or not comparator_id:
        raise LineageError("parent_comparator has no id")
    if not isinstance(report_path, str) or not report_path:
        raise LineageError("parent_comparator has no report_path")
    expected = {
        "task_id": stage["task_id"],
        "worker_route": state["worker_route"],
        "worker_budget": state["worker_budget"],
    }
    version_field = "parent_version"
    expected_version = state["current_parent"]["version"]
    if selection_spec is not None:
        version_field = "reference_version"
        expected_version = selection_spec.get("reference_version")
        if not isinstance(expected_version, str) or not expected_version:
            raise LineageError("selection_reference has no reference_version")
    expected[version_field] = expected_version
    for field, value in expected.items():
        if spec.get(field) != value:
            raise LineageError(
                f"comparison reference {comparator_id!r} {field} does not match "
                f"the active lineage"
            )
    path = Path(report_path)
    if not path.is_file():
        raise LineageError(f"parent comparator is missing: {path}")
    report = _json(path)
    if report.get("status") not in {"complete", "invalid_worker_execution"}:
        raise LineageError("parent comparator report is not complete")
    return comparator_id, path, report


def compose_reused_parent_report(
    *,
    parent_comparator: tuple[str, Path, Mapping[str, object]],
    candidate_report: Mapping[str, object],
    parent_arm: str,
    candidate_arm: str,
    task_id: str,
) -> dict[str, object]:
    """Compose a normal comparison while charging only the new candidate arm."""

    comparator_id, parent_path, parent_report = parent_comparator
    parent_status = parent_report.get("status")
    candidate_status = candidate_report.get("status")
    if parent_status not in {"complete", "invalid_worker_execution"}:
        raise LineageError("parent comparator pilot report is not complete")
    if candidate_status not in {"complete", "invalid_worker_execution"}:
        raise LineageError("candidate-only pilot report is not complete")
    if parent_arm == candidate_arm:
        raise LineageError("parent and candidate arm labels must differ")

    def arm_value(
        report: Mapping[str, object], section: str, arm: str
    ) -> object:
        values = report.get(section)
        if not isinstance(values, Mapping) or arm not in values:
            raise LineageError(f"pilot report has no {arm!r} {section}")
        return values[arm]

    # Validate that both reports actually carry the task before composing them.
    _tests_failed(parent_report, parent_arm, task_id)
    _tests_failed(candidate_report, candidate_arm, task_id)
    cost = candidate_report.get("cost")
    if not isinstance(cost, Mapping):
        raise LineageError("candidate-only pilot report has no cost summary")
    run_id = candidate_report.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise LineageError("candidate-only pilot report has no run_id")

    result = {
        "schema_version": 1,
        "run_id": run_id,
        "status": (
            "invalid_worker_execution"
            if "invalid_worker_execution" in {parent_status, candidate_status}
            else "complete"
        ),
        "task_ids": [task_id],
        "summaries": {
            parent_arm: arm_value(parent_report, "summaries", parent_arm),
            candidate_arm: arm_value(
                candidate_report, "summaries", candidate_arm
            ),
        },
        "activations": {
            parent_arm: arm_value(parent_report, "activations", parent_arm),
            candidate_arm: arm_value(
                candidate_report, "activations", candidate_arm
            ),
        },
        "cost": dict(cost),
        "parent_comparator_reuse": {
            "id": comparator_id,
            "report_path": str(parent_path),
            "parent_run_id": parent_report.get("run_id"),
            "candidate_run_id": run_id,
            "cost_accounting": "candidate_only",
        },
    }
    invalid_executions = {}
    if parent_status == "invalid_worker_execution":
        invalid_executions[parent_arm] = arm_value(
            parent_report, "worker_executions", parent_arm
        )
    if candidate_status == "invalid_worker_execution":
        invalid_executions[candidate_arm] = arm_value(
            candidate_report, "worker_executions", candidate_arm
        )
    if invalid_executions:
        result["worker_executions"] = invalid_executions
    return result


def _quantitative_triage(stage: Mapping[str, object]) -> dict[str, object]:
    """Return the explicitly supplied deterministic protection result."""

    value = stage.get("quantitative_triage")
    if not isinstance(value, Mapping):
        raise LineageError(
            f"{stage.get('name')} has no explicit quantitative_triage result"
        )
    return dict(value)


def _optional_mapping(
    value: object, *, label: str
) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise LineageError(f"{label} must be a JSON object")
    return dict(value)


def _quantcodeeval_comparison(
    stage: Mapping[str, object],
) -> dict[str, object]:
    """Normalize one retained QuantCodeEval parent--candidate result pair."""

    task_id = stage.get("task_id")
    parent_source = stage.get("parent_result")
    candidate_source = stage.get("candidate_result")
    if not isinstance(task_id, str) or not task_id:
        raise LineageError("QuantCodeEval stage has no task_id")
    if not isinstance(parent_source, (str, Mapping)):
        raise LineageError("QuantCodeEval stage has no parent_result")
    if not isinstance(candidate_source, (str, Mapping)):
        raise LineageError("QuantCodeEval stage has no candidate_result")
    adapter_stage = str(stage.get("name"))
    if adapter_stage == "protection_repeat":
        adapter_stage = "protection"
    property_total = stage.get("official_property_total")
    parent_run_id = stage.get("parent_run_id")
    candidate_run_id = stage.get("candidate_run_id")
    if parent_run_id is not None and not isinstance(parent_run_id, str):
        raise LineageError("QuantCodeEval parent_run_id must be a string")
    if candidate_run_id is not None and not isinstance(candidate_run_id, str):
        raise LineageError("QuantCodeEval candidate_run_id must be a string")
    try:
        parent_observation = normalize_quantcodeeval_lineage_observation(
            parent_source,
            task_id=task_id,
            stage=adapter_stage,
            run_id=parent_run_id,
            cost=_optional_mapping(
                stage.get("parent_cost"), label="QuantCodeEval parent_cost"
            ),
            official_property_total=property_total,
        )
        candidate_observation = normalize_quantcodeeval_lineage_observation(
            candidate_source,
            task_id=task_id,
            stage=adapter_stage,
            run_id=candidate_run_id,
            cost=_optional_mapping(
                stage.get("candidate_cost"),
                label="QuantCodeEval candidate_cost",
            ),
            official_property_total=property_total,
        )
        parent_score = quantcodeeval_lineage_score(
            parent_observation,
            official_property_total=property_total,
            require_accounting=False,
        )
        candidate_score = quantcodeeval_lineage_score(
            candidate_observation,
            official_property_total=property_total,
        )
    except QuantCodeEvalLineageAdapterError as exc:
        raise LineageError(f"QuantCodeEval comparison is not ready: {exc}") from exc

    comparison_run_id = stage.get("comparison_run_id")
    if comparison_run_id is None:
        comparison_run_id = candidate_observation.get("run_id")
    if not isinstance(comparison_run_id, str) or not comparison_run_id:
        raise LineageError("QuantCodeEval comparison has no run_id")
    candidate_cost = candidate_observation.get("cost")
    if not isinstance(candidate_cost, Mapping):
        raise LineageError("QuantCodeEval candidate has no explicit cost")
    report_path = (
        candidate_source
        if isinstance(candidate_source, str)
        else f"<embedded:{comparison_run_id}:candidate>"
    )
    return {
        "run_id": comparison_run_id,
        "task_id": task_id,
        "parent": parent_score,
        "candidate": candidate_score,
        "cost": dict(candidate_cost),
        "report_path": report_path,
        "provenance": {
            "parent_result": (
                parent_source if isinstance(parent_source, str) else "<embedded>"
            ),
            "parent_run_id": parent_observation.get("run_id"),
            "parent_status": parent_observation.get("status"),
            "candidate_result": report_path,
            "candidate_run_id": candidate_observation.get("run_id"),
            "candidate_status": candidate_observation.get("status"),
            "official_property_total": property_total,
            "cost_accounting": "candidate_only",
        },
    }


def _quantcodeeval_stage_with_live_result(
    plan: Mapping[str, object],
    lineage: Mapping[str, object],
    stage: Mapping[str, object],
    *,
    approve_external_run: bool,
    runner: Runner,
) -> dict[str, object]:
    """Resolve a retained result or run one fixed-ID candidate child."""

    resolved = dict(stage)
    if isinstance(stage.get("candidate_result"), (str, Mapping)):
        return resolved
    result_path = _quantcodeeval_live_result_path(plan, lineage, stage)
    if not result_path.is_file():
        if plan.get("mode") == "replay":
            raise LineageError(
                f"replay QuantCodeEval candidate is missing: {result_path}"
            )
        argv = build_quantcodeeval_child_argv(
            plan,
            lineage,
            stage,
            approve_external_run=approve_external_run,
        )
        child = runner(argv)
        return_code = getattr(child, "returncode", 0)
        if return_code and not result_path.is_file():
            raise RuntimeError(
                f"QuantCodeEval child runner exited with code {return_code}"
            )
    if not result_path.is_file():
        raise LineageError(
            f"QuantCodeEval child did not write its result: {result_path}"
        )
    resolved["candidate_result"] = str(result_path)
    return resolved


def _quantcodeeval_property_set_safe(
    stage: Mapping[str, object],
    comparison: Mapping[str, object],
) -> bool:
    """Use conclusive counts, otherwise require the declared property verdict."""

    parent = comparison["parent"]
    candidate = comparison["candidate"]
    candidate_failed = candidate["tests_failed"]
    parent_failed = parent["tests_failed"]
    if candidate_failed == 0:
        return True
    if parent_failed == 0:
        return False
    declared = stage.get("property_set_safe")
    if not isinstance(declared, bool):
        raise LineageError(
            "QuantCodeEval protection with nonzero parent and candidate "
            "failures needs explicit property_set_safe"
        )
    return declared


def _quantitative_review(
    lineage: Mapping[str, object],
) -> tuple[
    str,
    str,
    Path,
    dict[str, object],
    dict[str, object] | None,
]:
    """Load one pre-generated answer-free Reviewer result from the plan."""

    review = lineage.get("quantitative_review")
    if not isinstance(review, Mapping):
        raise LineageError("PROTECTION_REVIEW has no quantitative_review plan")
    review_id = review.get("review_id")
    case_id = review.get("case_id")
    result_path = review.get("result_path")
    if not isinstance(review_id, str) or not review_id:
        raise LineageError("quantitative_review has no review_id")
    if not isinstance(case_id, str) or not case_id:
        raise LineageError("quantitative_review has no case_id")
    if not isinstance(result_path, str) or not result_path:
        raise LineageError("quantitative_review has no result_path")
    path = Path(result_path)
    if not path.is_file():
        raise LineageError(f"quantitative review is missing: {path}")
    payload = _json(path)
    accounting = _review_accounting(payload)
    wrapped = payload.get("review")
    if isinstance(wrapped, Mapping):
        payload = dict(wrapped)
    reviews = payload.get("reviews")
    if not isinstance(reviews, list):
        raise LineageError("quantitative review result has no reviews list")
    matching_reviews = [
        value
        for value in reviews
        if isinstance(value, Mapping) and value.get("case_id") == case_id
    ]
    if len(matching_reviews) != 1:
        raise LineageError(
            "quantitative review result must contain exactly one review for "
            f"case_id {case_id!r}; found {len(matching_reviews)}"
        )
    payload = {
        **payload,
        "reviews": [dict(matching_reviews[0])],
    }
    return review_id, case_id, path, payload, accounting


def _review_accounting(
    payload: Mapping[str, object],
) -> dict[str, object] | None:
    """Normalize the explicit accounting in a Reviewer RESULT wrapper."""

    request = payload.get("request")
    if not isinstance(request, Mapping):
        return None
    accounting = request.get("accounting")
    if isinstance(accounting, Mapping):
        prompt_tokens = int(accounting.get("prompt_tokens", 0))
        completion_tokens = int(accounting.get("completion_tokens", 0))
        usage = request.get("response_usage")
        total_tokens = prompt_tokens + completion_tokens
        if isinstance(usage, Mapping) and usage.get("total_tokens") is not None:
            total_tokens = int(usage["total_tokens"])
        provider_cost = accounting.get("provider_cost_usd")
        if provider_cost is None and isinstance(usage, Mapping):
            provider_cost = usage.get("cost", 0)
        return {
            "provider_cost_usd": provider_cost or 0,
            "completed_request_count": 1,
            "total_tokens": total_tokens,
        }
    usage = request.get("response_usage")
    if isinstance(usage, Mapping):
        return {
            "provider_cost_usd": usage.get("cost", 0),
            "completed_request_count": 1,
            "total_tokens": int(
                usage.get(
                    "total_tokens",
                    int(usage.get("prompt_tokens", 0))
                    + int(usage.get("completion_tokens", 0)),
                )
            ),
        }
    return None


def _attempt_id(
    report: Mapping[str, object], arm: str, task_id: str
) -> str | None:
    activations = report.get("activations")
    if not isinstance(activations, Mapping):
        return None
    arm_value = activations.get(arm)
    if not isinstance(arm_value, Mapping):
        return None
    attempts = arm_value.get("attempts")
    if not isinstance(attempts, list):
        return None
    matches = [value for value in attempts if value.get("task_id") == task_id]
    if len(matches) != 1:
        return None
    value = matches[0].get("attempt_id")
    return value if isinstance(value, str) and value else None


def _tests_failed(report: Mapping[str, object], arm: str, task_id: str) -> int:
    summaries = report.get("summaries")
    if not isinstance(summaries, Mapping):
        raise LineageError("pilot report has no summaries")
    summary = summaries.get(arm)
    if not isinstance(summary, Mapping) or not isinstance(summary.get("scores"), list):
        raise LineageError(f"pilot report has no {arm!r} scores")
    matches = [item for item in summary["scores"] if item.get("task_id") == task_id]
    if len(matches) != 1 or not isinstance(matches[0].get("tests_failed"), int):
        raise LineageError(f"pilot report has no {arm!r}/{task_id!r} failure count")
    return int(matches[0]["tests_failed"])


def failed_properties(
    report_path: Path,
    report: Mapping[str, object],
    *,
    arm: str,
    task_id: str,
) -> frozenset[str]:
    """Read the trusted failed-property names adjacent to one pilot report."""

    if _tests_failed(report, arm, task_id) == 0:
        return frozenset()
    attempt_id = _attempt_id(report, arm, task_id)
    if attempt_id is None:
        raise LineageError(f"cannot locate {arm!r}/{task_id!r} verifier attempt")
    ctrf_path = report_path.parent / "attempts" / attempt_id / "verifier/ctrf.json"
    ctrf = _json(ctrf_path)
    results = ctrf.get("results")
    if not isinstance(results, Mapping) or not isinstance(results.get("tests"), list):
        raise LineageError(f"{ctrf_path} has no test results")
    return frozenset(
        str(item["name"])
        for item in results["tests"]
        if str(item.get("status", "")).lower() == "failed" and item.get("name")
    )


def property_set_safe(
    report_path: Path,
    report: Mapping[str, object],
    *,
    parent_arm: str,
    candidate_arm: str,
    task_id: str,
) -> bool:
    """Return whether the candidate retained every parent-passed property."""

    parent_failed = failed_properties(
        report_path, report, arm=parent_arm, task_id=task_id
    )
    candidate_failed = failed_properties(
        report_path, report, arm=candidate_arm, task_id=task_id
    )
    return candidate_failed.issubset(parent_failed)


def property_set_safe_from_reports(
    *,
    parent_report_path: Path,
    parent_report: Mapping[str, object],
    parent_arm: str,
    candidate_report_path: Path,
    candidate_report: Mapping[str, object],
    candidate_arm: str,
    task_id: str,
) -> bool:
    """Compare failed properties when parent and candidate ran separately."""

    parent_failed = failed_properties(
        parent_report_path,
        parent_report,
        arm=parent_arm,
        task_id=task_id,
    )
    candidate_failed = failed_properties(
        candidate_report_path,
        candidate_report,
        arm=candidate_arm,
        task_id=task_id,
    )
    return candidate_failed.issubset(parent_failed)


def failed_property_delta(
    report_path: Path,
    report: Mapping[str, object],
    *,
    parent_arm: str,
    candidate_arm: str,
    task_id: str,
) -> dict[str, object]:
    """Return one trusted parent--candidate failed-property delta."""

    parent_failed = failed_properties(
        report_path, report, arm=parent_arm, task_id=task_id
    )
    candidate_failed = failed_properties(
        report_path, report, arm=candidate_arm, task_id=task_id
    )
    return _failed_property_delta(parent_failed, candidate_failed)


def failed_property_delta_from_reports(
    *,
    parent_report_path: Path,
    parent_report: Mapping[str, object],
    parent_arm: str,
    candidate_report_path: Path,
    candidate_report: Mapping[str, object],
    candidate_arm: str,
    task_id: str,
) -> dict[str, object]:
    """Return a trusted delta when the parent comparator is reused."""

    parent_failed = failed_properties(
        parent_report_path,
        parent_report,
        arm=parent_arm,
        task_id=task_id,
    )
    candidate_failed = failed_properties(
        candidate_report_path,
        candidate_report,
        arm=candidate_arm,
        task_id=task_id,
    )
    return _failed_property_delta(parent_failed, candidate_failed)


def _failed_property_delta(
    parent_failed: frozenset[str], candidate_failed: frozenset[str]
) -> dict[str, object]:
    return {
        "parent_failed": sorted(parent_failed),
        "candidate_failed": sorted(candidate_failed),
        "resolved": sorted(parent_failed - candidate_failed),
        "introduced": sorted(candidate_failed - parent_failed),
        "persistent": sorted(parent_failed & candidate_failed),
    }


def _run_child(runner: Runner, argv: Sequence[str]) -> None:
    result = runner(argv)
    return_code = getattr(result, "returncode", 0)
    if return_code:
        raise RuntimeError(f"child runner exited with code {return_code}")


def run_controller(
    plan_path: str | Path,
    state_dir: str | Path,
    *,
    approve_external_run: bool = False,
    runner: Runner | None = None,
    selected_lineages: frozenset[str] | None = None,
    stop_after_stage: str | None = None,
) -> dict[str, object]:
    """Run replay and/or live stages until every selected lineage is terminal."""

    plan = _json(Path(plan_path))
    states_root = Path(state_dir)
    states_root.mkdir(parents=True, exist_ok=True)
    child_runner = runner or (
        lambda argv: subprocess.run(argv, check=False, text=True)
    )
    outputs: dict[str, object] = {}
    for lineage in plan.get("lineages", []):
        lineage_id = str(lineage["lineage_id"])
        if selected_lineages is not None and lineage_id not in selected_lineages:
            continue
        paused_this_run = False
        state_path = states_root / f"{lineage_id}.json"
        if state_path.is_file():
            state = load_lineage(state_path)
            if state.pop("stopped_after_stage", None) is not None:
                save_lineage(state_path, state)
        else:
            target = _stage(lineage, "target")
            protection = _stage(lineage, "protection")
            proposal = lineage.get("proposal")
            information_set_review = _information_set_review_spec(lineage)
            common = {
                "lineage_id": lineage_id,
                "parent_version": str(lineage["parent"]["version"]),
                "parent_path": str(lineage["parent"]["worker_dir"]),
                "target_task_id": str(target["task_id"]),
                "protection_task_id": str(protection["task_id"]),
                "worker_route": str(
                    plan["runtime"].get("worker_route", "declared-main0-route")
                ),
                "worker_budget": "normal",
                "cost_limit_usd": plan.get("limits", {}).get(
                    "provider_cost_usd", "1"
                ),
                "candidate_information_set_review": (
                    information_set_review is not None
                ),
                "quantitative_protection_review": (
                    lineage.get("quantitative_protection_review") is True
                ),
                "repeat_consistency_policy": lineage.get(
                    "repeat_consistency_policy", "aggregate_only"
                ),
                "retained_activation_token": lineage["parent"].get(
                    "retained_activation_token"
                ),
            }
            if isinstance(proposal, Mapping):
                state = new_proposal_lineage(**common)
            else:
                state = new_lineage(
                    **common,
                    candidate_version=str(lineage["candidate"]["version"]),
                    candidate_path=str(lineage["candidate"]["worker_dir"]),
                )
            save_lineage(state_path, state)

        if state.get("phase") == "PROPOSAL":
            proposal = lineage.get("proposal")
            if not isinstance(proposal, Mapping):
                raise LineageError("proposal phase has no proposal plan")
            report_path = _proposal_report_path(plan, lineage, proposal)
            if not report_path.is_file():
                if plan.get("mode") == "replay":
                    raise LineageError(f"replay proposal is missing: {report_path}")
                argv = build_proposal_argv(
                    plan,
                    lineage,
                    proposal,
                    approve_external_run=approve_external_run,
                )
                _run_child(child_runner, argv)
            report = _json(report_path)
            state = import_proposal_report(
                state,
                report=report,
                report_path=str(report_path),
                proposal_run_id=_proposal_run_id(plan, lineage, proposal),
                candidate_version=str(
                    proposal.get("candidate_version")
                    or _proposal_run_id(plan, lineage, proposal)
                ),
            )
            save_lineage(state_path, state)
            if (
                stop_after_stage == "proposal"
                and state.get("stopped_after_stage") != "proposal"
            ):
                state["stopped_after_stage"] = "proposal"
                save_lineage(state_path, state)
                paused_this_run = True

        while not paused_this_run and state.get("phase") in {
            "INFORMATION_SET_REVIEW",
            "TARGET",
            "REPEAT",
            "PROTECTION",
            "PROTECTION_REVIEW",
            "PROTECTION_REPEAT",
        }:
            if state.get("phase") == "INFORMATION_SET_REVIEW":
                review_spec = _information_set_review_spec(lineage)
                if review_spec is None:
                    raise LineageError(
                        "INFORMATION_SET_REVIEW has no enabled trusted plan"
                    )
                package, hold_reason = _candidate_information_set_review_package(
                    state, review_spec
                )
                if package is None:
                    state = hold_candidate_information_set_review(
                        state, reason=str(hold_reason)
                    )
                    save_lineage(state_path, state)
                    continue
                review_path, review_payload, review_accounting = (
                    _candidate_information_set_review_result(
                        plan,
                        review_spec,
                        package,
                        states_root,
                        approve_external_run=approve_external_run,
                        runner=child_runner,
                    )
                )
                state = import_candidate_information_set_review(
                    state,
                    review_id=str(review_spec["review_id"]),
                    review_path=str(review_path),
                    review_package=package,
                    review_payload=review_payload,
                    review_accounting=review_accounting,
                )
                save_lineage(state_path, state)
                if (
                    stop_after_stage == "information_set_review"
                    and state.get("stopped_after_stage")
                    != "information_set_review"
                ):
                    state["stopped_after_stage"] = "information_set_review"
                    save_lineage(state_path, state)
                    paused_this_run = True
                continue

            if state.get("phase") == "PROTECTION_REVIEW":
                (
                    review_id,
                    case_id,
                    review_path,
                    review_payload,
                    review_accounting,
                ) = _quantitative_review(lineage)
                state = import_quantitative_protection_review(
                    state,
                    review_id=review_id,
                    review_path=str(review_path),
                    review_payload=review_payload,
                    case_id=case_id,
                    review_accounting=review_accounting,
                )
                save_lineage(state_path, state)
                continue

            stage_name = str(state["phase"]).lower()
            stage = _stage(lineage, stage_name)
            if stage.get("benchmark") == "quantcodeeval":
                resolved_stage = _quantcodeeval_stage_with_live_result(
                    plan,
                    {
                        **lineage,
                        "parent": state["current_parent"],
                        "candidate": {
                            **dict(lineage.get("candidate", {})),
                            **state["candidate"],
                        },
                    },
                    stage,
                    approve_external_run=approve_external_run,
                    runner=child_runner,
                )
                comparison = _quantcodeeval_comparison(resolved_stage)
                property_safe = None
                quantitative_triage = None
                quantitative_review = (
                    state.get("quantitative_protection_review") is True
                )
                if stage_name in {"protection", "protection_repeat"} and (
                    quantitative_review
                ):
                    quantitative_triage = _quantitative_triage(stage)
                elif stage_name == "protection":
                    property_safe = _quantcodeeval_property_set_safe(
                        stage, comparison
                    )
                state = import_comparison_observation(
                    state,
                    stage=stage_name,
                    run_id=str(comparison["run_id"]),
                    task_id=str(comparison["task_id"]),
                    parent=comparison["parent"],
                    candidate=comparison["candidate"],
                    cost=comparison["cost"],
                    benchmark="quantcodeeval",
                    report_path=str(comparison["report_path"]),
                    provenance=comparison["provenance"],
                    relation_observed=stage.get("relation_observed"),
                    property_set_safe=property_safe,
                    quantitative_protection_triage=quantitative_triage,
                )
                save_lineage(state_path, state)
                if (
                    stop_after_stage == stage_name
                    and state.get("stopped_after_stage") != stage_name
                ):
                    state["stopped_after_stage"] = stage_name
                    save_lineage(state_path, state)
                    paused_this_run = True
                    break
                continue
            parent_comparator = _parent_comparator(stage, state)
            report_path = _report_path(plan, lineage, stage)
            if not report_path.is_file():
                if plan.get("mode") == "replay":
                    raise LineageError(f"replay report is missing: {report_path}")
                argv = build_child_argv(
                    plan,
                    {
                        **lineage,
                        "parent": state["current_parent"],
                        "candidate": state["candidate"],
                    },
                    stage,
                    approve_external_run=approve_external_run,
                )
                _run_child(child_runner, argv)
            child_report = _json(report_path)
            parent_arm = str(stage.get("parent_arm", "parent"))
            candidate_arm = str(stage.get("candidate_arm", "candidate"))
            report = child_report
            if parent_comparator is not None:
                report = compose_reused_parent_report(
                    parent_comparator=parent_comparator,
                    candidate_report=child_report,
                    parent_arm=parent_arm,
                    candidate_arm=candidate_arm,
                    task_id=str(stage["task_id"]),
                )
                selection_reference = stage.get("selection_reference")
                if isinstance(selection_reference, Mapping):
                    reuse = report.pop("parent_comparator_reuse")
                    reuse["reference_version"] = selection_reference[
                        "reference_version"
                    ]
                    reuse["current_parent_version"] = state["current_parent"][
                        "version"
                    ]
                    report["selection_reference_reuse"] = reuse
            if report.get("status") == "invalid_worker_execution":
                state = import_pilot_report(
                    state,
                    stage=stage_name,
                    report=report,
                    report_path=str(report_path),
                    parent_arm=parent_arm,
                    candidate_arm=candidate_arm,
                )
                save_lineage(state_path, state)
                if (
                    stop_after_stage == stage_name
                    and state.get("stopped_after_stage") != stage_name
                ):
                    state["stopped_after_stage"] = stage_name
                    save_lineage(state_path, state)
                    paused_this_run = True
                    break
                continue
            property_safe = None
            property_delta = None
            quantitative_triage = None
            quantitative_review = (
                state.get("quantitative_protection_review") is True
            )
            if stage_name in {"protection", "protection_repeat"} and (
                quantitative_review
            ):
                quantitative_triage = _quantitative_triage(stage)
            elif stage_name == "protection":
                if parent_comparator is None:
                    property_safe = property_set_safe(
                        report_path,
                        report,
                        parent_arm=parent_arm,
                        candidate_arm=candidate_arm,
                        task_id=str(stage["task_id"]),
                    )
                else:
                    _, parent_report_path, parent_report = parent_comparator
                    property_safe = property_set_safe_from_reports(
                        parent_report_path=parent_report_path,
                        parent_report=parent_report,
                        parent_arm=parent_arm,
                        candidate_report_path=report_path,
                        candidate_report=child_report,
                        candidate_arm=candidate_arm,
                        task_id=str(stage["task_id"]),
                    )
            if (
                stage_name in {"target", "repeat"}
                and state.get("repeat_consistency_policy")
                == "resolved_property_footprint_v1"
            ):
                if parent_comparator is None:
                    property_delta = failed_property_delta(
                        report_path,
                        report,
                        parent_arm=parent_arm,
                        candidate_arm=candidate_arm,
                        task_id=str(stage["task_id"]),
                    )
                else:
                    _, parent_report_path, parent_report = parent_comparator
                    property_delta = failed_property_delta_from_reports(
                        parent_report_path=parent_report_path,
                        parent_report=parent_report,
                        parent_arm=parent_arm,
                        candidate_report_path=report_path,
                        candidate_report=child_report,
                        candidate_arm=candidate_arm,
                        task_id=str(stage["task_id"]),
                    )
            state = import_pilot_report(
                state,
                stage=stage_name,
                report=report,
                report_path=str(report_path),
                parent_arm=parent_arm,
                candidate_arm=candidate_arm,
                relation_observed=stage.get("relation_observed"),
                property_delta=property_delta,
                property_set_safe=property_safe,
                quantitative_protection_triage=quantitative_triage,
            )
            save_lineage(state_path, state)
            if (
                stop_after_stage == stage_name
                and state.get("stopped_after_stage") != stage_name
            ):
                state["stopped_after_stage"] = stage_name
                save_lineage(state_path, state)
                paused_this_run = True
                break

        if state.get("phase") == "PROPOSE" and not paused_this_run:
            state = freeze_lineage(state)
            save_lineage(state_path, state)
        outputs[lineage_id] = state
    result = {
        "schema_version": 1,
        "controller_run_id": plan.get("controller_run_id"),
        "lineages": outputs,
    }
    (states_root / "CONTROLLER-RESULT.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--lineage", action="append")
    parser.add_argument(
        "--stop-after-stage",
        choices=(
            "proposal",
            "information_set_review",
            "target",
            "repeat",
            "protection",
            "protection_repeat",
        ),
    )
    parser.add_argument("--approve-external-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_controller(
        args.plan,
        args.state_dir,
        approve_external_run=args.approve_external_run,
        selected_lineages=(frozenset(args.lineage) if args.lineage else None),
        stop_after_stage=args.stop_after_stage,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
