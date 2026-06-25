"""Task family: GDPval finance/accounting (Econ/Finance/Accounting).

B-pile (the real benchmark): real GDPval "Finance and Insurance" deliverable
tasks (``load_gdpval_finance``), graded by an LLM judge against the ``rubric_json``
as a continuous rubric percentage. This is what ``run_gdpval_soft`` evolves on.

A-pile (synthetic fixture only): numeric tasks with an objective core. Each ships
a deterministic ``reference(inputs) -> {metric: value}`` plus a ``perturb`` that
produces a different-but-valid instance. The ``HardVerifier`` recomputes the
reference and re-runs the solution on perturbed inputs (the *perturbation probe* /
integrity guard): a hardcoded constant passes the base inputs but fails the probe.
These tasks are NOT a real benchmark (capability-sufficient, no headroom); they
survive only as the offline ``--mock`` plumbing fixture.

The A-pile inputs are authored in code with clean reference values; each cites a
real GDPval ``task_id`` for lineage (the real rubric numbers, e.g. the
$559,377.61 amortization balance, prove these numeric cores are real economic
work — but the raw rubric numbers live in prose inside .xlsx/.pdf and ship no
deterministic verifier, so we author clean instances rather than parse them).
"""

from __future__ import annotations

import io
import json
import math
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

SUBTYPES = ("option_pricing", "amortization", "audit_metric", "valuation")

# Standard normal CDF without scipy (math.erf only).
def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# --------------------------------------------------------------------------- #
# Reference computations (pure, deterministic).                               #
# --------------------------------------------------------------------------- #
def bs_call_reference(inputs: dict) -> dict:
    """Black-Scholes price of a European call. Lineage: GDPval c7d83f01 (option pricing)."""
    S, K, r, sigma, T = (inputs[k] for k in ("S", "K", "r", "sigma", "T"))
    if S <= 0 or K <= 0:
        return {"call_price": float("nan")}
    if T <= 0 or sigma <= 0:
        return {"call_price": max(0.0, S - K)}
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    price = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return {"call_price": price}


def loan_amort_reference(inputs: dict) -> dict:
    """Fixed-rate fully-amortizing loan. Lineage: GDPval 7d7fc9a7 (amortization schedule)."""
    P = inputs["principal"]
    annual_rate = inputs["annual_rate"]
    years = inputs["years"]
    ppy = inputs.get("payments_per_year", 12)
    n = int(round(years * ppy))
    i = annual_rate / ppy
    if i == 0:
        payment = P / n
    else:
        payment = P * i / (1.0 - (1.0 + i) ** (-n))
    balance = P
    total_interest = 0.0
    for _ in range(n):
        interest = balance * i
        principal_paid = payment - interest
        total_interest += interest
        balance -= principal_paid
    # Invariant: a correct schedule amortizes to ~0 (the GDPval rubric checks
    # Begin + Adds - Amortization = End and variance == 0).
    return {"payment": payment, "final_balance": balance, "total_interest": total_interest}


def current_ratio_reference(inputs: dict) -> dict:
    """Audit liquidity metric. Lineage: GDPval Accountants/Auditors (audit metric)."""
    ca = inputs["current_assets"]
    cl = inputs["current_liabilities"]
    return {"current_ratio": ca / cl, "working_capital": ca - cl}


def _npv(rate: float, cashflows: list[float]) -> float:
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))


def _irr(cashflows: list[float]) -> float:
    """IRR via bracketed bisection, Newton fallback. Returns nan if no sign change."""
    lo, hi = -0.9999, 10.0
    f_lo, f_hi = _npv(lo, cashflows), _npv(hi, cashflows)
    if f_lo * f_hi > 0:
        # No bracket -> Newton from 0.1
        r = 0.1
        for _ in range(100):
            f = _npv(r, cashflows)
            # analytical derivative d(NPV)/dr = sum_t -t*cf_t/(1+r)^(t+1)
            df = sum(-t * cf / (1.0 + r) ** (t + 1) for t, cf in enumerate(cashflows))
            if abs(df) < 1e-12:
                break
            r_new = r - f / df
            if not math.isfinite(r_new):
                return float("nan")
            if abs(r_new - r) < 1e-10:
                return r_new
            r = r_new
        return r if abs(_npv(r, cashflows)) < 1e-4 else float("nan")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f_mid = _npv(mid, cashflows)
        if abs(f_mid) < 1e-10:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)


def npv_reference(inputs: dict) -> dict:
    """NPV + IRR of a cashflow stream. Lineage: GDPval b78fd844 (NPV/IRR/WACC=9%)."""
    rate = inputs["rate"]
    cfs = list(inputs["cashflows"])
    return {"npv": _npv(rate, cfs), "irr": _irr(cfs)}


# --------------------------------------------------------------------------- #
# Perturbations (produce a different-but-valid instance for the probe).        #
# --------------------------------------------------------------------------- #
def _scale(d: dict, key: str, factor: float) -> dict:
    out = dict(d)
    out[key] = d[key] * factor
    return out


def perturb_bs(inputs: dict, seed: int) -> dict:
    out = dict(inputs)
    out["S"] = inputs["S"] * (1.0 + 0.1 * ((seed % 5) + 1))
    out["sigma"] = inputs["sigma"] * (1.0 + 0.05 * ((seed % 3) + 1))
    return out


def perturb_amort(inputs: dict, seed: int) -> dict:
    out = dict(inputs)
    out["principal"] = inputs["principal"] * (1.0 + 0.2 * ((seed % 4) + 1))
    out["annual_rate"] = inputs["annual_rate"] + 0.005 * ((seed % 3) + 1)
    return out


def perturb_ratio(inputs: dict, seed: int) -> dict:
    out = dict(inputs)
    out["current_assets"] = inputs["current_assets"] * (1.0 + 0.15 * ((seed % 4) + 1))
    return out


def perturb_npv(inputs: dict, seed: int) -> dict:
    out = dict(inputs)
    out["rate"] = inputs["rate"] + 0.01 * ((seed % 3) + 1)
    cfs = list(inputs["cashflows"])
    cfs[1] = cfs[1] * (1.0 + 0.1 * ((seed % 3) + 1))
    out["cashflows"] = cfs
    return out


# --------------------------------------------------------------------------- #
# Task dataclasses.                                                            #
# --------------------------------------------------------------------------- #
@dataclass
class ATask:
    """A-pile hard task. The agent must return a function ``solve(inputs)->dict``."""

    task_id: str
    subtype: str
    prompt: str
    inputs: dict
    reference: Callable[[dict], dict]
    perturb: Callable[[dict, int], dict]
    tol: float | dict = 1e-4  # float (all metrics) or {metric: tol} for per-metric tolerance
    gdpval_lineage: str = ""
    # Mock-only: a "capability wall" task the harness can never fix (models the
    # AHE lesson that no middleware patches a base-capability gap — iron law 1).
    capability_wall: bool = False
    pile: str = "A"


@dataclass
class BTask:
    """B-pile soft task. The agent produces a deliverable; the judge scores it
    against the GDPval `rubric_json` criteria (weighted by points)."""

    task_id: str
    subtype: str
    prompt: str
    rubric: str                              # rubric_pretty (human-readable)
    rubric_items: list = field(default_factory=list)  # [{points, criterion}] from rubric_json
    reference_files: list = field(default_factory=list)  # local paths of GDPval input files
    # Required deliverable file extension(s) = the GDPval GOLD deliverable's type(s).
    # Empty == the gold deliverable is text (no file required). Used by the format gate.
    deliverable_exts: list = field(default_factory=list)
    gold: str | None = None
    gdpval_lineage: str = ""
    # Mock-only: scores the world model returns with/without the discipline a
    # hard-A-evolved harness imparts (so transfer is visible offline).
    mock_base_score: float = 0.45
    mock_disciplined_score: float = 0.72
    pile: str = "B"


def _parse_rubric_json(rj) -> list[dict]:
    """rubric_json -> [{points: float, criterion: str}], the open GDPval scoring spec."""
    try:
        data = json.loads(rj) if isinstance(rj, str) else rj
        out = []
        for c in data:
            crit = (c.get("criterion") or "").strip()
            if not crit:
                continue
            pts = c.get("score")
            out.append({"points": float(pts) if pts else 1.0, "criterion": crit})
        return out
    except Exception:  # noqa: BLE001
        return []


def rubric_corpus(tasks: list) -> list[str]:
    """v1 leakage answer_corpus = rubric-criteria text across the benchmark's tasks.
    (Gold deliverable text is deferred: GDPval gold is binary xlsx/pptx URLs.)"""
    out: list[str] = []
    for t in tasks:
        for c in getattr(t, "rubric_items", None) or []:
            out.append(c["criterion"])
        if getattr(t, "rubric", ""):
            out.append(t.rubric)
    return out


# --------------------------------------------------------------------------- #
# Loaders.                                                                     #
# --------------------------------------------------------------------------- #
def load_gdpval_a_pile() -> list[ATask]:
    """Authored A-pile across the 4 subtypes (+ synthetic supplement, incl. one
    capability wall). Clean inputs/reference; real GDPval task_ids for lineage."""
    tasks: list[ATask] = [
        ATask(
            task_id="A_opt_01",
            subtype="option_pricing",
            prompt=(
                "Write `def solve(inputs):` returning {'call_price': <float>}, the "
                "Black-Scholes price of a European call for inputs S,K,r,sigma,T. "
                "Do not hardcode; your function will be run on other inputs too."
            ),
            inputs={"S": 100.0, "K": 100.0, "r": 0.05, "sigma": 0.2, "T": 1.0},
            reference=bs_call_reference,
            perturb=perturb_bs,
            tol=1e-3,
            gdpval_lineage="gdpval:c7d83f01 (Financial/Investment Analysts, American option pricing)",
        ),
        ATask(
            task_id="A_amort_01",
            subtype="amortization",
            prompt=(
                "Write `def solve(inputs):` returning {'payment','final_balance',"
                "'total_interest'} for a fixed-rate loan (principal, annual_rate, "
                "years, payments_per_year). final_balance must amortize to ~0."
            ),
            inputs={"principal": 500_000.0, "annual_rate": 0.06, "years": 30, "payments_per_year": 12},
            reference=loan_amort_reference,
            perturb=perturb_amort,
            tol=1e-2,
            gdpval_lineage="gdpval:7d7fc9a7 (Accountants and Auditors, prepaid amortization schedule)",
        ),
        ATask(
            task_id="A_audit_01",
            subtype="audit_metric",
            prompt=(
                "Write `def solve(inputs):` returning {'current_ratio','working_capital'} "
                "from current_assets and current_liabilities."
            ),
            inputs={"current_assets": 1_250_000.0, "current_liabilities": 800_000.0},
            reference=current_ratio_reference,
            perturb=perturb_ratio,
            tol=1e-6,
            gdpval_lineage="gdpval:Finance/Insurance (Accountants and Auditors, audit metric)",
        ),
        ATask(
            task_id="A_val_01",
            subtype="valuation",
            prompt=(
                "Write `def solve(inputs):` returning {'npv','irr'} for a cashflow "
                "stream `cashflows` (index 0 = initial outlay, negative) discounted "
                "at `rate`."
            ),
            inputs={"rate": 0.09, "cashflows": [-100_000_000.0, 28_000_000.0, 33_000_000.0, 39_000_000.0, 46_000_000.0]},
            reference=npv_reference,
            perturb=perturb_npv,
            tol={"npv": 1.0, "irr": 1e-4},  # NPV in dollars; IRR is dimensionless
            gdpval_lineage="gdpval:b78fd844 (Financial Managers, NPV/IRR capital budgeting, WACC=9%)",
        ),
        # ---- synthetic supplement (thin real A-pile -> add signal; iron law 1) ----
        ATask(
            task_id="A_opt_02",
            subtype="option_pricing",
            prompt=(
                "Write `def solve(inputs):` returning {'call_price': <float>}, the "
                "Black-Scholes price of a European call for inputs S,K,r,sigma,T. "
                "Do not hardcode; your function will be run on other inputs too."
            ),
            inputs={"S": 42.0, "K": 40.0, "r": 0.03, "sigma": 0.35, "T": 0.5},
            reference=bs_call_reference,
            perturb=perturb_bs,
            tol=1e-3,
            gdpval_lineage="gdpval:c7d83f01 (synthetic supplement)",
        ),
        ATask(
            task_id="A_val_02",
            subtype="valuation",
            prompt=(
                "Write `def solve(inputs):` returning {'npv','irr'} for a cashflow "
                "stream `cashflows` (index 0 = initial outlay, negative) discounted "
                "at `rate`."
            ),
            inputs={"rate": 0.12, "cashflows": [-5_000_000.0, 1_200_000.0, 1_500_000.0, 1_800_000.0, 2_400_000.0]},
            reference=npv_reference,
            perturb=perturb_npv,
            tol={"npv": 1.0, "irr": 1e-4},
            gdpval_lineage="gdpval:b78fd844 (synthetic supplement)",
        ),
        # ---- one capability wall: harness can NEVER lift this in mock ----
        ATask(
            task_id="A_amort_wall",
            subtype="amortization",
            prompt=(
                "Write `def solve(inputs):` returning {'payment','final_balance',"
                "'total_interest'} for a fixed-rate loan (principal, annual_rate, "
                "years, payments_per_year). final_balance must amortize to ~0."
            ),
            inputs={"principal": 750_000.0, "annual_rate": 0.085, "years": 7, "payments_per_year": 12},
            reference=loan_amort_reference,
            perturb=perturb_amort,
            tol=1e-2,
            gdpval_lineage="gdpval:7d7fc9a7 (hard edge case)",
            capability_wall=True,
        ),
    ]
    return tasks


# Offline fixtures used when the real GDPval download is unavailable.
_B_FIXTURES = [
    BTask(
        task_id="B_fix_advisory",
        subtype="valuation",
        prompt=(
            "A client (age 58, $1.2M portfolio, retiring in 7 years) asks for a "
            "written recommendation on shifting allocation toward fixed income. "
            "Produce an advisory memo."
        ),
        rubric="Quantifies the glide path; states assumptions; addresses sequence-of-returns risk; cites tax implications; recommendation is actionable.",
        rubric_items=[
            {"points": 2, "criterion": "Quantifies a concrete glide path (target equity/fixed-income mix over time)."},
            {"points": 1, "criterion": "States its assumptions (return, inflation, time horizon) explicitly."},
            {"points": 2, "criterion": "Addresses sequence-of-returns risk for someone retiring in 7 years."},
            {"points": 1, "criterion": "Cites tax implications of reallocating."},
            {"points": 1, "criterion": "Ends with a specific, actionable recommendation."},
        ],
        gdpval_lineage="gdpval:Personal Financial Advisors (offline fixture)",
    ),
    BTask(
        task_id="B_fix_valuation_memo",
        subtype="valuation",
        prompt="Write a one-page valuation memo for a SaaS acquisition target given the attached metrics.",
        rubric="Picks a defensible method (DCF/comps); states discount rate and why; sensitivity to key driver; clear recommended range.",
        rubric_items=[
            {"points": 2, "criterion": "Selects a defensible valuation method (DCF and/or comparables) and justifies it."},
            {"points": 2, "criterion": "States the discount rate / multiple used and the reasoning."},
            {"points": 1, "criterion": "Includes a sensitivity analysis on the key driver."},
            {"points": 1, "criterion": "Gives a clear recommended valuation range."},
        ],
        gdpval_lineage="gdpval:Financial and Investment Analysts (offline fixture)",
    ),
    BTask(
        task_id="B_fix_audit_findings",
        subtype="audit_metric",
        prompt="Summarize audit findings for a mid-cap retailer's liquidity position into a board-ready note.",
        rubric="Correctly interprets current/quick ratios; flags going-concern triggers; references the underlying figures; recommendation is specific.",
        rubric_items=[
            {"points": 2, "criterion": "Correctly interprets the current ratio and quick ratio."},
            {"points": 2, "criterion": "Flags any going-concern triggers in the liquidity position."},
            {"points": 1, "criterion": "References the underlying figures (not just qualitative claims)."},
            {"points": 1, "criterion": "Gives a specific recommendation to the board."},
        ],
        gdpval_lineage="gdpval:Accountants and Auditors (offline fixture)",
    ),
]

_GDPVAL_PARQUET_URL = (
    "https://huggingface.co/datasets/openai/gdpval/resolve/main/data/train-00000-of-00001.parquet"
)
# Local fork of the gold parquet (scripts/fork_gdpval.py); preferred over the
# network so runs are pinned to the snapshot in data/gdpval/MANIFEST.md.
_GDPVAL_LOCAL_PARQUET = Path(__file__).resolve().parent.parent / "data" / "gdpval" / "gdpval_gold.parquet"
# GDPval reference INPUT files, fetched by scripts/fetch_gdpval_reference_files.py to
# data/gdpval/reference_files/<task_id>/<basename>. Empty if not yet fetched.
_GDPVAL_REF_DIR = Path(__file__).resolve().parent.parent / "data" / "gdpval" / "reference_files"


def _local_reference_files(task_id: str, ref_entries) -> list[str]:
    """Map a row's reference_files entries to existing local paths (or []) ."""
    out: list[str] = []
    try:
        entries = list(ref_entries) if ref_entries is not None else []
    except TypeError:
        entries = []
    for e in entries:
        name = str(e).split("/")[-1]
        p = _GDPVAL_REF_DIR / str(task_id) / name
        if p.exists():
            out.append(str(p))
    return out


def _gold_deliverable_exts(del_entries) -> list[str]:
    """Distinct file extension(s) of the GDPval GOLD deliverable(s) = the REQUIRED
    output format(s). Empty list means the gold deliverable is text (no file)."""
    import os
    try:
        entries = list(del_entries) if del_entries is not None else []
    except TypeError:
        entries = []
    exts = {os.path.splitext(str(e))[1].lower() for e in entries}
    return sorted(e for e in exts if e)


def _load_gdpval_df():
    """Gold parquet as a DataFrame: local fork first, network fallback."""
    import pandas as pd  # optional dep

    if _GDPVAL_LOCAL_PARQUET.exists():
        return pd.read_parquet(_GDPVAL_LOCAL_PARQUET), "local fork"
    with urllib.request.urlopen(_GDPVAL_PARQUET_URL, timeout=30) as resp:
        return pd.read_parquet(io.BytesIO(resp.read())), "network"


# Finance/accounting-relevant GDPval occupations (across all 9 sectors). There is
# no "Economist" occupation in GDPval; the gold subset caps at 5 tasks/occupation.
_FIN_OCC_CORE = (
    "Accountants and Auditors",
    "Financial Managers",
    "Financial and Investment Analysts",
    "Personal Financial Advisors",
    "Securities",  # "Securities, Commodities, and Financial Services Sales Agents"
)
_FIN_OCC_BROAD = _FIN_OCC_CORE + ("Real Estate Brokers",)


def load_gdpval_finance(*, broad: bool = True, allow_download: bool = True) -> list[BTask]:
    """The ORIGINAL GDPval finance/accounting tasks (deliverable + rubric_json),
    soft-graded per-criterion. ~30 broad / ~25 core, from the open gold subset.

    These are real open-ended deliverables with NO hard verifier, so the loop is
    driven by the soft rubric-% grader (the observation firewall, law 2, still
    holds)."""
    stems = _FIN_OCC_BROAD if broad else _FIN_OCC_CORE
    if allow_download:
        try:
            df, src = _load_gdpval_df()
            mask = df["occupation"].apply(lambda o: any(s in str(o) for s in stems))
            sel = df[mask]
            out: list[BTask] = []
            for _, row in sel.iterrows():
                out.append(
                    BTask(
                        task_id=str(row["task_id"]),
                        subtype=str(row["occupation"]),  # per-occupation deltas (iron law 4)
                        prompt=str(row["prompt"]),
                        rubric=str(row.get("rubric_pretty", "")),
                        rubric_items=_parse_rubric_json(row.get("rubric_json")),
                        reference_files=_local_reference_files(row["task_id"], row.get("reference_files")),
                        deliverable_exts=_gold_deliverable_exts(row.get("deliverable_files")),
                        gdpval_lineage=f"gdpval:{row['occupation']} (real, original task)",
                    )
                )
            if out:
                print(f"[tasks] loaded {len(out)} ORIGINAL GDPval finance tasks "
                      f"({sel['occupation'].nunique()} occupations) from {src}")
                return out
        except Exception as exc:  # noqa: BLE001
            print(f"[tasks] real GDPval finance load failed ({type(exc).__name__}: {exc}); using offline fixtures")
    return list(_B_FIXTURES)
