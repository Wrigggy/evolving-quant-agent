import json
from pathlib import Path
import subprocess
import sys

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]
PINNED_COMMIT = "024921eb507fcc0c4ffe3e0a96802724be1ae84a"


def test_repository_manifest_preregisters_three_optimize_two_holdout_and_copy_exclusions():
    payload = json.loads((REPOSITORY / "data/qfbench/MANIFEST.json").read_text())

    assert payload["commit"] == PINNED_COMMIT
    assert [item["task_id"] for item in payload["pilot"]["optimize"]] == [
        "historical-var-data-prep",
        "momentum-backtest",
        "evt-pot-var",
    ]
    assert [item["task_id"] for item in payload["pilot"]["held_out"]] == [
        "fx-forward-cross-rate",
        "option-put-call-parity-forward-audit",
    ]
    assert payload["inoperable_tasks"] == [
        {
            "task_id": "sec-8k-event-alpha",
            "reason": "official verifier raises before writing reward.txt at the pinned commit",
        }
    ]
    assert len(payload["copy_oracle_tasks"]) == 8
    selected = {
        item["task_id"]
        for split in ("optimize", "held_out")
        for item in payload["pilot"][split]
    }
    assert selected.isdisjoint(payload["copy_oracle_tasks"])
    assert selected.isdisjoint(item["task_id"] for item in payload["inoperable_tasks"])
    optimize_lineages = {item["lineage"] for item in payload["pilot"]["optimize"]}
    heldout_lineages = {item["lineage"] for item in payload["pilot"]["held_out"]}
    assert optimize_lineages.isdisjoint(heldout_lineages)


def test_repository_manifest_30_preregisters_exact_stratified_split():
    path = REPOSITORY / "data/qfbench/MANIFEST_30.json"
    payload = json.loads(path.read_text())
    optimize = payload["pilot"]["optimize"]
    held_out = payload["pilot"]["held_out"]

    assert payload["commit"] == PINNED_COMMIT
    assert [item["task_id"] for item in optimize] == [
        "historical-var-data-prep",
        "evt-pot-var",
        "credit-migration-matrix",
        "credit-spread-decomposition",
        "momentum-backtest",
        "bollinger-backtest-aapl",
        "brinson-sector-attribution",
        "etf-cross-asset-lead-lag",
        "cme-hdd-option-pricing",
        "delta-hedging-pnl-simulation",
        "localvol-barrier",
        "fomc-tone-event-study",
        "swap-curve-bootstrap-ois",
        "yield-curve-bond-immunization",
        "zero-coupon-bootstrapping",
        "crypto-funding-rate-basis-carry",
        "prediction-markets-cross-venue-dislocation",
        "13f-amendment-aware-crowding",
        "corporate-action-adjustment",
        "earnings-surprise-calculator",
    ]
    assert [item["task_id"] for item in held_out] == [
        "dcc-garch-portfolio-var",
        "fft-compound-poisson",
        "pca-factor-portfolio",
        "bl-regime-hmm",
        "option-put-call-parity-forward-audit",
        "interest-rate-cap-floor",
        "fx-forward-cross-rate",
        "cir-bond-pricing",
        "intraday-volume-fitting-and-execution-scheduling",
        "form4-cross-sectional-sale-pressure",
    ]
    assert len(optimize) == 20
    assert len(held_out) == 10
    expected_domains = {
        "risk_credit",
        "systematic_strategy",
        "derivatives",
        "rates_fx_macro",
        "execution_microstructure",
        "data_engineering",
    }
    assert {item["domain"] for item in optimize} == expected_domains
    assert {item["domain"] for item in held_out} == expected_domains
    assert sum(item["reward_kind"] == "partial" for item in optimize) == 4
    assert {item["lineage"] for item in optimize}.isdisjoint(
        item["lineage"] for item in held_out
    )
    selected = {item["task_id"] for item in optimize + held_out}
    assert selected.isdisjoint(payload["copy_oracle_tasks"])
    assert selected.isdisjoint(
        item["task_id"] for item in payload["inoperable_tasks"]
    )


def test_saved_local_oracle_anchor_is_pinned_and_passed():
    anchor = REPOSITORY / "results/qfbench_smoke/20260721T144046+0800_024921eb"
    status = json.loads((anchor / "run_status.json").read_text())

    assert status["benchmark"]["commit"] == PINNED_COMMIT
    assert status["benchmark"]["task"] == "historical-var-data-prep"
    assert status["oracle"]["reward"] == 1
    assert status["oracle"]["pytest_passed"] == 12
    assert status["oracle"]["pytest_failed"] == 0
    assert (anchor / "oracle_output/results.json").is_file()
    assert (anchor / "oracle_output/solution.json").is_file()


def test_oracle_artifact_parity_canonicalizes_json_and_detects_mismatch(tmp_path):
    from qea.oracle_parity import OracleParityError, compare_oracle_artifacts

    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()
    (expected / "results.json").write_text('{"b": 2, "a": [1, 2]}\n')
    (actual / "results.json").write_text('{\n  "a": [1,2],\n  "b": 2\n}\n')
    (expected / "table.csv").write_bytes(b"x\n1\n")
    (actual / "table.csv").write_bytes(b"x\n1\n")

    parity = compare_oracle_artifacts(expected, actual)
    assert parity.matches is True
    assert parity.files == ("results.json", "table.csv")

    (actual / "results.json").write_text('{"a": [1, 3], "b": 2}\n')
    with pytest.raises(OracleParityError, match="content mismatch"):
        compare_oracle_artifacts(expected, actual)


def test_e2b_oracle_script_is_directly_invokable():
    proc = subprocess.run(
        [sys.executable, "scripts/run_qfbench_e2b_oracle.py", "--help"],
        cwd=REPOSITORY,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "--anchor-dir" in proc.stdout
    assert "--approve-paid-e2b" in proc.stdout
