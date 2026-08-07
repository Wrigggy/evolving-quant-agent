# 2026-08-07 — Self-Hosted, Model-Configurable Quant Discovery

Status: **implemented locally; self-hosted mechanism canary pending**.

This decision supersedes
[the earlier same-day discovery-canary decision](2026-08-07-quant-evolver-discovery-canary.md).
It changes the methodological identity and the runtime route; it does not erase
the earlier record or the infrastructure failures observed while attempting it.

## Conclusion

QEA will not reproduce Agentic Harness Engineering (AHE) as its proposed
method. AHE remains cited related work and an attributed historical baseline.
The current research object is QEA's own quant-specific discovery protocol,
executed with a model selected by us in our self-hosted rootless environment.
E2B is not used by this discovery track.

The exact model, provider, and deliberation request are run configuration, not
the identity of the method. A capable reasoning model may be selected, but the
paper cannot describe “using AHE's full-reasoning harness” as a QEA
contribution.

## Method boundary

The independent QEA discovery protocol under test consists of:

1. a quant evidence graph connecting task outcomes, trace events, component
   bindings, activation, candidate ancestry, and artifact/process summaries;
2. a deterministic debugger/indexer that exposes anomalies without asserting a
   root cause, paired with an evolver that must check the index against raw
   evidence;
3. a fail-closed discovery contract requiring competing mechanisms,
   counterevidence, uncertainty, an exact-evidence trail, and a discriminating
   probe before any candidate write;
4. a quant component and reachability model spanning prompt, agent config,
   tools, tool descriptions, validators, skills, memory, middleware, and
   routing, with no skill-first prior;
5. process measurements for evidence access, grounded citation, hypothesis
   competition, contract consistency, component activation, and later task
   outcome.

These elements are hypotheses about an effective quant evolver, not yet a
novelty or performance claim. Before a paper-level novelty claim, the combined
mechanism still requires a dedicated prior-art screen and component ablations.

## What remains attributed rather than claimed

The repository's original v0 contains an explicitly credited AHE-derived
`evolve -> falsify -> rollback` baseline and some ported verdict/manifest logic.
Those files keep their provenance notices. They may serve as a historical or
experimental baseline, but they are excluded from QEA's novelty claim.

Likewise, long contexts, tool-using agents, debuggers, structured traces,
component observability, and keep/rollback selection are general or published
ideas. QEA does not claim any one of them in isolation. The candidate research
claim, if the experiments support it, must concern the quant-specific discovery
and evidence-to-intervention mechanism above.

## Self-hosted execution contract

The discovery canary uses the existing self-hosted rootless Docker backend:

- immutable role images and exact runtime identity;
- an allowlisted model proxy binding one exact model and provider;
- no unrestricted host shell or network for the evolver;
- sanitized public evidence only;
- a trusted coordinator for admission and scheduling;
- an offline, evaluator-isolated verifier for later candidate scoring.

Historical E2B support remains in the repository because it is prior evidence
and an older backend, but no new discovery-E2B runner is part of this method.
The briefly added E2B discovery canary was removed before any external call.

## Model and deliberation configuration

`qea/evolve_agent_full/agent.yaml` is model-neutral: it reads the model, base
URL, and credential from the bounded runtime environment and contains no fixed
reasoning body. For each run, the coordinator materializes an auditable evolver
profile containing:

- exact selected model;
- exact required provider;
- deliberation request: `none`, `minimal`, `low`, `medium`, `high`, or `xhigh`;
- source and materialized evolver tree digests.

The selected deliberation request is added only if the chosen model route
supports that request. Resume is fail-closed: changing the model, provider,
deliberation level, or evolver bytes under the same run identity is rejected.
The rootless config remains the enforcement point for the actual route.

## Immediate experiment

Build matched raw and indexed public-evidence arms from the same post-A3 state,
then produce one proposal per arm with one explicitly selected self-hosted model
profile. This is a quick engineering mechanism check, not an AHE replication
and not a paper-scale comparison. Candidate scoring, if performed, uses the
same protected worker route and offline verifier in both arms.

The canary asks whether the full loop is observable and behaviorally testable:
does the evolver inspect exact evidence, distinguish competing mechanisms,
select a reachable component for a causal reason, make an admissible change,
and state a prediction that later traces and task rewards can falsify?

## Preserved negative infrastructure evidence

Three rootless attempts under the superseded route did not test the mechanism:

- `qfbench-discovery-full-reasoning-raw-gpt54-xhigh-20260807-r1` failed because
  the evidence path was outside the trusted run root; no model call occurred;
- `...-r2` and `...-r3` reached the selected GPT-5.4 route but received provider
  HTTP 403 region failures before the agent read evidence or proposed a change;
- the E2B alternative was stopped before external execution and incurred no E2B
  run.

These are retained as infrastructure results. They are not negative evidence
about QEA discovery quality, and the new decision does not continue that route.
