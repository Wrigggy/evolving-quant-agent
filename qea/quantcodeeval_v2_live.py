"""One-round live activation canary for QuantCodeEval full-harness search v2.

This module intentionally stops before candidate benchmark evaluation.  It
reuses the exact measured H0, gives the real Evolver one isolated round to
edit and smoke the complete worker harness, and retains the result for a human
or later controller to decide whether a full T16/T24 candidate panel is worth
running.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Mapping

from .candidate_admission import (
    AdmissionPolicy,
    CandidateAdmissionError,
    admit_candidate,
)
from .backends.rootless_docker import RootlessDockerBackend
from .executors.sandbox_evolver import (
    SandboxEvolverConfig,
    SandboxFullHarnessProposer,
)
from .executors.sandbox_proxy import SandboxProxyConfig, SandboxProxyManager
from .loop_benchmark import hash_worker_directory
from .mutation_metrics import measure_mutation
from .quantcodeeval_experiment import (
    h0_evaluation_ref,
    materialize_h0_attempt_sources,
)
from .quantcodeeval_release import validate_quantcodeeval_release
from .quantcodeeval_history import append_quantcodeeval_history
from .quantcodeeval_search import (
    QuantSearchLimits,
    initialize_quantcodeeval_search,
    quantcodeeval_search_payload,
)
from .quantcodeeval_v2_evidence import build_quantcodeeval_v2_evidence
from .quantcodeeval_v2_loop import (
    QuantCandidateEvaluation,
    run_quantcodeeval_v2_loop,
)
from .resource_lease import HostResourceLeasePool
from .rootless_full_harness import (
    _default_health_probe,
    load_rootless_full_harness_config,
)


MODEL = "deepseek/deepseek-v4-flash-0731"
PROVIDER = "deepseek"
PROTOCOL = "quant_property_v2_live_activation_canary"
EXECUTABLE_COMPONENTS = frozenset(
    {"agent_config", "tools", "validator", "skills", "memory", "middleware", "routing"}
)


class QuantCodeEvalV2LiveError(RuntimeError):
    """A live activation canary identity or result is incomplete."""


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, value: object, *, replace: bool = False) -> None:
    payload = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise QuantCodeEvalV2LiveError(f"unsafe persisted record: {path}")
        if not replace:
            if path.read_text(encoding="utf-8") != payload:
                raise QuantCodeEvalV2LiveError(f"persisted record differs: {path}")
            return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _source_identity() -> dict[str, str]:
    package = Path(__file__).resolve().parent
    paths = (
        "executors/remote_evolver.py",
        "executors/sandbox_evolver.py",
        "evolve_agent_full/agent.yaml",
        "evolve_agent_full/systemprompt.md",
        "evolve_agent_full/tools/guarded_workspace.py",
        "quantcodeeval_history.py",
        "quantcodeeval_search.py",
        "quantcodeeval_v2_evidence.py",
        "quantcodeeval_v2_live.py",
        "quantcodeeval_v2_loop.py",
    )
    return {relative: _sha256(package / relative) for relative in paths}


def _proxy_audit(run_root: Path) -> dict[str, object]:
    path = run_root / "attempts/evolver-iteration-1/proxy-audit.jsonl"
    if not path.is_file():
        return {
            "request_count": 0,
            "completed_request_count": 0,
            "cost_complete": False,
            "provider_cost_usd": None,
            "provider_request_ids": [],
            "reason": "proxy audit is absent",
        }
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    completed = [
        row
        for row in rows
        if row.get("request_state") == "completed"
        and row.get("failure_class") is None
        and row.get("upstream_status_code") == 200
    ]
    costs = [row.get("provider_cost_usd") for row in completed]
    numeric_costs = [
        float(value)
        for value in costs
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    request_ids = [
        str(row["provider_request_id"])
        for row in completed
        if isinstance(row.get("provider_request_id"), str)
    ]
    return {
        "request_count": len(rows),
        "completed_request_count": len(completed),
        "all_requests_completed": len(rows) == len(completed) and bool(rows),
        "cost_complete": len(numeric_costs) == len(completed) and bool(completed),
        "provider_cost_usd": (
            sum(numeric_costs) if len(numeric_costs) == len(completed) else None
        ),
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in completed),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in completed),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in completed),
        "provider_request_ids": request_ids,
        "provider_request_ids_unique": len(request_ids) == len(set(request_ids)),
    }


def _seed_rejected_attempt_history(
    *,
    history_root: Path,
    prior_attempt_dir: Path,
    seed_worker_dir: Path,
    h0_rewards: Mapping[str, float],
) -> dict[str, object]:
    """Import one exact, answer-free rejected activation as searchable history."""

    prior = prior_attempt_dir.expanduser().resolve()
    attempt = prior / "evolutions/iteration-0001"
    summary_path = attempt / "summary.json"
    result_path = attempt / "result.json"
    candidate = attempt / "candidate"
    if not summary_path.is_file() or not result_path.is_file() or not candidate.is_dir():
        raise QuantCodeEvalV2LiveError(
            "prior rejected attempt lacks summary, result, or candidate"
        )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    discovery = summary.get("discovery_hypothesis")
    if not isinstance(discovery, Mapping) or discovery.get("decision") != "ACT":
        raise QuantCodeEvalV2LiveError("prior rejected attempt is not a persisted ACT")
    decision = discovery.get("hypothesis")
    if not isinstance(decision, Mapping) or decision.get("decision") != "ACT":
        raise QuantCodeEvalV2LiveError("prior rejected ACT decision is inconsistent")
    candidate_digest = hash_worker_directory(candidate)
    if result.get("candidate_digest") != candidate_digest:
        raise QuantCodeEvalV2LiveError("prior rejected candidate digest differs")
    components = tuple(str(value) for value in decision.get("components", ()))
    primary = tuple(str(value) for value in decision.get("primary_components", ()))
    metrics = measure_mutation(
        before_root=seed_worker_dir,
        after_root=candidate,
        declared_roles=components,
    )
    attribution_mismatch = metrics["declared_roles_match_actual"] is not True
    admission_error = None
    if not attribution_mismatch:
        try:
            admit_candidate(
                seed_worker_dir, candidate, AdmissionPolicy.qfbench_full()
            )
        except CandidateAdmissionError as exc:
            admission_error = str(exc)
    if not attribution_mismatch and admission_error is None:
        raise QuantCodeEvalV2LiveError(
            "prior rejected attempt now passes attribution and admission"
        )
    hypotheses = decision.get("hypotheses_considered", ())
    mechanism = next(
        (
            str(value.get("mechanism"))
            for value in hypotheses
            if isinstance(value, Mapping)
            and value.get("hypothesis_id") == decision.get("selected_hypothesis_id")
        ),
        str(decision.get("selected_hypothesis_id", "unknown mechanism")),
    )
    raw_tests = summary.get("component_tests", [])
    if not isinstance(raw_tests, list) or any(
        not isinstance(value, Mapping) for value in raw_tests
    ):
        raise QuantCodeEvalV2LiveError("prior component tests are invalid")
    if attribution_mismatch:
        reason = (
            "declared component file roles differ from the exact mutation: "
            f"declared={metrics['declared_roles']}, "
            f"actual={metrics['component_roles']}"
        )
        failure_stage = "candidate_contract"
    else:
        assert admission_error is not None
        reason = "independent full-harness admission failed: " + admission_error
        failure_stage = "candidate_admission"
    history = append_quantcodeeval_history(
        history_root=history_root,
        run_id=prior.name,
        iteration=1,
        parent_worker_dir=seed_worker_dir,
        candidate_worker_dir=candidate,
        decision=decision,
        mechanism=mechanism,
        primary_components=primary,
        declared_roles=components,
        component_tests=tuple(dict(value) for value in raw_tests),
        activation={
            "status": "failed",
            "failure_stage": failure_stage,
            "candidate_digest": candidate_digest,
            "reason": reason,
            "official_worker_evaluation_run": False,
        },
        evaluation={
            "official_evaluated": False,
            "official_rewards": dict(h0_rewards),
            "new_information": True,
            "reason": reason,
        },
        selection="rejected",
        rollback_reason=reason,
        allow_rejected_attribution_mismatch=attribution_mismatch,
    )
    return {
        "run_id": prior.name,
        "entry_id": history.entry_id,
        "candidate_digest": candidate_digest,
        "summary_sha256": _sha256(summary_path),
        "result_sha256": _sha256(result_path),
        "declared_roles": list(metrics["declared_roles"]),
        "actual_roles": list(metrics["component_roles"]),
        "reason": reason,
    }


def _prior_attempt_paths(
    value: str | Path | Iterable[str | Path] | None,
) -> tuple[Path, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, Path)):
        return (Path(value),)
    paths = tuple(Path(item) for item in value)
    if not paths:
        raise QuantCodeEvalV2LiveError("prior rejected attempt list is empty")
    if len({path.expanduser().resolve() for path in paths}) != len(paths):
        raise QuantCodeEvalV2LiveError("prior rejected attempt list is duplicated")
    return paths


def _selected_mechanism(decision: Mapping[str, object]) -> str:
    selected = decision.get("selected_hypothesis_id")
    hypotheses = decision.get("hypotheses_considered", ())
    if isinstance(hypotheses, (str, bytes)) or not isinstance(hypotheses, list):
        raise QuantCodeEvalV2LiveError("ACT hypotheses are invalid")
    for value in hypotheses:
        if isinstance(value, Mapping) and value.get("hypothesis_id") == selected:
            mechanism = value.get("mechanism")
            if isinstance(mechanism, str) and mechanism.strip():
                return mechanism.strip()
    raise QuantCodeEvalV2LiveError("ACT lacks its selected mechanism")


def _seed_full_candidate_failure_history(
    *,
    history_root: Path,
    activation_run_dir: Path,
    full_candidate_run_dir: Path,
    seed_worker_dir: Path,
    h0_evaluation_id: str,
) -> dict[str, object]:
    """Import one activation-passed, worker-contract-failed candidate."""

    activation_root = activation_run_dir.expanduser().resolve()
    full_root = full_candidate_run_dir.expanduser().resolve()
    live_path = activation_root / "LIVE-RESULT.json"
    preflight_path = full_root / "FULL-CANDIDATE-PREFLIGHT.json"
    failure_path = full_root / "FULL-CANDIDATE-RESULT.json"
    candidate = activation_root / "evolutions/iteration-0001/candidate"
    for path in (live_path, preflight_path, failure_path):
        if path.is_symlink() or not path.is_file():
            raise QuantCodeEvalV2LiveError(
                "full-candidate failure import lacks an immutable result surface"
            )
    if candidate.is_symlink() or not candidate.is_dir():
        raise QuantCodeEvalV2LiveError(
            "full-candidate failure import lacks its candidate snapshot"
        )
    live = json.loads(live_path.read_text(encoding="utf-8"))
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    if (
        not isinstance(live, Mapping)
        or live.get("status") != "PASS"
        or live.get("candidate_benchmark_evaluated") is not False
    ):
        raise QuantCodeEvalV2LiveError("source activation is not an unscored PASS")
    if (
        not isinstance(preflight, Mapping)
        or preflight.get("status") != "preflight_complete"
        or preflight.get("source_h0_evaluation_id") != h0_evaluation_id
    ):
        raise QuantCodeEvalV2LiveError("full-candidate preflight identity differs")
    if (
        not isinstance(failure, Mapping)
        or failure.get("status") != "evaluation_failed"
        or failure.get("official_evaluated") is not False
        or failure.get("benchmark_score_claimed") is not False
    ):
        raise QuantCodeEvalV2LiveError(
            "full-candidate result is not a fail-closed unscored panel"
        )
    candidate_digest = hash_worker_directory(candidate)
    if (
        candidate_digest != live.get("candidate_digest")
        or candidate_digest != preflight.get("candidate_worker_digest")
        or candidate_digest != failure.get("candidate_worker_digest")
    ):
        raise QuantCodeEvalV2LiveError("failed candidate digest differs")
    decision = live.get("decision")
    if not isinstance(decision, Mapping) or decision.get("decision") != "ACT":
        raise QuantCodeEvalV2LiveError("failed candidate lacks a legal ACT")
    components = tuple(str(value) for value in decision.get("components", ()))
    primary = tuple(
        str(value) for value in decision.get("primary_components", ())
    )
    if list(preflight.get("declared_roles", ())) != sorted(set(components)):
        raise QuantCodeEvalV2LiveError("failed candidate declared roles differ")
    tests = live.get("component_tests")
    if not isinstance(tests, list) or any(
        not isinstance(value, Mapping) for value in tests
    ):
        raise QuantCodeEvalV2LiveError("failed candidate component tests are invalid")
    activation = live.get("activation")
    if not isinstance(activation, Mapping) or activation.get("status") != "passed":
        raise QuantCodeEvalV2LiveError("failed candidate activation did not pass")
    attempts = failure.get("attempts")
    partial_audit = failure.get("partial_cost_and_lifecycle_audit")
    if not isinstance(attempts, list) or not attempts or any(
        not isinstance(value, Mapping) for value in attempts
    ):
        raise QuantCodeEvalV2LiveError("failed candidate has no task outcomes")
    if not isinstance(partial_audit, Mapping):
        raise QuantCodeEvalV2LiveError("failed candidate has no partial audit")
    if any(value.get("official_score_available") is not False for value in attempts):
        raise QuantCodeEvalV2LiveError("failed panel unexpectedly exposes a score")
    reason = (
        "candidate passed component activation but failed before official scoring "
        "at the worker artifact contract"
    )
    history = append_quantcodeeval_history(
        history_root=history_root,
        run_id=full_root.name,
        iteration=int(preflight.get("iteration", 1)),
        parent_worker_dir=seed_worker_dir,
        candidate_worker_dir=candidate,
        decision=dict(decision),
        mechanism=_selected_mechanism(decision),
        primary_components=primary,
        declared_roles=components,
        component_tests=tuple(dict(value) for value in tests),
        activation=dict(activation),
        evaluation={
            "schema_version": 1,
            "candidate_panel_attempted": True,
            "official_evaluated": False,
            "benchmark_score_claimed": False,
            "task_outcomes": [dict(value) for value in attempts],
            "cost_and_lifecycle_audit": dict(partial_audit),
            "new_information": True,
            "reason": reason,
        },
        selection="rejected",
        rollback_reason=reason,
    )
    return {
        "run_id": full_root.name,
        "activation_run_id": activation_root.name,
        "entry_id": history.entry_id,
        "candidate_digest": candidate_digest,
        "live_result_sha256": _sha256(live_path),
        "preflight_sha256": _sha256(preflight_path),
        "failure_result_sha256": _sha256(failure_path),
        "reason": reason,
    }


def _seed_scored_candidate_history(
    *,
    history_root: Path,
    activation_run_dir: Path,
    full_candidate_run_dir: Path,
    seed_worker_dir: Path,
    h0_evaluation_id: str,
    h0_rewards: Mapping[str, float],
) -> dict[str, object]:
    """Import one completed candidate panel as rejected search experience."""

    activation_root = activation_run_dir.expanduser().resolve()
    full_root = full_candidate_run_dir.expanduser().resolve()
    live_path = activation_root / "LIVE-RESULT.json"
    preflight_path = full_root / "FULL-CANDIDATE-PREFLIGHT.json"
    result_path = full_root / "FULL-CANDIDATE-RESULT.json"
    candidate = activation_root / "evolutions/iteration-0001/candidate"
    if any(not path.is_file() for path in (live_path, preflight_path, result_path)):
        raise QuantCodeEvalV2LiveError(
            "scored candidate import lacks its result surface"
        )
    if not candidate.is_dir():
        raise QuantCodeEvalV2LiveError(
            "scored candidate import lacks its candidate snapshot"
        )

    live = json.loads(live_path.read_text(encoding="utf-8"))
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if live.get("status") != "PASS" or live.get(
        "candidate_benchmark_evaluated"
    ) is not False:
        raise QuantCodeEvalV2LiveError("source activation is not an unscored PASS")
    if preflight.get("status") != "preflight_complete" or preflight.get(
        "source_h0_evaluation_id"
    ) != h0_evaluation_id:
        raise QuantCodeEvalV2LiveError("scored candidate preflight differs")
    if result.get("status") != "complete" or result.get(
        "official_evaluated"
    ) is not True:
        raise QuantCodeEvalV2LiveError("candidate panel is not a completed score")

    candidate_digest = hash_worker_directory(candidate)
    if any(
        value != candidate_digest
        for value in (
            live.get("candidate_digest"),
            preflight.get("candidate_worker_digest"),
            result.get("candidate_worker_digest"),
        )
    ):
        raise QuantCodeEvalV2LiveError("scored candidate snapshot differs")
    decision = live.get("decision")
    if not isinstance(decision, Mapping) or decision.get("decision") != "ACT":
        raise QuantCodeEvalV2LiveError("scored candidate lacks a legal ACT")
    components = tuple(str(value) for value in decision.get("components", ()))
    primary = tuple(
        str(value) for value in decision.get("primary_components", ())
    )
    tests = live.get("component_tests")
    activation = live.get("activation")
    if not isinstance(tests, list) or not isinstance(activation, Mapping):
        raise QuantCodeEvalV2LiveError("scored candidate lacks component evidence")
    if activation.get("status") != "passed":
        raise QuantCodeEvalV2LiveError("scored candidate activation did not pass")

    score_summary = result.get("score_summary")
    if not isinstance(score_summary, Mapping) or not isinstance(
        score_summary.get("task_rewards"), Mapping
    ):
        raise QuantCodeEvalV2LiveError("completed panel lacks task rewards")
    official_rewards = {
        str(task_id): float(value)
        for task_id, value in score_summary["task_rewards"].items()
    }
    attempts = result.get("attempts")
    if not isinstance(attempts, list):
        raise QuantCodeEvalV2LiveError("completed panel lacks answer-free outcomes")
    reason = (
        "completed candidate panel did not improve H0: "
        f"candidate={official_rewards}, h0={dict(h0_rewards)}"
    )
    append_quantcodeeval_history(
        history_root=history_root,
        run_id=full_root.name,
        iteration=int(preflight.get("iteration", 1)),
        parent_worker_dir=seed_worker_dir,
        candidate_worker_dir=candidate,
        decision=dict(decision),
        mechanism=_selected_mechanism(decision),
        primary_components=primary,
        declared_roles=components,
        component_tests=tuple(dict(value) for value in tests),
        activation=dict(activation),
        evaluation={
            "schema_version": 1,
            "candidate_panel_attempted": True,
            "official_evaluated": True,
            "official_rewards": official_rewards,
            "h0_official_rewards": dict(h0_rewards),
            "task_outcomes": [dict(value) for value in attempts],
            "cost_audit": dict(result.get("cost_audit") or {}),
            "new_information": True,
            "reason": reason,
        },
        selection="rejected",
        rollback_reason=reason,
    )
    return {
        "run_id": full_root.name,
        "activation_run_id": activation_root.name,
        "official_rewards": official_rewards,
        "reason": reason,
    }


def _activation_from_component_tests(
    candidate: Path,
    decision: Mapping[str, object],
    component_tests: tuple[Mapping[str, object], ...],
    iteration: int,
) -> dict[str, object]:
    digest = hash_worker_directory(candidate)
    primary = tuple(str(value) for value in decision.get("primary_components", ()))
    executable = tuple(value for value in primary if value in EXECUTABLE_COMPONENTS)
    latest: dict[str, Mapping[str, object]] = {}
    for record in component_tests:
        component = record.get("component")
        if isinstance(component, str):
            latest[component] = record
    activated = tuple(
        component
        for component in executable
        if latest.get(component, {}).get("status") == "passed"
        and latest.get(component, {}).get("candidate_digest") == digest
    )
    passed = bool(executable) and activated == executable
    return {
        "schema_version": 1,
        "status": "passed" if passed else "failed",
        "iteration": iteration,
        "candidate_digest": digest,
        "primary_components": list(primary),
        "executable_primary_components": list(executable),
        "activated_primary_components": list(activated),
        "basis": (
            "trusted Evolver sandbox component smoke bound to final candidate digest"
        ),
        "official_worker_evaluation_run": False,
    }


def run_quantcodeeval_v2_activation_canary(
    *,
    config_path: str | Path,
    release_dir: str | Path,
    run_dir: str | Path,
    evolver_image_ref: str,
    proxy_image_ref: str,
    prior_rejected_attempt_dir: str | Path | Iterable[str | Path] | None = None,
    prior_failed_candidate_activation_dir: str | Path | None = None,
    prior_failed_candidate_run_dir: str | Path | None = None,
    prior_scored_candidate_activation_dir: (
        str | Path | Iterable[str | Path] | None
    ) = None,
    prior_scored_candidate_run_dir: str | Path | Iterable[str | Path] | None = None,
    preflight_only: bool = False,
) -> dict[str, object]:
    """Run or preflight one real Evolver round without resampling H0."""

    root = Path(run_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    release = Path(release_dir).expanduser().resolve()
    release_identity = validate_quantcodeeval_release(release)
    config_file = Path(config_path).expanduser().resolve()
    config = load_rootless_full_harness_config(config_file)
    if config.allowed_model != MODEL or config.required_provider != PROVIDER:
        raise QuantCodeEvalV2LiveError("live config has the wrong model route")

    h0_root = release / "h0"
    seed = h0_root / "workers/H0"
    public = release / "public"
    h0 = h0_evaluation_ref(h0_root)
    seed_digest = hash_worker_directory(seed)
    if seed_digest != h0.worker_digest:
        raise QuantCodeEvalV2LiveError("released H0 worker digest differs")
    rewards = {
        task_id: float(result.official_reward)
        for task_id, result in h0.task_results.items()
    }
    prior_rejected_attempts = [
        _seed_rejected_attempt_history(
            history_root=root / "history",
            prior_attempt_dir=path,
            seed_worker_dir=seed,
            h0_rewards=rewards,
        )
        for path in _prior_attempt_paths(prior_rejected_attempt_dir)
    ]
    if (prior_failed_candidate_activation_dir is None) != (
        prior_failed_candidate_run_dir is None
    ):
        raise QuantCodeEvalV2LiveError(
            "failed candidate activation and full run must be supplied together"
        )
    prior_full_candidate_failure = None
    if prior_failed_candidate_run_dir is not None:
        assert prior_failed_candidate_activation_dir is not None
        prior_full_candidate_failure = _seed_full_candidate_failure_history(
            history_root=root / "history",
            activation_run_dir=Path(prior_failed_candidate_activation_dir),
            full_candidate_run_dir=Path(prior_failed_candidate_run_dir),
            seed_worker_dir=seed,
            h0_evaluation_id=h0.evaluation_id,
        )
    scored_activations = _prior_attempt_paths(
        prior_scored_candidate_activation_dir
    )
    scored_runs = _prior_attempt_paths(prior_scored_candidate_run_dir)
    if len(scored_activations) != len(scored_runs):
        raise QuantCodeEvalV2LiveError(
            "scored candidate activations and full runs must be paired"
        )
    prior_scored_candidates = [
        _seed_scored_candidate_history(
            history_root=root / "history",
            activation_run_dir=activation_dir,
            full_candidate_run_dir=full_run_dir,
            seed_worker_dir=seed,
            h0_evaluation_id=h0.evaluation_id,
            h0_rewards=rewards,
        )
        for activation_dir, full_run_dir in zip(scored_activations, scored_runs)
    ]

    backend = RootlessDockerBackend(
        docker_host=config.docker_host,
        expected_uid=config.expected_uid,
    )
    docker_preflight = backend.preflight(
        expected_server_version="29.4.1",
        expected_security_options=(
            "name=seccomp,profile=builtin",
            "name=rootless",
            "name=cgroupns",
        ),
        image_ids=(evolver_image_ref, proxy_image_ref),
    )
    plan_material = {
        "schema_version": 1,
        "protocol": PROTOCOL,
        "run_id": root.name,
        "claim_scope": (
            "one real Evolver edit-and-smoke round; no candidate benchmark score"
        ),
        "h0_evaluation_id": h0.evaluation_id,
        "h0_worker_digest": seed_digest,
        "h0_official_rewards": rewards,
        "h0_resampled": False,
        "release_identity": release_identity,
        "config_sha256": _sha256(config_file),
        "model": MODEL,
        "required_provider": PROVIDER,
        "allow_fallbacks": False,
        "evolver_image_ref": evolver_image_ref,
        "proxy_image_ref": proxy_image_ref,
        "docker_preflight_identity_sha256": docker_preflight.identity_sha256,
        "source_sha256": _source_identity(),
        "prior_rejected_attempts": prior_rejected_attempts,
        "prior_full_candidate_failure": prior_full_candidate_failure,
        "prior_scored_candidates": prior_scored_candidates,
        "search_limits": asdict(
            QuantSearchLimits(
                max_rounds=1,
                max_no_information_rounds=1,
                max_consecutive_abstain=1,
                max_model_requests=64,
                max_cost_usd=1.0,
            )
        ),
    }
    plan = {
        **plan_material,
        "plan_identity_sha256": _canonical_sha256(plan_material),
        "status": "preflight_complete",
        "model_request_count": 0,
    }
    _atomic_json(root / "LIVE-PREFLIGHT.json", plan)
    if preflight_only:
        return plan

    proxy_manager = SandboxProxyManager(
        backend=backend,
        config=SandboxProxyConfig(
            image_ref=proxy_image_ref,
            resource_contract=config.proxy_resources,
            token_file=config.token_file,
            upstream_base_url=config.upstream_base_url,
            allowed_path_prefix=config.allowed_path_prefix,
            allowed_model=MODEL,
            required_provider=PROVIDER,
            timeout_seconds=120,
            finalize_timeout_seconds=360,
            expect_request=True,
        ),
    )
    pool = HostResourceLeasePool(
        config.capacity,
        config.headroom,
        _default_health_probe(root),
    )
    proposer = SandboxFullHarnessProposer(
        config=SandboxEvolverConfig(
            image_ref=evolver_image_ref,
            resource_contract=config.evolver_resources,
            command_timeout_seconds=1800,
            lease_timeout_seconds=float(config.lease_timeout_seconds),
        ),
        backend=backend,
        lifecycle_root=root / "lifecycles",
        proxy_manager=proxy_manager,
        resource_pool=pool,
        model_name=MODEL,
    )
    attempts = materialize_h0_attempt_sources(
        master_root=root,
        h0_root=h0_root,
        evaluation=h0,
    )
    public_roots = {
        task_id: public / "tasks" / task_id for task_id in h0.task_results
    }

    def evidence_builder(state, iteration, history_root):
        return build_quantcodeeval_v2_evidence(
            destination=root / "evidence" / f"iteration-{iteration:04d}",
            public_task_roots=public_roots,
            attempts=attempts,
            current_evaluation_id=h0.evaluation_id,
            history_root=history_root,
            iteration_summaries=(
                {
                    "iteration": item.iteration,
                    "selection": item.selection.value,
                    "reason": item.reason,
                }
                for item in state.rounds
            ),
        )

    def activation_only_evaluator(
        parent, candidate, decision, tests, activation, iteration
    ):
        audit = _proxy_audit(root)
        request_count = int(audit.get("request_count") or 0)
        audited_cost = audit.get("provider_cost_usd")
        return QuantCandidateEvaluation(
            official_rewards=rewards,
            answer_free_evaluation={
                "schema_version": 1,
                "activation": dict(activation),
                "official_candidate_panel_run": False,
                "h0_evaluation_id": h0.evaluation_id,
            },
            official_evaluated=False,
            new_information=True,
            reason="activation canary retained candidate without running T16/T24",
            # The outer loop already counts one proposer call.  A NexAU
            # proposal may contain many provider turns, so add the remainder
            # from the finalized exact proxy audit.
            model_requests=max(0, request_count - 1),
            cost_usd=(
                float(audited_cost)
                if isinstance(audited_cost, (int, float))
                and not isinstance(audited_cost, bool)
                else 0.0
            ),
        )

    state = initialize_quantcodeeval_search(
        run_id=root.name,
        h0_digest=seed_digest,
        h0_official_rewards=rewards,
        limits=QuantSearchLimits(**plan_material["search_limits"]),
    )
    final = run_quantcodeeval_v2_loop(
        state=state,
        run_dir=root,
        seed_worker_dir=seed,
        evolver_dir=Path(__file__).resolve().parent / "evolve_agent_full",
        proposer=proposer,
        evidence_builder=evidence_builder,
        activation_runner=_activation_from_component_tests,
        candidate_evaluator=activation_only_evaluator,
        diagnosis_builder=lambda current, iteration: (
            "T16 is protected at reward 1; T24 remains incomplete. Earlier five-round "
            "prompt-only mutations produced no gain or regressions. Later immutable "
            "history may include activation-passed candidates that failed the worker "
            "artifact contract before official scoring; treat those as component-level "
            "delivery evidence, never as task reward zero. History may also include a "
            "completed candidate that regressed the protected task and still missed "
            "target delivery; do not repeat that broad intervention unchanged. Use the "
            "latest scored history too: a later candidate preserved T16 and moved T24 "
            "from one Type-A plus one Type-B failure to one remaining Type-A failure, "
            "so retain or refine that useful mechanism instead of treating it as an "
            "all-or-nothing zero. Use the "
            "exact answer-free "
            "evidence and immutable attempt history to choose between at least two "
            "mechanisms. Components are exact changed file roles, not conceptual "
            "capability names. If ACT, "
            "prefer a testable executable harness component, edit it coherently with "
            "its bindings, and rerun its component smoke after the final edit."
        ),
    )
    round_payload = json.loads(
        (root / "rounds/iteration-0001.json").read_text(encoding="utf-8")
    )
    decision = round_payload["decision"]
    activation = round_payload["activation"]
    proxy_audit = _proxy_audit(root)
    if decision.get("decision") == "ABSTAIN":
        status = "CALIBRATED_ABSTAIN"
    elif activation.get("status") == "passed":
        status = "PASS"
    else:
        status = "FAIL"
    result_material = {
        "schema_version": 1,
        "protocol": PROTOCOL,
        "status": status,
        "plan_identity_sha256": plan["plan_identity_sha256"],
        "h0_evaluation_id": h0.evaluation_id,
        "h0_resampled": False,
        "candidate_benchmark_evaluated": False,
        "benchmark_score_claimed": False,
        "decision": decision,
        "candidate_digest": round_payload.get("candidate_digest"),
        "history_entry_id": round_payload.get("history_entry_id"),
        "selection": round_payload.get("selection"),
        "activation": activation,
        "component_tests": round_payload.get("component_tests"),
        "search_state": quantcodeeval_search_payload(final),
        "proxy_audit": proxy_audit,
    }
    result = {
        **result_material,
        "result_identity_sha256": _canonical_sha256(result_material),
    }
    _atomic_json(root / "LIVE-RESULT.json", result)
    return result


__all__ = [
    "QuantCodeEvalV2LiveError",
    "run_quantcodeeval_v2_activation_canary",
]
