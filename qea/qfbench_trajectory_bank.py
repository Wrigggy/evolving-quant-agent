"""Build a panelized, answer-separated QFBench H0 trajectory bank."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Iterable, Mapping, Sequence


class QFBenchTrajectoryBankError(ValueError):
    """A source set cannot form a safe QFBench trajectory bank."""


_CONTROLLER_ROOT = "controller-only"
_EVOLVER_ROOT = "evolver-answer-free"
_SAFE_RUNTIME_FIELDS = (
    "outcome",
    "turns",
    "tool_calls",
    "tool_errors",
    "files",
    "secs",
)
_FORBIDDEN_EVOLVER_TERMS = (
    "completed-score",
    "official-score",
    "public_evaluation",
    "optimization-diagnostic",
    "/verifier/",
    "\\verifier\\",
)


def _read_json(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise QFBenchTrajectoryBankError(f"{label} is unavailable: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QFBenchTrajectoryBankError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise QFBenchTrajectoryBankError(f"{label} must be a JSON object")
    return value


def _optional_json(path: Path) -> dict[str, object] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _without_identity_fields(value: object) -> object:
    """Remove existing content-addressed metadata from copied JSON values."""

    if isinstance(value, Mapping):
        clean: dict[str, object] = {}
        for key, child in value.items():
            name = str(key)
            folded = name.casefold()
            if (
                "sha" in folded
                or "digest" in folded
                or "hash" in folded
                or folded in {"attempt_id", "benchmark_commit"}
            ):
                continue
            clean[name] = _without_identity_fields(child)
        return clean
    if isinstance(value, list):
        return [_without_identity_fields(child) for child in value]
    return value


def _json_text(value: object) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _write_json_if_changed(path: Path, value: object) -> bool:
    text = _json_text(value)
    if path.is_file() and not path.is_symlink():
        try:
            if path.read_text(encoding="utf-8") == text:
                return False
        except (OSError, UnicodeError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
    return True


def _write_text_if_changed(path: Path, text: str) -> bool:
    if path.is_file() and not path.is_symlink():
        try:
            if path.read_text(encoding="utf-8") == text:
                return False
        except (OSError, UnicodeError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
    return True


def _read_public_text(path: Path, *, label: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise QFBenchTrajectoryBankError(f"{label} is unavailable: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise QFBenchTrajectoryBankError(
            f"{label} must be a regular UTF-8 text file: {path}"
        ) from exc


def _relative_output(path: Path, destination: Path) -> str:
    return path.relative_to(destination).as_posix()


def _task_metadata(manifest: Mapping[str, object]) -> dict[str, dict[str, object]]:
    baseline = manifest.get("baseline")
    rows = baseline.get("primary") if isinstance(baseline, Mapping) else None
    if not isinstance(rows, list):
        raise QFBenchTrajectoryBankError(
            "QFBench manifest must contain baseline.primary"
        )
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise QFBenchTrajectoryBankError("baseline.primary rows must be objects")
        task_id = row.get("task_id")
        family = row.get("domain")
        if not isinstance(task_id, str) or not task_id:
            raise QFBenchTrajectoryBankError("manifest task_id must be non-empty")
        if not isinstance(family, str) or not family:
            raise QFBenchTrajectoryBankError(
                f"manifest family is missing for {task_id}"
            )
        if task_id in result:
            raise QFBenchTrajectoryBankError(
                f"manifest task_id is duplicated: {task_id}"
            )
        result[task_id] = {
            "task_id": task_id,
            "family": family,
            "difficulty": row.get("difficulty", "unlabelled"),
            "reward_kind": row.get("reward_kind", "unknown"),
            "resource_source": row.get("resource_source", "unknown"),
            "lineage": row.get("lineage"),
        }
    return result


def _plan_layout(
    plan: Mapping[str, object],
    *,
    manifest_tasks: Mapping[str, Mapping[str, object]],
) -> tuple[list[dict[str, object]], dict[str, str], set[str]]:
    raw_sealed = plan.get("sealed_main_tasks")
    raw_panels = plan.get("development_panels")
    cross_family = plan.get("cross_family_workflow_evidence")
    raw_anchors = (
        cross_family.get("anchor_task_by_family")
        if isinstance(cross_family, Mapping)
        else None
    )
    if not isinstance(raw_sealed, list) or not isinstance(raw_panels, list):
        raise QFBenchTrajectoryBankError(
            "scheduler plan needs sealed_main_tasks and development_panels"
        )
    if not isinstance(raw_anchors, Mapping):
        raise QFBenchTrajectoryBankError(
            "scheduler plan needs cross-family anchor_task_by_family"
        )

    sealed: set[str] = set()
    for row in raw_sealed:
        task_id = row.get("task_id") if isinstance(row, Mapping) else None
        if not isinstance(task_id, str) or not task_id:
            raise QFBenchTrajectoryBankError("sealed task_id must be non-empty")
        if task_id in sealed:
            raise QFBenchTrajectoryBankError("sealed task IDs must be unique")
        sealed.add(task_id)

    panels: list[dict[str, object]] = []
    development_seen: set[str] = set()
    for position, row in enumerate(raw_panels, start=1):
        if not isinstance(row, Mapping):
            raise QFBenchTrajectoryBankError("development panel must be an object")
        panel_index = row.get("panel_index", position)
        family = row.get("family")
        task_ids = row.get("task_ids")
        if not isinstance(panel_index, int) or panel_index < 1:
            raise QFBenchTrajectoryBankError("panel_index must be a positive integer")
        if not isinstance(family, str) or not family:
            raise QFBenchTrajectoryBankError("panel family must be non-empty")
        if not isinstance(task_ids, list) or not task_ids:
            raise QFBenchTrajectoryBankError(
                f"panel {panel_index} must contain task_ids"
            )
        normalized: list[str] = []
        for task_id in task_ids:
            if not isinstance(task_id, str) or not task_id:
                raise QFBenchTrajectoryBankError(
                    f"panel {panel_index} task_id must be non-empty"
                )
            if task_id in sealed:
                raise QFBenchTrajectoryBankError(
                    "sealed tasks cannot enter development panels"
                )
            metadata = manifest_tasks.get(task_id)
            if metadata is None:
                raise QFBenchTrajectoryBankError(
                    f"panel task is absent from the public manifest: {task_id}"
                )
            if metadata.get("family") != family:
                raise QFBenchTrajectoryBankError(
                    f"panel family mismatch for {task_id}: {family}"
                )
            if task_id in development_seen:
                raise QFBenchTrajectoryBankError(
                    f"development task appears in more than one panel: {task_id}"
                )
            development_seen.add(task_id)
            normalized.append(task_id)
        panels.append(
            {
                "panel_index": panel_index,
                "family": family,
                "task_ids": sorted(normalized),
            }
        )
    panels.sort(key=lambda row: int(row["panel_index"]))
    panel_indices = [row["panel_index"] for row in panels]
    if len(panel_indices) != len(set(panel_indices)):
        raise QFBenchTrajectoryBankError("panel indices must be unique")

    anchors: dict[str, str] = {}
    for family, task_id in raw_anchors.items():
        if not isinstance(family, str) or not isinstance(task_id, str):
            raise QFBenchTrajectoryBankError("cross-family anchors must be strings")
        metadata = manifest_tasks.get(task_id)
        if task_id not in development_seen or metadata is None:
            raise QFBenchTrajectoryBankError(
                f"anchor is not a development task: {task_id}"
            )
        if metadata.get("family") != family:
            raise QFBenchTrajectoryBankError(
                f"anchor family mismatch for {task_id}: {family}"
            )
        anchors[family] = task_id
    panel_families = {str(row["family"]) for row in panels}
    if set(anchors) != panel_families:
        raise QFBenchTrajectoryBankError(
            "cross-family anchors must cover every development family exactly once"
        )
    return panels, anchors, sealed


def _contract_paths(root: Path, task_id: str) -> dict[str, object]:
    task_root = root / task_id
    instruction = task_root / "instruction.md"
    clauses = task_root / "clauses.json"
    if not clauses.is_file() or clauses.is_symlink():
        clauses = task_root / "public_clauses.json"
    instruction_path = (
        str(instruction.resolve())
        if instruction.is_file() and not instruction.is_symlink()
        else None
    )
    clauses_path = (
        str(clauses.resolve())
        if clauses.is_file() and not clauses.is_symlink()
        else None
    )
    return {
        "complete": instruction_path is not None and clauses_path is not None,
        "instruction_path": instruction_path,
        "public_clauses_path": clauses_path,
    }


def _local_member(attempt: Path, value: object, fallback: str) -> Path:
    name = value if isinstance(value, str) else fallback
    if Path(name).name != name:
        return attempt / "__unsafe_member__"
    return attempt / name


def _regular_file_record(path: Path) -> dict[str, object] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    return {"path": str(path.resolve()), "size_bytes": size}


def _artifact_records(attempt: Path) -> tuple[list[dict[str, object]], list[str]]:
    root = attempt / "artifacts"
    if root.is_symlink():
        return [], ["artifact_directory_is_symlink"]
    if not root.is_dir():
        return [], []
    records: list[dict[str, object]] = []
    issues: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            issues.append(
                f"artifact_symlink:{path.relative_to(root).as_posix()}"
            )
            continue
        if not path.is_file():
            continue
        record = _regular_file_record(path)
        if record is None:
            issues.append(
                f"artifact_unreadable:{path.relative_to(root).as_posix()}"
            )
            continue
        record["relative_path"] = path.relative_to(root).as_posix()
        records.append(record)
    return records, issues


def _runtime_summary(execution: Mapping[str, object] | None) -> dict[str, object]:
    if execution is None:
        return {"outcome": "missing_worker_execution"}
    raw = execution.get("summary")
    if not isinstance(raw, Mapping):
        return {"outcome": "missing_worker_summary"}
    summary = {key: raw[key] for key in _SAFE_RUNTIME_FIELDS if key in raw}
    if not isinstance(summary.get("outcome"), str):
        summary["outcome"] = "unknown"
    return summary


def _history_base(attempt: Path) -> tuple[dict[str, object], dict[str, object]]:
    execution_path = attempt / "worker-execution.json"
    execution = _optional_json(execution_path)
    summary = _runtime_summary(execution)
    trace = _local_member(
        attempt,
        execution.get("trace_uri") if execution is not None else None,
        "raw-trace.jsonl",
    )
    final = _local_member(
        attempt,
        execution.get("final_text_uri") if execution is not None else None,
        "final.txt",
    )
    state_trace = attempt / "research-state-trace.json"
    trace_record = _regular_file_record(trace)
    final_record = _regular_file_record(final)
    state_record = _regular_file_record(state_trace)
    artifacts, artifact_issues = _artifact_records(attempt)
    missing: list[str] = []
    if execution is None:
        missing.append("worker_execution")
    if trace_record is None:
        missing.append("worker_trace")
    if final_record is None:
        missing.append("worker_final")
    outcome = summary.get("outcome")
    valid = outcome == "completed" and not missing
    answer_free = {
        "runtime_status": "valid" if valid else "invalid",
        "runtime_summary": summary,
        "missing_surfaces": missing,
        "trace": trace_record,
        "final": final_record,
        "research_state_trace": state_record,
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "artifact_state": "present" if artifacts else "empty",
        "artifact_issues": artifact_issues,
    }
    controller = {
        **answer_free,
        "source_attempt_dir": str(attempt.resolve()),
        "worker_execution_path": (
            str(execution_path.resolve())
            if execution_path.is_file() and not execution_path.is_symlink()
            else None
        ),
    }
    return answer_free, controller


def _controller_verifier(attempt: Path) -> dict[str, object]:
    completed_path = attempt / "completed-score.json"
    official_path = attempt / "verifier" / "official-score.json"
    completed = _optional_json(completed_path)
    official = _optional_json(official_path)
    verifier_root = attempt / "verifier"
    files: list[dict[str, object]] = []
    if verifier_root.is_dir() and not verifier_root.is_symlink():
        for path in sorted(verifier_root.rglob("*")):
            record = _regular_file_record(path)
            if record is None:
                continue
            record["relative_path"] = path.relative_to(verifier_root).as_posix()
            files.append(record)
    return {
        "completed_score_path": (
            str(completed_path.resolve())
            if completed_path.is_file() and not completed_path.is_symlink()
            else None
        ),
        "completed_score": (
            _without_identity_fields(completed) if completed is not None else None
        ),
        "official_score_path": (
            str(official_path.resolve())
            if official_path.is_file() and not official_path.is_symlink()
            else None
        ),
        "official_score": (
            _without_identity_fields(official) if official is not None else None
        ),
        "verifier_files": files,
        "verifier_file_count": len(files),
    }


def _attempt_task_id(attempt: Path) -> str | None:
    record = _optional_json(attempt / "attempt.json")
    task_id = record.get("task_id") if record is not None else None
    return task_id if isinstance(task_id, str) and task_id else None


def _discover_histories(
    run_dirs: Sequence[Path],
    *,
    development_ids: set[str],
    sealed_ids: set[str],
) -> tuple[
    dict[str, list[Path]],
    list[Path],
    int,
    int,
]:
    histories: dict[str, list[Path]] = defaultdict(list)
    unassigned: list[Path] = []
    sealed_count = 0
    unrelated_count = 0
    seen_attempts: set[Path] = set()
    for run in sorted({path.expanduser().resolve() for path in run_dirs}, key=str):
        attempts_root = run / "attempts"
        if not attempts_root.is_dir() or attempts_root.is_symlink():
            raise QFBenchTrajectoryBankError(
                f"H0 run has no regular attempts directory: {run}"
            )
        for attempt in sorted(attempts_root.iterdir(), key=lambda path: path.name):
            if attempt.is_symlink() or not attempt.is_dir():
                continue
            resolved = attempt.resolve()
            if resolved in seen_attempts:
                continue
            seen_attempts.add(resolved)
            task_id = _attempt_task_id(attempt)
            if task_id is None:
                unassigned.append(resolved)
            elif task_id in sealed_ids:
                sealed_count += 1
            elif task_id in development_ids:
                histories[task_id].append(resolved)
            else:
                unrelated_count += 1
    return histories, unassigned, sealed_count, unrelated_count


def _assert_answer_free(value: object) -> None:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False).casefold()
    for term in _FORBIDDEN_EVOLVER_TERMS:
        if term in text:
            raise QFBenchTrajectoryBankError(
                f"forbidden controller-only reference entered Evolver evidence: {term}"
            )


def _assert_no_identity_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            folded = str(key).casefold()
            if "sha" in folded or "digest" in folded or "hash" in folded:
                raise QFBenchTrajectoryBankError(
                    f"generated JSON cannot contain content identity field: {key}"
                )
            _assert_no_identity_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_identity_keys(child)


def _safe_relative_member(value: object, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise QFBenchTrajectoryBankError(f"{label} must be a non-empty path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise QFBenchTrajectoryBankError(f"{label} is unsafe: {value}")
    return path


def _copy_answer_free_attempt(
    attempt: Path,
    destination: Path,
    *,
    label: str,
) -> None:
    answer_free, _controller = _history_base(attempt)
    if answer_free["runtime_status"] != "valid":
        raise QFBenchTrajectoryBankError(f"{label} is not a valid Worker history")
    trace = Path(str(answer_free["trace"]["path"]))
    final = Path(str(answer_free["final"]["path"]))
    _write_text_if_changed(
        destination / "worker_trace.jsonl",
        _read_public_text(trace, label=f"{label} Worker trace"),
    )
    _write_text_if_changed(
        destination / "worker_final.txt",
        _read_public_text(final, label=f"{label} Worker final"),
    )
    _write_json_if_changed(
        destination / "process_summary.json",
        answer_free["runtime_summary"],
    )
    state_trace = answer_free.get("research_state_trace")
    if isinstance(state_trace, Mapping):
        state_source = Path(str(state_trace["path"]))
        _write_json_if_changed(
            destination / "research_state_trace.json",
            _without_identity_fields(
                _read_json(state_source, label=f"{label} research state trace")
            ),
        )
    artifact_rows: list[dict[str, object]] = []
    for artifact in answer_free["artifacts"]:
        relative = _safe_relative_member(
            artifact.get("relative_path"), label=f"{label} artifact"
        )
        source = Path(str(artifact["path"]))
        _write_text_if_changed(
            destination / "artifacts" / relative,
            _read_public_text(source, label=f"{label} artifact {relative}"),
        )
        artifact_rows.append(
            {
                "relative_path": relative.as_posix(),
                "size_bytes": artifact["size_bytes"],
            }
        )
    _write_json_if_changed(
        destination / "artifact_manifest.json",
        {
            "schema_version": 1,
            "artifact_state": answer_free["artifact_state"],
            "artifacts": artifact_rows,
        },
    )


def _copy_existing_accepted_history(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    if source.is_symlink() or not source.is_dir():
        raise QFBenchTrajectoryBankError(
            f"accepted panel history is not a regular directory: {source}"
        )
    for member in sorted(source.rglob("*")):
        if member.is_symlink():
            raise QFBenchTrajectoryBankError(
                f"accepted panel history contains a symlink: {member}"
            )
        if not member.is_file():
            continue
        relative = member.relative_to(source)
        target = destination / relative
        _write_text_if_changed(
            target,
            _read_public_text(member, label=f"accepted history {relative}"),
        )


def _refresh_accepted_history_index(target_root: Path) -> list[dict[str, object]]:
    accepted_root = target_root / "accepted-panels"
    entries = []
    for record_path in sorted(accepted_root.glob("panel-*/ACCEPTED-PANEL.json")):
        record = _read_json(record_path, label="accepted panel record")
        entries.append(
            {
                "panel_index": record["panel_index"],
                "family": record["family"],
                "task_ids": record["task_ids"],
                "record": record_path.relative_to(target_root).as_posix(),
            }
        )
    index = {
        "schema_version": 1,
        "record_kind": "qrs_accepted_panel_history_index",
        "answer_free": True,
        "entries": entries,
    }
    _write_json_if_changed(accepted_root / "INDEX.json", index)
    contract_path = target_root / "contract.json"
    contract = _read_json(contract_path, label="next panel contract")
    contract["prior_accepted_panel_history"] = entries
    contract["accepted_history_index"] = "accepted-panels/INDEX.json"
    _assert_no_identity_keys(contract)
    _write_json_if_changed(contract_path, contract)
    return entries


def carry_accepted_panel_history(
    *, source_evidence_root: Path, next_evidence_root: Path
) -> dict[str, object]:
    """Carry only previously accepted histories across a retained panel."""

    source_root = source_evidence_root.expanduser().resolve()
    target_root = next_evidence_root.expanduser().resolve()
    if source_root == target_root:
        raise QFBenchTrajectoryBankError("source and next panel evidence must differ")
    for root, label in ((source_root, "source"), (target_root, "next")):
        if root.is_symlink() or not (root / "contract.json").is_file():
            raise QFBenchTrajectoryBankError(
                f"{label} panel evidence root is unavailable: {root}"
            )
    _copy_existing_accepted_history(
        source_root / "accepted-panels", target_root / "accepted-panels"
    )
    entries = _refresh_accepted_history_index(target_root)
    return {
        "schema_version": 1,
        "status": "complete",
        "answer_free": True,
        "next_evidence_root": str(target_root),
        "carried_entry_count": len(entries),
        "sealed_task_ids_present": [],
        "cost": {},
    }


def append_accepted_panel_history(
    *,
    source_evidence_root: Path,
    next_evidence_root: Path,
    panel_index: int,
    family: str,
    task_ids: Sequence[str],
    accepted_claims: Sequence[Mapping[str, object]],
    matched_run_dirs: Sequence[Path],
) -> dict[str, object]:
    """Carry one promoted panel's answer-free experience into the next view.

    This operation deliberately copies only candidate Worker traces, finals,
    public artifacts, passive state traces, and the already reviewed claim
    inventory.  It never reads or copies official score, verifier, Reviewer
    reasoning, or controller decision surfaces.
    """

    source_root = source_evidence_root.expanduser().resolve()
    target_root = next_evidence_root.expanduser().resolve()
    if source_root == target_root:
        raise QFBenchTrajectoryBankError("source and next panel evidence must differ")
    for root, label in ((source_root, "source"), (target_root, "next")):
        if root.is_symlink() or not (root / "contract.json").is_file():
            raise QFBenchTrajectoryBankError(
                f"{label} panel evidence root is unavailable: {root}"
            )
    if panel_index < 1 or not family or not task_ids:
        raise QFBenchTrajectoryBankError("accepted panel identity is incomplete")
    if len(matched_run_dirs) != 2:
        raise QFBenchTrajectoryBankError(
            "accepted panel history requires exactly two matched repetitions"
        )
    normalized_tasks = list(task_ids)
    if (
        any(not isinstance(task_id, str) or not task_id for task_id in normalized_tasks)
        or len(normalized_tasks) != len(set(normalized_tasks))
    ):
        raise QFBenchTrajectoryBankError("accepted panel task IDs are invalid")
    clean_claims: list[dict[str, object]] = []
    seen_claims: set[str] = set()
    for claim in accepted_claims:
        if not isinstance(claim, Mapping):
            raise QFBenchTrajectoryBankError("accepted claim must be an object")
        claim_id = claim.get("claim_id")
        text = claim.get("claim")
        surfaces = claim.get("surfaces")
        basis_refs = claim.get("basis_refs")
        safe_sources = claim.get("safe_sources")
        if (
            not isinstance(claim_id, str)
            or not claim_id
            or claim_id in seen_claims
            or not isinstance(text, str)
            or not text
            or not isinstance(surfaces, list)
            or not surfaces
            or not isinstance(basis_refs, list)
            or not basis_refs
            or not isinstance(safe_sources, list)
            or not safe_sources
        ):
            raise QFBenchTrajectoryBankError("accepted claim inventory is incomplete")
        safe_refs: set[str] = set()
        clean_sources: list[dict[str, object]] = []
        for source in safe_sources:
            if not isinstance(source, Mapping):
                raise QFBenchTrajectoryBankError("accepted safe source is invalid")
            ref = source.get("ref")
            source_type = source.get("source_type")
            if (
                not isinstance(ref, str)
                or not ref
                or ref in safe_refs
                or source_type not in {
                    "public_contract",
                    "public_reference",
                    "framework_reference",
                    "answer_free_development_observation",
                }
            ):
                raise QFBenchTrajectoryBankError(
                    "accepted safe source has no unique permitted identity"
                )
            safe_refs.add(ref)
            source_path_value = source.get("source_path")
            excerpt = source.get("excerpt")
            if (
                not isinstance(source_path_value, str)
                or not source_path_value
                or not isinstance(excerpt, str)
                or not excerpt
            ):
                raise QFBenchTrajectoryBankError(
                    "accepted safe source has no exact path and excerpt"
                )
            source_path = Path(source_path_value).expanduser().resolve()
            source_text = _read_public_text(
                source_path, label=f"accepted safe source {ref}"
            )
            if source_type == "answer_free_development_observation":
                source_lines = source_text.splitlines()
                for excerpt_line in excerpt.splitlines():
                    match = re.fullmatch(r"line (\d+): (.*)", excerpt_line)
                    if (
                        match is None
                        or int(match.group(1)) < 1
                        or int(match.group(1)) > len(source_lines)
                        or source_lines[int(match.group(1)) - 1] != match.group(2)
                    ):
                        raise QFBenchTrajectoryBankError(
                            "accepted development excerpt differs from its source"
                        )
            elif excerpt != source_text:
                raise QFBenchTrajectoryBankError(
                    "accepted safe excerpt differs from its source"
                )
            clean_source = deepcopy(dict(source))
            clean_sources.append(clean_source)
        basis_identities = {
            str(record.get("ref"))
            for record in basis_refs
            if isinstance(record, Mapping) and record.get("ref")
        }
        if not basis_identities or not basis_identities.issubset(safe_refs):
            raise QFBenchTrajectoryBankError(
                "accepted claim basis lacks an exact safe source"
            )
        seen_claims.add(claim_id)
        clean_claims.append(
            {
                "claim_id": claim_id,
                "claim_scope": claim.get(
                    "claim_scope", "task_specific_requirement"
                ),
                "claim": text,
                "surfaces": list(surfaces),
                "basis_refs": list(basis_refs),
                "safe_sources": clean_sources,
            }
        )

    accepted_root = target_root / "accepted-panels"
    _copy_existing_accepted_history(
        source_root / "accepted-panels", accepted_root
    )
    panel_name = f"panel-{panel_index:02d}-{family}"
    panel_root = accepted_root / panel_name
    if panel_root.exists() and any(panel_root.iterdir()):
        existing = _optional_json(panel_root / "ACCEPTED-PANEL.json")
        if existing is None:
            raise QFBenchTrajectoryBankError(
                f"partial accepted panel history already exists: {panel_root}"
            )

    repetition_rows: list[dict[str, object]] = []
    for repetition, run_dir_value in enumerate(matched_run_dirs, start=1):
        run_dir = run_dir_value.expanduser().resolve()
        plan = _read_json(run_dir / "pilot-plan.json", label="matched pilot plan")
        report = _read_json(run_dir / "pilot-report.json", label="matched pilot report")
        if report.get("status") != "complete":
            raise QFBenchTrajectoryBankError("matched panel report is not complete")
        if plan.get("task_ids") != normalized_tasks or report.get("task_ids") != normalized_tasks:
            raise QFBenchTrajectoryBankError("matched panel task vector differs")
        arms = plan.get("arms")
        if not isinstance(arms, list) or {
            value.get("label") for value in arms if isinstance(value, Mapping)
        } != {"parent", "candidate"}:
            raise QFBenchTrajectoryBankError("matched panel arms are invalid")
        checkpoint = f"{plan.get('checkpoint_prefix')}-candidate"
        candidate_attempts: dict[str, Path] = {}
        attempts_root = run_dir / "attempts"
        if attempts_root.is_symlink() or not attempts_root.is_dir():
            raise QFBenchTrajectoryBankError("matched run has no attempts directory")
        for attempt in sorted(attempts_root.iterdir(), key=lambda path: path.name):
            record = _optional_json(attempt / "attempt.json")
            if record is None or record.get("checkpoint") != checkpoint:
                continue
            task_id = record.get("task_id")
            if isinstance(task_id, str) and task_id in normalized_tasks:
                if task_id in candidate_attempts:
                    raise QFBenchTrajectoryBankError(
                        f"matched repetition has duplicate candidate task: {task_id}"
                    )
                candidate_attempts[task_id] = attempt
        if set(candidate_attempts) != set(normalized_tasks):
            raise QFBenchTrajectoryBankError(
                "matched repetition has incomplete candidate task histories"
            )
        repetition_root = panel_root / f"repetition-{repetition:02d}" / "tasks"
        for task_id in normalized_tasks:
            _copy_answer_free_attempt(
                candidate_attempts[task_id],
                repetition_root / task_id,
                label=f"panel {panel_index} repetition {repetition} {task_id}",
            )
        repetition_rows.append(
            {
                "repetition": repetition,
                "task_ids": normalized_tasks,
                "trajectory_root": (
                    f"accepted-panels/{panel_name}/repetition-{repetition:02d}/tasks"
                ),
            }
        )

    accepted_record = {
        "schema_version": 1,
        "record_kind": "qrs_accepted_panel_answer_free_history",
        "answer_free": True,
        "worker_visible": False,
        "panel_index": panel_index,
        "family": family,
        "task_ids": normalized_tasks,
        "accepted_claims": clean_claims,
        "repetitions": repetition_rows,
        "excluded_surface_classes": [
            "official scores and rewards",
            "verifier and checker output",
            "Reviewer verdicts and reasons",
            "controller promotion decisions",
        ],
    }
    _assert_answer_free(accepted_record)
    _assert_no_identity_keys(accepted_record)
    _write_json_if_changed(panel_root / "ACCEPTED-PANEL.json", accepted_record)

    entries = _refresh_accepted_history_index(target_root)
    return {
        "schema_version": 1,
        "status": "complete",
        "panel_index": panel_index,
        "family": family,
        "task_ids": normalized_tasks,
        "accepted_claim_count": len(clean_claims),
        "matched_repetition_count": 2,
        "next_evidence_root": str(target_root),
        "answer_free": True,
        "sealed_task_ids_present": [],
        "cost": {},
    }


def build_trajectory_bank(
    *,
    manifest_path: Path,
    scheduler_plan_path: Path,
    public_contracts_root: Path,
    h0_run_dirs: Sequence[Path],
    destination: Path,
    require_complete: bool = False,
) -> dict[str, object]:
    """Build or resume one All-N H0 bank without dispatching any experiment."""

    if not h0_run_dirs:
        raise QFBenchTrajectoryBankError("at least one H0 run directory is required")
    manifest_file = manifest_path.expanduser().resolve()
    plan_file = scheduler_plan_path.expanduser().resolve()
    contracts_root = public_contracts_root.expanduser().resolve()
    target = destination.expanduser().resolve()
    manifest = _read_json(manifest_file, label="QFBench public manifest")
    plan = _read_json(plan_file, label="QFBench scheduler plan")
    arm_identities = plan.get("arm_identities")
    candidate_lineage = (
        arm_identities.get("candidate_lineage")
        if isinstance(arm_identities, Mapping)
        else None
    )
    workflow_contract = plan.get("cross_family_workflow_evidence")
    framework_reference = {
        "schema_version": 1,
        "record_kind": "qrs_frozen_preproposal_workflow_framework",
        "answer_free": True,
        "workflow_scope": (
            workflow_contract.get("workflow_scope") or "workflow_global"
            if isinstance(workflow_contract, Mapping)
            else "workflow_global"
        ),
        "involved_states": (
            workflow_contract.get("involved_states")
            or ["S1", "S2", "S3", "S4", "S5", "S6"]
            if isinstance(workflow_contract, Mapping)
            else ["S1", "S2", "S3", "S4", "S5", "S6"]
        ),
        "minimum_distinct_trajectory_tasks": 2,
        "minimum_distinct_task_families": 2,
        "allowed_search_loci": ["skills", "systemprompt"],
        "allowed_change": (
            candidate_lineage.get("allowed_change")
            if isinstance(candidate_lineage, Mapping)
            else (
                "One task-agnostic clarification of the six-stage quantitative "
                "workflow."
            )
        ),
        "forbidden_change": (
            candidate_lineage.get("forbidden_change")
            if isinstance(candidate_lineage, Mapping)
            else (
                "Task-specific formulas, outputs, constants, routing, evaluator "
                "predicates, or hidden outcomes."
            )
        ),
        "evidence_boundary": (
            "Answer-free development observations may ground a reusable workflow "
            "hypothesis and its empirical origin. They do not establish correctness "
            "or utility; utility is decided only by the later matched gate."
        ),
    }
    _assert_answer_free(framework_reference)
    _assert_no_identity_keys(framework_reference)
    manifest_tasks = _task_metadata(manifest)
    panels, anchors, sealed_ids = _plan_layout(
        plan,
        manifest_tasks=manifest_tasks,
    )
    development_ids = {
        task_id
        for panel in panels
        for task_id in panel["task_ids"]
        if isinstance(task_id, str)
    }
    histories, unassigned, sealed_history_count, unrelated_history_count = (
        _discover_histories(
            h0_run_dirs,
            development_ids=development_ids,
            sealed_ids=sealed_ids,
        )
    )

    outputs: dict[Path, object] = {}
    text_outputs: dict[Path, str] = {}
    controller_task_rows: list[dict[str, object]] = []
    evolver_task_rows: list[dict[str, object]] = []
    missing_tasks: list[str] = []
    invalid_only_tasks: list[str] = []
    ambiguous_tasks: list[str] = []
    incomplete_contracts: list[str] = []
    history_count = 0
    valid_history_count = 0
    invalid_history_count = 0

    for task_id in sorted(development_ids):
        metadata = dict(manifest_tasks[task_id])
        contracts = _contract_paths(contracts_root, task_id)
        if not contracts["complete"]:
            incomplete_contracts.append(task_id)
        task_attempts = histories.get(task_id, [])
        controller_histories: list[dict[str, object]] = []
        evolver_histories: list[dict[str, object]] = []
        for ordinal, attempt in enumerate(task_attempts, start=1):
            history_key = f"{task_id}--history-{ordinal:02d}"
            answer_free, controller = _history_base(attempt)
            answer_free["history_key"] = history_key
            controller["history_key"] = history_key
            controller["controller_only_evaluation"] = _controller_verifier(attempt)
            evolver_histories.append(answer_free)
            controller_histories.append(controller)
            history_count += 1
            if answer_free["runtime_status"] == "valid":
                valid_history_count += 1
            else:
                invalid_history_count += 1
        task_valid_count = sum(
            history["runtime_status"] == "valid" for history in evolver_histories
        )
        if not task_attempts:
            bank_status = "missing"
            missing_tasks.append(task_id)
        elif task_valid_count == 0:
            bank_status = "invalid_only"
            invalid_only_tasks.append(task_id)
        elif task_valid_count > 1:
            bank_status = "ambiguous_multiple_valid_histories"
            ambiguous_tasks.append(task_id)
        else:
            bank_status = "ready"

        controller_packet = {
            "schema_version": 1,
            "record_kind": "qfbench_h0_controller_task_packet",
            "access_surface": "controller_only",
            "task": metadata,
            "public_contract": contracts,
            "bank_status": bank_status,
            "history_count": len(controller_histories),
            "valid_runtime_history_count": task_valid_count,
            "histories": controller_histories,
        }
        evolver_packet = {
            "schema_version": 1,
            "record_kind": "qfbench_h0_answer_free_task_packet",
            "access_surface": "evolver_answer_free",
            "answer_free": True,
            "task": metadata,
            "public_contract": contracts,
            "bank_status": bank_status,
            "history_count": len(evolver_histories),
            "valid_runtime_history_count": task_valid_count,
            "histories": evolver_histories,
            "excluded_surface_classes": [
                "official scores and rewards",
                "passed or failed property counts",
                "verifier and CTRF files",
                "checker output and expected values",
                "optimization diagnostics",
                "sealed tasks and histories",
            ],
        }
        controller_path = (
            target / _CONTROLLER_ROOT / "tasks" / f"{task_id}.json"
        )
        evolver_path = target / _EVOLVER_ROOT / "tasks" / f"{task_id}.json"
        outputs[controller_path] = controller_packet
        outputs[evolver_path] = evolver_packet
        controller_task_rows.append(
            {
                **metadata,
                "bank_status": bank_status,
                "history_count": len(controller_histories),
                "task_packet": _relative_output(controller_path, target),
            }
        )
        evolver_task_rows.append(
            {
                **metadata,
                "bank_status": bank_status,
                "history_count": len(evolver_histories),
                "task_packet": _relative_output(evolver_path, target),
            }
        )

    panel_rows: list[dict[str, object]] = []
    for panel in panels:
        panel_index = int(panel["panel_index"])
        family = str(panel["family"])
        focus_task_ids = list(panel["task_ids"])
        cross_family_anchors = [
            {
                "family": anchor_family,
                "task_id": anchors[anchor_family],
            }
            for anchor_family in sorted(anchors)
            if anchor_family != family
        ]
        visible_task_ids = sorted(
            set(focus_task_ids)
            | {str(anchor["task_id"]) for anchor in cross_family_anchors}
        )
        panel_view = {
            "schema_version": 1,
            "record_kind": "qfbench_h0_answer_free_panel_view",
            "access_surface": "evolver_answer_free",
            "answer_free": True,
            "panel_index": panel_index,
            "focus_family": family,
            "focus_task_ids": focus_task_ids,
            "cross_family_anchors": cross_family_anchors,
            "visible_task_ids": visible_task_ids,
            "visible_family_count": len(
                {
                    str(manifest_tasks[task_id]["family"])
                    for task_id in visible_task_ids
                }
            ),
            "task_packets": [
                f"{_EVOLVER_ROOT}/tasks/{task_id}.json"
                for task_id in visible_task_ids
            ],
            "exposure_rule": (
                "Expose this bounded view only in its scheduled panel round. "
                "The complete bank remains controller-side."
            ),
            "excluded_surface_classes": [
                "controller-only evaluation",
                "later sealed work",
                "answer-rich diagnostics",
            ],
        }
        panel_path = (
            target
            / _EVOLVER_ROOT
            / "panels"
            / f"panel-{panel_index:02d}-{family}.json"
        )
        outputs[panel_path] = panel_view

        panel_valid_attempts: dict[str, tuple[Path, dict[str, object]]] = {}
        panel_evidence_ready = True
        for task_id in visible_task_ids:
            contract = _contract_paths(contracts_root, task_id)
            valid_attempts: list[tuple[Path, dict[str, object]]] = []
            for attempt in histories.get(task_id, []):
                answer_free, _controller = _history_base(attempt)
                if answer_free["runtime_status"] == "valid":
                    valid_attempts.append((attempt, answer_free))
            if not contract["complete"] or len(valid_attempts) != 1:
                panel_evidence_ready = False
            elif valid_attempts:
                panel_valid_attempts[task_id] = valid_attempts[0]
        if not panel_evidence_ready:
            panel_rows.append(
                {
                    "panel_index": panel_index,
                    "focus_family": family,
                    "focus_task_count": len(focus_task_ids),
                    "cross_family_anchor_count": len(cross_family_anchors),
                    "panel_view": _relative_output(panel_path, target),
                    "evidence_root": None,
                }
            )
            continue

        evidence_root = (
            target
            / _EVOLVER_ROOT
            / "panel-evidence"
            / f"panel-{panel_index:02d}-{family}"
        )
        text_outputs[evidence_root / "access_log.jsonl"] = ""
        outputs[
            evidence_root / "guidance/qrs-workflow-framework.json"
        ] = framework_reference
        task_cards: list[dict[str, object]] = []
        task_keys: list[str] = []
        task_family_by_key: dict[str, str] = {}
        task_evidence_prefixes: dict[str, list[str]] = {}
        for task_id in visible_task_ids:
            task_key = f"qfbench:{task_id}"
            task_keys.append(task_key)
            task_family = str(manifest_tasks[task_id]["family"])
            task_family_by_key[task_key] = task_family
            task_prefix = f"benchmarks/qfbench/tasks/{task_id}/"
            task_evidence_prefixes[task_key] = [
                task_prefix,
                f"tasks/cards/qfbench--{task_id}.json",
            ]
            contract = _contract_paths(contracts_root, task_id)
            instruction_source = Path(str(contract["instruction_path"]))
            clauses_source = Path(str(contract["public_clauses_path"]))
            task_root = evidence_root / "benchmarks/qfbench/tasks" / task_id
            text_outputs[task_root / "instruction.md"] = _read_public_text(
                instruction_source, label=f"{task_id} public instruction"
            )
            clauses = _without_identity_fields(
                _read_json(clauses_source, label=f"{task_id} public clauses")
            )
            outputs[task_root / "public_clauses.json"] = clauses

            attempt, answer_free = panel_valid_attempts[task_id]
            trace_source = Path(str(answer_free["trace"]["path"]))
            final_source = Path(str(answer_free["final"]["path"]))
            text_outputs[task_root / "worker_trace.jsonl"] = _read_public_text(
                trace_source, label=f"{task_id} Worker trace"
            )
            text_outputs[task_root / "worker_final.txt"] = _read_public_text(
                final_source, label=f"{task_id} Worker final"
            )
            state_trace = answer_free.get("research_state_trace")
            if isinstance(state_trace, Mapping):
                state_source = Path(str(state_trace["path"]))
                state_payload = _without_identity_fields(
                    _read_json(state_source, label=f"{task_id} research state trace")
                )
                outputs[task_root / "research_state_trace.json"] = state_payload
            outputs[task_root / "process_summary.json"] = answer_free[
                "runtime_summary"
            ]
            artifact_root = task_root / "artifacts"
            for artifact in answer_free["artifacts"]:
                relative = Path(str(artifact["relative_path"]))
                if relative.is_absolute() or ".." in relative.parts:
                    raise QFBenchTrajectoryBankError(
                        f"unsafe artifact path for {task_id}: {relative}"
                    )
                source = Path(str(artifact["path"]))
                text_outputs[artifact_root / relative] = _read_public_text(
                    source, label=f"{task_id} artifact {relative}"
                )
            outputs[task_root / "artifact_manifest.json"] = {
                "schema_version": 1,
                "artifact_state": answer_free["artifact_state"],
                "artifacts": [
                    {
                        "relative_path": str(value["relative_path"]),
                        "size_bytes": value["size_bytes"],
                    }
                    for value in answer_free["artifacts"]
                ],
            }
            evidence_paths = {
                "instruction": f"{task_prefix}instruction.md",
                "public_clauses": f"{task_prefix}public_clauses.json",
                "worker_trace": f"{task_prefix}worker_trace.jsonl",
                "worker_final": f"{task_prefix}worker_final.txt",
                "process_summary": f"{task_prefix}process_summary.json",
                "artifact_manifest": f"{task_prefix}artifact_manifest.json",
            }
            if isinstance(state_trace, Mapping):
                evidence_paths["research_state_trace"] = (
                    f"{task_prefix}research_state_trace.json"
                )
            card = {
                "schema_version": 1,
                "task_key": task_key,
                "benchmark": "qfbench",
                "task_id": task_id,
                "family": task_family,
                "role": "focus" if task_id in focus_task_ids else "anchor",
                "feedback_mode": "answer_free",
                "trajectory_source": "fresh_frozen_h0",
                "evidence_paths": evidence_paths,
            }
            task_cards.append(card)
            outputs[evidence_root / "tasks/cards" / f"qfbench--{task_id}.json"] = card

        outputs[evidence_root / "tasks/CATALOG.json"] = {
            "schema_version": 1,
            "task_count": len(task_cards),
            "tasks": task_cards,
        }
        outputs[evidence_root / "tasks/RELEVANT_COMPONENTS.json"] = {
            "schema_version": 1,
            "history_enabled": False,
            "task_keys": task_keys,
            "tasks": [],
        }
        outputs[evidence_root / "components/CATALOG.json"] = {
            "schema_version": 1,
            "component_count": 0,
            "components": [],
            "catalog_policy": "no_candidate_history",
        }
        outputs[evidence_root / "contract.json"] = {
            "schema_version": 1,
            "stage": "COORDINATED_BREADTH",
            "contract_arm": "quant-state",
            "answer_free": True,
            "decision_protocol": "quant_property_v2",
            "feedback_tier": "answer_free_global_h0_trajectory_bank_v1",
            "optimization_answers_exposed_to_evolver": False,
            "optimization_answers_exposed_to_worker": False,
            "component_history_enabled": False,
            "task_keys": task_keys,
            "task_ids": visible_task_ids,
            "focus_task_keys": [
                f"qfbench:{task_id}" for task_id in focus_task_ids
            ],
            "task_family_by_key": task_family_by_key,
            "task_evidence_prefixes": task_evidence_prefixes,
            "workflow_scope_required_for_act": True,
            "research_state_transition_required_for_act": True,
            "quant_research_state_card_required_for_act": True,
            "worker_visible_claim_provenance_required_for_act": True,
            "coordinated_evidence_required_for_act": False,
            "probe_task_selection_required_for_act": False,
            "history_required": False,
            "max_primary_components": 2,
            "max_declared_components": 2,
            "allowed_candidate_components": ["skills", "systemprompt"],
            "allowed_candidate_paths": [
                "skills/quant-research-six-stage-workflow/SKILL.md",
                "systemprompt.md",
            ],
            "candidate_goal": (
                "Use the complete focus-family Primitive-H0 histories and the "
                "cross-family anchors present in this panel to propose at most one task-agnostic "
                "workflow_global clarification in only the six-stage skill and/or "
                "system prompt. Cite at least two inspected fresh H0 trajectories "
                "from different families. Do not encode a task answer, task ID, "
                "official outcome, failed property, expected value, or checker rule."
            ),
            "framework_reference": "guidance/qrs-workflow-framework.json",
        }
        panel_rows.append(
            {
                "panel_index": panel_index,
                "focus_family": family,
                "focus_task_count": len(focus_task_ids),
                "cross_family_anchor_count": len(cross_family_anchors),
                "panel_view": _relative_output(panel_path, target),
                "evidence_root": _relative_output(evidence_root, target),
            }
        )

    unassigned_rows: list[dict[str, object]] = []
    for ordinal, attempt in enumerate(sorted(unassigned, key=str), start=1):
        answer_free, controller = _history_base(attempt)
        controller["history_key"] = f"unassigned-history-{ordinal:02d}"
        controller["controller_only_evaluation"] = _controller_verifier(attempt)
        unassigned_rows.append(controller)
    unassigned_path = target / _CONTROLLER_ROOT / "unassigned-histories.json"
    outputs[unassigned_path] = {
        "schema_version": 1,
        "record_kind": "qfbench_h0_unassigned_histories",
        "access_surface": "controller_only",
        "history_count": len(unassigned_rows),
        "histories": unassigned_rows,
    }

    bank_complete = not (
        missing_tasks
        or invalid_only_tasks
        or ambiguous_tasks
        or incomplete_contracts
        or unassigned_rows
    )
    controller_index_path = target / _CONTROLLER_ROOT / "bank-index.json"
    evolver_index_path = target / _EVOLVER_ROOT / "bank-index.json"
    outputs[controller_index_path] = {
        "schema_version": 1,
        "record_kind": "qfbench_h0_controller_bank_index",
        "access_surface": "controller_only",
        "complete": bank_complete,
        "expected_task_count": len(development_ids),
        "task_count_with_history": len(development_ids) - len(missing_tasks),
        "history_count": history_count,
        "valid_runtime_history_count": valid_history_count,
        "invalid_runtime_history_count": invalid_history_count,
        "missing_task_ids": missing_tasks,
        "invalid_only_task_ids": invalid_only_tasks,
        "ambiguous_multiple_valid_history_task_ids": ambiguous_tasks,
        "incomplete_public_contract_task_ids": incomplete_contracts,
        "unassigned_history_count": len(unassigned_rows),
        "sealed_history_count_excluded": sealed_history_count,
        "unrelated_history_count_excluded": unrelated_history_count,
        "tasks": controller_task_rows,
    }
    evolver_index = {
        "schema_version": 1,
        "record_kind": "qfbench_h0_answer_free_bank_index",
        "access_surface": "evolver_answer_free",
        "answer_free": True,
        "complete": bank_complete,
        "expected_task_count": len(development_ids),
        "task_count_with_history": len(development_ids) - len(missing_tasks),
        "history_count": history_count,
        "tasks": evolver_task_rows,
        "panels": panel_rows,
        "controller_only_surface_exposed": False,
    }
    outputs[evolver_index_path] = evolver_index
    outputs[target / "BANK-MANIFEST.json"] = {
        "schema_version": 1,
        "record_kind": "qfbench_all_n_h0_trajectory_bank",
        "complete": bank_complete,
        "resume_policy": "rebuild_missing_or_changed_json_in_place",
        "source_policy": "completed H0 run directories; no model dispatch",
        "expected_task_count": len(development_ids),
        "panel_count": len(panels),
        "controller_index": _relative_output(controller_index_path, target),
        "evolver_index": _relative_output(evolver_index_path, target),
        "surface_boundary": {
            "controller_only": (
                "official scores, rewards, verifier files, all runtime histories"
            ),
            "evolver_answer_free": (
                "public contracts plus blind H0 traces, finals, artifacts, "
                "state telemetry, and runtime status"
            ),
        },
        "sealed_policy": (
            "Sealed task identities, contracts, histories, artifacts, scores, "
            "and verifier records are absent from this bank."
        ),
    }

    for path, value in outputs.items():
        _assert_no_identity_keys(value)
        if _EVOLVER_ROOT in path.parts:
            _assert_answer_free(value)
    for path, text in text_outputs.items():
        if _EVOLVER_ROOT in path.parts:
            _assert_answer_free(text)
    written = 0
    unchanged = 0
    for path in sorted(outputs, key=str):
        if _write_json_if_changed(path, outputs[path]):
            written += 1
        else:
            unchanged += 1
    for path in sorted(text_outputs, key=str):
        if _write_text_if_changed(path, text_outputs[path]):
            written += 1
        else:
            unchanged += 1

    report = {
        "schema_version": 1,
        "destination": str(target),
        "complete": bank_complete,
        "expected_task_count": len(development_ids),
        "task_count_with_history": len(development_ids) - len(missing_tasks),
        "history_count": history_count,
        "valid_runtime_history_count": valid_history_count,
        "invalid_runtime_history_count": invalid_history_count,
        "excluded_sealed_history_count": sealed_history_count,
        "files_written": written,
        "files_unchanged": unchanged,
    }
    if require_complete and not bank_complete:
        raise QFBenchTrajectoryBankError(
            "trajectory bank is incomplete; inspect controller-only/bank-index.json"
        )
    return report


__all__ = [
    "QFBenchTrajectoryBankError",
    "build_trajectory_bank",
]
