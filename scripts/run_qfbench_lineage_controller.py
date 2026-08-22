#!/usr/bin/env python3
"""Run the thin Main-0 QFBench candidate lifecycle."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.qfbench_lineage import (  # noqa: E402
    LineageError,
    freeze_lineage,
    import_pilot_report,
    import_proposal_report,
    load_lineage,
    new_lineage,
    new_proposal_lineage,
    save_lineage,
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
        "--arm",
        f"parent={parent['worker_dir']}",
        "--arm",
        f"candidate={candidate['worker_dir']}",
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
    if stage.get("activation_token"):
        argv.extend(("--activation-token", str(stage["activation_token"])))
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
        else:
            target = _stage(lineage, "target")
            protection = _stage(lineage, "protection")
            proposal = lineage.get("proposal")
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

        while (
            not paused_this_run
            and state.get("phase") in {"TARGET", "REPEAT", "PROTECTION"}
        ):
            stage_name = str(state["phase"]).lower()
            stage = _stage(lineage, stage_name)
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
            report = _json(report_path)
            parent_arm = str(stage.get("parent_arm", "parent"))
            candidate_arm = str(stage.get("candidate_arm", "candidate"))
            property_safe = None
            if stage_name == "protection":
                property_safe = property_set_safe(
                    report_path,
                    report,
                    parent_arm=parent_arm,
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
                property_set_safe=property_safe,
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
        choices=("proposal", "target", "repeat", "protection"),
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
