import json
from pathlib import Path

import qea.quantcodeeval_diagnostic_refinement as refinement_module


def _decision():
    return {
        "experiment_spec": {
            "mode": "repair",
            "seed_experience": "run_local_h0",
            "worker_instruction": "Use the diagnostic and repair the public artifact.",
            "max_iterations": 6,
            "prediction": "The refined residual will localize the mismatch.",
            "decision_changing_observation": "If unused, revise the component.",
        }
    }


def _inputs(tmp_path: Path):
    release = tmp_path / "release"
    (release / "public").mkdir(parents=True)
    (release / "trusted").mkdir()
    component = tmp_path / "component"
    component.mkdir()
    (component / "systemprompt.md").write_text("Use quant diagnostic.\n")
    seed = tmp_path / "seed.py"
    seed.write_text("VALUE = 1\n")
    prior = tmp_path / "prior.json"
    prior.write_text(
        json.dumps({"score": {"tests_passed": 12, "reward": 0}})
    )
    diagnostic = tmp_path / "diagnostic.json"
    diagnostic.write_text(
        json.dumps(
            {
                "task_id": "T26",
                "feedback_mode": "answer_rich_evolver",
                "worker_visible": False,
            }
        )
    )
    return release, component, seed, prior, diagnostic


def _kwargs(tmp_path: Path):
    release, component, seed, prior, diagnostic = _inputs(tmp_path)
    return {
        "config_path": tmp_path / "config.json",
        "release_dir": release,
        "run_dir": tmp_path / "run",
        "component_source": component,
        "seed_strategy": seed,
        "prior_probe_result_path": prior,
        "optimization_diagnostic_path": diagnostic,
        "evolver_image_ref": "evolver",
        "worker_image_ref": "worker",
        "verifier_image_ref": "verifier",
        "proxy_image_ref": "proxy",
        "task_panel_path": tmp_path / "panel.json",
    }


def test_refinement_routes_answers_only_to_evolver_and_runs_blind_probe(
    tmp_path, monkeypatch
):
    kwargs = _kwargs(tmp_path)
    activation_calls = []
    probe_calls = []

    def fake_activation(**call):
        activation_calls.append(call)
        candidate = Path(call["run_dir"]) / "evolutions/iteration-0001/candidate"
        candidate.mkdir(parents=True)
        return {
            "status": "PASS",
            "decision": _decision(),
            "proxy_audit": {"provider_cost_usd": 0.02},
        }

    def fake_probe(**call):
        probe_calls.append(call)
        artifact = tmp_path / "probe-output.py"
        artifact.write_text("VALUE = 2\n")
        return {
            "score": {"tests_passed": 14, "reward": 0},
            "artifact": str(artifact),
            "cost": {"provider_cost_usd": 0.01},
        }

    monkeypatch.setattr(
        refinement_module, "run_quantcodeeval_v2_activation_canary", fake_activation
    )
    monkeypatch.setattr(refinement_module, "run_probe_arm", fake_probe)

    result = refinement_module.run_quantcodeeval_diagnostic_refinement(**kwargs)

    assert activation_calls[0]["optimization_diagnostic_path"] == (
        kwargs["optimization_diagnostic_path"]
    )
    assert activation_calls[0]["worker_artifact_sources"] == {
        "run_local_h0": kwargs["seed_strategy"]
    }
    assert "optimization_diagnostic" not in probe_calls[0]
    assert probe_calls[0]["seed_strategy"] == kwargs["seed_strategy"]
    assert result["status"] == "property_gain"
    assert result["property_delta"] == 2
    assert result["artifact_changed"] is True
    assert result["cost_usd"] == 0.03


def test_refinement_calibrated_abstain_does_not_run_worker(tmp_path, monkeypatch):
    kwargs = _kwargs(tmp_path)
    monkeypatch.setattr(
        refinement_module,
        "run_quantcodeeval_v2_activation_canary",
        lambda **call: {
            "status": "CALIBRATED_ABSTAIN",
            "decision": {"decision": "ABSTAIN"},
            "proxy_audit": {"provider_cost_usd": 0.02},
        },
    )
    monkeypatch.setattr(
        refinement_module,
        "run_probe_arm",
        lambda **call: (_ for _ in ()).throw(AssertionError("Worker must not run")),
    )

    result = refinement_module.run_quantcodeeval_diagnostic_refinement(**kwargs)

    assert result["status"] == "calibrated_abstain"
    assert result["worker_probe_run"] is False
