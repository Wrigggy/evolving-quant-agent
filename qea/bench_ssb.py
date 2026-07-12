"""SpreadsheetBench (NeurIPS 2024) integration: loader + deterministic evaluator.

Task mapping: one loop task per (instruction, test case) — the official protocol
runs the SAME instruction once per test-case input (differing data defeats
hard-coding), so each case is an independent binary-scored task and the pool
mean carries the official "soft restriction" gradient. The grader is the
official checker (`repo/evaluation/evaluation.py::compare_workbooks`, cell
VALUES over `answer_position`) — deterministic, zero judge noise: on this
benchmark the only eval noise left is worker stochasticity (use n_samples).

Splits (see data/spreadsheetbench/DATA_NOTES.md):
- ssb_912:      all_data_912_v0.1 (905x3 + 4x2 + 3x1 cases) — evolution pool
- ssb_verified: spreadsheetbench_verified_400 (1 case/task, refined prompts) —
                held-out / reporting

Answer files NEVER enter the task (not referenced in prompt/reference_files);
the evaluator resolves them from the on-disk layout at grade time.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "data" / "spreadsheetbench"
_EVAL_DIR = _ROOT / "repo" / "evaluation"
_SOFFICE = "/Applications/LibreOffice.app/Contents/MacOS/soffice"


@dataclass
class SSBTask:
    """Duck-typed task for the Level-B loop (same attrs evaluate_dir/worker use)."""
    task_id: str
    subtype: str                  # instruction_type (Cell-/Sheet-Level Manipulation)
    prompt: str
    reference_files: list         # [input xlsx] — the answer file is NEVER here
    deliverable_exts: list        # [".xlsx"]
    answer_xlsx: str              # resolved by the loader, consumed ONLY by the evaluator
    instruction_type: str
    answer_position: str
    expected_output: str          # required output filename
    rubric_items: list = field(default_factory=list)  # none — deterministic grading
    rubric: str = ""
    gold: str = ""                # no text gold; leakage corpus stays empty
    pile: str = "B"


def _prompt(instruction: str, input_name: str, output_name: str,
            instruction_type: str, answer_position: str) -> str:
    return (
        "You are solving a real-world spreadsheet manipulation task.\n\n"
        f"INSTRUCTION:\n{instruction}\n\n"
        f"The input spreadsheet `{input_name}` is in your working directory. "
        f"Manipulation type: {instruction_type}. The answer must appear at "
        f"`{answer_position}` (modify only what the instruction requires).\n\n"
        f"Save the completed spreadsheet as `{output_name}` in the working directory, "
        "keeping the sheet names of the input. IMPORTANT: the grader reads cached cell "
        "VALUES only — write computed values (e.g. via openpyxl after computing in "
        "Python); a formula string without a cached value grades as empty."
    )


def _case_files(folder: Path, tid: str, k: int):
    """(input, answer) paths for test case k, tolerating the verified split's
    _init/_initial/_golden naming."""
    pairs = [(f"{k}_{tid}_input.xlsx", f"{k}_{tid}_answer.xlsx"),
             (f"{k}_{tid}_init.xlsx", f"{k}_{tid}_golden.xlsx"),
             (f"{k}_{tid}_initial.xlsx", f"{k}_{tid}_golden.xlsx")]
    for inp, ans in pairs:
        if (folder / inp).exists() and (folder / ans).exists():
            return folder / inp, folder / ans
    return None, None


def load_ssb(split: str = "912", limit: int = 0) -> list:
    """Load SpreadsheetBench as per-test-case tasks. split: '912' | 'verified' | 'sample'."""
    base = {"912": _ROOT / "raw" / "all_data_912_v0.1",
            "verified": _ROOT / "raw" / "spreadsheetbench_verified_400",
            "sample": _ROOT / "raw" / "sample_data_200"}[split]
    rows = json.loads((base / "dataset.json").read_text())
    out = []
    for row in rows:
        tid = str(row["id"])
        folder = base / "spreadsheet" / tid
        for k in (1, 2, 3):
            inp, ans = _case_files(folder, tid, k)
            if inp is None:
                continue
            out_name = f"{k}_{tid}_output.xlsx"
            out.append(SSBTask(
                task_id=f"{tid}_tc{k}",
                subtype=str(row.get("instruction_type", "")),
                prompt=_prompt(str(row["instruction"]), inp.name, out_name,
                               str(row.get("instruction_type", "")),
                               str(row.get("answer_position", ""))),
                reference_files=[str(inp)],
                deliverable_exts=[".xlsx"],
                answer_xlsx=str(ans),
                instruction_type=str(row.get("instruction_type", "")),
                answer_position=str(row.get("answer_position", "")),
                expected_output=out_name,
            ))
        if limit and len(out) >= limit:
            break
    print(f"[tasks] loaded {len(out)} SpreadsheetBench case-tasks (split={split})", flush=True)
    return out


def _recalc(path: Path) -> None:
    """LibreOffice headless round-trip to cache formula values (official
    open_spreadsheet.py step). Best-effort: skipped when soffice is missing."""
    if not Path(_SOFFICE).exists():
        return
    try:
        tmp = path.parent / "_recalc"
        tmp.mkdir(exist_ok=True)
        subprocess.run([_SOFFICE, "--headless", "--convert-to", "xlsx", "--outdir",
                        str(tmp), str(path)], capture_output=True, timeout=60)
        conv = tmp / path.name
        if conv.exists():
            shutil.move(str(conv), str(path))
    except Exception:  # noqa: BLE001 - recalc is an enhancement, never a failure source
        pass


class SSBEvaluator:
    """Deterministic evaluator: official compare_workbooks on the produced file.
    Binary per case-task; TaskEval.gated_score in {0.0, 1.0}."""

    def __init__(self, recalc: bool = True) -> None:
        self.recalc = recalc
        if str(_EVAL_DIR) not in sys.path:
            sys.path.insert(0, str(_EVAL_DIR))

    def evaluate(self, task, worker_run, out_dir=None):
        from .evaluator import TaskEval
        from evaluation import compare_workbooks  # official checker (repo/evaluation)
        produced = None
        for p in worker_run.produced_files or []:
            if Path(p).name == task.expected_output:
                produced = Path(p)
                break
        if produced is None:  # fall back to any produced xlsx (wrong name loses nothing else)
            xl = [p for p in (worker_run.produced_files or []) if str(p).endswith(".xlsx")]
            produced = Path(xl[0]) if xl else None
        ok = False
        if produced is not None and produced.exists():
            if self.recalc:
                _recalc(produced)
            try:
                ok, _ = compare_workbooks(task.answer_xlsx, str(produced),
                                          task.instruction_type, task.answer_position)
            except Exception:  # noqa: BLE001 - unreadable workbook = fail, not crash
                ok = False
        s = 1.0 if ok else 0.0
        return TaskEval(s, s, produced is not None, worker_run.deliverable_text or "",
                        {"1": bool(ok)}, 0.0)
