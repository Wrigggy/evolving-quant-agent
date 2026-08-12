# 2026-08-09 — QFBench A6 Expanded Panel, Feedback, and Mutation Protocol

## Decision

A6 is frozen as a **16-task, six-domain discovery canary**, not a five-task
score pilot and not a general multi-round evolution run. The first round keeps
three matched discovery arms:

- **A6-R**: A5-style raw/indexed answer-free evidence and
  `failure_type_v1`;
- **A6-E**: the same contract plus a separately indexed public-instruction and
  public-clause representation;
- **A6-EC**: byte-identical semantic evidence plus `semantic_contract_v1`, a
  typed clause–artifact–trace probe, and a semantic comparison required for
  `ACT`.

All three arms retain the same aggregate, answer-free evaluator exposure. An
optional **A6-F** arm may later add exactly one minimal sanitized feedback
channel, but only as a sequential comparison against A6-EC and only after a
predeclared evidence-sufficiency trigger and leak preflight. Raw or
numeric-masked verifier output is not permitted.

Mutation amplitude and proposal throughput are a **separate second-stage
ablation**. The A6 core retains `max_components=3`, one proposal per arm, and
the current admission rules. If the core localizes a viable discovery regime,
the next engineering experiment should first test mutation amplitude at fixed
throughput, then proposal throughput at a frozen amplitude. It must not change
feedback, evidence representation, contract, amplitude, and throughput at
once.

This record and
[`MANIFEST_A6_EXPANDED_CANARY.json`](../../data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json)
are a design freeze only. No A6 model call, worker evaluation, paid run, or
remote launch has occurred.

## What the larger panel changes—and what it does not

The panel uses only the frozen 30-task evolution-train split and the measured
five-repeat official baseline. It contains:

| Role | Count | Members |
|---|---:|---|
| clean repeat-failure targets | 6 | `swap-curve-bootstrap-ois`, `zero-coupon-bootstrapping`, `earnings-surprise-calculator`, `corporate-action-adjustment`, `13f-amendment-aware-crowding`, `localvol-barrier` |
| strict 5/5 protections | 8 | `historical-var-data-prep`, `credit-spread-decomposition`, `momentum-backtest`, `brinson-sector-attribution`, `sma-crossover-spy`, `bs-greeks-pde`, `merton-jump-diffusion`, `variance-swap-replication` |
| volatile coverage sentinels | 2 | `crypto-funding-rate-basis-carry`, `fomc-tone-event-study` |

Domain counts are data engineering 3, derivatives 4, execution/microstructure
1, rates/FX/macro 3, risk/credit 2, and systematic strategy 3. The two
sentinels are deliberately **not** strict protections: their baseline reward
vectors are `[1,1,1,1,0]` and `[0,1,1,0,1]`.

Expanding five tasks to sixteen improves deterministic breadth, protection
coverage, and task-level resolution: a one-task change is 0.0625 of the task
mean rather than 0.20. It does **not** create sixteen independent samples.
These are fixed, adaptively selected train tasks, several share domains and
artifact patterns, and the same candidate acts on every task. Consequently:

- the primary first-round outcomes are false-`ACT`, unsupported semantic
  leaps, valid grounded clause–artifact–trace comparisons, and calibrated
  `ABSTAIN`;
- the all-sixteen paired six-domain macro reward is secondary and descriptive;
- a separate stable fourteen-task, five-domain macro excludes both volatile
  sentinels and is the only reward macro used in the advancement gate;
- one Evolver sample per arm cannot support a causal arm-effect or
  significance claim;
- the unit for later discovery inference is an independent Evolver sample;
- the unit for later reward inference is a fresh paired worker repetition
  block, not a task;
- six paired blocks are only an engineering minimum. Under an exchangeable
  sharp null, the smallest attainable two-sided exact sign-flip p-value is
  0.03125; ten blocks are preferred for formal planning and must be frozen in
  advance rather than added after an inconclusive six.

Historical panel task means are 0.5625, 0.625, 0.625, 0.5625, and 0.5625
(mean 0.5875, sample SD 0.0342). Historical six-domain macros are 0.6250,
0.6806, 0.6806, 0.6250, and 0.5139 (mean 0.6250, sample SD 0.0680). These
describe old seed volatility only and are not fresh A6 measurements.

## First-round estimands and advancement

Each admitted `ACT` candidate is evaluated once on all sixteen tasks. An
`ABSTAIN` is terminal for its arm and keeps writes locked. The first-round
reports must keep the following distinct:

1. **False-`ACT`**: the arm acts but its preregistered primary
   component-specific observable prediction is falsified by candidate audit or
   evaluation.
2. **Unsupported semantic leap**: a selected-mechanism claim asserts a public
   requirement, artifact fact, trace fact, or causal link without an exact
   authorized citation and resolvable relation.
3. **Grounded semantic comparison**: exact public clause ID, exact public
   artifact path/field, trace phase/slice, and an explicit supported,
   contradicted, or insufficient relation.
4. **Calibrated `ABSTAIN`**: writes remain locked, unresolved comparisons or
   insufficient contrast are recorded, and the arm lacks evidence required by
   its own `ACT` gate.

Reward alone cannot rescue an unsupported `ACT`. A candidate may be considered
for a frozen independent-repetition stage only if it has no false-`ACT`, no
unsupported selected claim, a satisfied arm-specific `ACT` gate, its component
prediction holds, paired stable fourteen-task five-domain macro delta is at
least 0.10, at least two
repeat-failure targets improve, and none of the eight strict protections
regresses. The all-sixteen six-domain macro remains descriptive because its
sixth domain is represented only by a volatile singleton. Volatile sentinels
are reported separately and count toward neither the strict-protection gate nor
the stable domain gate.

The core maximum is 64 official scores: 16 shared fresh seed scores plus at
most 3 × 16 candidate scores. A5-linear planning gives a central worst case of
about USD 0.98, 920 provider requests, and 26 million tokens, with caps of USD
1.50, 1,000 requests, and 35 million tokens. These are estimates, not
authorization.

## What published systems actually expose to their optimizers

The useful lesson from prior systems is not “more feedback is always better.”
It is that many reported evolution systems operate with substantially more
evaluator or answer access than the QFBench firewall allows. Their results do
not license silently importing that information.

### Agentic Harness Engineering

The [AHE paper](https://arxiv.org/abs/2604.25850) describes full traces,
pass/fail outcomes, per-task debugger reports, and an Evolver that uses the
layered corpus over ten outer iterations. The pinned open-source
[`evolve.py`](https://github.com/china-qijizhifeng/agentic-harness-engineering/blob/8b2a55d97590363fe50c3cc6b5e833b020a4bb4c/evolve.py)
goes further: it reads failing `verifier/test-stdout.txt`, injects truncated
“real external test results” into the debugger, and persists failing verifier
snippets in `analysis/detail/{task}.md`, which the Evolver can read. Depending
on the benchmark, those snippets can contain test names, assertion text, and
actual/expected values. This is high-leak feedback by the QFBench standard.

### Rethinking Harness Evolution

The [paper](https://arxiv.org/abs/2607.12227) formalizes three budget-matched
regimes. Parallel sampling receives unit-test accept/reject or model
self-selection; sequential sampling receives the previous trajectory and
binary outcome; harness evolution receives batches of trajectories with
per-rollout binary outcomes. Its experiments use K=5 rollouts, a 45-task train,
10-task validation, and 34-task held-out test split with two independent runs.

The pinned [repository](https://github.com/rethinking-harness-evolution/code/tree/62df2b9624ff32ca61b8accce7fb4a0fd8cbc8a8)
must be read in two modes. The normal AHE-derived path in
[`evolve_ahe.py`](https://github.com/rethinking-harness-evolution/code/blob/62df2b9624ff32ca61b8accce7fb4a0fd8cbc8a8/evolve_ahe.py)
reads raw verifier stdout. The explicit blind configurations and
[`run_blind_rollout_selector.py`](https://github.com/rethinking-harness-evolution/code/blob/62df2b9624ff32ca61b8accce7fb4a0fd8cbc8a8/run_blind_rollout_selector.py)
omit verifier/reward/test output. Paper formalism and a particular repository
execution path therefore must not be conflated.

### Harness Updating Is Not Harness Benefit

The [paper](https://arxiv.org/abs/2605.30621) and pinned
[`skill_bench.py`](https://github.com/A-EVO-Lab/a-evolve/blob/986d97d43b6313c94c7e72c0b0ab6181ed9edba0/agent_evolve/benchmarks/skillbench/skill_bench.py)
provide the clearest source-audited feedback ladder:

- `none`: category/failure class;
- `score`: reward and aggregate pass/fail counts;
- `tests`: stripped test-function names;
- `masked`: test names plus verifier output with selected numeric assertion
  values masked;
- `full`: raw verifier output and assertion values.

The mask is regex-based. It removes several numeric expected/got/assertion and
parameter patterns but retains test names and arbitrary nonnumeric content.
It is therefore a useful experimental precedent, not a sufficient QFBench
sanitizer. Its train/test split keeps test evaluation out of evolution.

### GEPA

The [GEPA paper](https://arxiv.org/abs/2507.19457) and pinned
[`gepa_launcher.py`](https://github.com/gepa-ai/gepa/blob/8a2bed96385202f69caaeb5327a843ed2f5ea225/src/gepa/gepa_launcher.py)
use scores, trajectories, and qualitative `Feedback`. The documented adapter
schema can include correct answers, error messages, and expected-versus-actual
information; the framework itself does not impose a QFBench-style evaluator
firewall. The adapter owns the exposure policy.

### SkillOpt

The [SkillOpt paper](https://arxiv.org/abs/2605.23904) and pinned
[`reflect.py`](https://github.com/microsoft/SkillOpt/blob/47fe269d75d3def79ffd90236261d26d84868ae5/skillopt/gradient/reflect.py)
show full minibatch trajectories to analysts and include `reference_text` as a
“Hidden Reference” when an adapter supplies it. The SearchQA
[`rollout.py`](https://github.com/microsoft/SkillOpt/blob/47fe269d75d3def79ffd90236261d26d84868ae5/skillopt/envs/searchqa/rollout.py)
can append exact gold answers and predicted-versus-expected failure reasons.
Other adapters expose less. This is benchmark-specific high-answer access, not
a safe default for QFBench.

### MLEvolve and BES

[MLEvolve](https://arxiv.org/abs/2606.06473) evolves Kaggle-style executable
solutions using the candidate's own stdout/stderr, parsed validation metric,
task/data previews, and an LLM feedback summary. Its pinned
[`config.yaml`](https://github.com/InternScience/MLEvolve/blob/7d8403c899c40f01941c0429f1c4ef51e82ae41c/config/config.yaml)
also enables submission-format and leakage checks. This is rich feedback but
not raw hidden-leaderboard code or labels.

[BES](https://arxiv.org/abs/2605.28814) searches answer/solution trajectories
and executable programs with explicit rewards, goal trees, elites, and
references. Its object and oracle regime is much closer to program/solution
search than persistent harness discovery, so it is an analogy for operators
and amplitude, not for the QFBench firewall.

## QFBench feedback ladder

The frozen ladder is:

| Level | Evolver-visible signal | A6 policy |
|---|---|---|
| L0 trajectory-only | public task material, worker-visible trace/final, artifacts, process/lifecycle status | admissible but not the current core |
| L1 aggregate outcome, answer-free | L0 plus scalar reward, completion/timeout/missingness, and already-authorized aggregate test counts | all R/E/EC core arms |
| L2 deterministic public-clause localization | L1 plus public clause ID, categorical `observed_missing` / `observed_inconsistent` / `not_assessable`, public artifact path/field, and a frozen coarse failure family | optional A6-F only |
| L3 masked verifier fragments | test names or verifier snippets with numeric values masked | excluded |
| L4 raw oracle | raw output/code, hidden tests, assertions, expected/actual values, official solutions, gold/reference material | forbidden |

L2 is intentionally categorical and fail-closed. It may emit a public clause
identifier only through a deterministic mapping frozen before execution. If a
private verifier observation cannot be mapped without transmitting private
semantics, the only valid output is `not_assessable`.

Before A6-F, the trusted side must freeze the mapping and sanitizer digests,
run synthetic canaries, scan against the protected corpus, taint-label all
verifier-derived fields, reject every non-schema field, mount no verifier
filesystem into worker or Evolver sandboxes, and scan the candidate diff for
protected substrings or suspicious constants. Validation, test, and diagnostic
lineages remain unavailable.

A6-F is run only after the R/E/EC core and only if either:

- A6-EC validly `ABSTAIN`s because grounded public comparisons remain
  `not_assessable` or insufficiently contrastive; or
- A6-EC false-acts and the preregistered trusted audit attributes the missing
  discriminator to information unavailable at L1 rather than to a malformed
  hypothesis or probe.

A6-F is otherwise skipped. It is matched directly to A6-EC, changes only L1 to
L2, uses one Evolver sample, and evaluates its admitted `ACT` on all sixteen
tasks. It is never pooled with the core. Worst case, it adds sixteen candidate
scores and one Evolver, bringing the sequential maximum to 80 official scores,
about USD 1.2337 centrally, 1,160 requests, and 32 million tokens, with planning
caps of USD 1.90, 1,250 requests, and 42 million tokens. These estimates do not
authorize the run.

## Mutation amplitude and throughput audit

### Published artifacts and code

| System | Evolved object and measured amplitude | Throughput, operators, and evaluation | Comparability limit |
|---|---|---|---|
| AHE | The checked-in [seed](https://github.com/china-qijizhifeng/agentic-harness-engineering/tree/8b2a55d97590363fe50c3cc6b5e833b020a4bb4c/agents/code_agent_simple) versus [evolved harness](https://github.com/china-qijizhifeng/agentic-harness-engineering/tree/8b2a55d97590363fe50c3cc6b5e833b020a4bb4c/experiments/evolved_harness) changes 8 paths, +1,100/−25 lines. Full trees are 12→14 files and 500→1,575 lines. Python top-level symbols are 5→19 (all function/class nodes 5→44). The diff adds 525 lines of middleware, 424 lines of shell-tool implementation, a middleware binding, 66 prompt lines, 57/−4 tool-description lines, and memory/YAML changes. | Paper: ten evaluate–analyze–improve iterations, k=2 rollouts/task, one harness proposal/iteration. Current repo adds optional best-of-N, default disabled, and explicit structural versus guidance hints. | Concrete full-harness amplitude evidence, but evaluator exposure is much stronger than QFBench. The final artifact is an endpoint, not a per-iteration amplitude distribution. |
| Rethinking | Persistent harness mutation; no final candidate snapshot was found in the pinned public repository, so files/LOC/AST/bindings are **not observable**. | Repository experiment configs use five outer iterations; paper K=5 denotes rollout budget, not five harness diffs. Parallel, sequential, and harness-evolution conditions are budget matched; train/validation/test remain split. | Strong on search-control design, weak on public diff-amplitude measurement. |
| Harness Updating Is Not Harness Benefit | Skill/harness updating with explicit feedback regimes; no frozen final harness corpus supporting a baseline-to-best files/LOC/AST audit was found, so mutation amplitude is **not observable**. | Batch/cycle configurations vary by benchmark and feedback level. | Best source for feedback ablation, not for a measured full-harness diff envelope. |
| GEPA | Candidate is a mapping of component name to optimizable text; text can represent prompts or code. Default round-robin updates one component, `all` is optional. No published harness candidate snapshots were found, so files/LOC/AST are **not observable**. | The paper proposes one reflective mutation per iteration with minibatch acceptance, Pareto validation, and optional complementary-candidate merge. Current pinned [`proposal_sampling.py`](https://github.com/gepa-ai/gepa/blob/8a2bed96385202f69caaeb5327a843ed2f5ea225/src/gepa/strategies/proposal_sampling.py) also exposes single, same-parent-N, independent-N, and P×N sampling; `max_metric_calls` is the hard evaluation budget. | Current portfolio APIs may postdate the paper experiments. Framework feedback and candidate semantics are adapter-defined. |
| SkillOpt | One persistent Markdown skill. Checked-in initial→paper checkpoint diffs are: ALFWorld 45→113 lines (+68), DocVQA 11→25 (+15), LiveMath 16→34 (+19), OfficeQA 15→50 (+35), SearchQA 3→71 (+68), SpreadsheetBench 56→133 (+77). Word counts grow 516→2,034, 81→306, 154→479, 145→916, 16→1,507, and 224→1,918. No executable code or bindings are in these candidate artifacts. | Default [config](https://github.com/microsoft/SkillOpt/blob/47fe269d75d3def79ffd90236261d26d84868ae5/configs/_base_/default.yaml): four epochs, batch 40, minibatch 8, 16 analyst workers, maximum four edits decaying to two, validation gate. From frozen train sizes, derived proposal steps are 4, 12, 4, 8, 40, and 8 respectively; analysts propose minibatch patches in parallel, then aggregate to one candidate/step. | Strong evidence for high-throughput textual skill growth, not multi-component executable harness evolution. Several adapters expose references/gold. |
| MLEvolve | One full executable Python solution; incremental SEARCH/REPLACE diff is preferred with full rewrite fallback. No public `runs/` snapshot was found, so baseline-to-best files/LOC/AST are **not observable**. | Up to 500 nodes or 12 hours, three initial drafts, three parallel searches, five draft branches, at most three improvements/node, top-k 10, and stagnation-triggered intra-branch evolution or cross-branch fusion. Global memory stores plans, code, metrics, and success/failure. | High-throughput program search on a single solution file, not persistent multi-role agent harness search. |
| BES | Checked-in executable results are genuinely high amplitude. Circle packing starts at 100 lines/3 top-level symbols; three results are 1,234/25, 718/20, and 915/21 lines with diffs +1,190/−55, +670/−51, and +879/−63. Rectangle packing starts 22/1; results are 346/1, 615/19, and 393/1 with +331/−6, +598/−4, +378/−6. Heilbronn starts 19/1; results are 824/22, 387/13, and 322/10 with +815/−9, +376/−7, +314/−10. | Pinned [config](https://github.com/Embodied-Minds-Lab/BES/blob/7c2696f3b5c340dfe34062df93af009cee9152bc/inference/tasks/circle_packing/shinka_backward_adaptive_gpt5.yaml): 100 generations, four islands, archive 40, two proposal and two evaluation jobs, diff/full/cross probabilities 0.6/0.3/0.1, USD 50 cap, prompt evolution every five generations. Operators include crossover, combination, translocation, and deletion. | Useful evidence that large executable mutations and recombination can be productive under a different object and much stronger goal/reward/reference regime; not direct evidence to remove QFBench admission controls. |

The AHE and BES measurements were derived from pinned checked-in artifacts. The
SkillOpt counts were derived from its pinned initial skills and `ckpt/` paper
artifacts. “Not observable” means the pinned public repository did not contain
the necessary baseline-to-candidate artifact; it is not an estimate of zero.

### Local measured mutation history

All local stats below compare the retained candidate artifact against the
pinned minimal seed. “AST symbols” refers to executable Python function/class
nodes in the candidate diff.

| Stage | Proposals / iterations | Actual changed surface | Diff | AST / binding |
|---|---:|---|---:|---|
| old nominal 10-iter run | 4 completed proposals | iterations 1–3 changed only `systemprompt.md`; iteration 4 was empty | +32, +40, +12, then empty | no executable AST or binding; no candidate kept |
| A1 | one manual canary | `SKILL.md` plus `agent.yaml` registration | 2 paths, +35/−3 | 0 AST; one skill binding; not an Evolver proposal |
| A2 | one Evolver proposal | skill, `agent.yaml`, prompt pointer | 3 paths, +90/−0 | 0 AST; one skill binding; translocation from selected source to seed backbone |
| A3 | one Evolver proposal | skill, `agent.yaml`, prompt pointer | 3 paths, +71/−0 | 0 AST; one skill binding; debugger selected source/backbone; activated on 4/4 and regressed FOMC |
| A4 | one Evolver proposal | `systemprompt.md` only | 1 path, +68/−1 | 0 AST; no binding; primary mechanism falsified |
| A5 failure-only | one Evolver proposal | `systemprompt.md` and shell tool description | 2 paths, +24/−2 | 0 AST; no executable/binding; behavior changed but binary vector did not |
| A5 contrastive | one Evolver sample | calibrated `ABSTAIN`, writes locked | empty | not applicable |

The honest conclusion is two-part:

- **Measured**: the old run was an exposure/throughput failure for general
  full-harness search—three prompt-only candidates and one empty diff, no kept
  candidate. Across A2–A5 there was only one proposal per arm/stage, and no
  executable code mutation was discovered.
- **Not falsified**: A1–A5 were deliberately narrow localization canaries.
  They established structural selection/wiring, exposed activation confusion,
  and then tested semantic discovery and abstention. Their narrowness makes
  them underpowered for a general search-yield claim, not invalid for those
  mechanism claims.

There is not yet measured evidence that `max_components=3` itself truncated a
valid local proposal: A4 selected one role and A5 selected two. Removing the cap
inside the A6 core would therefore confound the next evidence/contract result.

## Separate staged mutation ablation

### Stage 0: freeze discovery regime

First finish the R/E/EC localization and, only if triggered, the matched A6-F
feedback increment. Freeze one evidence representation, decision contract,
probe policy, feedback level, model, runtime, seed evidence, and 16-task panel.
No mutation-amplitude result is pooled with the discovery arms.

### Stage 1: static preflight without official scores

Every proposal receives a unique digest and the following audit before any
official task score:

- empty/duplicate diff detection;
- changed files and insertion/deletion counts;
- prompt/docs/YAML versus executable LOC;
- component-role, dependency, and binding closure;
- AST functions/classes added, removed, or modified;
- JSON/YAML schema, Python parse/compile/import, NexAU binding resolution, and
  executable smoke tests;
- forbidden-path, credential, protected-string, suspicious-constant, and
  evaluator-leak scans;
- declared mechanism, actual diff, activation route, target prediction, and
  protection prediction alignment.

This stage costs no official QFBench score.

### Stage 2: amplitude at fixed throughput

Hold throughput at one proposal and compare:

- **M0**: current maximum three component roles and “narrowest coherent
  improvement”;
- **M2**: up to five component roles and “smallest causally complete change,”
  allowing a coupled tool implementation + description + agent binding +
  middleware + routing/prompt bundle. Code is permitted when causally
  required, not forced for a genuinely text-only mechanism.

M1, an intermediate wording-only change that keeps the three-role cap, is
available if the manipulation check shows the wording rather than the cap is
binding. M3, all admissible harness roles, remains unavailable until M2
produces a preregistered truncation signal and a new budget is authorized.

Relax “narrowest” to “smallest causally complete” only when a static dependency
graph shows an omitted implementation/binding or when a prompt-only/empty diff
contradicts an executable/routing prediction. Relax the component cap from
three to five only when:

1. admission records `component_closure_truncated=true` for a selected
   greater-than-three-role closure;
2. at least two independent proposals select the same closure; or
3. repeated false-`ACT` is localized to an omitted binding/dependency rather
   than a wrong hypothesis.

Do not relax either control because reward failed, because an external system
made a large diff, or because broad mutation sounds more ambitious.

One M0/M2 sample is only a manipulation/localization check. If the actual diffs
do not differ in amplitude, there is no amplitude treatment and no causal
interpretation.

### Stage 3: fixed eight-task sentinel

Each preflight-passing candidate runs on all six repeat-failure targets plus
`historical-var-data-prep` and `momentum-backtest`. This fixed eight-task
sentinel is triage, not a headline benchmark and not a source of inferential
reward estimates.

A candidate advances when it has no infrastructure-invalid result, neither
strict protection regresses, and its preregistered component-specific process
or activation prediction appears on at least one predicted target. Target
reward gain is reported but is not required at this gate; this prevents the
sentinel from becoming an adaptive best-score selector.

Sentinel scores are never pooled into the later fresh full-panel estimate.

### Stage 4: throughput at frozen amplitude

After selecting the smallest causally complete amplitude envelope, compare:

- **T1**: one proposal;
- **T3**: three proposals, all frozen before any candidate score and mutually
  blind, with predeclared roles:
  1. smallest causally complete local repair;
  2. coupled structural/executable repair with dependency closure;
  3. recombination/translocation from the frozen train-lineage archive.

Every preflight- and sentinel-passing candidate, up to the portfolio cap, is
evaluated on the full sixteen tasks. Do not evaluate only the candidate whose
proposal prose or sentinel reward looks best. Report proposal count, unique
diff yield, structural diversity, preflight pass rate, sentinel pass rate,
full-panel advancement yield, and cost per admitted candidate. Candidate
portfolio members are correlated search products, not independent task
samples; best-of-N p-values are invalid.

T6 is considered only if T3 produces nonduplicate proposals and nonzero
admission yield under a new cost authorization. Crossover is considered only
after two frozen parents have nonoverlapping positive target signatures and
compatible strict-protection signatures. Otherwise translocation stays the
safer recombination operator.

Worst-case official score counts, without reusing sentinel scores, are:

- M0 versus M2: 16 shared seed + 2 × 8 sentinel + 2 × 16 full panel = 64;
- one T3 portfolio: 16 shared seed + 3 × 8 sentinel + 3 × 16 full panel = 88.

These mutation costs are outside the A6 core and A6-F caps and require a
separate frozen cost plan and authorization.

## Fail-closed prelaunch identity freeze

The protocol manifest and the effective launch environment are distinct frozen
objects. The SHA-256 of the exact protocol-manifest bytes must be recorded in a
separate materialized identity record; it cannot be embedded in the manifest
itself without creating a self-referential digest. A second digest binds the
canonical materialized launch fields.

Before **any** A6 seed, Evolver, candidate, or scored model call, the separate
record named by `prelaunch_identity_freeze.record_path` must be materialized and
validated. That path is source-root-relative and resolves to an external
sibling outside the source tree; placing the record inside the source release
would make its `a6_source_release_sha256` self-referential. It must bind:

- the external protocol-manifest SHA-256;
- the exact rootless config and image-set manifest SHA-256 values;
- the public-task and trusted-task role-manifest SHA-256 values;
- the scheduler epoch and scheduler-identity SHA-256;
- the exact provider-route identity SHA-256;
- one A6 source-release tree SHA-256 recomputed from a canonical sorted member
  manifest against the exact release root from which the runner is executing;
  hashing an unverified self-described manifest alone is insufficient; and
- the canonical materialized-launch identity SHA-256 over all preceding launch
  fields.

The model-visible evidence contract is a separate fail-closed binding, not a
free-form run label. Its ordered train, target, protection, and sentinel IDs;
arm; decision protocol; probe policy; semantic-comparison rule; public-contract
exposure; feedback tier; component cap; and exact shared Evolver instruction
must equal the frozen manifest. It also binds the fresh seed's materialized
launch digest and exact external identity-record digest. A6-R must have no
`contracts/` corpus. A6-E and A6-EC additionally carry the pinned public-role
manifest SHA-256 and a canonical digest over each frozen instruction source
path and exact bytes. Before the model starts, the runner rederives both from
the live public role root, verifies that whole root against `MANIFEST.json`, and
revalidates complete `contracts/index.json` membership, benchmark commit,
source path, copied instruction bytes, per-task digest, and deterministic
clause corpus. A corpus that is internally self-consistent but came from
another checkout or role tree fails closed. The instruction-member digest is
transitively part of the ten-field launch identity because that identity pins
both the protocol manifest (and therefore the ordered 16 task IDs) and the
complete public-role manifest; no redundant eleventh launch field is added.

The code-source member manifest and prelaunch identity record must both live
outside the release root. The source member manifest must enumerate every and
only regular release member with canonical relative path, byte size, and
SHA-256, and reproduce the canonical tree digest. Unsafe, duplicate, unsorted,
missing, undeclared, or symlinked members fail closed. AppleDouble `._*`,
`.DS_Store`, secrets or credentials, caches, results, outputs, runtime roots,
and generated evidence are forbidden. The runner must independently require
that its own resolved repository root equals the declared release root.

These values are deliberately not guessed in this design record. The 2026-08-09
read-only host audit found that the two older A5 release directories had no
source member manifest and contained AppleDouble files, so neither is an A6
release identity. Until a clean A6 release is staged and both the final protocol
digest and source-tree digest are materialized, the manifest status remains
`required_not_materialized`, and launch is blocked. A preflight record is not a
protocol-manifest revision: preserve both digests, and regenerate the external
protocol digest whenever the protocol manifest changes.

## Execution order and stop conditions

1. Materialize and validate the external prelaunch identity record, then
   validate the frozen panel, model/runtime/image/provider identities, evidence
   member equality, and evaluator firewall.
2. Run shared fresh seed evidence once.
3. Run R, E, and EC as matched single samples; evaluate every admitted `ACT`,
   never a selected winner.
4. Audit primary discovery endpoints before reward interpretation.
5. Run A6-F only on the predeclared feedback-sufficiency trigger and only after
   all L2 leak tests pass.
6. Freeze a viable regime before any amplitude or throughput ablation.
7. Stop on identity drift, evaluator leakage, duplicate accepted requests,
   missing cost/token records, invalid verifier execution, unresolved
   lifecycle residue, unsupported `ACT`, failed component prediction, or any
   strict-protection regression.
8. Preserve all negative, `ABSTAIN`, empty-diff, rejected, and superseded
   artifacts. Do not extend repetitions or portfolio size after reading the
   outcome.

## Frozen identities and source audit

- benchmark commit: `024921eb507fcc0c4ffe3e0a96802724be1ae84a`
- split manifest SHA-256:
  `fcd9a1c20f9d76d754e12ad8828b22a5179aa93a29434389100010d288f74a42`
- baseline result SHA-256:
  `db70607b56c5241fd00f2b288d9f460d42333d48b488d22c6cf25edc19cd86d1`
- seed worker digest:
  `4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`
- A5 manifest SHA-256:
  `56aa6a51b61c14fad0557d154c4234900c15fefd3b168fab2f53f2ec369bb4f6`

Primary repositories were audited at AHE
`8b2a55d97590363fe50c3cc6b5e833b020a4bb4c`, Rethinking
`62df2b9624ff32ca61b8accce7fb4a0fd8cbc8a8`, Harness Benefit branch
`986d97d43b6313c94c7e72c0b0ab6181ed9edba0`, GEPA
`8a2bed96385202f69caaeb5327a843ed2f5ea225`, SkillOpt
`47fe269d75d3def79ffd90236261d26d84868ae5`, MLEvolve
`7d8403c899c40f01941c0429f1c4ef51e82ae41c`, and BES
`7c2696f3b5c340dfe34062df93af009cee9152bc`.

## Account-exit handoff

As of 2026-08-09, this A6 protocol and its 16-task R/E/EC implementation are
frozen, but A6 has **not run**. Current no-model checks pass: the focused
protocol/source/runner/isolation set is `232 passed, 1 skipped`, the final
provenance-targeted set is `54 passed`, and a formal-wrapper synthetic
three-arm corpus passed the ladder audit with byte-identical shared cores,
byte-identical E/EC semantic members, no R semantic corpus, exact fresh-seed
identity equality, exact E/EC public-role/member binding, no unexpected
contract differences, and calibrated synthetic `ABSTAIN`. These are
implementation checks only and are not experimental results.

Resume only after revalidating every fail-closed gate: the exact public-role
manifest and instruction source paths/bytes; the canonical public-instruction
member digest; the fresh seed's materialized launch and identity-record
digests; the canonical clean source-release member/tree digest; the external
sibling prelaunch record; all ten launch-identity fields; scheduler, image,
config, provider route, task order, and evaluator firewall. The clean release
identity and final materialized digests are intentionally carried by the
implementation agent's separate progress report, not copied into this protocol
record.

Before resuming, read in order: `docs/PROJECT_MEMORY.md`,
`data/qfbench/MANIFEST_A6_EXPANDED_CANARY.json`, this decision, the separate A6
implementation progress report containing the clean-release identities, and
the external prelaunch/source-member manifests named there. Do not launch from
an older A5 release or reconstruct an identity from remembered hashes. Do not
edit `results/qfbench-experiment-index.json` until a real uniquely identified
A6 run exists, and do not claim an A6 score, benefit, causal effect, or
statistical result from the synthetic audits or implementation tests.
