# QEA Grader/Evaluator split + B-pile debugger — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the tangled "verifier" into a benchmark-owned **grader** (absolute rubric %) and a loop-side **evaluator** (keep/rollback), delete the pairwise gate, add a firewalled **B-pile debugger** and a universal **leakage guard**, and remove the A-pile benchmark (keeping a synthetic offline fixture).

**Architecture:** Three layers — `grader` (benchmark property, neutral judge model, absolute score + per-criterion verdicts) → `evaluator` (loop logic: `decide_keep_soft` on rubric %, leakage guard, verdict taxonomy) → `loop` (benchmark-agnostic driver). Ground truth flows only into diagnosis (firewall); a leaked answer can only be caught by auditing the *edit content*, so the leakage guard is an evaluator-layer mechanism parameterized by each benchmark's `answer_corpus`.

**Tech Stack:** Python 3.10+, pure-stdlib core, `pytest`, optional `openai`/`pandas`/`pyarrow` extras. Spec: `docs/superpowers/specs/2026-06-15-qea-grader-evaluator-bdebugger-design.md`.

**Scope note (spec deviation, confirmed):** GDPval gold deliverables are binary xlsx/pptx behind URLs, not text. The v1 leakage `answer_corpus` is **rubric-criteria text only**; gold-deliverable-text extraction is deferred. All work happens on branch `qea/grader-evaluator-bdebugger`.

---

## File map

- `qea/verifier.py` → grading layer: drop `_quantize_parity` from real scoring; expose per-criterion verdicts; **delete `PairwiseJudge` + `bt_elo`**; add `Critic`; add `LeakageGuard`. (File keeps its name; conceptually "grader".)
- `qea/falsify.py` → evaluator layer: keep `evaluate_changes`/`compute_diff`/buffer/`decide_keep_soft`; **delete `decide_keep_pairwise`**; add `LEAKAGE_BLOCKED` constant.
- `qea/agents.py` → B-pile `diagnose` branch (verdicts + critic → tags), dual-mode attribution, firewall in `_propose_real`.
- `qea/harness.py` → add `Harness.signature()` for the deliverable cache.
- `qea/benchmark.py` (**new**) → `Benchmark` dataclass (`tasks`, `grader`, `answer_corpus`, `debugger_kind`) + `gdpval_benchmark()` + `synthetic_fixture_benchmark()`.
- `qea/loop.py` → rewire `run_gdpval_soft` to % gate + B-debugger + leakage guard + worker cache; **remove `run_ablation`/`run_arm`/`ArmResult`/`AblationResult`**; add `run_synthetic_fixture` for `--mock`.
- `qea/tasks.py` → drop real A-pile loader from the live path (keep authored tasks as the synthetic fixture); add `rubric_corpus()` helper for the leakage corpus.
- `run.py` → `--mock` drives the synthetic fixture; `--real` drives `run_gdpval_soft`; remove ablation printing.
- `tests/test_smoke.py` → remove pairwise/ablation tests; update grader test; add new-mechanism tests.

---

## Task 1: Grader returns a continuous % and exposes per-criterion verdicts

**Files:**
- Modify: `qea/verifier.py` (`TaskResult`, `SoftJudge._real_sample`, `SoftJudge.score`, `_real_holistic`)
- Test: `tests/test_smoke.py::test_gdpval_rubric_grader_continuous`

- [ ] **Step 1: Update the failing grader test** — replace `test_gdpval_rubric_grader_weighted` with the continuous-% version.

```python
def test_gdpval_rubric_grader_continuous():
    from qea.tasks import BTask, _parse_rubric_json
    from qea.verifier import SoftJudge

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
    # earned 2+1=3 of total 4 -> 0.75 (NO quantize to {0,0.5,1})
    assert abs(r.score - 0.75) < 1e-9
    # per-criterion verdicts are exposed on the result
    assert r.criterion_verdicts == {"1": True, "2": False, "3": True}
```

- [ ] **Step 2: Run it, expect FAIL** — `pytest tests/test_smoke.py::test_gdpval_rubric_grader_continuous -v` → FAIL (`score==0.5`, no `criterion_verdicts`).

- [ ] **Step 3: Add the `criterion_verdicts` field to `TaskResult`** (`qea/verifier.py`):

```python
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
```

- [ ] **Step 4: Make `_real_sample` return `(frac, verdicts)` without quantizing** (`qea/verifier.py`):

```python
def _real_sample(self, task, deliverable: str) -> tuple[float, dict]:
    """GDPval rubric grading: per-criterion satisfied? -> points-weighted CONTINUOUS
    fraction in [0,1] (no parity quantization). Returns (fraction, verdicts)."""
    items = getattr(task, "rubric_items", None) or []
    if not items:
        return self._real_holistic(task, deliverable), {}
    lines = [f"{i + 1}. (+{c['points']}) {c['criterion']}" for i, c in enumerate(items)]
    prompt = (
        "You are grading a finance deliverable against an itemized GDPval rubric. "
        "For EACH numbered criterion, decide whether the deliverable satisfies it. "
        'Return ONLY a JSON object mapping each criterion number (as a string) to '
        "true or false.\n\n"
        f"TASK:\n{task.prompt}\n\nRUBRIC:\n" + "\n".join(lines) +
        f"\n\nDELIVERABLE:\n{deliverable}\n\nJSON:"
    )
    txt = self.llm.complete(prompt, role="judge")
    verdicts = _parse_json_obj(txt) or {}
    earned = sum(c["points"] for i, c in enumerate(items) if _truthy(verdicts.get(str(i + 1))))
    total = sum(c["points"] for c in items) or 1.0
    return earned / total, verdicts
```

- [ ] **Step 5: Make `_real_holistic` continuous** — change its return from `_quantize_parity(...)` to the raw clamped float:

```python
        return max(0.0, min(1.0, float(m.group())))
```

(and `return 0.0` paths stay). Then **delete the now-unused `_quantize_parity` and `_PARITY_HIGH`/`_PARITY_LOW`** if no other reference remains (grep first: `grep -n "_quantize_parity\|_PARITY" qea/`).

- [ ] **Step 6: Update `SoftJudge.score` to collect verdicts + continuous median** (`qea/verifier.py`):

```python
def score(self, task, deliverable, harness, *, mock: bool, k: int = 2) -> TaskResult:
    verdicts: dict = {}
    if mock:
        samples = [self._mock_sample(task, harness, r) for r in range(k)]
    else:
        pairs = [self._real_sample(task, deliverable) for _ in range(k)]
        samples = [p[0] for p in pairs]
        verdicts = pairs[-1][1]  # last sample's per-criterion verdicts (for the debugger)
    med = statistics.median(samples)
    var = statistics.pvariance(samples) if len(samples) > 1 else 0.0
    thresh = _SOFT_PASS if mock else 0.6  # reporting-only pass threshold (matches docs)
    oos = med >= thresh
    return TaskResult(task.task_id, task.subtype, "B", oos, oos, oos, med, var, None,
                      criterion_verdicts=verdicts)
```

- [ ] **Step 7: Run the test, expect PASS** — `pytest tests/test_smoke.py::test_gdpval_rubric_grader_continuous -v` → PASS.

- [ ] **Step 8: Commit**

```bash
git add qea/verifier.py tests/test_smoke.py
git commit -m "feat(grader): continuous rubric % + exposed per-criterion verdicts"
```

---

## Task 2: Evaluator reverts to the % gate; delete the pairwise machinery

**Files:**
- Modify: `qea/verifier.py` (delete `PairwiseJudge`, `bt_elo`), `qea/falsify.py` (delete `decide_keep_pairwise`), `qea/loop.py` (`run_gdpval_soft`, `SoftRunResult`), `qea/llm.py` (none), `run.py` (soft printing)
- Test: `tests/test_smoke.py` (remove pairwise tests; rewrite the mock end-to-end test)

- [ ] **Step 1: Delete the pairwise tests** from `tests/test_smoke.py`:
remove `test_pairwise_judge_deanonymizes_correctly`, `test_pairwise_judge_tie_and_garbage_default_to_tie`, `test_bt_elo_anchoring`, `test_decide_keep_pairwise_excludes_ties_and_needs_margin`, `test_match_set_parallel_real_path`, `test_gdpval_soft_mock_pairwise_gate`.

- [ ] **Step 2: Write the new mock end-to-end test** (replaces the pairwise one):

```python
def test_gdpval_soft_mock_pct_gate(tmp_path):
    # End-to-end mock: iter-1 integrity_guard lifts the mock soft score
    # (0.45 -> 0.72), beating the noise floor, so the % gate keeps it and the
    # mean-score trajectory rises.
    from qea.loop import Config, run_gdpval_soft
    res = run_gdpval_soft(Config(mock=True, n_iters=2, k=2, results_dir=str(tmp_path)))
    assert res.n_kept >= 1
    assert res.mean_score_trajectory[-1] > res.mean_score_trajectory[0]
    assert not hasattr(res, "final_elo_vs_seed")  # pairwise fields gone
```

- [ ] **Step 3: Run it, expect FAIL** — `pytest tests/test_smoke.py::test_gdpval_soft_mock_pct_gate -v` → FAIL (import/field errors).

- [ ] **Step 4: Delete `PairwiseJudge` and `bt_elo`** from `qea/verifier.py` (the whole `class PairwiseJudge` block and the `def bt_elo`). Also delete the `_stable_unit`-only-for-pairwise usage if now unused (grep `_stable_unit` — it is still used by `_mock_sample` jitter, so KEEP it).

- [ ] **Step 5: Delete `decide_keep_pairwise`** from `qea/falsify.py`.

- [ ] **Step 6: Simplify `SoftRunResult`** (`qea/loop.py`) — remove pairwise fields:

```python
@dataclass
class SoftRunResult:
    n_tasks: int
    oos_trajectory: list[int]
    mean_score_trajectory: list[float]   # the GATE signal now (was diagnostic)
    records: list[IterationRecord]
    final_per_occupation: dict
    final_mean_score: float
    n_kept: int
    n_rolled_back: int
    n_blocked: int
    noise_margin: float = 0.0
    final_per_occupation_mean: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["records"] = [r.to_dict() if isinstance(r, IterationRecord) else r for r in self.records]
        return d
```

- [ ] **Step 7: Rewrite the decision block in `run_gdpval_soft`** — replace the pairwise gate + replication + anchor/Elo with `decide_keep_soft`. The seed/noise setup keeps `noise_margin` (already computed at `loop.py:428-429`); delete the `pairwise.match_set` null/anchor calls, `pw_margin`, `wr_traj`, `anchor_w/l`. The per-iteration decision becomes:

```python
            candidate = incumbent.clone(); candidate.apply(edit)
            cand_eval = evaluate(candidate, tasks, mock=cfg.mock, llm=llm, hard=hard, soft=soft, k=cfg.k, label=f"iter{it}")
            diff = compute_diff(inc_eval, cand_eval)
            evaluation = evaluate_changes(edit, diff)  # verdict taxonomy, audit trail
            inc_mean, cand_mean = _mean_score(inc_eval), _mean_score(cand_eval)
            kept = decide_keep_soft(inc_mean, cand_mean, noise_margin)
            evaluation["soft_gate"] = {
                "inc_mean": round(inc_mean, 4), "cand_mean": round(cand_mean, 4),
                "noise_margin": round(noise_margin, 4), "kept": kept,
            }
            manifest = attach_verdict(build_manifest(it, "evolve_agent", edit, "gdpval_soft"), evaluation, kept)
            if kept:
                n_kept += 1; incumbent, inc_eval = candidate, cand_eval
            else:
                n_rb += 1
                buffer.add(edit, evaluation["verdict"], inc_eval.total_oos(), cand_eval.total_oos(), _failure_pattern(evaluation, edit))
            oos_traj.append(inc_eval.total_oos()); ms_traj.append(round(_mean_score(inc_eval), 4))
```

Update the `import` line (`loop.py:23-30`) to drop `decide_keep_pairwise`, `PairwiseJudge`, `bt_elo`; the seed setup to drop the `null`/`pw_margin`/`wr_traj`/`anchor` lines; the blocked-branch to drop `wr_traj.append`; `_write_resume` to drop pairwise args; and the final `SoftRunResult(...)` construction to match the new fields. Remove the `_gen_deliverables` replication usage (the function may stay for the resume anchor rebuild — grep; if now unused, delete it and its resume-branch callers).

- [ ] **Step 8: Update `run.py` soft printing** — in `_print_soft`, drop the pairwise/Elo/winrate lines; print `mean_score_trajectory` as the gate signal. In `main()`'s real branch, replace the winrate verdict with: `rose = res.mean_score_trajectory[-1] > res.mean_score_trajectory[0] + res.noise_margin`.

- [ ] **Step 9: Run the new test + full suite for the soft path** — `pytest tests/test_smoke.py::test_gdpval_soft_mock_pct_gate tests/test_smoke.py::test_soft_gate_noise_aware -v` → PASS. (Other tests still reference removed symbols; they are fixed in Task 7.)

- [ ] **Step 10: Commit**

```bash
git add qea/verifier.py qea/falsify.py qea/loop.py run.py tests/test_smoke.py
git commit -m "feat(evaluator): revert GDPval gate to decide_keep_soft; delete pairwise machinery"
```

---

## Task 3: Worker deliverable cache (kills regeneration noise)

**Files:**
- Modify: `qea/harness.py` (add `signature()`), `qea/loop.py` (cache in `evaluate`/`_score_one`)
- Test: `tests/test_smoke.py::test_deliverable_cache_stable_per_harness`

- [ ] **Step 1: Write the failing test**:

```python
def test_deliverable_cache_stable_per_harness():
    # The same harness must yield the SAME deliverable within a run (cache hit),
    # so re-evaluating an unchanged harness does not wobble from regeneration.
    from qea.harness import seed_harness
    from qea.loop import _DeliverableCache
    calls = {"n": 0}

    def gen():
        calls["n"] += 1
        return f"deliverable v{calls['n']}"

    cache = _DeliverableCache()
    h = seed_harness()
    a = cache.get_or_make("t1", h, gen)
    b = cache.get_or_make("t1", h, gen)
    assert a == b and calls["n"] == 1            # second call is a cache hit
    # a different harness must miss the cache and regenerate
    from qea.harness import Edit
    h2 = h.clone(); h2.apply(Edit(op="add", slot="memory", component_name="kb", content="x"))
    c = cache.get_or_make("t1", h2, gen)
    assert c == "deliverable v2" and calls["n"] == 2
```

- [ ] **Step 2: Run it, expect FAIL** — no `_DeliverableCache`, no `signature()`.

- [ ] **Step 3: Add `Harness.signature()`** (`qea/harness.py`):

```python
    def signature(self) -> str:
        """Stable content hash of the whole harness (for the deliverable cache)."""
        import json
        return hashlib.md5(json.dumps(self.to_state(), sort_keys=True).encode()).hexdigest()
```

- [ ] **Step 4: Add `_DeliverableCache`** (`qea/loop.py`, near the top):

```python
class _DeliverableCache:
    """Caches a worker deliverable by (task_id, harness signature) so the same
    harness always produces the same text within a run — removes the regeneration
    noise that caused single-sample regression-to-mean in the % gate."""
    def __init__(self) -> None:
        self._d: dict[tuple[str, str], str] = {}

    def get_or_make(self, task_id: str, harness, make) -> str:
        key = (task_id, harness.signature())
        if key not in self._d:
            self._d[key] = make()
        return self._d[key]
```

- [ ] **Step 5: Thread the cache through `evaluate`/`_score_one`** — `run_gdpval_soft` creates one `_DeliverableCache()` and passes it into each `evaluate(...)`. In `_score_one`, for B tasks wrap the worker call:

```python
def _score_one(task, harness, *, mock, llm, hard, soft, k, cache=None):
    if task.pile == "B" and cache is not None and not mock:
        solution = cache.get_or_make(task.task_id, harness,
                                     lambda: quant_agent_solve(task, harness, mock=mock, llm=llm))
    else:
        solution = quant_agent_solve(task, harness, mock=mock, llm=llm)
    if task.pile == "A":
        return task.task_id, hard.score(task, solution, harness, mock=mock, k=k), solution
    return task.task_id, soft.score(task, solution, harness, mock=mock, k=k), solution
```

Add a `cache=None` parameter to `evaluate(...)` and forward it to `_score_one` in both the sequential and threaded branches. `run_gdpval_soft` passes the shared cache; `run_synthetic_fixture` (Task 7) passes `None`.

- [ ] **Step 6: Run the test, expect PASS**. — `pytest tests/test_smoke.py::test_deliverable_cache_stable_per_harness -v`.

- [ ] **Step 7: Commit**

```bash
git add qea/harness.py qea/loop.py tests/test_smoke.py
git commit -m "feat(evaluator): deliverable cache keyed by (task, harness signature)"
```

---

## Task 4: B-pile debugger — critic + diagnose branch + firewall

**Files:**
- Create: `qea/debugger.py` (`Critic`, `SanitizedDiagnosis`, `diagnose_b_pile`)
- Modify: `qea/agents.py` (`diagnose` dispatch, `_propose_real` firewall)
- Test: `tests/test_smoke.py::test_b_debugger_*`

- [ ] **Step 1: Write failing tests for the firewall + attribution**:

```python
def test_b_debugger_attributes_and_firewalls():
    from qea.tasks import BTask
    from qea.verifier import TaskResult
    from qea.falsify import EvalSummary
    from qea.debugger import diagnose_b_pile

    class CriticLLM:
        def complete(self, prompt, *, role="judge"):
            # answer-free deficiency note + a tag classification
            if "Classify" in prompt:
                return '{"root_cause_tag": "MissingDomainKnowledge", "target_slot": "memory"}'
            return "The deliverable omits the going-concern analysis the rubric requires."

    # one failing B task: criterion 2 failed
    res = {"t1": TaskResult("t1", "Accountants and Auditors", "B", False, False, False, 0.3, 0.0,
                            None, criterion_verdicts={"1": True, "2": False})}
    tasks = [BTask(task_id="t1", subtype="Accountants and Auditors", prompt="audit memo", rubric="",
                   rubric_items=[{"points": 1, "criterion": "states ratios"},
                                 {"points": 2, "criterion": "flags going-concern triggers"}],
                   gold="SECRET-ANSWER-12345")]
    diag = diagnose_b_pile(EvalSummary(res, {"t1": "weak memo"}), tasks, llm=CriticLLM(), mode="hybrid")
    assert diag.root_cause_tag == "MissingDomainKnowledge"
    assert diag.suggested_target_slot == "memory"
    # FIREWALL: the proposer-facing payload must contain no answer/gold material
    payload = diag.proposer_payload()
    blob = repr(payload)
    assert "SECRET-ANSWER-12345" not in blob          # gold never leaks
    assert "going-concern triggers" not in blob        # raw rubric criterion text never leaks
    assert "t1" in payload["predicted_fix_task_ids"]    # task ids are fine
```

- [ ] **Step 2: Run it, expect FAIL** — no `qea/debugger.py`.

- [ ] **Step 3: Create `qea/debugger.py`** with the critic (answer-free), the tag vocabulary, dual-mode attribution, and the sanitized payload:

```python
"""B-pile debugger: rubric verdicts + an answer-free critic -> a component-level
root cause, behind an information firewall. Ground truth (rubric text, gold) is
visible HERE; only a sanitized, component-level payload reaches the proposer."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

# B-pile root-cause vocabulary + its slot affinity (guides, does not force).
B_TAG_SLOT = {
    "MissingDomainKnowledge": "memory",
    "WrongStructure": "prompt",
    "FormatGap": "skill",
    "OccupationMismatch": "router",
    "CalcError": "tool",
}


@dataclass
class SanitizedDiagnosis:
    root_cause_tag: str
    deficiency_category: str            # answer-free, e.g. "missing required analysis section"
    suggested_target_slot: str
    predicted_fix_task_ids: list = field(default_factory=list)
    overview: str = ""                  # answer-free summary

    def proposer_payload(self) -> dict:
        """The ONLY thing the proposer sees. Contains no rubric answers / gold."""
        return {
            "root_cause_tag": self.root_cause_tag,
            "deficiency_category": self.deficiency_category,
            "suggested_target_slot": self.suggested_target_slot,
            "predicted_fix_task_ids": list(self.predicted_fix_task_ids),
            "overview": self.overview,
        }


class Critic:
    """Sees the deliverable + which criteria failed (+ gold as reference) and emits
    an ANSWER-FREE deficiency note: what capability/structure is missing, never the
    answer value. This is the inner wall of the firewall."""
    def __init__(self, llm) -> None:
        self.llm = llm

    def note(self, task, deliverable: str, failed_criteria: list[str]) -> str:
        prompt = (
            "You are reviewing why a finance deliverable fell short. You may see the "
            "rubric and a reference answer, but your note MUST describe only the "
            "MISSING CAPABILITY OR STRUCTURE (e.g. 'omits the required sensitivity "
            "analysis'). NEVER state any specific answer value, number, or verbatim "
            "rubric text. One sentence.\n\n"
            f"TASK:\n{task.prompt}\n\n"
            f"FAILED CRITERIA (count={len(failed_criteria)}):\n"
            + "\n".join(f"- {c}" for c in failed_criteria) +
            f"\n\nDELIVERABLE:\n{deliverable}\n\nANSWER-FREE DEFICIENCY NOTE:"
        )
        return self.llm.complete(prompt, role="judge").strip()


def _failed_criteria_texts(task, verdicts: dict) -> list[str]:
    items = getattr(task, "rubric_items", None) or []
    out = []
    for i, c in enumerate(items):
        if verdicts and verdicts.get(str(i + 1)) is False:
            out.append(c["criterion"])
    return out


def diagnose_b_pile(eval_summary, tasks, *, llm, mode: str = "hybrid") -> SanitizedDiagnosis:
    by_id = {t.task_id: t for t in tasks}
    critic = Critic(llm)
    notes, failing_ids, occ_counts = [], [], {}
    for tid, r in eval_summary.results.items():
        if r.pile != "B" or r.oos_pass:
            continue
        task = by_id.get(tid)
        if task is None:
            continue
        failed = _failed_criteria_texts(task, r.criterion_verdicts or {})
        notes.append(critic.note(task, eval_summary.deliverables.get(tid, ""), failed))
        failing_ids.append(tid)
        occ_counts[r.subtype] = occ_counts.get(r.subtype, 0) + 1

    if not notes:
        return SanitizedDiagnosis("None", "no dominant deficiency", "", [], "No failing B tasks.")

    # Attribution. hybrid: classify notes into a tag (+ slot affinity). free: let
    # the LLM name the slot directly (used when a component is being rewritten).
    tag_vocab = ", ".join(B_TAG_SLOT)
    classify = (
        "Classify the dominant deficiency across these answer-free notes into ONE tag "
        f"from {{{tag_vocab}}}"
        + (" and name the harness slot to target" if mode == "free" else "")
        + '. Return JSON {"root_cause_tag":..., "target_slot":...}.\n\nNOTES:\n'
        + "\n".join(f"- {n}" for n in notes)
    )
    obj = _parse_first_json(llm.complete(classify, role="evolve_agent")) or {}
    tag = obj.get("root_cause_tag", "WrongStructure")
    slot = obj.get("target_slot") if mode == "free" else B_TAG_SLOT.get(tag, "prompt")
    return SanitizedDiagnosis(
        root_cause_tag=tag,
        deficiency_category=f"{len(notes)} task(s) with {tag} across {len(occ_counts)} occupation(s)",
        suggested_target_slot=slot or B_TAG_SLOT.get(tag, "prompt"),
        predicted_fix_task_ids=failing_ids,
        overview=f"{tag}: dominant B-pile deficiency over {len(failing_ids)} failing task(s).",
    )


def _parse_first_json(txt: str):
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
```

- [ ] **Step 4: Run the test, expect PASS** — `pytest tests/test_smoke.py::test_b_debugger_attributes_and_firewalls -v`.

- [ ] **Step 5: Wire `diagnose` dispatch + firewalled `_propose_real`** (`qea/agents.py`). Add a B-pile branch: if any result has `pile == "B"`, call `diagnose_b_pile` and return its `proposer_payload()` merged into the diagnosis dict; else keep `_diagnose_real`/`_diagnose_mock`. In `_propose_real`, build the prompt from the **sanitized payload only** (no rubric/gold/failed-criteria text). Add a firewall test:

```python
def test_propose_real_prompt_has_no_answers():
    from qea.agents import _propose_real
    from qea.harness import seed_harness
    from qea.falsify import RejectedEditBuffer

    captured = {}
    class LLM:
        def complete(self, prompt, *, role="agent"):
            captured["p"] = prompt
            return '{"slot":"memory","component_name":"kb","content":"general finance knowledge",' \
                   '"summary":"add kb","predicted_fixes":["t1"],"risk_tasks":[]}'
    diag = {"root_cause_tag": "MissingDomainKnowledge", "deficiency_category": "1 task",
            "suggested_target_slot": "memory", "predicted_fix_task_ids": ["t1"],
            "overview": "MissingDomainKnowledge deficiency", "_b_pile": True}
    _propose_real(1, _StubEval(), diag, seed_harness(), RejectedEditBuffer(), LLM())
    assert "SECRET" not in captured["p"]  # nothing from ground truth
    assert "MissingDomainKnowledge" in captured["p"]  # sanitized signal present
```

(Provide a minimal `_StubEval` in the test with `.results = {}`.) The `_propose_real` change: when `diagnosis.get("_b_pile")`, build the FAILING-context section purely from `diagnosis["overview"]` + `predicted_fix_task_ids`, NOT from `eval_summary` rubric/deliverable text.

- [ ] **Step 6: Run both debugger tests, expect PASS**.

- [ ] **Step 7: Commit**

```bash
git add qea/debugger.py qea/agents.py tests/test_smoke.py
git commit -m "feat(debugger): firewalled B-pile critic + dual-mode attribution"
```

---

## Task 5: Universal leakage guard (evaluator layer)

**Files:**
- Modify: `qea/verifier.py` (add `LeakageGuard`), `qea/falsify.py` (add `LEAKAGE_BLOCKED`), `qea/tasks.py` (`rubric_corpus`), `qea/loop.py` (pre-apply wiring)
- Test: `tests/test_smoke.py::test_leakage_guard_*`

- [ ] **Step 1: Write the failing test**:

```python
def test_leakage_guard_blocks_copied_answer():
    from qea.verifier import LeakageGuard
    from qea.harness import Edit
    corpus = ["flags any going-concern triggers in the liquidity position"]
    guard = LeakageGuard(corpus, threshold=0.6)
    # an edit that copies rubric answer material -> blocked
    leak = Edit(op="add", slot="memory", component_name="kb",
                content="Always flags any going-concern triggers in the liquidity position.")
    assert guard.is_leak(leak) is True
    # a generic capability edit -> allowed
    ok = Edit(op="add", slot="prompt", component_name="p",
              content="Structure the memo with a clear recommendation section.")
    assert guard.is_leak(ok) is False
```

- [ ] **Step 2: Run it, expect FAIL** — no `LeakageGuard`.

- [ ] **Step 3: Add `LeakageGuard`** (`qea/verifier.py`):

```python
class LeakageGuard:
    """Universal evaluator-layer anti-cheat: rejects an edit whose component content
    overlaps the benchmark's answer_corpus (rubric/answer material) above a
    threshold. n-gram (token-shingle) Jaccard-style containment; no embeddings (v1)."""
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
```

- [ ] **Step 4: Add the verdict constant** (`qea/falsify.py`, module level): `LEAKAGE_BLOCKED = "LEAKAGE_BLOCKED"`.

- [ ] **Step 5: Add `rubric_corpus`** (`qea/tasks.py`):

```python
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
```

- [ ] **Step 6: Wire the guard pre-apply in `run_gdpval_soft`** — build `guard = LeakageGuard(rubric_corpus(tasks))` once; in the iteration, right after `edit` is obtained and before `buffer.blocks(edit)` handling, add:

```python
        if edit is not None and guard.is_leak(edit):
            n_blocked += 1
            records.append(IterationRecord(
                iteration=it, blocked=True, verdict=LEAKAGE_BLOCKED, kept=False,
                edit_summary=edit.summary, edit_slot=edit.slot, edit_component=edit.component_name,
                root_cause_tag=diag.get("root_cause_tag", ""), diagnosis_overview=diag.get("overview", ""),
                incumbent_oos=inc_eval.total_oos(), per_subtype=inc_eval.per_subtype(), cand_oos=inc_eval.total_oos()))
            buffer.add(edit, LEAKAGE_BLOCKED, inc_eval.total_oos(), inc_eval.total_oos(), "leaked answer material into a component")
            oos_traj.append(inc_eval.total_oos()); ms_traj.append(round(_mean_score(inc_eval), 4))
            expdir.persist_iteration("gdpval_soft", {"iteration": it, "eval": None, "diagnosis": diag,
                "manifest": {"blocked": True, "reason": "leakage guard", "edit": edit.signature()}, "workspace": incumbent.summary()})
            _write_resume(...)  # same as the other blocked branches
            continue
```

Import `LEAKAGE_BLOCKED` and `LeakageGuard`/`rubric_corpus` at the top of `loop.py`.

- [ ] **Step 7: Run the guard test + the soft mock test, expect PASS**.

- [ ] **Step 8: Commit**

```bash
git add qea/verifier.py qea/falsify.py qea/tasks.py qea/loop.py tests/test_smoke.py
git commit -m "feat(evaluator): universal leakage guard + LEAKAGE_BLOCKED verdict"
```

---

## Task 6: Benchmark abstraction

**Files:**
- Create: `qea/benchmark.py`
- Modify: `qea/loop.py` (`run_gdpval_soft` builds a `Benchmark`)
- Test: `tests/test_smoke.py::test_benchmark_owns_grader_and_corpus`

- [ ] **Step 1: Write the failing test**:

```python
def test_benchmark_owns_grader_and_corpus():
    from qea.benchmark import gdpval_benchmark
    bm = gdpval_benchmark(broad=False, allow_download=False)  # offline fixtures
    assert bm.name == "gdpval_finance"
    assert bm.tasks and all(t.pile == "B" for t in bm.tasks)
    assert bm.grader is not None
    assert isinstance(bm.answer_corpus, list) and len(bm.answer_corpus) > 0
    assert bm.debugger_kind == "b_pile"
```

- [ ] **Step 2: Run it, expect FAIL** — no `qea/benchmark.py`.

- [ ] **Step 3: Create `qea/benchmark.py`**:

```python
"""A Benchmark owns its tasks, its grader, and its leakage answer_corpus. The loop
is benchmark-agnostic; the router selects the (grader, debugger) per benchmark."""
from __future__ import annotations

from dataclasses import dataclass

from .tasks import load_gdpval_finance, load_gdpval_a_pile, rubric_corpus
from .verifier import SoftJudge, HardVerifier


@dataclass
class Benchmark:
    name: str
    tasks: list
    grader: object
    answer_corpus: list
    debugger_kind: str  # "b_pile" | "synthetic"


def gdpval_benchmark(*, broad: bool = True, allow_download: bool = True, llm=None) -> Benchmark:
    tasks = load_gdpval_finance(broad=broad, allow_download=allow_download)
    return Benchmark("gdpval_finance", tasks, SoftJudge(llm), rubric_corpus(tasks), "b_pile")


def synthetic_fixture_benchmark() -> Benchmark:
    """Offline plumbing fixture only — NOT a real benchmark, makes no headroom claim."""
    tasks = load_gdpval_a_pile()
    refs = [str(t.reference(t.inputs)) for t in tasks]  # numeric answers as the corpus
    return Benchmark("synthetic_fixture", tasks, HardVerifier(), refs, "synthetic")
```

- [ ] **Step 4: Use the benchmark in `run_gdpval_soft`** — replace the inline `tasks = load_gdpval_finance(...)` + `soft = SoftJudge(llm)` + `guard = LeakageGuard(rubric_corpus(tasks))` with `bm = gdpval_benchmark(broad=cfg.gdpval_broad, allow_download=not cfg.mock, llm=llm); tasks = bm.tasks; soft = bm.grader; guard = LeakageGuard(bm.answer_corpus)`. (Keep `hard = HardVerifier()` only if still referenced; for the B-only path it is unused — drop it.)

- [ ] **Step 5: Run the test + soft mock test, expect PASS**.

- [ ] **Step 6: Commit**

```bash
git add qea/benchmark.py qea/loop.py tests/test_smoke.py
git commit -m "feat: Benchmark abstraction (tasks + grader + answer_corpus)"
```

---

## Task 7: Remove A-pile benchmark + ablation; synthetic fixture for `--mock`

**Files:**
- Modify: `qea/loop.py` (delete ablation; add `run_synthetic_fixture`), `run.py` (`--mock` → fixture), `tests/test_smoke.py` (final cleanup)
- Keep: `qea/tasks.py` authored A-pile (now only the synthetic fixture), `HardVerifier`, the probe.

- [ ] **Step 1: Add `run_synthetic_fixture`** (`qea/loop.py`) — a single-arm version of the old `run_arm` over the synthetic benchmark, exercising evolve→falsify→rollback→buffer with the scripted mock edits and producing `acceptance_signals`. Reuse the existing `run_arm` body but for one arm and drive it from `synthetic_fixture_benchmark()`; keep `ArmResult` ONLY if `run_synthetic_fixture` returns it, else inline a small `FixtureResult`. Simplest: rename `run_arm`'s single-arm use:

```python
def run_synthetic_fixture(cfg: Config) -> ArmResult:
    """Offline plumbing test: the scripted mock loop over the synthetic fixture.
    Asserts the three mechanism signals; makes no headroom claim."""
    llm = make_llm(cfg.mock)
    bm = synthetic_fixture_benchmark()
    hard, soft = HardVerifier(), SoftJudge(llm)
    return run_arm("synthetic_fixture", bm.tasks, [], cfg=cfg, llm=llm,
                   hard=hard, soft=soft, expdir=ExperimentDir(cfg.results_dir),
                   b_baseline={"mean_score": 0.0, "n_oos": 0, "n": 0})
```

(Keep `run_arm`, `ArmResult`; **delete `run_ablation`, `AblationResult`** and the `arm2`/A+B comparison.)

- [ ] **Step 2: Update `run.py`** — `--mock` calls `run_synthetic_fixture` and prints one arm + `acceptance_signals`; `--real` calls `run_gdpval_soft`. Remove the ablation comparison print block and the `run_ablation` import.

- [ ] **Step 3: Update the A-pile/ablation tests** in `tests/test_smoke.py`:
  - Change the `ablation` fixture to call `run_synthetic_fixture` and return it directly; update `test_signal_*`, `test_acceptance_all_signals`, `test_capability_wall_never_solved` to read the single result (e.g. `fix = run_synthetic_fixture(cfg)` then `fix.records`, `fix.oos_trajectory`, `fix.final_per_subtype`).
  - **Delete `test_arm2_softB_adds_variance`** (no Arm 2).
  - Keep `test_black_scholes_atm`, `test_amort_fully_amortizes`, `test_current_ratio`, `test_npv_irr`, `test_perturbation_probe_kills_hardcoding`, `test_irr_tolerance_is_per_metric`, `test_unattributed_regression_downgrades_verdict`, `test_sandbox_*`, `test_soft_gate_noise_aware`, `test_signature_*`, `test_provider_pin_*`, `test_gdpval_local_fork_preferred` (these still test kept code).

- [ ] **Step 4: Run the FULL suite, expect all PASS** — `python3 -m pytest -q`. Fix any remaining references to deleted symbols (`run_ablation`, `PairwiseJudge`, `bt_elo`, `decide_keep_pairwise`, `_quantize_parity`) revealed by import errors.

- [ ] **Step 5: Run the offline demo end-to-end** — `python3 run.py --mock` → prints the synthetic-fixture arm + `HEADROOM CONFIRMED (MOCK)` (exit 0).

- [ ] **Step 6: Commit**

```bash
git add qea/loop.py run.py tests/test_smoke.py
git commit -m "refactor: remove A-pile benchmark + ablation; synthetic fixture drives --mock"
```

---

## Task 8: Docs + README sync

**Files:**
- Modify: `README.md`, `ROADMAP.md`

- [ ] **Step 1: Update `README.md`** — replace the iron-law-2 text + the GDPval-AA pairwise sections with: the grader/evaluator split, the observation-firewall law, the % gate, the B-pile debugger, the leakage guard, and "A-pile removed (no headroom); synthetic fixture drives `--mock`". Update the architecture map + the `--mock`/`--real` descriptions.

- [ ] **Step 2: Update `ROADMAP.md`** — mark "pairwise grader" and "A-pile" as superseded/removed; move gold-deliverable-text leakage corpus + leakage threshold tuning into the deferred list.

- [ ] **Step 3: Commit**

```bash
git add README.md ROADMAP.md
git commit -m "docs: sync README/ROADMAP to grader/evaluator + B-debugger architecture"
```

---

## Self-review checklist (run before execution)

- **Spec coverage:** grader % (T1), per-criterion verdicts (T1), neutral judge model (already wired via `role="judge"`; documented in T8), evaluator/`decide_keep_soft` (T2), delete pairwise (T2), worker k-sample/cache (T3), B-debugger observation+attribution+firewall (T4), leakage guard universal + answer_corpus (T5), Benchmark abstraction (T6), router-by-benchmark (T6), remove A-pile+ablation (T7), synthetic fixture (T7), acceptance criteria §12 (T1/T4/T5/T7 tests). **Gap noted:** gold-deliverable-text corpus deferred (rubric-text only) — a deliberate, flagged deviation, not a silent gap.
- **Placeholders:** none — every code step shows full code; the one `_write_resume(...)` ellipsis in T5 explicitly says "same as the other blocked branches" (the engineer copies the existing call).
- **Type consistency:** `criterion_verdicts` (T1) consumed in T4; `Harness.signature()` (T3) consumed in T3 cache + reused by T5 nowhere; `SanitizedDiagnosis.proposer_payload()` (T4) consumed by `_propose_real` (T4); `LeakageGuard.is_leak` (T5) consumed in loop (T5) + benchmark corpus (T6); `Benchmark` fields (T6) consumed by `run_synthetic_fixture` (T7).
