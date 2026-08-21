import json

import pytest

from qea.evolution_evidence import authorize_evidence_tree
from qea.evolver_discovery import measure_discovery_quality


def test_discovery_quality_measures_grounding_and_contract_consistency():
    members = (
        "debugger/overview.json",
        "tasks/task-a/worker_trace.jsonl",
        "tasks/task-a/public_evaluation.json",
    )
    state = {
        "unlocked": True,
        "hypothesis": {
            "hypotheses_considered": ["routing collision", "bad quant formula"],
            "selected_mechanism": "routing collision",
            "evidence_refs": [
                "debugger/overview.json",
                "tasks/task-a/worker_trace.jsonl",
            ],
            "counterevidence": "the same skill helps task-b",
            "uncertainty": "one trace per task",
            "discriminating_probe": "skill activation precedes the divergence",
            "component": "routing",
            "prediction": {"task-a": "skill no longer activates"},
            "risk_tasks": ["task-b"],
        },
    }
    prediction = {
        "selected_mechanism": "routing collision",
        "component_changed": "routing",
        "evidence_used": [
            "debugger/overview.json",
            "tasks/task-a/worker_trace.jsonl (activation span)",
        ],
        "predicted_process_changes": ["task-a does not load the broad skill"],
    }
    access = {
        "evidence_paths": [
            "**/*",
            "debugger/overview.json",
            "tasks/task-a/worker_trace.jsonl",
        ],
        "operations": {"map": 1, "read": 2, "trace_slice": 1},
    }

    measured = measure_discovery_quality(
        prediction=prediction,
        access_summary=access,
        discovery_state=state,
        evidence_members=members,
    )

    assert measured["contract_score"] == 1.0
    assert measured["grounded_citation_ratio"] == 1.0
    assert measured["evidence_access_ratio"] == 2 / 3
    assert measured["debugger_files_accessed"] == 1
    assert measured["trace_files_accessed"] == 1


def test_discovery_quality_does_not_treat_listing_or_uncited_output_as_grounded():
    measured = measure_discovery_quality(
        prediction={"component_changed": "skills"},
        access_summary={
            "evidence_paths": ["**/*"],
            "operations": {"map": 1},
        },
        discovery_state=None,
        evidence_members=("debugger/overview.json", "tasks/task-a/worker_trace.jsonl"),
    )

    assert measured["contract_score"] == 0.0
    assert measured["exact_evidence_access_count"] == 0
    assert measured["grounded_citation_ratio"] is None
    assert measured["query_operations"]["map"] == 1


def test_failure_type_quality_measures_probe_decision_and_multi_component_act():
    members = (
        "tasks/target-a/worker_trace.jsonl",
        "tasks/target-c/worker_trace.jsonl",
        "tasks/success-b/worker_trace.jsonl",
    )
    state = {
        "schema_version": 2,
        "protocol": "failure_type_v1",
        "decision": "ACT",
        "unlocked": True,
        "contract_requirements": {
            "success_counterfactual": "required_or_insufficient",
        },
        "hypothesis": {
            "decision": "ACT",
            "failure_types": [
                {
                    "type_id": "t1",
                    "member_tasks": ["target-a", "target-c"],
                    "matched_success_tasks": ["success-b"],
                    "evidence_refs": [
                        "tasks/target-a/worker_trace.jsonl",
                        "tasks/target-c/worker_trace.jsonl",
                    ],
                }
            ],
            "hypotheses_considered": [
                {
                    "hypothesis_id": "h1",
                    "success_counterfactual": "validation appears",
                },
                {"hypothesis_id": "h2", "insufficient_contrast": True},
            ],
            "selected_hypothesis_id": "h1",
            "hypotheses_eliminated": ["h2"],
            "probe_records_used": [{"probe_id": "p1"}],
            "evidence_refs": [
                "tasks/target-a/worker_trace.jsonl",
                "tasks/target-c/worker_trace.jsonl",
            ],
            "components": ["tools", "validator"],
            "counterevidence": "success-b has no local validator",
            "uncertainty": "one trace per task",
            "prediction": {"targets": "validation behavior appears"},
        },
    }
    prediction = {
        "decision": "ACT",
        "selected_hypothesis_id": "h1",
        "components_changed": ["tools", "validator"],
        "evidence_used": [
            "tasks/target-a/worker_trace.jsonl",
            "tasks/target-c/worker_trace.jsonl",
        ],
    }
    access = {
        "evidence_paths": list(members),
        "operations": {"probe": 2, "decision": 1},
    }

    measured = measure_discovery_quality(
        prediction=prediction,
        access_summary=access,
        discovery_state=state,
        evidence_members=members,
    )

    assert measured["protocol"] == "failure_type_v1"
    assert measured["decision"] == "ACT"
    assert measured["contract_score"] == 1.0
    assert measured["recurrent_failure_type_count"] == 1
    assert measured["typed_failure_task_count"] == 2
    assert measured["probe_count"] == 1
    assert measured["hypotheses_eliminated_count"] == 1
    assert measured["components_selected"] == ["tools", "validator"]


def test_failure_type_abstain_is_calibrated_without_component_or_prediction():
    members = ("tasks/target-a/worker_trace.jsonl", "tasks/target-c/worker_trace.jsonl")
    state = {
        "schema_version": 2,
        "protocol": "failure_type_v1",
        "decision": "ABSTAIN",
        "unlocked": False,
        "hypothesis": {
            "decision": "ABSTAIN",
            "failure_types": [
                {
                    "type_id": "t1",
                    "member_tasks": ["target-a", "target-c"],
                    "evidence_refs": list(members),
                }
            ],
            "hypotheses_considered": [
                {"hypothesis_id": "h1"},
                {"hypothesis_id": "h2"},
            ],
            "selected_hypothesis_id": None,
            "hypotheses_eliminated": [],
            "probe_records_used": [{"probe_id": "p1"}],
            "evidence_refs": list(members),
            "components": [],
            "counterevidence": "both mechanisms remain compatible",
            "uncertainty": "probe was inconclusive",
            "abstain_reason": "no hypothesis was eliminated",
        },
    }

    measured = measure_discovery_quality(
        prediction={
            "decision": "ABSTAIN",
            "components_changed": [],
            "evidence_used": list(members),
        },
        access_summary={"evidence_paths": list(members)},
        discovery_state=state,
        evidence_members=members,
    )

    assert measured["decision"] == "ABSTAIN"
    assert measured["checks"]["probe_discriminated_or_abstained"] is True
    assert measured["checks"]["act_components_or_abstain"] is True
    assert measured["contract_score"] == 1.0


def test_semantic_contract_quality_requires_valid_grounded_triple_for_act():
    members = (
        "contracts/target-a/clauses.json",
        "contracts/target-a/instruction.md",
        "tasks/target-a/artifacts/result.json",
        "tasks/target-a/artifact_manifest.json",
        "tasks/target-a/worker_trace.jsonl",
    )
    typed_probe = {
        "probe_id": "typed_gap",
        "probe_kind": "typed_contract_artifact_trace_v1",
        "task_id": "target-a",
        "hypothesis_expectations": {
            "h_schema": {"artifact_exists": False},
            "h_formula": {"artifact_exists": True},
        },
        "expectation_matches": {"h_schema": True, "h_formula": False},
        "semantic_relation": "contradicts",
        "evidence_paths": list(members),
    }
    state = {
        "schema_version": 3,
        "protocol": "semantic_contract_v1",
        "decision": "ACT",
        "unlocked": True,
        "contract_requirements": {
            "success_counterfactual": "required_or_insufficient",
            "semantic_comparison": "required_for_act",
        },
        "hypothesis": {
            "decision": "ACT",
            "failure_types": [
                {
                    "type_id": "t1",
                    "member_tasks": ["target-a", "target-c"],
                    "evidence_refs": list(members[:2]),
                }
            ],
            "hypotheses_considered": [
                {
                    "hypothesis_id": "h_schema",
                    "success_counterfactual": "field appears",
                },
                {"hypothesis_id": "h_formula", "insufficient_contrast": True},
            ],
            "selected_hypothesis_id": "h_schema",
            "hypotheses_eliminated": ["h_formula"],
            "probe_records_used": [typed_probe],
            "grounded_comparison_probe_ids": ["typed_gap"],
            "evidence_refs": list(members[:2]),
            "components": ["validator"],
            "counterevidence": "success can occur without the validator",
            "uncertainty": "one fresh trace",
            "prediction": {"target-a": "required field appears"},
        },
    }
    prediction = {
        "decision": "ACT",
        "selected_hypothesis_id": "h_schema",
        "components_changed": ["validator"],
        "grounded_comparison_probe_ids": ["typed_gap"],
        "evidence_used": list(members),
    }

    measured = measure_discovery_quality(
        prediction=prediction,
        access_summary={
            "evidence_paths": list(members),
            "operations": {"semantic_probe": len(members), "decision": 1},
        },
        discovery_state=state,
        evidence_members=members,
    )

    assert measured["protocol"] == "semantic_contract_v1"
    assert measured["contract_score"] == 1.0
    assert measured["typed_semantic_probe_count"] == 1
    assert measured["valid_grounded_semantic_comparison_count"] == 1
    assert measured["unsupported_semantic_leap"] is False
    assert measured["causal_truth_certified"] is False


def test_semantic_contract_quality_flags_unsupported_act_without_claiming_truth():
    state = {
        "schema_version": 3,
        "protocol": "semantic_contract_v1",
        "decision": "ACT",
        "contract_requirements": {"semantic_comparison": "required_for_act"},
        "hypothesis": {
            "decision": "ACT",
            "failure_types": [
                {
                    "type_id": "t1",
                    "member_tasks": ["target-a", "target-c"],
                    "evidence_refs": ["a.json", "b.json"],
                }
            ],
            "hypotheses_considered": [
                {"hypothesis_id": "h1"},
                {"hypothesis_id": "h2"},
            ],
            "selected_hypothesis_id": "h1",
            "hypotheses_eliminated": ["h2"],
            "probe_records_used": [{"probe_id": "generic"}],
            "evidence_refs": ["a.json", "b.json"],
            "components": ["systemprompt"],
            "counterevidence": "counter",
            "uncertainty": "uncertain",
            "prediction": "change",
        },
    }

    measured = measure_discovery_quality(
        prediction={"decision": "ACT", "components_changed": ["systemprompt"]},
        access_summary={"evidence_paths": ["a.json", "b.json"]},
        discovery_state=state,
        evidence_members=("a.json", "b.json"),
    )

    assert measured["unsupported_semantic_leap"] is True
    assert measured["causal_truth_certified"] is False
    assert measured["checks"]["grounded_semantic_comparison_or_abstain"] is False


def test_failure_type_act_does_not_fabricate_semantic_verdict_when_unavailable():
    state = {
        "schema_version": 2,
        "protocol": "failure_type_v1",
        "decision": "ACT",
        "unlocked": True,
        "contract_requirements": {
            "semantic_comparison": "not_required",
        },
        "hypothesis": {
            "decision": "ACT",
            "failure_types": [
                {
                    "type_id": "t1",
                    "member_tasks": ["target-a", "target-c"],
                    "evidence_refs": ["a.json", "b.json"],
                }
            ],
            "hypotheses_considered": [
                {"hypothesis_id": "h1"},
                {"hypothesis_id": "h2"},
            ],
            "selected_hypothesis_id": "h1",
            "hypotheses_eliminated": ["h2"],
            "probe_records_used": [{"probe_id": "generic"}],
            "evidence_refs": ["a.json", "b.json"],
            "components": ["systemprompt"],
            "counterevidence": "counter",
            "uncertainty": "uncertain",
            "prediction": "change",
        },
    }

    measured = measure_discovery_quality(
        prediction={"decision": "ACT", "components_changed": ["systemprompt"]},
        access_summary={"evidence_paths": ["a.json", "b.json"]},
        discovery_state=state,
        evidence_members=("a.json", "b.json"),
    )

    assert measured["unsupported_semantic_leap"] is None
    assert measured["unsupported_semantic_leap_applicable"] is False
    assert measured["semantic_comparison_availability"] == "structurally_unavailable"


def test_failure_type_act_keeps_optional_semantic_audit_not_applicable_without_claim():
    state = {
        "schema_version": 2,
        "protocol": "failure_type_v1",
        "decision": "ACT",
        "unlocked": True,
        "contract_requirements": {
            "semantic_comparison": "available_not_required",
        },
        "hypothesis": {
            "decision": "ACT",
            "failure_types": [
                {
                    "type_id": "t1",
                    "member_tasks": ["target-a", "target-c"],
                    "evidence_refs": ["a.json", "b.json"],
                }
            ],
            "hypotheses_considered": [
                {"hypothesis_id": "h1"},
                {"hypothesis_id": "h2"},
            ],
            "selected_hypothesis_id": "h1",
            "hypotheses_eliminated": ["h2"],
            "probe_records_used": [{"probe_id": "generic"}],
            "evidence_refs": ["a.json", "b.json"],
            "components": ["systemprompt"],
            "counterevidence": "counter",
            "uncertainty": "uncertain",
            "prediction": "change",
        },
    }

    measured = measure_discovery_quality(
        prediction={"decision": "ACT", "components_changed": ["systemprompt"]},
        access_summary={"evidence_paths": ["a.json", "b.json"]},
        discovery_state=state,
        evidence_members=("a.json", "b.json"),
    )

    assert measured["unsupported_semantic_leap"] is None
    assert measured["unsupported_semantic_leap_applicable"] is False
    assert measured["semantic_comparison_availability"] == "available_optional"


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n")


def _pilot_run(path, stage, *, task_reward=0.0):
    path.mkdir()
    _write_json(
        path / "pilot-report.json",
        {
            "run_id": path.name,
            "stage": stage,
            "status": "complete",
            "evaluation": {
                "task_rewards": {"task-a": task_reward},
                "task_mean": task_reward,
                "overall": task_reward,
            },
            "activation": {
                "activation_count": 1,
                "declared_skills": ["contract-skill"],
                "attempts": [
                    {
                        "task_id": "task-a",
                        "attempt_id": "attempt-a",
                        "activated_skills": ["contract-skill"],
                    }
                ],
            },
            "proposal": {
                "prediction": {
                    "component_changed": "skills",
                    "failure_kind": "broad activation",
                }
            },
            "cost": {"provider_cost_usd": 0.01},
        },
    )


def test_post_a3_evidence_builder_keeps_raw_arms_matched_and_adds_debugger_index(
    tmp_path,
):
    from scripts.build_qfbench_discovery_evidence import build

    a1 = tmp_path / "a1"
    a2 = tmp_path / "a2"
    a3 = tmp_path / "a3"
    _pilot_run(a1, "A1", task_reward=0.5)
    _pilot_run(a2, "A2", task_reward=0.0)
    _pilot_run(a3, "A3", task_reward=1.0)
    _write_json(
        a3 / "proposal-report.json",
        {
            "diff": "--- a/agent.yaml\n+++ b/agent.yaml\n+skills:\n",
            "prediction": {"component_changed": "skills"},
            "access_summary": {"evidence_paths": ["task_vectors.json"]},
            "summary": {"tool_calls": 3},
            "admission": {"checks": ["local_skills"]},
        },
    )
    for root, prompt in (
        (a3 / "workers/backbone", "before\n"),
        (a3 / "evolutions/iteration-0001/candidate", "after\n"),
    ):
        root.mkdir(parents=True)
        (root / "agent.yaml").write_text("skills: []\n")
        (root / "systemprompt.md").write_text(prompt)
    authorized = a3 / "authorized-evidence"
    _write_json(
        authorized / "task_vectors.json",
        {
            "vectors": {
                "backbone": {"task_rewards": {"task-a": 0.0}},
            }
        },
    )
    _write_json(
        authorized / "selection.json", {"backbone_parent": "backbone"}
    )
    _write_json(authorized / "debugger_overview.json", {"generator": "fixture"})
    attempt = a3 / "attempts/attempt-a"
    _write_json(
        attempt / "attempt.json",
        {"task_id": "task-a", "checkpoint": "a3-candidate"},
    )
    _write_json(
        attempt / "completed-score.json",
        {
            "task_id": "task-a",
            "reward": 1.0,
            "diagnostic_tags": [],
            "tests_passed": 3,
            "tests_failed": 0,
            "log_uri": "/trusted/verifier-command.json",
        },
    )
    _write_json(attempt / "worker-execution.json", {"summary": {"tool_calls": 2}})
    (attempt / "raw-trace.jsonl").write_text(
        '{"role":"assistant","content":"load contract-skill"}\n'
    )
    (attempt / "final.txt").write_text("completed\n")

    raw = tmp_path / "raw"
    indexed = tmp_path / "indexed"
    raw_report = build(
        a1_run=a1, a2_run=a2, a3_run=a3, destination=raw, mode="raw"
    )
    indexed_report = build(
        a1_run=a1, a2_run=a2, a3_run=a3, destination=indexed, mode="indexed"
    )

    assert raw_report["credential_redactions"] == 0
    assert indexed_report["member_count"] == raw_report["member_count"] + 3
    assert not (raw / "debugger/overview.json").exists()
    assert (indexed / "debugger/overview.json").is_file()
    assert (raw / "tasks/task-a/worker_trace.jsonl").read_bytes() == (
        indexed / "tasks/task-a/worker_trace.jsonl"
    ).read_bytes()
    public = json.loads((indexed / "tasks/task-a/public_evaluation.json").read_text())
    assert "log_uri" not in public
    assert public["official_reward"] == 1.0
    assert authorize_evidence_tree(raw).sha256 == raw_report["sha256"]
    assert authorize_evidence_tree(indexed).sha256 == indexed_report["sha256"]


def test_discovery_pilot_stages_evidence_under_exact_run(tmp_path):
    from scripts.run_qfbench_discovery_pilot import _stage_evidence

    source = tmp_path / "source"
    source.mkdir()
    (source / "access_log.jsonl").write_text("", encoding="utf-8")
    (source / "fact.json").write_text('{"value": 1}\n', encoding="utf-8")
    record = authorize_evidence_tree(source)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    staged = _stage_evidence(record, run_dir)

    assert staged.root == (run_dir / "authorized-evidence").resolve()
    assert staged.sha256 == record.sha256
    assert staged.members == record.members


def test_discovery_pilot_takes_generic_instruction_from_evidence_contract(tmp_path):
    from scripts.run_qfbench_discovery_pilot import _diagnosis

    evidence = tmp_path / "evidence"
    _write_json(
        evidence / "contract.json",
        {
            "stage": "A4",
            "evolver_instruction": "Inspect train traces and test one mechanism.",
        },
    )

    diagnosis = _diagnosis(evidence, "a4-indexed")

    assert diagnosis == {
        "stage": "A4",
        "arm": "a4-indexed",
        "instruction": "Inspect train traces and test one mechanism.",
    }


def test_discovery_pilot_binds_requested_arm_to_evidence_contract(tmp_path):
    from scripts.run_qfbench_discovery_pilot import _diagnosis

    evidence = tmp_path / "evidence"
    _write_json(
        evidence / "contract.json",
        {
            "stage": "A6",
            "contract_arm": "A6-EC",
            "evolver_instruction": "Use the frozen semantic contract.",
        },
    )

    assert _diagnosis(evidence, "a6-ec")["arm"] == "a6-ec"
    with pytest.raises(ValueError, match="requested arm differs"):
        _diagnosis(evidence, "a6-e")


def test_discovery_pilot_missing_terminal_decision_never_reaches_admission(
    tmp_path, monkeypatch
):
    import scripts.run_qfbench_discovery_pilot as pilot

    called = False

    def forbidden_admission(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("admit_candidate must not be called")

    monkeypatch.setattr(pilot, "admit_candidate", forbidden_admission)
    assert pilot._terminal_decision({}) is None
    assert pilot._terminal_decision({"decision": "continue"}) is None
    assert pilot._terminal_decision({}, {"decision": "ABSTAIN"}) == "ABSTAIN"

    admission = pilot._candidate_admission(
        decision=None,
        backbone=tmp_path / "backbone",
        candidate=tmp_path / "candidate",
    )

    assert called is False
    assert admission["admitted"] is False
    assert admission["not_applicable"] is True
    assert "fail-closed" in admission["reason"]


def test_coordinated_probe_selects_only_the_admitted_target():
    from scripts.run_qfbench_discovery_pilot import (
        _coordinated_probe_task_key,
    )

    contract = {
        "stage": "COORDINATED_BREADTH",
        "max_worker_probes_this_round": 1,
        "target_task_keys": ["qfbench:curve-target"],
    }
    state = {"hypothesis": {"probe_task_key": "qfbench:curve-target"}}

    assert _coordinated_probe_task_key(
        contract=contract,
        decision="ACT",
        admission={"admitted": True},
        discovery_state=state,
    ) == "qfbench:curve-target"
    assert _coordinated_probe_task_key(
        contract=contract,
        decision="ABSTAIN",
        admission={"admitted": None},
        discovery_state={},
    ) is None
    assert _coordinated_probe_task_key(
        contract=contract,
        decision="ACT",
        admission={"admitted": False},
        discovery_state=state,
    ) is None


def test_lineage_refinement_dispatches_its_declared_target():
    from scripts.run_qfbench_discovery_pilot import _coordinated_probe_task_key

    assert _coordinated_probe_task_key(
        contract={
            "stage": "LINEAGE_REFINEMENT",
            "max_worker_probes_this_round": 1,
            "target_task_keys": ["qfbench:holdings-target"],
        },
        decision="ACT",
        admission={"admitted": True},
        discovery_state={
            "hypothesis": {"probe_task_key": "qfbench:holdings-target"}
        },
    ) == "qfbench:holdings-target"


def test_coordinated_probe_never_falls_back_or_dispatches_protection():
    from scripts.run_qfbench_discovery_pilot import (
        _coordinated_probe_task_key,
    )

    contract = {
        "stage": "COORDINATED_BREADTH",
        "max_worker_probes_this_round": 1,
        "target_task_keys": ["qfbench:curve-target"],
    }
    with pytest.raises(ValueError, match="no probe_task_key"):
        _coordinated_probe_task_key(
            contract=contract,
            decision="ACT",
            admission={"admitted": True},
            discovery_state={"hypothesis": {}},
        )
    with pytest.raises(ValueError, match="non-target"):
        _coordinated_probe_task_key(
            contract=contract,
            decision="ACT",
            admission={"admitted": True},
            discovery_state={
                "hypothesis": {"probe_task_key": "qfbench:curve-protection"}
            },
        )


def test_qfbench_probe_key_resolves_exactly_one_task():
    from types import SimpleNamespace

    from scripts.run_qfbench_discovery_pilot import _qfbench_task_for_key

    target = SimpleNamespace(task_id="curve-target")
    protection = SimpleNamespace(task_id="curve-protection")

    assert _qfbench_task_for_key(
        "qfbench:curve-target", (target, protection)
    ) is target
    with pytest.raises(ValueError, match="QFBench task key"):
        _qfbench_task_for_key("quantcodeeval:T26", (target, protection))


def test_coordinated_probe_worker_uses_evolver_directive_and_budget(tmp_path):
    from scripts.run_qfbench_discovery_pilot import (
        _materialize_coordinated_probe_worker,
    )

    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "agent.yaml").write_text(
        "type: agent\nmax_iterations: 60\nsystem_prompt: ./systemprompt.md\n",
        encoding="utf-8",
    )
    (candidate / "systemprompt.md").write_text(
        "Solve the quantitative task.\n", encoding="utf-8"
    )
    worker, iterations = _materialize_coordinated_probe_worker(
        candidate=candidate,
        destination=tmp_path / "probe-worker",
        hypothesis={
            "quant_research_state_card": "quant-research-state-card.json",
            "selected_relation": {
                "relation_id": "curve-repricing",
                "applicability": "public instruments must reprice",
                "predicted_status_change": "FAIL to PASS",
            },
            "optimize_only_diagnostic": {
                "expected_value": "PRIVATE_EXPECTED_VALUE"
            },
            "experiment_spec": {
                "mode": "from_scratch",
                "seed_experience": None,
                "max_iterations": 7,
                "worker_instruction": (
                    "Exercise the new curve checker before final delivery."
                ),
            }
        },
    )

    assert iterations == 7
    assert "max_iterations: 7" in (worker / "agent.yaml").read_text()
    assert "Evolver-authored bounded experiment" in (
        worker / "systemprompt.md"
    ).read_text()
    assert "curve checker" in (worker / "systemprompt.md").read_text()
    probe_prompt = (worker / "systemprompt.md").read_text()
    assert "quant-research-state-card.json" not in probe_prompt
    assert "PRIVATE_EXPECTED_VALUE" not in probe_prompt


def test_discovery_cost_counts_caller_confirmed_downstream_delivery(tmp_path):
    from scripts.run_qfbench_discovery_pilot import _cost

    audit = tmp_path / "attempts" / "evolver-iteration-1" / "proxy-audit.jsonl"
    audit.parent.mkdir(parents=True)
    records = (
        {
            "request_state": "completed",
            "failure_class": None,
            "provider_cost_usd": 0.1,
            "total_tokens": 10,
        },
        {
            "request_state": "quarantined",
            "failure_class": "downstream_delivery",
            "provider_cost_usd": 0.2,
            "total_tokens": 20,
        },
        {
            "request_state": "not_accepted",
            "failure_class": "policy_rejection",
            "provider_cost_usd": None,
            "total_tokens": None,
        },
    )
    audit.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    measured = _cost(tmp_path)

    assert measured == {
        "completed_request_count": 1,
        "downstream_delivery_request_count": 1,
        "noncompleted_request_count": 1,
        "provider_cost_usd": 0.30000000000000004,
        "total_tokens": 30,
        "missing_cost_count": 0,
        "missing_token_count": 0,
    }
