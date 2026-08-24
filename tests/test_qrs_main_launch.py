from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from qea.frozen_base_harness import build_selected_runtime, freeze_base_harness
from qea.qrs_main_launch import QRSMainLaunchError, build_qrs_main_launch


ROOT = Path(__file__).resolve().parents[1]
METHOD = (
    ROOT
    / "data/breadth/QF_GLOBAL_S6_PRIMITIVE_H0_TRAJECTORY_SCHEDULER_PLAN.json"
)
MINI_METHOD = ROOT / "data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_PLAN.json"
MINI_R2_METHOD = (
    ROOT / "data/breadth/QF_QRS_MINI_SCHEDULER_CANARY_R2_PLAN.json"
)
PRIMITIVE = ROOT / "qea/worker_quant_h0_s6_primitive_v1"


def _method() -> dict[str, object]:
    return json.loads(METHOD.read_text(encoding="utf-8"))


def _contracts(tmp_path: Path) -> Path:
    root = tmp_path / "public-contracts"
    task_ids = {
        task_id
        for panel in _method()["development_panels"]
        for task_id in panel["task_ids"]
    }
    for task_id in task_ids:
        task = root / task_id
        task.mkdir(parents=True)
        (task / "instruction.md").write_text(
            f"Public task contract for {task_id}.\n", encoding="utf-8"
        )
        (task / "clauses.json").write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "clauses": ["Use the required public input and output contract."],
                }
            )
            + "\n",
            encoding="utf-8",
        )
    return root


def _handoff(tmp_path: Path, rootless_config: Path) -> Path:
    worker = tmp_path / "source-worker"
    shutil.copytree(PRIMITIVE, worker)
    artifacts = tmp_path / "external-selection"
    artifacts.mkdir()
    agent = __import__("yaml").safe_load(
        (worker / "agent.yaml").read_text(encoding="utf-8")
    )
    runtime = build_selected_runtime(
        agent,
        worker_model_route="test-worker-route",
        rootless_config=str(rootless_config.resolve()),
    )
    output = tmp_path / "frozen-h0-handoff.json"
    freeze_base_harness(
        worker_dir=worker,
        run_root=tmp_path / "adapter-run",
        selected_profile_id="primitive-frozen-v1",
        selected_runtime=runtime,
        selection_artifact_root=artifacts,
        handoff_path=output,
    )
    return output


def _build(tmp_path: Path) -> dict[str, object]:
    rootless = tmp_path / "runtime/rootless.json"
    rootless.parent.mkdir(parents=True)
    rootless.write_text("{}\n", encoding="utf-8")
    handoff = _handoff(tmp_path, rootless)
    contracts = _contracts(tmp_path)
    public_manifest = tmp_path / "deploy/public-manifest.json"
    return build_qrs_main_launch(
        method_plan_path=METHOD,
        frozen_h0_handoff_path=handoff,
        scheduler_run_id="qrs-main-test-r1",
        runtime={
            "python": tmp_path / "runtime/python",
            "source_root": tmp_path / "deploy",
            "qfbench_root": tmp_path / "qfbench",
            "qfbench_manifest": public_manifest,
            "rootless_config": rootless,
            "image_set_manifest": tmp_path / "runtime/images.json",
            "results_dir": tmp_path / "runs",
            "worker_route": "test-worker-route",
        },
        qfbench_public_manifest=public_manifest,
        trajectory_bank_output=tmp_path / "runs/qrs-main-test-r1/trajectory-bank",
        public_contracts_root=contracts,
        reviewer_config={
            "backend": "openrouter",
            "model": "reviewer/test-model",
            "token_file": str(tmp_path / "runtime/model-token"),
            "reasoning_effort": "high",
        },
        output_root=tmp_path / "launch",
    )


def _walk_keys(value: object) -> list[str]:
    if isinstance(value, dict):
        return [
            *(str(key) for key in value),
            *(
                nested
                for child in value.values()
                for nested in _walk_keys(child)
            ),
        ]
    if isinstance(value, list):
        return [nested for child in value for nested in _walk_keys(child)]
    return []


def test_materializes_exact_six_fixed_panel_plans_and_scheduler_launch(
    tmp_path: Path,
) -> None:
    launch = _build(tmp_path)

    assert launch["panel_count"] == 6
    assert set(launch["panel_controller_plans"]) == {
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
    }
    assert Path(launch["launch_plan_path"]).is_file()
    persisted = json.loads(Path(launch["launch_plan_path"]).read_text())
    assert "launch_plan_path" not in persisted
    assert "method_plan" not in persisted
    assert persisted["method_plan_path"] == str(METHOD.resolve())
    assert persisted["trajectory_bank_manifest"].endswith(
        "trajectory-bank/BANK-MANIFEST.json"
    )
    assert persisted["qfbench_public_manifest"] == persisted["runtime"][
        "qfbench_manifest"
    ]
    for required in (
        "scheduler_run_id",
        "frozen_h0_handoff",
        "runtime",
        "scheduler_state_root",
        "qfbench_public_manifest",
        "trajectory_bank_output",
        "trajectory_bank_manifest",
        "public_contracts_root",
        "panel_controller_plans",
    ):
        assert required in persisted
    assert launch["builder_dispatched_children"] is False


@pytest.mark.parametrize("mini_method", [MINI_METHOD, MINI_R2_METHOD])
def test_launch_builder_also_materializes_bounded_three_panel_mini_canary(
    tmp_path: Path, mini_method: Path
) -> None:
    rootless = tmp_path / "runtime/rootless.json"
    rootless.parent.mkdir(parents=True)
    rootless.write_text("{}\n", encoding="utf-8")
    handoff = _handoff(tmp_path, rootless)
    mini = json.loads(mini_method.read_text(encoding="utf-8"))
    contracts = tmp_path / "mini-contracts"
    for panel in mini["development_panels"]:
        for task_id in panel["task_ids"]:
            task = contracts / task_id
            task.mkdir(parents=True)
            (task / "instruction.md").write_text(
                f"Public contract for {task_id}.\n", encoding="utf-8"
            )
            (task / "clauses.json").write_text(
                json.dumps({"task_id": task_id, "clauses": ["public"]}) + "\n",
                encoding="utf-8",
            )
    public_manifest = tmp_path / "deploy/public-manifest.json"
    launch = build_qrs_main_launch(
        method_plan_path=mini_method,
        frozen_h0_handoff_path=handoff,
        scheduler_run_id="qrs-mini-test-r1",
        runtime={
            "python": tmp_path / "runtime/python",
            "source_root": tmp_path / "deploy",
            "qfbench_root": tmp_path / "qfbench",
            "qfbench_manifest": public_manifest,
            "rootless_config": rootless,
            "image_set_manifest": tmp_path / "runtime/images.json",
            "results_dir": tmp_path / "runs",
            "worker_route": "test-worker-route",
        },
        qfbench_public_manifest=public_manifest,
        trajectory_bank_output=tmp_path / "runs/qrs-mini-test-r1/trajectory-bank",
        public_contracts_root=contracts,
        reviewer_config={
            "backend": "openrouter",
            "model": "reviewer/test-model",
            "token_file": str(tmp_path / "runtime/model-token"),
        },
        output_root=tmp_path / "mini-launch",
    )

    assert launch["panel_count"] == 3
    assert set(launch["panel_controller_plans"]) == {"1", "2", "3"}


def test_parent_chain_uses_frozen_h0_then_prior_reviewed_snapshots(
    tmp_path: Path,
) -> None:
    launch = _build(tmp_path)
    method = _method()
    plans = [
        json.loads(Path(launch["panel_controller_plans"][str(index)]).read_text())
        for index in range(1, 7)
    ]
    handoff = json.loads(Path(launch["frozen_h0_handoff"]).read_text())

    first_parent = plans[0]["lineages"][0]["parent"]
    assert first_parent == {
        "version": "primitive-frozen-v1",
        "worker_dir": handoff["selected_worker_root"],
    }
    assert all(
        plan["parent_binding"]["mode"]
        == "scheduler_current_incumbent_at_dispatch"
        for plan in plans
    )
    for index in range(1, 6):
        previous_lineage = plans[index - 1]["lineages"][0]
        previous_review = previous_lineage["candidate_information_set_review"]
        expected_path = (
            Path(launch["scheduler_state_root"])
            / f"panel-{index}-controller"
            / "reviewed-candidates"
            / previous_lineage["lineage_id"]
            / previous_review["review_id"]
        ).resolve()
        parent = plans[index]["lineages"][0]["parent"]
        assert parent["version"] == method["development_panels"][index - 1][
            "proposal"
        ]
        assert parent["worker_dir"] == str(expected_path)


def test_every_proposal_is_workflow_global_answer_free_and_review_mandatory(
    tmp_path: Path,
) -> None:
    launch = _build(tmp_path)
    frozen_worker = json.loads(Path(launch["frozen_h0_handoff"]).read_text())[
        "selected_worker_root"
    ]
    for index in range(1, 7):
        plan = json.loads(
            Path(launch["panel_controller_plans"][str(index)]).read_text()
        )
        lineage = plan["lineages"][0]
        proposal = lineage["proposal"]
        review = lineage["candidate_information_set_review"]

        assert proposal["workflow_scope"] == "workflow_global"
        assert proposal["evidence"].endswith(
            f"panel-evidence/panel-{index:02d}-{lineage['family']}"
        )
        assert Path(plan["states_root"]) == (
            Path(launch["scheduler_state_root"])
            / f"panel-{index}-controller"
        )
        assert review["enabled"] is True
        assert review["feedback_mode"] == "answer_free"
        assert review["arm_blind"] is True
        assert review["optimize_only_sources"] == []
        assert review["candidate_material_baseline_worker_dir"] == frozen_worker
        assert len(review["public_sources"]) >= 12
        assert plan["dispatch_boundary"]["required_stop_after_stage"] == (
            "information_set_review"
        )


def test_review_contracts_are_cumulative_without_future_or_sealed_tasks(
    tmp_path: Path,
) -> None:
    launch = _build(tmp_path)
    method = _method()
    anchors = set(
        method["cross_family_workflow_evidence"]["anchor_task_by_family"].values()
    )
    sealed = {row["task_id"] for row in method["sealed_main_tasks"]}
    cumulative: set[str] = set()

    for index, panel in enumerate(method["development_panels"], start=1):
        cumulative.update(panel["task_ids"])
        expected = cumulative | anchors
        future = {
            task_id
            for future_panel in method["development_panels"][index:]
            for task_id in future_panel["task_ids"]
        } - anchors
        controller = json.loads(
            Path(launch["panel_controller_plans"][str(index)]).read_text()
        )
        review = controller["lineages"][0][
            "candidate_information_set_review"
        ]
        refs = {source["ref"] for source in review["public_sources"]}
        observed = {
            ref.split(":", 2)[1]
            for ref in refs
            if ref.startswith("public:")
        }

        assert observed == expected
        assert future.isdisjoint(observed)
        assert sealed.isdisjoint(observed)
        assert len(refs) == 2 * len(expected)
        assert review["feedback_mode"] == "answer_free"
        assert review["optimize_only_sources"] == []
        assert not any(
            forbidden in key.casefold()
            for key in _walk_keys(review)
            for forbidden in ("score", "reward", "expected", "verifier")
        )


def test_builder_never_dispatches_target_or_embeds_result_fields(
    tmp_path: Path,
) -> None:
    launch = _build(tmp_path)

    assert not (tmp_path / "runs").exists()
    for path in launch["panel_controller_plans"].values():
        plan = json.loads(Path(path).read_text())
        assert plan["dispatch_boundary"]["worker_calls"] == 0
        assert plan["dispatch_boundary"]["builder_dispatched_children"] is False
        stages = plan["lineages"][0]["stages"]
        assert {stage["name"] for stage in stages} == {"target", "protection"}
        assert all(stage["conditional_not_authorized"] is True for stage in stages)
        forbidden_keys = {
            key
            for key in _walk_keys(plan)
            if "official" in key.casefold() or "verifier" in key.casefold()
        }
        assert forbidden_keys == set()


def test_builder_is_idempotent_but_refuses_changed_fixed_output(
    tmp_path: Path,
) -> None:
    launch = _build(tmp_path)
    rootless = tmp_path / "runtime/rootless.json"
    contracts = tmp_path / "public-contracts"
    handoff = tmp_path / "frozen-h0-handoff.json"
    kwargs = {
        "method_plan_path": METHOD,
        "frozen_h0_handoff_path": handoff,
        "scheduler_run_id": "qrs-main-test-r1",
        "runtime": launch["runtime"],
        "qfbench_public_manifest": launch["qfbench_public_manifest"],
        "trajectory_bank_output": launch["trajectory_bank_output"],
        "public_contracts_root": contracts,
        "reviewer_config": {
            "backend": "openrouter",
            "model": "reviewer/test-model",
            "token_file": str(tmp_path / "runtime/model-token"),
            "reasoning_effort": "high",
        },
        "output_root": tmp_path / "launch",
    }
    assert build_qrs_main_launch(**kwargs)["panel_controller_plans"] == launch[
        "panel_controller_plans"
    ]

    changed = dict(kwargs)
    changed["reviewer_config"] = {
        **kwargs["reviewer_config"],
        "model": "reviewer/different-model",
    }
    with pytest.raises(QRSMainLaunchError, match="refusing to replace"):
        build_qrs_main_launch(**changed)


def test_rejects_runtime_that_differs_from_frozen_h0(tmp_path: Path) -> None:
    rootless = tmp_path / "runtime/rootless.json"
    rootless.parent.mkdir(parents=True)
    rootless.write_text("{}\n", encoding="utf-8")
    handoff = _handoff(tmp_path, rootless)
    contracts = _contracts(tmp_path)

    with pytest.raises(QRSMainLaunchError, match="worker route differs"):
        build_qrs_main_launch(
            method_plan_path=METHOD,
            frozen_h0_handoff_path=handoff,
            scheduler_run_id="qrs-main-test-r1",
            runtime={
                "python": tmp_path / "runtime/python",
                "source_root": tmp_path / "deploy",
                "qfbench_root": tmp_path / "qfbench",
                "qfbench_manifest": tmp_path / "manifest.json",
                "rootless_config": rootless,
                "image_set_manifest": tmp_path / "images.json",
                "results_dir": tmp_path / "runs",
                "worker_route": "different-route",
            },
            qfbench_public_manifest=tmp_path / "manifest.json",
            trajectory_bank_output=tmp_path / "bank",
            public_contracts_root=contracts,
            reviewer_config={"backend": "openrouter"},
            output_root=tmp_path / "launch",
        )
