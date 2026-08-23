#!/usr/bin/env python3
"""Build answer-free Evolver evidence for one candidate-review refinement."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.evolution_evidence import authorize_evidence_tree  # noqa: E402
from scripts.run_qfbench_lineage_controller import (  # noqa: E402
    _worker_visible_candidate_material,
)


class CandidateReviewRefinementEvidenceError(ValueError):
    """The supplied candidate-review lineage cannot form safe evidence."""


_REFINEMENT_INSTRUCTION = (
    " This is a LINEAGE_REFINEMENT round for an existing answer-free candidate. "
    "Read every entry in required_runtime_experience_entries, including the exact "
    "candidate snapshot, reviewed diff, structured Worker-visible claims, and "
    "Candidate Information-Set Review feedback. Preserve the distinction between "
    "claim coverage and public support. Reviewer feedback is Worker-hidden, "
    "Evolver-only semantic feedback: it may identify which claim to narrow, remove, "
    "or reground, but it is not public evidence and must never be cited as the public "
    "basis for a new Worker-visible rule. Any refined Worker-visible claim still "
    "requires its own exact supplied public or benchmark-independent basis. Do not "
    "infer evaluator outcomes from this answer-free review."
)


def _json(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise CandidateReviewRefinementEvidenceError(
            f"{label} is unavailable: {path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CandidateReviewRefinementEvidenceError(
            f"cannot read {label}: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise CandidateReviewRefinementEvidenceError(
            f"{label} must be a JSON object"
        )
    return payload


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CandidateReviewRefinementEvidenceError(
            f"{label} must be non-empty text"
        )
    return value


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CandidateReviewRefinementEvidenceError(f"{label} must be an object")
    return value


def _list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise CandidateReviewRefinementEvidenceError(f"{label} must be a list")
    return value


def _safe_relative(value: object, *, label: str) -> Path:
    text = _text(value, label=label)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != text:
        raise CandidateReviewRefinementEvidenceError(
            f"{label} must be a safe POSIX-relative path"
        )
    return path


def _copy_candidate(source: Path, destination: Path) -> list[str]:
    if source.is_symlink() or not source.is_dir():
        raise CandidateReviewRefinementEvidenceError(
            f"candidate directory is unavailable: {source}"
        )
    copied: list[str] = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_symlink():
            raise CandidateReviewRefinementEvidenceError(
                f"candidate symlink is unsupported: {relative}"
            )
        if not path.is_file():
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise CandidateReviewRefinementEvidenceError(
                f"candidate evidence must be UTF-8 text: {relative}"
            ) from exc
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(relative.as_posix())
    if not copied:
        raise CandidateReviewRefinementEvidenceError(
            "candidate snapshot must contain at least one file"
        )
    return copied


def _proposal_claims(proposal: Mapping[str, object]) -> list[object]:
    direct = proposal.get("worker_visible_claims")
    if isinstance(direct, list):
        return direct
    try:
        summary = _mapping(proposal.get("summary"), label="proposal summary")
        discovery = _mapping(
            summary.get("discovery_hypothesis"),
            label="proposal discovery hypothesis",
        )
        hypothesis = _mapping(
            discovery.get("hypothesis"),
            label="proposal hypothesis",
        )
    except CandidateReviewRefinementEvidenceError:
        raise CandidateReviewRefinementEvidenceError(
            "proposal has no structured Worker-visible claims"
        ) from None
    return _list(
        hypothesis.get("worker_visible_claims"),
        label="proposal Worker-visible claims",
    )


def _claim_ids(claims: list[object], *, label: str) -> list[str]:
    ids: list[str] = []
    for index, raw_claim in enumerate(claims):
        claim = _mapping(raw_claim, label=f"{label}[{index}]")
        ids.append(_text(claim.get("claim_id"), label=f"{label}[{index}].claim_id"))
    if not ids or len(ids) != len(set(ids)):
        raise CandidateReviewRefinementEvidenceError(
            f"{label} must contain unique claim IDs"
        )
    return ids


def _diff_body(value: str) -> str:
    marker = value.find("@@")
    return value[marker:] if marker >= 0 else value


def _candidate_material(
    *, baseline: Path, candidate: Path, label: str
) -> dict[str, object]:
    if baseline.is_symlink() or not baseline.is_dir():
        raise CandidateReviewRefinementEvidenceError(
            f"{label} is unavailable: {baseline}"
        )
    material = _worker_visible_candidate_material(str(baseline), str(candidate))
    if not isinstance(material, dict):
        raise CandidateReviewRefinementEvidenceError(
            f"{label} has no Worker-visible difference from the candidate"
        )
    return material


def _reviewed_material(candidate: Mapping[str, object]) -> dict[str, object]:
    return {
        "diff_ref": _text(
            candidate.get("diff_ref", "candidate:diff"),
            label="reviewed diff ref",
        ),
        "diff": _text(candidate.get("diff"), label="reviewed diff"),
        "files": _list(candidate.get("files"), label="reviewed candidate files"),
    }


def _semantic_basis(value: object, *, label: str) -> list[dict[str, str]]:
    bases: list[dict[str, str]] = []
    for index, raw_basis in enumerate(_list(value, label=label)):
        basis = _mapping(raw_basis, label=f"{label}[{index}]")
        bases.append(
            {
                "ref": _text(basis.get("ref"), label=f"{label}[{index}].ref"),
                "role": _text(basis.get("role"), label=f"{label}[{index}].role"),
            }
        )
    if not bases:
        raise CandidateReviewRefinementEvidenceError(f"{label} must not be empty")
    return bases


def _semantic_exposures(value: object) -> list[dict[str, object]]:
    exposures: list[dict[str, object]] = []
    for index, raw_exposure in enumerate(
        _list(value, label="coverage review undeclared exposures")
    ):
        exposure = _mapping(raw_exposure, label=f"undeclared exposure[{index}]")
        surfaces = [
            _text(surface, label=f"undeclared exposure[{index}].surface")
            for surface in _list(
                exposure.get("surfaces"),
                label=f"undeclared exposure[{index}].surfaces",
            )
        ]
        if not surfaces:
            raise CandidateReviewRefinementEvidenceError(
                "undeclared exposure surfaces must not be empty"
            )
        exposures.append(
            {
                "exposure": _text(
                    exposure.get("exposure"),
                    label=f"undeclared exposure[{index}].exposure",
                ),
                "surfaces": surfaces,
            }
        )
    return exposures


def _semantic_review(
    *,
    result: Mapping[str, object],
    review_id: str,
    candidate_id: str,
    expected_claim_ids: list[str],
) -> dict[str, object]:
    if result.get("status") != "complete":
        raise CandidateReviewRefinementEvidenceError(
            "Reviewer result must have complete status"
        )
    if result.get("review_scope") != "answer_free_candidate_information_set":
        raise CandidateReviewRefinementEvidenceError(
            "Reviewer result must be answer-free Candidate Information-Set Review"
        )
    if result.get("worker_visible") is not False:
        raise CandidateReviewRefinementEvidenceError(
            "Reviewer feedback must be Worker-hidden"
        )
    if result.get("promotion_authority") is not False:
        raise CandidateReviewRefinementEvidenceError(
            "Reviewer feedback must not have promotion authority"
        )
    review = _mapping(result.get("review"), label="semantic review")
    if review.get("review_id") != review_id:
        raise CandidateReviewRefinementEvidenceError(
            "Reviewer result identity does not match review input"
        )
    if review.get("candidate_id") != candidate_id:
        raise CandidateReviewRefinementEvidenceError(
            "Reviewer result candidate does not match review input"
        )
    raw_claim_reviews = _list(
        review.get("claim_reviews"), label="semantic claim reviews"
    )
    claim_reviews: list[dict[str, object]] = []
    for index, raw_claim_review in enumerate(raw_claim_reviews):
        item = _mapping(raw_claim_review, label=f"claim review[{index}]")
        claim_reviews.append(
            {
                "claim_id": _text(
                    item.get("claim_id"), label=f"claim review[{index}].claim_id"
                ),
                "verdict": _text(
                    item.get("verdict"), label=f"claim review[{index}].verdict"
                ),
                "reason": _text(
                    item.get("reason"), label=f"claim review[{index}].reason"
                ),
                "source_basis": _semantic_basis(
                    item.get("source_basis"),
                    label=f"claim review[{index}].source_basis",
                ),
            }
        )
    if [item["claim_id"] for item in claim_reviews] != expected_claim_ids:
        raise CandidateReviewRefinementEvidenceError(
            "Reviewer claim order/identity does not match structured proposal claims"
        )
    coverage = _mapping(review.get("coverage_review"), label="coverage review")
    semantic = {
        "schema_version": 1,
        "feedback_mode": "answer_free",
        "worker_visible": False,
        "promotion_authority": False,
        "public_basis_authority": False,
        "overall_verdict": _text(
            review.get("overall_verdict"), label="overall review verdict"
        ),
        "claim_reviews": claim_reviews,
        "coverage_review": {
            "verdict": _text(
                coverage.get("verdict"), label="coverage review verdict"
            ),
            "reason": _text(
                coverage.get("reason"), label="coverage review reason"
            ),
            "source_basis": _semantic_basis(
                coverage.get("source_basis"), label="coverage review source basis"
            ),
            "undeclared_exposures": _semantic_exposures(
                coverage.get("undeclared_exposures")
            ),
        },
    }
    return semantic


def build(
    *,
    base_view: Path,
    proposal_report: Path,
    proposal_parent_dir: Path | None = None,
    candidate_dir: Path,
    review_input: Path,
    review_result: Path,
    review_baseline_dir: Path | None = None,
    destination: Path,
    round_label: str = "candidate-review-refinement-r1",
) -> dict[str, object]:
    """Create one LINEAGE_REFINEMENT view from answer-free review feedback."""

    base = base_view.expanduser().resolve()
    proposal_path = proposal_report.expanduser().resolve()
    candidate = candidate_dir.expanduser().resolve()
    proposal_parent = (
        proposal_parent_dir.expanduser().resolve()
        if proposal_parent_dir is not None
        else None
    )
    review_baseline = (
        review_baseline_dir.expanduser().resolve()
        if review_baseline_dir is not None
        else None
    )
    if proposal_parent is None and review_baseline is not None:
        proposal_parent = review_baseline
    if review_baseline is None and proposal_parent is not None:
        review_baseline = proposal_parent
    review_input_path = review_input.expanduser().resolve()
    review_result_path = review_result.expanduser().resolve()
    target = destination.expanduser().resolve()
    label = _safe_relative(round_label, label="round label")
    if len(label.parts) != 1:
        raise CandidateReviewRefinementEvidenceError(
            "round label must be a single path component"
        )
    if target.exists():
        raise CandidateReviewRefinementEvidenceError(
            f"destination already exists: {target}"
        )
    staging = target.with_name(target.name + ".partial")
    if staging.exists():
        raise CandidateReviewRefinementEvidenceError(
            f"staging destination already exists: {staging}"
        )

    # This validates the base corpus before any lineage material is attached.
    authorize_evidence_tree(base)
    proposal = _json(proposal_path, label="proposal report")
    if proposal.get("decision") != "ACT":
        raise CandidateReviewRefinementEvidenceError("proposal must be ACT")
    admission = _mapping(proposal.get("admission"), label="proposal admission")
    if admission.get("admitted") is not True:
        raise CandidateReviewRefinementEvidenceError(
            "proposal candidate must be admitted"
        )
    review_package = _json(review_input_path, label="review input")
    review_id = _text(review_package.get("review_id"), label="review ID")
    candidate_id = _text(
        review_package.get("candidate_id"), label="review candidate ID"
    )
    if review_package.get("optimize_only_sources") != []:
        raise CandidateReviewRefinementEvidenceError(
            "answer-free refinement requires an empty optimize-only source set"
        )
    reviewed_candidate = _mapping(
        review_package.get("candidate"), label="review candidate"
    )
    reviewed_material = _reviewed_material(reviewed_candidate)
    reviewed_diff = str(reviewed_material["diff"])
    proposal_diff = _text(proposal.get("diff"), label="proposal diff")
    if proposal_parent is not None and review_baseline is not None:
        incremental_material = _candidate_material(
            baseline=proposal_parent,
            candidate=candidate,
            label="proposal parent directory",
        )
        if _diff_body(str(incremental_material["diff"])) != _diff_body(
            proposal_diff
        ):
            raise CandidateReviewRefinementEvidenceError(
                "proposal incremental diff does not match proposal parent to "
                "candidate Worker-visible material"
            )
        cumulative_material = _candidate_material(
            baseline=review_baseline,
            candidate=candidate,
            label="review baseline directory",
        )
        if cumulative_material != reviewed_material:
            raise CandidateReviewRefinementEvidenceError(
                "review package cumulative material does not match review "
                "baseline to candidate Worker-visible material"
            )
    elif _diff_body(reviewed_diff) != _diff_body(proposal_diff):
        # Legacy equal-baseline packages predate explicit parent inputs. They
        # remain usable when the proposal and review both describe one delta.
        raise CandidateReviewRefinementEvidenceError(
            "proposal and reviewed candidate diffs do not match in legacy "
            "equal-baseline mode"
        )
    claims = _list(
        review_package.get("worker_visible_claims"),
        label="reviewed Worker-visible claims",
    )
    if claims != _proposal_claims(proposal):
        raise CandidateReviewRefinementEvidenceError(
            "reviewed claims do not match the structured proposal claims"
        )
    claim_ids = _claim_ids(claims, label="reviewed Worker-visible claims")

    reviewed_files = list(reviewed_material["files"])
    if not reviewed_files:
        raise CandidateReviewRefinementEvidenceError(
            "review input must expose at least one candidate file"
        )
    for index, raw_file in enumerate(reviewed_files):
        item = _mapping(raw_file, label=f"reviewed candidate file[{index}]")
        relative = _safe_relative(
            item.get("path"), label=f"reviewed candidate file[{index}].path"
        )
        source = candidate / relative
        if source.is_symlink() or not source.is_file():
            raise CandidateReviewRefinementEvidenceError(
                f"reviewed candidate file is unavailable: {relative}"
            )
        excerpt = _text(
            item.get("excerpt"), label=f"reviewed candidate file[{index}].excerpt"
        )
        if source.read_text(encoding="utf-8") != excerpt:
            raise CandidateReviewRefinementEvidenceError(
                f"reviewed exposure does not match candidate snapshot: {relative}"
            )

    semantic_review = _semantic_review(
        result=_json(review_result_path, label="review result"),
        review_id=review_id,
        candidate_id=candidate_id,
        expected_claim_ids=claim_ids,
    )

    shutil.copytree(base, staging)
    try:
        entry_relative = Path("history/archive/entries") / f"{label.name}.json"
        candidate_relative = Path("history/archive/candidates") / label.name
        diff_relative = Path("history/archive/diffs") / f"{label.name}.diff"
        claims_relative = (
            Path("history/archive/objects") / f"{label.name}-proposal-claims.json"
        )
        review_relative = (
            Path("history/archive/objects") / f"{label.name}-semantic-review.json"
        )
        round_paths = (
            entry_relative,
            candidate_relative,
            diff_relative,
            claims_relative,
            review_relative,
        )
        duplicates = [
            path.as_posix()
            for path in round_paths
            if (staging / path).exists()
        ]
        if duplicates:
            raise CandidateReviewRefinementEvidenceError(
                "round label already exists in retained history: "
                + ", ".join(duplicates)
            )
        copied = _copy_candidate(candidate, staging / candidate_relative)
        (staging / diff_relative).parent.mkdir(parents=True, exist_ok=True)
        (staging / diff_relative).write_text(reviewed_diff, encoding="utf-8")
        _write_json(
            staging / claims_relative,
            {
                "schema_version": 1,
                "candidate_id": candidate_id,
                "authority": "untrusted_proposal_assertions",
                "worker_visible_claims": claims,
            },
        )
        _write_json(staging / review_relative, semantic_review)
        entry = {
            "schema_version": 1,
            "protocol": "candidate_information_set_review_refinement",
            "candidate_id": candidate_id,
            "feedback_mode": "answer_free",
            "worker_visible": False,
            "candidate_component_history_exposed": False,
            "review_feedback_public_basis_allowed": False,
            "evidence_paths": {
                "candidate_snapshot": candidate_relative.as_posix(),
                "candidate_diff": diff_relative.as_posix(),
                "structured_proposal_claims": claims_relative.as_posix(),
                "semantic_review_feedback": review_relative.as_posix(),
            },
            "candidate_snapshot_members": copied,
        }
        _write_json(staging / entry_relative, entry)

        contract_path = staging / "contract.json"
        contract = _json(contract_path, label="base evidence contract")
        retained_entries = contract.get("prior_runtime_experience_entries", [])
        if not isinstance(retained_entries, list):
            raise CandidateReviewRefinementEvidenceError(
                "base prior_runtime_experience_entries must be a list"
            )
        retained_entries = [str(path) for path in retained_entries]
        legacy_entry = contract.get("prior_runtime_experience")
        if (
            not retained_entries
            and isinstance(legacy_entry, str)
            and legacy_entry
        ):
            retained_entries.append(legacy_entry)
        if entry_relative.as_posix() in retained_entries:
            raise CandidateReviewRefinementEvidenceError(
                "round label already exists in retained history entries"
            )
        retained_entries.append(entry_relative.as_posix())
        contract.update(
            {
                "stage": "LINEAGE_REFINEMENT",
                "candidate_parent": candidate_id,
                "candidate_history_exposed": True,
                "candidate_component_history_exposed": False,
                "component_history_enabled": False,
                "history_required": True,
                "coordinated_evidence_required_for_act": False,
                "shared_mechanism_assessment_required": False,
                "shared_mechanism_required_for_act": False,
                "prior_runtime_experience": entry_relative.as_posix(),
                "prior_runtime_experience_entries": retained_entries,
                "required_runtime_experience_entries": [entry_relative.as_posix()],
                "answer_free": True,
                "optimization_answers_exposed_to_evolver": False,
                "optimization_answers_exposed_to_worker": False,
                "review_feedback_worker_visible": False,
                "review_feedback_public_basis_allowed": False,
                "evolver_worker_evaluation_in_this_stage": False,
                "worker_evaluation_in_this_stage": "none",
            }
        )
        instruction = str(contract.get("evolver_instruction", ""))
        if _REFINEMENT_INSTRUCTION not in instruction:
            instruction += _REFINEMENT_INSTRUCTION
        contract["evolver_instruction"] = instruction
        _write_json(contract_path, contract)

        catalog = _json(
            staging / "components/CATALOG.json", label="component catalog"
        )
        if catalog.get("component_count") != 0 or catalog.get("components") != []:
            raise CandidateReviewRefinementEvidenceError(
                "base view must not expose candidate component history"
            )
        _write_json(
            staging / "CANDIDATE-REVIEW-REFINEMENT-RECORD.json",
            {
                "schema_version": 1,
                "stage": "LINEAGE_REFINEMENT",
                "candidate_id": candidate_id,
                "required_history_entry": entry_relative.as_posix(),
                "feedback_mode": "answer_free",
                "worker_visible": False,
                "review_feedback_public_basis_allowed": False,
                "candidate_component_history_exposed": False,
            },
        )
        authorize_evidence_tree(staging)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "schema_version": 1,
        "destination": str(target),
        "stage": "LINEAGE_REFINEMENT",
        "candidate_id": candidate_id,
        "claim_count": len(claims),
        "overall_verdict": semantic_review["overall_verdict"],
        "answer_free": True,
        "worker_visible": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-view", type=Path, required=True)
    parser.add_argument("--proposal-report", type=Path, required=True)
    parser.add_argument(
        "--proposal-parent-dir",
        type=Path,
        help=(
            "Candidate mutation parent used to validate the proposal's "
            "incremental Worker-visible diff."
        ),
    )
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--review-input", type=Path, required=True)
    parser.add_argument("--review-result", type=Path, required=True)
    parser.add_argument(
        "--review-baseline-dir",
        type=Path,
        help=(
            "Baseline used to validate the Reviewer's cumulative "
            "Worker-visible candidate material."
        ),
    )
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--round-label", default="candidate-review-refinement-r1")
    args = parser.parse_args(argv)
    report = build(
        base_view=args.base_view,
        proposal_report=args.proposal_report,
        proposal_parent_dir=args.proposal_parent_dir,
        candidate_dir=args.candidate_dir,
        review_input=args.review_input,
        review_result=args.review_result,
        review_baseline_dir=args.review_baseline_dir,
        destination=args.destination,
        round_label=args.round_label,
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
