"""Evidence-bound preparation and bookkeeping for the QuantCodeEval PGBHS canary."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Mapping

from .quantcodeeval_evidence import (
    PropertyFamilyProgress,
    QuantAttemptEvidence,
    QuantEvidenceAttemptSource,
    build_quantcodeeval_evidence,
)
from .quantcodeeval_pgbs import (
    CandidateAdmissionSummary,
    EvaluationRef,
    TaskPanelResult,
    initialize_pgbs_state,
    load_decision_payload,
    load_state_payload,
    record_pgbs_iteration,
    state_payload,
    validate_quant_decision,
)


class QuantCodeEvalExperimentError(ValueError):
    """The retained experiment evidence is incomplete or inconsistent."""


def _json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalExperimentError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise QuantCodeEvalExperimentError(f"{path} must contain a JSON object")
    return value


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _atomic_immutable_json(path: Path, value: object) -> None:
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
            raise QuantCodeEvalExperimentError(f"immutable record differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    if temporary.exists() or temporary.is_symlink():
        raise QuantCodeEvalExperimentError(f"stale partial record exists: {temporary}")
    temporary.write_bytes(payload)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _family(value: object) -> PropertyFamilyProgress:
    if not isinstance(value, Mapping):
        raise QuantCodeEvalExperimentError("property family must be an object")
    try:
        return PropertyFamilyProgress(
            total=value["total"],
            passed=value["passed"],
            failed=value["failed"],
            skipped=value["skipped"],
            errors=value["errors"],
        )
    except (KeyError, TypeError) as exc:
        raise QuantCodeEvalExperimentError("property family schema differs") from exc


def _panel_result(task_id: str, value: object) -> TaskPanelResult:
    if not isinstance(value, Mapping):
        raise QuantCodeEvalExperimentError("answer-free evidence must be an object")
    families = value.get("property_families")
    if not isinstance(families, Mapping):
        raise QuantCodeEvalExperimentError("answer-free property families are missing")
    return TaskPanelResult(
        task_id=task_id,
        official_reward=value.get("official_reward"),
        type_a=_family(families.get("type_a")),
        type_b=_family(families.get("type_b")),
    )


def _panel_identity(preflight: Mapping[str, object]) -> str:
    return _canonical_sha256(
        {
            "benchmark_commit": preflight["benchmark_commit"],
            "public_manifest_sha256": preflight["public_manifest_sha256"],
            "trusted_manifest_sha256": preflight["trusted_manifest_sha256"],
            "task_ids": preflight["task_ids"],
        }
    )


def _sampling_identity(preflight: Mapping[str, object]) -> str:
    return _canonical_sha256(
        {
            "model": preflight["model"],
            "required_provider": preflight["required_provider"],
            "allow_fallbacks": preflight["allow_fallbacks"],
            "split": preflight["split"],
            "runtime_identity_sha256": preflight["runtime_identity_sha256"],
            "worker_image_ref": preflight["worker_image_ref"],
            "verifier_image_ref": preflight["verifier_image_ref"],
            "proxy_image_ref": preflight["proxy_image_ref"],
            "worker_concurrency": preflight["worker_concurrency"],
            "verifier_concurrency": preflight["verifier_concurrency"],
        }
    )


def h0_evaluation_ref(h0_run_dir: str | Path) -> EvaluationRef:
    """Reconstruct the frozen two-task H0 reference without resampling it."""

    root = Path(h0_run_dir).resolve()
    preflight = _json(root / "H0-PREFLIGHT.json")
    result = _json(root / "H0-RESULT.json")
    if result.get("status") != "complete" or result.get("resampled") is not True:
        raise QuantCodeEvalExperimentError("H0 is not one completed seed sample")
    attempts: dict[str, str] = {}
    task_results: dict[str, TaskPanelResult] = {}
    raw_attempts = result.get("attempts")
    if not isinstance(raw_attempts, list):
        raise QuantCodeEvalExperimentError("H0 attempts are missing")
    for row in raw_attempts:
        if not isinstance(row, Mapping):
            raise QuantCodeEvalExperimentError("H0 attempt row must be an object")
        task_id = str(row.get("task_id"))
        attempts[task_id] = str(row.get("attempt_id"))
        task_results[task_id] = _panel_result(
            task_id, row.get("answer_free_evidence")
        )
    if tuple(sorted(task_results)) != tuple(sorted(preflight["task_ids"])):
        raise QuantCodeEvalExperimentError("H0 panel differs from preflight")
    return EvaluationRef(
        evaluation_id=str(result["evaluation_identity_sha256"]),
        checkpoint=str(preflight["checkpoint"]),
        worker_digest=str(preflight["worker_digest"]),
        panel_digest=_panel_identity(preflight),
        sampling_identity_digest=_sampling_identity(preflight),
        attempt_ids=attempts,
        task_results=task_results,
        resampled=False,
    )


def candidate_evaluation_ref(candidate_run_dir: str | Path) -> EvaluationRef:
    """Load one completed candidate panel, including explicit worker-zero skips."""

    root = Path(candidate_run_dir).resolve()
    plan = _json(root / "CANDIDATE-PREFLIGHT.json")
    result = _json(root / "CANDIDATE-RESULT.json")
    if result.get("status") != "complete":
        raise QuantCodeEvalExperimentError("candidate panel is incomplete")
    attempts: dict[str, str] = {}
    task_results: dict[str, TaskPanelResult] = {}
    for row in result.get("attempts", []):
        if not isinstance(row, Mapping):
            raise QuantCodeEvalExperimentError("candidate attempt row is invalid")
        task_id = str(row.get("task_id"))
        attempts[task_id] = str(row.get("attempt_id"))
        task_results[task_id] = _panel_result(
            task_id, row.get("answer_free_evidence")
        )
    return EvaluationRef(
        evaluation_id=str(result["evaluation_identity_sha256"]),
        checkpoint=str(plan["checkpoint"]),
        worker_digest=str(plan["candidate_worker_digest"]),
        panel_digest=str(plan["panel_identity_sha256"]),
        sampling_identity_digest=str(plan["sampling_identity_sha256"]),
        attempt_ids=attempts,
        task_results=task_results,
        resampled=False,
    )


def materialize_h0_attempt_sources(
    *, master_root: Path, h0_root: Path, evaluation: EvaluationRef
) -> tuple[QuantEvidenceAttemptSource, ...]:
    result = _json(h0_root / "H0-RESULT.json")
    by_task = {
        str(row["task_id"]): row
        for row in result["attempts"]
        if isinstance(row, Mapping)
    }
    sources: list[QuantEvidenceAttemptSource] = []
    for task_id in sorted(evaluation.task_results):
        attempt_id = evaluation.attempt_ids[task_id]
        row = by_task[task_id]
        attempt_root = h0_root / "attempts" / attempt_id
        inputs = master_root / "answer-free-inputs" / evaluation.evaluation_id / task_id
        summary_path = inputs / "answer-free-summary.json"
        _atomic_immutable_json(summary_path, row["answer_free_evidence"])
        execution = _json(attempt_root / "worker-execution.json")
        raw_summary = execution.get("summary")
        if not isinstance(raw_summary, Mapping):
            raise QuantCodeEvalExperimentError("worker process summary is missing")
        process_path = inputs / "process-summary.json"
        _atomic_immutable_json(
            process_path,
            {
                "turns": raw_summary.get("turns"),
                "tool_calls": raw_summary.get("tool_calls"),
                "tool_errors": raw_summary.get("tool_errors"),
                "files": raw_summary.get("files"),
                "elapsed_seconds": raw_summary.get("secs"),
                "timed_out": raw_summary.get("outcome") == "timed_out",
                "dependency_lock_sha256": raw_summary.get(
                    "dependency_lock_sha256"
                ),
            },
        )
        panel = evaluation.task_results[task_id]
        tags = row["answer_free_evidence"].get("diagnostic_tags", [])
        sources.append(
            QuantEvidenceAttemptSource(
                record=QuantAttemptEvidence(
                    task_id=task_id,
                    evaluation_id=evaluation.evaluation_id,
                    attempt_id=attempt_id,
                    checkpoint=evaluation.checkpoint,
                    worker_digest=evaluation.worker_digest,
                    official_reward=panel.official_reward,
                    type_a=panel.type_a,
                    type_b=panel.type_b,
                    diagnostic_tags=tuple(tags),
                ),
                answer_free_summary_path=summary_path,
                strategy_path=attempt_root / "artifacts" / "strategy.py",
                trace_path=attempt_root / "raw-trace.jsonl",
                final_text_path=attempt_root / "final.txt",
                process_summary_path=process_path,
            )
        )
    return tuple(sources)


def prepare_initial_pgbs(
    *,
    master_run_dir: str | Path,
    h0_run_dir: str | Path,
    public_task_roots: Mapping[str, str | Path],
) -> dict[str, object]:
    """Create immutable H0 reuse evidence, an ACT decision, and state at round zero."""

    root = Path(master_run_dir).resolve()
    h0_root = Path(h0_run_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    evaluation = h0_evaluation_ref(h0_root)
    state = initialize_pgbs_state(
        run_id=root.name,
        h0_worker_digest=evaluation.worker_digest,
        h0_evaluation=evaluation,
    )
    evidence = build_quantcodeeval_evidence(
        destination=root / "evidence" / "iteration-01",
        public_task_roots=public_task_roots,
        attempts=materialize_h0_attempt_sources(
            master_root=root, h0_root=h0_root, evaluation=evaluation
        ),
        current_evaluation_id=evaluation.evaluation_id,
    )
    instruction_ref = "tasks/T24/instruction.md"
    paper_ref = "tasks/T24/paper_text.md"
    prefix = f"tasks/T24/evaluations/{evaluation.evaluation_id}"
    official_ref = f"{prefix}/official_and_families.json"
    artifact_ref = f"{prefix}/strategy_ast_facts.json"
    trace_ref = f"{prefix}/trace_facts.json"
    accessed = {instruction_ref, paper_ref, official_ref, artifact_ref, trace_ref}
    for ref in sorted(accessed):
        if ref not in evidence.members:
            raise QuantCodeEvalExperimentError(f"required evidence member missing: {ref}")
    lines = (evidence.root / instruction_ref).read_text(encoding="utf-8").splitlines()
    start_line, end_line = 56, 66
    selected = "\n".join(lines[start_line - 1 : end_line]) + "\n"
    decision_payload = {
        "decision": "ACT",
        "failure_class": "quant_definition_estimation",
        "hypotheses_considered": [
            {
                "hypothesis_id": "percent_decimal_unit_contract",
                "mechanism": (
                    "The public 5.34 percent target may have been encoded as 5.34 "
                    "rather than 0.0534 while returns remain decimal-valued."
                ),
            },
            {
                "hypothesis_id": "formation_realization_lag",
                "mechanism": (
                    "The remaining failures may instead arise from a signal, weight, "
                    "or realized-return timing mismatch."
                ),
            },
        ],
        "selected_hypothesis_id": "percent_decimal_unit_contract",
        "evidence_refs": sorted(accessed),
        "public_clause_ref": {
            "path": instruction_ref,
            "start_line": start_line,
            "end_line": end_line,
            "text_sha256": hashlib.sha256(selected.encode("utf-8")).hexdigest(),
        },
        "artifact_fact_ref": artifact_ref,
        "trace_fact_ref": trace_ref,
        "evidence_basis": "type_a_clause_artifact_trace",
        "component": "systemprompt",
        "mutation_operator": "add",
        "prediction": {
            "task_id": "T24",
            "family": "type_a",
            "minimum_passed_delta": 1,
            "protected_task_ids": ["T16"],
        },
        "risk_tasks": ["T16"],
        "counterevidence": (
            "T24 also has one incomplete Type-B property and the public contract "
            "separately mandates a one-period position lag, so a unit correction "
            "need not explain every observed failure."
        ),
        "uncertainty": (
            "The diagnosis uses public instruction and paper text plus answer-free "
            "family counts and coarse artifact/process facts; checker identities, "
            "expected values, and raw verdict details were not exposed."
        ),
        "abstain_reason": None,
    }
    decision = validate_quant_decision(
        decision_payload,
        evidence_root=evidence.root,
        evidence_members=evidence.members,
        accessed_evidence_paths=accessed,
        allowed_task_ids=state.task_ids,
    )
    access_log = evidence.root / "access_log.jsonl"
    access_log.write_text(
        "".join(
            json.dumps({"iteration": 1, "path": ref}, sort_keys=True) + "\n"
            for ref in sorted(accessed)
        ),
        encoding="utf-8",
    )
    _atomic_immutable_json(root / "ITERATION-01-DECISION.json", asdict(decision))
    _atomic_immutable_json(root / "STATE.json", state_payload(state))
    preflight = {
        "schema_version": 1,
        "protocol": "quant_property_v1",
        "status": "preflight_complete",
        "run_id": root.name,
        "n_iters": 5,
        "task_ids": list(state.task_ids),
        "h0_evaluation_id": evaluation.evaluation_id,
        "h0_worker_digest": evaluation.worker_digest,
        "h0_resampled_by_search": False,
        "h0_source_run": h0_root.name,
        "evidence_sha256": evidence.sha256,
        "evidence_members": list(evidence.members),
        "decision": asdict(decision),
        "model_request_count": 0,
    }
    _atomic_immutable_json(root / "PGBHS-PREFLIGHT.json", preflight)
    return preflight


def _candidate_attempt_inputs(
    *, master_root: Path, candidate_root: Path, evaluation: EvaluationRef
) -> tuple[QuantEvidenceAttemptSource, ...]:
    result = _json(candidate_root / "CANDIDATE-RESULT.json")
    by_task = {
        str(row["task_id"]): row
        for row in result["attempts"]
        if isinstance(row, Mapping)
    }
    sources: list[QuantEvidenceAttemptSource] = []
    for task_id in sorted(evaluation.task_results):
        attempt_id = evaluation.attempt_ids[task_id]
        row = by_task[task_id]
        attempt_root = candidate_root / "attempts" / attempt_id
        inputs = master_root / "answer-free-inputs" / evaluation.evaluation_id / task_id
        summary_path = inputs / "answer-free-summary.json"
        _atomic_immutable_json(summary_path, row["answer_free_evidence"])
        process_path = inputs / "process-summary.json"
        execution_path = attempt_root / "worker-execution.json"
        if execution_path.is_file():
            execution = _json(execution_path).get("summary", {})
            if not isinstance(execution, Mapping):
                raise QuantCodeEvalExperimentError("candidate process summary is invalid")
            process = {
                "turns": execution.get("turns"),
                "tool_calls": execution.get("tool_calls"),
                "tool_errors": execution.get("tool_errors"),
                "files": execution.get("files"),
                "elapsed_seconds": execution.get("secs"),
                "timed_out": execution.get("outcome") == "timed_out",
                "dependency_lock_sha256": execution.get("dependency_lock_sha256"),
            }
        else:
            proxy_rows = sum(
                bool(line.strip())
                for line in (attempt_root / "proxy-audit.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            )
            process = {
                "turns": proxy_rows,
                "tool_calls": 0,
                "tool_errors": 0,
                "files": 0,
                "elapsed_seconds": None,
                "timed_out": False,
            }
        _atomic_immutable_json(process_path, process)
        panel = evaluation.task_results[task_id]
        sources.append(
            QuantEvidenceAttemptSource(
                record=QuantAttemptEvidence(
                    task_id=task_id,
                    evaluation_id=evaluation.evaluation_id,
                    attempt_id=attempt_id,
                    checkpoint=evaluation.checkpoint,
                    worker_digest=evaluation.worker_digest,
                    official_reward=panel.official_reward,
                    type_a=panel.type_a,
                    type_b=panel.type_b,
                    diagnostic_tags=tuple(
                        row["answer_free_evidence"].get("diagnostic_tags", [])
                    ),
                ),
                answer_free_summary_path=summary_path,
                strategy_path=(
                    attempt_root / "artifacts" / "strategy.py"
                    if (attempt_root / "artifacts" / "strategy.py").is_file()
                    else None
                ),
                trace_path=attempt_root / "raw-trace.jsonl",
                final_text_path=attempt_root / "final.txt",
                process_summary_path=process_path,
            )
        )
    return tuple(sources)


def record_iteration_one_and_prepare_second(
    *,
    master_run_dir: str | Path,
    candidate_run_dir: str | Path,
    public_task_roots: Mapping[str, str | Path],
) -> dict[str, object]:
    """Rollback the measured first candidate and prepare a resource-bounded ACT."""

    root = Path(master_run_dir).resolve()
    candidate_root = Path(candidate_run_dir).resolve()
    state = load_state_payload(_json(root / "STATE.json"))
    preflight = _json(root / "PGBHS-PREFLIGHT.json")
    decision = load_decision_payload(preflight["decision"])
    candidate = candidate_evaluation_ref(candidate_root)
    candidate_plan = _json(candidate_root / "CANDIDATE-PREFLIGHT.json")
    metrics = candidate_plan["mutation_metrics"]
    admission = CandidateAdmissionSummary(
        admitted=bool(candidate_plan["admission"]["admitted"]),
        nonempty_diff=int(metrics["changed_file_count"]) > 0,
        declared_roles_match_actual=bool(metrics["declared_roles_match_actual"]),
    )
    state = record_pgbs_iteration(
        state,
        evidence_digest=str(preflight["evidence_sha256"]),
        decision=decision,
        candidate_worker_digest=candidate.worker_digest,
        admission=admission,
        candidate_evaluation=candidate,
    )
    first = state.iterations[0]
    if first.selection is None or first.selection.search_parent_promoted:
        raise QuantCodeEvalExperimentError("first negative candidate was not rolled back")
    _atomic_immutable_json(
        root / "states" / "iteration-01.json", state_payload(state)
    )
    evidence = build_quantcodeeval_evidence(
        destination=root / "evidence" / "iteration-02",
        public_task_roots=public_task_roots,
        attempts=_candidate_attempt_inputs(
            master_root=root, candidate_root=candidate_root, evaluation=candidate
        ),
        current_evaluation_id=candidate.evaluation_id,
        history=(
            {
                "iteration": 1,
                "decision": "ACT",
                "failure_class": decision.failure_class.value,
                "candidate_evaluation_id": candidate.evaluation_id,
                "official_promoted": first.selection.official_promoted,
                "search_parent_promoted": first.selection.search_parent_promoted,
                "rollback_reason": first.rollback_reason,
            },
        ),
    )
    instruction_ref = "tasks/T24/instruction.md"
    prefix = f"tasks/T24/evaluations/{candidate.evaluation_id}"
    official_ref = f"{prefix}/official_and_families.json"
    trace_ref = f"{prefix}/trace_facts.json"
    final_ref = f"{prefix}/final_facts.json"
    accessed = {instruction_ref, official_ref, trace_ref, final_ref}
    lines = (evidence.root / instruction_ref).read_text(encoding="utf-8").splitlines()
    selected = "\n".join(lines[0:4]) + "\n"
    payload = {
        "decision": "ACT",
        "failure_class": "resource_termination",
        "hypotheses_considered": [
            {
                "hypothesis_id": "unbounded_analysis_without_checkpoint",
                "mechanism": (
                    "The worker completed 59 requests but reached its iteration limit "
                    "without retaining the required strategy.py artifact."
                ),
            },
            {
                "hypothesis_id": "provider_or_runtime_interruption",
                "mechanism": (
                    "The empty artifact may instead have resulted from provider or "
                    "sandbox interruption before a valid file could be written."
                ),
            },
        ],
        "selected_hypothesis_id": "unbounded_analysis_without_checkpoint",
        "evidence_refs": sorted(accessed),
        "public_clause_ref": {
            "path": instruction_ref,
            "start_line": 1,
            "end_line": 4,
            "text_sha256": hashlib.sha256(selected.encode("utf-8")).hexdigest(),
        },
        "artifact_fact_ref": official_ref.replace(
            "official_and_families.json", "artifact_manifest.json"
        ),
        "trace_fact_ref": trace_ref,
        "evidence_basis": "deterministic_interface",
        "component": "systemprompt",
        "mutation_operator": "add",
        "prediction": {
            "task_id": "T24",
            "family": "type_a",
            "minimum_passed_delta": 1,
            "protected_task_ids": ["T16"],
        },
        "risk_tasks": ["T16"],
        "counterevidence": (
            "All 59 T24 model requests were reconciled as completed and T16 used the "
            "same provider/runtime successfully, weakening the interruption hypothesis."
        ),
        "uncertainty": (
            "The worker content and hidden checker details remain unavailable; the "
            "next intervention therefore targets bounded process and early artifact "
            "retention, while retaining the prior public unit-contract clue."
        ),
        "abstain_reason": None,
    }
    artifact_ref = payload["artifact_fact_ref"]
    assert isinstance(artifact_ref, str)
    accessed.add(artifact_ref)
    decision_two = validate_quant_decision(
        payload,
        evidence_root=evidence.root,
        evidence_members=evidence.members,
        accessed_evidence_paths=accessed,
        allowed_task_ids=state.task_ids,
    )
    (evidence.root / "access_log.jsonl").write_text(
        "".join(
            json.dumps({"iteration": 2, "path": ref}, sort_keys=True) + "\n"
            for ref in sorted(accessed)
        ),
        encoding="utf-8",
    )
    _atomic_immutable_json(root / "ITERATION-02-DECISION.json", asdict(decision_two))
    result = {
        "schema_version": 1,
        "protocol": "quant_property_v1",
        "status": "iteration_02_preflight_complete",
        "iteration_01_state": state_payload(state),
        "iteration_02_evidence_sha256": evidence.sha256,
        "iteration_02_evidence_members": list(evidence.members),
        "iteration_02_decision": asdict(decision_two),
        "model_request_count": 0,
        "h0_resampled": False,
    }
    _atomic_immutable_json(root / "ITERATION-02-PREFLIGHT.json", result)
    return result


def record_iteration_two_and_prepare_third(
    *,
    master_run_dir: str | Path,
    h0_run_dir: str | Path,
    iteration_one_candidate_dir: str | Path,
    iteration_two_candidate_dir: str | Path,
    public_task_roots: Mapping[str, str | Path],
) -> dict[str, object]:
    """Rollback the over-constrained second candidate and prepare a minimal unit ACT."""

    root = Path(master_run_dir).resolve()
    h0_root = Path(h0_run_dir).resolve()
    candidate_one_root = Path(iteration_one_candidate_dir).resolve()
    candidate_two_root = Path(iteration_two_candidate_dir).resolve()
    state = load_state_payload(_json(root / "states" / "iteration-01.json"))
    preflight_two = _json(root / "ITERATION-02-PREFLIGHT.json")
    decision_two = load_decision_payload(preflight_two["iteration_02_decision"])
    candidate_two = candidate_evaluation_ref(candidate_two_root)
    candidate_plan = _json(candidate_two_root / "CANDIDATE-PREFLIGHT.json")
    metrics = candidate_plan["mutation_metrics"]
    state = record_pgbs_iteration(
        state,
        evidence_digest=str(preflight_two["iteration_02_evidence_sha256"]),
        decision=decision_two,
        candidate_worker_digest=candidate_two.worker_digest,
        admission=CandidateAdmissionSummary(
            admitted=bool(candidate_plan["admission"]["admitted"]),
            nonempty_diff=int(metrics["changed_file_count"]) > 0,
            declared_roles_match_actual=bool(metrics["declared_roles_match_actual"]),
        ),
        candidate_evaluation=candidate_two,
    )
    second = state.iterations[1]
    if second.selection is None or second.selection.search_parent_promoted:
        raise QuantCodeEvalExperimentError("second negative candidate was not rolled back")
    _atomic_immutable_json(
        root / "states" / "iteration-02.json", state_payload(state)
    )
    h0_evaluation = h0_evaluation_ref(h0_root)
    candidate_one = candidate_evaluation_ref(candidate_one_root)
    sources = (
        *materialize_h0_attempt_sources(
            master_root=root, h0_root=h0_root, evaluation=h0_evaluation
        ),
        *_candidate_attempt_inputs(
            master_root=root,
            candidate_root=candidate_one_root,
            evaluation=candidate_one,
        ),
        *_candidate_attempt_inputs(
            master_root=root,
            candidate_root=candidate_two_root,
            evaluation=candidate_two,
        ),
    )
    evidence = build_quantcodeeval_evidence(
        destination=root / "evidence" / "iteration-03",
        public_task_roots=public_task_roots,
        attempts=sources,
        current_evaluation_id=candidate_two.evaluation_id,
        history=(
            {
                "iteration": 1,
                "candidate_evaluation_id": candidate_one.evaluation_id,
                "official_promoted": False,
                "search_parent_promoted": False,
                "rollback_reason": state.iterations[0].rollback_reason,
            },
            {
                "iteration": 2,
                "candidate_evaluation_id": candidate_two.evaluation_id,
                "official_promoted": False,
                "search_parent_promoted": False,
                "rollback_reason": second.rollback_reason,
            },
        ),
    )
    instruction_ref = "tasks/T24/instruction.md"
    paper_ref = "tasks/T24/paper_text.md"
    h0_prefix = f"tasks/T24/evaluations/{h0_evaluation.evaluation_id}"
    one_prefix = f"tasks/T24/evaluations/{candidate_one.evaluation_id}"
    two_prefix = f"tasks/T24/evaluations/{candidate_two.evaluation_id}"
    artifact_ref = f"{h0_prefix}/strategy_ast_facts.json"
    trace_ref = f"{h0_prefix}/trace_facts.json"
    accessed = {
        instruction_ref,
        paper_ref,
        f"{h0_prefix}/official_and_families.json",
        f"{one_prefix}/official_and_families.json",
        f"{two_prefix}/official_and_families.json",
        artifact_ref,
        trace_ref,
    }
    lines = (evidence.root / instruction_ref).read_text(encoding="utf-8").splitlines()
    start_line, end_line = 56, 66
    selected = "\n".join(lines[start_line - 1 : end_line]) + "\n"
    payload = {
        "decision": "ACT",
        "failure_class": "quant_definition_estimation",
        "hypotheses_considered": [
            {
                "hypothesis_id": "minimal_percent_decimal_contract",
                "mechanism": (
                    "The strong H0 artifact exposes a 5.34 numeric constant while the "
                    "public paper writes 5.34 percent and decimal returns are used."
                ),
            },
            {
                "hypothesis_id": "retain_global_resource_restrictions",
                "mechanism": (
                    "The primary need may instead be strict global limits on lookup and "
                    "validation, despite their cross-task quality regressions."
                ),
            },
        ],
        "selected_hypothesis_id": "minimal_percent_decimal_contract",
        "evidence_refs": sorted(accessed),
        "public_clause_ref": {
            "path": instruction_ref,
            "start_line": start_line,
            "end_line": end_line,
            "text_sha256": hashlib.sha256(selected.encode("utf-8")).hexdigest(),
        },
        "artifact_fact_ref": artifact_ref,
        "trace_fact_ref": trace_ref,
        "evidence_basis": "type_a_clause_artifact_trace",
        "component": "systemprompt",
        "mutation_operator": "replace",
        "prediction": {
            "task_id": "T24",
            "family": "type_a",
            "minimum_passed_delta": 1,
            "protected_task_ids": ["T16"],
        },
        "risk_tasks": ["T16"],
        "counterevidence": (
            "H0 also has one incomplete T24 Type-B property, so a unit correction may "
            "not be sufficient for full official success."
        ),
        "uncertainty": (
            "Each worker panel is a single stochastic sample; the intervention is kept "
            "minimal because both broader prompts caused measured cross-task regressions."
        ),
        "abstain_reason": None,
    }
    decision_three = validate_quant_decision(
        payload,
        evidence_root=evidence.root,
        evidence_members=evidence.members,
        accessed_evidence_paths=accessed,
        allowed_task_ids=state.task_ids,
    )
    (evidence.root / "access_log.jsonl").write_text(
        "".join(
            json.dumps({"iteration": 3, "path": ref}, sort_keys=True) + "\n"
            for ref in sorted(accessed)
        ),
        encoding="utf-8",
    )
    _atomic_immutable_json(root / "ITERATION-03-DECISION.json", asdict(decision_three))
    result = {
        "schema_version": 1,
        "protocol": "quant_property_v1",
        "status": "iteration_03_preflight_complete",
        "iteration_02_state": state_payload(state),
        "iteration_03_evidence_sha256": evidence.sha256,
        "iteration_03_evidence_members": list(evidence.members),
        "iteration_03_decision": asdict(decision_three),
        "model_request_count": 0,
        "h0_resampled": False,
        "candidate_source_identity_gap_iteration_02": True,
    }
    _atomic_immutable_json(root / "ITERATION-03-PREFLIGHT.json", result)
    return result


def record_iteration_three_and_prepare_fourth(
    *,
    master_run_dir: str | Path,
    h0_run_dir: str | Path,
    iteration_three_candidate_dir: str | Path,
    public_task_roots: Mapping[str, str | Path],
) -> dict[str, object]:
    """Record the empty-response third sample and prepare one minimal unit rule."""

    root = Path(master_run_dir).resolve()
    h0_root = Path(h0_run_dir).resolve()
    candidate_root = Path(iteration_three_candidate_dir).resolve()
    state = load_state_payload(_json(root / "states" / "iteration-02.json"))
    preflight_three = _json(root / "ITERATION-03-PREFLIGHT.json")
    decision_three = load_decision_payload(preflight_three["iteration_03_decision"])
    candidate = candidate_evaluation_ref(candidate_root)
    candidate_plan = _json(candidate_root / "CANDIDATE-PREFLIGHT.json")
    metrics = candidate_plan["mutation_metrics"]
    state = record_pgbs_iteration(
        state,
        evidence_digest=str(preflight_three["iteration_03_evidence_sha256"]),
        decision=decision_three,
        candidate_worker_digest=candidate.worker_digest,
        admission=CandidateAdmissionSummary(
            admitted=bool(candidate_plan["admission"]["admitted"]),
            nonempty_diff=int(metrics["changed_file_count"]) > 0,
            declared_roles_match_actual=bool(metrics["declared_roles_match_actual"]),
        ),
        candidate_evaluation=candidate,
    )
    third = state.iterations[2]
    if third.selection is None or third.selection.search_parent_promoted:
        raise QuantCodeEvalExperimentError("third worker-zero candidate was not rolled back")
    _atomic_immutable_json(
        root / "states" / "iteration-03.json", state_payload(state)
    )
    h0_evaluation = h0_evaluation_ref(h0_root)
    evidence = build_quantcodeeval_evidence(
        destination=root / "evidence" / "iteration-04",
        public_task_roots=public_task_roots,
        attempts=(
            *materialize_h0_attempt_sources(
                master_root=root, h0_root=h0_root, evaluation=h0_evaluation
            ),
            *_candidate_attempt_inputs(
                master_root=root,
                candidate_root=candidate_root,
                evaluation=candidate,
            ),
        ),
        current_evaluation_id=candidate.evaluation_id,
        history=tuple(
            {
                "iteration": item.iteration,
                "candidate_evaluation_id": (
                    item.candidate_evaluation.evaluation_id
                    if item.candidate_evaluation is not None
                    else None
                ),
                "official_promoted": (
                    item.selection.official_promoted if item.selection else False
                ),
                "search_parent_promoted": (
                    item.selection.search_parent_promoted if item.selection else False
                ),
                "rollback_reason": item.rollback_reason,
            }
            for item in state.iterations
        ),
    )
    instruction_ref = "tasks/T24/instruction.md"
    paper_ref = "tasks/T24/paper_text.md"
    h0_prefix = f"tasks/T24/evaluations/{h0_evaluation.evaluation_id}"
    current_prefix = f"tasks/T24/evaluations/{candidate.evaluation_id}"
    artifact_ref = f"{h0_prefix}/strategy_ast_facts.json"
    trace_ref = f"{h0_prefix}/trace_facts.json"
    accessed = {
        instruction_ref,
        paper_ref,
        f"{h0_prefix}/official_and_families.json",
        f"{current_prefix}/official_and_families.json",
        f"{current_prefix}/process_facts.json",
        artifact_ref,
        trace_ref,
    }
    lines = (evidence.root / instruction_ref).read_text(encoding="utf-8").splitlines()
    start_line, end_line = 56, 66
    selected = "\n".join(lines[start_line - 1 : end_line]) + "\n"
    payload = {
        "decision": "ACT",
        "failure_class": "quant_definition_estimation",
        "hypotheses_considered": [
            {
                "hypothesis_id": "single_unit_rule",
                "mechanism": (
                    "H0 remains one property short in each family and exposes 5.34 as "
                    "a raw numeric constant despite the public paper's percent notation."
                ),
            },
            {
                "hypothesis_id": "model_reasoning_exhaustion",
                "mechanism": (
                    "The prior T24 sample ended with 32,000 reasoning tokens and no "
                    "content or tool call, so provider/model behavior may dominate."
                ),
            },
        ],
        "selected_hypothesis_id": "single_unit_rule",
        "evidence_refs": sorted(accessed),
        "public_clause_ref": {
            "path": instruction_ref,
            "start_line": start_line,
            "end_line": end_line,
            "text_sha256": hashlib.sha256(selected.encode("utf-8")).hexdigest(),
        },
        "artifact_fact_ref": artifact_ref,
        "trace_fact_ref": trace_ref,
        "evidence_basis": "type_a_clause_artifact_trace",
        "component": "systemprompt",
        "mutation_operator": "replace",
        "prediction": {
            "task_id": "T24",
            "family": "type_a",
            "minimum_passed_delta": 1,
            "protected_task_ids": ["T16"],
        },
        "risk_tasks": ["T16"],
        "counterevidence": (
            "Iteration 3 did not reach a tool call on T24, so it did not behaviorally "
            "test the unit rule; model reasoning exhaustion remains a competing cause."
        ),
        "uncertainty": (
            "This is a final bounded mechanism probe with a one-sentence mutation; "
            "failure will not be reinterpreted as evidence that the unit rule is false."
        ),
        "abstain_reason": None,
    }
    decision_four = validate_quant_decision(
        payload,
        evidence_root=evidence.root,
        evidence_members=evidence.members,
        accessed_evidence_paths=accessed,
        allowed_task_ids=state.task_ids,
    )
    (evidence.root / "access_log.jsonl").write_text(
        "".join(
            json.dumps({"iteration": 4, "path": ref}, sort_keys=True) + "\n"
            for ref in sorted(accessed)
        ),
        encoding="utf-8",
    )
    _atomic_immutable_json(root / "ITERATION-04-DECISION.json", asdict(decision_four))
    result = {
        "schema_version": 1,
        "protocol": "quant_property_v1",
        "status": "iteration_04_preflight_complete",
        "iteration_03_state": state_payload(state),
        "iteration_04_evidence_sha256": evidence.sha256,
        "iteration_04_evidence_members": list(evidence.members),
        "iteration_04_decision": asdict(decision_four),
        "model_request_count": 0,
        "h0_resampled": False,
    }
    _atomic_immutable_json(root / "ITERATION-04-PREFLIGHT.json", result)
    return result


def record_iteration_four_and_prepare_fifth(
    *,
    master_run_dir: str | Path,
    h0_run_dir: str | Path,
    iteration_four_candidate_dir: str | Path,
    public_task_roots: Mapping[str, str | Path],
) -> dict[str, object]:
    """Rollback the fourth max-iteration sample and prepare one final ACT."""

    root = Path(master_run_dir).resolve()
    h0_root = Path(h0_run_dir).resolve()
    candidate_root = Path(iteration_four_candidate_dir).resolve()
    state = load_state_payload(_json(root / "states" / "iteration-03.json"))
    preflight_four = _json(root / "ITERATION-04-PREFLIGHT.json")
    decision_four = load_decision_payload(preflight_four["iteration_04_decision"])
    candidate = candidate_evaluation_ref(candidate_root)
    candidate_plan = _json(candidate_root / "CANDIDATE-PREFLIGHT.json")
    metrics = candidate_plan["mutation_metrics"]
    state = record_pgbs_iteration(
        state,
        evidence_digest=str(preflight_four["iteration_04_evidence_sha256"]),
        decision=decision_four,
        candidate_worker_digest=candidate.worker_digest,
        admission=CandidateAdmissionSummary(
            admitted=bool(candidate_plan["admission"]["admitted"]),
            nonempty_diff=int(metrics["changed_file_count"]) > 0,
            declared_roles_match_actual=bool(metrics["declared_roles_match_actual"]),
        ),
        candidate_evaluation=candidate,
    )
    fourth = state.iterations[3]
    if fourth.selection is None or fourth.selection.search_parent_promoted:
        raise QuantCodeEvalExperimentError("fourth max-iteration candidate was not rolled back")
    if candidate.task_results["T24"].type_a.skipped != 7 or candidate.task_results[
        "T24"
    ].type_b.skipped != 10:
        raise QuantCodeEvalExperimentError("fourth candidate is not the artifact-zero panel")
    _atomic_immutable_json(root / "states" / "iteration-04.json", state_payload(state))

    h0_evaluation = h0_evaluation_ref(h0_root)
    evidence = build_quantcodeeval_evidence(
        destination=root / "evidence" / "iteration-05",
        public_task_roots=public_task_roots,
        attempts=(
            *materialize_h0_attempt_sources(
                master_root=root, h0_root=h0_root, evaluation=h0_evaluation
            ),
            *_candidate_attempt_inputs(
                master_root=root,
                candidate_root=candidate_root,
                evaluation=candidate,
            ),
        ),
        current_evaluation_id=candidate.evaluation_id,
        history=tuple(
            {
                "iteration": item.iteration,
                "candidate_evaluation_id": (
                    item.candidate_evaluation.evaluation_id
                    if item.candidate_evaluation is not None
                    else None
                ),
                "official_promoted": (
                    item.selection.official_promoted if item.selection else False
                ),
                "search_parent_promoted": (
                    item.selection.search_parent_promoted if item.selection else False
                ),
                "rollback_reason": item.rollback_reason,
            }
            for item in state.iterations
        ),
    )
    instruction_ref = "tasks/T24/instruction.md"
    h0_prefix = f"tasks/T24/evaluations/{h0_evaluation.evaluation_id}"
    current_prefix = f"tasks/T24/evaluations/{candidate.evaluation_id}"
    artifact_ref = f"{current_prefix}/artifact_manifest.json"
    trace_ref = f"{current_prefix}/process_facts.json"
    accessed = {
        instruction_ref,
        f"{h0_prefix}/official_and_families.json",
        f"{current_prefix}/official_and_families.json",
        artifact_ref,
        trace_ref,
    }
    lines = (evidence.root / instruction_ref).read_text(encoding="utf-8").splitlines()
    selected = "\n".join(lines[0:4]) + "\n"
    decision_five = validate_quant_decision(
        {
            "decision": "ACT",
            "failure_class": "resource_termination",
            "hypotheses_considered": [
                {
                    "hypothesis_id": "artifact_checkpoint_omission",
                    "mechanism": (
                        "The fourth T24 worker completed 59 requests and reached the "
                        "iteration limit without ever retaining strategy.py."
                    ),
                },
                {
                    "hypothesis_id": "stochastic_model_noncompliance",
                    "mechanism": (
                        "The model may ignore any prompt-level checkpoint rule, making "
                        "the failure irreducible without executable middleware."
                    ),
                },
            ],
            "selected_hypothesis_id": "artifact_checkpoint_omission",
            "evidence_refs": sorted(accessed),
            "public_clause_ref": {
                "path": instruction_ref,
                "start_line": 1,
                "end_line": 4,
                "text_sha256": hashlib.sha256(selected.encode("utf-8")).hexdigest(),
            },
            "artifact_fact_ref": artifact_ref,
            "trace_fact_ref": trace_ref,
            "evidence_basis": "deterministic_interface",
            "component": "systemprompt",
            "mutation_operator": "replace",
            "prediction": {
                "task_id": "T24",
                "family": "type_a",
                "minimum_passed_delta": 1,
                "protected_task_ids": ["T16"],
            },
            "risk_tasks": ["T16"],
            "counterevidence": (
                "The broader iteration-2 resource prompt retained artifacts on both "
                "tasks but regressed their correctness, so process constraints can "
                "damage solution quality."
            ),
            "uncertainty": (
                "The final mutation is restricted to early checkpoint retention plus "
                "the public unit rule; a failure will remain a negative mechanism result."
            ),
            "abstain_reason": None,
        },
        evidence_root=evidence.root,
        evidence_members=evidence.members,
        accessed_evidence_paths=accessed,
        allowed_task_ids=state.task_ids,
    )
    (evidence.root / "access_log.jsonl").write_text(
        "".join(
            json.dumps({"iteration": 5, "path": ref}, sort_keys=True) + "\n"
            for ref in sorted(accessed)
        ),
        encoding="utf-8",
    )
    _atomic_immutable_json(root / "ITERATION-05-DECISION.json", asdict(decision_five))
    result = {
        "schema_version": 1,
        "protocol": "quant_property_v1",
        "status": "iteration_05_preflight_complete",
        "iteration_04_state": state_payload(state),
        "iteration_05_evidence_sha256": evidence.sha256,
        "iteration_05_evidence_members": list(evidence.members),
        "iteration_05_decision": asdict(decision_five),
        "model_request_count": 0,
        "h0_resampled": False,
    }
    _atomic_immutable_json(root / "ITERATION-05-PREFLIGHT.json", result)
    return result


def record_iteration_four_and_finalize_success(
    *,
    master_run_dir: str | Path,
    h0_run_dir: str | Path,
    iteration_four_candidate_dir: str | Path,
    public_task_roots: Mapping[str, str | Path],
) -> dict[str, object]:
    """Promote a successful fourth candidate and close round five by ABSTAIN.

    The fifth round deliberately performs no model sampling.  Once the fixed
    engineering panel has no observed failure, another mutation has no
    answer-free failure target.  The terminal ABSTAIN preserves that fact while
    recording that one stochastic panel is not evidence of generalization.
    """

    root = Path(master_run_dir).resolve()
    h0_root = Path(h0_run_dir).resolve()
    candidate_root = Path(iteration_four_candidate_dir).resolve()
    state = load_state_payload(_json(root / "states" / "iteration-03.json"))
    preflight_four = _json(root / "ITERATION-04-PREFLIGHT.json")
    decision_four = load_decision_payload(preflight_four["iteration_04_decision"])
    candidate = candidate_evaluation_ref(candidate_root)
    candidate_plan = _json(candidate_root / "CANDIDATE-PREFLIGHT.json")
    metrics = candidate_plan["mutation_metrics"]
    state = record_pgbs_iteration(
        state,
        evidence_digest=str(preflight_four["iteration_04_evidence_sha256"]),
        decision=decision_four,
        candidate_worker_digest=candidate.worker_digest,
        admission=CandidateAdmissionSummary(
            admitted=bool(candidate_plan["admission"]["admitted"]),
            nonempty_diff=int(metrics["changed_file_count"]) > 0,
            declared_roles_match_actual=bool(metrics["declared_roles_match_actual"]),
        ),
        candidate_evaluation=candidate,
    )
    fourth = state.iterations[3]
    if (
        fourth.selection is None
        or not fourth.selection.official_promoted
        or not fourth.selection.search_parent_promoted
        or any(
            result.official_reward != 1.0
            for result in candidate.task_results.values()
        )
    ):
        raise QuantCodeEvalExperimentError(
            "fourth candidate is not a successful fixed-panel incumbent"
        )
    _atomic_immutable_json(root / "states" / "iteration-04.json", state_payload(state))

    h0_evaluation = h0_evaluation_ref(h0_root)
    evidence = build_quantcodeeval_evidence(
        destination=root / "evidence" / "iteration-05",
        public_task_roots=public_task_roots,
        attempts=(
            *materialize_h0_attempt_sources(
                master_root=root, h0_root=h0_root, evaluation=h0_evaluation
            ),
            *_candidate_attempt_inputs(
                master_root=root,
                candidate_root=candidate_root,
                evaluation=candidate,
            ),
        ),
        current_evaluation_id=candidate.evaluation_id,
        history=tuple(
            {
                "iteration": item.iteration,
                "candidate_evaluation_id": (
                    item.candidate_evaluation.evaluation_id
                    if item.candidate_evaluation is not None
                    else None
                ),
                "official_promoted": (
                    item.selection.official_promoted if item.selection else False
                ),
                "search_parent_promoted": (
                    item.selection.search_parent_promoted if item.selection else False
                ),
                "rollback_reason": item.rollback_reason,
            }
            for item in state.iterations
        ),
    )
    t16_prefix = f"tasks/T16/evaluations/{candidate.evaluation_id}"
    t24_prefix = f"tasks/T24/evaluations/{candidate.evaluation_id}"
    accessed = {
        f"{t16_prefix}/official_and_families.json",
        f"{t24_prefix}/official_and_families.json",
        f"{t24_prefix}/process_facts.json",
    }
    decision_five = validate_quant_decision(
        {
            "decision": "ABSTAIN",
            "failure_class": "unknown",
            "hypotheses_considered": [
                {
                    "hypothesis_id": "observed_panel_resolved",
                    "mechanism": (
                        "The fourth candidate completed every Type-A and Type-B "
                        "property on both tasks, leaving no observed failure target."
                    ),
                },
                {
                    "hypothesis_id": "stochastic_replication_uncertainty",
                    "mechanism": (
                        "The successful candidate is one stochastic model sample and "
                        "may not reproduce or transfer beyond the fixed canary panel."
                    ),
                },
            ],
            "selected_hypothesis_id": None,
            "evidence_refs": sorted(accessed),
            "public_clause_ref": None,
            "artifact_fact_ref": None,
            "trace_fact_ref": None,
            "evidence_basis": None,
            "component": None,
            "mutation_operator": None,
            "prediction": None,
            "risk_tasks": ["T16", "T24"],
            "counterevidence": (
                "H0 failed T24 and the first three admitted mutations were rolled "
                "back, so the result does not establish a generally reliable policy."
            ),
            "uncertainty": (
                "No independent model-seed repetition or held-out task was evaluated "
                "inside this engineering canary."
            ),
            "abstain_reason": (
                "The fixed panel has no remaining observed failure to localize; a "
                "fifth mutation would be unguided and is therefore not sampled."
            ),
        },
        evidence_root=evidence.root,
        evidence_members=evidence.members,
        accessed_evidence_paths=accessed,
        allowed_task_ids=state.task_ids,
    )
    (evidence.root / "access_log.jsonl").write_text(
        "".join(
            json.dumps({"iteration": 5, "path": ref}, sort_keys=True) + "\n"
            for ref in sorted(accessed)
        ),
        encoding="utf-8",
    )
    _atomic_immutable_json(root / "ITERATION-05-DECISION.json", asdict(decision_five))
    state = record_pgbs_iteration(
        state,
        evidence_digest=evidence.sha256,
        decision=decision_five,
    )
    if not state.complete or len(state.iterations) != 5:
        raise QuantCodeEvalExperimentError("terminal PGBHS state is incomplete")
    _atomic_immutable_json(root / "states" / "iteration-05.json", state_payload(state))
    result = {
        "schema_version": 1,
        "protocol": "quant_property_v1",
        "status": "complete",
        "run_id": state.run_id,
        "n_iters": 5,
        "task_ids": list(state.task_ids),
        "h0_evaluation_id": h0_evaluation.evaluation_id,
        "h0_resampled_by_search": False,
        "final_official_worker_digest": state.official_incumbent_worker_digest,
        "final_official_evaluation_id": state.official_incumbent_evaluation.evaluation_id,
        "final_reward_vector": [
            state.official_incumbent_evaluation.task_results[task_id].official_reward
            for task_id in state.task_ids
        ],
        "iteration_05_model_request_count": 0,
        "iteration_05_decision": asdict(decision_five),
        "state_sha256": _canonical_sha256(state_payload(state)),
        "state": state_payload(state),
    }
    result["result_identity_sha256"] = _canonical_sha256(result)
    _atomic_immutable_json(root / "PGBHS-RESULT.json", result)
    return result


def record_iteration_five_and_finalize(
    *,
    master_run_dir: str | Path,
    h0_run_dir: str | Path,
    iteration_five_candidate_dir: str | Path,
) -> dict[str, object]:
    """Record the fifth ACT panel and publish the complete five-round ledger."""

    root = Path(master_run_dir).resolve()
    h0_root = Path(h0_run_dir).resolve()
    candidate_root = Path(iteration_five_candidate_dir).resolve()
    state = load_state_payload(_json(root / "states" / "iteration-04.json"))
    preflight_five = _json(root / "ITERATION-05-PREFLIGHT.json")
    decision_five = load_decision_payload(preflight_five["iteration_05_decision"])
    candidate = candidate_evaluation_ref(candidate_root)
    candidate_plan = _json(candidate_root / "CANDIDATE-PREFLIGHT.json")
    metrics = candidate_plan["mutation_metrics"]
    state = record_pgbs_iteration(
        state,
        evidence_digest=str(preflight_five["iteration_05_evidence_sha256"]),
        decision=decision_five,
        candidate_worker_digest=candidate.worker_digest,
        admission=CandidateAdmissionSummary(
            admitted=bool(candidate_plan["admission"]["admitted"]),
            nonempty_diff=int(metrics["changed_file_count"]) > 0,
            declared_roles_match_actual=bool(metrics["declared_roles_match_actual"]),
        ),
        candidate_evaluation=candidate,
    )
    if not state.complete or len(state.iterations) != 5:
        raise QuantCodeEvalExperimentError("terminal PGBHS state is incomplete")
    fifth = state.iterations[4]
    _atomic_immutable_json(root / "states" / "iteration-05.json", state_payload(state))
    h0_evaluation = h0_evaluation_ref(h0_root)
    result = {
        "schema_version": 1,
        "protocol": "quant_property_v1",
        "status": "complete",
        "run_id": state.run_id,
        "n_iters": 5,
        "task_ids": list(state.task_ids),
        "h0_evaluation_id": h0_evaluation.evaluation_id,
        "h0_resampled_by_search": False,
        "final_official_worker_digest": state.official_incumbent_worker_digest,
        "final_official_evaluation_id": state.official_incumbent_evaluation.evaluation_id,
        "final_reward_vector": [
            state.official_incumbent_evaluation.task_results[task_id].official_reward
            for task_id in state.task_ids
        ],
        "iteration_05_candidate_evaluation_id": candidate.evaluation_id,
        "iteration_05_official_promoted": (
            fifth.selection.official_promoted if fifth.selection else False
        ),
        "iteration_05_search_parent_promoted": (
            fifth.selection.search_parent_promoted if fifth.selection else False
        ),
        "iteration_05_rollback_reason": fifth.rollback_reason,
        "state_sha256": _canonical_sha256(state_payload(state)),
        "state": state_payload(state),
    }
    result["result_identity_sha256"] = _canonical_sha256(result)
    _atomic_immutable_json(root / "PGBHS-RESULT.json", result)
    return result


__all__ = [
    "QuantCodeEvalExperimentError",
    "candidate_evaluation_ref",
    "h0_evaluation_ref",
    "materialize_h0_attempt_sources",
    "prepare_initial_pgbs",
    "record_iteration_one_and_prepare_second",
    "record_iteration_two_and_prepare_third",
    "record_iteration_three_and_prepare_fourth",
    "record_iteration_four_and_prepare_fifth",
    "record_iteration_four_and_finalize_success",
    "record_iteration_five_and_finalize",
]
