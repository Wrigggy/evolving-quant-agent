import json

import pytest

from qea.quantcodeeval_search import (
    QuantCodeEvalSearchError,
    QuantSearchLimits,
    SearchDecision,
    SearchSelection,
    SearchStopReason,
    initialize_quantcodeeval_search,
    load_quantcodeeval_search_state,
    quantcodeeval_search_payload,
    record_quantcodeeval_search_round,
)


H0 = "0" * 64


def _state(**limits):
    return initialize_quantcodeeval_search(
        run_id="qce-v2-search",
        h0_digest=H0,
        h0_official_rewards={"T16": 1.0, "T24": 0.0},
        limits=QuantSearchLimits(**limits),
    )


def _act(state, number, selection, rewards, *, new_information=True):
    return record_quantcodeeval_search_round(
        state,
        decision=SearchDecision.ACT,
        candidate_digest=str(number) * 64,
        history_entry_id=hex(number)[2:] * 64,
        mechanism=f"mechanism-{number}",
        primary_components=("tools",),
        declared_roles=("agent_config", "tool_descriptions", "tools"),
        official_rewards=rewards,
        selection=selection,
        reason="measured candidate outcome",
        new_information=new_information,
        model_requests=2,
        cost_usd=0.01,
    )


def test_variable_length_search_retains_rejections_and_promotes_parents():
    state = _state(max_rounds=12)
    state = _act(
        state,
        1,
        SearchSelection.REJECTED,
        {"T16": 1.0, "T24": 0.0},
    )
    assert state.search_parent_digest == H0
    assert state.rounds[0].candidate_digest == "1" * 64
    assert state.archive[0].selection is SearchSelection.REJECTED

    state = _act(
        state,
        2,
        SearchSelection.DIAGNOSTIC_PROMOTED,
        {"T16": 1.0, "T24": 0.0},
    )
    assert state.search_parent_digest == "2" * 64
    assert state.official_incumbent_digest == H0

    state = _act(
        state,
        3,
        SearchSelection.OFFICIAL_PROMOTED,
        {"T16": 1.0, "T24": 1.0},
    )
    assert state.stopped is True
    assert state.stop_reason is SearchStopReason.TARGET_REACHED
    assert len(state.rounds) == 3
    assert state.official_incumbent_digest == "3" * 64
    assert quantcodeeval_search_payload(state)["protocol"] == (
        "quant_property_v2_full_harness"
    )


def test_research_state_promotion_advances_only_the_search_parent():
    state = _act(
        _state(max_rounds=2),
        1,
        SearchSelection.RESEARCH_STATE_PROMOTED,
        {"T16": 1.0, "T24": 0.0},
    )

    assert state.search_parent_digest == "1" * 64
    assert state.official_incumbent_digest == H0
    assert state.official_rewards == {"T16": 1.0, "T24": 0.0}
    assert state.archive[0].selection is SearchSelection.RESEARCH_STATE_PROMOTED


def test_search_stops_on_repeated_no_information_not_fixed_five_rounds():
    state = _state(max_rounds=20, max_no_information_rounds=2)
    state = _act(
        state,
        1,
        SearchSelection.REJECTED,
        {"T16": 1.0, "T24": 0.0},
        new_information=False,
    )
    state = _act(
        state,
        2,
        SearchSelection.REJECTED,
        {"T16": 1.0, "T24": 0.0},
        new_information=False,
    )
    assert len(state.rounds) == 2
    assert state.stop_reason is SearchStopReason.NO_NEW_INFORMATION


def test_search_allows_calibrated_abstain_then_stops_on_repetition():
    state = _state(max_consecutive_abstain=2)
    for _ in range(2):
        state = record_quantcodeeval_search_round(
            state,
            decision="ABSTAIN",
            official_rewards={"T16": 1.0, "T24": 0.0},
            selection="abstained",
            reason="evidence cannot distinguish two causes",
            new_information=True,
        )
    assert state.stop_reason is SearchStopReason.TERMINAL_ABSTAIN


def test_search_rejects_false_official_promotion_and_post_stop_append():
    state = _state(max_rounds=1)
    with pytest.raises(QuantCodeEvalSearchError, match="Pareto"):
        _act(
            state,
            1,
            SearchSelection.OFFICIAL_PROMOTED,
            {"T16": 1.0, "T24": 0.0},
        )
    stopped = _act(
        state,
        1,
        SearchSelection.REJECTED,
        {"T16": 1.0, "T24": 0.0},
    )
    assert stopped.stop_reason is SearchStopReason.BUDGET_EXHAUSTED
    with pytest.raises(QuantCodeEvalSearchError, match="stopped"):
        _act(
            stopped,
            2,
            SearchSelection.REJECTED,
            {"T16": 1.0, "T24": 0.0},
        )


def test_search_checkpoint_round_trips_and_rejects_tamper(tmp_path):
    state = _act(
        _state(max_rounds=12),
        1,
        SearchSelection.RESEARCH_STATE_PROMOTED,
        {"T16": 1.0, "T24": 0.0},
    )
    path = tmp_path / "SEARCH-STATE.json"
    path.write_text(
        json.dumps(quantcodeeval_search_payload(state), sort_keys=True),
        encoding="utf-8",
    )

    assert load_quantcodeeval_search_state(path) == state

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["search_parent_digest"] = "9" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(QuantCodeEvalSearchError, match="digest differs"):
        load_quantcodeeval_search_state(path)
