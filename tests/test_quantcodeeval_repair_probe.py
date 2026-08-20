import json
from pathlib import Path

import pytest

from qea.quantcodeeval_repair_probe import (
    QuantCodeEvalRepairProbeError,
    compare_probe_arms,
    materialize_probe_public_root,
    materialize_probe_worker,
)


def test_materializes_same_budget_worker_and_public_seed(tmp_path: Path):
    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "agent.yaml").write_text("type: agent\nmax_iterations: 60\n")
    (worker / "systemprompt.md").write_text("work\n")
    public = tmp_path / "public"
    task = public / "tasks/T26"
    data = task / "environment/data"
    data.mkdir(parents=True)
    (data / "paper.md").write_text("public\n")
    (task / "instruction.md").write_text("# Official T26 contract\n\nKeep this.\n")
    seed = tmp_path / "strategy.py"
    seed.write_text("VALUE = 1\n")

    copied = materialize_probe_worker(worker, tmp_path / "probe-worker", max_iterations=9)
    overlay = materialize_probe_public_root(
        public, tmp_path / "overlay", task_id="T26", seed_strategy=seed
    )

    assert "max_iterations: 9" in (copied / "agent.yaml").read_text()
    assert (overlay / "tasks/T26/environment/data/probe_seed_strategy.py").read_text() == "VALUE = 1\n"
    instruction = (overlay / "tasks/T26/instruction.md").read_text()
    assert instruction.startswith("# Official T26 contract\n\nKeep this.")
    assert "## Evolver-authored Worker experiment directive" in instruction
    assert "pre-staged at\n`/app/output/strategy.py`" in instruction
    assert "matrix/row-shape mismatch" in instruction
    assert "checker code" in instruction


def test_rejects_missing_iteration_field(tmp_path: Path):
    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "agent.yaml").write_text("type: agent\n")
    with pytest.raises(QuantCodeEvalRepairProbeError, match="max_iterations"):
        materialize_probe_worker(worker, tmp_path / "out", max_iterations=4)


def test_materializes_evolver_authored_from_scratch_probe(tmp_path: Path):
    public = tmp_path / "public"
    source_task = public / "tasks/T26"
    data = source_task / "environment/data"
    data.mkdir(parents=True)
    (data / "paper.md").write_text("public\n")
    (source_task / "instruction.md").write_text(
        "# Official interface\n\n- Save seven required functions.\n"
    )

    overlay = materialize_probe_public_root(
        public,
        tmp_path / "overlay",
        task_id="T26",
        seed_strategy=None,
        worker_instruction="Build strategy.py from the public task and run a smoke.",
    )

    task = overlay / "tasks/T26"
    assert not (task / "environment/data/probe_seed_strategy.py").exists()
    instruction = (task / "instruction.md").read_text()
    assert instruction.startswith(
        "# Official interface\n\n- Save seven required functions.\n\n"
    )
    assert instruction.endswith(
        "Build strategy.py from the public task and run a smoke.\n"
    )


def test_rejects_probe_overlay_without_official_instruction(tmp_path: Path):
    public = tmp_path / "public"
    (public / "tasks/T26/environment/data").mkdir(parents=True)

    with pytest.raises(QuantCodeEvalRepairProbeError, match="instruction is missing"):
        materialize_probe_public_root(
            public,
            tmp_path / "overlay",
            task_id="T26",
            seed_strategy=None,
            worker_instruction="Run the bounded probe.",
        )


def test_comparison_separates_probe_benefit_from_benchmark_claim():
    parent = {"score": {"tests_passed": 3, "tests_failed": 14, "reward": 0.0}}
    candidate = {"score": {"tests_passed": 16, "tests_failed": 1, "reward": 0.0}}
    result = compare_probe_arms(parent, candidate)
    assert result["status"] == "score-helpful"
    assert result["property_delta"] == 13
    assert result["advance_to_blind_t26"] is True
    assert "not a from-scratch" in result["claim_boundary"]
