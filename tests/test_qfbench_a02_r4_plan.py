import json
from pathlib import Path

from scripts.run_qfbench_lineage_controller import (
    build_child_argv,
    build_proposal_argv,
)


def _plan():
    path = (
        Path(__file__).resolve().parents[1]
        / "data/breadth/QF_A02_QRS_REFINEMENT_R4_PLAN.json"
    )
    return json.loads(path.read_text())


def test_a02_r4_chains_r3_evidence_and_keeps_c2_as_backbone():
    plan = _plan()
    lineage = plan["lineages"][0]
    evidence = plan["evidence_build"]

    assert evidence["base_view"].endswith(
        "qf-a01-localvol-qrs-refinement-20260823-r1"
    )
    assert evidence["source_proposal_run"].endswith(
        "qf-a01-localvol-qrs-refine-proposal-20260824-r3"
    )
    assert evidence["source_worker_run"].endswith(
        "qf-a01-localvol-qrs-refine-target-20260824-r3"
    )
    assert "--optimization-diagnostic" in evidence["argv"]
    assert "--parent-candidate" in evidence["argv"]
    assert lineage["parent"]["version"] == "qf-a01-localvol-qrs-c2-r3"
    assert lineage["parent"]["retained_activation_token"] == (
        "check_parameter_admissibility"
    )

    argv = build_proposal_argv(
        plan,
        lineage,
        lineage["proposal"],
        approve_external_run=True,
    )
    assert argv[argv.index("--backbone") + 1] == lineage["parent"][
        "worker_dir"
    ]
    assert argv[argv.index("--evidence") + 1] == evidence["destination"]


def test_a02_r4_uses_c1_only_as_selection_reference():
    plan = _plan()
    lineage = plan["lineages"][0]
    target = lineage["stages"][0]
    assert target["selection_reference"]["reference_version"] == (
        "qf-a0-localvol-qrs-c1"
    )
    assert target["selection_reference"]["report_path"].endswith(
        "qf-a0-localvol-qrs-repeat-20260823-r1/pilot-report.json"
    )
    assert lineage["repeat_consistency_policy"] == (
        "resolved_property_footprint_v1"
    )
    protection = lineage["stages"][2]
    assert protection["selection_reference"]["reference_version"] == (
        "qf-a0-localvol-qrs-c1"
    )
    assert protection["selection_reference"]["report_path"].endswith(
        "qf-a0-localvol-qrs-protection-20260823-r1/pilot-report.json"
    )

    active = {
        **lineage,
        "candidate": {
            "worker_dir": "/candidate/c3",
            "activation_binding": {"status": "retained"},
            "activation_token": "check_parameter_admissibility",
        },
    }
    argv = build_child_argv(
        plan, active, target, approve_external_run=True
    )
    arm_values = [
        argv[index + 1] for index, value in enumerate(argv) if value == "--arm"
    ]
    assert argv[argv.index("--seed-worker") + 1] == lineage["parent"][
        "worker_dir"
    ]
    assert arm_values == ["quant-state-refined-r4=/candidate/c3"]
    assert argv[argv.index("--activation-token") + 1] == (
        "check_parameter_admissibility"
    )
