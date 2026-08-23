import json
from pathlib import Path

import pytest

from qea.evolution_evidence import authorize_evidence_tree
from scripts.build_qfbench_candidate_review_refinement_evidence import (
    CandidateReviewRefinementEvidenceError,
    build,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(
            json.dumps(value, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )


def _claims() -> list[dict[str, object]]:
    return [
        {
            "claim_id": "canonical_keys",
            "claim": "Canonicalize comparable keys before joining tables.",
            "surfaces": ["systemprompt"],
            "basis_refs": [
                {
                    "kind": "public_contract",
                    "ref": "benchmarks/qfbench/tasks/holdings/instruction.md",
                    "support": "The public task declares a cross-table universe.",
                }
            ],
        },
        {
            "claim_id": "source_reconciliation",
            "claim": "Reconcile derived totals with the supplied source summary.",
            "surfaces": ["systemprompt"],
            "basis_refs": [
                {
                    "kind": "public_contract",
                    "ref": "benchmarks/qfbench/tasks/holdings/instruction.md",
                    "support": "The public task requires reconciliation.",
                }
            ],
        },
    ]


def _fixture(tmp_path: Path) -> dict[str, Path]:
    base = tmp_path / "public-trajectory"
    _write(base / "access_log.jsonl", "")
    _write(
        base / "contract.json",
        {
            "schema_version": 1,
            "stage": "COORDINATED_BREADTH",
            "candidate_history_exposed": False,
            "component_history_enabled": False,
            "history_required": False,
            "coordinated_evidence_required_for_act": True,
            "shared_mechanism_assessment_required": True,
            "shared_mechanism_required_for_act": True,
            "answer_free": True,
            "optimization_answers_exposed_to_evolver": False,
            "optimization_answers_exposed_to_worker": False,
            "evolver_instruction": "Inspect the public trajectory.",
        },
    )
    _write(
        base / "components/CATALOG.json",
        {
            "schema_version": 1,
            "catalog_policy": "no_candidate_history",
            "component_count": 0,
            "components": [],
        },
    )
    _write(
        base / "benchmarks/qfbench/tasks/holdings/instruction.md",
        "Public holdings instruction.\n",
    )

    candidate = tmp_path / "candidate-c1"
    candidate_prompt = "Base prompt.\n\nCanonicalize keys and reconcile totals.\n"
    _write(candidate / "agent.yaml", "name: public_holdings_c1\n")
    _write(candidate / "systemprompt.md", candidate_prompt)
    _write(
        candidate / "tool_descriptions/run_shell_command.tool.yaml",
        "name: run_shell_command\n",
    )
    proposal_diff = (
        "--- a/systemprompt.md\n"
        "+++ b/systemprompt.md\n"
        "@@ -1 +1,3 @@\n"
        " Base prompt.\n"
        "+\n"
        "+Canonicalize keys and reconcile totals.\n"
    )
    reviewed_diff = proposal_diff.replace(
        "--- a/systemprompt.md\n+++ b/systemprompt.md",
        "--- parent/systemprompt.md\n+++ candidate/systemprompt.md",
    )
    claims = _claims()
    proposal = tmp_path / "proposal-report.json"
    _write(
        proposal,
        {
            "decision": "ACT",
            "admission": {"admitted": True},
            "diff": proposal_diff,
            "summary": {
                "discovery_hypothesis": {
                    "hypothesis": {"worker_visible_claims": claims}
                }
            },
            "provider": "must not be copied",
            "cost": 12.3,
        },
    )
    review_input = tmp_path / "review-input.json"
    _write(
        review_input,
        {
            "schema_version": 1,
            "review_id": "review-r2",
            "candidate_id": "holdings-c1",
            "candidate": {
                "diff": reviewed_diff,
                "files": [
                    {
                        "ref": "candidate:file:systemprompt.md",
                        "path": "systemprompt.md",
                        "surface": "systemprompt",
                        "change_type": "modified",
                        "excerpt": candidate_prompt,
                    }
                ],
            },
            "worker_visible_claims": claims,
            "public_sources": [
                {
                    "ref": "public:holdings",
                    "source_type": "public_contract",
                    "source_path": (
                        "benchmarks/qfbench/tasks/holdings/instruction.md"
                    ),
                    "excerpt": "Public holdings instruction.\n",
                }
            ],
            "optimize_only_sources": [],
        },
    )
    review_result = tmp_path / "review-result.json"
    _write(
        review_result,
        {
            "schema_version": 1,
            "status": "complete",
            "review_scope": "answer_free_candidate_information_set",
            "model": "must not be copied",
            "backend": "must not be copied",
            "source_input": "must not be copied",
            "request": {
                "request_id": "must not be copied",
                "provider": "must not be copied",
                "tokens": 999,
                "cost": 1.25,
            },
            "review": {
                "schema_version": 1,
                "review_id": "review-r2",
                "candidate_id": "holdings-c1",
                "claim_reviews": [
                    {
                        "claim_id": "canonical_keys",
                        "verdict": "INCONCLUSIVE",
                        "reason": "The public wording does not directly entail the full rule.",
                        "source_basis": [
                            {
                                "ref": "public:holdings",
                                "role": "INSUFFICIENT_PUBLIC_SUPPORT",
                            }
                        ],
                    },
                    {
                        "claim_id": "source_reconciliation",
                        "verdict": "PASS",
                        "reason": "The public task directly requires reconciliation.",
                        "source_basis": [
                            {"ref": "public:holdings", "role": "PUBLIC_SUPPORT"}
                        ],
                    },
                ],
                "coverage_review": {
                    "verdict": "PASS",
                    "reason": "The declared claims cover the exact reviewed diff.",
                    "source_basis": [
                        {"ref": "candidate:diff", "role": "CANDIDATE_EXPOSURE"}
                    ],
                    "undeclared_exposures": [],
                },
                "overall_verdict": "INCONCLUSIVE",
            },
            "worker_visible": False,
            "promotion_authority": False,
        },
    )
    return {
        "base": base,
        "candidate": candidate,
        "proposal": proposal,
        "review_input": review_input,
        "review_result": review_result,
    }


def _build(source: dict[str, Path], destination: Path) -> dict[str, object]:
    return build(
        base_view=source["base"],
        proposal_report=source["proposal"],
        candidate_dir=source["candidate"],
        review_input=source["review_input"],
        review_result=source["review_result"],
        destination=destination,
        round_label="holdings-c1-review-r2",
    )


def test_builds_guarded_answer_free_lineage_refinement_view(tmp_path, monkeypatch):
    source = _fixture(tmp_path)
    destination = tmp_path / "refinement-view"

    report = _build(source, destination)

    assert report == {
        "schema_version": 1,
        "destination": str(destination.resolve()),
        "stage": "LINEAGE_REFINEMENT",
        "candidate_id": "holdings-c1",
        "claim_count": 2,
        "overall_verdict": "INCONCLUSIVE",
        "answer_free": True,
        "worker_visible": False,
    }
    authorized = authorize_evidence_tree(destination)
    assert "history/archive/entries/holdings-c1-review-r2.json" in authorized.members

    contract = json.loads((destination / "contract.json").read_text())
    entry_path = "history/archive/entries/holdings-c1-review-r2.json"
    assert contract["stage"] == "LINEAGE_REFINEMENT"
    assert contract["history_required"] is True
    assert contract["required_runtime_experience_entries"] == [entry_path]
    assert contract["candidate_history_exposed"] is True
    assert contract["candidate_component_history_exposed"] is False
    assert contract["component_history_enabled"] is False
    assert contract["coordinated_evidence_required_for_act"] is False
    assert contract["shared_mechanism_assessment_required"] is False
    assert contract["shared_mechanism_required_for_act"] is False
    assert contract["answer_free"] is True
    assert contract["review_feedback_worker_visible"] is False
    assert contract["review_feedback_public_basis_allowed"] is False
    assert "not public evidence" in contract["evolver_instruction"]

    entry = json.loads((destination / entry_path).read_text())
    snapshot = destination / entry["evidence_paths"]["candidate_snapshot"]
    assert (snapshot / "systemprompt.md").read_bytes() == (
        source["candidate"] / "systemprompt.md"
    ).read_bytes()
    assert (snapshot / "agent.yaml").read_bytes() == (
        source["candidate"] / "agent.yaml"
    ).read_bytes()
    reviewed_diff = json.loads(source["review_input"].read_text())["candidate"][
        "diff"
    ]
    assert (
        destination / entry["evidence_paths"]["candidate_diff"]
    ).read_text() == reviewed_diff

    claims = json.loads(
        (
            destination / entry["evidence_paths"]["structured_proposal_claims"]
        ).read_text()
    )
    assert claims["authority"] == "untrusted_proposal_assertions"
    assert claims["worker_visible_claims"] == _claims()
    feedback_path = destination / entry["evidence_paths"][
        "semantic_review_feedback"
    ]
    feedback = json.loads(feedback_path.read_text())
    assert feedback["overall_verdict"] == "INCONCLUSIVE"
    assert feedback["public_basis_authority"] is False
    assert feedback["claim_reviews"][0]["reason"] == (
        "The public wording does not directly entail the full rule."
    )
    assert feedback["claim_reviews"][1]["reason"] == (
        "The public task directly requires reconciliation."
    )
    forbidden_metadata = {
        "model",
        "backend",
        "source_input",
        "request",
        "request_id",
        "provider",
        "cost",
        "tokens",
        "score",
        "reward",
        "official_property",
        "verifier",
        "checker",
        "expected",
    }
    archived_json = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (destination / "history").rglob("*.json")
    )
    assert all(f'"{key}"' not in archived_json for key in forbidden_metadata)

    component_catalog = json.loads(
        (destination / "components/CATALOG.json").read_text()
    )
    assert component_catalog["catalog_policy"] == "no_candidate_history"
    assert component_catalog["component_count"] == 0
    assert component_catalog["components"] == []

    # The newly attached history is readable through the same guarded evidence
    # surface used by the Evolver; no controller-specific adapter is required.
    candidate_root = tmp_path / "guarded-candidate"
    reference_root = tmp_path / "guarded-reference"
    candidate_root.mkdir()
    reference_root.mkdir()
    guarded_log = tmp_path / "guarded-access.jsonl"
    monkeypatch.setenv("QEA_CANDIDATE_ROOT", str(candidate_root))
    monkeypatch.setenv("QEA_EVIDENCE_ROOT", str(destination))
    monkeypatch.setenv("QEA_REFERENCE_ROOT", str(reference_root))
    monkeypatch.setenv("QEA_ACCESS_LOG", str(guarded_log))
    from qea.evolve_agent_full.tools.guarded_workspace import read_workspace

    guarded_entry = read_workspace(source="evidence", file_path=entry_path)
    assert "candidate_information_set_review_refinement" in guarded_entry["content"]
    guarded_feedback = read_workspace(
        source="evidence",
        file_path=entry["evidence_paths"]["semantic_review_feedback"],
    )
    assert "The public wording does not directly entail" in guarded_feedback[
        "content"
    ]


def test_rejects_existing_destination_without_overwriting(tmp_path):
    source = _fixture(tmp_path)
    destination = tmp_path / "refinement-view"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("keep\n", encoding="utf-8")

    with pytest.raises(
        CandidateReviewRefinementEvidenceError, match="destination already exists"
    ):
        _build(source, destination)

    assert marker.read_text(encoding="utf-8") == "keep\n"


def test_rejects_review_exposure_that_is_not_the_exact_candidate_snapshot(tmp_path):
    source = _fixture(tmp_path)
    review_input = json.loads(source["review_input"].read_text())
    review_input["candidate"]["files"][0]["excerpt"] += "Unreviewed change.\n"
    _write(source["review_input"], review_input)

    with pytest.raises(
        CandidateReviewRefinementEvidenceError,
        match="reviewed exposure does not match candidate snapshot",
    ):
        _build(source, tmp_path / "refinement-view")
