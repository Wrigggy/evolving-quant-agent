"""Falsification: diff -> verdict -> strict gate -> rejected-edit buffer.

``evaluate_changes`` is ported (logic-for-logic) from the AHE reproduction's
``evolve.py:evaluate_changes``: it compares an edit's *predicted* fixes/risks
against what actually flipped/regressed and assigns the verdict taxonomy
EFFECTIVE / PARTIALLY_EFFECTIVE / MIXED / INEFFECTIVE / HARMFUL.

We add (SkillOpt): a STRICT gate (keep only on strict OOS improvement; ties
reject) and a rejected-edit buffer (rolled-back edits are remembered so the
proposer does not re-propose them; no semantic dedup — signature match only).

There is no selection split in v0 (by design): the OOS signal is the
perturbation-probe-robust score, so "overfit/hardcoded" edits are caught by the
probe rather than a held-out fold.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LEAKAGE_BLOCKED = "LEAKAGE_BLOCKED"


@dataclass
class EvalSummary:
    results: dict  # task_id -> TaskResult
    # task_id -> the produced deliverable text (B-pile); kept so the B-pile
    # debugger's critic can read each deliverable when attributing failures.
    deliverables: dict = field(default_factory=dict)

    def oos_ids(self) -> set[str]:
        return {tid for tid, r in self.results.items() if r.oos_pass}

    def total_oos(self) -> int:
        return len(self.oos_ids())

    def per_subtype(self) -> dict[str, tuple[int, int]]:
        agg: dict[str, list[int]] = {}
        for r in self.results.values():
            a = agg.setdefault(r.subtype, [0, 0])
            a[1] += 1
            if r.oos_pass:
                a[0] += 1
        return {k: (v[0], v[1]) for k, v in agg.items()}

    def per_subtype_mean(self) -> dict[str, float]:
        """Mean rubric score per subtype/occupation (finer than the binary pass count)."""
        agg: dict[str, list[float]] = {}
        for r in self.results.values():
            a = agg.setdefault(r.subtype, [0.0, 0])
            a[0] += r.score
            a[1] += 1
        return {k: (v[0] / v[1] if v[1] else 0.0) for k, v in agg.items()}

    def mean_variance(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.variance for r in self.results.values()) / len(self.results)


def compute_diff(prev: EvalSummary | None, cur: EvalSummary) -> dict:
    """flipped = OOS fail->pass; regressed = OOS pass->fail."""
    if prev is None:
        prev_oos: set[str] = set()
    else:
        prev_oos = prev.oos_ids()
    cur_oos = cur.oos_ids()
    flipped = sorted(cur_oos - prev_oos)
    regressed = sorted(prev_oos - cur_oos)
    return {"flipped": flipped, "regressed": regressed}


def evaluate_changes(edit, diff: dict) -> dict:
    """Ported from AHE evolve.py:evaluate_changes (single-edit form)."""
    predicted = list(edit.predicted_fixes)
    risks = list(edit.risk_tasks)
    flipped_set = set(diff.get("flipped", []))
    regressed_set = set(diff.get("regressed", []))

    actually_fixed = [t for t in predicted if t in flipped_set]
    still_failed = [t for t in predicted if t not in flipped_set]
    risk_realized = [t for t in risks if t in regressed_set]

    n_fixed = len(actually_fixed)
    n_predicted = len(predicted)
    n_risk_hit = len(risk_realized)

    if n_risk_hit > 0 and n_fixed == 0:
        verdict = "HARMFUL"
    elif n_risk_hit > 0 and n_fixed > 0:
        verdict = "MIXED"
    elif n_predicted > 0 and n_fixed == n_predicted:
        verdict = "EFFECTIVE"
    elif n_fixed > 0:
        verdict = "PARTIALLY_EFFECTIVE"
    else:
        verdict = "INEFFECTIVE"

    attributed = set(predicted) | set(risks)
    unattributed_regressions = sorted(regressed_set - attributed)
    # Unattributed regressions are harm the proposer did not predict. ANY verdict
    # carrying them is downgraded so side-effect breakage cannot hide behind a net
    # OOS gain (PLAN iron law 4: "lift one, regress another -> visible, not kept").
    if unattributed_regressions:
        verdict = "MIXED" if n_fixed > 0 else "HARMFUL"

    return {
        "change_id": f"ch::{edit.slot}:{edit.component_name}",
        "predicted_fixes": predicted,
        "actually_fixed": actually_fixed,
        "still_failed": still_failed,
        "predicted_risks": risks,
        "risk_realized": risk_realized,
        "unattributed_regressions": unattributed_regressions,
        "hit_rate": f"{n_fixed}/{n_predicted}" if n_predicted else "0/0",
        "verdict": verdict,
    }


def decide_keep(evaluation: dict, prev_total: int, cur_total: int) -> bool:
    """Strict gate (SkillOpt): keep only if verdict is (PARTIALLY_)EFFECTIVE, total
    OOS strictly improved, AND there are no unattributed regressions. Ties /
    non-improvement / any unpredicted breakage -> reject."""
    verdict = evaluation["verdict"]
    if verdict not in ("EFFECTIVE", "PARTIALLY_EFFECTIVE"):
        return False
    if evaluation.get("unattributed_regressions"):
        return False
    return cur_total > prev_total


def decide_keep_soft(inc_mean: float, cand_mean: float, noise_margin: float) -> bool:
    """Soft-mode gate: keep only if the AGGREGATE mean rubric score improves beyond
    the estimated eval noise floor. The binary per-task gate (reject on any
    unattributed regression) is too strict for a noisy soft signal — the judge +
    deliverable regenerate each eval, so a few spurious per-task regressions appear
    on every edit. Here we tolerate those and credit a real aggregate gain."""
    return cand_mean > inc_mean + noise_margin


def decide_keep_paired(inc_scores: dict, cand_scores: dict, *, noise_margin: float = 0.0,
                       stability_lambda: float = 0.0, inc_vars: dict = None,
                       cand_vars: dict = None, n_resamples: int = 2000, seed: int = 7) -> dict:
    """Protocol-v2 keep gate: a PAIRED test on per-task deltas instead of a bare
    mean-vs-floor comparison (field norm — ADAS keeps by bootstrap CI; measured on
    GDPval the mean-delta sigma exceeds the 0.05 floor, so a floor-only gate is ~1
    sigma from noise). Keep iff BOTH:
      (1) mean stability-penalized delta > noise_margin, where each side's objective
          is mean(score) - stability_lambda * mean(per-task cross-sample spread) —
          the "stable high output" objective (spreads need n_samples >= 2; with
          lambda 0 or no variances this is the plain mean delta), AND
      (2) the seeded-bootstrap 5th percentile of the mean per-task delta > 0
          (one-sided 95%: the gain direction survives resampling).
    Returns {kept, mean_delta, ci_lo, objective_delta, n} for the manifest."""
    import random

    common = sorted(set(inc_scores) & set(cand_scores))
    if not common:
        return {"kept": False, "mean_delta": 0.0, "ci_lo": 0.0, "objective_delta": 0.0, "n": 0}
    deltas = [cand_scores[t] - inc_scores[t] for t in common]
    n = len(deltas)
    mean_delta = sum(deltas) / n
    instab = 0.0
    if stability_lambda and (inc_vars or cand_vars):
        iv = sum((inc_vars or {}).get(t, 0.0) for t in common) / n
        cv = sum((cand_vars or {}).get(t, 0.0) for t in common) / n
        instab = stability_lambda * (cv - iv)   # candidate more unstable -> penalty
    objective_delta = mean_delta - instab
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(deltas) for _ in range(n)) / n for _ in range(n_resamples))
    ci_lo = means[int(0.05 * n_resamples)]
    kept = objective_delta > noise_margin and ci_lo > 0
    return {"kept": kept, "mean_delta": round(mean_delta, 4), "ci_lo": round(ci_lo, 4),
            "objective_delta": round(objective_delta, 4), "n": n}


@dataclass
class RejectedEditBuffer:
    """SkillOpt rejected-edit buffer. No embedding/semantic dedup — signature
    match only — exactly as SkillOpt delegates dedup to the proposer LLM."""

    entries: list[dict] = field(default_factory=list)
    _sigs: set[str] = field(default_factory=set)

    def blocks(self, edit) -> bool:
        return edit.signature() in self._sigs

    def add(self, edit, verdict: str, score_before: int, score_after: int, failure_pattern: str) -> None:
        self._sigs.add(edit.signature())
        self.entries.append(
            {
                "signature": edit.signature(),
                "summary": edit.summary or f"{edit.op} {edit.slot}:{edit.component_name}",
                "verdict": verdict,
                "score_before": score_before,
                "score_after": score_after,
                "failure_pattern": failure_pattern,
            }
        )

    def render(self) -> str:
        if not self.entries:
            return "(none yet)"
        lines = ["These edits were already tried and FALSIFIED. Do NOT re-propose them:"]
        for e in self.entries:
            lines.append(
                f"- [{e['verdict']}] {e['summary']} "
                f"(OOS {e['score_before']}->{e['score_after']}; {e['failure_pattern']})"
            )
        return "\n".join(lines)
