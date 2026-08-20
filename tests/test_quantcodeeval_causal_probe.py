import json
from pathlib import Path

import qea.quantcodeeval_causal_probe as causal_module


def test_runs_phase_aware_probe_and_classifies_property_gain(tmp_path, monkeypatch):
    source = tmp_path / "source"
    candidate = source / "evolver/evolutions/iteration-0001/candidate"
    candidate.mkdir(parents=True)
    (candidate / "agent.yaml").write_text("type: agent\n")
    (source / "COMPONENT-IMPACT-RESULT.json").write_text(
        json.dumps({"baseline_tests_passed": 12, "baseline_reward": 0})
    )
    decision = {
        "decision": "ACT",
        "experiment_spec": {
            "mode": "repair",
            "seed_experience": "run_local_h0",
            "worker_instruction": "Audit the retained artifact.",
            "max_iterations": 8,
            "prediction": "The artifact changes.",
            "decision_changing_observation": "No edit changes the mechanism.",
        },
    }
    (source / "evolver/LIVE-RESULT.json").write_text(
        json.dumps({"decision": decision})
    )
    release = tmp_path / "release"
    (release / "h0/workers/H0").mkdir(parents=True)
    (release / "public").mkdir()
    (release / "trusted").mkdir()
    seed = tmp_path / "seed.py"
    seed.write_text("VALUE = 1\n")
    artifact = tmp_path / "artifact.py"
    artifact.write_text("VALUE = 2\n")
    calls = []
    monkeypatch.setattr(causal_module, "admit_candidate", lambda *args: None)

    def fake_probe(**kwargs):
        calls.append(kwargs)
        return {
            "score": {"tests_passed": 13, "reward": 0},
            "artifact": str(artifact),
            "tool_usage": {
                "counts": {"check_quant_relations": 2},
                "first_assistant_turn": {"check_quant_relations": 3},
            },
            "component_observations": {
                "observations": [{"summary": {"errors": 2}}]
            },
            "worker_summary": {"turns": 10},
            "cost": {"provider_cost_usd": "0.02"},
        }

    monkeypatch.setattr(causal_module, "run_probe_arm", fake_probe)
    result = causal_module.run_quantcodeeval_causal_probe(
        config_path=tmp_path / "config.json",
        release_dir=release,
        source_run_dir=source,
        run_dir=tmp_path / "run",
        seed_strategy=seed,
        worker_image_ref="worker",
        verifier_image_ref="verifier",
        proxy_image_ref="proxy",
        task_panel_path=tmp_path / "panel.json",
    )

    assert calls[0]["max_iterations"] == 13
    assert calls[0]["inventory_turns"] == 2
    assert calls[0]["min_post_observation_turns"] == 3
    assert result["status"] == "property_gain"
    assert result["re_audit_observed"] is True
    assert result["artifact_changed"] is True
