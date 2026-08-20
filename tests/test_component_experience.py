import json
from pathlib import Path

import pytest

from qea.component_experience import (
    ComponentExperienceError,
    build_breadth_evolver_view,
    build_coordinated_evolver_view,
    build_cross_benchmark_experience,
)


LEDGER = (
    Path(__file__).resolve().parents[1]
    / "data/quantcodeeval/COMPONENT_EVIDENCE_CANARY.json"
)


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")


def _qfbench_evidence(tmp_path: Path) -> Path:
    root = tmp_path / "qfbench"
    task_ids = ("swap-curve-bootstrap-ois", "zero-coupon-bootstrapping")
    _write(
        root / "debugger/task_index.json",
        {
            "tasks": [
                {
                    "task_id": task_id,
                    "fresh_execution_status": "complete",
                    "fresh_evidence_completeness": "full_structured_trace",
                }
                for task_id in task_ids
            ]
        },
    )
    for index, task_id in enumerate(task_ids):
        task = root / "tasks" / task_id
        _write(
            task / "public_evaluation.json",
            {
                "task_id": task_id,
                "official_reward": 0.0,
                "tests_passed": 17 if index == 0 else 1,
                "tests_failed": 2 if index == 0 else 5,
                "source_sha256": "not-carried-forward",
            },
        )
        _write(
            task / "process_summary.json",
            {"turns": 12, "tool_calls": 16, "dependency_lock_sha256": "old"},
        )
        _write(
            task / "artifact_manifest.json",
            {
                "artifacts": [
                    {
                        "path": "summary.json",
                        "representation": "full_text",
                        "sha256": "old",
                    }
                ]
            },
        )
        _write(
            task / "worker_trace.jsonl",
            '{"role":"assistant","content":"work"}\n',
        )
        _write(task / "worker_final.txt", "done\n")
        _write(task / "artifacts/summary.json", {"max_residual": 0.1})
        contract = root / "contracts" / task_id
        _write(contract / "instruction.md", "Bootstrap and reprice the curve.\n")
        _write(
            contract / "clauses.json",
            {
                "clause_count": 1,
                "clauses": [
                    {
                        "clause_id": f"{task_id}#c1",
                        "text": "Reprice supplied instruments consistently.",
                        "text_sha256": "old",
                    }
                ],
            },
        )
    return root


def _quantcodeeval_evidence(tmp_path: Path) -> Path:
    root = tmp_path / "quantcodeeval"
    task_id = "T26"
    _write(root / "current.json", {"evaluation_id": "eval-h0"})
    task = root / "tasks" / task_id
    _write(task / "instruction.md", "Implement strategy.py.\n")
    _write(task / "paper_text.md", "Public paper.\n")
    evaluation = task / "evaluations/eval-h0"
    _write(
        evaluation / "official_and_families.json",
        {
            "task_id": task_id,
            "official_reward": 0.0,
            "worker_digest": "old",
            "property_families": {
                "type_a": {"total": 7, "passed": 5, "failed": 2},
                "type_b": {"total": 10, "passed": 8, "failed": 2},
            },
        },
    )
    _write(
        evaluation / "artifact_manifest.json",
        {"artifacts": [{"path": "strategy.py", "sha256": "old"}]},
    )
    _write(
        evaluation / "process_facts.json",
        {"facts": {"turns": 9, "tool_calls": 7}},
    )
    _write(evaluation / "trace_facts.json", {"event_count": 14})
    return root


def test_builds_shared_qfbench_and_quantcodeeval_cards_without_new_hash_fields(
    tmp_path,
):
    result = build_cross_benchmark_experience(
        destination=tmp_path / "breadth",
        task_profiles=(
            {
                "benchmark": "qfbench",
                "task_id": "swap-curve-bootstrap-ois",
                "role": "target",
                "domain": "rates_fx_macro",
                "state_tags": ["public_semantic", "unit_state"],
            },
            {
                "benchmark": "quantcodeeval",
                "task_id": "T26",
                "role": "target",
                "domain": "cross_sectional_shrinkage",
                "state_tags": ["quantity_semantic", "portfolio_normalization"],
            },
        ),
        component_ledger_path=LEDGER,
        qfbench_evidence_root=_qfbench_evidence(tmp_path),
        quantcodeeval_evidence_root=_quantcodeeval_evidence(tmp_path),
        component_portability={
            "empty_response_recovery": "source_reusable_if_same_nexau_runtime"
        },
    )

    assert result["benchmarks"] == ["qfbench", "quantcodeeval"]
    assert result["task_count"] == 2
    catalog = json.loads((tmp_path / "breadth/tasks/CATALOG.json").read_text())
    by_key = {row["task_key"]: row for row in catalog["tasks"]}
    assert by_key["qfbench:swap-curve-bootstrap-ois"]["answer_free_outcome"][
        "tests_passed"
    ] == 17
    assert by_key["quantcodeeval:T26"]["answer_free_outcome"][
        "property_families"
    ]["type_a"]["passed"] == 5
    assert by_key["qfbench:swap-curve-bootstrap-ois"]["artifact_paths"] == [
        "summary.json"
    ]

    structured_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "breadth").rglob("*.json")
    )
    assert '"sha256"' not in structured_text
    assert "_sha256" not in structured_text
    assert "worker_digest" not in structured_text


def test_retrieval_uses_public_state_terms_and_keeps_portability(tmp_path):
    build_cross_benchmark_experience(
        destination=tmp_path / "breadth",
        task_profiles=(
            {
                "benchmark": "qfbench",
                "task_id": "swap-curve-bootstrap-ois",
                "role": "target",
                "state_tags": ["public_semantic", "quantity"],
            },
        ),
        component_ledger_path=LEDGER,
        qfbench_evidence_root=_qfbench_evidence(tmp_path),
        component_portability={
            "public_quantity_semantic_binding": "lesson_only",
        },
        relevant_component_limit=2,
    )

    relevant = json.loads(
        (tmp_path / "breadth/tasks/RELEVANT_COMPONENTS.json").read_text()
    )
    rows = relevant["tasks"][0]["components"]
    assert len(rows) <= 2
    semantic = next(
        row
        for row in rows
        if row["component_id"] == "public_quantity_semantic_binding"
    )
    assert semantic["portability"] == "lesson_only"
    assert set(semantic["matched_state_terms"]) >= {"public", "quantity", "semantic"}


def test_qfbench_retrieval_excludes_quantcodeeval_only_components(tmp_path):
    build_cross_benchmark_experience(
        destination=tmp_path / "breadth",
        task_profiles=(
            {
                "benchmark": "qfbench",
                "task_id": "swap-curve-bootstrap-ois",
                "role": "target",
                "state_tags": ["temporal_anchor"],
            },
        ),
        component_ledger_path=LEDGER,
        qfbench_evidence_root=_qfbench_evidence(tmp_path),
        component_portability={
            "warmup_boundary_arbitration": "quantcodeeval_only",
        },
    )

    relevant = json.loads(
        (tmp_path / "breadth/tasks/RELEVANT_COMPONENTS.json").read_text()
    )
    component_ids = {
        row["component_id"] for row in relevant["tasks"][0]["components"]
    }
    assert "warmup_boundary_arbitration" not in component_ids


def test_missing_benchmark_task_stops_before_materialization(tmp_path):
    with pytest.raises(ComponentExperienceError, match="has no task"):
        build_cross_benchmark_experience(
            destination=tmp_path / "breadth",
            task_profiles=(
                {
                    "benchmark": "qfbench",
                    "task_id": "missing-task",
                    "role": "target",
                    "state_tags": ["data_state"],
                },
            ),
            component_ledger_path=LEDGER,
            qfbench_evidence_root=_qfbench_evidence(tmp_path),
        )
    assert not (tmp_path / "breadth").exists()


def test_builds_matched_task_only_and_history_enabled_views(tmp_path):
    corpus = tmp_path / "breadth"
    build_cross_benchmark_experience(
        destination=corpus,
        task_profiles=(
            {
                "benchmark": "qfbench",
                "task_id": "swap-curve-bootstrap-ois",
                "role": "target",
                "state_tags": ["public_semantic", "quantity"],
            },
        ),
        component_ledger_path=LEDGER,
        qfbench_evidence_root=_qfbench_evidence(tmp_path),
    )

    task_only = build_breadth_evolver_view(
        corpus_root=corpus,
        destination=tmp_path / "task-only",
        task_key="qfbench:swap-curve-bootstrap-ois",
        include_component_history=False,
    )
    history = build_breadth_evolver_view(
        corpus_root=corpus,
        destination=tmp_path / "history",
        task_key="qfbench:swap-curve-bootstrap-ois",
        include_component_history=True,
    )

    assert task_only["retrieved_component_count"] == 0
    assert history["retrieved_component_count"] > 0
    assert not (tmp_path / "task-only/components").exists()
    assert (tmp_path / "history/components/CATALOG.json").is_file()
    for root, enabled in (
        (tmp_path / "task-only", False),
        (tmp_path / "history", True),
    ):
        contract = json.loads((root / "contract.json").read_text())
        catalog = json.loads((root / "tasks/CATALOG.json").read_text())
        assert contract["component_history_enabled"] is enabled
        assert (root / "access_log.jsonl").read_text() == ""
        assert catalog["task_count"] == 1
        assert catalog["tasks"][0]["task_key"] == (
            "qfbench:swap-curve-bootstrap-ois"
        )


def test_quantcodeeval_answer_rich_view_is_evolver_only(tmp_path):
    corpus = tmp_path / "breadth"
    build_cross_benchmark_experience(
        destination=corpus,
        task_profiles=(
            {
                "benchmark": "quantcodeeval",
                "task_id": "T26",
                "role": "target",
                "state_tags": ["formula_semantics", "temporal_state"],
            },
        ),
        component_ledger_path=LEDGER,
        quantcodeeval_evidence_root=_quantcodeeval_evidence(tmp_path),
    )
    diagnostic = tmp_path / "optimization-diagnostic.json"
    _write(
        diagnostic,
        {
            "schema_version": 1,
            "task_id": "T26",
            "feedback_mode": "answer_rich_evolver",
            "visibility": "evolver_only",
            "worker_visible": False,
            "rubric_items": [{"property_id": "B5", "expected_behavior": "HJ"}],
        },
    )

    result = build_breadth_evolver_view(
        corpus_root=corpus,
        destination=tmp_path / "answer-rich",
        task_key="quantcodeeval:T26",
        include_component_history=True,
        optimization_diagnostic_path=diagnostic,
    )

    projected = tmp_path / "answer-rich"
    contract = json.loads((projected / "contract.json").read_text())
    catalog = json.loads((projected / "tasks/CATALOG.json").read_text())
    diagnostic_path = (
        projected
        / "benchmarks/quantcodeeval/tasks/T26/optimization-diagnostic.json"
    )
    assert result["evolver_feedback_mode"] == "answer_rich_evolver"
    assert contract["decision_protocol"] == "quant_property_v2"
    assert contract["feedback_tier"] == "answer_rich_optimization_v1"
    assert contract["research_state_transition_required_for_act"] is True
    assert contract["failure_signature_required_for_act"] is True
    assert contract["optimization_answers_exposed_to_evolver"] is True
    assert contract["optimization_answers_exposed_to_worker"] is False
    assert "COMPOSE" in contract["evolver_instruction"]
    assert catalog["tasks"][0]["feedback_mode"] == "answer_rich_evolver"
    assert diagnostic_path.is_file()
    assert not list(corpus.rglob("optimization-diagnostic.json"))


def test_coordinated_view_requires_mechanism_match_and_one_probe(tmp_path):
    corpus = tmp_path / "breadth"
    build_cross_benchmark_experience(
        destination=corpus,
        task_profiles=(
            {
                "benchmark": "qfbench",
                "task_id": "zero-coupon-bootstrapping",
                "role": "target",
                "state_tags": ["curve_bootstrap", "repricing"],
            },
            {
                "benchmark": "qfbench",
                "task_id": "swap-curve-bootstrap-ois",
                "role": "protection",
                "state_tags": ["curve_bootstrap", "repricing"],
            },
        ),
        component_ledger_path=LEDGER,
        qfbench_evidence_root=_qfbench_evidence(tmp_path),
    )

    result = build_coordinated_evolver_view(
        corpus_root=corpus,
        destination=tmp_path / "coordinated",
        task_keys=(
            "qfbench:zero-coupon-bootstrapping",
            "qfbench:swap-curve-bootstrap-ois",
        ),
        include_component_history=True,
    )

    assert result["task_count"] == 2
    assert result["max_worker_probes_this_round"] == 1
    contract = json.loads(
        (tmp_path / "coordinated/contract.json").read_text()
    )
    assert contract["shared_mechanism_assessment_required"] is True
    assert contract["probe_task_selection_required_for_act"] is True
    assert contract["positive_target_before_contrast_evaluation"] is True
    assert contract["decision_protocol"] == "quant_property_v2"
    assert contract["autonomous_probe_required"] is True
    assert contract["coordinated_evidence_required_for_act"] is True
    assert contract["target_task_keys"] == [
        "qfbench:zero-coupon-bootstrapping"
    ]
    assert contract["protection_task_keys"] == [
        "qfbench:swap-curve-bootstrap-ois"
    ]
    assert contract["coordinator_selected_probe_evaluation_allowed"] is True
    assert "broad Research-State label alone" in contract["evolver_instruction"]
    assert "Do not request Worker evaluation on every task" in (
        contract["evolver_instruction"]
    )
    assert "from_scratch experiment_spec" in contract["evolver_instruction"]
    assert (tmp_path / "coordinated/components/CATALOG.json").is_file()


def test_coordinated_view_rejects_one_task(tmp_path):
    corpus = tmp_path / "breadth"
    build_cross_benchmark_experience(
        destination=corpus,
        task_profiles=(
            {
                "benchmark": "qfbench",
                "task_id": "swap-curve-bootstrap-ois",
                "role": "target",
                "state_tags": ["curve_bootstrap"],
            },
        ),
        component_ledger_path=LEDGER,
        qfbench_evidence_root=_qfbench_evidence(tmp_path),
    )
    with pytest.raises(ComponentExperienceError, match="two and four"):
        build_coordinated_evolver_view(
            corpus_root=corpus,
            destination=tmp_path / "coordinated",
            task_keys=("qfbench:swap-curve-bootstrap-ois",),
            include_component_history=False,
        )
