# QEA Repository Memory

## 2026-08-23 property-wise protection ablation retained

The offline A2 replay compared aggregate-only and property-wise promotion on
two retained official protection reports without new model or Worker calls.
Both rules promoted the safe holdings case at 42/42 to 42/42. On
`localvol-barrier`, both parent and Search-v2 candidate remained 38/39 with
reward 0.96, but the failed property changed from
`barrier_outputs_reasonable` to `vanilla_mc_close_to_surface`. Aggregate-only
would promote; property-wise protection correctly rolls back under the
accepted no-new-failed-property criterion. The policies therefore disagreed
on one of two cases.

This is evidence that property identity can alter harness selection when
aggregate performance ties. It is a verification ablation, not evidence that
QRS search beats a generic Evolver and not a new benchmark evaluation. Full
record: `docs/decisions/2026-08-23-property-wise-protection-ablation.md`;
compact result: `data/breadth/QF_PROTECTION_POLICY_ABLATION_RESULT.json`.

## 2026-08-22 thin Main-0 lifecycle controller retained

The thin fixed controller is retained for the next QFBench campaign. It uses a
plain JSON lineage with target, independent repeat, protection, promotion or
rollback, freeze, cost accounting, and resumable ingestion of completed child
reports. The no-model replay reproduced both retained decisions: holdings
48/51 to 50/51, repeat 37/51 to 50/51, and protection 42/42 to 42/42 produced
`PROMOTE`; local-vol repeated two binary gains but exchanged one failed
protection property for another and produced `ROLLBACK`. A second replay did
not duplicate cost, archive, or decisions.

In the real live path, the controller imported the retained holdings target
and repeat, then dispatched a fresh normal-budget `brinson-sector-attribution`
protection comparison. Quant-H0 and candidate both scored 42/42 with reward 1.
The candidate called `reconcile_portfolio_deliverables` once, received a
grounded skip because the task had no holdings-file deliverable set, and did
not regress. The controller automatically promoted `holdings-qrs-v1`, froze
the lineage, and resumed again without rerunning the child. The live child used
16 completed requests, 167,113 tokens, and $0.015420772; the complete imported
lineage accounted for 151 requests, 5,619,133 tokens, and $0.533176724. The
successful service had zero restarts, retries, unreconciled requests, active
processes, containers, or networks.

This is lifecycle and small-scale readiness evidence around already retained
autonomous candidates, not a complete from-H0 proposal campaign, matched
relation transfer on Brinson, sealed gain, or benchmark-wide improvement. The
controller remains ordinary infrastructure; the quant-specific claim remains
Research-State-conditioned relation search and activation--state--outcome
verification. The two task-family applicability and claim boundaries are
frozen in `data/breadth/QF_MAIN0_RELATION_APPLICABILITY.json`. Full decision:
`docs/decisions/2026-08-22-thin-main0-controller-result.md`; compact result:
`data/breadth/QF_MAIN0_THIN_RESULT.json`.

Do not run the remaining 20 licensed QuantCodeEval tasks before Main-0. The
current adapter supports the ten credential-free public tasks; the remaining
20 require active WRDS dataset entitlement and new adapter/runtime work. T28
and T29 also still need public-task materialization/parity. If extra breadth is
needed later, prefer one blind Quant-H0 T27 canary before licensed expansion.

## 2026-08-22 Search-v2 repeated binary gain and matched property swap

Search-v2 is retained as a positive search-mechanism result, but its frozen
candidate is archived rather than promoted. Under the same Quant-H0, runtime
evidence, history, model route, answer access, full mutation surface, and
proposal limits, the strong generic Evolver returned calibrated `ABSTAIN`.
Quant-state-v2 selected `maturity_propagation_terminal_completeness` as its
primary relation and `local_vol_surface_terminal_coverage` as one independent
residual-risk relation, then admitted a prompt-only refinement.

On two independent normal-budget `dupire-local-vol` comparisons, fresh
Quant-H0 scored 65/68 and 66/68 with reward 0; the same frozen candidate scored
68/68 with reward 1 both times. Its artifacts realized the predeclared
terminal-maturity, full-surface-coverage, and no-missing-cell observations.
On matched `localvol-barrier`, Quant-H0 and candidate both scored 38/39,
reward 0.96, and the candidate actually executed the maturity/surface audit.
However, Quant-H0 failed `barrier_outputs_reasonable` while the candidate
failed `vanilla_mc_close_to_surface`. Aggregate performance was preserved but
the property set was not Pareto-safe, so the candidate is a real rollback path,
not a stable/reusable promotion.

The complete path used 228 completed requests, 13,880,354 tokens, and
$0.515488768, with no retry, replacement, or unreconciled attempt. Search-v2
therefore closes the pre-main repeated-binary-gain gate and shows that the
quantitative relation representation can change search, but it does not prove
general superiority, safe reuse, Main-0, or sealed benchmark gain. Before
Main-0, freeze a small public-relation applicability table for the proposed
tasks and implement only the thin JSON lifecycle controller that ingests
existing child reports and performs target, repeat, protection, promotion or
rollback, and resume. Full decision:
`docs/decisions/2026-08-22-search-v2-localvol-result.md`; compact record:
`data/breadth/QSTATE_SEARCH_V2_RESULT.json`.

## 2026-08-21 Search-v2 and pre-main gates

Proceed with one bounded Search-v2 canary before Main-0. The method story is
**Evolving the Quant Researcher** by changing the persistent research
capability substrate, not claiming a new generic harness-evolution outer loop.
The six Research States are open coordinates; the domain contribution is a
task-conditioned quantitative relation prior that changes experience
retrieval, component localization, intervention scope, and
activation--relation--outcome evidence.

Search-v2 retains one primary intervention relation and permits at most one
independently supported residual-risk relation. This is not a mandatory slot
or finance failure taxonomy. Launch preflight rejected the initially proposed
corporate-action pair because corrected evaluator replay had already
invalidated its historical low score. The superseding pair is
`dupire-local-vol` to `localvol-barrier`, using the observed transition from
calibration-parameter admissibility to unresolved forward-variance maturity
consistency. Compare a strong generic Evolver with quant-state-v2 under
matched evidence, history, routes, mutation surface, explicit component-use
contract, and evaluation gates. Both arms receive the same prior candidate and
its scored runtime experience. Use proposal-only discovery, then normal
target, conditional repeat, and a matched second task only after a repeated
gain. Hard limits are two candidates, nine Worker sessions, $0.75 before
starting a new stage, and six hours.

Do not start Main-0 merely because V2 code or a proposal succeeds. Before
Main-0, require a source-level coverage screen of the planned tasks, a
domain-specific positive observation such as repeatable gain or genuine
matched-relation execution, and a thin JSON-backed candidate-lineage
controller with target, repeat, protection, promote/rollback, cost boundary,
comparator cache, and resume tests. Main-0 should use two screened pairs, two
lineages, and at most two candidates per lineage. Main-1 sizing remains
proposed until Main-0 measures cost and long-tail wall time. Full decision:
`docs/decisions/2026-08-21-search-v2-and-pre-main-gates.md`.

## 2026-08-21 evolving-the-quant-researcher story and search-method gate

Before expanding the candidate-scale controller, freeze the proposed story as
**Evolving the Quant Researcher, Not the Strategy**. Quant Research State is
now treated as a task-conditioned representation of information, economic,
convention, estimation, derived-result, and artifact state. The proposed method
must use that representation to change evidence retrieval, component routing,
probe selection, or intervention verdict; finance-shaped labels alone are not
a mechanism.

Candidate history, exact-parent evidence, rollback, caching, independent search
replicates, and scheduling remain necessary infrastructure rather than
quant-specific novelty. Point-in-time work is one relation family---
point-in-time effective-state reconciliation---rather than the name of the
search. The generic full-harness comparison remains strong and matched; a valid
result may be comparable frozen official performance with fewer Worker or
verifier calls, fewer inactive or mislocalized interventions, or fewer
protection regressions.

The compact State Card search path now has a no-model implementation preflight:
the Evolver can materialize a task-conditioned card after reading supporting
evidence, query the existing component catalog by state/relation/component
coordinates, bind an `ACT` to the selected relation and component locus, and
retain activation, state correction, official gain, and stability as separate
verdict levels. Generic and quant-state coordinated views share the same
history and diagnostics; only the operational card/retrieval helper differs.
This is an implemented mechanism fixture, not a live search result or benchmark
gain. The next gate remains the bounded two-family generic-versus-quant canary
with at most four initial candidates; only after that should work return to a
simplified Main-0 controller and the Main-1 runway. See the
[story backup](decisions/2026-08-21-evolving-the-quant-researcher-story-backup.md)
and [method specification](superpowers/specs/2026-08-21-quant-research-state-guided-search-method-spec.md).

## 2026-08-21 point-in-time lineage refinement and rollback

The first complete point-in-time feedback refinement path ended in rollback.
After two observed setup repairs, a `LINEAGE_REFINEMENT` Evolver inspected the
exact 50/51 parent skill and Worker observation, selected `REFINE`, changed only
the skill's canonical-label rule, passed admission, and activated in a short
probe and a normal-budget Worker. The short probe delivered no artifacts; the
normal Worker delivered all eight but scored 49/51, below the 50/51 parent and
without fully realizing the predicted label-consistency transition. No repeat
or protection ran; the parent remains unchanged.

The setup repairs are required for scale: feedback bundles now carry the exact
tested parent source; later feedback uses a refinement contract rather than
repeating `COORDINATED_BREADTH`; and long JSONL trace lines are excerpted around
the match to reduce Evolver context growth. The valid r4 chain used 59 requests
and $0.249454672; the full localization path including one calibrated ABSTAIN
and one setup-invalid attempt used 81 requests and $0.52965072. See the
[measured decision](decisions/2026-08-21-point-lineage-refinement-result.md)
and [compact result](../data/breadth/MT_POINT_LINEAGE_REFINEMENT_RESULT.json).

## 2026-08-21 runway to stable main-experiment scale

The next scale unit is a serialized candidate lineage, not a fixed five-round
loop and not an unbounded Evolver conversation. One current parent produces one
candidate; a normal-budget target gain triggers a repeat, then a matched
protection check, and only a repeat-confirmed protection-safe candidate becomes
the next parent. Short probes remain activation/completion diagnostics and are
not numeric rejection gates for observed long-tail tasks. Parent-task outcomes
are cached while the parent and run contract stay unchanged, so rejected
candidates do not force every long task to rerun.

Independent lineages and eligible Worker evaluations may run concurrently, but
promotion within one lineage is serialized. Main-0 will rehearse this controller
on four screened pairs and two lineages before a proposed 12-optimize, six-
protection, 12-sealed-task Main-1 panel is preregistered. Sealed results never
guide candidate selection. See the
[scale decision](decisions/2026-08-21-candidate-lineage-main-scale-runway.md)
and [compact protocol](../data/breadth/QF_MAIN_SCALE_RUNWAY.json).

## 2026-08-21 independent-pair breadth result

Four isolated QFBench pair Evolvers started from the same Quant-$H_0$ and did
not share their candidates. Three returned `ACT` with executable candidates
and one returned calibrated `ABSTAIN`. Experimenter-arranged normal-budget
fresh confirmations produced two real component activations on two target
families. The point-in-time `effective-state-reconciliation` skill improved
`13f-amendment-aware-crowding` from the corrected retained 46/51 to 50/51; the
same frozen candidate preserved `fomc-tone-event-study` at 20/20 but the
protection Worker did not load the skill. The copula artifact validator
activated but tied its retained comparator at 27/28. The option candidate was
not used and regressed to 65/68; the carry/basis lineage abstained.

This establishes bounded breadth of autonomous component search and one fresh
property-gain event outside the earlier local-vol task. It does not establish
binary gain in this batch, concurrent-H0 causal superiority, repeated
stability, or protection-side component reuse. Short probes again
underestimated normal-budget capability: both 13F and copula short Workers
ended before artifact delivery, while their normal-budget Workers completed.
See the [measured decision](decisions/2026-08-21-qfbench-independent-pair-breadth-result.md)
and [compact result](../data/breadth/MT_INDEPENDENT_PAIR_RESULT.json).

## 2026-08-21 coordinated local-vol result

The bounded multi-task route now has one local binary target gain, but the
candidate failed protection and is not promoted. Corrected evaluator replay
invalidated the original rates and corporate-action low-score screens, then
identified a nearby derivatives pair: `dupire-local-vol` at 67/68, reward 0,
and `localvol-barrier` at 38/39, reward 0.96.

The Evolver autonomously synthesized `validate_surface_artifacts`, then used a
failed short probe as persisted runtime feedback to select `REFINE` and modify
the system prompt, tool description, and executable validator. Both bounded
10/12-request probes ended before artifact delivery or component activation.
An experimenter-arranged normal-budget fresh confirmation of the frozen r3
candidate subsequently called the component five times and improved
`dupire-local-vol` to 68/68, reward 1. The unchanged candidate called the
component three times on `localvol-barrier` but regressed to 36/39, reward
0.92. This establishes a bounded local chain from autonomous component
refinement to fresh activation and official binary gain; it does not establish
stable transfer, pair-level promotion, or benchmark-wide improvement.

The normal-budget target needed 50 Worker turns, while the short probes never
reached delivery. The next mechanism problem is therefore joint completion and
stopping efficiency plus protection-aware scope refinement, not immediate
full-panel scheduling. See the
[measured decision](decisions/2026-08-21-qfbench-coordinated-localvol-result.md),
[compact result](../data/breadth/MT_LOCALVOL_R3_RESULT.json), and the earlier
[parallel-pair design](decisions/2026-08-21-parallel-multi-task-pair-canary.md).

> Canonical research and architecture memory for future contributors and agents.
> Last updated: 2026-08-21. This file records current decisions, not merely historical discussion.

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

GDPval, PRBench, hosted blind sets, and sealed held-out answers must never enter proposer-facing prompts. A declared optimization task may return post-run rubric answers, expected-versus-observed diagnostics, and counterexamples to the Evolver only. The Worker remains blind, protection/transfer tasks remain answer-free, and no task answer may be persisted in a reusable harness component. This scoped exception and its split semantics are defined in [the 2026-08-16 answer-rich Evolver decision](decisions/2026-08-16-answer-rich-evolver-and-task-conditioned-harness.md).

## Execution Architecture Decision

High-parallel memory pressure primarily comes from one NexAU `Agent` per task, 200k-token contexts, up to 60 turns, `InMemoryTracer`, and concurrent document rendering—not from the small keep/rollback controller state.

Adopt the original AHE pattern in stages:

1. **Current default:** keep the trusted QEA coordinator on the persistent `bc-server` user account and run evolver, worker, credential-proxy, and independent offline-verifier roles in attempt-isolated rootless Docker containers.
2. Return compact summaries, rewards, artifact manifests, and trace URIs to the coordinator. For a declared answer-rich optimization task, the trusted coordinator may also construct a post-run Evolver-only rubric diagnostic; it never enters the Worker or a reusable candidate.
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

The first r4 full-candidate launch subsequently passed exact preflight but
failed before verifier scoring at the worker artifact contract. T16 completed
seven requests and exceeded the three-file output limit with bytecode-cache
side effects; T24 completed eight requests and delivered no `strategy.py`.
Together they used 226,685 tokens and exact cost `$0.0218750168`; every
recorded resource was cleaned. This is measured component-delivery failure,
not a task reward vector. The original exception lacked a top-level result, so
the mirror now contains an explicitly recovered answer-free failure record,
and future runs persist that record during the failing call. A later Evolver
round may import the exact failed candidate as immutable history while keeping
H0 as incumbent and unresampled. See the updated
[live activation and full-candidate report](reports/2026-08-12-quantcodeeval-v2-live-activation-r1.md).

r5 then proved that the Evolver consumed both earlier failure classes and
changed the validator's delivery behavior, but it left
`tools/_selftest_strategy_validate.py` in the final harness. Its own later
smokes passed, while independent admission rejected the unbound Python module.
No benchmark ran. r5 used 35 requests, 2,345,431 tokens, and exact cost
`$0.0435037288`; all resources were cleaned. The outer loop now persists this
admission failure as a rejected history entry, and multiple ordered rejected
attempts can be imported so the next round sees r1, r4 full-panel, and r5
together. The result is measured component-contract evidence only; see the
updated live/full-candidate report above.

r6 then imported all three prior negatives: the r1 attribution mismatch, the
r4 worker-delivery failure, and the r5 admission rejection. It removed the
retained self-test, changed executable tool code plus its registration,
description, and activation prompt, passed component smokes and independent
admission, and reached activation `PASS`. The activation used 31 requests,
2,134,291 tokens, and `$0.0395237752`; H0 was not resampled and all three
recorded resources were cleaned.

The r6 candidate subsequently completed the two-task panel, with a negative
result. T16 regressed from 18/18 under H0 to 12/18 and reward 0. T24 again
finished without `strategy.py` and received reward 0. The panel used 24
requests, 362,946 tokens, and `$0.0131630576`; all eight recorded resources
were cleaned. This falsifies the current broad validator intervention: it
damaged the protected passing task and did not fix the target task's delivery.
The next engineering direction is a smaller task/failure-conditioned component
that guarantees final artifact delivery without applying quant validation to
already-passing tasks. Do a local component smoke first, then a small task
panel; do not add more general validator complexity.

That component direction is an investigator hypothesis, not the answer to give
the Evolver. The next live round must receive the answer-free r1/r4/r5/r6
history and an open full-harness mutation surface, then autonomously propose
the mechanism, choose its component, implement it, and design its local smoke.
Do not instruct it to build an artifact finalizer or completion middleware.
An investigator-written finalizer is reserved for a later diagnostic control
only if autonomous search cannot localize or implement a working mechanism;
that control would test the mechanism separately from search capability.

The accepted execution order is now explicit. Reuse the published H0 without
resampling, run the focused deterministic mechanism tests, then launch one real
autonomous round. Only a non-empty candidate that passes its component smoke
and independent admission reaches the T16/T24 panel. Feed its answer-free result
back into later rounds and continue while the search adds new information; five
rounds is not a requirement. A diagnostic improvement may become the next
search parent without becoming the official incumbent. Expand beyond T16/T24
only after this mechanism canary works. See the
[next-round decision](decisions/2026-08-12-quantcodeeval-next-autonomous-round.md).

The next autonomous round, r8, then established the missing end-to-end
activation result. The Evolver read the accumulated answer-free r1/r4/r5/r6
history, selected a T24 unit-scale hypothesis, and changed agent configuration,
the system prompt, a tool description, and executable tool code. Its new static
strategy audit passed component smokes and admission and was actually called by
the real T24 worker. This is the first measured QuantCodeEval round here in
which an autonomously proposed executable component was both activated and
evaluated.

The official candidate vector remained `T16=1, T24=0`, task mean `0.5`, so no
benchmark gain is claimed. The more informative property result was partial:
H0 failed one Type-A and one Type-B T24 property, while r8 passed every Type-B
property and retained one Type-A failure. The mechanism therefore helped one
failure family without crossing the benchmark's all-properties gate. Search
and evaluation together used 56 requests, 2,875,559 tokens, and
`$0.0958629504`; both services exited successfully with no residual experiment
containers or networks. The next round should import this scored result and
focus its autonomous component choice on the residual Type-A semantics while
retaining T16 as the protected passing task. See the
[r8 autonomous tool canary report](reports/2026-08-12-quantcodeeval-r8-autonomous-tool-canary.md).

r9 then imported both r6 and r8 as independently scored history, in addition
to the earlier rejected and unscored failures. The Evolver correctly recognized
the r8 partial result and expanded the static audit to cover declared output
columns, window causality, and calendar indicators. Tool import, graph smoke,
and admission all passed, but the official panel regressed to `T16=0, T24=0`.
T16 passed only 3/18 properties. T24 did not produce an artifact because the
model consumed the full 32,000-token reasoning allowance and returned an empty
response; a fixed-candidate T24-only retry reproduced the same five-request
failure. Search, panel, and retry together used 49 requests, 2,908,883 tokens,
and `$0.0808046904`, with no residual experiment containers or networks.

This falsifies continued growth of a broad static audit as the immediate
mechanism direction. Trusted diagnosis also found that r8's only T24 property
failure crossed an inconsistent interface: the public contract specifies a
one-argument strategy-return function, while the differential reference
pipeline calls it with the separate scale returned by the preceding function.
Do not teach that hidden call to the Evolver. Correct and rebaseline the T24
adapter separately. For mechanism discovery, retain r8 as partial evidence,
test a compact investigator-authored public-data behavior probe, and expand to
self-contained tasks T01, T12, T18, and T19 rather than further overfitting T24.
See the
[r9 negative report](reports/2026-08-12-quantcodeeval-r9-structural-audit-negative.md).

### 2026-08-12 speed-first experimental engineering policy

Repository engineering is now explicitly mechanism-first rather than
security-first. Avoid over-defensive infrastructure, new content hashes, and
tests for implausible cases. Preserve enough evidence to reconstruct setup,
candidate changes, scores, costs, and observed failures; an engineering canary
does not require exhaustive equality of every runtime contract. Prefer a small
smoke or preflight and fast iteration, while retaining only the minimum
research boundaries around verifier answers, credentials, truthful scoring,
and obviously invalid runs.

Before the next live run, a macOS repository-health audit found no damaged Git
repository in the active workspace or its sibling projects: all discovered
repositories and nested benchmark repositories resolved normally, had no lock
or interrupted-operation residue, and passed connectivity checks. The active
repository does have three valid ignored worktrees under `.claude/worktrees`,
with three additional benchmark repositories nested inside one worktree. It
also retains a large set of old unreachable loose objects created together on
2026-07-28; no cleanup was performed because those objects may still be useful
for recovery.

The heat symptom is operationally credible and should be mitigated before paid
runs. During an otherwise idle eight-second window, macOS recorded 15 new Git
processes, while Codex Desktop logs showed repeated review-summary Git commands
being canceled rather than repository failures. A contemporaneous
`syspolicyd` burst tracked many short-lived Git processes and was followed by
repeated `trustd` signature checks. This matches an open Codex Desktop macOS
issue involving source-control polling, nested repositories, and Gatekeeper
validation.

The post-exit A/B check refined the attribution. After Codex Desktop and its
helper had fully exited, `syspolicyd` and `trustd` remained idle and the Git
spawn rate fell from about 1.9 per second to about 0.7 per second. The remaining
activity arrived as four-process waves approximately every five seconds. A
short parent-process trace attributed every captured Git process in those waves
to the Visual Studio Code extension host (`Code Helper (Plugin)`), not to Codex
CLI. Therefore Desktop was a contributor to the original amplification but not
the only source of Git polling. For the cleanest long-run setup, use Codex CLI,
fully quit VS Code as well, and recheck activity; if VS Code must stay open,
limit it to the repository and disable unnecessary Git refresh or fetch. Treat
worktree removal or Git object cleanup as separate user-approved maintenance.

A complete Desktop restartability check then passed. No Desktop process or
helper remained before launch; the app restarted with its renderer, service,
app-server, and computer-use helper alive after the startup interval and without
an immediate crash. A normal application quit removed the Desktop main process
and runtime helpers again. Four older `node_repl` processes were verified as
children of the active terminal Codex CLI and intentionally left running. The
machine is therefore back in CLI-only state, and a full Desktop exit does not
prevent a later normal restart.

### 2026-08-13 QuantCodeEval public-probe expansion

The self-contained QuantCodeEval engineering panel now contains T01, T12, T18,
and T19 and does not require WRDS. Its shell H0 replay vector was all zero at
the official all-properties gate, with property progress `2/17`, `14/16`,
`16/18`, and `16/18`. Transferring the autonomous r8 static-audit candidate
produced `T01=0, T12=0, T18=0, T19=1`: T19 reached 18/18, while T12 regressed
to 8/16 and T01/T18 were unchanged. This is a narrow positive transfer, not a
general harness improvement.

An investigator-authored public behavior-probe worker then tested a different
mechanism. It adds a quant-definition arbitration skill plus an executable
probe over public instructions, public data, and synthetic examples; it does
not receive checker output. T12 v1 passed 7/16. After making competing
definitions, public basis, and portable data lookup explicit, a T12-only v2
sample passed 16/16, but a fresh four-task sample passed only 12/16. The full
fresh vector was again `0,0,0,1`: T01 remained 2/17, T18 produced no artifact,
and T19 passed 18/18. A separate T18 retry wrote a candidate, activated the
probe and skill, and still passed only 16/18, identical to H0. Therefore the
T12 effect is promising but not stable, and T18's missing artifact is a
separate sampling-sensitive completion problem rather than evidence that the
probe was sufficient.

This localizes the next search target. Do not globally accumulate more static
rules or claim the manual component was Evolver-discovered. Use the manual
worker as a diagnostic search parent and expose the answer-free contrast to the
Evolver: activated success on T19, activated non-improvement on T01, unstable
definition choice on T12, and completion-versus-correctness separation on T18.
Keep the full mutation surface open and let the Evolver choose among routing,
memory/state, executable candidate/probe consistency, completion middleware,
or another supported mechanism. These are competing investigator hypotheses,
not a prescribed artifact finalizer. Retain every attempt as searchable
history, run a local component smoke before a small official panel, and keep
the search variable-length. Full measurements, costs, activation counts, and
evidence paths are in the
[public-probe expansion report](reports/2026-08-13-quantcodeeval-public-probe-expansion.md).

**Measured later on 2026-08-13:** the first autonomous round over this
four-task contrast produced a legal ACT and an executable, non-prompt-only
candidate. The Evolver selected a real-data contract audit and changed the
public probe tool, its tool description, and the system prompt. Component
smoke and admission passed. On a fresh candidate panel, property progress
changed from `2/17, 12/16, 16/18, 18/18` to
`3/17, 15/16, 16/18, 18/18`; the official vector therefore remained
`0,0,0,1` and task mean remained `0.25`. The candidate preserved T19 and
improved some properties, but solved no new task. Activation cost was 45
requests, 2,662,056 tokens, and `$0.0471596608`; candidate sampling cost was
136 requests, 6,250,275 tokens, and `$0.1638542808`.

Do not promote or cumulatively layer this candidate. Its central limitation is
now measured: T01's worker-declared real-data audit and probes were green while
the official answer-free families were only Type-A `3/7` and Type-B `0/10`.
Checking a self-declared contract cannot correct a mistaken reading of the
public instruction, and the added audit also induced long repair loops. The
next round should restart from the same diagnostic parent with this exact
candidate diff, component tests, per-task outcomes, cost, and rollback reason
available as searchable history. Ask the Evolver to compare alternative ways
to obtain an independently checkable public semantic contract; keep the full
harness mutation surface open and T19 as the protection task. Detailed
evidence is appended to the
[public-probe expansion report](reports/2026-08-13-quantcodeeval-public-probe-expansion.md).

**Measured later on 2026-08-13:** a second autonomous round successfully used
the exact scored history from the rejected contract-audit candidate. Two
initial activations failed before mutation because long model responses returned
no usable content. Requiring the Evolver to inspect the candidate and map
evidence in its first response repaired the response-control failure. The next
activation completed, compared three causes, rejected environment mismatch and
failure-to-read-the-paper, and selected a parameter-identity gap. It modified
the quant-contract-arbitration skill plus system prompt to derive library
arguments from paper equations and test each mapping with an independently
computed fixture. Component smoke and admission passed.

The resulting four-task candidate sample produced property progress
`5/17, 16/16, 16/18, 18/18` and official vector `0,1,0,1`, for a task mean of
`0.50`. This is the first autonomous branch in this panel to solve an
additional task while preserving T19. It is not promoted, because an immediate
T12-only repeat of the same harness passed only `8/16` and returned reward 0.
The observed gain is therefore sampling-sensitive, not a stable mechanism
result. The full panel cost 104 requests, 3,266,600 tokens, and
`$0.1133131552`; the repeat cost 16 requests, 320,141 tokens, and
`$0.0170303784`. The successful activation cost 39 requests, 2,294,526 tokens,
and `$0.0346782856`; the two failed response-control attempts are retained as
negative evidence.

Do not cumulatively layer or promote this candidate. Keep it in searchable
history because it proves that the Evolver can use prior wrong edits and
outcomes to change both its cause attribution and selected component. The next
search target is cross-sample reliability: prefer an executable
competing-definition probe that materializes alternative mappings, runs
discriminating fixtures, and binds the selected definition to submitted code,
rather than adding more skill prose. When a small panel appears to gain a
binary solve, run a focused repeat before incumbent promotion. Keep T19 as the
protection task. Full evidence and exact run identities are in the
[public-probe expansion report](reports/2026-08-13-quantcodeeval-public-probe-expansion.md).

**Measured later on 2026-08-13:** the next autonomous round crossed the
prompt-only boundary. Using the same candidate's contradictory T12 outcomes as
history, the Evolver selected and implemented an executable public-behavior
audit in `tools/public_behavior_probe.py` plus its tool description. It read
the exact rejected candidate source on the following retry, ran a final tools
component smoke, passed independent admission, and the new runner was observed
executing inside the official worker against the generated strategy and public
data. This establishes a working cumulative full-harness mutation mechanism;
it does not establish a benchmark benefit.

The focused candidate panel was negative: T12 passed `9/16` (Type-A `4/8`,
Type-B `5/8`) versus the diagnostic parent's `12/16`, while T19 remained
`18/18`. The official vector stayed `0,1` on the local T12/T19 panel, so the
candidate is rejected and the experiment does not expand to T01/T18. Candidate
cost was 65 requests, 2,833,409 tokens, and `$0.0733250952`; the completed r3d
activation cost 26 requests, 1,448,502 tokens, and `$0.0291706968`.

Three observed controller failures were fixed without broadening defensive
infrastructure: terminal reserve now recognizes QuantCodeEval decisions;
final-smoke rejections can enter searchable history; and component-test records
belong to an attempt/history entry rather than globally to candidate code.
R3d's completed activation was recovered after its post-run history append
failed, using its already-persisted ACT, candidate, proxy audit, admission, and
final component smoke; it was not model-resampled and was explicitly marked as
recovered. The next search should not add more parameter prose or promote this
audit. Prefer an externally materialized public-definition fixture or
candidate finalization/state component that binds the selected definition to
submitted code. Start with T12 and protect T19; expand only if a focused gain
survives an immediate repeat. Full evidence is in the
[public-probe expansion report](reports/2026-08-13-quantcodeeval-public-probe-expansion.md).

Interpret these next directions carefully. The terminal-reserve repair is a
controller compatibility fix, not a Worker improvement: r3b already contained
a real ACT and executable tool, but the terminal middleware did not recognize
the QuantCodeEval `quant_property_v2` decision schema and incorrectly kept
requesting ABSTAIN. The fix allowed the completed decision to terminate
normally; it did not produce a benchmark gain.

Direction A, an independently materialized public-definition fixture, is the
stronger current hypothesis. The Evolver partly identified its premise—that a
worker-authored contract can validate its own wrong interpretation—but the
external fixture itself is an investigator-proposed extension and has not yet
been autonomously discovered or validated. Direction B, retaining a selected
definition and passing component state through later edits and final assembly,
is an unverified investigator hypothesis. No current trace proves that a
correct intermediate T12 implementation was later overwritten, so do not call
B an Evolver finding or an observed root cause.

For the next experiment, first give the Evolver the full accumulated
answer-free history and open harness mutation surface without prescribing A or
B. If autonomous search stalls, present A and B as competing hypotheses while
allowing another mechanism or ABSTAIN; label that run hypothesis-seeded. An
investigator-authored A implementation is a later localization control that
tests mechanism viability separately from autonomous discovery. Use T12 first,
protect T19, immediately repeat any apparent T12 solve, and expand only after a
repeatable gain. Search length is determined by information, success,
abstention, and budget rather than a fixed five rounds.

**Superseding implementation decision later on 2026-08-13:** before the next
paid autonomous search, enhance the Evolver's diagnosis with the locally tested
two-axis quant/finance failure map. The first axis locates the earliest
breakdown among public-source retrieval, requirement comprehension,
specification preservation, implementation realization, and execution/
completion. The second axis identifies interface delivery, data/universe
preprocessing, temporal causality, formula/parameterization, signal direction,
portfolio accounting, runtime/completion, isolated task-specific, or unknown
semantics. A legal ACT must cite observed symptoms, distinguish an adjacent
semantic class, explain the selected class, and name the concrete component
state to change. The map and component routing remain advisory; the Evolver may
reject A and B, propose another mechanism, or ABSTAIN.

This refines rather than erases the earlier five-class PGBS history. Direction
A is a possible mechanism for comprehension or implementation failures where
an independent public expectation can distinguish definitions. Direction B is
specific to specification preservation and requires evidence that a correct
requirement or intermediate implementation was later lost; it is not justified
by final failure alone. The third open family is a failure-specialized
component chosen by the Evolver for a recurring finance state or operation.
Implementation and local tests are recorded in the
[quant/finance failure-map decision](decisions/2026-08-13-quant-finance-failure-map-middleware.md).
No paid model call or candidate benchmark run has yet used this middleware.

**Superseding flexibility and experience decision later on 2026-08-13:** keep
the failure map, but use it as optional domain vocabulary rather than a
mandatory two-axis form. The Evolver may add free-form finance/data/execution
tags or propose a better class. A legal ACT still needs competing mechanisms,
inspected evidence, a falsifiable prediction, explicit component roles, and a
coherent edit; it no longer needs to populate every fixed taxonomy field.

The exact mutation archive remains the source of truth. Each later evidence
bundle now adds an experience catalog, current branch ancestry, and a compact
relevant set with result-validated lessons and suggested branch operations
(`CONTINUE`, `REUSE`, `REVERT`, `FUSE`, or `NEW_PROBE`). Worker evidence also
retains a longer answer-free runtime timeline with event role, tool success or
error, duration, exit-code counts, truncation, and consecutive-error structure,
while excluding messages, commands, tool output, and evaluator details. This is
derived both for ordinary H0/comparison evidence and when completed candidate
panels are imported into later search history; importing reuses their persisted
attempt files and does not rerun the Worker. This is
locally smoke-tested retrieval/plumbing, not a measured reward improvement; no
paid model or benchmark run was launched. See the
[runtime-experience retrieval decision](decisions/2026-08-13-quantcodeeval-runtime-experience-retrieval.md).
The live activation entry point now supports an explicit task panel. The next
mechanism search must use T12 as its target and T19 as its protection task;
historical T01/T18 outcomes may remain in archived experience but must not be
presented as current optimization targets.

**Measured first focused use later on 2026-08-13:** the T12-target/T19-protect
activation ended in a calibrated ABSTAIN, with no candidate mutation and no
new Worker evaluation. The Evolver read four prior scored mechanisms and their
exact history, but judged them tied against run-to-run T12 variation. It used
23 successful model requests, about 1.25 million tokens, and `$0.0294`.

This run exposed a narrower evidence problem. Raw Worker traces already record
definition retrieval, data inspection, candidate writes, local checks,
public-probe failures, revisions, and later probe success, but the next-round
projection retained only generic role and tool-status order. The projection
therefore now keeps coarse action/stage labels, revision counts, and probe
outcome order while still omitting message, command, output, source, and
verifier content. Treat this as a locally tested evidence repair. It has not
yet produced an ACT, candidate score, or reward improvement; replay the prior
T12 traces and rerun the focused autonomous activation before considering an
investigator-seeded mechanism.

**Measured continuation later on 2026-08-13:** a second focused activation
received the new action/stage history and also ended in calibrated ABSTAIN. It
correctly observed that all prior T12 branches eventually passed the existing
free-form public probe while official completion ranged from 8/16 to 16/16.
Across both autonomous activations, 45 requests and 2,909,824 tokens cost
`$0.0756148848`; neither run mutated a candidate or launched a Worker panel.

An explicitly investigator-seeded localization control then tested a
declarative quant-invariant tool. The first version independently computed the
operation declared by the Worker, but allowed public “average return” language
to be paired with an additive sum; that real T12 canary scored 8/16. One
observed-failure repair bound public quantity vocabulary to arithmetic mean,
geometric cumulative return, or explicitly additive sum. With that repaired
component, two independent T12 Workers both scored 16/16 and the T19
protection Worker scored 18/18. Those four Worker runs used 92 requests,
2,192,638 tokens, and `$0.0791807128`. The complete continuation total was 137
requests, 5,102,462 tokens, and `$0.1547955976`; all resources were cleaned.

Treat this as a positive mechanism-localization result, not autonomous harness
evolution or a benchmark gain. The key causal lesson is that independently
computing a Worker-selected operation is still self-confirming when the Worker
also chooses the interpretation. Binding the public term to the executable
operation removed the observed T12 average-versus-sum drift in two samples.
Before expanding tasks, append the negative and positive Worker attempts to
searchable experience and test whether the Evolver can autonomously `REUSE` or
refine the component for another target. See the
[runtime invariant localization report](reports/2026-08-13-quant-runtime-invariant-localization.md).

**Component-stability representation implemented later on 2026-08-13:** the
first non-paid step toward scalable component search is now a lightweight
component-hypothesis ledger. It is deliberately separate from candidate-file
history: a hypothesis records a claimed capability composition and its expected
Worker effect, while trials record availability, selection, actual activation,
target, independent repeat, protection, transfer, and ablation roles. The
current T12/T19 canary is represented without overstating attribution: the
independent invariant alone is unsupported at 8/16; the invariant plus public-
quantity semantic binding is repeated on T12 and protected on T19; semantic
binding has no standalone trial; transfer and component necessity remain
untested. The existing evidence builder can optionally expose an answer-free
summary of this ledger to the Evolver, but default search behavior is unchanged.
No model call, Worker run, or official evaluation was launched for this step.

Use this representation to make stability sequential rather than a one-run
claim. A first target success is provisional, an independent repeat can make it
replicated, and protection can make it protected; conflicting repeat or
protection evidence remains mixed. For a successful composition, prefer a small
ablation and then transfer rather than enumerating all component subsets. Full
bidirectional discovery is a future fallback for capability gaps not covered by
retrieved components, not the default path for every task.

**Autonomous retrieval and first transfer result later on 2026-08-13:** the
Evolver was given the answer-free stability ledger plus a read-only measured
source for the semantic-bound invariant. It independently chose `COMPOSE`,
cited the ledger and source files, and reproduced the exact multi-component
harness (`tools`, tool description, agent config, and system-prompt routing).
Its executable tool smoke passed. The activation used 29 model requests,
1,410,616 tokens, and $0.0282095352; it did not run a candidate benchmark.
Because the resulting harness matched the already measured T12/T19 candidate,
the existing T12 repeat and T19 protection results were reused rather than
resampled.

The same candidate was then evaluated once on T01 as the first transfer probe.
The Worker repeatedly invoked the structured invariant and passed both its
declarative checks and a public-behavior probe, but official T01 stayed at the
parent's 2/17 properties and reward 0. The run used 28 requests, 662,108 tokens,
and $0.0234224144. This is an activated-but-nontransferring component result,
not an activation failure. The composition is therefore mixed across domains;
the next autonomous search should prefer routing or a T01-specific refinement,
while retaining the T12/T19 positive evidence. All new run artifacts were
stored below `/data/qea-julius-storage/runs`; no benchmark-wide claim is made.

**T01 routing and Worker-artifact follow-up later on 2026-08-13:** after the
failed transfer was imported as exact scored history, the next Evolver round
correctly refused to reuse the T12 component globally. It returned calibrated
`ABSTAIN`: four public T01 mechanisms remained observationally confounded by
the available family counts and coarse runtime facts. That round used 15
requests, 766,572 tokens, and $0.0298032616. No candidate was produced or
evaluated.

The history channel was then extended to retain the scored Worker's final
`strategy.py` as answer-free runtime experience. It does not retain checker,
gold, property IDs, or raw reasoning. A preflight verified that the T01 history
entry exposed the 12,181-character failed implementation. A final Evolver
round read that implementation and compared it with the public instruction and
paper. It again returned calibrated `ABSTAIN`, using 24 requests, 1,647,094
tokens, and $0.0470061368. Its analysis eliminated a coarse “component was not
used” explanation, but did not identify one public-evidence-supported harness
change. Its suggestion that an exact reference convention may differ from the
public contract is unverified and must not be reported as a benchmark defect.

The measured conclusion is narrower: runtime experience retrieval can produce
an autonomous multi-component `COMPOSE`; failed transfer evidence changes the
next action away from blind reuse; and final Worker artifacts improve failure
localization but were still insufficient to support a T01 ACT. Stop further
T01 guessing at this point. The next informative experiment should either add
a public, independently discriminating probe for one of the remaining T01
mechanisms or move the same retrieval/routing protocol to a different public
task where component-task fit is identifiable. All sandboxes were cleaned up.

**T18 runtime-artifact component search on 2026-08-14:** the evidence surface
now accepts an explicitly named, scored H0 Worker `strategy.py` as read-only
runtime experience. This is a small bridge for first-round tasks whose failed
Worker output predates evolved-candidate history; it is labeled as runtime
experience and never as a reference answer. The local and deployed focused
test suites each passed 53 tests before the run.

On a T18 target plus T19 protection evidence panel, the Evolver read the T18 H0
implementation and autonomously chose `ACT`. It refined the existing
`quant-contract-arbitration` skill plus `systemprompt.md` to force explicit
minimum-history flip-index selection, an exactly-N synthetic fixture, and
temporal-anchor checking. The change added 28 lines across two files, passed
skill-load smoke and full-harness admission, and did not blindly reuse the T12
component. Activation used 28 model requests, 1,454,428 tokens, and
$0.0403022424.

The fresh T18 Worker then loaded the skill, executed an exactly-120 fixture,
stated the 120th observation as the first classified row, and changed its final
implementation accordingly. Despite this real activation, official T18 stayed
exactly at Type A 2/4 plus Type B 14/14, or 16/18 and reward 0. The Worker run
used 21 requests, 641,753 tokens, and $0.0253538264. Because the target did not
improve, no repeat and no T19 protection resample were run. Total incremental
cost was 49 requests, 2,096,181 tokens, and $0.0656560688; all containers were
cleaned and all data was stored below `/data/qea-julius-storage`.

Interpret this as a successful autonomous discovery-and-activation canary but a
negative benchmark-benefit result. The run rules out the warmup-fencepost
intervention as a sufficient explanation for the two remaining Type A failures.
The component ledger therefore records `warmup_boundary_arbitration` as
Evolver-discovered, fully activated, and unsupported. The next round may refine
toward the still-unresolved percentile-method or early-NaN mechanisms using
this failed intervention as experience; it must not repeat the same boundary
edit, and calibrated `ABSTAIN` remains acceptable. Detailed evidence is in
`docs/reports/2026-08-14-quantcodeeval-t18-runtime-component-search.md`.

**T18 history-guided refinement later on 2026-08-14:** the next Evolver round
imported the prior activation and scored candidate as searchable experience,
including its decision, exact diff, component tests, answer-free tied outcome,
and final Worker artifact. The updated ledger identified
`warmup_boundary_arbitration` as fully activated but unsupported. The Evolver
read and cited that history, used the unchanged Type A 2/4 plus Type B 14/14 to
eliminate the warmup flip index, and also eliminated the already conforming
weight-cap formula.

It retained percentile/quintile boundary semantics and early-observation NaN
policy as plausible competitors, but found that the authorized public
instruction and paper did not uniquely select strict versus inclusive/rank
thresholds or sample-versus-population first-month behavior. Because the two
failing Type A property definitions were not exposed, it returned calibrated
`ABSTAIN`, produced no candidate, and triggered no T18 or T19 benchmark run.
This is measured evidence that the Evolver can use its own failed component
intervention to avoid repetition and preserve uncertainty; it is not a score
gain. The activation used 24 completed requests, 1,807,639 tokens, and
$0.0492410744, with complete top-level proxy accounting and cleaned containers.

An observed bookkeeping defect recorded one request and zero cost inside the
ABSTAIN search-state round even though the finalized proxy audit was correct.
The live controller now reconciles finalized proxy usage into future ABSTAIN
states; focused tests cover the correction. The historical result remains
unchanged and the top-level proxy audit is authoritative. Stop this T18 branch
under the current answer-free evidence rather than guessing another convention.
Detailed evidence is in
`docs/reports/2026-08-14-quantcodeeval-t18-history-refinement-abstain.md`.

**T24 endpoint-consistency search and repeated delivery block later on
2026-08-14:** the next autonomous branch reused the earlier T24 candidate that
had moved the task from Type A 6/7 plus Type B 9/10 to Type A 6/7 plus Type B
10/10 while preserving T16 at 18/18. The Evolver read that scored Worker
artifact, selected a residual temporal-causality mechanism, and extended the
existing static audit with an executable window-endpoint consistency check.
The candidate changed configuration, prompt, tool description, and Python tool;
after four failed tool self-tests it repaired the implementation, passed the
final discriminating self-test, passed graph smoke and admission, and returned
legal `ACT`. This is autonomous component discovery and activation, not a
prompt-only mutation. The activation used 28 completed requests, 2,546,172
tokens, and $0.0623815864; three uncharged provider-429 attempts were retained
as nonaccepted requests.

The benchmark effect was not measured. The first T24 Worker attempt and its
single preregistered replacement both ended with the same model-delivery
failure: the terminal request consumed 32,000 reasoning tokens and returned an
empty assistant message with no tool call, leaving no `strategy.py`. The first
attempt used six requests, 101,455 tokens, and $0.0164936856; the replacement
used seven requests, 162,549 tokens, and $0.0203747656. Neither reached the
verifier, so neither is an official T24 reward-zero result. No third retry,
success repeat, or T16 protection resample was run. Total incremental use was
41 completed requests, 2,810,176 tokens, and $0.0992500376; all containers were
cleaned.

Keep the endpoint component in `pending_evaluation`: these runs neither support
nor refute its benchmark effect. The repeated observed failure does justify a
new autonomous component-search round focused on artifact delivery and
recoverable completion. Give the Evolver both failed attempts and require it to
choose the harness locus and write a local component smoke; do not hand it a
preselected finalizer. Detailed evidence is in
`docs/reports/2026-08-14-quantcodeeval-t24-endpoint-component-delivery-blocked.md`.

**T24 delivery recovery and component interaction later on 2026-08-14:** the
Evolver used the two failed Worker attempts as runtime experience and correctly
selected middleware rather than another prompt-only quant mutation. Its first
implementation used an `after_model` hook and passed a fabricated-input smoke,
but installed-runtime inspection showed the observed empty-response exception
is raised before that hook. No Worker was spent on this unreachable design.

A second autonomous round incorporated that reachability observation, selected
`COMPOSE`, and implemented bounded recovery at `wrap_model_call` while retaining
the endpoint-audit tool. The Evolver omitted a final repeat of the unchanged
tool smoke after composition, so an explicitly labeled investigator supplement
ran the missing tool smoke, real middleware-manager cases, and admission on an
unchanged copy. The resulting T24 Worker then hit the exact 32,000-reasoning-
token empty response twice; the middleware caught both exceptions, the third
call continued, `strategy.py` was delivered, and the official checker ran.
This directly supports the runtime delivery mechanism.

The quant composition did not improve. T24 regressed from the prior candidate's
Type A 6/7 plus Type B 10/10 to Type A 5/7 plus Type B 6/10, or 11/17 overall,
so no T16 protection run was launched. The final artifact repeatedly invokes
an in-place percent-to-decimal conversion as a DataFrame crosses four pipeline
components. That suggests a missing unit-state or transformation-lifecycle
contract, but it is an artifact-based hypothesis rather than a measured cause.
The next round should let the Evolver compare the exact scored artifacts,
preserve delivery recovery, and autonomously choose whether to introduce such a
component. Do not hard-code the repair.

The delivery phase used 142 completed requests, 11,733,043 tokens, and
$0.178233636. All data remains below `/data/qea-julius-storage/runs`, and all
containers were cleaned. A separate observed bookkeeping bug left rejected
`ACT` search rounds with provisional request/cost values; finalized proxy usage
is now reconciled for all terminal decisions. Detailed evidence is in the
[delivery recovery report](reports/2026-08-14-quantcodeeval-delivery-recovery-component-interaction.md).

**Cross-benchmark component-search breadth preflight on 2026-08-15:** the next
method unit remains a component hypothesis, but task navigation is no longer
limited to the T18/T24 QuantCodeEval branches. A thin answer-free experience
adapter now presents public task state, runtime history, Worker artifacts, and
positive or negative component evidence through one task-card interface for
both QuantCodeEval and QFBench. Candidate contracts, Worker execution, and
official verification remain benchmark-specific. Component retrieval is an
advisory public-state match rather than an exhaustive finance failure map;
QuantCodeEval-only components are not routed to QFBench, and no match permits
new synthesis or calibrated abstention.

The real QFBench evidence preflight built four task cards and five component
cards for two targets plus two protections. Separately, public QuantCodeEval
T26/T27 source and runtime support were staged below `/data/qea-julius-storage`
on bc without WRDS. In a network-disabled Python 3.11.15 canary container, the
official golden/checker smoke passed T26 at 17/17 and T27 at 18/18. These are
setup checks, not Worker baselines or harness-benefit measurements; no model
was called and cost was zero.

The proposed paid breadth phase uses T26/T27 with T19 protection and two
QFBench targets (`swap-curve-bootstrap-ois`,
`earnings-surprise-calculator`) with two QFBench protections
(`credit-spread-decomposition`, `historical-var-data-prep`). Start with one
target from each benchmark, stop a branch after abstention or scored
non-improvement, and run one repeat plus one protection only after improvement.
The experiment asks whether runtime history can localize a component on an
unseen task, whether the navigation mechanism transfers across benchmark
contracts, and whether multi-component composition helps without regressing a
known-good protection task. Detailed setup and evidence are in
`docs/reports/2026-08-15-cross-benchmark-breadth-adapter-preflight.md`.

**Cross-benchmark breadth live canary on 2026-08-16:** the common navigation
surface produced calibrated semantic ABSTAINs in matched task-only and
history-enabled QFBench `swap-curve-bootstrap-ois` arms; neither changed the
harness or launched a Worker. The history arm read two retrieved component
cards but correctly refused unsupported reuse. Both old reports recorded a
null decision because the runner ignored an explicit `prediction.json`
ABSTAIN; the runner now recognizes either terminal artifact, while the original
evidence remains unchanged.

QuantCodeEval T26 H0 scored 13/17 (Type A 5/7, Type B 8/10). The history-enabled
Evolver then autonomously synthesized an independent public-clause audit and
revision loop, changed five files across tools, tool description, agent config,
and system prompt, passed smoke/admission, and registered ACT. The first T26
Worker activated the checker three times and improved to 14/17, but the repeat
also activated it and regressed to 12/17. The target benefit is not stable and
binary reward remained zero in both samples.

The T19 protection Worker scored 18/18 versus the earlier shell-only 16/18
sample. However, the T26-specific checker reported two irrelevant failures on
all three T19 audits. This makes the broader contract-read, independent-
validation, revise, and re-audit workflow a stronger transfer hypothesis than
the static checker itself. The result is protected and process-positive but
causally unresolved; next run a workflow-only ablation on two T26 samples plus
one T19 protection before designing a task-conditioned checker or expanding to
more tasks. The seven live runs used 183 completed requests, 8,231,008 tokens,
and $0.2101171912 with zero restarts. All run-scoped monitoring and containers
were cleaned, and evidence was additively mirrored. See
`docs/reports/2026-08-16-cross-benchmark-breadth-live-results.md` and
`results/cross-benchmark-breadth-20260816/RESULT.json`.

**Answer-rich optimization and reusable-component definition accepted on
2026-08-16:** QEA now distinguishes task-specific evidence, task-conditioned
behavior, and task-specific harness patches. A declared optimization task may
show post-run rubric answers, expected-versus-observed behavior, and
counterexamples to the Evolver after a blind Worker attempt. Answers never
enter the Worker. A reusable component may dynamically inspect the current
public task contract and data, but it may not persist an optimization task ID,
expected constant/output, reference implementation, or fixed task-only
assertion. Such an edit is an overfit task patch, not a reusable component.

The macro protocol combines two related-work lessons. From Learning to
Discover at Test Time, retain complete candidate/reward history, explicit
best-state retention, promising-branch reuse, and a matched-budget
task-solution-search control; do not inherit its single-problem no-
generalization claim boundary. From Self-Harness, mine proposer-facing failure
evidence only from held-in tasks, abstract verifier causes into reusable agent
mechanisms, propose minimal edits, and require answer-free regression evidence.
QEA uses stricter naming: any split repeatedly consulted for promotion is
protection/selection data, while sealed held-out tasks never guide search.

T26 is now an answer-rich optimization task, T19 is answer-free
protection/development, and T27 may be a one-shot answer-free transfer canary.
The existing T26 clause-semantic component is reclassified as an unresolved
mixed candidate because it combines a potentially general revision workflow
with T26-specific static assertions. The next experiment reuses the existing
13/17, 14/17, and 12/17 attempts to build an Evolver-only item-level diagnostic
packet, then asks the Evolver to abstract a reusable capability before running
a fresh blind Worker. See
`docs/decisions/2026-08-16-answer-rich-evolver-and-task-conditioned-harness.md`.

**Transfer-first path and closed-benchmark fallback accepted on 2026-08-16:**
the next experiment remains a strict reusable-transfer test, but held-out gain
is not an indefinite prerequisite for useful benchmark optimization. Level A
searches for a shared, task-conditioned component using answer-rich optimization
evidence, a blind Worker, and answer-free protection/transfer. After two
genuinely different, activated component hypotheses show repeated target gains
but consistently null or negative transfer, record reusable transfer as a
negative result for this setup and move to Level B: full-QuantCodeEval adaptive
development with one shared harness. That result is reported as closed-
benchmark or full-corpus optimization, not held-out generalization.

If a shared harness then shows repeated cross-task interference despite routing
or composition attempts, Level C permits separate per-task test-time discovery
lineages. Its final artifact is a task-conditioned portfolio and its claim is
task-solving under test-time compute, not reusable harness evolution. At every
level keep matched-budget seed, best-of-N, and sequential task-solution controls
and report score against requests, verifier calls, cost, and wall time. A
within-benchmark held-out result supports internal task transfer only; it does
not by itself establish universal quant generalization. See
`docs/decisions/2026-08-16-transfer-first-and-closed-benchmark-fallback.md`.

The immediate Level-A design reuses the existing T26 13/17, 14/17, and 12/17
attempts to build an Evolver-only item-level diagnostic packet. One Evolver call
may edit the full harness; a fresh blind T26 Worker is run only after local
admission, followed by a T26 repeat, T19 protection, and matched T27 shell-only
versus candidate transfer only when each preceding gate passes. The full path
is at most six model executions with a proposed $0.25 cap. No paid run has been
launched or authorized by this documentation update. See
`docs/decisions/2026-08-16-t26-answer-rich-evolver-experiment-design.md`.

**Matched failure-family gate added on 2026-08-16:** improvement outside T26
counts as positive component transfer only when the source and destination H0
failures share a mechanism on which the same task-conditioned component can
act. Match on semantic primitive or state, pipeline phase, and observable;
benchmark membership, finance topic, Type A/Type B, or the generic A10 label is
not sufficient. T26's observed H0 failures cover training/CV temporal scope,
HJ-objective semantics, and end-to-end reconciliation. T19's observed H0
failures cover volatility-normalization semantics and end-to-end
reconciliation, so it matches only a broader formula/scale reconciliation
component, not an HJ-specific repair.

T27 is source-compatible with temporal and end-to-end mechanisms, but it has no
blind Worker H0; the golden 18/18 result is only a setup check. The planned T27
H0 now acts as an eligibility gate. Run the unchanged candidate only if its
observed H0 failure matches the predeclared T26 component mechanism; otherwise
stop and choose another task with a measured matching H0 failure. An unrelated
task may still be protection evidence, but preserving it is not positive
transfer. See
`docs/decisions/2026-08-16-t26-failure-family-transfer-gate.md`.

**T26 answer-rich REFINE canary on 2026-08-17:** the Evolver consumed the three
retained blind T26 attempts and autonomously refined the unstable prompt-led
audit loop into a registered executable quant-contract auditor. The admitted
candidate changed `tools`, `tool_descriptions`, `agent_config`, and
`systemprompt`; it was not a prompt-only mutation. The one valid fresh blind
Worker called the auditor 14 times, revised its artifact repeatedly, and
improved T26 to 16/17: all ten Type-B properties passed, including the predicted
B5/B9 HJ-objective checks, while A10 end-to-end numeric identity remained the
only failure. This is measured component activation and a strong single-sample
property gain, but binary reward remains zero and repeat stability is not yet
measured.

Two replacement Workers were invalid for performance comparison. The first
lost its model stream after ten completed requests and produced no artifact;
the second spent its final 32,000 completion tokens entirely on hidden
reasoning, returned empty content with no tool call, and likewise produced no
artifact. Stop paid redraws after these two route failures. Do not count either
as a component regression, and do not advance to T19/T27 transfer until a valid
T26 repeat confirms the B5/B9 gain. The complete round used 101 completed model
requests, 4,178,080 tokens, and $0.1098010424. See
`docs/reports/2026-08-17-quantcodeeval-answer-rich-refine-canary.md` and
`results/quantcodeeval-answer-rich-refine-20260817/RESULT.json`.

**T26 repeat and Worker-delivery repair later on 2026-08-17:** the same admitted
candidate produced a second valid blind T26 sample without resampling H0 or the
Evolver. Run `qce-t26-answer-rich-candidate-20260817-r4` scored 16/17 again:
Type A was 6/7, Type B was 10/10, B5/B9 both remained PASS, and A10 remained the
only failure. A10's worst relative metric difference improved from about 25.9%
in r2 to 8.65% in r4. The Worker made 38 completed requests, used 1,662,929
tokens, ran for 1,131.21 seconds, invoked the audit component repeatedly, and
made four measured implementation revisions. This supports repeated
property-level benefit and component activation on T26, but official binary
reward remains zero and cross-task transfer is untested.

The coordinator now performs at most one same-evaluation QuantCodeEval Worker
replacement for the two observed model-delivery failures: a lost model stream,
or an empty model response when no `strategy.py` exists. It accepts both the
older and current Proxy audit record shapes. Focused tests passed, and read-only
classification of the retained r1/r3 failure records recognized both. The r4
live run did not trigger replacement, so live replacement success is not
claimed. r4 cost $0.182514808; the complete retained Evolver+r1+r2+r3+r4 lineage
used 139 completed requests, 5,841,009 tokens, and $0.2923158504. See
`docs/reports/2026-08-17-quantcodeeval-answer-rich-repeat-and-delivery-recovery.md`
and `results/quantcodeeval-answer-rich-refine-repeat-20260817/RESULT.json`.

**Mechanism-first binary gate accepted later on 2026-08-17:** do not implement
a progressive asynchronous evaluation scheduler before the current discovery
mechanism reaches an official task-level success. The repeated T26 `16/17`
result remains valid property-mechanism evidence, but the next hard gate is an
Evolver-produced harness that moves a fresh blind optimization Worker from
official reward `0` to `1`. Continue T26 with its retained answer-rich A10
history and full-harness mutation surface. Search length is evidence-driven,
not fixed at five rounds; retain each candidate, result, cost, and failure
lesson. A first `17/17` triggers an independent blind repeat, followed only then
by protection and matched transfer.

The previously discussed L0-L4 progressive evaluation is deferred until task
breadth makes long-tail evaluation a measured bottleneck. At that future scale,
the early L0-L2 cycle may give the Evolver a budgeted action to decide when its
candidate is ready for a benchmark call, which allowed optimization task is
most informative, and whether a repeat is worth the cost. L0 remains local;
the coordinator executes and records allowed L1/L2 requests. This is a proposed
adaptive-evaluation extension, not a tested mechanism or current implementation.

After a binary mechanism success, freeze the method and run a fresh shell-only
H0-to-Evolver-to-candidate lineage. The final primary gate is improvement in
official binary reward on a declared test set whose answers and scores did not
guide candidate selection. If all benchmark tasks instead become answer-rich
adaptive evidence, retain the accepted Level B label: closed-benchmark
optimization, not unseen-test generalization. See
`docs/decisions/2026-08-17-mechanism-first-binary-gate-and-deferred-adaptive-evaluation.md`.

**T26 binary-gate continuation later on 2026-08-17:** the coordinator can now
extend the answer-rich diagnostic across rounds, and the candidate evaluator
can preserve multiple Evolver-selected primary components, reuse their final
component tests, and measure an incremental mutation against its immediate
parent. Focused validation passed locally and on `bc-server`. The T26 packet
contained five retained attempts, while the Worker remained blind to all
answer-rich property details.

One valid replacement Evolver autonomously refined the existing quant-contract
auditor with a second-moment scale-consistency check. The admitted candidate
changed `tools`, `tool_descriptions`, and `systemprompt`, and passed component
smoke and no-model candidate preflight. It has no official performance result:
two fresh blind Workers both reached the provider rate-limit retry deadline
before writing `strategy.py`, so the verifier never ran and neither attempt is
a zero-reward sample. Stop further redraws. This phase used 66 completed
requests, 2,906,594 recorded tokens, and $0.440088144. The binary gate remains
open.

The next mechanism priority is resumable checkpointing at completed model/tool
boundaries. Preserve the candidate workspace and sufficient conversation/tool
state so a provider delivery failure continues the same Evolver or Worker
sample instead of discarding a long trajectory. After a focused continuation
test, evaluate the frozen admitted T26 candidate without rerunning the Evolver.
See
`docs/reports/2026-08-17-quantcodeeval-t26-binary-gate-continuation.md` and
`results/quantcodeeval-t26-binary-gate-20260817/RESULT.json`.

**Provider repair and T26 binary engineering success later on 2026-08-17:**
the route/transport blocker is resolved for the engineering track. The model
remained `deepseek/deepseek-v4-flash-0731`, while the OpenRouter route now
prefers DeepSeek and permits Baseten, GMI Cloud, and DeepInfra fallbacks. A
completed upstream 200 response is no longer discarded merely because the
budget for starting another retry has expired. Across five post-repair real
Evolver/Worker runs, all 251 requests completed with HTTP 200, proxy retry was
zero, and the longest observed request took about 254 seconds. The audit does
not identify which upstream provider served a request, so do not claim that a
specific fallback was exercised. This provider-flexible engineering track must
not be pooled with older fixed-DeepSeek formal comparisons.

The same continuation reached the first official T26 binary success. A
zero-model causal ablation began from the retained 16/17 blind-Worker artifact,
falsified the Evolver's grid-resolution-only hypothesis, and localized A10 to
CV state semantics: a non-contiguous two-fold complement had been converted to
its first/last-month bounding interval, which silently reintroduced the
held-out fold into moment estimation. Using exact selected-month membership,
fold-local regularization scaling, population covariance, and the 50-point log
grid produced 17/17, Type A 7/7, Type B 10/10, and official reward 1. The final
verifier replay made zero model requests. Paid post-route work totaled 251
requests, 13,448,547 tokens, and $0.549950156.

This is a measured binary solution-mechanism result, not yet an autonomous
fresh-lineage harness gain: the successful strategy was produced by trusted
answer-rich causal ablation of an Evolver-assisted artifact. The next gate is
to encode the general estimator-scope rule as a reusable public-semantics
component, obtain 17/17 from a fresh blind Worker, repeat it, and only then run
protection/matched transfer. Detailed evidence is in
`docs/reports/2026-08-17-quantcodeeval-provider-repair-and-t26-binary-improvement.md`
and
`results/quantcodeeval-t26-provider-and-binary-improvement-20260817/RESULT.json`.

**Estimator-semantics and empty-response recovery on 2026-08-18:** an
autonomous estimator-state refinement was admitted but rejected by independent
component contrasts. A generalized repair then produced a fresh blind T26
15/17 result with all ten Type-B properties passing, but reward remained zero.
The next static refinement added first-versus-second-moment and public
training-scope checks. Although its synthetic contrasts passed, its valid blind
artifact scored only 3/17 because a multi-output OLS helper crashed on
incompatible array shapes. Static contrast success is therefore insufficient
evidence of component runtime stability.

Provider diagnosis also supersedes the assumption that ordered fallback alone
resolves empty completions. A real SSE-aware proxy intercepted a reasoning-only
empty response, but the first fallback also returned empty after a long
full-budget attempt. Their combined latency exceeded the downstream timeout,
interrupted audit finalization, and made the emitted result report zero cost.
Live observation before cleanup retained a lower bound of 16 paid responses,
557,902 tokens, and $0.075398272; use that lower bound, not the emitted zero.

The proxy now permits one recovery continuation with low reasoning and an
8,192-token output cap, then returns a prompt infrastructure error if recovery
is also empty. Paid empty responses remain cost records. Local validation
passed 97 related tests with one skip; this final bounded behavior has not yet
been used in a paid Worker. Next compose the static quant-contract auditor with
a small executable runtime probe for public-entrypoint no-crash, shape, and
finiteness. Do not add more static failure classes or start protection/transfer
before a fresh blind 17/17 T26 result repeats. See
`docs/reports/2026-08-18-quantcodeeval-estimator-semantics-and-empty-response-recovery.md`
and
`results/quantcodeeval-estimator-semantics-and-provider-recovery-20260818/RESULT.json`.

## Memory Maintenance Rules

- Update this file when a decision is accepted, superseded, or invalidated.
- Add detailed evidence as a dated report or decision record; keep this file an index and current-state summary.
- Never silently rewrite historical result files. Record an explicit superseding decision instead.
- Record the setup, benchmark version, verifier version, model/provider, and run ID needed to interpret each publishable experiment; do not add new content-hash gates.
- Distinguish `measured`, `source-audited`, `proposed`, and `not yet tested` claims.
# 2026-08-18 AP-1 paired runtime-repair probe

The next QuantCodeEval validation is now implemented as
`quantcodeeval-paired-runtime-repair-probe-v1`.  It gives a parent harness and
an autonomous Evolver candidate the same real failed T26 artifact, public data,
answer-free runtime symptom, and 12-iteration repair budget.  Worker inputs do
not include checker answers; trusted property scoring happens only after each
Worker exits.  The implementation is in `qea/quantcodeeval_repair_probe.py`
and the protocol decision is
`docs/decisions/2026-08-18-autonomous-component-paired-repair-probe.md`.

Measured AP-1 result on bc-server: the common seed was 3/17.  The shell-only
parent repaired it to 12/17 using 11 requests, 202,942 tokens, $0.025572696,
and 262.334 Worker seconds.  The R3 autonomous component candidate repaired it
to 14/17 using 11 requests, 207,523 tokens, $0.040720820, and 481.553 Worker
seconds.  The candidate is therefore `score-helpful` (+2 properties over the
paired parent), but not `efficiency-helpful` and not `binary-helpful`; both
official rewards remain zero.  This is seeded-repair evidence, not a
from-scratch benchmark result.

The artifact diffs show that the parent already fixed the multi-output OLS and
monthly-vs-daily fold-index bugs.  The candidate made broader repairs,
including date parsing, data resolution, and calendar-month fold mapping.
However, the candidate's static auditor still reports false negatives on its
own 14/17 artifact.  Attribute AP-1 to the candidate harness bundle/workflow,
not to proven auditor correctness.  The predeclared promotion rule was met, so
a fresh blind T26 candidate run was launched at
`/data/qea-julius-storage/runs/qce-t26-ap1-candidate-blind-20260818-r1`.
Do not claim binary improvement until that run reaches 17/17 and repeats.

**Fresh binary result later on 2026-08-18:** the promoted R3
Evolver-produced harness candidate completed a fresh Worker run from the public
T26 task at
`/data/qea-julius-storage/runs/qce-t26-ap1-candidate-blind-20260818-r1`.
The official verifier returned 17/17, Type A 7/7, Type B 10/10, and reward 1.
The Worker completed 59 turns, 76 tool calls, and 13 recorded tool errors in
1,766.607 seconds.  Cost reconciliation is complete: 59/59 accepted requests,
3,162,048 input tokens, 122,443 output tokens, 3,284,491 total tokens, and
$0.120627420.  All 59 requests resolved to DeepSeek; configured fallbacks were
not exercised.  The service exited normally and wrote `H0-RESULT.json`.

This closes the immediate fresh-Worker binary gate for this admitted autonomous
component candidate.  It does not yet prove a complete autonomous search loop:
the experimenter designed AP-1 and manually promoted the candidate.  It also
does not establish stability until an independent repeat.  Preserve the result
as a measured fresh candidate-harness success while AP-2M tests autonomous
experiment choice and AP-3 separately tests bootstrap from H0.

## 2026-08-18 AP-2 autonomous runtime-experience search order

AP-1 is a measured component-utility experiment under an experimenter-designed
repair probe; it does not establish complete autonomous exploration.  The next
mechanism experiment is AP-2A, a cold-history autonomous runtime-experience
search.  Human control is limited to the optimize task, evidence cutoff,
resource budget, generic experiment interfaces, and independent final scoring.
The Evolver owns history retrieval, artifact or from-scratch selection, probe
design, component choice, Worker invocation, result interpretation,
retain/refine/compose/rollback decisions, and final candidate submission or
ABSTAIN.

Execute in this order: (1) finish and freeze the already-running fresh T26
confirmation without using it to hand-author the AP-2 prompt; (2) build a
run-based experience index containing historical artifacts, traces, candidate
changes, scores, costs, and prior Evolver decisions; (3) expose generic
`search`, `inspect`, candidate-edit, component-smoke, Worker-experiment,
optimize-evaluation, comparison, submission, and ABSTAIN actions, with no
T26-specific repair template; (4) persist an Evolver-readable experiment
notebook across iterations; (5) verify the plumbing with deterministic fakes,
including a second iteration that can observe and react to the first; (6) run
a no-model preflight; (7) execute one paid AP-2A T26 canary for at most three
Evolver iterations and three bounded Worker experiments; (8) independently
evaluate the submitted candidate with a fresh Worker; (9) repeat from a fresh
Evolver start only after a 17/17 result; and (10) defer runtime-search ablation,
matched transfer, QFBench expansion, and asynchronous scheduling until the
single-task autonomous loop is positive.

AP-2A uses a pre-AP-1 evidence cutoff so the Evolver cannot simply copy the
experimenter's paired-repair instruction.  It may inspect raw optimize
runtime evidence and answer-rich optimize diagnostics, while the Worker remains
answer-blind.  Domain specialization uses an extensible runtime-state record
(`observed_symptom`, `pipeline_stage`, `quant_state_variable`,
`suspected_component`, `competing_explanation`, `confidence`, and
`experiment_needed`) rather than an exhaustive fixed failure enumeration.
The initial engineering budget is one task, concurrency one, at most three
Worker experiments of 8--12 iterations each, a normal-budget final Worker,
and a total paid cap of $0.40.

Interpret results in layers.  A complete legal search-and-update trajectory is
autonomy feasibility; a later decision that explicitly responds to a real
earlier runtime observation is feedback-driven exploration; a repaired failure,
property improvement, or efficiency gain is component utility; and only an
independently scored final candidate is benchmark benefit.  A single AP-2A
success demonstrates one T26 feasibility canary, not stable general autonomous
ability.  The full accepted order and claim boundaries are recorded in
`docs/decisions/2026-08-18-ap2-autonomous-runtime-experience-search.md`.

## 2026-08-18 streamlined AP-2M to AP-3 H0-bootstrap sequence

The accepted speed-first mechanism sequence supersedes the heavier immediate
AP-2A platform build.  AP-2M uses two Evolver decision rounds, one
Evolver-authored Worker probe, and one independent final T26 evaluation.  Round
one selects its own historical experience, candidate components, repair or
from-scratch mode, seed artifact if any, instruction, prediction, and
counter-observation.  The coordinator executes that specification.  Round two
receives the real artifact, trace, score, runtime, and cost, then retains,
refines, rolls back, composes, submits, or ABSTAINS.  The final candidate is
scored independently.  Defer a general experience service, durable notebook
platform, extra probes, ablation, transfer, QFBench breadth, and asynchronous
scheduling.

AP-2M success demonstrates warm-history autonomous experience-guided search;
it is not evidence that the system can bootstrap from H0.  AP-3 is the minimum
separate H0 test.  It starts only from the shell-only H0 harness, the public
T26 task, and evidence generated by one fresh H0 Worker inside the same run.
It excludes historical high-scoring artifacts, R3/AP-1 candidates, handcrafted
repair prompts, known root-cause summaries, and task-specific component
recommendations.  The same two-round mechanism must autonomously diagnose H0,
select and activate a component, design a real experiment, update from its
result, and submit a final candidate or grounded ABSTAIN.  A final score above
the fresh H0 reference is H0-bootstrap mechanism success; 17/17 is binary
success.  One success is a T26 canary, a fresh-start repeat supports initial
stability, and a second different task is required before a broader H0-autonomy
claim.  Full details are in
`docs/decisions/2026-08-18-ap3-h0-autonomous-bootstrap-canary.md`.

## 2026-08-18 seven-day mechanism-validation report structure

The concise synthesis covering 2026-08-11 through 2026-08-18 begins with one
linear progress graph.  The left side shows the actual project sequence from
terminal ACT/ABSTAIN through full-harness mutation, retained runtime history,
cross-benchmark execution, rich-evidence T26 search, and fresh 17/17; the right
side says what mechanism each step validates.  The remaining prose uses
concrete statements about what was run, what the Worker or Evolver actually
did, and what that result does or does not establish.  It avoids repeating an
abstract Mechanism/Question/Signal/Status template for every node.  Minor
infrastructure outcomes remain attached only where they change a mechanism
conclusion.

The report's headline boundary is that a R3 Evolver-produced candidate harness
has one fresh T26 17/17 Worker result, while complete autonomous experiment
choice and H0 bootstrap remain unmeasured.  The next plan is therefore written
separately from the historical route: implement and run AP-2M first, using two
Evolver decisions and one self-authored Worker probe; if that loop is
feedback-driven, reuse it for AP-3 starting only from shell-only H0 and one
run-local H0 Worker.  Repeat and cross-task/QFBench breadth follow only after a
positive AP-3 result; the asynchronous cost-aware scheduler remains deferred.
The synthesis is in
`docs/reports/2026-08-18-qea-seven-day-mechanism-validation-route-report.md`.

## 2026-08-18 future self-evolve scenario and evidence split

The training-like optimization view is a future, more open-ended self-evolve
scenario; it is not the current AP-2M/AP-3 evolution protocol. In that future
scenario, the Evolver receives a resource budget and generic experiment
interfaces, then autonomously chooses when to call Workers, which candidate or
component to test, whether to branch or revise, and when to submit an incumbent.
Candidate versions record material harness changes, while multiple Worker calls
may be experiment events attached to one version.

The expected benefit is more efficient and flexible search: the Evolver need
not run every candidate on every task, can test component reachability before
broad evaluation, and can accumulate positive, negative, and contradictory
runtime experience for long-horizon retrieval. The main problems are adaptive
overfitting to repeatedly observed optimize tasks, lucky-sample selection,
unclear stopping and final-candidate rules, and biased or unwieldy history.

Any task whose result changes search or candidate selection is `optimize` or
development evidence rather than out-of-sample evidence. A `sealed_final`
surface is run only after the incumbent is frozen and never returns to the
Evolver or retrieval index. RAG can reduce context and navigation cost, but it
does not remove adaptive selection overfitting.

AP-2M remains only the bounded prerequisite canary: two Evolver decisions and
one self-selected Worker experiment. AP-3 tests that bounded mechanism from H0.
Variable Worker calls, candidate branching, long-horizon RAG, autonomous
submission, and multi-task scheduling remain later extensions. Full rationale:
`docs/decisions/2026-08-18-candidate-version-optimization-and-evidence-split.md`.

## 2026-08-19 ICLR 2027 research and writing direction

For the ICLR 2027 submission sprint, defer the open-ended scenario in which the
Evolver autonomously schedules Worker calls, branches experiments, and decides
when to stop. Restore the fixed outer evolution loop as the submission-critical
method: the coordinator runs a declared task panel, collects trajectories,
gives accumulated evidence to the Evolver, evaluates one proposed harness
candidate under a fixed protocol, and accepts or rolls it back. The earlier
self-evolve records remain valid future directions, not the immediate paper
scope.

Name the task-solving agent the **Quant Research Worker Agent**, shortened to
**Worker**. Treat a Worker Agent version as a frozen base model instantiated
under one versioned harness. The high-level research object is the effective
capability of this Agent system: unlike quantitative-agent methods that
primarily evolve factors, strategies, models, or generated programs while
holding the agent scaffold fixed, QEA evolves the prompt, tools, memory,
middleware, validation, routing, and workflow that shape future quantitative
research behavior. State explicitly that this is harness-space adaptation, not
base-model weight training.

Use **Quant Research Trajectory** for one observable Worker execution of a
**Quant Research Task**; do not equate the task with its trajectory. The
Evolver converts accumulated trajectories into an open **Quant Research State**
covering relevant data, time, quantity, estimator, portfolio/execution, and
artifact states, then maps the diagnosed mismatch to a missing capability and
target harness component. Attribute the harness-evolution concept to AHE and
the evaluated-attempt discovery intuition to TTT-Discover. The intended
distinction is agent-capability evolution for quantitative research rather than
another alpha-, factor-, or strategy-evolution method.

The working paper title is **Evolving Quantitative Research Agents through
Harness Adaptation**. The writing outline centers on idea construction,
terminology, conceptual formulation, related-work positioning, method
narrative, and claim boundaries. It deliberately leaves the main experiment
matrix for a separate decision. Full outline:
`docs/decisions/2026-08-19-iclr-quant-research-agent-evolution-writing-direction.md`.

## 2026-08-19 adversarial novelty and verification revision

The same-day Quant Research Agent story remains useful motivation but is not a
sufficient novelty claim. AHE already evolves the full harness from layered
trajectories, records predicted fixes and regressions, verifies them against
task-level deltas, rolls back edits, ablates components, and evaluates frozen
transfer. AQuA already recursively updates quantitative research state to
improve later factors and model configurations. Do not distinguish QEA through
renaming, a finance failure taxonomy, or the inaccurate claim that AHE observes
only a scalar score.

The provisional method contribution is instead a quant research-state
intervention loop. The Evolver must connect competing explanations of a Worker
trajectory to a predicted capability deficit, a reachable harness component,
and a predicted research-state transition. Candidate evidence then separates
component reach and activation, behavioral state correction, fixed official
artifact outcome, and repeat or matched-mechanism scope. These intervention
verdicts feed later evolution; official verifier outcomes alone support
benchmark-performance claims.

The final study should include a faithful AHE-on-quant reproduction with the
same seed, editable surface, model routes, optimize split, official verifier,
answer policy, and model-token or verifier-call budget. The primary method
comparison is generic AHE trajectory summaries plus task-delta attribution
versus QEA's competing quant-state hypotheses plus component-mediated
intervention verification. H0, prompt-only, no-quant-state, and task-score-only
promotion are supporting ablations. This is a proposed method and experiment
boundary, not a measured result. Full record:
`docs/decisions/2026-08-19-adversarial-novelty-and-verification-positioning.md`.

## 2026-08-19 post-AP-2M Quant Research Reviewer path

The next research-state identification mechanism is now placed after AP-2M and
before AP-3. The discussion used `MP-2`; the repository has no such prior name,
so this record interprets it as the existing AP-2M warm-history autonomy
canary. AP-2M keeps its original contract and is not modified to include the
Reviewer.

QR-1 first tests whether a Quant Research Reviewer can reconstruct a task-
conditioned expected research process, align it with the Worker artifact and
trajectory, maintain competing causes, and choose an executable audit that
changes the diagnosis. Its small controlled panel includes temporal or fit-
scope leakage, quantity or estimator semantics, portfolio timing or accounting,
artifact or workflow state, and an ambiguous abstention case. The old failure
map is a comparison and retrieval prior, not the answer.

Only after that identification gate passes, run one matched live intervention
canary comparing generic evidence with Reviewer evidence under the same
harness, models, budget, and official verifier. Keep component activation,
predicted research-state correction, official outcome, repeat or protection,
and cost separate. The Evolver still chooses and implements the component. If
the Reviewer adds no discrimination or does not influence an activated
intervention, preserve the negative and run AP-3 through its previous generic
evidence path. Full decision:
`docs/decisions/2026-08-19-post-ap2m-quant-research-reviewer-canary.md`.

## 2026-08-19 invariant-guided quant harness evolution route

The research route has rolled back from making broad Research State
identification, causal mediation, and a large Reviewer benchmark immediate
requirements. AHE and Meta-Harness already establish closely related outer
harness-evolution loops. The immediate relative novelty hypothesis is instead
whether public, executable quantitative-research invariants can provide a
domain-specific feedback, component-search, routing, and cumulative-experience
signal beyond generic trajectories and sparse official task outcomes.

This continues rather than replaces earlier public-definition and quant-
invariant work. Prior probes already exercised quantity semantics, temporal
windows, sign, portfolio relations, and artifact behavior; the T12 continuation
showed that a free-form green probe could be self-confirming, while binding the
public quantity definition produced the intended property behavior in repeated
Workers. The next method should synthesize task-applicable invariants and record
an executable `PASS`/`FAIL`/`N-A`/`UNKNOWN` signature, rather than equate a broad
failure label with a cause.

Keep improvement levels separate. A predicted invariant transition in a fresh
Worker with real component activation is `mechanism_helpful`; an official
property or reward gain is `benchmark_helpful`; repeat, protection, or matched-
mechanism transfer supports `stable_or_reusable`. The first is meaningful
harness evidence even when the complete answer remains wrong, but it must not
be reported as an official benchmark gain. An unexplained official gain remains
performance evidence with unresolved attribution.

The revised path keeps AP-2M unchanged, then runs QI-1 task-conditioned
invariant synthesis and QI-2 invariant-guided component search before AP-3. A
Quant Research Reviewer may synthesize invariants and select audits, but it is
supporting machinery rather than the immediate novelty claim. AP-3 adopts the
invariant feedback only if the bounded canaries add grounded search value;
otherwise it retains the generic evidence path. Full decision:
`docs/decisions/2026-08-19-invariant-guided-quant-harness-evolution-route.md`.

## 2026-08-19 AP-2M first live attempt

The first paid AP-2M run is retained at
`results/bc-mirror/qce-t26-ap2m-20260819-r3/`. It completed 35 Evolver model
requests at a provider cost of `$0.1652724772`; all requests completed, no rate
limit occurred, and all managed containers were cleaned. An initial no-cost
launch exposed that the previous proxy image did not understand provider
fallback configuration. A lightweight proxy refresh fixed that observed setup
failure before the measured run.

Round one produced a legal `ACT` and a non-prompt-only candidate. The Evolver
diagnosed a `formula_parameterization` / executed-semantics gap, created an
executable `check_strategy_contract` tool, modified its registration and
activation prompt, exercised paired positive and negative fixtures, selected
`candidate12_t26` for an eight-iteration repair experiment, and recorded both a
prediction and a decision-changing counter-observation. This is measured
autonomous component construction and experiment design.

The candidate was rejected before any Worker probe. The final candidate state
lacked a passed smoke for the primary `tools` component because the Evolver's
tool smokes occurred before it deleted temporary fixture files; the admission
rule treated that cleanup as making the earlier whole-candidate-bound smoke
stale. AP-2M therefore ended at `round_one_terminal`: no Worker probe, second
Evolver decision, fresh Worker, or official candidate evaluation occurred.
Classify this as an informative negative AP-2M result and an observed
completion-orchestration gap, not autonomy success or benchmark improvement.
The next bounded repair should let the Evolver perform final primary-component
smokes during completion, then rerun AP-2M under a fresh budget.

## 2026-08-19 AP-2M feedback-driven r4 result

The AP-2M r4 rerun is retained at
`results/bc-mirror/qce-t26-ap2m-20260819-r4/`. It completed normally with no
rate-limit event. The two Evolver rounds cost `$0.3293828616`; the intervening
Worker probe cost `$0.0060602752`, for `$0.3354431368` end to end. All managed
containers were cleaned.

The r3 completion repair worked in the live protocol. Round one autonomously
selected an executable semantic-invariant checker, implemented it as a real
tool plus registration and prompt changes, ran positive and negative fixture
checks, passed final component and full-harness admission, and launched the
selected Worker repair probe. The probe nevertheless produced no artifact:
within its eight-iteration budget the Worker inspected the public data, paper,
and seed, copied the seed only to a temporary path, never wrote
`/app/output/strategy.py`, and never invoked the checker. This is not component
activation, official evaluation, or benchmark improvement.

Round two read the retained `missing_artifact` observation before deciding. It
submitted a distinct `ACT/REFINE`, preserved the unobservability of the direct
delivery cause from the exposed summary, and independently found that the
round-one audit fixed gamma and used synthetic windows inconsistent with the
public CV and sample-window clauses. This is measured warm-history,
feedback-driven autonomy feasibility: a component was built, a Worker probe
was scheduled, its negative outcome entered the next decision, and the second
candidate contained new quant-specific information. It is not evidence that
the component helped the Worker or benchmark.

The second candidate passed ordinary full-harness admission but was rejected
because its final `tools` version lacked a passed final-version component
smoke. The model ended voluntarily before the token-triggered terminal reserve,
so the r3 repair did not cover this adjacent early-final branch. The observed
branch is now repaired: a valid early-final `ACT` with a changed candidate and
missing primary smoke is forced into one bounded component-smoke continuation.
The middleware-manager propagation and focused suites pass 83 tests. This
post-run repair has not yet been verified by another paid live AP-2M run.

The Worker probe also exposed a direct setup mismatch. Its Evolver-authored
instruction said that an existing strategy was already at the designated
output path, but the coordinator supplied the seed only as
`/app/data/probe_seed_strategy.py` and left `/app/output` empty. The probe
runtime now pre-stages that optional repair seed as `/app/output/strategy.py`
while retaining the data copy as a public backup. This makes a no-op or early
stop preserve the starting artifact and lets the limited Worker budget focus
on repair. The combined focused suite now passes 102 tests; no paid live rerun
has yet exercised both post-r4 repairs.

## 2026-08-19 Quant-H0 and Research-State-guided search revision

The historical shell-only H0 remains unchanged. A separate
`qea/worker_quant_h0` now defines the future common seed with only the Quant
Research Worker Agent identity, six short Research State descriptions, one
shell tool, and basic input/code/deliverable behavior. It omits additional
finance-discipline hints, prior history, diagnosis, component selection, and
task-specific content. Historical H0 results retain their old identity; future
matched AHE-on-quant and QEA comparisons should start from the same Quant-H0.

The six states are Research Mandate & Contract, Research Evidence & Data,
Quantitative Representation, Research Operation, Evaluation & Reconciliation,
and Research Artifact & Completion. They are general, revisitable research
states rather than QuantCodeEval's fixed strategy stages. QuantCodeEval and
QFBench ground the abstraction through stage-aware integrity, heterogeneous
quant operations, multi-step state construction, financial verification, and
complete artifact contracts, but neither benchmark is claimed to define this
same method.

The existing `quant_property_v2` search contract is now Research-State-guided.
For enabled contracts, an `ACT` records one task-conditioned expected state,
the state observed in the Worker trajectory or artifact, the target state after
intervention, and a concrete transition observable. The former finance failure
map remains optional vocabulary, and the Evolver still selects from the full
harness mutation surface. Task-conditioned invariants are possible executable
observations of a predicted state transition. Component activation, state
correction, official outcome, and repeat/protection/transfer remain separate.

The local focused implementation suite passed 18 tests. This is a mechanism
and story update, not a benchmark result. An AHE-author-style story-only review
found that the proposed real distinction is the independently observed chain
`component activation -> predicted Research State transition -> official
outcome`, not the six labels or outer loop. It also identified the remaining
gap: the implementation now binds transition fields into proposal admission,
but has not yet made the observed transition an independent retain/rollback
signal. Full decision and current story:
`docs/decisions/2026-08-19-quant-h0-and-research-state-search.md` and
`docs/2026-08-19-iclr-quant-research-agent-story-mainline.md`.

## 2026-08-19 outcome-side Research State control and callable Reviewer idea

The reviewer-identified outcome-control gap is now closed at the local
mechanism level. QuantCodeEval v2 candidate evaluation can return a structured
Research State verdict containing `state_id`, component activation, transition
outcome, and the observed runtime evidence. A new
`research_state_promoted` selection advances only the search parent when the
component activated, the predeclared transition is supported, the official
panel was evaluated, and no official incumbent task regressed. Official binary
reward Pareto improvement remains the only route to official-incumbent
promotion. Inactive, unsupported, and unknown transitions are archived as
experience without search-parent promotion. The focused search, loop, and
history suite passed 19 tests; the combined Quant-H0, Evolver contract,
middleware, evidence, component-experience, search, loop, and history suite
plus the live-runner compatibility suite passed 108 tests. No live Worker or
benchmark was run.

A future Evolver-callable Quant Research Reviewer is also recorded. When the
Evolver cannot locate a mismatch from ordinary evidence inspection, it may call
`investigate_research_state` over the already authorized public task, Worker
trajectory, artifact, component-use, candidate-history, and runtime-evidence
surfaces. The Reviewer should return the expected and observed state, exact
evidence locations, competing explanations, and a discriminating observation,
or `insufficient_evidence`. It investigates but does not edit the harness,
select the final component, submit `ACT`, or promote the candidate. Reviewer
calls and outcomes become searchable Evolver experience. This callable is a
proposed next capability, not implemented or measured.

## 2026-08-20 Quant Evidence Certificate canary

The immediate Reviewer mechanism test is now QEC-1, a paired generic-versus-
certificate canary that refines QR-1/QI-1. An optional
`quant_evidence_certificate` attaches to the existing Research State transition
and may express task-conditioned quantitative semantic coordinates, an
economic reconciliation bridge, or a residual-and-sensitivity fingerprint.
It is not a seventh Research State, a closed failure taxonomy, or an official
reward.

Both arms receive the same public contract, runtime evidence, audit choices,
model route, and call budget. The first controlled panel distinguishes a
percentage-scale error from a formula error, a missing transaction-cost term
from a holdings-timing error, and includes one deliberately ambiguous case.
The certificate is useful only if it improves mechanism discrimination or
calibrated insufficiency beyond generic structured diagnosis. A positive
QEC-1 advances to one live QI-2/QR-1B intervention before AP-3; a neutral or
negative result is retained and AP-3 uses the existing generic evidence path.

Prior-art language is also narrowed: RHI already evolves prompt-level harnesses
on a quantitative-finance task family, and AQuA-like systems adapt persistent
quant research state or memory. The candidate contribution is therefore the
identifiable intervention chain, not the first use of harness evolution in
quant. Full decision:
`docs/decisions/2026-08-20-quant-evidence-certificate-canary.md`.

### 2026-08-20 measured QEC-1 and AP-3 r3

QEC-1 r1 completed the planned three-case, two-arm, two-stage Reviewer panel.
Generic and certificate arms both chose 3/3 audits, resolved 2/3 cases, and
calibrated the ambiguous case. There were no improved or regressed paired
cases, so the certificate gate is `not_positive`; QI-2/QR-1B was skipped and
AP-3 used the generic Research-State evidence path. The retained result is
`results/quant-evidence-certificate-qec1-20260820-r1/RESULT.json`.

The retained AP-3 run is
`results/bc-mirror/qce-t26-ap3-20260820-r3/`. Fresh Quant-H0 scored T26 12/17,
reward zero. Round one autonomously created and smoked an artifact-check tool
and selected a from-scratch twelve-iteration probe. The probe used eleven
requests but returned `missing_artifact`. Round two cited that observation,
changed the located mismatch from Evaluation and Reconciliation to Research
Artifact and Completion, and made a calibrated `ABSTAIN`; no final Worker ran.
Thus `bootstrap_loop_feasible` is true, while component activation/help,
official candidate gain, and binary gain are not established.

The run used 48 H0, 22 round-one Evolver, 11 probe Worker, and 18 round-two
Evolver requests. Corrected total provider cost is $0.259885044. The first
result total omitted H0 and probe numeric-string costs; the parser was repaired
without changing the run outcome. Round two also lacked the round-one
prediction record, so it could react to the observation but not explicitly
compare prediction with outcome. Repair that handoff before an AP-3 repeat.

### 2026-08-20 AP-3 run-local activation-probe repair

AP-3 r3's missing artifact is now source-localized more precisely. The candidate
registered and advertised its artifact checker, but the probe overlay replaced
the complete public T26 instruction with the Evolver's short directive. The
twelve-iteration from-scratch Worker consequently spent its eleven requests
reconstructing the task from paper and data, produced no artifact, and never
reached the checker's near-completion activation state.

The superseding `quantcodeeval-ap3-v2` intermediate experiment is a short
run-local activation/repair probe. It preserves the complete official public
instruction, appends the Evolver directive, and pre-stages only the fresh H0
artifact produced inside the same AP-3 run. Round two receives the original H0
artifact, the probe output when delivered, the round-one prediction, and the
actual observation. Historical artifacts and answers remain excluded.

The normal-budget no-seed Worker remains a separate formal final candidate
evaluation after admission and the cost gate. Seeded probe behavior cannot be
reported as a fresh benchmark result. Focused local validation passed 27 tests;
the bounded intermediate probe described below subsequently exercised v2.
Full rationale and claim boundary:
`docs/decisions/2026-08-20-ap3-run-local-activation-probe.md`.

### 2026-08-20 AP-3 v2 intermediate activation r1

The experimenter-arranged, candidate-only T26 probe reused the 12/17 artifact
from AP-3 r3's fresh Quant-H0 Worker and the autonomous round-one candidate. It
did not rerun Quant-H0, the Evolver, or the formal no-seed Worker. The complete
public instruction was preserved, but the live deploy had not received the
already-committed `remote_nexau_worker` seed-prestage helper. The seed was
available only as `/app/data/probe_seed_strategy.py` at the first Worker turn,
despite the experiment directive promising `/app/output/strategy.py`.

The Worker completed seven model requests in 40.996 seconds, delivered
`strategy.py`, and invoked the candidate's `check_strategy_artifact` once. The
component returned `ok=true` with zero errors, seven warnings, and one info.
The Worker first failed to read the promised output, then later copied the data
backup itself. The component invocation occurred on the final model request.
The eight-iteration runtime then terminated before any model turn could
reconcile the findings, edit the artifact, or invoke the component again. The
delivered file was unchanged from the seed and the official result remained
12/17, reward zero. Thus component reach and invocation are measured, while the
complete intended pre-stage intervention, post-audit state transition, seeded
repair, component helpfulness, and benchmark gain are not.

The probe used 113,110 tokens across seven completed requests, cost
$0.015230112, had no rate-limit retry, and left no scoped Docker container or
network. The retained evidence is
`results/bc-mirror/qce-t26-ap3-v2-intermediate-activation-20260820-r1/`, with a
small tracked summary at
`data/quantcodeeval/AP3_V2_INTERMEDIATE_ACTIVATION_RESULT.json`. After the run,
the committed pre-stage runner was synchronized to bc and its staging helper
passed a no-model smoke. The next valid comparison is the same bounded probe
with this exact deploy correction, before changing the search logic or making a
general claim that post-audit turns must be reserved.

### 2026-08-20 AP-3 v2 paired intermediate activation r2

R2 repeated r1 with the same T26 seed, round-one candidate, public instruction,
model route, images, and eight-iteration cap. The only controlled change was
synchronizing the already-committed `remote_nexau_worker` pre-stage helper.
The first Worker turn confirmed that the 531-line seed existed at both
`/app/output/strategy.py` and its data backup, validating the deployment repair.

The Worker invoked `check_strategy_artifact` on model request five of seven.
The component again returned zero errors, seven warnings, and one info. Two
later model requests explicitly reconciled those findings against R12 and
attempted deeper functional checks. Thus pre-stage, component reach,
activation, and post-audit reconciliation are now measured; a forced
post-audit reserve is not justified by this result.

The artifact nevertheless remained identical to the 12/17 seed and the
official result remained 12/17, reward zero. The component warnings concerned
temporary period/join-key patterns, while trusted optimize-only diagnostics
identified failures involving training-cutoff evidence, the identity-L2/HJ
solver form, and an end-to-end numerical mismatch. The diagnostic component
therefore did not surface the distinctions that mattered for the remaining
official failures. The Worker-authored functional probe also stopped on an
incorrect CSV `skiprows` assumption before completing.

R2 used 116,504 tokens across seven requests, cost $0.01515752, had no
rate-limit retry, and left no scoped container or network. Detailed evidence is
at `results/bc-mirror/qce-t26-ap3-v2-intermediate-activation-20260820-r2/` and
the tracked summary is
`data/quantcodeeval/AP3_V2_INTERMEDIATE_ACTIVATION_R2_RESULT.json`. The next
bounded mechanism test should give the Evolver—not the Worker—the permitted
answer-rich optimize mismatch and require it to refine, replace, or abstain on
the component before one further paired probe. It should not add a generic
budget increase or hard-code the five property answers into the Worker.

### 2026-08-20 QDR-1 quant diagnostic refinement

QDR-1 supplied the AP-3 r2 blind trajectory and permitted optimize-only
answer-rich mismatch to the Evolver, while keeping the Worker answer-blind. The
Evolver autonomously separated relation observability, genuine numeric
deviation, and activation/stopping hypotheses. It synthesized a four-surface
candidate centered on a new `check_quant_relations` tool for information-time,
identity-ridge, and metric-weighted-residual relations.

The component's local discrimination gate was positive: a correct synthetic
fixture realized 3/3 relations with zero residuals, while removing only the
training-boundary gate produced two localized errors and a 0.0947 truncation
residual without breaking the other relations. This establishes quant-specific
diagnostic synthesis and local discrimination, not Worker or benchmark benefit.

The six-iteration blind seeded Worker used five requests, never called the new
component, did not change the artifact, and remained T26 12/17, reward zero. A
controlled ten-iteration follow-up held the candidate, seed, task, model,
runtime, and Evolver-authored instruction fixed. It used nine requests but
again made zero component calls, repeatedly inspected the seed and paper, left
the artifact unchanged, and remained 12/17. The 6-versus-10 comparison rejects
a simple small-budget explanation and localizes the next gap to Worker
activation/tool selection before Evaluation and Reconciliation.

The Evolver used 30 requests and cost $0.186782712; the two Worker probes cost
$0.005077364 and $0.013176676. Corrected total cost was $0.205036752. Retain the
candidate and negative trajectories as experience, but do not label the
component Worker-helpful or benchmark-helpful. Full result and boundary:
`docs/decisions/2026-08-20-qdr1-quant-diagnostic-refinement-result.md`.

### 2026-08-20 activation-first route before selective scheduling

The complete progressive/selective multi-task scheduler remains deferred. The
next bounded mechanism changes activation timing and tool selection only. QDR-1
already registered the quant-relations tool and mentioned it in both the Worker
prompt and the Evolver-authored directive, but both framed the first call as a
late "before finalizing" action. The retained six- and ten-iteration Workers
spent their turns on the public contract, paper, and existing artifact and
never reached that checkpoint. Late timing and call complexity are therefore
leading, not yet proven, causes.

For the next candidate, the Evolver must treat activation as part of the same
component intervention. With an existing repair artifact, it should provide an
early task-conditioned trigger after a bounded contract/artifact inventory and
before broad background research, and predict both the first component call
and the Worker's next action. Do not hard-code the T26 tool or relation payload
in the coordinator. If prompt/tool-description routing fails again, test one
generic one-shot middleware or routing reminder before considering automatic
audit execution. Measure registration, actual call, decision-changing output,
artifact change, and official outcome separately. Full rationale and the later
scheduler boundary are in
`docs/decisions/2026-08-20-activation-first-before-selective-scheduler.md`.

### 2026-08-20 QDR-1 directed component-impact follow-up

Two Evolver runs independently selected activation timing after reading the
retained six- and ten-iteration zero-call probes. Both authored a bounded
eight-iteration component-impact experiment. R1 was blocked before the Worker
because candidate admission unnecessarily froze the agent name; R2 passed
admission but the old activation gate rejected a prompt-primary treatment for
lacking a locally executable primary component. These observed blockers were
repaired narrowly. R2's original result remains retained, and its unmodified
decision/candidate was resumed into one separate blind seeded Worker probe.

The resumed Worker called `check_quant_relations` once, changing the prior
zero-call outcome, but only on assistant turn 6 after seven shell calls. The
component returned two blocking errors and one warning. The next turn reread
the relevant function but did not edit or re-audit; the artifact stayed
identical to the seed and official T26 stayed 12/17, reward zero. Thus Evolver
diagnosis and directed activation are measured, while early activation,
decision-changing use, artifact repair, property gain, and binary gain are not.

R1 cost $0.10219428, R2 cost $0.128972568, and the resumed Worker cost
$0.0268286; the 51-request campaign total was $0.257995448 with no rate-limit
retry. The next bounded mechanism should test one generic early Research-State
checkpoint or a simpler component call surface, holding component, seed, and
task fixed. Do not add the deferred multi-task scheduler yet. Full result and
boundary:
`docs/decisions/2026-08-20-qdr1-component-impact-result.md`.

### 2026-08-20 QDR-1 bounded causal probe P-v2

P-v2 restored the probe's original role as a short causal experiment over a
retained artifact, rather than a miniature fresh Worker run. It held the T26
task, retained QDR-1 r2 component harness, blind 12/17 seed, model route, and
official verifier fixed. Generic middleware limited public-contract and
artifact inventory to two assistant turns, required an applicability decision
at the next turn, and preserved at least three post-observation responses. It
did not author relation declarations, run the component automatically, edit
the artifact, or expose checker answers.

The Worker called `check_quant_relations` on assistant turn three. Its first
call returned two errors and four warnings. The Worker then revised the target
function, ran syntax and real-data smokes, and called the component again on
turn six; the second call realized 6/6 relations with zero errors and zero
warnings. The artifact changed and the official T26 score improved from 12/17
to 14/17, with A3 and B3 changing from fail to pass and no observed property
regression. Binary reward remained zero. The 12-request run took 220.235
seconds, cost $0.063367496, had no rate-limit retry, and left no scoped
container or network.

This measures the full seeded causal chain from early activation through
official property gain. It is not a fresh-Worker, repeat, protection, transfer,
sealed-test, binary-gain, or end-to-end-autonomous-search result. Full record:
`docs/decisions/2026-08-20-qdr1-causal-probe-pv2-result.md`.

### 2026-08-20 QDR-1 fresh T26 confirmation

The retained QDR-1 r2 harness was next tested with one answer-blind T26 Worker
starting only from the public task, data, and paper text; no strategy seed was
staged. The Worker wrote a parsable draft on assistant turn ten and called
`check_quant_relations` on turn twelve, before the generic middleware fallback
configured for turn twenty-four. The first audit realized 2/6 declared
relations and returned four errors and four warnings. After revising the
artifact, the Worker re-audited on turn fifteen with 6/6 relations realized,
zero errors or warnings, and zero measured truncation residual.

The fresh artifact scored 15/17 with reward zero versus the retained fresh
Quant-H0 comparison at 12/17. A3, B3, B5, and B9 became passing, while B7
regressed, for a net gain of three properties. This is measured fresh-trajectory
and property-gain evidence, not monotone improvement, a repeat, transfer,
sealed-test result, binary gain, or end-to-end H0 Evolver result.

The run used 40 completed requests, 2,619,722 tokens, 767.525 Worker seconds,
and $0.182935552 with no rate-limit retry. The Worker first declared completion
on turn twenty-seven, but completion middleware continued through turn forty.
Treat that terminal overrun as a measured efficiency defect before multi-task
scaling. Full record:
`docs/decisions/2026-08-20-qdr1-fresh-t26-confirmation-result.md`.

### 2026-08-20 AP-3 r4 setup-invalid H0 rerun

AP-3 r4 generated a new answer-blind Quant-H0 T26 artifact at 13/17, reward
zero, using 27 requests and $0.121280528. Evolver round one then used 20
requests, wrote candidate files, and cost $0.116974576. The coordinator failed
before round-one history/admission completed because the synchronized Linux
deploy contained macOS AppleDouble files such as `._agent.yaml`; history
validation correctly reported the binary sidecar as non-UTF8 source.

Retain r4 as setup-invalid after round-one execution, with total observed cost
$0.238255104. It is not a candidate, feedback-loop, final-Worker, or improvement
result. Remove the sidecars from the remote deploy, disable macOS metadata in
future archive syncs, preflight the Quant-H0 worker tree, and rerun under a new
ID. Full record:
`docs/decisions/2026-08-20-ap3-r4-appledouble-setup-failure.md`.

### 2026-08-20 AP-3 r5 complete Quant-H0 feedback loop

After removing the observed AppleDouble sync pollution, AP-3 r5 ran a
cold-history campaign from a fresh answer-blind Quant-H0 T26 attempt. H0 scored
13/17 with reward zero. Round one autonomously selected a
`quantitative_representation` hypothesis, created and admitted a new
`convention-reconciliation` skill plus system-prompt and agent-graph changes,
and chose a six-iteration repair probe.

The probe Worker loaded the skill on assistant turn one, but completed after
five requests with an unchanged artifact and unchanged 13/17 score. Round two
read the persisted prediction and actual probe observation, reclassified skill
activation as insufficient, retained the beta-frequency, CV-output, and
signature hypotheses as untested, and returned calibrated ABSTAIN. No final
Worker ran because no candidate was submitted.

This measures a complete autonomous bounded feedback loop from H0 through
component activation and runtime-experience-conditioned updating. It does not
measure a helpful candidate, benchmark gain, repeat, transfer, or multi-task
coordination. The campaign used 69 completed requests and $0.228217836 with no
rate-limit retry or coordinator restart. Full record:
`docs/decisions/2026-08-20-ap3-r5-h0-autonomy-result.md`.

### 2026-08-21 MT-1 coordinated local-vol result

The original curve pair was superseded after evaluator repairs and zero-model
replay showed that its low scores were integration artifacts. On the corrected
`dupire-local-vol`/`localvol-barrier` pair, the Evolver autonomously built and
then feedback-refined an executable surface-artifact validator. A normal-budget
fresh target Worker invoked it five times and improved from 67/68, reward 0 to
68/68, reward 1. The unchanged candidate invoked it three times on protection
but regressed from 38/39, reward 0.96 to 36/39, reward 0.92.

This is a measured local activated-component and binary-gain result, not a
promoted pair or stable-transfer result. The short autonomous probes ended
before artifact delivery; the successful confirmation needed 50 turns. Next
work should refine completion/stopping and component scope before broad
scheduling. Full result:
`docs/decisions/2026-08-21-qfbench-coordinated-localvol-result.md`.

### 2026-08-21 quant-state-guided search canary

The operational Quant Research State Card was compared with a strong generic
Evolver under matched Quant-H0, evidence, model, mutation, and evaluation
budgets on holdings and local-vol families. Both quant-state Evolvers issued
admitted ACT decisions and selected different quantitative relations and
component loci. Holdings improved from concurrent H0 48/51 to 50/51 and
repeated at 50/51 against a second H0 sample of 37/51. Its unchanged candidate
kept the matched protection task at 42/42; the component was called but made a
grounded schema-mismatch skip, so this is safe protection rather than relation
transfer. The generic holdings candidate regressed protection to 28/42.

Local-vol first-run results were H0 66/68, generic 68/68, and quant-state
67/68. On repeat, generic fell to 67/68 and quant-state timed out without a
score. Do not dispatch local-vol protection or claim stable binary gain. The
valid campaign used 515 completed requests, 26,669,461 tokens, and
$2.087186840. Retain the redundant State Card access-gate and stale-deployment
attempts as setup-invalid evidence outside these totals.

The measured conclusion is that quant-state guidance changes retrieval,
relation selection, component routing, and intervention prediction and can
produce a repeatable property-level improvement. Main-0 remains no-go until a
binary gain repeats or a second mechanism family yields a repeatable gain, the
same selected relation actually executes on a matched second task, and
long-tail monitoring stops treating active numerical fitting as a stalled
Worker. The next search revision may select one primary relation plus at most
one evidence-supported residual-risk relation; do not turn this into a closed
failure taxonomy. Full record:
`docs/decisions/2026-08-21-quant-state-guided-search-canary-result.md`.

The observed watchdog false alert was repaired narrowly: the no-file-progress
threshold is configurable and defaults to 60 minutes for these component
pilots instead of 20. Worker wall-time remains the execution bound; CPU
activity is not treated as evidence of task benefit.
