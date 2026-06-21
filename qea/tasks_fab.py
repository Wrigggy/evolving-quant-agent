"""FAB v2 (Finance Agent Benchmark v2) loader — public split.

Parses data/fab/public.csv (Question | Question Type | Expert time | Rubric) into
BTask objects. Each rubric criterion = 1 point, so the existing per-rubric scorer
(qea.verifier.score_rubric) yields the FAB "generous" fraction, and frac == 1.0 is
the FAB "strict" (all-pass). Answers are TEXT (no file deliverable / no render).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .tasks import BTask

_FAB_CSV = Path(__file__).resolve().parent.parent / "data" / "fab" / "public.csv"


def load_fab_v2(path: Path | None = None) -> list[BTask]:
    csv_path = path or _FAB_CSV
    out: list[BTask] = []
    with open(csv_path, newline="") as f:
        for i, row in enumerate(csv.DictReader(f)):
            try:
                rubric = json.loads(row["Rubric"]) if row.get("Rubric", "").strip() else []
            except json.JSONDecodeError:
                rubric = []
            items = [{"points": 1, "criterion": c.get("criteria", "").strip()}
                     for c in rubric if c.get("criteria", "").strip()]
            out.append(BTask(
                task_id=f"fab_{i:02d}",
                subtype=row.get("Question Type", "").strip(),
                prompt=row["Question"].strip(),
                rubric="",
                rubric_items=items,
                gdpval_lineage=f"fab_v2_public (expert ~{row.get('Expert time (mins)','?')}min)",
            ))
    print(f"[fab] loaded {len(out)} FAB v2 public tasks "
          f"({sum(len(t.rubric_items) for t in out)} rubric criteria)")
    return out
