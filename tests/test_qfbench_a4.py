import copy
import hashlib
import json
from pathlib import Path

import pytest

from qea.qfbench_a4 import (
    A4SelectionError,
    derive_a4_panel,
    validate_frozen_panel,
)
from qea.worker_identity import hash_worker_directory


def _score(task_id, reward, passed, failed, *, exit_code=0):
    return {
        "task_id": task_id,
        "reward": reward,
        "tests_passed": passed,
        "tests_failed": failed,
        "verifier_exit_code": exit_code,
        "diagnostic_tags": [] if reward == 1 else ["tests_failed"],
    }


def _fixture():
    tasks = [
        ("weak-consistent", "rates"),
        ("weak-variable", "data"),
        ("weak-medium", "data"),
        ("weak-low", "derivatives"),
        ("stable-large", "systematic"),
        ("stable-other", "risk"),
        ("stable-same-domain", "rates"),
        ("held-out-near-pass", "risk"),
    ]
    manifest = {
        "evolution": {
            "train": [
                {"task_id": task_id, "domain": domain}
                for task_id, domain in tasks[:-1]
            ],
            "test": [{"task_id": tasks[-1][0], "domain": tasks[-1][1]}],
        }
    }
    repetitions = []
    for index in range(5):
        repetitions.append(
            {
                "repetition": index + 1,
                "primary": {
                    "scores": [
                        _score("weak-consistent", 0, 9, 1),
                        _score(
                            "weak-variable", 0, 10 if index else 0, 1 if index else 10
                        ),
                        _score("weak-medium", 0, 5, 5),
                        _score("weak-low", 0, 2, 8),
                        _score("stable-large", 1, 50, 0),
                        _score("stable-other", 1, 40, 0),
                        _score("stable-same-domain", 1, 60, 0),
                        _score("held-out-near-pass", 0, 99, 1),
                    ]
                },
            }
        )
    return {"complete": True, "repetitions": repetitions}, manifest


def test_a4_selector_uses_repeatable_train_failures_and_cross_domain_protections():
    baseline, manifest = _fixture()

    panel = derive_a4_panel(
        baseline_result=baseline,
        evolution_manifest=manifest,
        target_count=3,
        protection_count=2,
    )

    assert [item.task_id for item in panel.targets] == [
        "weak-consistent",
        "weak-medium",
        "weak-low",
    ]
    assert "held-out-near-pass" not in panel.task_ids
    assert [item.task_id for item in panel.protections] == [
        "stable-large",
        "stable-other",
    ]
    assert panel.targets[0].min_pass_fraction == 0.9


def test_a4_selector_rejects_incomplete_or_infrastructure_tainted_baseline():
    baseline, manifest = _fixture()
    baseline["complete"] = False
    with pytest.raises(A4SelectionError, match="not complete"):
        derive_a4_panel(baseline_result=baseline, evolution_manifest=manifest)

    baseline, manifest = _fixture()
    for repetition in baseline["repetitions"]:
        repetition["primary"]["scores"][0]["verifier_exit_code"] = 2
    with pytest.raises(A4SelectionError, match="too few eligible"):
        derive_a4_panel(
            baseline_result=baseline,
            evolution_manifest=manifest,
            target_count=4,
            protection_count=2,
        )


def test_frozen_a4_panel_must_match_source_derivation_exactly():
    baseline, manifest = _fixture()
    panel = derive_a4_panel(
        baseline_result=baseline,
        evolution_manifest=manifest,
        target_count=3,
        protection_count=2,
    )
    frozen = panel.as_dict()

    validate_frozen_panel(frozen=frozen, derived=panel)
    drifted = copy.deepcopy(frozen)
    drifted["task_ids"][0] = "different"
    with pytest.raises(A4SelectionError, match="differs"):
        validate_frozen_panel(frozen=drifted, derived=panel)


def test_repository_a4_manifest_matches_the_pinned_five_repeat_baseline():
    repository = Path(__file__).resolve().parents[1]
    baseline_root = repository / (
        "results/bc-mirror/"
        "qfbench-rootless-base-85x5-official-deepseek-v4-flash-0731-"
        "all12x3-20260804"
    )
    if not baseline_root.is_dir():
        pytest.skip("the mirrored five-repeat baseline is not present")
    baseline = json.loads((baseline_root / "result.json").read_text())
    evolution = json.loads(
        (repository / "data/qfbench/MANIFEST_30_15_40_EVOLUTION.json").read_text()
    )
    frozen = json.loads(
        (repository / "data/qfbench/MANIFEST_A4_EVOLVER_BEHAVIOR.json").read_text()
    )

    derived = derive_a4_panel(
        baseline_result=baseline,
        evolution_manifest=evolution,
    )

    validate_frozen_panel(frozen=frozen["panel"], derived=derived)
    assert set(derived.task_ids).isdisjoint(
        task["task_id"] for task in evolution["evolution"]["validation"]
    )
    assert set(derived.task_ids).isdisjoint(
        task["task_id"] for task in evolution["evolution"]["test"]
    )


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def test_a4_evidence_builder_exposes_structured_train_evidence_without_oracles(
    tmp_path,
):
    from scripts.build_qfbench_a4_evidence import build

    baseline_payload, evolution = _fixture()
    baseline_payload["run_id"] = "baseline-fixture"
    baseline = tmp_path / "baseline"
    _write_json(baseline / "result.json", baseline_payload)
    seed = baseline / "workers/seed"
    seed.mkdir(parents=True)
    (seed / "agent.yaml").write_text("type: agent\n")
    (seed / "systemprompt.md").write_text("fixture\n")
    seed_digest = hash_worker_directory(seed)
    evolution["commit"] = "fixture-commit"
    evolution_path = tmp_path / "evolution.json"
    _write_json(evolution_path, evolution)
    panel = derive_a4_panel(
        baseline_result=baseline_payload,
        evolution_manifest=evolution,
        target_count=3,
        protection_count=2,
    )
    a4 = {
        "schema_version": 1,
        "benchmark_commit": "fixture-commit",
        "baseline": {
            "run_id": "baseline-fixture",
            "result_sha256": hashlib.sha256(
                (baseline / "result.json").read_bytes()
            ).hexdigest(),
            "seed_worker_digest": seed_digest,
        },
        "selection": {
            "target_count": 3,
            "tvt_manifest_sha256": hashlib.sha256(
                evolution_path.read_bytes()
            ).hexdigest(),
        },
        "panel": panel.as_dict(),
    }
    a4_path = tmp_path / "a4.json"
    _write_json(a4_path, a4)

    evidence_run = tmp_path / "fresh"
    _write_json(
        evidence_run / "pilot-plan.json",
        {
            "benchmark_commit": "fixture-commit",
            "arms": [
                {"label": "seed-evidence", "worker_digest": seed_digest}
            ],
        },
    )
    _write_json(
        evidence_run / "pilot-report.json",
        {
            "status": "complete",
            "task_ids": list(panel.task_ids),
            "activations": {
                "seed-evidence": {"checkpoint": "a4-seed-evidence"}
            },
        },
    )
    role_by_task = {
        item.task_id: item.role for item in panel.targets + panel.protections
    }
    for index, task_id in enumerate(panel.task_ids):
        attempt = evidence_run / "attempts" / f"attempt-{index}"
        _write_json(
            attempt / "attempt.json",
            {
                "task_id": task_id,
                "checkpoint": "a4-seed-evidence",
                "worker_digest": seed_digest,
            },
        )
        reward = 0.0 if role_by_task[task_id] == "target" else 1.0
        _write_json(
            attempt / "completed-score.json",
            {
                "task_id": task_id,
                "reward": reward,
                "tests_passed": 9 if reward == 0 else 10,
                "tests_failed": 1 if reward == 0 else 0,
                "verifier_exit_code": 0,
                "diagnostic_tags": ["tests_failed"] if reward == 0 else [],
            },
        )
        _write_json(
            attempt / "worker-execution.json",
            {
                "trace_uri": "raw-trace.jsonl",
                "final_text_uri": "final.txt",
                "artifact_dir": "artifacts",
                "summary": {"tool_calls": 4, "tool_errors": 0},
            },
        )
        (attempt / "raw-trace.jsonl").write_text(
            json.dumps(
                {
                    "role": "assistant",
                    "content": (
                        '<ToolUse>{"name":"write_file","input":'
                        '{"path":"solve.py"}}</ToolUse>'
                    ),
                }
            )
            + "\n"
        )
        (attempt / "final.txt").write_text("all checks look good\n")
        artifacts = attempt / "artifacts"
        artifacts.mkdir()
        (artifacts / "result.csv").write_text("x,y\n1,2\n")
        if index == 0:
            (artifacts / "large.csv").write_text("a,b\n" + "1,2\n" * 60_000)

    destination = tmp_path / "evidence"
    report = build(
        baseline_run=baseline,
        evolution_manifest_path=evolution_path,
        a4_manifest_path=a4_path,
        evidence_run=evidence_run,
        arm="seed-evidence",
        destination=destination,
    )

    assert report["task_ids"] == list(panel.task_ids)
    assert (destination / "debugger/overview.json").is_file()
    assert "<ToolUse>" in (
        destination / f"tasks/{panel.task_ids[0]}/worker_trace.jsonl"
    ).read_text()
    artifact_manifest = json.loads(
        (
            destination
            / f"tasks/{panel.task_ids[0]}/artifact_manifest.json"
        ).read_text()
    )
    large = next(
        item for item in artifact_manifest["artifacts"] if item["path"] == "large.csv"
    )
    assert large["representation"] == "head_tail_preview"
    all_members = "\n".join(report["members"])
    assert "official-tests" not in all_members
    assert "reference-data" not in all_members


def test_a4_audit_keeps_process_gate_separate_from_directional_scores():
    from scripts.audit_qfbench_a4_behavior import audit

    manifest = {
        "panel": {
            "targets": [{"task_id": "target-a"}, {"task_id": "target-b"}],
            "protections": [{"task_id": "protect-a"}],
        }
    }
    proposal = {
        "proposal": {
            "admission": {"admitted": True},
            "diff": "--- a/routing/rules.py\n+++ b/routing/rules.py\n+change\n",
            "prediction": {"component_changed": "routing"},
            "access_summary": {
                "evidence_paths": [
                    "tasks/target-a/worker_trace.jsonl",
                    "tasks/target-b/worker_trace.jsonl",
                ]
            },
            "summary": {
                "discovery": {
                    "checks": {
                        "writes_unlocked": True,
                        "multiple_hypotheses": True,
                        "counterevidence_recorded": True,
                        "falsifiable_prediction_recorded": True,
                        "final_mechanism_consistent": True,
                        "final_component_consistent": True,
                    },
                    "contract_score": 1.0,
                    "hypotheses_considered_count": 2,
                    "exact_evidence_access_count": 5,
                    "evidence_access_ratio": 0.5,
                    "grounded_citation_ratio": 1.0,
                    "trace_files_accessed": 2,
                }
            },
        }
    }
    seed = {
        "summaries": {
            "seed": {
                "task_rewards": {
                    "target-a": 0.0,
                    "target-b": 0.0,
                    "protect-a": 1.0,
                }
            }
        }
    }
    candidate = {
        "summaries": {
            "candidate": {
                "task_rewards": {
                    "target-a": 1.0,
                    "target-b": 0.0,
                    "protect-a": 0.0,
                }
            }
        }
    }

    report = audit(
        a4_manifest=manifest,
        proposal_report=proposal,
        seed_report=seed,
        candidate_report=candidate,
        seed_arm="seed",
        candidate_arm="candidate",
    )

    assert report["process"]["gate_passed"] is True
    assert report["outcome"]["target_gains"] == ["target-a"]
    assert report["outcome"]["protection_regressions"] == ["protect-a"]
    assert report["multi_round_readiness"] == "manual_causal_audit_required"
