import pytest

from qea.quantcodeeval_ap3 import (
    QuantCodeEvalAP3Error,
    ap3_round_one_prediction_record,
    require_ap3_from_scratch,
)


def _decision(mode="from_scratch", seed=None):
    return {
        "experiment_spec": {
            "mode": mode,
            "seed_experience": seed,
            "worker_instruction": "Solve the public task and test the artifact.",
            "max_iterations": 8,
            "prediction": "The selected component will change the observation.",
            "decision_changing_observation": "If unused, revise or roll back.",
        }
    }


def test_ap3_accepts_only_from_scratch_experiment():
    spec = require_ap3_from_scratch(_decision())
    assert spec.mode == "from_scratch"
    assert spec.seed_experience is None


def test_ap3_rejects_repair_seed():
    with pytest.raises(QuantCodeEvalAP3Error, match="without an artifact seed"):
        require_ap3_from_scratch(_decision("repair", "historical_t26"))


def test_ap3_persists_round_one_prediction_for_round_two():
    decision = _decision()
    decision["selected_hypothesis_id"] = "artifact_completion"
    decision["research_state_transition"] = {
        "state_id": "research_artifact_completion"
    }
    spec = require_ap3_from_scratch(decision)
    record = ap3_round_one_prediction_record(decision, spec)
    assert record["prediction"] == spec.prediction
    assert record["decision_changing_observation"] == spec.decision_changing_observation
    assert record["research_state_transition"] == {
        "state_id": "research_artifact_completion"
    }
