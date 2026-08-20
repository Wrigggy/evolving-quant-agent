import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/run_quantcodeeval_activation_probe.py"
)
SPEC = importlib.util.spec_from_file_location("activation_probe_script", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_reads_exact_evolver_instruction_from_qdr_result(tmp_path):
    result = tmp_path / "QDR-RESULT.json"
    result.write_text(
        json.dumps(
            {
                "evolution": {
                    "decision": {
                        "experiment_spec": {
                            "worker_instruction": "Run the declared relation audit."
                        }
                    }
                }
            }
        )
    )

    assert MODULE._worker_instruction(None, result) == (
        "Run the declared relation audit."
    )


def test_instruction_source_is_unambiguous(tmp_path):
    instruction = tmp_path / "instruction.txt"
    instruction.write_text("Use the tool.\n")

    with pytest.raises(ValueError, match="exactly one"):
        MODULE._worker_instruction(instruction, tmp_path / "result.json")
