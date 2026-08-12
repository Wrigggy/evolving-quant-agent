import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from qea.evolution_evidence import EvidenceRecord
from qea.loop_benchmark import hash_worker_directory
from qea.quantcodeeval_history import materialize_quantcodeeval_history_evidence
from qea.quantcodeeval_search import (
    QuantSearchLimits,
    SearchSelection,
    SearchStopReason,
    initialize_quantcodeeval_search,
)
from qea.quantcodeeval_v2_loop import (
    QuantCandidateEvaluation,
    run_quantcodeeval_v2_loop,
)


def _record(root: Path) -> EvidenceRecord:
    digest = hashlib.sha256()
    members = []
    for path in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
        if not path.is_file() or path.name == "access_log.jsonl":
            continue
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        encoded = relative.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        members.append(relative)
    return EvidenceRecord(root=root, sha256=digest.hexdigest(), members=tuple(members))


def _add_tool(candidate: Path) -> None:
    (candidate / "tools").mkdir()
    (candidate / "tools/__init__.py").write_text("", encoding="utf-8")
    (candidate / "tools/robust_estimator.py").write_text(
        "def robust_estimator(values):\n"
        "    values = [float(value) for value in values]\n"
        "    return {'estimate': sum(values) / len(values)}\n",
        encoding="utf-8",
    )
    (candidate / "tool_descriptions/robust_estimator.tool.yaml").write_text(
        "type: tool\n"
        "name: robust_estimator\n"
        "description: Compute a deterministic arithmetic estimate.\n"
        "input_schema:\n"
        "  type: object\n"
        "  properties:\n"
        "    values:\n"
        "      type: array\n"
        "      items: {type: number}\n"
        "  required: [values]\n"
        "  additionalProperties: false\n",
        encoding="utf-8",
    )
    agent = (candidate / "agent.yaml").read_text(encoding="utf-8")
    agent = agent.replace(
        "\ntracers:\n",
        "\n  - name: robust_estimator\n"
        "    yaml_path: ./tool_descriptions/robust_estimator.tool.yaml\n"
        "    binding: tools.robust_estimator:robust_estimator\n"
        "\ntracers:\n",
    )
    (candidate / "agent.yaml").write_text(agent, encoding="utf-8")


class FakeProposer:
    def __init__(self):
        self.saw_rejected_diff = False

    def propose(self, **kwargs):
        iteration = kwargs["iteration"]
        parent = Path(kwargs["candidate_dir"])
        evidence = kwargs["evidence_dir"].root
        root = Path(kwargs["run_dir"]) / "fake-proposals" / f"round-{iteration}"
        candidate = root / "candidate"
        root.mkdir(parents=True)
        shutil.copytree(parent, candidate)
        if iteration == 1:
            prompt = candidate / "systemprompt.md"
            prompt.write_text(
                prompt.read_text(encoding="utf-8")
                + "Always add generic estimation prose.\n",
                encoding="utf-8",
            )
            components = ["systemprompt"]
            primary = ["systemprompt"]
            selected = "h_prompt"
            hypotheses = [
                {
                    "hypothesis_id": "h_prompt",
                    "mechanism": "generic prompt guidance is missing",
                    "prediction": "the task reward improves",
                },
                {
                    "hypothesis_id": "h_tool",
                    "mechanism": "a deterministic operation is missing",
                    "prediction": "a tool must activate",
                },
            ]
        else:
            patches = list((evidence / "history/archive/diffs").glob("*.patch"))
            assert len(patches) == 1
            self.saw_rejected_diff = "generic estimation prose" in patches[0].read_text()
            assert self.saw_rejected_diff
            _add_tool(candidate)
            components = ["agent_config", "tool_descriptions", "tools"]
            primary = ["tools"]
            selected = "h_tool"
            hypotheses = [
                {
                    "hypothesis_id": "h_tool",
                    "mechanism": "a deterministic estimator operation is missing",
                    "prediction": "the tool activates and T24 improves",
                },
                {
                    "hypothesis_id": "h_prompt",
                    "mechanism": "generic prompt guidance is missing",
                    "prediction": "repeat the rejected prompt-only effect",
                },
            ]
        decision = {
            "decision": "ACT",
            "failure_class": "quant_definition_estimation",
            "hypotheses_considered": hypotheses,
            "selected_hypothesis_id": selected,
            "evidence_refs": ["contract.json", "history/SUMMARY.json"],
            "counterevidence": "the worker already produces strategy.py",
            "uncertainty": "property-family feedback remains answer-free",
            "primary_components": primary,
            "components": components,
            "prediction": {"T24": "improve"},
            "risk_tasks": ["T16"],
        }
        component_tests = []
        if iteration == 2:
            component_tests = [
                {
                    "schema_version": 1,
                    "test_index": 1,
                    "component": "tools",
                    "operation": "call",
                    "target": "tools.robust_estimator:robust_estimator",
                    "status": "passed",
                    "exit_code": 0,
                }
            ]
        summary = {
            "model_usage": [],
            "component_tests": component_tests,
            "discovery_hypothesis": {
                "schema_version": 4,
                "protocol": "quant_property_v2",
                "decision": "ACT",
                "unlocked": True,
                "hypothesis": decision,
            },
        }
        summary_path = root / "summary.json"
        prediction_path = root / "prediction.json"
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
        prediction_path.write_text(
            json.dumps({"decision": "ACT", "round": iteration}), encoding="utf-8"
        )
        return SimpleNamespace(
            candidate_dir=candidate,
            candidate_digest=hash_worker_directory(candidate),
            summary_uri=summary_path,
            prediction_uri=prediction_path,
        )


def test_no_model_loop_reuses_rejected_round_and_promotes_full_component(tmp_path):
    source = Path(__file__).resolve().parents[1] / "qea/worker_gdpval_weak"
    seed = tmp_path / "seed"
    shutil.copytree(source, seed)
    evolver = tmp_path / "evolver"
    evolver.mkdir()
    (evolver / "agent.yaml").write_text("name: fake\n", encoding="utf-8")
    run = tmp_path / "run"
    proposer = FakeProposer()
    state = initialize_quantcodeeval_search(
        run_id="qce-v2-no-model",
        h0_digest=hash_worker_directory(seed),
        h0_official_rewards={"T16": 1.0, "T24": 0.0},
        limits=QuantSearchLimits(max_rounds=8),
    )

    def evidence_builder(current, iteration, history_root):
        root = run / "evidence" / f"round-{iteration}"
        root.mkdir(parents=True)
        (root / "access_log.jsonl").write_text("", encoding="utf-8")
        (root / "contract.json").write_text(
            json.dumps({"decision_protocol": "quant_property_v2"}), encoding="utf-8"
        )
        history = root / "history"
        history.mkdir()
        if history_root is not None:
            projection = materialize_quantcodeeval_history_evidence(
                history_root=history_root,
                destination=history / "archive",
            )
            count = projection["entry_count"]
        else:
            count = 0
        (history / "SUMMARY.json").write_text(
            json.dumps({"entry_count": count}), encoding="utf-8"
        )
        return _record(root)

    def activation(candidate, decision, iteration):
        return {
            "status": "passed",
            "iteration": iteration,
            "activated_primary_components": decision["primary_components"],
        }

    def evaluate(parent, candidate, decision, tests, activation, iteration):
        if iteration == 1:
            return QuantCandidateEvaluation(
                official_rewards={"T16": 1.0, "T24": 0.0},
                answer_free_evaluation={"T16": "pass", "T24": "incomplete"},
                official_evaluated=True,
                new_information=False,
                reason="prompt-only mutation produced no property-family change",
                model_requests=2,
            )
        assert decision["primary_components"] == ["tools"]
        assert tests[0]["component"] == "tools"
        assert tests[0]["status"] == "passed"
        assert tests[-1]["kind"] == "independent_full_harness_admission"
        return QuantCandidateEvaluation(
            official_rewards={"T16": 1.0, "T24": 1.0},
            answer_free_evaluation={"T16": "pass", "T24": "pass"},
            official_evaluated=True,
            new_information=True,
            reason="deterministic estimator improved the fixed task panel",
            model_requests=2,
        )

    final = run_quantcodeeval_v2_loop(
        state=state,
        run_dir=run,
        seed_worker_dir=seed,
        evolver_dir=evolver,
        proposer=proposer,
        evidence_builder=evidence_builder,
        activation_runner=activation,
        candidate_evaluator=evaluate,
        diagnosis_builder=lambda current, iteration: f"round {iteration}",
    )

    assert final.stopped is True
    assert final.stop_reason is SearchStopReason.TARGET_REACHED
    assert [round.selection for round in final.rounds] == [
        SearchSelection.REJECTED,
        SearchSelection.OFFICIAL_PROMOTED,
    ]
    assert proposer.saw_rejected_diff is True
    assert final.official_rewards == {"T16": 1.0, "T24": 1.0}
    assert (run / "SEARCH-STATE.json").is_file()
    assert len(list((run / "history/entries").glob("*.json"))) == 2
    second = json.loads((run / "rounds/iteration-0002.json").read_text())
    assert second["decision"]["primary_components"] == ["tools"]
    assert second["component_tests"][0]["status"] == "passed"
