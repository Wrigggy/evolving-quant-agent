#!/usr/bin/env python3
"""Build indexed, train-only evidence for A4 or successor discovery canaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.evolution_evidence import authorize_evidence_tree  # noqa: E402
from qea.public_contract_evidence import (  # noqa: E402
    build_public_contract_index,
    public_contract_source_identity,
)
from qea.qfbench_a4 import derive_a4_panel, validate_frozen_panel  # noqa: E402
from qea.qfbench_a6 import validate_frozen_a6_panel  # noqa: E402
from qea.qfbench_baseline import (  # noqa: E402
    audit_fixed_checkpoint_proxy_costs,
)
from qea.worker_identity import hash_worker_directory  # noqa: E402


_CREDENTIAL = re.compile(
    r"(?i)(?:Bearer\s+|\bsk-[A-Za-z0-9_-]*)([A-Za-z0-9._-]{12,})"
)
_PRIVATE_PARTS = frozenset(
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
_FULL_ARTIFACT_LIMIT = 192 * 1024
_PREVIEW_EDGE_BYTES = 48 * 1024


def _json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"required regular JSON file is unavailable: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sanitize_text(text: str) -> tuple[str, int]:
    redactions = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal redactions
        redactions += 1
        prefix = "Bearer " if match.group(0).casefold().startswith("bearer") else "sk-"
        return prefix + "[REDACTED]"

    return _CREDENTIAL.sub(replace, text), redactions


def _safe_source(source: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"evidence source must be a regular file: {source}")
    if any(part.casefold() in _PRIVATE_PARTS for part in source.parts):
        raise ValueError(f"private evaluator path is forbidden: {source}")


def _copy_text(source: Path, destination: Path) -> int:
    _safe_source(source)
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"evidence source is not UTF-8: {source}") from exc
    sanitized, redactions = _sanitize_text(text)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(sanitized, encoding="utf-8")
    return redactions


def _artifact_evidence(
    *,
    source: Path,
    destination: Path,
) -> tuple[dict[str, object], int]:
    _safe_source(source)
    payload = source.read_bytes()
    record: dict[str, object] = {
        "path": source.name,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        record.update({
            "representation": "omitted_non_utf8",
            "evidence_path": None,
        })
        return record, 0

    if len(payload) <= _FULL_ARTIFACT_LIMIT:
        sanitized, redactions = _sanitize_text(text)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(sanitized, encoding="utf-8")
        record.update({
            "representation": "full_text",
            "evidence_path": destination.name,
        })
        return record, redactions

    head = payload[:_PREVIEW_EDGE_BYTES].decode("utf-8", errors="replace")
    tail = payload[-_PREVIEW_EDGE_BYTES:].decode("utf-8", errors="replace")
    preview = (
        "[A4 ARTIFACT PREVIEW: HEAD]\n"
        + head
        + "\n[A4 ARTIFACT PREVIEW: MIDDLE OMITTED]\n"
        + tail
        + "\n[A4 ARTIFACT PREVIEW: TAIL]\n"
    )
    sanitized, redactions = _sanitize_text(preview)
    preview_destination = destination.with_suffix(destination.suffix + ".preview.txt")
    preview_destination.parent.mkdir(parents=True, exist_ok=True)
    preview_destination.write_text(sanitized, encoding="utf-8")
    record.update({
        "representation": "head_tail_preview",
        "evidence_path": preview_destination.name,
        "preview_edge_bytes": _PREVIEW_EDGE_BYTES,
    })
    return record, redactions


def _public_score(score: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "task_id": str(score["task_id"]),
        "official_reward": float(score["reward"]),
        "diagnostic_tags": sorted(
            str(value) for value in score.get("diagnostic_tags", [])
        ),
        "tests_passed": score.get("tests_passed"),
        "tests_failed": score.get("tests_failed"),
        "verifier_exit_code": score.get("verifier_exit_code"),
        "provenance": "official scalar and answer-free aggregate diagnostics",
    }


def _timeout_execution_summary(
    attempt_dir: Path,
    score: Mapping[str, object],
) -> dict[str, object]:
    """Describe an observed worker timeout without inventing a missing trace."""

    tags = {str(value) for value in score.get("diagnostic_tags", [])}
    if "timeout" not in tags:
        raise ValueError(
            "worker-execution.json is missing without an explicit timeout score: "
            f"{attempt_dir}"
        )
    audit_path = attempt_dir / "proxy-audit.jsonl"
    completed_requests = 0
    noncompleted_requests = 0
    total_tokens = 0
    if audit_path.exists():
        _safe_source(audit_path)
        for line_number, line in enumerate(
            audit_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid proxy audit line {audit_path}:{line_number}"
                ) from exc
            if not isinstance(record, Mapping):
                raise ValueError(
                    f"proxy audit line is not an object {audit_path}:{line_number}"
                )
            if record.get("request_state") == "completed":
                completed_requests += 1
            else:
                noncompleted_requests += 1
            tokens = record.get("total_tokens")
            if isinstance(tokens, int):
                total_tokens += tokens
    return {
        "status": "worker_timeout",
        "diagnostic_tags": sorted(tags),
        "worker_execution_record_available": False,
        "worker_trace_available": False,
        "worker_final_available": False,
        "artifact_snapshot_available": False,
        "completed_model_requests_before_timeout": completed_requests,
        "noncompleted_model_requests_before_timeout": noncompleted_requests,
        "observed_total_tokens_before_timeout": total_tokens,
        "provenance": (
            "derived from the answer-free completed score and proxy audit; "
            "no missing worker trace was reconstructed"
        ),
    }


def _attempts_for_arm(
    evidence_run: Path,
    *,
    arm: str,
    expected_tasks: tuple[str, ...],
) -> dict[str, Path]:
    report = _json(evidence_run / "pilot-report.json")
    if report.get("status") != "complete":
        raise ValueError("fresh seed-evidence pilot is not complete")
    if tuple(report.get("task_ids", ())) != expected_tasks:
        raise ValueError("fresh seed-evidence task panel differs from A4")
    activations = report.get("activations")
    if not isinstance(activations, Mapping) or arm not in activations:
        raise ValueError(f"fresh seed-evidence pilot has no arm {arm!r}")
    activation = activations[arm]
    if not isinstance(activation, Mapping):
        raise ValueError("fresh seed-evidence activation payload is invalid")
    checkpoint = activation.get("checkpoint")
    if not isinstance(checkpoint, str) or not checkpoint:
        raise ValueError("fresh seed-evidence checkpoint is unavailable")

    attempts: dict[str, Path] = {}
    for attempt_path in sorted((evidence_run / "attempts").glob("*/attempt.json")):
        attempt = _json(attempt_path)
        if attempt.get("checkpoint") != checkpoint:
            continue
        task_id = str(attempt.get("task_id", ""))
        if task_id not in expected_tasks:
            raise ValueError(f"unexpected A4 evidence task: {task_id}")
        if task_id in attempts:
            raise ValueError(f"duplicate A4 evidence attempt: {task_id}")
        attempts[task_id] = attempt_path.parent
    if set(attempts) != set(expected_tasks):
        raise ValueError("fresh seed-evidence attempts are incomplete")
    return attempts


def _require_complete_component_cost(
    evidence_run: Path,
    *,
    report: Mapping[str, object],
    arm: str,
    expected_tasks: tuple[str, ...],
) -> dict[str, object]:
    """Require an exact canonical request/token/cost ledger for one arm."""

    activations = report.get("activations")
    activation = (
        activations.get(arm) if isinstance(activations, Mapping) else None
    )
    checkpoint = (
        activation.get("checkpoint") if isinstance(activation, Mapping) else None
    )
    if not isinstance(checkpoint, str) or not checkpoint:
        raise ValueError("fresh seed-evidence checkpoint is unavailable")
    canonical = audit_fixed_checkpoint_proxy_costs(
        evidence_run,
        expected_attempts=len(expected_tasks),
        checkpoint=checkpoint,
        split="mechanism-pilot",
    )
    if report.get("cost") != canonical:
        raise ValueError(
            "fresh seed-evidence report cost differs from the canonical audit"
        )
    completed_requests = canonical.get("completed_request_count")
    request_count = canonical.get("request_count")
    rate_limited_retries = canonical.get("rate_limited_retry_count", 0)
    logical_requests = canonical.get(
        "logical_request_count", completed_requests
    )
    other_nonaccepted = canonical.get(
        "other_nonaccepted_request_count", 0
    )
    if (
        canonical.get("attempt_count") != len(expected_tasks)
        or request_count != completed_requests + rate_limited_retries
        or logical_requests != completed_requests
        or other_nonaccepted != 0
        or canonical.get("cost_complete") is not True
        or canonical.get("provider_cost_is_lower_bound") is not False
        or canonical.get("unreconciled_attempt_count") != 0
        or canonical.get("unreconciled_request_count") != 0
    ):
        raise ValueError(
            "fresh seed-evidence canonical request/token/cost ledger is incomplete"
        )
    return canonical


def build(
    *,
    baseline_run: Path,
    evolution_manifest_path: Path,
    a4_manifest_path: Path,
    evidence_run: Path,
    arm: str,
    destination: Path,
    contract_arm: str | None = None,
    public_task_root: Path | None = None,
    a6_seed_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Create one immutable answer-free corpus from a fresh structured trace run."""

    baseline_run = baseline_run.resolve()
    evidence_run = evidence_run.resolve()
    evolution_manifest_path = evolution_manifest_path.resolve()
    a4_manifest_path = a4_manifest_path.resolve()
    baseline = _json(baseline_run / "result.json")
    evolution_manifest = _json(evolution_manifest_path)
    a4_manifest = _json(a4_manifest_path)
    stage = str(a4_manifest.get("stage", "A4"))
    experiment = a4_manifest.get("experiment")
    experiment = dict(experiment) if isinstance(experiment, Mapping) else {}
    contracts = experiment.get("contracts")
    contracts = dict(contracts) if isinstance(contracts, Mapping) else {}
    discovery_design: dict[str, object] = {}
    if stage == "A6":
        raw_discovery_design = a4_manifest.get("discovery_design")
        discovery_design = (
            dict(raw_discovery_design)
            if isinstance(raw_discovery_design, Mapping)
            else {}
        )
        a6_contracts = discovery_design.get("arms")
        if isinstance(a6_contracts, Mapping):
            contracts = {
                str(key): dict(value)
                for key, value in a6_contracts.items()
                if isinstance(value, Mapping)
            }
    if contract_arm is None:
        if stage != "A4" and contracts:
            raise ValueError("successor evidence requires an explicit contract arm")
        experiment_contract: dict[str, object] = {}
    else:
        raw_contract = contracts.get(contract_arm)
        if not isinstance(raw_contract, Mapping):
            raise ValueError(f"unknown discovery contract arm: {contract_arm!r}")
        experiment_contract = dict(raw_contract)
        if stage == "A6" and "max_components" not in experiment_contract:
            max_components = discovery_design.get("max_components")
            if max_components is not None:
                experiment_contract["max_components"] = max_components
    if stage == "A6":
        panel = validate_frozen_a6_panel(
            frozen=a4_manifest["panel"],
            baseline_result=baseline,
            evolution_manifest=evolution_manifest,
        )
    else:
        panel = derive_a4_panel(
            baseline_result=baseline,
            evolution_manifest=evolution_manifest,
            target_count=int(a4_manifest["selection"]["target_count"]),
            protection_count=len(a4_manifest["panel"]["protections"]),
        )
        validate_frozen_panel(frozen=a4_manifest["panel"], derived=panel)

    decision_protocol = experiment_contract.get("decision_protocol")
    semantic_contract = decision_protocol == "semantic_contract_v1"
    exposes_public_contracts = public_task_root is not None
    feedback_tier = experiment_contract.get(
        "evaluator_feedback_tier",
        discovery_design.get(
            "evaluator_feedback_tier", "answer_free_public_process"
        ),
    )
    feedback_manifest_digest = experiment_contract.get(
        "feedback_manifest_digest",
        discovery_design.get("feedback_manifest_digest"),
    )
    if stage == "A6" and feedback_tier != "answer_free_public_process":
        raise ValueError("A6 builder does not support this evaluator feedback tier")
    if feedback_manifest_digest is not None and (
        not isinstance(feedback_manifest_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", feedback_manifest_digest) is None
    ):
        raise ValueError("feedback_manifest_digest must be null or lowercase SHA-256")
    if stage == "A6" and semantic_contract and not exposes_public_contracts:
        raise ValueError(
            "semantic_contract_v1 requires indexed public-contract evidence"
        )
    if stage == "A6" and experiment_contract.get(
        "public_contract_index", exposes_public_contracts
    ) is not exposes_public_contracts:
        raise ValueError(
            "A6 public-contract evidence exposure differs from the arm contract"
        )
    if stage != "A6" and exposes_public_contracts:
        raise ValueError("indexed public-contract evidence is only supported for A6")

    baseline_contract = a4_manifest.get("baseline")
    if not isinstance(baseline_contract, Mapping):
        raise ValueError("A4 baseline contract is invalid")
    checks = {
        "run_id": baseline.get("run_id") == baseline_contract.get("run_id"),
        "result_sha256": _sha256(baseline_run / "result.json")
        == baseline_contract.get("result_sha256"),
        "seed_worker_digest": hash_worker_directory(baseline_run / "workers/seed")
        == baseline_contract.get("seed_worker_digest"),
        "benchmark_commit": evolution_manifest.get("commit")
        == a4_manifest.get("benchmark_commit"),
        "tvt_manifest_sha256": _sha256(evolution_manifest_path)
        == a4_manifest["selection"].get("tvt_manifest_sha256"),
    }
    failed_checks = sorted(name for name, passed in checks.items() if not passed)
    if failed_checks:
        raise ValueError(f"A4 pinned identity checks failed: {failed_checks}")

    plan = _json(evidence_run / "pilot-plan.json")
    if plan.get("benchmark_commit") != a4_manifest.get("benchmark_commit"):
        raise ValueError("fresh seed-evidence benchmark identity differs")
    arms = plan.get("arms")
    arm_records = {
        item.get("label"): item
        for item in arms
        if isinstance(arms, list) and isinstance(item, Mapping)
    } if isinstance(arms, list) else {}
    if arm not in arm_records:
        raise ValueError(f"fresh seed-evidence plan has no arm {arm!r}")
    if arm_records[arm].get("worker_digest") != baseline_contract.get(
        "seed_worker_digest"
    ):
        raise ValueError("fresh seed-evidence worker is not the pinned baseline seed")

    expected_tasks = panel.task_ids
    if stage == "A6":
        _require_complete_component_cost(
            evidence_run,
            report=_json(evidence_run / "pilot-report.json"),
            arm=arm,
            expected_tasks=expected_tasks,
        )
    public_contract_source: dict[str, object] | None = None
    if exposes_public_contracts:
        public_contract_source = public_contract_source_identity(
            public_task_root=public_task_root,
            task_ids=expected_tasks,
            benchmark_commit=str(a4_manifest.get("benchmark_commit", "")),
        )
    attempts = _attempts_for_arm(
        evidence_run, arm=arm, expected_tasks=expected_tasks
    )
    if destination.exists():
        raise ValueError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = Path(
        tempfile.mkdtemp(prefix=destination.name + ".tmp-", dir=destination.parent)
    )
    redactions = 0
    try:
        (temporary / "access_log.jsonl").write_text("", encoding="utf-8")
        contract_payload: dict[str, object] = {
                "schema_version": 1,
                "stage": stage,
                "purpose": (
                    "single-proposal Evolver discovery behavior canary"
                    if stage == "A4"
                    else "failure-type induction, probe, and decision canary"
                ),
                "mode": "indexed_full_trace",
                "train_task_ids": list(expected_tasks),
                "target_task_ids": [item.task_id for item in panel.targets],
                "protection_task_ids": [
                    item.task_id for item in panel.protections
                ],
                "held_out_feedback": False,
                "private_evaluator_feedback": False,
                "official_solution": False,
                "component_hint": None,
                "root_cause_hint": None,
                "evolver_instruction": experiment_contract.get(
                    "instruction",
                    discovery_design.get(
                        "evolver_instruction",
                        "Use the repeated train-only baseline outcomes and the fresh "
                        "structured worker traces, finals, process summaries, and "
                        "artifacts to discover and test one transferable harness "
                        "mechanism. Verify the deterministic index against raw "
                        "evidence. Do not specialize to task IDs. The coordinator "
                        "prescribes no component, file, root cause, or implementation.",
                    ),
                ),
            }
        if stage == "A6":
            contract_payload.update(
                {
                    "sentinel_task_ids": [
                        item.task_id for item in panel.sentinels
                    ],
                    "public_contract_evidence": exposes_public_contracts,
                    "public_contract_index": (
                        "contracts/index.json" if exposes_public_contracts else None
                    ),
                    "public_task_role_manifest_sha256": (
                        public_contract_source[
                            "public_task_role_manifest_sha256"
                        ]
                        if public_contract_source is not None
                        else None
                    ),
                    "public_contract_source_members_sha256": (
                        public_contract_source["instruction_members_sha256"]
                        if public_contract_source is not None
                        else None
                    ),
                    "semantic_comparison": (
                        experiment_contract.get("semantic_comparison")
                        or (
                            "required_for_act"
                            if semantic_contract
                            else (
                                "available_not_required"
                                if exposes_public_contracts
                                else "not_required"
                            )
                        )
                    ),
                    "evaluator_feedback_tier": feedback_tier,
                    "feedback_manifest_digest": feedback_manifest_digest,
                }
            )
            if a6_seed_identity is not None:
                seed_launch_identity = a6_seed_identity.get(
                    "seed_launch_identity_sha256"
                )
                seed_record_identity = a6_seed_identity.get(
                    "seed_identity_record_sha256"
                )
                for label, value in (
                    ("seed_launch_identity_sha256", seed_launch_identity),
                    ("seed_identity_record_sha256", seed_record_identity),
                ):
                    if (
                        not isinstance(value, str)
                        or re.fullmatch(r"[0-9a-f]{64}", value) is None
                    ):
                        raise ValueError(f"A6 {label} is not lowercase SHA-256")
                contract_payload.update(
                    {
                        "seed_launch_identity_sha256": seed_launch_identity,
                        "seed_identity_record_sha256": seed_record_identity,
                    }
                )
        if stage != "A4":
            contract_payload["contract_arm"] = contract_arm
        for key in (
            "decision_protocol",
            "success_counterfactual",
            "probe_policy",
            "max_components",
        ):
            if key in experiment_contract:
                contract_payload[key] = experiment_contract[key]
        _write_json(temporary / "contract.json", contract_payload)
        _write_json(
            temporary / "baseline" / "selection.json",
            {
                "schema_version": 1,
                "selection_policy": a4_manifest["selection"],
                "baseline": baseline_contract,
                "panel": panel.as_dict(),
            },
        )

        task_index: list[dict[str, object]] = []
        current_outcomes: dict[str, dict[str, object]] = {}
        timed_out_tasks: list[str] = []
        role_items = panel.targets + panel.protections
        if stage == "A6":
            role_items += panel.sentinels
        role_by_task = {item.task_id: item.role for item in role_items}
        for task_id in expected_tasks:
            attempt_dir = attempts[task_id]
            attempt = _json(attempt_dir / "attempt.json")
            score = _public_score(_json(attempt_dir / "completed-score.json"))
            if attempt.get("worker_digest") != baseline_contract.get(
                "seed_worker_digest"
            ):
                raise ValueError(f"fresh task {task_id} used the wrong worker")
            if score["task_id"] != task_id:
                raise ValueError(f"fresh task score identity differs for {task_id}")
            task_root = temporary / "tasks" / task_id
            _write_json(task_root / "public_evaluation.json", score)
            execution_path = attempt_dir / "worker-execution.json"
            execution_status = "complete"
            if execution_path.is_file() and not execution_path.is_symlink():
                execution = _json(execution_path)
                _write_json(
                    task_root / "process_summary.json",
                    execution.get("summary", {}),
                )
                trace = attempt_dir / str(
                    execution.get("trace_uri", "raw-trace.jsonl")
                )
                final = attempt_dir / str(
                    execution.get("final_text_uri", "final.txt")
                )
                redactions += _copy_text(
                    trace, task_root / "worker_trace.jsonl"
                )
                redactions += _copy_text(
                    final, task_root / "worker_final.txt"
                )
                artifact_root: Path | None = attempt_dir / str(
                    execution.get("artifact_dir", "artifacts")
                )
            else:
                process_summary = _timeout_execution_summary(attempt_dir, score)
                execution_status = "worker_timeout"
                timed_out_tasks.append(task_id)
                _write_json(task_root / "process_summary.json", process_summary)
                (task_root / "worker_trace.jsonl").write_text(
                    json.dumps(
                        {
                            "event": "evidence_unavailable",
                            "reason": "worker_timeout_before_result_materialization",
                            "schema_version": 1,
                            "task_id": task_id,
                        },
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                (task_root / "worker_final.txt").write_text(
                    "[worker final unavailable: worker timed out before result "
                    "materialization]\n",
                    encoding="utf-8",
                )
                artifact_root = None
            artifact_records: list[dict[str, object]] = []
            if artifact_root is not None and artifact_root.is_dir():
                for source in sorted(
                    artifact_root.rglob("*"),
                    key=lambda path: path.relative_to(artifact_root).as_posix(),
                ):
                    if source.is_symlink():
                        raise ValueError(f"artifact symlink is forbidden: {source}")
                    if not source.is_file():
                        continue
                    relative = source.relative_to(artifact_root)
                    record, count = _artifact_evidence(
                        source=source,
                        destination=task_root / "artifacts" / relative,
                    )
                    record["path"] = relative.as_posix()
                    if record.get("evidence_path") is not None:
                        evidence_name = str(record["evidence_path"])
                        record["evidence_path"] = (
                            Path("tasks") / task_id / "artifacts" / relative.parent
                            / evidence_name
                        ).as_posix()
                    artifact_records.append(record)
                    redactions += count
            _write_json(task_root / "artifact_manifest.json", {
                "schema_version": 1,
                "artifacts": artifact_records,
            })
            current_outcomes[task_id] = score
            task_record: dict[str, object] = {
                    "task_id": task_id,
                    "role": role_by_task[task_id],
                    "fresh_official_reward": score["official_reward"],
                    "fresh_tests_passed": score["tests_passed"],
                    "fresh_tests_failed": score["tests_failed"],
                    "paths": {
                        "evaluation": f"tasks/{task_id}/public_evaluation.json",
                        "trace": f"tasks/{task_id}/worker_trace.jsonl",
                        "final": f"tasks/{task_id}/worker_final.txt",
                        "process": f"tasks/{task_id}/process_summary.json",
                        "artifacts": f"tasks/{task_id}/artifact_manifest.json",
                    },
                }
            if stage != "A4":
                task_record["fresh_execution_status"] = execution_status
                task_record["fresh_evidence_completeness"] = (
                    "timeout_without_trace"
                    if execution_status == "worker_timeout"
                    else "full_structured_trace"
                )
            task_index.append(task_record)

        public_contract_index: dict[str, object] | None = None
        if exposes_public_contracts:
            public_contract_index = build_public_contract_index(
                qfbench_root=public_task_root,
                task_ids=expected_tasks,
                destination=temporary / "contracts",
                benchmark_commit=str(a4_manifest.get("benchmark_commit", "")),
            )

        _write_json(temporary / "debugger" / "task_index.json", {
            "schema_version": 1,
            "generator": "deterministic evidence librarian; not a root-cause oracle",
            "tasks": task_index,
        })
        unresolved_questions = [
            "which earliest worker behavior separates target failures from protection successes",
            "whether a repeated pattern is a transferable harness mechanism or task-specific finance logic",
            "which of the nine candidate component roles can test the leading mechanism with bounded blast radius",
            "whether the next traces and protection outcomes falsify the intervention prediction",
        ]
        if stage != "A4":
            unresolved_questions = [
                "whether the failed tasks form one reusable type, several types, or no coherent shared type",
                unresolved_questions[0],
                "which competing causal hypotheses make different answer-free probe predictions",
                *unresolved_questions[1:],
            ]
        observed_anomalies = [
            "target tasks failed all five pinned baseline repetitions despite normal verifier execution and non-empty official test counts",
            "protection tasks passed all five pinned baseline repetitions",
        ]
        if timed_out_tasks:
            observed_anomalies.append(
                "the fresh seed worker timed out before trace materialization on: "
                + ", ".join(sorted(timed_out_tasks))
            )
        _write_json(temporary / "debugger" / "overview.json", {
            "schema_version": 1,
            "generator": "deterministic evidence librarian; not a root-cause oracle",
            "selection_facts": {
                "targets": [item.task_id for item in panel.targets],
                "protections": [item.task_id for item in panel.protections],
                "baseline_repetitions": 5,
                "fresh_seed_outcomes": current_outcomes,
            },
            "observed_anomalies": observed_anomalies,
            "unresolved_questions": unresolved_questions,
            "interpretation_boundary": (
                "The index exposes selection and execution facts only. The Evolver "
                "must inspect exact traces and artifacts before claiming a cause."
            ),
        })
        _write_json(temporary / "sanitization.json", {
            "schema_version": 1,
            "credential_redactions": redactions,
            "copied_private_evaluator_material": False,
            "copied_official_solutions": False,
            "copied_validation_or_test_evidence": False,
            "large_text_artifact_limit_bytes": _FULL_ARTIFACT_LIMIT,
            "large_artifact_representation": "head_tail_preview",
        })

        record = authorize_evidence_tree(temporary)
        os.replace(temporary, destination)
        temporary = None
        report = {
            "schema_version": 1,
            "stage": stage,
            "destination": str(destination),
            "sha256": record.sha256,
            "member_count": len(record.members),
            "members": list(record.members),
            "task_ids": list(expected_tasks),
            "credential_redactions": redactions,
        }
        if stage != "A4":
            report["contract_arm"] = contract_arm
        if stage == "A6":
            report.update(
                {
                    "role_counts": {
                        "target": len(panel.targets),
                        "protection": len(panel.protections),
                        "sentinel": len(panel.sentinels),
                    },
                    "public_contract_evidence": exposes_public_contracts,
                    "public_contract_clause_count": (
                        public_contract_index["clause_count"]
                        if public_contract_index is not None
                        else 0
                    ),
                    "public_task_role_manifest_sha256": contract_payload.get(
                        "public_task_role_manifest_sha256"
                    ),
                    "public_contract_source_members_sha256": contract_payload.get(
                        "public_contract_source_members_sha256"
                    ),
                    "semantic_comparison": contract_payload.get(
                        "semantic_comparison"
                    ),
                    "seed_launch_identity_sha256": contract_payload.get(
                        "seed_launch_identity_sha256"
                    ),
                    "seed_identity_record_sha256": contract_payload.get(
                        "seed_identity_record_sha256"
                    ),
                }
            )
        return report
    finally:
        if temporary is not None and temporary.exists():
            shutil.rmtree(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--evolution-manifest", type=Path, required=True)
    parser.add_argument("--a4-manifest", type=Path, required=True)
    parser.add_argument("--evidence-run", type=Path, required=True)
    parser.add_argument("--arm", default="seed-evidence")
    parser.add_argument("--contract-arm")
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build(
        baseline_run=args.baseline_run,
        evolution_manifest_path=args.evolution_manifest,
        a4_manifest_path=args.a4_manifest,
        evidence_run=args.evidence_run,
        arm=args.arm,
        destination=args.destination.expanduser().resolve(),
        contract_arm=args.contract_arm,
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
