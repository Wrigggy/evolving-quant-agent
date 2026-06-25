"""Deliverable-format gate: a worker scores 0 unless it produced a file whose
extension matches the task's REQUIRED format (= the GDPval gold deliverable
extension, `task.deliverable_exts`). Tasks whose gold deliverable is text
(`deliverable_exts == []`) require no file and always pass.

The CONTENT rubric % is kept separately (logged for the firewalled debugger's
diagnosis) — the gate only decides the canonical score, so 'content good but wrong
container' is distinguishable from 'content bad'.
"""
from __future__ import annotations

from pathlib import Path


def format_ok(task, produced_files) -> bool:
    """True if no specific format is required (text-gold) OR the worker produced at
    least one file whose extension matches a required extension."""
    req = {e.lower() for e in (getattr(task, "deliverable_exts", None) or [])}
    if not req:
        return True
    produced = {Path(p).suffix.lower() for p in (produced_files or [])}
    return bool(produced & req)


def apply_gate(content_score: float, task, produced_files) -> tuple[float, bool]:
    """Return (gated_score, format_ok). gated_score == content_score when the format
    is satisfied, else 0.0."""
    ok = format_ok(task, produced_files)
    return (content_score if ok else 0.0), ok
