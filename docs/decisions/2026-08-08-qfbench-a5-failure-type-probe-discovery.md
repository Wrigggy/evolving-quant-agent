# 2026-08-08 — QFBench A5 Failure-Type and Probe Discovery

Status: **implemented and measured as an engineering canary; no causal or
score-gain claim**.

This decision follows the completed negative A4 behavior canary. It does not
rewrite A1–A4 or treat their candidates as a new ancestry. A4 showed that the
Evolver could inspect broad evidence and produce a falsifiable candidate, but
it mapped an unvalidated broad process story directly to a global prompt. The
intervention activated and increased process cost without changing any of the
five task outcomes. A5 therefore changes the discovery decision, not the worker
model.

## Core mechanism

The Evolver must separate four objects that A4 partly conflated:

1. an observed failure phenotype recurring across multiple distinct tasks;
2. one or more reusable failure types induced from those phenotypes;
3. competing causal hypotheses for a type, with counterevidence;
4. the harness component or components that implement one surviving causal
   intervention.

A low score is not a type. A type is eligible for an ACT decision only when it
contains at least two train failures, cites exact inspected evidence, identifies
excluded failures, and survives a probe that makes different predictions under
at least two causal hypotheses. It is valid to induce several types or no
coherent shared type.

The decision space is `ACT` or `ABSTAIN`; `PROBE` is the evidence-gathering
phase before that terminal decision. ACT requires at least one executed probe
to eliminate a competing hypothesis. ABSTAIN records the type, hypotheses,
probe, uncertainty, and the reason evidence is insufficient while leaving the
candidate unchanged. This is a calibrated result, not an empty candidate or a
failed run.

## Success counterfactual question

It is not assumed that the Evolver can produce a reliable complete explanation
for successful tasks. A5 compares two matched contracts:

- `failure_only`: induce recurring failure types and competing failure
  mechanisms; a success counterfactual is optional.
- `contrastive`: for each mechanism, state only the minimum observable success
  counterfactual that would follow if it were true, or explicitly mark
  `insufficient_contrast`. A matched success should be used to specify what must
  remain unchanged, not to invent a symmetric success story.

Both contracts see the same train-only evidence and use the same constrained
probe interface. The contrastive requirement is retained only if it improves
hypothesis elimination, ACT/ABSTAIN calibration, component localization, or
candidate behavior. More prose, citations, or tokens are not uplift by
themselves.

## Probe policy

The first A5 comparison fixes a deterministic constrained probe. The Evolver
pre-registers a question and different expected observations for at least two
hypotheses, then profiles or compares exact authorized JSON, CSV, trace, or
text evidence. The probe cannot execute arbitrary model-written code, use the
network, inspect evaluator material, or mutate the candidate.

Free AI-authored probes versus constrained probes remain an explicit later
ablation. That comparison will freeze one shared type/hypothesis package first;
otherwise a result cannot distinguish type-induction quality from probe-policy
quality. Free means freedom of method inside an authorized answer-free sandbox,
not broader evidence access or weaker evaluator isolation.

## Expanded train-only panel

The exact panel is frozen in
`data/qfbench/MANIFEST_A5_FAILURE_TYPE_DISCOVERY.json`. It is derived from the
completed five-repeat Flash baseline and the frozen 30-task evolution-train
split.

Six targets had reward 0 in all five repetitions, normal verifier exit in all
five, and non-empty aggregate test counts:

- `swap-curve-bootstrap-ois`
- `earnings-surprise-calculator`
- `corporate-action-adjustment`
- `zero-coupon-bootstrapping`
- `13f-amendment-aware-crowding`
- `localvol-barrier`

Five stable 5/5 successes serve as matched contrasts where possible and broad
regression protections:

- `brinson-sector-attribution`
- `credit-spread-decomposition`
- `bs-greeks-pde`
- `merton-jump-diffusion`
- `momentum-backtest`

`residual-momentum` is excluded because its verifier exited 1 in every
repetition. `yield-curve-bond-immunization`,
`prediction-markets-cross-venue-dislocation`, and
`binance-btc-participation-tca` are excluded because one or more repetitions
lack non-empty valid test counts. Infrastructure or unobservable verifier
failures must not be induced into a worker failure type.

Eleven tasks improve cross-task coverage relative to A4's five, but one fresh
sample per arm does not establish statistical significance. Independent model
repetitions remain necessary for a formal performance claim.

## Frozen model and QFBench setup

The baseline, fresh evidence workers, Evolvers, and candidate workers use one
formal route: `deepseek/deepseek-v4-flash-0731`, provider `deepseek`, with
fallbacks disabled. Each Evolver uses supported `high` reasoning. The debugger,
indexer, probes, admission, and audit are deterministic and make no model call.
Pro is excluded from the A5 conclusion.

The worker is copied from the exact measured five-repeat baseline seed digest
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`:
200k context, `max_iterations=60`, 32k maximum response tokens, temperature
0.2, and one shell tool. Task CPU, memory, agent timeout, verifier timeout,
public inputs, official scoring, and offline verifier identities remain pinned.

QFBench itself defines task resources and evaluates real agents that may read,
write, execute, inspect, and iterate; it does not prescribe one universal
conversation-turn limit across Claude Code, Codex CLI, Gemini CLI, and external
agents. Therefore comparability means preserving the official task/verifier
contract and matching our measured baseline worker setup, not replacing the
60-turn seed with an invented “official” turn count. Primary source:
<https://github.com/QF-Bench/QuantitativeFinance-Bench>.

## Multi-component intervention

ACT may declare and edit up to three component roles when all edits jointly
implement one selected causal mechanism. The guarded write interface rejects
paths outside the declared roles. Admission and the behavioral audit compare
declared roles with the actual diff. Multiple components are not permission to
bundle independent fixes or raise mutation breadth for its own sake.

## Primary measurements

Discovery capability is measured before task reward:

- recurring type count and number of failed tasks typed;
- explicit exclusions and matched-success coverage;
- competing hypotheses, probes executed, and hypotheses eliminated;
- success-counterfactual or `insufficient_contrast` coverage in the contrastive
  arm;
- evidence access and grounded citation;
- ACT/ABSTAIN decision, selected components, and declared/diff alignment.

Worker harness capability is separately compared before and after ACT:

- turns, tool calls, tool errors, error rate, wall time, and artifact count;
- first-turn workspace inventory;
- observable validation behavior;
- observable independent cross-check behavior;
- output/artifact inspection behavior.

Official reward and answer-free aggregate test-pass fraction remain outcome
measures. Target gains, target regressions, and protection regressions are
reported separately. A score improvement cannot rescue an ungrounded discovery
decision, and a process-metric increase is not automatically beneficial unless
it matches the prediction without unacceptable cost or regressions.

## Execution and claim boundary

Run one shared fresh seed-evidence pass over the 11 tasks, one Evolver proposal
per contract, and evaluate only ACT candidates on the same 11 tasks. Do not
begin multi-round evolution from A5 until at least one arm shows a coherent
type, discriminating probe, calibrated decision, declared/diff alignment, and
a plausible predicted harness or task effect.

A5 uses the self-hosted rootless Docker backend and never E2B. It is an
engineering mechanism comparison, not yet a paper-level causal or statistical
claim. The later free-versus-constrained probe ablation and independent model
repetitions remain separate work.

## Measured outcome on 2026-08-08

The shared 11-task seed run, both valid Evolver arms, and the only ACT
candidate evaluation completed on the pinned Flash route. The valid runs used
334 completed provider requests, 12,857,239 tokens, and $0.3953654432. A first
contrastive attempt made zero model requests and failed because concurrent
Evolver processes used the same container name; it is preserved and excluded,
and the arm was rerun sequentially under a fresh run ID.

The failure-only Evolver accessed 41/93 evidence members, generated 17
hypotheses, eliminated 12 with six probes, and chose ACT. It induced a
two-failure deliverable-completeness type and coherently edited two roles:
`systemprompt.md` and the shell tool description. The candidate was admitted,
but its primary prediction was falsified: `zero-coupon-bootstrapping` remained
at 1/6 tests, all six targets remained reward 0, all five protections remained
reward 1, and the 11-task task mean remained 5/11.

The contrastive Evolver accessed 39/93 evidence members, generated six
hypotheses and six minimal success counterfactual records, marked three of the
six `insufficient_contrast`, eliminated three hypotheses with three probes, and
chose ABSTAIN. No candidate write was unlocked. In this one matched sample,
success-side reasoning was feasible but difficult and was useful primarily as
an identifiability/calibration gate, not as a direct solution generator. One
sample per arm cannot attribute the different terminal decisions causally to
the counterfactual contract.

The ACT candidate changed observable worker behavior. Across ten tasks with
traces on both sides, first-turn inventory increased by 0.30, validation by
0.30, and independent cross-checking by 0.10. It also added a mean 1.7 turns,
2.6 tool calls, 40.3622 seconds, and 0.038836 tool-error rate. The eleventh task,
`localvol-barrier`, changed from seed timeout/no trace to normal completion at
0/7. This is a mixed harness-capability change, not an outcome gain.

Do not begin multi-round evolution from the ACT candidate. The next discovery
step should expose the exact public task contract as an indexed answer-free
object and require ACT claims to connect a cited public contract clause to an
exact artifact or trace fact. Keep `insufficient_contrast` and ABSTAIN; repeat a
frozen contrastive arm before the free-versus-constrained probe ablation. Full
evidence and claim limits are in the
[A5 report](../reports/2026-08-08-qfbench-a5-failure-type-probe-discovery-report.md).
