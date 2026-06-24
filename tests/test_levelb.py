"""Phase-4 Level-B loop: unit tests for the pure logic + a gated NexAU smoke test.

The NexAU-real pieces (run_worker / run_evolve_agent / the full loop) require an
API key + proxy and are gated behind QEA_LEVELB_SMOKE=1; everything else is
offline and deterministic.
"""
import os
from pathlib import Path

import pytest


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
