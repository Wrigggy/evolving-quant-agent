import hashlib
import importlib
import importlib.abc
import json
import os
import sys
from dataclasses import fields, replace
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from qea.benchmarks.qfbench import git_blob_oid


COMMIT = "024921eb507fcc0c4ffe3e0a96802724be1ae84a"


def _write_role_manifest(root: Path, role: str) -> None:
    records = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "MANIFEST.json":
            continue
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


def _refresh_manifest_record(root: Path, relative_path: str) -> None:
    manifest_path = root / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    payload = (root / relative_path).read_bytes()
    record = next(
        item for item in manifest["files"] if item["path"] == relative_path
    )
    record.update(
        {
            "git_blob_oid": git_blob_oid(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    )


def _write_role_roots(public: Path, trusted: Path) -> None:
    environment = public / "tasks/task-a/environment"
    (environment / "data").mkdir(parents=True)
    (public / "docker").mkdir()
    (public / "docker/sandbox.Dockerfile").write_text("FROM fixture\n")
    (public / "docker/requirements-sandbox.txt").write_text("numpy==2.2.3\n")
    (public / "tasks/task-a/instruction.md").write_text("Produce result.json\n")
    (public / "tasks/task-a/task.toml").write_text("[agent]\ntimeout_sec=1800\n")
    (environment / "Dockerfile").write_text("FROM fixture\n")
    (environment / "data/input.csv").write_text("x\n1\n")
    _write_role_manifest(public, "public")

    tests = trusted / "tasks/task-a/tests"
    (tests / "reference_data").mkdir(parents=True)
    (tests / "test.sh").write_text("pytest /tests/test_outputs.py\n")
    (tests / "test_outputs.py").write_text("def test_output(): pass\n")
    (tests / "reference_data/expected.json").write_text('{"expected": 17}\n')
    _write_role_manifest(trusted, "trusted-verifier")


def _resource(*, cpu: int = 1, memory: int = 512, role: str = "evolver"):
    from qea.executors.sandbox_runtime import SandboxResourceContract

    tmpfs = {"/tmp": 64, "/qea": 128}
    if role == "proxy":
        tmpfs["/run/qea-secrets"] = 16
    return SandboxResourceContract(
        cpu_count=cpu,
        memory_mb=memory,
        pids_limit=64,
        timeout_seconds=600,
        writable_tmpfs_mb=tmpfs,
    )


def _valid_config(tmp_path):
    from qea.resource_lease import HostHeadroomPolicy, ResourceCapacity
    from qea.rootless_full_harness import (
        RoleExecutionLimits,
        RootlessFullHarnessConfig,
    )

    public = tmp_path / "public"
    trusted = tmp_path / "trusted"
    public.mkdir(parents=True)
    trusted.mkdir()
    _write_role_roots(public, trusted)
    trusted.chmod(0o700)
    token = tmp_path / "model-token"
    token.write_text("fixture-token\n")
    token.chmod(0o600)
    uid = os.getuid()
    return RootlessFullHarnessConfig(
        docker_host=f"unix:///run/user/{uid}/docker.sock",
        expected_uid=uid,
        public_root=public,
        trusted_root=trusted,
        token_file=token,
        upstream_base_url="https://openrouter.ai/api/v1",
        allowed_path_prefix="/v1",
        allowed_model="provider/model",
        evolver_resources=_resource(role="evolver"),
        proxy_resources=_resource(role="proxy"),
        worker_limits=RoleExecutionLimits(
            pids_limit=256,
            timeout_seconds=5400,
            writable_tmpfs_mb={"/app": 2048, "/qea": 512, "/tmp": 256},
        ),
        verifier_limits=RoleExecutionLimits(
            pids_limit=256,
            timeout_seconds=5400,
            writable_tmpfs_mb={
                "/app": 2048,
                "/logs": 128,
                "/opt/qea/uv-cache": 256,
                "/opt/qea/uv-tools": 64,
                "/qea": 512,
                "/tests": 128,
                "/tmp": 256,
            },
        ),
        capacity=ResourceCapacity(
            cpu_count=16,
            memory_mb=32768,
            pids_limit=4096,
            tmpfs_mb=16384,
            sandboxes=16,
        ),
        headroom=HostHeadroomPolicy(
            max_load_1m=24,
            min_available_memory_mb=4096,
            min_free_disk_mb=8192,
            min_free_inodes=1000,
        ),
        worker_concurrency=8,
        verifier_concurrency=4,
    )


def _catalog(*, identity: str = "b" * 64, worker_cpu: int = 3):
    from qea.executors.sandbox_runtime import SandboxResourceContract
    from qea.rootless_runtime import RootlessRuntimeCatalog, RootlessTaskRuntime

    worker_resources = SandboxResourceContract(
        cpu_count=worker_cpu,
        memory_mb=6144,
        pids_limit=256,
        timeout_seconds=5400,
        writable_tmpfs_mb={"/app": 2048, "/qea": 512, "/tmp": 256},
    )
    verifier_resources = SandboxResourceContract(
        cpu_count=worker_cpu,
        memory_mb=6144,
        pids_limit=256,
        timeout_seconds=5400,
        writable_tmpfs_mb={
            "/app": 2048,
            "/logs": 128,
            "/opt/qea/uv-cache": 256,
            "/opt/qea/uv-tools": 64,
            "/qea": 512,
            "/tests": 128,
            "/tmp": 256,
        },
    )
    task = RootlessTaskRuntime(
        task_id="task-a",
        worker_image_ref="sha256:" + "4" * 64,
        verifier_image_ref="sha256:" + "5" * 64,
        worker_resources=worker_resources,
        verifier_resources=verifier_resources,
        identity_sha256="c" * 64,
    )
    return RootlessRuntimeCatalog(
        benchmark_commit="024921eb507fcc0c4ffe3e0a96802724be1ae84a",
        base_image_ref="sha256:" + "1" * 64,
        evolver_image_ref="sha256:" + "2" * 64,
        proxy_image_ref="sha256:" + "3" * 64,
        tasks=MappingProxyType({"task-a": task}),
        image_set_identity_sha256="a" * 64,
        identity_sha256=identity,
    )


def _healthy_snapshot():
    from qea.resource_lease import HostHealthSnapshot

    return HostHealthSnapshot(
        load_1m=0,
        available_memory_mb=65536,
        free_disk_mb=65536,
        free_inodes=65536,
    )


def _selected_image_set(catalog, config, *, proxy_cpu: int = 1):
    source_sha = hashlib.sha256(
        (config.public_root / "MANIFEST.json").read_bytes()
    ).hexdigest()
    verifier_sha = hashlib.sha256(
        (config.trusted_root / "tasks/task-a/tests/test.sh").read_bytes()
    ).hexdigest()
    docker_identity = {
        "version": "29.4.1",
        "security_options": ["name=rootless"],
    }

    def entry(role, image_id, *, cpu, memory, test_sha=None):
        return {
            "role": role,
            "image_id": image_id,
            "source_manifest_sha256": source_sha,
            "verifier_test_script_sha256": test_sha,
            "resource_contract": {"cpu_count": cpu, "memory_mb": memory},
            "docker_identity": {
                "version": docker_identity["version"],
                "security_options": list(docker_identity["security_options"]),
            },
        }

    return SimpleNamespace(
        benchmark_commit=catalog.benchmark_commit,
        task_ids=tuple(catalog.tasks),
        identity_sha256=catalog.image_set_identity_sha256,
        base=entry(
            "base", catalog.base_image_ref, cpu=2, memory=4096
        ),
        evolver=entry(
            "evolver", catalog.evolver_image_ref, cpu=1, memory=512
        ),
        proxy=entry(
            "proxy", catalog.proxy_image_ref, cpu=proxy_cpu, memory=512
        ),
        tasks=(
            {
                "task_id": "task-a",
                "worker": entry(
                    "worker",
                    catalog.tasks["task-a"].worker_image_ref,
                    cpu=3,
                    memory=6144,
                ),
                "verifier": entry(
                    "verifier",
                    catalog.tasks["task-a"].verifier_image_ref,
                    cpu=3,
                    memory=6144,
                    test_sha=verifier_sha,
                ),
            },
        ),
    )


def _patch_catalog(monkeypatch, catalog, *, config, image_set=None) -> None:
    from qea.backends.rootless_docker import (
        RootlessDockerBackend,
        RootlessDockerPreflight,
    )
    import qea.rootless_full_harness as rootless_full_harness
    import qea.rootless_image_set as rootless_image_set
    import qea.rootless_runtime as rootless_runtime

    monkeypatch.setattr(
        rootless_runtime,
        "load_rootless_runtime_catalog",
        lambda *args, **kwargs: catalog,
    )
    selected = image_set or _selected_image_set(catalog, config)
    monkeypatch.setattr(
        rootless_image_set.RootlessImageSet,
        "load",
        classmethod(lambda cls, path: selected),
    )
    monkeypatch.setattr(
        rootless_full_harness,
        "_default_health_probe",
        lambda root: _healthy_snapshot,
    )

    def fake_preflight(
        self,
        *,
        expected_server_version,
        expected_security_options,
        image_ids,
    ):
        return RootlessDockerPreflight.measured(
            docker_host=self.docker_host,
            actual_uid=config.expected_uid,
            server_version=expected_server_version,
            security_options=tuple(sorted(expected_security_options)),
            image_ids=tuple(sorted(image_ids)),
        )

    monkeypatch.setattr(RootlessDockerBackend, "preflight", fake_preflight)


def _task(*, cpus: int = 3):
    return SimpleNamespace(
        task_id="task-a",
        cpus=cpus,
        memory_mb=6144,
        agent_timeout_seconds=1800,
        verifier_timeout_seconds=1800,
    )


def test_rootless_full_harness_exposes_frozen_runtime_schema() -> None:
    from qea.rootless_full_harness import (
        RoleExecutionLimits,
        RootlessFullHarnessConfig,
        RootlessFullHarnessRuntime,
        build_rootless_full_harness_runtime,
    )

    assert RoleExecutionLimits.__dataclass_params__.frozen is True
    assert RootlessFullHarnessConfig.__dataclass_params__.frozen is True
    assert RootlessFullHarnessRuntime.__dataclass_params__.frozen is True
    assert {field.name for field in fields(RoleExecutionLimits)} == {
        "pids_limit",
        "timeout_seconds",
        "writable_tmpfs_mb",
    }
    assert callable(build_rootless_full_harness_runtime)


def test_rootless_optional_extra_is_focused_and_e2b_independent() -> None:
    from pathlib import Path
    tomllib = pytest.importorskip("tomllib")

    project = tomllib.loads(Path("pyproject.toml").read_text())
    assert project["project"]["optional-dependencies"]["qfbench-rootless"] == [
        "PyYAML>=6.0"
    ]


def test_approved_rootless_factory_constructs_when_all_e2b_modules_are_blocked(
    tmp_path, monkeypatch,
) -> None:
    import qea.rootless_full_harness as module

    class RejectE2BFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "e2b" or fullname.startswith("e2b.") or fullname.startswith(
                "qea.e2b"
            ) or fullname.startswith("qea.executors.e2b_"):
                raise ModuleNotFoundError(fullname)
            return None

    refresh = {
        name: loaded
        for name, loaded in tuple(sys.modules.items())
        if name in {"qea.rootless_runtime", "qea.executors.sandbox_nexau"}
        or name.startswith("qea.e2b")
        or name.startswith("qea.executors.e2b_")
    }
    for name in refresh:
        sys.modules.pop(name, None)
    finder = RejectE2BFinder()
    sys.meta_path.insert(0, finder)
    runtime = None
    try:
        selected = _catalog()
        config = _valid_config(tmp_path / "config")
        _patch_catalog(monkeypatch, selected, config=config)
        runtime = module.build_rootless_full_harness_runtime(
            config=config,
            image_set_manifest=tmp_path / "image-set.json",
            benchmark_commit=selected.benchmark_commit,
            tasks=(_task(),),
            run_id="no-e2b-approved",
            results_root=tmp_path / "results",
        )
        assert runtime.backend.backend_name == "rootless-docker"
    finally:
        if runtime is not None:
            runtime.close()
        sys.meta_path.remove(finder)
        for name in tuple(sys.modules):
            if name in {"qea.rootless_runtime", "qea.executors.sandbox_nexau"}:
                sys.modules.pop(name, None)
        sys.modules.update(refresh)


def test_rootless_config_normalizes_immutable_limits_and_private_paths(tmp_path) -> None:
    config = _valid_config(tmp_path)

    assert config.public_root == (tmp_path / "public").resolve()
    assert config.trusted_root == (tmp_path / "trusted").resolve()
    assert config.token_file == (tmp_path / "model-token").resolve()
    assert type(config.worker_limits.writable_tmpfs_mb) is MappingProxyType
    with pytest.raises(TypeError):
        config.worker_limits.writable_tmpfs_mb["/new"] = 1


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"expected_uid": 0}, "expected_uid"),
        ({"docker_host": "unix:///var/run/docker.sock"}, "rootless"),
        ({"upstream_base_url": "http://openrouter.ai/api/v1"}, "HTTPS"),
        ({"upstream_base_url": "https://user:pass@openrouter.ai/api/v1"}, "HTTPS"),
        ({"upstream_base_url": "https://openrouter.ai/api/%2e%2e/v1"}, "unsafe"),
        ({"upstream_base_url": "https://openrouter.ai/api\\v1"}, "unsafe"),
        ({"allowed_path_prefix": "api/v1"}, "path prefix"),
        ({"allowed_path_prefix": "/v1/%2e%2e/admin"}, "path prefix"),
        ({"allowed_path_prefix": "/v1\\admin"}, "path prefix"),
        ({"allowed_model": ""}, "allowed_model"),
        ({"allowed_model": " provider/model"}, "allowed_model"),
        ({"allowed_model": "provider/model\n"}, "allowed_model"),
        ({"allowed_model": "m" * 257}, "allowed_model"),
        ({"worker_concurrency": 0}, "worker_concurrency"),
        ({"verifier_concurrency": 0}, "verifier_concurrency"),
    ],
)
def test_rootless_config_rejects_unsafe_provider_socket_and_concurrency(
    tmp_path, changes, message
) -> None:
    config = _valid_config(tmp_path)
    with pytest.raises((ValueError, RuntimeError), match=message):
        replace(config, **changes)


def test_rootless_config_rejects_overlapping_roots_and_public_token(tmp_path) -> None:
    config = _valid_config(tmp_path)
    (config.public_root / "trusted").mkdir(mode=0o700)
    with pytest.raises((ValueError, RuntimeError), match="disjoint"):
        replace(config, trusted_root=config.public_root / "trusted")

    config.token_file.chmod(0o644)
    with pytest.raises((ValueError, RuntimeError), match="owner-only"):
        replace(config)

    public_token = config.public_root / "token"
    public_token.write_text("forbidden\n")
    public_token.chmod(0o600)
    with pytest.raises((ValueError, RuntimeError), match="outside public and trusted"):
        replace(config, token_file=public_token)


def test_rootless_config_preserves_openrouter_base_path_and_proxy_route(tmp_path) -> None:
    from qea.model_proxy import _ModelProxyHandler, _ProxyPolicy, _parse_upstream

    config = _valid_config(tmp_path)
    upstream = _parse_upstream(config.upstream_base_url)
    policy = _ProxyPolicy(
        upstream=upstream,
        prefix=config.allowed_path_prefix,
        token="fixture-token",
        allowed_model=config.allowed_model,
        required_provider="deepseek",
        audit_file=tmp_path / "unused-audit.jsonl",
        denied_request_identities_sha256=frozenset(),
        max_request_bytes=1,
        max_response_bytes=1,
        connect_timeout_seconds=1.0,
        read_timeout_seconds=1.0,
    )
    handler = object.__new__(_ModelProxyHandler)

    assert upstream.base_path == "/api/v1"
    assert handler._route("/v1/chat/completions", policy) == (
        "/api/v1/chat/completions"
    )


def test_rootless_config_rejects_unsafe_required_provider(tmp_path) -> None:
    config = _valid_config(tmp_path)

    with pytest.raises((ValueError, RuntimeError), match="provider"):
        replace(config, required_provider=" DeepSeek")


@pytest.mark.parametrize(
    ("field_name", "missing_mount"),
    [
        ("evolver_resources", "/qea"),
        ("proxy_resources", "/run/qea-secrets"),
        ("worker_limits", "/app"),
        ("verifier_limits", "/tests"),
    ],
)
def test_rootless_config_rejects_missing_role_tmpfs_mounts(
    tmp_path, field_name, missing_mount
) -> None:
    config = _valid_config(tmp_path)
    role_config = getattr(config, field_name)
    tmpfs = dict(role_config.writable_tmpfs_mb)
    del tmpfs[missing_mount]

    with pytest.raises((ValueError, RuntimeError), match="tmpfs"):
        replace(config, **{field_name: replace(role_config, writable_tmpfs_mb=tmpfs)})


def test_rootless_config_requires_private_trusted_root_and_positive_headroom(
    tmp_path,
) -> None:
    config = _valid_config(tmp_path)
    config.trusted_root.chmod(0o755)
    with pytest.raises((ValueError, RuntimeError), match="trusted_root.*owner-only"):
        replace(config)
    config.trusted_root.chmod(0o700)

    with pytest.raises((ValueError, RuntimeError), match="headroom"):
        replace(
            config,
            headroom=replace(config.headroom, min_free_disk_mb=0),
        )


def test_rootless_config_rejects_symlinked_root_or_token_parent(tmp_path) -> None:
    config = _valid_config(tmp_path / "config")
    root_alias = tmp_path / "public-alias"
    root_alias.symlink_to(config.public_root, target_is_directory=True)
    with pytest.raises((ValueError, RuntimeError), match="symlink|real directory"):
        replace(config, public_root=root_alias)

    secret_alias = tmp_path / "secret-alias"
    secret_alias.symlink_to(config.token_file.parent, target_is_directory=True)
    with pytest.raises((ValueError, RuntimeError), match="symlink|trusted"):
        replace(config, token_file=secret_alias / config.token_file.name)


def test_rootless_config_loader_rejects_secret_value_and_parses_paths(tmp_path) -> None:
    from qea.rootless_full_harness import load_rootless_full_harness_config

    config = _valid_config(tmp_path)
    payload = {
        "schema_version": 1,
        "docker_host": config.docker_host,
        "expected_uid": config.expected_uid,
        "public_root": str(config.public_root),
        "trusted_root": str(config.trusted_root),
        "token_file": str(config.token_file),
        "upstream_base_url": config.upstream_base_url,
        "allowed_path_prefix": config.allowed_path_prefix,
        "allowed_model": config.allowed_model,
        "evolver_resources": {
            "cpu_count": 1,
            "memory_mb": 512,
            "pids_limit": 64,
            "timeout_seconds": 600,
            "writable_tmpfs_mb": {"/qea": 128, "/tmp": 64},
        },
        "proxy_resources": {
            "cpu_count": 1,
            "memory_mb": 512,
            "pids_limit": 64,
            "timeout_seconds": 600,
            "writable_tmpfs_mb": {
                "/qea": 128,
                "/run/qea-secrets": 16,
                "/tmp": 64,
            },
        },
        "worker_limits": {
            "pids_limit": 256,
            "timeout_seconds": 5400,
            "writable_tmpfs_mb": dict(config.worker_limits.writable_tmpfs_mb),
        },
        "verifier_limits": {
            "pids_limit": 256,
            "timeout_seconds": 5400,
            "writable_tmpfs_mb": dict(config.verifier_limits.writable_tmpfs_mb),
        },
        "capacity": {
            "cpu_count": 16,
            "memory_mb": 32768,
            "pids_limit": 4096,
            "tmpfs_mb": 16384,
            "sandboxes": 16,
        },
        "headroom": {
            "max_load_1m": 24,
            "min_available_memory_mb": 4096,
            "min_free_disk_mb": 8192,
            "min_free_inodes": 1000,
        },
        "worker_concurrency": 8,
        "verifier_concurrency": 4,
    }
    path = tmp_path / "rootless.json"
    path.write_text(json.dumps(payload))

    loaded = load_rootless_full_harness_config(path)
    assert loaded == config
    assert loaded.required_provider is None

    for invalid_schema in (True, 1.0, 2.0):
        payload["schema_version"] = invalid_schema
        path.write_text(json.dumps(payload))
        with pytest.raises((ValueError, RuntimeError), match="schema_version"):
            load_rootless_full_harness_config(path)

    payload["schema_version"] = 2
    payload["required_provider"] = "deepseek"
    path.write_text(json.dumps(payload))
    official = load_rootless_full_harness_config(path)
    assert official.required_provider == "deepseek"

    payload["required_provider"] = None
    path.write_text(json.dumps(payload))
    with pytest.raises((ValueError, RuntimeError), match="provider"):
        load_rootless_full_harness_config(path)
    payload["required_provider"] = "deepseek"

    payload["schema_version"] = 3
    payload["scheduler_epoch"] = "repetitions-02-through-05"
    path.write_text(json.dumps(payload))
    epoch_two = load_rootless_full_harness_config(path)
    assert epoch_two.required_provider == "deepseek"
    assert epoch_two.scheduler_epoch == "repetitions-02-through-05"

    payload["scheduler_epoch"] = ""
    path.write_text(json.dumps(payload))
    with pytest.raises((ValueError, RuntimeError), match="scheduler_epoch"):
        load_rootless_full_harness_config(path)
    payload["scheduler_epoch"] = "repetitions-02-through-05"

    payload["model_token"] = "forbidden-inline-secret"
    path.write_text(json.dumps(payload))
    with pytest.raises((ValueError, RuntimeError), match="unknown|secret|token"):
        load_rootless_full_harness_config(path)

    config_alias = tmp_path / "config-alias"
    config_alias.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises((ValueError, RuntimeError), match="symlink|trusted"):
        load_rootless_full_harness_config(config_alias / path.name)


def test_factory_builds_one_shared_runtime_and_applies_explicit_role_limits(
    tmp_path, monkeypatch
) -> None:
    from qea.rootless_full_harness import build_rootless_full_harness_runtime
    selected = _catalog()
    config = _valid_config(tmp_path / "config")
    _patch_catalog(monkeypatch, selected, config=config)
    results = tmp_path / "results"

    runtime = build_rootless_full_harness_runtime(
        config=config,
        image_set_manifest=tmp_path / "image-set.json",
        benchmark_commit=selected.benchmark_commit,
        tasks=(_task(),),
        run_id="rootless-task8",
        results_root=results,
    )
    try:
        assert runtime.backend.backend_name == "rootless-docker"
        assert runtime.evaluator.worker_concurrency == 8
        assert runtime.evaluator.verifier_concurrency == 4
        assert runtime.evaluator.executor.backend is runtime.backend
        assert runtime.evaluator.verifier.backend is runtime.backend
        assert runtime.proposer.backend is runtime.backend
        assert runtime.evaluator.executor.resource_pool is runtime.proposer.resource_pool
        assert runtime.evaluator.verifier.resource_pool is runtime.proposer.resource_pool
        assert runtime.evaluator.executor.proxy_manager is runtime.proposer.proxy_manager
        routed = runtime.evaluator.executor.catalog.tasks["task-a"]
        assert routed.worker_resources.pids_limit == config.worker_limits.pids_limit
        assert routed.worker_resources.timeout_seconds == config.worker_limits.timeout_seconds
        assert dict(routed.worker_resources.writable_tmpfs_mb) == dict(
            config.worker_limits.writable_tmpfs_mb
        )
        assert routed.verifier_resources.pids_limit == config.verifier_limits.pids_limit
        assert len(runtime.image_identity_digest) == 64
        assert len(runtime.scheduler_identity_digest) == 64
        assert len(runtime.runtime_identity_digest) == 64
        assert (results / "rootless-task8" / ".coordinator.lock").is_file()
    finally:
        runtime.close()


@pytest.mark.parametrize(
    "relative_path",
    (
        "public/tasks/task-a/environment/data/input.csv",
        "trusted/tasks/task-a/tests/test.sh",
        "trusted/tasks/task-a/tests/reference_data/expected.json",
    ),
)
def test_factory_rejects_manifested_material_byte_mutation_before_backend(
    tmp_path, monkeypatch, relative_path
) -> None:
    from qea.rootless_full_harness import (
        RootlessFullHarnessError,
        build_rootless_full_harness_runtime,
    )

    selected = _catalog()
    config = _valid_config(tmp_path / "config")
    _patch_catalog(monkeypatch, selected, config=config)
    mutated = config.public_root.parent / relative_path
    mutated.write_bytes(mutated.read_bytes() + b"tampered\n")

    with pytest.raises(RootlessFullHarnessError, match="material|manifest|hash"):
        build_rootless_full_harness_runtime(
            config=config,
            image_set_manifest=tmp_path / "image-set.json",
            benchmark_commit=selected.benchmark_commit,
            tasks=(_task(),),
            run_id="material-mutation",
            results_root=tmp_path / "results",
        )

    assert not (tmp_path / "results/material-mutation/.coordinator.lock").exists()


def test_factory_api_has_no_unbound_health_probe_injection() -> None:
    import inspect

    from qea.rootless_full_harness import build_rootless_full_harness_runtime

    assert "health_probe" not in inspect.signature(
        build_rootless_full_harness_runtime
    ).parameters


def test_linux_available_memory_uses_memavailable_not_free_pages(tmp_path) -> None:
    from qea.rootless_full_harness import _linux_available_memory_mb

    meminfo = tmp_path / "meminfo"
    meminfo.write_text(
        "MemTotal:       131842520 kB\n"
        "MemFree:          5035400 kB\n"
        "MemAvailable:   105816440 kB\n"
        "Cached:         102354352 kB\n"
    )

    assert _linux_available_memory_mb(meminfo) == 105816440 // 1024


@pytest.mark.parametrize(
    "payload",
    (
        "MemTotal: 131842520 kB\nMemFree: 5035400 kB\n",
        "MemAvailable: unavailable kB\n",
        "MemAvailable: 105816440 bytes\n",
        "MemAvailable: 1 kB\nMemAvailable: 2 kB\n",
    ),
)
def test_linux_available_memory_fails_closed_on_invalid_meminfo(
    tmp_path, payload
) -> None:
    from qea.rootless_full_harness import (
        RootlessFullHarnessError,
        _linux_available_memory_mb,
    )

    meminfo = tmp_path / "meminfo"
    meminfo.write_text(payload)

    with pytest.raises(RootlessFullHarnessError, match="MemAvailable"):
        _linux_available_memory_mb(meminfo)


def test_factory_binds_self_consistent_trusted_reference_manifest_drift(
    tmp_path, monkeypatch
) -> None:
    from qea.rootless_full_harness import build_rootless_full_harness_runtime

    selected = _catalog()
    config = _valid_config(tmp_path / "config")
    _patch_catalog(monkeypatch, selected, config=config)

    baseline = build_rootless_full_harness_runtime(
        config=config,
        image_set_manifest=tmp_path / "image-set.json",
        benchmark_commit=selected.benchmark_commit,
        tasks=(_task(),),
        run_id="material-baseline",
        results_root=tmp_path / "results",
    )
    baseline.close()

    relative = "tasks/task-a/tests/reference_data/expected.json"
    reference = config.trusted_root / relative
    reference.write_text('{"expected": 18}\n')
    _refresh_manifest_record(config.trusted_root, relative)
    changed = build_rootless_full_harness_runtime(
        config=config,
        image_set_manifest=tmp_path / "image-set.json",
        benchmark_commit=selected.benchmark_commit,
        tasks=(_task(),),
        run_id="material-changed",
        results_root=tmp_path / "results",
    )
    changed.close()

    assert changed.runtime_identity_digest != baseline.runtime_identity_digest


@pytest.mark.parametrize(
    ("relative_path", "message"),
    [
        ("tasks/task-a/environment/data/input.csv", "public material"),
        ("tasks/task-a/instruction.md", "public material"),
    ],
)
def test_factory_rejects_self_consistent_public_material_drift_from_images(
    tmp_path, monkeypatch, relative_path, message
) -> None:
    from qea.rootless_full_harness import (
        RootlessFullHarnessError,
        build_rootless_full_harness_runtime,
    )

    selected = _catalog()
    config = _valid_config(tmp_path / "config")
    _patch_catalog(monkeypatch, selected, config=config)
    path = config.public_root / relative_path
    path.write_bytes(path.read_bytes() + b"changed\n")
    _refresh_manifest_record(config.public_root, relative_path)

    with pytest.raises(RootlessFullHarnessError, match=message):
        build_rootless_full_harness_runtime(
            config=config,
            image_set_manifest=tmp_path / "image-set.json",
            benchmark_commit=selected.benchmark_commit,
            tasks=(_task(),),
            run_id="public-drift",
            results_root=tmp_path / "results",
        )


def test_factory_rejects_self_consistent_test_script_drift_from_verifier_image(
    tmp_path, monkeypatch
) -> None:
    from qea.rootless_full_harness import (
        RootlessFullHarnessError,
        build_rootless_full_harness_runtime,
    )

    selected = _catalog()
    config = _valid_config(tmp_path / "config")
    _patch_catalog(monkeypatch, selected, config=config)
    relative = "tasks/task-a/tests/test.sh"
    script = config.trusted_root / relative
    script.write_bytes(script.read_bytes() + b"# changed\n")
    _refresh_manifest_record(config.trusted_root, relative)

    with pytest.raises(RootlessFullHarnessError, match="verifier script"):
        build_rootless_full_harness_runtime(
            config=config,
            image_set_manifest=tmp_path / "image-set.json",
            benchmark_commit=selected.benchmark_commit,
            tasks=(_task(),),
            run_id="test-script-drift",
            results_root=tmp_path / "results",
        )


def test_factory_rejects_inconsistent_image_daemons_before_lock(
    tmp_path, monkeypatch
) -> None:
    from qea.rootless_full_harness import (
        RootlessFullHarnessError,
        build_rootless_full_harness_runtime,
    )

    selected = _catalog()
    config = _valid_config(tmp_path / "config")
    image_set = _selected_image_set(selected, config)
    image_set.proxy["docker_identity"] = {
        "version": "29.4.2",
        "security_options": ["name=rootless"],
    }
    _patch_catalog(monkeypatch, selected, config=config, image_set=image_set)

    with pytest.raises(RootlessFullHarnessError, match="inconsistent Docker daemon"):
        build_rootless_full_harness_runtime(
            config=config,
            image_set_manifest=tmp_path / "image-set.json",
            benchmark_commit=selected.benchmark_commit,
            tasks=(_task(),),
            run_id="daemon-drift",
            results_root=tmp_path / "results",
        )
    assert not (tmp_path / "results/daemon-drift/.coordinator.lock").exists()


def test_factory_preflight_failure_releases_coordinator_lock(
    tmp_path, monkeypatch
) -> None:
    from qea.backends.rootless_docker import RootlessDockerBackend
    from qea.rootless_full_harness import build_rootless_full_harness_runtime

    selected = _catalog()
    config = _valid_config(tmp_path / "config")
    _patch_catalog(monkeypatch, selected, config=config)
    successful_preflight = RootlessDockerBackend.preflight
    monkeypatch.setattr(
        RootlessDockerBackend,
        "preflight",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic daemon preflight failure")
        ),
    )
    kwargs = dict(
        config=config,
        image_set_manifest=tmp_path / "image-set.json",
        benchmark_commit=selected.benchmark_commit,
        tasks=(_task(),),
        run_id="preflight-lock",
        results_root=tmp_path / "results",
    )
    with pytest.raises(
        RuntimeError, match="rootless Docker daemon and image preflight failed"
    ):
        build_rootless_full_harness_runtime(**kwargs)

    monkeypatch.setattr(RootlessDockerBackend, "preflight", successful_preflight)
    replacement = build_rootless_full_harness_runtime(**kwargs)
    replacement.close()


def test_factory_lock_is_exclusive_for_the_complete_runtime_lifetime(
    tmp_path, monkeypatch
) -> None:
    from qea.rootless_full_harness import (
        RootlessFullHarnessError,
        build_rootless_full_harness_runtime,
    )
    selected = _catalog()
    config = _valid_config(tmp_path / "config")
    _patch_catalog(monkeypatch, selected, config=config)
    kwargs = dict(
        config=config,
        image_set_manifest=tmp_path / "image-set.json",
        benchmark_commit=selected.benchmark_commit,
        tasks=(_task(),),
        run_id="exclusive-run",
        results_root=tmp_path / "results",
    )
    first = build_rootless_full_harness_runtime(**kwargs)
    try:
        with pytest.raises(RootlessFullHarnessError, match="coordinator lock"):
            build_rootless_full_harness_runtime(**kwargs)
    finally:
        first.close()
    replacement = build_rootless_full_harness_runtime(**kwargs)
    replacement.close()


def test_factory_binds_runtime_scheduler_and_catalog_identity(tmp_path, monkeypatch) -> None:
    import qea.rootless_full_harness as rootless_full_harness

    from qea.rootless_full_harness import build_rootless_full_harness_runtime
    selected = _catalog()
    config = _valid_config(tmp_path / "config")
    _patch_catalog(monkeypatch, selected, config=config)

    def build(current_config, *, suffix):
        runtime = build_rootless_full_harness_runtime(
            config=current_config,
            image_set_manifest=tmp_path / "image-set.json",
            benchmark_commit=selected.benchmark_commit,
            tasks=(_task(),),
            run_id="identity-run",
            results_root=tmp_path / f"results-{suffix}",
        )
        runtime.close()
        return runtime

    baseline = build(config, suffix="base")
    model = build(replace(config, allowed_model="provider/other"), suffix="model")
    provider = build(
        replace(config, required_provider="deepseek"),
        suffix="provider",
    )
    limits = build(
        replace(
            config,
            worker_limits=replace(config.worker_limits, pids_limit=257),
        ),
        suffix="limits",
    )
    scheduling = build(
        replace(config, worker_concurrency=7), suffix="scheduling"
    )
    labeled_epoch = build(
        replace(config, scheduler_epoch="repetitions-02-through-05"),
        suffix="epoch",
    )

    assert model.runtime_identity_digest != baseline.runtime_identity_digest
    assert model.scheduler_identity_digest == baseline.scheduler_identity_digest
    assert provider.runtime_identity_digest != baseline.runtime_identity_digest
    assert provider.scheduler_identity_digest == baseline.scheduler_identity_digest
    assert limits.runtime_identity_digest != baseline.runtime_identity_digest
    assert scheduling.runtime_identity_digest != baseline.runtime_identity_digest
    assert scheduling.scheduler_identity_digest != baseline.scheduler_identity_digest
    assert labeled_epoch.runtime_identity_digest != baseline.runtime_identity_digest
    assert labeled_epoch.scheduler_identity_digest != baseline.scheduler_identity_digest
    assert labeled_epoch.image_identity_digest == baseline.image_identity_digest

    changed_catalog = _catalog(identity="d" * 64)
    _patch_catalog(monkeypatch, changed_catalog, config=config)
    catalog_drift = build(config, suffix="catalog")
    assert catalog_drift.runtime_identity_digest != baseline.runtime_identity_digest

    monkeypatch.setattr(
        rootless_full_harness,
        "_runtime_adapter_identity",
        lambda: {
            "schema_version": 1,
            "identity_sha256": "e" * 64,
            "files": [],
        },
    )
    adapter_drift = build(config, suffix="adapter")
    assert adapter_drift.runtime_identity_digest != baseline.runtime_identity_digest


def test_runtime_adapter_identity_hashes_exact_uploaded_worker_bytes() -> None:
    import hashlib

    from qea.executors import sandbox_evolver, sandbox_nexau
    from qea.rootless_full_harness import _runtime_adapter_identity

    identity = _runtime_adapter_identity()
    files = {record["role"]: record for record in identity["files"]}

    assert set(files) == {
        "evolver_runner",
        "worker_runner",
        "worker_runtime_bridge",
    }
    assert files["worker_runner"]["sha256"] == hashlib.sha256(
        sandbox_nexau._REMOTE_RUNNER.read_bytes()
    ).hexdigest()
    assert files["worker_runtime_bridge"]["sha256"] == hashlib.sha256(
        sandbox_nexau._RUNTIME_BRIDGE.read_bytes()
    ).hexdigest()
    assert files["evolver_runner"]["sha256"] == hashlib.sha256(
        sandbox_evolver._REMOTE_RUNNER.read_bytes()
    ).hexdigest()


def test_factory_fails_before_construction_on_uid_task_or_capacity_drift(
    tmp_path, monkeypatch
) -> None:
    from qea.rootless_full_harness import (
        RootlessFullHarnessError,
        build_rootless_full_harness_runtime,
    )
    selected = _catalog()
    config = _valid_config(tmp_path / "config")
    _patch_catalog(monkeypatch, selected, config=config)
    common = dict(
        config=config,
        image_set_manifest=tmp_path / "image-set.json",
        benchmark_commit=selected.benchmark_commit,
        run_id="invalid-run",
        results_root=tmp_path / "results",
    )
    monkeypatch.setattr(os, "getuid", lambda: config.expected_uid + 1)
    with pytest.raises(RootlessFullHarnessError, match="UID"):
        build_rootless_full_harness_runtime(tasks=(_task(),), **common)
    monkeypatch.setattr(os, "getuid", lambda: config.expected_uid)

    with pytest.raises(RootlessFullHarnessError, match="resource"):
        build_rootless_full_harness_runtime(tasks=(_task(cpus=2),), **common)

    too_small = replace(
        config,
        capacity=replace(config.capacity, cpu_count=1),
    )
    with pytest.raises(RootlessFullHarnessError, match="capacity"):
        build_rootless_full_harness_runtime(
            tasks=(_task(),), **{**common, "config": too_small}
        )


def test_factory_rejects_neutral_image_resource_drift(tmp_path, monkeypatch) -> None:
    from qea.rootless_full_harness import (
        RootlessFullHarnessError,
        build_rootless_full_harness_runtime,
    )

    selected = _catalog()
    config = _valid_config(tmp_path / "config")
    _patch_catalog(
        monkeypatch,
        selected,
        config=config,
        image_set=_selected_image_set(selected, config, proxy_cpu=9),
    )
    with pytest.raises(RootlessFullHarnessError, match="proxy image resource"):
        build_rootless_full_harness_runtime(
            config=config,
            image_set_manifest=tmp_path / "image-set.json",
            benchmark_commit=selected.benchmark_commit,
            tasks=(_task(),),
            run_id="neutral-resource-drift",
            results_root=tmp_path / "results",
        )
