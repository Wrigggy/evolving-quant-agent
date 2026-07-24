from types import SimpleNamespace

import pytest


def test_qfbench_cli_parses_e2b_three_iteration_pilot():
    import run

    args = run.build_parser().parse_args([
        "--benchmark", "qfbench",
        "--executor", "e2b",
        "--qfbench-root", "/tmp/qfbench",
        "--template-manifest-dir", "/tmp/templates",
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
    assert run.resolve_iterations(args) == 3


def test_qfbench_cli_rejects_four_iterations_but_legacy_defaults_to_four():
    import run

    qf = run.build_parser().parse_args(["--benchmark", "qfbench", "--iters", "4"])
    with pytest.raises(ValueError, match="3 or 5"):
        run.resolve_iterations(qf)

    legacy = run.build_parser().parse_args(["--mock"])
    assert run.resolve_iterations(legacy) == 4


def test_qfbench_30x5_estimates_140_official_attempts():
    import run

    assert run.estimate_qfbench_attempts(20, 10, 5) == 140


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
