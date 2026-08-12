"""Execute an independent behavior probe against a saved strategy module."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


_RUNNER = r'''
import importlib.util
import json
import pathlib
import sys

import numpy as np
import pandas as pd

module_path = pathlib.Path(sys.argv[1])
data_dir = pathlib.Path(sys.argv[2])
probe_path = pathlib.Path(sys.argv[3])
spec = importlib.util.spec_from_file_location("candidate_strategy", module_path)
strategy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strategy)
probe_code = probe_path.read_text(encoding="utf-8")
exec(compile(probe_code, str(probe_path), "exec"), globals(), globals())
'''


def probe_public_behavior(
    module_path: str,
    probe_code: str,
    data_dir: str = "/app/data",
    timeout_seconds: int = 90,
) -> dict[str, object]:
    """Run probe code with an isolated copy of the candidate module."""

    source = Path(module_path)
    public_data = Path(data_dir)
    timeout = max(1, min(int(timeout_seconds), 180))
    if not source.is_file():
        return {"status": "failed", "error": "strategy module is missing"}
    if not public_data.is_dir():
        return {"status": "failed", "error": "public data directory is missing"}
    if not isinstance(probe_code, str) or not probe_code.strip():
        return {"status": "failed", "error": "probe code is empty"}

    with tempfile.TemporaryDirectory(prefix="qea-public-probe-") as temporary:
        root = Path(temporary)
        candidate = root / "strategy.py"
        probe = root / "probe.py"
        runner = root / "runner.py"
        shutil.copy2(source, candidate)
        probe.write_text(probe_code, encoding="utf-8")
        runner.write_text(_RUNNER, encoding="utf-8")
        try:
            completed = subprocess.run(
                [sys.executable, str(runner), str(candidate), str(public_data), str(probe)],
                cwd=root,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"status": "failed", "error": "probe timed out"}

    stdout = completed.stdout[-12_000:]
    stderr = completed.stderr[-12_000:]
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


__all__ = ["probe_public_behavior"]
