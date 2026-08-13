import json
from pathlib import Path

import pytest

from qea.quantcodeeval_components import (
    QuantComponentLedgerError,
    load_quantcodeeval_component_ledger,
)


LEDGER = (
    Path(__file__).resolve().parents[1]
    / "data/quantcodeeval/COMPONENT_EVIDENCE_CANARY.json"
)


def test_canary_ledger_keeps_failed_component_and_replicated_composition_distinct():
    ledger = load_quantcodeeval_component_ledger(LEDGER)

    initial = ledger.hypothesis_summary(
        "independent_invariant_without_semantic_binding"
    )
    repaired = ledger.hypothesis_summary("public_semantic_bound_invariant")

    assert initial["stability"] == "unsupported"
    assert initial["evidence_by_role"]["target"] == {
        "trials": 1,
        "successes": 0,
    }
    assert initial["next_actions"] == ["REFINE", "ABSTAIN"]

    assert repaired["stability"] == "mixed"
    assert repaired["fully_activated_trial_count"] == 4
    assert repaired["evidence_by_role"]["target"]["successes"] == 1
    assert repaired["evidence_by_role"]["repeat"]["successes"] == 1
    assert repaired["evidence_by_role"]["protection"]["successes"] == 1
    assert repaired["evidence_by_role"]["transfer"] == {
        "trials": 1,
        "successes": 0,
    }
    assert repaired["next_actions"] == ["ROUTE", "REFINE", "ABSTAIN"]
    assert "cross-task transfer failed" in repaired["claim_boundary"]


def test_semantic_binding_is_not_mislabeled_as_a_standalone_success():
    ledger = load_quantcodeeval_component_ledger(LEDGER)

    semantic = ledger.component_summary("public_quantity_semantic_binding")
    invariant = ledger.component_summary("declarative_quant_invariant")

    assert semantic == {
        "component_id": "public_quantity_semantic_binding",
        "available_trial_count": 4,
        "selected_trial_count": 4,
        "activated_trial_count": 4,
        "standalone_trial_count": 0,
        "composition_trial_count": 4,
        "hypothesis_ids": ["public_semantic_bound_invariant"],
    }
    assert invariant["standalone_trial_count"] == 1
    assert invariant["composition_trial_count"] == 4

    boundary = ledger.hypothesis_summary(
        "explicit_warmup_boundary_arbitration"
    )
    assert boundary["stability"] == "unsupported"
    assert boundary["fully_activated_trial_count"] == 1
    assert boundary["evidence_by_role"]["target"] == {
        "trials": 1,
        "successes": 0,
    }
    assert boundary["next_actions"] == ["REFINE", "ABSTAIN"]


def test_canary_ledger_preserves_measured_component_trial_costs():
    ledger = load_quantcodeeval_component_ledger(LEDGER)

    assert ledger.experiment_totals() == {
        "trial_count": 9,
        "requests": 193,
        "tokens": 5314621,
        "cost_usd": pytest.approx(0.2316014456),
    }
    assert any("benchmark estimate" in note for note in ledger.notes)


def test_success_followed_by_failed_repeat_remains_mixed(tmp_path):
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))
    payload["trials"][2]["official_reward"] = 0
    payload["trials"][2]["properties_passed"] = 8
    path = tmp_path / "mixed-ledger.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    ledger = load_quantcodeeval_component_ledger(path)
    repaired = ledger.hypothesis_summary("public_semantic_bound_invariant")

    assert repaired["stability"] == "mixed"
    assert repaired["next_actions"] == ["ROUTE", "REFINE", "ABSTAIN"]


def test_component_ablation_can_remove_one_member_of_a_composition(tmp_path):
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))
    payload["trials"].append(
        {
            "run_id": "t12-semantic-binding-ablation",
            "hypothesis_id": "public_semantic_bound_invariant",
            "task_id": "T12",
            "role": "ablation",
            "available_components": [
                "declarative_quant_invariant",
                "public_quantity_semantic_binding",
            ],
            "selected_components": ["declarative_quant_invariant"],
            "activated_components": ["declarative_quant_invariant"],
            "removed_components": ["public_quantity_semantic_binding"],
            "official_reward": 0,
            "properties_passed": 8,
            "properties_total": 16,
            "requests": 1,
            "tokens": 10,
            "cost_usd": 0.001,
            "observation": "Removing semantic binding reintroduced the T12 error.",
        }
    )
    path = tmp_path / "ablation-ledger.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    ledger = load_quantcodeeval_component_ledger(path)
    repaired = ledger.hypothesis_summary("public_semantic_bound_invariant")

    assert repaired["stability"] == "mixed"
    assert repaired["evidence_by_role"]["ablation"] == {
        "trials": 1,
        "successes": 0,
    }
    assert repaired["next_actions"] == ["ROUTE", "REFINE", "ABSTAIN"]


def test_ledger_requires_activated_components_to_have_been_selected(tmp_path):
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))
    payload["trials"][0]["selected_components"] = []
    path = tmp_path / "invalid-ledger.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(QuantComponentLedgerError, match="must not be empty"):
        load_quantcodeeval_component_ledger(path)
