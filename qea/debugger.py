"""B-pile debugger: rubric verdicts + an answer-free critic -> a component-level
root cause, behind an information firewall. Ground truth (rubric text, gold) is
visible HERE; only a sanitized, component-level payload reaches the proposer."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

# B-pile root-cause vocabulary + its slot affinity (guides, does not force).
B_TAG_SLOT = {
    "MissingDomainKnowledge": "memory",
    "WrongStructure": "prompt",
    "FormatGap": "skill",
    "OccupationMismatch": "router",
    "CalcError": "tool",
}


def process_note(trace: dict) -> str:
    """Turn a worker trace summary into an ANSWER-FREE process observation. The
    trace carries only counts (files/turns/tool_calls/tool_errors/secs), never any
    task answer, so it is inherently firewall-safe — this function only formats it."""
    if not trace:
        return "no trace captured"
    files = int(trace.get("files", 0) or 0)
    turns = int(trace.get("turns", 0) or 0)
    errs = int(trace.get("tool_errors", 0) or 0)
    parts = []
    if files == 0:
        parts.append(f"produced no deliverable file after {turns} turn(s)")
    else:
        parts.append(f"produced {files} file(s) in {turns} turn(s)")
    if errs:
        parts.append(f"{errs} tool error(s)")
    return "; ".join(parts)


@dataclass
class SanitizedDiagnosis:
    root_cause_tag: str
    deficiency_category: str
    suggested_target_slot: str
    predicted_fix_task_ids: list = field(default_factory=list)
    overview: str = ""
    # OPEN-ENDED diagnosis (the real Agent Debugger's `ask` mode, not the retired fixed
    # 5-tag classifier): a free-form ROOT CAUSE + a GENERAL MECHANISM = one harness change
    # (a prompt rule, a TOOL to wire in/add, a binding, or middleware). mechanism_kind is
    # an OPEN hint (prompt|tool|binding|middleware|other), not a closed vocabulary. Both are
    # answer-free (the AHE "NOT task-specific knowledge" instruction IS the firewall).
    root_cause: str = ""
    general_mechanism: str = ""
    mechanism_kind: str = ""

    def proposer_payload(self) -> dict:
        """The ONLY thing the proposer sees. Contains no rubric answers / gold."""
        return {
            "root_cause_tag": self.root_cause_tag,
            "deficiency_category": self.deficiency_category,
            "suggested_target_slot": self.suggested_target_slot,
            "predicted_fix_task_ids": list(self.predicted_fix_task_ids),
            "overview": self.overview,
            "root_cause": self.root_cause,
            "general_mechanism": self.general_mechanism,
            "mechanism_kind": self.mechanism_kind,
            "_b_pile": True,
        }


class Critic:
    """Sees the deliverable + which criteria failed (+ gold as reference) and emits
    an ANSWER-FREE deficiency note: what capability/structure is missing, never the
    answer value. This is the inner wall of the firewall."""
    def __init__(self, llm) -> None:
        self.llm = llm

    def note(self, task, deliverable: str, failed_criteria: list[str]) -> str:
        prompt = (
            "You are reviewing why a finance deliverable fell short. You may see the "
            "rubric and a reference answer, but your note MUST describe only the "
            "MISSING CAPABILITY OR STRUCTURE (e.g. 'omits the required sensitivity "
            "analysis'). NEVER state any specific answer value, number, or verbatim "
            "rubric text. One sentence.\n\n"
            f"TASK:\n{task.prompt}\n\n"
            f"FAILED CRITERIA (count={len(failed_criteria)}):\n"
            + "\n".join(f"- {c}" for c in failed_criteria) +
            f"\n\nDELIVERABLE:\n{deliverable}\n\nANSWER-FREE DEFICIENCY NOTE:"
        )
        return self.llm.complete(prompt, role="judge").strip()


def _failed_criteria_texts(task, verdicts: dict) -> list[str]:
    items = getattr(task, "rubric_items", None) or []
    out = []
    for i, c in enumerate(items):
        if verdicts and verdicts.get(str(i + 1)) is False:
            out.append(c["criterion"])
    return out


def diagnose_b_pile(eval_summary, tasks, *, llm, mode: str = "hybrid", traces: dict | None = None) -> SanitizedDiagnosis:
    # COST: one Critic judge-call per FAILING B task + one classify call, per
    # iteration (up to ~n+1 judge calls when most tasks fail). Keep in mind on
    # large task sets / long runs. The worker trace (process side) is folded in
    # answer-free via process_note().
    by_id = {t.task_id: t for t in tasks}
    critic = Critic(llm)
    notes, failing_ids, occ_counts = [], [], {}
    for tid, r in eval_summary.results.items():
        if r.pile != "B" or r.oos_pass:
            continue
        task = by_id.get(tid)
        if task is None:
            continue
        failed = _failed_criteria_texts(task, r.criterion_verdicts or {})
        try:
            note = critic.note(task, eval_summary.deliverables.get(tid, ""), failed)
        except Exception:  # noqa: BLE001 - a critic outage must not kill the run (mirror evaluate())
            note = f"deliverable left {len(failed)} rubric criterion(s) unmet (critic unavailable)"
        if traces and tid in traces:
            note = f"{note} [process: {process_note(traces[tid])}]"
        notes.append(note)
        failing_ids.append(tid)
        occ_counts[r.subtype] = occ_counts.get(r.subtype, 0) + 1

    if not notes:
        return SanitizedDiagnosis("None", "no dominant deficiency", "", [], "No failing B tasks.")

    # OPEN-ENDED cross-task root-cause analysis, faithful to the real Agent Debugger's
    # `ask` mode (agentic_harness_engineering): ask for a free-form ROOT CAUSE + a
    # GENERAL MECHANISM = ONE harness change (prompt rule / TOOL / binding / middleware),
    # NOT a pick from a closed vocabulary. The "NOT task-specific" instruction is the
    # firewall (iron-law-2) — it forbids leaking any answer/number. The retired fixed
    # 5-tag classifier (B_TAG_SLOT) had no "missing tool/capability" category, so it
    # mislabeled tool gaps and steered edits toward prompt; this does not.
    ask = (
        "You are doing cross-task root-cause analysis of an agent worker's failures, to "
        "propose ONE harness change. Below are answer-free deficiency notes + process "
        "observations for the failing tasks.\n\n"
        "Rules: describe only the MISSING CAPABILITY / STRUCTURE / MECHANISM — NEVER a "
        "task-specific answer, number, or domain fact (that is a hard firewall).\n\n"
        "Produce JSON with:\n"
        '- "root_cause": the fundamental reason these tasks fail (one sentence).\n'
        '- "general_mechanism": ONE harness change that would prevent this failure CLASS '
        "generally — a prompt rule, a TOOL to wire in or add, a tool binding, or middleware. "
        "If the worker loops without reaching a data source / gives up without an answer, "
        "consider whether it is MISSING A TOOL/CAPABILITY that should be wired in (look for "
        "an unbound implementation) or added.\n"
        '- "kind": one of prompt | tool | binding | middleware | other.\n\n'
        'Return JSON {"root_cause": "...", "general_mechanism": "...", "kind": "..."}.\n\nNOTES:\n'
        + "\n".join(f"- {n}" for n in notes)
    )
    try:
        obj = _parse_first_json(llm.complete(ask, role="evolve_agent")) or {}
    except Exception:  # noqa: BLE001 - debugger outage -> minimal diagnosis, don't crash
        obj = {}
    root_cause = str(obj.get("root_cause", "") or "").strip()
    mechanism = str(obj.get("general_mechanism", "") or "").strip()
    kind = str(obj.get("kind", "") or "other").strip().lower()
    return SanitizedDiagnosis(
        root_cause_tag=kind or "other",  # kept for logging/back-compat (now the open kind)
        deficiency_category=f"{len(notes)} failing task(s) across {len(occ_counts)} occupation(s)",
        suggested_target_slot=kind,
        predicted_fix_task_ids=failing_ids,
        overview=(root_cause or f"dominant B-pile deficiency over {len(failing_ids)} failing task(s)."),
        root_cause=root_cause,
        general_mechanism=mechanism,
        mechanism_kind=kind,
    )


def _parse_first_json(txt: str):
    dec = json.JSONDecoder()
    i = txt.find("{")
    while i >= 0:
        try:
            obj, _ = dec.raw_decode(txt[i:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        i = txt.find("{", i + 1)
    return None
