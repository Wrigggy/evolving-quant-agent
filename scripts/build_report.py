"""Build a per-task report for the Stirrup-on-E2B base-harness run.

For each GDPval finance task: prompt, reference INPUT files, the produced
deliverable file paths (so you can open them), the score, and the FULL
per-criterion rubric pass/fail. Re-grades each saved deliverable once (k=1) to
capture criterion-level verdicts -- this single-pass score may differ slightly
from the k=2 median in docs/RESULTS_base_stirrup_e2b.md (judge nondeterminism).

    .venv312/bin/python scripts/build_report.py
"""
from __future__ import annotations

import os
import pathlib

from qea.tasks import load_gdpval_finance
from qea.grading.render import render
from qea.verifier import build_rubric_prompt, score_rubric, _truthy
from qea.llm import make_llm

ROOT = pathlib.Path(__file__).resolve().parent.parent
STIRRUP_OUT = ROOT / "output" / "stirrup"
OUT = ROOT / "docs" / "REPORT_base_stirrup_e2b.md"


def _load_env():
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    _load_env()
    llm = make_llm(mock=False)
    tasks = sorted(load_gdpval_finance(broad=True, allow_download=True), key=lambda t: t.subtype)

    out = ["# Per-task report — vanilla Stirrup-on-E2B base harness (GDPval finance)",
           "",
           "Single-pass (k=1) re-grade for criterion-level transparency. Official k=2-median",
           "aggregate: `docs/RESULTS_base_stirrup_e2b.md`. Open deliverables with e.g. "
           "`open output/stirrup/<task_id>/<file>`.",
           ""]
    summary = ["## Summary", "",
               "| task | occupation | status | score | #deliv | #ref |",
               "|------|-----------|--------|-------|--------|------|"]
    details = ["", "## Per-task detail", ""]

    for t in tasks:
        tid = t.task_id
        d = STIRRUP_OUT / tid
        ref_names = {pathlib.Path(p).name for p in (t.reference_files or [])}
        files = [p for p in d.rglob("*") if p.is_file()] if d.exists() else []
        # produced deliverables = files that are NOT just the uploaded reference inputs
        produced = [p for p in files if p.name not in ref_names]

        if not files:
            status, score = "NO DELIVERABLE", None
        else:
            rendered = render("", files, ROOT / "output" / "render" / tid)
            items = t.rubric_items
            prompt = build_rubric_prompt(t, rendered.extracted_text or "", items,
                                         has_images=bool(rendered.images))
            txt = llm.complete(prompt, role="judge", images=rendered.images or None)
            score, verdicts = score_rubric(txt, items)
            status = "graded"

        summary.append(f"| {tid[:8]} | {t.subtype[:34]} | {status} | "
                       f"{'%.3f'%score if score is not None else '—'} | "
                       f"{len(produced)} | {len(t.reference_files or [])} |")

        details.append(f"### {tid}  —  {t.subtype}")
        details.append("")
        details.append(f"**Prompt:** {t.prompt.strip()[:600].replace(chr(10),' ')}"
                       + ("…" if len(t.prompt) > 600 else ""))
        details.append("")
        if t.reference_files:
            details.append("**Reference INPUT files (uploaded to sandbox):**")
            for p in t.reference_files:
                details.append(f"- `{os.path.relpath(p, ROOT)}`")
            details.append("")
        if produced:
            details.append("**Produced deliverable (open these):**")
            for p in produced:
                details.append(f"- `{os.path.relpath(p, ROOT)}`")
            details.append("")
        if score is None:
            details.append("_No deliverable produced (agent did not finish / failed). "
                           "See RESULTS doc for the failure reason._")
            details.append("")
            continue

        pos_total = sum(c["points"] for c in items if c["points"] > 0)
        earned = sum(c["points"] for i, c in enumerate(items) if _truthy(verdicts.get(str(i + 1))))
        details.append(f"**Score:** {score:.3f}  (earned {earned:g} / positive-total {pos_total:g}; "
                       f"imgs graded: {len(rendered.images)})")
        details.append("")
        details.append("**Per-criterion (✓ satisfied / · not):**")
        details.append("")
        for i, c in enumerate(items):
            ok = "✓" if _truthy(verdicts.get(str(i + 1))) else "·"
            crit = c["criterion"].strip().replace("\n", " ")[:110]
            details.append(f"- {ok} ({c['points']:+g}) {crit}")
        details.append("")

    OUT.write_text("\n".join(out + summary + details) + "\n")
    print(f"wrote {OUT}  ({len(tasks)} tasks)")


if __name__ == "__main__":
    main()
