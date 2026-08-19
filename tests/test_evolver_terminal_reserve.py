import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from nexau.archs.main_sub.execution.hooks import (
    AfterAgentHookInput,
    AfterModelHookInput,
    AfterToolHookInput,
    BeforeModelHookInput,
    BeforeAgentHookInput,
    ModelCallParams,
    ToolCallParams,
    MiddlewareManager,
)
from nexau.archs.main_sub.agent_context import AgentContext, GlobalStorage
from nexau.archs.main_sub.agent_state import AgentState
from nexau.archs.main_sub.utils.token_counter import TokenCounter
from nexau.core.messages import Message, Role, TextBlock

from qea.evolve_agent_full.middleware.terminal_reserve import (
    DiscoveryTerminalReserve,
    TerminalReserveError,
)
from qea.evolve_agent_full.middleware.quant_failure_map import (
    QuantFailureMapMiddleware,
)


def _tool(name):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"bounded {name}",
            "parameters": {"type": "object", "additionalProperties": True},
        },
    }


class _State:
    def __init__(self):
        self.values = {}
        self._executor = SimpleNamespace(
            token_counter=TokenCounter(),
            structured_tool_payload=[
                _tool("read_workspace"),
                _tool("probe_evidence"),
                _tool("decide_candidate"),
                _tool("write_candidate"),
                _tool("smoke_candidate_component"),
            ],
        )

    def get_context_value(self, key, default=None):
        return self.values.get(key, default)

    def set_context_value(self, key, value):
        self.values[key] = value


def _real_agent_state(executor=None):
    attached = executor
    if attached is None:
        attached = SimpleNamespace(
            token_counter=TokenCounter(),
            structured_tool_payload=[
                _tool("read_workspace"),
                _tool("probe_evidence"),
                _tool("decide_candidate"),
                _tool("write_candidate"),
                _tool("smoke_candidate_component"),
            ],
        )
    return AgentState(
        agent_name="terminal-reserve-integration",
        agent_id="agent-terminal-reserve-integration",
        run_id="run-terminal-reserve-integration",
        root_run_id="run-terminal-reserve-integration",
        context=AgentContext(),
        global_storage=GlobalStorage(),
        executor=attached,
    )


@pytest.fixture
def terminal_root(tmp_path, monkeypatch):
    result = tmp_path / "result"
    candidate = tmp_path / "candidate"
    result.mkdir()
    candidate.mkdir()
    (candidate / "agent.yaml").write_text("name: candidate\n")
    access = result / "access_log.jsonl"
    access.write_text("")
    monkeypatch.setenv("QEA_ACCESS_LOG", str(access))
    monkeypatch.setenv("QEA_CANDIDATE_ROOT", str(candidate))
    return result


def _large_messages(arm):
    contract_note = {
        "A6-R": "raw evidence failure_type_v1",
        "A6-E": "public contract representation failure_type_v1",
        "A6-EC": "typed semantic_contract_v1 with grounded ACT gate",
    }[arm]
    return [
        Message(role=Role.SYSTEM, content=[TextBlock(text="strict discovery contract")]),
        Message(
            role=Role.USER,
            content=[TextBlock(text=f"{contract_note}\n" + ("evidence " * 101_000))],
        ),
        Message(
            role=Role.ASSISTANT,
            content=[TextBlock(text="warning ignored; continue reading evidence " * 2_000)],
        ),
    ]


def _boundary_messages(characters):
    return [
        Message(role=Role.SYSTEM, content=[TextBlock(text="strict discovery contract")]),
        Message(role=Role.USER, content=[TextBlock(text="x" * characters)]),
    ]


def _before(state, messages, iteration=17):
    return BeforeModelHookInput(
        agent_state=state,
        max_iterations=200,
        current_iteration=iteration,
        messages=messages,
    )


def _model_params(state, messages):
    tools = list(state._executor.structured_tool_payload)
    return ModelCallParams(
        messages=messages,
        max_tokens=None,
        force_stop_reason=None,
        agent_state=state,
        tool_call_mode="openai",
        tools=tools,
        api_params={"tools": tools, "tool_choice": "auto", "max_tokens": 32_000},
    )


def _record_component_smoke(result_root, middleware, component="tools"):
    record = {
        "schema_version": 1,
        "test_index": 1,
        "candidate_digest": middleware._candidate_sha256(),
        "component": component,
        "operation": "import",
        "target": "tools.public_behavior_probe",
        "status": "passed",
        "exit_code": 0,
    }
    (result_root / "component-tests.jsonl").write_text(
        json.dumps(record, sort_keys=True) + "\n"
    )
    return record


@pytest.mark.parametrize("arm", ["A6-R", "A6-E", "A6-EC"])
def test_large_a6_arm_enters_bounded_decision_phase_before_overflow(
    terminal_root, arm
):
    access = terminal_root / "access_log.jsonl"
    original_access = (
        json.dumps(
            {
                "operation": "read",
                "source": "evidence",
                "relative_path": f"{arm}/large.json",
                "bytes_returned": 404_000,
            },
            sort_keys=True,
        )
        + "\n"
    )
    access.write_text(original_access)
    (terminal_root / "probe-log.jsonl").write_text(
        json.dumps({"probe_id": f"{arm.casefold()}-probe", "result_sha256": "a" * 64})
        + "\n"
    )
    middleware = DiscoveryTerminalReserve()
    state = _State()
    messages = _large_messages(arm)
    source_tokens = state._executor.token_counter.count_tokens(
        messages, tools=state._executor.structured_tool_payload
    )
    assert source_tokens > 200_000

    result = middleware.before_model(_before(state, messages))

    assert result.messages is not None
    compacted = result.messages
    compacted_tokens = state._executor.token_counter.count_tokens(
        compacted, tools=state._executor.structured_tool_payload
    )
    assert compacted_tokens + 32_000 < 200_000
    assert len(compacted) == 2
    assert "TERMINAL RESERVE" in compacted[-1].get_text_content()
    assert "Call decide_candidate exactly once" in compacted[-1].get_text_content()
    assert "ACT is forbidden" in compacted[-1].get_text_content()
    assert access.read_text() == original_access
    assert len(state.values["__nexau_full_trace_messages__"]) == len(messages)

    captured = {}

    def model_call(params):
        captured["params"] = params
        return "model-result"

    assert middleware.wrap_model_call(
        _model_params(state, compacted), model_call
    ) == "model-result"
    bounded = captured["params"]
    assert [tool["function"]["name"] for tool in bounded.tools] == [
        "decide_candidate"
    ]
    assert bounded.api_params["max_tokens"] == 32_000
    audit = json.loads((terminal_root / "terminal-reserve.json").read_text())
    assert audit["phase"] == "decision"
    assert audit["activated"] is True
    assert audit["trigger"]["prompt_tokens"] == source_tokens
    assert audit["access"]["record_count"] == 1
    assert audit["access"]["bytes_returned"] == 404_000
    assert audit["last_compact"]["bytes"] <= 65_536


def test_terminal_phase_blocks_all_nondecision_tools_and_never_synthesizes_abstain(
    terminal_root,
):
    middleware = DiscoveryTerminalReserve()
    state = _State()
    compacted = middleware.before_model(
        _before(state, _large_messages("A6-R"))
    ).messages
    assert compacted is not None
    called = False

    def tool_call(params):
        nonlocal called
        called = True
        return {"unexpected": True}

    denied = middleware.wrap_tool_call(
        ToolCallParams(
            agent_state=state,
            sandbox=None,
            tool_name="read_workspace",
            parameters={"file_path": "large.json"},
            tool_call_id="read-1",
            execution_params={},
        ),
        tool_call,
    )
    assert called is False
    assert denied["tool_blocked"] is True

    response = "I need to inspect one more trace before deciding."
    middleware.after_agent(
        AfterAgentHookInput(
            agent_state=state,
            messages=compacted,
            agent_response=response,
            stop_reason=None,
        )
    )
    assert not (terminal_root / "discovery-hypothesis.json").exists()
    audit = json.loads((terminal_root / "terminal-reserve.json").read_text())
    assert audit["phase"] == "invalid"
    assert audit["decision_state_present"] is False
    assert audit["blocked_tool_calls"] == {"read_workspace": 1}
    assert audit["events"][-1]["decision"] is None


def test_terminal_decision_gate_allows_only_abstain(terminal_root):
    middleware = DiscoveryTerminalReserve()
    state = _State()
    middleware.before_model(_before(state, _large_messages("A6-EC")))
    called = []

    def tool_call(params):
        called.append(params.parameters)
        return {"decision": "ABSTAIN", "unlocked": False}

    base = {
        "agent_state": state,
        "sandbox": None,
        "tool_name": "decide_candidate",
        "tool_call_id": "decision-1",
        "execution_params": {},
    }
    blocked = middleware.wrap_tool_call(
        ToolCallParams(
            **base,
            parameters={"discovery": {"decision": "ACT"}},
        ),
        tool_call,
    )
    assert blocked["tool_blocked"] is True
    assert called == []

    allowed = middleware.wrap_tool_call(
        ToolCallParams(
            **base,
            parameters={"discovery": {"decision": "ABSTAIN"}},
        ),
        tool_call,
    )
    assert allowed == {"decision": "ABSTAIN", "unlocked": False}
    assert called == [{"discovery": {"decision": "ABSTAIN"}}]


def test_recorded_abstain_enters_tool_free_final_turn_and_preserves_usage_audit(
    terminal_root,
):
    middleware = DiscoveryTerminalReserve()
    state = _State()
    compacted = middleware.before_model(
        _before(state, _large_messages("A6-EC"))
    ).messages
    assert compacted is not None
    decision = {
        "schema_version": 3,
        "protocol": "semantic_contract_v1",
        "decision": "ABSTAIN",
        "unlocked": False,
        "hypothesis": {"abstain_reason": "typed evidence remains insufficient"},
    }
    (terminal_root / "discovery-hypothesis.json").write_text(
        json.dumps(decision, sort_keys=True) + "\n"
    )
    middleware.after_tool(
        AfterToolHookInput(
            agent_state=state,
            sandbox=None,
            tool_name="decide_candidate",
            tool_call_id="decision-1",
            tool_input={"discovery": decision["hypothesis"]},
            tool_output={"decision": "ABSTAIN", "unlocked": False},
        )
    )
    final_messages = middleware.before_model(
        _before(state, compacted, iteration=18)
    ).messages
    assert final_messages is not None
    seen = {}

    def final_call(params):
        seen["params"] = params
        return "final"

    middleware.wrap_model_call(_model_params(state, final_messages), final_call)
    assert seen["params"].tools == []
    assert "tools" not in seen["params"].api_params
    middleware.after_model(
        AfterModelHookInput(
            agent_state=state,
            max_iterations=200,
            current_iteration=18,
            messages=final_messages,
            original_response='{"decision":"ABSTAIN"}',
            model_response=SimpleNamespace(
                usage={"prompt_tokens": 12_345, "completion_tokens": 321, "total_tokens": 12_666}
            ),
        )
    )
    middleware.after_agent(
        AfterAgentHookInput(
            agent_state=state,
            messages=final_messages,
            agent_response='{"decision":"ABSTAIN"}',
            stop_reason=None,
        )
    )
    audit = json.loads((terminal_root / "terminal-reserve.json").read_text())
    assert audit["phase"] == "complete"
    assert audit["decision_state_present"] is True
    post = [event for event in audit["events"] if event["kind"] == "post_model"][-1]
    assert post["reported_input_tokens"] == 12_345
    assert post["reported_output_tokens"] == 321
    assert post["reported_total_tokens"] == 12_666


def test_recorded_quant_act_with_candidate_change_enters_final_turn(terminal_root):
    middleware = DiscoveryTerminalReserve()
    state = _State()
    initial = _boundary_messages(100)
    middleware.before_agent(SimpleNamespace(agent_state=state, messages=initial))
    decision = {
        "schema_version": 4,
        "protocol": "quant_property_v2",
        "decision": "ACT",
        "unlocked": True,
        "hypothesis": {"primary_components": ["tools"]},
    }
    (terminal_root / "discovery-hypothesis.json").write_text(
        json.dumps(decision, sort_keys=True) + "\n"
    )
    candidate = Path(os.environ["QEA_CANDIDATE_ROOT"])
    (candidate / "tools").mkdir(exist_ok=True)
    (candidate / "tools" / "public_behavior_probe.py").write_text(
        "def probe():\n    return True\n"
    )
    _record_component_smoke(terminal_root, middleware)

    compacted = middleware.before_model(
        _before(state, _boundary_messages(550_000))
    ).messages

    assert compacted is not None
    assert (
        "A valid decision and all required final component smokes are already "
        "durably recorded"
        in compacted[-1].get_text_content()
    )
    audit = json.loads((terminal_root / "terminal-reserve.json").read_text())
    assert audit["phase"] == "final"
    assert audit["decision_state_present"] is True
    assert audit["requires_terminal_abstain"] is False


def test_recorded_quant_act_gets_one_bounded_final_component_smoke(
    terminal_root,
):
    middleware = DiscoveryTerminalReserve()
    state = _State()
    initial = _boundary_messages(100)
    middleware.before_agent(SimpleNamespace(agent_state=state, messages=initial))
    decision = {
        "schema_version": 4,
        "protocol": "quant_property_v2",
        "decision": "ACT",
        "unlocked": True,
        "hypothesis": {"primary_components": ["tools"]},
    }
    (terminal_root / "discovery-hypothesis.json").write_text(
        json.dumps(decision, sort_keys=True) + "\n"
    )
    candidate = Path(os.environ["QEA_CANDIDATE_ROOT"])
    (candidate / "tools").mkdir(exist_ok=True)
    (candidate / "tools" / "public_behavior_probe.py").write_text(
        "def probe():\n    return True\n"
    )
    fixture = candidate / "tools" / "_temporary_fixture.py"
    fixture.write_text("VALUE = 1\n")
    _record_component_smoke(terminal_root, middleware)
    fixture.unlink()

    compacted = middleware.before_model(
        _before(state, _boundary_messages(550_000))
    ).messages
    assert compacted is not None
    terminal = compacted[-1].get_text_content()
    assert "still lacks a passed primary-component smoke for: tools" in terminal
    captured = {}
    assert middleware.wrap_model_call(
        _model_params(state, compacted),
        lambda params: captured.setdefault("params", params) or "smoke",
    ) == captured["params"]
    assert [tool["function"]["name"] for tool in captured["params"].tools] == [
        "smoke_candidate_component"
    ]

    tool_params = ToolCallParams(
        agent_state=state,
        sandbox=None,
        tool_name="smoke_candidate_component",
        parameters={
            "component": "tools",
            "target": "tools.public_behavior_probe",
            "operation": "import",
        },
        tool_call_id="smoke-1",
        execution_params={},
    )

    def smoke_call(_params):
        return _record_component_smoke(terminal_root, middleware)

    smoke_result = middleware.wrap_tool_call(tool_params, smoke_call)
    assert smoke_result["status"] == "passed"
    middleware.after_tool(
        AfterToolHookInput(
            agent_state=state,
            sandbox=None,
            tool_name="smoke_candidate_component",
            tool_call_id="smoke-1",
            tool_input=tool_params.parameters,
            tool_output=smoke_result,
        )
    )

    final_messages = middleware.before_model(
        _before(state, compacted, iteration=18)
    ).messages
    assert final_messages is not None
    final_call = {}
    middleware.wrap_model_call(
        _model_params(state, final_messages),
        lambda params: final_call.setdefault("params", params) or "final",
    )
    assert final_call["params"].tools == []
    middleware.after_agent(
        AfterAgentHookInput(
            agent_state=state,
            messages=final_messages,
            agent_response='{"decision":"ACT"}',
            stop_reason=None,
        )
    )
    audit = json.loads((terminal_root / "terminal-reserve.json").read_text())
    assert audit["phase"] == "complete"
    assert audit["decision_state_present"] is True
    assert any(
        event["kind"] == "final_component_smokes_recorded"
        for event in audit["events"]
    )


def test_early_final_act_redirects_once_to_missing_component_smoke(terminal_root):
    middleware = DiscoveryTerminalReserve()
    state = _State()
    messages = _boundary_messages(100)
    middleware.before_agent(SimpleNamespace(agent_state=state, messages=messages))
    decision = {
        "schema_version": 4,
        "protocol": "quant_property_v2",
        "decision": "ACT",
        "unlocked": True,
        "hypothesis": {"primary_components": ["tools"]},
    }
    (terminal_root / "discovery-hypothesis.json").write_text(
        json.dumps(decision, sort_keys=True) + "\n"
    )
    candidate = Path(os.environ["QEA_CANDIDATE_ROOT"])
    (candidate / "tools").mkdir(exist_ok=True)
    (candidate / "tools" / "public_behavior_probe.py").write_text(
        "def probe():\n    return True\n"
    )

    hook_input = AfterModelHookInput(
        agent_state=state,
        max_iterations=60,
        current_iteration=31,
        messages=messages,
        original_response="The candidate is ready.",
        parsed_response=SimpleNamespace(has_calls=lambda: False),
        model_response=None,
    )
    manager = MiddlewareManager([middleware])
    _, redirected_messages, force_continue = manager.run_after_model(hook_input)

    assert force_continue is True
    assert redirected_messages is not None
    assert "passed primary-component smoke for: tools" in (
        redirected_messages[-1].get_text_content()
    )
    compacted = middleware.before_model(
        _before(state, redirected_messages, iteration=32)
    ).messages
    assert compacted is not None
    captured = {}
    middleware.wrap_model_call(
        _model_params(state, compacted),
        lambda params: captured.setdefault("params", params) or "smoke",
    )
    assert [tool["function"]["name"] for tool in captured["params"].tools] == [
        "smoke_candidate_component"
    ]
    audit = json.loads((terminal_root / "terminal-reserve.json").read_text())
    assert audit["phase"] == "component_smoke"
    assert audit["trigger"]["reason"] == "early_final_missing_component_smoke"
    assert any(
        event["kind"] == "early_final_redirected_to_component_smoke"
        for event in audit["events"]
    )


def test_unimplemented_preterminal_act_must_be_superseded_by_abstain(terminal_root):
    middleware = DiscoveryTerminalReserve()
    state = _State()
    initial = _boundary_messages(100)
    middleware.before_agent(
        SimpleNamespace(agent_state=state, messages=initial)
    )
    act = {
        "schema_version": 2,
        "protocol": "failure_type_v1",
        "decision": "ACT",
        "unlocked": True,
        "hypothesis": {"components": ["validator"]},
    }
    (terminal_root / "discovery-hypothesis.json").write_text(
        json.dumps(act, sort_keys=True) + "\n"
    )

    compacted = middleware.before_model(
        _before(state, _boundary_messages(550_000))
    ).messages

    assert compacted is not None
    assert "ACT is forbidden" in compacted[-1].get_text_content()
    audit = json.loads((terminal_root / "terminal-reserve.json").read_text())
    assert audit["phase"] == "decision"
    assert audit["requires_terminal_abstain"] is True
    assert audit["candidate"]["changed"] is False


def test_terminal_model_call_budget_is_hard(terminal_root):
    middleware = DiscoveryTerminalReserve(max_terminal_model_calls=3)
    state = _State()
    messages = _large_messages("A6-E")
    for index, value in enumerate(("first", "second", "third"), start=1):
        compacted = middleware.before_model(
            _before(state, messages, iteration=16 + index)
        ).messages
        assert compacted is not None
        middleware.wrap_model_call(
            _model_params(state, compacted), lambda bounded, value=value: value
        )
        messages = compacted
    compacted = middleware.before_model(
        _before(state, messages, iteration=20)
    ).messages
    assert compacted is not None
    with pytest.raises(TerminalReserveError, match="budget exhausted"):
        middleware.wrap_model_call(
            _model_params(state, compacted), lambda bounded: "fourth"
        )


@pytest.mark.parametrize("messages", [_large_messages("A6-R"), _boundary_messages(20_000)])
def test_failed_before_model_hook_never_reaches_provider(
    terminal_root, monkeypatch, messages
):
    middleware = DiscoveryTerminalReserve()
    state = _State()
    def fail_before_model(hook_input):
        raise RuntimeError("audit path failed")

    monkeypatch.setattr(middleware, "before_model", fail_before_model)
    manager = MiddlewareManager([middleware])
    unchanged = manager.run_before_model(_before(state, messages))
    assert unchanged == messages
    provider_called = False

    def provider(params):
        nonlocal provider_called
        provider_called = True
        return "unsafe"

    with pytest.raises(TerminalReserveError, match="no successful before-model"):
        middleware.wrap_model_call(_model_params(state, unchanged), provider)
    assert provider_called is False


def test_real_nexau_agent_state_private_executor_drives_guarded_model_call(
    terminal_root,
):
    middleware = DiscoveryTerminalReserve()
    manager = MiddlewareManager([middleware])
    state = _real_agent_state()
    messages = _boundary_messages(20_000)
    assert not hasattr(state, "executor")

    audited = manager.run_before_model(_before(state, messages))
    provider_calls = []
    result = manager.wrap_model_call(
        _model_params(state, audited),
        lambda params: provider_calls.append(params) or "guarded",
    )

    assert result == "guarded"
    assert len(provider_calls) == 1
    audit = json.loads((terminal_root / "terminal-reserve.json").read_text())
    assert [event["kind"] for event in audit["events"]][-2:] == [
        "model_guard_armed",
        "model_guard_consumed",
    ]


def test_real_nexau_agent_state_missing_counter_never_reaches_provider(
    terminal_root,
):
    middleware = DiscoveryTerminalReserve()
    manager = MiddlewareManager([middleware])
    state = _real_agent_state(
        SimpleNamespace(structured_tool_payload=[_tool("decide_candidate")])
    )
    messages = _boundary_messages(20_000)
    assert manager.run_before_model(_before(state, messages)) == messages
    provider_calls = []

    with pytest.raises(TerminalReserveError, match="no successful before-model"):
        manager.wrap_model_call(
            _model_params(state, messages),
            lambda params: provider_calls.append(params) or "unsafe",
        )
    assert provider_calls == []


def test_real_nexau_agent_state_executor_identity_drift_blocks_provider(
    terminal_root,
):
    middleware = DiscoveryTerminalReserve()
    manager = MiddlewareManager([middleware])
    state = _real_agent_state()
    messages = _boundary_messages(20_000)
    audited = manager.run_before_model(_before(state, messages))
    state._executor = SimpleNamespace(
        token_counter=TokenCounter(),
        structured_tool_payload=list(state._executor.structured_tool_payload),
    )
    provider_calls = []

    with pytest.raises(TerminalReserveError, match="executor identity changed"):
        manager.wrap_model_call(
            _model_params(state, audited),
            lambda params: provider_calls.append(params) or "unsafe",
        )
    assert provider_calls == []


def test_exact_prelimit_boundary_triggers_and_below_threshold_does_not(
    terminal_root,
):
    state = _State()
    boundary = _boundary_messages(550_000)
    boundary_tokens = state._executor.token_counter.count_tokens(
        boundary, tools=state._executor.structured_tool_payload
    )
    assert 136_000 <= boundary_tokens < 200_000
    middleware = DiscoveryTerminalReserve()
    assert middleware.before_model(_before(state, boundary)).messages is not None

    below_state = _State()
    below = _boundary_messages(200_000)
    below_tokens = below_state._executor.token_counter.count_tokens(
        below, tools=below_state._executor.structured_tool_payload
    )
    assert below_tokens < 136_000
    below_middleware = DiscoveryTerminalReserve()
    result = below_middleware.before_model(_before(below_state, below))
    assert result.messages is None
    called = []
    assert below_middleware.wrap_model_call(
        _model_params(below_state, below),
        lambda params: called.append(params) or "safe",
    ) == "safe"
    assert len(called) == 1


def test_old_decisive_probe_survives_later_access_pressure(terminal_root):
    old_probe = {
        "schema_version": 1,
        "probe_id": "old-decisive",
        "question": "Does the artifact shape distinguish the hypotheses?",
        "hypothesis_expectations": {
            "h_schema": "rows remain structurally valid",
            "h_formula": "rows become invalid",
        },
        "evidence_paths": ["tasks/a/artifact.json", "tasks/b/artifact.json"],
        "operation": "compare_profiles",
        "result_sha256": "a" * 64,
        "observation": {
            "operation": "compare_profiles",
            "profiles": [
                {"path": "tasks/a/artifact.json", "kind": "json", "size": 17},
                {"path": "tasks/b/artifact.json", "kind": "json", "size": 17},
            ],
        },
    }
    (terminal_root / "probe-log.jsonl").write_text(
        json.dumps(old_probe, sort_keys=True) + "\n"
    )
    with (terminal_root / "access_log.jsonl").open("w") as handle:
        for index in range(2_000):
            handle.write(
                json.dumps(
                    {
                        "operation": "read",
                        "source": "evidence",
                        "relative_path": f"later/{index:04d}.json",
                        "bytes_returned": 100,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    middleware = DiscoveryTerminalReserve()
    state = _State()
    compacted = middleware.before_model(
        _before(state, _boundary_messages(550_000))
    ).messages
    assert compacted is not None
    terminal = compacted[-1].get_text_content()
    assert '"probe_id":"old-decisive"' in terminal
    assert '"observation"' in terminal
    assert '"size":17' in terminal
    audit = json.loads((terminal_root / "terminal-reserve.json").read_text())
    assert audit["access"]["record_count"] == 2_000


def test_agent_profile_registers_exact_terminal_middleware(
    monkeypatch,
    terminal_root,
):
    from nexau import Agent, AgentConfig

    root = Path(__file__).resolve().parents[1] / "qea/evolve_agent_full"
    # Other profile tests may have imported a different top-level ``tools``
    # package.  The real Evolver process starts with a clean module cache, so
    # make that isolation explicit before exercising NexAU's YAML loader.
    monkeypatch.delitem(sys.modules, "tools", raising=False)
    monkeypatch.delitem(sys.modules, "tools.guarded_workspace", raising=False)
    monkeypatch.syspath_prepend(str(root))
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-5.4")
    monkeypatch.setenv("LLM_BASE_URL", "http://proxy.invalid/v1")
    monkeypatch.setenv("LLM_API_KEY", "public-proxy-placeholder")

    config = AgentConfig.from_yaml(config_path=root / "agent.yaml")

    assert len(config.middlewares or []) == 2
    assert type(config.middlewares[0]).__name__ == "QuantFailureMapMiddleware"
    middleware = config.middlewares[1]
    assert type(middleware).__name__ == "DiscoveryTerminalReserve"
    assert type(middleware).__module__ == "middleware.terminal_reserve"
    assert middleware.trigger_tokens == 136_000
    assert middleware.terminal_output_tokens == 32_000
    assert middleware.max_terminal_model_calls == 3
    agent = Agent(config=config)
    configured = agent.executor.middleware_manager.middlewares
    assert [type(value).__name__ for value in configured] == [
        "QuantFailureMapMiddleware",
        "DiscoveryTerminalReserve"
    ]
    assert any(
        tool["function"]["name"] == "decide_candidate"
        for tool in agent.executor.structured_tool_payload
    )
    state = _real_agent_state(agent.executor)
    messages = _boundary_messages(20_000)
    assert not hasattr(state, "executor")
    audited = agent.executor.middleware_manager.run_before_model(
        _before(state, messages)
    )
    provider_calls = []
    assert agent.executor.middleware_manager.wrap_model_call(
        _model_params(state, audited),
        lambda params: provider_calls.append(params) or "profile-guarded",
    ) == "profile-guarded"
    assert len(provider_calls) == 1
    assert middleware._bound_executor is agent.executor
    assert state._executor.token_counter is agent.executor.token_counter
    assert provider_calls[0].tools == agent.executor.structured_tool_payload


def test_quant_failure_map_middleware_injects_only_for_quant_v2(
    tmp_path, monkeypatch
):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    contract = evidence / "contract.json"
    monkeypatch.setenv("QEA_EVIDENCE_ROOT", str(evidence))
    messages = _boundary_messages(100)
    hook = BeforeAgentHookInput(agent_state=_State(), messages=messages)
    middleware = QuantFailureMapMiddleware()

    contract.write_text(
        json.dumps({"decision_protocol": "failure_type_v1"}) + "\n"
    )
    assert middleware.before_agent(hook).messages is None

    contract.write_text(
        json.dumps({"decision_protocol": "quant_property_v2"}) + "\n"
    )
    injected = middleware.before_agent(hook).messages
    assert injected is not None
    assert len(injected) == len(messages) + 1
    guidance = injected[-1].get_text_content()
    assert "QUANT RESEARCH STATE SEARCH" in guidance
    assert "Research Mandate & Contract" in guidance
    assert "research_operation" in guidance
    assert "not the fixed stages of one strategy pipeline" in guidance
    assert "optional domain vocabulary" in guidance
    assert "free-form domain_tags" in guidance
    assert "specification_preservation" in guidance
    assert "formula_parameterization" in guidance
    assert "you may reject both" in guidance
