import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from qea.evaluation import OfficialTaskScore, aggregate_domain_macro


AGENT_YAML = """\
type: agent
name: qea_worker
max_context_tokens: 200000
system_prompt: ./systemprompt.md
system_prompt_type: jinja
tool_call_mode: openai
max_iterations: 60
llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  max_tokens: 32000
  temperature: 0.2
  stream: true
  api_type: openai_chat_completion
  timeout: 180
tools:
  - name: run_shell_command
    yaml_path: ./tool_descriptions/run_shell_command.tool.yaml
    binding: nexau.archs.tool.builtin.shell_tools.run_shell_command:run_shell_command
tracers:
  - import: nexau.archs.tracer.adapters.in_memory:InMemoryTracer
"""


SHELL_TOOL = """\
type: tool
name: run_shell_command
description: Run a command in the public task workspace.
input_schema:
  type: object
  properties:
    command: {type: string}
  required: [command]
  additionalProperties: false
"""


def _seed_worker(tmp_path: Path) -> Path:
    seed = tmp_path / "seed"
    (seed / "tool_descriptions").mkdir(parents=True)
    (seed / "agent.yaml").write_text(AGENT_YAML)
    (seed / "systemprompt.md").write_text("Solve the public task.\n")
    (seed / "tool_descriptions/run_shell_command.tool.yaml").write_text(SHELL_TOOL)
    return seed


def _task(tmp_path: Path, task_id: str, domain: str, lineage: str, marker: str):
    root = tmp_path / "tasks" / task_id
    (root / "environment" / "data").mkdir(parents=True)
    instruction = root / "instruction.md"
    data = root / "environment" / "data" / "input.txt"
    instruction.write_text(f"PUBLIC INSTRUCTION {marker}\n")
    data.write_text(f"PUBLIC DATA {marker}\n")
    return SimpleNamespace(
        task_id=task_id,
        domain=domain,
        lineage=lineage,
        root=root,
        worker_files=(instruction, data),
    )


def _tasks(tmp_path: Path):
    optimize = (
        _task(tmp_path, "risk-train", "risk", "risk-lineage", "RISK"),
        _task(
            tmp_path,
            "strategy-train",
            "strategy",
            "strategy-lineage",
            "STRATEGY",
        ),
    )
    held_out = (
        _task(
            tmp_path,
            "fx-secret-holdout",
            "fx",
            "fx-lineage",
            "HELDOUT_CANARY",
        ),
    )
    return optimize, held_out


def _contracts(tmp_path: Path, optimize) -> tuple[Path, Path]:
    rubric = tmp_path / "feedback.json"
    mapping = tmp_path / "mapping.json"
    rubric.write_text(json.dumps({
        "schema_version": 1,
        "tasks": {
            task.task_id: {
                "criteria": [{
                    "criterion_id": "required_output",
                    "requirement": "Produce the requested public deliverable.",
                    "evidence_kind": "missing_output",
                }]
            }
            for task in optimize
        },
    }))
    mapping.write_text(json.dumps({
        "schema_version": 1,
        "tasks": {task.task_id: [] for task in optimize},
    }))
    return rubric, mapping


class RecordingEvaluator:
    def __init__(self):
        self.calls = []

    def evaluate(self, *, worker_dir, tasks, split, checkpoint, run_dir):
        markers = (worker_dir / "systemprompt.md").read_text().count("IMPROVEMENT")
        self.calls.append((
            split,
            checkpoint,
            tuple(task.task_id for task in tasks),
            markers,
        ))
        reward = 0.8 if split == "held_out" else 0.2 + 0.1 * markers
        scores = []
        for task in tasks:
            score = OfficialTaskScore(
                task_id=task.task_id,
                domain=task.domain,
                reward=reward,
                diagnostic_tags=("tests_failed",) if reward < 1 else (),
            )
            scores.append(score)
            attempt_id = hashlib.sha256(
                f"{split}:{checkpoint}:{task.task_id}:{markers}".encode()
            ).hexdigest()[:24]
            attempt_dir = run_dir / "attempts" / attempt_id
            (attempt_dir / "artifacts").mkdir(parents=True, exist_ok=True)
            (attempt_dir / "attempt.json").write_text(json.dumps({
                "attempt_id": attempt_id,
                "task_id": task.task_id,
                "split": split,
                "checkpoint": checkpoint,
            }))
            (attempt_dir / "completed-score.json").write_text(
                json.dumps(asdict(score))
            )
            trace_marker = (
                "HELDOUT PRIVATE TRACE"
                if split == "held_out"
                else f"OPTIMIZE TRACE {task.task_id}"
            )
            (attempt_dir / "raw-trace.jsonl").write_text(trace_marker + "\n")
            (attempt_dir / "final.txt").write_text("worker final\n")
            (attempt_dir / "artifacts" / "deliverable.txt").write_text(
                f"artifact {trace_marker}\n"
            )
            (attempt_dir / "worker-execution.json").write_text(json.dumps({
                "attempt_id": attempt_id,
                "trace_uri": "raw-trace.jsonl",
                "final_text_uri": "final.txt",
                "artifact_dir": "artifacts",
                "summary": {"turns": 1},
            }))
        return aggregate_domain_macro(scores)


def _config(tmp_path, *, run_id, seed, rubric, mapping, mode):
    from qea.loop_benchmark import BenchmarkEvolutionConfig

    return BenchmarkEvolutionConfig(
        run_id=run_id,
        n_iters=3,
        results_dir=tmp_path / "results",
        seed_worker_dir=seed,
        noise_floor=0.0,
        feedback_mode=mode,
        public_rubric_path=rubric,
        verifier_mapping_path=mapping,
        model_identity="deepseek/deepseek-v4-pro",
        template_identity_digest="template-set-fixture",
    )


def _corpus_text(root: Path) -> str:
    return "\n".join(
        path.read_text(errors="replace")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def test_control_and_rich_use_same_calls_and_policy_but_different_evidence(tmp_path):
    from qea.loop_benchmark import run_benchmark_evolution

    optimize, held_out = _tasks(tmp_path)
    rubric, mapping = _contracts(tmp_path, optimize)
    seed = _seed_worker(tmp_path)
    observations = {}
    evaluators = {}
    results = {}

    for mode in ("control", "rich"):
        evaluator = RecordingEvaluator()
        evaluators[mode] = evaluator
        seen = []

        def proposer(context, *, _seen=seen):
            _seen.append({
                "members": context.evidence.members,
                "text": _corpus_text(context.evidence.root),
                "history": context.history,
            })
            prompt = context.candidate_dir / "systemprompt.md"
            prompt.write_text(prompt.read_text() + f"IMPROVEMENT {context.iteration}\n")
            return {"trace": {"turns": 1}, "prediction": "general validation"}

        results[mode] = run_benchmark_evolution(
            _config(
                tmp_path,
                run_id=f"ab-{mode}",
                seed=seed,
                rubric=rubric,
                mapping=mapping,
                mode=mode,
            ),
            optimize_tasks=optimize,
            held_out_tasks=held_out,
            benchmark_commit="0" * 40,
            evaluator=evaluator,
            proposer=proposer,
        )
        observations[mode] = seen

    normalized_calls = {
        mode: [(split, task_ids, markers) for split, _, task_ids, markers in evaluator.calls]
        for mode, evaluator in evaluators.items()
    }
    assert normalized_calls["control"] == normalized_calls["rich"]
    assert all(record.admitted for result in results.values() for record in result.records)
    control_state = json.loads((results["control"].run_dir / "resume.json").read_text())
    rich_state = json.loads((results["rich"].run_dir / "resume.json").read_text())
    assert (
        control_state["identity"]["admission_policy_digest"]
        == rich_state["identity"]["admission_policy_digest"]
    )
    assert not any(
        member.startswith("tasks/")
        for item in observations["control"]
        for member in item["members"]
    )
    assert "PUBLIC INSTRUCTION" not in observations["control"][0]["text"]
    assert "OPTIMIZE TRACE" not in observations["control"][0]["text"]
    assert "PUBLIC INSTRUCTION" in observations["rich"][0]["text"]
    assert "OPTIMIZE TRACE" in observations["rich"][0]["text"]
    assert all(
        "HELDOUT" not in item["text"] and "fx-secret-holdout" not in item["text"]
        for mode in observations.values()
        for item in mode
    )


def test_admission_failure_skips_candidate_scoring_and_enters_next_history(tmp_path):
    from qea.loop_benchmark import run_benchmark_evolution

    optimize, held_out = _tasks(tmp_path)
    rubric, mapping = _contracts(tmp_path, optimize)
    seed = _seed_worker(tmp_path)
    evaluator = RecordingEvaluator()
    histories = []

    def proposer(context):
        histories.append(context.history)
        config = context.candidate_dir / "agent.yaml"
        config.write_text(
            config.read_text().replace("${env.LLM_MODEL}", "forbidden/model")
        )
        return {"prediction": "unsafe model change"}

    result = run_benchmark_evolution(
        _config(
            tmp_path,
            run_id="admission-rejection",
            seed=seed,
            rubric=rubric,
            mapping=mapping,
            mode="rich",
        ),
        optimize_tasks=optimize,
        held_out_tasks=held_out,
        benchmark_commit="0" * 40,
        evaluator=evaluator,
        proposer=proposer,
    )

    assert [call[0] for call in evaluator.calls].count("optimize") == 1
    assert [call[0] for call in evaluator.calls].count("held_out") == 2
    assert all(record.admitted is False for record in result.records)
    assert all("admission rejected" in record.reason for record in result.records)
    assert [len(history) for history in histories] == [0, 1, 2]
    assert histories[1][0]["admitted"] is False
    assert "protected field llm_config.model" in histories[1][0]["admission_failure"]


def test_resume_rejects_feedback_arm_identity_change(tmp_path):
    from qea.loop_benchmark import EvolutionConfigError, run_benchmark_evolution

    optimize, held_out = _tasks(tmp_path)
    rubric, mapping = _contracts(tmp_path, optimize)
    seed = _seed_worker(tmp_path)

    def proposer(context):
        prompt = context.candidate_dir / "systemprompt.md"
        prompt.write_text(prompt.read_text() + "IMPROVEMENT\n")
        return {}

    common = dict(
        optimize_tasks=optimize,
        held_out_tasks=held_out,
        benchmark_commit="0" * 40,
        evaluator=RecordingEvaluator(),
        proposer=proposer,
    )
    run_benchmark_evolution(
        _config(
            tmp_path,
            run_id="identity-lock",
            seed=seed,
            rubric=rubric,
            mapping=mapping,
            mode="control",
        ),
        **common,
    )

    with pytest.raises(EvolutionConfigError, match="immutable identity mismatch"):
        run_benchmark_evolution(
            _config(
                tmp_path,
                run_id="identity-lock",
                seed=seed,
                rubric=rubric,
                mapping=mapping,
                mode="rich",
            ),
            **common,
        )
