"""Runs INSIDE an E2B VM (uploaded by evolve_e2b.run_evolve_agent_e2b). Builds the
file-editing NexAU evolve agent from the uploaded evolve_agent dir and runs its FULL
control loop here: it EDITS the worker snapshot at /home/user/work (read_file/write_file/
replace/run_shell_command/run_code), self-testing synthesized tool code with run_code in
the SAME environment the worker will run in. LLM calls go direct to OpenRouter from the VM.

Self-contained: imports only nexau + stdlib (NO qea). The provider-pin, model override,
prediction parse, and trace summary are inlined copies of qea.evolve_runtime's.

Reads   /home/user/message.txt              the evolve-agent prompt (built by the orchestrator)
        /home/user/work/                     the worker snapshot to EDIT (comes back edited)
        /home/user/evidence/                 (optional) AHE evidence corpus for shell drill-down
Writes  /home/user/output/final.txt          the agent's final message
        /home/user/output/prediction.json    parsed {predicted_fixes, risk_tasks}
        /home/user/output/trace.json          answer-free trace summary
        /home/user/output/trajectory.txt      full (capped) trajectory dump
        /home/user/output/work_manifest.json  every file rel-path under work/ (to download back)
"""
import json
import os
import sys
from pathlib import Path

EVOLVE_DIR = Path("/home/user/evolve_agent")
WORK = Path("/home/user/work")
OUT = Path("/home/user/output"); OUT.mkdir(parents=True, exist_ok=True)

os.environ["LLM_API_KEY"] = os.environ.get("OPENROUTER_API_KEY", os.environ.get("LLM_API_KEY", ""))
os.environ.setdefault("LLM_BASE_URL", "https://openrouter.ai/api/v1")
os.environ.setdefault("LLM_MODEL", "deepseek/deepseek-v4-pro")

from nexau import Agent, AgentConfig  # noqa: E402


def _provider_for(model: str) -> str:
    pmap = {"deepseek": "deepseek", "qwen": "alibaba", "z-ai": "z-ai"}
    for pair in os.environ.get("QEA_PROVIDER_MAP", "").split(","):
        k, _, v = pair.partition("=")
        if k.strip() and v.strip():
            pmap[k.strip()] = v.strip()
    return pmap.get((model or "").split("/")[0])


def _parse_prediction(text: str) -> dict:
    dec = json.JSONDecoder()
    i = text.find("{")
    while i >= 0:
        try:
            obj, _ = dec.raw_decode(text[i:])
            if isinstance(obj, dict) and ("predicted_fixes" in obj or "risk_tasks" in obj):
                return {"predicted_fixes": [str(t) for t in (obj.get("predicted_fixes") or [])],
                        "risk_tasks": [str(t) for t in (obj.get("risk_tasks") or [])]}
        except json.JSONDecodeError:
            pass
        i = text.find("{", i + 1)
    return {"predicted_fixes": [], "risk_tasks": []}


cfg = AgentConfig.from_yaml(config_path=EVOLVE_DIR / "agent.yaml")
# Override the evolve agent's model INDEPENDENTLY of the worker (LLM_MODEL is the worker's).
_evolve_model = os.environ.get("QEA_EVOLVE_AGENT_MODEL")
if _evolve_model:
    try:
        cfg.llm_config.model = _evolve_model
    except Exception:  # noqa: BLE001
        cfg.llm_config.set_param("model", _evolve_model)
# Provider-pin (inline copy of pin_provider) — supports z-ai (GLM) too.
try:
    prov = _provider_for(getattr(cfg.llm_config, "model", "") or "")
    if prov:
        cfg.llm_config.set_param("extra_body", {"provider": {"order": [prov], "allow_fallbacks": False}})
except Exception as e:  # noqa: BLE001
    print("provider-pin skipped:", e, flush=True)

agent = Agent(config=cfg)
try:
    agent.sandbox_manager.instance.work_dir = WORK
except Exception as e:  # noqa: BLE001
    print("work_dir pin skipped:", e, flush=True)

msg = Path("/home/user/message.txt").read_text()
ctx = {"working_directory": str(WORK), "username": "user"}
ctx["env_content"] = dict(ctx)
resp = agent.run(message=msg, context=ctx)
final = resp if isinstance(resp, str) else (resp[0] if resp else "")

(OUT / "final.txt").write_text(final or "")
(OUT / "prediction.json").write_text(json.dumps(_parse_prediction(final or "")))

# Answer-free trace summary + full trajectory dump (mirror evolve_runtime).
turns = tool_results = tool_errors = 0
dump = []
for m in (agent.full_trace or []):
    role = str(getattr(getattr(m, "role", ""), "value", getattr(m, "role", ""))).split(".")[-1].lower()
    try:
        text = m.get_text_content()
    except Exception:  # noqa: BLE001
        text = str(getattr(m, "content", "") or "")
    if role == "assistant":
        turns += 1
    elif role in ("tool", "tool_result", "function") and text:
        tool_results += 1
        if any(k in text for k in ("Error", "❌", "failed", "Traceback", "Invalid parameters")):
            tool_errors += 1
    tcs = getattr(m, "tool_calls", None)
    tc_repr = ""
    if tcs:
        parts = []
        for tc in tcs:
            fn = getattr(getattr(tc, "function", None), "name", None) or getattr(tc, "name", "?")
            args = getattr(getattr(tc, "function", None), "arguments", None) or getattr(tc, "arguments", "")
            parts.append(f"CALL {fn}({str(args)[:400]})")
        tc_repr = " | ".join(parts)
    dump.append(f"=== [{role}] ===\nTOOL_CALLS: {tc_repr}\nCONTENT: {str(text)[:1200]}")
(OUT / "trace.json").write_text(json.dumps({
    "turns": turns, "tool_calls": tool_results, "tool_errors": tool_errors, "len": len(final or "")}))
(OUT / "trajectory.txt").write_text("\n\n".join(dump)[:160000])

# Manifest of every file under work/ so the orchestrator downloads the EDITED dir back.
files = [str(p.relative_to(WORK)) for p in WORK.rglob("*")
         if p.is_file() and "__pycache__" not in str(p) and p.suffix != ".pyc"]
(OUT / "work_manifest.json").write_text(json.dumps(files))
print(f"EVOLVE_ENTRY_DONE turns={turns} tool_calls={tool_results} files={len(files)} "
      f"pred={_parse_prediction(final or '')}", flush=True)
