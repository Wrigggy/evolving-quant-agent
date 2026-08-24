import json

import pytest

from qea.candidate_information_set_review import (
    CandidateInformationSetReviewError,
    build_candidate_information_set_reviewer_prompt,
    run_candidate_information_set_review,
    validate_candidate_information_set_review,
    validate_candidate_information_set_review_package,
)


def _review_package(search_arm="qrs", *, with_reconciliation_reference=False):
    public_sources = [
        {
            "ref": "public:local-vol-instruction",
            "source_type": "public_contract",
            "excerpt": "Every written local-volatility value must be strictly positive.",
        },
        {
            "ref": "public:holdings-instruction",
            "source_type": "public_contract",
            "excerpt": "Any unambiguous encoding of a pair is acceptable.",
        },
    ]
    if with_reconciliation_reference:
        public_sources.append(
            {
                "ref": "reference:written-object-reconciliation",
                "source_type": "public_reference",
                "excerpt": (
                    "Completion checks must be computed from the serialized "
                    "artifact that is delivered, not only an in-memory object."
                ),
            }
        )
    return {
        "schema_version": 1,
        "review_id": "cisr-fixture-1",
        "candidate_id": "candidate-fixture-1",
        "search_arm": search_arm,
        "candidate": {
            "diff_ref": "candidate:diff",
            "diff": (
                "+ require fitted SVI a > 0\n"
                "+ require pair fields to be two-element arrays\n"
                "+ require written local volatility > 0\n"
                "+ reconcile completion against written artifacts\n"
            ),
        },
        "worker_visible_claims": [
            {
                "claim_id": "svi-a-positive",
                "claim": "Every fitted SVI intercept a must be strictly positive.",
                "surfaces": ["tools", "tool_descriptions"],
                "basis_refs": [
                    "principle:parameter-admissibility",
                    "diagnostic:local-vol",
                ],
            },
            {
                "claim_id": "pair-array-convention",
                "claim": "Every pair field must be a two-element JSON array.",
                "surfaces": ["tools"],
                "basis_refs": [
                    "principle:unambiguous-serialization",
                    "public:holdings-instruction",
                ],
            },
            {
                "claim_id": "local-vol-positive",
                "claim": "Every written local-volatility value must be positive.",
                "surfaces": ["worker_instruction"],
                "basis_refs": ["public:local-vol-instruction"],
            },
            {
                "claim_id": "written-object-reconciliation",
                "claim": "Run completion checks against the written artifact.",
                "surfaces": ["tools"],
                "basis_refs": [
                    "reference:written-object-reconciliation"
                    if with_reconciliation_reference
                    else "principle:written-object-reconciliation"
                ],
            },
        ],
        "public_sources": public_sources,
        "optimize_only_sources": [
            {
                "ref": "diagnostic:local-vol",
                "source_type": "optimize_only_diagnostic",
                "worker_visible": False,
                "excerpt": "Observed fitted SVI a == 0; checker expects a > 0.",
            },
            {
                "ref": "diagnostic:holdings",
                "source_type": "optimize_only_diagnostic",
                "worker_visible": False,
                "excerpt": "Expected pair fields are two-element arrays.",
            },
        ],
    }


def _response(
    *,
    reconciliation_verdict="INCONCLUSIVE",
    reconciliation_ref="candidate:diff",
    coverage_verdict="PASS",
):
    reconciliation_role = (
        "PUBLIC_SUPPORT"
        if reconciliation_verdict == "PASS"
        else "INSUFFICIENT_PUBLIC_SUPPORT"
    )
    overall = "REJECT"
    return {
        "schema_version": 1,
        "review_id": "cisr-fixture-1",
        "candidate_id": "candidate-fixture-1",
        "claim_reviews": [
            {
                "claim_id": "svi-a-positive",
                "verdict": "REJECT",
                "reason": "The fitted-parameter predicate appears only in the optimize diagnostic.",
                "source_basis": [
                    {"ref": "candidate:diff", "role": "CANDIDATE_EXPOSURE"},
                    {"ref": "diagnostic:local-vol", "role": "OPTIMIZE_ONLY_ORIGIN"},
                ],
            },
            {
                "claim_id": "pair-array-convention",
                "verdict": "REJECT",
                "reason": "The exact array convention narrows the public any-unambiguous rule.",
                "source_basis": [
                    {"ref": "public:holdings-instruction", "role": "PUBLIC_CONTRADICTION"}
                ],
            },
            {
                "claim_id": "local-vol-positive",
                "verdict": "PASS",
                "reason": "The public instruction directly requires positive written local volatility.",
                "source_basis": [
                    {"ref": "public:local-vol-instruction", "role": "PUBLIC_SUPPORT"}
                ],
            },
            {
                "claim_id": "written-object-reconciliation",
                "verdict": reconciliation_verdict,
                "reason": (
                    "The supplied public reference directly supports reconciliation."
                    if reconciliation_verdict == "PASS"
                    else "A named principle alone does not establish public support."
                ),
                "source_basis": [
                    {"ref": reconciliation_ref, "role": reconciliation_role}
                ],
            },
        ],
        "coverage_review": {
            "verdict": coverage_verdict,
            "reason": "Every decision-changing rule in the supplied diff is declared.",
            "source_basis": [
                {"ref": "candidate:diff", "role": "CANDIDATE_EXPOSURE"}
            ],
            "undeclared_exposures": [],
        },
        "overall_verdict": overall,
    }


def test_four_observed_claim_boundaries_use_one_batched_call():
    package = _review_package()
    response = _response()
    prompts = []

    def complete(prompt):
        prompts.append(prompt)
        return json.dumps(response)

    result = run_candidate_information_set_review(package, complete=complete)

    assert result == response
    assert len(prompts) == 1
    assert [item["verdict"] for item in result["claim_reviews"]] == [
        "REJECT",
        "REJECT",
        "PASS",
        "INCONCLUSIVE",
    ]
    assert "principle:...` label" in prompts[0]
    assert "contents must never enter the Worker" in prompts[0]
    assert "cannot rewrite the candidate" in prompts[0]
    assert "do not assume the Evolver's claim list is exhaustive" in prompts[0]


def test_written_object_reconciliation_passes_with_supplied_public_reference():
    package = _review_package(with_reconciliation_reference=True)
    response = _response(
        reconciliation_verdict="PASS",
        reconciliation_ref="reference:written-object-reconciliation",
    )

    result = validate_candidate_information_set_review(response, package)

    assert result["claim_reviews"][-1]["verdict"] == "PASS"


@pytest.mark.parametrize("search_arm", ["generic", "qrs"])
def test_generic_and_qrs_receive_the_same_boundary(search_arm):
    prompt = build_candidate_information_set_reviewer_prompt(
        _review_package(search_arm)
    )

    assert "exactly the same information boundary" in prompt
    assert '"search_arm"' not in prompt


def test_generic_and_qrs_reviewer_prompts_are_arm_blind():
    generic = build_candidate_information_set_reviewer_prompt(
        _review_package("generic")
    )
    qrs = build_candidate_information_set_reviewer_prompt(_review_package("qrs"))

    assert generic == qrs


def test_pass_cannot_be_self_justified_by_a_principle_label():
    package = _review_package()
    response = _response(
        reconciliation_verdict="PASS",
        reconciliation_ref="candidate:diff",
    )
    response["claim_reviews"][-1]["source_basis"][0]["role"] = (
        "INSUFFICIENT_PUBLIC_SUPPORT"
    )

    with pytest.raises(
        CandidateInformationSetReviewError, match="PASS requires PUBLIC_SUPPORT"
    ):
        validate_candidate_information_set_review(response, package)


def test_reviewer_rejects_an_invented_source_ref():
    package = _review_package()
    response = _response()
    response["claim_reviews"][0]["source_basis"][0]["ref"] = "public:invented"

    with pytest.raises(CandidateInformationSetReviewError, match="unknown source ref"):
        validate_candidate_information_set_review(response, package)


def test_undeclared_candidate_predicate_rejects_coverage_and_overall():
    package = _review_package()
    package["worker_visible_claims"] = [
        claim
        for claim in package["worker_visible_claims"]
        if claim["claim_id"] != "pair-array-convention"
    ]
    response = _response()
    response["claim_reviews"] = [
        review
        for review in response["claim_reviews"]
        if review["claim_id"] != "pair-array-convention"
    ]
    response["coverage_review"] = {
        "verdict": "REJECT",
        "reason": "The diff contains an undeclared pair-array requirement.",
        "source_basis": [
            {"ref": "candidate:diff", "role": "CANDIDATE_EXPOSURE"}
        ],
        "undeclared_exposures": [
            {
                "exposure": "Every pair field must be a two-element array.",
                "surfaces": ["tools"],
            }
        ],
    }

    result = validate_candidate_information_set_review(response, package)

    assert result["coverage_review"]["verdict"] == "REJECT"
    assert result["overall_verdict"] == "REJECT"


def test_coverage_pass_cannot_hide_undeclared_exposures():
    package = _review_package()
    response = _response()
    response["coverage_review"]["undeclared_exposures"] = [
        {"exposure": "hidden threshold", "surfaces": ["tools"]}
    ]

    with pytest.raises(
        CandidateInformationSetReviewError,
        match="coverage PASS cannot contain undeclared exposures",
    ):
        validate_candidate_information_set_review(response, package)


def test_review_rejects_extra_authority_field():
    package = _review_package()
    response = _response()
    response["promotion_decision"] = "PROMOTE"

    with pytest.raises(
        CandidateInformationSetReviewError,
        match="unexpected Reviewer fields",
    ):
        validate_candidate_information_set_review(response, package)


def test_package_keeps_public_and_optimize_sources_disjoint():
    package = _review_package()
    package["optimize_only_sources"][0]["ref"] = "public:local-vol-instruction"

    with pytest.raises(
        CandidateInformationSetReviewError,
        match="must be disjoint",
    ):
        validate_candidate_information_set_review_package(package)


def test_package_requires_optimize_sources_to_remain_worker_hidden():
    package = _review_package()
    package["optimize_only_sources"][0]["worker_visible"] = True

    with pytest.raises(
        CandidateInformationSetReviewError,
        match="must be Worker-hidden",
    ):
        validate_candidate_information_set_review_package(package)


def test_overall_pass_requires_every_claim_and_coverage_to_pass():
    package = _review_package(with_reconciliation_reference=True)
    for claim in package["worker_visible_claims"]:
        if "public:local-vol-instruction" not in claim["basis_refs"]:
            claim["basis_refs"].append("public:local-vol-instruction")
    response = _response(
        reconciliation_verdict="PASS",
        reconciliation_ref="reference:written-object-reconciliation",
    )
    for review in response["claim_reviews"]:
        review["verdict"] = "PASS"
        review["source_basis"] = [
            {"ref": "public:local-vol-instruction", "role": "PUBLIC_SUPPORT"}
        ]
    response["overall_verdict"] = "PASS"

    result = validate_candidate_information_set_review(response, package)

    assert result["overall_verdict"] == "PASS"


def test_overall_inconclusive_when_no_claim_rejects():
    package = _review_package()
    for claim in package["worker_visible_claims"][:-1]:
        if "public:local-vol-instruction" not in claim["basis_refs"]:
            claim["basis_refs"].append("public:local-vol-instruction")
    response = _response()
    for review in response["claim_reviews"][:-1]:
        review["verdict"] = "PASS"
        review["source_basis"] = [
            {"ref": "public:local-vol-instruction", "role": "PUBLIC_SUPPORT"}
        ]
    response["overall_verdict"] = "INCONCLUSIVE"

    result = validate_candidate_information_set_review(response, package)

    assert result["overall_verdict"] == "INCONCLUSIVE"


def _workflow_policy_package(*, claim_scope="task_agnostic_harness_policy"):
    framework_ref = "guidance/qrs-workflow-framework.json"
    observations = [
        {
            "ref": "benchmarks/qfbench/tasks/holdings/worker_trace.jsonl",
            "source_type": "answer_free_development_observation",
            "task_key": "qfbench:holdings",
            "task_family": "data_engineering",
            "observation": "S1 contains later-state work at line 7.",
            "excerpt": "line 7: task-directed S2 work before S1 COMPLETE",
            "answer_free": True,
        },
        {
            "ref": "benchmarks/qfbench/tasks/localvol/worker_trace.jsonl",
            "source_type": "answer_free_development_observation",
            "task_key": "qfbench:localvol",
            "task_family": "derivatives",
            "observation": "S5 completes without fresh checks at lines 9-10.",
            "excerpt": "line 9: S5 ENTER\nline 10: S5 COMPLETE",
            "answer_free": True,
        },
    ]
    return {
        "schema_version": 1,
        "review_id": "workflow-review",
        "candidate_id": "workflow-candidate",
        "candidate": {
            "diff_ref": "candidate:diff",
            "diff": "+ Keep each state span explicit and observable.\n",
        },
        "worker_visible_claims": [
            {
                "claim_id": "state-span-anchor",
                "claim_scope": claim_scope,
                "claim": "Keep each six-state span explicit and observable.",
                "surfaces": ["skills"],
                "basis_refs": [
                    {"kind": "framework_reference", "ref": framework_ref},
                    *[
                        {
                            "kind": "answer_free_development_observation",
                            "ref": source["ref"],
                        }
                        for source in observations
                    ],
                ],
            }
        ],
        "public_sources": [],
        "trusted_answer_free_sources": [
            {
                "ref": framework_ref,
                "source_type": "framework_reference",
                "excerpt": "Frozen task-agnostic six-state workflow surface.",
                "answer_free": True,
            },
            *observations,
        ],
        "optimize_only_sources": [],
    }


def _workflow_policy_pass_response():
    return {
        "schema_version": 1,
        "review_id": "workflow-review",
        "candidate_id": "workflow-candidate",
        "claim_reviews": [
            {
                "claim_id": "state-span-anchor",
                "verdict": "PASS",
                "reason": (
                    "The frozen workflow surface and two answer-free families "
                    "ground this task-agnostic span policy."
                ),
                "source_basis": [
                    {
                        "ref": "guidance/qrs-workflow-framework.json",
                        "role": "FRAMEWORK_SUPPORT",
                    },
                    {
                        "ref": "benchmarks/qfbench/tasks/holdings/worker_trace.jsonl",
                        "role": "DEVELOPMENT_OBSERVATION",
                    },
                    {
                        "ref": "benchmarks/qfbench/tasks/localvol/worker_trace.jsonl",
                        "role": "DEVELOPMENT_OBSERVATION",
                    },
                ],
            }
        ],
        "coverage_review": {
            "verdict": "PASS",
            "reason": "The complete candidate diff is represented.",
            "source_basis": [
                {"ref": "candidate:diff", "role": "CANDIDATE_EXPOSURE"}
            ],
            "undeclared_exposures": [],
        },
        "overall_verdict": "PASS",
    }


def test_task_agnostic_workflow_policy_can_pass_with_framework_and_cross_family_observations():
    result = validate_candidate_information_set_review(
        _workflow_policy_pass_response(), _workflow_policy_package()
    )

    assert result["overall_verdict"] == "PASS"


def test_task_specific_predicate_cannot_pass_from_trajectory_only_support():
    with pytest.raises(
        CandidateInformationSetReviewError,
        match="PASS requires PUBLIC_SUPPORT",
    ):
        validate_candidate_information_set_review(
            _workflow_policy_pass_response(),
            _workflow_policy_package(claim_scope="task_specific_requirement"),
        )


@pytest.mark.parametrize(
    "field",
    ["public_sources", "trusted_answer_free_sources", "optimize_only_sources"],
)
def test_review_package_rejects_duplicate_source_refs(field):
    package = _workflow_policy_package()
    if not package[field]:
        package[field] = (
            [
                {
                    "ref": "public:one",
                    "source_type": "public_contract",
                    "excerpt": "Public requirement.",
                }
            ]
            if field == "public_sources"
            else [
                {
                    "ref": "diagnostic:one",
                    "source_type": "optimize_only_diagnostic",
                    "worker_visible": False,
                }
            ]
        )
    package[field].append(dict(package[field][0]))

    with pytest.raises(
        CandidateInformationSetReviewError, match="source refs must be unique"
    ):
        validate_candidate_information_set_review_package(package)


def test_review_package_rejects_oversized_model_input():
    package = _workflow_policy_package()
    package["candidate"]["diff"] = "+" + ("x" * 192_000)

    with pytest.raises(
        CandidateInformationSetReviewError,
        match="exceeds the bounded model-input size",
    ):
        validate_candidate_information_set_review_package(package)
