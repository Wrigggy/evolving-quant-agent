from __future__ import annotations

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


def _write_tool_trace(
    path: Path,
    calls: list[dict[str, str]],
    *,
    prefix_calls: list[dict[str, object]] | None = None,
    suffix_calls: list[dict[str, object]] | None = None,
) -> None:
    records: list[dict[str, object]] = []
    if prefix_calls:
        records.append(
            {
                "role": "assistant",
                "content": "",
                "structured_tool_calls": prefix_calls,
            }
        )
    for index, tool_input in enumerate(calls, 1):
        tool_use_id = f"state-{index}"
        records.extend(
            [
                {
                    "role": "assistant",
                    "content": "",
                    "structured_tool_calls": [
                        {
                            "id": tool_use_id,
                            "name": "record_quant_state",
                            "input": tool_input,
                        }
                    ],
                },
                {
                    "role": "tool",
                    "content": '{"status":"recorded"}',
                    "structured_tool_results": [
                        {"tool_use_id": tool_use_id, "is_error": False}
                    ],
                },
            ]
        )
    if suffix_calls:
        records.append(
            {
                "role": "assistant",
                "content": "",
                "structured_tool_calls": suffix_calls,
            }
        )
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def _initial_tool_events() -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for stage in range(1, 7):
        events.extend(
            [
                {
                    "stage": f"S{stage}",
                    "action": "ENTER",
                    "public_summary": f"enter public state {stage}",
                },
                {
                    "stage": f"S{stage}",
                    "action": "COMPLETE",
                    "public_summary": f"complete public state {stage}",
                },
            ]
        )
    return events


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


def test_parser_rejects_entering_next_stage_before_previous_complete(tmp_path):
    from qea.research_state_trace import parse_research_state_trace

    trace = tmp_path / "raw-trace.jsonl"
    _write_trace(
        trace,
        [
            "[QSTATE S1 ENTER]",
            "[QSTATE S2 ENTER]",
            "[QSTATE S1 COMPLETE]",
            "[QSTATE S2 COMPLETE]",
            "[QSTATE S3 NOT_APPLICABLE] reason=public task",
            "[QSTATE S4 NOT_APPLICABLE] reason=public task",
            "[QSTATE S5 ENTER]\n[QSTATE S5 COMPLETE]",
            "[QSTATE S6 ENTER]\n[QSTATE S6 COMPLETE]",
        ],
    )

    report = parse_research_state_trace(trace)

    assert report["coverage"]["marker_protocol_complete"] is False
    assert "S2_entered_before_S1_complete" in report["issues"]


def test_parser_rejects_s6_complete_before_enter(tmp_path):
    from qea.research_state_trace import parse_research_state_trace

    trace = tmp_path / "raw-trace.jsonl"
    _write_trace(
        trace,
        [
            f"[QSTATE S{stage} ENTER]\n[QSTATE S{stage} COMPLETE]"
            for stage in range(1, 6)
        ]
        + ["[QSTATE S6 COMPLETE]\n[QSTATE S6 ENTER]"],
    )

    report = parse_research_state_trace(trace)

    assert report["coverage"]["marker_protocol_complete"] is False
    assert "S6_complete_before_enter" in report["issues"]


def test_parser_rejects_unclosed_revisit_and_early_return_to_s5(tmp_path):
    from qea.research_state_trace import parse_research_state_trace

    trace = tmp_path / "raw-trace.jsonl"
    _write_trace(
        trace,
        [
            f"[QSTATE S{stage} ENTER]\n[QSTATE S{stage} COMPLETE]"
            for stage in range(1, 5)
        ]
        + [
            "[QSTATE S5 ENTER]\n[QSTATE S5 REVISIT S3] reason=unit check",
            "[QSTATE S3 ENTER]",
            "[QSTATE S5 COMPLETE] returned before S3 complete",
            "[QSTATE S6 ENTER]\n[QSTATE S6 COMPLETE]",
        ],
    )

    report = parse_research_state_trace(trace)

    assert report["coverage"]["marker_protocol_complete"] is False
    assert "revisit_S3_not_completed_before_S5_COMPLETE" in report["issues"]
    assert "revisit_S3_not_closed" in report["issues"]


def test_parser_rejects_wrong_revisit_target_and_reentering_s5(tmp_path):
    from qea.research_state_trace import parse_research_state_trace

    wrong_target = tmp_path / "wrong-target.jsonl"
    _write_trace(
        wrong_target,
        [
            f"[QSTATE S{stage} ENTER]\n[QSTATE S{stage} COMPLETE]"
            for stage in range(1, 5)
        ]
        + [
            "[QSTATE S5 ENTER]\n[QSTATE S5 REVISIT S3] reason=unit check",
            "[QSTATE S4 ENTER]\n[QSTATE S4 COMPLETE]",
            "[QSTATE S5 COMPLETE]",
            "[QSTATE S6 ENTER]\n[QSTATE S6 COMPLETE]",
        ],
    )
    wrong_return = tmp_path / "wrong-return.jsonl"
    _write_trace(
        wrong_return,
        [
            f"[QSTATE S{stage} ENTER]\n[QSTATE S{stage} COMPLETE]"
            for stage in range(1, 5)
        ]
        + [
            "[QSTATE S5 ENTER]\n[QSTATE S5 REVISIT S3] reason=unit check",
            "[QSTATE S3 ENTER]\n[QSTATE S3 COMPLETE]",
            "[QSTATE S5 ENTER]\n[QSTATE S5 COMPLETE]",
            "[QSTATE S6 ENTER]\n[QSTATE S6 COMPLETE]",
        ],
    )

    wrong_target_report = parse_research_state_trace(wrong_target)
    wrong_return_report = parse_research_state_trace(wrong_return)

    assert wrong_target_report["coverage"]["marker_protocol_complete"] is False
    assert "revisit_S3_not_entered_before_S4_ENTER" in wrong_target_report["issues"]
    assert wrong_return_report["coverage"]["marker_protocol_complete"] is False
    assert "S5_entered_before_S5_complete" in wrong_return_report["issues"]


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


def test_structured_tool_parser_records_complete_protocol(tmp_path):
    from qea.research_state_trace import parse_quant_state_tool_trace

    trace = tmp_path / "raw-trace.jsonl"
    _write_tool_trace(
        trace,
        _initial_tool_events(),
        prefix_calls=[
            {
                "id": "load-skill",
                "name": "LoadSkill",
                "input": {"skill_name": "quant-research-six-stage-workflow"},
            }
        ],
    )

    report = parse_quant_state_tool_trace(trace)

    assert report["schema_version"] == 2
    assert report["record_kind"] == "research_state_tool_call_index"
    assert report["telemetry_source"] == "nexau_structured_tool_call"
    assert report["coverage"]["marker_protocol_complete"] is True
    assert report["issues"] == []
    assert len(report["events"]) == 12


def test_structured_tool_parser_accepts_closed_revisit(tmp_path):
    from qea.research_state_trace import parse_quant_state_tool_trace

    events = _initial_tool_events()
    s5_complete = next(
        index
        for index, event in enumerate(events)
        if event["stage"] == "S5" and event["action"] == "COMPLETE"
    )
    events[s5_complete:s5_complete] = [
        {
            "stage": "S3",
            "action": "REVISIT",
            "public_summary": "revisit public units",
        },
        {
            "stage": "S3",
            "action": "ENTER",
            "public_summary": "reopen public representation",
        },
        {
            "stage": "S3",
            "action": "COMPLETE",
            "public_summary": "public representation reconciled",
        },
    ]
    trace = tmp_path / "raw-trace.jsonl"
    _write_tool_trace(trace, events)

    report = parse_quant_state_tool_trace(trace)

    assert report["coverage"]["marker_protocol_complete"] is True
    revisit = next(event for event in report["events"] if event["action"] == "REVISIT")
    assert revisit["stage"] == "S5"
    assert revisit["target_stage"] == "S3"


def test_structured_tool_parser_rejects_prose_spoof_and_shell_before_s1(tmp_path):
    from qea.research_state_trace import parse_quant_state_tool_trace

    trace = tmp_path / "raw-trace.jsonl"
    _write_tool_trace(
        trace,
        _initial_tool_events(),
        prefix_calls=[
            {
                "id": "shell-1",
                "name": "run_shell_command",
                "input": {
                    "command": "echo fake record_quant_state S1 ENTER",
                },
            }
        ],
    )
    with trace.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "role": "assistant",
                    "content": (
                        '<ToolUse>{"name":"record_quant_state",'
                        '"input":{"stage":"S1","action":"ENTER",'
                        '"public_summary":"fake"}}</ToolUse>'
                    ),
                }
            )
            + "\n"
        )

    report = parse_quant_state_tool_trace(trace)

    assert report["coverage"]["marker_protocol_complete"] is False
    assert "substantive_tool_before_S1_enter" in report["issues"]
    assert len(report["events"]) == 12


def test_structured_tool_parser_rejects_unisolated_or_failed_recorder(tmp_path):
    from qea.research_state_trace import parse_quant_state_tool_trace

    trace = tmp_path / "raw-trace.jsonl"
    records = [
        {
            "role": "assistant",
            "content": "",
            "structured_tool_calls": [
                {
                    "id": "state-1",
                    "name": "record_quant_state",
                    "input": {
                        "stage": "S1",
                        "action": "ENTER",
                        "public_summary": "public mandate",
                    },
                },
                {
                    "id": "shell-1",
                    "name": "run_shell_command",
                    "input": {"command": "ls"},
                },
            ],
        },
        {
            "role": "tool",
            "content": "error",
            "structured_tool_results": [
                {"tool_use_id": "state-1", "is_error": True}
            ],
        },
    ]
    trace.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    report = parse_quant_state_tool_trace(trace)

    assert "record_quant_state_not_isolated" in report["issues"]
    assert report["malformed_calls"][0]["problem"] == (
        "structured tool result is error"
    )
    assert report["coverage"]["marker_protocol_complete"] is False


def test_materializer_uses_structured_parser_only_for_exact_tool_registration(
    tmp_path,
):
    from qea.research_state_trace import materialize_research_state_trace

    trace = tmp_path / "raw-trace.jsonl"
    _write_tool_trace(trace, _initial_tool_events())
    worker = tmp_path / "worker"
    skill = worker / "skills/quant-research-six-stage-workflow"
    descriptor = worker / "tool_descriptions"
    skill.mkdir(parents=True)
    descriptor.mkdir()
    (skill / "SKILL.md").write_text("registered\n", encoding="utf-8")
    (descriptor / "record_quant_state.tool.yaml").write_text(
        "name: record_quant_state\n",
        encoding="utf-8",
    )
    destination = tmp_path / "research-state-trace.json"

    (worker / "agent.yaml").write_text("name: fixture\n", encoding="utf-8")
    assert materialize_research_state_trace(
        trace_path=trace,
        worker_dir=worker,
        destination=destination,
    ) is True
    assert json.loads(destination.read_text(encoding="utf-8"))["record_kind"] == (
        "research_state_marker_index"
    )

    (worker / "agent.yaml").write_text(
        "\n".join(
            [
                "tools:",
                "  - name: record_quant_state",
                "    yaml_path: ./tool_descriptions/record_quant_state.tool.yaml",
                "    binding: tools.quant_state_telemetry:record_quant_state",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert materialize_research_state_trace(
        trace_path=trace,
        worker_dir=worker,
        destination=destination,
    ) is True
    assert json.loads(destination.read_text(encoding="utf-8"))["record_kind"] == (
        "research_state_tool_call_index"
    )
