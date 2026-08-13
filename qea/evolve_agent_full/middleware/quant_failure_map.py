"""Inject a compact finance-specific diagnostic map for QuantCodeEval search."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from nexau.archs.main_sub.execution.hooks import (
    BeforeAgentHookInput,
    HookResult,
    Middleware,
)
from nexau.core.messages import Message, Role, TextBlock


class QuantFailureMapMiddleware(Middleware):
    """Give the Evolver a finance failure map without choosing its mechanism."""

    @staticmethod
    def _contract() -> Mapping[str, object] | None:
        raw = os.environ.get("QEA_EVIDENCE_ROOT")
        if not raw:
            return None
        path = Path(raw) / "contract.json"
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, Mapping) else None

    @staticmethod
    def _map() -> Mapping[str, object]:
        path = Path(__file__).resolve().parents[1] / "quant_failure_map.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError("quant failure map must be a JSON object")
        return value

    def before_agent(self, hook_input: BeforeAgentHookInput) -> HookResult:
        contract = self._contract()
        if contract is None or contract.get("decision_protocol") != "quant_property_v2":
            return HookResult.no_changes()
        failure_map = self._map()
        stages = failure_map.get("breakdown_stages")
        classes = failure_map.get("semantic_classes")
        if not isinstance(stages, list) or not isinstance(classes, list):
            raise ValueError("quant failure map axes are unavailable")
        compact_stages = []
        for item in stages:
            if not isinstance(item, Mapping):
                continue
            compact_stages.append(
                {
                    "breakdown_stage": item.get("breakdown_stage"),
                    "diagnostic_question": item.get("diagnostic_question"),
                    "component_state_target": item.get("component_state_target"),
                }
            )
        compact_classes = []
        for item in classes:
            if not isinstance(item, Mapping):
                continue
            compact_classes.append(
                {
                    "failure_class": item.get("failure_class"),
                    "diagnostic_question": item.get("diagnostic_question"),
                    "nearby_classes_to_eliminate": item.get(
                        "nearby_classes_to_eliminate"
                    ),
                }
            )
        guidance = (
            "QUANT/FINANCE DIAGNOSTIC MAP\n"
            "Use this as optional domain vocabulary, not a required form or answer. "
            "Use a listed stage/class only when runtime evidence supports it; add "
            "free-form domain_tags or propose a new concise class when it does not. "
            "The concrete component state and a falsifiable mechanism matter more "
            "than filling every category. A and B are optional mechanism hypotheses; "
            "you may reject both, propose another mechanism, or ABSTAIN. Read "
            "evidence/guidance/quant_failure_map.json for the complete map.\n"
            + json.dumps(
                {"breakdown_stages": compact_stages, "semantic_classes": compact_classes},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        messages = list(hook_input.messages)
        messages.append(
            Message(role=Role.FRAMEWORK, content=[TextBlock(text=guidance)])
        )
        return HookResult.with_modifications(messages=messages)


__all__ = ["QuantFailureMapMiddleware"]
