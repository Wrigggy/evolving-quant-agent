"""QuantCodeEval v2 evidence with exact, answer-free mutation experience."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Iterable, Mapping

from .evolution_evidence import EvidenceRecord
from .quantcodeeval_evidence import (
    QuantCodeEvalEvidenceError,
    QuantEvidenceAttemptSource,
    build_quantcodeeval_evidence,
)
from .quantcodeeval_components import (
    QuantComponentLedgerError,
    load_quantcodeeval_component_ledger,
)
from .quantcodeeval_history import (
    QuantCodeEvalHistoryError,
    materialize_quantcodeeval_history_evidence,
)
from .quantcodeeval_experience import (
    QuantCodeEvalExperienceError,
    materialize_quantcodeeval_experience,
)


class QuantCodeEvalV2EvidenceError(ValueError):
    """A v2 evidence corpus or its history projection is inconsistent."""


_PREFERRED_PRIMARY_COMPONENTS = {
    "interface_delivery": ["validator", "tools", "tool_descriptions"],
    "data_universe_preprocessing": ["tools", "skills", "validator"],
    "temporal_causality": ["tools", "validator", "skills"],
    "formula_parameterization": ["tools", "skills", "memory"],
    "signal_direction": ["tools", "validator", "memory"],
    "portfolio_accounting": ["tools", "validator", "routing"],
    "runtime_completion": ["middleware", "agent_config", "routing"],
    "isolated_task_specific": [],
    "unknown": [],
}
_COMPONENT_SOURCE_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")


def _quant_failure_map() -> dict[str, object]:
    path = Path(__file__).resolve().parent / "evolve_agent_full/quant_failure_map.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalV2EvidenceError(
            f"cannot read quant failure map: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise QuantCodeEvalV2EvidenceError("quant failure map must be an object")
    return value


def _quant_research_states() -> dict[str, object]:
    path = Path(__file__).resolve().parent / "evolve_agent_full/quant_research_states.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuantCodeEvalV2EvidenceError(
            f"cannot read quant research states: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise QuantCodeEvalV2EvidenceError("quant research states must be an object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _digest_tree(root: Path) -> tuple[str, tuple[str, ...]]:
    digest = hashlib.sha256()
    members: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise QuantCodeEvalV2EvidenceError("v2 evidence contains a symlink")
        if not path.is_file() or path.name == "access_log.jsonl":
            continue
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        members.append(relative)
    return digest.hexdigest(), tuple(members)


def build_quantcodeeval_v2_evidence(
    *,
    destination: str | Path,
    public_task_roots: Mapping[str, str | Path],
    attempts: Iterable[QuantEvidenceAttemptSource],
    current_evaluation_id: str,
    history_root: str | Path | None,
    component_ledger_path: str | Path | None = None,
    component_sources: Mapping[str, str | Path] | None = None,
    worker_artifact_sources: Mapping[str, str | Path] | None = None,
    experiment_observation_sources: Mapping[str, str | Path] | None = None,
    autonomous_probe_required: bool = False,
    iteration_summaries: Iterable[Mapping[str, object]] = (),
    current_parent: str | None = None,
    max_primary_components: int = 2,
    max_declared_components: int = 6,
) -> EvidenceRecord:
    """Build v1-safe evidence plus immutable prior candidate snapshots and diffs."""

    if type(max_primary_components) is not int or not 1 <= max_primary_components <= 2:
        raise QuantCodeEvalV2EvidenceError(
            "max_primary_components must be one or two"
        )
    if (
        type(max_declared_components) is not int
        or not max_primary_components <= max_declared_components <= 9
    ):
        raise QuantCodeEvalV2EvidenceError(
            "max_declared_components must cover primary roles and be at most nine"
        )
    sources = tuple(attempts)
    current = [
        source
        for source in sources
        if source.record.evaluation_id == current_evaluation_id
    ]
    current_rewards = {
        source.record.task_id: float(source.record.official_reward)
        for source in current
    }
    if set(current_rewards) != {str(task_id) for task_id in public_task_roots}:
        raise QuantCodeEvalV2EvidenceError(
            "current v2 evidence must cover the complete fixed task panel"
        )

    target = Path(destination).expanduser().resolve()
    if target.exists() or target.is_symlink():
        raise QuantCodeEvalV2EvidenceError(
            "v2 evidence destination must not already exist"
        )
    staging = target.with_name(target.name + ".partial")
    base = target.with_name(target.name + ".base-partial")
    for path in (staging, base):
        if path.exists() or path.is_symlink():
            raise QuantCodeEvalV2EvidenceError(
                f"v2 evidence staging path already exists: {path.name}"
            )
    try:
        build_quantcodeeval_evidence(
            destination=base,
            public_task_roots=public_task_roots,
            attempts=sources,
            current_evaluation_id=current_evaluation_id,
            history=iteration_summaries,
        )
        shutil.copytree(base, staging, copy_function=shutil.copy2)
        history_summary: dict[str, object] = {
            "schema_version": 1,
            "entry_count": 0,
            "entry_ids": [],
            "object_count": 0,
            "diff_count": 0,
            "experience_count": 0,
            "relevant_experience_count": 0,
        }
        if history_root is not None:
            try:
                projected = materialize_quantcodeeval_history_evidence(
                    history_root=history_root,
                    destination=staging / "history" / "archive",
                )
            except QuantCodeEvalHistoryError as exc:
                raise QuantCodeEvalV2EvidenceError(
                    f"cannot project QuantCodeEval history: {exc}"
                ) from exc
            history_summary = {
                key: projected[key]
                for key in (
                    "schema_version",
                    "entry_count",
                    "entry_ids",
                    "object_count",
                    "diff_count",
                )
            }
            experience = materialize_quantcodeeval_experience(
                archive_root=staging / "history" / "archive",
                destination=staging / "history" / "experience",
                target_task_ids=(
                    task_id
                    for task_id, reward in current_rewards.items()
                    if reward == 0.0
                ),
                current_parent=current_parent,
            )
            history_summary.update(
                {
                    "experience_count": experience["experience_count"],
                    "relevant_experience_count": experience["relevant_count"],
                    "current_parent_experience_key": experience[
                        "current_parent_experience_key"
                    ],
                }
            )
        _write_json(staging / "history" / "SUMMARY.json", history_summary)
        _write_json(
            staging / "guidance" / "quant_failure_map.json",
            _quant_failure_map(),
        )
        _write_json(
            staging / "guidance" / "quant_research_states.json",
            _quant_research_states(),
        )
        component_stability = None
        if component_ledger_path is not None:
            component_stability = "guidance/component_stability.json"
            ledger = load_quantcodeeval_component_ledger(component_ledger_path)
            _write_json(staging / component_stability, ledger.summary())
        exposed_component_sources = {}
        for name, raw_source in sorted((component_sources or {}).items()):
            if _COMPONENT_SOURCE_NAME.fullmatch(name) is None:
                raise QuantCodeEvalV2EvidenceError(
                    f"component source name is invalid: {name}"
                )
            source = Path(raw_source).expanduser().resolve()
            if not source.is_dir():
                raise QuantCodeEvalV2EvidenceError(
                    f"component source is not a directory: {source}"
                )
            relative = f"guidance/component_sources/{name}"
            shutil.copytree(
                source,
                staging / relative,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            exposed_component_sources[name] = relative
        exposed_worker_artifacts = {}
        for name, raw_source in sorted((worker_artifact_sources or {}).items()):
            if _COMPONENT_SOURCE_NAME.fullmatch(name) is None:
                raise QuantCodeEvalV2EvidenceError(
                    f"worker artifact name is invalid: {name}"
                )
            source = Path(raw_source).expanduser().resolve()
            if not source.is_file():
                raise QuantCodeEvalV2EvidenceError(
                    f"worker artifact is not a file: {source}"
                )
            relative = f"guidance/worker_artifacts/{name}.py"
            destination_path = staging / relative
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination_path)
            exposed_worker_artifacts[name] = relative
        exposed_experiment_observations = {}
        for name, raw_source in sorted(
            (experiment_observation_sources or {}).items()
        ):
            if _COMPONENT_SOURCE_NAME.fullmatch(name) is None:
                raise QuantCodeEvalV2EvidenceError(
                    f"experiment observation name is invalid: {name}"
                )
            source = Path(raw_source).expanduser().resolve()
            if not source.is_file():
                raise QuantCodeEvalV2EvidenceError(
                    f"experiment observation is not a file: {source}"
                )
            try:
                observation = json.loads(source.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise QuantCodeEvalV2EvidenceError(
                    f"experiment observation is not valid JSON: {source}"
                ) from exc
            if not isinstance(observation, Mapping):
                raise QuantCodeEvalV2EvidenceError(
                    "experiment observation must contain a JSON object"
                )
            relative = f"guidance/experiment_observations/{name}.json"
            _write_json(staging / relative, dict(observation))
            exposed_experiment_observations[name] = relative
        _write_json(
            staging / "contract.json",
            {
                "schema_version": 2,
                "stage": "PGBHS_V2",
                "benchmark": "quantcodeeval",
                "decision_protocol": "quant_property_v2",
                "feedback_tier": "answer_free_property_family_v2",
                "task_ids": sorted(current_rewards),
                "target_task_ids": sorted(
                    task_id
                    for task_id, reward in current_rewards.items()
                    if reward == 0.0
                ),
                "protection_task_ids": sorted(
                    task_id
                    for task_id, reward in current_rewards.items()
                    if reward == 1.0
                ),
                "current_evaluation_id": current_evaluation_id,
                "history_required": history_summary["entry_count"] != 0,
                "history_entry_ids": history_summary["entry_ids"],
                "experience_catalog": (
                    "history/experience/CATALOG.json"
                    if history_summary["entry_count"]
                    else None
                ),
                "relevant_experience": (
                    "history/experience/RELEVANT.json"
                    if history_summary["entry_count"]
                    else None
                ),
                "max_primary_components": max_primary_components,
                "max_declared_components": max_declared_components,
                "preferred_primary_components": _PREFERRED_PRIMARY_COMPONENTS,
                "component_priors_are_advisory": True,
                "research_state_definitions": "guidance/quant_research_states.json",
                "research_state_transition_required_for_act": True,
                "quant_failure_map": "guidance/quant_failure_map.json",
                "component_stability": component_stability,
                "component_stability_is_answer_free": True,
                "component_stability_is_advisory": True,
                "component_sources": exposed_component_sources,
                "component_sources_are_advisory": True,
                "worker_artifacts": exposed_worker_artifacts,
                "worker_artifacts_are_scored_runtime_experience": True,
                "worker_artifacts_are_reference_answers": False,
                "experiment_observations": exposed_experiment_observations,
                "experiment_observations_are_runtime_feedback": True,
                "autonomous_probe_required": bool(autonomous_probe_required),
                "quant_failure_classification_required_for_act": False,
                "domain_guidance_is_advisory": True,
                "domain_tags_are_extensible": True,
                "search_operators": [
                    "CONTINUE",
                    "REUSE",
                    "REVERT",
                    "FUSE",
                    "COMPOSE",
                    "SYNTHESIZE",
                    "ROUTE",
                    "NEW_PROBE",
                ],
                "component_role_semantics": (
                    "components and primary_components are exact candidate file roles, "
                    "not conceptual capabilities; declare validator only when validator/** "
                    "changes, and declare tools for validator behavior implemented in tools/**"
                ),
                "declared_components_must_equal_exact_changed_file_roles": True,
                "exact_history_content_exposed": history_summary["entry_count"] != 0,
                "oracle_fields_exposed": False,
            },
        )
        sha256, members = _digest_tree(staging)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
        return EvidenceRecord(root=target, sha256=sha256, members=members)
    except (
        QuantCodeEvalEvidenceError,
        QuantComponentLedgerError,
        QuantCodeEvalExperienceError,
        OSError,
        ValueError,
    ) as exc:
        if isinstance(exc, QuantCodeEvalV2EvidenceError):
            raise
        raise QuantCodeEvalV2EvidenceError(f"cannot build v2 evidence: {exc}") from exc
    finally:
        shutil.rmtree(base, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)


__all__ = [
    "QuantCodeEvalV2EvidenceError",
    "build_quantcodeeval_v2_evidence",
]
