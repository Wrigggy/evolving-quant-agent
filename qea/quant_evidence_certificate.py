"""Paired canary for task-conditioned quantitative evidence certificates."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping


class QuantEvidenceCertificateError(ValueError):
    """A certificate canary input or Reviewer response is invalid."""


@dataclass(frozen=True)
class QuantEvidenceCase:
    """One public diagnosis case with trusted scoring metadata."""

    case_id: str
    state_id: str
    public_contract: str
    runtime_evidence: tuple[str, ...]
    audits: Mapping[str, Mapping[str, str]]
    true_mechanism: str | None
    adjacent_mechanism: str | None
    true_mechanism_markers: tuple[str, ...]
    adjacent_mechanism_markers: tuple[str, ...]
    discriminating_audit_id: str | None


@dataclass(frozen=True)
class ReviewerArmResult:
    """One arm's two-stage outputs and trusted canary score."""

    arm: str
    case_id: str
    audit_id: str | None
    proposal: Mapping[str, object]
    final: Mapping[str, object]
    audit_choice_correct: bool
    diagnosis_correct: bool
    calibrated_insufficiency: bool
    certificate_valid: bool | None
    elapsed_seconds: float


def load_quant_evidence_cases(path: Path) -> tuple[QuantEvidenceCase, ...]:
    """Load the small QEC-1 panel."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise QuantEvidenceCertificateError("certificate case panel is empty")
    cases: list[QuantEvidenceCase] = []
    for raw in payload:
        if not isinstance(raw, Mapping):
            raise QuantEvidenceCertificateError("certificate case is not an object")
        audits = raw.get("audits")
        if not isinstance(audits, Mapping) or not audits:
            raise QuantEvidenceCertificateError("certificate case audits are empty")
        normalized_audits: dict[str, dict[str, str]] = {}
        for audit_id, audit in audits.items():
            if not isinstance(audit_id, str) or not isinstance(audit, Mapping):
                raise QuantEvidenceCertificateError("certificate audit is invalid")
            description = audit.get("description")
            observation = audit.get("observation")
            if not isinstance(description, str) or not isinstance(observation, str):
                raise QuantEvidenceCertificateError("certificate audit text is invalid")
            normalized_audits[audit_id] = {
                "description": description,
                "observation": observation,
            }
        evidence = raw.get("runtime_evidence")
        if not isinstance(evidence, list) or not all(
            isinstance(value, str) and value.strip() for value in evidence
        ):
            raise QuantEvidenceCertificateError("runtime evidence is invalid")
        cases.append(
            QuantEvidenceCase(
                case_id=str(raw["case_id"]),
                state_id=str(raw["state_id"]),
                public_contract=str(raw["public_contract"]),
                runtime_evidence=tuple(evidence),
                audits=normalized_audits,
                true_mechanism=(
                    str(raw["true_mechanism"])
                    if raw.get("true_mechanism") is not None
                    else None
                ),
                adjacent_mechanism=(
                    str(raw["adjacent_mechanism"])
                    if raw.get("adjacent_mechanism") is not None
                    else None
                ),
                true_mechanism_markers=tuple(
                    str(value).lower()
                    for value in raw.get("true_mechanism_markers", [])
                    if isinstance(value, str) and value.strip()
                ),
                adjacent_mechanism_markers=tuple(
                    str(value).lower()
                    for value in raw.get("adjacent_mechanism_markers", [])
                    if isinstance(value, str) and value.strip()
                ),
                discriminating_audit_id=(
                    str(raw["discriminating_audit_id"])
                    if raw.get("discriminating_audit_id") is not None
                    else None
                ),
            )
        )
    return tuple(cases)


def _json_response(text: str) -> dict[str, object]:
    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise QuantEvidenceCertificateError(
            f"Reviewer did not return one JSON object: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise QuantEvidenceCertificateError("Reviewer response is not an object")
    return payload


def validate_quant_evidence_certificate(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Validate the deliberately small, open certificate schema."""

    if payload.get("schema_version") != 1:
        raise QuantEvidenceCertificateError("certificate schema_version must be 1")
    applicability = payload.get("applicability")
    if applicability not in {
        "applicable",
        "not_applicable",
        "insufficient_evidence",
    }:
        raise QuantEvidenceCertificateError("certificate applicability is invalid")
    refs = payload.get("evidence_refs", [])
    if not isinstance(refs, list) or not all(
        isinstance(value, str) and value.strip() for value in refs
    ):
        raise QuantEvidenceCertificateError("certificate evidence_refs are invalid")
    alternatives = payload.get("alternative_explanations", [])
    if not isinstance(alternatives, list) or not all(
        isinstance(value, str) and value.strip() for value in alternatives
    ):
        raise QuantEvidenceCertificateError(
            "certificate alternative_explanations are invalid"
        )
    forms = (
        "semantic_coordinates",
        "reconciliation_bridge",
        "residual_probe",
    )
    populated = [name for name in forms if isinstance(payload.get(name), Mapping)]
    if applicability == "applicable":
        if not refs:
            raise QuantEvidenceCertificateError(
                "an applicable certificate needs evidence_refs"
            )
        if len(alternatives) < 2:
            raise QuantEvidenceCertificateError(
                "an applicable certificate needs competing explanations"
            )
        if not populated:
            raise QuantEvidenceCertificateError(
                "an applicable certificate needs one quantitative evidence form"
            )
        observation = payload.get("discriminating_observation")
        if not isinstance(observation, str) or not observation.strip():
            raise QuantEvidenceCertificateError(
                "an applicable certificate needs a discriminating observation"
            )
    return dict(payload)


def _case_context(case: QuantEvidenceCase) -> str:
    audits = "\n".join(
        f"- {audit_id}: {audit['description']}"
        for audit_id, audit in case.audits.items()
    )
    evidence = "\n".join(
        f"- evidence:{index}: {value}"
        for index, value in enumerate(case.runtime_evidence, start=1)
    )
    return (
        f"Research State: {case.state_id}\n"
        f"Public contract:\n{case.public_contract}\n\n"
        f"Observed runtime evidence:\n{evidence}\n\n"
        f"Available low-cost audits:\n{audits}"
    )


def build_reviewer_prompt(
    case: QuantEvidenceCase,
    *,
    arm: str,
    audit_observation: str | None = None,
) -> str:
    """Build one proposal or final-diagnosis prompt for a paired arm."""

    if arm not in {"generic", "certificate"}:
        raise QuantEvidenceCertificateError("Reviewer arm is invalid")
    stage = "proposal" if audit_observation is None else "final"
    common = (
        "You are a Quant Research Reviewer. Diagnose the research-process "
        "mismatch, not the hidden task answer. Keep competing explanations when "
        "the evidence permits. Use only the supplied public contract and runtime "
        "evidence. Return exactly one JSON object with no markdown.\n\n"
        + _case_context(case)
    )
    if stage == "proposal":
        output = (
            '\n\nChoose one available audit. Return keys: "status" '
            '("investigate" or "insufficient_contrast"), "hypotheses" '
            '(array of objects with mechanism_id and evidence), "audit_id", '
            '"audit_prediction", and "candidate_component_loci".'
        )
    else:
        output = (
            f"\n\nExecuted audit observation:\n{audit_observation}\n\n"
            'Return keys: "status" ("resolved" or "insufficient_contrast"), '
            '"surviving_mechanisms", "eliminated_mechanisms", '
            '"candidate_component_loci", and "observation".'
        )
    if arm == "certificate":
        output += (
            '\nAlso return "quant_evidence_certificate" with schema_version=1, '
            'applicability ("applicable", "not_applicable", or '
            '"insufficient_evidence"), evidence_refs, '
            'alternative_explanations, discriminating_observation, and only the '
            'task-supported evidence form(s): semantic_coordinates, '
            'reconciliation_bridge, or residual_probe. Each populated evidence '
            'form is a JSON object. Do not invent unavailable coordinates or values.'
        )
    return common + output


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if isinstance(item, str)}


def _mentions(items: set[str], mechanism: str | None, markers: tuple[str, ...]) -> bool:
    normalized = "\n".join(items).lower()
    if mechanism and mechanism.lower() in normalized:
        return True
    return any(marker in normalized for marker in markers)


def run_reviewer_arm(
    case: QuantEvidenceCase,
    *,
    arm: str,
    complete: Callable[[str], str],
) -> ReviewerArmResult:
    """Run proposal, declared audit, and final diagnosis for one arm."""

    started = time.monotonic()
    proposal = _json_response(complete(build_reviewer_prompt(case, arm=arm)))
    raw_audit_id = proposal.get("audit_id")
    audit_id = raw_audit_id if isinstance(raw_audit_id, str) else None
    if audit_id not in case.audits:
        audit_observation = "No valid audit was selected; no new observation exists."
    else:
        audit_observation = case.audits[audit_id]["observation"]
    final = _json_response(
        complete(
            build_reviewer_prompt(
                case,
                arm=arm,
                audit_observation=audit_observation,
            )
        )
    )
    certificate_valid: bool | None = None
    if arm == "certificate":
        certificate = final.get("quant_evidence_certificate")
        try:
            if not isinstance(certificate, Mapping):
                raise QuantEvidenceCertificateError("final certificate is missing")
            validate_quant_evidence_certificate(certificate)
            certificate_valid = True
        except QuantEvidenceCertificateError:
            certificate_valid = False

    status = final.get("status")
    calibrated = case.true_mechanism is None and status == "insufficient_contrast"
    survivors = _string_set(final.get("surviving_mechanisms"))
    eliminated = _string_set(final.get("eliminated_mechanisms"))
    diagnosis_correct = calibrated or (
        _mentions(survivors, case.true_mechanism, case.true_mechanism_markers)
        and _mentions(
            eliminated,
            case.adjacent_mechanism,
            case.adjacent_mechanism_markers,
        )
    )
    audit_correct = (
        case.discriminating_audit_id is None
        or audit_id == case.discriminating_audit_id
    )
    return ReviewerArmResult(
        arm=arm,
        case_id=case.case_id,
        audit_id=audit_id,
        proposal=proposal,
        final=final,
        audit_choice_correct=audit_correct,
        diagnosis_correct=diagnosis_correct,
        calibrated_insufficiency=calibrated,
        certificate_valid=certificate_valid,
        elapsed_seconds=round(time.monotonic() - started, 3),
    )


def summarize_qec1(
    results: tuple[ReviewerArmResult, ...],
) -> dict[str, object]:
    """Compare paired generic and certificate results using preregistered gates."""

    by_arm: dict[str, list[ReviewerArmResult]] = {"generic": [], "certificate": []}
    for result in results:
        by_arm[result.arm].append(result)
    if not by_arm["generic"] or len(by_arm["generic"]) != len(by_arm["certificate"]):
        raise QuantEvidenceCertificateError("QEC-1 arms are not paired")

    metrics: dict[str, dict[str, object]] = {}
    successes: dict[str, dict[str, bool]] = {}
    for arm, values in by_arm.items():
        successes[arm] = {
            value.case_id: (
                value.audit_choice_correct
                and value.diagnosis_correct
                and (value.certificate_valid is not False)
            )
            for value in values
        }
        metrics[arm] = {
            "case_count": len(values),
            "audit_choice_correct": sum(v.audit_choice_correct for v in values),
            "diagnosis_correct": sum(v.diagnosis_correct for v in values),
            "calibrated_insufficiency": sum(
                v.calibrated_insufficiency for v in values
            ),
            "case_successes": sum(successes[arm].values()),
            "model_calls": 2 * len(values),
            "elapsed_seconds": round(sum(v.elapsed_seconds for v in values), 3),
        }
    generic = successes["generic"]
    certificate = successes["certificate"]
    improved_cases = sorted(
        case_id for case_id in certificate if certificate[case_id] and not generic[case_id]
    )
    regressed_cases = sorted(
        case_id for case_id in certificate if generic[case_id] and not certificate[case_id]
    )
    positive = bool(improved_cases) and not regressed_cases
    return {
        "protocol": "qec-1",
        "metrics": metrics,
        "improved_cases": improved_cases,
        "regressed_cases": regressed_cases,
        "mechanism_gate": "positive" if positive else "not_positive",
        "claim_boundary": (
            "controlled Reviewer representation canary only; no Worker, harness "
            "intervention, official benchmark, repeat, or transfer was run"
        ),
        "results": [asdict(value) for value in results],
    }


__all__ = [
    "QuantEvidenceCase",
    "QuantEvidenceCertificateError",
    "ReviewerArmResult",
    "build_reviewer_prompt",
    "load_quant_evidence_cases",
    "run_reviewer_arm",
    "summarize_qec1",
    "validate_quant_evidence_certificate",
]
