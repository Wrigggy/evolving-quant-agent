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


def test_gdpval_rubric_grader_weighted():
    # Open GDPval rubric grading: per-criterion satisfied? -> weighted score.
    from qea.tasks import BTask, _parse_rubric_json
    from qea.verifier import SoftJudge

    # rubric_json parsing keeps points + criterion
    items = _parse_rubric_json('[{"score":2,"criterion":"a"},{"score":1,"criterion":"b"}]')
    assert items == [{"points": 2.0, "criterion": "a"}, {"points": 1.0, "criterion": "b"}]

    class StubLLM:
        def complete(self, prompt, *, role="judge"):
            return 'sure: {"1": true, "2": false, "3": true}'

    t = BTask(task_id="b", subtype="x", prompt="p", rubric="",
              rubric_items=[{"points": 2, "criterion": "a"},
                            {"points": 1, "criterion": "b"},
                            {"points": 1, "criterion": "c"}])
    r = SoftJudge(StubLLM()).score(t, "deliverable", None, mock=False, k=1)
    # earned 2+1=3 of total 4 -> frac 0.75 -> quantized to GDPval parity scale {0,0.5,1} -> 0.5
    assert r.score == 0.5


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


def test_sandbox_allows_safe_imports_blocks_others():
    from qea.verifier import safe_exec_solve
    # models naturally write `import math` — must work
    ok = "def solve(inputs):\n    import math\n    return {'x': math.sqrt(inputs['v'])}\n"
    assert safe_exec_solve(ok, {"v": 16.0})["x"] == 4.0
    # disallowed imports stay blocked
    bad = "def solve(inputs):\n    import os\n    return {'x': 1}\n"
    with pytest.raises(Exception):
        safe_exec_solve(bad, {})


def test_soft_gate_noise_aware():
    from qea.falsify import decide_keep_soft
    assert decide_keep_soft(0.618, 0.651, 0.02) is True    # gain 0.033 > noise 0.02 -> keep
    assert decide_keep_soft(0.618, 0.651, 0.05) is False   # gain within noise -> reject
    assert decide_keep_soft(0.618, 0.560, 0.02) is False   # regression -> reject


def test_signature_no_collision_past_120_chars():
    from qea.harness import Edit
    base = "x" * 130
    a = Edit(op="add", slot="prompt", component_name="p", content=base + "AAA")
    b = Edit(op="add", slot="prompt", component_name="p", content=base + "BBB")
    assert a.signature() != b.signature()


# --------------------------------------------------------------------------- #
# GDPval-AA pairwise grader (Artificial Analysis protocol).                    #
# --------------------------------------------------------------------------- #
def test_pairwise_judge_deanonymizes_correctly():
    # The judge sees randomly-ordered "Submission A/B"; the verdict must map back
    # to the (sub_a, sub_b) the caller passed in, regardless of the shuffle.
    from qea.tasks import BTask
    from qea.verifier import PairwiseJudge

    class StubLLM:
        def __init__(self):
            self.prompts = []

        def complete(self, prompt, *, role="judge"):
            self.prompts.append(prompt)
            # always prefer the submission whose text is "GOOD", wherever it is shown
            a_block = prompt.split("<submission_a>")[1].split("</submission_a>")[0]
            return '{"winner": "A"}' if "GOOD" in a_block else '{"winner": "B"}'

    t = BTask(task_id="pw1", subtype="x", prompt="write a memo", rubric="")
    res = PairwiseJudge(StubLLM()).compare(t, "GOOD deliverable", "weak", mock=False, k=4)
    assert res["verdict"] == "a"
    assert all(v == "a" for v in res["votes"])
    # and the reverse order must invert the verdict
    res2 = PairwiseJudge(StubLLM()).compare(t, "weak", "GOOD deliverable", mock=False, k=4)
    assert res2["verdict"] == "b"


def test_pairwise_judge_tie_and_garbage_default_to_tie():
    from qea.tasks import BTask
    from qea.verifier import PairwiseJudge

    class TieLLM:
        def complete(self, prompt, *, role="judge"):
            return '{"winner": "tie"}'

    class GarbageLLM:
        def complete(self, prompt, *, role="judge"):
            return "no json here"

    t = BTask(task_id="pw2", subtype="x", prompt="p", rubric="")
    assert PairwiseJudge(TieLLM()).compare(t, "a", "b", mock=False, k=2)["verdict"] == "tie"
    assert PairwiseJudge(GarbageLLM()).compare(t, "a", "b", mock=False, k=2)["verdict"] == "tie"


def test_bt_elo_anchoring():
    from qea.verifier import bt_elo
    assert bt_elo(0, 0) == 1000.0                 # nothing decided -> anchor
    assert bt_elo(10, 10) == 1000.0               # even record -> anchor
    assert bt_elo(20, 10) > 1000.0 > bt_elo(10, 20)
    # symmetric around the anchor
    assert abs((bt_elo(20, 10) - 1000.0) + (bt_elo(10, 20) - 1000.0)) < 1e-9


def test_decide_keep_pairwise_excludes_ties_and_needs_margin():
    from qea.falsify import decide_keep_pairwise
    assert decide_keep_pairwise(0, 0, 0.05) is False          # all ties -> reject
    assert decide_keep_pairwise(16, 10, 0.05) is True         # 0.615 > 0.55
    assert decide_keep_pairwise(14, 12, 0.05) is False        # 0.538 within margin
    assert decide_keep_pairwise(10, 16, 0.05) is False        # losing -> reject


def test_gdpval_soft_mock_pairwise_gate(tmp_path):
    # End-to-end mock: iter-1 integrity_guard lifts the mock soft score
    # (0.45 -> 0.72), so the pairwise gate must keep it and the win rate vs the
    # frozen seed must end above 0.5 + null margin.
    from qea.loop import Config, run_gdpval_soft
    res = run_gdpval_soft(Config(mock=True, n_iters=2, k=2, results_dir=str(tmp_path)))
    assert res.n_kept >= 1
    assert res.winrate_trajectory[0] == 0.5
    assert res.winrate_trajectory[-1] > 0.5 + res.pairwise_margin
    assert res.final_elo_vs_seed > 1000.0


def test_match_set_parallel_real_path():
    # Real-mode match_set fans out across a thread pool; verdicts must still map
    # back per task, and a throwing judge call degrades to a tie, not a crash.
    from qea.tasks import BTask
    from qea.verifier import PairwiseJudge

    class StubLLM:
        def complete(self, prompt, *, role="judge"):
            a_block = prompt.split("<submission_a>")[1].split("</submission_a>")[0]
            if "BOOM" in prompt:
                raise RuntimeError("judge exploded")
            return '{"winner": "A"}' if "GOOD" in a_block else '{"winner": "B"}'

    tasks = [BTask(task_id=f"t{i}", subtype="x", prompt=f"task {i}", rubric="") for i in range(8)]
    subs_a = {t.task_id: "GOOD deliverable" for t in tasks}
    subs_b = {t.task_id: "weak" for t in tasks}
    subs_b["t3"] = "BOOM"  # poison one match -> tie, not crash
    res = PairwiseJudge(StubLLM()).match_set(tasks, subs_a, subs_b, mock=False, k=2)
    assert res["wins"] == 7 and res["losses"] == 0 and res["ties"] == 1
    assert res["per_task"]["t3"] == "tie"
    assert all(res["per_task"][f"t{i}"] == "a" for i in range(8) if i != 3)


def test_provider_pin_is_per_model_official(monkeypatch):
    # Every model must pin ITS OWN official provider; no cross-pinning.
    from qea.llm import provider_for, resolve_provider_map
    monkeypatch.setenv("QEA_PROVIDER_ORDER", "deepseek")
    pmap = resolve_provider_map()
    assert provider_for("deepseek/deepseek-v4-pro", pmap) == "deepseek"
    assert provider_for("qwen/qwen3.7-max", pmap) == "alibaba"      # built-in official map
    assert provider_for("google/gemini-3.1-pro-preview", pmap) is None  # unpinned -> free routing
    monkeypatch.setenv("QEA_PROVIDER_MAP", "google=google-ai-studio,qwen=other")
    pmap = resolve_provider_map()
    assert provider_for("google/gemini-3.1-pro-preview", pmap) == "google-ai-studio"
    assert provider_for("qwen/qwen3.7-max", pmap) == "other"        # env overrides built-in


def test_gdpval_local_fork_preferred():
    # The rubric fork in data/gdpval/ must be used (no network) when present.
    from qea.tasks import _GDPVAL_LOCAL_PARQUET, _load_gdpval_df
    if not _GDPVAL_LOCAL_PARQUET.exists():
        pytest.skip("local GDPval fork not present (run scripts/fork_gdpval.py)")
    df, src = _load_gdpval_df()
    assert src == "local fork"
    assert len(df) == 220
    assert {"task_id", "rubric_json", "rubric_pretty"} <= set(df.columns)
