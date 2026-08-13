from pathlib import Path

from qea.worker_quantcodeeval_public_probe.tools.quant_invariant_probe import (
    probe_quant_invariants,
)


def _strategy(path: Path, *, lagged: bool = True) -> Path:
    shift = ".shift(1)" if lagged else ""
    path.write_text(
        "import numpy as np\n"
        "import pandas as pd\n\n"
        "def trailing(rows):\n"
        "    value = rows.copy()\n"
        "    value['date'] = pd.to_datetime(value['date'])\n"
        "    value = value.sort_values(['factor_id', 'date'])\n"
        f"    value['trailing'] = value.groupby('factor_id')['ret'].transform(lambda x: x{shift}.rolling(3, min_periods=3).sum())\n"
        "    return value[['date', 'factor_id', 'trailing']]\n\n"
        "def signs(rows):\n"
        "    value = rows.copy()\n"
        "    value['signal'] = np.sign(value['trailing'])\n"
        "    return value\n\n"
        "def portfolio(returns, signals):\n"
        "    value = returns.merge(signals, on=['date', 'factor_id'])\n"
        "    value = value.dropna(subset=['ret', 'signal'])\n"
        "    value = value[value['signal'] != 0]\n"
        "    value['pnl'] = value['ret'] * value['signal']\n"
        "    return value.groupby('date')['pnl'].mean().reset_index(name='strategy_return')\n",
        encoding="utf-8",
    )
    return path


def _checks():
    rows = [
        {"date": date, "factor_id": "f1", "ret": value}
        for date, value in zip(
            ("2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"),
            (0.1, 0.2, 0.3, 9.0),
        )
    ]
    return [
        {
            "kind": "window_aggregation",
            "function": "trailing",
            "rows": rows,
            "group_column": "factor_id",
            "time_column": "date",
            "value_column": "ret",
            "output_column": "trailing",
            "window": 3,
            "lag": 1,
            "aggregation": "sum",
            "target_where": {"date": "2020-04-30", "factor_id": "f1"},
        },
        {
            "kind": "sign_mapping",
            "function": "signs",
            "input_column": "trailing",
            "output_column": "signal",
        },
        {
            "kind": "equal_weighted_signed_return",
            "function": "portfolio",
            "return_rows": [
                {"date": "2020-04-30", "factor_id": "f1", "ret": 0.1},
                {"date": "2020-04-30", "factor_id": "f2", "ret": 0.2},
                {"date": "2020-04-30", "factor_id": "f3", "ret": 0.5},
            ],
            "signal_rows": [
                {"date": "2020-04-30", "factor_id": "f1", "signal": 1},
                {"date": "2020-04-30", "factor_id": "f2", "signal": -1},
                {"date": "2020-04-30", "factor_id": "f3", "signal": 0},
            ],
            "time_column": "date",
            "group_column": "factor_id",
            "return_column": "ret",
            "signal_column": "signal",
            "output_column": "strategy_return",
            "denominator": "nonzero_signal",
        },
    ]


def test_quant_invariant_probe_checks_window_sign_and_portfolio(tmp_path):
    result = probe_quant_invariants(
        str(_strategy(tmp_path / "strategy.py")),
        _checks(),
        "Public task defines t-3 through t-1, sign mapping, and equal weights.",
        ["strictly lagged", "includes current month"],
    )

    assert result["status"] == "passed"
    assert result["check_kinds"] == [
        "window_aggregation",
        "sign_mapping",
        "equal_weighted_signed_return",
    ]


def test_quant_invariant_probe_rejects_current_period_window(tmp_path):
    result = probe_quant_invariants(
        str(_strategy(tmp_path / "strategy.py", lagged=False)),
        [_checks()[0]],
        "Public task defines t-3 through t-1.",
        ["strictly lagged", "includes current month"],
    )

    assert result["status"] == "failed"
    assert result["exit_code"] != 0
