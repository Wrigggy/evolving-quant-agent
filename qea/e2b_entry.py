"""Runs INSIDE an E2B VM (uploaded there by worker_e2b.run_worker_e2b). Builds the
NexAU worker agent from the uploaded agent dir and runs its FULL control loop here:
the LLM calls go direct to OpenRouter from the VM (no local proxy), and the worker's
shell tools run as a local subprocess inside the VM. This is the Harbor-style
"whole agent in the sandbox" pattern — the local orchestrator only ships inputs and
reads back outputs, so its memory footprint stays near-zero regardless of concurrency.

Self-contained: imports only nexau + stdlib (NO qea), so nothing beyond the prebuilt
template need exist in the VM. The provider-pin and answer-free trace summary are
inlined copies of qea.worker_runtime's (kept deliberately in sync).

Reads   /home/user/task.json   {task_id, prompt, is_file_task, ref_names}
Writes  /home/user/output/deliverable.txt   final answer text
        /home/user/output/trace.json         answer-free trace summary
        /home/user/output/files.json         produced deliverable filenames (rel to work/)
"""
import json
import os
import sys
import time
from pathlib import Path

AGENT_DIR = Path("/home/user/agent")
WORK = Path("/home/user/work"); WORK.mkdir(parents=True, exist_ok=True)
OUT = Path("/home/user/output"); OUT.mkdir(parents=True, exist_ok=True)
SUPPORTED = {".xlsx", ".pptx", ".docx", ".pdf"}

task = json.loads(Path("/home/user/task.json").read_text())

# NexAU's agent.yaml resolves ${env.LLM_*} at load; map from the OPENROUTER_API_KEY the
# orchestrator injected as a sandbox env var.
os.environ["LLM_API_KEY"] = os.environ.get("OPENROUTER_API_KEY", os.environ.get("LLM_API_KEY", ""))
os.environ.setdefault("LLM_BASE_URL", "https://openrouter.ai/api/v1")
os.environ.setdefault("LLM_MODEL", "deepseek/deepseek-v4-pro")
sys.path.insert(0, str(AGENT_DIR))  # tools.* are bound by relative module path

# Optional capability gate for Level-B gap experiments: QEA_E2B_BLOCK_PIP=1 disables
# pip inside this VM BEFORE the agent runs, so a shell worker cannot self-install
# missing libraries (openpyxl etc.) — otherwise the "missing library" gap self-heals
# within one episode (observed: the weak GDPval worker pip-installed openpyxl).
if os.environ.get("QEA_E2B_BLOCK_PIP") == "1":
    import subprocess
    subprocess.run(
        "sudo mv /usr/lib/python3/dist-packages/pip /usr/lib/python3/dist-packages/.pip_disabled 2>/dev/null; "
        "for p in $(which -a pip pip3 2>/dev/null | sort -u); do sudo chmod -x \"$p\" 2>/dev/null; done; "
        "python3 -m pip --version >/dev/null 2>&1 && echo PIP_STILL_WORKS || echo PIP_BLOCKED",
        shell=True)

from nexau import Agent, AgentConfig  # noqa: E402

cfg = AgentConfig.from_yaml(config_path=AGENT_DIR / "agent.yaml")
# Provider-pin (inline copy of worker_runtime.pin_provider): routed providers return
# empty/mis-parsed completions; NexAU's LLMConfig has no provider field, so inject via
# extra_body, which to_openai_params() forwards to chat.completions.create.
try:
    model = getattr(cfg.llm_config, "model", "") or ""
    prov = {"deepseek": "deepseek", "qwen": "alibaba"}.get(model.split("/")[0])
    if prov:
        cfg.llm_config.set_param("extra_body", {"provider": {"order": [prov], "allow_fallbacks": False}})
except Exception as e:  # noqa: BLE001
    print("provider-pin skipped:", e, flush=True)

agent = Agent(config=cfg)
try:
    agent.sandbox_manager.instance.work_dir = WORK
except Exception as e:  # noqa: BLE001
    print("work_dir pin skipped:", e, flush=True)

# Reference input files are uploaded into WORK by the orchestrator BEFORE this runs;
# capture the pre-run file set so produced deliverables are the after-minus-before diff.
ref_names = set(task.get("ref_names") or [])
pre = {p for p in WORK.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED}

is_file_task = bool(task.get("is_file_task"))
note = ((f"\n\nIMPORTANT: Your working directory is {WORK}\n"
         f"The reference input files {sorted(ref_names)} are in that directory. "
         "Read inputs from there, and SAVE your deliverable file(s) into that directory.")
        if is_file_task else "")
ctx = {"date": "2026-06-25", "username": "user", "working_directory": str(WORK)}
ctx["env_content"] = dict(ctx)

t0 = time.time()
resp = agent.run(message=task["prompt"] + note, context=ctx)
final = resp if isinstance(resp, str) else (resp[0] if resp else "")

(OUT / "deliverable.txt").write_text(final or "")

produced = [p for p in WORK.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED
            and p not in pre and p.name not in ref_names]
produced = sorted(produced, key=lambda p: p.stat().st_mtime, reverse=True)[:12]
(OUT / "files.json").write_text(json.dumps([str(p.relative_to(WORK)) for p in produced]))

def _render_message(m) -> str:
    """Block-aware message renderer (inline copy of worker_runtime.render_message).
    Message.content is a list of typed blocks; get_text_content() returns only
    TextBlocks, so pure-tool-call assistant turns and ALL tool results rendered as
    "" — the trajectory dump was content-empty and useless as evolve evidence."""
    parts = []
    try:
        blocks = getattr(m, "content", None) or []
        if isinstance(blocks, str):
            return blocks
        for b in blocks:
            btype = getattr(b, "type", "")
            if btype == "text" and getattr(b, "text", ""):
                parts.append(b.text)
            elif btype == "tool_use":
                try:
                    args = json.dumps(getattr(b, "input", {}), ensure_ascii=False)
                except Exception:  # noqa: BLE001
                    args = str(getattr(b, "input", ""))
                parts.append(f"<tool_call {getattr(b, 'name', '?')}> {args[:3000]}")
            elif btype == "tool_result":
                c = getattr(b, "content", "")
                if isinstance(c, list):
                    c = "".join(getattr(p, "text", "") if getattr(p, "type", "") == "text"
                                else "<image>" for p in c)
                tag = "<tool_result ERROR>" if getattr(b, "is_error", False) else "<tool_result>"
                parts.append(f"{tag} {str(c)[:5000]}")
            elif btype == "reasoning" and getattr(b, "text", ""):
                parts.append(f"<reasoning> {b.text[:1500]}")
    except Exception:  # noqa: BLE001
        pass
    if not parts:
        try:
            return m.get_text_content()
        except Exception:  # noqa: BLE001
            return str(getattr(m, "content", "") or "")
    return "\n".join(parts)


# Answer-free trace summary (mirror worker_runtime.summarize_trace).
turns = tool_results = tool_errors = 0
for m in (agent.full_trace or []):
    role = getattr(m, "role", "")
    role = str(getattr(role, "value", role)).split(".")[-1].lower()
    text = _render_message(m)
    if role == "assistant":
        turns += 1
    elif role in ("tool", "tool_result", "function") and text:
        tool_results += 1
        if any(k in text for k in ("Error", "❌", "failed", "Traceback", "Invalid parameters")):
            tool_errors += 1
(OUT / "trace.json").write_text(json.dumps({
    "turns": turns, "tool_calls": tool_results, "tool_errors": tool_errors,
    "secs": round(time.time() - t0, 1), "files": len(produced), "len": len(final or ""),
}))

# Full trajectory (capped) for the AHE-corpus evidence drill-down path (mirror
# worker_runtime's trace.txt); the orchestrator downloads it next to the trace.
try:
    msgs = []
    for m in (agent.full_trace or []):
        role = getattr(m, "role", "")
        msgs.append(f"[{role}] {_render_message(m)}")
    (OUT / "trajectory.txt").write_text("\n\n".join(msgs)[:200000])
except Exception:  # noqa: BLE001
    pass
print(f"ENTRY_DONE len={len(final or '')} turns={turns} tool_calls={tool_results} "
      f"files={len(produced)} secs={round(time.time()-t0,1)}", flush=True)
