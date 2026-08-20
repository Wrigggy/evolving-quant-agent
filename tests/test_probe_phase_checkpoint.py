from types import SimpleNamespace

from nexau.archs.main_sub.execution.hooks import (
    AfterModelHookInput,
    AfterToolHookInput,
    BeforeModelHookInput,
    ModelCallParams,
)
from nexau.core.messages import Message, Role, TextBlock

from qea.probe_phase_checkpoint import ProbePhaseCheckpoint


def _message(text="task"):
    return Message(role=Role.USER, content=[TextBlock(text=text)])


def test_checkpoint_closes_inventory_and_preserves_post_observation_turns():
    middleware = ProbePhaseCheckpoint(
        component_tool="check_quant_relations",
        inventory_turns=2,
        min_post_observation_turns=3,
    )
    state = SimpleNamespace()
    before = middleware.before_model(BeforeModelHookInput(
        agent_state=state,
        max_iterations=13,
        current_iteration=2,
        messages=[_message()],
    ))
    assert before.messages is not None
    assert "inventory phase is now closed" in before.messages[-1].get_text_content()

    tools = [
        {"type": "function", "function": {"name": "run_shell_command"}},
        {"type": "function", "function": {"name": "check_quant_relations"}},
    ]
    captured = {}
    params = ModelCallParams(
        messages=before.messages,
        max_tokens=1000,
        force_stop_reason=None,
        agent_state=state,
        tool_call_mode="openai",
        tools=tools,
        api_params={"tools": tools},
    )
    middleware.wrap_model_call(
        params, lambda value: captured.setdefault("params", value) or "ok"
    )
    assert [tool["function"]["name"] for tool in captured["params"].tools] == [
        "check_quant_relations"
    ]

    middleware.after_tool(AfterToolHookInput(
        agent_state=state,
        sandbox=None,
        tool_name="check_quant_relations",
        tool_call_id="call-1",
        tool_input={},
        tool_output={"ok": False, "summary": {"errors": 2}},
    ))
    early = middleware.after_model(AfterModelHookInput(
        agent_state=state,
        max_iterations=13,
        current_iteration=3,
        messages=before.messages,
        original_response="done",
        parsed_response=SimpleNamespace(has_calls=lambda: False),
    ))
    assert early.force_continue is True
    finished = middleware.after_model(AfterModelHookInput(
        agent_state=state,
        max_iterations=13,
        current_iteration=5,
        messages=early.messages,
        original_response="done",
        parsed_response=SimpleNamespace(has_calls=lambda: False),
    ))
    assert finished.force_continue is False


def test_reaudit_does_not_restart_post_observation_reserve():
    middleware = ProbePhaseCheckpoint(
        component_tool="check_quant_relations",
        inventory_turns=2,
        min_post_observation_turns=3,
    )
    state = SimpleNamespace()

    middleware.before_model(BeforeModelHookInput(
        agent_state=state,
        max_iterations=20,
        current_iteration=2,
        messages=[_message()],
    ))
    middleware.after_tool(AfterToolHookInput(
        agent_state=state,
        sandbox=None,
        tool_name="check_quant_relations",
        tool_call_id="call-1",
        tool_input={},
        tool_output={"ok": False},
    ))

    middleware.before_model(BeforeModelHookInput(
        agent_state=state,
        max_iterations=20,
        current_iteration=5,
        messages=[_message()],
    ))
    middleware.after_tool(AfterToolHookInput(
        agent_state=state,
        sandbox=None,
        tool_name="check_quant_relations",
        tool_call_id="call-2",
        tool_input={},
        tool_output={"ok": True},
    ))

    finished = middleware.after_model(AfterModelHookInput(
        agent_state=state,
        max_iterations=20,
        current_iteration=6,
        messages=[_message()],
        original_response="done",
        parsed_response=SimpleNamespace(has_calls=lambda: False),
    ))
    assert finished.force_continue is False
