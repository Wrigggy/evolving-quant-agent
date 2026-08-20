import json
from pathlib import Path

import qea.quantcodeeval_component_impact as impact_module


def _decision():
    return {
        "experiment_spec": {
            "mode": "repair",
            "seed_experience": "run_local_h0",
            "worker_instruction": (
                "Run a component-impact experiment, call the new audit early, "
                "revise the artifact, re-check it, and save strategy.py."
            ),
            "max_iterations": 8,
            "prediction": "The audit activates and changes the artifact.",
            "decision_changing_observation": "No call means revise activation.",
        }
    }


def _kwargs(tmp_path: Path):
    release = tmp_path / "release"
    (release / "public").mkdir(parents=True)
    (release / "trusted").mkdir()
    component = tmp_path / "component"
    component.mkdir()
    (component / "systemprompt.md").write_text("Use the component.\n")
    seed = tmp_path / "seed.py"
    seed.write_text("VALUE = 1\n")
    evolution = tmp_path / "evolution.json"
    evolution.write_text('{"status":"PASS"}\n')
    probes = []
    for index in range(2):
        probe = tmp_path / f"probe-{index}.json"
        probe.write_text(json.dumps({"score": {"tests_passed": 12, "reward": 0}}))
        probes.append(probe)
    return {
        "config_path": tmp_path / "config.json",
        "release_dir": release,
        "run_dir": tmp_path / "run",
        "component_source": component,
        "seed_strategy": seed,
        "prior_evolution_result_path": evolution,
        "prior_probe_result_paths": probes,
        "evolver_image_ref": "evolver",
        "worker_image_ref": "worker",
        "verifier_image_ref": "verifier",
        "proxy_image_ref": "proxy",
        "task_panel_path": tmp_path / "panel.json",
    }


def test_runs_evolver_directed_component_impact_and_scores_artifact(
    tmp_path, monkeypatch
):
    kwargs = _kwargs(tmp_path)
    evolution_calls = []
    probe_calls = []

    def fake_evolution(**call):
        evolution_calls.append(call)
        candidate = Path(call["run_dir"]) / "evolutions/iteration-0001/candidate"
        candidate.mkdir(parents=True)
        return {
            "status": "PASS",
            "decision": _decision(),
            "proxy_audit": {"provider_cost_usd": 0.02},
        }

    def fake_probe(**call):
        probe_calls.append(call)
        artifact = tmp_path / "artifact.py"
        artifact.write_text("VALUE = 2\n")
        return {
            "score": {"tests_passed": 15, "reward": 0},
            "artifact": str(artifact),
            "tool_usage": {
                "counts": {"run_shell_command": 2, "check_quant_relations": 2}
            },
            "cost": {"provider_cost_usd": "0.01"},
        }

    monkeypatch.setattr(
        impact_module, "run_quantcodeeval_v2_activation_canary", fake_evolution
    )
    monkeypatch.setattr(impact_module, "run_probe_arm", fake_probe)

    result = impact_module.run_quantcodeeval_component_impact(**kwargs)

    observations = evolution_calls[0]["experiment_observation_sources"]
    assert sorted(observations) == [
        "prior_component_design",
        "zero_activation_probe_1",
        "zero_activation_probe_2",
    ]
    assert "component-impact experiment" in evolution_calls[0]["diagnosis_note"]
    assert probe_calls[0]["worker_instruction"].startswith(
        "Run a component-impact experiment"
    )
    assert result["status"] == "property_gain"
    assert result["component_calls"] == {"check_quant_relations": 2}
    assert result["artifact_changed"] is True
    assert result["property_delta"] == 3
    assert result["cost_usd"] == 0.03


def test_preflight_stops_before_worker(tmp_path, monkeypatch):
    kwargs = _kwargs(tmp_path)
    monkeypatch.setattr(
        impact_module,
        "run_quantcodeeval_v2_activation_canary",
        lambda **call: {"status": "preflight_complete"},
    )
    monkeypatch.setattr(
        impact_module,
        "run_probe_arm",
        lambda **call: (_ for _ in ()).throw(AssertionError("Worker must not run")),
    )

    result = impact_module.run_quantcodeeval_component_impact(
        **kwargs, preflight_only=True
    )

    assert result["status"] == "preflight_complete"
    assert result["baseline_tests_passed"] == 12


def test_prompt_only_candidate_uses_worker_probe_as_activation_test(
    tmp_path, monkeypatch
):
    kwargs = _kwargs(tmp_path)

    def fake_evolution(**call):
        candidate = Path(call["run_dir"]) / "evolutions/iteration-0001/candidate"
        candidate.mkdir(parents=True)
        decision = _decision()
        decision.update({"decision": "ACT", "primary_components": ["systemprompt"]})
        return {
            "status": "FAIL",
            "decision": decision,
            "activation": {
                "status": "failed",
                "executable_primary_components": [],
            },
            "component_tests": [
                {
                    "kind": "independent_full_harness_admission",
                    "status": "passed",
                }
            ],
            "proxy_audit": {"provider_cost_usd": 0.02},
        }

    artifact = tmp_path / "artifact.py"
    artifact.write_text("VALUE = 2\n")
    monkeypatch.setattr(
        impact_module, "run_quantcodeeval_v2_activation_canary", fake_evolution
    )
    monkeypatch.setattr(
        impact_module,
        "run_probe_arm",
        lambda **call: {
            "score": {"tests_passed": 12, "reward": 0},
            "artifact": str(artifact),
            "tool_usage": {"counts": {"check_quant_relations": 1}},
        },
    )

    result = impact_module.run_quantcodeeval_component_impact(**kwargs)

    assert result["status"] == "artifact_changed_no_score_gain"
    assert result["component_called"] is True
