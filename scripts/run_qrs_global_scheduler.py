#!/usr/bin/env python3
"""Run the deterministic global QRS scheduler over existing child CLIs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.qrs_global_scheduler import (  # noqa: E402
    GlobalSchedulerError,
    run_scheduler,
)
from qea.qfbench_trajectory_bank import build_trajectory_bank  # noqa: E402
from scripts.run_qfbench_lineage_controller import run_controller  # noqa: E402


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GlobalSchedulerError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _finite_nonnegative(value: object, *, label: str) -> Decimal:
    if isinstance(value, bool):
        raise GlobalSchedulerError(f"{label} is not a finite non-negative number")
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise GlobalSchedulerError(
            f"{label} is not a finite non-negative number"
        ) from exc
    if not normalized.is_finite() or normalized < 0:
        raise GlobalSchedulerError(f"{label} is not a finite non-negative number")
    return normalized


def _nonnegative_int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GlobalSchedulerError(f"{label} is not a non-negative integer")
    return value


def _bind_runner_inputs(
    method_path: Path, launch_path: Path, state_dir: Path
) -> tuple[dict[str, object], dict[str, object]]:
    """Freeze ordinary-JSON runner inputs and reject drift on resume."""

    method_source = method_path.expanduser().resolve()
    launch_source = launch_path.expanduser().resolve()
    method = _json(method_source)
    launch = _json(launch_source)
    declared_method = launch.get("method_plan_path")
    if not isinstance(declared_method, str) or not declared_method:
        raise GlobalSchedulerError("launch plan has no method_plan_path")
    declared_path = Path(declared_method).expanduser().resolve()
    if declared_path != method_source or _json(declared_path) != method:
        raise GlobalSchedulerError(
            "launch method_plan_path differs from the scheduler method input"
        )
    snapshot = {
        "schema_version": 1,
        "method_path": str(method_source),
        "launch_path": str(launch_source),
        "method": method,
        "launch": launch,
    }
    snapshot_path = state_dir.expanduser().resolve() / "RUNNER-INPUTS.json"
    if snapshot_path.is_file():
        if _json(snapshot_path) != snapshot:
            raise GlobalSchedulerError(
                "method or launch input changed after scheduler initialization"
            )
    else:
        _write_json(snapshot_path, snapshot)
    return method, launch


def _run(argv: Sequence[str]) -> None:
    result = subprocess.run(argv, check=False, text=True)
    if result.returncode:
        raise GlobalSchedulerError(
            f"child exited with code {result.returncode}: {argv[0]}"
        )


def _component_argv(
    action: Mapping[str, object], launch: Mapping[str, object]
) -> tuple[str, ...]:
    runtime = launch["runtime"]
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
        str(action["run_id"]),
        "--results-dir",
        str(runtime["results_dir"]),
        "--seed-worker",
        str(action["seed_worker"]),
    ]
    for arm in action["arms"]:
        argv.extend(("--arm", f"{arm['label']}={arm['worker_dir']}"))
    for task_id in action["task_ids"]:
        argv.extend(("--task-id", str(task_id)))
    argv.extend(
        (
            "--checkpoint-prefix",
            str(action["run_id"]),
            "--worker-concurrency",
            "1",
            "--verifier-concurrency",
            "1",
            "--approve-external-run",
        )
    )
    return tuple(argv)


def _protocol_audit(
    run_dir: Path, action: Mapping[str, object]
) -> dict[str, dict[str, bool]]:
    result = {
        str(arm["label"]): {str(task_id): False for task_id in action["task_ids"]}
        for arm in action["arms"]
    }
    checkpoint_to_label = {
        f"{action['run_id']}-{arm['label']}": str(arm["label"])
        for arm in action["arms"]
    }
    terminals: dict[str, dict[str, list[Path]]] = {
        label: {str(task_id): [] for task_id in action["task_ids"]}
        for label in result
    }
    for attempt_path in sorted(run_dir.glob("attempts/*/attempt.json")):
        attempt = _json(attempt_path)
        if attempt.get("run_id") != action.get("run_id"):
            continue
        checkpoint = str(attempt.get("checkpoint"))
        label = checkpoint_to_label.get(checkpoint)
        if label is None:
            for logical_checkpoint, logical_label in checkpoint_to_label.items():
                prefix = logical_checkpoint + "+infra-replacement-"
                ordinal = checkpoint.removeprefix(prefix)
                if checkpoint.startswith(prefix) and ordinal.isdigit():
                    label = logical_label
                    break
        task_id = attempt.get("task_id")
        if label is None or task_id not in result[label]:
            continue
        task_key = str(task_id)
        replacement_path = attempt_path.with_name("worker-attempt-replacement.json")
        if replacement_path.is_file() and not replacement_path.is_symlink():
            replacement = _json(replacement_path)
            if replacement.get("superseded_attempt_id") == attempt.get("attempt_id"):
                continue
        score_path = attempt_path.with_name("completed-score.json")
        if score_path.is_symlink() or not score_path.is_file():
            continue
        terminals[label][task_key].append(attempt_path)

    for label, tasks in terminals.items():
        for task_key, attempts in tasks.items():
            if len(attempts) != 1:
                continue
            attempt_path = attempts[0]
            attempt = _json(attempt_path)
            score = _json(attempt_path.with_name("completed-score.json"))
            if score.get("task_id") != task_key or attempt.get("task_id") != task_key:
                continue
            trace_path = attempt_path.with_name("research-state-trace.json")
            if trace_path.is_symlink() or not trace_path.is_file():
                continue
            trace = _json(trace_path)
            coverage = trace.get("coverage")
            events = trace.get("events")
            s6_complete = bool(
                isinstance(events, list)
                and sum(
                    isinstance(event, Mapping)
                    and event.get("stage") == "S6"
                    and event.get("action") == "COMPLETE"
                    for event in events
                )
                == 1
            )
            result[label][task_key] = bool(
                trace.get("schema_version") == 2
                and trace.get("record_kind") == "research_state_tool_call_index"
                and trace.get("telemetry_source") == "nexau_structured_tool_call"
                and trace.get("issues") == []
                and trace.get("malformed_calls") == []
                and isinstance(coverage, Mapping)
                and coverage.get("marker_protocol_complete") is True
                and s6_complete
            )
    return result


def _expected_component_plan(action: Mapping[str, object]) -> dict[str, object]:
    arms = action.get("arms")
    if not isinstance(arms, list):
        raise GlobalSchedulerError("component action has no arm list")
    expected_arms: list[dict[str, str]] = []
    for arm in arms:
        if not isinstance(arm, Mapping):
            raise GlobalSchedulerError("component action arm is invalid")
        label = arm.get("label")
        worker_dir = arm.get("worker_dir")
        if not isinstance(label, str) or not isinstance(worker_dir, str):
            raise GlobalSchedulerError("component action arm is incomplete")
        expected_arms.append(
            {"label": label, "worker_dir": str(Path(worker_dir).resolve())}
        )
    return {
        "run_id": action.get("run_id"),
        "task_ids": action.get("task_ids"),
        "checkpoint_prefix": action.get("run_id"),
        "arms": expected_arms,
    }


def _validate_component_plan(
    plan: Mapping[str, object], action: Mapping[str, object]
) -> None:
    expected = _expected_component_plan(action)
    for key in ("run_id", "task_ids", "checkpoint_prefix"):
        if plan.get(key) != expected[key]:
            raise GlobalSchedulerError(
                f"existing component pilot plan has different {key}"
            )
    raw_arms = plan.get("arms")
    if not isinstance(raw_arms, list):
        raise GlobalSchedulerError("existing component pilot plan has no arms")
    actual_arms: list[dict[str, str]] = []
    for arm in raw_arms:
        if not isinstance(arm, Mapping):
            raise GlobalSchedulerError("existing component pilot plan arm is invalid")
        label = arm.get("label")
        worker_dir = arm.get("worker_dir")
        if not isinstance(label, str) or not isinstance(worker_dir, str):
            raise GlobalSchedulerError("existing component pilot plan arm is incomplete")
        actual_arms.append(
            {"label": label, "worker_dir": str(Path(worker_dir).resolve())}
        )
    if actual_arms != expected["arms"]:
        raise GlobalSchedulerError(
            "existing component pilot plan has different exact Worker arms"
        )
    runtime = plan.get("effective_runtime")
    if not isinstance(runtime, Mapping):
        raise GlobalSchedulerError(
            "existing component pilot plan has no effective runtime"
        )
    if runtime.get("worker_concurrency") != 1 or runtime.get(
        "verifier_concurrency"
    ) != 1:
        raise GlobalSchedulerError(
            "existing component pilot plan has different concurrency"
        )


def _require_component_cost(cost: object) -> None:
    if not isinstance(cost, Mapping):
        raise GlobalSchedulerError("component result has no cost accounting")
    if cost.get("cost_complete") is not True:
        raise GlobalSchedulerError("component cost accounting is incomplete")
    if cost.get("provider_cost_is_lower_bound") is not False:
        raise GlobalSchedulerError("component provider cost is only a lower bound")
    _nonnegative_int(
        cost.get("completed_request_count"),
        label="component completed_request_count",
    )
    _nonnegative_int(cost.get("total_tokens"), label="component total_tokens")
    _finite_nonnegative(
        cost.get("provider_cost_usd"), label="component provider_cost_usd"
    )


def _component_result(
    action: Mapping[str, object],
    launch: Mapping[str, object],
    *,
    method: Mapping[str, object] | None = None,
    scheduler_state_path: Path | None = None,
) -> dict[str, object]:
    runtime = launch["runtime"]
    run_dir = Path(str(runtime["results_dir"])) / str(action["run_id"])
    report_path = run_dir / "pilot-report.json"
    if not report_path.is_file():
        if method is not None and scheduler_state_path is not None:
            _require_dispatch_capacity(action, method, scheduler_state_path)
        _run(_component_argv(action, launch))
    if report_path.is_symlink() or not report_path.is_file():
        raise GlobalSchedulerError("component pilot wrote no regular pilot-report.json")
    plan_path = run_dir / "pilot-plan.json"
    if plan_path.is_symlink() or not plan_path.is_file():
        raise GlobalSchedulerError("component pilot wrote no regular pilot-plan.json")
    _validate_component_plan(_json(plan_path), action)
    report = _json(report_path)
    if report.get("status") != "complete":
        raise GlobalSchedulerError("component report is not complete")
    if report.get("run_id") != action.get("run_id"):
        raise GlobalSchedulerError("component report run_id differs from its action")
    if report.get("task_ids") != action.get("task_ids"):
        raise GlobalSchedulerError("component report task vector differs from its action")
    _require_component_cost(report.get("cost"))
    report["accounting_complete"] = True
    report["report_path"] = str(report_path)
    report["scheduler_protocol"] = _protocol_audit(run_dir, action)
    return report


def _clean_accepted_claims(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value:
        raise GlobalSchedulerError("Review PASS has no Worker-visible claim inventory")
    claims: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, Mapping):
            raise GlobalSchedulerError("Worker-visible claim is not a JSON object")
        claim_id = raw.get("claim_id")
        claim = raw.get("claim")
        surfaces = raw.get("surfaces")
        basis_refs = raw.get("basis_refs")
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
        ):
            raise GlobalSchedulerError("Worker-visible claim inventory is incomplete")
        seen.add(claim_id)
        claims.append(
            {
                "claim_id": claim_id,
                "claim": claim,
                "surfaces": list(surfaces),
                "basis_refs": list(basis_refs),
            }
        )
    return claims


def _proposal_cost(report: Mapping[str, object]) -> dict[str, object]:
    throughput = report.get("candidate_generation_throughput")
    if not isinstance(throughput, Mapping):
        raise GlobalSchedulerError("panel proposal has no generation accounting")
    completed = _nonnegative_int(
        throughput.get("completed_request_count"),
        label="proposal completed_request_count",
    )
    delivered = _nonnegative_int(
        throughput.get("downstream_delivery_request_count"),
        label="proposal downstream_delivery_request_count",
    )
    noncompleted = _nonnegative_int(
        throughput.get("noncompleted_request_count"),
        label="proposal noncompleted_request_count",
    )
    billable = _nonnegative_int(
        throughput.get("billable_or_delivered_request_count"),
        label="proposal billable_or_delivered_request_count",
    )
    if noncompleted != 0 or billable != completed + delivered:
        raise GlobalSchedulerError("panel proposal accounting is incomplete")
    tokens = _nonnegative_int(
        throughput.get("total_tokens"), label="proposal total_tokens"
    )
    provider_cost = _finite_nonnegative(
        throughput.get("provider_cost_usd"), label="proposal provider_cost_usd"
    )
    return {
        "provider_cost_usd": provider_cost,
        "completed_requests": completed + delivered,
        "total_tokens": tokens,
    }


def _review_cost(
    wrapper: Mapping[str, object],
    *,
    review_id: object,
    candidate_version: object,
    verdict: str,
    coverage: str,
) -> dict[str, object]:
    if (
        wrapper.get("status") != "complete"
        or wrapper.get("worker_visible") is not False
        or wrapper.get("promotion_authority") is not False
    ):
        raise GlobalSchedulerError("candidate Review result is not a complete audit")
    review = wrapper.get("review")
    if not isinstance(review, Mapping):
        raise GlobalSchedulerError("candidate Review result has no review payload")
    review_coverage = review.get("coverage_review")
    if (
        review.get("review_id") != review_id
        or review.get("candidate_id") != candidate_version
        or review.get("overall_verdict") != verdict
        or not isinstance(review_coverage, Mapping)
        or review_coverage.get("verdict") != coverage
    ):
        raise GlobalSchedulerError("candidate Review payload differs from retained state")
    request = wrapper.get("request")
    if not isinstance(request, Mapping) or request.get("request_count") != 1:
        raise GlobalSchedulerError("candidate Review did not account for one request")
    accounting = request.get("accounting")
    if not isinstance(accounting, Mapping):
        raise GlobalSchedulerError("candidate Review request accounting is incomplete")
    prompt_tokens = _nonnegative_int(
        accounting.get("prompt_tokens"), label="Review prompt_tokens"
    )
    completion_tokens = _nonnegative_int(
        accounting.get("completion_tokens"), label="Review completion_tokens"
    )
    provider_cost = _finite_nonnegative(
        accounting.get("provider_cost_usd"), label="Review provider_cost_usd"
    )
    total_tokens = prompt_tokens + completion_tokens
    usage = request.get("response_usage")
    if isinstance(usage, Mapping) and usage.get("total_tokens") is not None:
        total_tokens = _nonnegative_int(
            usage.get("total_tokens"), label="Review response total_tokens"
        )
    return {
        "provider_cost_usd": provider_cost,
        "completed_requests": 1,
        "total_tokens": total_tokens,
    }


def _require_exact_panel_cost(
    state: Mapping[str, object],
    proposal_cost: Mapping[str, object],
    review_cost: Mapping[str, object] | None,
) -> dict[str, object]:
    expected_cost = Decimal(str(proposal_cost["provider_cost_usd"]))
    expected_requests = int(proposal_cost["completed_requests"])
    expected_tokens = int(proposal_cost["total_tokens"])
    if review_cost is not None:
        expected_cost += Decimal(str(review_cost["provider_cost_usd"]))
        expected_requests += int(review_cost["completed_requests"])
        expected_tokens += int(review_cost["total_tokens"])
    cost = state.get("cost")
    if not isinstance(cost, Mapping):
        raise GlobalSchedulerError("panel controller state has no cost accounting")
    actual_cost = _finite_nonnegative(
        cost.get("provider_cost_usd"), label="panel provider_cost_usd"
    )
    actual_requests = _nonnegative_int(
        cost.get("completed_requests"), label="panel completed_requests"
    )
    actual_tokens = _nonnegative_int(
        cost.get("total_tokens"), label="panel total_tokens"
    )
    if (
        actual_cost != expected_cost
        or actual_requests != expected_requests
        or actual_tokens != expected_tokens
    ):
        raise GlobalSchedulerError(
            "panel aggregate cost does not match proposal and Review accounting"
        )
    return {
        "provider_cost_usd": format(actual_cost, "f"),
        "completed_requests": actual_requests,
        "total_tokens": actual_tokens,
    }


def _retained_panel_state(state_path: Path) -> dict[str, object] | None:
    if not state_path.is_file():
        return None
    state = _json(state_path)
    observations = state.get("observations")
    if not isinstance(observations, Mapping):
        return None
    review = observations.get("information_set_review")
    if not isinstance(review, Mapping):
        if state.get("stopped_after_stage") == "information_set_review":
            raise GlobalSchedulerError(
                "retained panel stop marker has no information-set Review"
            )
        if (
            state.get("phase") in {"FROZEN", "HOLD_FOR_REFINE", "BUDGET_STOP"}
            and isinstance(state.get("proposal"), Mapping)
        ):
            return state
        return None
    if set(observations) != {"information_set_review"}:
        raise GlobalSchedulerError(
            "retained panel state already contains post-Review observations"
        )
    if state.get("stopped_after_stage") not in (None, "information_set_review"):
        raise GlobalSchedulerError("retained panel state has a different stop stage")
    return state


def _validate_public_sources(
    review_spec: Mapping[str, object], launch: Mapping[str, object]
) -> None:
    root_value = launch.get("public_contracts_root")
    if not isinstance(root_value, str) or not root_value:
        raise GlobalSchedulerError("launch plan has no public_contracts_root")
    root_path = Path(root_value).expanduser()
    root = root_path.resolve()
    if root_path.is_symlink() or not root.is_dir():
        raise GlobalSchedulerError("public contracts root is unavailable")
    sources = review_spec.get("public_sources")
    if not isinstance(sources, list) or not sources:
        raise GlobalSchedulerError("panel Review has no public sources")
    refs: set[str] = set()
    for source in sources:
        if not isinstance(source, Mapping):
            raise GlobalSchedulerError("panel Review public source is invalid")
        ref = source.get("ref")
        path_value = source.get("source_path")
        excerpt = source.get("excerpt")
        if (
            not isinstance(ref, str)
            or not ref
            or ref in refs
            or source.get("source_type") != "public_contract"
            or not isinstance(path_value, str)
            or not path_value
            or not isinstance(excerpt, str)
        ):
            raise GlobalSchedulerError("panel Review public source is incomplete")
        refs.add(ref)
        source_path = Path(path_value).expanduser()
        resolved = source_path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise GlobalSchedulerError(
                "panel Review public source is outside public_contracts_root"
            ) from exc
        if source_path.is_symlink() or resolved.is_symlink() or not resolved.is_file():
            raise GlobalSchedulerError("panel Review public source is unavailable")
        try:
            text = resolved.read_text(encoding="utf-8")
            if resolved.suffix == ".json":
                expected = json.dumps(
                    json.loads(text),
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
            else:
                expected = text
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GlobalSchedulerError(
                "cannot read panel Review public source"
            ) from exc
        if excerpt != expected:
            raise GlobalSchedulerError(
                "panel Review public excerpt differs from its source file"
            )


def _resolved_panel_plan(
    template: Mapping[str, object],
    *,
    action: Mapping[str, object],
    state_dir: Path,
) -> Path:
    current_parent = action.get("current_parent")
    if not isinstance(current_parent, Mapping):
        raise GlobalSchedulerError("panel action has no current parent")
    parent_version = current_parent.get("version")
    parent_worker = current_parent.get("worker_dir")
    if (
        not isinstance(parent_version, str)
        or not parent_version
        or not isinstance(parent_worker, str)
        or not parent_worker
        or Path(parent_worker).is_symlink()
        or not Path(parent_worker).is_dir()
    ):
        raise GlobalSchedulerError("panel current parent Worker is unavailable")
    resolved = deepcopy(dict(template))
    lineages = resolved.get("lineages")
    if not isinstance(lineages, list) or len(lineages) != 1:
        raise GlobalSchedulerError("panel controller template has no unique lineage")
    lineage = lineages[0]
    if not isinstance(lineage, dict):
        raise GlobalSchedulerError("panel controller template lineage is invalid")
    template_parent = lineage.get("parent")
    if (
        not isinstance(template_parent, Mapping)
        or not isinstance(template_parent.get("version"), str)
        or not isinstance(template_parent.get("worker_dir"), str)
    ):
        raise GlobalSchedulerError("panel controller template parent is invalid")
    lineage["parent"] = deepcopy(dict(current_parent))
    resolved_path = state_dir / "RESOLVED-CONTROLLER-PLAN.json"
    if resolved_path.is_file():
        if _json(resolved_path) != resolved:
            raise GlobalSchedulerError(
                "resolved panel controller plan changed after initialization"
            )
    else:
        _write_json(resolved_path, resolved)
    return resolved_path


def _panel_result(
    action: Mapping[str, object],
    launch: Mapping[str, object],
    *,
    method: Mapping[str, object] | None = None,
    scheduler_state_path: Path | None = None,
) -> dict[str, object]:
    plan_path = Path(str(action["controller_plan_path"]))
    plan = _json(plan_path)
    lineages = plan.get("lineages")
    if not isinstance(lineages, list) or len(lineages) != 1:
        raise GlobalSchedulerError("panel controller plan must have one lineage")
    lineage = lineages[0]
    if not isinstance(lineage, Mapping):
        raise GlobalSchedulerError("panel controller lineage is invalid")
    lineage_id = lineage.get("lineage_id")
    if (
        not isinstance(lineage_id, str)
        or not lineage_id
        or Path(lineage_id).name != lineage_id
    ):
        raise GlobalSchedulerError("panel controller lineage_id is unsafe")
    proposal = lineage.get("proposal")
    if not isinstance(proposal, Mapping):
        raise GlobalSchedulerError("panel controller plan has no proposal")
    if proposal.get("candidate_version") != action.get("proposal_version"):
        raise GlobalSchedulerError("panel controller plan has a different proposal version")
    trajectory_bank = action.get("trajectory_bank")
    panel_views = (
        trajectory_bank.get("panel_views")
        if isinstance(trajectory_bank, Mapping)
        else None
    )
    expected_evidence = (
        panel_views.get(str(action["panel_index"]))
        if isinstance(panel_views, Mapping)
        else None
    )
    if proposal.get("evidence") != expected_evidence:
        raise GlobalSchedulerError("panel proposal does not use its frozen bank view")
    review_spec = lineage.get("candidate_information_set_review")
    if (
        not isinstance(review_spec, Mapping)
        or review_spec.get("enabled") is not True
        or review_spec.get("feedback_mode") != "answer_free"
        or review_spec.get("optimize_only_sources") != []
    ):
        raise GlobalSchedulerError(
            "panel candidate Review must be answer-free with no optimize-only source"
        )
    _validate_public_sources(review_spec, launch)
    states_root = plan.get("states_root")
    if not isinstance(states_root, str) or not states_root:
        raise GlobalSchedulerError("panel controller plan has no states_root")
    state_dir = Path(states_root).expanduser().resolve()
    resolved_plan_path = _resolved_panel_plan(
        plan, action=action, state_dir=state_dir
    )
    state_path = state_dir / f"{lineage_id}.json"
    state = _retained_panel_state(state_path)
    if state is None:
        if method is not None and scheduler_state_path is not None:
            _require_dispatch_capacity(action, method, scheduler_state_path)
        result = run_controller(
            resolved_plan_path,
            state_dir,
            approve_external_run=True,
            stop_after_stage="information_set_review",
        )
        states = result.get("lineages")
        if (
            not isinstance(states, Mapping)
            or set(states) != {lineage_id}
            or not isinstance(states.get(lineage_id), Mapping)
        ):
            raise GlobalSchedulerError("panel controller returned no exact lineage")
        state = dict(states[lineage_id])
    if state.get("lineage_id") != lineage_id:
        raise GlobalSchedulerError("panel controller returned a different lineage")
    if state.get("current_parent") != action.get("current_parent"):
        raise GlobalSchedulerError("panel state is not bound to the current parent")
    state_proposal = state.get("proposal")
    if not isinstance(state_proposal, Mapping):
        raise GlobalSchedulerError("panel controller state has no proposal")
    if state_proposal.get("run_id") != proposal.get("live_run_id"):
        raise GlobalSchedulerError("panel state has a different proposal run")
    proposal_report_path = state_proposal.get("report_path")
    if not isinstance(proposal_report_path, str) or not proposal_report_path:
        raise GlobalSchedulerError("panel state has no proposal report")
    proposal_report = Path(proposal_report_path)
    if proposal_report.is_symlink() or not proposal_report.is_file():
        raise GlobalSchedulerError("panel proposal report is unavailable")
    proposal_payload = _json(proposal_report)
    proposal_accounting = _proposal_cost(proposal_payload)
    admission = proposal_payload.get("admission")
    if (
        proposal_payload.get("decision") != state_proposal.get("decision")
        or proposal_payload.get("candidate_dir")
        != state_proposal.get("candidate_dir")
        or not isinstance(admission, Mapping)
        or admission.get("admitted") != state_proposal.get("admitted")
    ):
        raise GlobalSchedulerError(
            "panel proposal report differs from retained proposal state"
        )
    phase = state.get("phase")
    observations = state.get("observations")
    if not isinstance(observations, Mapping):
        observations = {}
    if any(name != "information_set_review" for name in observations):
        raise GlobalSchedulerError("panel controller ran beyond the Review boundary")
    observation = observations.get("information_set_review")
    proposal_decision = state_proposal.get("decision")
    if proposal_decision not in {"ACT", "ABSTAIN"}:
        raise GlobalSchedulerError("panel proposal has no valid terminal decision")
    if proposal_decision == "ABSTAIN" and isinstance(observation, Mapping):
        raise GlobalSchedulerError("panel proposal ABSTAIN cannot have a Review")
    review_verdict = (
        str(observation.get("overall_verdict"))
        if isinstance(observation, Mapping)
        else "NON_PASS"
    )
    coverage_record = (
        observation.get("coverage_review")
        if isinstance(observation, Mapping)
        else None
    )
    coverage = (
        str(coverage_record.get("verdict"))
        if isinstance(coverage_record, Mapping)
        else "NON_PASS"
    )
    candidate = state.get("candidate")
    review_accounting = None
    review_path_value = None
    if isinstance(observation, Mapping):
        if observation.get("review_id") != review_spec.get("review_id"):
            raise GlobalSchedulerError("panel Review differs from its trusted plan")
        review_path_value = observation.get("review_path")
        if not isinstance(review_path_value, str) or not review_path_value:
            raise GlobalSchedulerError("panel Review observation has no result path")
        review_path = Path(review_path_value)
        if review_path.is_symlink() or not review_path.is_file():
            raise GlobalSchedulerError("panel Review result is unavailable")
        review_accounting = _review_cost(
            _json(review_path),
            review_id=observation.get("review_id"),
            candidate_version=(
                candidate.get("version") if isinstance(candidate, Mapping) else None
            ),
            verdict=review_verdict,
            coverage=coverage,
        )
    elif proposal_decision == "ABSTAIN":
        if (
            phase != "FROZEN"
            or state.get("status") != "abstained"
            or state_proposal.get("admitted") is not None
            or candidate is not None
            or state.get("accounted_review_ids") != []
        ):
            raise GlobalSchedulerError(
                "panel proposal ABSTAIN state is not a clean pre-Review terminal"
            )
        review_verdict = "NOT_RUN"
        coverage = "NOT_RUN"
    elif state_proposal.get("admitted") is not True:
        raise GlobalSchedulerError(
            "panel ACT did not produce an admitted candidate for Review"
        )
    cost = _require_exact_panel_cost(state, proposal_accounting, review_accounting)
    accepted_claims: list[dict[str, object]] = []
    if isinstance(observation, Mapping):
        if not isinstance(candidate, Mapping):
            raise GlobalSchedulerError("panel Review has no candidate snapshot")
        candidate_dir = candidate.get("worker_dir")
        if candidate.get("version") != action.get("proposal_version"):
            raise GlobalSchedulerError("panel Review returned a different candidate")
        if not isinstance(candidate_dir, str) or not candidate_dir:
            raise GlobalSchedulerError("panel Review candidate has no Worker")
        candidate_path = Path(candidate_dir)
        if candidate_path.is_symlink() or not candidate_path.is_dir():
            raise GlobalSchedulerError("panel Review Worker is unavailable")
        source_dir = candidate.get("source_worker_dir")
        proposal_candidate_dir = state_proposal.get("candidate_dir")
        source_path = Path(source_dir) if isinstance(source_dir, str) else None
        if (
            candidate.get("reviewed_candidate_dir") != candidate_dir
            or observation.get("reviewed_candidate_dir") != candidate_dir
            or source_path is None
            or source_path.is_symlink()
            or not source_path.is_dir()
            or not isinstance(proposal_candidate_dir, str)
            or source_path.resolve() != Path(proposal_candidate_dir).resolve()
        ):
            raise GlobalSchedulerError(
                "panel Review is not bound to the retained candidate snapshot"
            )
        accounted_reviews = state.get("accounted_review_ids")
        if (
            not isinstance(accounted_reviews, list)
            or observation.get("review_id") not in accounted_reviews
        ):
            raise GlobalSchedulerError("panel Review request is not accounted")
    if review_verdict == "PASS":
        if coverage != "PASS" or phase != "TARGET":
            raise GlobalSchedulerError(
                "panel Review PASS, coverage PASS, and TARGET phase are inconsistent"
            )
        candidate_review = candidate.get("information_set_review")
        if (
            not isinstance(candidate_review, Mapping)
            or candidate_review.get("overall_verdict") != "PASS"
            or candidate_review.get("review_id") != observation.get("review_id")
            or candidate_review.get("reviewed_candidate_dir") != candidate_dir
        ):
            raise GlobalSchedulerError(
                "panel Review is not bound to the retained candidate snapshot"
            )
        accepted_claims = _clean_accepted_claims(
            state_proposal.get("worker_visible_claims")
        )
    elif phase == "TARGET":
        raise GlobalSchedulerError("non-PASS panel Review cannot enter TARGET")
    return {
        "status": "complete",
        "accounting_complete": True,
        "proposal_decision": proposal_decision,
        "review_verdict": review_verdict,
        "coverage": coverage,
        "candidate": candidate,
        "reviewed_parent": state["current_parent"],
        "review_result_path": review_path_value,
        "accepted_claims": accepted_claims,
        "cost": cost,
    }


def _augment_panel_evidence_result(
    action: Mapping[str, object],
) -> dict[str, object]:
    from qea.qfbench_trajectory_bank import append_accepted_panel_history

    report_paths = action.get("matched_report_paths")
    if not isinstance(report_paths, list) or len(report_paths) != 2:
        raise GlobalSchedulerError(
            "accepted panel history requires two matched report paths"
        )
    paths = [Path(str(value)) for value in report_paths]
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise GlobalSchedulerError("accepted panel matched report is unavailable")
    task_ids = action.get("task_ids")
    if not isinstance(task_ids, list):
        raise GlobalSchedulerError("accepted panel action has no task vector")
    report = append_accepted_panel_history(
        source_evidence_root=Path(str(action["source_evidence_root"])),
        next_evidence_root=Path(str(action["next_evidence_root"])),
        panel_index=int(action["panel_index"]),
        family=str(action["family"]),
        task_ids=[str(value) for value in task_ids],
        accepted_claims=_clean_accepted_claims(action.get("accepted_claims")),
        matched_run_dirs=[path.parent for path in paths],
    )
    report["accounting_complete"] = True
    return report


def _carry_panel_evidence_result(
    action: Mapping[str, object],
) -> dict[str, object]:
    from qea.qfbench_trajectory_bank import carry_accepted_panel_history

    report = carry_accepted_panel_history(
        source_evidence_root=Path(str(action["source_evidence_root"])),
        next_evidence_root=Path(str(action["next_evidence_root"])),
    )
    report["accounting_complete"] = True
    return report


def _require_dispatch_capacity(
    action: Mapping[str, object],
    method: Mapping[str, object],
    scheduler_state_path: Path,
) -> None:
    """Reject a new billable child when the exact frozen cap is exhausted."""

    limits = method.get("limits")
    if not isinstance(limits, Mapping):
        raise GlobalSchedulerError("method plan has no scheduler limits")
    if scheduler_state_path.is_file():
        state = _json(scheduler_state_path)
    else:
        state = {
            "cost": {
                "provider_cost_usd": "0",
                "completed_requests": 0,
                "total_tokens": 0,
            },
            "qfbench_cells_accounted": 0,
            "accounted_action_ids": [],
        }
    cost = state.get("cost")
    if not isinstance(cost, Mapping):
        raise GlobalSchedulerError("scheduler state has no cost accounting")
    total_tokens = _nonnegative_int(
        cost.get("total_tokens"), label="scheduler total_tokens"
    )
    provider_cost = _finite_nonnegative(
        cost.get("provider_cost_usd"), label="scheduler provider_cost_usd"
    )
    maximum_tokens = _nonnegative_int(
        limits.get("maximum_total_tokens"), label="maximum_total_tokens"
    )
    maximum_cost = _finite_nonnegative(
        limits.get("maximum_provider_cost_usd"),
        label="maximum_provider_cost_usd",
    )
    if total_tokens >= maximum_tokens:
        raise GlobalSchedulerError("maximum_total_tokens exhausted before dispatch")
    if provider_cost >= maximum_cost:
        raise GlobalSchedulerError(
            "maximum_provider_cost_usd exhausted before dispatch"
        )
    kind = action.get("kind")
    if kind == "component_pilot":
        task_ids = action.get("task_ids")
        arms = action.get("arms")
        if not isinstance(task_ids, list) or not isinstance(arms, list):
            raise GlobalSchedulerError("component action has no exact cell vector")
        upcoming_cells = len(task_ids) * len(arms)
        current_cells = _nonnegative_int(
            state.get("qfbench_cells_accounted"),
            label="qfbench_cells_accounted",
        )
        for cap_name in (
            "maximum_qfbench_sessions_including_recovery",
            "maximum_all_worker_sessions",
        ):
            cap = _nonnegative_int(limits.get(cap_name), label=cap_name)
            if current_cells + upcoming_cells > cap:
                raise GlobalSchedulerError(f"{cap_name} exceeded before dispatch")
    elif kind == "panel_proposal_review":
        action_ids = state.get("accounted_action_ids")
        if not isinstance(action_ids, list):
            raise GlobalSchedulerError("scheduler action accounting is invalid")
        completed_panels = sum(
            isinstance(value, str) and value.endswith("-review")
            for value in action_ids
        )
        for cap_name in ("evolver_calls", "reviewer_calls"):
            cap = _nonnegative_int(limits.get(cap_name), label=cap_name)
            if completed_panels >= cap:
                raise GlobalSchedulerError(f"{cap_name} exhausted before dispatch")


def _build_bank_result(
    action: Mapping[str, object], launch: Mapping[str, object]
) -> dict[str, object]:
    report_paths = [Path(str(value)) for value in action["controller_reports"]]
    if any(not path.is_file() for path in report_paths):
        raise GlobalSchedulerError("trajectory bank input report is unavailable")
    run_dirs = sorted({path.parent.resolve() for path in report_paths}, key=str)
    report = build_trajectory_bank(
        manifest_path=Path(str(launch["qfbench_public_manifest"])),
        scheduler_plan_path=Path(str(launch["method_plan_path"])),
        public_contracts_root=Path(str(launch["public_contracts_root"])),
        h0_run_dirs=run_dirs,
        destination=Path(str(action["output_root"])),
        require_complete=True,
    )
    output_root = Path(str(action["output_root"]))
    index = _json(output_root / "evolver-answer-free" / "bank-index.json")
    indexed = [str(value["task_id"]) for value in index.get("tasks", [])]
    if set(indexed) != set(action["task_ids"]) or len(indexed) != len(
        action["task_ids"]
    ):
        raise GlobalSchedulerError("trajectory bank index differs from the frozen task set")
    panel_views = {
        str(value["panel_index"]): str(output_root / str(value["evidence_root"]))
        for value in index.get("panels", [])
    }
    result = {
        **report,
        "status": "complete" if report.get("complete") is True else "incomplete",
        "accounting_complete": True,
        "indexed_task_ids": list(action["task_ids"]),
        "sealed_task_ids_present": [],
        "panel_views": panel_views,
        "cost": {},
    }
    result_path = output_root / "TRAJECTORY-BANK-RESULT.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method-plan", type=Path, required=True)
    parser.add_argument("--launch-plan", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--stop-after-phase")
    parser.add_argument("--stop-after-panel", type=int)
    parser.add_argument("--approve-external-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.approve_external_run:
        raise GlobalSchedulerError(
            "live scheduler execution requires --approve-external-run"
        )
    method, launch = _bind_runner_inputs(
        args.method_plan, args.launch_plan, args.state_dir
    )
    scheduler_state_path = args.state_dir.expanduser().resolve() / "scheduler-state.json"

    def runner(action: Mapping[str, object]) -> Mapping[str, object]:
        if action["kind"] == "component_pilot":
            return _component_result(
                action,
                launch,
                method=method,
                scheduler_state_path=scheduler_state_path,
            )
        if action["kind"] == "panel_proposal_review":
            return _panel_result(
                action,
                launch,
                method=method,
                scheduler_state_path=scheduler_state_path,
            )
        if action["kind"] == "build_trajectory_bank":
            return _build_bank_result(action, launch)
        if action["kind"] == "augment_panel_evidence":
            return _augment_panel_evidence_result(action)
        if action["kind"] == "carry_panel_evidence":
            return _carry_panel_evidence_result(action)
        raise GlobalSchedulerError(f"unsupported child kind: {action['kind']}")

    result = run_scheduler(
        args.method_plan,
        args.launch_plan,
        args.state_dir,
        action_runner=runner,
        stop_after_phase=args.stop_after_phase,
        stop_after_panel=args.stop_after_panel,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
