"""Run the ENTIRE NexAU worker agent inside an E2B cloud VM (Harbor-style full offload).

Why: the local orchestrator was memory-bound — every worker run holds a large LLM
context in the local process, so N-way concurrency batch-killed background jobs under
macOS memory pressure. Moving the whole agent into a per-task cloud VM keeps the local
process near-empty (it only ships inputs + reads outputs); the LLM context, control
loop, and shell tools all live in the VM. LLM calls go DIRECT from the US-hosted VM to
OpenRouter (verified: no local SOCKS proxy needed), which the local machine cannot do.

`run_worker_e2b` mirrors `worker_runtime.run_worker`'s signature and return type
(WorkerRun) so `evaluate_dir` swaps backends transparently. It relies on a prebuilt E2B
template (default `qea-nexau-worker`: Python 3.12 + NexAU@v0.3.9 + ddgs baked in) so a
sandbox starts in ~1-2s with no per-sandbox pip install — required for 20-way concurrency.
Build/refresh the template with scripts/build_e2b_template.py.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .worker_runtime import WorkerRun, ensure_nexau_llm_env

SUPPORTED = {".xlsx", ".pptx", ".docx", ".pdf"}
_ENTRY = Path(__file__).parent / "e2b_entry.py"


def _template() -> str:
    return os.environ.get("QEA_E2B_TEMPLATE", "qea-nexau-worker")


def _sandbox_timeout() -> int:
    # Sandbox lifetime ceiling. A weak worker can flail to max_iterations (~15-20 min);
    # give generous headroom. Overridable for cheap tiers.
    return int(os.environ.get("QEA_E2B_SANDBOX_TIMEOUT", "1800"))


def _upload_dir(sbx, local_root: Path, remote_root: str) -> int:
    n = 0
    for f in local_root.rglob("*"):
        if f.is_file() and "__pycache__" not in str(f) and f.suffix != ".pyc":
            rel = f.relative_to(local_root)
            sbx.files.write(f"{remote_root}/{rel}", f.read_bytes())
            n += 1
    return n


def run_worker_e2b(task, worker_dir, run_dir) -> WorkerRun:
    """Run the worker agent at `worker_dir` on one task inside a fresh E2B VM. Uploads
    the agent dir + reference files + entry script, runs the full agent loop in the VM,
    downloads the deliverable + produced files + answer-free trace, and kills the VM.
    Signature/return match worker_runtime.run_worker for drop-in use by evaluate_dir."""
    from e2b import Sandbox

    ensure_nexau_llm_env()  # ensures OPENROUTER_API_KEY -> LLM_* mapping is consistent
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY", "")
    worker_dir, run_dir = Path(worker_dir), Path(run_dir)

    # Local mirror of the per-task workdir (so the evaluator reads produced files locally,
    # exactly as with the local backend). MUST be absolute — matches run_worker.
    workdir = (run_dir / str(task.task_id) / "work").resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    ref_files = [Path(rf) for rf in (getattr(task, "reference_files", None) or []) if Path(rf).exists()]
    ref_names = sorted(rf.name for rf in ref_files)
    is_file_task = bool(ref_names) or bool(getattr(task, "deliverable_exts", None))

    sbx = Sandbox.create(template=_template(), timeout=_sandbox_timeout())
    try:
        # Upload agent dir, entry script, reference inputs, task spec.
        _upload_dir(sbx, worker_dir, "/home/user/agent")
        sbx.files.write("/home/user/entry.py", _ENTRY.read_bytes())
        for rf in ref_files:
            sbx.files.write(f"/home/user/work/{rf.name}", rf.read_bytes())
        sbx.files.write("/home/user/task.json", json.dumps({
            "task_id": str(task.task_id), "prompt": task.prompt,
            "is_file_task": is_file_task, "ref_names": ref_names,
        }))

        run = sbx.commands.run(
            "cd /home/user && python3 entry.py",
            envs={"OPENROUTER_API_KEY": key,
                  "LLM_MODEL": os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-pro"),
                  # capability gate for gap experiments (see e2b_entry): block in-VM pip
                  "QEA_E2B_BLOCK_PIP": os.environ.get("QEA_E2B_BLOCK_PIP", "")},
            timeout=_sandbox_timeout(),
        )

        deliverable = sbx.files.read("/home/user/output/deliverable.txt")
        trace = json.loads(sbx.files.read("/home/user/output/trace.json"))
        try:
            produced_rel = json.loads(sbx.files.read("/home/user/output/files.json"))
        except Exception:  # noqa: BLE001
            produced_rel = []

        # Download produced deliverable files into the LOCAL workdir so the evaluator's
        # format gate + multimodal render (which read local files) work unchanged.
        produced = []
        for rel in produced_rel:
            data = sbx.files.read(f"/home/user/work/{rel}", format="bytes")
            dst = workdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            produced.append(dst)

        # Full trajectory for the AHE-corpus evidence path (parity with run_worker).
        trace_path = workdir.parent / "trace.txt"
        try:
            traj = sbx.files.read("/home/user/output/trajectory.txt")
            trace_path.write_text(traj)
            trace["trace_path"] = str(trace_path)
        except Exception:  # noqa: BLE001
            trace["trace_path"] = ""
        trace.setdefault("backend", "e2b_full")
        if run.exit_code != 0 and not deliverable:
            trace["error"] = f"entry exit={run.exit_code}: {(run.stderr or '')[:200]}"
        return WorkerRun(deliverable or "", produced, trace)
    finally:
        try:
            sbx.kill()
        except Exception:  # noqa: BLE001
            pass
