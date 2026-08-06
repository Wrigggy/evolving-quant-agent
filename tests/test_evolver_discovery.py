import json

from qea.evolution_evidence import authorize_evidence_tree
from qea.evolver_discovery import measure_discovery_quality


def test_discovery_quality_measures_grounding_and_contract_consistency():
    members = (
        "debugger/overview.json",
        "tasks/task-a/worker_trace.jsonl",
        "tasks/task-a/public_evaluation.json",
    )
    state = {
        "unlocked": True,
        "hypothesis": {
            "hypotheses_considered": ["routing collision", "bad quant formula"],
            "selected_mechanism": "routing collision",
            "evidence_refs": [
                "debugger/overview.json",
                "tasks/task-a/worker_trace.jsonl",
            ],
            "counterevidence": "the same skill helps task-b",
            "uncertainty": "one trace per task",
            "discriminating_probe": "skill activation precedes the divergence",
            "component": "routing",
            "prediction": {"task-a": "skill no longer activates"},
            "risk_tasks": ["task-b"],
        },
    }
    prediction = {
        "selected_mechanism": "routing collision",
        "component_changed": "routing",
        "evidence_used": [
            "debugger/overview.json",
            "tasks/task-a/worker_trace.jsonl (activation span)",
        ],
        "predicted_process_changes": ["task-a does not load the broad skill"],
    }
    access = {
        "evidence_paths": [
            "**/*",
            "debugger/overview.json",
            "tasks/task-a/worker_trace.jsonl",
        ],
        "operations": {"map": 1, "read": 2, "trace_slice": 1},
    }

    measured = measure_discovery_quality(
        prediction=prediction,
        access_summary=access,
        discovery_state=state,
        evidence_members=members,
    )

    assert measured["contract_score"] == 1.0
    assert measured["grounded_citation_ratio"] == 1.0
    assert measured["evidence_access_ratio"] == 2 / 3
    assert measured["debugger_files_accessed"] == 1
    assert measured["trace_files_accessed"] == 1


def test_discovery_quality_does_not_treat_listing_or_uncited_output_as_grounded():
    measured = measure_discovery_quality(
        prediction={"component_changed": "skills"},
        access_summary={
            "evidence_paths": ["**/*"],
            "operations": {"map": 1},
        },
        discovery_state=None,
        evidence_members=("debugger/overview.json", "tasks/task-a/worker_trace.jsonl"),
    )

    assert measured["contract_score"] == 0.0
    assert measured["exact_evidence_access_count"] == 0
    assert measured["grounded_citation_ratio"] is None
    assert measured["query_operations"]["map"] == 1


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n")


def _pilot_run(path, stage, *, task_reward=0.0):
    path.mkdir()
    _write_json(
        path / "pilot-report.json",
        {
            "run_id": path.name,
            "stage": stage,
            "status": "complete",
            "evaluation": {
                "task_rewards": {"task-a": task_reward},
                "task_mean": task_reward,
                "overall": task_reward,
            },
            "activation": {
                "activation_count": 1,
                "declared_skills": ["contract-skill"],
                "attempts": [
                    {
                        "task_id": "task-a",
                        "attempt_id": "attempt-a",
                        "activated_skills": ["contract-skill"],
                    }
                ],
            },
            "proposal": {
                "prediction": {
                    "component_changed": "skills",
                    "failure_kind": "broad activation",
                }
            },
            "cost": {"provider_cost_usd": 0.01},
        },
    )


def test_post_a3_evidence_builder_keeps_raw_arms_matched_and_adds_debugger_index(
    tmp_path,
):
    from scripts.build_qfbench_discovery_evidence import build

    a1 = tmp_path / "a1"
    a2 = tmp_path / "a2"
    a3 = tmp_path / "a3"
    _pilot_run(a1, "A1", task_reward=0.5)
    _pilot_run(a2, "A2", task_reward=0.0)
    _pilot_run(a3, "A3", task_reward=1.0)
    _write_json(
        a3 / "proposal-report.json",
        {
            "diff": "--- a/agent.yaml\n+++ b/agent.yaml\n+skills:\n",
            "prediction": {"component_changed": "skills"},
            "access_summary": {"evidence_paths": ["task_vectors.json"]},
            "summary": {"tool_calls": 3},
            "admission": {"checks": ["local_skills"]},
        },
    )
    for root, prompt in (
        (a3 / "workers/backbone", "before\n"),
        (a3 / "evolutions/iteration-0001/candidate", "after\n"),
    ):
        root.mkdir(parents=True)
        (root / "agent.yaml").write_text("skills: []\n")
        (root / "systemprompt.md").write_text(prompt)
    authorized = a3 / "authorized-evidence"
    _write_json(
        authorized / "task_vectors.json",
        {
            "vectors": {
                "backbone": {"task_rewards": {"task-a": 0.0}},
            }
        },
    )
    _write_json(
        authorized / "selection.json", {"backbone_parent": "backbone"}
    )
    _write_json(authorized / "debugger_overview.json", {"generator": "fixture"})
    attempt = a3 / "attempts/attempt-a"
    _write_json(
        attempt / "attempt.json",
        {"task_id": "task-a", "checkpoint": "a3-candidate"},
    )
    _write_json(
        attempt / "completed-score.json",
        {
            "task_id": "task-a",
            "reward": 1.0,
            "diagnostic_tags": [],
            "tests_passed": 3,
            "tests_failed": 0,
            "log_uri": "/trusted/verifier-command.json",
        },
    )
    _write_json(attempt / "worker-execution.json", {"summary": {"tool_calls": 2}})
    (attempt / "raw-trace.jsonl").write_text(
        '{"role":"assistant","content":"load contract-skill"}\n'
    )
    (attempt / "final.txt").write_text("completed\n")

    raw = tmp_path / "raw"
    indexed = tmp_path / "indexed"
    raw_report = build(
        a1_run=a1, a2_run=a2, a3_run=a3, destination=raw, mode="raw"
    )
    indexed_report = build(
        a1_run=a1, a2_run=a2, a3_run=a3, destination=indexed, mode="indexed"
    )

    assert raw_report["credential_redactions"] == 0
    assert indexed_report["member_count"] == raw_report["member_count"] + 3
    assert not (raw / "debugger/overview.json").exists()
    assert (indexed / "debugger/overview.json").is_file()
    assert (raw / "tasks/task-a/worker_trace.jsonl").read_bytes() == (
        indexed / "tasks/task-a/worker_trace.jsonl"
    ).read_bytes()
    public = json.loads((indexed / "tasks/task-a/public_evaluation.json").read_text())
    assert "log_uri" not in public
    assert public["official_reward"] == 1.0
    assert authorize_evidence_tree(raw).sha256 == raw_report["sha256"]
    assert authorize_evidence_tree(indexed).sha256 == indexed_report["sha256"]
