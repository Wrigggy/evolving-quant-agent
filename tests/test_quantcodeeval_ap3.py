import json
from pathlib import Path

import pytest

import qea.quantcodeeval_ap3 as ap3_module
from qea.quantcodeeval_ap3 import (
    QuantCodeEvalAP3Error,
    ap3_round_one_prediction_record,
    find_ap3_run_local_h0_artifact,
    require_ap3_run_local_probe,
)


def _decision(mode="repair", seed="run_local_h0"):
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


def test_ap3_accepts_only_run_local_h0_activation_probe():
    spec = require_ap3_run_local_probe(_decision())
    assert spec.mode == "repair"
    assert spec.seed_experience == "run_local_h0"


@pytest.mark.parametrize(
    ("mode", "seed"),
    (("repair", "historical_t26"), ("from_scratch", None)),
)
def test_ap3_rejects_non_run_local_probe(mode, seed):
    with pytest.raises(QuantCodeEvalAP3Error, match="run-local H0 artifact"):
        require_ap3_run_local_probe(_decision(mode, seed))


def test_ap3_persists_round_one_prediction_for_round_two():
    decision = _decision()
    decision["selected_hypothesis_id"] = "artifact_completion"
    decision["research_state_transition"] = {
        "state_id": "research_artifact_completion"
    }
    spec = require_ap3_run_local_probe(decision)
    record = ap3_round_one_prediction_record(decision, spec)
    assert record["prediction"] == spec.prediction
    assert record["decision_changing_observation"] == spec.decision_changing_observation
    assert record["research_state_transition"] == {
        "state_id": "research_artifact_completion"
    }


def test_ap3_locates_fresh_run_local_h0_artifact(tmp_path: Path):
    artifact = tmp_path / "attempts/a1/artifacts/strategy.py"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("VALUE = 1\n")
    result = {"attempts": [{"task_id": "T26", "attempt_id": "a1"}]}

    assert find_ap3_run_local_h0_artifact(tmp_path, result) == artifact


def test_ap3_rejects_missing_run_local_h0_artifact(tmp_path: Path):
    result = {"attempts": [{"task_id": "T26", "attempt_id": "a1"}]}

    with pytest.raises(QuantCodeEvalAP3Error, match="produced no T26 artifact"):
        find_ap3_run_local_h0_artifact(tmp_path, result)


def test_ap3_wires_run_local_h0_into_short_probe_and_keeps_final_separate(
    tmp_path: Path, monkeypatch
):
    source_release = tmp_path / "source-release"
    public_task = source_release / "public/tasks/T26"
    (public_task / "environment/data").mkdir(parents=True)
    (public_task / "instruction.md").write_text("# Official T26 contract\n")
    (source_release / "trusted").mkdir()
    quant_h0 = tmp_path / "quant-h0"
    quant_h0.mkdir()
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"token_file": str(tmp_path / "token")}))

    activation_calls = []
    probe_calls = []

    def fake_prepare(**kwargs):
        h0_root = Path(kwargs["run_dir"])
        frozen = h0_root / "workers/H0"
        frozen.mkdir(parents=True)
        return object(), object(), {"status": "preflight_complete"}, frozen

    def fake_h0(**kwargs):
        artifact = (
            Path(kwargs["run_dir"])
            / "attempts/h0-attempt/artifacts/strategy.py"
        )
        artifact.parent.mkdir(parents=True)
        artifact.write_text("VALUE = 'h0'\n")
        return {
            "attempts": [{"task_id": "T26", "attempt_id": "h0-attempt"}],
            "score_summary": {"scores": [{"tests_passed": 12, "reward": 0}]},
            "cost_audit": {"provider_cost_usd": 0},
        }

    def fake_activation(**kwargs):
        activation_calls.append(kwargs)
        if len(activation_calls) == 1:
            candidate = (
                Path(kwargs["run_dir"])
                / "evolutions/iteration-0001/candidate"
            )
            candidate.mkdir(parents=True)
            decision = _decision()
            decision.update(
                {
                    "selected_hypothesis_id": "artifact_audit",
                    "research_state_transition": {
                        "state_id": "evaluation_reconciliation"
                    },
                }
            )
            return {
                "status": "PASS",
                "decision": decision,
                "proxy_audit": {"provider_cost_usd": 0},
            }
        return {
            "status": "ABSTAIN",
            "decision": {
                "evidence_refs": [
                    "guidance/experiment_observations/round1_probe.json"
                ]
            },
            "proxy_audit": {"provider_cost_usd": 0},
        }

    def fake_probe(**kwargs):
        probe_calls.append(kwargs)
        probe_root = Path(kwargs["run_dir"])
        artifact = probe_root / "attempts/probe-attempt/artifacts/strategy.py"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("VALUE = 'probe'\n")
        (probe_root / "PROBE-RESULT.json").write_text("{}\n")
        return {
            "terminal_attempt_id": "probe-attempt",
            "cost": {"provider_cost_usd": 0},
            "score": {"tests_passed": 13, "reward": 0},
        }

    monkeypatch.setattr(ap3_module, "prepare_quantcodeeval_h0", fake_prepare)
    monkeypatch.setattr(ap3_module, "run_quantcodeeval_h0", fake_h0)
    monkeypatch.setattr(
        ap3_module, "run_quantcodeeval_v2_activation_canary", fake_activation
    )
    monkeypatch.setattr(ap3_module, "run_probe_arm", fake_probe)
    monkeypatch.setattr(
        ap3_module,
        "run_quantcodeeval_full_candidate",
        lambda **kwargs: pytest.fail("formal fresh Worker must not run after ABSTAIN"),
    )

    result = ap3_module.run_quantcodeeval_ap3(
        config_path=config,
        source_release_dir=source_release,
        quant_h0_worker_dir=quant_h0,
        run_dir=tmp_path / "run",
        evolver_image_ref="evolver",
        worker_image_ref="worker",
        verifier_image_ref="verifier",
        proxy_image_ref="proxy",
        task_panel_path=tmp_path / "panel.json",
    )

    h0_artifact = (
        tmp_path
        / "run/engineering-release/h0/attempts/h0-attempt/artifacts/strategy.py"
    )
    assert activation_calls[0]["worker_artifact_sources"] == {
        "run_local_h0": h0_artifact
    }
    assert probe_calls[0]["seed_strategy"] == h0_artifact
    assert activation_calls[1]["worker_artifact_sources"] == {
        "run_local_h0": h0_artifact,
        "round1_probe_output": (
            tmp_path
            / "run/worker-probe/attempts/probe-attempt/artifacts/strategy.py"
        ),
    }
    assert result["protocol"] == "quantcodeeval-ap3-v2"
    assert result["probe_kind"] == "run_local_h0_artifact_activation"
    assert result["final"] is None
