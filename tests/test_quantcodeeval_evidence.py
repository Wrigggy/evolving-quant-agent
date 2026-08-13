import json
from pathlib import Path

import pytest

from qea.quantcodeeval_evidence import (
    PropertyFamilyProgress,
    QuantAttemptEvidence,
    QuantCodeEvalEvidenceError,
    QuantEvidenceAttemptSource,
    build_quantcodeeval_evidence,
    load_answer_free_property_summary,
    strategy_ast_facts,
    trace_coarse_facts,
)


def _public_task(tmp_path: Path, task_id: str) -> Path:
    root = tmp_path / "public" / "tasks" / task_id
    data = root / "environment" / "data"
    data.mkdir(parents=True)
    (root / "instruction.md").write_text(
        "Implement the public strategy contract.\n"
        "Save a strategy module with the requested functions.\n",
        encoding="utf-8",
    )
    (data / "paper_text.md").write_text(
        f"# Public paper for {task_id}\n", encoding="utf-8"
    )
    return root


def _summary(path: Path, *, reward: float, a_passed: int, b_passed: int) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "benchmark": "quantcodeeval",
                "official_reward": reward,
                "property_families": {
                    "type_a": {
                        "total": 3,
                        "passed": a_passed,
                        "failed": 3 - a_passed,
                        "skipped": 0,
                        "errors": 0,
                    },
                    "type_b": {
                        "total": 2,
                        "passed": b_passed,
                        "failed": 2 - b_passed,
                        "skipped": 0,
                        "errors": 0,
                    },
                },
                "diagnostic_tags": [] if reward else ["properties_incomplete"],
            }
        ),
        encoding="utf-8",
    )
    return path


def _attempt_source(tmp_path: Path, task_id: str) -> QuantEvidenceAttemptSource:
    attempt = tmp_path / "attempts" / task_id
    attempt.mkdir(parents=True)
    summary = _summary(
        attempt / "answer-free-summary.json", reward=0.0, a_passed=1, b_passed=1
    )
    strategy = attempt / "strategy.py"
    strategy.write_text(
        "import pandas as pd\n\n"
        "TARGET_VOLATILITY = 5.34\n\n"
        "def build_strategy(data, *, window=20):\n"
        "    return data.tail(window)\n",
        encoding="utf-8",
    )
    trace = attempt / "worker-trace.jsonl"
    trace.write_text(
        json.dumps({"role": "assistant", "content": "private content canary"})
        + "\n"
        + json.dumps(
            {
                "role": "tool",
                "type": "tool_result",
                "content": json.dumps(
                    {"exit_code": 3, "duration_ms": 125, "stderr": "private"}
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    final = attempt / "worker-final.txt"
    final.write_text("another private content canary\n", encoding="utf-8")
    process = attempt / "process-summary.json"
    process.write_text(
        json.dumps(
            {
                "turns": 4,
                "tool_calls": 2,
                "tool_errors": 0,
                "ignored_internal_field": "not copied",
            }
        ),
        encoding="utf-8",
    )
    record = QuantAttemptEvidence(
        task_id=task_id,
        evaluation_id="eval-h0",
        attempt_id=f"attempt-{task_id}",
        checkpoint="seed-optimize",
        worker_digest="1" * 64,
        official_reward=0.0,
        type_a=PropertyFamilyProgress(3, 1, 2, 0, 0),
        type_b=PropertyFamilyProgress(2, 1, 1, 0, 0),
        diagnostic_tags=("properties_incomplete",),
    )
    return QuantEvidenceAttemptSource(
        record=record,
        answer_free_summary_path=summary,
        strategy_path=strategy,
        trace_path=trace,
        final_text_path=final,
        process_summary_path=process,
    )


def _all_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def test_closed_property_summary_and_coarse_facts_do_not_return_content(tmp_path):
    source = _attempt_source(tmp_path, "T16")

    reward, type_a, type_b, tags = load_answer_free_property_summary(
        source.answer_free_summary_path
    )
    ast_facts = strategy_ast_facts(source.strategy_path)
    trace_facts = trace_coarse_facts(source.trace_path)

    assert reward == 0.0
    assert type_a == PropertyFamilyProgress(3, 1, 2, 0, 0)
    assert type_b == PropertyFamilyProgress(2, 1, 1, 0, 0)
    assert tags == ("properties_incomplete",)
    assert ast_facts["import_roots"] == ["pandas"]
    assert ast_facts["top_level_symbols"][0]["name"] == "build_strategy"
    assert ast_facts["module_numeric_constants"] == [
        {"name": "TARGET_VOLATILITY", "value": 5.34}
    ]
    assert trace_facts["event_count"] == 2
    assert trace_facts["tool_event_count"] == 1
    assert trace_facts["tool_error_count"] == 1
    assert trace_facts["longest_consecutive_tool_errors"] == 1
    assert trace_facts["tool_duration_ms_total"] == 125
    assert trace_facts["tool_exit_codes"] == {"3": 1}
    assert trace_facts["runtime_timeline"] == [
        {"event": 1, "role": "assistant"},
        {
            "duration_ms": 125,
            "event": 2,
            "role": "tool",
            "tool_status": "error",
        },
    ]
    assert "private content canary" not in json.dumps(trace_facts)
    assert "private" not in json.dumps(trace_facts)


def test_build_evidence_contains_only_aggregate_ast_and_trace_facts(tmp_path):
    roots = {
        task_id: _public_task(tmp_path, task_id) for task_id in ("T16", "T24")
    }
    sources = tuple(_attempt_source(tmp_path, task_id) for task_id in roots)

    record = build_quantcodeeval_evidence(
        destination=tmp_path / "evidence",
        public_task_roots=roots,
        attempts=sources,
        current_evaluation_id="eval-h0",
        history=({"iteration": 1, "decision": "ABSTAIN"},),
    )

    text = _all_text(record.root)
    assert len(record.sha256) == 64
    assert record.members == tuple(sorted(record.members))
    assert "property_id" not in text
    assert '"verdict"' not in text
    assert "private content canary" not in text
    assert "another private content canary" not in text
    assert "ignored_internal_field" not in text
    assert (
        record.root
        / "tasks/T16/evaluations/eval-h0/strategy_ast_facts.json"
    ).is_file()
    assert (
        record.root / "tasks/T24/evaluations/eval-h0/trace_facts.json"
    ).is_file()
    assert not any(path.name == "strategy.py" for path in record.root.rglob("*"))
    assert not any(path.name == "ctrf.json" for path in record.root.rglob("*"))


def test_property_summary_rejects_oracle_fields_fail_closed(tmp_path):
    path = _summary(tmp_path / "summary.json", reward=0.0, a_passed=1, b_passed=1)
    payload = json.loads(path.read_text())
    payload["property_id"] = "A1"
    path.write_text(json.dumps(payload))

    with pytest.raises(QuantCodeEvalEvidenceError, match="prohibited oracle field"):
        load_answer_free_property_summary(path)


def test_evidence_rejects_checker_or_ctrf_source_paths(tmp_path):
    path = tmp_path / "checkers" / "ctrf.json"
    path.parent.mkdir()
    path.write_text("{}")

    with pytest.raises(QuantCodeEvalEvidenceError, match="prohibited oracle path"):
        load_answer_free_property_summary(path)


def test_current_evaluation_requires_both_fixed_tasks(tmp_path):
    roots = {
        task_id: _public_task(tmp_path, task_id) for task_id in ("T16", "T24")
    }

    with pytest.raises(QuantCodeEvalEvidenceError, match="complete fixed task panel"):
        build_quantcodeeval_evidence(
            destination=tmp_path / "evidence",
            public_task_roots=roots,
            attempts=(_attempt_source(tmp_path, "T16"),),
            current_evaluation_id="eval-h0",
        )
