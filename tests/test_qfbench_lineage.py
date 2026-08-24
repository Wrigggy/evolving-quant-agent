import pytest

from qea.qfbench_lineage import (
    LineageError,
    freeze_lineage,
    import_candidate_information_set_review,
    import_pilot_report,
    import_proposal_report,
    import_quantitative_protection_review,
    load_lineage,
    new_lineage,
    new_proposal_lineage,
    save_lineage,
)


def _state(limit="1"):
    return _mark_review_passed(new_lineage(
        lineage_id="lineage-a",
        parent_version="h0",
        parent_path="/workers/h0",
        candidate_version="c1",
        candidate_path="/workers/c1",
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd=limit,
    ))


def _quant_state(limit="2"):
    return _mark_review_passed(new_lineage(
        lineage_id="quant-lineage",
        parent_version="h0",
        parent_path="/workers/h0",
        candidate_version="search-v2",
        candidate_path="/workers/search-v2",
        target_task_id="dupire-local-vol",
        protection_task_id="localvol-barrier",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd=limit,
        quantitative_protection_review=True,
    ))


def _report(run_id, task, parent, candidate, cost="0.1"):
    def summary(score):
        passed, total, reward = score
        return {
            "scores": [{
                "task_id": task,
                "reward": reward,
                "tests_passed": passed,
                "tests_failed": total - passed,
                "verifier_exit_code": 0,
            }]
        }

    return {
        "status": "complete",
        "run_id": run_id,
        "summaries": {
            "h0": summary(parent),
            "candidate": summary(candidate),
        },
        "cost": {
            "provider_cost_usd": cost,
            "completed_request_count": 2,
            "total_tokens": 100,
        },
    }


def _proposal_state(limit="1"):
    return new_proposal_lineage(
        lineage_id="lineage-a",
        parent_version="h0",
        parent_path="/workers/h0",
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd=limit,
    )


def _proposal(decision, admitted, candidate_dir="/real/proposal/candidate"):
    return {
        "decision": decision,
        "candidate_dir": candidate_dir,
        "admission": {"admitted": admitted},
        "candidate_generation_throughput": {
            "provider_cost_usd": "0.02",
            "completed_request_count": 3,
            "downstream_delivery_request_count": 1,
            "total_tokens": 200,
        },
    }


def _mark_review_passed(state):
    candidate = state["candidate"]
    worker_dir = candidate["worker_dir"]
    candidate["information_set_review"] = {
        "review_id": "fixture-review",
        "overall_verdict": "PASS",
        "reviewed_candidate_dir": worker_dir,
    }
    state["candidate_information_set_review"] = True
    state["observations"]["information_set_review"] = {
        "review_id": "fixture-review",
        "overall_verdict": "PASS",
        "reviewed_candidate_dir": worker_dir,
        "coverage_review": {"verdict": "PASS"},
    }
    state["phase"] = "TARGET"
    return state


def _worker(root, tools):
    root.mkdir(parents=True)
    entries = "\n".join(
        f"  - name: {name}\n    yaml_path: ./tool_descriptions/{name}.tool.yaml"
        for name in tools
    )
    (root / "agent.yaml").write_text(f"tools:\n{entries}\n")
    return root


def _worker_with_registered_tool(
    root,
    *,
    description="Audit quantitative state.",
    source="def audit_quant_state():\n    return 1\n",
):
    root.mkdir(parents=True)
    (root / "tool_descriptions").mkdir()
    (root / "tools").mkdir()
    (root / "agent.yaml").write_text(
        "tools:\n"
        "  - name: run_shell_command\n"
        "    yaml_path: ./tool_descriptions/run_shell_command.tool.yaml\n"
        "  - name: audit_quant_state\n"
        "    yaml_path: ./tool_descriptions/audit_quant_state.tool.yaml\n"
        "    binding: tools.audit:audit_quant_state\n"
    )
    (root / "tool_descriptions/run_shell_command.tool.yaml").write_text(
        "type: tool\nname: run_shell_command\ndescription: Run shell.\n"
    )
    (root / "tool_descriptions/audit_quant_state.tool.yaml").write_text(
        "type: tool\n"
        "name: audit_quant_state\n"
        f"description: {description}\n"
    )
    (root / "tools/audit.py").write_text(source)
    return root


def _apply(
    state,
    stage,
    report,
    *,
    property_set_safe=None,
    relation_observed=None,
    property_delta=None,
):
    return import_pilot_report(
        state,
        stage=stage,
        report=report,
        report_path=f"/{report['run_id']}/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
        relation_observed=relation_observed,
        property_delta=property_delta,
        property_set_safe=property_set_safe,
    )


def _semantic_state(*, token="audit_component", relation="relation-any"):
    state = _state()
    state["repeat_consistency_policy"] = "resolved_property_footprint_v1"
    state["proposal"] = {
        "mechanism_claim": {
            "selected_relation": (
                {"relation_id": relation} if relation is not None else None
            )
        }
    }
    if token is not None:
        state["candidate"]["activation_token"] = token
    return state


def _activated(report, *, token="audit_component", count=1):
    report["activations"] = {
        "candidate": {
            "activation_count": count,
            "attempts": [
                {
                    "attempt_id": f"{report['run_id']}-candidate",
                    "task_id": report["summaries"]["candidate"]["scores"][0][
                        "task_id"
                    ],
                    "activation_token": token,
                    "activated": count > 0,
                }
            ],
        }
    }
    return report


def _delta(parent_failed, candidate_failed):
    parent = set(parent_failed)
    candidate = set(candidate_failed)
    return {
        "parent_failed": sorted(parent),
        "candidate_failed": sorted(candidate),
        "resolved": sorted(parent - candidate),
        "introduced": sorted(candidate - parent),
        "persistent": sorted(parent & candidate),
    }


def test_repeated_gain_and_safe_protection_promote_then_freeze():
    state = _apply(_state(), "target", _report("target-run", "target", (48, 51, 0), (50, 51, 0)))
    state = _apply(state, "repeat", _report("repeat-run", "target", (37, 51, 0), (50, 51, 0)))
    state = _apply(
        state,
        "protection",
        _report("protect-run", "protect", (42, 42, 1), (42, 42, 1)),
        property_set_safe=True,
    )

    assert state["decision"] == "PROMOTE"
    assert state["current_parent"]["version"] == "c1"
    assert freeze_lineage(state)["phase"] == "FROZEN"


def test_property_swap_rolls_back_aggregate_tie():
    state = _apply(_state(), "target", _report("target-run", "target", (65, 68, 0), (68, 68, 1)))
    state = _apply(state, "repeat", _report("repeat-run", "target", (66, 68, 0), (68, 68, 1)))
    state = _apply(
        state,
        "protection",
        _report("protect-run", "protect", (38, 39, 0.96), (38, 39, 0.96)),
        property_set_safe=False,
    )

    assert state["decision"] == "ROLLBACK"
    assert state["current_parent"]["version"] == "h0"


def test_target_without_gain_rolls_back_without_repeat():
    state = _apply(_state(), "target", _report("target-run", "target", (50, 51, 0), (49, 51, 0)))

    assert state["decision"] == "ROLLBACK"
    assert "repeat" not in state["observations"]


def test_repeat_semantic_footprint_consistent_advances_to_protection():
    target = _activated(
        _report("target-run", "target", (1, 3, 0), (2, 3, 1))
    )
    state = _apply(
        _semantic_state(),
        "target",
        target,
        property_delta=_delta(("property-P", "property-Z"), ("property-Z",)),
    )
    repeat = _activated(
        _report("repeat-run", "target", (1, 3, 0), (2, 3, 1))
    )
    state = _apply(
        state,
        "repeat",
        repeat,
        property_delta=_delta(("property-P", "property-Z"), ("property-Z",)),
    )

    semantic = state["observations"]["repeat"]["mechanism"]["semantic_repeat"]
    assert semantic["verdict"] == "CONSISTENT"
    assert semantic["expected_property_ids"] == ["property-P"]
    assert state["phase"] == "PROTECTION"
    assert _apply(
        state,
        "repeat",
        repeat,
        property_delta=_delta(("property-P", "property-Z"), ("property-Z",)),
    ) == state


def test_unmatched_protection_keeps_safe_gate_without_relation_gain_label():
    state = _apply(
        _semantic_state(),
        "target",
        _activated(
            _report("target-run", "target", (67, 68, 0), (68, 68, 1))
        ),
        property_delta=_delta(("property-svi-a",), ()),
    )
    state = _apply(
        state,
        "repeat",
        _activated(
            _report("repeat-run", "target", (67, 68, 0), (68, 68, 1))
        ),
        property_delta=_delta(("property-svi-a",), ()),
    )
    protection = _activated(
        _report("protect-run", "protect", (38, 39, 0.96), (39, 39, 1))
    )
    promoted = _apply(
        state,
        "protection",
        protection,
        property_set_safe=True,
    )

    observation = promoted["observations"]["protection"]
    mechanism = observation["mechanism"]
    assert promoted["decision"] == "PROMOTE"
    assert observation["gate_passed"] is True
    assert observation["property_set_safe"] is True
    assert mechanism["official_outcome"]["strict_gain_observed"] is True
    assert mechanism["relation_outcome"] == "NOT_EXERCISED"
    assert mechanism["protection_outcome"] == "SAFE_NO_REGRESSION"
    assert mechanism["semantic_protection"] == {
        "policy": "target_relation_exercise_v1",
        "relation_id": "relation-any",
        "expected_property_ids": ["property-svi-a"],
        "relation_observed": None,
        "verdict": "NOT_EXERCISED",
        "reason": "target_relation_not_observed_on_protection",
        "boundary": "safety_gate_not_relation_transfer",
    }
    assert (
        _apply(
            promoted,
            "protection",
            protection,
            property_set_safe=True,
        )
        == promoted
    )


def test_matched_semantic_protection_retains_relation_outcome():
    state = _apply(
        _semantic_state(),
        "target",
        _activated(_report("target-run", "target", (1, 2, 0), (2, 2, 1))),
        property_delta=_delta(("property-P",), ()),
    )
    state = _apply(
        state,
        "repeat",
        _activated(_report("repeat-run", "target", (1, 2, 0), (2, 2, 1))),
        property_delta=_delta(("property-P",), ()),
    )
    state = _apply(
        state,
        "protection",
        _activated(_report("protect-run", "protect", (1, 2, 0), (2, 2, 1))),
        property_set_safe=True,
        property_delta=_delta(("property-P",), ()),
    )

    mechanism = state["observations"]["protection"]["mechanism"]
    assert state["decision"] == "PROMOTE"
    assert mechanism["relation_outcome"] == "ACTIVATED_WITH_OFFICIAL_GAIN"
    assert mechanism["protection_outcome"] == "SAFE_NO_REGRESSION"
    assert mechanism["semantic_protection"]["verdict"] == "MATCHED"
    assert mechanism["semantic_protection"]["reason"] == (
        "target_property_footprint_observed"
    )


def test_repeat_same_score_gain_on_unrelated_property_rolls_back():
    target = _activated(
        _report("target-run", "target", (1, 3, 0), (2, 3, 1))
    )
    state = _apply(
        _semantic_state(relation="open-family-relation"),
        "target",
        target,
        property_delta=_delta(("property-P", "property-Q"), ("property-Q",)),
    )
    repeat = _activated(
        _report("repeat-run", "target", (1, 3, 0), (2, 3, 1),),
        count=2,
    )
    state = _apply(
        state,
        "repeat",
        repeat,
        property_delta=_delta(("property-P", "property-Q"), ("property-P",)),
    )

    semantic = state["observations"]["repeat"]["mechanism"]["semantic_repeat"]
    assert semantic["persistent_expected"] == ["property-P"]
    assert semantic["unrelated_resolved"] == ["property-Q"]
    assert semantic["verdict"] == "INCONSISTENT"
    assert state["decision"] == "ROLLBACK"


def test_repeat_callable_component_must_activate_again():
    state = _apply(
        _semantic_state(),
        "target",
        _activated(_report("target-run", "target", (1, 2, 0), (2, 2, 1))),
        property_delta=_delta(("property-P",), ()),
    )
    state = _apply(
        state,
        "repeat",
        _activated(
            _report("repeat-run", "target", (1, 2, 0), (2, 2, 1)), count=0
        ),
        property_delta=_delta(("property-P",), ()),
    )

    semantic = state["observations"]["repeat"]["mechanism"]["semantic_repeat"]
    assert semantic["verdict"] == "INCONSISTENT"
    assert semantic["reason"] == "repeat_component_not_activated"
    assert state["decision"] == "ROLLBACK"


def test_repeat_reintroducing_target_property_rolls_back():
    state = _apply(
        _semantic_state(),
        "target",
        _activated(_report("target-run", "target", (1, 3, 0), (2, 3, 1))),
        property_delta=_delta(("property-P", "property-Q"), ("property-Q",)),
    )
    state = _apply(
        state,
        "repeat",
        _activated(_report("repeat-run", "target", (1, 3, 0), (2, 3, 1))),
        property_delta=_delta(("property-Q",), ("property-P",)),
    )

    semantic = state["observations"]["repeat"]["mechanism"]["semantic_repeat"]
    assert semantic["introduced_expected"] == ["property-P"]
    assert semantic["repeat_introduced"] == ["property-P"]
    assert semantic["verdict"] == "INCONSISTENT"
    assert state["decision"] == "ROLLBACK"


def test_repeat_target_footprint_not_exercised_holds_for_refine():
    state = _apply(
        _semantic_state(),
        "target",
        _activated(_report("target-run", "target", (1, 3, 0), (2, 3, 1))),
        property_delta=_delta(("property-P", "property-Q"), ("property-Q",)),
    )
    state = _apply(
        state,
        "repeat",
        _activated(_report("repeat-run", "target", (2, 3, 0), (3, 3, 1))),
        property_delta=_delta(("property-Q",), ()),
    )

    semantic = state["observations"]["repeat"]["mechanism"]["semantic_repeat"]
    assert semantic["not_exercised_expected"] == ["property-P"]
    assert semantic["verdict"] == "NOT_EXERCISED"
    assert state["decision"] == "HOLD_FOR_REFINE"


def test_unexercised_footprint_holds_before_aggregate_repeat_gate():
    state = _apply(
        _semantic_state(),
        "target",
        _activated(_report("target-run", "target", (1, 3, 0), (2, 3, 1))),
        property_delta=_delta(("property-P", "property-Q"), ("property-Q",)),
    )
    state = _apply(
        state,
        "repeat",
        _activated(_report("repeat-run", "target", (2, 3, 0), (2, 3, 0))),
        property_delta=_delta(("property-Q",), ("property-Q",)),
    )

    semantic = state["observations"]["repeat"]["mechanism"]["semantic_repeat"]
    assert state["observations"]["repeat"]["gate_passed"] is False
    assert semantic["not_exercised_expected"] == ["property-P"]
    assert semantic["verdict"] == "NOT_EXERCISED"
    assert state["decision"] == "HOLD_FOR_REFINE"


def test_callable_target_without_activation_is_unbound_and_holds():
    state = _apply(
        _semantic_state(),
        "target",
        _activated(
            _report("target-run", "target", (1, 2, 0), (2, 2, 1)), count=0
        ),
        property_delta=_delta(("property-P",), ()),
    )

    footprint = state["observations"]["target"]["mechanism"][
        "empirical_relation_footprint"
    ]
    assert footprint["status"] == "UNBOUND"
    assert state["decision"] == "HOLD_FOR_REFINE"


def test_prompt_only_candidate_can_repeat_same_property_footprint():
    state = _apply(
        _semantic_state(token=None),
        "target",
        _report("target-run", "target", (1, 2, 0), (2, 2, 1)),
        property_delta=_delta(("arbitrary-property",), ()),
    )
    state = _apply(
        state,
        "repeat",
        _report("repeat-run", "target", (1, 2, 0), (2, 2, 1)),
        property_delta=_delta(("arbitrary-property",), ()),
    )

    assert (
        state["observations"]["repeat"]["mechanism"]["semantic_repeat"][
            "verdict"
        ]
        == "CONSISTENT"
    )
    assert state["phase"] == "PROTECTION"


def test_generic_candidate_can_anchor_footprint_without_named_relation():
    state = _apply(
        _semantic_state(token=None, relation=None),
        "target",
        _report("target-run", "target", (1, 2, 0), (2, 2, 1)),
        property_delta=_delta(("open-property",), ()),
    )
    footprint = state["observations"]["target"]["mechanism"][
        "empirical_relation_footprint"
    ]
    assert footprint["relation_id"] is None
    assert footprint["status"] == "ANCHORED"

    state = _apply(
        state,
        "repeat",
        _report("repeat-run", "target", (1, 2, 0), (2, 2, 1)),
        property_delta=_delta(("open-property",), ()),
    )
    assert state["phase"] == "PROTECTION"


def test_reimporting_accounted_report_is_idempotent():
    report = _report("target-run", "target", (48, 51, 0), (50, 51, 0))
    state = _apply(_state(), "target", report)
    again = _apply(state, "target", report)

    assert again == state
    assert again["cost"]["provider_cost_usd"] == "0.1"


def test_cost_limit_stops_before_repeat():
    state = _apply(
        _state(limit="0.1"),
        "target",
        _report("target-run", "target", (48, 51, 0), (50, 51, 0)),
    )

    assert state["decision"] == "BUDGET_STOP"
    assert state["phase"] == "BUDGET_STOP"


def test_admitted_act_without_claims_holds_for_universal_review():
    report = _proposal("ACT", True)
    state = import_proposal_report(
        _proposal_state(),
        report=report,
        report_path="/proposal/proposal-report.json",
        proposal_run_id="proposal-r1",
        candidate_version="candidate-r1",
    )
    again = import_proposal_report(
        state,
        report=report,
        report_path="/proposal/proposal-report.json",
        proposal_run_id="proposal-r1",
        candidate_version="candidate-r1",
    )

    assert state["phase"] == "HOLD_FOR_REFINE"
    assert state["candidate"] == {
        "version": "candidate-r1",
        "worker_dir": "/real/proposal/candidate",
        "activation_binding": {
            "status": "none",
            "new_registered_tools": [],
            "modified_registered_tools": [],
        },
    }
    assert again == state
    assert state["cost"]["provider_cost_usd"] == "0.02"
    assert state["cost"]["completed_requests"] == 4


def test_proposal_singleton_tool_binds_and_observes_activation(tmp_path):
    parent = _worker(tmp_path / "parent", ("run_shell_command",))
    candidate = _worker(
        tmp_path / "candidate", ("run_shell_command", "audit_quant_state")
    )
    state = new_proposal_lineage(
        lineage_id="lineage-a",
        parent_version="h0",
        parent_path=str(parent),
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
    )
    report = _proposal("ACT", True, str(candidate))
    report["summary"] = {
        "discovery_hypothesis": {
            "hypothesis": {
                "selected_relation": {"relation_id": "state_reconciliation"},
                "component_routing": {"selected_locus": "tools"},
            }
        }
    }
    state = import_proposal_report(
        state,
        report=report,
        report_path="/proposal/proposal-report.json",
        proposal_run_id="proposal-r1",
        candidate_version="candidate-r1",
    )
    state = _mark_review_passed(state)

    assert state["candidate"]["activation_token"] == "audit_quant_state"
    assert state["candidate"]["activation_binding"]["status"] == "singleton"
    realized = state["candidate"]["realized_component"]
    assert realized["change_kind"] == "added"
    assert realized["changed_surfaces"] == ["registration"]
    assert (
        state["proposal"]["mechanism_claim"]["selected_relation"]["relation_id"]
        == "state_reconciliation"
    )

    pilot = _report("target-run", "target", (1, 2, 0), (2, 2, 1))
    pilot["activations"] = {
        "candidate": {
            "activation_count": 1,
            "attempts": [
                {
                    "attempt_id": "attempt-c1",
                    "task_id": "target",
                    "trace_path": "attempts/attempt-c1/raw-trace.jsonl",
                    "activation_token": "audit_quant_state",
                    "activated": True,
                }
            ],
        }
    }
    observed = _apply(state, "target", pilot, relation_observed=True)
    mechanism = observed["observations"]["target"]["mechanism"]

    assert observed["observations"]["target"]["relation_observed"] is True
    assert mechanism["activation"]["status"] == "ACTIVATED"
    assert mechanism["activation"]["count"] == 1
    assert mechanism["official_outcome"] == {
        "reward_delta": 1.0,
        "tests_passed_delta": 1,
        "strict_gain_observed": True,
    }
    assert mechanism["relation_outcome"] == "ACTIVATED_WITH_OFFICIAL_GAIN"
    assert _apply(observed, "target", pilot, relation_observed=True) == observed


def test_proposal_zero_or_multiple_new_tools_does_not_guess(tmp_path):
    parent = _worker(tmp_path / "parent", ("run_shell_command",))
    for label, tools, expected in (
        ("zero", ("run_shell_command",), "none"),
        (
            "multiple",
            ("run_shell_command", "audit_one", "audit_two"),
            "ambiguous",
        ),
    ):
        candidate = _worker(tmp_path / label, tools)
        state = new_proposal_lineage(
            lineage_id=label,
            parent_version="h0",
            parent_path=str(parent),
            target_task_id="target",
            protection_task_id="protect",
            worker_route="route-a",
            worker_budget="normal",
            cost_limit_usd="1",
        )
        state = import_proposal_report(
            state,
            report=_proposal("ACT", True, str(candidate)),
            report_path=f"/{label}/proposal-report.json",
            proposal_run_id=f"proposal-{label}",
            candidate_version=f"candidate-{label}",
        )

        assert state["candidate"]["activation_binding"]["status"] == expected
        assert "activation_token" not in state["candidate"]


def test_proposal_single_modified_registered_tool_binds_and_resumes(tmp_path):
    parent = _worker_with_registered_tool(tmp_path / "parent")
    candidate = _worker_with_registered_tool(
        tmp_path / "candidate",
        source="def audit_quant_state():\n    return 2\n",
    )
    state = new_proposal_lineage(
        lineage_id="modified",
        parent_version="h0",
        parent_path=str(parent),
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
    )
    report = _proposal("ACT", True, str(candidate))
    state = import_proposal_report(
        state,
        report=report,
        report_path="/modified/proposal-report.json",
        proposal_run_id="proposal-modified",
        candidate_version="candidate-modified",
    )
    again = import_proposal_report(
        state,
        report=report,
        report_path="/modified/proposal-report.json",
        proposal_run_id="proposal-modified",
        candidate_version="candidate-modified",
    )

    binding = state["candidate"]["activation_binding"]
    assert binding["status"] == "singleton"
    assert binding["new_registered_tools"] == []
    assert binding["modified_registered_tools"] == ["audit_quant_state"]
    assert state["candidate"]["activation_token"] == "audit_quant_state"
    assert state["candidate"]["realized_component"]["change_kind"] == "modified"
    assert state["candidate"]["realized_component"]["changed_surfaces"] == [
        "source"
    ]
    assert again == state
    assert state["cost"]["completed_requests"] == 4


def test_proposal_descriptor_modification_binds_registered_tool(tmp_path):
    parent = _worker_with_registered_tool(tmp_path / "parent")
    candidate = _worker_with_registered_tool(
        tmp_path / "candidate", description="Audit calibrated surfaces."
    )
    state = new_proposal_lineage(
        lineage_id="descriptor-modified",
        parent_version="h0",
        parent_path=str(parent),
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
    )
    state = import_proposal_report(
        state,
        report=_proposal("ACT", True, str(candidate)),
        report_path="/descriptor-modified/proposal-report.json",
        proposal_run_id="proposal-descriptor-modified",
        candidate_version="candidate-descriptor-modified",
    )

    assert state["candidate"]["activation_token"] == "audit_quant_state"
    assert state["candidate"]["realized_component"]["changed_surfaces"] == [
        "descriptor"
    ]


def test_proposal_multiple_registered_tool_changes_remain_ambiguous(tmp_path):
    parent = _worker_with_registered_tool(tmp_path / "parent")
    candidate = _worker_with_registered_tool(
        tmp_path / "candidate",
        source="def audit_quant_state():\n    return 2\n",
    )
    with candidate.joinpath("agent.yaml").open("a") as stream:
        stream.write(
            "  - name: audit_second_state\n"
            "    yaml_path: ./tool_descriptions/audit_second_state.tool.yaml\n"
        )
    candidate.joinpath(
        "tool_descriptions/audit_second_state.tool.yaml"
    ).write_text(
        "type: tool\nname: audit_second_state\n"
        "description: Audit a second state.\n"
    )
    state = new_proposal_lineage(
        lineage_id="ambiguous-modified",
        parent_version="h0",
        parent_path=str(parent),
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
    )
    state = import_proposal_report(
        state,
        report=_proposal("ACT", True, str(candidate)),
        report_path="/ambiguous-modified/proposal-report.json",
        proposal_run_id="proposal-ambiguous-modified",
        candidate_version="candidate-ambiguous-modified",
    )

    binding = state["candidate"]["activation_binding"]
    assert binding["status"] == "ambiguous"
    assert binding["new_registered_tools"] == ["audit_second_state"]
    assert binding["modified_registered_tools"] == ["audit_quant_state"]
    assert "activation_token" not in state["candidate"]


def test_prompt_only_refinement_inherits_declared_registered_component(tmp_path):
    parent = _worker_with_registered_tool(tmp_path / "parent")
    candidate = _worker_with_registered_tool(tmp_path / "candidate")
    parent.joinpath("systemprompt.md").write_text("Use the audit when relevant.\n")
    candidate.joinpath("systemprompt.md").write_text(
        "Route reconciliation work through the audit before finalizing.\n"
    )
    state = new_proposal_lineage(
        lineage_id="prompt-refinement",
        parent_version="component-v1",
        parent_path=str(parent),
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
        retained_activation_token="audit_quant_state",
    )
    state = import_proposal_report(
        state,
        report=_proposal("ACT", True, str(candidate)),
        report_path="/prompt-refinement/proposal-report.json",
        proposal_run_id="proposal-prompt-refinement",
        candidate_version="candidate-prompt-refinement",
    )
    again = import_proposal_report(
        state,
        report=_proposal("ACT", True, str(candidate)),
        report_path="/prompt-refinement/proposal-report.json",
        proposal_run_id="proposal-prompt-refinement",
        candidate_version="candidate-prompt-refinement",
    )

    assert state["current_parent"]["retained_activation_token"] == (
        "audit_quant_state"
    )
    binding = state["candidate"]["activation_binding"]
    assert binding["status"] == "retained"
    assert binding["new_registered_tools"] == []
    assert binding["modified_registered_tools"] == []
    assert state["candidate"]["activation_token"] == "audit_quant_state"
    assert state["candidate"]["realized_component"] == {
        "kind": "tool",
        "token": "audit_quant_state",
        "change_kind": "retained",
        "changed_surfaces": [],
        "descriptor_path": (
            "./tool_descriptions/audit_quant_state.tool.yaml"
        ),
        "binding": "tools.audit:audit_quant_state",
        "source": "lineage_parent_retained_activation_token",
    }
    assert again == state


def test_retained_component_must_remain_registered_in_candidate(tmp_path):
    parent = _worker_with_registered_tool(tmp_path / "parent")
    candidate = _worker_with_registered_tool(tmp_path / "candidate")
    candidate.joinpath("agent.yaml").write_text(
        "tools:\n"
        "  - name: run_shell_command\n"
        "    yaml_path: ./tool_descriptions/run_shell_command.tool.yaml\n"
    )
    state = new_proposal_lineage(
        lineage_id="removed-component",
        parent_version="component-v1",
        parent_path=str(parent),
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
        retained_activation_token="audit_quant_state",
    )
    state = import_proposal_report(
        state,
        report=_proposal("ACT", True, str(candidate)),
        report_path="/removed-component/proposal-report.json",
        proposal_run_id="proposal-removed-component",
        candidate_version="candidate-removed-component",
    )

    assert state["candidate"]["activation_binding"]["status"] == "none"
    assert "activation_token" not in state["candidate"]


def test_singleton_change_wins_over_retained_component(tmp_path):
    parent = _worker_with_registered_tool(tmp_path / "parent")
    candidate = _worker_with_registered_tool(tmp_path / "candidate")
    with candidate.joinpath("agent.yaml").open("a") as stream:
        stream.write(
            "  - name: new_reconciliation_tool\n"
            "    yaml_path: ./tool_descriptions/new_reconciliation_tool.tool.yaml\n"
        )
    candidate.joinpath(
        "tool_descriptions/new_reconciliation_tool.tool.yaml"
    ).write_text(
        "type: tool\nname: new_reconciliation_tool\n"
        "description: Reconcile the current state.\n"
    )
    state = new_proposal_lineage(
        lineage_id="singleton-wins",
        parent_version="component-v1",
        parent_path=str(parent),
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
        retained_activation_token="audit_quant_state",
    )
    state = import_proposal_report(
        state,
        report=_proposal("ACT", True, str(candidate)),
        report_path="/singleton-wins/proposal-report.json",
        proposal_run_id="proposal-singleton-wins",
        candidate_version="candidate-singleton-wins",
    )

    assert state["candidate"]["activation_binding"]["status"] == "singleton"
    assert state["candidate"]["activation_token"] == "new_reconciliation_tool"
    assert state["candidate"]["realized_component"]["source"] == (
        "admitted_candidate_registration"
    )


def test_ambiguous_change_never_falls_back_to_retained_component(tmp_path):
    parent = _worker_with_registered_tool(tmp_path / "parent")
    candidate = _worker_with_registered_tool(
        tmp_path / "candidate",
        source="def audit_quant_state():\n    return 2\n",
    )
    with candidate.joinpath("agent.yaml").open("a") as stream:
        stream.write(
            "  - name: second_component\n"
            "    yaml_path: ./tool_descriptions/second_component.tool.yaml\n"
        )
    candidate.joinpath("tool_descriptions/second_component.tool.yaml").write_text(
        "type: tool\nname: second_component\ndescription: Second component.\n"
    )
    state = new_proposal_lineage(
        lineage_id="ambiguous-retained",
        parent_version="component-v1",
        parent_path=str(parent),
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
        retained_activation_token="audit_quant_state",
    )
    state = import_proposal_report(
        state,
        report=_proposal("ACT", True, str(candidate)),
        report_path="/ambiguous-retained/proposal-report.json",
        proposal_run_id="proposal-ambiguous-retained",
        candidate_version="candidate-ambiguous-retained",
    )

    assert state["candidate"]["activation_binding"]["status"] == "ambiguous"
    assert "activation_token" not in state["candidate"]


def test_abstain_is_a_terminal_proposal_without_candidate():
    state = import_proposal_report(
        _proposal_state(),
        report=_proposal("ABSTAIN", None),
        report_path="/proposal/proposal-report.json",
        proposal_run_id="proposal-r1",
        candidate_version="unused",
    )

    assert state["decision"] == "ABSTAIN"
    assert state["phase"] == "FROZEN"
    assert state["candidate"] is None


def test_unadmitted_act_never_enters_candidate_lineage():
    state = import_proposal_report(
        _proposal_state(),
        report=_proposal("ACT", False),
        report_path="/proposal/proposal-report.json",
        proposal_run_id="proposal-r1",
        candidate_version="unused",
    )

    assert state["decision"] == "ROLLBACK"
    assert state["status"] == "proposal_rejected"
    assert state["candidate"] is None


def test_search_v2_conflicting_protection_repeat_holds_for_refinement():
    state = _apply(
        _quant_state(),
        "target",
        _report(
            "target-run", "dupire-local-vol", (65, 68, 0), (68, 68, 1)
        ),
    )
    state = _apply(
        state,
        "repeat",
        _report(
            "target-repeat", "dupire-local-vol", (66, 68, 0), (68, 68, 1)
        ),
    )
    first_protection = _report(
        "protection-r1",
        "localvol-barrier",
        (38, 39, 0.96),
        (38, 39, 0.96),
    )
    state = import_pilot_report(
        state,
        stage="protection",
        report=first_protection,
        report_path="/protection-r1/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
        property_set_safe=False,
        quantitative_protection_triage={
            "verdict": "INCONCLUSIVE",
            "outcome_severity": "UNRESOLVED",
            "failed_properties": {
                "parent": ["barrier_outputs_reasonable"],
                "candidate": ["vanilla_mc_close_to_surface"],
            },
        },
    )
    assert state["phase"] == "PROTECTION_REVIEW"

    review = {
        "schema_version": 1,
        "reviews": [{
            "case_id": "search-v2-protection",
            "outcome_severity": "UNRESOLVED",
            "causal_attribution": "UNRESOLVED",
            "quantitative_diagnosis": "NUMERIC_TOLERANCE_ONLY",
            "next_evidence": "PAIRED_PROTECTION_REPEAT",
            "evidence_refs": ["search-v2:protection-r1"],
        }],
    }
    state = import_quantitative_protection_review(
        state,
        review_id="review-r1",
        review_path="/review-r1/RESULT.json",
        review_payload=review,
        case_id="search-v2-protection",
        review_accounting={
            "provider_cost_usd": "0.012",
            "completed_request_count": 1,
            "total_tokens": 123,
        },
    )
    resumed_review = import_quantitative_protection_review(
        state,
        review_id="review-r1",
        review_path="/review-r1/RESULT.json",
        review_payload=review,
        case_id="search-v2-protection",
        review_accounting={
            "provider_cost_usd": "0.012",
            "completed_request_count": 1,
            "total_tokens": 123,
        },
    )
    assert resumed_review == state
    assert state["phase"] == "PROTECTION_REPEAT"

    repeat_report = _report(
        "protection-r2",
        "localvol-barrier",
        (39, 39, 1),
        (38, 39, 0.96),
    )
    state = import_pilot_report(
        state,
        stage="protection_repeat",
        report=repeat_report,
        report_path="/protection-r2/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
        property_set_safe=False,
        quantitative_protection_triage={
            "verdict": "INCONCLUSIVE",
            "outcome_severity": "UNRESOLVED",
            "decision_label": "STILL_INCONCLUSIVE",
            "failed_properties": {
                "parent": [],
                "candidate": ["barrier_outputs_reasonable"],
            },
            "evidence_summary": (
                "candidate failure identity rotated across protection repeats"
            ),
        },
    )
    resumed_repeat = import_pilot_report(
        state,
        stage="protection_repeat",
        report=repeat_report,
        report_path="/protection-r2/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
        property_set_safe=False,
        quantitative_protection_triage={"verdict": "INCONCLUSIVE"},
    )

    assert resumed_repeat == state
    assert state["decision"] == "HOLD_FOR_REFINE"
    assert state["phase"] == "HOLD_FOR_REFINE"
    assert state["current_parent"]["version"] == "h0"
    assert state["candidate"]["version"] == "search-v2"
    assert state["archive"] == []
    assert state["hold"]["reason"] == (
        "quantitative_protection_still_inconclusive"
    )
    assert state["cost"]["provider_cost_usd"] == "0.412"
    assert state["cost"]["completed_requests"] == 9
    assert state["cost"]["total_tokens"] == 523
    assert state["accounted_review_ids"] == ["review-r1"]


def test_main0b_clear_protection_failure_holds_component_for_refinement(
    tmp_path,
):
    state = _apply(
        _quant_state(),
        "target",
        _report(
            "target-run", "dupire-local-vol", (66, 68, 0), (68, 68, 1)
        ),
    )
    state = _apply(
        state,
        "repeat",
        _report(
            "target-repeat", "dupire-local-vol", (66, 68, 0), (68, 68, 1)
        ),
    )
    report = _report(
        "protection-main0b",
        "localvol-barrier",
        (35, 39, 0.9),
        (29, 39, 0.768857),
    )
    state = import_pilot_report(
        state,
        stage="protection",
        report=report,
        report_path="/protection-main0b/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
        property_set_safe=False,
        quantitative_protection_triage={
            "verdict": "FAIL",
            "outcome_severity": "MEANINGFUL_CANDIDATE_REGRESSION",
            "causal_attribution": "HARNESS_WORKER_INTERACTION",
        },
    )
    resumed = import_pilot_report(
        state,
        stage="protection",
        report=report,
        report_path="/protection-main0b/pilot-report.json",
        parent_arm="h0",
        candidate_arm="candidate",
        property_set_safe=False,
        quantitative_protection_triage={"verdict": "FAIL"},
    )

    assert resumed == state
    assert state["decision"] == "HOLD_FOR_REFINE"
    assert state["phase"] == "HOLD_FOR_REFINE"
    assert state["current_parent"]["version"] == "h0"
    assert state["candidate"]["version"] == "search-v2"
    assert state["archive"] == []
    assert state["hold"]["reason"] == "quantitative_protection_regression"

    state_path = tmp_path / "lineage.json"
    save_lineage(state_path, state)
    restored = load_lineage(state_path)
    assert restored["phase"] == "HOLD_FOR_REFINE"
    assert restored["status"] == "candidate_hold"
    assert restored["current_parent"] == state["current_parent"]
    assert restored["candidate"] == state["candidate"]
    assert restored["hold"] == state["hold"]


def _information_review_proposal_state(tmp_path):
    parent = _worker(tmp_path / "information-parent", ("run_shell_command",))
    candidate = _worker(
        tmp_path / "information-candidate",
        ("run_shell_command", "audit_public_output"),
    )
    state = new_proposal_lineage(
        lineage_id="information-review",
        parent_version="h0",
        parent_path=str(parent),
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
        candidate_information_set_review=True,
    )
    report = _proposal("ACT", True, str(candidate))
    report["summary"] = {
        "discovery_hypothesis": {
            "hypothesis": {
                "worker_visible_claims": [
                    {
                        "claim_id": "public-output-positive",
                        "claim": "Written output values must be positive.",
                        "surfaces": ["tools"],
                        "basis_refs": [
                            "public:instruction",
                            "diagnostic:target",
                        ],
                    }
                ]
            }
        }
    }
    return import_proposal_report(
        state,
        report=report,
        report_path="/proposal/proposal-report.json",
        proposal_run_id="proposal-information-r1",
        candidate_version="candidate-information-r1",
    )


def _information_review_package(state):
    return {
        "schema_version": 1,
        "review_id": "information-review-r1",
        "candidate_id": state["candidate"]["version"],
        "candidate": {
            "diff_ref": "candidate:diff",
            "diff": "+ enforce positive written output\n",
        },
        "worker_visible_claims": state["proposal"]["worker_visible_claims"],
        "public_sources": [
            {
                "ref": "public:instruction",
                "source_type": "public_contract",
                "excerpt": "Written output values must be positive.",
            }
        ],
        "optimize_only_sources": [
            {
                "ref": "diagnostic:target",
                "source_type": "optimize_only_diagnostic",
                "worker_visible": False,
                "excerpt": "The prior artifact failed a hidden property.",
            }
        ],
    }


def _information_review_payload(package, verdict):
    if verdict == "PASS":
        role = "PUBLIC_SUPPORT"
        ref = "public:instruction"
    elif verdict == "REJECT":
        role = "OPTIMIZE_ONLY_ORIGIN"
        ref = "diagnostic:target"
    else:
        role = "INSUFFICIENT_PUBLIC_SUPPORT"
        ref = "candidate:diff"
    return {
        "schema_version": 1,
        "review_id": package["review_id"],
        "candidate_id": package["candidate_id"],
        "claim_reviews": [
            {
                "claim_id": "public-output-positive",
                "verdict": verdict,
                "reason": f"fixture {verdict.lower()} boundary",
                "source_basis": [{"ref": ref, "role": role}],
            }
        ],
        "coverage_review": {
            "verdict": "PASS",
            "reason": "The supplied diff is fully covered by the claim.",
            "source_basis": [
                {"ref": "candidate:diff", "role": "CANDIDATE_EXPOSURE"}
            ],
            "undeclared_exposures": [],
        },
        "overall_verdict": verdict,
    }


def test_information_set_review_pass_enters_target_and_accounts_once(tmp_path):
    state = _information_review_proposal_state(tmp_path)
    package = _information_review_package(state)
    payload = _information_review_payload(package, "PASS")

    reviewed = import_candidate_information_set_review(
        state,
        review_id="information-review-r1",
        review_path="/reviews/information-review-r1/RESULT.json",
        review_package=package,
        review_payload=payload,
        review_accounting={
            "provider_cost_usd": "0.01",
            "completed_request_count": 1,
            "total_tokens": 50,
        },
        reviewed_candidate_dir=state["candidate"]["worker_dir"],
    )
    resumed = import_candidate_information_set_review(
        reviewed,
        review_id="information-review-r1",
        review_path="/reviews/information-review-r1/RESULT.json",
        review_package=package,
        review_payload=payload,
        review_accounting={
            "provider_cost_usd": "0.01",
            "completed_request_count": 1,
            "total_tokens": 50,
        },
        reviewed_candidate_dir=reviewed["candidate"]["worker_dir"],
    )

    assert state["phase"] == "INFORMATION_SET_REVIEW"
    assert reviewed["phase"] == "TARGET"
    assert reviewed["current_parent"]["version"] == "h0"
    assert reviewed["accounted_review_ids"] == ["information-review-r1"]
    assert reviewed["cost"] == {
        "provider_cost_usd": "0.03",
        "completed_requests": 5,
        "total_tokens": 250,
    }
    assert resumed == reviewed


@pytest.mark.parametrize("verdict", ["REJECT", "INCONCLUSIVE"])
def test_information_set_review_nonpass_holds_without_worker(tmp_path, verdict):
    state = _information_review_proposal_state(tmp_path)
    package = _information_review_package(state)

    reviewed = import_candidate_information_set_review(
        state,
        review_id="information-review-r1",
        review_path="/reviews/information-review-r1/RESULT.json",
        review_package=package,
        review_payload=_information_review_payload(package, verdict),
        review_accounting={
            "provider_cost_usd": "0.01",
            "completed_request_count": 1,
            "total_tokens": 50,
        },
        reviewed_candidate_dir=state["candidate"]["worker_dir"],
    )

    assert reviewed["phase"] == "HOLD_FOR_REFINE"
    assert reviewed["decision"] == "HOLD_FOR_REFINE"
    assert reviewed["current_parent"]["version"] == "h0"
    assert reviewed["observations"] == {
        "information_set_review": {
            "review_id": "information-review-r1",
            "review_path": "/reviews/information-review-r1/RESULT.json",
            "overall_verdict": verdict,
            "claim_reviews": _information_review_payload(package, verdict)[
                "claim_reviews"
            ],
            "coverage_review": _information_review_payload(package, verdict)[
                "coverage_review"
            ],
            "worker_visible": False,
            "promotion_authority": False,
            "reviewed_candidate_dir": state["candidate"]["worker_dir"],
        }
    }


def test_information_set_review_missing_claims_holds_admitted_act(tmp_path):
    state = new_proposal_lineage(
        lineage_id="information-review-missing-claims",
        parent_version="h0",
        parent_path=str(_worker(tmp_path / "missing-parent", ("shell",))),
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
        candidate_information_set_review=True,
    )
    report = _proposal(
        "ACT",
        True,
        str(_worker(tmp_path / "missing-candidate", ("shell", "audit"))),
    )

    result = import_proposal_report(
        state,
        report=report,
        report_path="/proposal/proposal-report.json",
        proposal_run_id="proposal-missing-claims-r1",
        candidate_version="candidate-missing-claims-r1",
    )

    assert result["phase"] == "HOLD_FOR_REFINE"
    assert result["hold"]["reason"] == (
        "information_set_review_missing_worker_visible_claims"
    )


def test_frozen_h0_same_worker_path_needs_no_candidate_review():
    state = new_lineage(
        lineage_id="frozen-h0",
        parent_version="h0",
        parent_path="/workers/h0",
        candidate_version="h0",
        candidate_path="/workers/h0",
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
    )

    imported = import_pilot_report(
        state,
        stage="target",
        report=_report(
            "frozen-h0-target", "target", (1, 2, 0), (1, 2, 0)
        ),
        report_path="/reports/frozen-h0-target.json",
        parent_arm="h0",
        candidate_arm="candidate",
    )

    assert state["phase"] == "TARGET"
    assert state["candidate_information_set_review"] is False
    assert imported["decision"] == "ROLLBACK"


def test_preconstructed_changed_candidate_requires_review_even_if_opted_out():
    state = new_lineage(
        lineage_id="preconstructed",
        parent_version="h0",
        parent_path="/workers/h0",
        candidate_version="candidate",
        candidate_path="/workers/candidate",
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
        candidate_information_set_review=False,
    )

    assert state["phase"] == "INFORMATION_SET_REVIEW"
    assert state["candidate_information_set_review"] is True

    in_place_identity_change = new_lineage(
        lineage_id="in-place-candidate",
        parent_version="h0",
        parent_path="/workers/h0",
        candidate_version="candidate-v1",
        candidate_path="/workers/h0",
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
        candidate_information_set_review=False,
    )
    assert in_place_identity_change["phase"] == "INFORMATION_SET_REVIEW"


def test_legacy_changed_candidate_result_import_cannot_bypass_review():
    state = new_lineage(
        lineage_id="legacy-bypass",
        parent_version="h0",
        parent_path="/workers/h0",
        candidate_version="candidate",
        candidate_path="/workers/candidate",
        target_task_id="target",
        protection_task_id="protect",
        worker_route="route-a",
        worker_budget="normal",
        cost_limit_usd="1",
    )
    # Reproduce the old persisted-state shape that directly entered TARGET.
    state["phase"] = "TARGET"
    state["candidate_information_set_review"] = False

    with pytest.raises(LineageError, match="without Review PASS"):
        import_pilot_report(
            state,
            stage="target",
            report=_report(
                "legacy-target", "target", (1, 2, 0), (2, 2, 1)
            ),
            report_path="/reports/legacy-target.json",
            parent_arm="h0",
            candidate_arm="candidate",
        )


def test_review_pass_must_bind_the_active_candidate_snapshot(tmp_path):
    state = _information_review_proposal_state(tmp_path)
    package = _information_review_package(state)

    with pytest.raises(LineageError, match="active reviewed_candidate snapshot"):
        import_candidate_information_set_review(
            state,
            review_id="information-review-r1",
            review_path="/reviews/information-review-r1/RESULT.json",
            review_package=package,
            review_payload=_information_review_payload(package, "PASS"),
            review_accounting={
                "provider_cost_usd": "0.01",
                "completed_request_count": 1,
                "total_tokens": 50,
            },
            reviewed_candidate_dir="/workers/post-review-mutated-candidate",
        )
