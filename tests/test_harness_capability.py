import json

from qea.harness_capability import (
    capability_delta,
    measure_checkpoint_capability,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n")


def _attempt(root, name, task_id, checkpoint, *, improved):
    attempt = root / "attempts" / name
    _write_json(
        attempt / "attempt.json",
        {"attempt_id": name, "task_id": task_id, "checkpoint": checkpoint},
    )
    _write_json(
        attempt / "worker-execution.json",
        {
            "trace_uri": "raw-trace.jsonl",
            "summary": {
                "turns": 5 if improved else 7,
                "tool_calls": 6 if improved else 8,
                "tool_errors": 0 if improved else 2,
                "secs": 10 if improved else 20,
                "files": 2,
            },
        },
    )
    first = (
        "<ToolUse>ls -la /app/data /app/output</ToolUse>"
        if improved
        else "<ToolUse>python solve.py</ToolUse>"
    )
    second = (
        "<ToolUse>validate outputs with independent cross-check and assert</ToolUse>"
        if improved
        else "done"
    )
    (attempt / "raw-trace.jsonl").write_text(
        json.dumps({"role": "assistant", "content": first})
        + "\n"
        + json.dumps({"role": "assistant", "content": second})
        + "\n"
    )


def test_harness_capability_reports_process_change_separately_from_score(tmp_path):
    tasks = ["task-a", "task-b"]
    for index, task_id in enumerate(tasks):
        _attempt(tmp_path, f"seed-{index}", task_id, "seed", improved=False)
        _attempt(tmp_path, f"candidate-{index}", task_id, "candidate", improved=True)

    seed = measure_checkpoint_capability(
        run_dir=tmp_path, checkpoint="seed", task_ids=tasks
    )
    candidate = measure_checkpoint_capability(
        run_dir=tmp_path, checkpoint="candidate", task_ids=tasks
    )
    delta = capability_delta(seed, candidate)

    assert seed["rates"]["first_turn_workspace_inventory"] == 0.0
    assert candidate["rates"]["first_turn_workspace_inventory"] == 1.0
    assert candidate["rates"]["independent_crosscheck"] == 1.0
    assert delta["totals"]["tool_errors"] == -4.0
    assert delta["rates"]["tool_error_rate"] < 0
    assert delta["means"]["wall_seconds"] == -10.0


def test_harness_capability_preserves_timeout_to_complete_transition(tmp_path):
    tasks = ["stable", "timed"]
    _attempt(tmp_path, "seed-stable", "stable", "seed", improved=False)
    _attempt(tmp_path, "candidate-stable", "stable", "candidate", improved=True)
    timeout = tmp_path / "attempts/seed-timeout"
    _write_json(
        timeout / "attempt.json",
        {"attempt_id": "seed-timeout", "task_id": "timed", "checkpoint": "seed"},
    )
    _write_json(
        timeout / "completed-score.json",
        {"task_id": "timed", "reward": 0.0, "diagnostic_tags": ["timeout"]},
    )
    (timeout / "proxy-audit.jsonl").write_text(
        json.dumps({"request_state": "completed", "total_tokens": 100}) + "\n"
    )
    _attempt(tmp_path, "candidate-timed", "timed", "candidate", improved=True)

    seed = measure_checkpoint_capability(
        run_dir=tmp_path, checkpoint="seed", task_ids=tasks
    )
    candidate = measure_checkpoint_capability(
        run_dir=tmp_path, checkpoint="candidate", task_ids=tasks
    )
    delta = capability_delta(seed, candidate)

    assert seed["coverage"]["worker_timeout_count"] == 1
    assert seed["task_vectors"][1]["turns"] is None
    assert candidate["coverage"]["trace_available_count"] == 2
    assert delta["status_transitions"]["worker_timeout->complete"] == 1
    assert delta["paired_task_ids"] == ["stable"]
    assert delta["coverage"]["trace_available_count"] == 1.0
