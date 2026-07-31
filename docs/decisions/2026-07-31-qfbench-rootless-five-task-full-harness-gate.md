# Decision Record: Rootless Five-Task Full-Harness Gate

> Date: 2026-07-31<br>
> Status: accepted for staged rootless scoring; larger repetitions gated<br>
> Scope: shared `bc-server` rootless Docker full harness<br>
> Evidence run: `qfbench-rootless-five-rich-1x-20260731-r3`<br>
> Supersedes: the operational-default and fresh-worker restrictions in the
> [2026-07-30 backend gate](2026-07-30-qfbench-rootless-backend-gate.md)

## Decision

Self-hosted rootless Docker is now the default backend for new QFBench
full-harness development and staged scoring. E2B remains an explicit fallback
and historical reference, but a new matched E2B run is not a prerequisite for
rootless experiments. This implements the approved
[direct-cutover design](../superpowers/specs/2026-07-30-qfbench-rootless-direct-cutover-design.md).

The rootless backend may run the five-task, one-iteration protocol. Do not yet
advance to the five-task three-iteration or 30-task protocols. First complete a
deliberate coordinator-kill, exact-ID reaper, and resume exercise through the
production full harness, and make provider token/cost telemetry authoritative.
This is a rollout gate, not a return to E2B as the default.

## Measured Evidence

Run `qfbench-rootless-five-rich-1x-20260731-r3` completed one Rich evolver
proposal and all 10 scheduled official scoring attempts: three optimize seed,
two held-out seed, three optimize candidate, and two final held-out attempts.
The run used QFBench commit
`024921eb507fcc0c4ffe3e0a96802724be1ae84a`, model
`deepseek/deepseek-v4-pro` through OpenRouter, and these identities:

- image set: `22518d957a872648e01ad3076336fe9f582d08ae5437f954fbec454c48963715`;
- runtime: `c0e986e18e2ef3d407903910c1490b4c1360b9976b5007a04d3f41844581e3b8`;
- scheduler: `9c10b5f6af38645b0c11e17990e452fb34d50084d2810eaa6f0c847dd33e9b18`.

The source lineage began at `8eecc0f` and required two tested repairs:
`b7d1a2f` added bounded proxy-readiness retry, and `33e2294` restricted replay
quarantine to ambiguous post-accept requests. Resume reused completed work and
retried only failures proven to precede upstream acceptance.

The candidate was admitted but rolled back. Optimize domain macro remained
`0.95833325`; held-out seed and final scores were both `1.0`. The candidate
improved the `evt-pot-var` diagnostic count from 48/55 to 51/55 passing tests,
but its official reward remained `0.833333`. This is backend and orchestration
evidence, not an evolution-gain claim.

## Isolation, Recovery, and Cost Findings

- Verifiers were independent containers with `--network none`; official tests
  and reference data remained in coordinator-trusted storage.
- Worker/evolver inputs contained no official tests, reference data, solutions,
  `.env`, or real provider credential. A 34,199,316-byte scan over 294 files
  found zero secret exposure; no official solution was uploaded or run.
- The evolver received Rich optimize-only evidence. Held-out task identities and
  outcomes did not appear in its evidence surface.
- All 123 canonical proxy request records completed with HTTP 200. Two archived
  replay-denial lineages were pre-upstream and therefore safely retried.
- Final managed container and network counts were zero.
- Provider cost/token fields for the full run are `null`, not zero. A separate
  route probe recorded `$0.00028275432`, but it is not the full-run cost.

The run's end-to-end wall-clock span was about 94.9 minutes, including repair
and resume downtime. Individual verifiers took roughly 2–4 seconds; model-bound
worker/evolver lifecycles dominated elapsed time.

## Preserved Boundaries and Next Gate

Official scoring remains deterministic and verifier-based; no LLM judge is
introduced. Official tests, expected/reference values, raw trusted verdicts,
solutions, credentials, and held-out outcomes remain unavailable to workers and
the evolver. The shared-host administrator can theoretically inspect
`julius`-owned files; this accepted residual risk means rootless Docker is not
claimed to provide microVM-equivalent isolation.

Before any larger repetition, record a production full-harness interruption
that proves no duplicate completed model request, worker artifact, verifier
score, or proposal after exact-ID reaping and resume. Also persist authoritative
provider usage/cost or explicitly reconcile it from provider billing. Stable
gain, held-out transfer, cost advantage, and statistical significance remain
unproven.
