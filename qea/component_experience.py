"""Small cross-benchmark experience cards for component-search canaries.

QuantCodeEval and QFBench keep their own task contracts and verifiers.  This
module only gives the Evolver one common navigation surface over public task
state, answer-free outcomes, runtime summaries, artifacts, and component
experience.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Iterable, Mapping

from .quantcodeeval_components import (
    QuantComponentLedgerError,
    load_quantcodeeval_component_ledger,
)


class ComponentExperienceError(ValueError):
    """A breadth-canary evidence source cannot form public experience cards."""


_BENCHMARKS = {"qfbench", "quantcodeeval"}
_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_HASH_KEYS = {"sha256", "worker_digest", "candidate_digest", "attempt_id"}


def _json(path: Path, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ComponentExperienceError(f"cannot read {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise ComponentExperienceError(f"{label} must be a JSON object: {path}")
    return payload


def _without_hashes(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _without_hashes(child)
            for key, child in value.items()
            if str(key) not in _HASH_KEYS and not str(key).endswith("_sha256")
        }
    if isinstance(value, list):
        return [_without_hashes(child) for child in value]
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _copy_text(source: Path, destination: Path) -> None:
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ComponentExperienceError(f"cannot copy public text: {source}") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def _copy_tree(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination)


def _profile(row: Mapping[str, object]) -> dict[str, object]:
    benchmark = row.get("benchmark")
    task_id = row.get("task_id")
    role = row.get("role")
    tags = row.get("state_tags", [])
    if benchmark not in _BENCHMARKS:
        raise ComponentExperienceError(f"unsupported benchmark: {benchmark}")
    if not isinstance(task_id, str) or _TASK_ID.fullmatch(task_id) is None:
        raise ComponentExperienceError(f"invalid task ID: {task_id}")
    if role not in {"target", "protection", "reserve"}:
        raise ComponentExperienceError(f"invalid task role for {task_id}: {role}")
    if not isinstance(tags, list) or any(
        not isinstance(tag, str) or not tag.strip() for tag in tags
    ):
        raise ComponentExperienceError(f"invalid state tags for {task_id}")
    return {
        "benchmark": benchmark,
        "task_id": task_id,
        "role": role,
        "domain": row.get("domain"),
        "state_tags": list(dict.fromkeys(tag.strip() for tag in tags)),
    }


def _qfbench_index(root: Path) -> dict[str, Mapping[str, object]]:
    payload = _json(root / "debugger/task_index.json", label="QFBench task index")
    rows = payload.get("tasks")
    if not isinstance(rows, list):
        raise ComponentExperienceError("QFBench task index has no task list")
    return {
        str(row.get("task_id")): row
        for row in rows
        if isinstance(row, Mapping) and isinstance(row.get("task_id"), str)
    }


def _qfbench_card(
    *, source_root: Path, destination_root: Path, profile: Mapping[str, object]
) -> dict[str, object]:
    task_id = str(profile["task_id"])
    indexed = _qfbench_index(source_root).get(task_id)
    if indexed is None:
        raise ComponentExperienceError(f"QFBench evidence has no task {task_id}")
    source_task = source_root / "tasks" / task_id
    source_contract = source_root / "contracts" / task_id
    destination = destination_root / "benchmarks/qfbench/tasks" / task_id

    evaluation = _without_hashes(
        _json(source_task / "public_evaluation.json", label=f"{task_id} evaluation")
    )
    process = _without_hashes(
        _json(source_task / "process_summary.json", label=f"{task_id} process")
    )
    artifacts = _without_hashes(
        _json(source_task / "artifact_manifest.json", label=f"{task_id} artifacts")
    )
    _write_json(destination / "public_evaluation.json", evaluation)
    _write_json(destination / "process_summary.json", process)
    _write_json(destination / "artifact_manifest.json", artifacts)
    _copy_text(source_task / "worker_trace.jsonl", destination / "worker_trace.jsonl")
    _copy_text(source_task / "worker_final.txt", destination / "worker_final.txt")
    _copy_tree(source_task / "artifacts", destination / "artifacts")
    if source_contract.is_dir():
        _copy_text(source_contract / "instruction.md", destination / "instruction.md")
        _write_json(
            destination / "public_clauses.json",
            _without_hashes(
                _json(source_contract / "clauses.json", label=f"{task_id} clauses")
            ),
        )

    artifact_rows = artifacts.get("artifacts", []) if isinstance(artifacts, Mapping) else []
    artifact_paths = [
        str(row.get("path"))
        for row in artifact_rows
        if isinstance(row, Mapping) and isinstance(row.get("path"), str)
    ]
    return {
        "schema_version": 1,
        "task_key": f"qfbench:{task_id}",
        **profile,
        "execution_status": indexed.get("fresh_execution_status", "complete"),
        "evidence_completeness": indexed.get(
            "fresh_evidence_completeness", "full_structured_trace"
        ),
        "answer_free_outcome": evaluation,
        "runtime_summary": process,
        "artifact_paths": artifact_paths,
        "evidence_paths": {
            "instruction": f"benchmarks/qfbench/tasks/{task_id}/instruction.md",
            "public_clauses": f"benchmarks/qfbench/tasks/{task_id}/public_clauses.json",
            "evaluation": f"benchmarks/qfbench/tasks/{task_id}/public_evaluation.json",
            "process": f"benchmarks/qfbench/tasks/{task_id}/process_summary.json",
            "trace": f"benchmarks/qfbench/tasks/{task_id}/worker_trace.jsonl",
            "final": f"benchmarks/qfbench/tasks/{task_id}/worker_final.txt",
            "artifacts": f"benchmarks/qfbench/tasks/{task_id}/artifacts",
        },
    }


def _quantcodeeval_card(
    *, source_root: Path, destination_root: Path, profile: Mapping[str, object]
) -> dict[str, object]:
    task_id = str(profile["task_id"])
    current = _json(source_root / "current.json", label="QuantCodeEval current evaluation")
    evaluation_id = current.get("evaluation_id")
    if not isinstance(evaluation_id, str) or not evaluation_id:
        raise ComponentExperienceError("QuantCodeEval current evaluation ID is missing")
    source_task = source_root / "tasks" / task_id
    source_evaluation = source_task / "evaluations" / evaluation_id
    if not source_evaluation.is_dir():
        raise ComponentExperienceError(
            f"QuantCodeEval evidence has no current task {task_id}"
        )
    destination = destination_root / "benchmarks/quantcodeeval/tasks" / task_id
    _copy_text(source_task / "instruction.md", destination / "instruction.md")
    _copy_text(source_task / "paper_text.md", destination / "paper_text.md")

    copied: dict[str, object] = {}
    for name in (
        "official_and_families.json",
        "artifact_manifest.json",
        "strategy_ast_facts.json",
        "trace_facts.json",
        "process_facts.json",
        "final_facts.json",
    ):
        source = source_evaluation / name
        if not source.is_file():
            continue
        payload = _without_hashes(_json(source, label=f"{task_id} {name}"))
        _write_json(destination / name, payload)
        copied[name] = payload

    outcome = copied.get("official_and_families.json")
    if not isinstance(outcome, Mapping):
        raise ComponentExperienceError(f"QuantCodeEval task {task_id} has no outcome")
    artifact_manifest = copied.get("artifact_manifest.json", {})
    artifact_rows = (
        artifact_manifest.get("artifacts", [])
        if isinstance(artifact_manifest, Mapping)
        else []
    )
    return {
        "schema_version": 1,
        "task_key": f"quantcodeeval:{task_id}",
        **profile,
        "execution_status": "complete",
        "evidence_completeness": "answer_free_property_and_runtime_facts",
        "answer_free_outcome": outcome,
        "runtime_summary": copied.get("process_facts.json", {}),
        "artifact_paths": [
            str(row.get("path"))
            for row in artifact_rows
            if isinstance(row, Mapping) and isinstance(row.get("path"), str)
        ],
        "evidence_paths": {
            "instruction": f"benchmarks/quantcodeeval/tasks/{task_id}/instruction.md",
            "paper": f"benchmarks/quantcodeeval/tasks/{task_id}/paper_text.md",
            "evaluation": (
                f"benchmarks/quantcodeeval/tasks/{task_id}/official_and_families.json"
            ),
            "process": f"benchmarks/quantcodeeval/tasks/{task_id}/process_facts.json",
            "trace": f"benchmarks/quantcodeeval/tasks/{task_id}/trace_facts.json",
            "artifacts": (
                f"benchmarks/quantcodeeval/tasks/{task_id}/artifact_manifest.json"
            ),
        },
    }


def _tokens(values: Iterable[object]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        tokens.update(
            token
            for token in re.split(r"[^a-z0-9]+", value.casefold())
            if len(token) > 2
        )
    return tokens


def _component_cards(
    *, ledger_path: Path, portability: Mapping[str, str]
) -> list[dict[str, object]]:
    try:
        ledger = load_quantcodeeval_component_ledger(ledger_path)
    except QuantComponentLedgerError as exc:
        raise ComponentExperienceError(f"cannot load component ledger: {exc}") from exc
    cards: list[dict[str, object]] = []
    for component in ledger.components:
        trials = [
            trial
            for trial in ledger.trials
            if component.component_id in trial.available_components
        ]
        cards.append(
            {
                "schema_version": 1,
                "component_id": component.component_id,
                "source_benchmark": "quantcodeeval",
                "origin": component.origin.value,
                "portability": portability.get(component.component_id, "lesson_only"),
                "capabilities": list(component.capabilities),
                "description": component.description,
                "evidence": ledger.component_summary(component.component_id),
                "measured_task_ids": sorted({trial.task_id for trial in trials}),
                "observed_trials": [
                    {
                        "task_id": trial.task_id,
                        "role": trial.role.value,
                        "activated": component.component_id
                        in trial.activated_components,
                        "official_reward": trial.official_reward,
                        "observation": trial.observation,
                    }
                    for trial in trials
                ],
            }
        )
    return cards


def _relevant_components(
    task: Mapping[str, object], components: Iterable[Mapping[str, object]], limit: int
) -> list[dict[str, object]]:
    task_tokens = _tokens(task.get("state_tags", []))
    ranked: list[tuple[int, str, Mapping[str, object]]] = []
    for component in components:
        if (
            component.get("portability") == "quantcodeeval_only"
            and task.get("benchmark") != "quantcodeeval"
        ):
            continue
        capabilities = component.get("capabilities", [])
        component_tokens = _tokens(
            [component.get("component_id"), component.get("description")]
            + (list(capabilities) if isinstance(capabilities, list) else [])
        )
        overlap = sorted(task_tokens & component_tokens)
        measured = task.get("task_id") in component.get("measured_task_ids", [])
        score = len(overlap) + (4 if measured else 0)
        if score:
            ranked.append((score, str(component["component_id"]), component))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [
        {
            "component_id": row[2]["component_id"],
            "retrieval_score": row[0],
            "matched_state_terms": sorted(
                task_tokens
                & _tokens(
                    [row[2].get("component_id"), row[2].get("description")]
                    + list(row[2].get("capabilities", []))
                )
            ),
            "portability": row[2]["portability"],
        }
        for row in ranked[:limit]
    ]


def build_cross_benchmark_experience(
    *,
    destination: str | Path,
    task_profiles: Iterable[Mapping[str, object]],
    component_ledger_path: str | Path,
    qfbench_evidence_root: str | Path | None = None,
    quantcodeeval_evidence_root: str | Path | None = None,
    component_portability: Mapping[str, str] | None = None,
    relevant_component_limit: int = 4,
) -> dict[str, object]:
    """Build a self-contained, answer-free navigation corpus for both benchmarks."""

    if type(relevant_component_limit) is not int or not 1 <= relevant_component_limit <= 6:
        raise ComponentExperienceError("relevant component limit must be between 1 and 6")
    profiles = [_profile(row) for row in task_profiles]
    if not profiles:
        raise ComponentExperienceError("at least one task profile is required")
    keys = [(row["benchmark"], row["task_id"]) for row in profiles]
    if len(keys) != len(set(keys)):
        raise ComponentExperienceError("task profiles contain duplicates")

    roots = {
        "qfbench": (
            Path(qfbench_evidence_root).expanduser().resolve()
            if qfbench_evidence_root is not None
            else None
        ),
        "quantcodeeval": (
            Path(quantcodeeval_evidence_root).expanduser().resolve()
            if quantcodeeval_evidence_root is not None
            else None
        ),
    }
    target = Path(destination).expanduser().resolve()
    if target.exists():
        raise ComponentExperienceError(f"destination already exists: {target}")
    staging = target.with_name(target.name + ".partial")
    if staging.exists():
        raise ComponentExperienceError(f"staging destination already exists: {staging}")
    staging.mkdir(parents=True)
    try:
        cards: list[dict[str, object]] = []
        for profile in profiles:
            benchmark = str(profile["benchmark"])
            source_root = roots[benchmark]
            if source_root is None:
                raise ComponentExperienceError(
                    f"no {benchmark} evidence root was provided"
                )
            if benchmark == "qfbench":
                card = _qfbench_card(
                    source_root=source_root,
                    destination_root=staging,
                    profile=profile,
                )
            else:
                card = _quantcodeeval_card(
                    source_root=source_root,
                    destination_root=staging,
                    profile=profile,
                )
            cards.append(card)
            _write_json(
                staging / "tasks/cards" / f"{benchmark}--{profile['task_id']}.json",
                card,
            )

        components = _component_cards(
            ledger_path=Path(component_ledger_path).expanduser().resolve(),
            portability=component_portability or {},
        )
        _write_json(
            staging / "components/CATALOG.json",
            {
                "schema_version": 1,
                "component_count": len(components),
                "components": components,
            },
        )
        relevant = [
            {
                "task_key": card["task_key"],
                "components": _relevant_components(
                    card, components, relevant_component_limit
                ),
            }
            for card in cards
        ]
        _write_json(
            staging / "tasks/CATALOG.json",
            {"schema_version": 1, "task_count": len(cards), "tasks": cards},
        )
        _write_json(
            staging / "tasks/RELEVANT_COMPONENTS.json",
            {
                "schema_version": 1,
                "selection_policy": (
                    "public task-state term overlap plus exact measured-task experience"
                ),
                "max_components_per_task": relevant_component_limit,
                "tasks": relevant,
            },
        )
        _write_json(
            staging / "contract.json",
            {
                "schema_version": 1,
                "purpose": "cross_benchmark_component_search_breadth_canary",
                "benchmarks": sorted({str(row["benchmark"]) for row in cards}),
                "task_keys": [row["task_key"] for row in cards],
                "answer_free": True,
                "reference_answers_exposed": False,
                "component_cards_are_advisory": True,
                "candidate_contracts_remain_benchmark_specific": True,
                "search_operators": [
                    "REUSE",
                    "REFINE",
                    "COMPOSE",
                    "SYNTHESIZE",
                    "ROUTE",
                    "REPLICATE",
                    "PROTECT",
                    "TRANSFER",
                    "ABLATE",
                    "ABSTAIN",
                ],
            },
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
        return {
            "schema_version": 1,
            "destination": str(target),
            "task_count": len(cards),
            "component_count": len(components),
            "benchmarks": sorted({str(row["benchmark"]) for row in cards}),
        }
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def build_breadth_evolver_view(
    *,
    corpus_root: str | Path,
    destination: str | Path,
    task_key: str,
    include_component_history: bool,
    optimization_diagnostic_path: str | Path | None = None,
) -> dict[str, object]:
    """Select one task, history, and optional Evolver-only optimization feedback."""

    source = Path(corpus_root).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    if target.exists():
        raise ComponentExperienceError(f"destination already exists: {target}")
    task_catalog = _json(source / "tasks/CATALOG.json", label="task catalog")
    raw_tasks = task_catalog.get("tasks")
    if not isinstance(raw_tasks, list):
        raise ComponentExperienceError("task catalog has no task list")
    matches = [
        row
        for row in raw_tasks
        if isinstance(row, Mapping) and row.get("task_key") == task_key
    ]
    if len(matches) != 1:
        raise ComponentExperienceError(f"corpus has no unique task {task_key}")
    card = dict(matches[0])
    benchmark = str(card["benchmark"])
    task_id = str(card["task_id"])
    arm = "history-enabled" if include_component_history else "task-only"
    diagnostic: dict[str, object] | None = None
    if optimization_diagnostic_path is not None:
        if benchmark != "quantcodeeval":
            raise ComponentExperienceError(
                "answer-rich optimization feedback is only configured for QuantCodeEval"
            )
        diagnostic = _json(
            Path(optimization_diagnostic_path).expanduser().resolve(),
            label="optimization diagnostic",
        )
        if diagnostic.get("task_id") != task_id:
            raise ComponentExperienceError(
                "optimization diagnostic task does not match the selected task"
            )
        if diagnostic.get("feedback_mode") != "answer_rich_evolver":
            raise ComponentExperienceError(
                "optimization diagnostic has the wrong feedback mode"
            )
        if diagnostic.get("worker_visible") is not False:
            raise ComponentExperienceError(
                "optimization diagnostic must be marked Evolver-only"
            )
        card["feedback_mode"] = "answer_rich_evolver"
        card["evolver_only_evidence_paths"] = {
            "optimization_diagnostic": (
                f"benchmarks/quantcodeeval/tasks/{task_id}/"
                "optimization-diagnostic.json"
            )
        }

    target.mkdir(parents=True)
    (target / "access_log.jsonl").write_text("", encoding="utf-8")
    _write_json(
        target / "tasks/CATALOG.json",
        {"schema_version": 1, "task_count": 1, "tasks": [card]},
    )
    _write_json(
        target / "tasks/cards" / f"{benchmark}--{task_id}.json",
        card,
    )
    _copy_tree(
        source / "benchmarks" / benchmark / "tasks" / task_id,
        target / "benchmarks" / benchmark / "tasks" / task_id,
    )
    if diagnostic is not None:
        _write_json(
            target
            / "benchmarks"
            / "quantcodeeval"
            / "tasks"
            / task_id
            / "optimization-diagnostic.json",
            diagnostic,
        )

    relevant_rows: list[dict[str, object]] = []
    if include_component_history:
        component_source = source / "components/CATALOG.json"
        if not component_source.is_file():
            raise ComponentExperienceError("history-enabled view needs components")
        _copy_text(component_source, target / "components/CATALOG.json")
        relevant = _json(
            source / "tasks/RELEVANT_COMPONENTS.json",
            label="relevant components",
        )
        raw_relevant = relevant.get("tasks")
        if isinstance(raw_relevant, list):
            relevant_rows = [
                dict(row)
                for row in raw_relevant
                if isinstance(row, Mapping) and row.get("task_key") == task_key
            ]
    _write_json(
        target / "tasks/RELEVANT_COMPONENTS.json",
        {
            "schema_version": 1,
            "task_key": task_key,
            "history_enabled": include_component_history,
            "tasks": relevant_rows,
        },
    )
    instruction = (
        "Use only the authorized public and answer-free evidence for the selected "
        "task. Reconstruct the expected and Worker-observed Quant Research State, "
        "localize the earliest consequential mismatch, and compare at least two "
        "plausible component hypotheses. Predict the state transition that the "
        "selected component should make observable. You may modify any coherent "
        "harness component, not only the prompt. Do not assume a listed component "
        "is correct. If ACT, implement one bounded component hypothesis and run a "
        "discriminating component smoke after the final edit. Otherwise record a "
        "calibrated ABSTAIN."
    )
    if include_component_history:
        instruction += (
            " Inspect positive and negative component history, explain whether you "
            "REUSE, REFINE, COMPOSE, reject, or replace it, and do not repeat an "
            "unsupported intervention unchanged."
        )
    else:
        instruction += (
            " This arm intentionally contains no prior component catalog; infer the "
            "component from the current task runtime evidence alone."
        )
    if diagnostic is not None:
        instruction += (
            " This is a declared answer-rich optimization task. Read the Evolver-only "
            "optimization diagnostic, compare all retained attempts item by item, and "
            "separate the task-specific answer from a reusable missing capability. "
            "Choose REFINE, SPLIT, SYNTHESIZE, COMPOSE, or ABSTAIN. For ACT, record a compact "
            "failure signature naming the mechanism family, semantic state, pipeline "
            "phase, and observable that an unchanged component could test elsewhere. "
            "Never copy task answers, expected constants, or fixed task-only assertions "
            "into the reusable candidate."
        )
    quant_contract: dict[str, object] = {}
    if benchmark == "quantcodeeval":
        quant_contract = {
            "benchmark": "quantcodeeval",
            "decision_protocol": "quant_property_v2",
            "feedback_tier": (
                "answer_rich_optimization_v1"
                if diagnostic is not None
                else "answer_free_property_family_v2"
            ),
            "task_ids": [task_id],
            "target_task_ids": [task_id],
            "protection_task_ids": [],
            "history_required": False,
            "max_primary_components": 2,
            "max_declared_components": 9,
            "research_state_transition_required_for_act": True,
            "quant_failure_classification_required_for_act": False,
            "domain_tags_are_extensible": True,
            "failure_signature_required_for_act": diagnostic is not None,
            "optimization_answers_exposed_to_evolver": diagnostic is not None,
            "optimization_answers_exposed_to_worker": False,
            "worker_feedback_mode": "blind_public_task",
            "oracle_fields_exposed": diagnostic is not None,
        }
    _write_json(
        target / "contract.json",
        {
            "schema_version": 1,
            "stage": "BREADTH",
            "contract_arm": arm,
            "task_key": task_key,
            "answer_free": diagnostic is None,
            "component_history_enabled": include_component_history,
            "evolver_feedback_mode": (
                "answer_rich_evolver" if diagnostic is not None else "answer_free"
            ),
            "optimization_diagnostic": (
                f"benchmarks/quantcodeeval/tasks/{task_id}/"
                "optimization-diagnostic.json"
                if diagnostic is not None
                else None
            ),
            "evolver_instruction": instruction,
            "worker_evaluation_in_this_stage": False,
            **quant_contract,
        },
    )
    return {
        "schema_version": 1,
        "destination": str(target),
        "task_key": task_key,
        "arm": arm,
        "component_history_enabled": include_component_history,
        "evolver_feedback_mode": (
            "answer_rich_evolver" if diagnostic is not None else "answer_free"
        ),
        "retrieved_component_count": sum(
            len(row.get("components", []))
            for row in relevant_rows
            if isinstance(row.get("components", []), list)
        ),
    }


def build_coordinated_evolver_view(
    *,
    corpus_root: str | Path,
    destination: str | Path,
    task_keys: Iterable[str],
    include_component_history: bool,
    optimization_diagnostic_paths: Mapping[str, str | Path] | None = None,
) -> dict[str, object]:
    """Build one bounded multi-task view with exactly one selectable probe."""

    source = Path(corpus_root).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    selected_keys = list(dict.fromkeys(task_keys))
    if not 2 <= len(selected_keys) <= 4:
        raise ComponentExperienceError(
            "coordinated view requires between two and four unique tasks"
        )
    if target.exists():
        raise ComponentExperienceError(f"destination already exists: {target}")

    task_catalog = _json(source / "tasks/CATALOG.json", label="task catalog")
    raw_tasks = task_catalog.get("tasks")
    if not isinstance(raw_tasks, list):
        raise ComponentExperienceError("task catalog has no task list")
    by_key = {
        str(row.get("task_key")): dict(row)
        for row in raw_tasks
        if isinstance(row, Mapping) and isinstance(row.get("task_key"), str)
    }
    missing = [key for key in selected_keys if key not in by_key]
    if missing:
        raise ComponentExperienceError(
            f"corpus has no coordinated tasks: {sorted(missing)}"
        )
    cards = [by_key[key] for key in selected_keys]
    diagnostics: dict[str, dict[str, object]] = {}
    for task_key, raw_path in (optimization_diagnostic_paths or {}).items():
        if task_key not in selected_keys:
            raise ComponentExperienceError(
                f"optimization diagnostic has no selected task: {task_key}"
            )
        diagnostic = _json(
            Path(raw_path).expanduser().resolve(),
            label=f"{task_key} optimization diagnostic",
        )
        card = by_key[task_key]
        if diagnostic.get("task_id") != card.get("task_id"):
            raise ComponentExperienceError(
                "optimization diagnostic task does not match the selected task"
            )
        if (
            diagnostic.get("feedback_mode") != "answer_rich_evolver"
            or diagnostic.get("worker_visible") is not False
        ):
            raise ComponentExperienceError(
                "optimization diagnostic must be answer-rich and Evolver-only"
            )
        diagnostics[task_key] = diagnostic
        card["feedback_mode"] = "answer_rich_evolver"
        card["evolver_only_evidence_paths"] = {
            "optimization_diagnostic": (
                f"benchmarks/{card['benchmark']}/tasks/{card['task_id']}/"
                "optimization-diagnostic.json"
            )
        }
    target_keys = [
        str(card["task_key"]) for card in cards if card.get("role") == "target"
    ]
    protection_keys = [
        str(card["task_key"])
        for card in cards
        if card.get("role") == "protection"
    ]
    if len(target_keys) != 1:
        raise ComponentExperienceError(
            "coordinated view requires exactly one predeclared target task"
        )
    if not protection_keys:
        raise ComponentExperienceError(
            "coordinated view requires at least one protection task"
        )

    target.mkdir(parents=True)
    (target / "access_log.jsonl").write_text("", encoding="utf-8")
    for card in cards:
        benchmark = str(card["benchmark"])
        task_id = str(card["task_id"])
        _write_json(
            target / "tasks/cards" / f"{benchmark}--{task_id}.json",
            card,
        )
        _copy_tree(
            source / "benchmarks" / benchmark / "tasks" / task_id,
            target / "benchmarks" / benchmark / "tasks" / task_id,
        )
        task_key = str(card["task_key"])
        if task_key in diagnostics:
            _write_json(
                target
                / "benchmarks"
                / benchmark
                / "tasks"
                / task_id
                / "optimization-diagnostic.json",
                diagnostics[task_key],
            )
    _write_json(
        target / "tasks/CATALOG.json",
        {"schema_version": 1, "task_count": len(cards), "tasks": cards},
    )

    relevant = _json(
        source / "tasks/RELEVANT_COMPONENTS.json",
        label="relevant components",
    )
    raw_relevant = relevant.get("tasks")
    relevant_rows = [
        dict(row)
        for row in raw_relevant or []
        if isinstance(row, Mapping) and row.get("task_key") in selected_keys
    ]
    if include_component_history:
        component_source = source / "components/CATALOG.json"
        if not component_source.is_file():
            raise ComponentExperienceError(
                "history-enabled coordinated view needs components"
            )
        _copy_text(component_source, target / "components/CATALOG.json")
    else:
        relevant_rows = []
    _write_json(
        target / "tasks/RELEVANT_COMPONENTS.json",
        {
            "schema_version": 1,
            "history_enabled": include_component_history,
            "task_keys": selected_keys,
            "tasks": relevant_rows,
        },
    )

    instruction = (
        "Compare the selected Quant Research Trajectories before proposing a "
        "component. First decide whether at least two tasks share one concrete "
        "failure mechanism, quantitative object, or executable invariant; a broad "
        "Research-State label alone is not evidence of a match. Preserve a "
        "non-match as a valid conclusion. If a shared mechanism is supported, "
        "record the predeclared target as the one probe_task_key whose Worker "
        "result would best "
        "discriminate the leading hypothesis from a competitor. Implement one "
        "bounded reusable harness candidate and predict an observable action "
        "target: an artifact edit, a validator finding acted upon, or an "
        "evidence-grounded skip. Do not request Worker evaluation on every task. "
        "The remaining tasks are contrast trajectories and are evaluated only "
        "after a positive target result. Otherwise record calibrated ABSTAIN."
        " For ACT, use decide_candidate, set shared_mechanism to the concrete "
        "cross-task relation supported by both trajectories, and provide a "
        "from_scratch experiment_spec with no seed experience."
    )
    if include_component_history:
        instruction += (
            " Prior component cards are advisory. Explain any REUSE, REFINE, "
            "COMPOSE, rejection, or replacement rather than copying a component "
            "because its state tags overlap."
        )
    if diagnostics:
        instruction += (
            " This declared optimize-only view includes Evolver-only answer-rich "
            "diagnostics produced after a blind Worker attempt. Use them to separate "
            "the observed task failure from a reusable missing capability. Never "
            "copy expected values or task-specific answers into the candidate; the "
            "Worker remains blind to these diagnostics."
        )
    _write_json(
        target / "contract.json",
        {
            "schema_version": 1,
            "stage": "COORDINATED_BREADTH",
            "contract_arm": (
                "history-enabled" if include_component_history else "task-only"
            ),
            "task_keys": selected_keys,
            "target_task_keys": target_keys,
            "protection_task_keys": protection_keys,
            "task_ids": [str(card["task_id"]) for card in cards],
            "target_task_ids": [
                str(card["task_id"])
                for card in cards
                if card.get("role") == "target"
            ],
            "protection_task_ids": [
                str(card["task_id"])
                for card in cards
                if card.get("role") == "protection"
            ],
            "task_evidence_prefixes": {
                str(card["task_key"]): [
                    (
                        f"benchmarks/{card['benchmark']}/tasks/"
                        f"{card['task_id']}/"
                    ),
                    (
                        f"tasks/cards/{card['benchmark']}--"
                        f"{card['task_id']}.json"
                    ),
                ]
                for card in cards
            },
            "answer_free": not diagnostics,
            "component_history_enabled": include_component_history,
            "evolver_instruction": instruction,
            "decision_protocol": "quant_property_v2",
            "feedback_tier": (
                "answer_rich_optimization_v1"
                if diagnostics
                else "answer_free_property_family_v2"
            ),
            "optimization_answers_exposed_to_evolver": bool(diagnostics),
            "optimization_answers_exposed_to_worker": False,
            "history_required": False,
            "max_primary_components": 2,
            "max_declared_components": 9,
            "research_state_transition_required_for_act": True,
            "quant_failure_classification_required_for_act": False,
            "domain_tags_are_extensible": True,
            "autonomous_probe_required": True,
            "coordinated_evidence_required_for_act": True,
            "probe_seed_policy": "none",
            "shared_mechanism_assessment_required": True,
            "probe_task_selection_required_for_act": True,
            "max_worker_probes_this_round": 1,
            "positive_target_before_contrast_evaluation": True,
            "evolver_worker_evaluation_in_this_stage": False,
            "coordinator_selected_probe_evaluation_allowed": True,
            "worker_evaluation_in_this_stage": "conditional_singleton_dispatch",
        },
    )
    return {
        "schema_version": 1,
        "destination": str(target),
        "task_keys": selected_keys,
        "task_count": len(cards),
        "target_task_key": target_keys[0],
        "protection_task_keys": protection_keys,
        "component_history_enabled": include_component_history,
        "max_worker_probes_this_round": 1,
    }


__all__ = [
    "ComponentExperienceError",
    "build_breadth_evolver_view",
    "build_coordinated_evolver_view",
    "build_cross_benchmark_experience",
]
