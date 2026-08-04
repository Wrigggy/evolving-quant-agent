from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace


def test_tvt_cli_accepts_calibration_and_ten_iterations() -> None:
    import run

    args = run.build_parser().parse_args([
        "--benchmark", "qfbench",
        "--executor", "rootless-docker",
        "--qfbench-manifest", "data/qfbench/MANIFEST_30_15_40_EVOLUTION.json",
        "--validation-calibration", "/tmp/calibration.json",
        "--iters", "10",
    ])

    assert args.validation_calibration == Path("/tmp/calibration.json")
    assert run.resolve_iterations(args) == 10
    assert run.estimate_qfbench_tvt_attempts(30, 15, 40, 10) == 575


@dataclass(frozen=True)
class _RootlessConfig:
    worker_concurrency: int = 20
    verifier_concurrency: int = 3
    upstream_base_url: str = "https://openrouter.ai/api/v1"
    allowed_path_prefix: str = "/v1"
    allowed_model: str = "deepseek/deepseek-v4-flash-0731"
    required_provider: str = "deepseek"
    scheduler_epoch: str | None = "iter01-10-20w3v"
    capacity: object = None


def _tasks(prefix: str, count: int):
    return tuple(SimpleNamespace(task_id=f"{prefix}-{i}") for i in range(count))


def _tvt_plan():
    train = _tasks("train", 30)
    validation = _tasks("validation", 15)
    test = _tasks("test", 32)
    diagnostic = _tasks("diagnostic", 8)
    snapshot = SimpleNamespace(
        commit="0" * 40,
        train=SimpleNamespace(tasks=train, task_ids=tuple(t.task_id for t in train)),
        validation=SimpleNamespace(
            tasks=validation,
            task_ids=tuple(t.task_id for t in validation),
        ),
        test=SimpleNamespace(tasks=test, task_ids=tuple(t.task_id for t in test)),
        diagnostic=SimpleNamespace(
            tasks=diagnostic,
            task_ids=tuple(t.task_id for t in diagnostic),
        ),
        tasks=train + validation + test + diagnostic,
    )
    return SimpleNamespace(
        snapshot=snapshot,
        protocol="train-validation-test-v1",
        calibration=SimpleNamespace(
            tolerance=0.025,
            digest="7" * 64,
            source_run_id="base-85x5",
        ),
        run_id="tvt-rootless-cli",
        iterations=10,
        estimated_attempts=575,
        contract_digest="1" * 64,
        admission_digest="2" * 64,
        task_manifest_digest="3" * 64,
        results_root=Path("/tmp/results"),
    )


def test_rootless_tvt_path_binds_calibration_and_four_panels(monkeypatch) -> None:
    import qea.loop_benchmark as loop_benchmark
    import qea.rootless_full_harness as rootless_full_harness
    import run

    captured = {}
    runtime = SimpleNamespace(
        backend=SimpleNamespace(backend_name="rootless-docker"),
        evaluator=object(),
        proposer=SimpleNamespace(propose=lambda **kwargs: object()),
        image_identity_digest="4" * 64,
        scheduler_identity_digest="5" * 64,
        runtime_identity_digest="6" * 64,
        close=lambda: None,
    )
    monkeypatch.setattr(run, "_prepare_qfbench_run", lambda args: _tvt_plan())
    monkeypatch.setattr(
        rootless_full_harness,
        "load_rootless_full_harness_config",
        lambda path: _RootlessConfig(),
    )
    monkeypatch.setattr(
        rootless_full_harness,
        "build_rootless_full_harness_runtime",
        lambda **kwargs: runtime,
    )

    def fake_run(configuration, **kwargs):
        captured["configuration"] = configuration
        captured["runner"] = kwargs
        return SimpleNamespace(run_id="tvt-rootless-cli")

    monkeypatch.setattr(loop_benchmark, "run_benchmark_evolution", fake_run)
    monkeypatch.setattr(run, "_print_qfbench", lambda result, **kwargs: None)
    args = run.build_parser().parse_args([
        "--benchmark", "qfbench",
        "--qfbench-root", "/tmp/qfbench",
        "--qfbench-manifest", "/tmp/evolution.json",
        "--validation-calibration", "/tmp/calibration.json",
        "--rootless-config", "/tmp/rootless.json",
        "--rootless-image-set-manifest", "/tmp/images.json",
        "--feedback-mode", "rich",
        "--feedback-manifest", "/tmp/feedback.json",
        "--verifier-criteria-map", "/tmp/mapping.json",
        "--iters", "10",
        "--approve-external-run",
    ])

    assert run._run_qfbench_rootless(args) == 0
    config = captured["configuration"]
    assert config.validation_noise_tolerance == 0.025
    assert config.validation_calibration_digest == "7" * 64
    assert config.validation_calibration_source_run_id == "base-85x5"
    assert config.model_identity == rootless_full_harness.rootless_model_route_identity(
        upstream_base_url="https://openrouter.ai/api/v1",
        allowed_path_prefix="/v1",
        allowed_model="deepseek/deepseek-v4-flash-0731",
        required_provider="deepseek",
    )
    runner = captured["runner"]
    assert len(runner["optimize_tasks"]) == 30
    assert len(runner["validation_tasks"]) == 15
    assert len(runner["test_tasks"]) == 32
    assert len(runner["diagnostic_tasks"]) == 8
    assert "held_out_tasks" not in runner
