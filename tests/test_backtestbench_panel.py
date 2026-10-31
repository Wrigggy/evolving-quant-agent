import json
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

import qea.backtestbench_panel as panel
from qea.benchmarks.backtestbench import project_public_task
from qea.evaluation import ArtifactRecord, TaskAttempt
from qea.executors.execution_record import WorkerExecution
from qea.executors.sandbox_runtime import SandboxInfrastructureError, SandboxResourceContract
from qea.worker_identity import hash_worker_directory


COMMIT = "1" * 40


def _fixture(tmp_path, categories=("metrics_calculation", "parameter_confirmation", "ticker_selection", "strategy_selection")):
    public, trusted, worker = (tmp_path / name for name in ("public", "trusted", "whole-H"))
    worker.mkdir()
    (worker / "agent.yaml").write_text(
        "max_iterations: 120\nmax_context_tokens: 200000\n"
        "llm_config:\n  model: ${env.LLM_MODEL}\n  max_tokens: 32000\n"
        "  temperature: 0.2\n  stream: true\n  timeout: 180\n",
    )
    (worker / "systemprompt.md").write_text("Use the complete shared research harness.\n")
    tasks = []
    for index, category in enumerate(categories):
        task = project_public_task(
            {"uuid": f"task{index}", "strategy": "Calculate the requested result.", "strategy_type": category},
            source_split="train" if index % 2 == 0 else "validation", source_row=index + 1,
        )
        data = public / "tasks" / task.task_id / "environment" / "data"
        data.mkdir(parents=True)
        (data / "public_task.json").write_text(json.dumps(task.public_record()))
        (data.parent.parent / "instruction.md").write_text(task.strategy)
        answer = trusted / "tasks" / task.task_id / "answer.json"
        answer.parent.mkdir(parents=True)
        answer.write_text(json.dumps({"uuid": task.source_id, "strategy_type": category, "answer": 1}))
        tasks.append(task)
    args = dict(
        config_path=tmp_path / "config.json", public_root=public, trusted_root=trusted,
        run_dir=tmp_path / "declared-panel", worker_dir=worker,
        task_ids=[task.task_id for task in tasks], benchmark_commit=COMMIT,
        worker_image_ref="sha256:worker", proxy_image_ref="sha256:proxy",
        harness_id="formal-whole-H", concurrency=4,
    )
    return args, tasks


def _audit(attempt_dir, cost=0.125):
    (attempt_dir / "proxy-audit.jsonl").write_text(json.dumps({
        "request_state": "completed", "failure_class": None, "upstream_status_code": 200,
        "input_tokens": 11, "output_tokens": 7, "total_tokens": 18, "provider_cost_usd": cost,
    }) + "\n")


class _Worker:
    metadata = {"model": "deepseek/deepseek-v4-flash-0731", "required_provider": "deepseek"}

    def __init__(self, barrier=None, failed=(), malformed=(), missing_cost=(), unclean=()):
        self.calls = []
        self.barrier = barrier
        self.failed = set(failed)
        self.malformed = set(malformed)
        self.missing_cost = set(missing_cost)
        self.unclean = set(unclean)

    def execute(self, *, attempt, task, worker_dir, run_dir):
        self.calls.append((task.task_id, Path(worker_dir)))
        if self.barrier:
            self.barrier.wait(timeout=5)
        attempt_dir = Path(run_dir) / "attempts" / attempt.attempt_id
        artifacts = attempt_dir / "artifacts"
        artifacts.mkdir()
        trace, command, final = (attempt_dir / name for name in ("raw-trace.jsonl", "worker-command.json", "final.txt"))
        trace.write_text('{"role":"assistant","content":"computed"}\n')
        command.write_text('{"exit_code":0}\n')
        final.write_text("The computation is complete.\n")
        if task.task_id not in self.missing_cost:
            _audit(attempt_dir)
        if task.task_id in self.failed:
            (artifacts / "partial.py").write_text("# retained failed attempt\n")
            raise SandboxInfrastructureError("worker.command", "HTTP 502 post-accept transport failure")
        answer = artifacts / "answer.json"
        answer.write_text("bare number 1" if task.task_id in self.malformed else '{"answer":1}\n')
        (artifacts / "computation.py").write_text("# actual code would be retained here\n")
        records = tuple(ArtifactRecord.from_file(path, root=artifacts) for path in sorted(artifacts.iterdir()))
        return WorkerExecution(
            attempt_id=attempt.attempt_id, artifact_dir=artifacts, artifacts=records,
            trace_uri=str(trace), log_uri=str(command), final_text_uri=str(final),
            summary={"outcome": "completed", "turns": 2, "tool_calls": 1},
            sandbox_id=f"worker-{task.task_id}", cleaned_up=task.task_id not in self.unclean,
        )


def test_complete_panel_concurrent_workers_checkpoint_each_result_and_keep_whole_h(tmp_path, monkeypatch):
    args, tasks = _fixture(tmp_path)
    worker = _Worker(threading.Barrier(4))
    monkeypatch.setattr(panel, "_prepare_panel_runtime", lambda **kwargs: worker)
    snapshots = []
    write = panel._atomic_private_json

    def checkpoint(path, value):
        if path.name == panel.STATE_FILE:
            snapshots.append(json.loads(json.dumps(value)))
        write(path, value)

    monkeypatch.setattr(panel, "_atomic_private_json", checkpoint)
    before = hash_worker_directory(args["worker_dir"])
    state = panel.run_backtestbench_panel(**args)
    assert state["status"] == "complete"
    assert len(worker.calls) == 4
    assert all(path == args["worker_dir"] for _, path in worker.calls)
    assert hash_worker_directory(args["worker_dir"]) == before
    assert state["worker_settings"]["max_iterations"] == 120
    assert state["worker_settings"]["max_context_tokens"] == 200000
    assert state["worker_settings"]["max_tokens"] == 32000
    assert state["worker_settings"]["temperature"] == 0.2
    assert {cell["public_task"]["source_split"] for cell in state["tasks"].values()} == {"train", "validation"}
    assert {snapshot["summary"]["returned_count"] for snapshot in snapshots} >= {0, 1, 2, 3, 4}
    assert state["summary"]["accuracy"] == 1.0
    assert state["summary"]["provider_cost_usd"] == 0.5
    assert state["summary"]["request_count"] == 4
    assert (args["run_dir"] / panel.RESULT_FILE).is_file()
    for task in tasks:
        cell = state["tasks"][task.task_id]
        result = cell["result"]
        assert result["worker_execution"]["cleaned_up"] is True
        assert result["worker_evidence"]["artifact_paths"] == ["answer.json", "computation.py"]
        assert result["official_evaluation"]["uuid"] == task.source_id
        assert "answer" not in result["official_evaluation"]
        assert (args["run_dir"] / "attempts" / cell["attempt"]["attempt_id"] / "attempt.json").is_file()
    # Retained terminal state is returned without touching a new runtime/model.
    monkeypatch.setattr(panel, "_prepare_panel_runtime", lambda **kwargs: pytest.fail("redraw"))
    assert panel.run_backtestbench_panel(**args) == state


def test_failed_transport_is_null_bad_completed_answer_is_zero_and_cost_stays_missing(tmp_path, monkeypatch):
    args, tasks = _fixture(tmp_path, ("metrics_calculation", "parameter_confirmation", "ticker_selection"))
    args["concurrency"] = 1
    worker = _Worker(failed=(tasks[0].task_id,), malformed=(tasks[1].task_id,), missing_cost=(tasks[0].task_id,))
    monkeypatch.setattr(panel, "_prepare_panel_runtime", lambda **kwargs: worker)
    state = panel.run_backtestbench_panel(**args)
    assert state["status"] == "complete_with_failures"
    results = [state["tasks"][task.task_id]["result"] for task in tasks]
    assert [result["reward"] for result in results] == [None, 0.0, 1.0]
    assert results[0]["status"] == "worker_failed"
    assert results[0]["worker_evidence"]["artifact_paths"] == ["partial.py"]
    assert results[1]["failure"] is None
    assert state["summary"]["accuracy"] is None
    assert state["summary"]["failed_count"] == 1
    assert state["summary"]["provider_cost_usd"] is None
    assert state["summary"]["known_provider_cost_usd"] == 0.25
    assert results[0]["proxy_cost"]["request_count"] is None
    # A provider failure gets bounded fresh attempts before it is retained.
    retries = state["tasks"][tasks[0].task_id]["provider_retries"]
    assert len(retries) == panel.PROVIDER_RETRY_LIMIT
    assert len({row["attempt_id"] for row in retries} | {results[0]["attempt_id"]}) == 3
    panel.run_backtestbench_panel(**args)
    assert len(worker.calls) == 3 + panel.PROVIDER_RETRY_LIMIT


def test_no_scoring_before_worker_cleanup(tmp_path, monkeypatch):
    args, tasks = _fixture(tmp_path, ("metrics_calculation",))
    worker = _Worker(unclean=(tasks[0].task_id,))
    monkeypatch.setattr(panel, "_prepare_panel_runtime", lambda **kwargs: worker)
    monkeypatch.setattr(panel, "grade_submission", lambda *args, **kwargs: pytest.fail("judged an active Worker"))
    state = panel.run_backtestbench_panel(**args)
    result = state["tasks"][tasks[0].task_id]["result"]
    assert result["reward"] is None
    assert result["status"] == "worker_failed"
    assert result["worker_execution"]["cleaned_up"] is False


def test_incomplete_or_changed_declaration_never_redraws(tmp_path, monkeypatch):
    args, _ = _fixture(tmp_path, ("metrics_calculation",))
    worker = _Worker()
    monkeypatch.setattr(panel, "_prepare_panel_runtime", lambda **kwargs: worker)
    state = panel.run_backtestbench_panel(**args)
    with pytest.raises(panel.BacktestBenchPanelError, match="different panel declaration"):
        panel.run_backtestbench_panel(**{**args, "checkpoint": "new-arm"})
    state["status"] = "running"
    panel._atomic_private_json(args["run_dir"] / panel.STATE_FILE, state)
    with pytest.raises(panel.BacktestBenchPanelError, match="no Worker is redrawn"):
        panel.run_backtestbench_panel(**args)
    assert len(worker.calls) == 1


def test_runtime_preparation_failure_retained_without_worker(tmp_path, monkeypatch):
    args, _ = _fixture(tmp_path, ("metrics_calculation",))

    def unavailable(**kwargs):
        raise SandboxInfrastructureError("backend.preflight", "required image is absent")

    monkeypatch.setattr(panel, "_prepare_panel_runtime", unavailable)
    state = panel.run_backtestbench_panel(**args)
    assert state["status"] == "preparation_failed"
    assert state["summary"]["returned_count"] == 0
    assert state["summary"]["accuracy"] is None
    assert state["summary"]["provider_cost_usd"] is None
    assert not (args["run_dir"] / "attempts").exists()
    assert panel.run_backtestbench_panel(**args) == state


def test_existing_runtime_composition_cleans_proxy_and_lease_before_return(tmp_path, monkeypatch):
    args, tasks = _fixture(tmp_path, ("metrics_calculation",))
    resource = SandboxResourceContract(2, 8192, 256, 3600, {"/tmp": 512, "/qea": 1024, "/app": 3072})
    events, executor_settings = [], []

    class Pool:
        @contextmanager
        def acquire(self, *args, **kwargs):
            events.append("lease-open")
            yield
            events.append("lease-closed")

    class Proxy:
        config = SimpleNamespace(
            resource_contract=resource, allowed_model="flash", required_provider="deepseek",
            fallback_providers=("baseten",), image_ref="proxy-image",
        )

        @contextmanager
        def open(self, **kwargs):
            events.append("proxy-open")
            yield SimpleNamespace(
                network_scope=kwargs["attempt_id"], allowed_model="flash", required_provider="deepseek",
                fallback_providers=("baseten",), immutable_image_ref="proxy-image",
                network_name="scoped-network", base_url="http://qea-model-proxy:8000/v1",
            )
            events.append("proxy-closed")

    real_worker = _Worker()

    class Executor:
        def __init__(self, **kwargs):
            executor_settings.append(kwargs)

        def execute(self, **kwargs):
            events.append("worker")
            kwargs.pop("model_env")
            return real_worker.execute(**kwargs)

    monkeypatch.setattr(panel, "SandboxNexAUExecutor", Executor)
    proposer = SimpleNamespace(backend=object(), proxy_manager=Proxy(), resource_pool=Pool())
    runtime = panel._PanelRuntime(proposer, args["public_root"], "worker-image", resource, 120.0, {})
    attempt = TaskAttempt.create(
        run_id="declared-panel", benchmark_commit=COMMIT, task_id=tasks[0].task_id,
        split="development", checkpoint="initial", worker_digest=hash_worker_directory(args["worker_dir"]),
    )
    attempt_dir = args["run_dir"] / "attempts" / attempt.attempt_id
    panel._atomic_private_json(attempt_dir / "attempt.json", asdict(attempt))
    execution = runtime.execute(attempt=attempt, task=tasks[0], worker_dir=args["worker_dir"], run_dir=args["run_dir"])
    assert execution.cleaned_up is True
    assert events == ["lease-open", "proxy-open", "worker", "proxy-closed", "lease-closed"]
    assert executor_settings[0]["public_task_root"] == args["public_root"]
    assert executor_settings[0]["expected_output_paths"] is None
    assert "trusted_root" not in executor_settings[0]
    assert (attempt_dir / "worker-execution.json").is_file()


def test_runtime_reserves_zip_copy_and_extraction_space_without_overwriting_h(tmp_path, monkeypatch):
    args, _ = _fixture(tmp_path, ("metrics_calculation",))
    limits = SimpleNamespace(pids_limit=256, timeout_seconds=5400, writable_tmpfs_mb={"/tmp": 512, "/qea": 512, "/app": 1024})
    proxy = SandboxResourceContract(1, 256, 128, 5400, {"/tmp": 128, "/run/qea-secrets": 16})
    config = SimpleNamespace(worker_limits=limits, proxy_resources=proxy, lease_timeout_seconds=120)
    calls = []
    monkeypatch.setattr(panel, "load_rootless_full_harness_config", lambda _: config)

    def prepare(**kwargs):
        calls.append(kwargs)
        return object(), {"model": "flash", "required_provider": "deepseek", "fallback_providers": ["baseten"]}

    monkeypatch.setattr(panel, "_prepare_revision_runtime", prepare)
    runtime = panel._prepare_panel_runtime(
        root=args["run_dir"], config_path=args["config_path"], public_root=args["public_root"],
        worker_image_ref="worker-image", proxy_image_ref="proxy-image", worker_timeout_seconds=None,
    )
    assert calls[0]["evolver_image_ref"] == "worker-image"
    assert runtime.worker_resources.cpu_count == 2
    assert runtime.worker_resources.memory_mb == 8192
    assert runtime.worker_resources.timeout_seconds == 5400
    assert dict(runtime.worker_resources.writable_tmpfs_mb) == {"/tmp": 512, "/qea": 1024, "/app": 3072}


def test_final_message_fallback_uses_the_official_json_extractor(tmp_path, monkeypatch):
    args, tasks = _fixture(tmp_path, ("metrics_calculation",))
    worker = _Worker()
    original = worker.execute

    def final_only(**kwargs):
        execution = original(**kwargs)
        (execution.artifact_dir / "answer.json").unlink()
        Path(execution.final_text_uri).write_text('Computed result: {"answer": 1}\n')
        return execution

    monkeypatch.setattr(worker, "execute", final_only)
    monkeypatch.setattr(panel, "_prepare_panel_runtime", lambda **kwargs: worker)
    state = panel.run_backtestbench_panel(**args)
    result = state["tasks"][tasks[0].task_id]["result"]
    assert result["reward"] == 1.0
    assert result["submission_uri"].endswith("/final.txt")


@pytest.mark.parametrize("scoring_mode,reward,scored_count", [
    ("official", None, 0), ("stock_selection_alias", 1.0, 1),
])
def test_legacy_stock_category_uses_only_declared_scoring_mode(tmp_path, monkeypatch, scoring_mode, reward, scored_count):
    args, tasks = _fixture(tmp_path, ("stock_selection",))
    args["scoring_mode"] = scoring_mode
    monkeypatch.setattr(panel, "_prepare_panel_runtime", lambda **kwargs: _Worker())
    state = panel.run_backtestbench_panel(**args)
    result = state["tasks"][tasks[0].task_id]["result"]
    assert result["reward"] == reward
    assert result["official_evaluation"]["scoring_mode"] == scoring_mode
    assert state["summary"]["scored_count"] == scored_count
    if scoring_mode == "stock_selection_alias":
        assert state["summary"]["categories"]["ticker_selection"]["accuracy"] == 1.0
    else:
        assert result["status"] == "unscored_category"
        assert state["summary"]["unscored_category_count"] == 1
