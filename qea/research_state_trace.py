"""Parse concise Quant-H0-S6 markers into a trusted attempt-side record."""

from __future__ import annotations

import json
import re
from pathlib import Path


STAGES = tuple(f"S{index}" for index in range(1, 7))
SIX_STAGE_SKILL = Path("skills/quant-research-six-stage-workflow/SKILL.md")
_MARKER = re.compile(
    r"^\[QSTATE (?P<stage>S[1-6]) "
    r"(?P<action>ENTER|COMPLETE|NOT_APPLICABLE|REVISIT S[2-4])\]"
    r"(?:\s*(?P<summary>.*))?$"
)


def _read_trace(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"trace line {line_number} is invalid JSON") from exc
        if not isinstance(record, dict):
            raise ValueError(f"trace line {line_number} is not an object")
        records.append(record)
    return records


def _marker_sequence_issues(events: list[dict[str, object]]) -> list[str]:
    """Validate the observable S1--S6 transition protocol."""

    issues: list[str] = []
    expected_index = 0
    active_stage: str | None = None
    revisit_target: str | None = None
    revisit_entered = False

    for event in events:
        stage = str(event["stage"])
        action = str(event["action"])

        if revisit_target is not None:
            if not revisit_entered:
                if stage == revisit_target and action == "ENTER":
                    revisit_entered = True
                    active_stage = revisit_target
                    continue
                issues.append(
                    f"revisit_{revisit_target}_not_entered_before_{stage}_{action}"
                )
                continue
            if stage == revisit_target and action == "COMPLETE":
                revisit_target = None
                revisit_entered = False
                active_stage = "S5"
                continue
            issues.append(
                f"revisit_{revisit_target}_not_completed_before_{stage}_{action}"
            )
            continue

        if action == "REVISIT":
            target_stage = str(event["target_stage"])
            if stage != "S5":
                issues.append("revisit_marker_not_emitted_from_s5")
            elif active_stage != "S5":
                issues.append("revisit_without_active_s5")
            else:
                revisit_target = target_stage
            continue

        expected_stage = (
            STAGES[expected_index] if expected_index < len(STAGES) else None
        )
        if action == "ENTER":
            if active_stage is not None:
                issues.append(f"{stage}_entered_before_{active_stage}_complete")
                continue
            if stage != expected_stage:
                issues.append(f"{stage}_entered_out_of_initial_order")
            active_stage = stage
            continue

        if action == "COMPLETE":
            if active_stage != stage:
                if stage == "S6":
                    issues.append("S6_complete_before_enter")
                else:
                    issues.append(f"{stage}_complete_without_active_enter")
                continue
            active_stage = None
            if stage == expected_stage:
                expected_index += 1
            continue

        if action == "NOT_APPLICABLE":
            if active_stage is not None:
                issues.append(
                    f"{stage}_not_applicable_before_{active_stage}_complete"
                )
                continue
            if stage == "S6":
                issues.append("S6_not_applicable_not_allowed")
            if stage != expected_stage:
                issues.append(f"{stage}_not_applicable_out_of_initial_order")
            else:
                expected_index += 1

    if revisit_target is not None:
        issues.append(f"revisit_{revisit_target}_not_closed")
    elif active_stage is not None:
        issues.append(f"{active_stage}_enter_without_complete")
    return list(dict.fromkeys(issues))


def parse_research_state_trace(path: str | Path) -> dict[str, object]:
    """Return marker coverage without treating marker presence as correctness."""

    events: list[dict[str, object]] = []
    malformed: list[dict[str, object]] = []
    counts = {
        stage: {"enter": 0, "complete": 0, "not_applicable": 0}
        for stage in STAGES
    }

    for trace_line, record in enumerate(_read_trace(Path(path)), 1):
        if str(record.get("role", "")) != "assistant":
            continue
        content = str(record.get("content", "") or "")
        for content_line, text in enumerate(content.splitlines(), 1):
            stripped = text.strip()
            if not stripped.startswith("[QSTATE"):
                continue
            match = _MARKER.fullmatch(stripped)
            if match is None:
                malformed.append(
                    {
                        "trace_line": trace_line,
                        "content_line": content_line,
                        "text": stripped,
                    }
                )
                continue
            stage = match.group("stage")
            raw_action = match.group("action")
            if raw_action.startswith("REVISIT "):
                action = "REVISIT"
                target_stage = raw_action.split()[1]
            else:
                action = raw_action
                target_stage = None
                counts[stage][raw_action.casefold()] += 1
            event: dict[str, object] = {
                "stage": stage,
                "action": action,
                "summary": match.group("summary") or "",
                "trace_line": trace_line,
                "content_line": content_line,
            }
            if target_stage is not None:
                event["target_stage"] = target_stage
            events.append(event)

    first_accounted: list[str] = []
    for event in events:
        if event["action"] not in {"ENTER", "NOT_APPLICABLE"}:
            continue
        stage = str(event["stage"])
        if stage not in first_accounted:
            first_accounted.append(stage)

    issues = _marker_sequence_issues(events)
    missing: list[str] = []
    for stage in STAGES:
        state = counts[stage]
        accounted = bool(
            state["not_applicable"]
            or (state["enter"] and state["complete"])
        )
        if not accounted:
            missing.append(stage)
        if state["complete"] and not state["enter"]:
            issues.append(f"{stage}_complete_without_enter")

    if first_accounted != list(STAGES):
        issues.append("first_stage_entries_out_of_order_or_missing")
    s5_terminal = next(
        (
            index
            for index, event in enumerate(events)
            if event["stage"] == "S5"
            and event["action"] in {"COMPLETE", "NOT_APPLICABLE"}
        ),
        None,
    )
    s6_enter = next(
        (
            index
            for index, event in enumerate(events)
            if event["stage"] == "S6"
            and event["action"] in {"ENTER", "NOT_APPLICABLE"}
        ),
        None,
    )
    if s6_enter is not None and (s5_terminal is None or s6_enter < s5_terminal):
        issues.append("s6_entered_before_s5_terminal_marker")
    if malformed:
        issues.append("malformed_qstate_marker")
    issues = list(dict.fromkeys(issues))

    return {
        "schema_version": 1,
        "record_kind": "research_state_marker_index",
        "marker_presence_is_not_stage_correctness": True,
        "events": events,
        "stages": counts,
        "coverage": {
            "accounted_stages": [stage for stage in STAGES if stage not in missing],
            "missing_stages": missing,
            "first_accounted_order": first_accounted,
            "marker_protocol_complete": not missing and not issues,
        },
        "malformed_markers": malformed,
        "issues": issues,
    }


def materialize_research_state_trace(
    *,
    trace_path: str | Path,
    worker_dir: str | Path,
    destination: str | Path,
) -> bool:
    """Write one attempt-side record when the Worker registers the S6 skill."""

    worker_root = Path(worker_dir)
    if not (worker_root / SIX_STAGE_SKILL).is_file():
        return False
    report = parse_research_state_trace(trace_path)
    Path(destination).write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return True
