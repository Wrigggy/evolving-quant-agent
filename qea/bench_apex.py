"""APEX-Agents Investment Banking subset (Mercor, arXiv 2601.14242): loader +
rubric evaluator.

160 IB tasks across 10 "worlds" (data rooms of ~100-140 files); 133 answer-type
(message_in_console) + 27 file-deliverable (sheets/decks). Rubrics are unweighted
binary criteria (mean ~2.9/task) judged per-criterion by an LLM — the same shape
as our GDPval rubric judge, which we reuse (per-criterion true/false JSON) instead
of archipelago's Docker stack.

World staging: the data room is 100-330MB per world — far too heavy to push
through the local uplink per sandbox, so tasks carry a `vm_setup_cmd` that makes
the E2B VM download + extract its world zip directly from HF (fast CDN; the
gated-dataset token is forwarded as HF_TOKEN by worker_e2b). Small per-task input
overlays upload normally as reference files.

LICENSE (dataset card): CC-BY 4.0 but "intended exclusively for model evaluation;
any use for training, fine-tuning, or parameter fitting is forbidden". We evolve
agent scaffolds, never model weights; still — do not put APEX content in any
weight-training corpus, and check with apex@mercor.com before publishing results
selected on it (see data/apex_agents/DATA_NOTES.md).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "data" / "apex_agents"
_RAW = _ROOT / "raw"
_HF_REPO = "mercor/apex-agents"

_FILE_TASK_EXTS = {"make_new_sheet": [".xlsx"], "edit_existing_sheet": [".xlsx"],
                   "make_new_slide_deck": [".pptx"]}


@dataclass
class APEXTask:
    """Duck-typed task for the Level-B loop."""
    task_id: str
    subtype: str                  # world_id (per-world deltas / competition-style splits)
    prompt: str
    reference_files: list         # small per-task input overlays only
    deliverable_exts: list        # [] for answer tasks; [".xlsx"/".pptx"] for file tasks
    rubric_items: list            # {points: 1, criterion} (unweighted binary)
    vm_setup_cmd: str             # world download+extract, run in the VM before the agent
    output_type: str
    rubric: str = ""
    gold: str = ""
    pile: str = "B"


def _setup_cmd(world_id: str) -> str:
    """Download the world zip from HF inside the VM and extract its data room to
    ./data_room. stdlib-only (urllib + zipfile) so it runs on any template."""
    url = f"https://huggingface.co/datasets/{_HF_REPO}/resolve/main/world_files_zipped/{world_id}.zip"
    py = (
        "import os,urllib.request,zipfile;"
        f"req=urllib.request.Request({url!r});"
        "tok=os.environ.get('HF_TOKEN','');"
        "tok and req.add_header('Authorization','Bearer '+tok);"
        "open('/tmp/world.zip','wb').write(urllib.request.urlopen(req,timeout=540).read());"
        "zf=zipfile.ZipFile('/tmp/world.zip');"
        "[zf.extract(m,'data_room') for m in zf.namelist() if m.startswith('filesystem/')];"
        "os.remove('/tmp/world.zip');print('world ready:',sum(1 for _ in __import__('pathlib').Path('data_room').rglob('*')))"
    )
    return f'python3 -c "{py}"'


def _prompt(task: dict) -> str:
    out_note = {
        "message_in_console": "Give your final answer as text at the end of your reply.",
        "make_new_sheet": "Save the required spreadsheet as a NEW .xlsx file in your working directory.",
        "edit_existing_sheet": "Save the edited spreadsheet as an .xlsx file in your working directory (do not overwrite data_room sources).",
        "make_new_slide_deck": "Save the deck as a .pptx file in your working directory.",
    }.get(str(task.get("expected_output", "")), "")
    return (
        f"{task['prompt']}\n\n"
        "The deal data room is under `data_room/filesystem/` in your working "
        "directory — inspect it with the shell (PDFs, spreadsheets, documents). "
        + out_note
    )


def load_apex_ib(limit: int = 0) -> list:
    rows = json.loads((_RAW / "tasks_and_rubrics.json").read_text())
    out = []
    for t in rows:
        if t.get("domain") != "Investment Banking":
            continue
        tid = str(t["task_id"])
        overlay = _RAW / "task_files" / tid / "filesystem"
        refs = sorted(str(p) for p in overlay.rglob("*") if p.is_file()) if overlay.is_dir() else []
        otype = str(t.get("expected_output", ""))
        out.append(APEXTask(
            task_id=tid,
            subtype=str(t["world_id"]),
            prompt=_prompt(t),
            reference_files=refs,
            deliverable_exts=_FILE_TASK_EXTS.get(otype, []),
            rubric_items=[{"points": 1, "criterion": item["criteria"]}
                          for item in (t.get("rubric") or [])],
            vm_setup_cmd=_setup_cmd(str(t["world_id"])),
            output_type=otype,
        ))
        if limit and len(out) >= limit:
            break
    print(f"[tasks] loaded {len(out)} APEX-Agents IB tasks "
          f"({len({t.subtype for t in out})} worlds)", flush=True)
    return out


def _xlsx_dump(path: Path, cap: int = 20000) -> str:
    """Plain-text dump of a produced workbook so the text rubric judge can check
    factual criteria ('States 2029E Net Income is 1,772 million')."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), data_only=True)
        parts = []
        for ws in wb.worksheets:
            parts.append(f"## sheet: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                if any(v is not None for v in row):
                    parts.append(" | ".join("" if v is None else str(v) for v in row))
        return "\n".join(parts)[:cap]
    except Exception as exc:  # noqa: BLE001
        return f"(unreadable workbook: {exc})"


class APEXEvaluator:
    """Per-criterion rubric judge (our shared scorer) over the final answer plus a
    text dump of any produced spreadsheet, with the standard format gate."""

    def __init__(self, llm, k: int = 2) -> None:
        from .evaluator import RubricTextEvaluator
        self.inner = RubricTextEvaluator(llm, k=k)

    def evaluate(self, task, worker_run, out_dir=None):
        text = worker_run.deliverable_text or ""
        for p in worker_run.produced_files or []:
            if str(p).endswith((".xlsx", ".xlsm")):
                text += f"\n\n# produced file: {Path(p).name}\n" + _xlsx_dump(Path(p))
        run = type(worker_run)(text, worker_run.produced_files, worker_run.trace)
        return self.inner.evaluate(task, run, out_dir)
