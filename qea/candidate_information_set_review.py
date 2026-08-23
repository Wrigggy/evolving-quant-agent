"""Answer-rich review of claims that a candidate would expose to a Worker.

The Reviewer may inspect optimize-only diagnostics to identify where a claim
came from, but only public contract or reference excerpts can support exposing
that claim to a blind Worker.  This module classifies evidence; it does not
mutate a candidate or authorize promotion.
"""

from __future__ import annotations

import json
from typing import Callable, Mapping


_VERDICTS = {"PASS", "REJECT", "INCONCLUSIVE"}
_SOURCE_ROLES = {
    "PUBLIC_SUPPORT",
    "PUBLIC_CONTRADICTION",
    "OPTIMIZE_ONLY_ORIGIN",
    "CANDIDATE_EXPOSURE",
    "INSUFFICIENT_PUBLIC_SUPPORT",
}


class CandidateInformationSetReviewError(ValueError):
    """Raised when a candidate information-set review is malformed."""


def validate_candidate_information_set_review_package(
    review_package: Mapping[str, object],
) -> dict[str, object]:
    """Validate the trusted controller package before spending a model call."""

    if review_package.get("schema_version") != 1:
        raise CandidateInformationSetReviewError("package schema_version must be 1")
    for field in ("review_id", "candidate_id"):
        if not isinstance(review_package.get(field), str) or not str(
            review_package[field]
        ).strip():
            raise CandidateInformationSetReviewError(f"package {field} is required")
    candidate = review_package.get("candidate")
    if not isinstance(candidate, Mapping) or not (
        candidate.get("diff") or candidate.get("files")
    ):
        raise CandidateInformationSetReviewError(
            "candidate diff or files are required"
        )
    claims = review_package.get("worker_visible_claims")
    if not isinstance(claims, list) or not claims:
        raise CandidateInformationSetReviewError(
            "worker_visible_claims must be a non-empty list"
        )

    public_refs = set()
    for record in review_package.get("public_sources", []):
        if not isinstance(record, Mapping) or not record.get("ref"):
            raise CandidateInformationSetReviewError(
                "public sources require exact refs"
            )
        if record.get("source_type") not in {"public_contract", "public_reference"}:
            raise CandidateInformationSetReviewError(
                "public source_type must be public_contract or public_reference"
            )
        public_refs.add(str(record["ref"]))

    diagnostic_refs = set()
    for record in review_package.get("optimize_only_sources", []):
        if not isinstance(record, Mapping) or not record.get("ref"):
            raise CandidateInformationSetReviewError(
                "optimize-only sources require exact refs"
            )
        if record.get("source_type") != "optimize_only_diagnostic":
            raise CandidateInformationSetReviewError(
                "optimize-only source_type must identify a diagnostic"
            )
        if record.get("worker_visible") is not False:
            raise CandidateInformationSetReviewError(
                "optimize-only sources must be Worker-hidden"
            )
        diagnostic_refs.add(str(record["ref"]))
    if public_refs.intersection(diagnostic_refs):
        raise CandidateInformationSetReviewError(
            "public and optimize-only source refs must be disjoint"
        )
    return dict(review_package)


def _candidate_refs(review_package: Mapping[str, object]) -> set[str]:
    candidate = review_package.get("candidate")
    if not isinstance(candidate, Mapping):
        return set()
    refs = set()
    if candidate.get("diff"):
        refs.add(str(candidate.get("diff_ref", "candidate:diff")))
    files = candidate.get("files", [])
    if isinstance(files, list):
        for item in files:
            if isinstance(item, Mapping) and item.get("ref"):
                refs.add(str(item["ref"]))
    return refs


def _source_refs(
    review_package: Mapping[str, object], field: str
) -> set[str]:
    records = review_package.get(field, [])
    if not isinstance(records, list):
        return set()
    return {
        str(record["ref"])
        for record in records
        if isinstance(record, Mapping) and record.get("ref")
    }


def build_candidate_information_set_reviewer_prompt(
    review_package: Mapping[str, object],
) -> str:
    """Build one prompt that reviews every Worker-visible claim in a candidate."""

    validated = validate_candidate_information_set_review_package(review_package)
    validated.pop("search_arm", None)
    package_json = json.dumps(
        validated, indent=2, ensure_ascii=False, sort_keys=True
    )
    return f"""You are the Candidate Information-Set Reviewer in a quantitative harness-evolution experiment.

Review every proposed Worker-visible claim in one batch. You may inspect the
candidate diff/files, public contract and public reference excerpts, and
optimize-only diagnostic excerpts supplied below. Optimize-only diagnostics are
answer-rich Evolver evidence: they may reveal that a proposed predicate came
from hidden evaluation, but their contents must never enter the Worker prompt,
candidate tools, descriptors, validators, skills, memory, or routing rules.

Apply exactly the same information boundary to every candidate. The Reviewer
is blind to the search-arm label. Judge the semantic claim, not whether it has
a well-formed basis label. A `principle:...` label, a claim's own explanation,
or a plausible finance convention is not evidence by itself. A public contract
or supplied public reference excerpt must actually entail the decision-changing
predicate before it can support Worker exposure.

For each claim return:

- PASS only when a supplied public contract or public reference excerpt
  directly supports the Worker-visible claim without adding a hidden threshold,
  serialization convention, expected value, or checker-specific predicate;
- REJECT when the claim contradicts or narrows the public contract, or when its
  decision-changing content is available only from an optimize-only diagnostic;
- INCONCLUSIVE when the claim may be reusable but the supplied public material
  neither supports nor contradicts it. Withhold or generalize such a claim until
  an actual public reference is supplied.

Examples of the boundary: a hidden fitted-SVI `a > 0` checker predicate is not
justified by a public requirement that final local volatility be positive; an
exact pair-array serialization rule is invalid when the public contract permits
any unambiguous encoding. Conversely, the public requirement that written
local-volatility values be positive supports that exact output predicate. A
written-object reconciliation rule is INCONCLUSIVE when it is backed only by a
named principle, and may PASS only when a supplied public reference actually
supports it.

Also compare the complete candidate diff/files with the declared claims. Return
`coverage_review` with verdict, reason, source_basis, and
`undeclared_exposures`. Each undeclared exposure contains a concise exposure
description and the Worker-visible surfaces where it appears. Coverage is
REJECT when the candidate contains any decision-changing semantic rule not
represented by a supplied claim, PASS when the supplied candidate material is
complete enough to check and every such rule is represented, and INCONCLUSIVE
when the supplied candidate material is incomplete. This coverage check is
essential: do not assume the Evolver's claim list is exhaustive.

Return one plain JSON object with schema_version=1, the supplied review_id and
candidate_id, `claim_reviews`, `coverage_review`, and `overall_verdict`. Return
claim reviews in the supplied order. Each claim review contains claim_id,
verdict, a concise reason, and non-empty source_basis. Each source-basis entry
contains an exact supplied ref and one role from {sorted(_SOURCE_ROLES)}. PASS
requires at least one PUBLIC_SUPPORT basis. Claim REJECT requires
PUBLIC_CONTRADICTION or OPTIMIZE_ONLY_ORIGIN. Coverage PASS/REJECT must cite a
CANDIDATE_EXPOSURE basis. Overall is REJECT if coverage or any claim is
rejected, otherwise INCONCLUSIVE if coverage or any claim is inconclusive,
otherwise PASS.

You classify this boundary only. You cannot rewrite the candidate, call a
Worker, PROMOTE or ROLLBACK a harness, select a benchmark result, or reveal the
review or diagnostics to a Worker. The fixed experiment controller retains all
candidate authority.

Candidate review package:
{package_json}
"""


def validate_candidate_information_set_review(
    payload: Mapping[str, object],
    review_package: Mapping[str, object],
) -> dict[str, object]:
    """Validate the small plain-JSON Candidate Reviewer response."""

    validate_candidate_information_set_review_package(review_package)
    allowed_fields = {
        "schema_version",
        "review_id",
        "candidate_id",
        "claim_reviews",
        "coverage_review",
        "overall_verdict",
    }
    extras = set(payload) - allowed_fields
    if extras:
        raise CandidateInformationSetReviewError(
            f"unexpected Reviewer fields: {sorted(extras)}"
        )
    if payload.get("schema_version") != 1:
        raise CandidateInformationSetReviewError("schema_version must be 1")
    for field in ("review_id", "candidate_id"):
        if payload.get(field) != review_package.get(field):
            raise CandidateInformationSetReviewError(
                f"Reviewer {field} must match the requested package"
            )

    claims = review_package.get("worker_visible_claims")
    reviews = payload.get("claim_reviews")
    if not isinstance(claims, list) or not claims:
        raise CandidateInformationSetReviewError(
            "worker_visible_claims must be a non-empty list"
        )
    if not isinstance(reviews, list):
        raise CandidateInformationSetReviewError("claim_reviews must be a list")
    expected_ids = [
        claim.get("claim_id") if isinstance(claim, Mapping) else None
        for claim in claims
    ]
    observed_ids = [
        review.get("claim_id") if isinstance(review, Mapping) else None
        for review in reviews
    ]
    if observed_ids != expected_ids:
        raise CandidateInformationSetReviewError(
            "Reviewer claim IDs must exactly match the requested claims"
        )

    public_refs = _source_refs(review_package, "public_sources")
    diagnostic_refs = _source_refs(review_package, "optimize_only_sources")
    candidate_refs = _candidate_refs(review_package)
    supplied_refs = public_refs | diagnostic_refs | candidate_refs
    verdicts = []
    for review in reviews:
        if not isinstance(review, Mapping):
            raise CandidateInformationSetReviewError(
                "every claim review must be an object"
            )
        verdict = review.get("verdict")
        if verdict not in _VERDICTS:
            raise CandidateInformationSetReviewError(
                f"invalid verdict for {review.get('claim_id')}"
            )
        verdicts.append(str(verdict))
        if not isinstance(review.get("reason"), str) or not review["reason"].strip():
            raise CandidateInformationSetReviewError(
                f"reason required for {review.get('claim_id')}"
            )
        bases = review.get("source_basis")
        if not isinstance(bases, list) or not bases:
            raise CandidateInformationSetReviewError(
                f"source_basis required for {review.get('claim_id')}"
            )
        roles = set()
        for basis in bases:
            if not isinstance(basis, Mapping):
                raise CandidateInformationSetReviewError(
                    "source_basis entries must be objects"
                )
            ref = basis.get("ref")
            role = basis.get("role")
            if ref not in supplied_refs:
                raise CandidateInformationSetReviewError(
                    f"unknown source ref for {review.get('claim_id')}: {ref}"
                )
            if role not in _SOURCE_ROLES:
                raise CandidateInformationSetReviewError(
                    f"invalid source role for {review.get('claim_id')}"
                )
            if role in {"PUBLIC_SUPPORT", "PUBLIC_CONTRADICTION"} and ref not in public_refs:
                raise CandidateInformationSetReviewError(
                    f"public source role requires a public ref: {ref}"
                )
            if role == "OPTIMIZE_ONLY_ORIGIN" and ref not in diagnostic_refs:
                raise CandidateInformationSetReviewError(
                    f"optimize-only role requires a diagnostic ref: {ref}"
                )
            if role == "CANDIDATE_EXPOSURE" and ref not in candidate_refs:
                raise CandidateInformationSetReviewError(
                    f"candidate exposure role requires a candidate ref: {ref}"
                )
            roles.add(str(role))
        if verdict == "PASS" and "PUBLIC_SUPPORT" not in roles:
            raise CandidateInformationSetReviewError(
                f"PASS requires PUBLIC_SUPPORT for {review.get('claim_id')}"
            )
        if verdict == "REJECT" and not roles.intersection(
            {"PUBLIC_CONTRADICTION", "OPTIMIZE_ONLY_ORIGIN"}
        ):
            raise CandidateInformationSetReviewError(
                f"REJECT requires boundary evidence for {review.get('claim_id')}"
            )

    coverage = payload.get("coverage_review")
    if not isinstance(coverage, Mapping):
        raise CandidateInformationSetReviewError(
            "coverage_review must be an object"
        )
    coverage_verdict = coverage.get("verdict")
    if coverage_verdict not in _VERDICTS:
        raise CandidateInformationSetReviewError("invalid coverage verdict")
    if not isinstance(coverage.get("reason"), str) or not coverage["reason"].strip():
        raise CandidateInformationSetReviewError("coverage reason is required")
    coverage_bases = coverage.get("source_basis")
    if not isinstance(coverage_bases, list) or not coverage_bases:
        raise CandidateInformationSetReviewError(
            "coverage source_basis is required"
        )
    coverage_roles = set()
    for basis in coverage_bases:
        if not isinstance(basis, Mapping):
            raise CandidateInformationSetReviewError(
                "coverage source_basis entries must be objects"
            )
        ref = basis.get("ref")
        role = basis.get("role")
        if ref not in supplied_refs:
            raise CandidateInformationSetReviewError(
                f"unknown coverage source ref: {ref}"
            )
        if role not in _SOURCE_ROLES:
            raise CandidateInformationSetReviewError(
                f"invalid coverage source role: {role}"
            )
        if role == "CANDIDATE_EXPOSURE" and ref not in candidate_refs:
            raise CandidateInformationSetReviewError(
                f"candidate coverage role requires a candidate ref: {ref}"
            )
        coverage_roles.add(str(role))
    if (
        coverage_verdict in {"PASS", "REJECT"}
        and "CANDIDATE_EXPOSURE" not in coverage_roles
    ):
        raise CandidateInformationSetReviewError(
            f"coverage {coverage_verdict} requires CANDIDATE_EXPOSURE"
        )
    undeclared = coverage.get("undeclared_exposures")
    if not isinstance(undeclared, list):
        raise CandidateInformationSetReviewError(
            "undeclared_exposures must be a list"
        )
    for item in undeclared:
        if not isinstance(item, Mapping):
            raise CandidateInformationSetReviewError(
                "undeclared exposures must be objects"
            )
        if (
            not isinstance(item.get("exposure"), str)
            or not item["exposure"].strip()
        ):
            raise CandidateInformationSetReviewError(
                "undeclared exposure text is required"
            )
        surfaces = item.get("surfaces")
        if not isinstance(surfaces, list) or not surfaces or not all(
            isinstance(surface, str) and surface.strip() for surface in surfaces
        ):
            raise CandidateInformationSetReviewError(
                "undeclared exposure surfaces are required"
            )
    if coverage_verdict == "PASS" and undeclared:
        raise CandidateInformationSetReviewError(
            "coverage PASS cannot contain undeclared exposures"
        )
    if coverage_verdict == "REJECT" and not undeclared:
        raise CandidateInformationSetReviewError(
            "coverage REJECT requires an undeclared exposure"
        )

    expected_overall = (
        "REJECT"
        if "REJECT" in verdicts or coverage_verdict == "REJECT"
        else "INCONCLUSIVE"
        if "INCONCLUSIVE" in verdicts or coverage_verdict == "INCONCLUSIVE"
        else "PASS"
    )
    if payload.get("overall_verdict") != expected_overall:
        raise CandidateInformationSetReviewError(
            f"overall_verdict must be {expected_overall}"
        )
    return dict(payload)


def run_candidate_information_set_review(
    review_package: Mapping[str, object],
    *,
    complete: Callable[[str], str],
) -> dict[str, object]:
    """Make one batched Reviewer call and validate its JSON response."""

    prompt = build_candidate_information_set_reviewer_prompt(review_package)
    raw = complete(prompt).strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:-1]).strip()
    payload = json.loads(raw)
    return validate_candidate_information_set_review(payload, review_package)


__all__ = [
    "CandidateInformationSetReviewError",
    "build_candidate_information_set_reviewer_prompt",
    "run_candidate_information_set_review",
    "validate_candidate_information_set_review_package",
    "validate_candidate_information_set_review",
]
