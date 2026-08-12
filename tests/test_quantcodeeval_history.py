import json
import shutil

import pytest

from qea.quantcodeeval_history import (
    QuantCodeEvalHistoryError,
    append_quantcodeeval_history,
    materialize_quantcodeeval_history_evidence,
    validate_quantcodeeval_history,
)


AGENT = """\
type: agent
name: history-worker
max_context_tokens: 1000
system_prompt: ./systemprompt.md
system_prompt_type: jinja
tool_call_mode: openai
max_iterations: 2
llm_config:
  model: fixed
  base_url: fixed
  api_key: fixed
  max_tokens: 100
  temperature: 0
  stream: false
  api_type: openai_chat_completion
  timeout: 10
tools: []
tracers: []
"""


def _worker(path):
    path.mkdir()
    (path / "agent.yaml").write_text(AGENT)
    (path / "systemprompt.md").write_text("Solve.\n")
    return path


def _candidate(parent, candidate):
    shutil.copytree(parent, candidate)
    (candidate / "tools").mkdir()
    (candidate / "tools/component.py").write_text(
        "def check(value):\n    return {'ok': bool(value)}\n"
    )
    text = (candidate / "agent.yaml").read_text()
    (candidate / "agent.yaml").write_text(text.replace("tools: []", "tools:\n  - name: check"))
    return candidate


def _append(history, parent, candidate, **overrides):
    values = {
        "history_root": history,
        "run_id": "qce-history-test",
        "iteration": 1,
        "parent_worker_dir": parent,
        "candidate_worker_dir": candidate,
        "decision": {"decision": "ACT", "hypothesis": "component is absent"},
        "mechanism": "register one deterministic component",
        "primary_components": ("tools",),
        "declared_roles": ("agent_config", "tools"),
        "component_tests": ({"kind": "tool", "status": "passed"},),
        "activation": {"status": "not_run"},
        "evaluation": {"T16": {"reward": 1}, "T24": {"reward": 0}},
        "selection": "rejected",
        "rollback_reason": "no property-family gain",
    }
    values.update(overrides)
    return append_quantcodeeval_history(**values)


def test_history_preserves_exact_diff_source_and_outcome(tmp_path):
    parent = _worker(tmp_path / "parent")
    candidate = _candidate(parent, tmp_path / "candidate")
    history = tmp_path / "history"

    first = _append(history, parent, candidate)
    second = _append(history, parent, candidate)

    assert first.entry_id == second.entry_id
    assert second.reused_existing is True
    entry = json.loads(first.entry_path.read_text())
    assert entry["primary_components"] == ["tools"]
    assert entry["declared_roles"] == ["agent_config", "tools"]
    assert entry["mutation_metrics"]["changed_file_count"] == 2
    assert (history / "objects" / first.candidate_digest / "tools/component.py").is_file()
    patch = history / "diffs" / f"{first.diff_sha256}.patch"
    assert "tools/component.py" in patch.read_text()
    assert validate_quantcodeeval_history(history)["entry_count"] == 1


def test_history_evidence_projection_is_read_only_and_complete(tmp_path):
    parent = _worker(tmp_path / "parent")
    candidate = _candidate(parent, tmp_path / "candidate")
    history = tmp_path / "history"
    result = _append(history, parent, candidate)

    projection = materialize_quantcodeeval_history_evidence(
        history_root=history,
        destination=tmp_path / "evidence/history",
    )

    assert projection["entry_ids"] == [result.entry_id]
    projected = tmp_path / "evidence/history"
    assert not (projected / "tests").exists()
    assert (
        projected / "component_checks" / f"{result.candidate_digest}.json"
    ).is_file()
    assert all(
        "tests" not in path.relative_to(projected).parts
        for path in projected.rglob("*")
    )
    assert validate_quantcodeeval_history(history)["entry_count"] == 1
    assert (projected / "entries" / f"{result.entry_id}.json").stat().st_mode & 0o222 == 0


def test_history_rejects_oracle_keys_and_role_mismatch(tmp_path):
    parent = _worker(tmp_path / "parent")
    candidate = _candidate(parent, tmp_path / "candidate")

    with pytest.raises(QuantCodeEvalHistoryError, match="oracle-like"):
        _append(
            tmp_path / "oracle-history",
            parent,
            candidate,
            evaluation={"checker_message": "hidden"},
        )
    with pytest.raises(QuantCodeEvalHistoryError, match="declared roles"):
        _append(
            tmp_path / "role-history",
            parent,
            candidate,
            declared_roles=("tools",),
        )


def test_history_can_retain_rejected_role_mismatch_as_search_experience(tmp_path):
    parent = _worker(tmp_path / "parent")
    candidate = _candidate(parent, tmp_path / "candidate")

    result = _append(
        tmp_path / "history",
        parent,
        candidate,
        declared_roles=("tools",),
        rollback_reason="declared file roles omitted agent_config",
        allow_rejected_attribution_mismatch=True,
    )

    entry = json.loads(result.entry_path.read_text())
    assert entry["selection"] == "rejected"
    assert entry["declared_roles"] == ["tools"]
    assert entry["mutation_metrics"]["component_roles"] == [
        "agent_config",
        "tools",
    ]
    assert entry["mutation_metrics"]["declared_roles_match_actual"] is False

    with pytest.raises(QuantCodeEvalHistoryError, match="declared roles"):
        _append(
            tmp_path / "accepted-history",
            parent,
            candidate,
            declared_roles=("tools",),
            selection="accepted",
            rollback_reason=None,
            allow_rejected_attribution_mismatch=True,
        )


def test_history_detects_snapshot_and_entry_tampering(tmp_path):
    parent = _worker(tmp_path / "parent")
    candidate = _candidate(parent, tmp_path / "candidate")
    history = tmp_path / "history"
    result = _append(history, parent, candidate)
    snapshot = history / "objects" / result.candidate_digest / "tools/component.py"
    snapshot.write_text("tampered\n")

    with pytest.raises(QuantCodeEvalHistoryError, match="snapshot"):
        validate_quantcodeeval_history(history)


def test_history_detects_component_test_tampering(tmp_path):
    parent = _worker(tmp_path / "parent")
    candidate = _candidate(parent, tmp_path / "candidate")
    history = tmp_path / "history"
    result = _append(history, parent, candidate)
    tests = history / "tests" / f"{result.candidate_digest}.json"
    payload = json.loads(tests.read_text())
    payload["tests"][0]["status"] = "failed"
    tests.write_text(json.dumps(payload))

    with pytest.raises(QuantCodeEvalHistoryError, match="component-test"):
        validate_quantcodeeval_history(history)


def test_history_rejects_forbidden_candidate_tree(tmp_path):
    parent = _worker(tmp_path / "parent")
    candidate = _candidate(parent, tmp_path / "candidate")
    (candidate / "tests").mkdir()
    (candidate / "tests/expected.json").write_text("{}\n")

    with pytest.raises(QuantCodeEvalHistoryError, match="forbidden path"):
        _append(tmp_path / "history", parent, candidate)
