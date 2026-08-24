"""Materialize one externally authored Worker as a frozen QRS base harness.

The adapter validates a small, public Worker contract and copies the Worker to
one run-scoped directory.  It deliberately does not select a harness, execute a
Worker, call an Evolver, or inspect benchmark outcomes.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml


SIX_QUANT_STATES = ("S1", "S2", "S3", "S4", "S5", "S6")
SHELL_TOOL_NAME = "run_shell_command"
STATE_TOOL_NAME = "record_quant_state"
SHELL_TOOL_BINDING = (
    "nexau.archs.tool.builtin.shell_tools.run_shell_command:run_shell_command"
)
STATE_TOOL_BINDING = "tools.quant_state_telemetry:record_quant_state"
_PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_UNRESOLVED_RUNTIME_TOKENS = ("${", "env.", "changeme", "<replace")


class FrozenBaseHarnessError(ValueError):
    """The proposed frozen base harness does not satisfy the adapter contract."""


def _read_yaml(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise FrozenBaseHarnessError(f"cannot read {label}: {path}") from exc
    except yaml.YAMLError as exc:
        raise FrozenBaseHarnessError(f"cannot parse {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FrozenBaseHarnessError(f"{label} must decode to a YAML object: {path}")
    return payload


def _declared_path(root: Path, value: object, *, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise FrozenBaseHarnessError(f"{label} must be a non-empty relative path")
    relative = Path(value.strip())
    if relative.is_absolute():
        raise FrozenBaseHarnessError(f"{label} must stay inside the Worker directory")
    root_resolved = root.resolve()
    resolved = (root_resolved / relative).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise FrozenBaseHarnessError(
            f"{label} escapes the Worker directory: {value!r}"
        ) from exc
    return resolved


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _nonempty_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        raise FrozenBaseHarnessError(f"{label} does not exist: {path}")
    if not path.read_text(encoding="utf-8").strip():
        raise FrozenBaseHarnessError(f"{label} is empty: {path}")


def _tool_map(agent: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    values = agent.get("tools")
    if not isinstance(values, list):
        raise FrozenBaseHarnessError("agent.yaml must declare a tools list")
    tools: dict[str, Mapping[str, object]] = {}
    for value in values:
        if not isinstance(value, Mapping):
            raise FrozenBaseHarnessError("every agent.yaml tool entry must be an object")
        name = value.get("name")
        if not isinstance(name, str) or not name:
            raise FrozenBaseHarnessError("every agent.yaml tool needs a concrete name")
        if name in tools:
            raise FrozenBaseHarnessError(f"duplicate tool declaration: {name}")
        tools[name] = value
    return tools


def _validate_tool(
    root: Path,
    tools: Mapping[str, Mapping[str, object]],
    *,
    name: str,
    required_binding: str,
) -> tuple[Path, dict[str, Any]]:
    tool = tools.get(name)
    if tool is None:
        raise FrozenBaseHarnessError(f"agent.yaml must declare {name}")
    if tool.get("binding") != required_binding:
        raise FrozenBaseHarnessError(
            f"{name} must use the common binding {required_binding!r}"
        )
    descriptor = _declared_path(
        root, tool.get("yaml_path"), label=f"{name} descriptor"
    )
    _nonempty_file(descriptor, label=f"{name} descriptor")
    payload = _read_yaml(descriptor, label=f"{name} descriptor")
    if payload.get("name") != name:
        raise FrozenBaseHarnessError(
            f"{name} descriptor must declare name: {name}"
        )
    return descriptor, payload


def _validate_state_descriptor(descriptor: Mapping[str, object]) -> None:
    schema = descriptor.get("input_schema")
    if not isinstance(schema, Mapping):
        raise FrozenBaseHarnessError("record_quant_state has no input_schema")
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        raise FrozenBaseHarnessError("record_quant_state has no properties schema")
    stage = properties.get("stage")
    if not isinstance(stage, Mapping):
        raise FrozenBaseHarnessError("record_quant_state has no stage property")
    states = stage.get("enum")
    if not isinstance(states, list) or tuple(states) != SIX_QUANT_STATES:
        raise FrozenBaseHarnessError(
            "record_quant_state stage enum must be exactly S1 through S6"
        )
    required = schema.get("required")
    if not isinstance(required, list) or not {
        "stage",
        "action",
        "public_summary",
    }.issubset(required):
        raise FrozenBaseHarnessError(
            "record_quant_state must require stage, action, and public_summary"
        )


def inspect_base_harness(worker_dir: str | Path) -> dict[str, object]:
    """Validate and describe one materialized Worker without copying it."""

    root = Path(worker_dir).expanduser().resolve()
    if not root.is_dir():
        raise FrozenBaseHarnessError(f"Worker directory does not exist: {root}")
    for member in root.rglob("*"):
        if member.is_symlink():
            raise FrozenBaseHarnessError(
                f"Worker directory must not contain symlinks: {member}"
            )
        if not member.is_dir() and not member.is_file():
            raise FrozenBaseHarnessError(
                f"Worker directory contains an unsupported entry: {member}"
            )
    agent_path = root / "agent.yaml"
    agent = _read_yaml(agent_path, label="agent.yaml")
    agent_name = agent.get("name")
    if not isinstance(agent_name, str) or not agent_name.strip():
        raise FrozenBaseHarnessError("agent.yaml must declare one concrete agent name")

    prompt = _declared_path(
        root, agent.get("system_prompt"), label="Worker-visible system prompt"
    )
    _nonempty_file(prompt, label="Worker-visible system prompt")

    skill_values = agent.get("skills", [])
    if not isinstance(skill_values, list):
        raise FrozenBaseHarnessError("agent.yaml skills must be a list")
    skill_files: list[Path] = []
    for index, value in enumerate(skill_values):
        skill_root = _declared_path(root, value, label=f"skill {index}")
        skill_file = skill_root / "SKILL.md" if skill_root.is_dir() else skill_root
        if skill_file.name != "SKILL.md":
            raise FrozenBaseHarnessError(
                f"skill {index} must declare a directory or SKILL.md"
            )
        _nonempty_file(skill_file, label=f"skill {index} SKILL.md")
        skill_files.append(skill_file)

    tools = _tool_map(agent)
    shell_descriptor, _ = _validate_tool(
        root,
        tools,
        name=SHELL_TOOL_NAME,
        required_binding=SHELL_TOOL_BINDING,
    )
    state_descriptor, state_payload = _validate_tool(
        root,
        tools,
        name=STATE_TOOL_NAME,
        required_binding=STATE_TOOL_BINDING,
    )
    _validate_state_descriptor(state_payload)
    state_implementation = root / "tools" / "quant_state_telemetry.py"
    _nonempty_file(state_implementation, label="passive state recorder implementation")

    visible = [
        "agent.yaml",
        _relative(root, prompt),
        _relative(root, shell_descriptor),
        _relative(root, state_descriptor),
        *(_relative(root, value) for value in skill_files),
    ]
    return {
        "agent_name": agent_name.strip(),
        "agent_config": agent,
        "worker_visible_surfaces": sorted(set(visible)),
        "declared_prompt_surface": _relative(root, prompt),
        "declared_skill_surfaces": [
            _relative(root, value) for value in skill_files
        ],
        "registered_tools": [SHELL_TOOL_NAME, STATE_TOOL_NAME],
        "state_identifiers": list(SIX_QUANT_STATES),
    }


def build_selected_runtime(
    agent_config: Mapping[str, object],
    *,
    worker_model_route: str,
    rootless_config: str,
) -> dict[str, object]:
    """Build the concrete scheduler runtime record from CLI inputs and agent limits."""

    llm = agent_config.get("llm_config")
    if not isinstance(llm, Mapping):
        raise FrozenBaseHarnessError("agent.yaml must declare llm_config")
    runtime = {
        "worker_model_route": worker_model_route,
        "rootless_config": rootless_config,
        "max_context_tokens": agent_config.get("max_context_tokens"),
        "max_iterations": agent_config.get("max_iterations"),
        "max_tokens": llm.get("max_tokens"),
        "temperature": llm.get("temperature"),
        "timeout_seconds": llm.get("timeout"),
        "tool_call_mode": agent_config.get("tool_call_mode"),
    }
    validate_selected_runtime(runtime)
    return runtime


def _is_concrete_json(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return value is not None
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        normalized = value.strip().casefold()
        return bool(normalized) and not any(
            token in normalized for token in _UNRESOLVED_RUNTIME_TOKENS
        )
    if isinstance(value, Mapping):
        return bool(value) and all(
            isinstance(key, str)
            and bool(key)
            and _is_concrete_json(child)
            for key, child in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return bool(value) and all(_is_concrete_json(child) for child in value)
    return False


def validate_selected_runtime(runtime: Mapping[str, object]) -> None:
    """Fail closed unless the handoff runtime is complete and JSON-concrete."""

    required = {
        "worker_model_route",
        "rootless_config",
        "max_context_tokens",
        "max_iterations",
        "max_tokens",
        "temperature",
        "timeout_seconds",
        "tool_call_mode",
    }
    missing = sorted(required - set(runtime))
    if missing:
        raise FrozenBaseHarnessError(
            f"selected_runtime is missing required fields: {', '.join(missing)}"
        )
    if not _is_concrete_json(dict(runtime)):
        raise FrozenBaseHarnessError(
            "selected_runtime must contain concrete JSON values without env placeholders"
        )
    for key in ("max_context_tokens", "max_iterations", "max_tokens", "timeout_seconds"):
        value = runtime[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise FrozenBaseHarnessError(f"selected_runtime.{key} must be positive")


def _mutation_surfaces(
    *,
    root: Path,
    inspection: Mapping[str, object],
    requested: Sequence[str] | None,
) -> list[str]:
    allowed = {
        str(inspection["declared_prompt_surface"]),
        *(str(value) for value in inspection["declared_skill_surfaces"]),
    }
    values = list(requested) if requested is not None else sorted(allowed)
    if not values:
        raise FrozenBaseHarnessError("at least one mutation surface must be declared")
    result: list[str] = []
    for value in values:
        path = _declared_path(root, value, label="mutation surface")
        _nonempty_file(path, label="mutation surface")
        relative = _relative(root, path)
        if relative not in allowed:
            raise FrozenBaseHarnessError(
                "mutation surfaces must be declared system-prompt or skill surfaces: "
                f"{relative}"
            )
        result.append(relative)
    if len(result) != len(set(result)):
        raise FrozenBaseHarnessError("mutation surfaces must not contain duplicates")
    return sorted(result)


def freeze_base_harness(
    *,
    worker_dir: str | Path,
    run_root: str | Path,
    selected_profile_id: str,
    selected_runtime: Mapping[str, object],
    selection_artifact_root: str | Path,
    handoff_path: str | Path,
    mutation_surfaces: Sequence[str] | None = None,
) -> dict[str, object]:
    """Copy one valid Worker into a run-scoped frozen directory and emit handoff."""

    if not _PROFILE_ID.fullmatch(selected_profile_id):
        raise FrozenBaseHarnessError(
            "selected_profile_id must use letters, digits, dot, underscore, or hyphen"
        )
    validate_selected_runtime(selected_runtime)
    artifacts = Path(selection_artifact_root).expanduser().resolve()
    if not artifacts.is_dir():
        raise FrozenBaseHarnessError(
            f"selection_artifact_root is not a materialized directory: {artifacts}"
        )

    source = Path(worker_dir).expanduser().resolve()
    source_inspection = inspect_base_harness(source)
    declared_mutations = _mutation_surfaces(
        root=source,
        inspection=source_inspection,
        requested=mutation_surfaces,
    )

    destination = (
        Path(run_root).expanduser().resolve()
        / "frozen-base-harness"
        / selected_profile_id
        / "worker"
    )
    if destination.exists():
        raise FrozenBaseHarnessError(
            f"frozen Worker destination already exists; refusing overwrite: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    frozen_inspection = inspect_base_harness(destination)
    if frozen_inspection["agent_name"] != source_inspection["agent_name"]:
        raise FrozenBaseHarnessError("copied Worker agent identity changed unexpectedly")

    manifest: dict[str, object] = {
        "schema_version": 1,
        "record_kind": "qrs_frozen_base_harness_handoff",
        "selection_complete": True,
        "selected_profile_id": selected_profile_id,
        "selected_worker_root": str(destination),
        "selected_agent_name": frozen_inspection["agent_name"],
        "selected_runtime": dict(selected_runtime),
        "selection_artifact_root": str(artifacts),
        "frozen_for_qrs_scheduler": True,
        "adapter_contract": {
            "source_authoring_outside_qrs_scheduler": True,
            "scheduler_must_not_modify_selected_worker_in_place": True,
            "registered_tools": frozen_inspection["registered_tools"],
            "state_identifiers": frozen_inspection["state_identifiers"],
            "worker_visible_surfaces": frozen_inspection[
                "worker_visible_surfaces"
            ],
            "mutation_surfaces": declared_mutations,
        },
    }
    output = Path(handoff_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FrozenBaseHarnessError(
            f"handoff manifest already exists; refusing overwrite: {output}"
        )
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest
