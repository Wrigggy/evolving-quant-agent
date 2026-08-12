"""Admission-independent functional self-test for tools.strategy_validate.

Runs the public validate_strategy_module against a temporary T24-style module
written into a temporary output directory, and asserts:

1. the percent-form constant warning fires (h1 unit-scale audit);
2. no __pycache__/*.pyc is created in the output directory (delivery safety);
3. the delivery audit reports the required file present;
4. the synthetic pipeline runs and reports output-column info (h2 NaN audit).

This test file itself is inert to the worker (nothing imports it from
agent.yaml); it exists only to let the Evolver smoke harness exercise the
validator end to end on a throwaway fixture.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.strategy_validate import validate_strategy_module  # noqa: E402

MODULE_SRC = '''\
import numpy as np
import pandas as pd

VOL_SCALING_TARGET = 5.34


def compute_demeaned_signal(ff_factors_monthly):
    df = ff_factors_monthly.copy()
    df["is_newsy"] = (df.index % 4 == 0).astype(int)
    df["sum_4_newsy"] = df["mkt"].rolling(4, min_periods=1).sum().shift(1)
    df["expanding_mean"] = df["mkt"].expanding().mean().shift(1)
    df["raw_signal"] = df["mkt"] * VOL_SCALING_TARGET
    df["demeaned_signal"] = df["raw_signal"] - df["expanding_mean"]
    return df
'''


def _run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        mod = out / "strategy.py"
        mod.write_text(MODULE_SRC, encoding="utf-8")

        spec = {
            "compute_demeaned_signal": {
                "input_columns": ["date", "mkt", "mkt_rf", "rf"],
                "output_columns": [
                    "is_newsy",
                    "sum_4_newsy",
                    "expanding_mean",
                    "raw_signal",
                    "demeaned_signal",
                ],
                "expected_params": ["ff_factors_monthly"],
            }
        }
        report = validate_strategy_module(
            str(mod),
            required_functions=spec,
            sample_rows=40,
            output_dir=str(out),
            required_deliverables=["strategy.py"],
        )

        warnings_text = "\n".join(report.get("warnings", []))
        assert "VOL_SCALING_TARGET = 5.34" in warnings_text or "percent-like" in warnings_text, warnings_text
        assert "no explicit decimal conversion" in warnings_text, warnings_text

        pyc_leftovers = list(out.rglob("__pycache__")) + list(out.rglob("*.pyc"))
        assert not pyc_leftovers, f"bytecode written into output dir: {pyc_leftovers}"

        delivery = report.get("delivery", {})
        assert "strategy.py" in delivery.get("files", []), delivery
        assert not delivery.get("errors"), delivery
        assert report["ok"], report

        info_text = "\n".join(report.get("info", []))
        assert "expanding_mean" in info_text and "leading NaN" in info_text, info_text

        print(json.dumps({"ok": True, "errors": report.get("errors", []), "warnings": report.get("warnings", []), "files": delivery.get("files", [])}))


def main() -> None:
    _run()


if __name__ == "__main__":
    main()
