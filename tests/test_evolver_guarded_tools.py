import hashlib
import json
from pathlib import Path

import pytest

from qea.benchmarks.qfbench import git_blob_oid


@pytest.fixture
def guarded_roots(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate"
    evidence = tmp_path / "evidence"
    reference = tmp_path / "reference"
    runtime = tmp_path / "runtime"
    candidate.mkdir()
    evidence.mkdir()
    reference.mkdir()
    runtime.mkdir()
    (candidate / "systemprompt.md").write_text("Solve carefully.\n")
    (evidence / "overview.md").write_text(
        "task-a failed its public deliverable requirement.\n"
    )
    (evidence / "counterexample.md").write_text(
        "task-b succeeded without the proposed workflow.\n"
    )
    (reference / "NEXAU_GUIDE.md").write_text("Use skills and middlewares.\n")
    (runtime / "runtime_bridge.py").write_text(
        "def marker():\n    return 'worker-runtime'\n"
    )
    access_log = tmp_path / "access_log.jsonl"
    monkeypatch.setenv("QEA_CANDIDATE_ROOT", str(candidate))
    monkeypatch.setenv("QEA_EVIDENCE_ROOT", str(evidence))
    monkeypatch.setenv("QEA_REFERENCE_ROOT", str(reference))
    monkeypatch.setenv("QEA_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("QEA_ACCESS_LOG", str(access_log))
    return candidate, evidence, reference, runtime, access_log


def _unlock(component="tools"):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        read_workspace,
        unlock_candidate,
    )

    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    return unlock_candidate(
        hypothesis={
            "hypotheses_considered": [
                "the worker lacks a deterministic operation",
                "the worker is misreading the deliverable contract",
            ],
            "selected_mechanism": "a deterministic operation removes repeated error",
            "evidence_refs": ["overview.md", "counterexample.md"],
            "counterevidence": "task-b succeeded without the operation",
            "uncertainty": "only two public traces are available",
            "discriminating_probe": "compare artifact construction in both traces",
            "component": component,
            "prediction": {"task-a": "artifact construction becomes deterministic"},
            "risk_tasks": ["task-b"],
        }
    )


def test_read_write_replace_and_list_candidate(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        list_workspace,
        read_workspace,
        replace_candidate,
        write_candidate,
    )

    candidate, _, _, _, _ = guarded_roots
    listing = list_workspace(source="candidate", pattern="**/*")
    assert listing["paths"] == ["systemprompt.md"]
    assert read_workspace(
        source="candidate", file_path="systemprompt.md"
    )["content"] == "Solve carefully.\n"
    assert _unlock()["unlocked"] is True

    written = write_candidate(
        file_path="tools/calc.py",
        content="def add(a, b):\n    return {'value': a + b}\n",
    )
    assert written["path"] == "tools/calc.py"
    assert (candidate / "tools/calc.py").is_file()

    replaced = replace_candidate(
        file_path="systemprompt.md",
        old_string="carefully",
        new_string="carefully and validate artifacts",
        expected_replacements=1,
    )
    assert replaced["replacements"] == 1
    assert "validate artifacts" in (candidate / "systemprompt.md").read_text()


def test_evidence_reads_and_searches_append_access_audit(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        read_workspace,
        search_evidence,
    )

    _, _, _, _, access_log = guarded_roots
    read = read_workspace(source="evidence", file_path="overview.md")
    search = search_evidence(pattern="deliverable", max_hits=10)

    assert "task-a failed" in read["content"]
    assert search["hits"][0]["path"] == "overview.md"
    records = [json.loads(line) for line in access_log.read_text().splitlines()]
    assert [record["operation"] for record in records] == ["read", "search"]
    assert all(record["source"] == "evidence" for record in records)
    assert records[0]["relative_path"] == "overview.md"


def test_reference_is_read_only_and_audited(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        list_workspace,
        read_workspace,
    )

    _, _, _, _, access_log = guarded_roots
    assert list_workspace(source="reference")["paths"] == ["NEXAU_GUIDE.md"]
    assert "middlewares" in read_workspace(
        source="reference", file_path="NEXAU_GUIDE.md"
    )["content"]
    records = [json.loads(line) for line in access_log.read_text().splitlines()]
    assert [record["source"] for record in records] == ["reference", "reference"]


@pytest.mark.parametrize(
    "source,file_path",
    [
        ("candidate", "/etc/passwd"),
        ("candidate", "../outside.txt"),
        ("evidence", "/etc/passwd"),
        ("evidence", "../outside.txt"),
    ],
)
def test_read_rejects_absolute_and_parent_paths(guarded_roots, source, file_path):
    from qea.evolve_agent_full.tools.guarded_workspace import GuardedWorkspaceError, read_workspace

    with pytest.raises(GuardedWorkspaceError, match="unsafe relative path"):
        read_workspace(source=source, file_path=file_path)


def test_rejects_symlink_read_and_write_escape(guarded_roots, tmp_path):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        read_workspace,
        write_candidate,
    )

    candidate, evidence, _, _, _ = guarded_roots
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n")
    (candidate / "escape.txt").symlink_to(outside)
    (evidence / "escape.txt").symlink_to(outside)
    _unlock()

    with pytest.raises(GuardedWorkspaceError, match="symlink"):
        read_workspace(source="candidate", file_path="escape.txt")
    with pytest.raises(GuardedWorkspaceError, match="symlink"):
        read_workspace(source="evidence", file_path="escape.txt")
    with pytest.raises(GuardedWorkspaceError, match="symlink"):
        write_candidate(file_path="escape.txt", content="overwrite\n")


def test_replace_requires_exact_expected_count(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        replace_candidate,
    )

    _unlock(component="systemprompt")
    with pytest.raises(GuardedWorkspaceError, match="expected 2 replacements, found 1"):
        replace_candidate(
            file_path="systemprompt.md",
            old_string="carefully",
            new_string="safely",
            expected_replacements=2,
        )


def test_smoke_candidate_tool_imports_calls_and_times_out(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        smoke_candidate_tool,
        write_candidate,
    )

    _unlock()
    write_candidate(file_path="tools/__init__.py", content="")
    write_candidate(
        file_path="tools/fixture.py",
        content=(
            "import time\n\n"
            "from runtime_bridge import marker\n\n"
            "def echo(value):\n    return {'value': value}\n\n"
            "def runtime():\n    return {'value': marker()}\n\n"
            "def sleep(seconds):\n    time.sleep(seconds)\n    return {}\n"
        ),
    )

    result = smoke_candidate_tool(
        module="tools.fixture",
        function="echo",
        args_json='{"value": "ok"}',
        timeout_seconds=5,
    )
    assert result["exit_code"] == 0
    assert json.loads(result["stdout"])["value"] == "ok"

    runtime = smoke_candidate_tool(
        module="tools.fixture",
        function="runtime",
        timeout_seconds=5,
    )
    assert json.loads(runtime["stdout"])["value"] == "worker-runtime"

    with pytest.raises(GuardedWorkspaceError, match="timed out"):
        smoke_candidate_tool(
            module="tools.fixture",
            function="sleep",
            args_json='{"seconds": 5}',
            timeout_seconds=1,
        )


def test_delete_and_component_smoke_support_inner_component_loop(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        delete_candidate,
        smoke_candidate_component,
        write_candidate,
    )

    candidate, _, _, _, access_log = guarded_roots
    _unlock(component="tools")
    write_candidate(file_path="tools/__init__.py", content="")
    write_candidate(
        file_path="tools/component.py",
        content="def check(value):\n    return {'ok': bool(value)}\n",
    )
    smoke = smoke_candidate_component(
        component="tools",
        target="tools.component",
        operation="call",
        symbol="check",
        args_json='{"value": 1}',
    )
    assert smoke["exit_code"] == 0
    assert json.loads(smoke["stdout"]) == {"ok": True}

    deleted = delete_candidate("tools/component.py")
    assert deleted == {"path": "tools/component.py", "deleted": True}
    assert not (candidate / "tools/component.py").exists()
    records = [json.loads(line) for line in access_log.read_text().splitlines()]
    assert "component_smoke" in [record["operation"] for record in records]
    assert records[-1]["operation"] == "delete"
    component_tests = [
        json.loads(line)
        for line in (access_log.parent / "component-tests.jsonl")
        .read_text()
        .splitlines()
    ]
    assert component_tests == [smoke]
    assert component_tests[0]["status"] == "passed"
    assert component_tests[0]["test_index"] == 1


def test_component_smoke_loads_declared_skill(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        smoke_candidate_component,
        write_candidate,
    )

    _unlock(component="skills")
    write_candidate(
        file_path="skills/contract/SKILL.md",
        content=(
            "---\nname: contract\ndescription: Validate a public contract.\n---\n"
            "Check units and timing.\n"
        ),
    )
    result = smoke_candidate_component(
        component="skills",
        target="skills/contract/SKILL.md",
        operation="load",
    )
    assert result["exit_code"] == 0
    assert result["metadata"]["name"] == "contract"


def test_tool_descriptions_expose_only_guarded_operations():
    root = Path(__file__).resolve().parents[1] / "qea/evolve_agent_full"
    config = (root / "agent.yaml").read_text()

    assert "guarded_workspace" in config
    assert "run_shell_command" not in config
    assert "builtin.file_tools" not in config
    assert "run_code_tool" not in config
    assert {
        path.stem.removesuffix(".tool")
        for path in (root / "tool_descriptions").glob("*.tool.yaml")
    } == {
        "compare_evidence",
        "decide_candidate",
        "delete_candidate",
        "inspect_candidate",
        "list_workspace",
        "map_evidence",
        "read_workspace",
        "replace_candidate",
        "probe_evidence",
        "probe_contract_semantics",
        "search_evidence",
        "smoke_candidate_component",
        "smoke_candidate_tool",
        "trace_slice",
        "unlock_candidate",
        "write_candidate",
    }


def _write_failure_type_contract(evidence, *, success_policy="optional"):
    (evidence / "contract.json").write_text(
        json.dumps(
            {
                "decision_protocol": "failure_type_v1",
                "success_counterfactual": success_policy,
                "probe_policy": "constrained_evidence_profile_v1",
                "max_components": 3,
                "target_task_ids": ["target-a", "target-c"],
                "protection_task_ids": ["success-b"],
            }
        )
        + "\n"
    )


def _write_semantic_fixture(evidence, tmp_path, *, protocol="semantic_contract_v1"):
    from qea.public_contract_evidence import build_public_contract_index

    qfbench = tmp_path / "qfbench-public"
    qfbench.mkdir()
    commit = "f" * 40
    for task_id in ("target-a", "target-c", "success-b"):
        task = qfbench / "tasks" / task_id
        task.mkdir(parents=True)
        (task / "instruction.md").write_text(
            "# Deliverable\n\n"
            "- Write result.json with a required top-level field.\n"
        )
    task_ids = ("target-a", "target-c", "success-b")
    records = []
    for path in sorted(qfbench.rglob("instruction.md")):
        payload = path.read_bytes()
        records.append(
            {
                "path": path.relative_to(qfbench).as_posix(),
                "git_blob_oid": git_blob_oid(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    (qfbench / "MANIFEST.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "role": "public",
                "repository_url": "https://example.invalid/qfbench.git",
                "commit": commit,
                "task_ids": sorted(task_ids),
                "files": records,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    (qfbench / ".qfbench-revision").write_text(commit + "\n")
    build_public_contract_index(
        qfbench_root=qfbench,
        task_ids=task_ids,
        destination=evidence / "contracts",
        benchmark_commit=commit,
    )
    _write_failure_type_contract(
        evidence, success_policy="required_or_insufficient"
    )
    contract = json.loads((evidence / "contract.json").read_text())
    contract.update(
        {
            "stage": "A6",
            "decision_protocol": protocol,
            "probe_policy": (
                "typed_contract_artifact_trace_v1"
                if protocol == "semantic_contract_v1"
                else "constrained_evidence_profile_v1"
            ),
            "train_task_ids": ["target-a", "target-c", "success-b"],
            "public_contract_evidence": True,
            "public_contract_index": "contracts/index.json",
            "semantic_comparison": (
                "required_for_act"
                if protocol == "semantic_contract_v1"
                else "available_not_required"
            ),
            "evaluator_feedback_tier": "answer_free_public_process",
            "feedback_manifest_digest": None,
        }
    )
    (evidence / "contract.json").write_text(json.dumps(contract) + "\n")
    artifact_root = evidence / "tasks/target-a/artifacts"
    artifact_root.mkdir(parents=True)
    (artifact_root / "result.json").write_text('{"present": 1}\n')
    (evidence / "tasks/target-a/artifact_manifest.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "path": "result.json",
                        "representation": "full_text",
                        "evidence_path": "tasks/target-a/artifacts/result.json",
                    }
                ]
            }
        )
        + "\n"
    )
    (evidence / "tasks/target-a/worker_trace.jsonl").write_text(
        json.dumps(
            {
                "role": "assistant",
                "content": "Validate output schema before completion.",
            }
        )
        + "\n"
    )


def _semantic_probe(*, semantic_relation="contradicts"):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        probe_contract_semantics,
    )

    return probe_contract_semantics(
        probe_id="typed_contract_gap",
        question="Is the required field absent despite a validation phase?",
        hypothesis_expectations={
            "h_schema": {
                "artifact_exists": False,
                "trace_phase_present": True,
            },
            "h_formula": {
                "artifact_exists": True,
                "trace_phase_present": True,
            },
        },
        task_id="target-a",
        clause_id="target-a#c0002",
        artifact_path="tasks/target-a/artifacts/result.json",
        artifact_selector={"kind": "json_pointer", "value": "/required"},
        trace_phase="validation",
        semantic_relation=semantic_relation,
        comparison_claim=(
            "The public clause requires the field, the artifact omits it, and the "
            "trace's validation phase did not make that validation effective."
        ),
    )


def test_semantic_contract_probe_grounds_act_and_unlocks_only_declared_roles(
    guarded_roots, tmp_path
):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        decide_candidate,
        read_workspace,
        write_candidate,
    )

    candidate, evidence, _, _, _ = guarded_roots
    _write_semantic_fixture(evidence, tmp_path)
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    probe = _semantic_probe()
    assert probe["expectation_matches"] == {
        "h_formula": False,
        "h_schema": True,
    }
    assert probe["clause"]["clause_id"] == "target-a#c0002"
    assert probe["artifact"]["value_type"] == "missing"
    assert probe["trace"]["phase_present"] is True
    decision = _failure_type_decision()
    decision["probe_ids_used"] = ["typed_contract_gap"]
    decision["grounded_comparison_probe_ids"] = ["typed_contract_gap"]

    result = decide_candidate(discovery=decision)

    assert result["decision"] == "ACT"
    assert result["grounded_comparison_probe_ids"] == ["typed_contract_gap"]
    write_candidate("validator/contract.md", "Validate the public field.\n")
    assert (candidate / "validator/contract.md").is_file()


def test_semantic_contract_rejects_act_without_discriminating_grounded_triple(
    guarded_roots, tmp_path
):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        read_workspace,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_semantic_fixture(evidence, tmp_path)
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    _semantic_probe()
    decision = _failure_type_decision()
    decision["probe_ids_used"] = ["typed_contract_gap"]
    with pytest.raises(GuardedWorkspaceError, match="grounded_comparison_probe_ids"):
        decide_candidate(discovery=decision)


def test_semantic_contract_rejects_insufficient_relation_for_act(
    guarded_roots, tmp_path
):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        read_workspace,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_semantic_fixture(evidence, tmp_path)
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    _semantic_probe(semantic_relation="insufficient")
    decision = _failure_type_decision()
    decision["probe_ids_used"] = ["typed_contract_gap"]
    decision["grounded_comparison_probe_ids"] = ["typed_contract_gap"]

    with pytest.raises(GuardedWorkspaceError, match="insufficient relation"):
        decide_candidate(discovery=decision)


def test_semantic_contract_abstain_needs_no_grounded_triple_and_keeps_lock(
    guarded_roots, tmp_path
):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        probe_evidence,
        write_candidate,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_semantic_fixture(evidence, tmp_path)
    probe = probe_evidence(
        probe_id="profile_contract",
        question="Does generic evidence discriminate the mechanisms?",
        hypothesis_expectations={"h_schema": "schema", "h_formula": "formula"},
        evidence_paths=["overview.md", "counterexample.md"],
    )
    persisted_probe = json.loads(
        (guarded_roots[-1].parent / "probe-log.jsonl").read_text().splitlines()[0]
    )
    assert persisted_probe["observation"] == probe["observation"]

    result = decide_candidate(discovery=_failure_type_decision(decision="ABSTAIN"))

    assert result["decision"] == "ABSTAIN"
    assert result["grounded_comparison_probe_ids"] == []
    with pytest.raises(GuardedWorkspaceError, match="writes are locked"):
        write_candidate("validator/contract.md", "no write\n")


def test_a6_e_exposes_contracts_without_imposing_semantic_act_gate(
    guarded_roots, tmp_path
):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        decide_candidate,
        probe_evidence,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_semantic_fixture(evidence, tmp_path, protocol="failure_type_v1")
    probe_evidence(
        probe_id="profile_contract",
        question="Does generic evidence discriminate the mechanisms?",
        hypothesis_expectations={"h_schema": "schema", "h_formula": "formula"},
        evidence_paths=["overview.md", "counterexample.md"],
    )

    result = decide_candidate(discovery=_failure_type_decision())

    assert result["decision"] == "ACT"
    assert result["grounded_comparison_probe_ids"] == []


def test_a6_e_preserves_optional_typed_comparison_without_requiring_it(
    guarded_roots, tmp_path
):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        decide_candidate,
        read_workspace,
    )

    _, evidence, _, _, access_log = guarded_roots
    _write_semantic_fixture(evidence, tmp_path, protocol="failure_type_v1")
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    _semantic_probe()
    decision = _failure_type_decision()
    decision["probe_ids_used"] = ["typed_contract_gap"]
    decision["grounded_comparison_probe_ids"] = ["typed_contract_gap"]

    result = decide_candidate(discovery=decision)
    state = json.loads(
        (access_log.parent / "discovery-hypothesis.json").read_text()
    )

    assert result["decision"] == "ACT"
    assert result["grounded_comparison_probe_ids"] == ["typed_contract_gap"]
    assert len(state["hypothesis"]["grounded_semantic_comparisons"]) == 1


def test_semantic_probe_fails_closed_for_higher_evaluator_feedback_tier(
    guarded_roots, tmp_path
):
    from qea.evolve_agent_full.tools.guarded_workspace import GuardedWorkspaceError

    _, evidence, _, _, _ = guarded_roots
    _write_semantic_fixture(evidence, tmp_path)
    contract = json.loads((evidence / "contract.json").read_text())
    contract["evaluator_feedback_tier"] = "raw_verifier_feedback"
    (evidence / "contract.json").write_text(json.dumps(contract) + "\n")

    with pytest.raises(GuardedWorkspaceError, match="feedback tier"):
        _semantic_probe()


def test_semantic_probe_fails_closed_when_a6_feedback_tier_is_missing(
    guarded_roots, tmp_path
):
    from qea.evolve_agent_full.tools.guarded_workspace import GuardedWorkspaceError

    _, evidence, _, _, _ = guarded_roots
    _write_semantic_fixture(evidence, tmp_path)
    contract = json.loads((evidence / "contract.json").read_text())
    contract.pop("evaluator_feedback_tier")
    (evidence / "contract.json").write_text(json.dumps(contract) + "\n")

    with pytest.raises(GuardedWorkspaceError, match="feedback tier"):
        _semantic_probe()


def test_semantic_probe_fails_closed_for_wrong_public_contract_index(
    guarded_roots, tmp_path
):
    from qea.evolve_agent_full.tools.guarded_workspace import GuardedWorkspaceError

    _, evidence, _, _, _ = guarded_roots
    _write_semantic_fixture(evidence, tmp_path)
    contract = json.loads((evidence / "contract.json").read_text())
    contract["public_contract_index"] = "contracts/other.json"
    (evidence / "contract.json").write_text(json.dumps(contract) + "\n")

    with pytest.raises(GuardedWorkspaceError, match="index identity"):
        _semantic_probe()


def test_semantic_probe_fails_closed_for_invalid_feedback_manifest_digest(
    guarded_roots, tmp_path
):
    from qea.evolve_agent_full.tools.guarded_workspace import GuardedWorkspaceError

    _, evidence, _, _, _ = guarded_roots
    _write_semantic_fixture(evidence, tmp_path)
    contract = json.loads((evidence / "contract.json").read_text())
    contract["feedback_manifest_digest"] = "not-a-sha256"
    (evidence / "contract.json").write_text(json.dumps(contract) + "\n")

    with pytest.raises(GuardedWorkspaceError, match="feedback_manifest_digest"):
        _semantic_probe()


def _failure_type_decision(*, decision="ACT", include_counterfactual=True):
    hypotheses = [
        {
            "hypothesis_id": "h_schema",
            "failure_type_id": "t_contract",
            "mechanism": "artifact schema is not checked before completion",
            "failure_prediction": "both targets omit a requested field",
        },
        {
            "hypothesis_id": "h_formula",
            "failure_type_id": "t_contract",
            "mechanism": "the quantitative formula is wrong",
            "failure_prediction": "both targets have structurally valid but wrong values",
        },
    ]
    if include_counterfactual:
        hypotheses[0]["success_counterfactual"] = (
            "schema validation appears before completion while success-b is preserved"
        )
        hypotheses[1]["insufficient_contrast"] = True
    payload = {
        "decision": decision,
        "failure_types": [
            {
                "type_id": "t_contract",
                "label": "deliverable contract drift",
                "member_tasks": ["target-a", "target-c"],
                "excluded_tasks": [],
                "matched_success_tasks": ["success-b"],
                "evidence_refs": ["overview.md", "counterexample.md"],
            }
        ],
        "hypotheses_considered": hypotheses,
        "selected_hypothesis_id": "h_schema" if decision == "ACT" else None,
        "probe_ids_used": ["profile_contract"],
        "hypotheses_eliminated": ["h_formula"] if decision == "ACT" else [],
        "evidence_refs": ["overview.md", "counterexample.md"],
        "counterevidence": "success-b completed without the proposed validator",
        "uncertainty": "only one trace per task is available",
    }
    if decision == "ACT":
        payload.update(
            {
                "components": ["tools", "validator"],
                "prediction": {
                    "targets": "schema validation appears and reward improves"
                },
                "risk_tasks": ["success-b"],
            }
        )
    else:
        payload["abstain_reason"] = "the probe did not distinguish the mechanisms"
    return payload


def _write_quant_v2_contract(evidence: Path, *, history_required: bool = True):
    (evidence / "contract.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "stage": "PGBHS_V2",
                "benchmark": "quantcodeeval",
                "decision_protocol": "quant_property_v2",
                "feedback_tier": "answer_free_property_family_v2",
                "task_ids": ["T16", "T24"],
                "target_task_ids": ["T24"],
                "protection_task_ids": ["T16"],
                "history_required": history_required,
                "max_primary_components": 2,
                "max_declared_components": 6,
                "preferred_primary_components": {
                    "formula_parameterization": ["tools", "skills", "memory"]
                },
                "research_state_transition_required_for_act": True,
                "quant_failure_classification_required_for_act": True,
                "oracle_fields_exposed": False,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    history = evidence / "history" / "archive"
    (history / "entries").mkdir(parents=True)
    (history / "diffs").mkdir()
    (history / "entries" / "prior.json").write_text(
        '{"selection":"rejected","mechanism":"prompt-only guidance"}\n',
        encoding="utf-8",
    )
    (history / "diffs" / "prior.patch").write_text(
        "--- systemprompt.md\n+++ systemprompt.md\n@@ ineffective guidance\n",
        encoding="utf-8",
    )


def _write_flexible_quant_v2_contract(
    evidence: Path, *, history_required: bool = True
):
    _write_quant_v2_contract(evidence, history_required=history_required)
    contract_path = evidence / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["quant_failure_classification_required_for_act"] = False
    contract["domain_tags_are_extensible"] = True
    contract_path.write_text(json.dumps(contract, sort_keys=True) + "\n", encoding="utf-8")
    experience = evidence / "history" / "experience"
    experience.mkdir(parents=True)
    (experience / "RELEVANT.json").write_text(
        '{"experiences":[{"experience_key":"experience-0001",'
        '"prediction_result":"not_supported"}]}\n',
        encoding="utf-8",
    )


def _quant_v2_decision():
    return {
        "decision": "ACT",
        "failure_class": "formula_parameterization",
        "breakdown_stage": "implementation_realization",
        "observed_symptoms": [
            "the submitted library mapping differs from the stated estimator"
        ],
        "adjacent_failure_classes_considered": ["temporal_causality"],
        "class_selection_reason": (
            "the dates align, but the formula-to-library parameter identity differs"
        ),
        "component_state_target": (
            "the executable mapping from the paper identity to library arguments"
        ),
        "research_state_transition": {
            "state_id": "research_operation",
            "expected_state": "the stated estimator is realized by the implementation",
            "observed_state": "the library mapping realizes a different estimator",
            "target_state": "a fresh Worker realizes the stated estimator",
            "transition_observable": (
                "the selected tool activates and the resulting implementation passes "
                "the public estimator fixture"
            ),
        },
        "hypotheses_considered": [
            {
                "hypothesis_id": "h_operation",
                "mechanism": "the worker repeatedly implements a fragile estimator",
                "prediction": "a deterministic tool is called before strategy output",
            },
            {
                "hypothesis_id": "h_prompt",
                "mechanism": "the general reasoning instructions are underspecified",
                "prediction": "more prose alone changes the calculation trace",
            },
        ],
        "selected_hypothesis_id": "h_operation",
        "evidence_refs": [
            "overview.md",
            "history/archive/diffs/prior.patch",
        ],
        "counterevidence": "the existing worker can already write a strategy module",
        "uncertainty": "the official property family is answer-free and coarse",
        "primary_components": ["tools"],
        "components": ["agent_config", "tool_descriptions", "tools"],
        "prediction": {"T24": "the new operation activates and reward does not regress"},
        "risk_tasks": ["T16"],
    }


def test_quant_v2_uses_exact_history_and_unlocks_binding_components(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        read_workspace,
        write_candidate,
    )

    candidate, evidence, _, _, _ = guarded_roots
    _write_quant_v2_contract(evidence)
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(
        source="evidence", file_path="history/archive/diffs/prior.patch"
    )

    result = decide_candidate(discovery=_quant_v2_decision())

    assert result["decision"] == "ACT"
    assert result["primary_components"] == ["tools"]
    assert result["components"] == ["agent_config", "tool_descriptions", "tools"]
    assert result["research_state_transition"]["state_id"] == "research_operation"
    write_candidate("tools/estimator.py", "def estimate(values):\n    return sum(values)\n")
    write_candidate("tool_descriptions/estimator.tool.yaml", "type: tool\n")
    with pytest.raises(GuardedWorkspaceError, match="undeclared component"):
        write_candidate("systemprompt.md", "unrelated broad rewrite\n")
    assert (candidate / "tools/estimator.py").is_file()


def test_quant_v2_act_requires_research_state_transition(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        read_workspace,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_quant_v2_contract(evidence, history_required=False)
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    decision = _quant_v2_decision()
    decision["evidence_refs"] = ["overview.md", "counterexample.md"]
    decision.pop("research_state_transition")

    with pytest.raises(GuardedWorkspaceError, match="research_state_transition"):
        decide_candidate(discovery=decision)


def test_quant_v2_autonomous_probe_contract_requires_experiment_spec(
    guarded_roots,
):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        read_workspace,
    )

    _, evidence, _, _, access_log = guarded_roots
    _write_quant_v2_contract(evidence, history_required=False)
    contract_path = evidence / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["autonomous_probe_required"] = True
    contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    decision = _quant_v2_decision()
    decision["evidence_refs"] = ["overview.md", "counterexample.md"]

    with pytest.raises(GuardedWorkspaceError, match="experiment_spec"):
        decide_candidate(discovery=decision)

    decision["experiment_spec"] = {
        "mode": "repair",
        "seed_experience": "t26_h0",
        "worker_instruction": "Repair the public artifact and run a smoke.",
        "max_iterations": 8,
        "prediction": "The estimator failure should disappear.",
        "decision_changing_observation": "If unchanged, roll back the component.",
    }
    result = decide_candidate(discovery=decision)
    state = json.loads(
        (access_log.parent / "discovery-hypothesis.json").read_text()
    )

    assert result["decision"] == "ACT"
    assert state["hypothesis"]["experiment_spec"]["seed_experience"] == "t26_h0"


def test_quant_v2_coordinated_act_cites_both_tasks_and_selects_one_target(
    guarded_roots,
):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        read_workspace,
    )

    _, evidence, _, _, access_log = guarded_roots
    _write_flexible_quant_v2_contract(evidence, history_required=False)
    task_paths = {
        "qfbench:curve-target": "benchmarks/qfbench/tasks/curve-target/trace.jsonl",
        "qfbench:curve-protection": (
            "benchmarks/qfbench/tasks/curve-protection/trace.jsonl"
        ),
    }
    for path in task_paths.values():
        target = evidence / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{\"event\":\"curve construction\"}\n", encoding="utf-8")
        read_workspace(source="evidence", file_path=path)
    contract_path = evidence / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract.update(
        {
            "stage": "COORDINATED_BREADTH",
            "task_keys": list(task_paths),
            "target_task_keys": ["qfbench:curve-target"],
            "protection_task_keys": ["qfbench:curve-protection"],
            "task_evidence_prefixes": {
                key: [path.rsplit("/", 1)[0] + "/"]
                for key, path in task_paths.items()
            },
            "coordinated_evidence_required_for_act": True,
            "autonomous_probe_required": True,
            "probe_seed_policy": "none",
            "max_worker_probes_this_round": 1,
        }
    )
    contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
    decision = _quant_v2_decision()
    decision["evidence_refs"] = list(task_paths.values())
    decision["shared_mechanism"] = (
        "quote-to-discount-factor construction closed by instrument repricing"
    )
    decision["probe_task_key"] = "qfbench:curve-target"
    decision["experiment_spec"] = {
        "mode": "from_scratch",
        "seed_experience": None,
        "worker_instruction": "Build the curve and reconcile every input quote.",
        "max_iterations": 8,
        "prediction": "The Worker will act on a repricing residual before delivery.",
        "decision_changing_observation": (
            "No residual-driven artifact edit means the mechanism is unsupported."
        ),
    }

    result = decide_candidate(discovery=decision)
    state = json.loads(
        (access_log.parent / "discovery-hypothesis.json").read_text()
    )

    assert result["decision"] == "ACT"
    assert state["hypothesis"]["probe_task_key"] == "qfbench:curve-target"
    assert state["hypothesis"]["shared_mechanism"].startswith("quote-to")

    decision["probe_task_key"] = "qfbench:curve-protection"
    with pytest.raises(GuardedWorkspaceError, match="predeclared target"):
        decide_candidate(discovery=decision)

    decision["probe_task_key"] = "qfbench:curve-target"
    decision["evidence_refs"] = [task_paths["qfbench:curve-target"], "overview.md"]
    read_workspace(source="evidence", file_path="overview.md")
    with pytest.raises(GuardedWorkspaceError, match="every coordinated task"):
        decide_candidate(discovery=decision)


def test_quant_v2_forbids_legacy_unlock_and_schema_uses_prediction(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        unlock_candidate,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_quant_v2_contract(evidence, history_required=False)

    schema = (
        Path(__file__).resolve().parents[1]
        / "qea/evolve_agent_full/tool_descriptions/decide_candidate.tool.yaml"
    ).read_text()
    assert "prediction: {type: string}" in schema
    assert "failure_prediction" not in schema
    with pytest.raises(GuardedWorkspaceError, match="legacy unlock is forbidden"):
        unlock_candidate(
            hypothesis={
                "selected_mechanism": "legacy path",
                "counterevidence": "counter",
                "uncertainty": "uncertain",
                "discriminating_probe": "probe",
                "hypotheses_considered": ["h1", "h2"],
                "evidence_refs": ["overview.md", "counterexample.md"],
                "component": "tools",
                "risk_tasks": [],
                "prediction": "change",
            }
        )


def test_quant_v2_rejects_unread_or_missing_exact_history(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        read_workspace,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_quant_v2_contract(evidence)
    read_workspace(source="evidence", file_path="overview.md")
    decision = _quant_v2_decision()
    decision["evidence_refs"] = ["overview.md", "counterexample.md"]
    read_workspace(source="evidence", file_path="counterexample.md")

    with pytest.raises(GuardedWorkspaceError, match="exact prior entry"):
        decide_candidate(discovery=decision)


def test_quant_v2_component_prior_is_advisory_but_requires_override_reason(
    guarded_roots,
):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        read_workspace,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_quant_v2_contract(evidence, history_required=False)
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    decision = _quant_v2_decision()
    decision["evidence_refs"] = ["overview.md", "counterexample.md"]
    decision["primary_components"] = ["middleware"]
    decision["components"] = ["middleware"]
    with pytest.raises(GuardedWorkspaceError, match="component_override_reason"):
        decide_candidate(discovery=decision)

    decision["component_override_reason"] = (
        "the trace stops before the estimator can run, so loop recovery is causal"
    )
    assert decide_candidate(discovery=decision)["primary_components"] == [
        "middleware"
    ]


def test_quant_v2_act_requires_two_axis_finance_localization(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        read_workspace,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_quant_v2_contract(evidence, history_required=False)
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    decision = _quant_v2_decision()
    decision["evidence_refs"] = ["overview.md", "counterexample.md"]
    decision.pop("breakdown_stage")
    with pytest.raises(GuardedWorkspaceError, match="breakdown_stage"):
        decide_candidate(discovery=decision)

    decision = _quant_v2_decision()
    decision["evidence_refs"] = ["overview.md", "counterexample.md"]
    decision["adjacent_failure_classes_considered"] = [
        "formula_parameterization"
    ]
    with pytest.raises(GuardedWorkspaceError, match="must differ"):
        decide_candidate(discovery=decision)


def test_quant_v2_accepts_extensible_domain_tags_and_experience_operator(
    guarded_roots,
):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        decide_candidate,
        read_workspace,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_flexible_quant_v2_contract(evidence)
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(
        source="evidence", file_path="history/experience/RELEVANT.json"
    )
    read_workspace(source="evidence", file_path="history/archive/diffs/prior.patch")
    decision = _quant_v2_decision()
    for field in (
        "failure_class",
        "breakdown_stage",
        "observed_symptoms",
        "adjacent_failure_classes_considered",
        "class_selection_reason",
        "component_state_target",
    ):
        decision.pop(field)
    decision["evidence_refs"] = [
        "overview.md",
        "history/experience/RELEVANT.json",
        "history/archive/diffs/prior.patch",
    ]
    decision["domain_tags"] = [
        "cross-sectional rank semantics",
        "warm-up window availability",
    ]
    decision["search_operator"] = "FUSE"

    result = decide_candidate(discovery=decision)

    assert result["decision"] == "ACT"
    assert result["failure_class"] == "unclassified"


@pytest.mark.parametrize(
    "operator", ["REFINE", "SPLIT", "COMPOSE", "SYNTHESIZE", "ROUTE"]
)
def test_quant_v2_accepts_component_search_operators(guarded_roots, operator):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        decide_candidate,
        read_workspace,
    )

    _, evidence, _, _, access_log = guarded_roots
    _write_flexible_quant_v2_contract(evidence, history_required=False)
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    decision = _quant_v2_decision()
    decision["evidence_refs"] = ["overview.md", "counterexample.md"]
    decision["search_operator"] = operator

    result = decide_candidate(discovery=decision)
    state = json.loads(
        (access_log.parent / "discovery-hypothesis.json").read_text()
    )

    assert result["decision"] == "ACT"
    assert state["hypothesis"]["search_operator"] == operator


def test_answer_rich_quant_act_requires_transferable_failure_signature(
    guarded_roots,
):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        read_workspace,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_flexible_quant_v2_contract(evidence, history_required=False)
    contract_path = evidence / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["feedback_tier"] = "answer_rich_optimization_v1"
    contract["failure_signature_required_for_act"] = True
    contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    decision = _quant_v2_decision()
    decision["evidence_refs"] = ["overview.md", "counterexample.md"]
    decision["search_operator"] = "SPLIT"

    with pytest.raises(GuardedWorkspaceError, match="failure_signature"):
        decide_candidate(discovery=decision)

    decision["failure_signature"] = {
        "mechanism_family": "task_conditioned_formula_reconciliation",
        "semantic_state": "public formula and unit state",
        "pipeline_phase": "estimation through final reconciliation",
        "observable": "intermediate formula and final metrics disagree",
    }
    result = decide_candidate(discovery=decision)

    assert result["decision"] == "ACT"
    assert result["failure_signature"]["mechanism_family"] == (
        "task_conditioned_formula_reconciliation"
    )


def test_failure_type_probe_can_unlock_two_declared_components(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        probe_evidence,
        write_candidate,
    )

    candidate, evidence, _, _, _ = guarded_roots
    _write_failure_type_contract(evidence)
    probe = probe_evidence(
        probe_id="profile_contract",
        question="Do failures differ structurally from the success?",
        hypothesis_expectations={
            "h_schema": "failed evidence has a structural contract gap",
            "h_formula": "structures match and only numeric behavior differs",
        },
        evidence_paths=["overview.md", "counterexample.md"],
    )
    assert probe["result_sha256"]

    result = decide_candidate(discovery=_failure_type_decision())

    assert result["decision"] == "ACT"
    assert result["components"] == ["tools", "validator"]
    write_candidate("tools/check.py", "def check():\n    return True\n")
    write_candidate("validator/contract.md", "Validate public schemas.\n")
    with pytest.raises(GuardedWorkspaceError, match="undeclared component"):
        write_candidate("systemprompt.md", "broad rewrite\n")
    assert (candidate / "tools/check.py").is_file()


def test_failure_type_abstain_keeps_writes_locked(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        probe_evidence,
        write_candidate,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_failure_type_contract(evidence)
    probe_evidence(
        probe_id="profile_contract",
        question="Can the observations separate schema and formula mechanisms?",
        hypothesis_expectations={"h_schema": "schema gap", "h_formula": "numeric gap"},
        evidence_paths=["overview.md", "counterexample.md"],
    )

    result = decide_candidate(discovery=_failure_type_decision(decision="ABSTAIN"))

    assert result["decision"] == "ABSTAIN"
    assert result["unlocked"] is False
    with pytest.raises(GuardedWorkspaceError, match="writes are locked"):
        write_candidate("tools/check.py", "pass\n")


def test_contrastive_contract_rejects_invented_missing_success_condition(
    guarded_roots,
):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        decide_candidate,
        probe_evidence,
    )

    _, evidence, _, _, _ = guarded_roots
    _write_failure_type_contract(
        evidence, success_policy="required_or_insufficient"
    )
    probe_evidence(
        probe_id="profile_contract",
        question="Can the observations separate schema and formula mechanisms?",
        hypothesis_expectations={"h_schema": "schema gap", "h_formula": "numeric gap"},
        evidence_paths=["overview.md", "counterexample.md"],
    )

    with pytest.raises(GuardedWorkspaceError, match="success counterfactual"):
        decide_candidate(
            discovery=_failure_type_decision(include_counterfactual=False)
        )


def test_candidate_writes_require_evidence_backed_unlock(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        GuardedWorkspaceError,
        read_workspace,
        unlock_candidate,
        write_candidate,
    )

    with pytest.raises(GuardedWorkspaceError, match="writes are locked"):
        write_candidate(file_path="memory/note.md", content="note\n")

    read_workspace(source="evidence", file_path="overview.md")
    with pytest.raises(GuardedWorkspaceError, match="read or inspected"):
        unlock_candidate(
            hypothesis={
                "hypotheses_considered": ["one", "two"],
                "selected_mechanism": "one",
                "evidence_refs": ["overview.md", "counterexample.md"],
                "counterevidence": "two",
                "uncertainty": "limited evidence",
                "discriminating_probe": "compare",
                "component": "memory",
                "prediction": "fewer repeated derivations",
                "risk_tasks": [],
            }
        )

    _unlock(component="memory")
    assert write_candidate(
        file_path="memory/note.md", content="note\n"
    )["bytes_written"] == 5


def test_discovery_queries_map_slice_and_compare_authorized_evidence(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        compare_evidence,
        map_evidence,
        trace_slice,
    )

    mapped = map_evidence()
    assert mapped["file_count"] == 2
    assert mapped["categories"] == {"other": 2}
    assert [item["path"] for item in mapped["files"]] == [
        "counterexample.md",
        "overview.md",
    ]

    sliced = trace_slice(
        file_path="overview.md", pattern="deliverable", context_lines=0
    )
    assert sliced["matches"][0]["match_line"] == 1
    assert "task-a failed" in sliced["matches"][0]["content"]

    compared = compare_evidence("overview.md", "counterexample.md")
    assert "--- overview.md" in compared["diff"]
    assert "+task-b succeeded" in compared["diff"]


def test_trace_slice_bounds_one_large_runtime_line(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import trace_slice

    _, evidence, _, _, _ = guarded_roots
    large_line = "prefix " + ("x" * 100_000) + " component-called tail"
    (evidence / "runtime.jsonl").write_text(large_line + "\n", encoding="utf-8")

    sliced = trace_slice(
        file_path="runtime.jsonl",
        pattern="component-called",
        context_lines=0,
        max_matches=1,
    )

    content = sliced["matches"][0]["content"]
    assert "component-called" in content
    assert "earlier text omitted" in content
    assert len(content.encode("utf-8")) < 9_000


def test_inspect_candidate_reports_components_bindings_and_syntax(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import inspect_candidate

    candidate, _, _, _, _ = guarded_roots
    (candidate / "agent.yaml").write_text(
        "tools:\n"
        "  - name: calc\n"
        "    yaml_path: ./tool_descriptions/calc.tool.yaml\n"
        "    binding: tools.calc:add\n"
        "skills:\n"
        "  - ./skills/quant-contract\n"
    )
    (candidate / "tools").mkdir()
    (candidate / "tools/calc.py").write_text(
        "def add(a, b):\n    return a + b\n"
    )
    (candidate / "tool_descriptions").mkdir()
    (candidate / "tool_descriptions/calc.tool.yaml").write_text(
        "type: tool\nname: calc\n"
    )
    (candidate / "skills/quant-contract").mkdir(parents=True)
    (candidate / "skills/quant-contract/SKILL.md").write_text("# Quant contract\n")

    report = inspect_candidate()
    assert report["valid"] is True
    assert report["issues"] == []
    assert "tools/calc.py" in report["components"]["tools"]
    assert {item["kind"] for item in report["declarations"]} == {"tool", "skill"}


def test_component_smoke_is_bound_to_exact_candidate_digest(guarded_roots):
    from qea.evolve_agent_full.tools.guarded_workspace import (
        decide_candidate,
        read_workspace,
        smoke_candidate_component,
        write_candidate,
    )
    from qea.worker_identity import hash_worker_directory

    candidate, evidence, _, _, _ = guarded_roots
    _write_quant_v2_contract(evidence, history_required=False)
    read_workspace(source="evidence", file_path="overview.md")
    read_workspace(source="evidence", file_path="counterexample.md")
    decision = _quant_v2_decision()
    decision["evidence_refs"] = ["overview.md", "counterexample.md"]
    decide_candidate(discovery=decision)
    write_candidate("tools/checkpoint.py", "def checkpoint():\n    return {'ok': True}\n")

    record = smoke_candidate_component(
        component="tools",
        target="tools.checkpoint",
        operation="call",
        symbol="checkpoint",
    )

    assert record["status"] == "passed"
    assert record["candidate_digest"] == hash_worker_directory(candidate)
    write_candidate(
        "tools/checkpoint.py", "def checkpoint():\n    return {'ok': False}\n"
    )
    assert record["candidate_digest"] != hash_worker_directory(candidate)
