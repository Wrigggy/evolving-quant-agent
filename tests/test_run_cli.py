import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_qfbench_cli_parses_e2b_three_iteration_pilot():
    import run

    args = run.build_parser().parse_args([
        "--benchmark", "qfbench",
        "--executor", "e2b",
        "--qfbench-root", "/tmp/qfbench",
        "--template-manifest-dir", "/tmp/templates",
        "--evolver-template-manifest", "/tmp/evolver.image.json",
        "--feedback-mode", "rich",
        "--feedback-manifest", "/tmp/feedback.json",
        "--verifier-criteria-map", "/tmp/criteria.json",
        "--iters", "3",
        "--concurrency", "4",
        "--run-id", "pilot-003",
        "--results-dir", "results/qfbench",
        "--approve-external-run",
    ])

    assert args.benchmark == "qfbench"
    assert args.executor == "e2b"
    assert args.iters == 3
    assert args.concurrency == 4
    assert args.approve_external_run is True
    assert args.feedback_mode == "rich"
    assert run.resolve_iterations(args) == 3


def test_qfbench_full_harness_defaults_to_rootless_and_accepts_one_iteration():
    import run

    args = run.build_parser().parse_args([
        "--benchmark", "qfbench",
        "--rootless-config", "/tmp/rootless.json",
        "--rootless-image-set-manifest", "/tmp/image-set.json",
        "--feedback-mode", "rich",
        "--feedback-manifest", "/tmp/feedback.json",
        "--verifier-criteria-map", "/tmp/criteria.json",
        "--iters", "1",
    ])

    assert args.executor == "rootless-docker"
    assert args.rootless_config.name == "rootless.json"
    assert args.rootless_image_set_manifest.name == "image-set.json"
    assert run.resolve_iterations(args) == 1


def test_qfbench_cli_rejects_four_iterations_but_legacy_defaults_to_four():
    import run

    qf = run.build_parser().parse_args(["--benchmark", "qfbench", "--iters", "4"])
    with pytest.raises(ValueError, match="1, 3, or 5"):
        run.resolve_iterations(qf)

    legacy = run.build_parser().parse_args(["--mock"])
    assert run.resolve_iterations(legacy) == 4


def test_qfbench_30x5_estimates_140_official_attempts():
    import run

    assert run.estimate_qfbench_attempts(20, 10, 5) == 140


def test_qfbench_30x1_estimates_60_official_attempts():
    import run

    assert run.estimate_qfbench_attempts(20, 10, 1) == 60


@pytest.mark.parametrize(
    ("omitted", "message"),
    [
        ("--feedback-mode", "feedback-mode"),
        ("--evolver-template-manifest", "evolver-template-manifest"),
        ("--feedback-manifest", "feedback-manifest"),
        ("--verifier-criteria-map", "verifier-criteria-map"),
    ],
)
def test_qfbench_full_harness_requires_explicit_arm_and_contract_files(
    omitted, message
):
    import run

    values = {
        "--feedback-mode": "control",
        "--evolver-template-manifest": "/tmp/evolver.json",
        "--feedback-manifest": "/tmp/feedback.json",
        "--verifier-criteria-map": "/tmp/mapping.json",
    }
    argv = ["--benchmark", "qfbench", "--executor", "e2b"]
    for flag, value in values.items():
        if flag != omitted:
            argv.extend([flag, value])
    args = run.build_parser().parse_args(argv)

    with pytest.raises(ValueError, match=message):
        run.validate_qfbench_full_harness_args(args)


@pytest.mark.parametrize(
    ("omitted", "message"),
    [
        ("--rootless-config", "rootless-config"),
        ("--rootless-image-set-manifest", "rootless-image-set-manifest"),
    ],
)
def test_rootless_full_harness_requires_explicit_config_and_image_set(
    omitted, message
):
    import run

    values = {
        "--rootless-config": "/tmp/rootless.json",
        "--rootless-image-set-manifest": "/tmp/image-set.json",
        "--feedback-mode": "control",
        "--feedback-manifest": "/tmp/feedback.json",
        "--verifier-criteria-map": "/tmp/mapping.json",
    }
    argv = ["--benchmark", "qfbench"]
    for flag, value in values.items():
        if flag != omitted:
            argv.extend([flag, value])
    args = run.build_parser().parse_args(argv)

    with pytest.raises(ValueError, match=message):
        run.validate_qfbench_full_harness_args(args)


def test_rootless_rejects_verifier_network_and_e2b_only_manifests() -> None:
    import run

    common = [
        "--benchmark", "qfbench",
        "--rootless-config", "/tmp/rootless.json",
        "--rootless-image-set-manifest", "/tmp/image-set.json",
        "--feedback-mode", "control",
        "--feedback-manifest", "/tmp/feedback.json",
        "--verifier-criteria-map", "/tmp/mapping.json",
    ]
    network = run.build_parser().parse_args(common + ["--allow-verifier-network"])
    with pytest.raises(ValueError, match="verifier network"):
        run.validate_qfbench_full_harness_args(network)

    templates = run.build_parser().parse_args(
        common + ["--template-manifest-dir", "/tmp/e2b"]
    )
    with pytest.raises(ValueError, match="E2B-only"):
        run.validate_qfbench_full_harness_args(templates)

    worker_network = run.build_parser().parse_args(common + ["--worker-no-internet"])
    with pytest.raises(ValueError, match="worker-no-internet"):
        run.validate_qfbench_full_harness_args(worker_network)


def test_qfbench_rootless_dispatch_never_loads_dotenv(monkeypatch) -> None:
    import run

    calls = []
    monkeypatch.setattr(
        run,
        "_load_dotenv",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("dotenv read")),
    )
    monkeypatch.setattr(
        run,
        "_run_qfbench_rootless",
        lambda args: calls.append(args.executor) or 0,
        raising=False,
    )

    assert run.main(["--benchmark", "qfbench"]) == 0
    assert calls == ["rootless-docker"]


def test_qfbench_explicit_e2b_dispatch_loads_dotenv(monkeypatch) -> None:
    import run

    calls = []
    monkeypatch.setattr(run, "_load_dotenv", lambda: calls.append("dotenv"))
    monkeypatch.setattr(
        run,
        "_run_qfbench_e2b",
        lambda args: calls.append(args.executor) or 0,
        raising=False,
    )

    assert run.main(["--benchmark", "qfbench", "--executor", "e2b"]) == 0
    assert calls == ["dotenv", "e2b"]


def test_rootless_concurrency_uses_config_with_legacy_worker_alias() -> None:
    import run

    config = SimpleNamespace(worker_concurrency=8, verifier_concurrency=4)
    defaults = run.build_parser().parse_args(["--benchmark", "qfbench"])
    assert run.resolve_qfbench_concurrency(defaults, config=config) == (8, 4)

    alias = run.build_parser().parse_args(
        ["--benchmark", "qfbench", "--concurrency", "6"]
    )
    assert run.resolve_qfbench_concurrency(alias, config=config) == (6, 4)

    explicit = run.build_parser().parse_args([
        "--benchmark", "qfbench",
        "--worker-concurrency", "5",
        "--verifier-concurrency", "2",
    ])
    assert run.resolve_qfbench_concurrency(explicit, config=config) == (5, 2)

    conflict = run.build_parser().parse_args([
        "--benchmark", "qfbench",
        "--concurrency", "5",
        "--worker-concurrency", "6",
    ])
    with pytest.raises(ValueError, match="conflicting worker concurrency"):
        run.resolve_qfbench_concurrency(conflict, config=config)


def test_rootless_approval_summary_names_real_cost_surfaces() -> None:
    import run

    summary = run.qfbench_external_run_approval_text("rootless-docker")
    assert "model-provider egress" in summary
    assert "self-hosted compute" in summary
    assert "E2B" not in summary

    assert "paid E2B" in run.qfbench_external_run_approval_text("e2b")


@dataclass(frozen=True)
class _CliRootlessConfig:
    worker_concurrency: int = 8
    verifier_concurrency: int = 4
    upstream_base_url: str = "https://openrouter.ai/api/v1"
    allowed_path_prefix: str = "/v1"
    allowed_model: str = "provider/model"
    scheduler_epoch: str | None = None
    capacity: object = None


def _rootless_plan():
    tasks = tuple(SimpleNamespace(task_id=f"task-{index}") for index in range(30))
    snapshot = SimpleNamespace(
        commit="0" * 40,
        tasks=tasks,
        optimize=SimpleNamespace(tasks=tasks[:20], task_ids=tuple(t.task_id for t in tasks[:20])),
        held_out=SimpleNamespace(tasks=tasks[20:], task_ids=tuple(t.task_id for t in tasks[20:])),
    )
    return SimpleNamespace(
        snapshot=snapshot,
        protocol="optimize-held-out-v1",
        calibration=None,
        run_id="rootless-cli",
        iterations=1,
        estimated_attempts=60,
        contract_digest="1" * 64,
        admission_digest="2" * 64,
        task_manifest_digest="3" * 64,
        results_root=Path("/tmp/results"),
    )


def test_rootless_dry_run_reports_60_attempts_without_e2b_or_key_reads(
    monkeypatch, capsys
) -> None:
    import qea.rootless_full_harness as rootless_full_harness
    import run

    class GuardedEnvironment(dict):
        def get(self, key, default=None):
            if key in {"E2B_API_KEY", "OPENROUTER_API_KEY", "LLM_API_KEY"}:
                raise AssertionError(f"forbidden environment key read: {key}")
            return super().get(key, default)

    monkeypatch.setattr(run, "_prepare_qfbench_run", lambda args: _rootless_plan(), raising=False)
    monkeypatch.setattr(
        rootless_full_harness,
        "load_rootless_full_harness_config",
        lambda path: _CliRootlessConfig(),
    )
    monkeypatch.setattr(run.os, "environ", GuardedEnvironment())
    args = run.build_parser().parse_args([
        "--benchmark", "qfbench",
        "--rootless-config", "/tmp/rootless.json",
        "--rootless-image-set-manifest", "/tmp/image-set.json",
        "--feedback-mode", "rich",
        "--feedback-manifest", "/tmp/feedback.json",
        "--verifier-criteria-map", "/tmp/criteria.json",
        "--iters", "1",
    ])

    assert run._run_qfbench_rootless(args) == 2
    output = capsys.readouterr().out
    assert "60" in output
    assert "rootless-docker" in output
    assert "model-provider egress and self-hosted compute" in output
    assert "E2B" not in output
    assert "upstream base: https://openrouter.ai/api/v1" in output
    assert "caller prefix: /v1" in output
    assert "https://openrouter.ai/api/v1/v1" not in output


def test_approved_rootless_path_binds_runtime_and_scheduler_identities(
    monkeypatch
) -> None:
    import qea.loop_benchmark as loop_benchmark
    import qea.rootless_full_harness as rootless_full_harness
    import run

    config = _CliRootlessConfig()
    runtime = SimpleNamespace(
        backend=SimpleNamespace(backend_name="rootless-docker"),
        evaluator=object(),
        proposer=SimpleNamespace(propose=lambda **kwargs: object()),
        image_identity_digest="4" * 64,
        scheduler_identity_digest="5" * 64,
        runtime_identity_digest="6" * 64,
        close=lambda: None,
    )
    captured = {}
    class GuardedEnvironment(dict):
        def get(self, key, default=None):
            if key in {"E2B_API_KEY", "OPENROUTER_API_KEY", "LLM_API_KEY"}:
                raise AssertionError(f"forbidden environment key read: {key}")
            return super().get(key, default)

    monkeypatch.setattr(run.os, "environ", GuardedEnvironment())
    monkeypatch.setattr(run, "_prepare_qfbench_run", lambda args: _rootless_plan(), raising=False)
    monkeypatch.setattr(
        rootless_full_harness,
        "load_rootless_full_harness_config",
        lambda path: config,
    )
    def fake_factory(**kwargs):
        captured["factory"] = kwargs
        return runtime

    monkeypatch.setattr(
        rootless_full_harness,
        "build_rootless_full_harness_runtime",
        fake_factory,
    )

    def fake_run(configuration, **kwargs):
        captured["configuration"] = configuration
        captured["runner"] = kwargs
        return SimpleNamespace(run_id="rootless-cli")

    monkeypatch.setattr(loop_benchmark, "run_benchmark_evolution", fake_run)
    monkeypatch.setattr(run, "_print_qfbench", lambda result, **kwargs: None)
    args = run.build_parser().parse_args([
        "--benchmark", "qfbench",
        "--rootless-config", "/tmp/rootless.json",
        "--rootless-image-set-manifest", "/tmp/image-set.json",
        "--feedback-mode", "rich",
        "--feedback-manifest", "/tmp/feedback.json",
        "--verifier-criteria-map", "/tmp/criteria.json",
        "--iters", "1",
        "--worker-concurrency", "6",
        "--verifier-concurrency", "2",
        "--approve-external-run",
    ])

    assert run._run_qfbench_rootless(args) == 0
    assert captured["factory"]["config"].worker_concurrency == 6
    assert captured["factory"]["config"].verifier_concurrency == 2
    evolution_config = captured["configuration"]
    assert evolution_config.worker_concurrency == 6
    assert evolution_config.verifier_concurrency == 2
    assert evolution_config.scheduler_identity_digest == "5" * 64
    assert evolution_config.template_identity_digest == "6" * 64
    assert len(evolution_config.model_identity) == 64
    assert "https://" not in evolution_config.model_identity
    assert captured["runner"]["evaluator"] is runtime.evaluator


def _baseline_plan():
    primary = tuple(
        SimpleNamespace(
            task_id=f"primary-{index}",
            domain="risk_credit",
            reward_kind="binary",
            resource_source="upstream",
        )
        for index in range(77)
    )
    diagnostic = tuple(
        SimpleNamespace(
            task_id=f"diagnostic-{index}",
            domain="derivatives",
            reward_kind="binary",
            resource_source="upstream",
        )
        for index in range(8)
    )
    snapshot = SimpleNamespace(
        commit="0" * 40,
        primary=SimpleNamespace(
            name="baseline_primary",
            tasks=primary,
            task_ids=tuple(task.task_id for task in primary),
        ),
        diagnostic=SimpleNamespace(
            name="baseline_diagnostic",
            tasks=diagnostic,
            task_ids=tuple(task.task_id for task in diagnostic),
        ),
        tasks=primary + diagnostic,
        resource_fallback_task_ids=frozenset(),
    )
    return SimpleNamespace(
        snapshot=snapshot,
        run_id="baseline-cli",
        repetitions=5,
        estimated_attempts=425,
        task_manifest_digest="3" * 64,
        results_root=Path("/tmp/results"),
    )


@pytest.mark.parametrize(
    ("argv", "message"),
    (
        (["--executor", "e2b"], "rootless"),
        (["--feedback-mode", "rich"], "feedback"),
        (["--iters", "1"], "iters"),
        (["--repetitions", "3"], "five"),
        (["--stop-after-repetition", "0"], "stop-after"),
        (["--stop-after-repetition", "6"], "stop-after"),
        ([], "qfbench-root"),
    ),
)
def test_baseline_cli_rejects_unsafe_or_incomplete_configuration(argv, message):
    import run

    common = [
        "--benchmark", "qfbench",
        "--qfbench-baseline",
        "--qfbench-root", "/tmp/qfbench",
        "--qfbench-manifest", "/tmp/baseline.json",
        "--rootless-config", "/tmp/rootless.json",
        "--rootless-image-set-manifest", "/tmp/image-set.json",
        "--run-id", "baseline-cli",
        "--repetitions", "5",
    ]
    if not argv:
        common[common.index("--qfbench-root"):common.index("--qfbench-root") + 2] = []
    elif argv[0] == "--repetitions":
        index = common.index("--repetitions")
        common[index:index + 2] = argv
    else:
        common.extend(argv)
    args = run.build_parser().parse_args(common)

    with pytest.raises(ValueError, match=message):
        run.validate_qfbench_baseline_args(args)


def test_baseline_dry_run_reports_425_attempts_850_lifecycles_and_zero_evolvers(
    monkeypatch, capsys
) -> None:
    import qea.rootless_full_harness as rootless_full_harness
    import run

    class GuardedEnvironment(dict):
        def get(self, key, default=None):
            if key in {"E2B_API_KEY", "OPENROUTER_API_KEY", "LLM_API_KEY"}:
                raise AssertionError(f"forbidden environment key read: {key}")
            return super().get(key, default)

    monkeypatch.setattr(
        run, "_prepare_qfbench_baseline_run", lambda args: _baseline_plan()
    )
    monkeypatch.setattr(
        rootless_full_harness,
        "load_rootless_full_harness_config",
        lambda path: _CliRootlessConfig(worker_concurrency=4, verifier_concurrency=3),
    )
    monkeypatch.setattr(run.os, "environ", GuardedEnvironment())
    args = run.build_parser().parse_args([
        "--benchmark", "qfbench",
        "--qfbench-baseline",
        "--qfbench-root", "/tmp/qfbench",
        "--qfbench-manifest", "/tmp/baseline.json",
        "--rootless-config", "/tmp/rootless.json",
        "--rootless-image-set-manifest", "/tmp/image-set.json",
        "--run-id", "baseline-cli",
        "--repetitions", "5",
        "--stop-after-repetition", "1",
    ])

    assert run._run_qfbench_rootless_baseline(args) == 2
    output = capsys.readouterr().out
    assert "85" in output
    assert "425" in output
    assert "850" in output
    assert "evolver lifecycles: 0" in output
    assert "E2B" not in output


def test_approved_baseline_path_uses_only_evaluator_and_binds_identities(
    monkeypatch,
) -> None:
    import qea.qfbench_baseline as qfbench_baseline
    import qea.rootless_full_harness as rootless_full_harness
    import run

    config = _CliRootlessConfig(worker_concurrency=4, verifier_concurrency=3)

    class Runtime:
        backend = SimpleNamespace(backend_name="rootless-docker")
        evaluator = object()
        image_identity_digest = "4" * 64
        scheduler_identity_digest = "5" * 64
        runtime_identity_digest = "6" * 64

        @property
        def proposer(self):
            raise AssertionError("baseline must never access the evolver")

        def close(self):
            pass

    runtime = Runtime()
    captured = {}
    monkeypatch.setattr(run, "_prepare_qfbench_baseline_run", lambda args: _baseline_plan())
    monkeypatch.setattr(
        rootless_full_harness,
        "load_rootless_full_harness_config",
        lambda path: config,
    )
    def fake_factory(**kwargs):
        captured["factory"] = kwargs
        return runtime

    monkeypatch.setattr(
        rootless_full_harness,
        "build_rootless_full_harness_runtime",
        fake_factory,
    )

    def fake_run(configuration, **kwargs):
        captured["configuration"] = configuration
        captured["runner"] = kwargs
        return SimpleNamespace(
            run_id="baseline-cli",
            run_dir=Path("/tmp/results/baseline-cli"),
            complete=False,
            repetitions=(object(),),
            aggregate={"primary": {"repeat_domain_macro": {"mean": 0.5}}},
        )

    monkeypatch.setattr(qfbench_baseline, "run_qfbench_baseline", fake_run)
    monkeypatch.setattr(
        qfbench_baseline,
        "audit_baseline_proxy_costs",
        lambda *args, **kwargs: {
            "provider_cost_usd": "1.25",
            "request_count": 10,
            "total_tokens": 100,
        },
    )
    args = run.build_parser().parse_args([
        "--benchmark", "qfbench",
        "--qfbench-baseline",
        "--qfbench-root", "/tmp/qfbench",
        "--qfbench-manifest", "/tmp/baseline.json",
        "--rootless-config", "/tmp/rootless.json",
        "--rootless-image-set-manifest", "/tmp/image-set.json",
        "--run-id", "baseline-cli",
        "--repetitions", "5",
        "--stop-after-repetition", "1",
        "--approve-external-run",
    ])

    assert run._run_qfbench_rootless_baseline(args) == 0
    assert len(captured["factory"]["tasks"]) == 85
    baseline_config = captured["configuration"]
    assert baseline_config.scheduler_identity_digest == "5" * 64
    assert baseline_config.runtime_identity_digest == "6" * 64
    assert baseline_config.template_identity_digest == "4" * 64
    assert len(baseline_config.model_identity) == 64
    assert captured["runner"]["evaluator"] is runtime.evaluator
    assert len(captured["runner"]["primary_tasks"]) == 77
    assert len(captured["runner"]["diagnostic_tasks"]) == 8
    assert captured["runner"]["stop_after_repetition"] == 1


def _write_schema_v2_baseline_resume(results_root: Path) -> tuple:
    from qea.qfbench_scheduler_epochs import SchedulerEpoch

    epochs = (
        SchedulerEpoch(1, 1, 4, 3, "5" * 64, "6" * 64),
        SchedulerEpoch(2, 5, 12, 3, "7" * 64, "8" * 64),
    )
    run_dir = results_root / "baseline-cli"
    run_dir.mkdir(parents=True)
    (run_dir / "resume.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "baseline-cli",
                "benchmark_commit": "0" * 40,
                "total_repetitions": 5,
                "scheduler_epochs": [epoch.to_dict() for epoch in epochs],
                "next_repetition": 2,
            }
        )
    )
    return epochs


def _baseline_plan_at(results_root: Path):
    plan = _baseline_plan()
    return SimpleNamespace(**{**vars(plan), "results_root": results_root})


def _schema_v2_baseline_args(run, results_root: Path, *extra: str):
    return run.build_parser().parse_args(
        [
            "--benchmark",
            "qfbench",
            "--qfbench-baseline",
            "--qfbench-root",
            "/tmp/qfbench",
            "--qfbench-manifest",
            "/tmp/baseline.json",
            "--rootless-config",
            "/tmp/rootless.json",
            "--rootless-image-set-manifest",
            "/tmp/image-set.json",
            "--run-id",
            "baseline-cli",
            "--repetitions",
            "5",
            "--results-dir",
            str(results_root),
            "--resume",
            "--approve-external-run",
            *extra,
        ]
    )


def test_schema_v2_resume_builds_runtime_with_epoch_two_limits(
    tmp_path, monkeypatch
) -> None:
    import qea.qfbench_baseline as qfbench_baseline
    import qea.rootless_full_harness as rootless_full_harness
    import run

    results_root = tmp_path / "results"
    epochs = _write_schema_v2_baseline_resume(results_root)
    config = _CliRootlessConfig(
        worker_concurrency=12,
        verifier_concurrency=3,
        scheduler_epoch="repetitions-02-through-05",
        capacity=SimpleNamespace(tmpfs_mb=40960),
    )
    runtime = SimpleNamespace(
        backend=SimpleNamespace(backend_name="rootless-docker"),
        evaluator=object(),
        image_identity_digest="4" * 64,
        scheduler_identity_digest="7" * 64,
        runtime_identity_digest="8" * 64,
        close=lambda: None,
    )
    captured = {}
    plan = _baseline_plan_at(results_root)
    monkeypatch.setattr(run, "_prepare_qfbench_baseline_run", lambda args: plan)
    monkeypatch.setattr(
        rootless_full_harness,
        "load_rootless_full_harness_config",
        lambda path: config,
    )
    def fake_factory(**kwargs):
        captured["factory"] = kwargs
        return runtime

    monkeypatch.setattr(
        rootless_full_harness,
        "build_rootless_full_harness_runtime",
        fake_factory,
    )

    def fake_run(configuration, **kwargs):
        captured["configuration"] = configuration
        return SimpleNamespace(
            run_dir=results_root / "baseline-cli",
            repetitions=(object(),),
            aggregate={"primary": {"repeat_domain_macro": {"mean": 0.5}}},
        )

    monkeypatch.setattr(qfbench_baseline, "run_qfbench_baseline", fake_run)
    monkeypatch.setattr(
        qfbench_baseline,
        "audit_baseline_proxy_costs",
        lambda *args, **kwargs: {
            "provider_cost_usd": "1",
            "request_count": 85,
            "total_tokens": 1,
        },
    )

    assert run._run_qfbench_rootless_baseline(
        _schema_v2_baseline_args(run, results_root)
    ) == 0
    selected = captured["factory"]["config"]
    assert selected.worker_concurrency == 12
    assert selected.verifier_concurrency == 3
    assert selected.capacity.tmpfs_mb == 40960
    assert captured["configuration"].scheduler_epochs == epochs


def test_schema_v2_resume_rejects_conflicting_cli_concurrency(
    tmp_path, monkeypatch
) -> None:
    import qea.rootless_full_harness as rootless_full_harness
    import run

    results_root = tmp_path / "results"
    _write_schema_v2_baseline_resume(results_root)
    config = _CliRootlessConfig(
        worker_concurrency=12,
        verifier_concurrency=3,
        scheduler_epoch="repetitions-02-through-05",
        capacity=SimpleNamespace(tmpfs_mb=40960),
    )
    monkeypatch.setattr(
        run,
        "_prepare_qfbench_baseline_run",
        lambda args: _baseline_plan_at(results_root),
    )
    monkeypatch.setattr(
        rootless_full_harness,
        "load_rootless_full_harness_config",
        lambda path: config,
    )

    with pytest.raises(ValueError, match="scheduler epoch.*concurrency"):
        run._run_qfbench_rootless_baseline(
            _schema_v2_baseline_args(
                run, results_root, "--worker-concurrency", "11"
            )
        )


def test_schema_v2_runtime_digest_mismatch_fails_before_evaluator(
    tmp_path, monkeypatch
) -> None:
    import qea.qfbench_baseline as qfbench_baseline
    import qea.rootless_full_harness as rootless_full_harness
    import run

    results_root = tmp_path / "results"
    _write_schema_v2_baseline_resume(results_root)
    config = _CliRootlessConfig(
        worker_concurrency=12,
        verifier_concurrency=3,
        scheduler_epoch="repetitions-02-through-05",
        capacity=SimpleNamespace(tmpfs_mb=40960),
    )
    runtime = SimpleNamespace(
        backend=SimpleNamespace(backend_name="rootless-docker"),
        evaluator=object(),
        image_identity_digest="4" * 64,
        scheduler_identity_digest="9" * 64,
        runtime_identity_digest="8" * 64,
        close=lambda: None,
    )
    monkeypatch.setattr(
        run,
        "_prepare_qfbench_baseline_run",
        lambda args: _baseline_plan_at(results_root),
    )
    monkeypatch.setattr(
        rootless_full_harness,
        "load_rootless_full_harness_config",
        lambda path: config,
    )
    monkeypatch.setattr(
        rootless_full_harness,
        "build_rootless_full_harness_runtime",
        lambda **kwargs: runtime,
    )
    monkeypatch.setattr(
        qfbench_baseline,
        "run_qfbench_baseline",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("evaluator path must not start")
        ),
    )

    with pytest.raises(ValueError, match="scheduler epoch identity"):
        run._run_qfbench_rootless_baseline(
            _schema_v2_baseline_args(run, results_root)
        )


def test_load_evolver_template_requires_published_matching_identity(tmp_path):
    import json
    import run

    manifest = tmp_path / "evolver.image.json"
    manifest.write_text(json.dumps({
        "role": "evolver",
        "benchmark_commit": "0" * 40,
        "base_template_id": "base-template",
        "base_build_id": "base-build",
        "identity_sha256": "a" * 64,
        "published_template_id": "evolver-template",
        "published_build_id": "evolver-build",
    }))

    assert run.load_evolver_template(
        manifest, benchmark_commit="0" * 40
    ) == ("evolver-template", "a" * 64)

    payload = json.loads(manifest.read_text())
    payload["benchmark_commit"] = "1" * 40
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="identity mismatch"):
        run.load_evolver_template(manifest, benchmark_commit="0" * 40)


def test_load_template_ids_requires_published_role_manifests(tmp_path):
    import json
    import run

    task = SimpleNamespace(task_id="historical-var-data-prep")
    for role, template_id in (("worker", "tpl-worker"), ("verifier", "tpl-verifier")):
        (tmp_path / f"{task.task_id}.{role}.image.json").write_text(json.dumps({
            "benchmark_commit": "0" * 40,
            "task_id": task.task_id,
            "role": role,
            "base_image": "ghcr.io/example/qf@sha256:" + "a" * 64,
            "published_template_id": template_id,
        }))

    workers, verifiers = run.load_template_ids(
        tmp_path, (task,), benchmark_commit="0" * 40
    )
    assert workers == {task.task_id: "tpl-worker"}
    assert verifiers == {task.task_id: "tpl-verifier"}

    (tmp_path / f"{task.task_id}.verifier.image.json").unlink()
    with pytest.raises(ValueError, match="missing template manifest"):
        run.load_template_ids(tmp_path, (task,), benchmark_commit="0" * 40)


def test_load_template_ids_accepts_immutable_e2b_base_build_manifests(tmp_path):
    import json
    import run

    task = SimpleNamespace(
        task_id="historical-var-data-prep",
        cpus=4,
        memory_mb=8192,
        build_timeout_seconds=600,
    )
    for role, template_id in (("worker", "tpl-worker"), ("verifier", "tpl-verifier")):
        (tmp_path / f"{task.task_id}.{role}.image.json").write_text(json.dumps({
            "benchmark_commit": "0" * 40,
            "task_id": task.task_id,
            "role": role,
            "base_template_id": "base-template-id",
            "base_build_id": "base-build-id",
            "published_template_id": template_id,
            "published_build_id": f"{role}-build-id",
            "cpu_count": 4,
            "memory_mb": 8192,
            "build_timeout_seconds": 600,
        }))

    workers, verifiers = run.load_template_ids(
        tmp_path, (task,), benchmark_commit="0" * 40
    )

    assert workers == {task.task_id: "tpl-worker"}
    assert verifiers == {task.task_id: "tpl-verifier"}

    verifier_path = tmp_path / f"{task.task_id}.verifier.image.json"
    payload = json.loads(verifier_path.read_text())
    payload["memory_mb"] = 1024
    verifier_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="resource mismatch"):
        run.load_template_ids(tmp_path, (task,), benchmark_commit="0" * 40)
