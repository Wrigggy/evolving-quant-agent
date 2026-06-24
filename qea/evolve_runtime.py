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
import os
import shutil
from dataclasses import dataclass
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
    """Edit-like shim so the existing RejectedEditBuffer + LeakageGuard work on a
    directory diff unchanged (they only call .signature() / read .content / .summary)."""
    diff: str

    def signature(self) -> str:
        return diff_signature(self.diff)

    @property
    def content(self) -> str:
        # only the ADDED lines feed the leakage guard (mirrors edit.content semantics)
        return "\n".join(l[1:] for l in self.diff.splitlines()
                         if l.startswith("+") and not l.startswith("+++"))

    @property
    def summary(self) -> str:
        files = sorted({l[4:] for l in self.diff.splitlines() if l.startswith("+++ b/")})
        adds = sum(1 for l in self.diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
        dels = sum(1 for l in self.diff.splitlines() if l.startswith("-") and not l.startswith("---"))
        return f"edit {', '.join(files) or '(none)'} (+{adds}/-{dels})" if self.diff else "(no change)"


def run_evolve_agent(snapshot_dir_path: Path, sanitized_diagnosis: dict, run_dir: Path) -> dict:
    """Invoke the file-editing NexAU evolve agent against the snapshot. Reads ONLY the
    sanitized diagnosis (answer-free) — never the grader gold / rubric text. Returns
    a small summary dict (final text + trace)."""
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
    msg = (
        "You may improve the worker agent in your working directory. You may edit ONLY "
        "files inside the working directory (its agent.yaml, systemprompt.md, and "
        "tool_descriptions/). Make ONE focused improvement that addresses the diagnosis "
        "below, then stop. Do NOT invent task answers or domain facts — improve the "
        "agent's PROCESS (prompt guidance, tool descriptions).\n\n"
        f"SANITIZED DIAGNOSIS (answer-free):\n"
        f"- root cause: {sanitized_diagnosis.get('root_cause_tag')}\n"
        f"- category: {sanitized_diagnosis.get('deficiency_category')}\n"
        f"- suggested focus: {sanitized_diagnosis.get('suggested_target_slot')}\n"
        f"- overview: {sanitized_diagnosis.get('overview')}\n"
    )
    ctx = {"working_directory": str(snap), "username": os.environ.get("USER", "kevin")}
    ctx["env_content"] = dict(ctx)
    resp = agent.run(message=msg, context=ctx)
    final_text = resp if isinstance(resp, str) else (resp[0] if resp else "")
    return {"final_text": final_text, "trace": summarize_trace(agent)}
