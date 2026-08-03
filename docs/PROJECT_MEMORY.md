# QEA Repository Memory

> Canonical research and architecture memory for future contributors and agents.
> Last updated: 2026-07-31. This file records current decisions, not merely historical discussion.

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

No report may describe adapter compatibility, E2B parity, AutoDL performance, or seed-worker QFBench score as measured until the corresponding run artifact exists.

## Memory Maintenance Rules

- Update this file when a decision is accepted, superseded, or invalidated.
- Add detailed evidence as a dated report or decision record; keep this file an index and current-state summary.
- Never silently rewrite historical result files. Record an explicit superseding decision instead.
- Pin commit IDs, dataset hashes, image digests, verifier versions, model/provider identifiers, and run IDs in every publishable experiment.
- Distinguish `measured`, `source-audited`, `proposed`, and `not yet tested` claims.
