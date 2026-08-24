import json
from pathlib import Path


def _write_trace(path: Path, assistant_lines: list[str]) -> None:
    records = [
        {"role": "user", "content": "[QSTATE S1 COMPLETE] do not parse user text"},
        *({"role": "assistant", "content": line} for line in assistant_lines),
    ]
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def test_parser_records_complete_six_stage_protocol_and_revisit(tmp_path):
    from qea.research_state_trace import parse_research_state_trace

    trace = tmp_path / "raw-trace.jsonl"
    _write_trace(
        trace,
        [
            "[QSTATE S1 ENTER]\n[QSTATE S1 COMPLETE] deliverables=results.json",
            "[QSTATE S2 ENTER]\n[QSTATE S2 COMPLETE] files=quotes.csv",
            "[QSTATE S3 ENTER]\n[QSTATE S3 COMPLETE] units=USD",
            "[QSTATE S4 ENTER]\n[QSTATE S4 COMPLETE] draft=results.json",
            "[QSTATE S5 ENTER]\n[QSTATE S5 REVISIT S3] reason=unit check",
            "[QSTATE S3 ENTER]\n[QSTATE S3 COMPLETE] units=USD per share",
            "[QSTATE S5 COMPLETE] checks=parseability,units",
            "[QSTATE S6 ENTER]\n[QSTATE S6 COMPLETE] artifacts=results.json",
        ],
    )

    report = parse_research_state_trace(trace)

    assert report["coverage"] == {
        "accounted_stages": ["S1", "S2", "S3", "S4", "S5", "S6"],
        "missing_stages": [],
        "first_accounted_order": ["S1", "S2", "S3", "S4", "S5", "S6"],
        "marker_protocol_complete": True,
    }
    assert report["issues"] == []
    assert report["marker_presence_is_not_stage_correctness"] is True
    assert report["stages"]["S3"]["enter"] == 2
    revisit = next(event for event in report["events"] if event["action"] == "REVISIT")
    assert revisit["stage"] == "S5"
    assert revisit["target_stage"] == "S3"


def test_parser_reports_missing_and_malformed_markers_without_claiming_success(tmp_path):
    from qea.research_state_trace import parse_research_state_trace

    trace = tmp_path / "raw-trace.jsonl"
    _write_trace(
        trace,
        [
            "[QSTATE S1 COMPLETE] no enter",
            "[QSTATE S3 ENTER]",
            "[QSTATE S3 DONE] malformed",
            "[QSTATE S6 ENTER] too early",
        ],
    )

    report = parse_research_state_trace(trace)

    assert report["coverage"]["marker_protocol_complete"] is False
    assert set(report["coverage"]["missing_stages"]) == set(
        ["S1", "S2", "S3", "S4", "S5", "S6"]
    )
    assert "S1_complete_without_enter" in report["issues"]
    assert "malformed_qstate_marker" in report["issues"]
    assert "s6_entered_before_s5_terminal_marker" in report["issues"]


def test_materializer_is_enabled_only_by_registered_six_stage_skill(tmp_path):
    from qea.research_state_trace import materialize_research_state_trace

    trace = tmp_path / "raw-trace.jsonl"
    _write_trace(trace, ["[QSTATE S1 NOT_APPLICABLE] reason=public inspection only"])
    worker = tmp_path / "worker"
    destination = tmp_path / "research-state-trace.json"
    worker.mkdir()

    assert materialize_research_state_trace(
        trace_path=trace,
        worker_dir=worker,
        destination=destination,
    ) is False
    assert not destination.exists()

    skill = worker / "skills/quant-research-six-stage-workflow"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("registered\n", encoding="utf-8")

    assert materialize_research_state_trace(
        trace_path=trace,
        worker_dir=worker,
        destination=destination,
    ) is True
    assert json.loads(destination.read_text(encoding="utf-8"))["record_kind"] == (
        "research_state_marker_index"
    )
