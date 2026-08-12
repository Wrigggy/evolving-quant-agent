# QFBench A6 R11 ME5B Engineering Negative

> Status: measured engineering-only negative result from one A6-E continuation.
> This is not a formal A6 result, a statistical comparison, or evidence of
> candidate benefit. The run ID is frozen and must not be resumed.

## Outcome first

ME5B materially improved the discovery mechanism's execution path: it produced
three real, artifact-bound probes and three durably validated checkpoints. One
malformed checkpoint was rejected locally with an exact error, then repaired on
a later model call. This is positive engineering evidence for the probe and
checkpoint interfaces.

It did **not** complete the intended end-to-end mechanism. All three checkpoints
were `CONTINUE`, all hypotheses remained open, and the final checkpoint was not
decision-ready. No `ACT`, valid `ABSTAIN`, downstream decision, proposal,
non-empty candidate diff, validation, admission, or candidate evaluation
exists. ME5B is therefore an engineering negative, not a weak success.

The machine record is
[r11-me5b-engineering-negative-20260811.json](../../output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me5b-continuation/r11-me5b-engineering-negative-20260811.json),
7,130 bytes, SHA-256
`c1ef8407f8f86be43b5949b1249d0a53a2b6b52bebdf14d01a0d1df0df38f769`.

## Measured execution and accounting

The sealed proxy ledger contains 25 rows. Every row is a completed HTTP-200
response from `deepseek/deepseek-v4-flash-0731`; all provider request IDs,
logical request identities, and wire request identities are unique, every
`retry_index` is zero, and no failure class or fallback is present.

| Metric | Measured value |
| --- | ---: |
| Provider calls / HTTP 200 | 25 / 25 |
| Input tokens | 993,640 |
| Output tokens | 70,234 |
| Total tokens | 1,063,874 |
| Provider cost | USD `0.064557136` |
| First request start | `2026-08-11T02:12:18.872143Z` |
| Last response finish | `2026-08-11T02:22:50.993589Z` |

The exact ledger is 15,587 bytes with SHA-256
`3c206d25503fe860672f46e7e3aeaca72d48b083d054a196699c895c709f9fb6`.
The middleware's terminal capture records 25 total model calls within the
unchanged bounds of 48 provider calls and 1,800 wall seconds; its elapsed time
was 632.994 seconds.

## Structured discovery progress

The run persisted 97 access records over 42 distinct recorded paths, then
created these three schema-1 contrastive probes:

| Probe | Bound result SHA-256 |
| --- | --- |
| `p_epoch0_bootstrap_process_sig` | `ed08960a9972f88c9d2630f770d5a2f3635b337f1e382fae01c91ad0d6a6e4cb` |
| `p_epoch1_repair_bootstrap_numeric_vs_construction` | `60ae60e4dfeab0bec44641da81f0bf73a75374696c8d9ccb3e8185adec387e66` |
| `p_epoch2_repair_manifest_vs_convention` | `048ea5f5476aeada32d96ad59126a1fb407a32387a7814942a86ff967e81eacc` |

Each probe was bound into one `CONTINUE` checkpoint. The first two checkpoints
advanced to a fresh exploration epoch; the third was the non-ready final
checkpoint and did not advance. The checkpoint hashes were, in sequence:

- `f0ca1b90a8be3e4d2abd944c32b3ba802409ceb9dffe699961236d8e788beb51`;
- `1b001b48b0aa947b0f667ad7e5513aeb2503dc45f628a2d5d583068b3ae28935`;
- `c116c06af5c5a7f533ec3c33972fa165306f4177c01ae3bbaf0f1e473ea8c963`.

All three records have `ready_for_decision=false`, an unchanged candidate tree
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`,
empty intervention fields, and open hypothesis statuses. Their semantic memory
is explicitly labeled `verified:false`; it is not counted as causal evidence or
readiness.

One checkpoint attempt was locally rejected with
`checkpoint_schema_or_binding: next_hypothesis_ids must be an exact subset of
probe expectation IDs`. The error was persisted, surfaced to the model, and
repaired: later checkpoints were successfully appended. This establishes that
the narrowed checkpoint schema, prevalidation, durable error feedback, and
bounded repair path were operational. It does not establish that the model can
reach a calibrated final decision.

## Terminal failure and fail-closed behavior

After checkpoint 3, the final-epoch gate raised `final exploration epoch
checkpoint is not decision-ready`. NexAU swallowed that before-model middleware
exception and attempted to enter another model call. The ME5 guard then rejected
that unpaired call with `model call has no matching before-model guard`, before
provider access. This second message is a fail-closed safety action, not an
additional provider failure and not evidence of a successful terminal result.

The generic sandbox wrapper prepended an `E2B SDK not installed` hint. Lifecycle
records prove that the actual backend was rootless Docker, so that boilerplate
is not treated as the causal failure. The measured immediate mechanism failure
is the non-ready final checkpoint plus the executor's attempted unguarded
re-entry.

Systemd scheduled one restart 30 seconds later. The durable model-boundary
marker rejected it before runtime/provider construction with `A6 model boundary
was already claimed; use a fresh run ID`. Thus the restart added zero provider
calls and zero cost.

## Identity, durability, and containment

The engineering overlay was external to and did not modify the immutable R10
release. Important identities are:

- immutable source tree:
  `d5d954b0c404e6f4521d91cd72a99c832aa237d33e219eaaa06a2350703a4335`;
- external ME5/ME5B runner:
  `6caca4ec8098d4f9bdd38bee7f41a8c10417b54a462eade3d997b08d7ec79b34`;
- overlay tree:
  `6d2cfb80b5c1097ed5d48ceb4e913305147aa6f3da8cf0a7d2c70c81669bfbc6`;
- agent overlay contract:
  `3a523f445266bb9c08d6af22d2d6827017893b92df343407dcba67513e189cdb`;
- plan / preflight:
  `977a197ac4eb37a43c29aa46b18066ebd554c6b66a7a1f28787d86f97f013785` /
  `ab6b843ac21e9606b6ef356a91f97d6917b18656319018458615001dba86a437`;
- model-boundary marker:
  `065d5d27d5fa8d2966ca268a8639d4ea495fde2eaf6a82bd6db3518d696ed2ee`.

Failure diagnostics were copied before exact sandbox cleanup and explicitly
labeled `ENGINEERING_EVOLVER_FAILURE_DIAGNOSTICS_NOT_A_RESULT`. The probe,
checkpoint, validation-error, and terminal-reserve SHA-256 digests are,
respectively:

- `ecc593f71bd593d447b688482b96a879e2b61480957c5fcbeb4027841a2cef9b`;
- `1221ba71d3c108f8a0baf5511b307858ef4cf4db9986287fd3475b85c92e812c`;
- `32273fa0e0d9c436996eb59f547422fa2c889ab11a68096a14a98fd1fc07a261`;
- `36a8b7b8dc0efdefa403a9c38a381b20b8f48f52436feb815955ddb16437483c`.

The Evolver container, proxy container, and run-scoped proxy network were all
cleaned by exact native ID. The canonical reaper's final pending/inventory count
was zero. The service is inactive and disabled. A final additive mirror
completed at `2026-08-11T02:25:33Z`.

## Engineering implication and next proposal

Measured: ME5's derived-artifact checkpoint interface and precise repair
feedback worked. Measured: the model still consumed its last epoch by choosing
another honest `CONTINUE`, leaving no terminal branch and no candidate.

Proposed, not tested in ME5B: a fresh ME6 mechanism should make the final epoch
a distinct commit phase that exposes only `ACT` and `ABSTAIN`; text,
`CONTINUE`, or unauthorized calls should be scrubbed and returned as exact local
errors for a bounded number of guarded repairs. Repair exhaustion should end as
a clean local no-decision failure, without attempting an unguarded provider
re-entry. This proposal must use a fresh identity, retain the 48-call / 1,800-s
global bounds, pass independent tests and packaging gates, and remain unlaunched
until independent source, package, and same-ID live-preflight gates pass; the
existing standing authorization then permits direct launch. A candidate panel
remains separately gated on a valid ACT plus a non-empty, validated, admitted
candidate diff.
