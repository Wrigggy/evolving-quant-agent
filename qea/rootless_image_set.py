"""Explicit, content-addressed indexes for rootless full-harness images."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .rootless_images import (
    RootlessImageError,
    rootless_image_result_identity_sha256,
)


_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IMAGE_DIGEST = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}\Z"
)
_TASK_ID = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
_ROLES = frozenset({"base", "proxy", "evolver", "worker", "verifier"})
_NEUTRAL_ROLES = ("base", "proxy", "evolver")
_PLAN_IDENTITY_KEYS = (
    "role",
    "task_id",
    "benchmark_commit",
    "base_image_ref",
    "source_manifest_sha256",
    "verifier_test_script_sha256",
    "context_files",
    "cpu_count",
    "memory_mb",
    "build_timeout_seconds",
    "build_network",
)


class RootlessImageSetError(RuntimeError):
    """An image manifest or image-set index is mutable or inconsistent."""


def _canonical_json(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _regular_leaf_path(path: str | Path, *, label: str) -> Path:
    unresolved = Path(path).expanduser()
    if unresolved.is_symlink() or not unresolved.is_file():
        raise RootlessImageSetError(
            f"{label} must be a regular non-symlink file: {unresolved}"
        )
    return unresolved.resolve()


def _json_file(
    path: str | Path,
    *,
    label: str,
) -> tuple[Path, bytes, Mapping[str, object]]:
    resolved = _regular_leaf_path(path, label=label)
    try:
        raw = resolved.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise RootlessImageSetError(f"cannot load {label} {resolved}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RootlessImageSetError(
            f"{label} must contain one JSON object: {resolved}"
        )
    return resolved, raw, payload


def _immutable_image(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not (
        _IMAGE_ID.fullmatch(value) or _IMAGE_DIGEST.fullmatch(value)
    ):
        raise RootlessImageSetError(f"{label} must be an immutable image reference")
    return value


def _digest(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise RootlessImageSetError(f"{label} must be a SHA-256 digest")
    return value


def _positive_integer(value: object, *, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise RootlessImageSetError(f"{label} must be a positive integer")
    return value


def _task_panel(task_ids: Iterable[str]) -> tuple[str, ...]:
    values = tuple(task_ids)
    if not values:
        raise RootlessImageSetError("task panel must not be empty")
    if any(not isinstance(value, str) or _TASK_ID.fullmatch(value) is None for value in values):
        raise RootlessImageSetError("task panel contains an invalid task ID")
    if len(set(values)) != len(values):
        raise RootlessImageSetError("task panel contains a duplicate task ID")
    return tuple(sorted(values))


def _manifest_entry(
    manifest_path: str | Path,
    *,
    benchmark_commit: str,
) -> dict[str, object]:
    path, raw, manifest = _json_file(manifest_path, label="image manifest")
    if manifest.get("schema_version") != 1:
        raise RootlessImageSetError(f"image manifest schema is unsupported: {path}")
    role = manifest.get("role")
    if role not in _ROLES:
        raise RootlessImageSetError(f"image manifest role is invalid: {path}")
    task_id = manifest.get("task_id")
    if role in _NEUTRAL_ROLES:
        if task_id is not None:
            raise RootlessImageSetError(f"task-neutral {role} manifest names a task")
    elif not isinstance(task_id, str) or _TASK_ID.fullmatch(task_id) is None:
        raise RootlessImageSetError(f"task image manifest has an invalid task ID: {path}")
    if manifest.get("benchmark_commit") != benchmark_commit:
        raise RootlessImageSetError(f"image manifest benchmark commit differs: {path}")
    verifier_test_script_sha256 = manifest.get("verifier_test_script_sha256")
    if role == "verifier":
        verifier_test_script_sha256 = _digest(
            verifier_test_script_sha256,
            label="verifier test script identity",
        )
    elif verifier_test_script_sha256 is not None:
        raise RootlessImageSetError(
            f"verifier test script identity must be null for {role}: {path}"
        )

    image_id = _immutable_image(manifest.get("image_id"), label="image ID")
    base_image_ref = _immutable_image(
        manifest.get("base_image_ref"), label="base image reference"
    )
    source_manifest_sha256 = _digest(
        manifest.get("source_manifest_sha256"),
        label="source manifest identity",
    )
    dependency_lock_sha256 = _digest(
        manifest.get("dependency_lock_sha256"),
        label="dependency lock identity",
    )
    plan_identity = _digest(
        manifest.get("plan_identity_sha256"), label="image plan identity"
    )
    result_identity = _digest(
        manifest.get("result_identity_sha256"), label="image result identity"
    )
    compatibility_identity = _digest(
        manifest.get("identity_sha256"), label="image compatibility identity"
    )
    if manifest.get("identity_kind") != "measured-result":
        raise RootlessImageSetError(f"image identity kind is invalid: {path}")
    context_files = manifest.get("context_files")
    if not isinstance(context_files, list) or not context_files:
        raise RootlessImageSetError(f"image manifest context is empty: {path}")
    dockerfile_sha256 = _digest(
        manifest.get("dockerfile_sha256"), label="Dockerfile identity"
    )
    dockerfiles = [
        item
        for item in context_files
        if isinstance(item, dict) and item.get("path") == "Dockerfile"
    ]
    if len(dockerfiles) != 1 or dockerfiles[0].get("sha256") != dockerfile_sha256:
        raise RootlessImageSetError(f"Dockerfile context identity differs: {path}")

    try:
        plan_identity_payload = {key: manifest[key] for key in _PLAN_IDENTITY_KEYS}
    except KeyError as exc:
        raise RootlessImageSetError(
            f"image manifest omits plan identity field {exc.args[0]!r}: {path}"
        ) from exc
    if _sha256(_canonical_json(plan_identity_payload)) != plan_identity:
        raise RootlessImageSetError(f"image plan identity differs: {path}")

    docker_version = manifest.get("docker_version")
    security_options = manifest.get("docker_security_options")
    try:
        recomputed_result_identity = rootless_image_result_identity_sha256(
            plan_identity_sha256=plan_identity,
            image_id=image_id,
            dependency_lock_sha256=dependency_lock_sha256,
            docker_version=docker_version,
            docker_security_options=security_options,
        )
    except RootlessImageError as exc:
        raise RootlessImageSetError(f"image result identity is invalid: {path}") from exc
    if (
        recomputed_result_identity != result_identity
        or compatibility_identity != result_identity
    ):
        raise RootlessImageSetError(f"image result identity differs: {path}")
    if path.parent.name != result_identity:
        raise RootlessImageSetError(
            f"image manifest publication path is not result-addressed: {path}"
        )

    lock_path = path.with_name("dependency-lock.txt")
    if lock_path.is_symlink() or not lock_path.is_file():
        raise RootlessImageSetError(f"dependency lock is missing beside {path}")
    try:
        lock_bytes = lock_path.read_bytes()
    except OSError as exc:
        raise RootlessImageSetError(f"cannot read dependency lock beside {path}") from exc
    if _sha256(lock_bytes) != dependency_lock_sha256:
        raise RootlessImageSetError(f"dependency lock hash differs beside {path}")

    resource_contract = {
        "cpu_count": _positive_integer(manifest.get("cpu_count"), label="cpu_count"),
        "memory_mb": _positive_integer(manifest.get("memory_mb"), label="memory_mb"),
        "build_timeout_seconds": _positive_integer(
            manifest.get("build_timeout_seconds"), label="build_timeout_seconds"
        ),
        "build_network": manifest.get("build_network"),
    }
    if not isinstance(resource_contract["build_network"], str) or not resource_contract[
        "build_network"
    ]:
        raise RootlessImageSetError("build_network must be a non-empty string")
    resource_contract_sha256 = _sha256(_canonical_json(resource_contract))

    if not isinstance(docker_version, str) or not docker_version:
        raise RootlessImageSetError(f"Docker version identity is missing: {path}")
    if (
        not isinstance(security_options, list)
        or not all(isinstance(value, str) for value in security_options)
        or "name=rootless" not in security_options
    ):
        raise RootlessImageSetError(f"Docker rootless identity is missing: {path}")
    docker_identity = {
        "version": docker_version,
        "security_options": security_options,
    }

    return {
        "role": role,
        "task_id": task_id,
        "manifest_path": str(path),
        "manifest_sha256": _sha256(raw),
        "manifest_identity_sha256": result_identity,
        "plan_identity_sha256": plan_identity,
        "result_identity_sha256": result_identity,
        "source_manifest_sha256": source_manifest_sha256,
        "verifier_test_script_sha256": verifier_test_script_sha256,
        "base_image_ref": base_image_ref,
        "image_id": image_id,
        "dependency_lock_sha256": dependency_lock_sha256,
        "resource_contract": resource_contract,
        "resource_contract_sha256": resource_contract_sha256,
        "docker_identity": docker_identity,
        "docker_identity_sha256": _sha256(_canonical_json(docker_identity)),
    }


@dataclass(frozen=True)
class RootlessImageSet:
    """One immutable full-harness image selection for an exact task panel."""

    benchmark_commit: str
    task_ids: tuple[str, ...]
    base: Mapping[str, object]
    proxy: Mapping[str, object]
    evolver: Mapping[str, object]
    tasks: tuple[Mapping[str, object], ...]
    identity_sha256: str

    @classmethod
    def from_manifest_paths(
        cls,
        *,
        benchmark_commit: str,
        task_ids: Iterable[str],
        manifest_paths: Iterable[str | Path],
    ) -> "RootlessImageSet":
        """Assemble an exact image set from explicitly supplied manifests."""

        if not isinstance(benchmark_commit, str) or _COMMIT.fullmatch(
            benchmark_commit
        ) is None:
            raise RootlessImageSetError("benchmark commit must be a full SHA")
        panel = _task_panel(task_ids)
        paths = tuple(manifest_paths)
        if not paths:
            raise RootlessImageSetError("explicit image manifest paths are required")
        entries = [
            _manifest_entry(path, benchmark_commit=benchmark_commit) for path in paths
        ]

        neutral: dict[str, list[dict[str, object]]] = {
            role: [] for role in _NEUTRAL_ROLES
        }
        task_entries: dict[str, dict[str, list[dict[str, object]]]] = {}
        for entry in entries:
            role = str(entry["role"])
            if role in neutral:
                neutral[role].append(entry)
                continue
            task_id = str(entry["task_id"])
            task_entries.setdefault(task_id, {"worker": [], "verifier": []})[
                role
            ].append(entry)

        for role, matches in neutral.items():
            if len(matches) != 1:
                raise RootlessImageSetError(
                    f"image set requires exactly one {role} manifest, found {len(matches)}"
                )
        if tuple(sorted(task_entries)) != panel:
            raise RootlessImageSetError(
                "image manifest task panel differs from the requested task panel"
            )
        tasks: list[dict[str, object]] = []
        for task_id in panel:
            pair = task_entries[task_id]
            for role in ("worker", "verifier"):
                if len(pair[role]) != 1:
                    raise RootlessImageSetError(
                        f"task {task_id!r} requires exactly one {role} manifest"
                    )
            worker = pair["worker"][0]
            verifier = pair["verifier"][0]
            tasks.append(
                {"task_id": task_id, "worker": worker, "verifier": verifier}
            )

        base = neutral["base"][0]
        for entry in (
            neutral["proxy"][0],
            neutral["evolver"][0],
            *(role for task in tasks for role in (task["worker"], task["verifier"])),
        ):
            if entry["base_image_ref"] != base["image_id"]:
                raise RootlessImageSetError(
                    f"{entry['role']} manifest does not derive from the selected base image"
                )

        unsigned = {
            "schema_version": 1,
            "benchmark_commit": benchmark_commit,
            "task_ids": list(panel),
            "base": base,
            "proxy": neutral["proxy"][0],
            "evolver": neutral["evolver"][0],
            "tasks": tasks,
        }
        identity = _sha256(_canonical_json(unsigned))
        return cls(
            benchmark_commit=benchmark_commit,
            task_ids=panel,
            base=base,
            proxy=neutral["proxy"][0],
            evolver=neutral["evolver"][0],
            tasks=tuple(tasks),
            identity_sha256=identity,
        )

    def to_payload(self) -> dict[str, object]:
        """Return the canonical JSON-compatible image-set payload."""

        return {
            "schema_version": 1,
            "benchmark_commit": self.benchmark_commit,
            "task_ids": list(self.task_ids),
            "base": dict(self.base),
            "proxy": dict(self.proxy),
            "evolver": dict(self.evolver),
            "tasks": [dict(task) for task in self.tasks],
            "identity_sha256": self.identity_sha256,
        }

    def write(self, path: str | Path) -> Path:
        """Atomically publish the index without replacing another identity."""

        unresolved = Path(path).expanduser()
        if unresolved.is_symlink():
            raise RootlessImageSetError(
                f"image-set output symlink is forbidden: {unresolved}"
            )
        destination = unresolved.resolve()
        payload = json.dumps(self.to_payload(), sort_keys=True, indent=2) + "\n"
        encoded = payload.encode()
        if destination.exists():
            if not destination.is_file() or destination.read_bytes() != encoded:
                raise RootlessImageSetError(
                    f"refusing to replace immutable image-set index: {destination}"
                )
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".partial")
        if temporary.exists() or temporary.is_symlink():
            raise RootlessImageSetError(f"existing partial image-set index: {temporary}")
        temporary.write_bytes(encoded)
        os.replace(temporary, destination)
        return destination

    @classmethod
    def load(cls, path: str | Path) -> "RootlessImageSet":
        """Load an index and revalidate its identity and referenced manifests."""

        _, _, payload = _json_file(path, label="image-set index")
        if payload.get("schema_version") != 1:
            raise RootlessImageSetError("image-set schema is unsupported")
        identity = payload.get("identity_sha256")
        if not isinstance(identity, str) or _SHA256.fullmatch(identity) is None:
            raise RootlessImageSetError("image-set top-level identity is invalid")
        unsigned = dict(payload)
        unsigned.pop("identity_sha256", None)
        if _sha256(_canonical_json(unsigned)) != identity:
            raise RootlessImageSetError("image-set top-level identity differs")
        task_ids = payload.get("task_ids")
        if not isinstance(task_ids, list):
            raise RootlessImageSetError("image-set task panel is invalid")
        try:
            manifest_paths = [
                payload[role]["manifest_path"] for role in _NEUTRAL_ROLES
            ]
            tasks = payload["tasks"]
            if not isinstance(tasks, list):
                raise TypeError
            manifest_paths.extend(
                task[role]["manifest_path"]
                for task in tasks
                for role in ("worker", "verifier")
            )
        except (KeyError, TypeError) as exc:
            raise RootlessImageSetError("image-set manifest references are invalid") from exc
        try:
            rebuilt = cls.from_manifest_paths(
                benchmark_commit=payload.get("benchmark_commit"),
                task_ids=task_ids,
                manifest_paths=manifest_paths,
            )
        except RootlessImageSetError as exc:
            raise RootlessImageSetError(
                f"referenced manifest validation failed: {exc}"
            ) from exc
        if rebuilt.to_payload() != payload:
            raise RootlessImageSetError("referenced manifest identities differ from index")
        return rebuilt
