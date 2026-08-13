#!/usr/bin/env python3
"""Persist the deterministic QuantCodeEval v2 mechanism canary and its evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TESTS = (
    (
        "tests/test_quantcodeeval_v2_loop.py::"
        "test_no_model_loop_reuses_rejected_round_and_promotes_full_component"
    ),
    (
        "tests/test_quantcodeeval_components.py::"
        "test_canary_ledger_keeps_failed_component_and_replicated_composition_distinct"
    ),
    (
        "tests/test_quantcodeeval_components.py::"
        "test_component_ablation_can_remove_one_member_of_a_composition"
    ),
    (
        "tests/test_quantcodeeval_v2_evidence.py::"
        "test_v2_evidence_exposes_exact_rejected_diff_and_candidate_source"
    ),
    (
        "tests/test_quantcodeeval_v2_live.py::"
        "test_activation_cli_passes_component_ledger_to_live_runner"
    ),
    (
        "tests/test_evolver_guarded_tools.py::"
        "test_quant_v2_accepts_component_search_operators"
    ),
)


def _write_json(path: Path, value: object) -> None:
    payload = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def _file_inventory(root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
        if not path.is_file() or path.name == "RESULT.json":
            continue
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise SystemExit("output must not already exist")
    output.mkdir(parents=True)
    _write_json(
        output / "PLAN.json",
        {
            "schema_version": 1,
            "protocol": "quant_property_v2_no_model_mechanism_canary",
            "claim_scope": (
                "mechanism only: rejected-history reuse, full-component admission, "
                "variable-length stop; no QuantCodeEval benchmark score"
            ),
            "tests": list(TESTS),
            "python": sys.version,
        },
    )
    try:
        import pytest
    except ImportError as exc:
        raise SystemExit("pytest is required for the no-model mechanism canary") from exc
    selected_tests = [
        str(ROOT / test.split("::", 1)[0]) + "::" + test.split("::", 1)[1]
        for test in TESTS
    ]
    exit_code = int(
        pytest.main(
            [
                "-q",
                *selected_tests,
                f"--basetemp={output / 'work'}",
                f"--junitxml={output / 'junit.xml'}",
            ]
        )
    )
    # Pytest creates a convenience ``*current`` symlink beside numbered temp
    # roots.  It is not experiment evidence and would violate exact regular-file
    # membership, so remove only those runner-created top-level links.
    for path in (output / "work").iterdir():
        if path.is_symlink() and path.name.endswith("current"):
            path.unlink()
    run_dirs = tuple(
        path
        for path in (output / "work").glob("*/run")
        if path.is_dir() and not path.parent.is_symlink()
    )
    passed = exit_code == 0 and len(run_dirs) == 1
    result = {
        "schema_version": 1,
        "protocol": "quant_property_v2_no_model_mechanism_canary",
        "status": "PASS" if passed else "FAIL",
        "pytest_exit_code": exit_code,
        "run_dir": (
            run_dirs[0].relative_to(output).as_posix() if len(run_dirs) == 1 else None
        ),
        "asserted_observations": [
            "round 1 prompt-only candidate was rejected after no property-family change",
            "round 2 read the exact rejected round-1 patch",
            "round 2 changed tools, tool_descriptions, and agent_config coherently",
            "independent full-harness admission passed before promotion",
            "search stopped on target_reached after 2 rounds, not a fixed 5 rounds",
            "component evidence distinguishes standalone failure from composition success",
            "ablation can remove one component from a successful composition",
            "Evolver evidence and live CLI expose component stability",
            "COMPOSE, SYNTHESIZE, and ROUTE are accepted search operators",
        ],
        "benchmark_score_claimed": False,
        "files": _file_inventory(output),
    }
    _write_json(output / "RESULT.json", result)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
