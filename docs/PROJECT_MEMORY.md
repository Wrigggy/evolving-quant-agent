# QEA Repository Memory

> Canonical research and architecture memory for future contributors and agents.
> Last updated: 2026-08-12. This file records current decisions, not merely historical discussion.

## How to Use This Memory

Read this file before changing benchmark selection, reward aggregation, worker execution, evaluator isolation, or cloud infrastructure. Detailed evidence lives in the linked reports and decision records. If documents conflict, use this precedence:

1. This memory and the newest decision record.
2. Pinned benchmark manifests and measured run artifacts.
3. Dated experiment reports.
4. Older plans/specs, which may describe superseded intentions.

In particular, the post-screen QFBench audit below supersedes the provisional “about 87 tasks, binary headline reward” description in the earlier authority report.

## Research Objective

QEA studies whether an evolver can improve the **agent harness** around a fixed finance/quant model and whether those improvements transfer beyond the optimization tasks. The evolved object is the NexAU-style worker directory: prompt, tools, middleware, skills, validator, memory, and routing components. A valid improvement must survive evaluator firewalls, keep/rollback falsification, repeated evaluation, and frozen external validation.

The project must not collapse “benchmark score improvement” into “real quant alpha.” Deterministic reconstruction, professional workflow completion, finance reasoning, live execution realism, and safety are separate claims and need separate evidence.

## Canonical Benchmark Suite Design

No single benchmark supplies deterministic reward, quant depth, professional workflow realism, top-venue authority, hidden evaluation, and bank-internal provenance. Use a layered suite:

| Layer | Benchmarks | Purpose | May drive mutation selection? |
|---|---|---|---|
| Optimize | **QFBench** | Frequent, deterministic quant coding reward | Yes, on a lineage-separated train/dev subset |
| Promotion | **FINCH/FinWorkBench**, **BankerToolBench** | Enterprise finance and banking deliverables | Sparingly; only after QF improvement |
| External confirm | **GDPval Finance**, **PRBench Finance** | Frozen, authoritative transfer checks | No |
| Blind final | **BigFinanceBench hosted**, Hedge-Bench candidate | Final contamination-resistant confirmation | Never before final evaluation |
| Auxiliary gates | DSBench/SpreadsheetBench, FinMCP, OccuBench, FinVault | Analysis mechanics, routing, robustness, safety | Diagnostic only |

Authority and evolvability are independent. GDPval and PRBench have stronger publication authority, while QFBench currently offers the most useful deterministic quant task surface. “Banker-authored/validated” must not be rewritten as “bank-internal data.” No selected benchmark has been verified as a large bank’s confidential production dataset.

Full authority and provenance evidence: [2026-07-21 benchmark authority report](reports/2026-07-21-qea-benchmark-authority-screen-report.md).

## QFBench Decision

The audited source is QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a` with **86 tasks**. Treat it as a set of heterogeneous file-producing quant mini-projects, not one homogeneous benchmark.

Key facts:

- Difficulty: 47 hard, 29 medium, 5 easy, 1 very hard, 1 medium-hard, 3 unlabelled.
- Inputs: 228 files, about 160.4 MiB; most tasks are small, but three duplicate the same 35.6 MiB factor panel.
- Outputs: about 353 required artifacts; JSON/CSV dominate, with some HTML, PNG, and source files.
- Verifiers: 72 strict `0/1` tasks and **14 partial-credit tasks**.
- Static tests include roughly 2,240 `test_*` functions and 3,301 assertions; many check numerical tolerances and finance identities.
- Data provenance is uneven: only two tasks contain a dedicated `provenance.md`, and only three task metadata files explicitly name a data source.
- The public tests, solutions, and reference data require a strict evaluator firewall and lineage-aware held-out split.
- Eight official `solution/solve.sh` implementations copy preset expected/reference artifacts instead of independently recomputing the answer. Exclude them from authoritative held-out evaluation until an independent oracle is built: `barrier-garch-var`, `cta-basel-capital`, `kelly-var-sizing`, `regime-cta-vol-target`, `regime-riskparity-cvar`, `sec-10k-report-long`, `sentiment-factor-alpha`, and `structured-note-risk`.

The seven source-audited partial-reward tasks with non-copying reference implementations are `evt-pot-var`, `fx-carry-forward-hedge`, `localvol-barrier`, `mtm-xccy-basis-desk`, `prediction-markets-cross-venue-dislocation`, `sec-8k-event-alpha`, and `yield-curve-bond-immunization`. However, `sec-8k-event-alpha` is **inoperable at the pinned commit**: its official verifier passes an extra positional argument to `write_outputs`, raises before writing `reward.txt`, and has no shell fallback reward. Exclude it from this pilot unless a future upstream commit fixes the official harness; do not locally invent a replacement reward.

Detailed task inventory, scoring audit, and runtime decision: [QFBench and remote execution architecture](decisions/2026-07-21-qfbench-and-runtime-architecture.md).

The five-task pilot is preregistered in `data/qfbench/MANIFEST.json`: optimize on `historical-var-data-prep`, `momentum-backtest`, and `evt-pot-var`; evaluate `fx-forward-cross-rate` and `option-put-call-parity-forward-audit` only at seed/final. The replacement and E2B template transport decision are recorded in [the 2026-07-23 implementation decision](decisions/2026-07-23-qfbench-e2b-template-and-pilot-adjustments.md); publish-once identity, exact resources, dependency locks, and orphan cleanup are recorded in [the 2026-07-24 hardening decision](decisions/2026-07-24-qfbench-template-reproducibility-and-cleanup.md). The measured template publication, dual-Python runtime, oracle parity, failure recovery, and three-iteration result are recorded in [the 2026-07-24 live-pilot decision](decisions/2026-07-24-qfbench-live-e2b-pilot-and-dual-python-runtime.md).

The expanded screen is preregistered in `data/qfbench/MANIFEST_30.json`: 20 optimize and 10 seed/final-only held-out tasks across six domains. Run `qfbench-30x5-20260725` completed all 140 scheduled score records and five rollback decisions; its detailed result is in [the 2026-07-25 decision](decisions/2026-07-25-qfbench-30-task-five-iteration-result.md) and [experiment report](reports/2026-07-25-qfbench-30x5-comparison-report.md). Treat its performance scores as **provisional**: three `if uvx ...` verifier scripts were not warmed by the original published templates, contaminating 14 attempts with offline dependency-cache zeros. Corrected templates were published and passed an isolated offline cache canary on 2026-07-26, as recorded in [the verifier-template repair decision](decisions/2026-07-26-qfbench-verifier-template-repair.md). The 14 historical scores have not been repaired; preserve the original run until a separately authorized superseding rescore.

## Reward and Upgrade Policy

Do not alter official per-task rewards merely to make evolution easier. Preserve each `r_i in [0,1]`, then aggregate outside the benchmark.

For formal reporting, use a domain macro-average over sealed held-out tasks so large task families do not dominate:

```text
R_overall = mean_domain(mean_task(r_i))
```

Daily optimization diagnostics may additionally report test/checkpoint pass fractions, but the headline score must remain the official reward. A worker is upgraded only when it improves held-out domain-macro reward beyond uncertainty, avoids material domain regression, and stays within declared runtime/token/cost budgets. Always publish raw per-benchmark scores beside any normalized `UpgradeIndex`; suite weights remain a proposal until preregistered.

GDPval, PRBench, hosted blind sets, gold artifacts, raw rubric verdicts, hidden tests, and reference solutions must never enter proposer-facing prompts. The proposer receives only scalar reward and answer-free process/failure tags.

## Execution Architecture Decision

High-parallel memory pressure primarily comes from one NexAU `Agent` per task, 200k-token contexts, up to 60 turns, `InMemoryTracer`, and concurrent document rendering—not from the small keep/rollback controller state.

Adopt the original AHE pattern in stages:

1. **Current default:** keep the trusted QEA coordinator on the persistent `bc-server` user account and run evolver, worker, credential-proxy, and independent offline-verifier roles in attempt-isolated rootless Docker containers.
2. Return only compact answer-free summaries, rewards, artifact manifests, and trace URIs to the coordinator.
3. Use the host-local weighted resource lease and preserve CPU, memory, PID, tmpfs, disk, and Docker headroom. Start scored fan-out conservatively; never infer safe concurrency from nominal core count alone.
4. Keep the coordinator outside task containers because it owns checkpoints, trusted verifier inputs, admission, and exact-ID cleanup. E2B remains an explicit fallback and historical reference, not the operational default.

Task environments support two immutable runtime transports: a registry-visible `image@sha256:digest`, or a published E2B base template/build ID extended with validated task `WORKDIR`/`COPY`/`RUN` operations. The E2B base-build route removes the private-registry dependency and freezes the published filesystem, but it is not rebuild-reproducible from the mutable upstream parent tag and ranged requirements. Manifests are publish-once identities, carry the exact pinned `task.toml` CPU/memory/timeout contract, and reject runtime mismatches. Reuse recorded build IDs; prefer the registry digest route when available. The E2B-template route has now passed live five-task publication, isolated oracle parity, force-kill/reap/resume, and a 16-attempt pilot.

Verifier templates use fixed uv cache/tool/bin directories, warm the exact official declaration, and persist `/opt/qea/verifier-requirements.lock`; the direct-Python verifier writes the same lock with `pip freeze`, while the base lock remains separate. Runtime copies the verifier lock into every attempt and rejects a missing or empty lock as infrastructure failure. Every created sandbox is immediately recorded in a lifecycle manifest. The cleanup tool previews and then kills only exact unfinished IDs, never performs broad account cleanup, and supports resume after cleanup review. Linux E2B no-network verification and real forced-failure recovery are measured for the five-task pilot.

For the 30-task extension, the warm-command invariant failed for exactly three official scripts prefixed by shell `if`. The resulting lock existed but described only the base Python environment; it did not prove that the official `uvx` tool environment was cached. Local code now requires a parsed warm command whenever an official script contains `uvx` and rejects the observed offline dependency-resolution zero as infrastructure failure. The corrected `delta-hedging-pnl-simulation`, `swap-curve-bootstrap-ois`, and `form4-cross-sectional-sale-pressure` verifier templates passed no-network E2B canaries with 27, 19, and 7 official tests executed respectively. Future runs must use the corrected IDs from the 2026-07-26 decision. The original IDs and their 14 historical scores remain invalid.

The official QFBench task runtime remains Python 3.11. NexAU 0.3.9 runs in an isolated Python 3.12 environment pinned to VCS commit `35ee1861546db3cb280a6e17e38a74060d7c96c3`; its resolved lock is copied into each attempt. Worker egress is deny-by-default and limited to the configured model-provider host, with E2B injecting authorization. Verifiers have no network. Do not collapse these runtimes or broaden worker credentials without a new decision and parity run.

Moving the whole coordinator to E2B is feasible but not the first optimization. The coordinator would consume a concurrency slot and accrue compute cost while waiting. E2B pause/resume preserves memory and filesystem state, but active network streams disconnect; application checkpoints remain mandatory. Never expose `E2B_API_KEY` or unrestricted model credentials to worker/evolve shell tools.

### Sandbox Provider Selection

E2B was the immutable measured backend for the completed Control/Rich A/B and remains an explicit fallback and historical reference; never change providers within an experiment arm. The approved direct cutover makes self-hosted rootless Docker the operational default for new QFBench full-harness work. The 2026-07-31 five-task run measured a complete fresh evolver/worker/offline-verifier path on rootless Docker, but it did not measure E2B-matched performance or authoritative full-run cost. Daytona, Vercel, and other providers remain future alternatives and must preserve provider-native image/lifecycle identities plus the same firewall and recovery contract.

Do not use Daytona's default container runtime for official scoring, and do not assume its Tier 1/2 `networkBlockAll` behavior is air-gapped until a raw DNS/TCP/HTTPS canary proves it. Do not use Blaxel for official verification while its public-preview filtering depends on `HTTP_PROXY`/`HTTPS_PROXY`; tools that ignore the proxy can bypass the filter. Modal is a secure but higher-cost fallback. Sprites is suitable for persistent development agents but its fixed 8-vCPU/100-GB shape cannot preserve QFBench resource identity. Full rationale, source audit, cost break-even, and canary order: [2026-07-27 sandbox provider decision](decisions/2026-07-27-sandbox-provider-selection-and-parity-plan.md).

## AutoDL Decision

Public AutoDL “no-GPU mode” is **not** an E2B replacement for this project. Its documented allocation is 0.5 CPU core and 2 GB RAM at RMB 0.1/hour, with only one no-GPU instance per main account. AutoDL container instances do not support nested Docker, and the API currently cannot boot an instance in no-GPU mode.

It may serve as a cheap manual watchdog, log viewer, or very low-concurrency coordinator after all heavy work is elsewhere. It cannot run high-parallel NexAU agents or preserve official QFBench Docker/Harbor semantics. If E2B must be avoided, use a persistent Docker-capable CPU VM (starting around 8 vCPU and 16–32 GB RAM), not AutoDL no-GPU mode.

## Current Evidence and Unfinished Work

### 2026-08-07 exploratory evolver-discovery baseline

The A1–A3 sequence established structural recombination and activation evidence,
but it did not exercise broad autonomous full-harness discovery: A1 was an
explicit skill mechanism test, while A2/A3 applied the same translocation
operator to a source parent whose useful behavior lived in the system prompt.
A3 activated the translocated skill on all four selected tasks, improved one
task, preserved two, and regressed `fomc-tone-event-study`; activation routing
was therefore not localized.

**Superseded later on 2026-08-07:** the following paragraph records the initial
canary framing but is not the active decision.

For the next exploratory mechanism check, treat a strong evolver as the normal
engineering baseline. Use GPT-5.4 xhigh reasoning, a longer bounded tool loop,
agent-legible quant evidence queries, explicit candidate component/binding
inspection, and a fail-closed evidence-backed write unlock. The debugger is a
deterministic evidence librarian rather than a root-cause oracle. Compare one
raw-evidence proposal with one indexed-evidence proposal on the same post-A3
candidate, then score admitted candidates separately with the unchanged pinned
DeepSeek worker route. This is an engineering canary, not a paper result or a
formal statistical protocol. Full rationale and boundaries:
[decision](decisions/2026-08-07-quant-evolver-discovery-canary.md) and
[research note](reports/2026-08-07-agent-legible-evidence-and-discovery-research.md).

### 2026-08-07 self-hosted, model-configurable quant discovery

Do not reproduce AHE as the proposed QEA method. Keep the original v0's
AHE-derived loop and verdict/manifest code explicitly attributed and outside the
novelty claim. AHE is related work and may be a baseline; the active research
object is QEA's own quant-specific evidence-to-intervention protocol: a quant
evidence graph, deterministic debugger/indexer, competing causal hypotheses,
counterevidence and uncertainty, a discriminating probe, reachability-aware
component choice, and a fail-closed write contract.

Run this track only in the self-hosted rootless Docker environment. Do not use
E2B for the discovery canary. Bind the exact evolver model and provider through
the rootless allowlisted route and materialize the supported deliberation level
per run; model identity and reasoning level are experimental configuration, not
the method. Preserve source/materialized digests and reject route drift on
resume. The initial GPT-5.4 attempts were infrastructure-only failures before
evidence inspection, and the E2B alternative never executed. See the
[superseding decision](decisions/2026-08-07-self-hosted-model-configurable-quant-discovery.md).

### 2026-08-07 A4 Evolver behavior canary

The immediate next experiment is A4: a one-proposal, train-only behavioral
canary that starts from the exact completed five-repeat baseline seed. It
supersedes the immediate raw/indexed post-A3 comparison but preserves it as a
later debugger ablation. A4 does not continue post-A3 ancestry and does not run
multiple evolution iterations. Its primary object is whether one configured
Evolver performs a grounded evidence-to-hypothesis-to-component-to-prediction
loop; the one-pass task score is secondary.

Only the frozen 30-task evolution-train split may enter the evidence corpus.
The deterministic policy selects three 0/5 tasks with normal verifier execution
and non-empty official test counts, ranked by their worst then mean test-pass
fraction: `swap-curve-bootstrap-ois`, `earnings-surprise-calculator`, and
`corporate-action-adjustment`. Stable 5/5 protections are
`brinson-sector-attribution` and `bs-greeks-pde`. Validation, authoritative
test, and diagnostic identities and evidence remain hidden from the Evolver.

Run a fresh seed pass on those five tasks to capture current structured tool
traces, finals, process summaries, and artifact contents/previews; provide them
with the five-repeat public selection facts and a deterministic non-oracle
index to one model-bound Evolver. If its single candidate is admitted, score it
once on the same five tasks. Audit candidate admission, hypothesis competition,
counterevidence, exact access to at least two tasks and two raw traces, grounded
citation, prediction consistency, and declared-component/diff alignment before
interpreting target gains or protection regressions. This schedule is at most
ten worker attempts plus one Evolver call, uses self-hosted rootless Docker, and
must not use E2B. Full contract:
[A4 decision](decisions/2026-08-07-qfbench-a4-evolver-behavior-canary.md).

The A4 main result must use one formal model route end to end: the baseline,
fresh seed-evidence workers, Evolver, and candidate-evaluation workers are all
`deepseek/deepseek-v4-flash-0731` on the pinned DeepSeek provider. The Evolver
uses route-supported `high` reasoning, while the deterministic debugger/indexer
uses no model. A previously started `deepseek-v4-pro` proposal is retained only
as engineering-path evidence because Pro is not the formal release chosen for
the A4 conclusion; never pool or headline it with the Flash run.

**Measured later on 2026-08-07:** the single-model Flash A4 run completed, but
the mechanism did not pass. The Evolver accessed all five raw traces and 30/44
evidence members, considered three mechanisms with counterevidence, and emitted
an admitted candidate that changed only `systemprompt.md`. The exact automated
behavior gate failed on final mechanism-string consistency. Manual review found
the descriptions conceptually aligned, but the intervention's substantive
prediction was falsified: first-call workspace inventory activated on all five
tasks, while target tool calls/errors/turns rose from 27/6/23 to 30/7/25 and all
five test-count/reward vectors remained unchanged. There were no protection
regressions. Do not begin multi-round evolution from this mechanism. Improve
discovery selectivity first with an identifiability/abstention gate and
executable answer-free discriminating probes, keeping Flash fixed for the next
matched canary. Full evidence:
[A4 report](reports/2026-08-07-qfbench-a4-evolver-behavior-canary-report.md).

### 2026-08-08 A5 failure-type and probe discovery

A5 changes the discovery gate after A4's broad prompt intervention was
falsified. The Evolver must induce one or more recurring failure types across
multiple clean train failures, generate competing causal hypotheses, execute a
bounded answer-free probe with different expected observations, and then choose
ACT or ABSTAIN. ACT requires that the probe eliminate at least one hypothesis;
ABSTAIN is a valid calibrated result and keeps candidate writes locked. Do not
force unrelated failures into one type.

The first matched comparison tests whether requiring a minimal observable
success counterfactual improves discovery. `failure_only` leaves it optional;
`contrastive` requires either the counterfactual or an explicit
`insufficient_contrast`. Both arms use the same constrained probe so this
contract effect is not confounded with free-versus-constrained probe policy.
The latter remains a later ablation with a frozen shared type/hypothesis
package.

The frozen panel expands to six repeatable clean 0/5 train failures and five
stable 5/5 successes/protections. Both arms keep the exact measured Flash seed
worker setup: `deepseek/deepseek-v4-flash-0731`, 200k context,
`max_iterations=60`, 32k per-call output cap, temperature 0.2, official pinned
task resources, and unchanged offline verifiers. QFBench does not define a
universal agent turn limit, so the project matches its own measured baseline
rather than inventing one. An ACT intervention may edit up to three declared
component roles only when they jointly implement one selected mechanism.

Measure discovery capability, ACT/ABSTAIN calibration, component localization,
and answer-free worker harness behavior separately from official reward. The
11-task panel improves cross-task coverage but does not by itself create
statistical significance. Full protocol:
[A5 decision](decisions/2026-08-08-qfbench-a5-failure-type-probe-discovery.md).

**Measured later on 2026-08-08:** the shared Flash seed, both valid Evolver
arms, and the only ACT candidate evaluation completed for $0.3953654432 across
334 completed requests and 12,857,239 tokens. `failure_only` accessed 41/93
evidence members, generated 17 hypotheses, eliminated 12 with six probes, and
ACTed on a two-task deliverable-completeness type by editing the system prompt
and shell-tool description. Its primary zero-coupon prediction was falsified,
and the complete 11-task binary vector remained six target failures plus five
protection successes. The intervention increased inventory, validation, and
cross-check behavior, and changed `localvol-barrier` from timeout to completed
0/7, but it also increased paired turns, tool calls, tool-error rate, and wall
time.

The matched `contrastive` arm accessed 39/93 evidence members, generated six
minimal success counterfactual records, marked three `insufficient_contrast`,
and ABSTAINed after its probes left only task-specific oracle-convention
uncertainty. No candidate write was unlocked. This single comparison supports
success-side reasoning as a useful identifiability/calibration gate, not yet as
a direct solution generator or a causal result. Do not continue the ACT
candidate into multi-round evolution. Next expose exact public task-contract
clauses as indexed answer-free evidence and require an ACT mechanism to connect
a cited clause to an exact artifact/trace fact; keep honest
`insufficient_contrast` and ABSTAIN. Full evidence and limitations:
[A5 report](reports/2026-08-08-qfbench-a5-failure-type-probe-discovery-report.md).

### 2026-08-09 A6 expanded semantic-discovery canary (frozen, not run)

A6 is an engineering localization canary over **16 frozen evolution-train
tasks**, not a continuation on the old five-task panel and not a significance
claim. The panel contains all six repeatable clean 0/5 failure targets, all
eight stable 5/5 successes as strict protections, and two explicitly volatile
coverage sentinels. It covers six descriptive domains. The stable advancement
panel is the 14 targets plus protections across five domains; both volatile
sentinels are excluded from strict-protection and stable-domain gates.

The core is a matched three-arm staircase over one shared fresh Flash seed
corpus and the same L1 answer-free public/process outcome exposure:

- `A6-R` uses the indexed raw A5-style representation, no public-clause corpus,
  `failure_type_v1`, and the constrained evidence probe;
- `A6-E` adds exact public instructions and deterministic clause indexes while
  keeping `failure_type_v1`; typed semantic comparison is available but is not
  an ACT precondition; and
- `A6-EC` receives the byte-identical public-clause corpus but uses
  `semantic_contract_v1`; ACT requires a complete resolvable clause-artifact-
  trace comparison from `typed_contract_artifact_trace_v1` that supports the
  selected hypothesis and contradicts an eliminated competitor.

The model-visible evidence contract is exact-manifest-bound before launch:
ordered train/target/protection/sentinel IDs, arm, decision protocol, probe
policy, public-contract exposure, semantic rule, feedback tier, component cap,
shared Evolver instruction, fresh-seed launch digest, and exact external
identity-record digest must match. `A6-R` must have no `contracts/` corpus;
`A6-E` and `A6-EC` additionally bind the verified public-role manifest SHA-256
and a canonical digest over each frozen instruction source path and exact
bytes. They must rederive those identities from the live pinned public role
root and revalidate the complete public-contract index, benchmark commit, task
membership, source paths, copied instruction bytes, instruction hashes, and
clause corpus. An internally self-consistent corpus from another checkout or
role tree is rejected.
Shared evidence members must be byte-identical across R/E/EC after excluding
only `contract.json` and `contracts/**`; E and EC semantic members must also be
byte-identical.

The four primary discovery audits are false-ACT, unsupported semantic leap,
valid grounded clause-artifact-trace comparison, and calibrated ABSTAIN. R's
semantic claim audit is structurally unavailable, not silently passed or
failed. E is audited only if it claims the optional typed relation. EC requires
it for ACT. ABSTAIN is never coded as false-ACT; it is calibrated only when the
terminal state is explicit, writes remain locked, the candidate and diff are
unchanged, uncertainty/insufficiency is recorded, and that arm's authorized ACT
evidence is absent. False-ACT requires a separate digest-bound audit of the
preregistered component-specific observable prediction; zero reward gain alone
does not establish it.

For every evaluated ACT, report all 16 paired task deltas and the all-panel
six-domain macro as descriptive. Candidate advancement uses only the stable
14-task five-domain macro and additionally requires: delta at least `0.10`, at
least two positive targets, zero regression among eight strict protections, a
supported component-specific prediction, no false-ACT, no applicable
unsupported semantic leap, and the arm-specific ACT gate. Mutation size,
throughput, tokens, and cost are measurement-only and cannot select or admit a
candidate. A threshold pass only authorizes consideration of frozen independent
repetitions; the first round has one stochastic Evolver sample per arm and no
confirmatory p-value. The optional feedback and mutation-portfolio stages remain
sequential, separately costed proposals, not part of the authorized core.

A6 now has a fail-closed ten-field external launch identity covering protocol,
rootless config, image set, public/trusted role manifests, scheduler epoch and
identity, provider route, clean source release, and a canonical materialized
launch digest. The source identity is a tree digest recomputed from a canonical
sorted exact-member manifest against the same release root from which the
runner executes. Symlinks, undeclared files, AppleDouble `._*`, `.DS_Store`,
secrets, caches, results, outputs, and runtime roots are rejected. The
prelaunch identity record is an exact source-root-relative external sibling,
not a member of that release, avoiding a self-reference through its own source
tree digest. The instruction-member digest remains transitively bound by the
existing ten launch fields: the launch pins both the protocol manifest with its
ordered 16 task IDs and the complete public-role manifest.
The 2026-08-09 read-only host audit measured the existing
config/image/public-role/
trusted-role/scheduler/provider identities, but the two older A5 releases had no
source manifest and contained AppleDouble files; they are not valid A6 source
releases. The final protocol digest and a clean source-tree digest therefore
remain unmaterialized, so every A6 seed, Evolver, candidate, scored call, and
even the A6 zero-model runner preflight remains blocked by design. No A6 model
call, paid evaluation, candidate score, or result claim exists, and no A6 run is
entered in the experiment ledger. Full frozen protocol:
[A6 decision](decisions/2026-08-09-qfbench-a6-expanded-panel-feedback-and-mutation-protocol.md).
The final no-model protocol, source-release, runner, auditor, discovery-state,
guarded-workspace, sandbox, and rootless regression set passes `232 passed, 1
skipped`; this verifies implementation invariants only, not benchmark benefit.

A later same-day implementation checkpoint materialized one clean **local**
261-member source release and reproduced its canonical tree digest, then passed
the final merged suite at `1112 passed, 1 skipped`. The payload was not uploaded:
security review required explicit authorization for private-source egress, the
empty staging leaf was removed, the remote final target remained absent, and
the external ten-field launch identity remained unmaterialized. No A6 model,
official score, paid request, or ledger entry exists. Exact local identities,
payload classification, remote audit, pause state, and resume checklist:
[A6 implementation and prelaunch progress](reports/2026-08-09-qfbench-a6-implementation-and-prelaunch-progress.md).

A same-day authorization-intent record removes the proposed USD 1.50 hard cap
for the frozen R/E/EC core and defines one seed, one proposal per arm, and at
most three ACT-triggered 16-task candidate evaluations. It does not authorize
A6-F, mutation, throughput, repetitions, or QuantCode-Bench, and it changes no
identity, evaluator-firewall, task, route, admission, or trigger rule. Security
review initially held the record non-executable because the then-current user
message did not state both the exact upload-tar SHA-256
`e35ddf01dc68b2f8de15d89c765e67064e7eb4ff7fcc1b306aed0300dc38b20b`
and exact final path
`/home/julius/qea/deploy/releases/a6-3b04a5b2257bd846` verbatim. The rejected
transfer created no process and uploaded zero bytes; the empty staging leaf was
removed, the final release and identity remained absent, and all no-model remote
preflight, paid, and model work remained fail-closed. The proposed run IDs and
four-layer watchdog/mirror stack are locally source-audited only and are absent
from the experiment ledger. This was the exact authorization requirement and
remote state at that checkpoint. Full scope and blocker:
[A6 remote execution and budget authorization](decisions/2026-08-09-qfbench-a6-remote-execution-and-budget-authorization.md).

**Superseding authorization later on 2026-08-09:** the user then explicitly
authorized the exact local tar path and SHA-256 above for upload to `bc-server`
and publication only at
`/home/julius/qea/deploy/releases/a6-3b04a5b2257bd846`, acknowledged the private
source/config/research/manifest and coordinator-only criteria contents, and
forbade exposing trusted criteria, the source tree, or coordinator material to
workers/Evolvers. The literal egress gate is therefore satisfied. At the first
post-authorization checkpoint, the exact 3,286,528-byte tar existed only at the
remote staging leaf with matching SHA-256 and mode `0600`; it was not unpacked
or published, no external identity or no-model preflight existed, and paid/model
execution had not started. Continue only through exact publication, live
ten-field identity and isolation equality, four-layer watchdog/mirror setup,
and same-final-ID zero-call preflight; an independent PASS is still required
before any paid/model attempt. The experiment ledger remains unchanged until a
real A6 stage exists.

**Live independent seed gate later on 2026-08-09:** the authorized remote
release, all 261 source members, source/manifest/tar digests, external ten-field
identity, public/trusted role separation, fixed Flash/DeepSeek route, ordered
16-task seed command, and same-final-ID no-model preflight were independently
rederived from live bytes. The preflight recorded zero model, score, verifier,
proxy, worker, container, network, or residual lifecycle activity. The bounded
systemd seed/health/timer bytes and installed Mac monitor were audited; the
coordinator/timer remained inactive and the Mac A6 monitor deliberately
unloaded until the gate. Persistent `caffeinate` and the exact-ID additive,
no-delete, sensitive-excluding mirror were active, and the ledger still had 14
historical runs and zero A6 entries. Outcome: **FRESH-SEED LAUNCH PASS**, limited
to the one shared 16-task seed and conditional on loading the exact Mac monitor,
starting its health timer and coordinator together, and immediately auditing
the first live identities/firewall/mirror state. R/E/EC discovery remains
blocked until the seed corpus, formal three-arm byte audit, each discovery
same-ID preflight, and a separate independent gate. This is infrastructure
evidence, not an experimental result or ledger event.

**Superseding interrupted-launch incident:** when implementation acted on that
PASS, the remote coordinator started but the Mac A6 repair monitor activation
was security-rejected. The coordinator exited in about one second, before
runtime/model/evaluator construction, and was stopped/disabled before its
30-second restart; the timer was disabled and the Mac monitor remained unloaded.
Independent review found zero attempts, accepted requests, tokens, costs,
scores, workers, verifiers, proxy records, lifecycles, containers, or networks,
so this is not a paid seed attempt or experimental result and does not enter the
ledger. The failure exposed a deterministic same-ID transition bug: admission
`checks` and `files` are tuples in the in-memory plan, become JSON arrays/lists
in the persisted preflight plan, and then fail direct dict equality against the
new tuples on the actual invocation despite identical values and digests. The
current release is not safely resumable; deleting/editing the plan or skipping
same-ID preflight is forbidden. The earlier seed PASS is withdrawn. Fix via
canonical JSON normalization plus a preflight-to-same-ID regression, then
rebuild the clean release, obtain new exact tar-SHA/final-path authorization,
rematerialize the ten-field identity, activate all four watchdog layers, rerun
no-model gates, and obtain a new independent seed PASS. Fresh seed and all
discovery/mutation stages are currently blocked.

**Local replacement payload later on 2026-08-09:** the serialization fix now
canonicalizes the complete plan through JSON before exact compare/write; it
does not omit fields or weaken value/order equality. A positive regression
covers preflight followed by the same final ID reaching a fake evaluator
boundary, while a negative identity-drift case fails before that boundary and
leaves the persisted plan unchanged. Independent system and full-dependency
environments each passed the 15 component/source-release tests; implementation
reports `1113 passed, 1 skipped` overall. A new reproducible 261-member local
release has tree SHA-256
`ad26fe36d95392731022c325451504476b99a97fbe820f8c7451c396c9991d23`,
manifest SHA-256
`5620aba6b6cda5791f3cc0e52609eea675388059e0d559abbe257eebc4bf2faa`,
and exact tar SHA-256
`777a5eb78b34f54432ca5bcc93e25052afab824e0f724c09a2467815465e981f`.
Independent rebuild/extract and forbidden-member audits passed. Outcome:
**NEW EGRESS READY**, meaning local payload review only. Nothing was uploaded.
Preserve old r1 evidence; use proposed new final path
`/home/julius/qea/deploy/releases/a6-ad26fe36d9539273` and seed ID
`qfbench-a6-seed-evidence-flash-20260809-r2` only after a new user message
literally authorizes the new exact tar SHA and final path. Security must also
allow loading the bounded A6 repair monitor before any future coordinator
start. All A6 execution remains blocked pending new remote identity, same-ID
preflight, four-layer watchdog, and independent gate.

**Combined r2 authorization package:** a separate offline namespace
`output/qfbench-supervisor/a6-ad26fe36d9539273/` now contains seven exact r2
IDs, a bounded 60-second Mac repair monitor, an additive 21-ID replacement
mirror, and local-only seed/health/timer templates. Independent checks found the
new remote release/run/units absent and both r2 LaunchAgent labels unloaded.
The monitor handles only installed exact IDs and only a live-rechecked
`coordinator_not_running` fingerprint, treats initial success as a no-op, never
restarts `stalled` or `restart_budget_exhausted`, and permits at most three
requests per fingerprint at least 15 minutes apart. The mirror retains all
historical and r1 evidence, uses no `--delete`, and excludes sensitive/trusted
and input bundles. Outcome: **COMBINED AUTH READY**, not activated. A single new
user message may authorize both exact tar SHA
`777a5eb78b34f54432ca5bcc93e25052afab824e0f724c09a2467815465e981f`
to final path `/home/julius/qea/deploy/releases/a6-ad26fe36d9539273` and the
explicitly bounded r2 monitor's ability to issue paid restarts for the seven
exact r2 IDs. It must name the new monitor/mirror labels and hashes and preserve
all identity, firewall, accounting, stage, and scientific gates. Until that
direct confirmation and a new live independent seed gate, no A6 execution is
authorized.

**Combined r2 authorization activated later on 2026-08-09:** the user directly
confirmed the exact new tar SHA/final path, sensitive-material boundary, three
remote-unit hashes, r2 monitor and replacement-mirror labels/hashes, seven-ID
digest and complete ID list, and the bounded paid-restart semantics described in
the dated authorization decision. Exact egress is now permitted and in progress;
there is no USD hard cap, but all identity, firewall, request-accounting, stage,
and scientific-trigger gates remain fail closed. This is not a launch result.
The r2 monitor, mirror, timer, and seed coordinator must stay unactivated until
an independent live audit returns `FRESH-SEED r2 PASS` for the atomic release,
fresh ten-field identity, same-final-ID zero-call preflight, exact disabled unit
bytes, clean residue, and preserved r1 incident. Discovery/candidate work,
A6-F, and mutation remain blocked behind later gates.

**Independent live r2 seed gate later on 2026-08-09:** read-only validation
recomputed the 261-member release/tree/manifest and final authorized tar,
rederived all ten launch-identity fields from the live config, image, role roots,
scheduler, provider route, and source bytes, and found identity record
`4679b6fca2d5eba7e328f86ea2eec3b553a6191437488e65aa63a3a65b86da43`
with launch digest
`3b3dee2cfda952c0528efe66ac9bee4ee7ac5804bd3a8dd533e7fa843ce68376`.
The r2 same-ID run root held only four preflight metadata files, with zero model
requests, attempts, scores, role artifacts, proxy records, journal entries, or
runtime residue. Exact remote unit bytes were installed but disabled/inactive;
r2 monitor/mirror labels were unloaded; r1 evidence remained immutable; the
ledger remained at 14 historical runs and zero A6 entries. A staging-path typo
in the evidence JSON was corrected without remote mutation; canonical evidence
SHA-256 is
`b67e280d1b7886c3735fb2bdb1943b88a4d4609f38b52cb1ee9257f18bd759c5`.
Outcome: **FRESH-SEED r2 PASS**, limited to the exact r2 seed. Activate the
authorized additive mirror, bounded monitor, health timer, and seed coordinator
in one launch window and immediately re-audit the first live state. Discovery,
candidate evaluation, A6-F, and mutation retain their later independent and
scientific gates; no seed score has yet been measured.

**Superseding r2 interruption later on 2026-08-09:** the authorized additive
mirror inherited its registry stdin into child SSH processes, so repeated runs
synced only the first historical ID (occasionally the second) and never reached
the live r2 seed. The fail-closed stop occurred before the monitor was unloaded;
the monitor issued one bounded restart, whose second service invocation failed
before a new proxy/model call on a collision with one of four first-invocation
networks. Final containment unloaded both r2 LaunchAgents, disabled/stopped the
timer and service, and used the deployed exact reaper to kill eight remaining
worker/proxy containers and remove four scoped networks. Final exact inventory,
networks, and leases are zero; all 16 worker/proxy/network lifecycle records and
12 verifier records are clean.

The interrupted r2 run has 12/16 scores and 103 persisted completed HTTP-200
Flash requests with unique request/provider IDs, measured cost USD `0.063910588`
and 909,594 tokens. Those are lower bounds only. Four proxy-local audits were
never finalized/downloaded because the coordinator was hard-stopped while the
proxies remained live, and the reaper later removed them; extra accepted calls,
tokens, and cost are therefore unknown, not zero. Outcome: the r2 PASS is
superseded for continuation, same-ID resume is forbidden, all 12 scores are
excluded from the A6 seed corpus, and r2 is frozen as interrupted infrastructure
evidence. Recovery requires a corrected all-ID mirror with stdin-isolation
regression, fresh exact hashes/direct authorization, a fresh r3 ID and attempts,
new zero-call preflight, and a new independent gate. Future intentional stop
order is monitor unload, timer disable/stop, coordinator stop, exact reaper,
then final mirror unload. Discovery and every later A6 stage remain blocked.
The ordered incident JSON has SHA-256
`838d3845f345ed71c59817a2a22f0784904511262d791594e589c0a07e63171e`
and distinguishes the first exact reaper cleanup from the later empty
verification; do not describe the resources as self-cleaned.

**Offline fresh-r3 recovery package later on 2026-08-09:** the corrected mirror
uses a private registry descriptor, closes it in every child, uses SSH `-n`, and
gives rsync `/dev/null` stdin. A deterministic regression with stdin-consuming
fake children traversed the actual ordered 28-ID additive registry; missing-ID,
SSH-failure, no-delete, exclusion, and mode tests also passed. Fresh seven-ID,
monitor/mirror, stop-order, and three remote-unit files have exact hashes in the
dated authorization decision. Independent checks found the r3 remote run/units,
local destination plists/labels, and state absent, while r2 resources remained
zero. Outcome: **R3 AUTH PACKAGE READY**, not activated. A new direct exact-hash
authorization, live reuse-validation of the release/ten-field identity, fresh
r3 zero-call preflight, and independent `FRESH-SEED r3 PASS` are required before
any install/load/start. Discovery and later stages remain blocked.

**Standing A6 operational authority accepted on 2026-08-10:** within the frozen
16-task core, existing `bc-server` trust boundary, existing provider account,
evaluator-isolation firewall, restart caps, and R/E/EC scientific scope, the
user no longer requires a separate confirmation for every two-agent-audited
content-addressed replacement. This covers fresh exact IDs, systemd units,
LaunchAgents, additive mirror/registry, fresh replacement seed, and same-category
source/runtime replacements. Every operation must still report exact hashes,
paths, IDs, request/token/cost results, and cleanup. Live ten-field equality,
same-ID zero-call preflight, independent launch PASS, four-layer watchdog,
request accounting, evaluator isolation, fail-closed stop order, seed-to-corpus
audit, and per-arm discovery gates remain mandatory. Host, sensitive-data
category, provider/account, restart-cap, destructive, or scientific-scope
changes still require asking. This authority supersedes only the prior per-item
exact-authorization cadence; it does not authorize discovery early or revive r2.
See the [standing authorization decision](decisions/2026-08-10-qfbench-a6-standing-operational-authorization.md).

**Independent fresh-r3 launch gate passed later on 2026-08-10:** the live
261-member release tree, ten-field identity, r3 same-ID preflight/progress,
exact systemd units, exact local LaunchAgent plists, ledger, and r2/r3 resource
inventory were independently re-read rather than accepted from the readiness
report. Outcome: **`FRESH-SEED r3 PASS`**, limited to
`qfbench-a6-seed-evidence-flash-20260809-r3`. The evidence JSON is 6,639 bytes,
SHA-256
`8275c4e219675c233cbd9e1b2f744db6df5c08896951d20c07af46483e0d4138`.
At the gate the coordinator/timer and both LaunchAgents were inactive; model
requests, attempts, scores, workers, verifiers, journal entries, containers,
networks, leases, watch state, and A6 ledger entries were all zero. The ignored
macOS provenance xattr warning did not alter any authorized extracted byte or
bound hash. Before the paid coordinator starts, the exact corrected mirror must
complete the actual ordered 28-ID traversal and materialize/advance the r3
preflight destination, while the exact bounded repair monitor is loaded. Any
stop must unload the monitor before stopping timer/coordinator, then reap exact
resources, advance the final mirror, and unload it. Discovery remains blocked
until clean seed completion, formal corpus construction, three-arm byte and
provenance audit, and separate per-arm live gates.

**Fresh-r3 terminal outcome later on 2026-08-10:** the prelaunch PASS was valid,
but it is superseded for corpus admission. The run finished with 16 score
records, task mean `0.5625`, domain macro `0.513888888888889`, no restart,
all exact lifecycles cleaned, zero resource residue, and a final additive
mirror. `localvol-barrier` timed out and has only an
`audit_download_or_validation_failed` quarantine marker, no canonical proxy
ledger, and no trace digest. The other 15 ledgers contain 146 known unique
HTTP-200 requests, USD `0.1195296368`, and 2,060,117 tokens. The canonical cost
auditor marks those values as lower bounds with one unreconciled attempt; the
component report's zero missing counts cover only downloaded ledgers and are
not run-level completeness. Outcome: **`R3 SEED FAIL/BLOCKED` for corpus and
discovery**. Do not resume r3, rerun only the timeout task, or build its A6
corpus. Fresh r4 requires durable timeout/finalizer-safe per-attempt accounting,
canonical completeness/lower-bound reporting, builder rejection of incomplete
audits, deterministic regressions, a new release/identity, and fresh 16-task
prelaunch plus post-seed independent gates. See the
[r3 quarantine report](reports/2026-08-10-qfbench-a6-r3-seed-quarantine.md).

**Superseding r5 discovery-launch quarantine later on 2026-08-10:** after r4
closed the timeout-accounting gap and r5 closed read-only source-profile
materialization, the fresh r5 seed completed all 16 tasks with a canonical
complete ledger of 211 unique Flash requests, 5,687,613 tokens, and USD
`0.1798568072`. Its byte-matched R/E/EC corpus and all three same-ID no-model
preflights passed. The approved concurrent proposal launch nevertheless failed
before any proposal because Docker container names used only role plus the
shared `evolver-iteration-1` attempt ID and omitted run identity. R ran one
proxy/Evolver pair until fail-closed containment; E and EC collided before
proxy creation and each automatic restart then correctly rejected its stale
committed input archive. R has one unreconciled attempt: accepted requests have
lower bound zero, but actual requests, tokens, and cost are `null`; E and EC are
exact zero-call. No proposal, ACT/ABSTAIN, candidate, score, A6-F, or mutation
result exists. Exact reaping and the final additive mirror left zero managed
containers, networks, or leases.

Freeze all r5 discovery IDs and do not delete inputs or resume them. The
accepted offline fix names containers with a full SHA-256 over exact
`(role, run_id, attempt_id)` canonical bytes while preserving labels, spec
identity, lifecycle, and reaper ownership. Recovery requires a newly audited
content-addressed release/identity, fresh r6 16-task seed and corpus, new
same-ID preflights, and independent launch gates. The user's request for more
tasks/repetitions remains a later statistical-design input and does not alter
the frozen A6 core. Full measured/source-audited/proposed boundaries:
[r5 discovery launch quarantine](reports/2026-08-10-qfbench-a6-r5-discovery-launch-quarantine.md).

**Superseding r6 discovery terminal failure later on 2026-08-10:** the fresh
r6 source identity fixed run-scoped container names, and its new 16-task seed
completed with 171 unique pinned-Flash requests, 3,728,316 tokens, USD
`0.1409971696`, task mean `0.625`, domain macro `0.6805555556`, complete
canonical accounting, and zero residue. The byte-matched R/E/EC corpus and all
three same-ID preflights passed. During the concurrent proposal-only launch,
however, all three Evolvers crossed the 200,000-token context limit before an
exact ACT/ABSTAIN terminal decision: R reached 201,959 prompt tokens, E 233,534,
and EC 221,691. Their 49 completed requests cost USD `0.1608470920` and used
5,216,211 tokens, but every decision is invalid/none, every diff is empty, and
no proposal or candidate was admitted. This is a common loop-control/context
exhaustion failure, not a parser issue and not an A6 mechanism result.

Freeze the r6 discovery and candidate IDs; do not resume them or reuse the r6
seed/corpus under a repaired identity. The independently accepted offline fix
adds a 136,000-token hard terminal trigger, deterministic bounded compact state,
32,000-token terminal output reserve, per-call one-shot middleware/provider
guard, ABSTAIN-only terminal exposure when no candidate has already been
implemented, strict invalid-decision failure, and persisted structured probe
and token/phase audit. The full suite passes `1159 passed, 1 skipped`, but no
repaired model run has occurred. Recovery requires a new content-addressed r7
release/ten-field identity, fresh 16-task seed and corpus, new exact IDs, and
the existing independent per-stage gates. Candidate evaluation, A6-F,
feedback, mutation, and a larger statistical panel remain separately gated and
not run. Exact measured/source-audited/proposed boundaries:
[r6 context-exhaustion incident](reports/2026-08-10-qfbench-a6-r6-discovery-context-exhaustion.md).

**Superseding r7 discovery infrastructure failure later on 2026-08-10:** the
fresh r7 source identity fixed terminal context exhaustion, and its new
16-task seed completed with 199 unique pinned-Flash requests, 5,441,229
tokens, USD `0.1840006784`, task mean `0.625`, domain macro
`0.6805555556`, complete canonical accounting, and zero residue. The fresh
byte-matched R/E/EC corpus and all three same-ID preflights passed. The
concurrent proposal launch nevertheless failed before its first provider call:
the terminal middleware requested public `AgentState.executor`, while pinned
NexAU stores the active executor only as private `AgentState._executor`. The
test fixture had invented the public attribute and masked this exact runtime
coupling mismatch.

All three `before_model` hooks failed before arming their one-shot guard; the
guard then rejected the base model call. Source and traceback audit therefore
establish exactly zero accepted/provider calls, tokens, and cost. This is not a
complete canonical ledger: each arm has an `accounting_complete=false`
quarantine marker and zero-byte unsealed prefix, so canonical request/token/cost
fields remain incomplete/null. No terminal decision, proposal, candidate,
score, A6-F, feedback, or mutation result exists. One bounded restart began,
then monitor-first containment stopped all arms; exact lifecycles, reapers,
leases, final additive mirror, and label audit leave zero residue.

Freeze every r7 discovery and candidate ID and do not resume or reuse its
seed/corpus under repaired source identity. The independently accepted fix
binds the middleware to the exact private `_executor` object across
`before_model`/`wrap_model_call`, validates the same exact counter and tool
payload, retains the one-shot provider guard, and provides no fallback token
counter. Real Agent/Profile/AgentState integration and absent/swap negative
tests pass. Recovery requires a new content-addressed r8 release and identity,
fresh 16-task seed/corpora, new exact IDs, and all existing independent stage
gates. The larger-task/repetition proposal remains a later statistical-design
decision. Exact measured/source-audited/proposed boundaries:
[r7 executor-coupling incident](reports/2026-08-10-qfbench-a6-r7-discovery-executor-coupling.md).

**Superseding r8 seed rate-limit failure later on 2026-08-10:** the fresh r8
release repaired the real NexAU executor coupling and passed live identity,
same-ID zero-call preflight, watchdog/mirror, and independent seed launch gates.
The seed was nevertheless stopped before admission: a 12-worker burst produced
12 HTTP 429 responses across 12 of 13 task proxy ledgers. R8 persisted all 40
raw rows as `completed`, including the 12 `provider_http_error`/429 rows, while
the canonical fixed-checkpoint auditor correctly requires completed rows to be
HTTP 200 with no failure class.

The immutable evidence contains 28 HTTP 200 rows with 28 unique provider IDs,
179,660 tokens, and USD `0.0148273832`; tokens and cost are lower bounds because
canonical accounting is incomplete. There is one worker-execution file but no
completed score, seed report, formal corpus, discovery proposal, or candidate.
Monitor-first containment left PID 0, timer disabled, `NRestarts=1`, all 39
worker/proxy/network lifecycles exact-ID clean, reaper pending/inventory zero,
and a final successful 63-ID additive mirror before unload.

Freeze all r8 seed/discovery/candidate IDs and do not resume or reinterpret the
429 rows. The independently accepted minimal r9 repair performs at most three
fresh upstream wire attempts for one safe rate-limited logical call, keeps each
429 as `not_accepted/rate_limited` with null usage/cost, returns only a final
200 to the agent, binds retries to a 60-second monotonic budget, and pins NexAU
and SDK outer retries off. A durable `O_EXCL` whole-run paid-boundary claim now
blocks component and discovery same-ID systemd restarts before provider access.
The fresh seed is identity-bound to worker concurrency 1 and discovery is
sequential. Focused source/integration tests pass 215, and the complete NexAU
suite passes `1189 passed, 1 skipped`, but no r9 remote/model run exists yet.
Exact measured/source-audited/proposed/not-run boundaries:
[r8 seed rate-limit incident](reports/2026-08-10-qfbench-a6-r8-seed-rate-limit.md).

**A6 engineering-only R11 discovery outcome later on 2026-08-10:** the user
explicitly prioritized a direct feasibility readout over further
publication-grade gate chasing. A separately content-hashed external runner
therefore launched proposal-only R/E/EC arms using complete historical R7
answer-free context plus an explicitly incomplete R11 runtime readout. Every
plan hard-labels the mixed provenance and sets formal seed admissibility,
statistical claims, and candidate evaluation to false. This does not relabel the
partial R11 seed or weaken the formal A6 validator.

All three arms reached the pinned DeepSeek Flash route with exact isolation and
complete sealed accounting, but none produced a contract-valid terminal
decision, proposal, diff, or candidate. R exhausted its terminal model-call
budget after invalid `read_workspace` parameters; E exhausted the terminal
budget; EC expressed an ABSTAIN intent inside an invalid `decide_candidate`
parameter structure. The combined ledger has 60 wire rows: 59 completed
HTTP-200 responses plus one safe rate-limited retry, 5,092,626 accepted-response
tokens, and USD `0.1645248976`, with no missing, quarantined, unsealed, fallback,
or ambiguous accepted call. Exact model-boundary markers blocked three R, two E,
and one EC restart invocations before a new provider call; R's fourth scheduled
start lost the explicit-stop race and received TERM before provider access.
Monitor-first closure, exact lifecycle cleanup, canonical reaper dry-runs, zero
leases, final additive mirroring, and LaunchAgent unload left zero managed
residue.

Outcome: preserve R11 as a **nonformal engineering negative**. It localizes the
immediate bottleneck to terminal/tool-interface interoperability, not to a
scientific difference among R, E, and EC. Freeze these run IDs; do not infer an
EC advantage from its rejected abstention text, and do not evaluate a candidate
because none exists. Candidate evaluation, A6-F, feedback, mutation, and
statistical repetitions remain not run. Exact per-arm identities, ledgers,
restart counts, artifact hashes, and claim boundaries:
[R11 engineering discovery negative result](reports/2026-08-10-qfbench-a6-r11-engineering-discovery-negative.md).

**A6 engineering-only R11 ME5B continuation outcome on 2026-08-11:** the
fresh-ID ME5B run exercised the same externally overlaid ME5 mechanism without
modifying the immutable R10 release. It made 25 completed HTTP-200 calls to the
pinned DeepSeek Flash route, totaling 1,063,874 tokens and USD `0.064557136`.
It durably produced three real artifact-bound probes and three probe-bound
`CONTINUE` checkpoints: the first two advanced epochs, while the third was the
non-ready final checkpoint and did not advance. One malformed
`checkpoint_continue` payload was
rejected with the exact local error `next_hypothesis_ids must be an exact subset
of probe expectation IDs`, after which the bounded repair path successfully
appended later checkpoints.

The final checkpoint was nevertheless not decision-ready: all hypotheses
remained open, no ACT or valid ABSTAIN was recorded, and there is no decision,
proposal, candidate diff, candidate validation, admission, or candidate
evaluation. When the final-epoch gate raised, NexAU attempted another unpaired
model call; the model guard blocked it before provider access. One scheduled
systemd restart was separately blocked before provider construction by the
durable same-ID model-boundary marker. Exact-ID cleanup and the canonical reaper
left zero managed resources, and the final additive mirror completed at
`02:25:33Z`.

Freeze the ME5B ID and preserve it as a **nonformal engineering negative**. It
is positive engineering evidence for real probe/checkpoint persistence and
precise checkpoint repair, but it is not end-to-end feasibility evidence because
the Evolver never made a terminal decision or mutation. A proposed, not-yet-run
ME6 should separate the final epoch into an ACT-or-ABSTAIN-only commit phase,
locally reject and boundedly repair text/CONTINUE/unauthorized output, and end
repair exhaustion as a clean local no-decision failure without unguarded
provider re-entry; retain the global 48-call and 1,800-second bounds. Exact
artifacts, hashes, accounting, and measured-versus-proposed boundaries:
[ME5B engineering negative](reports/2026-08-11-qfbench-a6-r11-me5b-engineering-negative.md).

**A6 engineering-only R11 ME6 continuation outcome on 2026-08-11:** the fresh
ME6 run made 14/14 completed HTTP-200 calls to the exact
`deepseek/deepseek-v4-flash-0731` route, totaling 352,838 tokens and USD
`0.0217533344`. It durably produced two real artifact-bound probes and two
probe-bound, non-ready `CONTINUE` checkpoints. Checkpoint 1 advanced epoch 0 to
epoch 1. Checkpoint 2 was recorded at provider call 12 and was eligible to
advance only at the next model boundary; calls 13 and 14 remained in ordinary
epoch-1 exploration.

Call 14 returned an HTTP-200 text-only synthesis with no executable call after
consuming the sixth epoch call. ME6 had a structured-response contract for
checkpoint repair and decision, but not for ordinary `explore`, so NexAU
treated no calls as a natural finish before the next rollover boundary.
`after_agent` correctly persisted `phase=invalid`, `complete=false`, and no
decision, while the immutable pilot runner unconditionally wrote
`status=complete` and returned zero. Treat systemd `success` / exit 0 as a
**false-success control-flow outcome**, not mechanism success. There is no ACT,
ABSTAIN, downstream decision, candidate diff, validation, admission, candidate
evaluation, formal result, or statistical comparison. The candidate tree
remained `4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`.
Exact lifecycle records show container/network cleanup, the service is inactive,
and the final additive mirror completed at `03:01:19Z`.

Freeze the ME6 ID as a **nonformal engineering negative**. A fresh ME7 change,
proposed separately from this measured record, should require structured tool
progress in ordinary exploration and incomplete mutation, scrub and
force-continue text/no-call/unauthorized responses without refund, remove legacy
unlock/downstream write tools from exploration, remove CONTINUE from final-epoch
exploration, and reject a successful outer report unless the terminal audit's
last `after_agent` record is complete with the same ACT/ABSTAIN decision. Keep
the global 48-call and 1,800-second bounds and never synthesize a decision.
Exact artifacts, hashes, accounting, source diagnosis, and claim boundaries:
[ME6 engineering negative](reports/2026-08-11-qfbench-a6-r11-me6-engineering-negative.md).

**A6 engineering-only R11 ME7 continuation outcome on 2026-08-11:** the fresh
ME7 run reached a valid terminal `ABSTAIN`. It made 23 wire attempts for 21
logical requests on exact `deepseek/deepseek-v4-flash-0731`: 21 completed HTTP
200, while two retry-index-0 HTTP-429 attempts were not accepted and carried no
provider ID, token usage, or cost. Each rejected logical prompt was reissued as
a distinct wire request and completed once at retry index 1. Completed usage
was 484,142 tokens and USD `0.0338504544`.

ME7 durably produced three real schema-1 probes, two non-ready `CONTINUE`
checkpoints, a final ready `ABSTAIN` checkpoint, a checkpoint-bound ABSTAIN
decision, and a final audit event `after_agent complete=true` whose decision
exactly matches the outer proposal. Candidate writes stayed locked and tree
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`
was unchanged; diff, validation, admission, and candidate evaluation were not
applicable. Treat this as an **end-to-end terminal ABSTAIN mechanism pass**, not
ACT evidence, candidate-benefit evidence, a formal A6 result, or a statistical
comparison.

The terminal prose claimed `contracts/**` and manifested artifacts were absent,
but read-only artifact inspection shows the authorized source was complete: 178
files, including `contracts/index.json`, all 16 instruction/clauses pairs, all
16 task artifact manifests, and 55 manifested artifact files. The actual cause
was navigation/compaction loss. `list_workspace` uses `Path.glob`; the literal
`contracts/**` yields a directory that its regular-file filter removes, while
the earlier recursive `map_evidence` audit preserved only broad `**/*`, not the
per-member pointers. Compaction then retained exact accessed paths and lost the
unread contract/artifact navigation. Thus ABSTAIN was honest for the accessed
state, but source absence was a false inference.

Freeze ME7 and keep its mechanism bytes unchanged. A separately proposed ME8
should recompute a bounded hash-verified `VERIFIED NAVIGATION` capsule from the
existing task and contract indexes, task manifests, public evaluations, and
trace pointers before each model boundary/compaction. Navigation must be
explicitly `navigation_only` with no readiness/access effect; exact reads and a
same-task schema-2 clause/artifact/trace discriminator remain mandatory before
ACT. Never add gold, official tests, evaluator verdicts, private criteria,
reference values, or hidden outcomes. Exact measured record and proposal:
[ME7 terminal ABSTAIN](reports/2026-08-11-qfbench-a6-r11-me7-engineering-terminal-abstain.md).

**A6 engineering-only R11 ME8 provider-interrupted outcome on 2026-08-11:**
the fresh ME8 run made nine unique wire attempts on exact
`deepseek/deepseek-v4-flash-0731`. The first eight completed HTTP 200; attempt
9 ended HTTP 520 with `failure_class=provider_http_error`, retry index 0, and
null provider request ID, usage, and cost. Accepted accounting was 211,435 input
tokens, 10,681 output tokens, 222,116 total tokens, and USD `0.0141870232`.

Before the provider interruption, ME8 durably recorded one real schema-1 probe
and one probe-bound non-ready `CONTINUE` checkpoint. It never reached a ready
decision, ACT, ABSTAIN, candidate write, diff, validation, admission, proposal,
pilot report, or candidate evaluation. The candidate tree remained
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`.
Treat this as a **provider-interrupted engineering negative, not a mechanism
verdict**. Freeze the ME8 ID and preserve its model-boundary marker, proxy audit,
failure diagnostics, and lifecycle artifacts forever.

The proxy network, proxy sandbox, and Evolver sandbox were cleaned by exact ID,
and final run-scoped Podman/Docker counts were zero. A fresh ME8B replacement
may reuse byte-identical runner and nine-overlay mechanism bytes with identical
answer-free evidence, route, budgets, and isolation; only fresh operational
identity may change. The measured record is in
[ME8 provider negative](reports/2026-08-11-qfbench-a6-r11-me8-provider-negative.md),
with machine JSON SHA
`1eef2824581f3fe26c4d64ee814977e90d3933447daa7b5dcdaea76e2bff61e7`.

**A6 engineering-only R11 ME8B compact-overflow negative on 2026-08-11:**
the fresh identity-only ME8 replacement made 15 unique HTTP-200 wire attempts
on exact `deepseek/deepseek-v4-flash-0731`, all at retry index zero. Exact
accounting was 570,103 input tokens, 45,433 output tokens, 615,536 total tokens,
and USD `0.0388147256`. Call 15 was a real paid request, not a locally blocked
attempt: it accounted for 26,964 input tokens, 1,569 output tokens, and USD
`0.0036171856`.

ME8B durably recorded one schema-1 probe, one probe-bound non-ready CONTINUE
checkpoint, and one schema-2 contract/artifact/trace probe, but no ACT,
ABSTAIN, decision, candidate write, validation, admission, or evaluation. The
pre-call-15 compact state was 65,492/65,536 bytes. Rejecting call 15's malformed
CONTINUE added exact error and validation state, making the next required
compact 65,943 bytes. NexAU swallowed the resulting before-model exception and
attempted one more model-call entry; the wrap guard blocked that attempted call
16 before provider I/O. The candidate tree stayed unchanged.

Freeze ME8B permanently. The service made two automatic restart attempts; both
were marker-blocked before model/provider work. Final service/timer and
run-scoped container resources were zero/inactive. A fresh ME9 must normalize
duplicated model-prompt navigation metadata, deterministically summarize older
probe/checkpoint history while keeping the latest active records complete,
retain all ACT-required bindings, and validate compact/navigation state again
inside the wrap immediately before provider I/O. The audit event sequence must
also reject reserved-key overwrite. Raising the compact cap to the already
bounded 131,072-byte epoch reserve is acceptable only together with projection
and exact live/worst-state tests, not as a cap-only workaround. Exact evidence:
[ME8B compact-overflow negative](reports/2026-08-11-qfbench-a6-r11-me8b-compact-overflow-negative.md),
machine JSON SHA
`33f6959e6f59d229f76d2e85acc2b75644241e4fb51c9a39c7d516657e392b75`.

**A6 engineering-only R11 ME9 uppercase-ID schema negative on 2026-08-11:**
the fresh ME9 run made 14 unique completed HTTP-200 calls on exact
`deepseek/deepseek-v4-flash-0731`, all at retry index zero. Exact accepted
accounting was 341,345 input tokens, 31,096 output tokens, 372,441 total
tokens, and USD `0.0315401464`.

The ME9 compact projection worked live: the final decision-phase state was
53,594/131,072 bytes, leaving 77,478 bytes of headroom, with no compact or
pre-model failure. The run durably produced one real schema-1 probe and one
reload-verified ready ABSTAIN checkpoint. Both case-sensitive hypotheses
`H1_artifact_shape_failure` and `H2_numeric_value_failure` remained open, so
the checkpoint honestly prohibited a candidate intervention.

The mechanism still failed before persisting the ABSTAIN decision. The generic
probe/checkpoint path accepted the uppercase hypothesis universe, while the
provider-facing `checkpoint_continue` and `decide_candidate` schemas required
`^[a-z][a-z0-9_-]{0,63}$`. NexAU rejected two CONTINUE executions and all four
decision executions with the exact causal error
`'H2_numeric_value_failure' does not match '^[a-z][a-z0-9_-]{0,63}$'`.
Those ABSTAIN calls never entered the engineering adapter or immutable guarded
decision validator. The terminal state was `complete=false`, decision null;
the candidate tree stayed unchanged and there was no write, validation,
admission, proposal, report, or candidate evaluation.

Freeze ME9 as a **nonformal engineering negative**. One scheduled automatic
restart was marker-blocked before provider construction; the final service and
timer are disabled/inactive and run-scoped containers are zero. A proposed,
not-yet-run ME10 should enforce one case-capable bounded identifier grammar
`^[A-Za-z][A-Za-z0-9_-]{0,63}$` before checkpoint persistence and across every
CONTINUE/ACT/decision echo field, retain case-sensitive exact-universe binding
with no normalization or autofill, preserve the causal JSON Schema error in
repair feedback, and use a distinct fail-closed nonzero exit that systemd does
not restart for an incomplete local terminal outcome. Preserve ME9's compact
fix, route, 48-call/1,800-second budgets, ACT gates, and candidate locks. Exact
measured record and proposed boundary:
[ME9 uppercase-ID schema negative](reports/2026-08-11-qfbench-a6-r11-me9-uppercase-id-schema-negative.md).

**A6 engineering-only R11 ME10 terminal-valid ABSTAIN on 2026-08-11:**
the fresh ME10 run made 22 unique completed HTTP-200 calls on exact
`deepseek/deepseek-v4-flash-0731`, all at retry index zero with no fallback.
Exact accounting was 1,032,205 input tokens, 69,335 output tokens, 1,101,540
total tokens, and USD `0.0718470312`. The terminal audit completed in
614.844755 seconds within the 1,800-second bound; the final compact was
65,288/131,072 bytes.

ME10 closed ME9's hypothesis-ID schema contradiction and completed a genuine
bounded terminal decision path. It recorded three real schema-1 probes and
three probe-bound checkpoints; the latest checkpoint was reload-verified and
ready under `ABSTAIN_DERIVED_V1`. Two decision-validation errors were repaired
before final closure. The immutable decision state persisted `ABSTAIN` with
SHA `6a29a5b88c11d6621d03fc36377fe6201d315a8a8c36bc5adf4527f6919f2e00`,
`unlocked=false`, and terminal `after_agent` event 139 reported
`phase=complete` and `complete=true`.

The calibrated rationale was that an early nonexistent `/app/<file>` access,
then `ls`/`find` recovery to `/app/data`, occurred in three of five readable
failed target traces and zero of two readable reward-1 protection traces. That
phenotype was not reward-causal evidence: `corporate-action-adjustment`
recovered and self-verified but still failed four of seven verifier tests, two
other target failures lacked the marker, the run lacked public-evaluation plus
task evidence for two declared target members, and it executed no same-task
schema-2 clause/artifact/trace discriminator. ACT prerequisites were therefore
unmet, so writes correctly remained locked.

Freeze ME10 as a **nonformal engineering result**, not a completed A6
feasibility or benchmark success. The candidate tree stayed byte-identical at
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`;
diff, writes, validation, admission, and candidate evaluation were all zero or
not applicable. The service exited zero without restart; service/timer and
run-scoped resources are inactive/zero, and the final additive mirror finished
at `2026-08-11T07:36:14Z`. Exact measured record:
[ME10 terminal-valid ABSTAIN](reports/2026-08-11-qfbench-a6-r11-me10-terminal-valid-abstain.md),
with machine JSON
`output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me10-continuation/r11-me10-engineering-terminal-abstain-20260811.json`.

**A6 R11 ME1–ME10 mechanism-validation synthesis on 2026-08-11:** treating
the prior R11 R/E/EC engineering-negative report as the baseline, the subsequent
ME sequence recorded 174 wire attempts and 172 logical requests: 170 HTTP-200
accepted responses, one ME2 HTTP 400, two safe not-accepted ME7 HTTP 429
attempts, and one ME8 HTTP 520. Known accepted usage was at least 5,407,027
input plus 391,080 output tokens, 5,798,107 total, with known provider cost at
least USD `0.3520366696`. The totals remain lower bounds because the ME2 400
and ME8 520 rows have null provider usage and cost; null is unknown, not zero.
ME5 was a separately proven provider-zero resource-lease failure.

The chronological mechanism evidence is cumulative but not a formal repeated
comparison. ME1 proved rollover/compaction but created no structured artifact;
ME2 exposed thinking-mode `tool_choice` incompatibility; ME3 persisted a probe
but swallowed checkpoint implementation errors; ME4 made checkpoint errors
durable but showed the monolithic payload was unusable; ME5's branch-minimal
path passed real NexAU tests but its live launch failed before provider; ME5B
persisted repeated probes/checkpoints but had no final ready decision; ME6
exposed explore no-tool and false-success terminal behavior; ME7 produced the
first truthful terminal ABSTAIN but revealed navigation loss; ME8's verified
navigation was provider-interrupted; ME8B exposed compact overflow; ME9's
compact/pre-wire repair passed but uppercase IDs could not cross the decision
schema; ME10 closed that interface and produced the strongest valid calibrated
ABSTAIN.

Across ME1–ME10, no run produced a legal ACT, non-empty full-harness diff,
candidate validation, admission, or candidate-panel evaluation. The sequence
therefore validates the bounded discovery control mechanism through honest
ABSTAIN, not complete A6 engineering feasibility and not harness benefit. The
remaining measured bottleneck is evidence sufficiency and semantic
identifiability: access public evaluation plus task evidence for declared
targets and any declared matched success, then execute a same-task schema-2
public-clause/artifact/trace discriminator before ACT. Only a legal ACT with a
non-empty validated and admitted diff may unlock a separately identified panel
of at most four relevant tasks.

Preserve every ME run ID and all negative/provider-interrupted evidence. ME1's
runtime access count was live-observed rather than durably copied; ME3's exact
bad arguments and ME4's raw rejected arguments are unavailable; ME7's source-
absence rationale was false even though its ABSTAIN was terminal-valid; and
ME10's path-mismatch phenotype was recurring but not proven reward-causal.
Exact per-run accounting, identities, artifacts, uncertainty, and the repair
chain are frozen in
[ME1–ME10 mechanism-validation synthesis](reports/2026-08-11-qfbench-a6-r11-me1-me10-mechanism-validation-synthesis.md),
with companion machine JSON
`output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me10-continuation/r11-me1-me10-mechanism-validation-synthesis-20260811.json`.

The dated host observations are not a materialized launch record: rootless
config `c82e9f0dc139ea6b42ebfb1a4c0b69918e10bcd9b98c2287dc297594c361d975`,
image-set manifest `36be1ec027aa50fbeb6c177c4429bcc0467b096bf982193d60f949911321c51c`,
public role manifest `eb6f933414b12e62d17b228fa16dd11e8d38c66619be58c055c0658c37e62440`,
trusted role manifest `005b24e7030147e7edd47d8c0c28cc65fc619118af5cd0894560b6b0a75217ab`,
scheduler epoch `repetitions-01-through-05` with scheduler identity
`824a2b76c78b0389538de8b5b2234867cd4174093d8fab7db938d6a5c532e5c0`, and
provider-route identity
`88f3d650ad15606378dff20e6fb093bb5ffd7819f40be54275304f437d10c3ba`.
Recheck them after staging the final source release; do not copy them into a
record without live equality validation.

### 2026-08-09 QuantCode-Bench conditional external-transfer screen

The Lime QuantCode-Bench repository was source-audited at commit
`f8bda951addb409a81aa316c00401dbde60774ae`; no model, scored task, market-data
download, gold/hidden solution read, adapter change, or evaluator change was
performed. It is **CONDITIONAL GO** only as a sealed near-domain external
seed-versus-final transfer check after QFBench harness selection is complete and
the final harness is frozen. It is **NO-GO** as the sole blind or
contamination-free generalization benchmark, and **NO-GO** for treating the
unmodified upstream local evaluator as publication-grade authority: all 400
prompts/evaluator code are public, most task sources are public websites, no
hosted hidden split was found, runtime market downloads and dependencies are
unfrozen, untrusted code shares an environment, and judge fallback paths can
fail open.

Promotion to a separately named `QuantCode-Bench-derived hardened protocol`
requires, before any scored call: immutable 39/39 market caches with repeated
fresh-container content parity; pinned Python, dependencies, wheels, image, and
model route; worker isolation with fixed-provider-only egress; trusted offline
execution; a fail-closed and calibrated semantic judge; frozen task
compatibility and QFBench-overlap exclusions; resume, missingness, cost, and
request ledgers; at least three independent paired seed/final repetitions; and
zero QuantCode prompt, metadata, trace, score, cache, evaluator, or judge
feedback contact with the Evolver or candidate selection. A separate
hosted/hidden confirm remains necessary for a blind-generalization claim. This
screen is not an experiment run and is not entered in the QFBench ledger. Full
source audit and claim boundary:
[QuantCode-Bench screen](reports/2026-08-09-quantcodebench-generalization-screen.md).

Confirmed repository evidence:

- Stirrup-on-E2B GDPval run at concurrency 20 hit account-cap 429 errors: [partial run](RESULTS_base_stirrup_e2b_run1_partial.md).
- Concurrency 16 completed 26/30 tasks with mean multimodal score 0.807, but still had infrastructure failures: [completed run](RESULTS_base_stirrup_e2b.md).
- NexAU LocalSandbox baseline completed 30/30 at mean 0.797: [baseline comparison](BASELINES.md).
- A local QFBench oracle canary for `historical-var-data-prep` passed 12/12 tests with reward 1.0 ([run status](../results/qfbench_smoke/20260721T144046+0800_024921eb/run_status.json)). This is a parity anchor, not evidence that the seed worker has passed QFBench.
- The 2026-07-24 extended local implementation suite passes `132 passed, 1 skipped`; it covers pinned sparse loading, split/firewall enforcement, exact task resources, publish-once manifests, minimal two-file base build context, no-secret E2B construction, lifecycle/reaping, offline verifier transformation and dependency locks, official reward parsing with/without CTRF, idempotent upload retry, resume, 3/5-iteration scheduling, and both template transport modes. The standard-library `.venv` intentionally lacks optional NexAU/GDPval/Stirrup dependencies; use an environment with the declared extras for the full suite.
- A local cache canary resolves all three distinct official `uvx` declarations with `UV_OFFLINE=1` and executes the dependency-lock command ([canary report](reports/2026-07-24-qfbench-offline-verifier-cache-canary.md)). The two upstream unpinned requirements resolved to NumPy 2.4.6 and pandas 3.0.5. The local canary alone did not establish Linux/E2B parity; the subsequent isolated oracle and pilot provide that live evidence for these five tasks.
- The shared E2B base and all ten five-task role templates are published under `output/qfbench-e2b-images/20260724T095950+0800_024921eb/`. The base ID is `h4d9iarzjjts2z472o8d`; exact task build/template IDs are in the live-pilot decision and manifests.
- E2B oracle run `qfbench-oracle-20260724T1025` achieved reward 1.0, 12/12 tests, and exact canonical artifact parity for `historical-var-data-prep`.
- Pilot `qfbench-pilot-3-20260724T102755` completed all 16 preregistered attempts. The optimize seed was 1.0; every candidate scored 0.95833325 due to `evt-pot-var` reward 0.833333 and was rolled back for risk-domain regression. No evolution gain was measured.
- Promotion held-out moved from 1.0 to 0.5 while evaluating the identical seed-worker digest twice. The drop was one schema-key error in one binary option-audit check, demonstrating observed model-sampling variation and the inadequacy of a two-task held-out estimate; it is not evidence of worker regression.
- A real coordinator exit 137 left one recorded sandbox. Exact-ID dry-run/reaping killed it, resume did not rerun completed attempts, and final pilot/oracle cleanup scans found no pending IDs.
- The preregistered 30-task run published 50 missing task-role templates, reused the five-task pilot's ten templates and shared base, and completed 140/140 content-addressed official score records over five iterations. It created 140 worker and 136 verifier sandboxes; four worker timeouts skipped verifier creation. Final exact-ID cleanup leaves 276/276 lifecycle manifests cleaned and zero pending IDs.
- All five 30-task candidates were rolled back. Iteration 4 improved observed overall score from 0.500000 to 0.529167 but regressed `systematic_strategy` by 0.25; iteration 5 reached 0.513194 with no domain regression but failed the preregistered 0.02 noise floor. These are measured gate behaviors, not a gain claim.
- Observed 30-task held-out domain macro moved from 0.666667 to 0.583333 and task mean from 0.7 to 0.6 for the unchanged seed worker. One binary task now changes task mean by 0.1 rather than 0.5 in the old two-task panel, but independent model-seed repetitions remain necessary.
- Fourteen attempts are verifier-infrastructure contaminated: six delta-hedging, six swap-bootstrap, and two Form 4 attempts could not resolve the official pytest tool environment with networking disabled. Do not use the current run as an authoritative QFBench performance estimate; preserve it as engineering, recovery, and firewall evidence.
- Three corrected verifier templates were published on 2026-07-26. Run `verifier-cache-20260726-rerun1` executed all 53 collected official tests from empty artifacts with networking disabled, matched every persisted dependency-lock hash, cleaned all three verifier sandboxes, and left zero pending exact IDs. The expected reward zeros are cache-execution evidence only. The run used no worker, model call, oracle lifecycle, or official solution.
- The matched full-harness runs `qfbench-30x5-full-control-20260727-024921eb` and `qfbench-30x5-full-rich-20260727-024921eb` each completed all 140 preregistered official scores using the corrected verifier identities. Control kept zero candidates and had optimize adaptation gain `0.000000`; Rich kept iteration 3 and moved optimize domain macro from `0.564583` to `0.720139`, a gain of `+0.155556`. The result is accepted as adaptation-mechanism evidence, not as a stable causal/generalization claim ([decision](decisions/2026-07-27-qfbench-full-harness-feedback-ab-result.md), [report](reports/2026-07-27-qfbench-full-harness-feedback-ab-report.md)).
- The Rich feedback contract exposed optimize-only public instruction, environment data, public rubric, worker-observable traces/artifacts, sanitized public criterion evidence, and prior candidate outcomes. It continued to exclude official tests, expected/reference values, solutions, credentials, and every held-out task/outcome. Both proposer-surface leak scans passed. Official scoring used deterministic offline verifiers, not an LLM judge.
- Across both full A/B arms, all 554 unique worker/verifier/evolver lifecycle identities were cleaned. The Rich arm resumed from a checkpoint without duplicating completed scores. Rich read 203 evidence records versus Control's 94, but used 2.67 times as much evolver wall time and 15.6% more recorded total execution time; token and monetary totals remain unavailable.
- Held-out evidence remains inconclusive. Rich moved from `0.666667` to `0.583333`, while unchanged Control moved from `0.583333` to `0.750000`. This directly demonstrates that a ten-task panel still does not replace independent model-seed repetitions. The Rich iteration-3 worker remains an experimental candidate and is not the canonical default.

Still required before a formal QFBench evolution-gain claim:

1. Repeat the matched 30-task Control/Rich protocol across at least three independent preregistered model seeds. More tasks reduce cross-task sampling error but do not by themselves estimate model-run variance.
2. Instrument model token/cost, sandbox lifecycle duration, and provider billing totals in durable run artifacts; current runs do not expose authoritative cost totals.
3. Independently rebuild or continue excluding the eight copy-oracle tasks and the pinned inoperable `sec-8k-event-alpha` verifier.
4. Before migrating an experiment arm to any other provider, run provider-specific isolation, resource, recovery, and billing gates; documentation review alone is not compatibility evidence. A new matched E2B panel is not required for continued rootless operation.
5. Preserve the historical 14 contaminated scores. Repair them only if historical score authority is worth a separately identified superseding rescore; the corrected full A/B runs now supply current evidence without rewriting history.

### 2026-07-30 Rootless Self-Hosted Backend Canary

The shared `bc-server` rootless Docker backend passed immutable image/lock, exact-resource, read-only filesystem, bounded exec/noexec tmpfs, worker-proxy, hard offline-verifier, artifact-firewall, force-kill, exact-ID reaper/resume, and cleanup gates at source commit `5d3aa5fcd5ea66a02042ddafd003f651b78149a3`. Run `qfbench-rootless-canary-20260730-r6` replayed the historical `historical-var-data-prep` artifact at official reward `1.0` with 12/12 tests, matching the E2B parity anchor.

The one authorized fresh model request did **not** complete: OpenRouter returned HTTP 403 because `openai/gpt-5` was unavailable from the shared server region. No fresh worker artifact or verifier lifecycle was produced, so this is an infrastructure/model-availability failure, not official reward zero and not end-to-end backend parity. Exact cost remains unknown. All paid-stage proxy/worker resources were cleaned; the final managed container and network counts were zero.

Official tests and test reference data from QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a` remain verifier-only under `/home/julius/qea/runtime/trusted-verifier/024921eb-five-task` with modes `700/600`. A final audit found three executable `test.sh` files had initially retained `0700`; they were normalized to `0600`, and follow-up commit `dbff80d` now enforces owner-only, non-executable trusted files before promotion. This did not change file bytes, hashes, or the measured parity result. Audits found zero trusted payload/hash, secret, forbidden path, or official-solution exposure to worker surfaces. No official solutions were downloaded, uploaded, checked out, or run.

**Decision at that date (superseded):** the rootless backend was retained as a verifier-parity/isolation candidate but was not accepted for formal scoring. E2B remained the only measured formal-scoring backend. Before another paid single-task canary, the gate required either a compliant model-proxy egress that preserved `openai/gpt-5`, or a region-available model treated as a new infrastructure-only identity. See the [gate decision](decisions/2026-07-30-qfbench-rootless-backend-gate.md) and [experiment report](reports/2026-07-30-qfbench-rootless-backend-canary-report.md).

This paragraph records the dated 2026-07-30 gate and is superseded by the
2026-07-31 decision below.

### 2026-07-31 Rootless Five-Task Full-Harness Gate

The approved [direct-cutover design](superpowers/specs/2026-07-30-qfbench-rootless-direct-cutover-design.md) makes self-hosted rootless Docker the default for new QFBench full-harness development and staged scoring; E2B is an explicit fallback, and a new matched E2B run is not a prerequisite. Run `qfbench-rootless-five-rich-1x-20260731-r3` completed one Rich proposal and all 10 scheduled five-task official scores using `deepseek/deepseek-v4-pro`. Optimize macro remained `0.95833325`, held-out seed/final remained `1.0`, and the admitted candidate was rolled back. This is end-to-end backend evidence, not an evolution-gain claim.

The run preserved optimize-only answer-free feedback, independent no-network official verification, verifier-only trusted inputs, credential mediation, exact attempt identities, and final zero managed containers/networks. Scans found no credential, official-test/reference, held-out, or solution exposure. Proxy-readiness and replay-quarantine bugs discovered during the run were fixed in commits `b7d1a2f` and `33e2294`; completed work was reused on resume. All 123 canonical provider requests ended HTTP 200, but their cost/token fields are unavailable and must remain `null`, not reported as zero.

Rootless is accepted only through the five-task one-iteration stage. Before five-task three-iteration or 30-task work, complete a deliberate production full-harness coordinator-kill, exact-ID reaper/resume exercise and authoritative provider-cost reconciliation. The shared-host administrator remains a documented residual risk, and rootless Docker is not microVM-equivalent. Full evidence and the current gate are in the [2026-07-31 decision](decisions/2026-07-31-qfbench-rootless-five-task-full-harness-gate.md).

### 2026-08-03 Baseline Restart After Same-Turn Model Replay

The repetition-01 accounting canary for `qfbench-rootless-base-85x5-official-deepseek-20260801` found 15 duplicated completed request identities across 13 attempts, representing 17 extra HTTP-200 provider calls. Thirteen groups align with the 180-second client timeout while the proxy could wait 300 seconds; two followed completed empty/unusable responses. The run's 85 scores remain immutable engineering evidence, but the run is invalid for repeated baseline performance and must not resume into repetition 02.

The coordinator-uploaded worker adapter now enforces OpenAI SDK `max_retries=0`, NexAU outer `retry_attempts=1`, and a 360-second client-timeout floor. A new content-addressed run must restart at repetition 01 and stop after repetition 02 only after no-model and paid worker/verifier canaries. Historical completed duplicates remain fatal; they are not reclassified as a cost-only exception. See the [superseding decision](decisions/2026-08-03-qfbench-baseline-restart-after-model-replay.md).

This V4 Pro restart action is superseded by the V4 Flash decision below.

### 2026-08-03 V4 Flash Five-Repetition Restart

The stopped V4 Pro no-replay run exited during repetition 01 with seven official
scores and one unscored attempt whose provider calls completed but whose worker
execution did not. Preserve it as engineering evidence; do not import its scores
or artifacts into another model arm. The proxy must record `completed` only after
the full response has been delivered and flushed to the worker.

OpenRouter identifies the requested model as `deepseek/deepseek-v4-flash`. The
new formal arm pins that model to provider `deepseek` with fallbacks disabled and
starts from repetition 01. It runs five independent repetitions of all 85
runnable tasks. Replay uniqueness is attempt-scoped: duplicate request content
within one attempt is fatal, while the same content hash across distinct
preregistered repetitions is valid. The remote sentinel, Mac repair controller,
and continuous run-scoped no-sleep assertion must be bound to the new run before
launch. See the [superseding decision](decisions/2026-08-03-qfbench-v4-flash-five-repeat-restart.md).

### 2026-08-03 Repetition-Boundary Scheduler Epoch Transition

The V4 Flash run keeps repetition 01 at worker/verifier concurrency `4/3` and,
only after a fail-closed 85-score clean boundary, records schema-v2 scheduler
epochs before repetitions 02–05 use `12/3`. Both scheduler and complete runtime
digests are bound per epoch; task/image/worker/model/provider/reward identities
remain fixed. The boundary guard rejects any repetition-02 evidence or residual
resource, and the epoch-2 supervisor owns the complete coordinator process group.

Before formal resume, a separate twelve-standard-task
`paid-baseline-batch` must measure worker overlap 12 and pass canonical cost,
provider route, no-replay, offline-verifier, evaluator-firewall, exact cleanup,
and zero-residual gates. It uses the immutable base worker and no evolver or
feedback input. Final reports must separate epoch 1 from epoch 2 and disclose a
possible scheduler batch effect. Local implementation is verified; the remote
boundary, paid canary, and resumed repetitions are not yet measured. See the
[scheduler epoch decision](decisions/2026-08-03-qfbench-scheduler-epoch-transition.md).

### 2026-08-03 Pre-Send Connect Retry and Fresh Formal Run

The scheduler-transition run stopped in repetition 01 with 85 attempts but only
82 official scores. Two attempts are verifier-only recoverable; the third has
four completed model requests followed by a connection failure proven to occur
before request transmission, and no worker-execution manifest. Replaying the
worker would duplicate accepted stochastic calls, while scoring zero would
misclassify infrastructure failure. Preserve the run unchanged and exclude its
scores from the formal five-repetition aggregate.

The proxy now retries only bounded `connection.connect()` failures before any
HTTP request bytes, with three attempts bound into public config/attempt/image
identity. Generic model-client retries remain disabled, and all after-send
failures remain quarantined. A fresh formal run must rebuild the proxy image and
pass the no-model, provider-route, recovery, twelve-worker paid, cost, firewall,
and zero-residual gates. The `4/3` then `12/3` scheduler epoch protocol applies
to the fresh run, not the frozen run. See the [superseding decision](decisions/2026-08-03-qfbench-pre-send-connect-retry-and-formal-restart.md).

No report may describe adapter compatibility, E2B parity, AutoDL performance, or seed-worker QFBench score as measured until the corresponding run artifact exists.

### 2026-08-11 Two-Week QEA Experiment Synthesis: Foundation through A6

The consolidated Chinese program report covers 2026-07-30 through 2026-08-11:
the self-hosted rootless canary, 85x5 fixed-worker baseline, first full-harness
evolution, and A1-A6 discovery experiments. It reports each stage as Purpose,
What we did, Measured data, and Conclusion; the ME1-ME10 sequence is retained
as an A6 mechanism appendix rather than expanded into a run log. The report
also defines the experiment-internal meanings of `ACT`, A6 `legal ACT`,
`CONTINUE`, `ABSTAIN`, calibrated `ABSTAIN`, probes, checkpoints,
full-harness diff, validation/admission, candidate panel, and semantic
identifiability. In particular, A5's earlier-contract ACT must not be confused
with the stricter A6 legal ACT gate.

Current conclusion: execution foundation and the bounded discovery-control
mechanism are operational, and ME7/ME10 demonstrate truthful calibrated
`ABSTAIN`. No experiment in this period produced the complete productive path
`legal ACT -> non-empty full-harness diff -> validation -> admission ->
<=4-task candidate panel`; therefore harness benefit, formal A6 representation
advantage, transfer, and reward-causal failure-phenotype claims remain unproven.
The next engineering experiment should target public evaluation plus task
evidence for declared targets and a matched success, together with a same-task
schema-2 public-clause/manifested-artifact/trace discriminator. Do not spend
another blind multi-iteration budget on terminal-control changes already proven
by ME10.

Canonical human-readable source:
[two-week A1-A6 Chinese synthesis](reports/2026-08-11-qea-two-week-a1-a6-experiment-synthesis-zh.md),
SHA-256 `afe2b0118eaf1859b2b0672ee906178e80f27f74e88832544f5f576baae441de`.
Rendered PDF:
`output/pdf/qea-two-week-a1-a6-experiment-synthesis-zh.pdf`, SHA-256
`256223ec5fd2599210bc42911c6c3ac45495c6229113092114b139dc2c7d8c16`.

### 2026-08-12 QuantCodeEval mechanism-localization canary

QuantCodeEval is accepted as a two-task **engineering canary**, not yet as a
formal baseline or external validation benchmark.  The pinned adapter uses
official fully-public release commit
`9bdacc4898aeec08813764290b12d356e0a011d1`, starts with T16 and T24, preserves
the official all-properties binary reward, and exposes only aggregate Type-A /
Type-B progress as answer-free Evolver evidence.  The public worker and trusted
verifier roles are materialized into disjoint roots; checker code, property
definitions, golden references, released traces, and prior results never enter
worker or Evolver surfaces.

The next mechanism is the proposed Property-Guided Bidirectional Harness Search:
backward-decompose public finance obligations into localized artifact/trace
evidence, route the resulting error class to one harness component family, and
apply small reversible forward mutations with explicit predicted effects.
This is intended to move beyond A6's validated control flow and calibrated
`ABSTAIN` toward the first legal ACT, non-empty diff, validation/admission, and
two-task candidate panel.  Full source audit, related-work comparison,
implementation scope, evidence-retention rule, and live-run gates are in the
[2026-08-12 decision](decisions/2026-08-12-quantcodeeval-canary-and-property-guided-search.md).

An ephemeral exact-revision T16/T24 source subset successfully materialized into
disjoint roles: 11 public files (1.6 MiB) and 190 trusted files (2.1 MiB), with
zero forbidden-answer scan matches.  T16 exposes only aggregate progress over
6 Type-A / 12 Type-B properties and T24 over 7 / 10.  Every consumed upstream
path must be tracked and clean against pinned `HEAD`, and the upstream
environment hashes are checked.  The focused suite passed 93 tests, including
a complete missing-target zero-reward path and dirty-source rejection.  The
complete NexAU-enabled suite passed `1195 passed, 1 skipped` when loopback socket
binding was allowed.  The existing
base worker `qea/worker_gdpval_weak` is confirmed shell-only at digest
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`.

No durable source/role snapshot or runtime image was built, the official
checker suite was not executed against a strategy, and no model call,
QuantCodeEval task score, candidate, or harness-benefit result exists at this
date.  Adapter tests and role materialization are implementation evidence only.

The preceding launch-readiness state is superseded by the measured result
below; it remains here as dated provenance rather than being rewritten.

### 2026-08-12 QuantCodeEval five-round engineering result

The T16/T24 canary now has a measured isolated runtime, golden parity and
firewall audit, one shell-only H0 baseline, five complete PGBHS iteration
records, and a content-addressed seven-surface evidence release.  The release
identity is `4d3813bfc58afb48ad0eb25f9e028a8529f5d4159bd2803cd4fe175f744c5499`
and its manifest SHA-256 is
`658b79356179d09cdda0770c9f6cedb17a61e8c0ed8b728f0c9811ef10a69199`.
It contains 1,255 files and 39,465,784 bytes, including all H0, superseded
negative, candidate, score, cost, admission, rollback, and lifecycle evidence.

H0 used the shell-only worker digest
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`:
T16 passed 18/18, T24 passed 15/17, official vector `[1, 0]`, 34 requests,
537,527 tokens, and exact cost `$0.0332853304`.  Search reused that exact
evaluation with `resampled=false`.  Five candidates used 200 requests,
6,152,505 tokens, and exact cost `$0.1532859160`.

All five rounds completed the productive engineering path `legal ACT ->
non-empty systemprompt diff -> admission -> two-task panel -> selection or
rollback`.  Iteration 5 repaired the observed resource-termination phenotype:
relative to iteration 4, T24 moved from 59 requests with no artifact and 17
SKIP to an early importable artifact and complete 15/17 checker execution;
the two-task request count fell from 76 to 23 and T16 remained 18/18.  This is
measured activation and mechanism-localization evidence, but not a formal
causal estimate because the samples are stochastic and unrepeated.

No candidate improved the H0 official or property-family vector.  All were
rolled back, the final incumbent remains H0 `[1, 0]`, and no QuantCodeEval
gain, transfer, or generalization claim is supported.  The next experiment is
a matched shell-only versus prompt-checkpoint versus deterministic-middleware
comparison across independent seeds, followed separately by executable public
unit/timing/accounting self-checks.  See the
[full measured decision](decisions/2026-08-12-quantcodeeval-five-round-canary-result.md).
All 60 retained lifecycle records report `cleaned_up=true`; final remote
inspection found zero managed containers and zero `qea-*` networks.  The local
NexAU-enabled regression suite passed `1255 passed, 1 skipped` when loopback
binding was permitted.

### 2026-08-12 QuantCodeEval v2 variable full-harness search

The fixed five-round prompt-only search definition is superseded by a
variable-length full-harness mechanism. The earlier measured five-round H0,
candidate, score, cost, runtime, and negative evidence remain valid historical
artifacts and are not overwritten.

The v2 Evolver may revise and smoke-test one primary component plus all files
required to bind the same mechanism. Exact parent/candidate snapshots, diffs,
component tests, activation, answer-free evaluation, and selection/rollback
state are stored content-addressably. From round two onward, prior rejected and
accepted experiences are projected into immutable Evolver evidence; an ACT
must inspect an exact prior entry, diff, or source snapshot. Official incumbent,
diagnostic search parent, and bounded archive are separate.

A deterministic no-model canary measured prompt-only rejection followed by a
second-round `tools + tool_descriptions + agent_config` mutation that read the
rejected patch, passed independent admission, and stopped on its fixture target
after two rounds. This is mechanism evidence only: fixture reward vectors and
request counts are not QuantCodeEval measurements. Final artifact
`results/quantcodeeval-v2-mechanism-canary-20260812-v5/RESULT.json` has SHA-256
`2e6ef538917d7408479d0413b6787cb89d74ff755994179750a1c95de39d563b`.
Every component smoke is now bound to the exact full candidate digest; later
edits invalidate that smoke. The focused activation/mechanism suite passed `51
passed`; a full rerun passed `1280 passed, 1 skipped` with one retry-audit
timing flake, and that exact test immediately passed alone. The persisted
canary passed `1 passed`.

The next live step is the implemented one-round real Evolver activation canary,
not a multi-round score claim. It reuses the exact published H0 and stops before
candidate benchmark evaluation. The measured T24 resource
failure should first route to deterministic early-checkpoint `middleware`;
quant correctness should then be tested separately with executable `tools` or
`validator` components. See the
[superseding v2 decision](decisions/2026-08-12-quantcodeeval-v2-variable-full-harness-search.md)
and [mechanism report](reports/2026-08-12-quantcodeeval-v2-mechanism-canary.md).

### 2026-08-12 QuantCodeEval v2 live activation r1

The first real v2 activation did not repeat prompt-only search. It compared
unit-scale and temporal-lag mechanisms, added and registered a deterministic
strategy-validation tool, exercised clean/defective/100-times-scale local
fixtures, removed those fixtures, and passed independent full-harness
admission. The exact candidate digest is
`5d73211371ffdaf116f845846d980d14e4370d412ced3fba910bdb27607488f3`.

The candidate was correctly rejected before benchmark evaluation because its
decision declared conceptual role `validator` while all validator code lived
under structural role `tools`; declared and actual file roles differed. H0 was
not resampled, no worker/verifier ran, and no candidate QuantCodeEval score is
claimed. The run used 34 successful requests, 1,611,603 tokens, and exact cost
`$0.0377605312`; all managed resources were cleaned.

The superseding mechanism contract now makes component roles exact file loci,
stores attribution/stale-smoke rejection as immutable searchable history, and
allows earlier failed draft tests while requiring latest final-digest primary
smokes. A follow-up activation can import r1's exact candidate/diff/decision as
round history. See the
[measured r1 report](reports/2026-08-12-quantcodeeval-v2-live-activation-r1.md).

Follow-up r2 proved exact r1 history import but exposed a zero-request evidence
firewall naming collision (`history/tests`); the Evolver projection is now
`component_checks`. r3 then measured real inter-round recall: the Evolver read
r1's exact entry, diff, validator source, config, and prompt, and correctly
probed that r1 was rejected for declarative attribution rather than mechanism
failure. r3 still stopped before scoring because the decision tool schema used
`failure_prediction` while its implementation used `prediction`, leading the
model to fall back to a legacy schema-1 unlock. This is now fixed and legacy
unlock is forbidden under quant v2. r3 used 29 requests, 1,506,130 tokens, and
`$0.036206044`; H0 was not resampled and no worker/verifier ran.

r4 then passed the complete activation mechanism. It persisted schema-4 ACT,
declared exact file roles, performed multiple draft/self-test repairs, removed
temporary fixtures, reran final-digest tool and graph smokes, and passed all
nine independent admission checks. Candidate digest is
`9a72fc74626774a24bda67d55bd25c39f06d35e1f3a20416dedd61ef5c092089`,
history entry is
`287323ea195f13f5983f351bf65f099c123fd8814240465b9f6106ff01df64b6`,
and activation result identity is
`c9ff158996c34faf74547b409d1500cfb3d1825d4a4b8df07a297cafe71d1fac`.
r4 used 48 requests, 3,037,562 tokens, and `$0.0345887416`. It did not run the
candidate benchmark panel and makes no T16/T24 score claim. Provider-turn
request/cost reconciliation is now wired into outer search accounting.

## Memory Maintenance Rules

- Update this file when a decision is accepted, superseded, or invalidated.
- Add detailed evidence as a dated report or decision record; keep this file an index and current-state summary.
- Never silently rewrite historical result files. Record an explicit superseding decision instead.
- Pin commit IDs, dataset hashes, image digests, verifier versions, model/provider identifiers, and run IDs in every publishable experiment.
- Distinguish `measured`, `source-audited`, `proposed`, and `not yet tested` claims.
