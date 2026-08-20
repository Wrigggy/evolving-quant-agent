"""Generic phase checkpoint used only by bounded causal Worker probes."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, cast

from nexau.archs.main_sub.execution.hooks import (
    AfterModelHookInput,
    AfterToolHookInput,
    BeforeModelHookInput,
    HookResult,
    Middleware,
    ModelCallFn,
    ModelCallParams,
)
from nexau.core.messages import Message, Role, TextBlock


def _tool_name(tool: object) -> str | None:
    if not isinstance(tool, Mapping):
        return None
    function = tool.get("function")
    if isinstance(function, Mapping) and isinstance(function.get("name"), str):
        return str(function["name"])
    name = tool.get("name")
    return str(name) if isinstance(name, str) else None


class ProbePhaseCheckpoint(Middleware):
    """End a short inventory phase and preserve action after a component call."""

    def __init__(
        self,
        *,
        component_tool: str,
        inventory_turns: int = 2,
        min_post_observation_turns: int = 3,
    ) -> None:
        if not component_tool or type(inventory_turns) is not int or inventory_turns < 1:
            raise ValueError("invalid component checkpoint configuration")
        if type(min_post_observation_turns) is not int or min_post_observation_turns < 1:
            raise ValueError("invalid post-observation reserve")
        self.component_tool = component_tool
        self.inventory_turns = inventory_turns
        self.min_post_observation_turns = min_post_observation_turns
        self._current_iteration = 0
        self._checkpoint_active = False
        self._checkpoint_injected = False
        self._component_iteration: int | None = None

    @staticmethod
    def _message(text: str) -> Message:
        return Message(role=Role.USER, content=[TextBlock(text=text)])

    def before_model(self, hook_input: BeforeModelHookInput) -> HookResult:
        self._current_iteration = hook_input.current_iteration
        if (
            self._component_iteration is None
            and not self._checkpoint_injected
            and hook_input.current_iteration >= self.inventory_turns
        ):
            self._checkpoint_injected = True
            self._checkpoint_active = True
            feedback = self._message(
                "The bounded inventory phase is now closed. Decide applicability "
                "in this response. If the candidate component applies, call "
                f"`{self.component_tool}` now using only public-task evidence and "
                "the current artifact. Do not make another shell call before that "
                "decision. If it does not apply, state `SKIP` with one concrete "
                "public reason."
            )
            return HookResult.with_modifications(
                messages=[*hook_input.messages, feedback]
            )
        return HookResult.no_changes()

    def wrap_model_call(
        self, params: ModelCallParams, call_next: ModelCallFn
    ) -> object:
        if not self._checkpoint_active:
            return call_next(params)
        tools = list(params.tools or [])
        allowed = [tool for tool in tools if _tool_name(tool) == self.component_tool]
        if len(allowed) != 1:
            raise RuntimeError(f"probe component tool unavailable: {self.component_tool}")
        api_params = dict(params.api_params)
        if params.tool_call_mode == "openai":
            api_params["tools"] = allowed
            api_params["tool_choice"] = "auto"
        bounded = replace(
            params,
            tools=cast(Any, allowed),
            api_params=api_params,
        )
        return call_next(bounded)

    def after_tool(self, hook_input: AfterToolHookInput) -> HookResult:
        if hook_input.tool_name == self.component_tool:
            self._component_iteration = self._current_iteration
            self._checkpoint_active = False
        return HookResult.no_changes()

    def after_model(self, hook_input: AfterModelHookInput) -> HookResult:
        parsed = hook_input.parsed_response
        has_calls = bool(parsed is not None and parsed.has_calls())
        if self._checkpoint_active and not has_calls:
            self._checkpoint_active = False
            return HookResult.no_changes()
        if self._component_iteration is None or has_calls:
            return HookResult.no_changes()
        completed_after = hook_input.current_iteration - self._component_iteration
        if completed_after >= self.min_post_observation_turns:
            return HookResult.no_changes()
        feedback = self._message(
            "The component has returned an observation, but the bounded causal "
            "probe still needs the post-observation transition. Use the remaining "
            "turns to act on any supported finding, run a focused smoke, re-run the "
            "component when applicable, and save the final artifact. Do not restart "
            "broad research."
        )
        return HookResult.with_modifications(
            messages=[*hook_input.messages, feedback],
            force_continue=True,
        )


__all__ = ["ProbePhaseCheckpoint"]
