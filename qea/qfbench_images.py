"""Generate read-only QFBench Dockerfile overlays for digest-pinned E2B templates."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


_DIGEST_IMAGE_RE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_FROM_RE = re.compile(r"^(?P<prefix>\s*FROM\s+)(?P<image>\S+)(?P<suffix>.*)$", re.IGNORECASE)
_QFBENCH_PARENT_RE = re.compile(
    r"^(?:finance-bench-sandbox|quantitative-finance-bench-sandbox):"
    r"[A-Za-z0-9_.-]+(?:@sha256:[0-9a-f]{64})?$"
)
_EXACT_PACKAGE_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9][A-Za-z0-9_.+-]*$"
)
_PINNED_HTTPS_VCS_RE = re.compile(
    r"^git\+https://[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.git@[0-9a-f]{40}$"
)

NEXAU_COMMIT = "35ee1861546db3cb280a6e17e38a74060d7c96c3"
NEXAU_WORKER_DEPENDENCY = (
    "git+https://github.com/nex-agi/NexAU.git@" + NEXAU_COMMIT
)
NEXAU_PYTHON_VERSION = "3.12"
NEXAU_RUNTIME_ROOT = "/opt/qea/nexau-venv"
NEXAU_RUNTIME_PYTHON = f"{NEXAU_RUNTIME_ROOT}/bin/python"
NEXAU_REQUIREMENTS_LOCK = "/opt/qea/nexau-requirements.lock"
NEXAU_UV_CACHE_DIR = "/opt/qea/nexau-uv-cache"
NEXAU_PYTHON_INSTALL_DIR = "/opt/qea/nexau-python"
NEXAU_PYTHON_BIN_DIR = "/opt/qea/nexau-bin"


class ImageConfigError(ValueError):
    """An image overlay is mutable, unpinned, or incompatible with the pilot."""


@dataclass(frozen=True)
class QFBenchOverlaySpec:
    task_id: str
    role: str
    benchmark_commit: str
    base_image: str
    dependencies: tuple[str, ...]
    install_commands: tuple[str, ...]
    context_dir: Path
    overlay_path: Path
    manifest_path: Path
    upstream_sha256: str
    overlay_sha256: str
    context_sha256: str
    template_name: str
    cpu_count: int
    memory_mb: int
    build_timeout_seconds: int


@dataclass(frozen=True)
class QFBenchTaskImageOperation:
    directive: str
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class QFBenchBaseTemplateOverlaySpec:
    task_id: str
    role: str
    benchmark_commit: str
    base_template_id: str
    base_build_id: str
    dependencies: tuple[str, ...]
    install_commands: tuple[str, ...]
    context_dir: Path
    dockerfile_path: Path
    manifest_path: Path
    upstream_sha256: str
    context_sha256: str
    template_name: str
    operations: tuple[QFBenchTaskImageOperation, ...]
    verifier_uvx_warm_command: str | None
    verifier_dependency_lock_command: str | None
    cpu_count: int
    memory_mb: int
    build_timeout_seconds: int


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_dependencies(dependencies: Iterable[str]) -> tuple[str, ...]:
    pinned = tuple(dependencies)
    if not pinned:
        raise ImageConfigError("overlay dependencies must not be empty")
    for dependency in pinned:
        if not (
            _EXACT_PACKAGE_RE.fullmatch(dependency)
            or _PINNED_HTTPS_VCS_RE.fullmatch(dependency)
        ):
            raise ImageConfigError(f"dependency must be exactly pinned: {dependency!r}")
    return pinned


def _dependency_install_commands(dependencies: Iterable[str]) -> tuple[str, ...]:
    """Return reproducible install steps without changing the task Python runtime."""

    pinned = _validate_dependencies(dependencies)
    if pinned != (NEXAU_WORKER_DEPENDENCY,):
        return (f"python -m pip install --no-cache-dir {shlex.join(pinned)}",)

    uv_environment = (
        f"UV_CACHE_DIR={NEXAU_UV_CACHE_DIR} "
        f"UV_PYTHON_INSTALL_DIR={NEXAU_PYTHON_INSTALL_DIR} "
        f"UV_PYTHON_BIN_DIR={NEXAU_PYTHON_BIN_DIR} "
        "UV_NO_PROGRESS=1"
    )
    return (
        "python -m pip install --no-cache-dir uv==0.9.5",
        (
            f"mkdir -p {NEXAU_UV_CACHE_DIR} {NEXAU_PYTHON_INSTALL_DIR} "
            f"{NEXAU_PYTHON_BIN_DIR}"
        ),
        f"{uv_environment} uv python install {NEXAU_PYTHON_VERSION}",
        (
            f"{uv_environment} uv venv --python {NEXAU_PYTHON_VERSION} "
            f"{NEXAU_RUNTIME_ROOT}"
        ),
        (
            f"{uv_environment} uv pip install --python {NEXAU_RUNTIME_PYTHON} "
            f"{NEXAU_WORKER_DEPENDENCY}"
        ),
        (
            f"{uv_environment} uv pip freeze --python {NEXAU_RUNTIME_PYTHON} "
            f"| LC_ALL=C sort > {NEXAU_REQUIREMENTS_LOCK}"
        ),
        (
            f'{NEXAU_RUNTIME_PYTHON} -c "import importlib.metadata as m, sys; '
            f"import nexau; assert sys.version_info[:2] == (3, 12); "
            f"assert m.version('nexau') == '0.3.9'\""
        ),
    )


def _validate_resources(
    cpu_count: int,
    memory_mb: int,
    build_timeout_seconds: int,
) -> tuple[int, int, int]:
    values = (cpu_count, memory_mb, build_timeout_seconds)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in values):
        raise ImageConfigError("CPU, memory, and build timeout must be positive integers")
    return values


def _write_publishable_manifest(path: Path, payload: dict) -> None:
    """Preserve one published identity and reject any attempt to rebind it."""

    if path.is_file():
        try:
            existing = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ImageConfigError(f"invalid existing image manifest {path}: {exc}") from exc
        published_template = existing.get("published_template_id")
        published_build = existing.get("published_build_id")
        if published_template or published_build:
            if existing.get("identity_sha256") != payload.get("identity_sha256"):
                raise ImageConfigError(
                    f"published manifest identity changed in {path}"
                )
            for key in ("published_template_id", "published_build_id", "published_at"):
                if key in existing:
                    payload[key] = existing[key]
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def _verifier_uvx_tokens(test_script: str) -> tuple[list[str], int] | None:
    logical = re.sub(r"\\\s*\n", " ", test_script)
    for line in logical.splitlines():
        stripped = line.strip()
        if stripped.startswith("if uvx "):
            stripped = stripped.removeprefix("if ")
        if not stripped.startswith("uvx "):
            continue
        try:
            tokens = shlex.split(stripped)
        except ValueError as exc:
            raise ImageConfigError(f"cannot parse official uvx command: {exc}") from exc
        try:
            pytest_index = tokens.index("pytest")
        except ValueError as exc:
            raise ImageConfigError("official uvx command does not invoke pytest") from exc
        return tokens, pytest_index
    if re.search(r"\buvx\b", logical):
        raise ImageConfigError("cannot locate official uvx command for offline warming")
    return None


def verifier_uvx_warm_command(test_script: str) -> str | None:
    """Extract the official uvx dependency declaration and replace tests with --version."""

    parsed = _verifier_uvx_tokens(test_script)
    if parsed is None:
        return None
    tokens, pytest_index = parsed
    return shlex.join([*tokens[:pytest_index + 1], "--version"])


def verifier_dependency_lock_command(test_script: str) -> str:
    """Persist the exact uvx environment, or the direct-Python image environment."""

    parsed = _verifier_uvx_tokens(test_script)
    if parsed is None:
        return "python -m pip freeze > /opt/qea/verifier-requirements.lock"
    tokens, pytest_index = parsed
    program = (
        "import importlib.metadata as m; "
        'print("\\n".join(sorted('
        'f"{d.metadata.get(\'Name\', \'UNKNOWN\')}=={d.version}" '
        "for d in m.distributions())))"
    )
    command = shlex.join([*tokens[:pytest_index], "python", "-c", program])
    return command + " > /opt/qea/verifier-requirements.lock"


def parse_qfbench_task_dockerfile(
    upstream_dockerfile: str,
) -> tuple[QFBenchTaskImageOperation, ...]:
    """Parse the deliberately small Dockerfile surface used by the pilot tasks."""

    operations: list[QFBenchTaskImageOperation] = []
    from_count = 0
    logical = re.sub(r"\\\s*\n", " ", upstream_dockerfile)
    for raw_line in logical.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        directive, separator, remainder = line.partition(" ")
        directive = directive.upper()
        remainder = remainder.strip() if separator else ""
        if directive == "FROM":
            from_count += 1
            words = shlex.split(remainder)
            if (
                len(words) != 1
                or _QFBENCH_PARENT_RE.fullmatch(words[0]) is None
            ):
                raise ImageConfigError(
                    f"unsupported QFBench task parent image: {remainder!r}"
                )
            continue
        if directive == "WORKDIR":
            words = shlex.split(remainder)
            if len(words) != 1 or not words[0].startswith("/"):
                raise ImageConfigError("task WORKDIR must be one absolute path")
            operations.append(QFBenchTaskImageOperation(directive, tuple(words)))
            continue
        if directive == "COPY":
            words = shlex.split(remainder)
            if len(words) != 2 or words[0].startswith("--"):
                raise ImageConfigError("task COPY must use one source and one destination")
            source = Path(words[0])
            if source.is_absolute() or ".." in source.parts or not words[1].startswith("/"):
                raise ImageConfigError("task COPY paths must stay inside the environment context")
            operations.append(QFBenchTaskImageOperation(directive, tuple(words)))
            continue
        if directive == "RUN":
            if not remainder:
                raise ImageConfigError("task RUN must not be empty")
            operations.append(QFBenchTaskImageOperation(directive, (remainder,)))
            continue
        raise ImageConfigError(
            f"unsupported task Dockerfile directive {directive!r}"
        )
    if from_count != 1:
        raise ImageConfigError("QFBench pilot requires exactly one task FROM directive")
    return tuple(operations)


def generate_qfbench_overlay(
    upstream_dockerfile: str,
    *,
    base_image: str,
    role: str,
    dependencies: Iterable[str],
    verifier_test_script: str | None = None,
) -> str:
    """Rewrite one upstream FROM and append a small role-specific pinned layer."""

    if not _DIGEST_IMAGE_RE.fullmatch(base_image):
        raise ImageConfigError(f"publication base image must be digest-pinned: {base_image!r}")
    if role not in {"worker", "verifier"}:
        raise ImageConfigError("overlay role must be worker or verifier")
    pinned = _validate_dependencies(dependencies)
    install_commands = _dependency_install_commands(pinned)

    lines = upstream_dockerfile.splitlines()
    indexes = [index for index, line in enumerate(lines) if _FROM_RE.match(line)]
    if len(indexes) != 1:
        raise ImageConfigError("QFBench pilot requires a single-stage Dockerfile")
    index = indexes[0]
    match = _FROM_RE.match(lines[index])
    assert match is not None
    lines[index] = f"{match.group('prefix')}{base_image}{match.group('suffix')}"
    lines.extend([
        "",
        f"# QEA generated {role} overlay; upstream snapshot remains unchanged.",
        "USER root",
        *(f"RUN {command}" for command in install_commands),
        'ENV PATH="/root/.local/bin:/usr/local/bin:${PATH}"',
        f'LABEL org.qea.qfbench.role="{role}"',
    ])
    if verifier_test_script is not None:
        if role != "verifier":
            raise ImageConfigError("verifier_test_script is only valid for verifier overlays")
        warm = verifier_uvx_warm_command(verifier_test_script)
        lock = verifier_dependency_lock_command(verifier_test_script)
        if warm:
            lines.extend([
                (
                    "RUN mkdir -p /opt/qea/uv-cache /opt/qea/uv-tools "
                    "/opt/qea/uv-bin && \\"
                ),
                (
                    "    UV_CACHE_DIR=/opt/qea/uv-cache "
                    "UV_TOOL_DIR=/opt/qea/uv-tools "
                    f"UV_TOOL_BIN_DIR=/opt/qea/uv-bin {warm}"
                ),
                (
                    "RUN UV_CACHE_DIR=/opt/qea/uv-cache "
                    "UV_TOOL_DIR=/opt/qea/uv-tools "
                    f"UV_TOOL_BIN_DIR=/opt/qea/uv-bin {lock}"
                ),
            ])
        else:
            lines.append(f"RUN {lock}")
    return "\n".join(lines) + "\n"


def _context_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((item for item in root.rglob("*") if item.is_file()),
                       key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        payload = path.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def prepare_qfbench_base_build_context(
    snapshot_root: str | Path,
    output_dir: str | Path,
) -> Path:
    """Stage only the two public files referenced by the QFBench base Dockerfile."""

    root = Path(snapshot_root).resolve()
    sources = {
        "docker/sandbox.Dockerfile": root / "docker" / "sandbox.Dockerfile",
        "docker/requirements-sandbox.txt": root / "docker" / "requirements-sandbox.txt",
    }
    missing = [relative for relative, source in sources.items() if not source.is_file()]
    if missing:
        raise ImageConfigError(f"QFBench base context is missing files: {missing}")
    context = Path(output_dir).resolve() / "base-context"
    context.mkdir(parents=True, exist_ok=True)
    existing = {
        path.relative_to(context).as_posix()
        for path in context.rglob("*")
        if path.is_file()
    }
    extras = existing - set(sources)
    if extras:
        raise ImageConfigError(f"refusing non-minimal QFBench base context: {sorted(extras)}")
    for relative, source in sources.items():
        target = context / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return context


def prepare_qfbench_overlay(
    *,
    task_id: str,
    upstream_dockerfile: str | Path,
    output_dir: str | Path,
    base_image: str,
    role: str,
    dependencies: Iterable[str],
    benchmark_commit: str,
    cpu_count: int,
    memory_mb: int,
    build_timeout_seconds: int,
    verifier_test_script: str | None = None,
) -> QFBenchOverlaySpec:
    dockerfile = Path(upstream_dockerfile).resolve()
    if not dockerfile.is_file():
        raise ImageConfigError(f"upstream Dockerfile does not exist: {dockerfile}")
    commit = benchmark_commit.strip().lower()
    if not _COMMIT_RE.fullmatch(commit):
        raise ImageConfigError("benchmark_commit must be a full 40-character SHA")
    pinned = _validate_dependencies(dependencies)
    install_commands = _dependency_install_commands(pinned)
    resources = _validate_resources(cpu_count, memory_mb, build_timeout_seconds)
    upstream = dockerfile.read_bytes()
    overlay = generate_qfbench_overlay(
        upstream.decode(),
        base_image=base_image,
        role=role,
        dependencies=pinned,
        verifier_test_script=verifier_test_script,
    ).encode()
    target_dir = Path(output_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = target_dir / f"Dockerfile.{task_id}.{role}"
    overlay_path.write_bytes(overlay)
    overlay_digest = _sha256(overlay)
    context_digest = _context_digest(dockerfile.parent)
    identity = _sha256(json.dumps({
        "task_id": task_id,
        "role": role,
        "benchmark_commit": commit,
        "base_image": base_image,
        "dependencies": pinned,
        "install_commands": install_commands,
        "upstream_sha256": _sha256(upstream),
        "overlay_sha256": overlay_digest,
        "context_sha256": context_digest,
        "cpu_count": resources[0],
        "memory_mb": resources[1],
        "build_timeout_seconds": resources[2],
    }, sort_keys=True, separators=(",", ":")).encode())
    template_name = f"qea-qfbench-{task_id}-{role}-{commit[:8]}-{identity[:12]}"
    manifest_path = target_dir / f"{task_id}.{role}.image.json"
    spec = QFBenchOverlaySpec(
        task_id=task_id,
        role=role,
        benchmark_commit=commit,
        base_image=base_image,
        dependencies=pinned,
        install_commands=install_commands,
        context_dir=dockerfile.parent,
        overlay_path=overlay_path,
        manifest_path=manifest_path,
        upstream_sha256=_sha256(upstream),
        overlay_sha256=overlay_digest,
        context_sha256=context_digest,
        template_name=template_name,
        cpu_count=resources[0],
        memory_mb=resources[1],
        build_timeout_seconds=resources[2],
    )
    payload = {
        **asdict(spec),
        "context_dir": str(spec.context_dir),
        "overlay_path": str(spec.overlay_path),
        "manifest_path": str(spec.manifest_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "identity_sha256": identity,
        "published_template_id": None,
        "published_build_id": None,
    }
    _write_publishable_manifest(manifest_path, payload)
    return spec


def prepare_qfbench_base_template_overlay(
    *,
    task_id: str,
    upstream_dockerfile: str | Path,
    output_dir: str | Path,
    base_template_id: str,
    base_build_id: str,
    role: str,
    dependencies: Iterable[str],
    benchmark_commit: str,
    cpu_count: int,
    memory_mb: int,
    build_timeout_seconds: int,
    verifier_test_script: str | None = None,
) -> QFBenchBaseTemplateOverlaySpec:
    """Describe an E2B task overlay rooted in an immutable E2B base build."""

    dockerfile = Path(upstream_dockerfile).resolve()
    if not dockerfile.is_file():
        raise ImageConfigError(f"upstream Dockerfile does not exist: {dockerfile}")
    if not base_template_id.strip() or not base_build_id.strip():
        raise ImageConfigError("base template ID and build ID must be non-empty")
    if role not in {"worker", "verifier"}:
        raise ImageConfigError("overlay role must be worker or verifier")
    commit = benchmark_commit.strip().lower()
    if not _COMMIT_RE.fullmatch(commit):
        raise ImageConfigError("benchmark_commit must be a full 40-character SHA")
    pinned = _validate_dependencies(dependencies)
    install_commands = _dependency_install_commands(pinned)
    resources = _validate_resources(cpu_count, memory_mb, build_timeout_seconds)
    upstream = dockerfile.read_bytes()
    operations = parse_qfbench_task_dockerfile(upstream.decode())
    warm = (
        verifier_uvx_warm_command(verifier_test_script or "")
        if role == "verifier"
        else None
    )
    lock = (
        verifier_dependency_lock_command(verifier_test_script or "")
        if role == "verifier"
        else None
    )
    context_digest = _context_digest(dockerfile.parent)
    identity_payload = json.dumps({
        "task_id": task_id,
        "role": role,
        "benchmark_commit": commit,
        "base_template_id": base_template_id,
        "base_build_id": base_build_id,
        "dependencies": pinned,
        "install_commands": install_commands,
        "upstream_sha256": _sha256(upstream),
        "context_sha256": context_digest,
        "operations": [asdict(item) for item in operations],
        "verifier_uvx_warm_command": warm,
        "verifier_dependency_lock_command": lock,
        "cpu_count": resources[0],
        "memory_mb": resources[1],
        "build_timeout_seconds": resources[2],
    }, sort_keys=True, separators=(",", ":")).encode()
    identity = _sha256(identity_payload)
    target_dir = Path(output_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / f"{task_id}.{role}.image.json"
    spec = QFBenchBaseTemplateOverlaySpec(
        task_id=task_id,
        role=role,
        benchmark_commit=commit,
        base_template_id=base_template_id.strip(),
        base_build_id=base_build_id.strip(),
        dependencies=pinned,
        install_commands=install_commands,
        context_dir=dockerfile.parent,
        dockerfile_path=dockerfile,
        manifest_path=manifest_path,
        upstream_sha256=_sha256(upstream),
        context_sha256=context_digest,
        template_name=f"qea-qfbench-{task_id}-{role}-{commit[:8]}-{identity[:12]}",
        operations=operations,
        verifier_uvx_warm_command=warm,
        verifier_dependency_lock_command=lock,
        cpu_count=resources[0],
        memory_mb=resources[1],
        build_timeout_seconds=resources[2],
    )
    payload = {
        "task_id": spec.task_id,
        "role": spec.role,
        "benchmark_commit": spec.benchmark_commit,
        "base_template_id": spec.base_template_id,
        "base_build_id": spec.base_build_id,
        "dependencies": list(spec.dependencies),
        "install_commands": list(spec.install_commands),
        "context_dir": str(spec.context_dir),
        "dockerfile_path": str(spec.dockerfile_path),
        "manifest_path": str(spec.manifest_path),
        "upstream_sha256": spec.upstream_sha256,
        "context_sha256": spec.context_sha256,
        "template_name": spec.template_name,
        "operations": [asdict(item) for item in spec.operations],
        "verifier_uvx_warm_command": spec.verifier_uvx_warm_command,
        "verifier_dependency_lock_command": spec.verifier_dependency_lock_command,
        "cpu_count": spec.cpu_count,
        "memory_mb": spec.memory_mb,
        "build_timeout_seconds": spec.build_timeout_seconds,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "identity_sha256": identity,
        "published_template_id": None,
        "published_build_id": None,
    }
    _write_publishable_manifest(manifest_path, payload)
    return spec


def apply_qfbench_e2b_task_overlay(builder, spec: QFBenchBaseTemplateOverlaySpec):
    """Apply validated task operations and role dependencies to an E2B builder."""

    builder.set_user("root")
    for operation in spec.operations:
        if operation.directive == "WORKDIR":
            builder.set_workdir(operation.arguments[0])
        elif operation.directive == "COPY":
            builder.copy(operation.arguments[0], operation.arguments[1])
        elif operation.directive == "RUN":
            builder.run_cmd(operation.arguments[0], user="root")
        else:  # pragma: no cover - construction validates this invariant.
            raise ImageConfigError(f"unsupported operation {operation.directive!r}")
    for command in spec.install_commands:
        builder.run_cmd(command, user="root")
    if spec.verifier_uvx_warm_command:
        builder.run_cmd(
            "mkdir -p /opt/qea/uv-cache /opt/qea/uv-tools /opt/qea/uv-bin",
            user="root",
        )
        builder.run_cmd(
            "UV_CACHE_DIR=/opt/qea/uv-cache UV_TOOL_DIR=/opt/qea/uv-tools "
            "UV_TOOL_BIN_DIR=/opt/qea/uv-bin " + spec.verifier_uvx_warm_command,
            user="root",
        )
    if spec.verifier_dependency_lock_command:
        lock_prefix = (
            "UV_CACHE_DIR=/opt/qea/uv-cache UV_TOOL_DIR=/opt/qea/uv-tools "
            "UV_TOOL_BIN_DIR=/opt/qea/uv-bin "
            if spec.verifier_uvx_warm_command
            else ""
        )
        builder.run_cmd(
            lock_prefix + spec.verifier_dependency_lock_command,
            user="root",
        )
    return builder


def record_published_template(
    spec: QFBenchOverlaySpec | QFBenchBaseTemplateOverlaySpec,
    *,
    template_id: str,
    build_id: str,
) -> None:
    payload = json.loads(spec.manifest_path.read_text())
    existing_template = payload.get("published_template_id")
    existing_build = payload.get("published_build_id")
    if (existing_template or existing_build) and (
        existing_template != template_id or existing_build != build_id
    ):
        raise ImageConfigError(
            f"template manifest is already published as {existing_template}/{existing_build}"
        )
    if existing_template == template_id and existing_build == build_id:
        return
    payload["published_template_id"] = template_id
    payload["published_build_id"] = build_id
    payload["published_at"] = datetime.now(timezone.utc).isoformat()
    spec.manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
