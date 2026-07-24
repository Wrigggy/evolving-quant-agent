import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


BASE_DIGEST = "ghcr.io/example/finance-bench@sha256:" + "a" * 64
NEXAU_COMMIT = "35ee1861546db3cb280a6e17e38a74060d7c96c3"
NEXAU_DEPENDENCY = (
    "git+https://github.com/nex-agi/NexAU.git@" + NEXAU_COMMIT
)


def test_generated_overlay_rewrites_only_from_and_pins_role_dependencies(tmp_path):
    from qea.qfbench_images import generate_qfbench_overlay

    upstream = (
        "# upstream task image\n"
        "FROM finance-bench-sandbox:latest\n"
        "COPY data /root/data\n"
        "RUN python -m pip install pandas==2.3.1\n"
    )
    source = tmp_path / "Dockerfile"
    source.write_text(upstream)

    worker = generate_qfbench_overlay(
        source.read_text(),
        base_image=BASE_DIGEST,
        role="worker",
        dependencies=(NEXAU_DEPENDENCY,),
    )
    verifier = generate_qfbench_overlay(
        source.read_text(),
        base_image=BASE_DIGEST,
        role="verifier",
        dependencies=("uv==0.9.5", "pytest==8.4.1"),
    )

    assert worker.splitlines()[1] == f"FROM {BASE_DIGEST}"
    assert "COPY data /root/data" in worker
    assert "pandas==2.3.1" in worker
    assert NEXAU_DEPENDENCY in worker
    assert "nexau==0.3.9" not in worker
    assert "uv venv --python 3.12 /opt/qea/nexau-venv" in worker
    assert "uv pip install --python /opt/qea/nexau-venv/bin/python" in worker
    assert "/opt/qea/nexau-requirements.lock" in worker
    assert "pytest==8.4.1" not in worker
    assert "uv==0.9.5 pytest==8.4.1" in verifier
    assert source.read_text() == upstream


def test_publication_overlay_rejects_mutable_base_and_multiple_from():
    from qea.qfbench_images import ImageConfigError, generate_qfbench_overlay

    with pytest.raises(ImageConfigError, match="digest-pinned"):
        generate_qfbench_overlay(
            "FROM finance-bench-sandbox:latest\n",
            base_image="finance-bench-sandbox:latest",
            role="worker",
            dependencies=(NEXAU_DEPENDENCY,),
        )
    with pytest.raises(ImageConfigError, match="single-stage"):
        generate_qfbench_overlay(
            "FROM python:3.12 AS build\nFROM python:3.12\n",
            base_image=BASE_DIGEST,
            role="worker",
            dependencies=(NEXAU_DEPENDENCY,),
        )


def test_prepare_overlay_records_content_digests_and_template_name(tmp_path):
    from qea.qfbench_images import prepare_qfbench_overlay

    environment = tmp_path / "environment"
    environment.mkdir()
    dockerfile = environment / "Dockerfile"
    dockerfile.write_text("FROM finance-bench-sandbox:latest\nCOPY data /root/data\n")
    (environment / "data").mkdir()
    (environment / "data" / "input.csv").write_text("x\n1\n")

    spec = prepare_qfbench_overlay(
        task_id="historical-var-data-prep",
        upstream_dockerfile=dockerfile,
        output_dir=tmp_path / "generated",
        base_image=BASE_DIGEST,
        role="worker",
        dependencies=(NEXAU_DEPENDENCY,),
        benchmark_commit="0" * 40,
        cpu_count=4,
        memory_mb=8192,
        build_timeout_seconds=600,
    )

    assert spec.template_name.startswith("qea-qfbench-historical-var-data-prep-worker-")
    assert spec.overlay_path.is_file()
    assert spec.context_dir == environment
    assert spec.upstream_sha256 == hashlib.sha256(dockerfile.read_bytes()).hexdigest()
    assert spec.overlay_sha256 == hashlib.sha256(spec.overlay_path.read_bytes()).hexdigest()
    payload = json.loads(spec.manifest_path.read_text())
    assert payload["base_image"] == BASE_DIGEST
    assert payload["benchmark_commit"] == "0" * 40
    assert payload["published_template_id"] is None
    assert payload["cpu_count"] == 4
    assert payload["memory_mb"] == 8192
    assert payload["build_timeout_seconds"] == 600
    assert payload["install_commands"]
    assert any("nexau-venv" in command for command in payload["install_commands"])


def test_worker_dependency_rejects_mutable_nexau_vcs_revision():
    from qea.qfbench_images import ImageConfigError, generate_qfbench_overlay

    with pytest.raises(ImageConfigError, match="exactly pinned"):
        generate_qfbench_overlay(
            "FROM finance-bench-sandbox:latest\n",
            base_image=BASE_DIGEST,
            role="worker",
            dependencies=(
                "git+https://github.com/nex-agi/NexAU.git@v0.3.9",
            ),
        )


def test_base_template_worker_uses_isolated_python_312_runtime(tmp_path):
    from qea.qfbench_images import (
        NEXAU_RUNTIME_PYTHON,
        apply_qfbench_e2b_task_overlay,
        prepare_qfbench_base_template_overlay,
    )

    environment = tmp_path / "environment"
    (environment / "data").mkdir(parents=True)
    dockerfile = environment / "Dockerfile"
    dockerfile.write_text(
        "FROM finance-bench-sandbox:latest\nCOPY data /app/data\n"
    )
    (environment / "data" / "input.csv").write_text("x\n1\n")
    spec = prepare_qfbench_base_template_overlay(
        task_id="fixture-task",
        upstream_dockerfile=dockerfile,
        output_dir=tmp_path / "generated",
        base_template_id="base-template-id",
        base_build_id="base-build-id",
        role="worker",
        dependencies=(NEXAU_DEPENDENCY,),
        benchmark_commit="0" * 40,
        cpu_count=2,
        memory_mb=4096,
        build_timeout_seconds=600,
    )

    class FakeBuilder:
        def __init__(self):
            self.calls = []

        def set_user(self, value):
            self.calls.append(("user", value))
            return self

        def copy(self, source, destination):
            self.calls.append(("copy", source, destination))
            return self

        def run_cmd(self, command, user=None):
            self.calls.append(("run", command, user))
            return self

    builder = FakeBuilder()
    apply_qfbench_e2b_task_overlay(builder, spec)
    commands = [call[1] for call in builder.calls if call[0] == "run"]
    assert any("uv venv --python 3.12 /opt/qea/nexau-venv" in item for item in commands)
    assert any(
        f"uv pip install --python {NEXAU_RUNTIME_PYTHON} {NEXAU_DEPENDENCY}" in item
        for item in commands
    )
    assert any("/opt/qea/nexau-requirements.lock" in item for item in commands)


def test_template_build_script_is_directly_invokable_from_repository_root():
    repository = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "scripts/build_qfbench_e2b_templates.py", "--help"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "--base-image" in proc.stdout
    assert "--base-template" in proc.stdout
    assert "--base-build-id" in proc.stdout


def test_uvx_warm_command_matches_official_dependency_declarations():
    from qea.qfbench_images import (
        verifier_dependency_lock_command,
        verifier_uvx_warm_command,
    )

    script = """#!/bin/bash
uvx \\
  -p 3.11 \\
  -w pytest==8.4.1 \\
  -w pytest-json-ctrf==0.3.5 \\
  -w numpy \\
  -w pandas \\
  pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
"""

    assert verifier_uvx_warm_command(script) == (
        "uvx -p 3.11 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 "
        "-w numpy -w pandas pytest --version"
    )
    lock = verifier_dependency_lock_command(script)
    assert lock is not None
    assert lock.startswith(
        "uvx -p 3.11 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 "
        "-w numpy -w pandas python -c "
    )
    assert lock.endswith(" > /opt/qea/verifier-requirements.lock")


def test_verifier_overlay_warms_official_uvx_environment_for_offline_reuse():
    from qea.qfbench_images import generate_qfbench_overlay

    test_script = """uvx -p 3.11 \\
  -w pytest==8.4.1 \\
  -w pytest-json-ctrf==0.3.5 \\
  -w numpy==2.2.3 \\
  -w pandas==2.2.3 \\
  -w scipy==1.15.2 \\
  pytest /tests/test_outputs.py
"""
    overlay = generate_qfbench_overlay(
        "FROM finance-bench-sandbox:latest\n",
        base_image=BASE_DIGEST,
        role="verifier",
        dependencies=("uv==0.9.5",),
        verifier_test_script=test_script,
    )

    assert "UV_CACHE_DIR=/opt/qea/uv-cache UV_TOOL_DIR=/opt/qea/uv-tools" in overlay
    assert "UV_TOOL_BIN_DIR=/opt/qea/uv-bin uvx -p 3.11" in overlay
    assert "-w scipy==1.15.2 pytest --version" in overlay
    assert "python -c" in overlay
    assert "> /opt/qea/verifier-requirements.lock" in overlay

    direct_python = generate_qfbench_overlay(
        "FROM finance-bench-sandbox:latest\n",
        base_image=BASE_DIGEST,
        role="verifier",
        dependencies=("uv==0.9.5",),
        verifier_test_script="python /tests/test_outputs.py\n",
    )
    assert (
        "python -m pip freeze > /opt/qea/verifier-requirements.lock"
        in direct_python
    )


def test_task_dockerfile_parser_accepts_pilot_directives_and_rejects_unsafe_ones():
    from qea.qfbench_images import ImageConfigError, parse_qfbench_task_dockerfile

    operations = parse_qfbench_task_dockerfile(
        """# task overlay
FROM finance-bench-sandbox:latest
WORKDIR /app
COPY data/input.csv /app/data/input.csv
RUN mkdir -p /app/output
"""
    )

    assert [(item.directive, item.arguments) for item in operations] == [
        ("WORKDIR", ("/app",)),
        ("COPY", ("data/input.csv", "/app/data/input.csv")),
        ("RUN", ("mkdir -p /app/output",)),
    ]
    with pytest.raises(ImageConfigError, match="unsupported task Dockerfile directive"):
        parse_qfbench_task_dockerfile(
            "FROM finance-bench-sandbox:latest\nENTRYPOINT [\"python\"]\n"
        )


def test_task_dockerfile_parser_accepts_both_official_base_families_only():
    from qea.qfbench_images import ImageConfigError, parse_qfbench_task_dockerfile

    for parent in (
        "finance-bench-sandbox:latest",
        "quantitative-finance-bench-sandbox:latest",
    ):
        assert parse_qfbench_task_dockerfile(f"FROM {parent}\n") == ()

    with pytest.raises(ImageConfigError, match="unsupported QFBench task parent image"):
        parse_qfbench_task_dockerfile("FROM python:3.11-slim\n")


def test_base_template_spec_records_immutable_base_and_applies_exact_task_steps(tmp_path):
    from qea.qfbench_images import (
        apply_qfbench_e2b_task_overlay,
        prepare_qfbench_base_template_overlay,
    )

    environment = tmp_path / "environment"
    (environment / "data").mkdir(parents=True)
    dockerfile = environment / "Dockerfile"
    dockerfile.write_text(
        "FROM finance-bench-sandbox:latest\n"
        "WORKDIR /app\n"
        "COPY data /app/data\n"
        "RUN mkdir -p /app/output\n"
    )
    (environment / "data" / "input.csv").write_text("x\n1\n")
    test_script = "uvx -p 3.11 -w pytest==8.4.1 pytest /tests/test_outputs.py\n"

    spec = prepare_qfbench_base_template_overlay(
        task_id="fixture-task",
        upstream_dockerfile=dockerfile,
        output_dir=tmp_path / "generated",
        base_template_id="base-template-id",
        base_build_id="base-build-id",
        role="verifier",
        dependencies=("uv==0.9.5",),
        benchmark_commit="0" * 40,
        verifier_test_script=test_script,
        cpu_count=2,
        memory_mb=4096,
        build_timeout_seconds=600,
    )

    payload = json.loads(spec.manifest_path.read_text())
    assert payload["base_template_id"] == "base-template-id"
    assert payload["base_build_id"] == "base-build-id"
    assert payload["published_template_id"] is None
    assert payload["cpu_count"] == 2
    assert payload["memory_mb"] == 4096
    assert payload["build_timeout_seconds"] == 600
    assert payload["verifier_uvx_warm_command"].endswith("pytest --version")
    assert payload["verifier_dependency_lock_command"].endswith(
        " > /opt/qea/verifier-requirements.lock"
    )

    class FakeBuilder:
        def __init__(self):
            self.calls = []

        def set_user(self, value):
            self.calls.append(("user", value))
            return self

        def set_workdir(self, value):
            self.calls.append(("workdir", value))
            return self

        def copy(self, source, destination):
            self.calls.append(("copy", source, destination))
            return self

        def run_cmd(self, command, user=None):
            self.calls.append(("run", command, user))
            return self

    builder = FakeBuilder()
    apply_qfbench_e2b_task_overlay(builder, spec)

    assert builder.calls == [
        ("user", "root"),
        ("workdir", "/app"),
        ("copy", "data", "/app/data"),
        ("run", "mkdir -p /app/output", "root"),
        ("run", "python -m pip install --no-cache-dir uv==0.9.5", "root"),
        ("run", "mkdir -p /opt/qea/uv-cache /opt/qea/uv-tools /opt/qea/uv-bin", "root"),
        (
            "run",
            "UV_CACHE_DIR=/opt/qea/uv-cache UV_TOOL_DIR=/opt/qea/uv-tools "
            "UV_TOOL_BIN_DIR=/opt/qea/uv-bin uvx -p 3.11 -w pytest==8.4.1 "
            "pytest --version",
            "root",
        ),
        (
            "run",
            "UV_CACHE_DIR=/opt/qea/uv-cache UV_TOOL_DIR=/opt/qea/uv-tools "
            "UV_TOOL_BIN_DIR=/opt/qea/uv-bin uvx -p 3.11 -w pytest==8.4.1 "
            "python -c 'import importlib.metadata as m; print(\"\\n\".join(sorted("
            "f\"{d.metadata.get('\"'\"'Name'\"'\"', '\"'\"'UNKNOWN'\"'\"')}=={d.version}\" "
            "for d in m.distributions())))' > /opt/qea/verifier-requirements.lock",
            "root",
        ),
    ]


def test_base_template_build_script_is_directly_invokable():
    repository = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "scripts/build_qfbench_e2b_base.py", "--help"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "--qfbench-root" in proc.stdout
    assert "--publish" in proc.stdout


def test_base_build_context_contains_only_official_docker_inputs(tmp_path):
    from qea.qfbench_images import prepare_qfbench_base_build_context

    snapshot = tmp_path / "snapshot"
    (snapshot / "docker").mkdir(parents=True)
    (snapshot / "docker" / "sandbox.Dockerfile").write_text(
        "FROM python:3.11-slim\nCOPY docker/requirements-sandbox.txt /tmp/requirements.txt\n"
    )
    (snapshot / "docker" / "requirements-sandbox.txt").write_text("numpy>=1.26\n")
    (snapshot / "tasks" / "secret-task" / "tests").mkdir(parents=True)
    (snapshot / "tasks" / "secret-task" / "tests" / "expected.json").write_text(
        '{"answer": 17}\n'
    )
    (snapshot / "tasks" / "secret-task" / "solution").mkdir()
    (snapshot / "tasks" / "secret-task" / "solution" / "solve.py").write_text(
        "print(17)\n"
    )

    context = prepare_qfbench_base_build_context(snapshot, tmp_path / "generated")

    assert sorted(
        path.relative_to(context).as_posix()
        for path in context.rglob("*")
        if path.is_file()
    ) == [
        "docker/requirements-sandbox.txt",
        "docker/sandbox.Dockerfile",
    ]


def test_published_task_manifest_is_idempotent_and_cannot_be_rebound(tmp_path):
    from qea.qfbench_images import (
        ImageConfigError,
        prepare_qfbench_base_template_overlay,
        record_published_template,
    )

    environment = tmp_path / "environment"
    (environment / "data").mkdir(parents=True)
    dockerfile = environment / "Dockerfile"
    dockerfile.write_text(
        "FROM finance-bench-sandbox:latest\nCOPY data /app/data\n"
    )
    data = environment / "data" / "input.csv"
    data.write_text("x\n1\n")
    kwargs = {
        "task_id": "fixture-task",
        "upstream_dockerfile": dockerfile,
        "output_dir": tmp_path / "generated",
        "base_template_id": "base-template-id",
        "base_build_id": "base-build-id",
        "role": "worker",
        "dependencies": (NEXAU_DEPENDENCY,),
        "benchmark_commit": "0" * 40,
        "cpu_count": 2,
        "memory_mb": 4096,
        "build_timeout_seconds": 600,
    }

    spec = prepare_qfbench_base_template_overlay(**kwargs)
    record_published_template(spec, template_id="task-template", build_id="task-build")
    same = prepare_qfbench_base_template_overlay(**kwargs)
    payload = json.loads(same.manifest_path.read_text())
    assert payload["published_template_id"] == "task-template"
    assert payload["published_build_id"] == "task-build"

    with pytest.raises(ImageConfigError, match="already published"):
        record_published_template(
            same, template_id="different-template", build_id="different-build"
        )

    data.write_text("x\n2\n")
    with pytest.raises(ImageConfigError, match="published manifest identity"):
        prepare_qfbench_base_template_overlay(**kwargs)
