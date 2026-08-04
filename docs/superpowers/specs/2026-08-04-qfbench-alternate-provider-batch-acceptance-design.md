# QFBench Alternate-Provider Batch Acceptance Design

> Date: 2026-08-04  
> Status: approved by the user's instruction to test twelve-way scheduling on
> another provider while reserving official scoring for DeepSeek

## Goal and Claim Boundary

Validate the rootless scheduler at twelve concurrent workers while the official
DeepSeek V4 Flash endpoint is unavailable. The acceptance run uses the same
model slug, task panel, worker, images, resource contracts, launch ramp, proxy,
and offline verifier path as the official concurrency canary, but explicitly
pins a healthy alternate OpenRouter provider.

This is infrastructure evidence only. Its rewards, latency, tokens, and cost
must not enter the formal five-repetition baseline or establish official
DeepSeek capacity. The formal run remains pinned to provider `deepseek` with
fallbacks disabled.

## CLI and Validation

Add a distinct rootless-only mode, `paid-provider-batch`, with a required
`--acceptance-provider` argument. It must:

- retain model `deepseek/deepseek-v4-flash`;
- reject `deepseek`, because official-provider validation already has the
  separate `paid-baseline-batch` mode;
- require the argument to equal the owner-only rootless config's
  `required_provider`;
- require schema-4 epoch-two scheduling: worker/verifier concurrency `12/3`,
  launch interval two seconds, and the existing twelve standard 2-CPU/4-GiB
  tasks;
- require explicit paid-run approval and build the runtime without an evolver.

The existing `paid-baseline-batch` contract remains unchanged and continues to
reject every provider except `deepseek`.

## Execution and Artifacts

Reuse the existing paid batch evaluator and lifecycle/cost audits. Parameterize
only the expected provider and claim metadata. The alternate-provider result
must record:

- `mode: paid-provider-batch`;
- the configured provider and model;
- `formal_scoring_eligible: false`;
- an infrastructure-only claim boundary;
- measured worker overlap, official verifier completion, request identities,
  token/cost accounting, and exact cleanup.

Provider routing remains fail-closed through the proxy's OpenRouter
`provider.only` rewrite; fallback remains disabled. Any sent-request failure
freezes that publish-once run. It is not retried under the same attempt ID.

## Formal Scheduling Decision

The current baseline keeps repetition checkpoints. Each repetition runs its 85
independent attempts through the 12-worker pipeline, then persists its summary
and cleanup boundary before the next repetition. This retains the controller's
auditable resume and cost unit. A future evolve controller may interleave
repetitions within one frozen candidate, but it must preserve an iteration
barrier: all declared samples are aggregated before keep/rollback and before a
new candidate is proposed.

## Acceptance

Unit tests must prove that the official mode still rejects alternate providers,
the alternate mode requires an explicit matching non-official provider, both
paid modes omit the evolver, and the alternate artifact is ineligible for formal
scoring. Live acceptance additionally requires twelve measured overlapping
workers, complete successful request accounting, verifier-only trusted inputs,
networkless verifiers, no replay within an attempt, and zero managed residual
containers or networks.
