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
    # A missing file is only a deficiency when a file was REQUIRED (format_ok is False).
    # On a TEXT-answer benchmark (e.g. FAB) files==0 is NORMAL — flagging it as "no
    # deliverable" mis-steers the diagnosis toward a write tool instead of the real gap.
    file_required_but_missing = files == 0 and not trace.get("format_ok", True)
    parts = [f"ran {turns} turn(s)"]
    if file_required_but_missing:
        parts.append("produced no deliverable file (one was required)")
    elif files:
        parts.append(f"produced {files} file(s)")
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
    """Sees the deliverable + which criteria failed (+ gold as reference) and emits a
    PRECISE root-cause note (AHE-style, no answer firewall): it MAY compare the produced
    value to the expected one to name the TRUE cause — e.g. distinguish 'computed the
    wrong figure' from 'read a truncated/wrong source and approximated' from 'omitted the
    section entirely'. The anti-cheat guard is at the EDIT stage (LeakageGuard blocks
    pasting answer material into worker files), not here — starving the diagnosis of the
    values destroyed exactly the signal that tells compute-gap from retrieval-gap."""
    def __init__(self, llm) -> None:
        self.llm = llm

    def note(self, task, deliverable: str, failed_criteria: list[str]) -> str:
        prompt = (
            "You are diagnosing WHY a finance deliverable fell short — find the TRUE root "
            "cause, like a debugger cross-referencing expected vs produced. You have the "
            "rubric/reference answer; USE it: compare what the worker produced to what was "
            "expected and infer the mechanism. Distinguish, when relevant: a COMPUTE gap "
            "(math/derivation wrong), a RETRIEVAL gap (produced a value CLOSE-but-wrong or "
            "generic, i.e. it never read the actual source/filing and approximated), a "
            "FORMAT gap (right content, wrong structure), or an OMISSION (section missing "
            "entirely). Name the mechanism in ONE sentence; you may cite the values as "
            "evidence. (Do NOT prescribe hard-coding the answer — that is caught at edit "
            "time; your job is to identify the capability gap.)\n\n"
            f"TASK:\n{task.prompt}\n\n"
            f"FAILED CRITERIA (count={len(failed_criteria)}):\n"
            + "\n".join(f"- {c}" for c in failed_criteria) +
            f"\n\nDELIVERABLE:\n{deliverable}\n\nROOT-CAUSE NOTE:"
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
    # Collect the failing B tasks first, then generate critic notes CONCURRENTLY. The
    # notes are independent per task; done sequentially this is ~n judge calls in series,
    # which dominates the loop when the judge endpoint is slow (observed ~40s/call). A
    # thread pool cuts diagnose wall-time ~n-fold without changing the notes or scoring.
    failing = []  # (tid, r, task, failed_criteria)
    for tid, r in eval_summary.results.items():
        if r.pile != "B" or r.oos_pass:
            continue
        task = by_id.get(tid)
        if task is None:
            continue
        failing.append((tid, r, task, _failed_criteria_texts(task, r.criterion_verdicts or {})))

    def _note(item):
        tid, _r, task, failed = item
        try:
            note = critic.note(task, eval_summary.deliverables.get(tid, ""), failed)
        except Exception:  # noqa: BLE001 - a critic outage must not kill the run (mirror evaluate())
            note = f"deliverable left {len(failed)} rubric criterion(s) unmet (critic unavailable)"
        if traces and tid in traces:
            note = f"{note} [process: {process_note(traces[tid])}]"
        return note

    if len(failing) > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(8, len(failing))) as pool:
            note_list = list(pool.map(_note, failing))  # map preserves order
    else:
        note_list = [_note(x) for x in failing]

    notes = note_list
    failing_ids = [tid for tid, *_ in failing]
    occ_counts = {}
    for tid, r, _task, _failed in failing:
        occ_counts[r.subtype] = occ_counts.get(r.subtype, 0) + 1

    if not notes:
        return SanitizedDiagnosis("None", "no dominant deficiency", "", [], "No failing B tasks.")

    # OPEN-ENDED cross-task root-cause analysis, faithful to the real Agent Debugger's
    # `ask` mode (agentic_harness_engineering). NO answer firewall: the notes above may
    # cite expected-vs-produced values, and the debugger reasons from them to find the TRUE
    # cause (a value that is close-but-wrong is a RETRIEVAL tell, not a compute one — the
    # old firewall abstracted that away and mis-steered edits to a calculator for iters).
    # The anti-cheat guard is at edit time (LeakageGuard), not here. It surfaces ALL
    # distinct capability gaps (not one dominant), since the evolve agent is now allowed to
    # ship several fixes per iteration.
    ask = (
        "You are doing cross-task root-cause analysis of an agent worker's failures, to "
        "propose the harness change(s) that would fix them. Below are root-cause notes "
        "(which may cite expected-vs-produced values) + process observations.\n\n"
        "Reason from the EVIDENCE to the TRUE cause. Watch the tells: a value that is "
        "close-but-wrong or generic => the worker never reached the real SOURCE (retrieval/"
        "deep-read gap), NOT a computation gap; math that is derived wrong => a compute gap; "
        "right content in the wrong shape => a format gap; a whole section absent => an "
        "omission/planning gap. If the worker loops without reaching a data source or gives "
        "up, check for a MISSING TOOL/CAPABILITY that should be wired in — look for an "
        "unbound implementation under tools/ that the agent.yaml no longer binds.\n\n"
        "Do NOT prescribe hard-coding any task answer (that is caught at edit time); "
        "prescribe GENERAL capability fixes.\n\n"
        "Produce JSON:\n"
        '- "root_cause": the single most important reason these tasks fail (one sentence, '
        "may cite values as evidence).\n"
        '- "general_mechanism": the harness change(s) that would prevent this failure class '
        "generally — a prompt rule, a TOOL to wire in / add, a tool binding, or middleware. "
        "If there are SEVERAL distinct gaps, list them all (the evolve agent can fix several "
        "in one pass), most impactful first.\n"
        '- "kind": the primary one of prompt | tool | binding | middleware | other.\n\n'
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
