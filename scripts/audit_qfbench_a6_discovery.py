#!/usr/bin/env python3
"""Audit the A6 raw/evidence/evidence-plus-contract discovery ladder."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Iterable, Mapping

if __name__ == "__main__":
    # A6 releases are content-addressed and must not be mutated by imports.
    sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.public_contract_evidence import (  # noqa: E402
    PublicContractEvidenceError,
    load_public_contract_clause,
)
from scripts.audit_qfbench_a5_discovery import audit as audit_a5  # noqa: E402


_ARMS = ("A6-R", "A6-E", "A6-EC")
_CONTRACT_DIFFERENCE_FIELDS = frozenset(
    {
        "contract_arm",
        "decision_protocol",
        "probe_policy",
        "public_contract_evidence",
        "public_contract_index",
        "public_contract_source_members_sha256",
        "public_task_role_manifest_sha256",
        "semantic_comparison",
    }
)


def _json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _label_path(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    if not separator or not label:
        raise argparse.ArgumentTypeError("value must be LABEL=PATH")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"run directory is unavailable: {path}")
    return label, path


def _label_file(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    if not separator or not label:
        raise argparse.ArgumentTypeError("value must be LABEL=PATH")
    path = Path(raw_path).expanduser().resolve()
    if path.is_symlink() or not path.is_file():
        raise argparse.ArgumentTypeError(f"audit file is unavailable: {path}")
    return label, path


def _arm(value: str) -> str:
    normalized = value.strip().upper().replace("_", "-")
    if normalized not in _ARMS:
        raise ValueError(f"unknown A6 arm label: {value!r}")
    return normalized


def _digest(root: Path, members: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(members):
        payload = (root / relative).read_bytes()
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _evidence_byte_record(run_dir: Path) -> dict[str, object]:
    root = run_dir / "authorized-evidence"
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"run has no staged authorized evidence: {run_dir}")
    members = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.name != "access_log.jsonl"
    )
    shared = [
        relative
        for relative in members
        if relative != "contract.json" and not relative.startswith("contracts/")
    ]
    semantic = [relative for relative in members if relative.startswith("contracts/")]
    contract = _json(root / "contract.json")
    return {
        "root": str(root),
        "contract": contract,
        "shared_core_members": shared,
        "shared_core_sha256": _digest(root, shared),
        "semantic_contract_members": semantic,
        "semantic_contract_sha256": _digest(root, semantic) if semantic else None,
    }


def _json_digest(payload: object) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _prediction_audit(
    *,
    arm: str,
    path: Path,
    prediction: Mapping[str, object],
    candidate_root: Path,
) -> dict[str, object]:
    payload = _json(path)
    if payload.get("schema_version") != 1:
        raise ValueError(f"{arm} prediction audit schema is unsupported")
    if payload.get("arm") != arm:
        raise ValueError(f"{arm} prediction audit names a different arm")
    if payload.get("adjudication_scope") != (
        "primary_component_specific_observable_prediction"
    ):
        raise ValueError(f"{arm} prediction audit has the wrong scope")
    expected_digest = _json_digest(prediction)
    if payload.get("prediction_sha256") != expected_digest:
        raise ValueError(f"{arm} prediction audit is not bound to the proposal")
    status = payload.get("status")
    if status not in {"supported", "falsified", "insufficient"}:
        raise ValueError(f"{arm} prediction audit status is invalid")
    evidence_refs = payload.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs or any(
        not isinstance(value, str) or not value.strip() for value in evidence_refs
    ):
        raise ValueError(f"{arm} prediction audit needs exact evidence_refs")
    unresolved_refs = [
        value
        for value in evidence_refs
        if not _authorized_file_exists(candidate_root, value)
    ]
    if unresolved_refs:
        raise ValueError(
            f"{arm} prediction audit has unresolved evidence_refs: "
            + ", ".join(unresolved_refs)
        )
    rationale = payload.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError(f"{arm} prediction audit needs a rationale")
    if payload.get("causal_truth_judged") is not False:
        raise ValueError(f"{arm} prediction audit must not certify causal truth")
    return {
        **payload,
        "prediction_sha256": expected_digest,
        "verified_prediction_binding": True,
    }


def _authorized_file_exists(root: Path, relative: object) -> bool:
    if not isinstance(relative, str):
        return False
    path = Path(relative)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        return False
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            return False
    return current.is_file()


def _grounded_triples(
    state: Mapping[str, object], *, evidence_root: Path
) -> list[dict[str, object]]:
    hypothesis = state.get("hypothesis")
    hypothesis = hypothesis if isinstance(hypothesis, Mapping) else {}
    raw = hypothesis.get("grounded_semantic_comparisons")
    grounded = [value for value in raw if isinstance(value, Mapping)] \
        if isinstance(raw, list) else []
    seen_probe_ids = {
        value.get("probe_id")
        for value in grounded
        if isinstance(value.get("probe_id"), str)
    }
    raw_probes = hypothesis.get("probe_records_used")
    used_probes = [value for value in raw_probes if isinstance(value, Mapping)] \
        if isinstance(raw_probes, list) else []
    selected = hypothesis.get("selected_hypothesis_id")
    raw_eliminated = hypothesis.get("hypotheses_eliminated")
    eliminated = {
        value for value in raw_eliminated if isinstance(value, str)
    } if isinstance(raw_eliminated, list) else set()
    attempts: list[tuple[Mapping[str, object], bool]] = [
        (value, True) for value in grounded
    ]
    for probe in used_probes:
        probe_id = probe.get("probe_id")
        if (
            probe.get("probe_kind") != "typed_contract_artifact_trace_v1"
            or not isinstance(probe_id, str)
            or probe_id in seen_probe_ids
        ):
            continue
        matches = probe.get("expectation_matches")
        matches = matches if isinstance(matches, Mapping) else {}
        attempts.append(
            (
                {
                    **dict(probe),
                    "selected_hypothesis_id": selected,
                    "contradicted_hypothesis_ids": sorted(
                        value for value in eliminated if matches.get(value) is False
                    ),
                },
                False,
            )
        )

    triples: list[dict[str, object]] = []
    for value, declared_grounding in attempts:
        clause = value.get("clause")
        artifact = value.get("artifact")
        trace = value.get("trace")
        clause = clause if isinstance(clause, Mapping) else {}
        artifact = artifact if isinstance(artifact, Mapping) else {}
        trace = trace if isinstance(trace, Mapping) else {}
        task_id = value.get("task_id")
        clause_id = clause.get("clause_id")
        clause_sha256 = clause.get("text_sha256")
        clause_resolves = False
        if all(
            isinstance(item, str) for item in (task_id, clause_id, clause_sha256)
        ):
            try:
                indexed_clause, _ = load_public_contract_clause(
                    evidence_root=evidence_root,
                    task_id=task_id,
                    clause_id=clause_id,
                )
            except (PublicContractEvidenceError, OSError):
                pass
            else:
                clause_resolves = indexed_clause.get("text_sha256") == clause_sha256
        selector = artifact.get("selector")
        relation = value.get("semantic_relation")
        explicit_relation = relation in {
            "supports",
            "contradicts",
            "insufficient",
        }
        structurally_complete = all(
            (
                isinstance(task_id, str),
                isinstance(clause_id, str),
                isinstance(clause_sha256, str),
                isinstance(artifact.get("path"), str),
                isinstance(selector, Mapping),
                isinstance(selector.get("kind"), str),
                isinstance(selector.get("value"), str),
                isinstance(artifact.get("value_type"), str),
                isinstance(trace.get("path"), str),
                isinstance(trace.get("phase"), str),
                isinstance(trace.get("phase_present"), bool),
                explicit_relation,
            )
        )
        artifact_resolves = _authorized_file_exists(
            evidence_root, artifact.get("path")
        )
        trace_resolves = _authorized_file_exists(evidence_root, trace.get("path"))
        complete = (
            structurally_complete
            and clause_resolves
            and artifact_resolves
            and trace_resolves
        )
        contradicted = value.get("contradicted_hypothesis_ids")
        contradicted = (
            [item for item in contradicted if isinstance(item, str)]
            if isinstance(contradicted, list)
            else []
        )
        selected_id = value.get("selected_hypothesis_id")
        act_evidence_signature_valid = (
            complete
            and relation in {"supports", "contradicts"}
            and isinstance(selected_id, str)
            and bool(contradicted)
        )
        act_grounding_valid = act_evidence_signature_valid and declared_grounding
        triples.append(
            {
                "probe_id": value.get("probe_id"),
                "task_id": task_id,
                "clause_id": clause_id,
                "clause_text_sha256": clause_sha256,
                "clause_resolves": clause_resolves,
                "artifact_path": artifact.get("path"),
                "artifact_selector": selector,
                "artifact_value_type": artifact.get("value_type"),
                "artifact_shape": artifact.get("shape"),
                "artifact_resolves": artifact_resolves,
                "trace_path": trace.get("path"),
                "trace_phase": trace.get("phase"),
                "trace_phase_present": trace.get("phase_present"),
                "trace_resolves": trace_resolves,
                "semantic_relation": relation,
                "explicit_relation": explicit_relation,
                "selected_hypothesis_id": selected_id,
                "contradicted_hypothesis_ids": contradicted,
                "declared_as_grounding": declared_grounding,
                "complete_grounded_triple": complete,
                "act_evidence_signature_valid": act_evidence_signature_valid,
                "act_grounding_valid": act_grounding_valid,
                "causal_truth_certified": False,
            }
        )
    return triples


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _panel_roles(
    manifest: Mapping[str, object],
) -> tuple[dict[str, str], set[str], set[str], set[str], list[str]]:
    panel = manifest.get("panel")
    if not isinstance(panel, Mapping):
        raise ValueError("A6 manifest has no panel")
    sentinel_items = panel.get("sentinels")
    if sentinel_items is None:
        sentinel_items = panel.get("coverage_sentinels", [])
    raw_roles = {
        "target": panel.get("targets", []),
        "protection": panel.get("protections", []),
        "sentinel": sentinel_items,
    }
    domains: dict[str, str] = {}
    role_ids: dict[str, set[str]] = {}
    ordered: list[str] = []
    for role, raw_items in raw_roles.items():
        if not isinstance(raw_items, list):
            raise ValueError(f"A6 panel {role} items must be an array")
        ids: set[str] = set()
        for item in raw_items:
            if not isinstance(item, Mapping):
                raise ValueError(f"A6 panel {role} item must be an object")
            task_id = item.get("task_id")
            domain = item.get("domain")
            if not isinstance(task_id, str) or not task_id:
                raise ValueError(f"A6 panel {role} item has no task_id")
            if not isinstance(domain, str) or not domain:
                raise ValueError(f"A6 panel task {task_id!r} has no domain")
            if task_id in domains:
                raise ValueError(f"A6 panel task roles overlap: {task_id}")
            domains[task_id] = domain
            ids.add(task_id)
            ordered.append(task_id)
        role_ids[role] = ids
    declared = panel.get("task_ids")
    if not isinstance(declared, list) or declared != ordered:
        raise ValueError("A6 panel task_ids differ from ordered role members")
    return (
        domains,
        role_ids["target"],
        role_ids["protection"],
        role_ids["sentinel"],
        ordered,
    )


def _domain_delta_summary(
    *,
    task_ids: set[str],
    domains: Mapping[str, str],
    deltas: Mapping[str, float],
) -> dict[str, object]:
    grouped: dict[str, list[str]] = {}
    for task_id in sorted(task_ids):
        grouped.setdefault(domains[task_id], []).append(task_id)
    records: dict[str, object] = {}
    complete_means: list[float] = []
    for domain in sorted(grouped):
        members = grouped[domain]
        missing = [task_id for task_id in members if task_id not in deltas]
        mean = (
            sum(deltas[task_id] for task_id in members) / len(members)
            if not missing
            else None
        )
        if mean is not None:
            complete_means.append(mean)
        records[domain] = {
            "task_ids": members,
            "observed_task_count": len(members) - len(missing),
            "missing_task_ids": missing,
            "mean_reward_delta": mean,
        }
    complete = len(complete_means) == len(grouped)
    return {
        "domain_count": len(grouped),
        "domains": records,
        "complete": complete,
        "macro_reward_delta": (
            sum(complete_means) / len(complete_means)
            if complete and complete_means
            else None
        ),
    }


def _reward_audit(
    *,
    candidate_evaluation: object,
    domains: Mapping[str, str],
    targets: set[str],
    protections: set[str],
    sentinels: set[str],
    ordered_task_ids: list[str],
) -> dict[str, object]:
    raw_vectors: object = None
    if isinstance(candidate_evaluation, Mapping):
        outcome = candidate_evaluation.get("outcome")
        if isinstance(outcome, Mapping):
            raw_vectors = outcome.get("task_vectors")
    vectors = raw_vectors if isinstance(raw_vectors, Mapping) else {}
    deltas: dict[str, float] = {}
    invalid: list[str] = []
    for task_id in ordered_task_ids:
        vector = vectors.get(task_id)
        reward = vector.get("reward") if isinstance(vector, Mapping) else None
        delta = _finite_number(reward)
        if delta is None:
            invalid.append(task_id)
        else:
            deltas[task_id] = delta
    extras = sorted(
        str(task_id) for task_id in vectors if str(task_id) not in domains
    )
    stable_ids = targets | protections
    all_domains = _domain_delta_summary(
        task_ids=set(ordered_task_ids), domains=domains, deltas=deltas
    )
    stable_domains = _domain_delta_summary(
        task_ids=stable_ids, domains=domains, deltas=deltas
    )
    target_complete = targets <= set(deltas)
    protection_complete = protections <= set(deltas)
    return {
        "status": (
            "complete"
            if not invalid and not extras
            else "missing_or_invalid_task_scores"
            if isinstance(raw_vectors, Mapping)
            else "candidate_evaluation_unavailable"
        ),
        "complete": not invalid and not extras,
        "task_reward_deltas": {
            task_id: deltas.get(task_id) for task_id in ordered_task_ids
        },
        "missing_or_invalid_task_ids": invalid,
        "unexpected_task_ids": extras,
        "target_reward_deltas": {
            task_id: deltas.get(task_id) for task_id in sorted(targets)
        },
        "strict_protection_reward_deltas": {
            task_id: deltas.get(task_id) for task_id in sorted(protections)
        },
        "volatile_sentinel_reward_deltas": {
            task_id: deltas.get(task_id) for task_id in sorted(sentinels)
        },
        "positive_target_task_count": (
            sum(deltas[task_id] > 0 for task_id in targets)
            if target_complete
            else None
        ),
        "strict_protection_regression_count": (
            sum(deltas[task_id] < 0 for task_id in protections)
            if protection_complete
            else None
        ),
        "all_16_descriptive_six_domain": {
            **all_domains,
            "scope": "all target, strict-protection, and volatile-sentinel tasks",
            "used_for_advancement": False,
        },
        "stable_14_task_five_domain": {
            **stable_domains,
            "scope": "repeat-failure targets and strict protections only",
            "used_for_advancement": True,
        },
        "volatile_sentinels_excluded_from_stable_gate": True,
    }


def _abstain_calibration(
    *,
    decision: str,
    state: Mapping[str, object],
    mutation_metrics: object,
    diff: object,
    triples: list[Mapping[str, object]],
) -> dict[str, object]:
    if decision != "ABSTAIN":
        return {
            "applicable": False,
            "calibrated_abstain": None,
            "status": (
                "not_applicable_act" if decision == "ACT" else "invalid_decision"
            ),
        }
    hypothesis = state.get("hypothesis")
    hypothesis = hypothesis if isinstance(hypothesis, Mapping) else {}
    hypotheses = hypothesis.get("hypotheses_considered")
    hypotheses = (
        [item for item in hypotheses if isinstance(item, Mapping)]
        if isinstance(hypotheses, list)
        else []
    )
    probes = hypothesis.get("probe_records_used")
    probes = (
        [item for item in probes if isinstance(item, Mapping)]
        if isinstance(probes, list)
        else []
    )
    eliminated_raw = hypothesis.get("hypotheses_eliminated")
    eliminated = {
        item for item in eliminated_raw if isinstance(item, str)
    } if isinstance(eliminated_raw, list) else set()
    selected = hypothesis.get("selected_hypothesis_id")
    probed_ids = {
        str(hypothesis_id)
        for probe in probes
        for hypothesis_id in (
            probe.get("hypothesis_expectations", {}).keys()
            if isinstance(probe.get("hypothesis_expectations"), Mapping)
            else ()
        )
    }
    failure_types = hypothesis.get("failure_types")
    recurrent_type = (
        any(
            isinstance(item, Mapping)
            and isinstance(item.get("member_tasks"), list)
            and len(
                {
                    value
                    for value in item["member_tasks"]
                    if isinstance(value, str)
                }
            )
            >= 2
            for item in failure_types
        )
        if isinstance(failure_types, list)
        else False
    )
    base_act_evidence = (
        recurrent_type
        and isinstance(selected, str)
        and bool(selected)
        and bool(eliminated)
        and {selected, *eliminated} <= probed_ids
    )
    semantic_required = state.get("protocol") == "semantic_contract_v1"
    typed_act_evidence = any(
        item.get("act_evidence_signature_valid") is True for item in triples
    )
    authorized_act_gate_evidence = base_act_evidence and (
        typed_act_evidence if semantic_required else True
    )
    abstain_reason = hypothesis.get("abstain_reason")
    reason_recorded = isinstance(abstain_reason, str) and bool(abstain_reason.strip())
    uncertainty = hypothesis.get("uncertainty")
    uncertainty_recorded = isinstance(uncertainty, str) and bool(uncertainty.strip())
    insufficient_contrast = any(
        item.get("insufficient_contrast") is True for item in hypotheses
    )
    insufficient_semantic_relation = any(
        probe.get("semantic_relation") == "insufficient" for probe in probes
    )
    unresolved_recorded = reason_recorded and (
        insufficient_contrast
        or insufficient_semantic_relation
        or not eliminated
        or not isinstance(selected, str)
    )
    components = hypothesis.get("components")
    no_components = components in (None, [])
    metric_unchanged: bool | None = None
    if isinstance(mutation_metrics, Mapping):
        changed = mutation_metrics.get("changed_file_count")
        if isinstance(changed, int) and not isinstance(changed, bool):
            metric_unchanged = changed == 0
    diff_unchanged = isinstance(diff, str) and not diff.strip()
    writes_locked = (
        state.get("decision") == "ABSTAIN"
        and state.get("unlocked") is False
        and no_components
        and metric_unchanged is True
        and diff_unchanged
    )
    checks = {
        "explicit_abstain_state": state.get("decision") == "ABSTAIN",
        "writes_locked_and_candidate_unchanged": writes_locked,
        "abstain_reason_recorded": reason_recorded,
        "uncertainty_recorded": uncertainty_recorded,
        "unresolved_or_insufficient_contrast_recorded": unresolved_recorded,
        "authorized_act_gate_evidence_absent": not authorized_act_gate_evidence,
    }
    calibrated = all(checks.values())
    return {
        "applicable": True,
        "calibrated_abstain": calibrated,
        "status": "calibrated" if calibrated else "uncalibrated",
        "checks": checks,
        "authorized_act_gate_evidence_present": authorized_act_gate_evidence,
        "semantic_act_evidence_required": semantic_required,
        "typed_act_evidence_signature_present": typed_act_evidence,
        "candidate_evaluation_used": False,
        "interpretation": (
            "procedural calibration only; this does not certify the truth of any "
            "surviving causal explanation"
        ),
    }


def _false_act_signal(
    *,
    decision: str,
    semantic_gate_passed: bool,
    candidate_evaluation: object,
) -> dict[str, object]:
    if decision != "ACT":
        return {
            "applicable": False,
            "false_act": None,
            "status": (
                "not_applicable_abstained"
                if decision == "ABSTAIN"
                else "not_applicable_invalid_decision"
            ),
            "reason": (
                "arm abstained"
                if decision == "ABSTAIN"
                else "arm has no valid ACT or ABSTAIN decision"
            ),
            "causal_truth_judged": False,
        }
    no_target_gain: bool | None = None
    protection_regression: bool | None = None
    if isinstance(candidate_evaluation, Mapping):
        outcome = candidate_evaluation.get("outcome")
        if isinstance(outcome, Mapping):
            target_gains = outcome.get(
                "target_reward_gain_count", outcome.get("reward_gain_count")
            )
            if isinstance(target_gains, int) and not isinstance(
                target_gains, bool
            ):
                no_target_gain = target_gains == 0
        regressions = candidate_evaluation.get("protection_regressions")
        if isinstance(regressions, list):
            protection_regression = bool(regressions)
    explicit_falsified: bool | None = None
    prediction_audit_status: str | None = None
    if isinstance(candidate_evaluation, Mapping):
        prediction_audit = candidate_evaluation.get("prediction_audit")
        if isinstance(prediction_audit, Mapping):
            status = prediction_audit.get("status")
            prediction_audit_status = status if isinstance(status, str) else None
            if status == "falsified":
                explicit_falsified = True
            elif status == "supported":
                explicit_falsified = False
    reasons: list[str] = []
    if not semantic_gate_passed:
        reasons.append("required semantic ACT gate failed; audited separately")
    if no_target_gain is True:
        reasons.append(
            "candidate produced no target reward gain; this alone is not false-ACT"
        )
    if protection_regression is True:
        reasons.append("candidate regressed a strict protection task")
    if no_target_gain is None:
        reasons.append("candidate outcome unavailable")
    if prediction_audit_status == "insufficient":
        reasons.append("prediction audit found insufficient observable evidence")
    elif explicit_falsified is None:
        reasons.append("primary component-specific prediction not adjudicated")
    return {
        "applicable": True,
        "false_act": explicit_falsified,
        "status": (
            "falsified"
            if explicit_falsified is True
            else "supported"
            if explicit_falsified is False
            else "insufficient_prediction_adjudication"
            if prediction_audit_status == "insufficient"
            else "missing_prediction_adjudication"
        ),
        "contract_invalid_act": not semantic_gate_passed,
        "no_target_reward_gain": no_target_gain,
        "strict_protection_regression": protection_regression,
        "primary_prediction_adjudicated_automatically": False,
        "requires_digest_bound_prediction_audit": True,
        "reason": "; ".join(reasons) if reasons else "no observable false-ACT signal",
        "causal_truth_judged": False,
        "interpretation": (
            "False-ACT follows only an explicit candidate audit of the preregistered "
            "primary component-specific prediction. Reward non-improvement and an "
            "unsupported semantic leap are reported separately."
        ),
    }


def _advancement_thresholds(manifest: Mapping[str, object]) -> dict[str, object]:
    analysis = manifest.get("analysis_plan")
    analysis = analysis if isinstance(analysis, Mapping) else {}
    raw = analysis.get("candidate_advancement_thresholds")
    if not isinstance(raw, Mapping):
        raise ValueError("A6 manifest has no candidate advancement thresholds")
    thresholds = dict(raw)
    required = {
        "false_act_allowed": False,
        "unsupported_semantic_leap_in_selected_act_allowed": False,
        "arm_specific_act_gate_must_hold": True,
        "minimum_interpretable_stable_five_domain_macro_delta": 0.1,
        "minimum_positive_target_tasks": 2,
        "maximum_strict_protection_regressions": 0,
        "component_specific_prediction_must_hold": True,
        "volatile_sentinels_count_toward_protection_gate": False,
        "volatile_sentinels_count_toward_stable_domain_gate": False,
    }
    drift = sorted(
        key for key, expected in required.items() if thresholds.get(key) != expected
    )
    if drift:
        raise ValueError(f"A6 candidate advancement thresholds drifted: {drift}")
    return thresholds


def _validate_declared_panel_aggregation(
    *,
    manifest: Mapping[str, object],
    domains: Mapping[str, str],
    targets: set[str],
    protections: set[str],
    ordered_task_ids: list[str],
) -> None:
    panel = manifest.get("panel")
    panel = panel if isinstance(panel, Mapping) else {}
    declared_task_count = panel.get("task_count")
    if declared_task_count is not None and declared_task_count != len(
        ordered_task_ids
    ):
        raise ValueError("A6 panel task_count differs from ordered task_ids")
    analysis = manifest.get("analysis_plan")
    analysis = analysis if isinstance(analysis, Mapping) else {}
    all_estimand = analysis.get("secondary_reward_estimand")
    all_estimand = all_estimand if isinstance(all_estimand, Mapping) else {}
    stable_estimand = analysis.get("stable_advancement_reward_estimand")
    stable_estimand = (
        stable_estimand if isinstance(stable_estimand, Mapping) else {}
    )
    all_domain_count = len({domains[task_id] for task_id in ordered_task_ids})
    stable_ids = targets | protections
    stable_domain_count = len({domains[task_id] for task_id in stable_ids})
    checks = {
        "all-panel domain_count": (
            all_estimand.get("domain_count"),
            all_domain_count,
        ),
        "stable-panel domain_count": (
            stable_estimand.get("domain_count"),
            stable_domain_count,
        ),
        "stable-panel task_count": (
            stable_estimand.get("task_count"),
            len(stable_ids),
        ),
    }
    drift = [
        label
        for label, (declared, observed) in checks.items()
        if declared is not None and declared != observed
    ]
    if drift:
        raise ValueError("A6 panel aggregation declarations drifted: " + ", ".join(drift))


def _state_act_gate(
    *,
    decision: str,
    state: Mapping[str, object],
    discovery_quality: object,
    semantic_gate_passed: bool,
) -> bool:
    if decision != "ACT" or state.get("decision") != "ACT":
        return False
    hypothesis = state.get("hypothesis")
    hypothesis = hypothesis if isinstance(hypothesis, Mapping) else {}
    selected = hypothesis.get("selected_hypothesis_id")
    eliminated = hypothesis.get("hypotheses_eliminated")
    components = hypothesis.get("components")
    prediction = hypothesis.get("prediction")
    state_gate = (
        state.get("unlocked") is True
        and isinstance(selected, str)
        and bool(selected)
        and isinstance(eliminated, list)
        and bool(eliminated)
        and isinstance(components, list)
        and bool(components)
        and bool(prediction)
        and semantic_gate_passed
    )
    if not state_gate:
        return False
    if not isinstance(discovery_quality, Mapping):
        return False
    checks = discovery_quality.get("checks")
    return isinstance(checks, Mapping) and bool(checks) and all(
        value is True for value in checks.values()
    )


def _advancement_audit(
    *,
    decision: str,
    thresholds: Mapping[str, object],
    reward_audit: Mapping[str, object],
    false_act_audit: Mapping[str, object],
    semantic_audit: Mapping[str, object],
    arm_act_gate_passed: bool,
    candidate_evaluation: object,
) -> dict[str, object]:
    if decision != "ACT":
        return {
            "applicable": False,
            "passed": None,
            "complete": decision == "ABSTAIN",
            "status": (
                "not_applicable_abstained"
                if decision == "ABSTAIN"
                else "invalid_decision"
            ),
        }
    stable = reward_audit.get("stable_14_task_five_domain")
    stable = stable if isinstance(stable, Mapping) else {}
    stable_macro = _finite_number(stable.get("macro_reward_delta"))
    positive_targets = reward_audit.get("positive_target_task_count")
    protection_regressions = reward_audit.get(
        "strict_protection_regression_count"
    )
    prediction_status: str | None = None
    if isinstance(candidate_evaluation, Mapping):
        prediction = candidate_evaluation.get("prediction_audit")
        if isinstance(prediction, Mapping) and isinstance(
            prediction.get("status"), str
        ):
            prediction_status = str(prediction["status"])
    false_act = false_act_audit.get("false_act")
    unsupported = semantic_audit.get("unsupported_semantic_leap")
    unsupported_applicable = semantic_audit.get(
        "unsupported_semantic_leap_applicable"
    )
    checks: dict[str, bool | None] = {
        "false_act_absent": (
            False
            if false_act is True
            else True
            if false_act is False
            else None
        ),
        "unsupported_semantic_leap_absent": (
            True
            if unsupported_applicable is False
            else False
            if unsupported is True
            else True
            if unsupported is False
            else None
        ),
        "arm_specific_act_gate_holds": arm_act_gate_passed,
        "stable_five_domain_macro_at_least_threshold": (
            stable_macro
            >= float(
                thresholds[
                    "minimum_interpretable_stable_five_domain_macro_delta"
                ]
            )
            if stable_macro is not None
            else None
        ),
        "minimum_positive_target_tasks_met": (
            int(positive_targets) >= int(thresholds["minimum_positive_target_tasks"])
            if isinstance(positive_targets, int)
            and not isinstance(positive_targets, bool)
            else None
        ),
        "strict_protection_regression_limit_met": (
            int(protection_regressions)
            <= int(thresholds["maximum_strict_protection_regressions"])
            if isinstance(protection_regressions, int)
            and not isinstance(protection_regressions, bool)
            else None
        ),
        "component_specific_prediction_holds": (
            True
            if prediction_status == "supported"
            else False
            if prediction_status == "falsified"
            else None
        ),
    }
    complete = all(value is not None for value in checks.values())
    passed = complete and all(value is True for value in checks.values())
    return {
        "applicable": True,
        "passed": passed,
        "complete": complete,
        "status": (
            "passed"
            if passed
            else "failed"
            if complete
            else "incomplete_missing_audit_or_score"
        ),
        "checks": checks,
        "thresholds": dict(thresholds),
        "stable_five_domain_macro_delta": stable_macro,
        "unsupported_semantic_leap_gate_applicable": unsupported_applicable,
        "all_16_six_domain_macro_used_for_gate": False,
        "volatile_sentinels_used_for_gate": False,
        "mutation_metrics_used_for_gate": False,
    }


def audit(
    *,
    manifest: Mapping[str, object],
    seed_run: Path,
    seed_arm: str,
    proposal_runs: Mapping[str, Path],
    candidate_runs: Mapping[str, Path] | None = None,
    prediction_audits: Mapping[str, Path] | None = None,
) -> dict[str, object]:
    if manifest.get("stage") != "A6":
        raise ValueError("A6 audit requires an A6 manifest")
    normalized_proposals = {_arm(label): path for label, path in proposal_runs.items()}
    if set(normalized_proposals) != set(_ARMS):
        raise ValueError("A6 audit requires exactly A6-R, A6-E, and A6-EC")
    normalized_candidates = {
        _arm(label): path for label, path in (candidate_runs or {}).items()
    }
    normalized_prediction_audits = {
        _arm(label): path for label, path in (prediction_audits or {}).items()
    }
    if not set(normalized_prediction_audits) <= set(_ARMS):
        raise ValueError("prediction audits contain an unknown A6 arm")

    domains, targets, protections, sentinels, ordered_task_ids = _panel_roles(manifest)
    thresholds = _advancement_thresholds(manifest)
    _validate_declared_panel_aggregation(
        manifest=manifest,
        domains=domains,
        targets=targets,
        protections=protections,
        ordered_task_ids=ordered_task_ids,
    )

    seed_capability: object | None = None
    arms: dict[str, object] = {}
    bytes_by_arm: dict[str, dict[str, object]] = {}
    for arm in _ARMS:
        partial = audit_a5(
            manifest=manifest,
            seed_run=seed_run,
            seed_arm=seed_arm,
            proposal_runs={arm: normalized_proposals[arm]},
            candidate_run=normalized_candidates.get(arm),
        )
        if seed_capability is None:
            seed_capability = partial["seed_harness_capability"]
        arm_payload = dict(partial["arms"][arm])
        proposal_report = _json(normalized_proposals[arm] / "pilot-report.json")
        proposal = proposal_report.get("proposal")
        proposal = proposal if isinstance(proposal, Mapping) else {}
        prediction = proposal.get("prediction")
        prediction = prediction if isinstance(prediction, Mapping) else {}
        summary = proposal.get("summary")
        summary = summary if isinstance(summary, Mapping) else {}
        state = summary.get("discovery_hypothesis")
        state = state if isinstance(state, Mapping) else {}
        mutation_metrics = proposal.get("mutation_metrics")
        throughput = proposal.get("candidate_generation_throughput")
        arm_payload["mutation_metrics"] = (
            dict(mutation_metrics) if isinstance(mutation_metrics, Mapping) else None
        )
        arm_payload["candidate_generation_throughput"] = (
            dict(throughput) if isinstance(throughput, Mapping) else None
        )
        triples = _grounded_triples(
            state,
            evidence_root=normalized_proposals[arm] / "authorized-evidence",
        )
        valid_triples = [
            value for value in triples if value["complete_grounded_triple"] is True
        ]
        act_grounding_triples = [
            value for value in valid_triples if value["act_grounding_valid"] is True
        ]
        decision = str(arm_payload.get("decision", "")).upper()
        hypothesis = state.get("hypothesis")
        hypothesis = hypothesis if isinstance(hypothesis, Mapping) else {}
        selected_id = hypothesis.get("selected_hypothesis_id")
        selected_claim_denominator = 1 if decision == "ACT" else 0
        selected_grounded = any(
            value.get("selected_hypothesis_id") == selected_id
            for value in act_grounding_triples
        )
        grounded_ids = hypothesis.get("grounded_comparison_probe_ids")
        grounding_claimed = isinstance(grounded_ids, list) and bool(grounded_ids)
        semantic_required = arm == "A6-EC" and decision == "ACT"
        semantic_gate_passed = not semantic_required or selected_grounded
        semantic_leap_applicable = decision == "ACT" and (
            arm == "A6-EC" or (arm == "A6-E" and grounding_claimed)
        )
        unsupported_leap = (
            not selected_grounded if semantic_leap_applicable else None
        )
        arm_payload["semantic_audit"] = {
            "grounded_triple_attempted_count": len(triples),
            "grounded_triple_valid_count": len(valid_triples),
            "act_grounding_valid_count": len(act_grounding_triples),
            "selected_hypothesis_count": selected_claim_denominator,
            "selected_hypothesis_grounded_count": (
                int(selected_grounded) if selected_claim_denominator else 0
            ),
            "selected_hypothesis_grounded_coverage": (
                float(selected_grounded) if selected_claim_denominator else None
            ),
            "grounded_triples": triples,
            "clause_link_availability": (
                "structurally_unavailable"
                if arm == "A6-R"
                else "available"
            ),
            "semantic_comparison_mode": (
                "structurally_unavailable"
                if arm == "A6-R"
                else "available_optional"
                if arm == "A6-E"
                else "required_for_act"
            ),
            "semantic_act_gate_required": semantic_required,
            "semantic_act_gate_passed": semantic_gate_passed,
            "unsupported_semantic_leap": unsupported_leap,
            "unsupported_semantic_leap_applicable": semantic_leap_applicable,
            "unsupported_semantic_leap_count": (
                int(unsupported_leap) if unsupported_leap is not None else None
            ),
            "audited_claim_denominator": (
                selected_claim_denominator if semantic_leap_applicable else 0
            ),
            "unsupported_semantic_leap_reason": (
                "A6-R has no public-clause representation; semantic claim audit "
                "is unavailable rather than passed"
                if decision == "ACT" and arm == "A6-R"
                else "A6-E did not claim an optional typed semantic comparison; "
                "no semantic leap verdict is fabricated"
                if decision == "ACT" and arm == "A6-E" and not grounding_claimed
                else "ACT has no complete, resolvable, decisive "
                "public-clause/artifact/trace relation"
                if unsupported_leap
                else None
            ),
            "causal_truth_judged": False,
        }
        candidate_evaluation = arm_payload.get("candidate_evaluation")
        if arm in normalized_prediction_audits:
            if decision != "ACT" or not isinstance(
                candidate_evaluation, Mapping
            ) or arm not in normalized_candidates:
                raise ValueError(
                    f"{arm} prediction audit is only valid for an evaluated ACT"
                )
            candidate_evaluation = {
                **dict(candidate_evaluation),
                "prediction_audit": _prediction_audit(
                    arm=arm,
                    path=normalized_prediction_audits[arm],
                    prediction=prediction,
                    candidate_root=normalized_candidates[arm],
                ),
            }
            arm_payload["candidate_evaluation"] = candidate_evaluation
        arm_payload["false_act_audit"] = _false_act_signal(
            decision=decision,
            semantic_gate_passed=semantic_gate_passed,
            candidate_evaluation=candidate_evaluation,
        )
        arm_payload["reward_audit"] = _reward_audit(
            candidate_evaluation=candidate_evaluation,
            domains=domains,
            targets=targets,
            protections=protections,
            sentinels=sentinels,
            ordered_task_ids=ordered_task_ids,
        )
        arm_payload["abstain_calibration"] = _abstain_calibration(
            decision=decision,
            state=state,
            mutation_metrics=mutation_metrics,
            diff=proposal.get("diff"),
            triples=triples,
        )
        arm_gate = _state_act_gate(
            decision=decision,
            state=state,
            discovery_quality=arm_payload.get("discovery"),
            semantic_gate_passed=semantic_gate_passed,
        )
        arm_payload["candidate_advancement"] = _advancement_audit(
            decision=decision,
            thresholds=thresholds,
            reward_audit=arm_payload["reward_audit"],
            false_act_audit=arm_payload["false_act_audit"],
            semantic_audit=arm_payload["semantic_audit"],
            arm_act_gate_passed=arm_gate,
            candidate_evaluation=candidate_evaluation,
        )
        arms[arm] = arm_payload
        bytes_by_arm[arm] = _evidence_byte_record(normalized_proposals[arm])

    expected_contracts = {
        "A6-R": {
            "contract_arm": "A6-R",
            "decision_protocol": "failure_type_v1",
            "probe_policy": "constrained_evidence_profile_v1",
            "public_contract_evidence": False,
            "public_contract_index": None,
            "semantic_comparison": "not_required",
        },
        "A6-E": {
            "contract_arm": "A6-E",
            "decision_protocol": "failure_type_v1",
            "probe_policy": "constrained_evidence_profile_v1",
            "public_contract_evidence": True,
            "public_contract_index": "contracts/index.json",
            "semantic_comparison": "available_not_required",
        },
        "A6-EC": {
            "contract_arm": "A6-EC",
            "decision_protocol": "semantic_contract_v1",
            "probe_policy": "typed_contract_artifact_trace_v1",
            "public_contract_evidence": True,
            "public_contract_index": "contracts/index.json",
            "semantic_comparison": "required_for_act",
        },
    }
    for arm, expected in expected_contracts.items():
        contract = bytes_by_arm[arm]["contract"]
        mismatches = sorted(
            key for key, value in expected.items() if contract.get(key) != value
        )
        if mismatches:
            raise ValueError(
                f"{arm} discovery contract differs from protocol: {mismatches}"
            )
        if contract.get("evaluator_feedback_tier") != "answer_free_public_process":
            raise ValueError(f"{arm} uses an unsupported evaluator feedback tier")

    def lowercase_sha256(value: object) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    seed_bindings = {
        (
            bytes_by_arm[arm]["contract"].get("seed_launch_identity_sha256"),
            bytes_by_arm[arm]["contract"].get("seed_identity_record_sha256"),
        )
        for arm in _ARMS
    }
    if len(seed_bindings) != 1 or not all(
        lowercase_sha256(value) for value in next(iter(seed_bindings))
    ):
        raise ValueError("A6 arms do not share one valid fresh-seed identity")

    raw_contract = bytes_by_arm["A6-R"]["contract"]
    if (
        raw_contract.get("public_task_role_manifest_sha256") is not None
        or raw_contract.get("public_contract_source_members_sha256") is not None
    ):
        raise ValueError("A6-R unexpectedly binds an exposed semantic corpus")
    semantic_source_bindings: set[tuple[object, object]] = set()
    public_source_contract_index_bound = True
    for arm in ("A6-E", "A6-EC"):
        contract = bytes_by_arm[arm]["contract"]
        binding = (
            contract.get("public_task_role_manifest_sha256"),
            contract.get("public_contract_source_members_sha256"),
        )
        semantic_source_bindings.add(binding)
        index = _json(
            Path(str(bytes_by_arm[arm]["root"])) / "contracts/index.json"
        )
        source_identity = index.get("source_identity")
        source_identity = (
            source_identity if isinstance(source_identity, Mapping) else {}
        )
        public_source_contract_index_bound = (
            public_source_contract_index_bound
            and source_identity.get("public_task_role_manifest_sha256")
            == binding[0]
            and source_identity.get("instruction_members_sha256") == binding[1]
        )
    semantic_source_binding_valid = (
        len(semantic_source_bindings) == 1
        and all(
            lowercase_sha256(value)
            for value in next(iter(semantic_source_bindings))
        )
        and public_source_contract_index_bound
    )
    if not semantic_source_binding_valid:
        raise ValueError(
            "A6-E/A6-EC public source identity is missing, different, or "
            "unbound to the semantic index"
        )

    contract_payloads = {
        arm: dict(value["contract"]) for arm, value in bytes_by_arm.items()
    }
    contract_keys = set().union(*(set(value) for value in contract_payloads.values()))
    changed_contract_fields = sorted(
        key
        for key in contract_keys
        if len(
            {
                (
                    key in contract_payloads[arm],
                    json.dumps(
                        contract_payloads[arm].get(key),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                )
                for arm in _ARMS
            }
        )
        > 1
    )
    unexpected_contract_differences = sorted(
        set(changed_contract_fields) - _CONTRACT_DIFFERENCE_FIELDS
    )
    contract_common_fields_identical = not unexpected_contract_differences

    shared_digests = {
        str(value["shared_core_sha256"]) for value in bytes_by_arm.values()
    }
    shared_members = {
        tuple(value["shared_core_members"]) for value in bytes_by_arm.values()
    }
    semantic_match = (
        bytes_by_arm["A6-E"]["semantic_contract_sha256"]
        == bytes_by_arm["A6-EC"]["semantic_contract_sha256"]
        and tuple(bytes_by_arm["A6-E"]["semantic_contract_members"])
        == tuple(bytes_by_arm["A6-EC"]["semantic_contract_members"])
    )
    raw_has_no_semantic = not bytes_by_arm["A6-R"]["semantic_contract_members"]
    ladder_byte_audit = {
        "shared_core_byte_identical": len(shared_digests) == 1
        and len(shared_members) == 1,
        "shared_core_sha256_by_arm": {
            arm: value["shared_core_sha256"]
            for arm, value in bytes_by_arm.items()
        },
        "a6_e_and_a6_ec_semantic_corpus_byte_identical": semantic_match,
        "semantic_contract_sha256_by_arm": {
            arm: value["semantic_contract_sha256"]
            for arm, value in bytes_by_arm.items()
        },
        "a6_r_has_no_semantic_corpus": raw_has_no_semantic,
        "allowed_contract_difference_fields": sorted(
            _CONTRACT_DIFFERENCE_FIELDS
        ),
        "observed_contract_difference_fields": changed_contract_fields,
        "unexpected_contract_difference_fields": unexpected_contract_differences,
        "contract_common_fields_identical": contract_common_fields_identical,
        "fresh_seed_identity_byte_identical": len(seed_bindings) == 1,
        "semantic_source_identity_byte_identical": (
            len(semantic_source_bindings) == 1
        ),
        "semantic_source_contract_index_bound": (
            public_source_contract_index_bound
        ),
        "predetermined_differences": {
            "contract_json": sorted(_CONTRACT_DIFFERENCE_FIELDS),
            "semantic_corpus": "contracts/** is absent only from A6-R",
        },
        "passed": len(shared_digests) == 1
        and len(shared_members) == 1
        and semantic_match
        and raw_has_no_semantic
        and contract_common_fields_identical,
    }

    panel = manifest.get("panel")
    panel = panel if isinstance(panel, Mapping) else {}
    sentinel_items = panel.get("sentinels")
    if sentinel_items is None:
        sentinel_items = panel.get("coverage_sentinels", [])
    return {
        "schema_version": 1,
        "stage": "A6",
        "panel": {
            "task_ids": list(panel.get("task_ids", [])),
            "target_count": len(panel.get("targets", [])),
            "protection_count": len(panel.get("protections", [])),
            "sentinel_count": len(sentinel_items),
            "sentinels_are_not_protection_gate": True,
            "sentinels_are_not_stable_domain_gate": True,
            "all_panel_domain_count": len(set(domains.values())),
            "stable_panel_domain_count": len(
                {domains[task_id] for task_id in targets | protections}
            ),
        },
        "seed_harness_capability": seed_capability,
        "arms": arms,
        "ladder_byte_audit": ladder_byte_audit,
        "candidate_advancement": {
            "thresholds": thresholds,
            "stable_gate_scope": (
                "six repeat-failure targets plus eight strict protections across "
                "five domains"
            ),
            "descriptive_all_panel_scope": (
                "all sixteen tasks across six domains, including two volatile "
                "sentinels"
            ),
            "arms": {
                arm: arms[arm]["candidate_advancement"] for arm in _ARMS
            },
            "mutation_metrics_used_for_selection_or_admission": False,
        },
        "claim_boundary": [
            "grounded triples establish observable linkage, not causal truth",
            "false-ACT requires an explicit digest-bound audit of the "
            "preregistered component-specific prediction",
            "unsupported-semantic-leap and false-ACT fields are audit signals, "
            "not automatic mechanism verdicts",
            "volatile sentinels measure coverage and blast radius but are excluded "
            "from both the strict-protection and stable-domain advancement gates; "
            "the all-16 six-domain macro is descriptive only",
            "all implemented A6 evidence remains answer-free public/process "
            "evidence with no raw verifier or test surface",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a6-manifest", type=Path, required=True)
    parser.add_argument("--seed-run", type=Path, required=True)
    parser.add_argument("--seed-arm", default="seed-evidence")
    parser.add_argument("--proposal", action="append", type=_label_path, required=True)
    parser.add_argument("--candidate", action="append", type=_label_path, default=[])
    parser.add_argument(
        "--prediction-audit", action="append", type=_label_file, default=[]
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    proposals = dict(args.proposal)
    candidates = dict(args.candidate)
    prediction_audits = dict(args.prediction_audit)
    if len(proposals) != len(args.proposal):
        raise ValueError("proposal labels must be unique")
    if len(candidates) != len(args.candidate):
        raise ValueError("candidate labels must be unique")
    if len(prediction_audits) != len(args.prediction_audit):
        raise ValueError("prediction-audit labels must be unique")
    report = audit(
        manifest=_json(args.a6_manifest.resolve()),
        seed_run=args.seed_run.resolve(),
        seed_arm=args.seed_arm,
        proposal_runs=proposals,
        candidate_runs=candidates,
        prediction_audits=prediction_audits,
    )
    _atomic_json(args.output.expanduser().resolve(), report)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
