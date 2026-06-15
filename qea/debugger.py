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


@dataclass
class SanitizedDiagnosis:
    root_cause_tag: str
    deficiency_category: str
    suggested_target_slot: str
    predicted_fix_task_ids: list = field(default_factory=list)
    overview: str = ""

    def proposer_payload(self) -> dict:
        """The ONLY thing the proposer sees. Contains no rubric answers / gold."""
        return {
            "root_cause_tag": self.root_cause_tag,
            "deficiency_category": self.deficiency_category,
            "suggested_target_slot": self.suggested_target_slot,
            "predicted_fix_task_ids": list(self.predicted_fix_task_ids),
            "overview": self.overview,
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


def diagnose_b_pile(eval_summary, tasks, *, llm, mode: str = "hybrid") -> SanitizedDiagnosis:
    # COST: one Critic judge-call per FAILING B task + one classify call, per
    # iteration (up to ~n+1 judge calls when most tasks fail). Keep in mind on
    # large task sets / long runs.
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
        notes.append(critic.note(task, eval_summary.deliverables.get(tid, ""), failed))
        failing_ids.append(tid)
        occ_counts[r.subtype] = occ_counts.get(r.subtype, 0) + 1

    if not notes:
        return SanitizedDiagnosis("None", "no dominant deficiency", "", [], "No failing B tasks.")

    tag_vocab = ", ".join(B_TAG_SLOT)
    classify = (
        "Classify the dominant deficiency across these answer-free notes into ONE tag "
        f"from {{{tag_vocab}}}"
        + (" and name the harness slot to target" if mode == "free" else "")
        + '. Return JSON {"root_cause_tag":..., "target_slot":...}.\n\nNOTES:\n'
        + "\n".join(f"- {n}" for n in notes)
    )
    obj = _parse_first_json(llm.complete(classify, role="evolve_agent")) or {}
    tag = obj.get("root_cause_tag", "WrongStructure")
    slot = obj.get("target_slot") if mode == "free" else B_TAG_SLOT.get(tag, "prompt")
    return SanitizedDiagnosis(
        root_cause_tag=tag,
        deficiency_category=f"{len(notes)} task(s) with {tag} across {len(occ_counts)} occupation(s)",
        suggested_target_slot=slot or B_TAG_SLOT.get(tag, "prompt"),
        predicted_fix_task_ids=failing_ids,
        overview=f"{tag}: dominant B-pile deficiency over {len(failing_ids)} failing task(s).",
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
