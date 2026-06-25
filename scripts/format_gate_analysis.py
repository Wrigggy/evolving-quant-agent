"""Post-hoc deliverable-format gate analysis (no worker rerun, no re-grade).

For a completed run (its output/<label>/ work dirs + monitor.jsonl), compute per task:
  content_mm : the existing lenient rubric % (from monitor.jsonl)
  gated_mm   : content_mm if the worker produced a file whose extension matches the
               GDPVAL GOLD deliverable extension(s); else 0.0.
Tasks whose gold deliverable is text (no file) require no file -> always format_ok.

    .venv-nexau/bin/python scripts/format_gate_analysis.py <label> [<label2> ...]
e.g. ... nexau_gdpval weak_gdpval
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
OFFICE = {".xlsx", ".pptx", ".docx", ".pdf"}


def gold_and_refs():
    """task_id -> (gold_exts:set, ref_names:set) from the local GDPval parquet."""
    df = pd.read_parquet(REPO / "data" / "gdpval" / "gdpval_gold.parquet")
    out = {}
    for _, r in df.iterrows():
        dels = list(r["deliverable_files"]) if r["deliverable_files"] is not None else []
        gold = {os.path.splitext(str(d))[1].lower() for d in dels}
        gold = {e for e in gold if e}  # drop empties; empty set == text deliverable
        refs = list(r["reference_files"]) if r["reference_files"] is not None else []
        ref_names = {os.path.basename(str(x)) for x in refs}
        out[r["task_id"]] = (gold, ref_names)
    return out


def find_workdir(label: str, task_id: str) -> Path | None:
    """Handle both nestings: output/<label>/<tid>/work and .../<tid>/<tid>/work."""
    base = REPO / "output" / label
    for cand in (base / task_id / "work", base / task_id / task_id / "work"):
        if cand.is_dir():
            return cand
    hits = list(base.glob(f"{task_id}/**/work"))
    return hits[0] if hits else None


def produced_exts(workdir: Path, ref_names: set) -> set:
    if workdir is None:
        return set()
    return {p.suffix.lower() for p in workdir.iterdir()
            if p.is_file() and p.suffix.lower() in OFFICE and p.name not in ref_names}


def analyze(label: str, meta: dict):
    monf = REPO / "output" / label / "monitor.jsonl"
    if not monf.exists():
        print(f"[{label}] no monitor.jsonl yet — skip"); return None
    rows = [json.loads(l) for l in monf.read_text().splitlines() if l.strip()]
    content, gated, flips = [], [], []
    print(f"\n=== {label} ===")
    print(f"{'task':10}{'gold':14}{'produced':12}{'fmt':5}{'content':9}{'gated':8}")
    for r in rows:
        tid = r["id"]
        if r.get("mm") is None:
            continue
        gold, ref_names = meta.get(tid, (set(), set()))
        prod = produced_exts(find_workdir(label, tid), ref_names)
        fmt_ok = (not gold) or bool(prod & gold)
        cm = float(r["mm"])
        gm = cm if fmt_ok else 0.0
        content.append(cm); gated.append(gm)
        if not fmt_ok:
            flips.append((tid[:8], ",".join(sorted(gold)) or "text", ",".join(sorted(prod)) or "none", cm))
        print(f"{tid[:8]:10}{(','.join(sorted(gold)) or 'text'):14}"
              f"{(','.join(sorted(prod)) or 'none'):12}{('OK' if fmt_ok else 'MISS'):5}{cm:<9.3f}{gm:<8.3f}")
    n = len(content)
    cmean = sum(content) / n if n else 0.0
    gmean = sum(gated) / n if n else 0.0
    print(f"  n={n}  content_mm mean={cmean:.3f}  gated_mm mean={gmean:.3f}  "
          f"(format misses zeroed: {len(flips)})")
    for tid, g, p, cm in flips:
        print(f"    MISS {tid}: gold={g} produced={p} content={cm:.3f} -> gated=0.000")
    return {"label": label, "n": n, "content_mean": round(cmean, 3),
            "gated_mean": round(gmean, 3), "misses": len(flips)}


def main():
    labels = sys.argv[1:] or ["nexau_gdpval"]
    meta = gold_and_refs()
    summ = [analyze(l, meta) for l in labels]
    print("\n=== SUMMARY (content vs gold-format-gated) ===")
    for s in summ:
        if s:
            print(f"  {s['label']:16} n={s['n']:2}  content={s['content_mean']:.3f}  "
                  f"gated={s['gated_mean']:.3f}  misses={s['misses']}")


if __name__ == "__main__":
    main()
