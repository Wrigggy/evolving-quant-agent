"""Materialize an exact, model-bound runtime profile for the QEA evolver.

The repository evolver definition is deliberately model-neutral. A run binds
its exact model/provider route in the self-hosted rootless configuration and
uses this module to add only the deliberation request supported by that route.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


_ROUTE_VALUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_REASONING_EFFORTS = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh"}
)
_PROFILE_FILE = ".qea-runtime-profile.json"
_REASONING_ANCHOR = "  timeout: 180\n"


@dataclass(frozen=True)
class EvolverRuntimeProfile:
    """Auditable identity of one materialized evolver runtime."""

    schema_version: int
    model: str
    provider: str
    reasoning_effort: str
    source_sha256: str
    materialized_sha256: str
    materialized_dir: str


def _ignored(relative: Path) -> bool:
    return (
        "__pycache__" in relative.parts
        or relative.suffix == ".pyc"
        or relative.name == ".DS_Store"
    )


def _tree_digest(root: Path) -> str:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"evolver directory is unavailable: {root}")
    digest = hashlib.sha256()
    for path in sorted(
        root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
    ):
        relative = path.relative_to(root)
        if _ignored(relative):
            continue
        if path.is_symlink():
            raise ValueError(f"evolver profile contains a symlink: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(
                f"evolver profile entry is not a regular file: {relative}"
            )
        encoded = relative.as_posix().encode("utf-8")
        payload = path.read_bytes()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _validate_route(value: str, *, label: str) -> str:
    if not isinstance(value, str) or _ROUTE_VALUE.fullmatch(value) is None:
        raise ValueError(f"{label} route is unsafe")
    return value


def _copy_source(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        symlinks=False,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )


def _prepare_materialized_copy(root: Path) -> Path:
    """Normalize only the private run-root copy to owner-only writable modes."""

    paths = (root, *root.rglob("*"))
    for path in paths:
        if path.is_symlink():
            raise ValueError("materialized evolver profile contains a symlink")
        if path.is_dir():
            path.chmod(0o700)
        elif path.is_file():
            owner_executable = bool(path.stat().st_mode & stat.S_IXUSR)
            path.chmod(0o700 if owner_executable else 0o600)
        else:
            raise ValueError("materialized evolver profile entry is not regular")
    agent_path = root / "agent.yaml"
    if not agent_path.is_file():
        raise ValueError("source evolver has no agent.yaml")
    return agent_path


def _configure_reasoning(agent_path: Path, effort: str) -> None:
    text = agent_path.read_text(encoding="utf-8")
    if text.count("  model: ${env.LLM_MODEL}\n") != 1:
        raise ValueError("source agent.yaml must use the runtime-selected model")
    if "  extra_body:\n" in text or "    reasoning:\n" in text:
        raise ValueError("source agent.yaml must be model-neutral")
    if text.count(_REASONING_ANCHOR) != 1:
        raise ValueError("source agent.yaml has no unique deliberation insertion point")
    if effort == "none":
        return
    block = (
        _REASONING_ANCHOR
        + "  extra_body:\n"
        + "    reasoning:\n"
        + f"      effort: {effort}\n"
        + "      exclude: true\n"
    )
    agent_path.write_text(text.replace(_REASONING_ANCHOR, block), encoding="utf-8")


def materialize_evolver_profile(
    source: str | Path,
    destination: str | Path,
    *,
    model: str,
    provider: str,
    reasoning_effort: str,
) -> EvolverRuntimeProfile:
    """Copy a neutral evolver and bind one exact self-hosted runtime profile.

    Repeating the call is allowed only when it produces byte-identical output.
    This supports coordinator resume without silently changing the model route.
    """

    source_path = Path(source).expanduser().resolve(strict=True)
    destination_path = Path(destination).expanduser().resolve()
    model = _validate_route(model, label="model")
    provider = _validate_route(provider, label="provider")
    if reasoning_effort not in _REASONING_EFFORTS:
        raise ValueError(
            "reasoning_effort must be one of " + ", ".join(sorted(_REASONING_EFFORTS))
        )
    if destination_path == source_path or source_path in destination_path.parents:
        raise ValueError("materialized evolver must be outside its source directory")

    source_sha256 = _tree_digest(source_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_parent = Path(
        tempfile.mkdtemp(prefix=".qea-evolver-profile-", dir=destination_path.parent)
    )
    temporary = temporary_parent / "evolver"
    try:
        _copy_source(source_path, temporary)
        agent_path = _prepare_materialized_copy(temporary)
        _configure_reasoning(agent_path, reasoning_effort)
        profile_payload = {
            "schema_version": 1,
            "model": model,
            "provider": provider,
            "reasoning_effort": reasoning_effort,
            "source_sha256": source_sha256,
        }
        profile_path = temporary / _PROFILE_FILE
        profile_path.write_text(
            json.dumps(profile_payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        profile_path.chmod(0o600)
        materialized_sha256 = _tree_digest(temporary)
        if destination_path.exists():
            if _tree_digest(destination_path) != materialized_sha256:
                raise ValueError("persisted evolver runtime profile differs")
        else:
            temporary.rename(destination_path)
        return EvolverRuntimeProfile(
            **profile_payload,
            materialized_sha256=materialized_sha256,
            materialized_dir=str(destination_path),
        )
    finally:
        shutil.rmtree(temporary_parent, ignore_errors=True)


def profile_as_dict(profile: EvolverRuntimeProfile) -> dict[str, object]:
    """Return the stable JSON form recorded in run plans."""

    return asdict(profile)
