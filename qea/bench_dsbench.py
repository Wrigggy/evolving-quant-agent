"""DSBench (ICLR 2025) data-analysis split integration: loader + low-noise evaluator.

466 ModelOff-sourced financial-analysis questions across 38 competitions; each
competition shares an introduction + (usually) one Excel workbook, each question
is one loop task with a short gold answer (427 strings — mostly a single
multiple-choice letter, 24 ints, 15 dicts).

Grading: a DETERMINISTIC matcher first (single-letter golds and numeric golds
compare exactly against the worker's `Final answer:` line), falling back to the
OFFICIAL binary LLM judge prompt (compute_answer.py, verbatim incl. its "Flase"
typo) only when the cheap match is inconclusive. This keeps judge noise near
zero on the ~90% of questions with letter/numeric golds.

Anti-leak: gold lives only on the task object for the evaluator; workbooks whose
filename contains "answer" are never uploaded. Split evolution pools by WHOLE
competitions — questions inside one share intro/workbook.
License: data research-only/non-commercial (see data/dsbench/DATA_NOTES.md).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "data" / "dsbench"
_DATA = _ROOT / "raw" / "data"
_META = _ROOT / "repo" / "data_analysis" / "data.json"

_REF_EXTS = {".xlsx", ".xlsb", ".xlsm", ".jpg", ".png"}


@dataclass
class DSTask:
    """Duck-typed task for the Level-B loop (text answer; format gate is a no-op)."""
    task_id: str
    subtype: str                  # competition id (per-competition deltas / splits)
    prompt: str
    reference_files: list
    deliverable_exts: list        # [] -> text gold, format_ok always True
    gold: str                     # verbatim gold; evaluator-only, never in the sandbox
    question_text: str
    rubric_items: list = field(default_factory=list)
    rubric: str = ""
    pile: str = "B"


def _prompt(intro: str, question: str, ref_names: list) -> str:
    files = ("Input files in your working directory: " + ", ".join(ref_names) + ".\n"
             if ref_names else "All data needed is in the case description below.\n")
    return (
        "You are a data analyst solving a financial-modeling exam question.\n\n"
        f"CASE BACKGROUND:\n{intro}\n\nQUESTION:\n{question}\n\n"
        + files +
        "Work the numbers precisely (use Python for any computation; never estimate). "
        "End your reply with a line of the form `Final answer: <answer>` — for a "
        "multiple-choice question output ONLY the option letter; for a numeric entry "
        "follow the rounding/format the question specifies. If unsure on multiple "
        "choice, you must still pick one option."
    )


def load_dsbench(limit: int = 0) -> list:
    rows = [json.loads(l) for l in _META.read_text().splitlines() if l.strip()]
    out = []
    for row in rows:
        comp = str(row["id"])
        cdir = _DATA / comp
        if not cdir.exists():
            continue
        intro = (cdir / "introduction.txt").read_text(errors="replace")
        refs = sorted(str(p) for p in cdir.iterdir()
                      if p.suffix.lower() in _REF_EXTS and "answer" not in p.name.lower())
        ref_names = [Path(r).name for r in refs]
        for qname, gold in zip(row["questions"], row["answers"]):
            qfile = cdir / f"{qname}.txt"
            if not qfile.exists():
                continue
            qtext = qfile.read_text(errors="replace")
            out.append(DSTask(
                task_id=f"{comp}_{qname}",
                subtype=comp,
                prompt=_prompt(intro, qtext, ref_names),
                reference_files=refs,
                deliverable_exts=[],
                gold=str(gold),
                question_text=qtext,
            ))
        if limit and len(out) >= limit:
            break
    print(f"[tasks] loaded {len(out)} DSBench data-analysis questions "
          f"({len({t.subtype for t in out})} competitions)", flush=True)
    return out


_FINAL_RE = re.compile(r"final answer\s*[:\-]\s*(.+)", re.IGNORECASE)
_NUM_RE = re.compile(r"-?[\d,]+(?:\.\d+)?")


def _final_line(prediction: str) -> str:
    """The text after the LAST 'Final answer:' marker (or the last non-empty line)."""
    hits = _FINAL_RE.findall(prediction or "")
    if hits:
        return hits[-1].strip()
    lines = [l.strip() for l in (prediction or "").splitlines() if l.strip()]
    return lines[-1] if lines else ""


def deterministic_match(gold: str, prediction: str):
    """True/False when the gold is cheap to check exactly; None = inconclusive
    (hand off to the LLM judge). Letter golds: the final line must contain exactly
    one A-I token and it must equal gold. Numeric golds: the final line's last
    number must equal gold exactly (the question fixes the rounding)."""
    gold = (gold or "").strip()
    line = _final_line(prediction)
    if not line:
        return False
    if re.fullmatch(r"[A-Ia-i]", gold):
        letters = re.findall(r"\b([A-Ia-i])\b", line)
        if len(set(l.upper() for l in letters)) == 1:
            return letters[0].upper() == gold.upper()
        return None
    if re.fullmatch(r"-?\d+(?:\.\d+)?", gold.replace(",", "")):
        nums = _NUM_RE.findall(line)
        if not nums:
            return False
        try:
            return abs(float(nums[-1].replace(",", "")) - float(gold.replace(",", ""))) < 1e-6
        except ValueError:
            return None
    return None


# Official judge prompt from repo/data_analysis/compute_answer.py — kept verbatim
# (including the "Flase" typo) for comparability with the paper's protocol.
_JUDGE_PROMPT = (
    "Please judge whether the generated answer is right or wrong. We require "
    "that the correct answer to the prediction gives a clear answer, not just "
    "a calculation process or a disassembly of ideas. The question is {question}. "
    "The true answer is \n {gold} \n The predicted answer is \n {prediction}\n "
    "If the predicted answer is right, please output True. Otherwise output "
    "Flase. Don't output any other text content. You only can output True or False."
)


class DSBenchEvaluator:
    """Binary per question: deterministic matcher first, official LLM judge as
    fallback for free-form/dict golds."""

    def __init__(self, llm) -> None:
        self.llm = llm

    def evaluate(self, task, worker_run, out_dir=None):
        from .evaluator import TaskEval
        pred = worker_run.deliverable_text or ""
        ok = deterministic_match(task.gold, pred)
        if ok is None:
            raw = self.llm.complete(_JUDGE_PROMPT.format(
                question=task.question_text[:6000], gold=task.gold,
                prediction=pred[-4000:]), role="judge")
            ok = "true" in (raw or "").lower()
        s = 1.0 if ok else 0.0
        return TaskEval(s, s, True, pred, {"1": bool(ok)}, 0.0)
