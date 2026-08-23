import json
from pathlib import Path

from scripts.build_qfbench_coordinated_feedback_view import main


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")


def _base_view(tmp_path: Path) -> Path:
    root = tmp_path / "base-view"
    _write(
        root / "contract.json",
        {
            "stage": "COORDINATED_BREADTH",
            "evolver_instruction": "Inspect the optimize trajectories.",
        },
    )
    return root


def _scored_run(tmp_path: Path, label: str, artifact_text: str) -> Path:
    root = tmp_path / label
    _write(
        root / "proposal-report.json",
        {
            "decision": "ACT",
            "prediction": {"component": f"component-{label}"},
            "diff": f"diff --git a/{label} b/{label}\n",
        },
    )
    attempt = root / "attempts" / "scored-worker"
    _write(
        attempt / "worker-execution.json",
        {
            "trace_uri": "raw-trace.jsonl",
            "final_text_uri": "final.txt",
            "summary": {"tool_calls": 3},
            "artifacts": [{"path": "strategy.py"}],
        },
    )
    _write(
        attempt / "completed-score.json",
        {
            "task_id": "dupire-local-vol",
            "domain": "derivatives",
            "reward": 0.5,
            "diagnostic_tags": [label],
            "tests_passed": 67,
            "tests_failed": 1,
            "verifier_exit_code": 0,
        },
    )
    _write(attempt / "raw-trace.jsonl", f'{{"tool":"component-{label}"}}\n')
    _write(attempt / "final.txt", f"finished {label}\n")
    _write(attempt / "artifacts" / "strategy.py", artifact_text)
    return root


def _diagnostic(tmp_path: Path, label: str) -> Path:
    path = tmp_path / f"{label}-diagnostic.json"
    _write(
        path,
        {
            "feedback_mode": "answer_rich_evolver",
            "worker_visible": False,
            "diagnostic": label,
        },
    )
    return path


def _parent(tmp_path: Path, label: str) -> Path:
    root = tmp_path / f"{label}-parent"
    _write(root / "agent.yaml", f"name: {label}\n")
    return root


def test_chains_two_worker_entries_with_artifacts_diagnostics_and_exact_parents(
    tmp_path,
):
    first_run = _scored_run(tmp_path, "run-one", "first artifact\n")
    first_parent = _parent(tmp_path, "parent-one")
    first_view = tmp_path / "feedback-one"
    assert main(
        [
            "--base-view",
            str(_base_view(tmp_path)),
            "--source-run",
            str(first_run),
            "--optimization-diagnostic",
            str(_diagnostic(tmp_path, "diagnostic-one")),
            "--parent-candidate",
            str(first_parent),
            "--component-token",
            "component-run-one",
            "--destination",
            str(first_view),
            "--round-label",
            "round-1",
        ]
    ) == 0

    second_run = _scored_run(tmp_path, "run-two", "second artifact\n")
    second_parent = _parent(tmp_path, "parent-two")
    second_view = tmp_path / "feedback-two"
    assert main(
        [
            "--base-view",
            str(first_view),
            "--source-run",
            str(second_run),
            "--optimization-diagnostic",
            str(_diagnostic(tmp_path, "diagnostic-two")),
            "--parent-candidate",
            str(second_parent),
            "--component-token",
            "component-run-two",
            "--destination",
            str(second_view),
            "--round-label",
            "round-2",
        ]
    ) == 0

    entries = [
        "history/archive/entries/round-1.json",
        "history/archive/entries/round-2.json",
    ]
    contract = json.loads((second_view / "contract.json").read_text())
    assert contract["prior_runtime_experience_entries"] == entries
    assert contract["required_runtime_experience_entries"] == entries
    assert contract["prior_runtime_experience"] == entries[-1]
    assert contract["runtime_feedback_round"] == 3
    assert contract["evolver_instruction"].count(
        "This is a feedback round."
    ) == 1
    assert "Read every runtime-experience entry selected" in contract[
        "evolver_instruction"
    ]

    for index, label in enumerate(("round-1", "round-2"), start=1):
        entry = json.loads(
            (second_view / f"history/archive/entries/{label}.json").read_text()
        )
        artifact_path = f"history/archive/worker-artifacts/{label}"
        assert entry["worker_artifact_directory"] == artifact_path
        assert entry["evidence_paths"]["worker_artifacts"] == artifact_path
        assert entry["evolver_only_optimization_diagnostic"] == (
            f"history/archive/objects/{label}-optimization-diagnostic.json"
        )
        assert entry["parent_candidate_snapshot"] == (
            f"history/archive/parent-candidates/{label}"
        )
        assert (
            second_view / artifact_path / "strategy.py"
        ).read_text() == f"{'first' if index == 1 else 'second'} artifact\n"
        assert (
            second_view
            / f"history/archive/parent-candidates/{label}/agent.yaml"
        ).read_text() == f"name: parent-{'one' if index == 1 else 'two'}\n"
        diagnostic = json.loads(
            (
                second_view
                / f"history/archive/objects/{label}-optimization-diagnostic.json"
            ).read_text()
        )
        assert diagnostic["worker_visible"] is False
