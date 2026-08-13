"""Lightweight component hypotheses and stability evidence for QuantCodeEval.

The ledger is deliberately separate from candidate-file history.  History says
what changed in one harness branch; this module says what capability a component
or small component composition was meant to provide and how often that exact
hypothesis was activated, repeated, protected, or transferred.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping


class QuantComponentLedgerError(ValueError):
    """A component ledger cannot support the requested interpretation."""


class ComponentOrigin(str, Enum):
    INVESTIGATOR_SEEDED = "investigator_seeded"
    EVOLVER_DISCOVERED = "evolver_discovered"
    HISTORY_REUSED = "history_reused"


class ComponentTrialRole(str, Enum):
    TARGET = "target"
    REPEAT = "repeat"
    PROTECTION = "protection"
    TRANSFER = "transfer"
    ABLATION = "ablation"


class ComponentStability(str, Enum):
    UNTESTED = "untested"
    NOT_ACTIVATED = "not_activated"
    UNSUPPORTED = "unsupported"
    MIXED = "mixed"
    PROVISIONAL = "provisional"
    REPLICATED = "replicated"
    PROTECTED = "protected"
    TRANSFERABLE = "transferable"


@dataclass(frozen=True)
class QuantComponent:
    component_id: str
    origin: ComponentOrigin
    capabilities: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class ComponentHypothesis:
    hypothesis_id: str
    component_ids: tuple[str, ...]
    evidence_gap: str
    expected_worker_change: str
    target_task_ids: tuple[str, ...]
    protection_task_ids: tuple[str, ...]


@dataclass(frozen=True)
class ComponentTrial:
    run_id: str
    hypothesis_id: str
    task_id: str
    role: ComponentTrialRole
    available_components: tuple[str, ...]
    selected_components: tuple[str, ...]
    activated_components: tuple[str, ...]
    official_reward: float | None
    properties_passed: int | None
    properties_total: int | None
    requests: int
    tokens: int
    cost_usd: float
    observation: str
    removed_components: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.official_reward == 1.0


@dataclass(frozen=True)
class QuantComponentLedger:
    scope: str
    components: tuple[QuantComponent, ...]
    hypotheses: tuple[ComponentHypothesis, ...]
    trials: tuple[ComponentTrial, ...]
    notes: tuple[str, ...] = ()

    def component(self, component_id: str) -> QuantComponent:
        for component in self.components:
            if component.component_id == component_id:
                return component
        raise QuantComponentLedgerError(f"unknown component: {component_id}")

    def hypothesis(self, hypothesis_id: str) -> ComponentHypothesis:
        for hypothesis in self.hypotheses:
            if hypothesis.hypothesis_id == hypothesis_id:
                return hypothesis
        raise QuantComponentLedgerError(f"unknown hypothesis: {hypothesis_id}")

    def hypothesis_summary(self, hypothesis_id: str) -> dict[str, object]:
        hypothesis = self.hypothesis(hypothesis_id)
        trials = [
            trial for trial in self.trials if trial.hypothesis_id == hypothesis_id
        ]
        activated = [
            trial
            for trial in trials
            if set(hypothesis.component_ids) <= set(trial.activated_components)
        ]

        by_role: dict[str, dict[str, int]] = {}
        for role in ComponentTrialRole:
            source = trials if role is ComponentTrialRole.ABLATION else activated
            role_trials = [trial for trial in source if trial.role is role]
            by_role[role.value] = {
                "trials": len(role_trials),
                "successes": sum(trial.succeeded for trial in role_trials),
            }

        target = by_role[ComponentTrialRole.TARGET.value]
        repeat = by_role[ComponentTrialRole.REPEAT.value]
        protection = by_role[ComponentTrialRole.PROTECTION.value]
        transfer = by_role[ComponentTrialRole.TRANSFER.value]
        measured = [
            trial for trial in activated if trial.official_reward is not None
        ]

        if not trials:
            stability = ComponentStability.UNTESTED
        elif not activated:
            stability = ComponentStability.NOT_ACTIVATED
        elif not measured:
            stability = ComponentStability.UNTESTED
        elif target["successes"] == 0:
            stability = ComponentStability.UNSUPPORTED
        elif target["successes"] < target["trials"]:
            stability = ComponentStability.MIXED
        elif repeat["trials"] and repeat["successes"] < repeat["trials"]:
            stability = ComponentStability.MIXED
        elif protection["trials"] and protection["successes"] < protection["trials"]:
            stability = ComponentStability.MIXED
        elif transfer["trials"] and transfer["successes"] < transfer["trials"]:
            stability = ComponentStability.MIXED
        elif transfer["successes"] and protection["successes"] and repeat["successes"]:
            stability = ComponentStability.TRANSFERABLE
        elif protection["successes"] and repeat["successes"]:
            stability = ComponentStability.PROTECTED
        elif repeat["successes"]:
            stability = ComponentStability.REPLICATED
        elif target["successes"]:
            stability = ComponentStability.PROVISIONAL
        else:
            stability = ComponentStability.MIXED

        next_actions = _next_actions(
            stability=stability,
            is_composition=len(hypothesis.component_ids) > 1,
            has_ablation=by_role[ComponentTrialRole.ABLATION.value]["trials"] > 0,
        )
        return {
            "hypothesis_id": hypothesis.hypothesis_id,
            "component_ids": list(hypothesis.component_ids),
            "evidence_gap": hypothesis.evidence_gap,
            "expected_worker_change": hypothesis.expected_worker_change,
            "target_task_ids": list(hypothesis.target_task_ids),
            "protection_task_ids": list(hypothesis.protection_task_ids),
            "stability": stability.value,
            "trial_count": len(trials),
            "fully_activated_trial_count": len(activated),
            "evidence_by_role": by_role,
            "next_actions": next_actions,
            "claim_boundary": _claim_boundary(hypothesis, stability, by_role),
        }

    def component_summary(self, component_id: str) -> dict[str, object]:
        self.component(component_id)
        relevant = [
            trial
            for trial in self.trials
            if component_id in trial.available_components
            or component_id in trial.selected_components
            or component_id in trial.activated_components
        ]
        standalone = [
            trial
            for trial in relevant
            if self.hypothesis(trial.hypothesis_id).component_ids == (component_id,)
        ]
        return {
            "component_id": component_id,
            "available_trial_count": sum(
                component_id in trial.available_components for trial in relevant
            ),
            "selected_trial_count": sum(
                component_id in trial.selected_components for trial in relevant
            ),
            "activated_trial_count": sum(
                component_id in trial.activated_components for trial in relevant
            ),
            "standalone_trial_count": len(standalone),
            "composition_trial_count": len(relevant) - len(standalone),
            "hypothesis_ids": [
                hypothesis.hypothesis_id
                for hypothesis in self.hypotheses
                if component_id in hypothesis.component_ids
            ],
        }

    def experiment_totals(self) -> dict[str, int | float]:
        return {
            "trial_count": len(self.trials),
            "requests": sum(trial.requests for trial in self.trials),
            "tokens": sum(trial.tokens for trial in self.trials),
            "cost_usd": sum(trial.cost_usd for trial in self.trials),
        }

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "scope": self.scope,
            "components": [
                {
                    "component_id": component.component_id,
                    "origin": component.origin.value,
                    "capabilities": list(component.capabilities),
                    "description": component.description,
                    "evidence": self.component_summary(component.component_id),
                }
                for component in self.components
            ],
            "hypotheses": [
                self.hypothesis_summary(hypothesis.hypothesis_id)
                for hypothesis in self.hypotheses
            ],
            "experiment_totals": self.experiment_totals(),
            "notes": list(self.notes),
        }


def _next_actions(
    *, stability: ComponentStability, is_composition: bool, has_ablation: bool
) -> list[str]:
    if stability is ComponentStability.UNTESTED:
        return ["RUN_TARGET"]
    if stability is ComponentStability.NOT_ACTIVATED:
        return ["REFINE_ACTIVATION", "ABSTAIN"]
    if stability in {ComponentStability.UNSUPPORTED, ComponentStability.MIXED}:
        if is_composition:
            return ["ROUTE", "REFINE", "ABSTAIN"]
        return ["REFINE", "ABSTAIN"]
    if stability is ComponentStability.PROVISIONAL:
        return ["REPLICATE"]
    if stability is ComponentStability.REPLICATED:
        return ["PROTECT"]
    if stability is ComponentStability.PROTECTED:
        actions = []
        if is_composition and not has_ablation:
            actions.append("ABLATE")
        actions.append("TRANSFER")
        return actions
    if is_composition and not has_ablation:
        return ["ABLATE", "ROUTE"]
    return ["ROUTE"]


def _claim_boundary(
    hypothesis: ComponentHypothesis,
    stability: ComponentStability,
    by_role: Mapping[str, Mapping[str, int]],
) -> str:
    if stability is ComponentStability.UNTESTED:
        return "The component hypothesis has not reached a Worker trial."
    if stability is ComponentStability.NOT_ACTIVATED:
        return "The component was not fully activated, so its task effect is unknown."
    if stability is ComponentStability.MIXED and (
        by_role["target"]["trials"]
        and by_role["target"]["successes"] == by_role["target"]["trials"]
        and by_role["transfer"]["trials"] > by_role["transfer"]["successes"]
    ):
        return (
            "The target result repeated and passed protection, but the measured "
            "cross-task transfer failed."
        )
    if stability in {ComponentStability.UNSUPPORTED, ComponentStability.MIXED}:
        return "Observed trials do not support a stable target improvement."
    if stability is ComponentStability.PROVISIONAL:
        return "One target success is provisional until an independent repeat."
    if stability is ComponentStability.REPLICATED:
        return "The target result repeated, but protection and transfer remain untested."
    if stability is ComponentStability.PROTECTED:
        if len(hypothesis.component_ids) > 1 and not by_role["ablation"]["trials"]:
            return (
                "The composition repeated and protected a solved task; individual "
                "component necessity and transfer remain untested."
            )
        return "The result repeated and passed protection; transfer remains untested."
    return "The hypothesis transferred at least once; broader reliability remains untested."


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuantComponentLedgerError(f"{field} must be non-empty text")
    return value.strip()


def _text_tuple(value: object, *, field: str, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise QuantComponentLedgerError(f"{field} must be a list of text values")
    normalized = tuple(item.strip() for item in value)
    if not allow_empty and not normalized:
        raise QuantComponentLedgerError(f"{field} must not be empty")
    if len(normalized) != len(set(normalized)):
        raise QuantComponentLedgerError(f"{field} contains duplicates")
    return normalized


def load_quantcodeeval_component_ledger(
    path: str | Path,
) -> QuantComponentLedger:
    """Load a human-readable component ledger without creating new identities."""

    source = Path(path).expanduser().resolve()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuantComponentLedgerError(f"cannot read component ledger: {source}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise QuantComponentLedgerError("component ledger schema is unsupported")

    components = tuple(
        QuantComponent(
            component_id=_text(row.get("component_id"), field="component_id"),
            origin=ComponentOrigin(row.get("origin")),
            capabilities=_text_tuple(row.get("capabilities"), field="capabilities"),
            description=_text(row.get("description"), field="description"),
        )
        for row in _object_rows(payload.get("components"), field="components")
    )
    component_ids = {component.component_id for component in components}
    if len(component_ids) != len(components):
        raise QuantComponentLedgerError("component IDs must be unique")

    hypotheses = tuple(
        ComponentHypothesis(
            hypothesis_id=_text(row.get("hypothesis_id"), field="hypothesis_id"),
            component_ids=_text_tuple(row.get("component_ids"), field="component_ids"),
            evidence_gap=_text(row.get("evidence_gap"), field="evidence_gap"),
            expected_worker_change=_text(
                row.get("expected_worker_change"), field="expected_worker_change"
            ),
            target_task_ids=_text_tuple(
                row.get("target_task_ids"), field="target_task_ids"
            ),
            protection_task_ids=_text_tuple(
                row.get("protection_task_ids", []),
                field="protection_task_ids",
                allow_empty=True,
            ),
        )
        for row in _object_rows(payload.get("hypotheses"), field="hypotheses")
    )
    hypothesis_ids = {hypothesis.hypothesis_id for hypothesis in hypotheses}
    if len(hypothesis_ids) != len(hypotheses):
        raise QuantComponentLedgerError("hypothesis IDs must be unique")
    for hypothesis in hypotheses:
        if not set(hypothesis.component_ids) <= component_ids:
            raise QuantComponentLedgerError(
                f"hypothesis references an unknown component: {hypothesis.hypothesis_id}"
            )

    trials = tuple(
        _parse_trial(row) for row in _object_rows(payload.get("trials"), field="trials")
    )
    run_ids = {trial.run_id for trial in trials}
    if len(run_ids) != len(trials):
        raise QuantComponentLedgerError("trial run IDs must be unique")
    hypothesis_by_id = {
        hypothesis.hypothesis_id: hypothesis for hypothesis in hypotheses
    }
    for trial in trials:
        hypothesis = hypothesis_by_id.get(trial.hypothesis_id)
        if hypothesis is None:
            raise QuantComponentLedgerError(
                f"trial references an unknown hypothesis: {trial.run_id}"
            )
        if not set(trial.available_components) <= component_ids:
            raise QuantComponentLedgerError(
                f"trial references an unknown available component: {trial.run_id}"
            )
        if not set(trial.activated_components) <= set(trial.selected_components) <= set(
            trial.available_components
        ):
            raise QuantComponentLedgerError(
                f"trial activation is not a subset of selection and availability: {trial.run_id}"
            )
        hypothesis_components = set(hypothesis.component_ids)
        removed = set(trial.removed_components)
        selected = set(trial.selected_components)
        if trial.role is ComponentTrialRole.ABLATION:
            if not removed or not removed < hypothesis_components:
                raise QuantComponentLedgerError(
                    f"ablation must remove part of its hypothesis: {trial.run_id}"
                )
            if removed & selected or not hypothesis_components - removed <= selected:
                raise QuantComponentLedgerError(
                    f"ablation selection differs from its declared removal: {trial.run_id}"
                )
        elif removed or not hypothesis_components <= selected:
            raise QuantComponentLedgerError(
                f"trial did not select its complete hypothesis: {trial.run_id}"
            )
        if trial.role in {ComponentTrialRole.TARGET, ComponentTrialRole.REPEAT} and (
            trial.task_id not in hypothesis.target_task_ids
        ):
            raise QuantComponentLedgerError(
                f"target trial task differs from its hypothesis: {trial.run_id}"
            )
        if trial.role is ComponentTrialRole.PROTECTION and (
            trial.task_id not in hypothesis.protection_task_ids
        ):
            raise QuantComponentLedgerError(
                f"protection trial task differs from its hypothesis: {trial.run_id}"
            )
        if trial.role is ComponentTrialRole.ABLATION and trial.task_id not in (
            set(hypothesis.target_task_ids) | set(hypothesis.protection_task_ids)
        ):
            raise QuantComponentLedgerError(
                f"ablation trial task differs from its hypothesis: {trial.run_id}"
            )

    notes = _text_tuple(payload.get("notes", []), field="notes", allow_empty=True)
    return QuantComponentLedger(
        scope=_text(payload.get("scope"), field="scope"),
        components=components,
        hypotheses=hypotheses,
        trials=trials,
        notes=notes,
    )


def _object_rows(value: object, *, field: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise QuantComponentLedgerError(f"{field} must be a list of objects")
    return value


def _parse_trial(row: Mapping[str, object]) -> ComponentTrial:
    reward = row.get("official_reward")
    if reward is not None and (
        isinstance(reward, bool) or reward not in {0, 0.0, 1, 1.0}
    ):
        raise QuantComponentLedgerError("official_reward must be binary or null")
    passed = row.get("properties_passed")
    total = row.get("properties_total")
    if (passed is None) != (total is None) or (
        passed is not None
        and (
            type(passed) is not int
            or type(total) is not int
            or passed < 0
            or total < 1
            or passed > total
        )
    ):
        raise QuantComponentLedgerError("property progress is invalid")
    requests = row.get("requests", 0)
    tokens = row.get("tokens", 0)
    cost = row.get("cost_usd", 0.0)
    if type(requests) is not int or requests < 0 or type(tokens) is not int or tokens < 0:
        raise QuantComponentLedgerError("trial request and token counts must be non-negative")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0:
        raise QuantComponentLedgerError("trial cost must be non-negative")
    return ComponentTrial(
        run_id=_text(row.get("run_id"), field="run_id"),
        hypothesis_id=_text(row.get("hypothesis_id"), field="hypothesis_id"),
        task_id=_text(row.get("task_id"), field="task_id"),
        role=ComponentTrialRole(row.get("role")),
        available_components=_text_tuple(
            row.get("available_components"), field="available_components"
        ),
        selected_components=_text_tuple(
            row.get("selected_components"), field="selected_components"
        ),
        activated_components=_text_tuple(
            row.get("activated_components", []),
            field="activated_components",
            allow_empty=True,
        ),
        official_reward=None if reward is None else float(reward),
        properties_passed=passed,
        properties_total=total,
        requests=requests,
        tokens=tokens,
        cost_usd=float(cost),
        observation=_text(row.get("observation"), field="observation"),
        removed_components=_text_tuple(
            row.get("removed_components", []),
            field="removed_components",
            allow_empty=True,
        ),
    )


__all__ = [
    "ComponentHypothesis",
    "ComponentOrigin",
    "ComponentStability",
    "ComponentTrial",
    "ComponentTrialRole",
    "QuantComponent",
    "QuantComponentLedger",
    "QuantComponentLedgerError",
    "load_quantcodeeval_component_ledger",
]
