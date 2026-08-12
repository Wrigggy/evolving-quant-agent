# QFBench A6 R11 Engineering Discovery Negative Result

> Status: measured engineering-only three-arm negative result. This is not a
> formal A6 result, a statistical comparison, or evidence of candidate benefit.
> All three discovery IDs are frozen; candidate evaluation remains not run.

## Outcome first

The explicitly nonformal R11 engineering path successfully exercised all three
proposal-only A6 representations against the pinned
`deepseek/deepseek-v4-flash-0731` route, with live Evolver/proxy isolation
(worker evaluation absent), sealed request accounting, bounded restart
protection, exact cleanup, and a durable additive mirror. It did **not** produce
a contract-valid terminal decision, proposal, diff, or candidate in any arm.

- A6-R exhausted the terminal model-call budget after repeated
  `read_workspace` calls used an invalid `max_lines` parameter.
- A6-E exhausted the terminal model-call budget before a valid terminal
  decision.
- A6-EC attempted an `ABSTAIN`, but nested it under a parameter structure that
  the exact `decide_candidate` tool schema rejected. The intent is preserved as
  diagnostic text; it is not a valid ABSTAIN result.

The machine-readable record is
[r11-engineering-discovery-negative-result.json](../../output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11/r11-engineering-discovery-negative-result.json),
6,995 bytes, SHA-256
`7ce74a2b3bddf918bebbbb1e48fee5e14b3c00ada4e9cc04cff6f951bf36d170`.

## Claim and provenance boundary

The launch was intentionally labeled
`ENGINEERING_ONLY_MIXED_HISTORICAL_AND_PARTIAL_CONTEXT_NOT_FORMAL_OR_STATISTICAL`.
It combined complete historical R7 answer-free context with an explicitly
incomplete R11 runtime readout. Every persisted plan and progress artifact
states:

- `formal_seed_admissible=false`;
- `statistical_claim_allowed=false`;
- `candidate_evaluation_authorized=false`.

The external engineering runner SHA-256 is
`425db2b1ea1442451a6fc96a3970c2e48c13be96881f22ac522b0948ffa982ca`.
It imported the immutable R10/R11 execution release at
`/home/julius/qea/deploy/releases/a6-d5d954b0c404e6f4-r10`, whose source tree,
external identity record, and launch identity are respectively:

- `d5d954b0c404e6f4521d91cd72a99c832aa237d33e219eaaa06a2350703a4335`;
- `c7064b96d3f83376a227bc5d8d77d08ac93c1f38f0bf3e46b2485c3c755c4808`;
- `b19c2a0f731e27dd367ac6620270887e4b02155e0e327c1539eaea3098727b89`.

The corrected partial-seed readout SHA-256 is
`2b7a576dd9a3628651cd0cad0064a005b144b73501bd3e30a019db65ebef28fd`;
the three-arm engineering corpus audit SHA-256 is
`65ce5698482314ea0c0eef9effff385e8ef54bab31dc113c22bae94920490e6f`.
The provider, model, high-reasoning setting, no-fallback rule, rootless config,
image set, and scheduler identities remained fixed across the three arms.

## Measured accounting and outcomes

The three sealed ledgers contain 60 wire rows representing 59 logical calls:
59 completed HTTP-200 responses and one safe `not_accepted/rate_limited` retry
in A6-E. There are no other noncompleted rows, missing ledgers, quarantines, or
unsealed prefixes. Usage and cost count accepted HTTP-200 responses only.

| Arm | Wire / logical | HTTP 200 | Safe 429 | Tokens | Cost | Terminal outcome |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| A6-R | 22 / 22 | 22 | 0 | 2,166,790 | USD `0.0569006424` | invalid; terminal budget exhausted after tool-parameter errors |
| A6-E | 21 / 20 | 20 | 1 | 1,761,639 | USD `0.0575479968` | invalid; terminal budget exhausted |
| A6-EC | 17 / 17 | 17 | 0 | 1,164,197 | USD `0.0500762584` | invalid; malformed tool call after ABSTAIN intent |
| **Total** | **60 / 59** | **59** | **1** | **5,092,626** | **USD `0.1645248976`** | **zero valid decisions or proposals** |

All ledger rows use the pinned Flash model. Wire, logical, and accepted-provider
identities are unique within their applicable scope. No fallback, unknown
accepted call, or accounting ambiguity was observed.

The exact per-arm raw command records are preserved and exited `1` without
runner timeout. Their SHA-256 digests are:

| Arm | Command record | Proxy audit | Model-boundary marker |
| --- | --- | --- | --- |
| A6-R | `409f21b5e6f76e665432faa75050f5cd695f3f8d914ed0bc9301accbb0fcb40b` | `34e8c5b1cfb62037b529e3e364e5c75152660f966557365b67035b780395119b` | `25e10c9904c75402409d3398313a863984cea4c6e2674cf31076f4c8f70da4a7` |
| A6-E | `74e6113ea110d5d1ebb7f85bbaec87c27e2436afb9785dff15319966706899b8` | `32ca962c7275d4be91a1a693a5c2e9ba81a87a5e2d7c9c81923c368e56dec29b` | `9bc308bdc5f53273e61c1100c3e3f334af7c224662762cce791f33338e4742a0` |
| A6-EC | `7a4aef6acbd9df6e1744fc389d18cbc4e403e3c6ecac456dd1527421c18864c6` | `96e0c3b6248b7e193c0e290e235c832b8efc9aeaf4f542327ffdfb5b170d1f59` | `03c80d2178ade3a8ee53f0fe79119fa84f1a619fac7bdec76a557676b10720a0` |

The generic sandbox error wrapper also printed an E2B-install hint. The live
backend and lifecycle records are rootless Docker, so that prefix is not treated
as evidence that missing E2B caused these failures; the arm-specific terminal
and tool-schema errors above are the measured immediate failures.

## Restart boundary and safety closure

Each paid invocation created its durable mode-`0600` model-boundary marker.
After the primary failures, systemd attempted three R restarts, two E restarts,
and one EC restart that all failed before runtime/provider construction on the
existing marker. R's final displayed `NRestarts=4` additionally includes a
fourth scheduled start that lost the explicit-stop race and received TERM before
provider access; it must not be reported as four paid retries. No restart made
an additional model call.

The live isolation audit found one unique run-scoped internal network and one
Evolver/proxy pair per arm. Evolvers were internal-only; proxies had bridge plus
the matching scoped network. Exact pinned images were used, with zero mounts,
published ports, or cross-arm network membership. Each authorized-evidence
access log remained a zero-byte file. Candidate, score, proposal-report, and
pilot-report artifacts are absent.

All six containers and three networks were exact-ID cleaned by their owning
runtime. A later canonical dry reaper scanned two container manifests and one
network manifest per arm and found zero pending IDs, identity mismatches,
failures, or final inventory; leases are zero. The monitor was unloaded before
the arm services were stopped, all timers and services are inactive, and both
LaunchAgent labels are absent.

The additive mirror synchronized the final R, E, and EC bytes at
`09:00:57Z`, `09:01:00Z`, and `09:01:03Z` respectively. The mirrored plans,
progress, markers, command records, and proxy-ledger digests match the remote
files; mirror stderr is zero bytes and the mirror LaunchAgent is unloaded.

## Engineering implication

This run localizes the immediate feasibility bottleneck to terminalization and
tool-interface interoperability. It does **not** distinguish the scientific
value of raw evidence, evidence, and evidence-plus-contract representations:
none reached the common exact decision boundary. The EC trace is useful only as
evidence that the model could articulate an abstention rationale before losing
it at tool-schema validation; it is not evidence that EC outperformed R or E.

The next engineering decision, if work resumes, should be made against these
preserved failures rather than by adding more tasks or evaluating a nonexistent
candidate. No repair, rerun, candidate evaluation, A6-F, feedback, mutation, or
statistical repetition was authorized or performed as part of this record.
