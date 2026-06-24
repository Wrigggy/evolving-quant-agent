"""Phase-4 Level-B loop: unit tests for the pure logic + a gated NexAU smoke test.

The NexAU-real pieces (run_worker / run_evolve_agent / the full loop) require an
API key + proxy and are gated behind QEA_LEVELB_SMOKE=1; everything else is
offline and deterministic.
"""
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _dummy_llm_env(monkeypatch):
    """AgentConfig.from_yaml eagerly resolves ${env.LLM_*}; offline tests only need
    the config to PARSE, so provide harmless dummies (no network is made)."""
    monkeypatch.setenv("LLM_MODEL", "deepseek/deepseek-v4-pro")
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")


class _FakeMsg:
    def __init__(self, role, text):
        self.role = role
        self._text = text
    def get_text_content(self):
        return self._text


class _FakeAgent:
    def __init__(self, msgs):
        self.full_trace = msgs


def test_summarize_trace_counts_roles_and_errors():
    from qea.worker_runtime import summarize_trace
    agent = _FakeAgent([
        _FakeMsg("assistant", "let me build it"),
        _FakeMsg("tool", "ok, file written"),
        _FakeMsg("assistant", "now verify"),
        _FakeMsg("tool", "Traceback (most recent call last): Error: boom"),
        _FakeMsg("user", "the task prompt"),
    ])
    mon = summarize_trace(agent)
    assert mon["turns"] == 2          # two assistant messages
    assert mon["tool_calls"] == 2     # two non-user tool/result messages
    assert mon["tool_errors"] == 1    # one carried an error marker


WEAK_DIR = Path(__file__).resolve().parent.parent / "qea" / "worker_gdpval_weak"
FULL_PROMPT = (Path(__file__).resolve().parent.parent
               / "qea" / "worker_gdpval" / "systemprompt.md").read_text()


def test_weak_seed_is_process_limited_not_capability_walled():
    # The weak seed must still load as a NexAU config and keep the shell tool
    # (so evolution CAN recover capability), but its prompt must be stripped of the
    # high-level finish-guidance / per-extension hints the full worker ships.
    from nexau import AgentConfig
    cfg = AgentConfig.from_yaml(config_path=WEAK_DIR / "agent.yaml")
    assert cfg is not None
    weak_prompt = (WEAK_DIR / "systemprompt.md").read_text()
    # headroom markers present in the FULL worker prompt, removed from the weak seed:
    assert "ls -la" not in weak_prompt              # finish/verify guidance removed
    assert "openpyxl" not in weak_prompt            # per-extension tool hints removed
    assert "Verify the file was written" not in weak_prompt
    assert len(weak_prompt) < len(FULL_PROMPT)      # strictly leaner
    # but the shell tool is still available (capability is recoverable by editing)
    tool_yaml = (WEAK_DIR / "tool_descriptions" / "run_shell_command.tool.yaml").read_text()
    assert "run_shell_command" in tool_yaml


def test_process_note_is_answer_free_and_flags_no_deliverable():
    from qea.debugger import process_note
    # produced no file, burned few turns -> the headroom signal
    n = process_note({"files": 0, "turns": 4, "tool_calls": 2, "tool_errors": 1, "secs": 30.0})
    assert "no deliverable file" in n.lower()
    assert "4 turn" in n
    assert "1 tool error" in n
    # a healthy run produces a benign note
    ok = process_note({"files": 1, "turns": 11, "tool_calls": 6, "tool_errors": 0, "secs": 200.0})
    assert "produced" in ok.lower() and "no deliverable file" not in ok.lower()
    # process notes carry only counts — never any answer/number-from-the-task content
    assert "$" not in n and "going-concern" not in n


def test_trace_fold_preserves_firewall():
    from qea.tasks import BTask
    from qea.verifier import TaskResult
    from qea.falsify import EvalSummary
    from qea.debugger import diagnose_b_pile

    class CriticLLM:
        def complete(self, prompt, *, role="judge"):
            if "Classify" in prompt:
                return '{"root_cause_tag": "WrongStructure", "target_slot": "prompt"}'
            return "The deliverable omits the required reconciliation section."

    res = {"t1": TaskResult("t1", "Accountants and Auditors", "B", False, False, False, 0.3, 0.0,
                            None, criterion_verdicts={"1": False})}
    tasks = [BTask(task_id="t1", subtype="Accountants and Auditors", prompt="reconcile the ledger",
                   rubric="", rubric_items=[{"points": 1, "criterion": "reconciles to control total"}],
                   gold="SECRET-CONTROL-TOTAL-98765")]
    diag = diagnose_b_pile(EvalSummary(res, {"t1": "weak memo"}), tasks, llm=CriticLLM(),
                           traces={"t1": {"files": 0, "turns": 3, "tool_errors": 1}})
    payload = repr(diag.proposer_payload())
    assert "SECRET-CONTROL-TOTAL-98765" not in payload   # firewall holds with traces folded in
    assert "t1" in diag.predicted_fix_task_ids
