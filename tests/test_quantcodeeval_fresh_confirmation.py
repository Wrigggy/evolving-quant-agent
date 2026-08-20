import json
from pathlib import Path

import qea.quantcodeeval_fresh_confirmation as fresh_module


def test_runs_no_seed_fresh_confirmation_and_classifies_binary_gain(
    tmp_path, monkeypatch
):
    source = tmp_path / "source"
    candidate = source / "evolver/evolutions/iteration-0001/candidate"
    candidate.mkdir(parents=True)
    (candidate / "agent.yaml").write_text("type: agent\n")
    (source / "COMPONENT-IMPACT-RESULT.json").write_text(
        json.dumps({"baseline_tests_passed": 12, "baseline_reward": 0})
    )
    (source / "evolver/LIVE-RESULT.json").write_text(
        json.dumps({"decision": {"decision": "ACT"}})
    )
    release = tmp_path / "release"
    (release / "h0/workers/H0").mkdir(parents=True)
    (release / "public").mkdir()
    (release / "trusted").mkdir()
    artifact = tmp_path / "strategy.py"
    artifact.write_text("VALUE = 1\n")
    calls = []
    monkeypatch.setattr(fresh_module, "admit_candidate", lambda *args: None)

    def fake_fresh(**kwargs):
        calls.append(kwargs)
        return {
            "score": {"tests_passed": 17, "reward": 1},
            "artifact": str(artifact),
            "tool_usage": {
                "counts": {"check_quant_relations": 2},
                "first_assistant_turn": {"check_quant_relations": 25},
            },
            "worker_summary": {"turns": 48},
            "cost": {"provider_cost_usd": "0.12"},
        }

    monkeypatch.setattr(fresh_module, "run_probe_arm", fake_fresh)
    result = fresh_module.run_quantcodeeval_fresh_confirmation(
        config_path=tmp_path / "config.json",
        release_dir=release,
        source_run_dir=source,
        run_dir=tmp_path / "run",
        worker_image_ref="worker",
        verifier_image_ref="verifier",
        proxy_image_ref="proxy",
        task_panel_path=tmp_path / "panel.json",
    )

    assert calls[0]["seed_strategy"] is None
    assert calls[0]["max_iterations"] == 60
    assert calls[0]["inventory_turns"] == 24
    assert "no strategy implementation is pre-staged" in calls[0][
        "worker_instruction"
    ]
    assert result["status"] == "binary_gain"
    assert result["fresh_tests_passed"] == 17
    assert result["component_reaudit_observed"] is True
    assert result["seed_strategy_present"] is False
