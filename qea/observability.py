"""Three-layer observability: eval / decision(manifest) / workspace, persisted
per iteration so a human can audit Case-A-style (the same root cause traceable
across EVAL -> DIAGNOSE -> WORKSPACE -> VERDICT).

Layout (mirrors the AHE iteration_NNN layout, trimmed for v0):

    <results>/<run>/<arm>/iteration_NNN/
        eval.json             # EVAL layer: per-task results + per-subtype + totals
        diagnosis.json        # ADB-lite root cause
        change_manifest.json  # DECISION layer: edit + verdict (or "blocked")
        workspace.json        # WORKSPACE layer: incumbent harness after decision
    <results>/<run>/<arm>/scores.json   # per-iteration OOS trajectory + per-subtype
"""

from __future__ import annotations

import json
from pathlib import Path


class ExperimentDir:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _iter_dir(self, arm: str, iteration: int) -> Path:
        d = self.root / arm / f"iteration_{iteration:03d}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def persist_iteration(self, arm: str, rec: dict) -> None:
        d = self._iter_dir(arm, rec["iteration"])
        _write(d / "eval.json", rec.get("eval"))
        _write(d / "diagnosis.json", rec.get("diagnosis"))
        _write(d / "change_manifest.json", rec.get("manifest"))
        _write(d / "workspace.json", rec.get("workspace"))

    def persist_arm(self, arm: str, scores: dict) -> None:
        _write(self.root / arm / "scores.json", scores)


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def eval_to_dict(eval_summary) -> dict:
    return {
        "total_oos": eval_summary.total_oos(),
        "per_subtype": {k: list(v) for k, v in eval_summary.per_subtype().items()},
        "mean_variance": eval_summary.mean_variance(),
        "tasks": {
            tid: {
                "subtype": r.subtype, "pile": r.pile, "base_pass": r.base_pass,
                "probe_pass": r.probe_pass, "oos_pass": r.oos_pass,
                "score": r.score, "variance": r.variance, "error": r.error,
            }
            for tid, r in eval_summary.results.items()
        },
    }
