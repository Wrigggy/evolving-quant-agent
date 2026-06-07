"""Change manifest — the falsifiable record of one harness edit.

Reuses the AHE HARNESS.md v1.0 change-manifest schema verbatim in spirit
(failure_evidence -> root_cause -> targeted_fix -> predicted_impact ->
verification verdict). The ``component`` enum here uses the QEA quant slot names
(tool/middleware/skill/prompt/validator/memory/router) instead of AHE's
coding-harness slots; everything else is the same shape, so the audit trail and
the falsify step are identical.
"""

from __future__ import annotations

import json
from datetime import datetime

MANIFEST_VERSION = "1.0"
HARNESS_SPEC_VERSION = "1.0-qea"


def build_manifest(iteration: int, author: str, edit, arm: str) -> dict:
    return {
        "manifest_version": MANIFEST_VERSION,
        "harness_spec_version": HARNESS_SPEC_VERSION,
        "iteration": iteration,
        "arm": arm,
        "timestamp": datetime.now().isoformat(),
        "author": author,
        "changes": [
            {
                "change_id": f"ch_{iteration:03d}",
                "component": edit.slot,        # quant slot name
                "subtype": edit.op,            # add | update | delete
                "file_path": f"{edit.slot}/{edit.component_name}",
                "summary": edit.summary,
                "failure_evidence": edit.failure_evidence,
                "root_cause": edit.root_cause,
                "targeted_fix": edit.targeted_fix,
                "predicted_impact": {
                    "expected_fixes": list(edit.predicted_fixes),
                    "at_risk_regressions": list(edit.risk_tasks),
                    "rationale": edit.rationale,
                },
            }
        ],
        "verification": {"status": "pending"},
    }


def attach_verdict(manifest: dict, evaluation: dict, kept: bool) -> dict:
    manifest = dict(manifest)
    manifest["verification"] = {
        "status": "verified" if kept else "reverted",
        "completed_at": datetime.now().isoformat(),
        "result": evaluation,
        "verdict": "keep" if kept else "revert",
    }
    return manifest


def dumps(manifest: dict) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2)
