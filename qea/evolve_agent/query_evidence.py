#!/usr/bin/env python3
"""Evidence query tool for the SELF-DIAGNOSING evolve agent (v3 architecture).

The evidence corpus lives on disk (traces are ~10-30k tokens EACH — far too big to
inline), so diagnosis works like a code agent works a codebase: targeted queries,
progressive disclosure. Run via the shell tool:

    python3 /home/user/evolve_agent/query_evidence.py <cmd> [args] [--evidence DIR]

Commands:
    list                      failing tasks: score, turns, tool_errors, error head
    trace <task> [--grep P] [--tail N] [--head N]
                              one task's full trajectory (default: tail 120 lines);
                              --grep prints matching lines with 2 lines of context
    tools <task>              tool-call histogram for one task's trajectory
    attempts                  every prior attempt: outcome, helped/hurt, behavior notes
    matrix                    task x attempt score matrix

Stdlib only. Default --evidence is /home/user/evidence (the E2B upload path).
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path


def _traces_dir(ev: Path) -> Path:
    return ev / "traces"


def _find_trace(ev: Path, task: str):
    cands = sorted(_traces_dir(ev).glob(f"{task}*"))
    if not cands:
        cands = sorted(p for p in _traces_dir(ev).glob("*") if task in p.name)
    return cands[0] if cands else None


def cmd_list(ev: Path) -> None:
    ov = ev / "overview.md"
    if not ov.exists():
        print("no overview.md found", file=sys.stderr)
        return
    for line in ov.read_text().splitlines():
        if line.startswith("## ") or line.startswith("- process:") or line.startswith("- failed criteria"):
            print(line)


def cmd_trace(ev: Path, task: str, grep: str, head: int, tail: int) -> None:
    p = _find_trace(ev, task)
    if p is None:
        print(f"no trace found for {task!r}; available: "
              f"{[x.name for x in sorted(_traces_dir(ev).glob('*'))[:20]]}", file=sys.stderr)
        return
    lines = p.read_text(errors="replace").splitlines()
    print(f"# {p.name}: {len(lines)} lines")
    if grep:
        rx = re.compile(grep, re.IGNORECASE)
        hits = [i for i, l in enumerate(lines) if rx.search(l)]
        print(f"# {len(hits)} matching lines for {grep!r}")
        shown = set()
        for i in hits[:80]:
            for j in range(max(0, i - 2), min(len(lines), i + 3)):
                if j not in shown:
                    print(f"{j + 1}: {lines[j][:400]}")
                    shown.add(j)
            print("--")
    elif head:
        print("\n".join(l[:400] for l in lines[:head]))
    else:
        print("\n".join(l[:400] for l in lines[-(tail or 120):]))


def cmd_tools(ev: Path, task: str) -> None:
    p = _find_trace(ev, task)
    if p is None:
        print(f"no trace found for {task!r}", file=sys.stderr)
        return
    txt = p.read_text(errors="replace")
    calls = Counter(re.findall(r"<tool_call ([a-z_]+)>", txt))
    errs = txt.count("<tool_result ERROR>")
    print(f"{p.name}: tool calls {dict(calls)} | error results: {errs}")


def cmd_attempts(ev: Path) -> None:
    pe = ev / "past_edits"
    if not pe.exists():
        print("(no prior attempts)")
        return
    for f in sorted(pe.glob("*.diff")):
        print(f"=== {f.name}")
        for line in f.read_text(errors="replace").splitlines():
            if line.startswith("#"):
                print(line)
            else:
                break


def cmd_matrix(ev: Path) -> None:
    m = ev / "archive_scores.md"
    print(m.read_text() if m.exists() else "(no score matrix)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "trace", "tools", "attempts", "matrix"])
    ap.add_argument("task", nargs="?", default="")
    ap.add_argument("--grep", default="")
    ap.add_argument("--head", type=int, default=0)
    ap.add_argument("--tail", type=int, default=0)
    ap.add_argument("--evidence", default="/home/user/evidence")
    a = ap.parse_args()
    ev = Path(a.evidence)
    if a.cmd == "list":
        cmd_list(ev)
    elif a.cmd == "trace":
        cmd_trace(ev, a.task, a.grep, a.head, a.tail)
    elif a.cmd == "tools":
        cmd_tools(ev, a.task)
    elif a.cmd == "attempts":
        cmd_attempts(ev)
    elif a.cmd == "matrix":
        cmd_matrix(ev)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
