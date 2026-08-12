# QFBench A6 R11 ME8B compact-overflow engineering negative

Date: 2026-08-11  
Run: `qfbench-a6-discovery-e-flash-high-20260811-r11-me8b`  
Status: contained mechanism failure; same ID frozen and non-resumable

## Outcome

ME8B did not fail at the provider boundary. All 15 wire attempts completed with
HTTP 200 on exact `deepseek/deepseek-v4-flash-0731`; all had retry index zero
and unique logical, request, and provider IDs. The accepted totals were 570,103
input tokens, 45,433 output tokens, 615,536 total tokens, and USD
`0.0388147256`.

The run made real discovery progress: it recorded one schema-1 probe, one
probe-bound non-ready `CONTINUE` checkpoint that advanced into epoch 1, and one
schema-2 contract/artifact/trace probe on `corporate-action-adjustment`. It did
not reach ACT, ABSTAIN, a decision, candidate mutation, validation, admission,
or evaluation. The candidate tree stayed byte-identical at
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`.

## Exact compact failure

Before paid call 15, the deterministic checkpoint-repair compact payload was
65,492 bytes against a 65,536-byte cap: only 44 bytes remained. Call 15
completed HTTP 200 and returned a malformed `checkpoint_continue`; the local
validator correctly rejected it with:

`next_hypothesis_ids must be an exact subset of probe expectation IDs`

Persisting the exact error and validation snapshot increased the next required
compact state to 65,943 bytes, 407 bytes over the cap. The measured dominant
components were 57,829 bytes of current progress, including 46,222 bytes of
verified navigation (44,630 bytes in its task records), 8,432 bytes of probe
state, and 1,311 bytes of access state.

The next `before_model` raised `structured epoch state exceeds byte cap`.
NexAU swallowed that hook exception and attempted another model-call entry.
The wrap guard blocked the attempted call before provider I/O, so there was no
sixteenth wire attempt. This means call 15 was a real paid request and must not
be described as blocked or absent; the blocked operation was the attempted
call 16.

The same trace also exposed an audit-ordering bug: the validation record's
`sequence` field overwrote the middleware event sequence, yielding the local
event order `91, 1, 93`. This did not cause the compact failure but weakens
machine audit ordering and must be fixed.

## Process and containment

The primary service exited nonzero. Systemd then made two automatic restart
attempts; both were rejected by the already-claimed model-boundary marker
before model/provider work. The service and health timer are now inactive and
disabled, and run-scoped Podman and Docker resource counts are zero. The ME8B
marker, append-only proxy ledger, diagnostics, probes, checkpoint, validation
error, and lifecycle records remain frozen; ME8B must never resume.

## ME9 boundary

ME9 is a fresh engineering successor, not a continuation of ME8B state. It
should normalize the model-prompt copy of navigation by removing recursively
duplicated `access_binding` objects while retaining all exact paths, hashes,
sizes, roles, manifests, task IDs, access flags, and durable navigation
identity. Older probes/checkpoints should be deterministic hash/reference
summaries while the latest active records remain complete. The byte cap may be
raised to the already bounded 131,072-byte epoch reserve only together with
that projection and worst-state tests; a cap-only change is insufficient.

Most importantly, wrap-side validation immediately before `next_handler` must
fail before provider I/O whenever compaction, navigation identity, or durable
state verification fails—even if NexAU swallows `before_model`. No ACT or
ABSTAIN may be synthesized.

Machine-readable evidence:
`output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me8b-continuation/r11-me8b-engineering-compact-overflow-negative-20260811.json`.
