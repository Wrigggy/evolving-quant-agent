"""Smoke test: the mock 2-arm run must exhibit the three §5.4 mechanism signals.

Also checks the reference computations and the perturbation-probe logic directly,
so the hard verifier itself is trusted (it is what drives evolution).
"""

import math

import pytest

from qea.loop import Config, acceptance_signals, run_ablation
from qea.tasks import (
    bs_call_reference,
    current_ratio_reference,
    load_gdpval_a_pile,
    loan_amort_reference,
    npv_reference,
)
from qea.verifier import HardVerifier


# --------------------------------------------------------------------------- #
# Reference computations.                                                     #
# --------------------------------------------------------------------------- #
def test_black_scholes_atm():
    # S=K=100, r=0.05, sigma=0.2, T=1 -> ~10.4506 (textbook value)
    p = bs_call_reference({"S": 100, "K": 100, "r": 0.05, "sigma": 0.2, "T": 1.0})["call_price"]
    assert abs(p - 10.4506) < 1e-3


def test_amort_fully_amortizes():
    out = loan_amort_reference({"principal": 500_000, "annual_rate": 0.06, "years": 30, "payments_per_year": 12})
    assert abs(out["payment"] - 2997.75) < 0.5     # ~$2,997.75/mo
    assert abs(out["final_balance"]) < 1e-2         # amortizes to ~0


def test_current_ratio():
    out = current_ratio_reference({"current_assets": 1_250_000, "current_liabilities": 800_000})
    assert abs(out["current_ratio"] - 1.5625) < 1e-9
    assert out["working_capital"] == 450_000


def test_npv_irr():
    out = npv_reference({"rate": 0.09, "cashflows": [-100_000_000, 28_000_000, 33_000_000, 39_000_000, 46_000_000]})
    assert out["npv"] > 0                            # positive NPV at 9%
    # IRR is the rate where NPV == 0
    from qea.tasks import _npv
    assert abs(_npv(out["irr"], [-100_000_000, 28_000_000, 33_000_000, 39_000_000, 46_000_000])) < 1.0


# --------------------------------------------------------------------------- #
# Perturbation probe: a hardcoded constant must FAIL the probe (the integrity   #
# guard's whole point). A general solution must PASS.                          #
# --------------------------------------------------------------------------- #
def test_perturbation_probe_kills_hardcoding():
    task = next(t for t in load_gdpval_a_pile() if t.task_id == "A_opt_01")
    hv = HardVerifier()
    base = task.reference(task.inputs)["call_price"]

    hardcoded = f"def solve(inputs):\n    return {{'call_price': {base}}}\n"
    res_hc = hv._score_real(task, hardcoded, k=2)
    assert res_hc.base_pass and not res_hc.probe_pass and not res_hc.oos_pass

    general = (
        "def solve(inputs):\n"
        "    S,K,r,s,T = inputs['S'],inputs['K'],inputs['r'],inputs['sigma'],inputs['T']\n"
        "    d1=(math.log(S/K)+(r+0.5*s*s)*T)/(s*math.sqrt(T)); d2=d1-s*math.sqrt(T)\n"
        "    nc=lambda x:0.5*(1+math.erf(x/math.sqrt(2)))\n"
        "    return {'call_price': S*nc(d1)-K*math.exp(-r*T)*nc(d2)}\n"
    )
    res_g = hv._score_real(task, general, k=2)
    assert res_g.base_pass and res_g.probe_pass and res_g.oos_pass


# --------------------------------------------------------------------------- #
# The three §5.4 mechanism signals (mock 2-arm run).                          #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def ablation(tmp_path_factory):
    cfg = Config(mock=True, n_iters=4, k=2, results_dir=str(tmp_path_factory.mktemp("results")))
    return run_ablation(cfg)


def test_signal_1_causal_loop(ablation):
    arm = ablation.arm1
    r1 = arm.records[0]
    # EVAL -> DIAGNOSE -> WORKSPACE -> VERDICT all reference the same root cause
    assert r1.root_cause_tag == "Hardcoding"
    assert r1.verdict == "EFFECTIVE" and r1.kept
    assert "integrity_guard" in arm.final_harness_summary.get("validator", [])


def test_signal_2_monotonic_oos(ablation):
    traj = ablation.arm1.oos_trajectory
    assert all(traj[i] <= traj[i + 1] for i in range(len(traj) - 1)), traj
    assert max(traj) > min(traj), traj                # strict rise at least once
    assert traj[0] == 0                               # seed hardcodes -> 0 OOS


def test_signal_3_correct_rollback(ablation):
    recs = ablation.arm1.records
    assert any(r.verdict == "HARMFUL" and not r.kept for r in recs)        # broke code_exec
    assert any(r.verdict == "INEFFECTIVE" and not r.kept for r in recs)    # overfit killed by probe
    assert any(r.blocked for r in recs)                                    # repeat blocked by buffer


def test_acceptance_all_signals(ablation):
    assert all(acceptance_signals(ablation.arm1).values())


def test_capability_wall_never_solved(ablation):
    # The amortization subtype includes a capability wall: even the evolved
    # harness cannot lift it (iron law 1), and it stays visible per-subtype.
    n_oos, n_total = ablation.arm1.final_per_subtype["amortization"]
    assert n_oos < n_total


def test_arm2_softB_adds_variance(ablation):
    # Arm2 puts soft-B in the loop -> noisier falsification signal than Arm1.
    assert ablation.arm2.mean_eval_variance > ablation.arm1.mean_eval_variance


# --------------------------------------------------------------------------- #
# Regression locks for the review fixes.                                      #
# --------------------------------------------------------------------------- #
def test_irr_tolerance_is_per_metric():
    # A solution with correct NPV but a wildly wrong IRR must FAIL (the old bug:
    # tol=1.0 applied to a ~0.15 IRR let ±643% error pass).
    task = next(t for t in load_gdpval_a_pile() if t.task_id == "A_val_01")
    hv = HardVerifier()
    exp = task.reference(task.inputs)
    bad_irr = (
        "def solve(inputs):\n"
        f"    cfs=inputs['cashflows']; r=inputs['rate']\n"
        "    npv=sum(cf/(1+r)**t for t,cf in enumerate(cfs))\n"
        f"    return {{'npv': npv, 'irr': 0.99}}\n"   # NPV right, IRR absurd
    )
    res = hv._score_real(task, bad_irr, k=2)
    assert not res.base_pass  # wrong IRR must fail the base check now


def test_unattributed_regression_downgrades_verdict():
    from qea.falsify import evaluate_changes
    from qea.harness import Edit
    # predicts to fix A, B; both flip, but unrelated C regresses -> not EFFECTIVE.
    edit = Edit(op="add", slot="validator", component_name="x", predicted_fixes=["A", "B"], risk_tasks=[])
    ev = evaluate_changes(edit, {"flipped": ["A", "B"], "regressed": ["C"]})
    assert ev["verdict"] in ("MIXED", "HARMFUL")
    assert ev["unattributed_regressions"] == ["C"]


def test_signature_no_collision_past_120_chars():
    from qea.harness import Edit
    base = "x" * 130
    a = Edit(op="add", slot="prompt", component_name="p", content=base + "AAA")
    b = Edit(op="add", slot="prompt", component_name="p", content=base + "BBB")
    assert a.signature() != b.signature()
