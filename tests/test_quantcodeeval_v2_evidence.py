import json
import shutil
from pathlib import Path

from qea.quantcodeeval_evidence import (
    PropertyFamilyProgress,
    QuantAttemptEvidence,
    QuantEvidenceAttemptSource,
)
from qea.quantcodeeval_history import append_quantcodeeval_history
from qea.quantcodeeval_v2_evidence import build_quantcodeeval_v2_evidence


AGENT = """\
type: agent
name: qce-v2-worker
max_context_tokens: 1000
system_prompt: ./systemprompt.md
system_prompt_type: jinja
tool_call_mode: openai
max_iterations: 2
llm_config:
  model: fixed
  base_url: fixed
  api_key: fixed
  max_tokens: 100
  temperature: 0
  stream: false
  api_type: openai_chat_completion
  timeout: 10
tools: []
tracers: []
"""


def _public_task(tmp_path: Path, task_id: str) -> Path:
    root = tmp_path / "public" / "tasks" / task_id
    data = root / "environment" / "data"
    data.mkdir(parents=True)
    (root / "instruction.md").write_text("Build strategy.py.\n", encoding="utf-8")
    (data / "paper_text.md").write_text(
        f"# Public paper {task_id}\n", encoding="utf-8"
    )
    return root


def _attempt(tmp_path: Path, task_id: str, reward: float):
    root = tmp_path / "attempts" / task_id
    root.mkdir(parents=True)
    summary = root / "answer-free-summary.json"
    passed = 1 if reward else 0
    summary.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "benchmark": "quantcodeeval",
                "official_reward": reward,
                "property_families": {
                    "type_a": {
                        "total": 1,
                        "passed": passed,
                        "failed": 1 - passed,
                        "skipped": 0,
                        "errors": 0,
                    },
                    "type_b": {
                        "total": 1,
                        "passed": passed,
                        "failed": 1 - passed,
                        "skipped": 0,
                        "errors": 0,
                    },
                },
                "diagnostic_tags": [] if reward else ["properties_incomplete"],
            }
        ),
        encoding="utf-8",
    )
    family = PropertyFamilyProgress(1, passed, 1 - passed, 0, 0)
    record = QuantAttemptEvidence(
        task_id=task_id,
        evaluation_id="eval-current",
        attempt_id=f"attempt-{task_id}",
        checkpoint="candidate",
        worker_digest="1" * 64,
        official_reward=reward,
        type_a=family,
        type_b=family,
        diagnostic_tags=() if reward else ("properties_incomplete",),
    )
    return QuantEvidenceAttemptSource(
        record=record,
        answer_free_summary_path=summary,
    )


def _history(tmp_path: Path) -> tuple[Path, str]:
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "agent.yaml").write_text(AGENT, encoding="utf-8")
    (parent / "systemprompt.md").write_text("Solve.\n", encoding="utf-8")
    candidate = tmp_path / "candidate"
    shutil.copytree(parent, candidate)
    (candidate / "systemprompt.md").write_text(
        "Solve and estimate carefully.\n", encoding="utf-8"
    )
    history = tmp_path / "history-store"
    result = append_quantcodeeval_history(
        history_root=history,
        run_id="qce-v2-evidence",
        iteration=1,
        parent_worker_dir=parent,
        candidate_worker_dir=candidate,
        decision={"decision": "ACT", "selected": "prompt hypothesis"},
        mechanism="add estimation guidance",
        primary_components=("systemprompt",),
        declared_roles=("systemprompt",),
        component_tests=({"kind": "prompt_lint", "status": "passed"},),
        activation={"status": "passed"},
        evaluation={"T16": {"reward": 1}, "T24": {"reward": 0}},
        selection="rejected",
        rollback_reason="no answer-free property-family gain",
    )
    return history, result.entry_id


def test_v2_evidence_exposes_exact_rejected_diff_and_candidate_source(tmp_path):
    roots = {
        task_id: _public_task(tmp_path, task_id) for task_id in ("T16", "T24")
    }
    attempts = (
        _attempt(tmp_path, "T16", 1.0),
        _attempt(tmp_path, "T24", 0.0),
    )
    history, entry_id = _history(tmp_path)

    record = build_quantcodeeval_v2_evidence(
        destination=tmp_path / "v2-evidence",
        public_task_roots=roots,
        attempts=attempts,
        current_evaluation_id="eval-current",
        history_root=history,
        iteration_summaries=({"iteration": 1, "selection": "rejected"},),
    )

    contract = json.loads((record.root / "contract.json").read_text())
    assert contract["decision_protocol"] == "quant_property_v2"
    assert contract["target_task_ids"] == ["T24"]
    assert contract["protection_task_ids"] == ["T16"]
    assert contract["history_required"] is True
    assert contract["history_entry_ids"] == [entry_id]
    entry = json.loads(
        (record.root / "history/archive/entries" / f"{entry_id}.json").read_text()
    )
    patch = record.root / "history/archive/diffs" / f"{entry['diff_sha256']}.patch"
    candidate_source = (
        record.root
        / "history/archive/objects"
        / entry["candidate_digest"]
        / "systemprompt.md"
    )
    assert "estimate carefully" in patch.read_text()
    assert candidate_source.read_text() == "Solve and estimate carefully.\n"
    assert patch.stat().st_mode & 0o222 == 0
    assert "property_id" not in "\n".join(
        path.read_text(encoding="utf-8")
        for path in record.root.rglob("*")
        if path.is_file()
    )


def test_first_v2_round_does_not_require_nonexistent_history(tmp_path):
    roots = {
        task_id: _public_task(tmp_path, task_id) for task_id in ("T16", "T24")
    }
    attempts = (
        _attempt(tmp_path, "T16", 1.0),
        _attempt(tmp_path, "T24", 0.0),
    )

    record = build_quantcodeeval_v2_evidence(
        destination=tmp_path / "first-evidence",
        public_task_roots=roots,
        attempts=attempts,
        current_evaluation_id="eval-current",
        history_root=None,
    )

    contract = json.loads((record.root / "contract.json").read_text())
    summary = json.loads((record.root / "history/SUMMARY.json").read_text())
    assert contract["history_required"] is False
    assert summary["entry_count"] == 0
    assert not (record.root / "history/archive").exists()
