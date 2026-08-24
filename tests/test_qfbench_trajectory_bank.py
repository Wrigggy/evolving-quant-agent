from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from qea.qfbench_trajectory_bank import (
    QFBenchTrajectoryBankError,
    append_accepted_panel_history,
    build_trajectory_bank,
    carry_accepted_panel_history,
)
from qea.evolution_evidence import authorize_evidence_tree
from scripts.build_qfbench_trajectory_bank import main


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _layout(tmp_path: Path) -> dict[str, Path]:
    manifest = tmp_path / "manifest.json"
    plan = tmp_path / "plan.json"
    contracts = tmp_path / "contracts"
    rows = [
        ("alpha-task", "alpha"),
        ("beta-task", "beta"),
        ("sealed-task", "alpha"),
    ]
    _write(
        manifest,
        {
            "schema_version": 1,
            "commit": "not copied into bank",
            "baseline": {
                "primary": [
                    {
                        "task_id": task_id,
                        "domain": family,
                        "lineage": task_id.replace("-", "_"),
                        "difficulty": "medium",
                        "reward_kind": "binary",
                        "resource_source": "upstream",
                    }
                    for task_id, family in rows
                ]
            },
        },
    )
    _write(
        plan,
        {
            "schema_version": 1,
            "sealed_main_tasks": [{"task_id": "sealed-task"}],
            "development_panels": [
                {"panel_index": 1, "family": "alpha", "task_ids": ["alpha-task"]},
                {"panel_index": 2, "family": "beta", "task_ids": ["beta-task"]},
            ],
            "cross_family_workflow_evidence": {
                "anchor_task_by_family": {
                    "alpha": "alpha-task",
                    "beta": "beta-task",
                }
            },
        },
    )
    for task_id, _family in rows:
        _write(contracts / task_id / "instruction.md", f"Public {task_id}\n")
        _write(
            contracts / task_id / "clauses.json",
            {
                "task_id": task_id,
                "clauses": [{"text": "Use public inputs."}],
                "source_sha256": "must not enter generated JSON",
            },
        )
    return {"manifest": manifest, "plan": plan, "contracts": contracts}


def _attempt(
    run: Path,
    name: str,
    task_id: str,
    *,
    outcome: str,
    artifacts: dict[str, str] | None = None,
    include_trace: bool = True,
    secret: str = "official-secret",
) -> Path:
    attempt = run / "attempts" / name
    _write(
        attempt / "attempt.json",
        {
            "attempt_id": name,
            "task_id": task_id,
            "worker_digest": "must not be copied",
        },
    )
    _write(
        attempt / "worker-execution.json",
        {
            "attempt_id": name,
            "trace_uri": "raw-trace.jsonl",
            "final_text_uri": "final.txt",
            "summary": {
                "outcome": outcome,
                "turns": 3,
                "tool_calls": 2,
                "tool_errors": 1,
                "dependency_lock_sha256": "must not be copied",
            },
        },
    )
    if include_trace:
        _write(attempt / "raw-trace.jsonl", '{"event":"blind H0 work"}\n')
        _write(attempt / "final.txt", "Blind H0 final.\n")
    for relative, text in (artifacts or {}).items():
        _write(attempt / "artifacts" / relative, text)
    _write(
        attempt / "completed-score.json",
        {"task_id": task_id, "reward": 0.0, "tests_failed": 2, "secret": secret},
    )
    _write(
        attempt / "verifier" / "official-score.json",
        {"task_id": task_id, "reward": 0.0, "tests_passed": 1, "secret": secret},
    )
    _write(attempt / "verifier" / "ctrf.json", {"expected": secret})
    return attempt


def _build(source: dict[str, Path], run: Path, destination: Path, **kwargs):
    return build_trajectory_bank(
        manifest_path=source["manifest"],
        scheduler_plan_path=source["plan"],
        public_contracts_root=source["contracts"],
        h0_run_dirs=[run],
        destination=destination,
        **kwargs,
    )


def _all_generated_text(destination: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(destination.rglob("*.json"))
    )


def _assert_no_identity_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            assert "sha" not in key.casefold()
            assert "digest" not in key.casefold()
            assert "hash" not in key.casefold()
            _assert_no_identity_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_identity_keys(child)


def test_separates_controller_scores_from_answer_free_panel_views(tmp_path):
    source = _layout(tmp_path)
    run = tmp_path / "h0-run"
    _attempt(
        run,
        "alpha-attempt",
        "alpha-task",
        outcome="completed",
        artifacts={"answer.csv": "x\n1\n"},
        secret="alpha-official-secret",
    )
    _attempt(
        run,
        "beta-attempt",
        "beta-task",
        outcome="model_empty_response",
        include_trace=False,
        secret="beta-official-secret",
    )
    _attempt(
        run,
        "sealed-attempt",
        "sealed-task",
        outcome="completed",
        artifacts={"sealed.json": "{}\n"},
        secret="sealed-official-secret",
    )
    destination = tmp_path / "bank"

    report = _build(source, run, destination)

    assert report["complete"] is False
    assert report["excluded_sealed_history_count"] == 1
    controller = json.loads(
        (destination / "controller-only/tasks/alpha-task.json").read_text()
    )
    controller_text = json.dumps(controller)
    assert "alpha-official-secret" in controller_text
    assert "official-score.json" in controller_text

    evolver_root = destination / "evolver-answer-free"
    evolver_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(evolver_root.rglob("*.json"))
    )
    assert "official-secret" not in evolver_text
    assert "official-score.json" not in evolver_text
    assert "completed-score.json" not in evolver_text
    assert "ctrf.json" not in evolver_text
    assert "tests_failed" not in evolver_text
    assert "sealed-task" not in _all_generated_text(destination)

    beta = json.loads(
        (evolver_root / "tasks/beta-task.json").read_text(encoding="utf-8")
    )
    history = beta["histories"][0]
    assert history["runtime_status"] == "invalid"
    assert history["artifact_state"] == "empty"
    assert history["artifacts"] == []
    assert set(history["missing_surfaces"]) == {"worker_trace", "worker_final"}

    first_panel = json.loads(
        (evolver_root / "panels/panel-01-alpha.json").read_text()
    )
    assert first_panel["focus_task_ids"] == ["alpha-task"]
    assert first_panel["cross_family_anchors"] == [
        {"family": "beta", "task_id": "beta-task"}
    ]
    assert first_panel["visible_task_ids"] == ["alpha-task", "beta-task"]
    assert first_panel["visible_family_count"] == 2


def test_resume_completes_partial_bank_and_stable_rebuild_is_idempotent(tmp_path):
    source = _layout(tmp_path)
    run = tmp_path / "h0-run"
    _attempt(run, "alpha-attempt", "alpha-task", outcome="completed")
    destination = tmp_path / "bank"

    first = _build(source, run, destination)
    assert first["complete"] is False
    assert first["task_count_with_history"] == 1

    _attempt(run, "beta-attempt", "beta-task", outcome="completed")
    second = _build(source, run, destination)
    before = {
        path.relative_to(destination).as_posix(): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    }
    third = _build(source, run, destination)
    after = {
        path.relative_to(destination).as_posix(): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    }

    assert second["complete"] is True
    assert second["task_count_with_history"] == 2
    assert third["complete"] is True
    assert third["files_written"] == 0
    assert third["files_unchanged"] == len(before)
    assert before == after

    manifest = json.loads((destination / "BANK-MANIFEST.json").read_text())
    assert manifest["complete"] is True
    index = json.loads(
        (destination / "evolver-answer-free/bank-index.json").read_text()
    )
    for panel in index["panels"]:
        evidence = destination / panel["evidence_root"]
        record = authorize_evidence_tree(evidence)
        assert "contract.json" in record.members
        assert (evidence / "access_log.jsonl").read_bytes() == b""
        contract = json.loads((evidence / "contract.json").read_text())
        assert contract["answer_free"] is True
        assert contract["decision_protocol"] == "quant_property_v2"
        assert contract["feedback_tier"] == (
            "answer_free_global_h0_trajectory_bank_v1"
        )
        assert contract["workflow_scope_required_for_act"] is True
        assert len(contract["task_family_by_key"]) == 2
        assert any(member.endswith("worker_trace.jsonl") for member in record.members)


def test_generated_json_has_no_content_identity_fields(tmp_path):
    source = _layout(tmp_path)
    run = tmp_path / "h0-run"
    _attempt(run, "alpha-attempt", "alpha-task", outcome="completed")
    _attempt(run, "beta-attempt", "beta-task", outcome="completed")
    destination = tmp_path / "bank"

    _build(source, run, destination)

    for path in destination.rglob("*.json"):
        _assert_no_identity_keys(json.loads(path.read_text(encoding="utf-8")))
    text = _all_generated_text(destination)
    assert "worker_digest" not in text
    assert "source_sha256" not in text
    assert "benchmark_commit" not in text


def test_promoted_panel_carries_only_answer_free_candidate_history_forward(tmp_path):
    source = _layout(tmp_path)
    h0_run = tmp_path / "h0-run"
    _attempt(h0_run, "alpha-h0", "alpha-task", outcome="completed")
    _attempt(h0_run, "beta-h0", "beta-task", outcome="completed")
    destination = tmp_path / "bank"
    _build(source, h0_run, destination, require_complete=True)
    panel_one = destination / "evolver-answer-free/panel-evidence/panel-01-alpha"
    panel_two = destination / "evolver-answer-free/panel-evidence/panel-02-beta"

    matched_runs = []
    for repetition in (1, 2):
        run = tmp_path / f"matched-{repetition}"
        _write(
            run / "pilot-plan.json",
            {
                "run_id": f"matched-{repetition}",
                "task_ids": ["alpha-task"],
                "checkpoint_prefix": f"matched-{repetition}",
                "arms": [
                    {"label": "parent", "worker_dir": "/parent"},
                    {"label": "candidate", "worker_dir": "/candidate"},
                ],
            },
        )
        _write(
            run / "pilot-report.json",
            {
                "run_id": f"matched-{repetition}",
                "status": "complete",
                "task_ids": ["alpha-task"],
                "official-score": "controller-only-secret",
            },
        )
        candidate = _attempt(
            run,
            f"candidate-{repetition}",
            "alpha-task",
            outcome="completed",
            artifacts={"public.csv": f"rep,{repetition}\n"},
            secret=f"matched-secret-{repetition}",
        )
        attempt = json.loads((candidate / "attempt.json").read_text())
        attempt["checkpoint"] = f"matched-{repetition}-candidate"
        _write(candidate / "attempt.json", attempt)
        parent = _attempt(
            run,
            f"parent-{repetition}",
            "alpha-task",
            outcome="completed",
            secret=f"parent-secret-{repetition}",
        )
        parent_record = json.loads((parent / "attempt.json").read_text())
        parent_record["checkpoint"] = f"matched-{repetition}-parent"
        _write(parent / "attempt.json", parent_record)
        matched_runs.append(run)

    result = append_accepted_panel_history(
        source_evidence_root=panel_one,
        next_evidence_root=panel_two,
        panel_index=1,
        family="alpha",
        task_ids=["alpha-task"],
        accepted_claims=[
            {
                "claim_id": "public-handoff",
                "claim": "Keep the public workflow handoff explicit.",
                "surfaces": ["systemprompt"],
                "basis_refs": ["public:alpha-full-contract"],
            }
        ],
        matched_run_dirs=matched_runs,
    )

    assert result["status"] == "complete"
    assert result["accepted_claim_count"] == 1
    index = json.loads(
        (panel_two / "accepted-panels/INDEX.json").read_text(encoding="utf-8")
    )
    assert [value["panel_index"] for value in index["entries"]] == [1]
    record = json.loads(
        (
            panel_two
            / "accepted-panels/panel-01-alpha/ACCEPTED-PANEL.json"
        ).read_text(encoding="utf-8")
    )
    assert record["accepted_claims"][0]["claim_id"] == "public-handoff"
    assert len(record["repetitions"]) == 2
    authorized = authorize_evidence_tree(panel_two)
    assert any(
        member.endswith("repetition-02/tasks/alpha-task/worker_trace.jsonl")
        for member in authorized.members
    )
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in panel_two.rglob("*")
        if path.is_file()
    )
    assert "matched-secret" not in text
    assert "parent-secret" not in text
    assert "controller-only-secret" not in text
    assert "official-score" not in text
    assert "tests_failed" not in text

    before = {
        path.relative_to(panel_two).as_posix(): path.read_bytes()
        for path in panel_two.rglob("*")
        if path.is_file()
    }
    append_accepted_panel_history(
        source_evidence_root=panel_one,
        next_evidence_root=panel_two,
        panel_index=1,
        family="alpha",
        task_ids=["alpha-task"],
        accepted_claims=record["accepted_claims"],
        matched_run_dirs=matched_runs,
    )
    after = {
        path.relative_to(panel_two).as_posix(): path.read_bytes()
        for path in panel_two.rglob("*")
        if path.is_file()
    }
    assert before == after

    panel_three = destination / "evolver-answer-free/panel-evidence/panel-03-next"
    shutil.copytree(panel_one, panel_three)
    carried = carry_accepted_panel_history(
        source_evidence_root=panel_two,
        next_evidence_root=panel_three,
    )
    assert carried["status"] == "complete"
    assert carried["carried_entry_count"] == 1
    carried_index = json.loads(
        (panel_three / "accepted-panels/INDEX.json").read_text(encoding="utf-8")
    )
    assert [value["panel_index"] for value in carried_index["entries"]] == [1]
    assert authorize_evidence_tree(panel_three).members


def test_require_complete_fails_after_writing_inspectable_partial_index(tmp_path):
    source = _layout(tmp_path)
    run = tmp_path / "h0-run"
    _attempt(run, "alpha-attempt", "alpha-task", outcome="completed")
    destination = tmp_path / "bank"

    with pytest.raises(QFBenchTrajectoryBankError, match="bank is incomplete"):
        _build(source, run, destination, require_complete=True)

    index = json.loads(
        (destination / "controller-only/bank-index.json").read_text()
    )
    assert index["complete"] is False
    assert index["missing_task_ids"] == ["beta-task"]


def test_cli_accepts_repeated_runs_and_prints_report(tmp_path, capsys):
    source = _layout(tmp_path)
    run = tmp_path / "h0-run"
    _attempt(run, "alpha-attempt", "alpha-task", outcome="completed")
    _attempt(run, "beta-attempt", "beta-task", outcome="completed")
    destination = tmp_path / "bank"

    code = main(
        [
            "--manifest",
            str(source["manifest"]),
            "--scheduler-plan",
            str(source["plan"]),
            "--public-contracts-root",
            str(source["contracts"]),
            "--h0-run",
            str(run),
            "--destination",
            str(destination),
            "--require-complete",
        ]
    )

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["complete"] is True
    assert report["history_count"] == 2
