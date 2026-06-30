# Phase 5 — Generalizable Level-B Evolution Mechanism (initial version)

Status: design (approved for spec). Supersedes the GDPval-hardwired loop in
`qea/loop_levelb.py` from Phase 4.

## 1. Motivation

Phase 4 stood up a Level-B evolution loop, but two things are wrong for the stated
goal — **the evolution mechanism must generalize across base harnesses, not be tuned
to GDPval or FAB**:

1. **The loop is GDPval-hardwired.** `qea/loop_levelb.py` imports `render`,
   `MultimodalJudge`, and `apply_gate` directly and calls `gdpval_benchmark()`. FAB
   (text answers, `score_rubric`, no multimodal render) cannot run through it without
   special-casing.
2. **The evolve agent is implicitly GDPval-tuned.** `qea/evolve_agent/systemprompt.md`
   and the `run_evolve_agent` prompt give GDPval-flavored examples ("save the
   deliverable as a real file"), and `SanitizedDiagnosis.suggested_target_slot` uses
   the Level-A 7-slot vocabulary (`memory/prompt/skill/router/tool`) that does not map
   onto a NexAU worker directory.

The keep/rollback rule (`decide_keep_soft`, aggregate gain beyond a noise floor) is
also coarse: it does not attribute a gain to specific tasks, has weak overfit/side-
effect detection, and gives the evolve agent no feedback for the next iteration.

This phase makes the mechanism benchmark-agnostic and adopts a literature-grounded
keep/rollback rule, then validates it on FAB (the one benchmark with confirmed,
recoverable Level-B headroom: weak 0.388 vs full 0.618, a −0.230 gap).

## 2. Goal and non-goals

**Goal.** A single `run_levelb(cfg, benchmark)` loop + evolve agent + diagnosis +
keep/rollback that runs on FAB **today** and GDPval **by swapping `Benchmark` +
`seed_worker_dir`, changing no loop code** — and that produces real, attributed
score gains on its benchmark. "Generalization" here means *the mechanism* generalizes;
it is enforced at the code level by the `Evaluator` abstraction (§4.1).

**Initial-version scope (what we build now).**
- Benchmark-agnostic loop via an `Evaluator` abstraction.
- AHE-style prediction-falsification keep/rollback + the existing noise floor.
- De-specialized diagnosis + evolve-agent prompt.
- AFlow-style labeled edit-history feedback to the evolve agent.
- Run on the FAB tool-removed weak seed (`qea/worker_fab_weak`) and measure recovery
  of the 0.230 gap.

**Non-goals (deferred to the Phase-5 backlog, §8).**
- Held-out / train-test split and cross-benchmark transfer testing. We evolve and
  select on the full task set for the initial version; honesty is carried by the
  firewall + leakage guard + prediction-falsification + shared-harness structure
  (the AHE stance). We deliberately measure only "does the mechanism improve."
- "Evolution-engine" headroom: crippling agentic-loop scaffolding (shell tool,
  `tracers:`, `max_iterations`) in `agent.yaml` to create benchmark-agnostic headroom.
  Feasible (those are editable wirings) and more generalizable than tool-removal, but
  the NexAU `Agent.run()` loop engine itself is library code and not editable, and
  over-crippling risks exceeding the evolve agent's reconstruction reach (the AHE
  capability-bottleneck finding). Recorded for a follow-up.
- Archive + DGM perf×novelty parent selection; AFlow 5× repeated eval; evaluation
  cascade; DGM tamper-evident execution markers; `evaluate_dir` concurrency.

## 3. Prior-art grounding

Researched against AHE (the reference), ADAS (arXiv 2408.08435), Darwin Gödel Machine
(2505.22954), Gödel Agent (2410.04444), AlphaEvolve (2506.13131), OpenEvolve, AFlow
(2410.10762), EvoPrompt (2309.08532), Promptbreeder (2309.16797).

| Design choice | AHE | Other papers | This phase |
|---|---|---|---|
| Action space | arbitrary code (shared components) | unanimous: all write real code; SEARCH/REPLACE + EVOLVE-BLOCK is the de-facto format | full worker dir incl. new tool `.py` |
| Keep/select | greedy incumbent + prediction-falsify | population/archive is the norm (MAP-Elites+islands, tree+softmax, GA/DE); DGM gates only on "still functional" + perf×novelty parent pick | greedy incumbent + prediction-falsify + noise floor (archive → backlog) |
| Noise handling | 2nd same-dir eval | AFlow 5×+std (strongest); ADAS 5×+bootstrap CI | keep noise floor; configurable repeat k |
| Train/test split | none | near-consensus: validation drives selection, held-out test reported; strongest evidence is transfer with no re-search (ADAS, DGM) | none for initial version (deferred); honesty via firewall+guard+falsify |
| Anti-reward-hacking | firewall + (our extra) leakage guard | universal gap; only DGM has a real case (agent blinded its own reward detector) + 3 lessons: hide grading code, tamper-evident markers, archive audit trail | firewall + leakage guard already ahead of the public norm; markers → backlog |
| Failure feedback | answer-free diagnosis (firewalled) | code-editing systems feed structured feedback (exec output / OpenEvolve artifacts / AFlow labeled edit history); none has a firewalled critic | keep firewalled diagnosis; add AFlow-style edit-history-with-verdicts |
| Eval cascade | none | AlphaEvolve / OpenEvolve explicit cheap→expensive | backlog (worker ~12 min/run) |

Net: our action space, anti-cheat, and failure-feedback choices are at or beyond the
published norm. The two deltas we adopt are AHE's prediction-falsification (keep rule)
and AFlow's labeled edit history (feedback). The one convention we knowingly defer is
the held-out/transfer split.

## 4. Architecture

The loop stays a deterministic orchestrator of two sibling NexAU agents (weak worker +
file-editing evolve agent). keep/rollback, the noise floor, the leakage guard, the
rejected-edit buffer, and the prediction-falsification verdict all live in code; the
evolve agent decides nothing and never runs the grader. Incumbent = a worker directory.

### 4.1 Generalization layer — the `Evaluator` abstraction

The benchmark-specific scoring of a worker run is pulled out of the loop into a
per-benchmark `Evaluator`. New module `qea/evaluator.py`:

```python
@dataclass
class TaskEval:
    content_score: float      # raw rubric/multimodal fraction in [0,1]
    gated_score: float        # canonical score after the format gate
    format_ok: bool
    deliverable_text: str     # rendered text the debugger/critic may read
    verdicts: dict            # per-criterion pass/fail (diagnostic)
    variance: float

class Evaluator(Protocol):
    def evaluate(self, task, worker_run: WorkerRun) -> TaskEval: ...
```

Two implementations:

- `MultimodalEvaluator(llm, k)` (GDPval): `render(worker_run.deliverable_text,
  worker_run.produced_files)` → `MultimodalJudge.grade` → `apply_gate(content,
  task, produced_files)`. Owns the imports that the loop currently hardwires.
- `RubricTextEvaluator(llm, k)` (FAB): `score_rubric` on `worker_run.deliverable_text`
  (k samples, median), no render. The format gate is trivial for FAB (text-gold tasks
  have no `deliverable_exts` → `format_ok=True`, `gated==content`), so we reuse
  `apply_gate` unchanged.

`Benchmark` gains an `evaluator` field. `qea/loop_levelb.py:evaluate_dir` becomes:

```python
def evaluate_dir(worker_dir, tasks, evaluator, run_dir, *, k):
    evals, traces, deliverables = {}, {}, {}
    for task in tasks:
        wr = run_worker(task, worker_dir, run_dir)
        te = evaluator.evaluate(task, wr)
        evals[task.task_id] = te
        traces[task.task_id] = {**wr.trace, "content": round(te.content_score, 4),
                                "format_ok": te.format_ok}
        deliverables[task.task_id] = te.deliverable_text
    mean = statistics.mean(e.gated_score for e in evals.values()) if evals else 0.0
    return evals, traces, deliverables, mean
```

It no longer imports `render`, `MultimodalJudge`, or `apply_gate`. `run_gdpval_levelb`
is renamed `run_levelb(cfg, benchmark, *, _tasks=None, _llm=None)` and reads
`benchmark.tasks`, `benchmark.evaluator`, `benchmark.answer_corpus`.

`qea/benchmark.py` gains `fab_benchmark(llm)` and a `make_benchmark(name, llm)` router.
`LevelBConfig` gains `benchmark: str = "fab"` (default flips to FAB for this phase).

### 4.2 Action space

The evolve agent may create or edit any file in the worker directory snapshot,
including new tool `.py` files and `agent.yaml` tool bindings. This is unchanged in
spirit from Phase 4 but the prompt must explicitly authorize tool/binding/code edits
(Phase 4 only mentioned prompt + tool descriptions). `dir_unified_diff` already
includes `.py`, so the leakage guard scans written code.

### 4.3 Keep/rollback — prediction-falsification + noise floor

After editing the candidate snapshot, the evolve agent ends its run with a fenced JSON
block:

```json
{"predicted_fixes": ["fab_07", "fab_08"], "risk_tasks": ["fab_05"], "rationale": "..."}
```

`run_evolve_agent` parses it from the final text (reuse `_parse_first_json`) and
returns `prediction = {"predicted_fixes": [...], "risk_tasks": [...]}`. The legal task
ids are exactly `diag["predicted_fix_task_ids"]` (the failing tasks), handed to the
evolve agent in its prompt — task ids are not answers, so this does not breach the
firewall (AHE gives task names for attribution).

The loop re-evaluates the candidate dir, then classifies the edit on per-task gated
deltas with a per-task tolerance `delta = noise_margin` (reuse the seed noise estimate):

```python
improved  = [t for t in predicted_fixes if cand[t] - inc[t] >  delta]
regressed = [t for t in all_tasks       if inc[t]  - cand[t] >  delta]
# AHE 5-class verdict
if regressed and not improved:                 verdict = "HARMFUL"
elif regressed and improved:                   verdict = "MIXED"
elif improved and len(improved)==len(predicted_fixes): verdict = "EFFECTIVE"
elif improved:                                 verdict = "PARTIALLY_EFFECTIVE"
else:                                          verdict = "INEFFECTIVE"
```

**Promote iff** `decide_keep_soft(inc_mean, cand_mean, noise_margin)` is true **and**
`verdict != "HARMFUL"`. The noise floor guards the aggregate; the verdict guards
against net-positive edits that secretly regress predicted-safe tasks. A rolled-back
edit (and its verdict + rationale) is recorded in the `RejectedEditBuffer` as today,
plus surfaced as edit history (§4.5).

The leakage guard, rejected-edit buffer signature check, and `NO_EDIT`/`BLOCKED`
branches are unchanged.

### 4.4 Anti-cheat firewall (unchanged)

Two existing layers, both kept: the **firewall** (`diagnose_b_pile` →
`SanitizedDiagnosis.proposer_payload()` is answer-free; the evolve agent never sees
gold/rubric text) and the **`LeakageGuard`** (n-gram containment of added diff lines —
including written `.py` — against the benchmark `answer_corpus`). DGM's case study
(an agent that edited code to blind its own reward detector) confirms the firewall
instinct: the grader and diagnosis code are never exposed to the evolve agent.

### 4.5 De-specialized diagnosis + evolve prompt + edit history

1. **Drop the prescriptive slot.** `SanitizedDiagnosis.suggested_target_slot` is no
   longer surfaced as an instruction. The diagnosis the evolve agent sees is
   target-agnostic: `root_cause_tag`, `deficiency_category`, `overview`,
   `predicted_fix_task_ids`, and the answer-free per-task process notes. The evolve
   agent inspects the worker dir (`ls`, `cat`) and decides what to edit. (The field
   stays on the dataclass for logging; it is dropped from the prompt only.)
2. **Benchmark-agnostic evolve prompt.** `qea/evolve_agent/systemprompt.md` and the
   `run_evolve_agent` message drop "save the deliverable as a real file" GDPval
   examples. New framing: "the diagnosis names a deficiency class + which tasks failed
   + process observations; inspect the worker dir; make ONE focused harness edit —
   prompt, tool description, `agent.yaml` binding, or a new tool — that addresses the
   deficiency *class* generally; never hardcode task answers or domain facts; end with
   the prediction JSON."
3. **AFlow edit-history feedback.** The loop passes a compact history of prior edits
   and their verdicts (`"iter 1: edit systemprompt.md → INEFFECTIVE"`, `"iter 2: add
   retrieve_from_filing binding → EFFECTIVE"`) into the evolve agent prompt, so it does
   not repeat rejected approaches. Built from the loop's `records` + buffer.

## 5. Components and interfaces

| File | Change |
|---|---|
| `qea/evaluator.py` | **new** — `TaskEval`, `Evaluator` protocol, `MultimodalEvaluator`, `RubricTextEvaluator` |
| `qea/benchmark.py` | add `evaluator` field; add `fab_benchmark`, `make_benchmark`; wire `MultimodalEvaluator` into `gdpval_benchmark` |
| `qea/loop_levelb.py` | `evaluate_dir` takes an `Evaluator`; rename `run_gdpval_levelb`→`run_levelb(cfg, benchmark)`; prediction-falsification verdict + promote rule; pass edit history to the evolve agent |
| `qea/evolve_runtime.py` | `run_evolve_agent` returns parsed `prediction`; benchmark-agnostic prompt; accept + render edit history |
| `qea/evolve_agent/systemprompt.md` | de-GDPval-ify; require the prediction JSON; authorize tool/binding/code edits |
| `qea/debugger.py` | `proposer_payload` keeps `suggested_target_slot` for logs but the loop stops surfacing it as an instruction (no behavior change in the debugger itself) |
| `qea/tasks_fab.py` / `qea/tasks.py` | confirm FAB `BTask` carries `rubric_items`, `subtype`, empty `deliverable_exts` so `apply_gate` is a no-op for FAB |
| `run.py` | `--levelb` honors `--benchmark {fab,gdpval}` |

`LevelBRecord` gains `verdict` detail (already present) + the per-task improved/
regressed lists for the history feed. `LevelBResult` is unchanged in shape.

## 6. Data flow (one iteration)

1. `diag = diagnose_b_pile(inc_eval, tasks, llm, traces).proposer_payload()` —
   answer-free; failing-task ids + process notes.
2. snapshot incumbent → candidate dir.
3. `run_evolve_agent(cand_dir, diag, edit_history, run_dir)` → edits files +
   returns `{final_text, trace, prediction}`.
4. `edit = DirEdit(dir_unified_diff(incumbent, cand_dir))`.
5. guard/buffer/`NO_EDIT` checks (unchanged) — may short-circuit to blocked.
6. `cand_evals, _, _, cand_mean = evaluate_dir(cand_dir, tasks, evaluator, ...)`.
7. classify verdict from `prediction` + per-task deltas (§4.3).
8. promote iff `decide_keep_soft(...)` and `verdict != HARMFUL`; else buffer + record.
9. append `(edit_summary, verdict)` to edit history; persist manifest + diff.

## 7. Run target and acceptance

- **Seed:** `qea/worker_fab_weak` (validated: generous 0.388 vs full 0.618).
- **Benchmark:** `fab_benchmark` (FAB v2 public-27), judge `qwen3.7-plus`, k=2,
  worker `deepseek-v4-pro`.
- **Acceptance for "the mechanism is good":** at least one `EFFECTIVE` (or
  net-positive `PARTIALLY_EFFECTIVE`/`MIXED`) **kept** edit that lifts the mean gated
  score beyond the noise floor, with the improvement attributed to the predicted
  tasks. Stretch: the kept edit re-wires `retrieve_from_filing` (or an equivalent
  retrieval capability) and recovers a measurable fraction of the 0.230 gap.
- **Negative result is informative too:** if every edit is INEFFECTIVE/HARMFUL, that
  reproduces the AHE capability-bottleneck finding (evolve-agent strength limits gains)
  rather than a loop bug — distinguishable because the loop's plumbing is unit-tested.

## 8. Phase-5 backlog (explicitly out of the initial version)

1. **Evolution-engine headroom** — crippled-loop seeds via `agent.yaml` (remove
   `run_shell_command`, remove `tracers:`, drop `max_iterations`); benchmark-agnostic
   and gives GDPval the headroom it lacks. Each lever needs the same empirical
   validation FAB got (confirm it actually drops the score). Cap crippling to one
   reconstructable component at a time.
2. **Held-out / transfer testing** — within-benchmark split and/or cross-benchmark
   transfer (evolve on A, freeze, measure on B). The field's headline generalization
   metric; deferred until the within-benchmark mechanism is shown to improve.
3. **Archive + DGM parent selection** — `sigmoid(λ(α−α₀))·1/(1+children)`; gate on
   "still a runnable agent" not on improvement, to keep stepping stones.
4. **AFlow 5× repeated eval**, **evaluation cascade** (cheap subset → full),
   **DGM tamper-evident markers**, **`evaluate_dir` concurrency**.

## 9. Testing

Offline (no LLM/network), extending `tests/test_levelb.py`:
- `RubricTextEvaluator` / `MultimodalEvaluator` return well-formed `TaskEval`
  (stub LLM); `apply_gate` is a no-op for a text-gold FAB task and active for a
  GDPval `.xlsx` task.
- Prediction-falsification verdict table: synthetic per-task deltas → each of the 5
  verdicts; promote rule honors both the noise floor and the HARMFUL veto.
- Prediction JSON parsing: well-formed, missing block (→ empty prediction →
  INEFFECTIVE-safe), and malformed block.
- Edit-history string is built from `records` and fed into the evolve prompt.
- `make_benchmark("fab")` / `("gdpval")` wire the right evaluator.
- Gated real smoke (`QEA_LEVELB_SMOKE=1`) runs one FAB iteration end-to-end.
