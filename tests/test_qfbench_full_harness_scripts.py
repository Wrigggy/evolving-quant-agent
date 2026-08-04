import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


class FakeRootlessImportBackend:
    backend_name = "rootless-docker"

    def __init__(self):
        self.network = None
        self.specs = []
        self.uploads = []
        self.commands = []
        self.killed = []
        self.removed_networks = []

    def create_internal_network(self, run_id, *, network_scope=None):
        self.network = SimpleNamespace(
            backend=self.backend_name,
            native_id="a" * 64,
            name="qea-import-network",
            run_id=run_id,
            network_scope=network_scope,
            identity_sha256="b" * 64,
        )
        return self.network

    def create(self, spec):
        self.specs.append(spec)
        return SimpleNamespace(
            backend=self.backend_name,
            native_id="c" * 64,
            immutable_image_ref=spec.image_ref,
            spec_sha256=spec.spec_sha256,
        )

    def start(self, handle):
        self.started = handle.native_id

    def put_bytes(self, handle, path, payload):
        self.uploads.append((handle.native_id, path, payload))

    def run(self, handle, argv, *, environment, timeout_seconds):
        self.commands.append((tuple(argv), dict(environment), timeout_seconds))
        stdout = (
            "IMPORT_OK\n"
            if any(value.endswith("import_canary.py") for value in argv)
            else ""
        )
        return SimpleNamespace(
            exit_code=0,
            stdout=stdout,
            stderr="",
            timed_out=False,
        )

    def kill(self, native_id):
        self.killed.append(native_id)
        return SimpleNamespace(native_id=native_id, outcome="killed")

    def remove_internal_network(self, handle):
        self.removed_networks.append(handle.native_id)
        return "killed"

    def list(self, labels):
        return ()


def test_full_harness_canary_script_is_directly_invokable():
    proc = subprocess.run(
        [sys.executable, "scripts/smoke_qfbench_full_harness.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "import" in proc.stdout
    assert "paid-rich" in proc.stdout
    assert "paid-baseline-batch" in proc.stdout
    assert "paid-provider-batch" in proc.stdout
    assert "--acceptance-provider" in proc.stdout
    assert "--executor {rootless-docker,e2b}" in proc.stdout
    assert "--rootless-config" in proc.stdout
    assert "--rootless-image-set-manifest" in proc.stdout


def test_paid_baseline_batch_requires_exact_epoch_two_standard_panel():
    from scripts.smoke_qfbench_full_harness import (
        PAID_BASELINE_BATCH_TASK_IDS,
        select_paid_baseline_batch_tasks,
    )

    expected = (
        "ohlc-realized-vol-estimators",
        "momentum-backtest",
        "evt-pot-var",
        "geometric-mean-reverting-jd",
        "option-put-call-parity-forward-audit",
        "sma-crossover-spy",
        "corporate-action-adjustment",
        "earnings-surprise-calculator",
        "fama-french-factor-model-new",
        "credit-migration-matrix",
        "zero-coupon-bootstrapping",
        "copula-sampling-rank-correlation",
    )
    manifest = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/qfbench/MANIFEST_85_BASELINE.json"
        ).read_text()
    )
    primary = {
        item["task_id"]: item for item in manifest["baseline"]["primary"]
    }
    for task_id in (
        "ohlc-realized-vol-estimators",
        "geometric-mean-reverting-jd",
    ):
        assert primary[task_id]["resource_source"] == "qea_fallback"
        assert primary[task_id]["resources"]["cpus"] == 2
        assert primary[task_id]["resources"]["memory_mb"] == 4096

    tasks = tuple(
        SimpleNamespace(task_id=task_id, cpus=2, memory_mb=4096)
        for task_id in expected
    )
    snapshot = SimpleNamespace(
        primary=SimpleNamespace(tasks=tasks, task_ids=expected)
    )
    config = SimpleNamespace(
        scheduler_epoch="repetitions-02-through-05",
        worker_concurrency=12,
        verifier_concurrency=3,
        worker_launch_interval_seconds=2,
        allowed_model="deepseek/deepseek-v4-flash-0731",
        required_provider="deepseek",
    )

    selected = select_paid_baseline_batch_tasks(
        snapshot, config=config, executor="rootless-docker"
    )

    assert PAID_BASELINE_BATCH_TASK_IDS == expected
    assert tuple(task.task_id for task in selected) == expected

    with pytest.raises(ValueError, match="two-second worker launch ramp"):
        select_paid_baseline_batch_tasks(
            snapshot,
            config=SimpleNamespace(
                **{
                    **config.__dict__,
                    "worker_launch_interval_seconds": 0,
                }
            ),
            executor="rootless-docker",
        )

    with pytest.raises(ValueError, match="V4 Flash 0731"):
        select_paid_baseline_batch_tasks(
            snapshot,
            config=SimpleNamespace(
                **{
                    **config.__dict__,
                    "allowed_model": "deepseek/deepseek-v4-flash",
                }
            ),
            executor="rootless-docker",
        )

    bad = (SimpleNamespace(**{**tasks[0].__dict__, "cpus": 4}), *tasks[1:])
    with pytest.raises(ValueError, match="2 CPU/4096 MiB"):
        select_paid_baseline_batch_tasks(
            SimpleNamespace(
                primary=SimpleNamespace(
                    tasks=bad,
                    task_ids=expected,
                )
            ),
            config=config,
            executor="rootless-docker",
        )


def test_paid_provider_batch_accepts_only_an_explicit_matching_nonofficial_provider():
    from scripts.smoke_qfbench_full_harness import (
        PAID_BASELINE_BATCH_TASK_IDS,
        select_paid_baseline_batch_tasks,
    )

    tasks = tuple(
        SimpleNamespace(task_id=task_id, cpus=2, memory_mb=4096)
        for task_id in PAID_BASELINE_BATCH_TASK_IDS
    )
    snapshot = SimpleNamespace(
        primary=SimpleNamespace(
            tasks=tasks,
            task_ids=PAID_BASELINE_BATCH_TASK_IDS,
        )
    )
    cloudflare = SimpleNamespace(
        scheduler_epoch="repetitions-02-through-05",
        worker_concurrency=12,
        verifier_concurrency=3,
        worker_launch_interval_seconds=2,
        allowed_model="deepseek/deepseek-v4-flash-0731",
        required_provider="cloudflare",
    )

    selected = select_paid_baseline_batch_tasks(
        snapshot,
        config=cloudflare,
        executor="rootless-docker",
        expected_provider="cloudflare",
        formal_scoring_eligible=False,
    )

    assert tuple(task.task_id for task in selected) == PAID_BASELINE_BATCH_TASK_IDS
    with pytest.raises(ValueError, match="official provider"):
        select_paid_baseline_batch_tasks(
            snapshot,
            config=cloudflare,
            executor="rootless-docker",
        )
    with pytest.raises(ValueError, match="must differ from the official provider"):
        select_paid_baseline_batch_tasks(
            snapshot,
            config=SimpleNamespace(
                **{**cloudflare.__dict__, "required_provider": "deepseek"}
            ),
            executor="rootless-docker",
            expected_provider="deepseek",
            formal_scoring_eligible=False,
        )


@pytest.mark.parametrize("provider", [None, "deepseek"])
def test_paid_provider_batch_cli_requires_nonofficial_provider_before_loading_data(
    tmp_path, provider
):
    from scripts import smoke_qfbench_full_harness as smoke

    argv = [
        "--executor",
        "rootless-docker",
        "--mode",
        "paid-provider-batch",
        "--qfbench-root",
        str(tmp_path / "missing-qfbench"),
        "--rootless-config",
        str(tmp_path / "missing-config.json"),
        "--rootless-image-set-manifest",
        str(tmp_path / "missing-images.json"),
        "--approve-external-run",
    ]
    if provider is not None:
        argv.extend(["--acceptance-provider", provider])

    with pytest.raises(ValueError, match="acceptance provider"):
        smoke.main(argv)


def test_paid_baseline_batch_evaluates_once_without_evolver_or_feedback(
    monkeypatch, tmp_path
):
    from scripts import smoke_qfbench_full_harness as smoke

    tasks = tuple(
        SimpleNamespace(
            task_id=task_id,
            cpus=2,
            memory_mb=4096,
            domain="domain-a",
        )
        for task_id in smoke.PAID_BASELINE_BATCH_TASK_IDS
    )
    snapshot = SimpleNamespace(
        commit="0" * 40,
        primary=SimpleNamespace(
            tasks=tasks,
            task_ids=smoke.PAID_BASELINE_BATCH_TASK_IDS,
        ),
    )
    config = SimpleNamespace(
        scheduler_epoch="repetitions-02-through-05",
        worker_concurrency=12,
        verifier_concurrency=3,
        worker_launch_interval_seconds=2,
        allowed_model="deepseek/deepseek-v4-flash-0731",
        required_provider="deepseek",
    )
    calls = []

    class Evaluator:
        def evaluate(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                task_mean=0.5,
                overall=0.5,
                scores=tuple(
                    SimpleNamespace(
                        task_id=task.task_id,
                        reward=0.5,
                        diagnostic_tags=(),
                    )
                    for task in tasks
                ),
            )

    runtime = SimpleNamespace(
        evaluator=Evaluator(),
        backend=SimpleNamespace(list=lambda labels: ()),
        image_identity_digest="1" * 64,
        scheduler_identity_digest="2" * 64,
        runtime_identity_digest="3" * 64,
    )
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "agent.yaml").write_text("type: agent\n")
    monkeypatch.setattr(
        smoke,
        "audit_fixed_checkpoint_proxy_costs",
        lambda *args, **kwargs: {
            "request_count": 12,
            "provider_cost_usd": None,
            "cost_complete": False,
            "provider_cost_is_lower_bound": True,
        },
        raising=False,
    )
    monkeypatch.setattr(
        smoke,
        "audit_paid_baseline_lifecycles",
        lambda *args, **kwargs: {
            "worker_overlap": 12,
            "cleaned_up": True,
            "verifier_networkless": True,
            "worker_proxy_only": True,
        },
        raising=False,
    )
    monkeypatch.setattr(
        smoke,
        "audit_paid_provider_records",
        lambda *args, **kwargs: {
            "request_count": 12,
            "latency_ms": {"mean": 100.0, "p90": 100.0},
            "model": "deepseek/deepseek-v4-flash-0731",
        },
        raising=False,
    )

    status = smoke.run_paid_baseline_batch(
        runtime=runtime,
        config=config,
        snapshot=snapshot,
        run_dir=tmp_path / "run",
        seed_worker=seed,
    )

    assert len(calls) == 1
    assert calls[0]["tasks"] == tasks
    assert calls[0]["split"] == "baseline_primary"
    assert calls[0]["checkpoint"] == "epoch-02-concurrency-canary"
    assert status["worker_overlap"] == 12
    assert status["worker_launch_interval_seconds"] == 2
    assert status["feedback_used"] is False
    assert status["evolver_used"] is False
    assert status["formal_scoring_eligible"] is True
    assert status["claim_boundary"] == "official-provider concurrency gate"
    assert status["cost_audit"]["cost_complete"] is False


def test_paid_provider_batch_result_is_infrastructure_only(monkeypatch, tmp_path):
    from scripts import smoke_qfbench_full_harness as smoke

    tasks = tuple(
        SimpleNamespace(
            task_id=task_id,
            cpus=2,
            memory_mb=4096,
            domain="domain-a",
        )
        for task_id in smoke.PAID_BASELINE_BATCH_TASK_IDS
    )
    snapshot = SimpleNamespace(
        commit="0" * 40,
        primary=SimpleNamespace(
            tasks=tasks,
            task_ids=smoke.PAID_BASELINE_BATCH_TASK_IDS,
        ),
    )
    config = SimpleNamespace(
        scheduler_epoch="repetitions-02-through-05",
        worker_concurrency=12,
        verifier_concurrency=3,
        worker_launch_interval_seconds=2,
        allowed_model="deepseek/deepseek-v4-flash-0731",
        required_provider="cloudflare",
    )

    class Evaluator:
        def evaluate(self, **kwargs):
            return SimpleNamespace(
                task_mean=0.5,
                overall=0.5,
                scores=tuple(
                    SimpleNamespace(
                        task_id=task.task_id,
                        reward=0.5,
                        diagnostic_tags=(),
                    )
                    for task in tasks
                ),
            )

    runtime = SimpleNamespace(
        evaluator=Evaluator(),
        backend=SimpleNamespace(list=lambda labels: ()),
        image_identity_digest="1" * 64,
        scheduler_identity_digest="2" * 64,
        runtime_identity_digest="3" * 64,
    )
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "agent.yaml").write_text("type: agent\n")
    monkeypatch.setattr(
        smoke,
        "audit_fixed_checkpoint_proxy_costs",
        lambda *args, **kwargs: {
            "request_count": 12,
            "provider_cost_usd": "0.12",
            "cost_complete": True,
            "provider_cost_is_lower_bound": False,
        },
    )
    monkeypatch.setattr(
        smoke,
        "audit_paid_baseline_lifecycles",
        lambda *args, **kwargs: {"worker_overlap": 12},
    )
    monkeypatch.setattr(
        smoke,
        "audit_paid_provider_records",
        lambda *args, **kwargs: {
            "request_count": 12,
            "latency_ms": {"mean": 100.0, "p90": 100.0},
            "model": "deepseek/deepseek-v4-flash-0731",
        },
    )

    status = smoke.run_paid_baseline_batch(
        runtime=runtime,
        config=config,
        snapshot=snapshot,
        run_dir=tmp_path / "run",
        seed_worker=seed,
        mode="paid-provider-batch",
        expected_provider="cloudflare",
        formal_scoring_eligible=False,
    )

    assert status["mode"] == "paid-provider-batch"
    assert status["provider"] == "cloudflare"
    assert status["formal_scoring_eligible"] is False
    assert status["claim_boundary"] == "infrastructure-only provider batch"


@pytest.mark.parametrize(
    "model",
    [
        "deepseek/deepseek-v4-flash-0731",
        "deepseek/deepseek-v4-flash-20260731",
    ],
)
def test_v4_flash_0731_canary_accepts_only_registered_and_canonical_model_ids(
    model,
):
    from scripts.qfbench_v4_flash_0731_provider_canary import (
        validate_generation_route,
    )

    validate_generation_route(provider="DeepSeek", model=model)
    with pytest.raises(RuntimeError, match="unexpected provider metadata"):
        validate_generation_route(provider="DeepInfra", model=model)
    with pytest.raises(RuntimeError, match="unexpected model metadata"):
        validate_generation_route(
            provider="DeepSeek",
            model="deepseek/deepseek-v4-flash-20260423",
        )


@pytest.mark.parametrize(
    ("mode", "acceptance_provider"),
    [
        ("paid-baseline-batch", None),
        ("paid-provider-batch", "cloudflare"),
    ],
)
def test_rootless_paid_baseline_runtime_is_built_without_evolver(
    monkeypatch, tmp_path, mode, acceptance_provider
):
    import qea.rootless_full_harness as rootless_module
    from scripts import smoke_qfbench_full_harness as smoke

    config = SimpleNamespace()
    runtime = SimpleNamespace(close=lambda: None)
    captured = {}

    def build_runtime(**kwargs):
        captured.update(kwargs)
        return runtime

    monkeypatch.setattr(
        rootless_module,
        "load_rootless_full_harness_config",
        lambda path: config,
    )
    monkeypatch.setattr(
        rootless_module,
        "build_rootless_full_harness_runtime",
        build_runtime,
    )
    monkeypatch.setattr(
        smoke, "select_paid_baseline_batch_tasks", lambda *args, **kwargs: ()
    )
    monkeypatch.setattr(
        smoke,
        "run_paid_baseline_batch",
        lambda **kwargs: {"mode": mode},
    )
    args = SimpleNamespace(
        mode=mode,
        acceptance_provider=acceptance_provider,
        executor="rootless-docker",
        rootless_config=tmp_path / "rootless.json",
        rootless_image_set_manifest=tmp_path / "images.json",
        run_id="paid-batch",
        results_dir=tmp_path / "results",
    )
    snapshot = SimpleNamespace(commit="0" * 40, tasks=())

    result = smoke.run_rootless_canary(
        args,
        snapshot=snapshot,
        task=SimpleNamespace(task_id="unused"),
        run_dir=tmp_path / "results" / "paid-batch",
    )

    assert result["mode"] == mode
    assert captured["include_evolver"] is False


def test_full_harness_canary_rootless_help_does_not_import_e2b_modules():
    repo = Path(__file__).resolve().parents[1]
    code = """
import builtins
import runpy
import sys

real_import = builtins.__import__

def reject_e2b(name, *args, **kwargs):
    if (
        name == "e2b"
        or name.startswith("qea.e2b_")
        or name.startswith("qea.executors.e2b_")
    ):
        raise AssertionError(f"rootless help imported {name}")
    return real_import(name, *args, **kwargs)

builtins.__import__ = reject_e2b
sys.argv = [
    "scripts/smoke_qfbench_full_harness.py",
    "--help",
]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "--executor {rootless-docker,e2b}" in proc.stdout


def test_full_harness_canary_help_does_not_import_evolver_or_feedback_modules():
    repo = Path(__file__).resolve().parents[1]
    code = """
import builtins
import runpy
import sys

real_import = builtins.__import__
blocked = {
    "qea.candidate_admission",
    "qea.evolution_feedback",
    "qea.evolve_runtime",
    "qea.executors.sandbox_evolver",
}

def reject_evolver(name, *args, **kwargs):
    if name in blocked:
        raise AssertionError(f"baseline-safe CLI imported {name}")
    return real_import(name, *args, **kwargs)

builtins.__import__ = reject_evolver
sys.argv = ["scripts/smoke_qfbench_full_harness.py", "--help"]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "paid-baseline-batch" in proc.stdout


def test_rootless_canary_requires_runtime_inputs_without_loading_dotenv(
    monkeypatch, tmp_path
):
    from scripts import smoke_qfbench_full_harness as smoke

    def fail_dotenv():
        raise AssertionError("rootless canary must not load .env")

    monkeypatch.setattr(smoke.run_cli, "_load_dotenv", fail_dotenv)
    with pytest.raises(ValueError, match="--rootless-config"):
        smoke.main(
            [
                "--executor",
                "rootless-docker",
                "--mode",
                "import",
                "--qfbench-root",
                str(tmp_path),
            ]
        )

    with pytest.raises(ValueError, match="--rootless-image-set-manifest"):
        smoke.main(
            [
                "--executor",
                "rootless-docker",
                "--mode",
                "import",
                "--qfbench-root",
                str(tmp_path),
                "--rootless-config",
                str(tmp_path / "rootless.json"),
            ]
        )


def test_rootless_import_uses_internal_network_without_model_and_exact_cleanup(
    tmp_path,
):
    from qea.executors.sandbox_nexau import SandboxResourceContract
    from scripts.smoke_qfbench_full_harness import run_rootless_import_canary

    backend = FakeRootlessImportBackend()
    task_runtime = SimpleNamespace(
        worker_image_ref="sha256:" + "d" * 64,
        worker_resources=SandboxResourceContract(
            cpu_count=2,
            memory_mb=4096,
            pids_limit=256,
            timeout_seconds=300,
            writable_tmpfs_mb={"/app": 2048, "/qea": 512, "/tmp": 256},
        ),
    )
    runtime = SimpleNamespace(
        backend=backend,
        evaluator=SimpleNamespace(
            executor=SimpleNamespace(
                catalog=SimpleNamespace(tasks={"task-a": task_runtime})
            )
        ),
    )

    result = run_rootless_import_canary(
        runtime=runtime,
        task=SimpleNamespace(task_id="task-a"),
        run_id="rootless-import-test",
        run_dir=tmp_path / "run",
    )

    assert result["import_ok"] is True
    assert result["model_calls"] == 0
    assert result["network_enabled"] is False
    assert len(backend.specs) == 1
    spec = backend.specs[0]
    assert spec.role == "worker"
    assert spec.network_policy == "worker-proxy-only"
    assert spec.environment == {}
    assert spec.network_scope == spec.attempt_id
    assert all("proxy" not in argv for argv, _, _ in backend.commands)
    assert backend.killed == ["c" * 64]
    assert backend.removed_networks == ["a" * 64]
    lifecycle = json.loads(
        (tmp_path / "run" / "worker-import-sandbox-lifecycle-v2.json").read_text()
    )
    assert lifecycle["cleaned_up"] is True
    assert lifecycle["cleanup_result"] == "killed"


def test_rootless_import_main_builds_production_runtime_and_closes(
    monkeypatch, tmp_path
):
    import qea.benchmarks.qfbench as benchmark_module
    import qea.rootless_full_harness as rootless_module
    from qea.executors.sandbox_nexau import SandboxResourceContract
    from scripts import smoke_qfbench_full_harness as smoke

    backend = FakeRootlessImportBackend()
    task = SimpleNamespace(task_id="task-a")
    task_runtime = SimpleNamespace(
        worker_image_ref="sha256:" + "d" * 64,
        worker_resources=SandboxResourceContract(
            cpu_count=2,
            memory_mb=4096,
            pids_limit=256,
            timeout_seconds=300,
            writable_tmpfs_mb={"/app": 2048, "/qea": 512, "/tmp": 256},
        ),
    )
    runtime = SimpleNamespace(
        backend=backend,
        evaluator=SimpleNamespace(
            executor=SimpleNamespace(
                catalog=SimpleNamespace(tasks={"task-a": task_runtime})
            )
        ),
        image_identity_digest="1" * 64,
        scheduler_identity_digest="2" * 64,
        runtime_identity_digest="3" * 64,
        closed=False,
    )

    def close_runtime():
        runtime.closed = True

    runtime.close = close_runtime
    snapshot = SimpleNamespace(
        commit="0" * 40,
        tasks=(task,),
        optimize=SimpleNamespace(task_ids=("task-a",)),
        task=lambda task_id: task if task_id == "task-a" else None,
    )
    monkeypatch.setattr(
        benchmark_module, "load_qfbench_snapshot", lambda *args, **kwargs: snapshot
    )
    monkeypatch.setattr(
        rootless_module,
        "load_rootless_full_harness_config",
        lambda path: SimpleNamespace(),
    )
    monkeypatch.setattr(
        rootless_module,
        "build_rootless_full_harness_runtime",
        lambda **kwargs: runtime,
    )
    monkeypatch.setattr(
        smoke,
        "_exact_reap",
        lambda path: (_ for _ in ()).throw(
            AssertionError("rootless import used the E2B reaper")
        ),
    )
    rootless_reaps = []
    monkeypatch.setattr(
        smoke,
        "_exact_rootless_reap",
        lambda run_dir, config_path: rootless_reaps.append(
            (run_dir, config_path)
        )
        or {
            "backend": "rootless-docker",
            "apply": True,
            "pending_ids": [],
            "failed": {},
        },
    )

    result = smoke.main(
        [
            "--executor",
            "rootless-docker",
            "--mode",
            "import",
            "--qfbench-root",
            str(tmp_path / "snapshot"),
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--rootless-config",
            str(tmp_path / "rootless.json"),
            "--rootless-image-set-manifest",
            str(tmp_path / "images.json"),
            "--run-id",
            "rootless-import-main",
            "--results-dir",
            str(tmp_path / "results"),
            "--task",
            "task-a",
        ]
    )

    assert result == 0
    assert runtime.closed is True
    assert rootless_reaps == [
        (
            tmp_path / "results" / "rootless-import-main",
            tmp_path / "rootless.json",
        )
    ]
    status = json.loads(
        (
            tmp_path
            / "results"
            / "rootless-import-main"
            / "run_status.json"
        ).read_text()
    )
    assert status["executor"] == "rootless-docker"
    assert status["status"]["model_calls"] == 0


def test_rootless_paid_rich_delegates_to_one_iteration_production_runner(
    monkeypatch, tmp_path
):
    import qea.benchmarks.qfbench as benchmark_module
    from scripts import smoke_qfbench_full_harness as smoke

    task = SimpleNamespace(task_id="task-a")
    snapshot = SimpleNamespace(
        commit="0" * 40,
        tasks=(task,),
        optimize=SimpleNamespace(task_ids=("task-a",)),
        task=lambda task_id: task if task_id == "task-a" else None,
    )
    monkeypatch.setattr(
        benchmark_module, "load_qfbench_snapshot", lambda *args, **kwargs: snapshot
    )
    calls = []

    def run_production(argv):
        calls.append(tuple(argv))
        return 0

    monkeypatch.setattr(smoke.run_cli, "main", run_production)
    monkeypatch.setattr(
        smoke,
        "_exact_rootless_reap",
        lambda *args: {
            "backend": "rootless-docker",
            "apply": True,
            "pending_ids": [],
            "failed": {},
        },
    )

    result = smoke.main(
        [
            "--executor",
            "rootless-docker",
            "--mode",
            "paid-rich",
            "--qfbench-root",
            str(tmp_path / "snapshot"),
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--rootless-config",
            str(tmp_path / "rootless.json"),
            "--rootless-image-set-manifest",
            str(tmp_path / "images.json"),
            "--feedback-manifest",
            str(tmp_path / "feedback.json"),
            "--verifier-criteria-map",
            str(tmp_path / "criteria.json"),
            "--run-id",
            "rootless-rich-main",
            "--results-dir",
            str(tmp_path / "results"),
            "--task",
            "task-a",
            "--approve-external-run",
        ]
    )

    assert result == 0
    assert len(calls) == 1
    argv = calls[0]
    assert argv[:4] == (
        "--benchmark",
        "qfbench",
        "--executor",
        "rootless-docker",
    )
    assert ("--iters", "1") == (argv[argv.index("--iters")], argv[argv.index("--iters") + 1])
    assert "--approve-external-run" in argv
    assert "--template-manifest-dir" not in argv
    assert "--evolver-template-manifest" not in argv

def test_synthetic_rich_canary_evidence_contains_only_public_worker_files(tmp_path):
    from qea.evolution_feedback import PublicCriterion, PublicTaskRubric
    from scripts.smoke_qfbench_full_harness import build_synthetic_rich_evidence

    task_root = tmp_path / "task"
    (task_root / "environment" / "data").mkdir(parents=True)
    (task_root / "tests").mkdir()
    instruction = task_root / "instruction.md"
    data = task_root / "environment" / "data" / "input.csv"
    private = task_root / "tests" / "expected.json"
    instruction.write_text("PUBLIC INSTRUCTION\n")
    data.write_text("PUBLIC DATA\n")
    private.write_text('{"PRIVATE_VERIFIER_CANARY": 17}\n')
    task = SimpleNamespace(
        task_id="task-a",
        root=task_root,
        worker_files=(instruction, data),
    )
    rubric = PublicTaskRubric(
        "task-a",
        (PublicCriterion("required_output", "Produce the requested output."),),
    )

    evidence = build_synthetic_rich_evidence(
        task=task,
        rubric=rubric,
        destination=tmp_path / "evidence",
    )
    text = "\n".join(
        path.read_text(errors="replace")
        for path in evidence.rglob("*")
        if path.is_file()
    )
    assert "PUBLIC INSTRUCTION" in text
    assert "PUBLIC DATA" in text
    assert "PRIVATE_VERIFIER_CANARY" not in text
    assert not any("tests" in path.parts for path in evidence.rglob("*"))


class FakeFiles:
    def __init__(self):
        self.data = {
            "/opt/qea/nexau-requirements.lock": "nexau==0.3.9\n",
        }

    def write(self, path, data, **kwargs):
        self.data[path] = data.read() if hasattr(data, "read") else data

    def read(self, path, format="text", **kwargs):
        value = self.data[path]
        if format == "text" and isinstance(value, bytes):
            return value.decode()
        return value


class FakeSandbox:
    sandbox_id = "import-canary-sandbox"

    def __init__(self):
        self.files = FakeFiles()
        self.commands = SimpleNamespace(run=self.run)
        self.calls = []
        self.killed = False

    def run(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return SimpleNamespace(exit_code=0, stdout="IMPORT_OK\n", stderr="", error="")

    def kill(self):
        self.killed = True


class FakeFactory:
    def __init__(self):
        self.created = []

    def create(self, **kwargs):
        sandbox = FakeSandbox()
        self.created.append((kwargs, sandbox))
        return sandbox


def test_import_canary_has_no_model_call_or_network_and_cleans_up(tmp_path):
    from qea.e2b_lease import E2BLeasePool
    from scripts.smoke_qfbench_full_harness import run_import_canary

    factory = FakeFactory()
    result = run_import_canary(
        template_id="worker-template",
        run_id="import-canary",
        run_dir=tmp_path / "run",
        sandbox_factory=factory,
        lease_pool=E2BLeasePool(tmp_path / "leases", max_leases=1),
    )

    kwargs, sandbox = factory.created[0]
    assert kwargs["secure"] is True
    assert kwargs["allow_internet_access"] is False
    assert kwargs["envs"] == {}
    assert "network" not in kwargs
    assert sandbox.killed is True
    assert result["import_ok"] is True
    assert not any("agent.run" in command for command, _ in sandbox.calls)
    assert any("import_canary.py" in command for command, _ in sandbox.calls)
    lifecycle = json.loads(next(
        (tmp_path / "run").rglob("*-sandbox-lifecycle.json")
    ).read_text())
    assert lifecycle["cleaned_up"] is True
