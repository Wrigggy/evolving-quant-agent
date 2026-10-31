"""One BacktestBench revision through the existing full-H Evolver.

The source is a completed blind Worker panel. Only declared train tasks, their
own original artifacts/traces, and binary outcomes enter the Evolver evidence.
One shared public market archive is transported without gold or judge files.
The native ACT/ABSTAIN interface, full-H admission, and actual R transport are
reused. A revised package stays unscored until a separately declared fresh panel.
An explicit separately registered opt-in may add scalar train supervision for
the Evolver only; the default and every earlier condition remain answer-free.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import partial
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import time
from typing import Mapping, Sequence

from .backtestbench_panel import STATE_FILE as PANEL_STATE_FILE
from .benchmarks.backtestbench import inspect_market_archive, project_public_task
from .evaluation import TaskAttempt
from .evolution_evidence import EvidenceRecord, authorize_evidence_tree
from .executors.execution_record import load_worker_execution
from .qfbench_research_episode import _usage_accounting
from .quantcodeeval_baseline import _atomic_private_json
from .quantcodeeval_behavior_revision import _prepare_revision_runtime, _qualify_revision

# Original multi-round evidence is more numerous than the mutable candidate files.
# Bound its transport separately; candidate/output and byte limits stay unchanged.
RESEARCH_INDEX_MAX_INPUT_FILES = 8192
from .quantcodeeval_v2_evidence import EARLY_INTERVENTION_FULL_HARNESS_PROFILE
from .quantcodeeval_v2_live import _materialize_evolver_profile
from .quantcodeeval_worker_observation import _failure_payload, _proxy_cost_evidence, _relative
from .research_operation_memory import (
    MEMORY_RESULT_NAME, compact_research_operation_index,
    copy_research_operation_memory, load_research_operation_memory,
)
from .rootless_full_harness import _CoordinatorLock


PREFLIGHT_FILE = "BACKTESTBENCH-REVISION-PREFLIGHT.json"
DISPATCH_FILE = "BACKTESTBENCH-REVISION-DISPATCH.json"
RESULT_FILE = "BACKTESTBENCH-REVISION-RESULT.json"
PROTOCOL = "backtestbench-public-full-harness-revision-v1"
MARKET_ARCHIVE = "public/shared-data/stock_tables.zip"
TRAIN_SUPERVISION_PROTOCOL = "backtestbench-evolver-only-train-scalar-supervision-v1"
TRAIN_SUPERVISION_PATH = "declared-training-supervision/targets.json"
TRAIN_SUPERVISION_TIER = "answer_rich_optimization_v1"
PROFILE = EARLY_INTERVENTION_FULL_HARNESS_PROFILE
MEMORY_INDEX_MODES = ("inline", "directory_v1")
MEMORY_INDEX_PATH = "research-memory/index.json"
_ROLES = (
    "systemprompt", "agent_config", "tool_descriptions", "tools", "validator",
    "skills", "memory", "middleware", "routing",
)


class BacktestBenchRevisionError(ValueError):
    """A revision lacks its original public Worker evidence or declared parent."""


@dataclass(frozen=True)
class PreparedBacktestBenchRevision:
    root: Path
    candidate_dir: Path
    evidence: EvidenceRecord
    diagnosis: dict
    research_memory_path: Path
    plan: dict


def _read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise BacktestBenchRevisionError(f"required record is missing or unsafe: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BacktestBenchRevisionError("expected a JSON object")
    return value


def _copy_text(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise BacktestBenchRevisionError(f"public evidence is not a regular file: {source}")
    payload = source.read_bytes()
    payload.decode("utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)


def _load_prepared(root: Path, plan: dict) -> PreparedBacktestBenchRevision:
    if plan.get("memory_index_mode") == "directory_v1":
        evidence_root = root / "prepared/evidence"
        directory = _read(evidence_root / "contract.json")["research_operation_memory"]["index"]
        index_path = evidence_root / MEMORY_INDEX_PATH
        if (directory.get("mode") != "directory_v1"
                or directory.get("source") != "evidence"
                or directory.get("path") != MEMORY_INDEX_PATH
                or index_path.is_symlink() or not index_path.is_file()
                or hashlib.sha256(index_path.read_bytes()).hexdigest() != directory.get("sha256")):
            raise BacktestBenchRevisionError("retained research-memory directory differs")
    if "continuation_context" in plan:
        if _read(root / "prepared/evidence/continuation/context.json") != plan["continuation_context"]:
            raise BacktestBenchRevisionError("retained continuation context differs")
    if plan.get("training_scalar_supervision"):
        binding = plan["training_scalar_supervision"]
        targets = root / "prepared/evidence" / TRAIN_SUPERVISION_PATH
        if targets.is_symlink() or hashlib.sha256(targets.read_bytes()).hexdigest() != binding["source_sha256"]:
            raise BacktestBenchRevisionError("retained declared train scalar supervision differs")
    if plan.get("selected_research_units"):
        evidence_root = root / "prepared" / "evidence"
        catalog = _read(evidence_root / "selected-research-units/catalog.json")
        if catalog["units"] != plan["selected_research_units"]:
            raise BacktestBenchRevisionError("retained selected research-unit identities differ")
        sources = {record["complete_trace"]: record for record in plan["selected_research_units"]}
        if [item["path"] for item in catalog["source_traces"]] != list(sources):
            raise BacktestBenchRevisionError("retained selected complete-trace identities differ")
        for record in plan["selected_research_units"]:
            path = evidence_root / record["path"]
            if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record["unit_sha256"]:
                raise BacktestBenchRevisionError("retained selected research-unit bytes differ")
        for item in catalog["source_traces"]:
            record = sources[item["path"]]
            path = evidence_root / item["path"]
            if (item["sha256"] != record["source_trace_sha256"]
                    or item["bytes"] != record["source_trace_bytes"]
                    or item["source_attempt"] != record["source_attempt"]
                    or item["source_panel_id"] != record["source_panel_id"]
                    or path.is_symlink() or not path.is_file()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]):
                raise BacktestBenchRevisionError("retained selected complete-trace bytes or identities differ")
            access = item["worker_trace_access"]
            if access.get("source") != item["path"] or access.get("source_bytes") != item["bytes"]:
                raise BacktestBenchRevisionError("retained selected complete-trace access differs")
            if access["mode"] == "ordered_utf8_text_fragments":
                parts_root = path.parent / "worker-trace-parts"
                part_catalog = _read(parts_root / "catalog.json")
                refs = [part["path"] for part in part_catalog["parts"]]
                expected = [(parts_root / f"worker-trace-part-{ordinal:04d}.txt").relative_to(evidence_root).as_posix()
                            for ordinal in range(1, len(refs) + 1)]
                if (access.get("catalog") != (parts_root / "catalog.json").relative_to(evidence_root).as_posix()
                        or refs != expected or refs != access.get("parts")
                        or part_catalog.get("source_path") != item["path"]
                        or part_catalog.get("lossless") is not True
                        or any((evidence_root / ref).is_symlink() for ref in refs)
                        or b"".join((evidence_root / ref).read_bytes() for ref in refs) != path.read_bytes()):
                    raise BacktestBenchRevisionError("retained selected complete-trace parts differ")
    evidence = authorize_evidence_tree(
        root / "prepared" / "evidence", backtestbench_market_archive=MARKET_ARCHIVE,
    )
    return PreparedBacktestBenchRevision(
        root, root / "prepared" / "candidate", evidence,
        _read(root / "prepared" / "diagnosis.json"),
        evidence.root / "research-memory" / "snapshot.json", plan,
    )


def _inspect_training_scalar_supervision(path, *, run_id, state, evidence_task_ids):
    """Accept only an explicitly supplied sanitized manifest, never a trusted tree."""
    supplied = Path(path).expanduser()
    if any(member.is_symlink() for member in (supplied, *supplied.parents)):
        raise BacktestBenchRevisionError("declared scalar supervision source must not have symlink ancestors")
    path = supplied.resolve()
    value = _read(path)
    if (set(value) != {"protocol", "run_id", "source_split", "task_ids", "rows"}
            or value["protocol"] != TRAIN_SUPERVISION_PROTOCOL or value["run_id"] != run_id
            or value["source_split"] != "train" or value["task_ids"] != list(evidence_task_ids)
            or len(evidence_task_ids) != 8 or not isinstance(value["rows"], list)
            or len(value["rows"]) != len(evidence_task_ids)):
        raise BacktestBenchRevisionError("declared scalar supervision must bind the exact eight train tasks")
    keys = {"task_id", "uuid", "source_split", "source_row", "strategy_type", "answer", "source_answer_sha256"}
    for task_id, row in zip(evidence_task_ids, value["rows"]):
        public = state["tasks"][task_id]["public_task"]
        if (not isinstance(row, dict) or set(row) != keys or row["task_id"] != task_id
                or row["source_split"] != "train" or public["source_split"] != "train"
                or any(row[key] != public[key] for key in ("uuid", "source_split", "source_row", "strategy_type"))
                or not isinstance(row["source_answer_sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", row["source_answer_sha256"]) is None
                or type(row["answer"]) not in {int, float, str}
                or (type(row["answer"]) is float and not math.isfinite(row["answer"]))):
            raise BacktestBenchRevisionError("scalar supervision contains a non-scalar, non-train or unknown field")
    return {
        "protocol": TRAIN_SUPERVISION_PROTOCOL, "source_manifest": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "path": TRAIN_SUPERVISION_PATH,
        "task_ids": list(evidence_task_ids), "visibility": "evolver_only", "scalar_only": True,
        "public_probe_data_included": False, "worker_inputs_included": False,
        "validation_targets_included": False, "test_targets_included": False,
        "sql_or_reference_code_included": False,
    }


def _inspect_selected_research_units(units, *, current_state, evidence_task_ids):
    """Resolve optional investigator-selected raw rows, never derive a finding."""
    records, payloads, seen = [], {}, set()
    keys = {"unit_id", "panel_run_dir", "task_id", "start_line", "end_line"}
    for unit in units:
        if not isinstance(unit, Mapping) or set(unit) != keys:
            raise BacktestBenchRevisionError("selected research unit requires exact source and row-range fields")
        unit_id, task_id = unit["unit_id"], unit["task_id"]
        if not isinstance(unit_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", unit_id) or unit_id in seen:
            raise BacktestBenchRevisionError("selected research-unit ID is unsafe or repeated")
        seen.add(unit_id)
        if task_id not in evidence_task_ids:
            raise BacktestBenchRevisionError("selected research unit is outside the declared train evidence")
        source_root = Path(unit["panel_run_dir"]).expanduser().resolve()
        source = _read(source_root / PANEL_STATE_FILE)
        if source.get("status") not in {"complete", "complete_with_failures"}:
            raise BacktestBenchRevisionError("selected research-unit source panel is not terminal")
        cell = source["tasks"][task_id]
        row = cell["public_task"]
        current = current_state["tasks"][task_id]["public_task"]
        if row["source_split"] != "train" or current["source_split"] != "train":
            raise BacktestBenchRevisionError("selected research units may contain train tasks only")
        public = project_public_task(row, source_split="train", source_row=row["source_row"])
        current_public = project_public_task(current, source_split="train", source_row=current["source_row"])
        if public.task_id != task_id or public.public_record() != current_public.public_record():
            raise BacktestBenchRevisionError("selected research-unit public task identity differs")
        attempt = TaskAttempt(**cell["attempt"])
        if (attempt.task_id != task_id or attempt.run_id != source["run_id"]
                or attempt.benchmark_commit != current_state["tasks"][task_id]["attempt"]["benchmark_commit"]):
            raise BacktestBenchRevisionError("selected research-unit attempt task or panel differs")
        attempt_dir = source_root / "attempts" / attempt.attempt_id
        if _read(attempt_dir / "attempt.json") != asdict(attempt):
            raise BacktestBenchRevisionError("selected research-unit original attempt identity differs")
        execution = load_worker_execution(attempt, source_root)
        if execution is None or not execution.cleaned_up:
            raise BacktestBenchRevisionError("selected research-unit original Worker delivery is unavailable")
        trace = Path(execution.trace_uri)
        if not trace.resolve().is_relative_to(attempt_dir.resolve()) or trace.is_symlink() or not trace.is_file():
            raise BacktestBenchRevisionError("selected research-unit trace is unsafe or outside its original attempt")
        raw = trace.read_bytes()
        raw.decode("utf-8")
        lines = raw.splitlines(keepends=True)
        start, end = unit["start_line"], unit["end_line"]
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            raise BacktestBenchRevisionError("selected research-unit raw row range is invalid")
        payload = b"".join(lines[start - 1:end])
        if len(payload) > 64000:
            raise BacktestBenchRevisionError("selected research unit exceeds the existing guarded read output bound")
        for line in lines[start - 1:end]:
            if not isinstance(json.loads(line), dict):
                raise BacktestBenchRevisionError("selected research-unit source is not original JSONL records")
        path = f"selected-research-units/{unit_id}/raw.jsonl"
        source_key = hashlib.sha256(json.dumps(
            [source["run_id"], attempt.attempt_id], separators=(",", ":"),
        ).encode()).hexdigest()
        complete_trace = f"selected-research-units/source-traces/{source_key}/worker_trace.jsonl"
        record = {
            **dict(unit), "panel_run_dir": str(source_root), "path": path,
            "complete_trace": complete_trace,
            "source_panel_id": source["run_id"], "source_attempt": asdict(attempt),
            "source_harness": source["declaration"]["full_harness"],
            "source_trace": trace.resolve().relative_to(source_root).as_posix(),
            "source_trace_sha256": hashlib.sha256(raw).hexdigest(),
            "source_trace_bytes": len(raw), "unit_sha256": hashlib.sha256(payload).hexdigest(),
            "unit_bytes": len(payload), "projection": "unmodified_original_raw_jsonl_rows",
        }
        records.append(record)
        payloads[path] = payload
        payloads[complete_trace] = raw
    return records, payloads


def prepare_backtestbench_revision(
    *, panel_run_dir: str | Path, revision_run_dir: str | Path,
    worker_dir: str | Path, active_task_id: str, evidence_task_ids: Sequence[str],
    research_memory_path: str | Path,
    completed_pair: Mapping[str, str | Path] | None = None,
    readable_trace_task_ids: Sequence[str] = (),
    selected_research_units: Sequence[Mapping[str, object]] = (),
    training_scalar_supervision_path: str | Path | None = None,
    continuation_context: Mapping[str, object] | None = None,
    research_index_path: str | Path | None = None,
    memory_index_mode: str = "inline",
    candidate_components: Sequence[str] = (),
) -> PreparedBacktestBenchRevision:
    """Prepare original train evidence only; never construct a model runtime."""
    panel_root = Path(panel_run_dir).expanduser().resolve()
    root = Path(revision_run_dir).expanduser().resolve()
    parent = Path(worker_dir).expanduser().resolve()
    memory = Path(research_memory_path).expanduser().resolve()
    if memory_index_mode not in MEMORY_INDEX_MODES:
        raise BacktestBenchRevisionError("unknown research-memory index mode")
    if not evidence_task_ids or len(set(evidence_task_ids)) != len(evidence_task_ids):
        raise BacktestBenchRevisionError("declare unique, nonempty evidence task IDs")
    if active_task_id not in evidence_task_ids:
        raise BacktestBenchRevisionError("active task is outside the declared evidence panel")
    if not set(readable_trace_task_ids) <= set(evidence_task_ids):
        raise BacktestBenchRevisionError("readable traces must belong to the declared evidence panel")
    state = _read(panel_root / PANEL_STATE_FILE)
    if state.get("status") not in {"complete", "complete_with_failures"}:
        raise BacktestBenchRevisionError("baseline panel is not terminal")
    if parent != Path(state["declaration"]["full_harness"]["worker_dir"]).resolve():
        raise BacktestBenchRevisionError("parent H differs from the original blind panel")
    pair = None
    if completed_pair is not None:
        from .backtestbench_completed_pair import inspect_completed_pair

        pair = inspect_completed_pair(
            completed_pair, current_panel_root=panel_root, current_state=state,
            parent=parent, memory=memory, evidence_task_ids=evidence_task_ids,
        )
    observation_namespace = "current-observations" if pair is not None else "observations"
    plan = {
        "protocol": PROTOCOL, "panel_run_dir": str(panel_root),
        "source_panel_id": state["run_id"], "worker_dir": str(parent),
        "source_parent_harness": state["declaration"]["full_harness"],
        "active_task_id": active_task_id, "evidence_task_ids": list(evidence_task_ids),
        "research_memory_source": str(memory), "evolver_profile": PROFILE,
        "worker_settings": state["worker_settings"],
        "source_scoring_mode": state["declaration"]["scoring_mode"],
        "feedback_contents": "public_inputs_original_worker_artifacts_traces_binary_outcomes",
        "trusted_answers_included": False,
    }
    if memory_index_mode != "inline":
        plan["memory_index_mode"] = memory_index_mode
    if candidate_components:
        plan["candidate_components"] = list(candidate_components)
    if research_index_path is not None:
        from .backtestbench_research_index import inspect_index, INDEX_FILE
        index_root = Path(research_index_path).expanduser().resolve()
        inspect_index(index_root, allowed_task_ids=evidence_task_ids)
        plan["research_index"] = {"source":str(index_root),
            "sha256":hashlib.sha256((index_root / INDEX_FILE).read_bytes()).hexdigest()}
    if continuation_context is not None:
        from .campaign_continuation import ACTIONS
        scheduled = (continuation_context.get("decision") == "DEFER_REVIEW_CONTINUE_CANDIDATE"
                     and continuation_context.get("llm_review_performed") is False)
        if ((continuation_context.get("decision") not in ACTIONS and not scheduled)
                or not isinstance(continuation_context.get("next_intent"), str)
                or not isinstance(continuation_context.get("reason"), str)):
            raise BacktestBenchRevisionError("continuation context is invalid")
        plan["continuation_context"] = dict(continuation_context)
    supervision = None
    if training_scalar_supervision_path is not None:
        supervision = _inspect_training_scalar_supervision(
            training_scalar_supervision_path, run_id=root.name, state=state, evidence_task_ids=evidence_task_ids,
        )
        plan.update(training_scalar_supervision=supervision, trusted_answers_included=True,
                    feedback_tier=TRAIN_SUPERVISION_TIER, answer_free=False,
                    feedback_contents="public_inputs_original_worker_artifacts_traces_binary_outcomes_plus_declared_train_scalar_targets")
    if pair is not None:
        plan["completed_pair"] = pair["reference"]
    if readable_trace_task_ids:
        plan["readable_trace_task_ids"] = list(readable_trace_task_ids)
    selected, unit_payloads = _inspect_selected_research_units(
        selected_research_units, current_state=state, evidence_task_ids=evidence_task_ids,
    )
    if selected:
        plan["selected_research_units"] = selected
    root.mkdir(parents=True, exist_ok=True)
    preflight = root / PREFLIGHT_FILE
    if preflight.exists():
        retained = _read(preflight)
        if retained != plan:
            raise BacktestBenchRevisionError("retained revision preparation differs")
        return _load_prepared(root, retained)
    if (root / "prepared").exists():
        raise BacktestBenchRevisionError("incomplete preparation retained; root recovery is required")

    cells = {task_id: state["tasks"][task_id] for task_id in evidence_task_ids}
    public_tasks = {}
    for task_id, cell in cells.items():
        if cell["public_task"]["source_split"] != "train":
            raise BacktestBenchRevisionError("validation and test tasks cannot enter optimization evidence")
        if not isinstance(cell.get("result"), dict):
            raise BacktestBenchRevisionError("declared source task has no retained result")
        task = project_public_task(
            cell["public_task"], source_split="train", source_row=cell["public_task"]["source_row"],
        )
        if task.task_id != task_id:
            raise BacktestBenchRevisionError("source public task identity differs")
        public_tasks[task_id] = task.public_record()
    active = cells[active_task_id]["result"]
    active_score = active.get("official_evaluation")
    if (
        active.get("status") != "scored" or active.get("failure") is not None
        or type(active.get("reward")) not in {int, float} or active["reward"] not in {0.0, 1.0}
        or not isinstance(active_score, dict) or active_score.get("scored") is not True
        or active_score.get("reward") != active["reward"]
    ):
        raise BacktestBenchRevisionError("active task requires one delivered, scored blind Worker")
    load_research_operation_memory(memory)
    if not parent.is_dir() or parent.is_symlink():
        raise BacktestBenchRevisionError("complete parent H is unavailable")
    public_root = Path(state["declaration"]["public_root"])
    evidence_root = root / "prepared" / "evidence"
    shared = evidence_root / "public" / "shared-data"
    shared.mkdir(parents=True)
    (evidence_root / "access_log.jsonl").write_text("", encoding="utf-8")
    first_data = public_root / "tasks" / active_task_id / "environment" / "data"
    shutil.copyfile(first_data / "stock_tables.zip", shared / "stock_tables.zip")
    manifest = inspect_market_archive(shared / "stock_tables.zip")
    _atomic_private_json(shared / "market_archive.json", manifest)
    for name in ("factors.json", "indexs.json", "backtest_protocol.md"):
        _copy_text(first_data / name, shared / name)
    _copy_text(
        Path(__file__).parent / "evolve_agent_full" / "reference" / "NEXAU_GUIDE.md",
        evidence_root / "reference" / "NEXAU_GUIDE.md",
    )
    candidate = root / "prepared" / "candidate"
    shutil.copytree(parent, candidate, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    # Existing public probes support an immutable selected complete H at this
    # history-object path. No synthetic Python strategy entrypoint is supplied.
    shutil.copytree(candidate, evidence_root / "history" / "archive" / "objects" / "selected-parent")
    memory_copy = evidence_root / "research-memory" / "snapshot.json"
    copy_research_operation_memory(memory, memory_copy)
    project_observations = partial(_project_panel_observations, readable_trace_task_ids=readable_trace_task_ids)
    probes, observations = project_observations(
        panel_root=panel_root, state=state, evidence_root=evidence_root,
        cells=cells, public_tasks=public_tasks, active_task_id=active_task_id,
        observation_namespace=observation_namespace,
    )
    linked_review = None
    if pair is not None:
        from .backtestbench_completed_pair import project_completed_pair

        linked_review = project_completed_pair(
            pair, evidence_root=evidence_root, current_observations=observations,
            evidence_task_ids=evidence_task_ids, project_observations=project_observations,
            memory=load_research_operation_memory(memory_copy),
        )
    memory_index = compact_research_operation_index(
        load_research_operation_memory(memory_copy), outcome_review=linked_review,
    )
    contract = _evidence_contract(root, plan, evidence_task_ids, active_task_id, probes, memory_index)
    if memory_index_mode == "directory_v1":
        _project_memory_index_directory(evidence_root, contract)
    if supervision is not None:
        _copy_text(Path(supervision["source_manifest"]), evidence_root / TRAIN_SUPERVISION_PATH)
    if linked_review is not None:
        contract["completed_pair"] = "completed-pair/catalog.json"
        contract["research_operation_memory"]["outcome_linked_experience_review"] = {
            "enabled": True, "catalog": "research-memory/outcome-linked-review.json",
            "linked_review_count": linked_review["review_count"],
            "same_round_decision_reversal": True, "actions": ["retain", "revise", "defer"],
            "automatic_semantic_verdict": False,
        }
    if selected:
        for relative, payload in unit_payloads.items():
            path = evidence_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        from .research_campaign_history import _project_readable_trace

        source_traces = []
        for relative, record in {unit["complete_trace"]: unit for unit in selected}.items():
            trace = evidence_root / relative
            access, _, _ = _project_readable_trace(
                source=trace, source_ref=relative,
                destination=trace.parent / "worker-trace-parts", projection_root=evidence_root,
            )
            source_traces.append({
                "path": relative, "source_panel_id": record["source_panel_id"],
                "source_attempt": record["source_attempt"], "sha256": record["source_trace_sha256"],
                "bytes": record["source_trace_bytes"], "worker_trace_access": access,
            })
        _atomic_private_json(evidence_root / "selected-research-units/catalog.json", {
            "schema_version": 1, "selection": "investigator_selected_original_worker_units",
            "source_synthesis": False, "calculated_finding_included": False,
            "trusted_answers_included": False, "units": selected, "source_traces": source_traces,
        })
        contract["selected_research_units"] = {
            "catalog": "selected-research-units/catalog.json", "optional": True,
            "selection": "investigator_selected_original_worker_units",
            "source_synthesis": False, "calculated_finding_included": False,
            "complete_original_source_traces_included": True,
        }
    if research_index_path is not None:
        from .backtestbench_research_index import project_index
        contract["research_index"] = project_index(
            Path(research_index_path).expanduser().resolve(), evidence_root / "research-index",
            allowed_task_ids=evidence_task_ids,
        )
    if continuation_context is not None:
        _atomic_private_json(evidence_root / "continuation/context.json", dict(continuation_context))
        contract["continuation_context"] = "continuation/context.json"
    _atomic_private_json(evidence_root / "contract.json", contract)
    diagnosis = {
        "protocol": PROTOCOL, "benchmark": "backtestbench", "active_task_id": active_task_id,
        "source_panel_id": state["run_id"], "source_parent_harness": plan["source_parent_harness"],
        "observations": f"{observation_namespace}/index.json",
        "instruction": (
            "Inspect the public requirement and the original Worker command/result trace, artifacts, "
            "and binary outcome. Choose a supported reusable method experiment or abstain. "
            "Look for an actual operation and its consumer; a binary failure alone does not identify "
            "its cause. All nine H roles are available. Preserve applicability and counterevidence. "
            "The original market ZIP is shared once at public/shared-data/stock_tables.zip; inspect "
            "market_archive.json and read its CSVs with zipfile inside a public artifact probe. "
            "Original binary Worker artifacts are bound by contract.original_binary_artifacts; "
            "use a suitable Python reader inside a public artifact probe for those exact bytes. "
            "read_workspace reads UTF-8 text and must not be used for the archive. "
            "Do not copy a task's computed answer into H. New H remains unscored until fresh Workers "
            "consume it under the unchanged answer comparator."
        ),
    }
    if supervision is not None:
        diagnosis.update(feedback_tier=TRAIN_SUPERVISION_TIER, answer_free=False,
                         trusted_answers_included=True, training_scalar_supervision=supervision)
        diagnosis["instruction"] += (
            " This NEW separately registered condition explicitly authorizes Evolver-only scalar labels "
            "for the declared eight TRAIN tasks at declared-training-supervision/targets.json. "
            "This is supervised feedback, not answer-free or independent generalization evidence. "
            "No SQL, reference program, validation/test label or Worker/probe-data label is supplied. "
            "Use the original computation/consumer evidence to investigate methods; do not copy target "
            "answers into persistent H. This scope requires no edit, executable component or ACT."
        )
    if pair is not None:
        diagnosis.update({
            "completed_pair": "completed-pair/catalog.json",
            "research_memory_source_resolution": "research-memory/source-resolution.json",
        })
        diagnosis["instruction"] += (
            " Your own exact previous method experiment and both original train draws are in "
            "completed-pair/catalog.json, including its decision, probe source/result and H diff. "
            "Current candidate-parent artifacts are in current-observations; observations preserves "
            "the initial draw cited by the previous R. Do not substitute one draw for the other. "
            "The unchanged actual R has an outcome-linked exact-read/review view; retain, revise or "
            "defer are available without an automatic verdict, forced review, edit or ACT. "
            "Missing scores remain null and this pair does not select or adopt a whole H."
        )
    if readable_trace_task_ids:
        diagnosis["instruction"] += (
            " For explicitly selected oversized raw Worker traces, observations/index.json "
            "records worker_trace_access with a readable catalog and lossless ordered UTF-8 "
            "parts. Read the catalog and parts with bounded read_workspace calls; fragments "
            "are not independent JSONL rows. Original raw traces remain unchanged."
        )
    if selected:
        diagnosis["selected_research_units"] = "selected-research-units/catalog.json"
        diagnosis["instruction"] += (
            " Optional investigator-selected original Worker row ranges are indexed in "
            "selected-research-units/catalog.json. They retain literal source/command/result "
            "bytes and their own panel/attempt identities, including sources outside your own "
            "completed pair. They contain no investigator finding, source synthesis or repair. "
            "Each complete_trace points to the unchanged complete original source context; "
            "source_traces records lossless ordered UTF-8 parts when needed. Read those catalogs "
            "and parts with bounded read_workspace calls; fragments are not JSONL rows. "
            "Read the raw units with bounded read_workspace calls; selection does not establish "
            "a failure cause or require a probe, component type, edit or ACT."
        )
    if research_index_path is not None:
        diagnosis["research_index"] = contract["research_index"]
        diagnosis["instruction"] += (
            " The incremental original research index is at research-index/RESEARCH-UNIT-INDEX.json. "
            "Search the compact public requirement and operation identifiers across all indexed development tasks. "
            "Choose a small number of useful units, then read their paired original code, trace/output, "
            "complete H diff and measured outcomes through source_refs. Include relevant ties and failures; "
            "separate measured fields from interpretation. Original details are available but not preloaded. "
            "The research_index.binary_artifacts manifest binds original non-text artifact paths, hashes "
            "and sizes. Inspect those files with an appropriate reader in a public artifact probe, "
            "not UTF-8 read_workspace; the original binary bytes are preserved. "
            "Prefer reads or probes whose possible results could change the next implementation choice."
        )
    if continuation_context is not None:
        diagnosis["continuation_context"] = "continuation/context.json"
        diagnosis["instruction"] += (
            " Read the actual previous post-run continuation decision at continuation/context.json. "
            "Develop from this complete selected H, preserving useful inherited operations. "
            "Use its next intent and retained counterevidence to guide repair or extension."
        )
    _atomic_private_json(root / "prepared" / "diagnosis.json", diagnosis)
    evidence = authorize_evidence_tree(evidence_root, backtestbench_market_archive=MARKET_ARCHIVE)
    _atomic_private_json(preflight, plan)
    return PreparedBacktestBenchRevision(root, candidate, evidence, diagnosis, memory_copy, plan)


def _project_panel_observations(
    *, panel_root, state, evidence_root, cells, public_tasks,
    active_task_id=None, observation_namespace="observations", include_public_tasks=True,
    readable_trace_task_ids=(),
):
    public_root = Path(state["declaration"]["public_root"])
    probes, observations = {}, {}
    for task_id, cell in cells.items():
        task_root = public_root / "tasks" / task_id
        public_task = evidence_root / "public" / "tasks" / task_id
        if include_public_tasks:
            _copy_text(task_root / "instruction.md", public_task / "instruction.md")
            _atomic_private_json(public_task / "public_task.json", public_tasks[task_id])
        attempt = TaskAttempt(**cell["attempt"])
        if attempt.task_id != task_id or attempt.run_id != state["run_id"]:
            raise BacktestBenchRevisionError("original Worker task or panel identity differs")
        attempt_dir = panel_root / "attempts" / attempt.attempt_id
        if _read(attempt_dir / "attempt.json") != asdict(attempt):
            raise BacktestBenchRevisionError("original Worker attempt identity differs")
        execution = load_worker_execution(attempt, panel_root)
        if task_id == active_task_id and (execution is None or not execution.cleaned_up):
            raise BacktestBenchRevisionError("active Worker delivery or cleanup is unavailable")
        observation = evidence_root / observation_namespace / task_id
        artifacts = observation / "artifacts"
        artifacts.mkdir(parents=True)
        source_artifacts = attempt_dir / "artifacts"
        artifact_manifest = []
        if source_artifacts.is_dir():
            for path in sorted(source_artifacts.rglob("*")):
                if path.is_symlink():
                    raise BacktestBenchRevisionError("Worker artifact symlinks cannot enter evidence")
                if path.is_file():
                    relative = path.relative_to(source_artifacts)
                    record = {"path": relative.as_posix(), "size_bytes": path.stat().st_size}
                    if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
                        record.update({
                            "projection": "excluded_generated_bytecode",
                            "reason": "original remains in the blind panel; generated Python cache is not Evolver source evidence",
                        })
                    else:
                        payload = path.read_bytes()
                        try:
                            payload.decode("utf-8")
                        except UnicodeDecodeError:
                            record["projection"] = "included_original_binary"
                        else:
                            record["projection"] = "included_original_text"
                        record["sha256"] = hashlib.sha256(payload).hexdigest()
                        target = artifacts / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(payload)
                    artifact_manifest.append(record)
        trace = Path(execution.trace_uri) if execution is not None else attempt_dir / "raw-trace.jsonl"
        final = Path(execution.final_text_uri) if execution is not None else attempt_dir / "final.txt"
        for source, evidence_name in ((trace, "worker_trace.jsonl"), (final, "worker_final.txt")):
            try:
                source.resolve().relative_to(attempt_dir.resolve())
            except ValueError as exc:
                raise BacktestBenchRevisionError("Worker trace or final text escapes its original attempt") from exc
            if source.is_file():
                _copy_text(source, observation / evidence_name)
        trace_access = None
        projected_trace = observation / "worker_trace.jsonl"
        if task_id in readable_trace_task_ids and projected_trace.is_file() and projected_trace.stat().st_size > 256000:
            from .research_campaign_history import _project_readable_trace

            trace_access, _, _ = _project_readable_trace(
                source=projected_trace, source_ref=f"{observation_namespace}/{task_id}/worker_trace.jsonl",
                destination=observation / "worker-trace-parts", projection_root=evidence_root,
            )
        _atomic_private_json(observation / "attempt.json", asdict(attempt))
        _atomic_private_json(observation / "artifact_manifest.json", {"artifacts": artifact_manifest})
        summary = dict(execution.summary) if execution is not None else {}
        _atomic_private_json(observation / "process_summary.json", {
            key: summary[key] for key in ("outcome", "turns", "tool_calls", "tool_errors", "files", "secs") if key in summary
        })
        result = cell["result"]
        raw_score = result.get("official_evaluation")
        score = {key: raw_score.get(key) for key in (
            "uuid", "strategy_type", "scoring_mode", "scored_category", "scored", "reward",
        )} if isinstance(raw_score, dict) else None
        _atomic_private_json(observation / "outcome.json", {
            "task_id": task_id, "status": result["status"],
            "official_evaluation": score, "failure": result.get("failure"),
            "trusted_answer_included": False,
        })
        observations[task_id] = {
            "source_attempt_id": attempt.attempt_id, "source_panel_id": state["run_id"],
            "public_task": f"public/tasks/{task_id}/public_task.json",
            "instruction": f"public/tasks/{task_id}/instruction.md",
            "worker_trace": f"{observation_namespace}/{task_id}/worker_trace.jsonl",
            "artifact_root": f"{observation_namespace}/{task_id}/artifacts",
            "outcome": f"{observation_namespace}/{task_id}/outcome.json",
            "status": result["status"], "reward": result["reward"],
        }
        if trace_access is not None:
            observations[task_id]["worker_trace_access"] = trace_access
        probes[task_id] = {
            "workspace": f"{observation_namespace}/{task_id}/artifacts",
            "artifact_root": f"{observation_namespace}/{task_id}/artifacts",
            "public_data": "public/shared-data", "source_observation_run_id": state["run_id"],
            "artifact_role": "observed_parent", "candidate_parent": True,
            "current_candidate_behavior": True,
        }
    _atomic_private_json(evidence_root / observation_namespace / "index.json", observations)
    return probes, observations


def _project_memory_index_directory(evidence_root: Path, contract: dict) -> None:
    """Keep the original index reachable without preloading its lesson excerpts."""
    memory = contract["research_operation_memory"]
    index = memory["index"]
    path = evidence_root / MEMORY_INDEX_PATH
    _atomic_private_json(path, index)
    memory["index"] = {
        "mode": "directory_v1", "source": "evidence", "path": MEMORY_INDEX_PATH,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        **{key: index[key] for key in (
            "schema_version", "operation_count", "experience_count", "item_count",
            "operation_version_count", "experience_version_count", "version_count",
            "truncated", "source_included", "deterministic_order",
        )},
        "lookup": (
            "Use search_research_operations(query=operation, applicability or counterevidence keywords) "
            "to search the current complete memory, including older versions. Read selected exact versions "
            "with read_research_operation or read_research_experience. An empty query lists bounded "
            "metadata, not all items. The original prepared index remains readable with "
            'read_workspace(source="evidence", file_path="research-memory/index.json"); '
            "input_snapshot preserves the complete original memory, including items omitted from this index. "
            "This directory is not a selected subset or a semantic verdict."
        ),
    }


def _evidence_contract(root, plan, evidence_task_ids, active_task_id, probes, memory_index):
    allowed_roles = list(plan.get("candidate_components") or _ROLES)
    binary_artifacts = []
    for namespace in ("observations", "current-observations"):
        for task_id in evidence_task_ids:
            manifest = root / "prepared/evidence" / namespace / task_id / "artifact_manifest.json"
            if not manifest.is_file():
                continue
            for row in _read(manifest)["artifacts"]:
                if row["projection"] == "included_original_binary":
                    binary_artifacts.append({
                        "path": f"{namespace}/{task_id}/artifacts/{row['path']}",
                        "sha256": row["sha256"], "size_bytes": row["size_bytes"],
                    })
    contract = {
        "schema_version": 2, "protocol": PROTOCOL, "benchmark": "backtestbench",
        "decision_protocol": "quant_property_v2", "evolver_profile": PROFILE,
        "feedback_tier": "answer_free_worker_observation_v1", "answer_free": True,
        "feedback_contents": plan["feedback_contents"], "trusted_answers_included": False,
        "task_ids": list(evidence_task_ids), "target_task_ids": [active_task_id],
        "protection_task_ids": [task_id for task_id in evidence_task_ids if task_id != active_task_id],
        "history_required": False, "max_primary_components": 2,
        "max_declared_components": len(allowed_roles), "allowed_candidate_components": allowed_roles,
        "nexau_runtime_reference": "reference/NEXAU_GUIDE.md",
        "quant_failure_classification_required_for_act": False,
        "research_state_transition_required_for_act": False,
        "failure_signature_required_for_act": False, "autonomous_probe_required": False,
        "quant_diagnostic_record_enabled": True, "quant_diagnostic_record_is_advisory": True,
        "research_state_vocabulary_is_open": True,
        "public_market_archive": MARKET_ARCHIVE,
        "original_binary_artifacts": binary_artifacts,
        "public_artifact_probe_enabled": True, "public_artifact_probe_kind": "public_artifact_python_v1",
        "candidate_behavior_probe_enabled": True,
        "public_artifact_probe_source": "backtestbench_observed_parent_artifacts",
        "public_artifact_probe_tasks": probes,
        "selected_parent_harness": {
            "status": "available", "path": "history/archive/objects/selected-parent",
            "role": "immutable_selected_parent_harness",
        },
        "research_operation_memory": {
            "enabled": True, "input_snapshot": "research-memory/snapshot.json",
            "input_declared": True, "result_name": MEMORY_RESULT_NAME,
            "current_revision_run_id": root.name, "index": memory_index,
            "full_source_preloaded": False, "worker_visible": False,
        },
    }
    if plan.get("training_scalar_supervision"):
        contract.update(feedback_tier=TRAIN_SUPERVISION_TIER, answer_free=False, trusted_answers_included=True,
                        training_scalar_supervision=plan["training_scalar_supervision"])
    return contract


def _retained_memory(root: Path, iteration: int, fallback: Path) -> tuple[Path, str]:
    for path in (
        root / "evolutions" / f"iteration-{iteration:04d}" / MEMORY_RESULT_NAME,
        root / "evolutions" / f"iteration-{iteration:04d}" / "failed-evidence" / MEMORY_RESULT_NAME,
    ):
        if path.is_file() and not path.is_symlink():
            try:
                load_research_operation_memory(path)
            except ValueError:
                continue
            return path, "current_evolver_result"
    return fallback, "input_snapshot_carried"


def run_backtestbench_revision(
    *, config_path: str | Path, evolver_config_path: str | Path,
    panel_run_dir: str | Path, revision_run_dir: str | Path, worker_dir: str | Path,
    active_task_id: str, evidence_task_ids: Sequence[str], research_memory_path: str | Path,
    evolver_image_ref: str, proxy_image_ref: str, iteration: int = 1,
    completed_pair: Mapping[str, str | Path] | None = None,
    readable_trace_task_ids: Sequence[str] = (),
    selected_research_units: Sequence[Mapping[str, object]] = (),
    training_scalar_supervision_path: str | Path | None = None,
    continuation_context: Mapping[str, object] | None = None,
    research_index_path: str | Path | None = None,
    memory_index_mode: str = "inline",
    candidate_components: Sequence[str] = (),
) -> dict:
    """Execute one native Evolver call, retaining its complete candidate and R."""
    if type(iteration) is not int or iteration < 1:
        raise BacktestBenchRevisionError("iteration must be positive")
    if memory_index_mode not in MEMORY_INDEX_MODES:
        raise BacktestBenchRevisionError("unknown research-memory index mode")
    if not set(candidate_components) <= set(_ROLES):
        raise BacktestBenchRevisionError("candidate_components names an unknown role")
    root = Path(revision_run_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = _CoordinatorLock(root / "coordinator.lock").acquire()
    try:
        declaration = {
            "config_path": str(Path(config_path).expanduser().resolve()),
            "evolver_config_path": str(Path(evolver_config_path).expanduser().resolve()),
            "panel_run_dir": str(Path(panel_run_dir).expanduser().resolve()),
            "worker_dir": str(Path(worker_dir).expanduser().resolve()),
            "active_task_id": active_task_id, "evidence_task_ids": list(evidence_task_ids),
            "research_memory_path": str(Path(research_memory_path).expanduser().resolve()),
            "evolver_image_ref": evolver_image_ref, "proxy_image_ref": proxy_image_ref,
            "iteration": iteration, "evolver_profile": PROFILE,
        }
        if memory_index_mode != "inline":
            declaration["memory_index_mode"] = memory_index_mode
        if candidate_components:
            declaration["candidate_components"] = list(candidate_components)
        if research_index_path is not None:
            from .backtestbench_research_index import INDEX_FILE
            index_root = Path(research_index_path).expanduser().resolve()
            declaration["research_index"] = {"source":str(index_root),
                "sha256":hashlib.sha256((index_root / INDEX_FILE).read_bytes()).hexdigest()}
        if continuation_context is not None:
            declaration["continuation_context"] = dict(continuation_context)
        if completed_pair is not None:
            declaration["completed_pair"] = {
                key: str(Path(value).expanduser().resolve()) for key, value in completed_pair.items()
            }
        if readable_trace_task_ids:
            declaration["readable_trace_task_ids"] = list(readable_trace_task_ids)
        if selected_research_units:
            declaration["selected_research_units"] = [
                {**dict(unit), "panel_run_dir": str(Path(unit["panel_run_dir"]).expanduser().resolve())}
                for unit in selected_research_units
            ]
        if training_scalar_supervision_path is not None:
            declaration.update(feedback_tier=TRAIN_SUPERVISION_TIER, answer_free=False, trusted_answers_included=True,
                training_scalar_supervision=_inspect_training_scalar_supervision(
                    training_scalar_supervision_path, run_id=root.name,
                    state=_read(Path(panel_run_dir).expanduser().resolve() / PANEL_STATE_FILE),
                    evidence_task_ids=evidence_task_ids,
                ))
        result_path = root / RESULT_FILE
        if result_path.exists():
            retained = _read(result_path)
            if retained["declaration"] != declaration:
                raise BacktestBenchRevisionError("retained revision declaration differs")
            return retained
        if (root / DISPATCH_FILE).exists() or (root / "attempts").exists():
            raise BacktestBenchRevisionError("incomplete Evolver attempt retained; no redraw is allowed")
        prepared = prepare_backtestbench_revision(
            panel_run_dir=panel_run_dir, revision_run_dir=root, worker_dir=worker_dir,
            active_task_id=active_task_id, evidence_task_ids=evidence_task_ids,
            research_memory_path=research_memory_path,
            completed_pair=completed_pair,
            readable_trace_task_ids=readable_trace_task_ids,
            selected_research_units=selected_research_units,
            training_scalar_supervision_path=training_scalar_supervision_path,
            continuation_context=continuation_context,
            research_index_path=research_index_path,
            memory_index_mode=memory_index_mode,
            candidate_components=candidate_components,
        )
        started = time.perf_counter()
        proposal, runtime, qualification, failure = None, None, None, None
        stage = "runtime_preflight"
        try:
            evolver_dir = _materialize_evolver_profile(run_root=root, evolver_profile=PROFILE)
            proposer, runtime = _prepare_revision_runtime(
                root=root, config_path=config_path, evolver_config_path=evolver_config_path,
                evolver_image_ref=evolver_image_ref, proxy_image_ref=proxy_image_ref,
                evolver_profile=PROFILE,
                max_input_files=RESEARCH_INDEX_MAX_INPUT_FILES if research_index_path is not None else 2000,
            )
            _atomic_private_json(root / DISPATCH_FILE, {"declaration": declaration, "runtime": runtime})
            stage = "evolver_proposal"
            proposal = proposer.propose(
                candidate_dir=prepared.candidate_dir, evidence_dir=prepared.evidence,
                evolver_dir=evolver_dir, diagnosis=prepared.diagnosis,
                iteration=iteration, run_id=root.name, run_dir=root,
            )
            stage = "candidate_qualification"
            if getattr(proposal, "cleaned_up", False) is not True:
                raise BacktestBenchRevisionError("Evolver cleanup did not complete")
            qualification = _qualify_revision(
                proposal, parent=prepared.candidate_dir, allow_prospective_role_subset=True,
            )
            outside = sorted(set(qualification["mutation"]["component_roles"]) - set(candidate_components or _ROLES))
            if outside:
                raise BacktestBenchRevisionError(
                    "candidate changed components outside the declared surface: " + ", ".join(outside)
                )
            if getattr(proposal, "research_memory_uri", None) is None:
                raise BacktestBenchRevisionError("declared R was not returned by the Evolver")
            load_research_operation_memory(proposal.research_memory_uri)
        except Exception as exc:  # noqa: BLE001 - retain the exact attempt, never retry.
            failure = {"stage": stage, **_failure_payload(exc)}
        memory_path, memory_status = _retained_memory(root, iteration, prepared.research_memory_path)
        summary = {}
        if proposal is not None:
            try:
                summary = _read(Path(proposal.summary_uri))
            except (ValueError, OSError) as exc:
                if failure is None:
                    failure = {"stage": "evolver_summary", **_failure_payload(exc)}
        proxy_cost = _proxy_cost_evidence(root / "attempts" / f"evolver-iteration-{iteration}", run_root=root)
        result = {
            "protocol": PROTOCOL, "run_id": root.name, "declaration": declaration,
            "status": "failed" if failure is not None else qualification["status"],
            "failure": failure, "runtime": runtime, "qualification": qualification,
            "parent_harness": {
                "source": prepared.plan["source_parent_harness"],
                "artifact_uri": _relative(prepared.candidate_dir, root),
            },
            "candidate_harness": (
                {"harness_id": f"{root.name}-candidate", "artifact_uri": _relative(proposal.candidate_dir, root)}
                if failure is None and qualification["status"] == "revised_unscored" else None
            ),
            "native_candidate_uri": _relative(proposal.candidate_dir, root) if proposal is not None else None,
            "research_memory": {"artifact_uri": _relative(memory_path, root), "retention": memory_status},
            "evidence_root": _relative(prepared.evidence.root, root),
            "evolver_evidence": {
                key: _relative(getattr(proposal, key), root)
                for key in ("trace_uri", "summary_uri", "final_uri", "access_summary_uri")
                if proposal is not None and getattr(proposal, key, None) is not None
            },
            "public_probe_refs": (
                qualification["decision"].get("public_artifact_probe_ids", []) if qualification is not None else []
            ),
            "proxy_cost": proxy_cost,
            "accounting": _usage_accounting(
                [summary] if summary else [], [proxy_cost],
                wall_time_seconds=time.perf_counter() - started,
                checks=len(qualification["component_tests"]) if qualification is not None else 0,
            ),
            "fresh_worker_uptake": "not_run", "candidate_official_evaluation": "not_run",
            "learned_gain_claimed": False,
        }
        if training_scalar_supervision_path is not None:
            result.update(feedback_tier=TRAIN_SUPERVISION_TIER, answer_free=False, trusted_answers_included=True,
                          training_scalar_supervision=prepared.plan["training_scalar_supervision"])
        _atomic_private_json(result_path, result)
        return result
    finally:
        lock.close()
