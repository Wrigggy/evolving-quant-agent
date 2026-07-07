"""Level-B evolve agent runtime: snapshot a worker dir, run the file-editing NexAU
evolve agent against it from a sanitized (answer-free) diagnosis, and produce the
diff artifacts the loop's buffer + leakage guard consume.

The evolve agent edits a SNAPSHOT (per-iteration copy), never the live incumbent;
the loop promotes the snapshot only on a kept edit. The agent's writes are confined
to the snapshot dir via the pinned sandbox work_dir + an explicit prompt constraint.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

EVOLVE_DIR = Path(__file__).resolve().parent / "evolve_agent"
# Files in the worker dir the evolve agent is allowed to read/diff (text only).
_TEXT_SUFFIXES = {".yaml", ".yml", ".md", ".py", ".txt", ".json"}


def snapshot_dir(src: Path, dst: Path) -> None:
    """Full per-iteration copy (AHE-style). Overwrites dst if present."""
    src, dst = Path(src), Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _text_files(d: Path) -> dict:
    d = Path(d)
    out = {}
    for p in sorted(d.rglob("*")):
        # Skip scratch files run_code/execute_code drops in the work dir (normally
        # auto-cleaned; guard against a leftover becoming a phantom edit in the diff/sig)
        # and __pycache__.
        if p.name.startswith("tmp") and p.suffix == ".py":
            continue
        if "__pycache__" in p.parts:
            continue
        if p.is_file() and p.suffix.lower() in _TEXT_SUFFIXES:
            try:
                out[str(p.relative_to(d))] = p.read_text().splitlines(keepends=True)
            except Exception:  # noqa: BLE001 - skip unreadable/binary
                pass
    return out


def dir_unified_diff(before: Path, after: Path) -> str:
    """Unified diff of the TEXT files between two worker dirs (relative paths)."""
    a, b = _text_files(before), _text_files(after)
    chunks = []
    for rel in sorted(set(a) | set(b)):
        d = difflib.unified_diff(a.get(rel, []), b.get(rel, []),
                                 fromfile=f"a/{rel}", tofile=f"b/{rel}")
        chunks.append("".join(d))
    return "".join(c for c in chunks if c)


def diff_signature(diff: str) -> str:
    """Stable signature of an edit = sha256 of its unified diff (buffer key)."""
    return hashlib.sha256(diff.encode("utf-8")).hexdigest()


@dataclass
class DirEdit:
    """Edit-like shim so the existing RejectedEditBuffer + LeakageGuard +
    evaluate_changes work on a directory diff unchanged. The buffer/guard call
    .signature()/.content/.summary; evaluate_changes reads .predicted_fixes /
    .risk_tasks (the evolve agent's prediction) + .slot/.component_name."""
    diff: str
    predicted_fixes: list = field(default_factory=list)
    risk_tasks: list = field(default_factory=list)
    op: str = "edit"
    slot: str = "worker_dir"

    def signature(self) -> str:
        return diff_signature(self.diff)

    @property
    def content(self) -> str:
        # only the ADDED lines feed the leakage guard (mirrors edit.content semantics)
        return "\n".join(l[1:] for l in self.diff.splitlines()
                         if l.startswith("+") and not l.startswith("+++"))

    @property
    def _files(self) -> list:
        return sorted({l[6:] for l in self.diff.splitlines() if l.startswith("+++ b/")})

    @property
    def component_name(self) -> str:
        return ",".join(self._files) or "(none)"

    @property
    def summary(self) -> str:
        adds = sum(1 for l in self.diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
        dels = sum(1 for l in self.diff.splitlines() if l.startswith("-") and not l.startswith("---"))
        return f"edit {', '.join(self._files) or '(none)'} (+{adds}/-{dels})" if self.diff else "(no change)"


def _parse_prediction(text: str) -> dict:
    """Pull the evolve agent's prediction JSON from its final message. Returns
    {"predicted_fixes": [...], "risk_tasks": [...]} (empty lists if absent/malformed)."""
    dec = json.JSONDecoder()
    i = text.find("{")
    while i >= 0:
        try:
            obj, _ = dec.raw_decode(text[i:])
            if isinstance(obj, dict) and ("predicted_fixes" in obj or "risk_tasks" in obj):
                return {
                    "predicted_fixes": [str(t) for t in (obj.get("predicted_fixes") or [])],
                    "risk_tasks": [str(t) for t in (obj.get("risk_tasks") or [])],
                }
        except json.JSONDecodeError:
            pass
        i = text.find("{", i + 1)
    return {"predicted_fixes": [], "risk_tasks": []}


def _read_reference() -> str:
    """The (b) answer-free NexAU-modification reference, inlined into every evolve
    prompt so the agent knows the substrate format (how to wire/write a tool, the
    agent.yaml schema, the loop knobs) when using its code-writing authority."""
    try:
        return (EVOLVE_DIR / "reference" / "NEXAU_GUIDE.md").read_text()
    except Exception:  # noqa: BLE001
        return ""


def _read_first(path: Path, limit: int = 20000) -> str:
    try:
        return path.read_text()[:limit]
    except Exception:  # noqa: BLE001
        return ""


def _build_evolve_message(sanitized_diagnosis: dict, *, edit_history: str = "",
                          evidence_dir=None, evidence_ref: str = None) -> str:
    """Build the evolve-agent prompt (diagnosis + optional AHE evidence + reference +
    predict-JSON tail). Shared by the local (run_evolve_agent) and E2B (run_evolve_agent_e2b)
    paths. `evidence_dir` is where overview.md/history are READ from (local); `evidence_ref`
    is the path STRING to reference for shell drill-down (the VM path for the E2B backend;
    defaults to the local evidence_dir/traces)."""
    reference = _read_reference()
    task_ids = sanitized_diagnosis.get("predicted_fix_task_ids") or []
    rc = sanitized_diagnosis.get("root_cause") or sanitized_diagnosis.get("overview") or ""
    mech = sanitized_diagnosis.get("general_mechanism") or ""
    kind = sanitized_diagnosis.get("mechanism_kind") or sanitized_diagnosis.get("root_cause_tag") or ""
    diag_lines = (
        f"- ROOT CAUSE: {rc}\n"
        f"- SUGGESTED HARNESS CHANGE ({kind}): {mech}\n"
        f"- tasks currently failing: {task_ids}\n"
    )
    head = (
        "Your working directory contains a worker agent defined as files (agent.yaml, "
        "systemprompt.md, tool_descriptions/, and possibly tools/). Make the harness "
        "improvement(s) that address the deficiency(ies) below. You are NOT limited to one "
        "change — if the diagnosis names several distinct capability gaps, fix as many as "
        "the evidence supports in this pass (e.g. wire in a retrieval tool AND add a "
        "calculator AND tighten the prompt). Prefer high-impact, well-supported edits; do "
        "not pad with speculative ones. You may edit any file — rewrite the prompt, edit a "
        "tool description, re-wire a tool binding in agent.yaml, or add a new tool. Improve "
        "how the worker WORKS, not what it answers: NEVER hard-code a task's answer, a "
        "specific number, or a domain fact into a worker file (that is cheating and is "
        "rejected) — even though the evidence may show you expected values, they are for "
        "diagnosis only.\n\n"
        "Inspect files with read_file (and `ls tools/` / read the impl to find unbound "
        "tools you can re-wire), then edit with the write_file (create/overwrite) or "
        "replace (surgical) tools — NOT run_shell_command heredocs, which fumble on "
        "multi-line YAML/Python. An edit only counts if it changes a file on disk; "
        "re-read each file you changed to confirm before finishing.\n\n"
        "SELF-TEST any tool code you WRITE or EDIT with the `run_code` tool before you "
        "finish: import the module and call the function on a small sample input to prove "
        "it imports and runs (`import tools.fab.research; print(research.some_fn(...))`). A "
        "tool that raises SyntaxError/ImportError/TypeError is worse than none — fix it "
        "before finishing. (A network error in the check is fine; a code error is not.)\n\n"
        f"## NexAU modification reference\n{reference}\n"
    )
    if evidence_dir is not None:
        evidence_dir = Path(evidence_dir).resolve()
        traces_ref = evidence_ref or str(evidence_dir / "traces")
        overview = _read_first(evidence_dir / "overview.md")
        history = _read_first(evidence_dir / "evolution_history.md", 6000)
        evidence_block = (
            "## Failure evidence (MANDATORY — read before editing)\n"
            "The overview distills why tasks failed (failed criteria incl. expected values, "
            "process, the worker's own deliverable). Use it to see WHAT the worker got wrong "
            "vs expected — for diagnosis only, never to hard-code an answer. Raw per-task "
            f"trajectories are on disk under `{traces_ref}` — drill in with the shell if you "
            "need more detail.\n\n"
            f"### overview.md\n{overview}\n\n### evolution_history.md\n{history}\n\n"
            f"## Diagnosis (root cause + suggested change)\n{diag_lines}"
        )
    else:
        history_block = f"\nEDITS ALREADY TRIED (do not repeat):\n{edit_history}\n" if edit_history else ""
        evidence_block = (
            f"## Diagnosis (root cause + suggested change)\n{diag_lines}{history_block}"
        )
    tail = (
        "\nEND your reply with a JSON object on its own line predicting the effect of "
        'your edit, using ONLY task ids from the failing list above, e.g.:\n'
        '{"predicted_fixes": ["<task_id>", ...], "risk_tasks": ["<task_id>", ...], '
        '"rationale": "<one sentence>"}\n'
    )
    return head + evidence_block + tail


def run_evolve_agent(snapshot_dir_path: Path, sanitized_diagnosis: dict, run_dir: Path,
                     *, edit_history: str = "", evidence_dir=None) -> dict:
    """Invoke the file-editing NexAU evolve agent against the snapshot. The agent may
    edit ANY file in the worker dir (prompt, tool descriptions, agent.yaml bindings, or
    new tool code) and is always handed the answer-free NexAU-modification reference (b).

    Two evidence modes:
    - sanitized (evidence_dir=None): the agent sees ONLY the answer-free diagnosis +
      edit history (iron-law-2 firewall ON).
    - ahe_corpus (evidence_dir set): the agent is ALSO handed the AHE-style evidence
      corpus (per-task failure overview + edit history inlined, raw traces available
      for drill-down). Firewall relaxed — but the gold answer is NEVER included.

    Returns the final text, an answer-free trace, and the parsed prediction."""
    from nexau import Agent, AgentConfig
    from .worker_runtime import ensure_nexau_llm_env, pin_provider, summarize_trace
    ensure_nexau_llm_env()
    # MUST be absolute: the sandbox shell/file tools `cd`/resolve relative to the pinned
    # work_dir from a different base cwd, so a relative work_dir -> "No such file or
    # directory" on every read/edit (the agent then loops + narrates phantom edits).
    snap = Path(snapshot_dir_path).resolve()
    cfg = AgentConfig.from_yaml(config_path=EVOLVE_DIR / "agent.yaml")
    # The evolve agent's model can be swapped INDEPENDENTLY of the worker via
    # QEA_EVOLVE_AGENT_MODEL. The agent.yaml resolves ${env.LLM_MODEL}, but LLM_MODEL is
    # SHARED with the worker (the E2B VM inherits it) — setting it globally would also
    # change the weak worker. So override just this agent's model here, after from_yaml,
    # leaving LLM_MODEL (worker) untouched. pin_provider() runs AFTER so the swapped
    # model gets its own official-provider pin (extend the map for new prefixes, e.g.
    # QEA_PROVIDER_MAP="z-ai=z-ai" for GLM).
    _evolve_model = os.environ.get("QEA_EVOLVE_AGENT_MODEL")
    if _evolve_model:
        try:
            cfg.llm_config.model = _evolve_model
        except Exception:  # noqa: BLE001 - fall back to the config-object setter
            cfg.llm_config.set_param("model", _evolve_model)
    pin_provider(cfg.llm_config)
    agent = Agent(config=cfg)
    try:
        agent.sandbox_manager.instance.work_dir = snap
    except Exception:  # noqa: BLE001
        pass
    msg = _build_evolve_message(sanitized_diagnosis, edit_history=edit_history,
                                evidence_dir=evidence_dir)
    ctx = {"working_directory": str(snap), "username": os.environ.get("USER", "kevin")}
    ctx["env_content"] = dict(ctx)
    resp = agent.run(message=msg, context=ctx)
    final_text = resp if isinstance(resp, str) else (resp[0] if resp else "")
    # Dump the evolve agent's own trajectory (capped) for debugging whether it actually
    # executed tool calls vs only narrated edits.
    try:
        out = []
        for m in (agent.full_trace or []):
            role = str(getattr(getattr(m, "role", ""), "value", getattr(m, "role", ""))).split(".")[-1].lower()
            content = getattr(m, "content", "")
            tcs = getattr(m, "tool_calls", None)
            tc_repr = ""
            if tcs:
                parts = []
                for tc in tcs:
                    fn = getattr(getattr(tc, "function", None), "name", None) or getattr(tc, "name", "?")
                    args = getattr(getattr(tc, "function", None), "arguments", None) or getattr(tc, "arguments", "")
                    parts.append(f"CALL {fn}({str(args)[:400]})")
                tc_repr = " | ".join(parts)
            out.append(f"=== [{role}] ===\nTOOL_CALLS: {tc_repr}\nCONTENT: {str(content)[:1200]}")
        (Path(run_dir) / "evolve_trace.txt").write_text("\n\n".join(out)[:160000])
    except Exception as exc:  # noqa: BLE001
        (Path(run_dir) / "evolve_trace.txt").write_text(f"dump failed: {exc}")
    return {"final_text": final_text, "trace": summarize_trace(agent),
            "prediction": _parse_prediction(final_text)}
