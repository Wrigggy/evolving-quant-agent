"""Deterministic rootless-Docker build plans and immutable image manifests."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Literal, Mapping

from .backends.rootless_docker import (
    CommandRunner,
    RootlessDockerBackend,
    SubprocessCommandRunner,
)
from .benchmarks.qfbench import git_blob_oid
from .qfbench_images import (
    NEXAU_WORKER_DEPENDENCY,
    _dependency_install_commands,
    verifier_dependency_lock_command,
    verifier_uvx_warm_command,
)


RootlessImageRole = Literal["base", "proxy", "evolver", "worker", "verifier"]

_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IMAGE_DIGEST = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}\Z"
)
_TASK_ID = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
_METADATA_NAMES = frozenset(
    {
        "MANIFEST.json",
        ".qfbench-revision",
        ".qfbench-sparse-tasks.json",
        ".qfbench-cache",
    }
)
_SUPERVISOR_PATH = "/usr/local/bin/qea-sandbox-supervisor"
_SUPERVISOR = b"""#!/usr/bin/env python3
import signal
import sys


def stop(_signum, _frame):
    raise SystemExit(0)


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
while True:
    signal.pause()
"""
_MODEL_PROXY_ENTRYPOINT_PATH = "/usr/local/bin/qea-model-proxy-entrypoint"
_MODEL_PROXY_ENTRYPOINT = b"""#!/usr/bin/env python3
import json
import os
import time
from pathlib import Path


config_path = Path('/run/qea-secrets/proxy-config.json')
token_path = Path('/run/qea-secrets/model-token')
while not (config_path.is_file() and token_path.is_file()):
    time.sleep(0.05)
config = json.loads(config_path.read_text())
required = {
    'listen_host', 'listen_port', 'upstream_base_url', 'allowed_path_prefix',
    'allowed_model', 'audit_file', 'denied_request_identities_sha256',
    'max_request_bytes', 'max_response_bytes', 'connect_timeout_seconds',
    'read_timeout_seconds',
}
if set(config) != required:
    raise SystemExit(78)
argv = [
    '/usr/local/bin/python3',
    '/usr/local/lib/qea/run_qea_model_proxy.py',
    '--listen-host', str(config['listen_host']),
    '--listen-port', str(config['listen_port']),
    '--upstream-base-url', str(config['upstream_base_url']),
    '--allowed-path-prefix', str(config['allowed_path_prefix']),
    '--allowed-model', str(config['allowed_model']),
    '--token-file', str(token_path),
    '--audit-file', str(config['audit_file']),
    '--max-request-bytes', str(config['max_request_bytes']),
    '--max-response-bytes', str(config['max_response_bytes']),
    '--connect-timeout-seconds', str(config['connect_timeout_seconds']),
    '--read-timeout-seconds', str(config['read_timeout_seconds']),
]
for identity in config['denied_request_identities_sha256']:
    argv.extend(['--denied-request-identity-sha256', str(identity)])
environment = os.environ.copy()
environment['PYTHONPATH'] = '/usr/local/lib'
os.execve(argv[0], argv, environment)
"""


class RootlessImageError(RuntimeError):
    """A build source, context, image identity, or Docker result is unsafe."""


@dataclass(frozen=True)
class RootlessContextFile:
    path: str
    payload: bytes
    mode: int
    sha256: str
    size_bytes: int

    @classmethod
    def from_payload(
        cls,
        path: str,
        payload: bytes,
        *,
        mode: int = 0o644,
    ) -> "RootlessContextFile":
        return cls(
            path=path,
            payload=payload,
            mode=mode,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
        )

    def manifest_record(self) -> dict[str, object]:
        return {
            "path": self.path,
            "mode": oct(self.mode),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class RootlessImageBuildPlan:
    role: RootlessImageRole
    task_id: str | None
    benchmark_commit: str
    base_image_ref: str
    source_manifest_sha256: str
    verifier_test_script_sha256: str | None
    context_files: tuple[RootlessContextFile, ...]
    dockerfile_bytes: bytes
    cpu_count: int
    memory_mb: int
    build_timeout_seconds: int
    build_network: str
    identity_sha256: str

    def manifest_payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "role": self.role,
            "task_id": self.task_id,
            "benchmark_commit": self.benchmark_commit,
            "base_image_ref": self.base_image_ref,
            "source_manifest_sha256": self.source_manifest_sha256,
            "verifier_test_script_sha256": self.verifier_test_script_sha256,
            "context_files": [
                item.manifest_record() for item in self.context_files
            ],
            "dockerfile_sha256": hashlib.sha256(
                self.dockerfile_bytes
            ).hexdigest(),
            "cpu_count": self.cpu_count,
            "memory_mb": self.memory_mb,
            "build_timeout_seconds": self.build_timeout_seconds,
            "build_network": self.build_network,
            "identity_kind": "plan",
            "identity_sha256": self.identity_sha256,
            "plan_identity_sha256": self.identity_sha256,
        }


@dataclass(frozen=True)
class RootlessImageBuildResult:
    output_dir: Path
    manifest_path: Path
    image_id: str
    plan_identity_sha256: str
    result_identity_sha256: str


@dataclass(frozen=True)
class _VerifiedRoleRoot:
    root: Path
    role: str
    commit: str
    records: Mapping[str, dict[str, object]]
    manifest_sha256: str


def _safe_relative_path(value: object) -> str:
    if not isinstance(value, str):
        raise RootlessImageError(f"unsafe source path: {value!r}")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
        or "solution" in path.parts
    ):
        raise RootlessImageError(f"unsafe source path: {value!r}")
    return value


def _verify_role_root(root: str | Path, expected_role: str) -> _VerifiedRoleRoot:
    resolved = Path(root).expanduser().resolve()
    manifest_path = resolved / "MANIFEST.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        payload = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise RootlessImageError(f"cannot load role manifest {manifest_path}: {exc}") from exc
    if payload.get("schema_version") != 1 or payload.get("role") != expected_role:
        raise RootlessImageError(
            f"role manifest at {manifest_path} is not {expected_role!r}"
        )
    commit = payload.get("commit")
    if not isinstance(commit, str) or _COMMIT.fullmatch(commit) is None:
        raise RootlessImageError("role manifest has invalid benchmark commit")
    raw_records = payload.get("files")
    if not isinstance(raw_records, list) or not raw_records:
        raise RootlessImageError("role manifest has no file records")
    records: dict[str, dict[str, object]] = {}
    for record in raw_records:
        if not isinstance(record, dict):
            raise RootlessImageError("role manifest file record is not an object")
        relative = _safe_relative_path(record.get("path"))
        if relative in records:
            raise RootlessImageError(f"duplicate role manifest path: {relative}")
        path = resolved / relative
        if path.is_symlink() or not path.is_file():
            raise RootlessImageError(f"manifest source is not a regular file: {relative}")
        file_bytes = path.read_bytes()
        if (
            record.get("sha256") != hashlib.sha256(file_bytes).hexdigest()
            or record.get("git_blob_oid") != git_blob_oid(file_bytes)
            or record.get("size_bytes") != len(file_bytes)
        ):
            raise RootlessImageError(f"manifest hash mismatch for {relative}")
        records[relative] = record
    discovered = tuple(resolved.rglob("*"))
    for path in discovered:
        relative = path.relative_to(resolved).as_posix()
        if relative in _METADATA_NAMES:
            continue
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise RootlessImageError(f"non-regular source entry: {relative}")
    actual_files = {
        path.relative_to(resolved).as_posix()
        for path in discovered
        if path.is_file() and path.relative_to(resolved).as_posix() not in _METADATA_NAMES
    }
    if actual_files != set(records):
        extras = sorted(actual_files - set(records))
        missing = sorted(set(records) - actual_files)
        raise RootlessImageError(
            f"unmanifested source file membership; extras={extras}, missing={missing}"
        )
    return _VerifiedRoleRoot(
        root=resolved,
        role=expected_role,
        commit=commit,
        records=records,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    )


def _require_image_ref(value: str) -> str:
    if not isinstance(value, str) or not (
        _IMAGE_ID.fullmatch(value) or _IMAGE_DIGEST.fullmatch(value)
    ):
        raise RootlessImageError(f"immutable base image is required: {value!r}")
    return value


def _dockerfile_base_ref(value: str) -> str:
    if _IMAGE_ID.fullmatch(value):
        return f"qea-local-base:{value.removeprefix('sha256:')}"
    return value


def _require_resources(
    cpu_count: int,
    memory_mb: int,
    build_timeout_seconds: int,
) -> None:
    if any(
        type(value) is not int or value <= 0
        for value in (cpu_count, memory_mb, build_timeout_seconds)
    ):
        raise RootlessImageError("image resource values must be positive integers")


def _rewrite_single_from(dockerfile: str, image_ref: str) -> str:
    output: list[str] = []
    found = 0
    for line in dockerfile.splitlines():
        if re.match(r"^\s*FROM\s+", line, flags=re.IGNORECASE):
            found += 1
            output.append(f"FROM {image_ref}")
        else:
            output.append(line)
    if found != 1:
        raise RootlessImageError("QFBench Dockerfile must contain exactly one FROM")
    return "\n".join(output) + "\n"


def _task_dockerfile(
    upstream: str,
    *,
    base_image_ref: str,
    role: Literal["worker", "verifier"],
    verifier_test_script: str | None,
) -> bytes:
    generated = _rewrite_single_from(upstream, base_image_ref).rstrip() + "\n\n"
    generated += f"# QEA generated rootless {role} layer.\nUSER root\n"
    dependencies = (
        (NEXAU_WORKER_DEPENDENCY,)
        if role == "worker"
        else ("uv==0.9.5",)
    )
    for command in _dependency_install_commands(dependencies):
        if role == "worker" and NEXAU_WORKER_DEPENDENCY in command:
            generated += (
                "RUN apt-get update && apt-get install -y "
                "--no-install-recommends git "
                "&& rm -rf /var/lib/apt/lists/*\n"
            )
        generated += f"RUN {command}\n"
    if role == "verifier":
        script = verifier_test_script or ""
        warm = verifier_uvx_warm_command(script)
        lock = verifier_dependency_lock_command(script)
        generated += "RUN mkdir -p /opt/qea/uv-cache /opt/qea/uv-tools /opt/qea/uv-bin\n"
        if warm is not None:
            generated += (
                "RUN UV_CACHE_DIR=/opt/qea/uv-cache "
                "UV_TOOL_DIR=/opt/qea/uv-tools "
                f"UV_TOOL_BIN_DIR=/opt/qea/uv-bin {warm}\n"
            )
        generated += (
            "RUN UV_CACHE_DIR=/opt/qea/uv-cache "
            "UV_TOOL_DIR=/opt/qea/uv-tools "
            f"UV_TOOL_BIN_DIR=/opt/qea/uv-bin {lock}\n"
        )
        generated += "RUN cp -a /opt/qea/uv-cache /opt/qea/uv-cache-seed\n"
    generated += f'LABEL org.qea.qfbench.role="{role}"\n'
    return generated.encode("utf-8")


def _task_neutral_dockerfile(
    *,
    base_image_ref: str,
    role: Literal["proxy", "evolver"],
) -> bytes:
    generated = (
        f"FROM {_dockerfile_base_ref(base_image_ref)}\n\n"
        f"# QEA generated rootless {role} layer.\n"
        "USER root\n"
    )
    if role == "evolver":
        for command in _dependency_install_commands((NEXAU_WORKER_DEPENDENCY,)):
            if NEXAU_WORKER_DEPENDENCY in command:
                generated += (
                    "RUN apt-get update && apt-get install -y "
                    "--no-install-recommends git "
                    "&& rm -rf /var/lib/apt/lists/*\n"
                )
            generated += f"RUN {command}\n"
        generated += "RUN mkdir -p /qea\n"
    else:
        generated += (
            "RUN mkdir -p /usr/local/lib/qea\n"
            "COPY qea/__init__.py /usr/local/lib/qea/__init__.py\n"
            "COPY qea/model_proxy.py /usr/local/lib/qea/model_proxy.py\n"
            "COPY qea/sandbox_backend.py /usr/local/lib/qea/sandbox_backend.py\n"
            "COPY qea/run_qea_model_proxy.py "
            "/usr/local/lib/qea/run_qea_model_proxy.py\n"
            "COPY qea/model-proxy-entrypoint.py "
            f"{_MODEL_PROXY_ENTRYPOINT_PATH}\n"
            f"RUN chmod 0555 {_MODEL_PROXY_ENTRYPOINT_PATH} "
            "/usr/local/lib/qea/run_qea_model_proxy.py\n"
        )
    generated += f'LABEL org.qea.qfbench.role="{role}"\n'
    return generated.encode("utf-8")


def _context_file(path: str, payload: bytes, mode: int = 0o644) -> RootlessContextFile:
    _safe_relative_path(path)
    return RootlessContextFile.from_payload(path, payload, mode=mode)


def _plan_identity(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def rootless_image_result_identity_sha256(
    *,
    plan_identity_sha256: str,
    image_id: str,
    dependency_lock_sha256: str,
    docker_version: str,
    docker_security_options: list[str] | tuple[str, ...],
) -> str:
    """Bind immutable build inputs to measured image, lock, and daemon identity."""

    if re.fullmatch(r"[0-9a-f]{64}", plan_identity_sha256) is None:
        raise RootlessImageError("result identity requires a valid plan identity")
    if _IMAGE_ID.fullmatch(image_id) is None:
        raise RootlessImageError("result identity requires an immutable image ID")
    if re.fullmatch(r"[0-9a-f]{64}", dependency_lock_sha256) is None:
        raise RootlessImageError("result identity requires a dependency-lock digest")
    if not isinstance(docker_version, str) or not docker_version:
        raise RootlessImageError("result identity requires a Docker version")
    if (
        not isinstance(docker_security_options, (list, tuple))
        or not all(isinstance(value, str) for value in docker_security_options)
        or "name=rootless" not in docker_security_options
    ):
        raise RootlessImageError("result identity requires rootless Docker identity")
    payload = {
        "plan_identity_sha256": plan_identity_sha256,
        "image_id": image_id,
        "dependency_lock_sha256": dependency_lock_sha256,
        "docker_version": docker_version,
        "docker_security_options": sorted(docker_security_options),
    }
    return _plan_identity(payload)


def prepare_rootless_image_plan(
    *,
    role: RootlessImageRole,
    public_root: str | Path,
    base_image_ref: str,
    cpu_count: int,
    memory_mb: int,
    build_timeout_seconds: int,
    task_id: str | None = None,
    trusted_root: str | Path | None = None,
) -> RootlessImageBuildPlan:
    """Build an in-memory, content-addressed image plan without filesystem writes."""

    if role not in {"base", "proxy", "evolver", "worker", "verifier"}:
        raise RootlessImageError(f"unsupported rootless image role: {role!r}")
    base_ref = _require_image_ref(base_image_ref)
    _require_resources(cpu_count, memory_mb, build_timeout_seconds)
    public = _verify_role_root(public_root, "public")
    if role in {"base", "proxy", "evolver"}:
        if task_id is not None or trusted_root is not None:
            raise RootlessImageError(
                f"{role} image plan cannot name a task or trusted root"
            )
        if role == "base":
            source_dockerfile = public.root / "docker/sandbox.Dockerfile"
            requirements = public.root / "docker/requirements-sandbox.txt"
            if not source_dockerfile.is_file() or not requirements.is_file():
                raise RootlessImageError("public root is missing QFBench base inputs")
            dockerfile = _rewrite_single_from(
                source_dockerfile.read_text(), base_ref
            ).encode("utf-8")
            dockerfile += (
                b"COPY qea/sandbox-supervisor.py "
                + _SUPERVISOR_PATH.encode("utf-8")
                + b"\nRUN chmod 0555 "
                + _SUPERVISOR_PATH.encode("utf-8")
            )
            files = (
                _context_file("Dockerfile", dockerfile),
                _context_file(
                    "docker/requirements-sandbox.txt", requirements.read_bytes()
                ),
                _context_file("qea/sandbox-supervisor.py", _SUPERVISOR, 0o555),
            )
        else:
            dockerfile = _task_neutral_dockerfile(
                base_image_ref=base_ref,
                role=role,
            )
            if role == "evolver":
                files = (_context_file("Dockerfile", dockerfile),)
            else:
                package_root = Path(__file__).resolve().parent
                proxy_script = (
                    package_root.parent / "scripts" / "run_qea_model_proxy.py"
                )
                files = (
                    _context_file("Dockerfile", dockerfile),
                    _context_file(
                        "qea/__init__.py",
                        (package_root / "__init__.py").read_bytes(),
                    ),
                    _context_file(
                        "qea/model-proxy-entrypoint.py",
                        _MODEL_PROXY_ENTRYPOINT,
                        0o555,
                    ),
                    _context_file(
                        "qea/model_proxy.py",
                        (package_root / "model_proxy.py").read_bytes(),
                    ),
                    _context_file(
                        "qea/run_qea_model_proxy.py",
                        proxy_script.read_bytes(),
                        0o555,
                    ),
                    _context_file(
                        "qea/sandbox_backend.py",
                        (package_root / "sandbox_backend.py").read_bytes(),
                    ),
                )
        verifier_hash = None
        normalized_task_id = None
    else:
        if not isinstance(task_id, str) or _TASK_ID.fullmatch(task_id) is None:
            raise RootlessImageError("task image plan requires a valid task_id")
        environment_root = public.root / "tasks" / task_id / "environment"
        upstream = environment_root / "Dockerfile"
        if not upstream.is_file():
            raise RootlessImageError(
                f"public root has no environment Dockerfile for {task_id!r}"
            )
        verifier_script: str | None = None
        verifier_hash: str | None = None
        if role == "verifier":
            if trusted_root is None:
                raise RootlessImageError("verifier image plan requires trusted_root")
            trusted = _verify_role_root(trusted_root, "trusted-verifier")
            if trusted.commit != public.commit:
                raise RootlessImageError("public and trusted commits differ")
            test_script = trusted.root / "tasks" / task_id / "tests" / "test.sh"
            if not test_script.is_file():
                raise RootlessImageError(
                    f"trusted root has no verifier script for {task_id!r}"
                )
            test_bytes = test_script.read_bytes()
            verifier_script = test_bytes.decode("utf-8")
            verifier_hash = hashlib.sha256(test_bytes).hexdigest()
        elif trusted_root is not None:
            raise RootlessImageError("worker image plan cannot name a trusted root")
        dockerfile = _task_dockerfile(
            upstream.read_text(),
            base_image_ref=_dockerfile_base_ref(base_ref),
            role=role,
            verifier_test_script=verifier_script,
        )
        context: list[RootlessContextFile] = [
            _context_file("Dockerfile", dockerfile)
        ]
        for path in sorted(environment_root.rglob("*")):
            if path == upstream or not path.is_file():
                continue
            if path.is_symlink():
                raise RootlessImageError(f"symlink in task environment: {path}")
            relative = path.relative_to(environment_root).as_posix()
            context.append(_context_file(relative, path.read_bytes()))
        files = tuple(sorted(context, key=lambda item: item.path))
        normalized_task_id = task_id

    identity_payload = {
        "role": role,
        "task_id": normalized_task_id,
        "benchmark_commit": public.commit,
        "base_image_ref": base_ref,
        "source_manifest_sha256": public.manifest_sha256,
        "verifier_test_script_sha256": verifier_hash,
        "context_files": [item.manifest_record() for item in files],
        "cpu_count": cpu_count,
        "memory_mb": memory_mb,
        "build_timeout_seconds": build_timeout_seconds,
        "build_network": "default",
    }
    identity = _plan_identity(identity_payload)
    return RootlessImageBuildPlan(
        role=role,
        task_id=normalized_task_id,
        benchmark_commit=public.commit,
        base_image_ref=base_ref,
        source_manifest_sha256=public.manifest_sha256,
        verifier_test_script_sha256=verifier_hash,
        context_files=files,
        dockerfile_bytes=dockerfile,
        cpu_count=cpu_count,
        memory_mb=memory_mb,
        build_timeout_seconds=build_timeout_seconds,
        build_network="default",
        identity_sha256=identity,
    )


def _write_context(plan: RootlessImageBuildPlan, context_root: Path) -> None:
    context_root.mkdir(parents=True)
    for member in plan.context_files:
        path = context_root / member.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(member.payload)
        path.chmod(member.mode)
    actual = {
        path.relative_to(context_root).as_posix()
        for path in context_root.rglob("*")
        if path.is_file()
    }
    expected = {member.path for member in plan.context_files}
    if actual != expected or any(path.is_symlink() for path in context_root.rglob("*")):
        raise RootlessImageError("materialized image context membership differs from plan")


def _docker_checked(
    runner: CommandRunner,
    argv: tuple[str, ...],
    *,
    timeout_seconds: int,
    operation: str,
):
    result = runner.run(argv, timeout_seconds=timeout_seconds)
    if result.returncode != 0:
        error = result.stderr[:16_384].decode("utf-8", errors="replace")
        raise RootlessImageError(f"Docker {operation} failed: {error}")
    return result


def _require_docker_image_id(
    runner: CommandRunner,
    docker_prefix: tuple[str, ...],
    reference: str,
    expected_image_id: str,
    *,
    operation: str,
) -> None:
    inspected = _docker_checked(
        runner,
        (*docker_prefix, "image", "inspect", "--format", "{{.Id}}", reference),
        timeout_seconds=30,
        operation=operation,
    )
    observed = inspected.stdout.decode("utf-8", errors="replace").strip()
    if observed != expected_image_id:
        raise RootlessImageError(
            f"Docker {operation} identity mismatch: expected {expected_image_id}, "
            f"found {observed or '<empty>'}"
        )


def execute_rootless_image_build(
    plan: RootlessImageBuildPlan,
    *,
    output_root: str | Path,
    docker_host: str,
    expected_uid: int,
    runner: CommandRunner | None = None,
    at: datetime | None = None,
) -> RootlessImageBuildResult:
    """Build one plan and atomically publish its measured immutable identity."""

    command_runner = runner or SubprocessCommandRunner()
    try:
        RootlessDockerBackend(
            docker_host=docker_host,
            expected_uid=expected_uid,
            runner=command_runner,
        )
    except Exception as exc:
        raise RootlessImageError(
            f"rootless Docker socket validation failed: {exc}"
        ) from exc
    docker_prefix = ("docker", "--host", docker_host)
    root = Path(output_root).expanduser().resolve()
    staging = root / f"{plan.identity_sha256}.partial"
    if staging.exists() or staging.is_symlink():
        raise RootlessImageError(f"existing partial image identity directory: {staging}")
    local_base_tag: str | None = None
    if _IMAGE_ID.fullmatch(plan.base_image_ref):
        local_base_tag = _dockerfile_base_ref(plan.base_image_ref)
        if f"FROM {local_base_tag}\n".encode() not in plan.dockerfile_bytes:
            raise RootlessImageError("local base tag differs from planned Dockerfile")
        _require_docker_image_id(
            command_runner,
            docker_prefix,
            plan.base_image_ref,
            plan.base_image_ref,
            operation="local base image inspection",
        )
        _docker_checked(
            command_runner,
            (
                *docker_prefix,
                "image",
                "tag",
                plan.base_image_ref,
                local_base_tag,
            ),
            timeout_seconds=30,
            operation="local base image tagging",
        )
        _require_docker_image_id(
            command_runner,
            docker_prefix,
            local_base_tag,
            plan.base_image_ref,
            operation="local base tag inspection",
        )
    root.mkdir(parents=True, exist_ok=True)
    staging.mkdir()
    context = staging / "context"
    _write_context(plan, context)
    tag = f"qea-rootless-{plan.role}-{plan.identity_sha256[:16]}"
    build = _docker_checked(
        command_runner,
        (
            *docker_prefix,
            "build",
            "--pull=false",
            "--network",
            plan.build_network,
            "--file",
            str(context / "Dockerfile"),
            "--tag",
            tag,
            "--quiet",
            str(context),
        ),
        timeout_seconds=plan.build_timeout_seconds,
        operation="image build",
    )
    image_id = build.stdout.decode("utf-8", errors="replace").strip()
    if _IMAGE_ID.fullmatch(image_id) is None:
        raise RootlessImageError(f"Docker build returned no immutable image ID: {image_id!r}")
    inspected = _docker_checked(
        command_runner,
        (*docker_prefix, "image", "inspect", "--format", "{{json .}}", image_id),
        timeout_seconds=30,
        operation="image inspect",
    )
    try:
        image_payload = json.loads(inspected.stdout)
        if image_payload["Id"] != image_id:
            raise RootlessImageError("Docker image inspect identity mismatch")
        repo_digests = image_payload.get("RepoDigests") or []
        if not isinstance(repo_digests, list):
            raise RootlessImageError("Docker image inspect has invalid RepoDigests")
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RootlessImageError("malformed Docker image inspect output") from exc
    docker_version = _docker_checked(
        command_runner,
        (*docker_prefix, "version", "--format", "{{.Server.Version}}"),
        timeout_seconds=30,
        operation="version inspection",
    ).stdout.decode("utf-8", errors="replace").strip()
    security_raw = _docker_checked(
        command_runner,
        (*docker_prefix, "info", "--format", "{{json .SecurityOptions}}"),
        timeout_seconds=30,
        operation="security inspection",
    ).stdout
    try:
        security_options = json.loads(security_raw)
    except json.JSONDecodeError as exc:
        raise RootlessImageError("malformed Docker security options") from exc
    if not isinstance(security_options, list) or "name=rootless" not in security_options:
        raise RootlessImageError("Docker build daemon is not rootless")
    if plan.role in {"base", "proxy"}:
        lock_command = (
            *docker_prefix,
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "python3",
            image_id,
            "-m",
            "pip",
            "freeze",
        )
    else:
        lock_path = (
            "/opt/qea/nexau-requirements.lock"
            if plan.role in {"worker", "evolver"}
            else "/opt/qea/verifier-requirements.lock"
        )
        lock_command = (
            *docker_prefix,
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "cat",
            image_id,
            lock_path,
        )
    dependency_lock = _docker_checked(
        command_runner,
        lock_command,
        timeout_seconds=120,
        operation="dependency lock extraction",
    ).stdout
    dependency_lock_sha256 = hashlib.sha256(dependency_lock).hexdigest()
    lock_path = staging / "dependency-lock.txt"
    lock_path.write_bytes(dependency_lock)
    lock_path.chmod(0o644)
    if local_base_tag is not None:
        _require_docker_image_id(
            command_runner,
            docker_prefix,
            local_base_tag,
            plan.base_image_ref,
            operation="post-build local base tag inspection",
        )
    timestamp = at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise RootlessImageError("build timestamp must be timezone-aware")
    result_identity = rootless_image_result_identity_sha256(
        plan_identity_sha256=plan.identity_sha256,
        image_id=image_id,
        dependency_lock_sha256=dependency_lock_sha256,
        docker_version=docker_version,
        docker_security_options=security_options,
    )
    final = root / result_identity
    if final.exists() or final.is_symlink():
        raise RootlessImageError(f"existing image result identity directory: {final}")
    manifest = {
        **plan.manifest_payload(),
        "identity_kind": "measured-result",
        "identity_sha256": result_identity,
        "result_identity_sha256": result_identity,
        "image_id": image_id,
        "repo_digests": repo_digests,
        "build_tag": tag,
        "local_base_tag": local_base_tag,
        "local_base_image_id": plan.base_image_ref if local_base_tag else None,
        "docker_version": docker_version,
        "docker_security_options": security_options,
        "dependency_lock_sha256": dependency_lock_sha256,
        "built_at": timestamp.astimezone(timezone.utc).isoformat(),
    }
    manifest_path = staging / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    os.replace(staging, final)
    return RootlessImageBuildResult(
        output_dir=final,
        manifest_path=final / "MANIFEST.json",
        image_id=image_id,
        plan_identity_sha256=plan.identity_sha256,
        result_identity_sha256=result_identity,
    )
