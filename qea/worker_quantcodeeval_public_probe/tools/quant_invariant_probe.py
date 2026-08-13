"""Run declarative, independently computed quant invariants on a strategy."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


_RUNNER = r'''
import importlib.util
import json
import pathlib
import sys

import numpy as np
import pandas as pd


def frame(rows):
    value = pd.DataFrame(rows)
    for column in value.columns:
        if "date" in str(column).lower():
            value[column] = pd.to_datetime(value[column])
    return value


def row_mask(value, where):
    mask = pd.Series(True, index=value.index)
    for column, expected in where.items():
        series = value[column]
        if "date" in str(column).lower():
            expected = pd.Timestamp(expected)
        mask &= series == expected
    return mask


def scalar(value, where, column):
    selected = value.loc[row_mask(value, where), column]
    assert len(selected) == 1, (where, column, len(selected))
    return selected.iloc[0]


def close(actual, expected, tolerance):
    if pd.isna(expected):
        assert pd.isna(actual), (actual, expected)
    else:
        assert np.isclose(float(actual), float(expected), atol=tolerance, rtol=tolerance), (
            actual,
            expected,
        )


def call(function, frames, kwargs=None):
    fn = getattr(strategy, function)
    return fn(*(frame(rows) for rows in frames), **(kwargs or {}))


def window_expected(rows, check):
    value = frame(rows).sort_values([check["group_column"], check["time_column"]])
    target = value.loc[row_mask(value, check["target_where"])]
    assert len(target) == 1
    target_row = target.iloc[0]
    group = value[value[check["group_column"]] == target_row[check["group_column"]]]
    position = group.index.get_loc(target.index[0])
    stop = position - check["lag"] + 1
    start = stop - check["window"]
    assert start >= 0 and stop > start
    inputs = group.iloc[start:stop][check["value_column"]].astype(float)
    aggregation = check["aggregation"]
    if aggregation == "sum":
        return inputs.sum()
    if aggregation == "mean":
        return inputs.mean()
    if aggregation == "geometric_return":
        return (1.0 + inputs).prod() - 1.0
    raise AssertionError(f"unsupported aggregation: {aggregation}")


def window_check(check):
    rows = check["rows"]
    output = call(check["function"], [rows], check.get("function_kwargs"))
    expected = window_expected(rows, check)
    actual = scalar(output, check["target_where"], check["output_column"])
    close(actual, expected, check.get("tolerance", 1e-9))

    shuffled = frame(rows).sample(frac=1.0, random_state=17).to_dict("records")
    shuffled_output = call(check["function"], [shuffled], check.get("function_kwargs"))
    shuffled_actual = scalar(
        shuffled_output, check["target_where"], check["output_column"]
    )
    close(shuffled_actual, expected, check.get("tolerance", 1e-9))

    if check["lag"] >= 1:
        changed = frame(rows)
        target_mask = row_mask(changed, check["target_where"])
        changed.loc[target_mask, check["value_column"]] += check.get(
            "current_perturbation", 10.0
        )
        changed_output = call(
            check["function"],
            [changed.to_dict("records")],
            check.get("function_kwargs"),
        )
        changed_actual = scalar(
            changed_output, check["target_where"], check["output_column"]
        )
        close(changed_actual, expected, check.get("tolerance", 1e-9))


def sign_check(check):
    rows = check.get(
        "rows",
        [
            {"case": "positive", check["input_column"]: 2.0},
            {"case": "negative", check["input_column"]: -3.0},
            {"case": "zero", check["input_column"]: 0.0},
            {"case": "missing", check["input_column"]: None},
        ],
    )
    source = frame(rows)
    output = call(check["function"], [rows], check.get("function_kwargs"))
    expected = np.sign(pd.to_numeric(source[check["input_column"]], errors="coerce"))
    actual = pd.to_numeric(output[check["output_column"]], errors="coerce")
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected):
        close(got, want, check.get("tolerance", 1e-9))


def portfolio_check(check):
    returns = frame(check["return_rows"])
    signals = frame(check["signal_rows"])
    output = call(
        check["function"],
        [check["return_rows"], check["signal_rows"]],
        check.get("function_kwargs"),
    )
    merged = returns.merge(
        signals,
        on=[check["time_column"], check["group_column"]],
        how="inner",
    ).dropna(subset=[check["return_column"], check["signal_column"]])
    if check.get("denominator", "all_valid") == "nonzero_signal":
        merged = merged[merged[check["signal_column"]] != 0]
    merged["expected"] = (
        merged[check["return_column"]] * merged[check["signal_column"]]
    )
    expected = merged.groupby(check["time_column"])["expected"].mean()
    for date, want in expected.items():
        got = scalar(
            output,
            {check["time_column"]: date},
            check["output_column"],
        )
        close(got, want, check.get("tolerance", 1e-9))


module_path = pathlib.Path(sys.argv[1])
spec_path = pathlib.Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("candidate_strategy", module_path)
strategy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strategy)
checks = json.loads(spec_path.read_text(encoding="utf-8"))
results = []
for index, check in enumerate(checks, 1):
    kind = check["kind"]
    if kind == "window_aggregation":
        window_check(check)
    elif kind == "sign_mapping":
        sign_check(check)
    elif kind == "equal_weighted_signed_return":
        portfolio_check(check)
    else:
        raise AssertionError(f"unsupported check kind: {kind}")
    results.append({"check": index, "kind": kind, "status": "passed"})
print(json.dumps(results, sort_keys=True))
'''


def probe_quant_invariants(
    module_path: str,
    checks: list[dict[str, object]],
    public_basis: str,
    competing_definitions: list[str],
    timeout_seconds: int = 90,
) -> dict[str, object]:
    """Execute structured quant checks whose expectations are tool-computed."""

    source = Path(module_path)
    if not source.is_file():
        return {"status": "failed", "error": "strategy module is missing"}
    if not checks or not all(isinstance(check, dict) for check in checks):
        return {"status": "failed", "error": "checks must be a non-empty list"}
    if not isinstance(public_basis, str) or not public_basis.strip():
        return {"status": "failed", "error": "public basis is empty"}
    definitions = [
        value.strip()
        for value in competing_definitions
        if isinstance(value, str) and value.strip()
    ]
    if len(definitions) < 2 or len(set(definitions)) != len(definitions):
        return {
            "status": "failed",
            "error": "at least two distinct competing definitions are required",
        }
    timeout = max(1, min(int(timeout_seconds), 180))

    with tempfile.TemporaryDirectory(prefix="qea-quant-invariants-") as temporary:
        root = Path(temporary)
        candidate = root / "strategy.py"
        specification = root / "checks.json"
        runner = root / "runner.py"
        shutil.copy2(source, candidate)
        specification.write_text(json.dumps(checks), encoding="utf-8")
        runner.write_text(_RUNNER, encoding="utf-8")
        try:
            completed = subprocess.run(
                [sys.executable, str(runner), str(candidate), str(specification)],
                cwd=root,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"status": "failed", "error": "invariant probe timed out"}

    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "check_kinds": [str(check.get("kind", "unknown")) for check in checks],
        "public_basis": public_basis.strip(),
        "competing_definitions": definitions,
        "stdout": completed.stdout[-4_000:],
        "stderr": completed.stderr[-8_000:],
    }


__all__ = ["probe_quant_invariants"]
