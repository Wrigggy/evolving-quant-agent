"""Run the file-editing NexAU evolve agent inside an E2B cloud VM (full offload, like
worker_e2b). Motivation: keep the LOCAL orchestrator near-empty for GDPval, where the
local footprint (evolve-agent LLM context + LibreOffice render + multimodal judge) is
heavier than FAB. With this, BOTH sibling agents — worker and evolve — run in cloud VMs.

Bonus: the evolve agent's run_code self-test now runs in the SAME template the worker
runs in, so "does my synthesized tool import + run" is checked against the worker's real
environment (not the local venv).

`run_evolve_agent_e2b` mirrors evolve_runtime.run_evolve_agent's signature/return so the
loop swaps backends transparently. It uploads the evolve_agent dir + the worker snapshot +
the evidence corpus + the prompt, runs the full edit loop in the VM, DOWNLOADS THE EDITED
snapshot back (the whole dir, since the agent may add/delete files), and returns the
prediction + answer-free trace.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .evolve_runtime import EVOLVE_DIR, _build_evolve_message
from .worker_e2b import _sandbox_timeout, _template, _upload_dir

_ENTRY = Path(__file__).parent / "evolve_e2b_entry.py"
_REMOTE_WORK = "/home/user/work"


def run_evolve_agent_e2b(snapshot_dir_path, sanitized_diagnosis: dict, run_dir,
                         *, edit_history: str = "", evidence_dir=None) -> dict:
    from e2b import Sandbox
    from .worker_runtime import ensure_nexau_llm_env
    ensure_nexau_llm_env()
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY", "")
    snap = Path(snapshot_dir_path).resolve()
    run_dir = Path(run_dir)

    # Build the prompt LOCALLY (reads the local evidence corpus), but point the shell
    # drill-down path at the VM location where we upload the evidence.
    msg = _build_evolve_message(sanitized_diagnosis, edit_history=edit_history,
                                evidence_dir=evidence_dir,
                                evidence_ref="/home/user/evidence/traces")

    sbx = Sandbox.create(template=_template(), timeout=_sandbox_timeout())
    try:
        _upload_dir(sbx, EVOLVE_DIR, "/home/user/evolve_agent")
        _upload_dir(sbx, snap, _REMOTE_WORK)
        if evidence_dir is not None and Path(evidence_dir).exists():
            _upload_dir(sbx, Path(evidence_dir), "/home/user/evidence")
        sbx.files.write("/home/user/message.txt", msg.encode())
        sbx.files.write("/home/user/entry.py", _ENTRY.read_bytes())

        run = sbx.commands.run(
            "cd /home/user && python3 entry.py",
            envs={"OPENROUTER_API_KEY": key,
                  "LLM_MODEL": os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-pro"),
                  "QEA_EVOLVE_AGENT_MODEL": os.environ.get("QEA_EVOLVE_AGENT_MODEL", ""),
                  "QEA_PROVIDER_MAP": os.environ.get("QEA_PROVIDER_MAP", "")},
            timeout=_sandbox_timeout(),
        )

        final = ""
        try:
            final = sbx.files.read("/home/user/output/final.txt")
        except Exception:  # noqa: BLE001
            pass
        try:
            prediction = json.loads(sbx.files.read("/home/user/output/prediction.json"))
        except Exception:  # noqa: BLE001
            prediction = {"predicted_fixes": [], "risk_tasks": []}
        try:
            trace = json.loads(sbx.files.read("/home/user/output/trace.json"))
        except Exception:  # noqa: BLE001
            trace = {"turns": 0, "tool_calls": 0, "tool_errors": 1}
        trace.setdefault("backend", "e2b_full")

        # Download the EDITED snapshot back. The agent may add/delete files, so clear the
        # local snapshot and repopulate from the VM manifest (exact edited state).
        try:
            manifest = json.loads(sbx.files.read("/home/user/output/work_manifest.json"))
        except Exception:  # noqa: BLE001
            manifest = []
        if manifest:
            for child in snap.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink()
            for rel in manifest:
                data = sbx.files.read(f"{_REMOTE_WORK}/{rel}", format="bytes")
                dst = snap / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
        else:
            trace["error"] = f"evolve entry produced no manifest (exit={run.exit_code}): {(run.stderr or '')[:200]}"

        # Persist the trajectory dump next to the local run (parity with the local path).
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "evolve_trace.txt").write_text(sbx.files.read("/home/user/output/trajectory.txt"))
        except Exception:  # noqa: BLE001
            pass
        return {"final_text": final or "", "trace": trace, "prediction": prediction}
    finally:
        try:
            sbx.kill()
        except Exception:  # noqa: BLE001
            pass
