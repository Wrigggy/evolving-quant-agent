# 2026-08-05 — Evolver Search-Space Exposure, Scheduler Capacity Correction, and Evolver Prompt v2

Status: **proposed**. The scheduler-capacity measurement and the evolver-exposure
observation are `measured`; the mechanism attribution is `source-audited`; the
prompt-v2 design and its theoretical framing are `proposed` and not yet tested.

Supersedes the launch conditions in
[2026-08-04 formal launch](2026-08-04-qfbench-v4-flash-0731-formal-launch.md)
for the evolution arm only. The 85x5 baseline is unaffected.

## 1. What stopped, and why it is being superseded rather than resumed

`qfbench-rootless-evolution-30x15x40-v4-flash-0731-10iter-20260805` stopped at
iteration 4 of 10 on a pinned-provider HTTP 402 (`provider_name: DeepSeek`,
`is_byok: false`, upstream message `Insufficient Balance`). The account balance
was **not** the cause: OpenRouter reported `total_credits 600 /
total_usage 532.27`, and a probe of the same model **without** provider pinning
returned HTTP 200 served by a fallback provider. `required_provider: deepseek`
with fallbacks disabled correctly refused the substitution.

**This is the proxy working as designed.** Without the pin, the run would have
continued on a different provider and the sampling identity would have been
silently invalidated. Record the refusal as a success of the route-pinning
mechanism, not as a failure mode to relax.

The run is superseded rather than resumed because no candidate was ever kept
(4/4 rejected, incumbent never left seed) and because two defects below
invalidate its scheduler premise. Full record:
`results/bc-mirror/qfbench-rootless-evolution-30x15x40-v4-flash-0731-10iter-20260805/operator-ledger/20260805T174500+0800-superseded-provider-outage.json`.

## 2. Defect: resume path misread a completed worker as timeout evidence

`load_persisted_worker_timeout` keyed "this attempt has timeout evidence" on the
existence of `worker-command.json`. That file is written for **every** attempt,
so the unpaired-evidence guard fired on any attempt whose `worker-execution.json`
was missing — 266 of 271 attempt directories satisfied the guard's trigger
condition. Combined with `StartLimitIntervalSec=15min` / `StartLimitBurst=4` /
`RestartSec=30s`, four restarts exhausted the budget in about two minutes and the
run stayed down for **7.4 hours** (2026-08-04T19:08Z to 2026-08-05T02:31Z).

Fixed in commit `7e36512`: read the command first and treat `timed_out: false`
as an absence of timeout evidence. Pairing is still required for genuine timeout
evidence; a quarantine record alongside a completed command is now an explicit
error. Systemd widened to `2h` / `10` / `300s` — a transient fault self-heals,
a genuine crash loop still gives up.

## 3. Defect: 12 workers and 3 verifiers could never coexist

**Measured.** One worker lease is not one container: it is the worker **plus its
dedicated per-attempt proxy**. Against the declared capacity:

| dimension | 12w+3v demand (2-CPU tasks) | capacity | |
|---|---|---|---|
| cpu_count | 54 | 48 | OVER |
| memory_mb | 110592 | 98304 | OVER |
| tmpfs_mb | 45696 | 40960 | OVER |
| sandboxes | 27 | 24 | OVER |
| pids_limit | 5376 | 8192 | ok |

Four of five dimensions oversubscribed; `cpu_count` binding. Only **10** workers
actually fit alongside 3 verifiers (**6** for the 8 four-CPU tasks). Because
`resource_lease` is FIFO with head-of-line blocking, workers and verifiers
starved each other. Observed effective worker concurrency was **5.13** against a
declared 12, and a 45-task panel took 60.5 min against a 30.0 min makespan floor.

**The declared configuration never took effect.** Any report describing this run
as having executed at concurrency 12/3 would be wrong.

### Correction

Two changes, both in `qfbench-evolution-formal-12x3-schema5-v2.json`:

1. **Proxy 2 CPU / 4096 MB → 1 CPU / 2048 MB.** The proxy is a fixed-upstream
   HTTP forwarder; two cores per attempt was 24 cores of pure overhead at
   concurrency 12.
2. **Capacity → `cpu 52, memory 106496, tmpfs 49152, sandboxes 30`** (headroom
   `max_load_1m` unchanged at 56).

Verified: 12w+3v now fits with one worker of slack (binding: sandboxes at 27/30).

**Deliberate non-goal — do not size capacity for the worst case.** Twelve
concurrent 4-CPU tasks would need 72 CPU, more than the 64-core host physically
has. Capacity is sized for the typical task (77 of 85 are 2-CPU); the lease pool
correctly throttles to 8 concurrent workers when large tasks dominate. Raising
capacity past the host would convert a clean queue into host thrashing.

**Identity consequence.** `capacity`, `worker_concurrency`, and
`verifier_concurrency` all feed `scheduler_identity`, and evolution schema-v3
resume compares the identity dict for **exact equality**. The
`qfbench_scheduler_epochs` escape hatch serves baseline schema-v1 only. So this
change cannot be applied to a running evolution; it takes effect only at a new
run. This is why the correction is bundled with a supersede rather than a resume.

## 4. Observation: the evolver used a fraction of its permitted search space

**Measured.** Across four iterations the evolver edited **only
`systemprompt.md`**. It never created any of the seven directories
`AdmissionPolicy.qfbench_full()` permits: `memory/`, `middleware/`, `routing/`,
`skills/`, `tools/`, `validator/`, `tool_descriptions/`.

| iter | edit | prompt lines | verdict |
|---|---|---|---|
| 1 | rewrite | 1 → 33 | domain regression: rates_fx_macro |
| 2 | extend | 33 → 41 | domain regression: derivatives, rates_fx_macro |
| 3 | **compress** | 41 → 13 | domain regression: derivatives, rates_fx_macro, systematic_strategy |
| 4 | **empty diff** | — | candidate made no change |

Iteration 3 is the diagnostic one: after two additive failures the evolver
*shortened* the prompt instead of changing dimension — a binary search along a
single axis. Iteration 4's `edit_signature` is
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, the SHA-256
of the empty string; the loop still spent 45 official scoring attempts before the
gate noticed.

The evolver was **not** lazy: iteration 1 read 42 evidence files and its prompt
rewrite correctly identified real failure causes (JSON key order, rounding, ddof,
`0*ln0=0`). It diagnosed well and acted narrowly.

### Mechanism (source-audited, three separable causes)

1. **No enumeration.** Neither `qea/evolve_agent_full/systemprompt.md` (28 lines)
   nor `reference/NEXAU_GUIDE.md` (22 lines) names the seven permitted
   directories; the guide mentions only `tools/*.py`. Five of the seven are
   absent from the seed candidate *and* unmentioned in anything the evolver can
   read, so nothing in its observation reveals they exist.
2. **"Smallest coherent change" penalizes structural edits.** Workflow step 4
   asks for the smallest coherent change. A single-file prompt rewrite is
   strictly smaller than a module plus an `agent.yaml` declaration plus a smoke
   test, so the instruction actively selects the prompt axis.
3. **Asymmetric cost.** Adding a tool must satisfy worker-runtime import,
   `runtime_bridge` for dependencies, fixed-argv/bounded-timeout/fixed-cwd/
   minimal-env/bounded-output for subprocesses, a mandatory `smoke_candidate_tool`
   call, and an AST import-root check. Editing the prompt costs nothing.

**The tool layer is not the constraint.** `write_candidate` calls
`path.parent.mkdir(parents=True, exist_ok=True)`; every one of the seven
directories was always writable. The restriction lived entirely in what the
evolver was told.

### Consequence for the research claim

The result "4/4 rejected" **cannot** be read as "an evolver cannot improve this
harness." It supports only "an evolver told about one dimension did not improve
that dimension." The run measured a narrower question than it was designed to
ask. This is the primary reason to redo it rather than resume it.

## 5. Theoretical framing for prompt v2

Three pieces of prior work bear on this directly. Two of them are adversarial to
our setup and are recorded here so the redesign does not quietly assume them away.

### 5.1 BES (arXiv:2605.28814, Xu et al., Kakade group) — why one axis is not enough

BES proves (Theorem 4.4, under bounded per-step surprise, decaying step
dependence, and linear block total correlation) that **expansion-only search is
confined to a narrow entropy shell**: every trajectory from autoregressive
extension lands in a typical set of size `exp(H_T + eps*T)` with probability
`1 - exp(-Omega(T))`. Escaping requires **recombination** — their four operators
are combination, deletion, translocation, crossover — which break inter-block
dependence and push expected surprise beyond `H_T + gamma*T`.

The transfer to our setting is by analogy, not by theorem: our evolver rewriting
`systemprompt.md` each iteration is the harness-level counterpart of
expansion-only search. It regenerates the same artifact from the same
conditioning, so its candidates concentrate. What we lack is a recombination
operator over *harness components*.

**Honest limit of the analogy.** BES's theorems are about candidate
**generation** and assume a usable verifier `V(x,y) in [0,1]`; Assumptions
4.1–4.3 are about the policy, not the evaluator. Our binding problem is on the
**selection** side under a noisy evaluator. Theorem 4.4 motivates giving the
evolver more than one axis; it does **not** license any claim about our keep gate.

### 5.2 Rethinking Harness Evolution (arXiv:2607.12227, Wang et al.) — the baseline we owe

On Terminal-Bench 2.1 with GPT-5.4 and Claude Opus 4.6, automatic harness
evolution "does not consistently outperform simple test-time scaling methods and
exhibits limited generalization." Their two protocol objections apply to us
almost verbatim: harness evolution is itself a search procedure, so it must be
compared against **task-level search baselines under matched feedback and
inference budgets**; and sharing one benchmark between search and evaluation
risks overfitting.

Our TVT split already answers the second objection. **We do not currently answer
the first.** A 10-iteration evolution run spends roughly 575 official scoring
attempts; a best-of-N worker at matched cost is an obvious and currently missing
control. Any transfer claim we make without it is vulnerable to exactly this
critique.

### 5.3 Harness Updating Is Not Harness Benefit (arXiv:2605.30621) — which side to invest in

Two capabilities are separable: producing useful harness updates
(**harness-updating**) and benefiting from them while solving tasks
(**harness-benefit**). Their findings: updating is roughly **flat** in base
capability (a 9B model's updates were comparable to a frontier model's), while
benefit is **non-monotonic** — weak models gain little (they fail to surface the
artifacts, or surface them and fail to follow them), mid-tier gain most, strong
gain less. Recommendation: spend capability budget on the **task-solving agent**,
not the evolver.

This predicts our result, and it predicts the AHE reproduction result recorded in
`project_ahe_deepseek_repro` (flash and pro both plateau at 70%; the evolve-agent
was assumed to be the bottleneck). Our seed worker is literally named
`qea_gdpval_worker_weak` and has one shell tool and a one-line prompt. If harness
benefit is non-monotonic in worker capability, **a maximally weak worker may sit
below the range where harness improvements can express themselves at all** —
which would make our headroom argument (weak seed ⇒ large headroom) exactly
backwards.

**This is a live threat to the experiment's premise and is not resolved here.**
It is recorded as an open question, not designed away.

### 5.4 Where the actual novelty is

The 2026-07-14 genre survey (`project_qea_research_direction`, never marked
final) found that **selection under noisy evaluation has no theory in this
genre**: AHE keeps on an n=1 outcome delta with self-reported 11.8%
regression-prediction precision; Bayesian-Agent does posterior bookkeeping but
acts on fixed thresholds and claims no optimality; MLEvolve is UCT-flavored
without theory; BES has the only theorems and they assume the verifier away.
Meanwhile best-arm identification, racing, SPRT, and noisy BO are all off the
shelf.

Our confirm gate is an ad-hoc instance of exactly that missing piece. Two
measurements from this run sharpen it:

- The tolerance `0.0556` is **1.03 sigma** of the difference of two independent
  single draws (baseline sample sd `0.0380`).
- Iteration 4's empty diff gives a **free repetition-noise sample**: an unchanged
  worker moved validation by **-0.0417** against that `0.0556` tolerance. The
  gate's margin over pure noise is thin.
- Validation has exactly **one** `data_engineering` task and **one**
  `execution_microstructure` task, so a single task flip moves the domain macro
  by `1/6 = 0.1667` — about **3x the tolerance**. Two of fifteen tasks control a
  third of the headline metric.

Formalizing the keep decision as a sequential/racing test with `(eps, delta)`
guarantees is the contribution the genre lacks. Prompt v2 does not attempt it;
it removes a confound that would otherwise contaminate the measurement.

## 6. Prompt v2 design

v1 archived at `qea/evolve_agent_full/archive/v1-minimal-20260805/` with digests,
retained as the **exposure control arm**.

v2 changes, each traceable to a cause in section 4:

1. **Enumerate all seven directories** with a purpose line and a "when to reach
   for this" line each (cause 1).
2. **Replace "smallest coherent change" with dimension-aware guidance**: prefer
   the narrowest change that tests a *distinct hypothesis*, and if the same
   component was edited and rejected twice, change component (cause 2).
3. **State the cost asymmetry explicitly** and pre-authorize the expensive path,
   so a structural edit is not treated as a violation of minimality (cause 3).
4. **Require an explicit component choice with a rationale** before editing, so
   the axis decision is observable in the trace rather than implicit.

**Confound to respect.** v1 carried causes 1, 2, and 3 simultaneously. A v2 that
fixes all three cannot attribute any behavior change to one of them. If the
attribution matters, vary them separately in later arms.

**Scope discipline.** Prompt v2 does **not** change the admission policy, the
keep gate, the firewall, the benchmark, the model, or the reward. The permitted
search space is unchanged; only its description changes.

## 7. What is measured, and what is not

**Measured**: the capacity oversubscription and effective concurrency 5.13; the
7.4-hour outage; the four-iteration score trajectory; the single-file edit
pattern; the empty-diff noise sample.

**Source-audited**: the three-cause mechanism for the evolver's narrow search;
the writability of all seven directories.

**Proposed, not tested**: that prompt v2 broadens the evolver's search;
that a broader search yields keeps; that any of it transfers to the test panel.

**Open and unresolved**: whether a maximally weak seed worker can express harness
benefit at all (section 5.3); the missing budget-matched task-level search
baseline (section 5.2).

No report may describe the 12/3 configuration as having been in effect, or
describe this evolution run as evidence about harness evolution in general.
