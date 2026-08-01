import hashlib
import json
from threading import Event
from types import SimpleNamespace

import pytest

from qea.evaluation import (
    ArtifactRecord,
    OfficialTaskScore,
    TaskAttempt,
    aggregate_domain_macro,
)


def _tasks():
    optimize = (
        SimpleNamespace(task_id="risk-train", domain="risk", lineage="risk-train-lineage"),
        SimpleNamespace(task_id="strategy-train", domain="strategy", lineage="strategy-lineage"),
    )
    held_out = (
        SimpleNamespace(task_id="fx-secret-holdout", domain="fx", lineage="fx-lineage"),
    )
    return optimize, held_out


def _seed_worker(tmp_path):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "agent.yaml").write_text("name: qf-worker\n")
    (seed / "systemprompt.md").write_text("Solve the task.\n")
    return seed


class ImprovingEvaluator:
    def __init__(self):
        self.calls = []

    def evaluate(self, *, worker_dir, tasks, split, checkpoint, run_dir):
        markers = (worker_dir / "systemprompt.md").read_text().count("IMPROVEMENT")
        self.calls.append((split, checkpoint, tuple(task.task_id for task in tasks), markers))
        if split == "held_out":
            reward = 0.91 if checkpoint == "seed-held-out" else min(1.0, 0.91 + 0.01 * markers)
        else:
            reward = min(1.0, 0.20 + 0.10 * markers)
        return aggregate_domain_macro([
            OfficialTaskScore(
                task_id=task.task_id,
                domain=task.domain,
                reward=reward,
                diagnostic_tags=(() if reward == 1.0 else ("tests_failed",)),
            )
            for task in tasks
        ])


@pytest.mark.parametrize("iterations", [1, 3, 5])
def test_runs_supported_iterations_and_holds_out_seed_and_final_only(tmp_path, iterations):
    from qea.loop_benchmark import BenchmarkEvolutionConfig, run_benchmark_evolution

    optimize, held_out = _tasks()
    evaluator = ImprovingEvaluator()
    proposer_payloads = []

    def proposer(candidate_dir, diagnosis, iteration, run_dir):
        proposer_payloads.append(json.dumps(diagnosis, sort_keys=True))
        prompt = candidate_dir / "systemprompt.md"
        prompt.write_text(prompt.read_text() + f"IMPROVEMENT {iteration}\n")
        return {"trace": {"turns": 1}, "final_text": "improved process"}

    config = BenchmarkEvolutionConfig(
        run_id=f"pilot-{iterations}",
        n_iters=iterations,
        results_dir=tmp_path / "results",
        seed_worker_dir=_seed_worker(tmp_path),
        noise_floor=0.0,
    )
    result = run_benchmark_evolution(
        config,
        optimize_tasks=optimize,
        held_out_tasks=held_out,
        benchmark_commit="0" * 40,
        evaluator=evaluator,
        proposer=proposer,
    )

    assert len(result.records) == iterations
    assert result.n_kept == iterations
    assert len(result.optimize_trajectory) == iterations + 1
    assert [call[1] for call in evaluator.calls if call[0] == "held_out"] == [
        "seed-held-out",
        "final-held-out",
    ]
    assert len([call for call in evaluator.calls if call[0] == "optimize"]) == iterations + 1
    assert all("fx-secret-holdout" not in payload for payload in proposer_payloads)
    assert all("0.91" not in payload for payload in proposer_payloads)
    assert result.held_out_final.overall >= result.held_out_seed.overall


def test_domain_regression_rejects_candidate_even_when_overall_improves(tmp_path):
    from qea.loop_benchmark import BenchmarkEvolutionConfig, run_benchmark_evolution

    optimize, held_out = _tasks()

    class RegressingEvaluator:
        def evaluate(self, *, worker_dir, tasks, split, checkpoint, run_dir):
            if split == "held_out":
                return aggregate_domain_macro([
                    OfficialTaskScore(task_id=tasks[0].task_id, domain="fx", reward=0.5)
                ])
            candidate = "candidate" in checkpoint
            rewards = {"risk-train": 0.3, "strategy-train": 0.9} if candidate else {
                "risk-train": 0.5, "strategy-train": 0.5,
            }
            return aggregate_domain_macro([
                OfficialTaskScore(task_id=task.task_id, domain=task.domain, reward=rewards[task.task_id])
                for task in tasks
            ])

    def proposer(candidate_dir, diagnosis, iteration, run_dir):
        prompt = candidate_dir / "systemprompt.md"
        prompt.write_text(prompt.read_text() + "RISKY CHANGE\n")
        return {}

    result = run_benchmark_evolution(
        BenchmarkEvolutionConfig(
            run_id="domain-gate",
            n_iters=3,
            results_dir=tmp_path / "results",
            seed_worker_dir=_seed_worker(tmp_path),
            noise_floor=0.0,
            max_domain_regression=0.0,
        ),
        optimize_tasks=optimize,
        held_out_tasks=held_out,
        benchmark_commit="0" * 40,
        evaluator=RegressingEvaluator(),
        proposer=proposer,
    )

    assert result.n_kept == 0
    assert all(record.kept is False for record in result.records)
    assert "domain regression" in result.records[0].reason
    assert all("repeats a rejected edit" in record.reason for record in result.records[1:])
    assert result.optimize_trajectory == (0.5,)


def test_config_rejects_nonpilot_iteration_count(tmp_path):
    from qea.loop_benchmark import BenchmarkEvolutionConfig, EvolutionConfigError

    with pytest.raises(EvolutionConfigError, match="1, 3, or 5"):
        BenchmarkEvolutionConfig(
            run_id="bad",
            n_iters=4,
            results_dir=tmp_path,
            seed_worker_dir=tmp_path,
        )


def test_config_maps_deprecated_concurrency_alias_and_rejects_conflicts(tmp_path):
    from qea.loop_benchmark import (
        LEGACY_SCHEDULER_IDENTITY_DIGEST,
        BenchmarkEvolutionConfig,
        EvolutionConfigError,
    )

    legacy = BenchmarkEvolutionConfig(
        run_id="legacy-concurrency",
        n_iters=1,
        results_dir=tmp_path,
        seed_worker_dir=tmp_path,
        concurrency=2,
        verifier_concurrency=1,
    )
    assert legacy.worker_concurrency == 2
    assert legacy.concurrency == 2
    assert legacy.verifier_concurrency == 1
    assert legacy.scheduler_identity_digest == LEGACY_SCHEDULER_IDENTITY_DIGEST

    with pytest.raises(EvolutionConfigError, match="conflicting worker concurrency"):
        BenchmarkEvolutionConfig(
            run_id="conflicting-concurrency",
            n_iters=1,
            results_dir=tmp_path,
            seed_worker_dir=tmp_path,
            concurrency=2,
            worker_concurrency=3,
        )


@pytest.mark.parametrize(
    "scheduler_identity_digest",
    ["typo", "A" * 64, "a" * 63, "g" * 64],
)
def test_config_rejects_invalid_scheduler_identity_digest(
    tmp_path,
    scheduler_identity_digest,
):
    from qea.loop_benchmark import BenchmarkEvolutionConfig, EvolutionConfigError

    with pytest.raises(
        EvolutionConfigError,
        match="scheduler_identity_digest must be 64 lowercase hex characters",
    ):
        BenchmarkEvolutionConfig(
            run_id="invalid-scheduler-identity",
            n_iters=1,
            results_dir=tmp_path,
            seed_worker_dir=tmp_path,
            scheduler_identity_digest=scheduler_identity_digest,
        )


def test_config_allows_scheduler_sentinel_only_for_legacy_concurrency(tmp_path):
    from qea.loop_benchmark import (
        LEGACY_SCHEDULER_IDENTITY_DIGEST,
        BenchmarkEvolutionConfig,
        EvolutionConfigError,
    )

    with pytest.raises(
        EvolutionConfigError,
        match="legacy scheduler identity sentinel requires deprecated concurrency",
    ):
        BenchmarkEvolutionConfig(
            run_id="new-scheduler-missing-identity",
            n_iters=1,
            results_dir=tmp_path,
            seed_worker_dir=tmp_path,
            worker_concurrency=2,
            scheduler_identity_digest=LEGACY_SCHEDULER_IDENTITY_DIGEST,
        )


def test_run_identity_records_stage_concurrency_and_scheduler_policy(tmp_path):
    from qea.loop_benchmark import (
        BenchmarkEvolutionConfig,
        EvolutionConfigError,
        run_benchmark_evolution,
    )

    optimize, held_out = _tasks()

    def proposer(candidate_dir, diagnosis, iteration, run_dir):
        prompt = candidate_dir / "systemprompt.md"
        prompt.write_text(prompt.read_text() + "IMPROVEMENT\n")
        return {}

    config = BenchmarkEvolutionConfig(
        run_id="scheduler-identity",
        n_iters=1,
        results_dir=tmp_path / "results",
        seed_worker_dir=_seed_worker(tmp_path),
        worker_concurrency=2,
        verifier_concurrency=1,
        scheduler_identity_digest="b" * 64,
        noise_floor=0.0,
    )
    result = run_benchmark_evolution(
        config,
        optimize_tasks=optimize,
        held_out_tasks=held_out,
        benchmark_commit="0" * 40,
        evaluator=ImprovingEvaluator(),
        proposer=proposer,
    )

    identity = json.loads((result.run_dir / "resume.json").read_text())["identity"]
    assert identity["worker_concurrency"] == 2
    assert identity["verifier_concurrency"] == 1
    assert identity["scheduler_identity_digest"] == "b" * 64

    changed_policy = BenchmarkEvolutionConfig(
        run_id="scheduler-identity",
        n_iters=1,
        results_dir=tmp_path / "results",
        seed_worker_dir=config.seed_worker_dir,
        worker_concurrency=2,
        verifier_concurrency=1,
        scheduler_identity_digest="c" * 64,
        noise_floor=0.0,
    )
    with pytest.raises(
        EvolutionConfigError,
        match="scheduler_identity_digest",
    ):
        run_benchmark_evolution(
            changed_policy,
            optimize_tasks=optimize,
            held_out_tasks=held_out,
            benchmark_commit="0" * 40,
            evaluator=ImprovingEvaluator(),
            proposer=proposer,
        )


def _execution_for(attempt, run_dir, task):
    from qea.executors.execution_record import WorkerExecution

    attempt_dir = run_dir / "attempts" / attempt.attempt_id
    artifact_dir = attempt_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / "answer.txt"
    artifact.write_text(f"{task.task_id}\n")
    trace = attempt_dir / "raw-trace.jsonl"
    log = attempt_dir / "worker-command.json"
    final = attempt_dir / "final.txt"
    trace.write_text("{}\n")
    log.write_text("{}\n")
    final.write_text("done\n")
    return WorkerExecution(
        attempt_id=attempt.attempt_id,
        artifact_dir=artifact_dir,
        artifacts=(ArtifactRecord.from_file(artifact, root=artifact_dir),),
        trace_uri=str(trace),
        log_uri=str(log),
        final_text_uri=str(final),
        summary={"files": 1},
        sandbox_id=f"sandbox-{task.task_id}",
        cleaned_up=True,
    )


def test_sandbox_evaluator_resume_reuses_worker_manifest_after_verifier_failure(tmp_path):
    from qea.loop_benchmark import QFBenchSandboxEvaluator

    tasks = (
        SimpleNamespace(task_id="task-a", domain="risk", lineage="a"),
        SimpleNamespace(task_id="task-b", domain="strategy", lineage="b"),
    )
    worker = _seed_worker(tmp_path)

    class FakeExecutor:
        def __init__(self):
            self.calls = []

        def execute(self, *, attempt, task, worker_dir, run_dir, model_env):
            self.calls.append(task.task_id)
            return _execution_for(attempt, run_dir, task)

    class InterruptingVerifier:
        def __init__(self):
            self.calls = []
            self.fail_task_b_once = True

        def verify(self, *, attempt, task, execution, run_dir):
            self.calls.append(task.task_id)
            if task.task_id == "task-b" and self.fail_task_b_once:
                self.fail_task_b_once = False
                raise RuntimeError("forced verifier interruption")
            return OfficialTaskScore(task_id=task.task_id, domain=task.domain, reward=0.5)

    executor = FakeExecutor()
    verifier = InterruptingVerifier()
    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit="0" * 40,
        run_id="attempt-resume",
        executor=executor,
        verifier=verifier,
        model_env={"LLM_API_KEY": "secret"},
        worker_concurrency=1,
        verifier_concurrency=1,
    )
    run_dir = tmp_path / "run"

    with pytest.raises(RuntimeError, match="forced verifier interruption"):
        evaluator.evaluate(
            worker_dir=worker,
            tasks=tasks,
            split="optimize",
            checkpoint="seed-optimize",
            run_dir=run_dir,
        )

    summary = evaluator.evaluate(
        worker_dir=worker,
        tasks=tasks,
        split="optimize",
        checkpoint="seed-optimize",
        run_dir=run_dir,
    )

    assert summary.overall == 0.5
    assert executor.calls.count("task-a") == 1
    assert verifier.calls.count("task-a") == 1
    assert executor.calls.count("task-b") == 1
    assert verifier.calls.count("task-b") == 2
    assert len(tuple((run_dir / "attempts").glob("*/worker-execution.json"))) == 2


def _persist_timeout_evidence(
    attempt_dir,
    *,
    command_changes=None,
    quarantine_changes=None,
    write_command=True,
    write_quarantine=True,
    write_audit=False,
):
    command = {
        "exit_code": 124,
        "stderr": "",
        "stdout": "",
        "timed_out": True,
    }
    command.update(command_changes or {})
    quarantine = {
        "reason": "audit_download_or_validation_failed",
        "request_state": "quarantined",
        "schema_version": 1,
    }
    quarantine.update(quarantine_changes or {})
    command_bytes = (json.dumps(command, sort_keys=True) + "\n").encode()
    quarantine_bytes = (json.dumps(quarantine, sort_keys=True) + "\n").encode()
    if write_command:
        (attempt_dir / "worker-command.json").write_bytes(command_bytes)
    if write_quarantine:
        (attempt_dir / "proxy-audit.quarantined.json").write_bytes(
            quarantine_bytes
        )
    if write_audit:
        (attempt_dir / "proxy-audit.jsonl").write_text("{}\n")
    return command_bytes, quarantine_bytes


def test_sandbox_evaluator_recovers_persisted_timeout_without_external_calls(
    tmp_path,
):
    from qea.loop_benchmark import QFBenchSandboxEvaluator, hash_worker_directory

    task = SimpleNamespace(task_id="slow-task", domain="derivatives", lineage="slow")
    worker = _seed_worker(tmp_path)
    attempt = TaskAttempt.create(
        run_id="timeout-resume",
        benchmark_commit="0" * 40,
        task_id=task.task_id,
        split="optimize",
        checkpoint="seed-optimize",
        worker_digest=hash_worker_directory(worker),
    )
    run_dir = tmp_path / "run"
    attempt_dir = run_dir / "attempts" / attempt.attempt_id
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "attempt.json").write_text(json.dumps(attempt.__dict__))
    command_bytes, quarantine_bytes = _persist_timeout_evidence(attempt_dir)

    class RefusingExecutor:
        def execute(self, **kwargs):
            raise AssertionError("persisted timeout must not resample the model")

    class RefusingVerifier:
        def verify(self, **kwargs):
            raise AssertionError("persisted timeout must not enter the verifier")

    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit="0" * 40,
        run_id="timeout-resume",
        executor=RefusingExecutor(),
        verifier=RefusingVerifier(),
        model_env={},
        worker_concurrency=1,
        verifier_concurrency=1,
    )

    summary = evaluator.evaluate(
        worker_dir=worker,
        tasks=(task,),
        split="optimize",
        checkpoint="seed-optimize",
        run_dir=run_dir,
    )

    assert summary.overall == 0.0
    assert summary.scores[0].diagnostic_tags == ("timeout",)
    score = json.loads((attempt_dir / "completed-score.json").read_text())
    assert score["reward"] == 0.0
    assert score["log_uri"] == str(
        (attempt_dir / "worker-command.json").resolve()
    )
    recovery = json.loads((attempt_dir / "timeout-recovery.json").read_text())
    assert recovery == {
        "attempt_id": attempt.attempt_id,
        "command_sha256": hashlib.sha256(command_bytes).hexdigest(),
        "outcome": "official_worker_timeout_zero",
        "quarantine_reason": "audit_download_or_validation_failed",
        "quarantine_sha256": hashlib.sha256(quarantine_bytes).hexdigest(),
        "schema_version": 1,
    }


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"write_command": False}, "paired"),
        ({"write_quarantine": False}, "paired"),
        ({"command_changes": {"timed_out": False}}, "timed_out"),
        ({"command_changes": {"exit_code": 1}}, "exit code"),
        ({"command_changes": {"extra": "field"}}, "schema"),
        ({"write_audit": True}, "canonical proxy audit"),
        (
            {"quarantine_changes": {"reason": "different_reason"}},
            "quarantine reason",
        ),
    ],
)
def test_sandbox_evaluator_rejects_invalid_persisted_timeout_before_external_calls(
    tmp_path,
    changes,
    message,
):
    from qea.executors.execution_record import WorkerExecutionError
    from qea.loop_benchmark import QFBenchSandboxEvaluator, hash_worker_directory

    task = SimpleNamespace(task_id="slow-task", domain="derivatives", lineage="slow")
    worker = _seed_worker(tmp_path)
    attempt = TaskAttempt.create(
        run_id="invalid-timeout-resume",
        benchmark_commit="0" * 40,
        task_id=task.task_id,
        split="optimize",
        checkpoint="seed-optimize",
        worker_digest=hash_worker_directory(worker),
    )
    run_dir = tmp_path / "run"
    attempt_dir = run_dir / "attempts" / attempt.attempt_id
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "attempt.json").write_text(json.dumps(attempt.__dict__))
    _persist_timeout_evidence(attempt_dir, **changes)

    class RefusingExecutor:
        def execute(self, **kwargs):
            raise AssertionError("invalid timeout evidence must fail before execution")

    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit="0" * 40,
        run_id="invalid-timeout-resume",
        executor=RefusingExecutor(),
        verifier=SimpleNamespace(),
        model_env={},
        worker_concurrency=1,
        verifier_concurrency=1,
    )

    with pytest.raises(WorkerExecutionError, match=message):
        evaluator.evaluate(
            worker_dir=worker,
            tasks=(task,),
            split="optimize",
            checkpoint="seed-optimize",
            run_dir=run_dir,
        )


def test_sandbox_evaluator_rejects_mismatched_persisted_attempt_identity(tmp_path):
    from qea.loop_benchmark import (
        EvolutionConfigError,
        QFBenchSandboxEvaluator,
        hash_worker_directory,
    )

    task = SimpleNamespace(task_id="task-a", domain="risk", lineage="a")
    worker = _seed_worker(tmp_path)
    attempt = TaskAttempt.create(
        run_id="attempt-identity",
        benchmark_commit="0" * 40,
        task_id=task.task_id,
        split="optimize",
        checkpoint="seed-optimize",
        worker_digest=hash_worker_directory(worker),
    )
    attempt_dir = tmp_path / "run" / "attempts" / attempt.attempt_id
    attempt_dir.mkdir(parents=True)
    mismatched = dict(attempt.__dict__)
    mismatched["split"] = "held_out"
    (attempt_dir / "attempt.json").write_text(json.dumps(mismatched))

    class RefusingExecutor:
        def execute(self, **kwargs):
            raise AssertionError("mismatched attempt must not execute")

    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit="0" * 40,
        run_id="attempt-identity",
        executor=RefusingExecutor(),
        verifier=SimpleNamespace(),
        model_env={},
        worker_concurrency=1,
        verifier_concurrency=1,
    )

    with pytest.raises(EvolutionConfigError, match="persisted attempt identity mismatch"):
        evaluator.evaluate(
            worker_dir=worker,
            tasks=(task,),
            split="optimize",
            checkpoint="seed-optimize",
            run_dir=tmp_path / "run",
        )


def test_sandbox_evaluator_uses_two_live_stages_and_restores_input_order(tmp_path):
    from qea.loop_benchmark import QFBenchE2BEvaluator, QFBenchSandboxEvaluator

    assert QFBenchE2BEvaluator is QFBenchSandboxEvaluator

    verifier_a_started = Event()
    worker_b_started = Event()
    verifier_b_finished = Event()
    tasks = (
        SimpleNamespace(task_id="task-a", domain="risk", lineage="a"),
        SimpleNamespace(task_id="task-b", domain="strategy", lineage="b"),
    )

    class BarrierExecutor:
        def execute(self, *, attempt, task, worker_dir, run_dir, model_env):
            if task.task_id == "task-b":
                assert verifier_a_started.wait(2), (
                    "worker stage waited for all workers before starting verification"
                )
                worker_b_started.set()
            return _execution_for(attempt, run_dir, task)

    class BarrierVerifier:
        def verify(self, *, attempt, task, execution, run_dir):
            if task.task_id == "task-a":
                verifier_a_started.set()
                assert worker_b_started.wait(2), (
                    "verification consumed the only worker-concurrency slot"
                )
                assert verifier_b_finished.wait(2), (
                    "verifier concurrency did not allow task-b to finish first"
                )
                reward = 0.25
            else:
                verifier_b_finished.set()
                reward = 0.75
            return OfficialTaskScore(
                task_id=task.task_id,
                domain=task.domain,
                reward=reward,
            )

    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit="0" * 40,
        run_id="two-stage",
        executor=BarrierExecutor(),
        verifier=BarrierVerifier(),
        model_env={},
        worker_concurrency=1,
        verifier_concurrency=2,
    )

    summary = evaluator.evaluate(
        worker_dir=_seed_worker(tmp_path),
        tasks=tasks,
        split="optimize",
        checkpoint="seed-optimize",
        run_dir=tmp_path / "run",
    )

    assert [score.task_id for score in summary.scores] == ["task-a", "task-b"]
    assert [score.reward for score in summary.scores] == [0.25, 0.75]


@pytest.mark.parametrize("phase", ["worker.create", "worker.upload", "worker.proxy"])
def test_sandbox_evaluator_propagates_worker_infrastructure_failures(tmp_path, phase):
    from qea.executors.sandbox_nexau import SandboxInfrastructureError
    from qea.loop_benchmark import QFBenchSandboxEvaluator

    class FailingExecutor:
        def execute(self, **kwargs):
            raise SandboxInfrastructureError(phase, "forced infrastructure failure")

    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit="0" * 40,
        run_id="infrastructure-failure",
        executor=FailingExecutor(),
        verifier=SimpleNamespace(),
        model_env={},
        worker_concurrency=1,
        verifier_concurrency=1,
    )

    with pytest.raises(SandboxInfrastructureError) as raised:
        evaluator.evaluate(
            worker_dir=_seed_worker(tmp_path),
            tasks=(SimpleNamespace(task_id="task-a", domain="risk", lineage="a"),),
            split="optimize",
            checkpoint="seed-optimize",
            run_dir=tmp_path / "run",
        )
    assert raised.value.phase == phase


def test_sandbox_evaluator_retains_inflight_failure_during_shutdown(
    tmp_path,
    monkeypatch,
):
    from concurrent.futures import ThreadPoolExecutor as RealThreadPoolExecutor

    import qea.loop_benchmark as loop_benchmark
    from qea.executors.sandbox_nexau import SandboxInfrastructureError

    shutdown_started = Event()
    secondary_started = Event()

    class SignalingThreadPoolExecutor(RealThreadPoolExecutor):
        def shutdown(self, wait=True, *, cancel_futures=False):
            shutdown_started.set()
            return super().shutdown(wait=wait, cancel_futures=cancel_futures)

    monkeypatch.setattr(
        loop_benchmark,
        "ThreadPoolExecutor",
        SignalingThreadPoolExecutor,
    )

    tasks = (
        SimpleNamespace(task_id="task-a", domain="risk", lineage="a"),
        SimpleNamespace(task_id="task-b", domain="strategy", lineage="b"),
    )

    class FailingExecutor:
        def execute(self, *, task, **kwargs):
            if task.task_id == "task-a":
                assert secondary_started.wait(2)
                raise SandboxInfrastructureError(
                    "worker.create",
                    "primary infrastructure failure",
                )
            secondary_started.set()
            assert shutdown_started.wait(2)
            raise SandboxInfrastructureError(
                "worker.upload",
                "secondary infrastructure failure during shutdown",
            )

    evaluator = loop_benchmark.QFBenchSandboxEvaluator(
        benchmark_commit="0" * 40,
        run_id="concurrent-failures",
        executor=FailingExecutor(),
        verifier=SimpleNamespace(),
        model_env={},
        worker_concurrency=2,
        verifier_concurrency=1,
    )

    with pytest.raises(
        SandboxInfrastructureError,
        match="primary infrastructure failure",
    ) as raised:
        evaluator.evaluate(
            worker_dir=_seed_worker(tmp_path),
            tasks=tasks,
            split="optimize",
            checkpoint="seed-optimize",
            run_dir=tmp_path / "run",
        )

    assert raised.value.phase == "worker.create"
    secondary = raised.value.evaluation_secondary_failures
    assert len(secondary) == 1
    assert secondary[0].stage == "worker"
    assert secondary[0].index == 1
    assert secondary[0].task_id == "task-b"
    assert isinstance(secondary[0].error, SandboxInfrastructureError)
    assert secondary[0].error.phase == "worker.upload"


def test_sandbox_evaluator_propagates_verifier_infrastructure_failure(tmp_path):
    from qea.executors.sandbox_nexau import SandboxInfrastructureError
    from qea.loop_benchmark import QFBenchSandboxEvaluator

    task = SimpleNamespace(task_id="task-a", domain="risk", lineage="a")

    class Executor:
        def execute(self, *, attempt, task, worker_dir, run_dir, model_env):
            return _execution_for(attempt, run_dir, task)

    class FailingVerifier:
        def verify(self, **kwargs):
            raise SandboxInfrastructureError(
                "verifier.command", "forced infrastructure failure"
            )

    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit="0" * 40,
        run_id="verifier-failure",
        executor=Executor(),
        verifier=FailingVerifier(),
        model_env={},
        worker_concurrency=1,
        verifier_concurrency=1,
    )
    run_dir = tmp_path / "run"

    with pytest.raises(SandboxInfrastructureError) as raised:
        evaluator.evaluate(
            worker_dir=_seed_worker(tmp_path),
            tasks=(task,),
            split="optimize",
            checkpoint="seed-optimize",
            run_dir=run_dir,
        )
    assert raised.value.phase == "verifier.command"
    assert len(tuple((run_dir / "attempts").glob("*/worker-execution.json"))) == 1


def test_sandbox_evaluator_rejects_verifier_score_identity_mismatch(tmp_path):
    from qea.loop_benchmark import EvolutionConfigError, QFBenchSandboxEvaluator

    task = SimpleNamespace(task_id="task-a", domain="risk", lineage="a")

    class Executor:
        def execute(self, *, attempt, task, worker_dir, run_dir, model_env):
            return _execution_for(attempt, run_dir, task)

    class WrongVerifier:
        def verify(self, **kwargs):
            return OfficialTaskScore(
                task_id="different-task",
                domain="risk",
                reward=1.0,
            )

    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit="0" * 40,
        run_id="verifier-mismatch",
        executor=Executor(),
        verifier=WrongVerifier(),
        model_env={},
        worker_concurrency=1,
        verifier_concurrency=1,
    )

    with pytest.raises(EvolutionConfigError, match="verifier score identity mismatch"):
        evaluator.evaluate(
            worker_dir=_seed_worker(tmp_path),
            tasks=(task,),
            split="optimize",
            checkpoint="seed-optimize",
            run_dir=tmp_path / "run",
        )


def test_e2b_evaluator_records_worker_command_timeout_as_zero_reward(tmp_path):
    from qea.executors.execution_record import WorkerBehaviorTimeout
    from qea.loop_benchmark import QFBenchSandboxEvaluator

    task = SimpleNamespace(task_id="slow-task", domain="derivatives", lineage="slow")
    worker = _seed_worker(tmp_path)

    class TimeoutExecutor:
        def execute(self, **kwargs):
            raise WorkerBehaviorTimeout("worker exceeded the official agent timeout")

    class RefusingVerifier:
        def verify(self, **kwargs):
            raise AssertionError("a timed-out worker must not enter the verifier")

    evaluator = QFBenchSandboxEvaluator(
        benchmark_commit="0" * 40,
        run_id="timeout-score",
        executor=TimeoutExecutor(),
        verifier=RefusingVerifier(),
        model_env={"LLM_API_KEY": "secret"},
        worker_concurrency=1,
        verifier_concurrency=1,
    )
    run_dir = tmp_path / "run"

    summary = evaluator.evaluate(
        worker_dir=worker,
        tasks=(task,),
        split="optimize",
        checkpoint="seed-optimize",
        run_dir=run_dir,
    )

    assert summary.overall == 0.0
    assert summary.scores[0].diagnostic_tags == ("timeout",)
    completed = tuple((run_dir / "attempts").glob("*/completed-score.json"))
    assert len(completed) == 1
    assert json.loads(completed[0].read_text())["reward"] == 0.0
    attempt_identity = completed[0].with_name("attempt.json")
    payload = json.loads(attempt_identity.read_text())
    assert payload["task_id"] == "slow-task"
    assert payload["split"] == "optimize"
    assert payload["checkpoint"] == "seed-optimize"
    assert payload["attempt_id"] == completed[0].parent.name
