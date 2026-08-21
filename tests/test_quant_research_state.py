from __future__ import annotations

import pytest

from qea.evolve_agent_full.quant_research_state import (
    QuantResearchStateCardError,
    normalize_quant_research_state_card,
    quant_research_intervention_verdict,
    retrieve_quant_research_episodes,
    validate_quant_research_state_card,
)


def _state_card() -> dict[str, object]:
    return {
        "task_key": " qfbench:curve-example ",
        "research_mandate": {
            "economic_object": "discount curve",
            "decision_or_as_of_time": "N-A",
            "task_local_note": "keep this open field",
        },
        "information_state": {"calendar_and_universe": "UNKNOWN"},
        "candidate_relations": (
            {
                "relation_id": " repricing-residual ",
                "applicability": "public task asks instruments to reprice",
                "observed_evidence": ("trajectory/worker.jsonl",),
                "status": "fail",
                "relation_local_note": {"tolerance_source": "public task"},
            },
        ),
        "selected_intervention": {
            "relation_id": "repricing-residual",
            "state_locus": "economic_reconciliation",
            "component_locus": "tools",
            "predicted_transition": "residual closes on a fresh Worker",
            "discriminating_observation": "replay public instruments",
        },
        "open_extension": {"confidence": "UNKNOWN"},
    }


def test_normalizes_open_card_and_preserves_na_unknown():
    card = normalize_quant_research_state_card(_state_card(), action="ACT")

    assert card["schema_version"] == 1
    assert card["task_key"] == "qfbench:curve-example"
    assert isinstance(card["candidate_relations"], list)
    assert card["candidate_relations"][0]["status"] == "FAIL"
    assert card["research_mandate"]["decision_or_as_of_time"] == "N-A"
    assert card["information_state"]["calendar_and_universe"] == "UNKNOWN"
    assert card["open_extension"] == {"confidence": "UNKNOWN"}
    assert card["candidate_relations"][0]["relation_local_note"] == {
        "tolerance_source": "public task"
    }


def test_validate_can_select_relation_outside_card_for_terminal_act():
    raw = _state_card()
    raw["selected_intervention"].pop("relation_id")

    card = validate_quant_research_state_card(
        raw,
        action="ACT",
        selected_relation_id="repricing-residual",
    )

    assert card["candidate_relations"][0]["relation_id"] == "repricing-residual"


@pytest.mark.parametrize("task_key", [None, "", "UNKNOWN", "N-A"])
def test_rejects_missing_task(task_key):
    raw = _state_card()
    raw["task_key"] = task_key

    with pytest.raises(QuantResearchStateCardError, match="task_key"):
        validate_quant_research_state_card(raw)


def test_rejects_card_without_candidate_relation():
    raw = _state_card()
    raw["candidate_relations"] = []

    with pytest.raises(QuantResearchStateCardError, match="candidate relation"):
        validate_quant_research_state_card(raw)


def test_act_rejects_selected_relation_without_support():
    raw = _state_card()
    raw["candidate_relations"][0]["applicability"] = "UNKNOWN"
    raw["candidate_relations"][0]["observed_evidence"] = []

    with pytest.raises(QuantResearchStateCardError, match="no support"):
        validate_quant_research_state_card(raw, action="ACT")


def test_act_rejects_missing_component_locus():
    raw = _state_card()
    raw["selected_intervention"].pop("component_locus")

    with pytest.raises(QuantResearchStateCardError, match="component locus"):
        validate_quant_research_state_card(raw, action="ACT")


def test_state_coordinates_retrieve_one_episode_per_outcome():
    catalog = {
        "components": [
            {
                "component_id": f"curve-audit-{outcome}-{ordinal}",
                "description": "Reconcile a calibrated curve with repriced instruments",
                "capabilities": ["curve repricing residual"],
                "state_locus": "economic_reconciliation",
                "relation_family": "repricing-residual",
                "component_locus": "tools",
                "task_mechanism": "public instruments must reprice",
                "observed_trials": [
                    {
                        "task_id": f"curve-{outcome}-{ordinal}",
                        "outcome_class": outcome,
                        "activated": outcome != "inactive",
                        "official_reward": 1 if outcome == "positive" else 0,
                        "observation": f"{outcome} repricing observation",
                    }
                ],
            }
            for outcome in ("positive", "negative", "inactive", "unstable")
            for ordinal in (1, 2)
        ]
    }

    result = retrieve_quant_research_episodes(_state_card(), catalog)

    assert result["query"]["state_locus"] == "economic_reconciliation"
    assert result["query"]["relation_family"] == "repricing-residual"
    assert [row["outcome_class"] for row in result["episodes"]] == [
        "positive",
        "negative",
        "inactive",
        "unstable",
    ]


def test_state_retrieval_uses_open_coordinates_not_unrelated_catalog_order():
    catalog = {
        "components": [
            {
                "component_id": "unrelated-finalizer",
                "description": "finish a spreadsheet artifact",
                "observed_trials": [
                    {
                        "task_id": "artifact-task",
                        "outcome_class": "positive",
                        "activated": True,
                        "official_reward": 1,
                        "observation": "artifact delivered",
                    }
                ],
            },
            {
                "component_id": "repricing-audit",
                "description": "curve repricing residual",
                "relation_family": "repricing-residual",
                "component_locus": "tools",
                "observed_trials": [
                    {
                        "task_id": "curve-task",
                        "outcome_class": "positive",
                        "activated": True,
                        "official_reward": 1,
                        "observation": "public instruments reprice",
                    }
                ],
            },
        ]
    }

    result = retrieve_quant_research_episodes(_state_card(), catalog)

    assert [row["component_id"] for row in result["episodes"]] == [
        "repricing-audit"
    ]


@pytest.mark.parametrize(
    ("observations", "expected"),
    [
        ({"activated": False}, "INACTIVE"),
        ({"activated": True}, "MISLOCALIZED"),
        (
            {
                "activated": True,
                "official_target_improved": True,
            },
            "UNRESOLVED",
        ),
        (
            {
                "activated": True,
                "predicted_relation_changed": True,
            },
            "STATE_CORRECTING",
        ),
        (
            {
                "activated": True,
                "predicted_relation_changed": True,
                "official_target_improved": True,
            },
            "TASK_HELPFUL",
        ),
        (
            {
                "activated": True,
                "predicted_relation_changed": True,
                "official_target_improved": True,
                "repeated_gain": True,
                "protection_safe": True,
            },
            "STABLE_OR_REUSABLE",
        ),
    ],
)
def test_intervention_verdict_separates_activation_state_gain_and_stability(
    observations, expected
):
    defaults = {
        "activated": False,
        "predicted_relation_changed": False,
        "official_target_improved": False,
    }
    defaults.update(observations)

    assert quant_research_intervention_verdict(**defaults) == expected


def test_protection_regression_does_not_claim_stability():
    assert quant_research_intervention_verdict(
        activated=True,
        predicted_relation_changed=True,
        official_target_improved=True,
        repeated_gain=True,
        protection_safe=False,
    ) == "TASK_HELPFUL"
