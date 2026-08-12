import hashlib
import json
from pathlib import Path

import pytest

from qea.quantcodeeval_evidence import PropertyFamilyProgress
from qea.quantcodeeval_pgbs import (
    CandidateAdmissionSummary,
    Decision,
    EvaluationRef,
    EvidenceBasis,
    FailureClass,
    MutationOperator,
    PropertyPrediction,
    QuantDecisionRecord,
    QuantPGBHSError,
    TaskPanelResult,
    diagnostic_search_parent_select,
    initialize_pgbs_state,
    load_state_payload,
    official_pareto_select,
    record_pgbs_iteration,
    state_payload,
    validate_quant_decision,
)


def _progress(total: int, passed: int, *, skipped: int = 0, errors: int = 0):
    return PropertyFamilyProgress(
        total=total,
        passed=passed,
        failed=total - passed - skipped - errors,
        skipped=skipped,
        errors=errors,
    )


def _evaluation(
    evaluation_id: str,
    worker: str,
    *,
    t16_a: int,
    t16_b: int,
    t24_a: int,
    t24_b: int,
    t16_reward: float = 0.0,
    t24_reward: float = 0.0,
) -> EvaluationRef:
    return EvaluationRef(
        evaluation_id=evaluation_id,
        checkpoint=evaluation_id,
        worker_digest=worker,
        panel_digest="a" * 64,
        sampling_identity_digest="b" * 64,
        attempt_ids={"T16": f"{evaluation_id}-T16", "T24": f"{evaluation_id}-T24"},
        task_results={
            "T16": TaskPanelResult(
                "T16", t16_reward, _progress(3, t16_a), _progress(2, t16_b)
            ),
            "T24": TaskPanelResult(
                "T24", t24_reward, _progress(3, t24_a), _progress(2, t24_b)
            ),
        },
        resampled=False,
    )


def _decision(*, prediction_delta: int = 1) -> QuantDecisionRecord:
    return QuantDecisionRecord(
        decision=Decision.ACT,
        failure_class=FailureClass.QUANT_DEFINITION_ESTIMATION,
        hypotheses=(
            {"hypothesis_id": "h_formula", "mechanism": "formula planning gap"},
            {"hypothesis_id": "h_runtime", "mechanism": "runtime interruption"},
        ),
        selected_hypothesis_id="h_formula",
        evidence_refs=("a", "b", "c"),
        public_clause_ref={"path": "instruction.md"},
        artifact_fact_ref="strategy_ast_facts.json",
        trace_fact_ref="trace_facts.json",
        evidence_basis=EvidenceBasis.TYPE_A_CLAUSE_ARTIFACT_TRACE,
        component="skills",
        mutation_operator=MutationOperator.ADD,
        prediction=PropertyPrediction("T16", "type_a", prediction_delta, ("T24",)),
        risk_tasks=("T24",),
        counterevidence="The module exists and parses.",
        uncertainty="The aggregate does not identify an individual property.",
        abstain_reason=None,
    )


def _abstain() -> QuantDecisionRecord:
    return QuantDecisionRecord(
        decision=Decision.ABSTAIN,
        failure_class=FailureClass.UNKNOWN,
        hypotheses=(
            {"hypothesis_id": "h1", "mechanism": "task-specific convention"},
            {"hypothesis_id": "h2", "mechanism": "general planning gap"},
        ),
        selected_hypothesis_id=None,
        evidence_refs=(),
        public_clause_ref=None,
        artifact_fact_ref=None,
        trace_fact_ref=None,
        evidence_basis=None,
        component=None,
        mutation_operator=None,
        prediction=None,
        risk_tasks=(),
        counterevidence="No cross-task recurrence is visible.",
        uncertainty="The causes remain observationally equivalent.",
        abstain_reason="Insufficient answer-free discrimination.",
    )


def _decision_evidence(tmp_path: Path):
    root = tmp_path / "evidence"
    instruction = root / "tasks/T16/instruction.md"
    ast_facts = root / "tasks/T16/evaluations/eval-h0/strategy_ast_facts.json"
    trace_facts = root / "tasks/T16/evaluations/eval-h0/trace_facts.json"
    instruction.parent.mkdir(parents=True)
    ast_facts.parent.mkdir(parents=True)
    instruction.write_text("First public clause.\nSecond public clause.\n")
    ast_facts.write_text('{"parse_valid": true}\n')
    trace_facts.write_text('{"event_count": 3}\n')
    members = tuple(
        path.relative_to(root).as_posix()
        for path in (instruction, ast_facts, trace_facts)
    )
    clause = "Second public clause.\n"
    payload = {
        "decision": "ACT",
        "failure_class": "quant_definition_estimation",
        "hypotheses_considered": [
            {"hypothesis_id": "formula", "mechanism": "formula planning gap"},
            {"hypothesis_id": "runtime", "mechanism": "runtime interruption"},
        ],
        "selected_hypothesis_id": "formula",
        "evidence_refs": list(members),
        "public_clause_ref": {
            "path": members[0],
            "start_line": 2,
            "end_line": 2,
            "text_sha256": hashlib.sha256(clause.encode()).hexdigest(),
        },
        "artifact_fact_ref": members[1],
        "trace_fact_ref": members[2],
        "evidence_basis": "type_a_clause_artifact_trace",
        "component": "skills",
        "mutation_operator": "add",
        "prediction": {
            "task_id": "T16",
            "family": "type_a",
            "minimum_passed_delta": 1,
            "protected_task_ids": ["T24"],
        },
        "risk_tasks": ["T24"],
        "counterevidence": "The source parses.",
        "uncertainty": "Aggregate families do not reveal individual properties.",
    }
    return root, members, payload


def test_quant_act_gate_requires_accessed_clause_artifact_and_trace(tmp_path):
    root, members, payload = _decision_evidence(tmp_path)

    decision = validate_quant_decision(
        payload,
        evidence_root=root,
        evidence_members=members,
        accessed_evidence_paths=set(members),
        allowed_task_ids=("T16", "T24"),
    )

    assert decision.unlocked is True
    assert decision.component == "skills"
    assert decision.prediction.family == "type_a"

    with pytest.raises(QuantPGBHSError, match="not accessed"):
        validate_quant_decision(
            payload,
            evidence_root=root,
            evidence_members=members,
            accessed_evidence_paths=set(members) - {members[2]},
            allowed_task_ids=("T16", "T24"),
        )


@pytest.mark.parametrize(
    ("failure_class", "family", "basis"),
    [
        (
            "data_temporal_integrity",
            "type_a",
            "type_a_clause_artifact_trace",
        ),
        ("portfolio_execution", "type_b", "cross_task_recurrence"),
    ],
)
def test_deterministic_quant_routes_allow_single_systemprompt_component(
    tmp_path, failure_class, family, basis
):
    root, members, payload = _decision_evidence(tmp_path)
    payload["failure_class"] = failure_class
    payload["component"] = "systemprompt"
    payload["prediction"]["family"] = family
    payload["evidence_basis"] = basis

    decision = validate_quant_decision(
        payload,
        evidence_root=root,
        evidence_members=members,
        accessed_evidence_paths=set(members),
        allowed_task_ids=("T16", "T24"),
    )

    assert decision.component == "systemprompt"
    assert decision.failure_class.value == failure_class


def test_isolated_failure_cannot_act_but_abstain_is_valid(tmp_path):
    root, members, payload = _decision_evidence(tmp_path)
    payload["failure_class"] = "isolated_task_specific"

    with pytest.raises(QuantPGBHSError, match="cannot unlock ACT"):
        validate_quant_decision(
            payload,
            evidence_root=root,
            evidence_members=members,
            accessed_evidence_paths=set(members),
            allowed_task_ids=("T16", "T24"),
        )

    abstain_payload = {
        "decision": "ABSTAIN",
        "failure_class": "isolated_task_specific",
        "hypotheses_considered": [
            {"hypothesis_id": "paper", "mechanism": "paper convention"},
            {"hypothesis_id": "harness", "mechanism": "general harness gap"},
        ],
        "selected_hypothesis_id": None,
        "evidence_refs": [],
        "component": None,
        "mutation_operator": None,
        "prediction": None,
        "risk_tasks": [],
        "counterevidence": "Only one paper is implicated.",
        "uncertainty": "No contrast identifies a general mechanism.",
        "abstain_reason": "Isolated Type-B evidence is insufficient.",
    }
    abstain = validate_quant_decision(
        abstain_payload,
        evidence_root=root,
        evidence_members=members,
        accessed_evidence_paths=set(),
        allowed_task_ids=("T16", "T24"),
    )
    assert abstain.decision is Decision.ABSTAIN
    assert abstain.unlocked is False


def test_official_and_diagnostic_selection_are_separate():
    h0 = _evaluation(
        "h0", "0" * 64, t16_a=1, t16_b=1, t24_a=1, t24_b=1
    )
    diagnostic = _evaluation(
        "diag", "1" * 64, t16_a=2, t16_b=1, t24_a=1, t24_b=1
    )
    prediction = PropertyPrediction("T16", "type_a", 1, ("T24",))

    official, official_reason = official_pareto_select(h0, diagnostic)
    search, consistent, delta, search_reason = diagnostic_search_parent_select(
        h0, diagnostic, prediction
    )

    assert official is False
    assert "did not strictly improve" in official_reason
    assert (search, consistent, delta) == (True, True, 1)
    assert "diagnostic prediction passed" in search_reason


def test_official_regression_and_diagnostic_error_growth_are_rejected():
    incumbent = _evaluation(
        "incumbent",
        "8" * 64,
        t16_a=3,
        t16_b=2,
        t24_a=1,
        t24_b=1,
        t16_reward=1.0,
    )
    regressed = _evaluation(
        "regressed",
        "9" * 64,
        t16_a=2,
        t16_b=2,
        t24_a=1,
        t24_b=1,
    )
    promoted, reason = official_pareto_select(incumbent, regressed)
    assert promoted is False
    assert "official task regression" in reason

    parent = _evaluation(
        "parent", "a" * 64, t16_a=1, t16_b=1, t24_a=1, t24_b=1
    )
    candidate = EvaluationRef(
        evaluation_id="errors",
        checkpoint="errors",
        worker_digest="b" * 64,
        panel_digest=parent.panel_digest,
        sampling_identity_digest=parent.sampling_identity_digest,
        attempt_ids={"T16": "errors-T16", "T24": "errors-T24"},
        task_results={
            "T16": TaskPanelResult(
                "T16",
                0.0,
                _progress(3, 2, errors=1),
                _progress(2, 1),
            ),
            "T24": parent.task_results["T24"],
        },
        resampled=False,
    )
    selected, consistent, _, search_reason = diagnostic_search_parent_select(
        parent,
        candidate,
        PropertyPrediction("T16", "type_a", 1, ("T24",)),
    )
    assert (selected, consistent) == (False, False)
    assert search_reason == "errors or skips increased"


def test_five_round_state_reuses_h0_and_abstain_does_not_terminate():
    h0_worker = "0" * 64
    h0 = _evaluation(
        "eval-h0", h0_worker, t16_a=1, t16_b=1, t24_a=1, t24_b=1
    )
    state = initialize_pgbs_state(
        run_id="qce-pgbs-five", h0_worker_digest=h0_worker, h0_evaluation=h0
    )

    state = record_pgbs_iteration(
        state, evidence_digest="1" * 64, decision=_abstain()
    )
    assert state.complete is False
    assert state.iterations[0].parent_evaluation.resampled is False
    assert state.iterations[0].parent_evaluation.reused_from_evaluation_id == "eval-h0"

    state = record_pgbs_iteration(
        state,
        evidence_digest="2" * 64,
        decision=_decision(),
        candidate_worker_digest="2" * 64,
        admission=CandidateAdmissionSummary(
            admitted=False,
            nonempty_diff=True,
            declared_roles_match_actual=True,
            failure="protected runtime field changed",
        ),
    )
    assert state.iterations[1].candidate_evaluation is None

    diagnostic = _evaluation(
        "eval-diagnostic",
        "3" * 64,
        t16_a=2,
        t16_b=1,
        t24_a=1,
        t24_b=1,
    )
    state = record_pgbs_iteration(
        state,
        evidence_digest="3" * 64,
        decision=_decision(),
        candidate_worker_digest="3" * 64,
        admission=CandidateAdmissionSummary(True, True, True),
        candidate_evaluation=diagnostic,
    )
    assert state.official_incumbent_worker_digest == h0_worker
    assert state.search_parent_worker_digest == "3" * 64
    assert state.iterations[2].selection.official_promoted is False
    assert state.iterations[2].selection.search_parent_promoted is True

    no_progress = _evaluation(
        "eval-no-progress",
        "4" * 64,
        t16_a=2,
        t16_b=1,
        t24_a=1,
        t24_b=1,
    )
    state = record_pgbs_iteration(
        state,
        evidence_digest="4" * 64,
        decision=_decision(),
        candidate_worker_digest="4" * 64,
        admission=CandidateAdmissionSummary(True, True, True),
        candidate_evaluation=no_progress,
    )
    assert state.search_parent_worker_digest == "3" * 64
    assert "not observed" in state.iterations[3].rollback_reason

    official = _evaluation(
        "eval-official",
        "5" * 64,
        t16_a=3,
        t16_b=2,
        t24_a=1,
        t24_b=1,
        t16_reward=1.0,
    )
    state = record_pgbs_iteration(
        state,
        evidence_digest="5" * 64,
        decision=_decision(),
        candidate_worker_digest="5" * 64,
        admission=CandidateAdmissionSummary(True, True, True),
        candidate_evaluation=official,
    )

    assert state.complete is True
    assert len(state.iterations) == 5
    assert state.official_incumbent_worker_digest == "5" * 64
    assert state.search_parent_worker_digest == "5" * 64
    assert len(state.archive) <= 2
    assert all(record.parent_evaluation.resampled is False for record in state.iterations)
    assert state_payload(state)["complete"] is True
    json.dumps(state_payload(state))

    with pytest.raises(QuantPGBHSError, match="already complete"):
        record_pgbs_iteration(
            state, evidence_digest="6" * 64, decision=_abstain()
        )


def test_admitted_act_requires_nonempty_role_aligned_diff():
    with pytest.raises(QuantPGBHSError, match="non-empty"):
        CandidateAdmissionSummary(
            admitted=True,
            nonempty_diff=False,
            declared_roles_match_actual=True,
        )


def test_five_abstains_are_five_records_not_early_termination():
    h0_worker = "c" * 64
    state = initialize_pgbs_state(
        run_id="five-abstains",
        h0_worker_digest=h0_worker,
        h0_evaluation=_evaluation(
            "abstain-h0",
            h0_worker,
            t16_a=1,
            t16_b=1,
            t24_a=1,
            t24_b=1,
        ),
    )
    for iteration in range(1, 6):
        state = record_pgbs_iteration(
            state,
            evidence_digest=f"{iteration:x}" * 64,
            decision=_abstain(),
        )
        assert len(state.iterations) == iteration
        assert state.complete is (iteration == 5)
    assert all(record.candidate_evaluation is None for record in state.iterations)
    encoded = json.loads(json.dumps(state_payload(state)))
    assert load_state_payload(encoded) == state
    encoded["complete"] = False
    with pytest.raises(QuantPGBHSError, match="completion marker"):
        load_state_payload(encoded)
