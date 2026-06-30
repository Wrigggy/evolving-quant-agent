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
    from .worker_runtime import ensure_nexau_llm_env, summarize_trace
    ensure_nexau_llm_env()
    snap = Path(snapshot_dir_path)
    cfg = AgentConfig.from_yaml(config_path=EVOLVE_DIR / "agent.yaml")
    agent = Agent(config=cfg)
    try:
        agent.sandbox_manager.instance.work_dir = snap
    except Exception:  # noqa: BLE001
        pass
    task_ids = sanitized_diagnosis.get("predicted_fix_task_ids") or []
    reference = _read_reference()

    head = (
        "Your working directory contains a worker agent defined as files (agent.yaml, "
        "systemprompt.md, tool_descriptions/, and possibly tools/). Make ONE focused "
        "harness improvement that addresses the deficiency CLASS below, then stop. You "
        "may edit any file in the working directory — rewrite the prompt, edit a tool "
        "description, re-wire a tool binding in agent.yaml, or add a new tool — but NEVER "
        "hardcode task answers, numbers, or domain facts. Improve how the worker WORKS, "
        "not what it answers.\n\n"
        "First inspect the current files (`cat agent.yaml`, `cat systemprompt.md`, "
        "`ls tool_descriptions/`), then make a minimal targeted edit.\n\n"
        f"## NexAU modification reference\n{reference}\n"
    )

    if evidence_dir is not None:
        evidence_dir = Path(evidence_dir)
        overview = _read_first(evidence_dir / "overview.md")
        history = _read_first(evidence_dir / "evolution_history.md", 6000)
        evidence_block = (
            "## Failure evidence (MANDATORY — read before editing; NO gold answer here)\n"
            "The overview below distills why tasks failed (failed criteria, process, the "
            "worker's own deliverable). Raw per-task trajectories are on disk under "
            f"`{evidence_dir / 'traces'}` — drill into them with the shell only if needed.\n\n"
            f"### overview.md\n{overview}\n\n### evolution_history.md\n{history}\n\n"
            f"- root cause (classified): {sanitized_diagnosis.get('root_cause_tag')}\n"
            f"- tasks currently failing: {task_ids}\n"
        )
    else:
        history_block = f"\nEDITS ALREADY TRIED (do not repeat):\n{edit_history}\n" if edit_history else ""
        evidence_block = (
            f"## Diagnosis (answer-free)\n"
            f"- root cause: {sanitized_diagnosis.get('root_cause_tag')}\n"
            f"- category: {sanitized_diagnosis.get('deficiency_category')}\n"
            f"- overview: {sanitized_diagnosis.get('overview')}\n"
            f"- tasks currently failing: {task_ids}\n"
            f"{history_block}"
        )

    tail = (
        "\nEND your reply with a JSON object on its own line predicting the effect of "
        'your edit, using ONLY task ids from the failing list above, e.g.:\n'
        '{"predicted_fixes": ["<task_id>", ...], "risk_tasks": ["<task_id>", ...], '
        '"rationale": "<one sentence>"}\n'
    )
    msg = head + evidence_block + tail
    ctx = {"working_directory": str(snap), "username": os.environ.get("USER", "kevin")}
    ctx["env_content"] = dict(ctx)
    resp = agent.run(message=msg, context=ctx)
    final_text = resp if isinstance(resp, str) else (resp[0] if resp else "")
    return {"final_text": final_text, "trace": summarize_trace(agent),
            "prediction": _parse_prediction(final_text)}
