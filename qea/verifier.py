"""Verifiers + the verifier router's two endpoints.

HardVerifier (A-pile, drives evolution): recomputes the deterministic reference
and runs the candidate solution on *perturbed* inputs (the perturbation probe /
integrity guard). A hardcoded constant matches the base inputs but fails the
probe, so ``oos_pass`` (probe-robust correctness) is the OOS signal that stands
in for a held-out split (we deliberately do not use a selection split in v0).

SoftJudge (B-pile grader): an LLM judge scoring a deliverable as a continuous
rubric percentage (earned/total points, per-criterion verdicts exposed). This is
the grader the GDPval benchmark drives the loop with; there is no hard verifier
for open-ended deliverables.

k-repeat denoising (iron law 3): hard scores are clean (variance ~0); soft
scores are repeated k times and we take the median + record the variance, so the
"soft signal is noisy in the loop" effect is measured, not assumed.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import re
import signal
import statistics
from dataclasses import dataclass


def _stable_unit(*parts) -> float:
    """Deterministic float in [0,1) from arbitrary parts (process-independent)."""
    h = hashlib.md5(":".join(str(p) for p in parts).encode()).hexdigest()
    return (int(h[:8], 16) % 10_000) / 10_000.0


def _parse_json_obj(txt: str) -> dict | None:
    """First balanced JSON object in txt (handles prose/fences), or None."""
    dec = json.JSONDecoder()
    i = txt.find("{")
    while i >= 0:
        try:
            obj, _ = dec.raw_decode(txt[i:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        i = txt.find("{", i + 1)
    return None


def _truthy(v) -> bool:
    if isinstance(v, dict):          # reason-mode verdict: {"pass": bool, "reason": str}
        v = v.get("pass")
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("true", "yes", "1", "y", "satisfied")
    return False

def build_rubric_prompt(task, deliverable: str, items: list, *, has_images: bool = False,
                        with_reasons: bool = False) -> str:
    """Single source of truth for the per-criterion rubric prompt (text + multimodal).

    ``with_reasons`` asks the judge to justify each verdict in one sentence. The
    reasons are a HUMAN DEBUG artifact only (judge_reasons.json next to the eval);
    they must never be fed to the debugger/evolve agent — a reason can paraphrase
    expected values, which would violate the observation firewall."""
    lines = [f"{i + 1}. (+{c['points']}) {c['criterion']}" for i, c in enumerate(items)]
    img_note = (" Rendered pages of the deliverable are attached as images; "
                "its extracted text is included below." if has_images else "")
    if with_reasons:
        shape = ('Return ONLY a JSON object mapping each criterion number (as a string) to '
                 'an object {"pass": true|false, "reason": "<ONE short sentence naming the '
                 'specific evidence for the verdict>"}.')
    else:
        shape = ('Return ONLY a JSON object mapping each criterion number (as a string) to '
                 "true or false.")
    return (
        "You are grading a finance deliverable against an itemized GDPval rubric. "
        "For EACH numbered criterion, decide whether the deliverable satisfies it. "
        + shape + img_note + "\n\n"
        f"TASK:\n{task.prompt}\n\nRUBRIC:\n" + "\n".join(lines) +
        f"\n\nDELIVERABLE:\n{deliverable}\n\nJSON:"
    )


def rubric_reasons(txt: str, items: list) -> dict:
    """Extract the judge's per-criterion reasons (reason-mode responses only) as
    {criterion_number: {"pass": bool, "reason": str, "criterion": str}}. Debug-file
    payload — keep OUT of TaskEval / the debugger evidence path."""
    verdicts = _parse_json_obj(txt) or {}
    out = {}
    for i, c in enumerate(items):
        v = verdicts.get(str(i + 1))
        if v is None:
            continue
        out[str(i + 1)] = {"pass": _truthy(v),
                           "reason": (v.get("reason", "") if isinstance(v, dict) else ""),
                           "criterion": c["criterion"]}
    return out


def score_rubric(txt: str, items: list) -> tuple[float, dict]:
    """Parse judge JSON -> (points-weighted continuous fraction in [0,1], verdicts).

    GDPval rubrics include authored NEGATIVE (penalty) criteria. ``earned`` sums the
    points of satisfied criteria (penalties subtract when their bad condition holds);
    the denominator is the POSITIVE-point total (max achievable), so a flawless
    deliverable scores 1.0 (not >1). Clamped to [0,1]."""
    raw = _parse_json_obj(txt) or {}
    # Normalize to plain bools: reason-mode responses carry {"pass": bool, "reason": str}
    # objects, but TaskEval.verdicts consumers (debugger, evidence builder) test
    # `is False` — reasons must never travel past this point (firewall).
    verdicts = {k: _truthy(v) for k, v in raw.items()}
    earned = sum(c["points"] for i, c in enumerate(items) if verdicts.get(str(i + 1)))
    pos_total = sum(c["points"] for c in items if c["points"] > 0) or 1.0
    return max(0.0, min(1.0, earned / pos_total)), verdicts


# Mock soft-judge pass threshold and the jitter amplitude used to model the
# non-determinism of an LLM judge (iron law 2 / 3 illustration).
_SOFT_PASS = 0.60
_SOFT_JITTER = 0.08


@dataclass
class TaskResult:
    task_id: str
    subtype: str
    pile: str
    base_pass: bool
    probe_pass: bool
    oos_pass: bool
    score: float
    variance: float = 0.0
    error: str | None = None
    criterion_verdicts: dict | None = None  # B-pile: {criterion_number: bool}, for the debugger


# --------------------------------------------------------------------------- #
# Real-mode sandboxed execution of the agent's `solve(inputs)`.               #
# v0 primitive: restricted builtins + SIGALRM timeout (main thread). ROADMAP: #
# real isolation (subprocess / container / E2B).                              #
# --------------------------------------------------------------------------- #
class _Timeout(Exception):
    pass


# Modules a candidate solution may import (models naturally write `import math`).
_ALLOWED_MODULES = {"math", "cmath", "statistics", "decimal", "fractions", "numbers"}


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
    root = name.split(".")[0]
    if root not in _ALLOWED_MODULES:
        raise ImportError(f"import of {name!r} is not allowed in the v0 sandbox")
    return importlib.import_module(name)


def safe_exec_solve(src: str, inputs: dict, timeout: float = 5.0) -> dict:
    safe_builtins = {
        "abs": abs, "min": min, "max": max, "sum": sum, "len": len, "range": range,
        "round": round, "float": float, "int": int, "pow": pow, "enumerate": enumerate,
        "list": list, "dict": dict, "tuple": tuple, "zip": zip, "map": map, "sorted": sorted,
        "str": str, "bool": bool, "any": any, "all": all, "reversed": reversed,
        "isinstance": isinstance, "type": type, "divmod": divmod, "filter": filter,
        "__import__": _safe_import,  # whitelist-gated; allows `import math` etc.
    }
    # Pre-inject the allowed modules so bare references work too (math is the common one).
    g: dict = {"__builtins__": safe_builtins}
    for _m in _ALLOWED_MODULES:
        g[_m] = importlib.import_module(_m)
    def _handler(signum, frame):  # noqa: ARG001
        raise _Timeout()
    had_alarm = hasattr(signal, "SIGALRM")
    if had_alarm:
        old = signal.signal(signal.SIGALRM, _handler)
        signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        exec(src, g)  # noqa: S102 - candidate code from our own model, sandboxed
        solve = g.get("solve")
        if not callable(solve):
            raise ValueError("no callable solve(inputs) defined")
        out = solve(dict(inputs))
        if not isinstance(out, dict):
            raise ValueError("solve must return a dict of {metric: value}")
        return out
    finally:
        if had_alarm:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)


def _metrics_match(got: dict, expected: dict, tol) -> bool:
    """tol may be a float (all metrics) or a dict {metric: tol} (per-metric)."""
    for k, exp in expected.items():
        if k not in got:
            return False
        a = got[k]
        try:
            a = float(a)
        except (TypeError, ValueError):
            return False
        if math.isnan(exp):
            if not math.isnan(a):
                return False
            continue
        if math.isnan(a):
            return False
        if math.isinf(exp) or math.isinf(a):
            if a != exp:               # +inf vs -inf must not match
                return False
            continue
        t = tol.get(k, 1e-4) if isinstance(tol, dict) else tol
        if abs(a - exp) > t + 1e-9 * max(abs(a), abs(exp)):
            return False
    return True


# --------------------------------------------------------------------------- #
# HardVerifier.                                                                #
# --------------------------------------------------------------------------- #
class HardVerifier:
    def score(self, task, solution, harness, *, mock: bool, k: int = 2) -> TaskResult:  # noqa: ARG002
        if mock:
            return self._score_mock(task, solution)
        return self._score_real(task, solution, k=k)

    def _score_mock(self, task, solution: dict) -> TaskResult:
        # solution sentinel from the mock quant_agent:
        #   {"runnable": bool, "parameterized": bool, "memorized": bool}
        runnable = bool(solution.get("runnable", False))
        parameterized = bool(solution.get("parameterized", False))
        memorized = bool(solution.get("memorized", False))
        if getattr(task, "capability_wall", False):
            # A wall is a base-capability gap. Memorizing the base answer can make
            # the BASE inputs pass, but the perturbation probe still fails -> oos
            # stays False. This is how the probe (not a selection split) kills the
            # overfit/hardcode edit in v0.
            base_pass = memorized
            probe_pass = False
            err = "wall: base passes via memorization only, probe fails" if memorized else "capability_wall (base model cannot solve; harness cannot fix)"
        elif not runnable:
            base_pass = probe_pass = False
            err = "code_exec unavailable/broken"
        else:
            base_pass = True
            probe_pass = parameterized
            err = None if probe_pass else "hardcoded: passes base, fails perturbation probe"
        oos = probe_pass
        score = 1.0 if oos else (0.5 if base_pass else 0.0)
        return TaskResult(task.task_id, task.subtype, "A", base_pass, probe_pass, oos, score, 0.0, err)

    def _score_real(self, task, src: str, *, k: int) -> TaskResult:
        # base correctness
        try:
            got = safe_exec_solve(src, task.inputs)
        except Exception as exc:  # noqa: BLE001
            return TaskResult(task.task_id, task.subtype, "A", False, False, False, 0.0, 0.0, f"base exec: {type(exc).__name__}: {exc}")
        base_pass = _metrics_match(got, task.reference(task.inputs), task.tol)
        # perturbation probe: must also be correct on k perturbed instances
        probe_pass = base_pass
        if base_pass:
            for seed in range(1, k + 1):
                pin = task.perturb(task.inputs, seed)
                try:
                    pgot = safe_exec_solve(src, pin)
                except Exception:  # noqa: BLE001
                    probe_pass = False
                    break
                if not _metrics_match(pgot, task.reference(pin), task.tol):
                    probe_pass = False
                    break
        oos = base_pass and probe_pass
        score = 1.0 if oos else (0.5 if base_pass else 0.0)
        err = None if oos else ("hardcoded: base ok, probe failed" if base_pass else "base wrong")
        return TaskResult(task.task_id, task.subtype, "A", base_pass, probe_pass, oos, score, 0.0, err)


# --------------------------------------------------------------------------- #
# SoftJudge.                                                                   #
# --------------------------------------------------------------------------- #
class SoftJudge:
    def __init__(self, llm=None) -> None:
        self.llm = llm

    def score(self, task, deliverable, harness, *, mock: bool, k: int = 2) -> TaskResult:
        verdicts: dict = {}
        if mock:
            samples = [self._mock_sample(task, harness, r) for r in range(k)]
        else:
            pairs = [self._real_sample(task, deliverable) for _ in range(k)]
            samples = [p[0] for p in pairs]
            # Single-sample snapshot: per-call verdicts may disagree across k and
            # are not merged; a snapshot is sufficient for the debugger's
            # observation (the SCORE is the median; verdicts are diagnostic only).
            verdicts = pairs[-1][1]
        med = statistics.median(samples)
        var = statistics.pvariance(samples) if len(samples) > 1 else 0.0
        thresh = _SOFT_PASS  # reporting-only pass threshold (same 0.60 for mock + real)
        oos = med >= thresh
        return TaskResult(task.task_id, task.subtype, "B", oos, oos, oos, med, var, None,
                          criterion_verdicts=verdicts)

    def _mock_sample(self, task, harness, repeat: int) -> float:
        disciplined = harness.has("validator", "integrity_guard")
        base = task.mock_disciplined_score if disciplined else task.mock_base_score
        # deterministic, repeat-dependent jitter: models LLM-judge non-determinism.
        # Uses a stable hash (Python's hash() is salted per process).
        jitter = _SOFT_JITTER * math.sin(_stable_unit(task.task_id, repeat) * math.tau)
        return max(0.0, min(1.0, base + jitter))

    def _real_sample(self, task, deliverable: str) -> tuple[float, dict]:
        """GDPval rubric grading: per-criterion satisfied? -> points-weighted CONTINUOUS
        fraction in [0,1] (no parity quantization). Returns (fraction, verdicts)."""
        items = getattr(task, "rubric_items", None) or []
        if not items:
            return self._real_holistic(task, deliverable), {}
        prompt = build_rubric_prompt(task, deliverable, items)
        txt = self.llm.complete(prompt, role="judge")
        return score_rubric(txt, items)

    def _real_holistic(self, task, deliverable: str) -> float:
        prompt = (
            "You are grading a finance deliverable against a rubric. Return ONLY a "
            "number in [0,1] = fraction of rubric satisfied.\n\n"
            f"RUBRIC:\n{task.rubric}\n\nDELIVERABLE:\n{deliverable}\n\nScore:"
        )
        txt = self.llm.complete(prompt, role="judge")
        m = re.search(r"\d*\.?\d+", txt)
        if not m:
            return 0.0
        try:
            return max(0.0, min(1.0, float(m.group())))
        except ValueError:
            return 0.0


# --------------------------------------------------------------------------- #
# LeakageGuard.                                                                #
# --------------------------------------------------------------------------- #
class LeakageGuard:
    """Universal evaluator-layer anti-cheat: rejects an edit whose component content
    overlaps the benchmark's answer_corpus (rubric/answer material) above a
    threshold. n-gram (token-shingle) containment; no embeddings (v1).

    v1 LIMITATIONS (revisit when tuning `threshold`, currently an untuned
    placeholder): an edit shorter than `n` tokens has no shingles and is never
    flagged (a <5-word verbatim fragment slips through); detection is lexical
    only (paraphrase evades it)."""

    def __init__(self, answer_corpus: list[str], threshold: float = 0.6, n: int = 5) -> None:
        self.n = n
        self.threshold = threshold
        self._corpus_ngrams = [self._ngrams(c) for c in answer_corpus if c]

    @staticmethod
    def _norm(text: str) -> list[str]:
        return "".join(ch.lower() if ch.isalnum() else " " for ch in text).split()

    def _ngrams(self, text: str) -> set:
        toks = self._norm(text)
        return {" ".join(toks[i:i + self.n]) for i in range(len(toks) - self.n + 1)}

    def is_leak(self, edit) -> bool:
        cand = self._ngrams(edit.content)
        if not cand:
            return False
        for corp in self._corpus_ngrams:
            if not corp:
                continue
            overlap = len(cand & corp) / len(cand)   # containment of edit in corpus
            if overlap >= self.threshold:
                return True
        return False
