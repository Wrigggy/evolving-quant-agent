"""Subprocess-based file-capable executor for B-pile artifact code.

Pattern mirrors AHE's nexau `LocalSandbox`: run model-written code as a SEPARATE
`python script.py` process in a throwaway work_dir, with a scrubbed env and
kill-on-timeout. Isolation is the OS process boundary, not a crippled in-process
interpreter — so the child can `import openpyxl` and write files normally. This is
the v0.1 posture; container/cloud isolation (docker / nexau E2BSandbox) is ROADMAP.
The strict in-process `safe_exec_solve` (A-pile, no files) is unaffected.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ArtifactResult:
    status: str                         # "success" | "error" | "timeout"
    paths: list[Path] = field(default_factory=list)   # produced *.xlsx Paths (in work_dir)
    stdout: str = ""
    stderr: str = ""
    work_dir: str = ""                  # temp dir holding artifacts (caller copies, then removes)


def _to_str(s) -> str:
    """TimeoutExpired carries raw bytes on POSIX even with text=True — normalize."""
    if s is None:
        return ""
    return s.decode(errors="replace") if isinstance(s, bytes) else s


def _scrubbed_env() -> dict:
    """Child env minus secrets so model-written code cannot exfiltrate credentials.
    Covers this project's credential families (*_API_KEY, *_TOKEN, OPENROUTER*);
    generic secret names (e.g. AWS_SECRET_ACCESS_KEY) are NOT scrubbed."""
    out = {}
    for k, v in os.environ.items():
        ku = k.upper()
        if ku.endswith("_API_KEY") or ku.endswith("_TOKEN") or ku.startswith("OPENROUTER"):
            continue
        out[k] = v
    return out


def exec_artifact(code: str, timeout: float = 10.0) -> ArtifactResult:
    """Run `code` as `python script.py` in a fresh temp work_dir; collect produced
    *.xlsx. Never raises for child failures — returns an ArtifactResult."""
    work_dir = tempfile.mkdtemp(prefix="qea_artifact_")
    (Path(work_dir) / "script.py").write_text(code, encoding="utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, "script.py"],
            cwd=work_dir, timeout=timeout, capture_output=True, text=True,
            env=_scrubbed_env(),
        )
    except subprocess.TimeoutExpired as exc:
        return ArtifactResult(status="timeout", stdout=_to_str(exc.stdout),
                              stderr=_to_str(exc.stderr), work_dir=work_dir)
    paths = sorted(Path(work_dir).glob("*.xlsx"))
    status = "success" if (proc.returncode == 0 and paths) else "error"
    return ArtifactResult(status=status, paths=paths,
                          stdout=proc.stdout, stderr=proc.stderr, work_dir=work_dir)
