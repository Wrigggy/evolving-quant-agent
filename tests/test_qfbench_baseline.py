import json
import math
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from qea.evaluation import OfficialTaskScore, aggregate_domain_macro


COMMIT = "0" * 40
DIGESTS = {
    "task_manifest_digest": "1" * 64,
    "runtime_identity_digest": "2" * 64,
    "scheduler_identity_digest": "3" * 64,
    "template_identity_digest": "4" * 64,
}


def _tasks():
    primary = (
        SimpleNamespace(
            task_id="risk-task",
            domain="risk_credit",
            reward_kind="binary",
            resource_source="upstream",
        ),
        SimpleNamespace(
            task_id="derivative-task",
            domain="derivatives",
            reward_kind="partial",
            resource_source="qea_fallback",
        ),
    )
    diagnostic = (
        SimpleNamespace(
            task_id="copy-task",
            domain="derivatives",
            reward_kind="binary",
            resource_source="upstream",
        ),
    )
    return primary, diagnostic


def _summary(tasks, reward):
    return aggregate_domain_macro(tuple(
        OfficialTaskScore(task_id=task.task_id, domain=task.domain, reward=reward)
        for task in tasks
    ))


class RecordingEvaluator:
    def __init__(self):
        self.calls = []

    def evaluate(self, *, worker_dir, tasks, split, checkpoint, run_dir):
        self.calls.append((split, checkpoint))
        repetition = int(checkpoint.split("-")[1])
        reward = repetition / 10
        return _summary(tuple(tasks), reward)


def _config(tmp_path: Path, worker: Path, **changes):
    from qea.qfbench_baseline import BaselineConfig

    values = {
        "run_id": "baseline-five",
        "repetitions": 5,
        "results_dir": tmp_path / "results",
        "seed_worker_dir": worker,
        "model_identity": "fixture-model",
        "worker_concurrency": 4,
        "verifier_concurrency": 3,
        **DIGESTS,
    }
    values.update(changes)
    return BaselineConfig(**values)


def test_runs_primary_then_diagnostic_for_five_repetitions_without_evolver(
    tmp_path,
) -> None:
    from qea.qfbench_baseline import run_qfbench_baseline

    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "systemprompt.md").write_text("base worker\n")
    primary, diagnostic = _tasks()
    evaluator = RecordingEvaluator()

    result = run_qfbench_baseline(
        _config(tmp_path, worker),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=evaluator,
    )

    assert evaluator.calls == [
        item
        for repetition in range(1, 6)
        for item in (
            ("baseline_primary", f"repetition-{repetition:02d}-primary"),
            ("baseline_diagnostic", f"repetition-{repetition:02d}-diagnostic"),
        )
    ]
    assert result.complete is True
    assert len(result.repetitions) == 5
    assert not (result.run_dir / "evidence").exists()
    assert not (result.run_dir / "iteration-01").exists()


def test_fresh_run_accepts_only_pristine_rootless_runtime_scaffold(tmp_path) -> None:
    from qea.qfbench_baseline import run_qfbench_baseline

    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "agent.yaml").write_text("name: base\n")
    run_dir = tmp_path / "results" / "baseline-five"
    run_dir.mkdir(parents=True)
    lock = run_dir / ".coordinator.lock"
    lock.touch(mode=0o600)
    lock.chmod(0o600)
    lifecycles = run_dir / "lifecycles"
    lifecycles.mkdir(mode=0o700)
    primary, diagnostic = _tasks()

    result = run_qfbench_baseline(
        _config(tmp_path, worker, resume=False),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=RecordingEvaluator(),
        stop_after_repetition=1,
    )

    assert result.run_dir == run_dir
    assert (run_dir / "resume.json").is_file()


@pytest.mark.parametrize("unexpected", ["attempts", "proxy-audit.jsonl"])
def test_fresh_run_rejects_non_pristine_runtime_scaffold(
    tmp_path, unexpected
) -> None:
    from qea.qfbench_baseline import BaselineConfigError, run_qfbench_baseline

    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "agent.yaml").write_text("name: base\n")
    run_dir = tmp_path / "results" / "baseline-five"
    run_dir.mkdir(parents=True)
    lock = run_dir / ".coordinator.lock"
    lock.touch(mode=0o600)
    lock.chmod(0o600)
    (run_dir / "lifecycles").mkdir(mode=0o700)
    unexpected_path = run_dir / unexpected
    if unexpected == "attempts":
        unexpected_path.mkdir()
    else:
        unexpected_path.write_text("stale\n")
    primary, diagnostic = _tasks()

    with pytest.raises(BaselineConfigError, match="already exists"):
        run_qfbench_baseline(
            _config(tmp_path, worker, resume=False),
            primary_tasks=primary,
            diagnostic_tasks=diagnostic,
            benchmark_commit=COMMIT,
            evaluator=RecordingEvaluator(),
        )


def test_calibration_stop_then_resume_starts_at_repetition_two(tmp_path) -> None:
    from qea.qfbench_baseline import run_qfbench_baseline

    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "agent.yaml").write_text("name: base\n")
    primary, diagnostic = _tasks()
    first = RecordingEvaluator()

    partial = run_qfbench_baseline(
        _config(tmp_path, worker),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=first,
        stop_after_repetition=1,
    )

    assert partial.complete is False
    assert first.calls == [
        ("baseline_primary", "repetition-01-primary"),
        ("baseline_diagnostic", "repetition-01-diagnostic"),
    ]
    state = json.loads((partial.run_dir / "resume.json").read_text())
    assert state["next_repetition"] == 2
    assert state["phase"] == "calibration_stop"

    resumed = RecordingEvaluator()
    complete = run_qfbench_baseline(
        _config(tmp_path, worker),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=resumed,
    )

    assert complete.complete is True
    assert resumed.calls[0] == (
        "baseline_primary",
        "repetition-02-primary",
    )
    assert len(resumed.calls) == 8


def test_stop_after_fifth_repetition_finishes_complete_run(tmp_path) -> None:
    from qea.qfbench_baseline import run_qfbench_baseline

    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "agent.yaml").write_text("name: base\n")
    primary, diagnostic = _tasks()

    result = run_qfbench_baseline(
        _config(tmp_path, worker),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=RecordingEvaluator(),
        stop_after_repetition=5,
    )

    assert result.complete is True
    assert len(result.repetitions) == 5


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model_identity", "other-model"),
        ("task_manifest_digest", "a" * 64),
        ("runtime_identity_digest", "b" * 64),
        ("scheduler_identity_digest", "c" * 64),
        ("template_identity_digest", "d" * 64),
        ("worker_concurrency", 3),
        ("verifier_concurrency", 2),
    ],
)
def test_resume_rejects_immutable_identity_change(tmp_path, field, value) -> None:
    from qea.qfbench_baseline import BaselineConfigError, run_qfbench_baseline

    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "agent.yaml").write_text("name: base\n")
    primary, diagnostic = _tasks()
    run_qfbench_baseline(
        _config(tmp_path, worker),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=RecordingEvaluator(),
        stop_after_repetition=1,
    )

    with pytest.raises(BaselineConfigError, match="identity mismatch"):
        run_qfbench_baseline(
            _config(tmp_path, worker, **{field: value}),
            primary_tasks=primary,
            diagnostic_tasks=diagnostic,
            benchmark_commit=COMMIT,
            evaluator=RecordingEvaluator(),
        )
def test_resume_rejects_worker_digest_and_benchmark_changes(tmp_path) -> None:
    from qea.qfbench_baseline import BaselineConfigError, run_qfbench_baseline

    worker = tmp_path / "worker"
    worker.mkdir()
    prompt = worker / "systemprompt.md"
    prompt.write_text("base\n")
    primary, diagnostic = _tasks()
    run_qfbench_baseline(
        _config(tmp_path, worker),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=RecordingEvaluator(),
        stop_after_repetition=1,
    )

    prompt.write_text("mutated\n")
    with pytest.raises(BaselineConfigError, match="identity mismatch"):
        run_qfbench_baseline(
            _config(tmp_path, worker),
            primary_tasks=primary,
            diagnostic_tasks=diagnostic,
            benchmark_commit=COMMIT,
            evaluator=RecordingEvaluator(),
        )
    prompt.write_text("base\n")
    with pytest.raises(BaselineConfigError, match="checkpoint mismatch"):
        run_qfbench_baseline(
            _config(tmp_path, worker),
            primary_tasks=primary,
            diagnostic_tasks=diagnostic,
            benchmark_commit="f" * 40,
            evaluator=RecordingEvaluator(),
        )


def test_resume_rejects_mutated_seed_worker_snapshot(tmp_path) -> None:
    from qea.qfbench_baseline import BaselineConfigError, run_qfbench_baseline

    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "agent.yaml").write_text("name: base\n")
    primary, diagnostic = _tasks()
    partial = run_qfbench_baseline(
        _config(tmp_path, worker),
        primary_tasks=primary,
        diagnostic_tasks=diagnostic,
        benchmark_commit=COMMIT,
        evaluator=RecordingEvaluator(),
        stop_after_repetition=1,
    )
    (partial.seed_worker_dir / "agent.yaml").write_text("name: tampered\n")

    with pytest.raises(BaselineConfigError, match="seed worker snapshot digest"):
        run_qfbench_baseline(
            _config(tmp_path, worker),
            primary_tasks=primary,
            diagnostic_tasks=diagnostic,
            benchmark_commit=COMMIT,
            evaluator=RecordingEvaluator(),
        )


def test_aggregate_repetitions_uses_repeat_level_t_interval_and_separate_panels():
    from qea.qfbench_baseline import aggregate_repetitions

    primary_tasks, diagnostic_tasks = _tasks()
    primary = tuple(_summary(primary_tasks, reward) for reward in (0.4, 0.5, 0.6, 0.7, 0.8))
    diagnostic = tuple(_summary(diagnostic_tasks, 1.0) for _ in range(5))

    aggregate = aggregate_repetitions(
        primary,
        diagnostic,
        resource_fallback_task_ids=frozenset({"derivative-task"}),
        primary_tasks=primary_tasks,
        diagnostic_tasks=diagnostic_tasks,
        expected_repetitions=5,
    )

    headline = aggregate["primary"]["repeat_domain_macro"]
    expected_sd = math.sqrt(0.025)
    expected_se = math.sqrt(0.005)
    half_width = 2.7764451051977987 * expected_se
    assert headline["mean"] == pytest.approx(0.6)
    assert headline["sample_sd"] == pytest.approx(expected_sd)
    assert headline["standard_error"] == pytest.approx(expected_se)
    assert headline["confidence_interval_95"] == pytest.approx(
        [0.6 - half_width, 0.6 + half_width]
    )
    assert aggregate["diagnostic"]["repeat_domain_macro"]["mean"] == 1.0
    assert aggregate["resource_declared_sensitivity"]["task_count"] == 1
    assert aggregate["primary"]["tasks"]["risk-task"]["success_count"] == 0
    assert "success_count" not in aggregate["primary"]["tasks"]["derivative-task"]


def test_partial_aggregate_has_no_confidence_interval() -> None:
    from qea.qfbench_baseline import aggregate_repetitions

    primary_tasks, diagnostic_tasks = _tasks()
    aggregate = aggregate_repetitions(
        (_summary(primary_tasks, 0.5),),
        (_summary(diagnostic_tasks, 0.0),),
        resource_fallback_task_ids=frozenset({"derivative-task"}),
        primary_tasks=primary_tasks,
        diagnostic_tasks=diagnostic_tasks,
        expected_repetitions=5,
    )

    assert aggregate["complete"] is False
    headline = aggregate["primary"]["repeat_domain_macro"]
    assert headline["mean"] == 0.5
    assert headline["sample_sd"] is None
    assert headline["confidence_interval_95"] is None


def _audit_record(*, identity: str, cost: float, input_tokens: int) -> dict:
    return {
        "schema_version": 1,
        "request_identity_sha256": identity * 64,
        "model": "fixture-model",
        "started_at": "2026-07-31T12:00:00+00:00",
        "finished_at": "2026-07-31T12:00:01+00:00",
        "latency_ms": 1000,
        "request_state": "completed",
        "upstream_status_code": 200,
        "provider_request_id": f"provider-{identity}",
        "input_tokens": input_tokens,
        "output_tokens": 5,
        "total_tokens": input_tokens + 5,
        "provider_cost_usd": cost,
        "failure_class": None,
    }


def _cost_fixture(run_dir: Path) -> tuple[Path, Path]:
    from qea.evaluation import TaskAttempt

    specs = (
        ("risk-task", "risk_credit", "baseline_primary", "repetition-01-primary"),
        ("copy-task", "derivatives", "baseline_diagnostic", "repetition-01-diagnostic"),
    )
    paths = []
    for task_id, domain, split, checkpoint in specs:
        attempt = TaskAttempt.create(
            run_id="baseline-five",
            benchmark_commit=COMMIT,
            task_id=task_id,
            split=split,
            checkpoint=checkpoint,
            worker_digest="e" * 64,
        )
        attempt_dir = run_dir / "attempts" / attempt.attempt_id
        attempt_dir.mkdir(parents=True)
        (attempt_dir / "attempt.json").write_text(json.dumps(asdict(attempt)))
        score = OfficialTaskScore(task_id=task_id, domain=domain, reward=0.5)
        (attempt_dir / "completed-score.json").write_text(json.dumps(asdict(score)))
        paths.append(attempt_dir)
    paths[0].joinpath("proxy-audit.jsonl").write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                _audit_record(identity="a", cost=0.01, input_tokens=10),
                _audit_record(identity="b", cost=0.02, input_tokens=20),
            )
        )
        + "\n"
    )
    paths[1].joinpath("proxy-audit.jsonl").write_text(
        json.dumps(_audit_record(identity="c", cost=0.03, input_tokens=30))
        + "\n"
    )
    return paths[0], paths[1]


def _add_timeout_cost_attempt(run_dir: Path) -> Path:
    from qea.evaluation import TaskAttempt

    attempt = TaskAttempt.create(
        run_id="baseline-five",
        benchmark_commit=COMMIT,
        task_id="slow-task",
        split="baseline_primary",
        checkpoint="repetition-01-primary",
        worker_digest="e" * 64,
    )
    attempt_dir = run_dir / "attempts" / attempt.attempt_id
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "attempt.json").write_text(json.dumps(asdict(attempt)))
    score = OfficialTaskScore(
        task_id="slow-task",
        domain="derivatives",
        reward=0.0,
        diagnostic_tags=("timeout",),
    )
    (attempt_dir / "completed-score.json").write_text(json.dumps(asdict(score)))
    (attempt_dir / "proxy-audit.quarantined.json").write_text(json.dumps({
        "schema_version": 1,
        "request_state": "quarantined",
        "reason": "audit_download_or_validation_failed",
    }))
    return attempt_dir


def test_cost_audit_reconciles_attempts_requests_tokens_and_groups(tmp_path) -> None:
    from qea.qfbench_baseline import audit_baseline_proxy_costs

    _cost_fixture(tmp_path)
    audit = audit_baseline_proxy_costs(tmp_path, expected_attempts=2)

    assert audit["attempt_count"] == 2
    assert audit["request_count"] == 3
    assert audit["input_tokens"] == 60
    assert audit["output_tokens"] == 15
    assert audit["total_tokens"] == 75
    assert audit["provider_cost_usd"] == "0.06"
    assert audit["cost_complete"] is True
    assert audit["provider_cost_is_lower_bound"] is False
    assert audit["unreconciled_attempt_count"] == 0
    assert audit["unreconciled_attempts"] == []
    primary = audit["by_repetition"]["1"]["primary"]
    assert primary["request_count"] == 2
    assert primary["provider_cost_usd"] == "0.03"
    assert primary["tasks"]["risk-task"]["provider_cost_usd"] == "0.03"
    diagnostic = audit["by_repetition"]["1"]["diagnostic"]
    assert diagnostic["request_count"] == 1


def test_cost_audit_reports_timeout_ledger_as_explicit_lower_bound(tmp_path) -> None:
    from qea.qfbench_baseline import audit_baseline_proxy_costs

    _cost_fixture(tmp_path)
    timeout_dir = _add_timeout_cost_attempt(tmp_path)

    audit = audit_baseline_proxy_costs(tmp_path, expected_attempts=3)

    assert audit["attempt_count"] == 3
    assert audit["request_count"] == 3
    assert audit["input_tokens"] == 60
    assert audit["output_tokens"] == 15
    assert audit["total_tokens"] == 75
    assert audit["provider_cost_usd"] == "0.06"
    assert audit["cost_complete"] is False
    assert audit["provider_cost_is_lower_bound"] is True
    assert audit["unreconciled_attempt_count"] == 1
    assert audit["unreconciled_attempts"] == [{
        "attempt_id": timeout_dir.name,
        "checkpoint": "repetition-01-primary",
        "panel": "primary",
        "repetition": 1,
        "task_id": "slow-task",
        "reason": "audit_download_or_validation_failed",
    }]
    slow = audit["by_repetition"]["1"]["primary"]["tasks"]["slow-task"]
    assert slow["attempt_count"] == 1
    assert slow["request_count"] == 0


@pytest.mark.parametrize(
    "corruption",
    (
        "reward_one",
        "missing_timeout_tag",
        "malformed_marker",
        "both_marker_and_audit",
        "missing_marker",
    ),
)
def test_cost_audit_rejects_non_timeout_or_ambiguous_missing_ledgers(
    tmp_path, corruption
) -> None:
    from qea.qfbench_baseline import BaselineConfigError, audit_baseline_proxy_costs

    _cost_fixture(tmp_path)
    timeout_dir = _add_timeout_cost_attempt(tmp_path)
    score_path = timeout_dir / "completed-score.json"
    score = json.loads(score_path.read_text())
    marker_path = timeout_dir / "proxy-audit.quarantined.json"
    if corruption == "reward_one":
        score["reward"] = 1.0
        score_path.write_text(json.dumps(score))
    elif corruption == "missing_timeout_tag":
        score["diagnostic_tags"] = []
        score_path.write_text(json.dumps(score))
    elif corruption == "malformed_marker":
        marker = json.loads(marker_path.read_text())
        marker["unexpected"] = True
        marker_path.write_text(json.dumps(marker))
    elif corruption == "both_marker_and_audit":
        (timeout_dir / "proxy-audit.jsonl").write_text(
            json.dumps(_audit_record(identity="d", cost=0.04, input_tokens=40))
            + "\n"
        )
    elif corruption == "missing_marker":
        marker_path.unlink()

    with pytest.raises(BaselineConfigError, match="cost audit"):
        audit_baseline_proxy_costs(tmp_path, expected_attempts=3)


@pytest.mark.parametrize(
    "corruption",
    (
        "missing_audit",
        "null_success_cost",
        "null_success_usage",
        "noncompleted_200",
        "unknown_checkpoint",
        "attempt_count",
    ),
)
def test_cost_audit_fails_closed_on_incomplete_or_drifted_ledger(
    tmp_path, corruption
) -> None:
    from qea.qfbench_baseline import BaselineConfigError, audit_baseline_proxy_costs

    primary_dir, _ = _cost_fixture(tmp_path)
    expected_attempts = 2
    audit_path = primary_dir / "proxy-audit.jsonl"
    records = [json.loads(line) for line in audit_path.read_text().splitlines()]
    if corruption == "missing_audit":
        audit_path.unlink()
    elif corruption == "null_success_cost":
        records[0]["provider_cost_usd"] = None
        audit_path.write_text("\n".join(map(json.dumps, records)) + "\n")
    elif corruption == "null_success_usage":
        records[0]["total_tokens"] = None
        audit_path.write_text("\n".join(map(json.dumps, records)) + "\n")
    elif corruption == "noncompleted_200":
        records[0]["request_state"] = "quarantined"
        audit_path.write_text("\n".join(map(json.dumps, records)) + "\n")
    elif corruption == "unknown_checkpoint":
        attempt_path = primary_dir / "attempt.json"
        attempt = json.loads(attempt_path.read_text())
        attempt["checkpoint"] = "seed-optimize"
        attempt_path.write_text(json.dumps(attempt))
    elif corruption == "attempt_count":
        expected_attempts = 3

    with pytest.raises(BaselineConfigError, match="cost audit"):
        audit_baseline_proxy_costs(tmp_path, expected_attempts=expected_attempts)
