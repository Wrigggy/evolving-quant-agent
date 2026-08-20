from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "assemble_qfbench_saved_pair_corpus.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("saved_pair_corpus", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _attempt(root: Path, attempt_id: str, task_id: str) -> Path:
    attempt = root / "attempts" / attempt_id
    attempt.mkdir(parents=True)
    (attempt / "attempt.json").write_text(
        json.dumps({"task_id": task_id}), encoding="utf-8"
    )
    (attempt / "worker-execution.json").write_text("{}", encoding="utf-8")
    return attempt


def test_saved_attempt_can_select_reviewed_trajectory(tmp_path: Path) -> None:
    module = _module()
    _attempt(tmp_path, "first", "target")
    selected = _attempt(tmp_path, "reviewed", "target")

    assert module._saved_attempt(
        tmp_path, "target", attempt_id="reviewed"
    ) == selected


def test_saved_attempt_rejects_task_mismatch(tmp_path: Path) -> None:
    module = _module()
    _attempt(tmp_path, "reviewed", "different-task")

    try:
        module._saved_attempt(tmp_path, "target", attempt_id="reviewed")
    except ValueError as error:
        assert "does not belong" in str(error)
    else:
        raise AssertionError("task-mismatched saved attempt was accepted")
