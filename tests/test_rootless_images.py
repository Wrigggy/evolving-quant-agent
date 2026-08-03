from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from qea.backends.rootless_docker import CompletedCommand
from qea.benchmarks.qfbench import git_blob_oid


COMMIT = "024921eb507fcc0c4ffe3e0a96802724be1ae84a"
UPSTREAM_BASE = "docker.io/library/python@sha256:" + "a" * 64
QFBENCH_BASE = "sha256:" + "b" * 64
NEXAU_COMMIT = "35ee1861546db3cb280a6e17e38a74060d7c96c3"
DOCKER_HOST = "unix:///run/user/1013/docker.sock"


@dataclass(frozen=True)
class Call:
    argv: tuple[str, ...]
    input_bytes: bytes | None
    timeout_seconds: int | float | None


class RecordingRunner:
    def __init__(self, *replies: CompletedCommand) -> None:
        self.replies = list(replies)
        self.calls: list[Call] = []

    def run(self, argv, *, input_bytes=None, timeout_seconds=None):
        self.calls.append(Call(tuple(argv), input_bytes, timeout_seconds))
        if not self.replies:
            raise AssertionError(f"unexpected command: {tuple(argv)!r}")
        return self.replies.pop(0)


def _successful_worker_build_runner(
    *,
    image_id: str,
    dependency_lock: bytes,
) -> RecordingRunner:
    return RecordingRunner(
        CompletedCommand(0, (QFBENCH_BASE + "\n").encode(), b""),
        CompletedCommand(0, b"", b""),
        CompletedCommand(0, (QFBENCH_BASE + "\n").encode(), b""),
        CompletedCommand(0, (image_id + "\n").encode(), b""),
        CompletedCommand(
            0,
            json.dumps({"Id": image_id, "RepoDigests": []}).encode(),
            b"",
        ),
        CompletedCommand(0, b"29.4.1\n", b""),
        CompletedCommand(0, b'["name=rootless"]\n', b""),
        CompletedCommand(0, dependency_lock, b""),
        CompletedCommand(0, (QFBENCH_BASE + "\n").encode(), b""),
    )


def _write_manifest(root: Path, role: str, paths: list[Path]) -> None:
    records = []
    for path in sorted(paths):
        payload = path.read_bytes()
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "mode": "100755" if path.stat().st_mode & 0o111 else "100644",
                "git_blob_oid": git_blob_oid(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    (root / "MANIFEST.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "role": role,
                "repository_url": "https://github.com/QF-Bench/QuantitativeFinance-Bench.git",
                "commit": COMMIT,
                "task_ids": ["task-a"],
                "files": records,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    (root / ".qfbench-revision").write_text(COMMIT + "\n")


def _role_roots(tmp_path: Path) -> tuple[Path, Path]:
    public = tmp_path / "public"
    trusted = tmp_path / "trusted"
    (public / "docker").mkdir(parents=True)
    task = public / "tasks" / "task-a"
    (task / "environment" / "data").mkdir(parents=True)
    (public / "docker" / "sandbox.Dockerfile").write_text(
        "FROM python:3.11-slim\n"
        "COPY docker/requirements-sandbox.txt /tmp/requirements.txt\n"
        "RUN pip install -r /tmp/requirements.txt\n"
    )
    (public / "docker" / "requirements-sandbox.txt").write_text(
        "numpy>=1.26\npandas>=2.1\n"
    )
    (task / "instruction.md").write_text("Create /root/output/result.json\n")
    (task / "task.toml").write_text(
        "[agent]\ntimeout_sec = 900\n"
        "[verifier]\ntimeout_sec = 300\n"
        "[environment]\ncpus = 2\nmemory = '4G'\nbuild_timeout_sec = 600\n"
    )
    (task / "environment" / "Dockerfile").write_text(
        "FROM finance-bench-sandbox:latest\n"
        "COPY data /app/data/\n"
        "RUN mkdir -p /app/output\n"
    )
    (task / "environment" / "data" / "input.csv").write_text("x\n1\n")
    public_files = [
        path
        for path in public.rglob("*")
        if path.is_file() and path.name != "MANIFEST.json"
    ]
    _write_manifest(public, "public", public_files)

    tests = trusted / "tasks" / "task-a" / "tests"
    (tests / "reference_data").mkdir(parents=True)
    test_sh = tests / "test.sh"
    test_sh.write_text(
        "uvx -p 3.11 -w pytest==8.4.1 -w numpy==2.2.3 "
        "pytest /tests/test_outputs.py\n"
    )
    test_sh.chmod(0o700)
    (tests / "test_outputs.py").write_text("def test_output(): pass\n")
    (tests / "reference_data" / "expected.json").write_text('{"expected": 17}\n')
    trusted_files = [
        path
        for path in trusted.rglob("*")
        if path.is_file() and path.name != "MANIFEST.json"
    ]
    _write_manifest(trusted, "trusted-verifier", trusted_files)
    return public, trusted


def test_base_plan_pins_from_and_contains_only_public_base_inputs(tmp_path) -> None:
    from qea.rootless_images import prepare_rootless_image_plan

    public, _ = _role_roots(tmp_path)

    plan = prepare_rootless_image_plan(
        role="base",
        public_root=public,
        base_image_ref=UPSTREAM_BASE,
        cpu_count=2,
        memory_mb=4096,
        build_timeout_seconds=1800,
    )

    assert plan.task_id is None
    assert plan.base_image_ref == UPSTREAM_BASE
    assert plan.dockerfile_bytes.decode().splitlines()[0] == f"FROM {UPSTREAM_BASE}"
    assert {member.path for member in plan.context_files} == {
        "Dockerfile",
        "docker/requirements-sandbox.txt",
        "qea/sandbox-supervisor.py",
    }
    assert b"/usr/local/bin/qea-sandbox-supervisor" in plan.dockerfile_bytes
    assert b"qea-model-proxy" not in plan.dockerfile_bytes
    assert all("tests" not in member.path for member in plan.context_files)


def test_task_neutral_proxy_and_evolver_plans_are_role_minimal(tmp_path) -> None:
    from qea.rootless_images import prepare_rootless_image_plan

    public, _ = _role_roots(tmp_path)
    proxy = prepare_rootless_image_plan(
        role="proxy",
        public_root=public,
        base_image_ref=QFBENCH_BASE,
        cpu_count=1,
        memory_mb=512,
        build_timeout_seconds=600,
    )
    assert proxy.manifest_payload()["identity_kind"] == "plan"
    assert proxy.manifest_payload()["identity_sha256"] == proxy.identity_sha256
    evolver = prepare_rootless_image_plan(
        role="evolver",
        public_root=public,
        base_image_ref=QFBENCH_BASE,
        cpu_count=2,
        memory_mb=4096,
        build_timeout_seconds=600,
    )

    proxy_dockerfile = proxy.dockerfile_bytes.decode()
    proxy_entrypoint = next(
        member.payload.decode()
        for member in proxy.context_files
        if member.path == "qea/model-proxy-entrypoint.py"
    )
    assert proxy.task_id is None
    assert proxy_dockerfile.splitlines()[0] == (
        f"FROM qea-local-base:{'b' * 64}"
    )
    assert {member.path for member in proxy.context_files} == {
        "Dockerfile",
        "qea/__init__.py",
        "qea/model-proxy-entrypoint.py",
        "qea/model_proxy.py",
        "qea/repair_supervisor.py",
        "qea/run_qea_model_proxy.py",
        "qea/sandbox_backend.py",
    }
    assert "nexau" not in proxy_dockerfile.lower()
    assert (
        "COPY qea/repair_supervisor.py /usr/local/lib/qea/repair_supervisor.py"
        in proxy_dockerfile
    )
    assert "--allowed-model" in proxy_entrypoint
    assert "--required-provider" in proxy_entrypoint
    assert "required_provider" in proxy_entrypoint
    assert "--audit-file" in proxy_entrypoint
    assert "--denied-request-identity-sha256" in proxy_entrypoint
    assert all(
        marker not in json.dumps(proxy.manifest_payload()).lower()
        for marker in ("tasks/", "tests/", "reference", "solution")
    )

    evolver_dockerfile = evolver.dockerfile_bytes.decode()
    assert evolver.task_id is None
    assert evolver_dockerfile.splitlines()[0] == (
        f"FROM qea-local-base:{'b' * 64}"
    )
    assert NEXAU_COMMIT in evolver_dockerfile
    assert "/opt/qea/nexau-requirements.lock" in evolver_dockerfile
    assert "apt-get install -y --no-install-recommends git" in evolver_dockerfile
    assert {member.path for member in evolver.context_files} == {"Dockerfile"}
    assert all(
        marker not in json.dumps(evolver.manifest_payload()).lower()
        for marker in ("tasks/", "tests/", "reference", "solution")
    )
    changed_base = prepare_rootless_image_plan(
        role="evolver",
        public_root=public,
        base_image_ref="sha256:" + "d" * 64,
        cpu_count=2,
        memory_mb=4096,
        build_timeout_seconds=600,
    )
    assert changed_base.identity_sha256 != evolver.identity_sha256


def test_proxy_entrypoint_emits_required_provider_only_when_configured(
    tmp_path, monkeypatch
) -> None:
    import qea.rootless_images as images

    config_path = tmp_path / "proxy-config.json"
    token_path = tmp_path / "model-token"
    token_path.write_text("fixture-token\n")
    source = images._MODEL_PROXY_ENTRYPOINT.decode()
    source = source.replace(
        "Path('/run/qea-secrets/proxy-config.json')",
        f"Path({str(config_path)!r})",
    ).replace(
        "Path('/run/qea-secrets/model-token')",
        f"Path({str(token_path)!r})",
    )
    base_config = {
        "listen_host": "0.0.0.0",
        "listen_port": 8080,
        "upstream_base_url": "https://openrouter.ai/api/v1",
        "allowed_path_prefix": "/v1",
        "allowed_model": "deepseek/deepseek-v4-pro",
        "audit_file": "/run/qea-secrets/proxy-audit.jsonl",
        "denied_request_identities_sha256": [],
        "max_request_bytes": 1024,
        "max_response_bytes": 4096,
        "connect_timeout_seconds": 10.0,
        "read_timeout_seconds": 300.0,
    }
    captured = []

    def fake_execve(executable, argv, environment):
        captured.append((executable, tuple(argv), dict(environment)))
        raise SystemExit(0)

    monkeypatch.setattr(os, "execve", fake_execve)
    for required_provider in (None, "deepseek"):
        payload = dict(base_config)
        if required_provider is not None:
            payload["required_provider"] = required_provider
        config_path.write_text(json.dumps(payload))
        with pytest.raises(SystemExit, match="0"):
            exec(compile(source, "model-proxy-entrypoint.py", "exec"), {})

    legacy_argv = captured[0][1]
    pinned_argv = captured[1][1]
    assert "--required-provider" not in legacy_argv
    index = pinned_argv.index("--required-provider")
    assert pinned_argv[index : index + 2] == (
        "--required-provider",
        "deepseek",
    )


def test_trusted_host_build_network_is_explicit_and_identity_bound(tmp_path) -> None:
    from qea.rootless_images import RootlessImageError, prepare_rootless_image_plan

    public, _ = _role_roots(tmp_path)
    common = {
        "role": "evolver",
        "public_root": public,
        "base_image_ref": QFBENCH_BASE,
        "cpu_count": 2,
        "memory_mb": 4096,
        "build_timeout_seconds": 600,
    }

    default = prepare_rootless_image_plan(**common)
    trusted_host = prepare_rootless_image_plan(**common, build_network="host")

    assert default.build_network == "default"
    assert trusted_host.build_network == "host"
    assert trusted_host.identity_sha256 != default.identity_sha256
    assert trusted_host.manifest_payload()["build_network"] == "host"
    with pytest.raises(RootlessImageError, match="build network"):
        prepare_rootless_image_plan(**common, build_network="bridge")


def test_worker_plan_can_bind_an_immutable_task_neutral_nexau_runtime(
    tmp_path,
) -> None:
    from qea.rootless_images import RootlessImageError, prepare_rootless_image_plan

    public, _ = _role_roots(tmp_path)
    donor = "sha256:" + "e" * 64
    common = {
        "role": "worker",
        "task_id": "task-a",
        "public_root": public,
        "base_image_ref": QFBENCH_BASE,
        "cpu_count": 2,
        "memory_mb": 4096,
        "build_timeout_seconds": 600,
        "build_network": "host",
    }

    online = prepare_rootless_image_plan(**common)
    offline = prepare_rootless_image_plan(
        **common,
        nexau_runtime_image_ref=donor,
    )
    dockerfile = offline.dockerfile_bytes.decode()

    assert offline.nexau_runtime_image_ref == donor
    assert offline.identity_sha256 != online.identity_sha256
    assert dockerfile.startswith(
        "FROM qea-local-nexau:" + "e" * 64 + " AS qea-nexau-runtime\n"
    )
    assert "FROM qea-local-base:" + "b" * 64 in dockerfile
    assert "COPY --from=qea-nexau-runtime /opt/qea /opt/qea" in dockerfile
    assert "git+https://github.com/nex-agi/NexAU.git" not in dockerfile
    assert "uv python install" not in dockerfile

    with pytest.raises(RootlessImageError, match="NexAU runtime image"):
        prepare_rootless_image_plan(
            **common,
            nexau_runtime_image_ref="qea/nexau:mutable",
        )
    with pytest.raises(RootlessImageError, match="worker image plan"):
        prepare_rootless_image_plan(
            **{**common, "role": "evolver", "task_id": None},
            nexau_runtime_image_ref=donor,
        )


@pytest.mark.parametrize("role", ("base", "proxy", "evolver"))
def test_task_neutral_roles_reject_task_and_trusted_inputs(
    tmp_path, role: str
) -> None:
    from qea.rootless_images import RootlessImageError, prepare_rootless_image_plan

    public, trusted = _role_roots(tmp_path)
    common = {
        "role": role,
        "public_root": public,
        "base_image_ref": QFBENCH_BASE,
        "cpu_count": 2,
        "memory_mb": 4096,
        "build_timeout_seconds": 600,
    }
    with pytest.raises(RootlessImageError, match="cannot name a task"):
        prepare_rootless_image_plan(**common, task_id="task-a")
    with pytest.raises(RootlessImageError, match="cannot name a task"):
        prepare_rootless_image_plan(**common, trusted_root=trusted)


def test_task_roles_enforce_task_and_trusted_root_matrix(tmp_path) -> None:
    from qea.rootless_images import RootlessImageError, prepare_rootless_image_plan

    public, trusted = _role_roots(tmp_path)
    common = {
        "public_root": public,
        "base_image_ref": QFBENCH_BASE,
        "cpu_count": 2,
        "memory_mb": 4096,
        "build_timeout_seconds": 600,
    }
    with pytest.raises(RootlessImageError, match="requires a valid task_id"):
        prepare_rootless_image_plan(role="worker", **common)
    with pytest.raises(RootlessImageError, match="cannot name a trusted root"):
        prepare_rootless_image_plan(
            role="worker", task_id="task-a", trusted_root=trusted, **common
        )
    with pytest.raises(RootlessImageError, match="requires trusted_root"):
        prepare_rootless_image_plan(role="verifier", task_id="task-a", **common)


def test_worker_plan_contains_public_environment_and_pinned_nexau_only(tmp_path) -> None:
    from qea.rootless_images import prepare_rootless_image_plan

    public, _ = _role_roots(tmp_path)

    plan = prepare_rootless_image_plan(
        role="worker",
        task_id="task-a",
        public_root=public,
        base_image_ref=QFBENCH_BASE,
        cpu_count=2,
        memory_mb=4096,
        build_timeout_seconds=600,
    )

    dockerfile = plan.dockerfile_bytes.decode()
    assert f"FROM qea-local-base:{'b' * 64}" in dockerfile
    assert plan.base_image_ref == QFBENCH_BASE
    assert NEXAU_COMMIT in dockerfile
    assert "/opt/qea/nexau-requirements.lock" in dockerfile
    git_install = (
        "apt-get update && apt-get install -y --no-install-recommends git "
        "&& rm -rf /var/lib/apt/lists/*"
    )
    assert git_install in dockerfile
    assert dockerfile.index("uv venv --python 3.12") < dockerfile.index(
        git_install
    )
    assert dockerfile.index(git_install) < dockerfile.index(
        f"git+https://github.com/nex-agi/NexAU.git@{NEXAU_COMMIT}"
    )
    assert {member.path for member in plan.context_files} == {
        "Dockerfile",
        "data/input.csv",
    }
    assert "tests" not in json.dumps(plan.manifest_payload())
    assert "solution" not in json.dumps(plan.manifest_payload())


def test_verifier_plan_reads_test_lock_declaration_but_never_copies_tests(tmp_path) -> None:
    from qea.rootless_images import prepare_rootless_image_plan

    public, trusted = _role_roots(tmp_path)

    plan = prepare_rootless_image_plan(
        role="verifier",
        task_id="task-a",
        public_root=public,
        trusted_root=trusted,
        base_image_ref=QFBENCH_BASE,
        cpu_count=2,
        memory_mb=4096,
        build_timeout_seconds=600,
    )

    dockerfile = plan.dockerfile_bytes.decode()
    assert "pytest==8.4.1" in dockerfile
    assert "numpy==2.2.3" in dockerfile
    assert "pytest --version" in dockerfile
    assert "/opt/qea/verifier-requirements.lock" in dockerfile
    assert (
        "cp -a /opt/qea/uv-cache /opt/qea/uv-cache-seed" in dockerfile
    )
    assert "/tests/test_outputs.py" not in dockerfile
    assert all("tests" not in member.path for member in plan.context_files)
    assert plan.verifier_test_script_sha256 == hashlib.sha256(
        (trusted / "tasks/task-a/tests/test.sh").read_bytes()
    ).hexdigest()
    assert "expected" not in json.dumps(plan.manifest_payload())


def test_plan_rejects_mutable_base_tampered_manifest_and_secret_extra(tmp_path) -> None:
    from qea.rootless_images import RootlessImageError, prepare_rootless_image_plan

    public, _ = _role_roots(tmp_path)
    with pytest.raises(RootlessImageError, match="immutable base image"):
        prepare_rootless_image_plan(
            role="base",
            public_root=public,
            base_image_ref="python:3.11-slim",
            cpu_count=2,
            memory_mb=4096,
            build_timeout_seconds=1800,
        )

    data = public / "tasks/task-a/environment/data/input.csv"
    data.write_text("x\n2\n")
    with pytest.raises(RootlessImageError, match="manifest hash mismatch"):
        prepare_rootless_image_plan(
            role="worker",
            task_id="task-a",
            public_root=public,
            base_image_ref=QFBENCH_BASE,
            cpu_count=2,
            memory_mb=4096,
            build_timeout_seconds=600,
        )

    data.write_text("x\n1\n")
    (public / ".env").write_text("API_KEY=secret\n")
    with pytest.raises(RootlessImageError, match="unmanifested source file"):
        prepare_rootless_image_plan(
            role="worker",
            task_id="task-a",
            public_root=public,
            base_image_ref=QFBENCH_BASE,
            cpu_count=2,
            memory_mb=4096,
            build_timeout_seconds=600,
        )


def test_plan_rejects_non_regular_unmanifested_source_entry(tmp_path) -> None:
    from qea.rootless_images import RootlessImageError, prepare_rootless_image_plan

    public, _ = _role_roots(tmp_path)
    os.mkfifo(public / "unexpected.pipe")

    with pytest.raises(RootlessImageError, match="non-regular source entry"):
        prepare_rootless_image_plan(
            role="base",
            public_root=public,
            base_image_ref=UPSTREAM_BASE,
            cpu_count=2,
            memory_mb=4096,
            build_timeout_seconds=1800,
        )

def test_execute_build_records_final_image_and_dependency_lock(tmp_path) -> None:
    from qea.rootless_images import (
        execute_rootless_image_build,
        prepare_rootless_image_plan,
    )

    public, _ = _role_roots(tmp_path)
    plan = prepare_rootless_image_plan(
        role="worker",
        task_id="task-a",
        public_root=public,
        base_image_ref=QFBENCH_BASE,
        cpu_count=2,
        memory_mb=4096,
        build_timeout_seconds=600,
    )
    image_id = "sha256:" + "c" * 64
    local_base_tag = "qea-local-base:" + "b" * 64
    runner = _successful_worker_build_runner(
        image_id=image_id,
        dependency_lock=b"nexau==0.3.9\nnumpy==2.2.3\n",
    )

    result = execute_rootless_image_build(
        plan,
        output_root=tmp_path / "images",
        docker_host=DOCKER_HOST,
        expected_uid=1013,
        runner=runner,
        at=datetime(2026, 7, 28, 14, 0, tzinfo=timezone.utc),
    )

    assert runner.calls[0].argv[-5:] == (
        "image",
        "inspect",
        "--format",
        "{{.Id}}",
    ) + (QFBENCH_BASE,)
    assert runner.calls[1].argv[-4:] == (
        "image",
        "tag",
        QFBENCH_BASE,
        local_base_tag,
    )
    assert runner.calls[2].argv[-1] == local_base_tag
    build_argv = runner.calls[3].argv
    assert build_argv[:4] == ("docker", "--host", DOCKER_HOST, "build")
    assert "--pull=false" in build_argv
    assert ("--network", "default") == _pair(build_argv, "--network")
    assert result.image_id == image_id
    assert result.plan_identity_sha256 == plan.identity_sha256
    assert result.output_dir.name == result.result_identity_sha256
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["plan_identity_sha256"] == plan.identity_sha256
    assert manifest["result_identity_sha256"] == result.result_identity_sha256
    assert manifest["identity_kind"] == "measured-result"
    assert manifest["identity_sha256"] == result.result_identity_sha256
    assert manifest["image_id"] == image_id
    assert manifest["local_base_tag"] == local_base_tag
    assert manifest["local_base_image_id"] == QFBENCH_BASE
    assert manifest["docker_version"] == "29.4.1"
    assert manifest["docker_security_options"] == ["name=rootless"]
    lock = result.output_dir / "dependency-lock.txt"
    assert manifest["dependency_lock_sha256"] == hashlib.sha256(
        lock.read_bytes()
    ).hexdigest()
    assert (result.output_dir / "context/Dockerfile").is_file()
    assert not result.output_dir.with_name(plan.identity_sha256 + ".partial").exists()
    assert runner.calls[-1].argv[-1] == local_base_tag


def test_execute_worker_build_measures_immutable_nexau_runtime_donor(
    tmp_path,
) -> None:
    from qea.rootless_images import (
        execute_rootless_image_build,
        prepare_rootless_image_plan,
    )

    public, _ = _role_roots(tmp_path)
    donor = "sha256:" + "e" * 64
    donor_tag = "qea-local-nexau:" + "e" * 64
    image_id = "sha256:" + "c" * 64
    plan = prepare_rootless_image_plan(
        role="worker",
        task_id="task-a",
        public_root=public,
        base_image_ref=QFBENCH_BASE,
        cpu_count=2,
        memory_mb=4096,
        build_timeout_seconds=600,
        build_network="host",
        nexau_runtime_image_ref=donor,
    )
    runner = RecordingRunner(
        CompletedCommand(0, (QFBENCH_BASE + "\n").encode(), b""),
        CompletedCommand(0, b"", b""),
        CompletedCommand(0, (QFBENCH_BASE + "\n").encode(), b""),
        CompletedCommand(0, (donor + "\n").encode(), b""),
        CompletedCommand(0, b"", b""),
        CompletedCommand(0, (donor + "\n").encode(), b""),
        CompletedCommand(0, (image_id + "\n").encode(), b""),
        CompletedCommand(
            0,
            json.dumps({"Id": image_id, "RepoDigests": []}).encode(),
            b"",
        ),
        CompletedCommand(0, b"29.4.1\n", b""),
        CompletedCommand(0, b'["name=rootless"]\n', b""),
        CompletedCommand(0, b"nexau==0.3.9\n", b""),
        CompletedCommand(0, (QFBENCH_BASE + "\n").encode(), b""),
        CompletedCommand(0, (donor + "\n").encode(), b""),
    )

    result = execute_rootless_image_build(
        plan,
        output_root=tmp_path / "images",
        docker_host=DOCKER_HOST,
        expected_uid=1013,
        runner=runner,
        at=datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc),
    )

    assert runner.calls[3].argv[-1] == donor
    assert runner.calls[4].argv[-3:] == ("tag", donor, donor_tag)
    assert runner.calls[5].argv[-1] == donor_tag
    assert _pair(runner.calls[6].argv, "--network") == ("--network", "host")
    assert runner.calls[-1].argv[-1] == donor_tag
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["local_nexau_runtime_tag"] == donor_tag
    assert manifest["local_nexau_runtime_image_id"] == donor


def test_execute_build_result_identity_changes_with_measured_lock(tmp_path) -> None:
    from qea.rootless_images import (
        execute_rootless_image_build,
        prepare_rootless_image_plan,
    )

    public, _ = _role_roots(tmp_path)
    plan = prepare_rootless_image_plan(
        role="worker",
        task_id="task-a",
        public_root=public,
        base_image_ref=QFBENCH_BASE,
        cpu_count=2,
        memory_mb=4096,
        build_timeout_seconds=600,
    )
    image_id = "sha256:" + "c" * 64
    first = execute_rootless_image_build(
        plan,
        output_root=tmp_path / "images",
        docker_host=DOCKER_HOST,
        expected_uid=1013,
        runner=_successful_worker_build_runner(
            image_id=image_id,
            dependency_lock=b"nexau==0.3.9\ntransitive==1.0\n",
        ),
        at=datetime(2026, 7, 28, 14, 0, tzinfo=timezone.utc),
    )
    second = execute_rootless_image_build(
        plan,
        output_root=tmp_path / "images",
        docker_host=DOCKER_HOST,
        expected_uid=1013,
        runner=_successful_worker_build_runner(
            image_id=image_id,
            dependency_lock=b"nexau==0.3.9\ntransitive==2.0\n",
        ),
        at=datetime(2026, 7, 28, 15, 0, tzinfo=timezone.utc),
    )

    assert first.plan_identity_sha256 == second.plan_identity_sha256
    assert first.result_identity_sha256 != second.result_identity_sha256
    assert first.output_dir != second.output_dir
    assert first.output_dir.name == first.result_identity_sha256
    assert second.output_dir.name == second.result_identity_sha256


def test_execute_build_refuses_system_socket_and_existing_identity(tmp_path) -> None:
    from qea.rootless_images import (
        RootlessImageError,
        execute_rootless_image_build,
        prepare_rootless_image_plan,
    )

    public, _ = _role_roots(tmp_path)
    plan = prepare_rootless_image_plan(
        role="base",
        public_root=public,
        base_image_ref=UPSTREAM_BASE,
        cpu_count=2,
        memory_mb=4096,
        build_timeout_seconds=1800,
    )
    with pytest.raises(RootlessImageError, match="rootless Docker socket"):
        execute_rootless_image_build(
            plan,
            output_root=tmp_path / "images",
            docker_host="unix:///var/run/docker.sock",
            expected_uid=1013,
            runner=RecordingRunner(),
        )

    existing = tmp_path / "images" / f"{plan.identity_sha256}.partial"
    existing.mkdir(parents=True)
    with pytest.raises(RootlessImageError, match="existing partial image identity"):
        execute_rootless_image_build(
            plan,
            output_root=tmp_path / "images",
            docker_host=DOCKER_HOST,
            expected_uid=1013,
            runner=RecordingRunner(),
        )


def test_rootless_image_cli_plan_only_writes_nothing(tmp_path) -> None:
    public, _ = _role_roots(tmp_path)
    output = tmp_path / "images"
    repository = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        (
            sys.executable,
            "scripts/build_qfbench_rootless_images.py",
            "--role",
            "base",
            "--public-root",
            str(public),
            "--manifest-root",
            str(output),
            "--base-image-ref",
            UPSTREAM_BASE,
            "--docker-host",
            DOCKER_HOST,
            "--expected-uid",
            "1013",
            "--plan-only",
        ),
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "identity sha256:" in result.stdout
    assert "context files: 3" in result.stdout
    assert not output.exists()


def test_rootless_image_cli_accepts_task_neutral_evolver_role(tmp_path) -> None:
    public, _ = _role_roots(tmp_path)
    output = tmp_path / "images"
    repository = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        (
            sys.executable,
            "scripts/build_qfbench_rootless_images.py",
            "--role",
            "evolver",
            "--public-root",
            str(public),
            "--manifest-root",
            str(output),
            "--base-image-ref",
            QFBENCH_BASE,
            "--docker-host",
            DOCKER_HOST,
            "--expected-uid",
            "1013",
            "--build-network",
            "host",
            "--plan-only",
        ),
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "role: evolver" in result.stdout
    assert "task: None" in result.stdout
    assert "context files: 1" in result.stdout
    assert "build network: host" in result.stdout
    assert not output.exists()


def _pair(argv: tuple[str, ...], option: str) -> tuple[str, str]:
    index = argv.index(option)
    return argv[index], argv[index + 1]
