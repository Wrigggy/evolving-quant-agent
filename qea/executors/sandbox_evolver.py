"""Run one full-harness evolver through a provider-neutral sandbox backend."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import stat
import tarfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping

from ..evolution_evidence import EvidenceRecord
from ..model_proxy import (
    ModelProxyError,
    build_model_proxy_sandbox_plan,
    model_proxy_attempt_identity,
)
from ..qfbench_images import NEXAU_REQUIREMENTS_LOCK, NEXAU_RUNTIME_PYTHON
from ..resource_lease import HostResourceLeasePool, ResourceRequest
from ..sandbox_backend import SandboxBackend, SandboxCommandResult, SandboxSpec
from ..sandbox_lifecycle import (
    create_lifecycle,
    load_lifecycle,
    mark_finished,
    mark_started,
)
from .bundles import (
    BundleError,
    build_evolver_input_bundle,
    extract_candidate_archive,
)
from .sandbox_proxy import SandboxProxyManager
from .sandbox_runtime import (
    SandboxInfrastructureError,
    SandboxResourceContract,
    atomic_json,
    atomic_bytes,
    backend_call,
    finish_and_cleanup,
    public_model_environment,
    read_bounded,
    require_tmpfs,
    run_required,
    trusted_directory,
    trusted_regular_path,
    utc_now,
    validate_public_model_env,
    write_command_log,
)


_REMOTE_RUNNER = Path(__file__).with_name("remote_evolver.py")
_RUNTIME_BRIDGE = Path(__file__).parents[1] / "runtime_bridge.py"
_REQUIRED_TMPFS = frozenset({"/tmp", "/qea"})
_TASK_ID = "full-harness-evolver"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CREDENTIAL_KEY = re.compile(
    r"(?i)(?:^|[_-])(?:api[_-]?key|access[_-]?token|authorization|auth|bearer|"
    r"token|secret|password|passwd|credential|credentials)$"
)
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)\b([a-z0-9_-]*(?:api[_-]?key|access[_-]?token|authorization|auth|"
    r"bearer|token|secret|password|passwd|credentials?))"
    r"(\s*[:=]\s*)([\"']?)([^\"'\s,;]+)\3"
)
_BEARER_CREDENTIAL = re.compile(r"(?i)\bBearer\s+([^\s,;\"']+)")
_URL_CREDENTIAL = re.compile(
    r"(?i)(https?://)([^/\s:@]+):([^@\s/]+)@"
)
_DOWNLOAD_LIMITS = {
    "raw_trace.jsonl": 4 * 1024 * 1024,
    "final.txt": 512 * 1024,
    "prediction.json": 2 * 1024 * 1024,
    "access-summary.json": 2 * 1024 * 1024,
    "summary.json": 2 * 1024 * 1024,
}
_JSON_EVIDENCE = frozenset(
    {"prediction.json", "access-summary.json", "summary.json"}
)
_DEPENDENCY_LOCK_LIMIT = 8 * 1024 * 1024
_TAR_MEMBER_ENVELOPE_BYTES = 8 * 1024
_TAR_TRAILER_BYTES = 10 * 1024
_PRIVATE_EVIDENCE_PARTS = frozenset(
    {
        "tests",
        "solution",
        "official-tests",
        "official_tests",
        "reference-data",
        "reference_data",
        "trusted-verifier",
        "trusted_verifier",
        "gold",
    }
)


@dataclass(frozen=True)
class SandboxEvolverConfig:
    image_ref: str
    resource_contract: SandboxResourceContract
    command_timeout_seconds: int = 1800
    max_input_files: int = 2000
    max_input_bytes: int = 512 * 1024 * 1024
    max_candidate_files: int = 2000
    max_candidate_bytes: int = 64 * 1024 * 1024
    lease_timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not isinstance(self.image_ref, str) or not self.image_ref:
            raise SandboxInfrastructureError(
                "evolver.config", "image_ref must be non-empty"
            )
        if not isinstance(self.resource_contract, SandboxResourceContract):
            raise SandboxInfrastructureError(
                "evolver.config",
                "resource_contract must be a SandboxResourceContract",
            )
        require_tmpfs(self.resource_contract, _REQUIRED_TMPFS, role="evolver")
        for name in (
            "command_timeout_seconds",
            "max_input_files",
            "max_input_bytes",
            "max_candidate_files",
            "max_candidate_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise SandboxInfrastructureError(
                    "evolver.config", f"{name} must be a positive integer"
                )
        if self.resource_contract.timeout_seconds < self.command_timeout_seconds:
            raise SandboxInfrastructureError(
                "evolver.config",
                "sandbox lifetime must be at least the command timeout",
            )
        if (
            isinstance(self.lease_timeout_seconds, bool)
            or not isinstance(self.lease_timeout_seconds, (int, float))
            or not math.isfinite(self.lease_timeout_seconds)
            or self.lease_timeout_seconds < 0
        ):
            raise SandboxInfrastructureError(
                "evolver.config",
                "lease_timeout_seconds must be non-negative and finite",
            )


@dataclass(frozen=True)
class SandboxEvolverResult:
    iteration: int
    candidate_dir: Path
    candidate_digest: str
    input_bundle_sha256: str
    trace_uri: Path
    final_uri: Path
    prediction_uri: Path
    access_summary_uri: Path
    summary_uri: Path
    command_log_uri: Path
    lifecycle_uri: Path
    proxy_lifecycle_uri: Path
    dependency_lock_uri: Path
    sandbox_id: str
    proxy_sandbox_id: str
    network_id: str
    cleaned_up: bool
    backend: str
    spec_sha256: str
    executed_proxy_image_ref: str
    executed_proxy_spec_sha256: str
    executed_proxy_public_plan_sha256: str
    executed_proxy_config_sha256: str
    executed_proxy_attempt_identity_sha256: str


def _digest_tree(root: Path) -> str:
    if root.is_symlink() or not root.is_dir():
        raise SandboxInfrastructureError(
            "evolver.candidate", f"candidate directory is unavailable: {root}"
        )
    digest = hashlib.sha256()
    for path in sorted(
        root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
    ):
        relative_path = path.relative_to(root)
        if path.is_symlink():
            raise SandboxInfrastructureError(
                "evolver.candidate", f"candidate symlink is forbidden: {relative_path}"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise SandboxInfrastructureError(
                "evolver.candidate", f"candidate entry is not regular: {relative_path}"
            )
        relative = relative_path.as_posix().encode()
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_evidence_member(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise SandboxInfrastructureError(
            "evolver.evidence", f"unsafe evidence member: {value!r}"
        )
    if any(part.casefold() in _PRIVATE_EVIDENCE_PARTS for part in path.parts):
        raise SandboxInfrastructureError(
            "evolver.evidence", f"private evaluator path in evidence: {value}"
        )
    return path


def _digest_evidence_payloads(
    payloads: Mapping[str, bytes],
) -> tuple[str, tuple[str, ...]]:
    nested_access_logs = [
        name
        for name in payloads
        if PurePosixPath(name).name == "access_log.jsonl"
        and name != "access_log.jsonl"
    ]
    if nested_access_logs:
        raise SandboxInfrastructureError(
            "evolver.evidence",
            f"nested access_log.jsonl is forbidden: {sorted(nested_access_logs)}",
        )
    if payloads.get("access_log.jsonl") != b"":
        raise SandboxInfrastructureError(
            "evolver.evidence",
            "evidence requires exactly one empty root access_log.jsonl",
        )
    digest = hashlib.sha256()
    members: list[str] = []
    for name in sorted(payloads):
        path = _safe_evidence_member(name)
        if path.as_posix() == "access_log.jsonl":
            continue
        payload = payloads[name]
        encoded = path.as_posix().encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        members.append(path.as_posix())
    return digest.hexdigest(), tuple(members)


def _validate_evidence_record(
    value: object, *, contained_by: Path
) -> tuple[EvidenceRecord, Path]:
    if not isinstance(value, EvidenceRecord):
        raise SandboxInfrastructureError(
            "evolver.evidence",
            "evidence_dir must be an authorized EvidenceRecord",
        )
    if _SHA256.fullmatch(value.sha256) is None:
        raise SandboxInfrastructureError(
            "evolver.evidence", "EvidenceRecord has an invalid digest"
        )
    if (
        not isinstance(value.members, tuple)
        or tuple(sorted(set(value.members))) != value.members
    ):
        raise SandboxInfrastructureError(
            "evolver.evidence", "EvidenceRecord members are not canonical"
        )
    for member in value.members:
        safe = _safe_evidence_member(member)
        if safe.name == "access_log.jsonl":
            raise SandboxInfrastructureError(
                "evolver.evidence",
                "EvidenceRecord must exclude access_log.jsonl from its identity",
            )
    root = trusted_directory(
        value.root,
        create=False,
        phase="evolver.evidence",
        contained_by=contained_by,
    )
    payloads: dict[str, bytes] = {}
    for path in sorted(
        root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
    ):
        relative = path.relative_to(root).as_posix()
        _safe_evidence_member(relative)
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise SandboxInfrastructureError(
                "evolver.evidence", f"cannot inspect evidence member {relative}: {exc}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise SandboxInfrastructureError(
                "evolver.evidence", f"symlink is forbidden in evidence: {relative}"
            )
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise SandboxInfrastructureError(
                "evolver.evidence", f"evidence member is not regular: {relative}"
            )
        try:
            payloads[relative] = path.read_bytes()
        except OSError as exc:
            raise SandboxInfrastructureError(
                "evolver.evidence", f"cannot read evidence member {relative}: {exc}"
            ) from exc
    digest, members = _digest_evidence_payloads(payloads)
    if digest != value.sha256 or members != value.members:
        raise SandboxInfrastructureError(
            "evolver.evidence", "EvidenceRecord evidence digest or members changed"
        )
    return value, root


def _verify_bundled_evidence(bundle_path: Path, record: EvidenceRecord) -> None:
    payloads: dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(bundle_path.read_bytes()), mode="r:*") as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if not path.parts or path.parts[0] != "evidence":
                    continue
                if member.isdir():
                    continue
                if not member.isfile():
                    raise SandboxInfrastructureError(
                        "evolver.evidence",
                        f"non-regular evidence bundle member: {member.name}",
                    )
                relative = PurePosixPath(*path.parts[1:]).as_posix()
                _safe_evidence_member(relative)
                if relative in payloads:
                    raise SandboxInfrastructureError(
                        "evolver.evidence",
                        f"duplicate evidence bundle member: {relative}",
                    )
                handle = archive.extractfile(member)
                if handle is None:
                    raise SandboxInfrastructureError(
                        "evolver.evidence",
                        f"unreadable evidence bundle member: {member.name}",
                    )
                payloads[relative] = handle.read()
    except (OSError, tarfile.TarError) as exc:
        raise SandboxInfrastructureError(
            "evolver.evidence", f"invalid evolver input archive: {exc}"
        ) from exc
    digest, members = _digest_evidence_payloads(payloads)
    if digest != record.sha256 or members != record.members:
        raise SandboxInfrastructureError(
            "evolver.evidence",
            "bundled evidence differs from the authorized EvidenceRecord",
        )


def _is_credential_key(value: object) -> bool:
    return isinstance(value, str) and _CREDENTIAL_KEY.search(value) is not None


def _text_secrets(text: str) -> set[str]:
    secrets = {
        match.group(4)
        for match in _CREDENTIAL_ASSIGNMENT.finditer(text)
        if match.group(4)
    }
    secrets.update(
        match.group(1) for match in _BEARER_CREDENTIAL.finditer(text)
    )
    secrets.update(
        match.group(3) for match in _URL_CREDENTIAL.finditer(text)
    )
    return secrets


def _collect_known_secrets(value: object) -> set[str]:
    secrets: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _is_credential_key(key) and isinstance(item, str) and item:
                bearer = _BEARER_CREDENTIAL.fullmatch(item.strip())
                secrets.add(bearer.group(1) if bearer else item)
            secrets.update(_collect_known_secrets(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            secrets.update(_collect_known_secrets(item))
    elif isinstance(value, str):
        secrets.update(_text_secrets(value))
    return {secret for secret in secrets if secret and secret != "[REDACTED]"}


def _redact_text(text: str, known_secrets: set[str]) -> str:
    scrubbed = _CREDENTIAL_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text
    )
    scrubbed = _BEARER_CREDENTIAL.sub("Bearer [REDACTED]", scrubbed)
    scrubbed = _URL_CREDENTIAL.sub(r"\1[REDACTED]@", scrubbed)
    for secret in sorted(known_secrets, key=len, reverse=True):
        scrubbed = scrubbed.replace(secret, "[REDACTED]")
    return scrubbed


def _scrub_structure(value: object, known_secrets: set[str]) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "[REDACTED]"
                if _is_credential_key(key)
                else _scrub_structure(item, known_secrets)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_structure(item, known_secrets) for item in value]
    if isinstance(value, tuple):
        return [_scrub_structure(item, known_secrets) for item in value]
    if isinstance(value, str):
        return _redact_text(value, known_secrets)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise SandboxInfrastructureError(
        "evolver.diagnosis", "diagnosis contains a non-JSON value"
    )


def _safe_diagnosis(value: object) -> tuple[bytes, tuple[str, ...]]:
    parsed: object = value
    serialize_json = isinstance(value, Mapping)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, (dict, list)):
            parsed = decoded
            serialize_json = True
    elif not isinstance(value, Mapping):
        raise SandboxInfrastructureError(
            "evolver.diagnosis", "diagnosis must be text or a JSON object"
        )
    known_secrets = _collect_known_secrets(parsed)
    scrubbed = _scrub_structure(parsed, known_secrets)
    if serialize_json:
        text = json.dumps(scrubbed, sort_keys=True, separators=(",", ":"))
    else:
        text = str(scrubbed)
    encoded = text.encode("utf-8")
    if len(encoded) > 2 * 1024 * 1024:
        raise SandboxInfrastructureError(
            "evolver.diagnosis", "diagnosis exceeds its bounded contract"
        )
    return encoded, tuple(sorted(known_secrets))


def _proxy_identity(
    proxy_manager: SandboxProxyManager,
    *,
    run_id: str,
    attempt_id: str,
) -> tuple[str, str, str]:
    config = proxy_manager.config
    resources = config.resource_contract
    try:
        plan = build_model_proxy_sandbox_plan(
            run_id=run_id,
            attempt_id=attempt_id,
            task_id=_TASK_ID,
            image_ref=config.image_ref,
            upstream_base_url=config.upstream_base_url,
            allowed_path_prefix=config.allowed_path_prefix,
            listen_port=config.listen_port,
            cpu_count=resources.cpu_count,
            memory_mb=resources.memory_mb,
            pids_limit=resources.pids_limit,
            timeout_seconds=resources.timeout_seconds,
            network_scope=attempt_id,
            allowed_model=config.allowed_model,
            audit_path="/run/qea-secrets/proxy-audit.jsonl",
            denied_request_identities_sha256=(),
            writable_tmpfs_mb=resources.writable_tmpfs_mb,
        )
    except (AttributeError, ModelProxyError) as exc:
        raise SandboxInfrastructureError(
            "evolver.config", f"invalid public proxy identity: {exc}"
        ) from exc
    public_config = {
        "plan_config": plan.config_payload(),
        "manager_timeout_seconds": config.timeout_seconds,
        "expect_request": config.expect_request,
    }
    config_sha256 = _sha256(
        json.dumps(public_config, sort_keys=True, separators=(",", ":")).encode()
    )
    return plan.spec.image_ref, plan.spec.spec_sha256, config_sha256


def _attempt_identity(
    *,
    run_id: str,
    iteration: int,
    input_bundle_sha256: str,
    diagnosis_sha256: str,
    model_name: str,
    image_ref: str,
    spec_sha256: str,
    proxy_image_ref: str,
    proxy_spec_sha256: str,
    proxy_config_sha256: str,
    backend: str,
) -> str:
    payload = {
        "backend": backend,
        "diagnosis_sha256": diagnosis_sha256,
        "image_ref": image_ref,
        "input_bundle_sha256": input_bundle_sha256,
        "iteration": iteration,
        "model_name": model_name,
        "proxy_config_sha256": proxy_config_sha256,
        "proxy_image_ref": proxy_image_ref,
        "proxy_spec_sha256": proxy_spec_sha256,
        "run_id": run_id,
        "spec_sha256": spec_sha256,
    }
    return _sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )


def _combined_request(
    evolver: SandboxResourceContract,
    proxy: SandboxResourceContract,
) -> ResourceRequest:
    return ResourceRequest(
        cpu_count=evolver.cpu_count + proxy.cpu_count,
        memory_mb=evolver.memory_mb + proxy.memory_mb,
        pids_limit=evolver.pids_limit + proxy.pids_limit,
        tmpfs_mb=sum(evolver.writable_tmpfs_mb.values())
        + sum(proxy.writable_tmpfs_mb.values()),
        sandboxes=2,
    )


def _validate_evidence(
    name: str,
    payload: object,
    *,
    forbidden_values: tuple[str, ...] = (),
) -> bytes:
    if not isinstance(payload, bytes):
        raise SandboxInfrastructureError(
            "evolver.download", f"{name} download is not bytes"
        )
    if len(payload) > _DOWNLOAD_LIMITS[name]:
        raise SandboxInfrastructureError(
            "evolver.download", f"{name} exceeds its bounded contract"
        )
    if any(value.encode() in payload for value in forbidden_values if value):
        raise SandboxInfrastructureError(
            "evolver.download", f"{name} contains a forbidden credential value"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SandboxInfrastructureError(
            "evolver.download", f"{name} is not UTF-8"
        ) from exc
    if name in _JSON_EVIDENCE:
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SandboxInfrastructureError(
                "evolver.download", f"{name} is invalid JSON"
            ) from exc
        if not isinstance(value, dict):
            raise SandboxInfrastructureError(
                "evolver.download", f"{name} must contain a JSON object"
            )
    elif name == "raw_trace.jsonl":
        for line_number, line in enumerate(text.splitlines(), start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SandboxInfrastructureError(
                    "evolver.download",
                    f"raw_trace.jsonl line {line_number} is invalid JSON",
                ) from exc
            if not isinstance(value, dict):
                raise SandboxInfrastructureError(
                    "evolver.download",
                    f"raw_trace.jsonl line {line_number} is not an object",
                )
    return payload


def _candidate_archive_limit(config: SandboxEvolverConfig) -> int:
    """Bound tar transport from the configured extracted payload and file caps."""

    return (
        config.max_candidate_bytes
        + config.max_candidate_files * _TAR_MEMBER_ENVELOPE_BYTES
        + _TAR_TRAILER_BYTES
    )


def _result_paths(
    evolution_dir: Path,
    lifecycle_path: Path,
    proxy_lifecycle_path: Path,
) -> dict[str, Path]:
    return {
        "trace_uri": evolution_dir / "raw_trace.jsonl",
        "final_uri": evolution_dir / "final.txt",
        "prediction_uri": evolution_dir / "prediction.json",
        "access_summary_uri": evolution_dir / "access-summary.json",
        "summary_uri": evolution_dir / "summary.json",
        "command_log_uri": evolution_dir / "command.json",
        "lifecycle_uri": lifecycle_path,
        "proxy_lifecycle_uri": proxy_lifecycle_path,
        "dependency_lock_uri": evolution_dir / "nexau-requirements.lock",
    }


def _load_completed(
    evolution_dir: Path,
    *,
    expected_identity: Mapping[str, object],
    paths: Mapping[str, Path],
) -> SandboxEvolverResult | None:
    manifest_path = evolution_dir / "result.json"
    trusted_regular_path(
        manifest_path,
        phase="evolver.resume",
        contained_by=evolution_dir,
        allow_missing=True,
    )
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SandboxInfrastructureError(
            "evolver.resume", f"invalid completed result: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise SandboxInfrastructureError(
            "evolver.resume", "completed result must be an object"
        )
    actual_identity = {name: payload.get(name) for name in expected_identity}
    if actual_identity != dict(expected_identity):
        raise SandboxInfrastructureError(
            "evolver.resume",
            f"completed result identity mismatch: expected {dict(expected_identity)}, "
            f"found {actual_identity}",
        )
    if payload.get("cleaned_up") is not True:
        raise SandboxInfrastructureError(
            "evolver.resume", "completed result was not exactly cleaned"
        )
    missing: list[str] = []
    for name, path in paths.items():
        trusted_regular_path(
            path,
            phase="evolver.resume",
            allow_missing=True,
        )
        if not path.exists():
            missing.append(name)
    if missing:
        raise SandboxInfrastructureError(
            "evolver.resume", f"completed result files are missing: {missing}"
        )
    candidate_dir = trusted_directory(
        evolution_dir / "candidate",
        create=False,
        phase="evolver.resume",
        contained_by=evolution_dir,
    )
    candidate_digest = _digest_tree(candidate_dir)
    if candidate_digest != payload.get("candidate_digest"):
        raise SandboxInfrastructureError(
            "evolver.resume", "completed candidate digest mismatch"
        )
    lifecycle = load_lifecycle(paths["lifecycle_uri"])
    if (
        lifecycle.cleaned_up is not True
        or lifecycle.native_id != payload.get("sandbox_id")
        or lifecycle.spec_sha256 != payload.get("spec_sha256")
        or lifecycle.attempt_identity_sha256
        != payload.get("attempt_identity_sha256")
    ):
        raise SandboxInfrastructureError(
            "evolver.resume", "completed lifecycle identity mismatch"
        )
    executed_identity_fields = (
        "executed_proxy_spec_sha256",
        "executed_proxy_public_plan_sha256",
        "executed_proxy_config_sha256",
        "executed_proxy_attempt_identity_sha256",
    )
    if any(
        _SHA256.fullmatch(str(payload.get(name, ""))) is None
        for name in executed_identity_fields
    ) or not isinstance(payload.get("executed_proxy_image_ref"), str):
        raise SandboxInfrastructureError(
            "evolver.resume", "completed proxy execution identity is invalid"
        )
    recomputed_proxy_attempt_identity = model_proxy_attempt_identity(
        public_plan_sha256=str(
            payload["executed_proxy_public_plan_sha256"]
        ),
        public_config_sha256=str(payload["executed_proxy_config_sha256"]),
    )
    if recomputed_proxy_attempt_identity != payload.get(
        "executed_proxy_attempt_identity_sha256"
    ):
        raise SandboxInfrastructureError(
            "evolver.resume", "completed proxy execution identity mismatch"
        )
    proxy_lifecycle = load_lifecycle(paths["proxy_lifecycle_uri"])
    if (
        proxy_lifecycle.cleaned_up is not True
        or proxy_lifecycle.native_id != payload.get("proxy_sandbox_id")
        or proxy_lifecycle.immutable_image_ref
        != payload.get("executed_proxy_image_ref")
        or proxy_lifecycle.spec_sha256
        != payload.get("executed_proxy_spec_sha256")
        or proxy_lifecycle.attempt_identity_sha256
        != payload.get("executed_proxy_attempt_identity_sha256")
    ):
        raise SandboxInfrastructureError(
            "evolver.resume", "completed proxy lifecycle identity mismatch"
        )
    file_digests = payload.get("file_sha256")
    if not isinstance(file_digests, dict) or any(
        _SHA256.fullmatch(str(file_digests.get(name, ""))) is None
        or _sha256(path.read_bytes()) != file_digests.get(name)
        for name, path in paths.items()
    ):
        raise SandboxInfrastructureError(
            "evolver.resume", "completed result evidence digest mismatch"
        )
    return SandboxEvolverResult(
        iteration=int(payload["iteration"]),
        candidate_dir=candidate_dir,
        candidate_digest=candidate_digest,
        input_bundle_sha256=str(payload["input_bundle_sha256"]),
        sandbox_id=str(payload["sandbox_id"]),
        proxy_sandbox_id=str(payload["proxy_sandbox_id"]),
        network_id=str(payload["network_id"]),
        cleaned_up=True,
        backend=str(payload["backend"]),
        spec_sha256=str(payload["spec_sha256"]),
        executed_proxy_image_ref=str(payload["executed_proxy_image_ref"]),
        executed_proxy_spec_sha256=str(
            payload["executed_proxy_spec_sha256"]
        ),
        executed_proxy_public_plan_sha256=str(
            payload["executed_proxy_public_plan_sha256"]
        ),
        executed_proxy_config_sha256=str(
            payload["executed_proxy_config_sha256"]
        ),
        executed_proxy_attempt_identity_sha256=str(
            payload["executed_proxy_attempt_identity_sha256"]
        ),
        **paths,
    )


def _validate_executed_proxy_session(
    session: object,
    *,
    lifecycle_path: Path,
    run_root: Path,
    run_id: str,
    attempt_id: str,
    expected_image_ref: str,
    expected_spec_sha256: str,
    require_cleaned: bool,
) -> None:
    try:
        session_lifecycle_path = trusted_regular_path(
            getattr(session, "lifecycle_uri"),
            phase="evolver.proxy",
            contained_by=run_root,
        )
        executed_image_ref = getattr(session, "immutable_image_ref")
        executed_spec_sha256 = getattr(session, "spec_sha256")
        public_plan_sha256 = getattr(session, "public_plan_sha256")
        public_config_sha256 = getattr(session, "public_config_sha256")
        attempt_identity_sha256 = getattr(
            session, "attempt_identity_sha256"
        )
    except (AttributeError, TypeError) as exc:
        raise SandboxInfrastructureError(
            "evolver.proxy", "proxy session identity is incomplete"
        ) from exc
    if session_lifecycle_path != lifecycle_path:
        raise SandboxInfrastructureError(
            "evolver.proxy", "proxy session lifecycle path is unexpected"
        )
    if (
        executed_image_ref != expected_image_ref
        or executed_spec_sha256 != expected_spec_sha256
        or _SHA256.fullmatch(str(public_plan_sha256)) is None
        or _SHA256.fullmatch(str(public_config_sha256)) is None
        or _SHA256.fullmatch(str(attempt_identity_sha256)) is None
    ):
        raise SandboxInfrastructureError(
            "evolver.proxy", "proxy session identity differs from static spec"
        )
    if model_proxy_attempt_identity(
        public_plan_sha256=str(public_plan_sha256),
        public_config_sha256=str(public_config_sha256),
    ) != str(attempt_identity_sha256):
        raise SandboxInfrastructureError(
            "evolver.proxy", "proxy session identity digest is inconsistent"
        )
    lifecycle = load_lifecycle(session_lifecycle_path)
    if (
        lifecycle.backend == ""
        or lifecycle.role != "proxy"
        or lifecycle.run_id != run_id
        or lifecycle.attempt_id != attempt_id
        or lifecycle.task_id != _TASK_ID
        or lifecycle.native_id != getattr(session, "native_id", None)
        or lifecycle.immutable_image_ref != executed_image_ref
        or lifecycle.spec_sha256 != executed_spec_sha256
        or lifecycle.attempt_identity_sha256 != attempt_identity_sha256
        or lifecycle.cleaned_up is not require_cleaned
    ):
        raise SandboxInfrastructureError(
            "evolver.proxy", "proxy session identity differs from lifecycle"
        )


class SandboxFullHarnessProposer:
    """Run exactly one evidence-driven edit behind a per-attempt model proxy."""

    def __init__(
        self,
        *,
        config: SandboxEvolverConfig,
        backend: SandboxBackend,
        lifecycle_root: str | Path,
        proxy_manager: SandboxProxyManager,
        resource_pool: HostResourceLeasePool,
        model_name: str,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not isinstance(config, SandboxEvolverConfig):
            raise SandboxInfrastructureError(
                "evolver.config", "config must be a SandboxEvolverConfig"
            )
        if getattr(proxy_manager, "backend", None) is not backend:
            raise SandboxInfrastructureError(
                "evolver.config", "evolver and proxy must use the same backend"
            )
        proxy_resources = getattr(
            getattr(proxy_manager, "config", None), "resource_contract", None
        )
        if not isinstance(proxy_resources, SandboxResourceContract):
            raise SandboxInfrastructureError(
                "evolver.config", "proxy resource contract is unavailable"
            )
        if (
            not isinstance(model_name, str)
            or not model_name.strip()
            or getattr(proxy_manager.config, "allowed_model", None) != model_name
        ):
            raise SandboxInfrastructureError(
                "evolver.config", "proxy and evolver model identity differ"
            )
        self.config = config
        self.backend = backend
        self.lifecycle_root = trusted_directory(
            lifecycle_root, create=True, phase="evolver.lifecycle"
        )
        self.proxy_manager = proxy_manager
        self.resource_pool = resource_pool
        self.model_name = model_name
        self.clock = clock
        self.proxy_resources = proxy_resources

    def propose(
        self,
        *,
        candidate_dir: str | Path,
        evidence_dir: EvidenceRecord,
        evolver_dir: str | Path,
        diagnosis: object,
        iteration: int,
        run_id: str,
        run_dir: str | Path,
        model_env: Mapping[str, str] | None = None,
    ) -> SandboxEvolverResult:
        if type(iteration) is not int or iteration < 1:
            raise SandboxInfrastructureError(
                "evolver.config", "iteration must be a positive integer"
            )
        run_root = trusted_directory(
            run_dir, create=False, phase="evolver.run"
        )
        evolution_dir = trusted_directory(
            run_root / "evolutions" / f"iteration-{iteration:04d}",
            create=True,
            phase="evolver.result",
            contained_by=run_root,
        )
        candidate_root = trusted_directory(
            candidate_dir, create=False, phase="evolver.input"
        )
        evolver_root = trusted_directory(
            evolver_dir, create=False, phase="evolver.input"
        )
        evidence_record, evidence_root = _validate_evidence_record(
            evidence_dir, contained_by=run_root
        )
        attempt_id = f"evolver-iteration-{iteration}"
        proxy_attempt_dir = trusted_directory(
            run_root / "attempts" / attempt_id,
            create=True,
            phase="evolver.proxy-state",
            contained_by=run_root,
        )
        proxy_lifecycle_dir = trusted_directory(
            run_root / "lifecycles" / attempt_id,
            create=True,
            phase="evolver.proxy-state",
            contained_by=run_root,
        )
        proxy_registry_path = run_root / "proxy-request-registry.json"
        proxy_audit_path = proxy_attempt_dir / "proxy-audit.jsonl"
        quarantine_path = proxy_attempt_dir / "proxy-audit.quarantined.json"
        proxy_lifecycle_path = (
            proxy_lifecycle_dir / "proxy-sandbox-lifecycle-v2.json"
        )
        for proxy_state_path in (
            proxy_registry_path,
            proxy_audit_path,
            quarantine_path,
            proxy_lifecycle_path,
        ):
            trusted_regular_path(
                proxy_state_path,
                phase="evolver.proxy-state",
                contained_by=run_root,
                allow_missing=True,
            )
        proxy_url = (
            f"http://qea-model-proxy:{self.proxy_manager.config.listen_port}"
            f"{self.proxy_manager.config.allowed_path_prefix}"
        )
        environment = public_model_environment(
            proxy_base_url=proxy_url, model_name=self.model_name
        )
        validate_public_model_env(model_env, environment, role="evolver")
        diagnosis_payload, known_secrets = _safe_diagnosis(diagnosis)
        diagnosis_sha256 = _sha256(diagnosis_payload)
        pending_input_path = evolution_dir / "input.pending.tar"
        trusted_regular_path(
            pending_input_path,
            phase="evolver.input",
            contained_by=evolution_dir,
            allow_missing=True,
        )
        if pending_input_path.exists():
            raise SandboxInfrastructureError(
                "evolver.input", "stale pending input archive is ambiguous"
            )
        try:
            input_bundle = build_evolver_input_bundle(
                candidate_root,
                evidence_root,
                evolver_root,
                pending_input_path,
                forbidden_values=known_secrets,
                max_files=self.config.max_input_files,
                max_bytes=self.config.max_input_bytes,
            )
            trusted_regular_path(
                input_bundle.path,
                phase="evolver.input",
                contained_by=evolution_dir,
            )
            _verify_bundled_evidence(input_bundle.path, evidence_record)
        except SandboxInfrastructureError:
            if pending_input_path.exists():
                pending_input_path.unlink()
            raise
        except BundleError as exc:
            if pending_input_path.exists():
                pending_input_path.unlink()
            raise SandboxInfrastructureError(
                "evolver.input", f"{type(exc).__name__}: {exc}"
            ) from exc
        spec = SandboxSpec(
            role="evolver",
            run_id=run_id,
            attempt_id=attempt_id,
            task_id=_TASK_ID,
            image_ref=self.config.image_ref,
            cpu_count=self.config.resource_contract.cpu_count,
            memory_mb=self.config.resource_contract.memory_mb,
            pids_limit=self.config.resource_contract.pids_limit,
            timeout_seconds=self.config.resource_contract.timeout_seconds,
            network_policy="worker-proxy-only",
            environment=environment,
            writable_tmpfs_mb=self.config.resource_contract.writable_tmpfs_mb,
            network_scope=attempt_id,
        )
        backend_name = str(getattr(self.backend, "backend_name", ""))
        if not backend_name:
            raise SandboxInfrastructureError(
                "evolver.config", "sandbox backend has no stable name"
            )
        (
            proxy_image_ref,
            proxy_spec_sha256,
            proxy_config_sha256,
        ) = _proxy_identity(
            self.proxy_manager,
            run_id=run_id,
            attempt_id=attempt_id,
        )
        attempt_identity = _attempt_identity(
            run_id=run_id,
            iteration=iteration,
            input_bundle_sha256=input_bundle.sha256,
            diagnosis_sha256=diagnosis_sha256,
            model_name=self.model_name,
            image_ref=self.config.image_ref,
            spec_sha256=spec.spec_sha256,
            proxy_image_ref=proxy_image_ref,
            proxy_spec_sha256=proxy_spec_sha256,
            proxy_config_sha256=proxy_config_sha256,
            backend=backend_name,
        )
        lifecycle_path = (
            self.lifecycle_root
            / run_id
            / attempt_id
            / "evolver-sandbox-lifecycle-v2.json"
        )
        trusted_directory(
            lifecycle_path.parent,
            create=True,
            phase="evolver.lifecycle",
            contained_by=self.lifecycle_root,
        )
        trusted_regular_path(
            lifecycle_path,
            phase="evolver.lifecycle",
            contained_by=self.lifecycle_root,
            allow_missing=True,
        )
        paths = _result_paths(
            evolution_dir, lifecycle_path, proxy_lifecycle_path
        )
        expected_identity = {
            "run_id": run_id,
            "iteration": iteration,
            "input_bundle_sha256": input_bundle.sha256,
            "diagnosis_sha256": diagnosis_sha256,
            "model_name": self.model_name,
            "image_ref": self.config.image_ref,
            "spec_sha256": spec.spec_sha256,
            "proxy_image_ref": proxy_image_ref,
            "proxy_spec_sha256": proxy_spec_sha256,
            "proxy_config_sha256": proxy_config_sha256,
            "backend": backend_name,
            "attempt_identity_sha256": attempt_identity,
        }
        try:
            completed = _load_completed(
                evolution_dir, expected_identity=expected_identity, paths=paths
            )
        except BaseException:
            if pending_input_path.exists():
                pending_input_path.unlink()
            raise
        if completed is not None:
            pending_input_path.unlink()
            return completed

        if quarantine_path.exists() or quarantine_path.is_symlink():
            pending_input_path.unlink()
            raise SandboxInfrastructureError(
                "evolver.resume",
                "quarantined model request identity must not reopen a sandbox",
            )
        if lifecycle_path.exists() or lifecycle_path.is_symlink():
            try:
                lifecycle = load_lifecycle(lifecycle_path)
            except BaseException:
                pending_input_path.unlink()
                raise
            if not lifecycle.cleaned_up:
                pending_input_path.unlink()
                raise SandboxInfrastructureError(
                    "evolver.resume",
                    "unfinished evolver sandbox requires exact-ID cleanup",
                )
            pending_input_path.unlink()
            raise SandboxInfrastructureError(
                "evolver.resume",
                "stale cleaned lifecycle without a completed result is ambiguous",
            )

        for name, path in paths.items():
            if name == "lifecycle_uri":
                continue
            trusted_regular_path(
                path,
                phase="evolver.resume",
                allow_missing=True,
            )
            if path.exists():
                pending_input_path.unlink()
                raise SandboxInfrastructureError(
                    "evolver.resume",
                    f"stale result evidence is ambiguous: {path.name}",
                )

        output_dir = evolution_dir / "candidate"
        try:
            output_metadata = output_dir.lstat()
        except FileNotFoundError:
            output_metadata = None
        if output_metadata is not None:
            pending_input_path.unlink()
            if stat.S_ISLNK(output_metadata.st_mode):
                raise SandboxInfrastructureError(
                    "evolver.resume", "candidate output symlink is forbidden"
                )
            raise SandboxInfrastructureError(
                "evolver.resume",
                "uncommitted candidate output makes the request identity ambiguous",
            )

        committed_input_path = evolution_dir / "input.tar"
        trusted_regular_path(
            committed_input_path,
            phase="evolver.resume",
            contained_by=evolution_dir,
            allow_missing=True,
        )
        if committed_input_path.exists():
            pending_input_path.unlink()
            raise SandboxInfrastructureError(
                "evolver.resume", "stale committed input archive is ambiguous"
            )
        os.replace(pending_input_path, committed_input_path)
        input_bundle = replace(input_bundle, path=committed_input_path)
        dependency_lock = b""
        session = None
        handle = None
        primary_error: BaseException | None = None
        finished = False

        request = _combined_request(
            self.config.resource_contract, self.proxy_resources
        )
        lease = self.resource_pool.acquire(
            f"evolver:{run_id}:{iteration}",
            request,
            timeout_seconds=self.config.lease_timeout_seconds,
        )
        with lease:
            with self.proxy_manager.open(
                run_id=run_id,
                attempt_id=attempt_id,
                task_id=_TASK_ID,
                caller_role="evolver",
                run_dir=run_root,
            ) as opened_session:
                session = opened_session
                if (
                    session.network_scope != attempt_id
                    or session.base_url != environment["LLM_BASE_URL"]
                    or session.allowed_model != self.model_name
                ):
                    raise SandboxInfrastructureError(
                        "evolver.proxy", "proxy session identity differs from evolver spec"
                    )
                _validate_executed_proxy_session(
                    session,
                    lifecycle_path=proxy_lifecycle_path,
                    run_root=run_root,
                    run_id=run_id,
                    attempt_id=attempt_id,
                    expected_image_ref=proxy_image_ref,
                    expected_spec_sha256=proxy_spec_sha256,
                    require_cleaned=False,
                )
                try:
                    handle = backend_call(
                        "evolver.create", lambda: self.backend.create(spec)
                    )
                    backend_call(
                        "evolver.lifecycle",
                        lambda: create_lifecycle(
                            lifecycle_path,
                            handle=handle,
                            spec=spec,
                            attempt_identity_sha256=attempt_identity,
                            at=self.clock(),
                        ),
                    )
                    backend_call(
                        "evolver.start", lambda: self.backend.start(handle)
                    )
                    backend_call(
                        "evolver.lifecycle",
                        lambda: mark_started(lifecycle_path, at=self.clock()),
                    )
                    dependency_lock = read_bounded(
                        self.backend,
                        handle,
                        NEXAU_REQUIREMENTS_LOCK,
                        max_bytes=_DEPENDENCY_LOCK_LIMIT,
                        timeout_seconds=min(
                            120, self.config.resource_contract.timeout_seconds
                        ),
                        phase="evolver.dependency",
                    )
                    if (
                        not isinstance(dependency_lock, bytes)
                        or not dependency_lock.strip()
                    ):
                        raise SandboxInfrastructureError(
                            "evolver.dependency",
                            "NexAU dependency lock is missing or empty",
                        )
                    if any(
                        value.encode() in dependency_lock
                        for value in known_secrets
                        if value
                    ):
                        raise SandboxInfrastructureError(
                            "evolver.dependency",
                            "dependency lock contains a forbidden credential value",
                        )
                    atomic_bytes(
                        paths["dependency_lock_uri"],
                        dependency_lock,
                        phase="evolver.result",
                    )
                    for remote_path, payload in (
                        ("/qea/evolver-input.tar", input_bundle.path.read_bytes()),
                        ("/qea/remote_evolver.py", _REMOTE_RUNNER.read_bytes()),
                        ("/qea/runtime_bridge.py", _RUNTIME_BRIDGE.read_bytes()),
                        ("/qea/diagnosis.txt", diagnosis_payload),
                    ):
                        backend_call(
                            "evolver.upload",
                            lambda remote_path=remote_path, payload=payload: (
                                self.backend.put_bytes(handle, remote_path, payload)
                            ),
                        )
                    setup_timeout = min(
                        120, self.config.resource_contract.timeout_seconds
                    )
                    for argv in (
                        ("mkdir", "-p", "/qea/input", "/qea/result"),
                        (
                            "tar",
                            "-xf",
                            "/qea/evolver-input.tar",
                            "-C",
                            "/qea/input",
                        ),
                        (
                            "chmod",
                            "-R",
                            "a-w",
                            "/qea/input/evidence",
                            "/qea/input/evolve_agent",
                        ),
                        (
                            "chmod",
                            "-R",
                            "u+w",
                            "/qea/input/candidate",
                            "/qea/result",
                        ),
                    ):
                        run_required(
                            self.backend,
                            handle,
                            argv,
                            environment={},
                            timeout_seconds=setup_timeout,
                            phase="evolver.setup",
                        )
                    command = (
                        NEXAU_RUNTIME_PYTHON,
                        "/qea/remote_evolver.py",
                        "--candidate-dir",
                        "/qea/input/candidate",
                        "--evidence-dir",
                        "/qea/input/evidence",
                        "--evolver-dir",
                        "/qea/input/evolve_agent",
                        "--result-dir",
                        "/qea/result",
                        "--diagnosis-file",
                        "/qea/diagnosis.txt",
                        "--iteration",
                        str(iteration),
                    )
                    command_result = backend_call(
                        "evolver.command",
                        lambda: self.backend.run(
                            handle,
                            command,
                            environment=environment,
                            timeout_seconds=self.config.command_timeout_seconds,
                        ),
                    )
                    if not isinstance(command_result, SandboxCommandResult):
                        raise SandboxInfrastructureError(
                            "evolver.command", "backend returned an invalid result"
                        )
                    write_command_log(
                        paths["command_log_uri"],
                        command_result,
                        forbidden_values=known_secrets,
                    )
                    if command_result.timed_out:
                        raise SandboxInfrastructureError(
                            "evolver.command", "evolver command timed out"
                        )
                    if command_result.exit_code != 0:
                        error_detail = _redact_text(
                            command_result.stderr or command_result.stdout,
                            set(known_secrets),
                        )
                        raise SandboxInfrastructureError(
                            "evolver.command",
                            f"evolver command exited {command_result.exit_code}: "
                            f"{error_detail}",
                        )
                    archive = read_bounded(
                        self.backend,
                        handle,
                        "/qea/result/candidate.tar",
                        max_bytes=_candidate_archive_limit(self.config),
                        timeout_seconds=min(
                            120, self.config.resource_contract.timeout_seconds
                        ),
                        phase="evolver.download",
                    )
                    if any(
                        value.encode() in archive
                        for value in known_secrets
                        if value
                    ):
                        raise SandboxInfrastructureError(
                            "evolver.download",
                            "candidate archive contains a forbidden credential value",
                        )
                    try:
                        extract_candidate_archive(
                            archive,
                            output_dir,
                            max_files=self.config.max_candidate_files,
                            max_bytes=self.config.max_candidate_bytes,
                        )
                    except BundleError as exc:
                        raise SandboxInfrastructureError(
                            "evolver.candidate", f"{type(exc).__name__}: {exc}"
                        ) from exc
                    for remote_name, path_key in (
                        ("raw_trace.jsonl", "trace_uri"),
                        ("final.txt", "final_uri"),
                        ("prediction.json", "prediction_uri"),
                        ("access-summary.json", "access_summary_uri"),
                        ("summary.json", "summary_uri"),
                    ):
                        payload = read_bounded(
                            self.backend,
                            handle,
                            f"/qea/result/{remote_name}",
                            max_bytes=_DOWNLOAD_LIMITS[remote_name],
                            timeout_seconds=min(
                                120,
                                self.config.resource_contract.timeout_seconds,
                            ),
                            phase="evolver.download",
                        )
                        atomic_bytes(
                            paths[path_key],
                            _validate_evidence(
                                remote_name,
                                payload,
                                forbidden_values=known_secrets,
                            ),
                            phase="evolver.result",
                        )
                    mark_finished(lifecycle_path, at=self.clock())
                    finished = True
                except SandboxInfrastructureError as exc:
                    primary_error = exc
                except Exception as exc:  # noqa: BLE001 - typed final boundary.
                    primary_error = SandboxInfrastructureError(
                        "evolver.coordinator", f"{type(exc).__name__}: {exc}"
                    )
                finally:
                    finish_and_cleanup(
                        backend=self.backend,
                        handle=handle,
                        lifecycle_path=lifecycle_path if handle is not None else None,
                        clock=self.clock,
                        role="evolver",
                        primary_error=primary_error,
                        finished=finished,
                        forbidden_values=known_secrets,
                    )
                if primary_error is not None:
                    raise primary_error

            if session is None or handle is None:
                raise SandboxInfrastructureError(
                    "evolver.coordinator", "sandbox identities were not recorded"
                )
            _validate_executed_proxy_session(
                session,
                lifecycle_path=proxy_lifecycle_path,
                run_root=run_root,
                run_id=run_id,
                attempt_id=attempt_id,
                expected_image_ref=proxy_image_ref,
                expected_spec_sha256=proxy_spec_sha256,
                require_cleaned=True,
            )
            lifecycle = load_lifecycle(lifecycle_path)
            if not lifecycle.cleaned_up:
                raise SandboxInfrastructureError(
                    "evolver.cleanup", "evolver lifecycle is not exactly cleaned"
                )
            candidate_digest = _digest_tree(output_dir)
            result = SandboxEvolverResult(
                iteration=iteration,
                candidate_dir=output_dir,
                candidate_digest=candidate_digest,
                input_bundle_sha256=input_bundle.sha256,
                trace_uri=paths["trace_uri"],
                final_uri=paths["final_uri"],
                prediction_uri=paths["prediction_uri"],
                access_summary_uri=paths["access_summary_uri"],
                summary_uri=paths["summary_uri"],
                command_log_uri=paths["command_log_uri"],
                lifecycle_uri=lifecycle_path,
                proxy_lifecycle_uri=proxy_lifecycle_path,
                dependency_lock_uri=paths["dependency_lock_uri"],
                sandbox_id=handle.native_id,
                proxy_sandbox_id=session.native_id,
                network_id=session.network_id,
                cleaned_up=True,
                backend=handle.backend,
                spec_sha256=handle.spec_sha256,
                executed_proxy_image_ref=session.immutable_image_ref,
                executed_proxy_spec_sha256=session.spec_sha256,
                executed_proxy_public_plan_sha256=(
                    session.public_plan_sha256
                ),
                executed_proxy_config_sha256=(
                    session.public_config_sha256
                ),
                executed_proxy_attempt_identity_sha256=(
                    session.attempt_identity_sha256
                ),
            )
            file_digests = {
                name: _sha256(path.read_bytes()) for name, path in paths.items()
            }
            atomic_json(
                evolution_dir / "result.json",
                {
                    "schema_version": 1,
                    **expected_identity,
                    "attempt_id": attempt_id,
                    "candidate_dir": "candidate",
                    "candidate_digest": candidate_digest,
                    "sandbox_id": result.sandbox_id,
                    "proxy_sandbox_id": result.proxy_sandbox_id,
                    "network_id": result.network_id,
                    "executed_proxy_image_ref": (
                        result.executed_proxy_image_ref
                    ),
                    "executed_proxy_spec_sha256": (
                        result.executed_proxy_spec_sha256
                    ),
                    "executed_proxy_public_plan_sha256": (
                        result.executed_proxy_public_plan_sha256
                    ),
                    "executed_proxy_config_sha256": (
                        result.executed_proxy_config_sha256
                    ),
                    "executed_proxy_attempt_identity_sha256": (
                        result.executed_proxy_attempt_identity_sha256
                    ),
                    "cleaned_up": True,
                    "file_sha256": file_digests,
                },
            )
            return result


__all__ = [
    "SandboxEvolverConfig",
    "SandboxEvolverResult",
    "SandboxFullHarnessProposer",
]
