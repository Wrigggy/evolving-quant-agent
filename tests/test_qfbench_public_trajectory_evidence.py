import json
from pathlib import Path

from scripts.build_qfbench_public_trajectory_evidence import build


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> dict[str, Path]:
    contracts = tmp_path / "contracts"
    for task_id in ("holdings-target", "attribution-protection"):
        _write(contracts / task_id / "instruction.md", f"Public {task_id}\n")
        _write(
            contracts / task_id / "clauses.json",
            {
                "task_id": task_id,
                "clauses": [{"clause_id": "public-1", "text": "reconcile state"}],
                "source_sha256": "not retained",
            },
        )
    run = tmp_path / "fresh-h0-run"
    attempt = run / "attempts" / "fresh-attempt"
    _write(attempt / "attempt.json", {"task_id": "holdings-target"})
    _write(
        attempt / "worker-execution.json",
        {
            "trace_uri": "raw-trace.jsonl",
            "final_text_uri": "final.txt",
            "summary": {
                "outcome": "completed",
                "turns": 7,
                "tool_calls": 9,
                "dependency_lock_sha256": "not retained",
            },
        },
    )
    _write(attempt / "raw-trace.jsonl", '{"event":"read public data"}\n')
    _write(attempt / "final.txt", "Delivered public artifacts.\n")
    _write(attempt / "artifacts" / "summary.json", {"turnover": 0.2})
    _write(attempt / "artifacts" / "effective.csv", "issuer,weight\nA,1.0\n")
    _write(attempt / "completed-score.json", {"reward": 0.0, "tests_failed": 1})
    _write(attempt / "public_evaluation.json", {"failed_property": "secret"})
    _write(attempt / "optimization-diagnostic.json", {"expected": "secret"})
    _write(attempt / "verifier" / "ctrf.json", {"expected": "secret"})
    worker = tmp_path / "quant-h0"
    _write(worker / "agent.yaml", "name: qea_quant_h0_worker\n")
    _write(worker / "systemprompt.md", "Public-task research shell.\n")
    return {
        "contracts": contracts,
        "run": run,
        "attempt": attempt,
        "worker": worker,
    }


def test_builds_answer_free_qrs_view_from_public_contracts_and_fresh_h0(tmp_path):
    source = _fixture(tmp_path)
    destination = tmp_path / "public-view"

    report = build(
        public_contracts_root=source["contracts"],
        h0_run=source["run"],
        h0_attempt=source["attempt"],
        quant_h0_worker=source["worker"],
        target_task_id="holdings-target",
        protection_task_ids=["attribution-protection"],
        destination=destination,
    )

    assert report["answer_free"] is True
    contract = json.loads((destination / "contract.json").read_text())
    assert contract["contract_arm"] == "quant-state"
    assert contract["answer_free"] is True
    assert contract["worker_visible_claim_provenance_required_for_act"] is True
    assert contract["quant_research_state_card_required_for_act"] is True
    assert contract["candidate_history_exposed"] is False
    catalog = json.loads(
        (destination / "components/CATALOG.json").read_text()
    )
    assert catalog == {
        "catalog_policy": "no_candidate_history",
        "component_count": 0,
        "components": [],
        "schema_version": 1,
    }
    target = destination / "benchmarks/qfbench/tasks/holdings-target"
    assert (target / "worker_trace.jsonl").is_file()
    assert (target / "worker_final.txt").is_file()
    assert (target / "artifacts/summary.json").is_file()
    assert (target / "artifacts/effective.csv").is_file()
    process = json.loads((target / "process_summary.json").read_text())
    assert process == {"outcome": "completed", "tool_calls": 9, "turns": 7}
    protection = (
        destination
        / "benchmarks/qfbench/tasks/attribution-protection"
    )
    assert (protection / "instruction.md").is_file()
    assert (protection / "public_clauses.json").is_file()
    assert not (protection / "worker_trace.jsonl").exists()
    assert not (destination / "history").exists()


def test_does_not_copy_forbidden_attempt_members(tmp_path):
    source = _fixture(tmp_path)
    destination = tmp_path / "public-view"

    build(
        public_contracts_root=source["contracts"],
        h0_run=source["run"],
        h0_attempt=source["attempt"],
        quant_h0_worker=source["worker"],
        target_task_id="holdings-target",
        protection_task_ids=["attribution-protection"],
        destination=destination,
    )

    members = {path.relative_to(destination).as_posix() for path in destination.rglob("*")}
    forbidden_tokens = {
        "completed-score.json",
        "public_evaluation.json",
        "optimization-diagnostic.json",
        "ctrf.json",
    }
    assert forbidden_tokens.isdisjoint({Path(member).name for member in members})
    assert all("verifier" not in member.casefold() for member in members)
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in destination.rglob("*")
        if path.is_file()
    )
    assert "failed_property" not in text
    assert '"expected"' not in text
    assert "not retained" not in text


def test_includes_trusted_six_stage_index_for_quant_h0_s6(tmp_path):
    source = _fixture(tmp_path)
    destination = tmp_path / "public-view"
    skill = source["worker"] / "skills/quant-research-six-stage-workflow"
    _write(skill / "SKILL.md", "registered six-stage workflow\n")
    stage_record = {
        "schema_version": 1,
        "record_kind": "research_state_marker_index",
        "marker_presence_is_not_stage_correctness": True,
        "coverage": {
            "accounted_stages": ["S1", "S2", "S3", "S4", "S5", "S6"],
            "missing_stages": [],
            "marker_protocol_complete": True,
        },
    }
    _write(source["attempt"] / "research-state-trace.json", stage_record)

    report = build(
        public_contracts_root=source["contracts"],
        h0_run=source["run"],
        h0_attempt=source["attempt"],
        quant_h0_worker=source["worker"],
        target_task_id="holdings-target",
        protection_task_ids=["attribution-protection"],
        destination=destination,
    )

    copied = (
        destination
        / "benchmarks/qfbench/tasks/holdings-target/research_state_trace.json"
    )
    card = json.loads(
        (
            destination / "tasks/cards/qfbench--holdings-target.json"
        ).read_text(encoding="utf-8")
    )
    contract = json.loads(
        (destination / "contract.json").read_text(encoding="utf-8")
    )

    assert json.loads(copied.read_text(encoding="utf-8")) == stage_record
    assert card["evidence_paths"]["research_state_trace"].endswith(
        "research_state_trace.json"
    )
    assert contract["candidate_parent"] == "Quant-H0-S6"
    assert report["parent"] == "Quant-H0-S6"
    assert report["research_state_trace_included"] is True
