# QFBench A6 R11 ME8 provider-interrupted engineering negative

Date: 2026-08-11  
Run: `qfbench-a6-discovery-e-flash-high-20260811-r11-me8`  
Status: contained provider interruption; not a mechanism verdict

## Outcome

ME8 did not reach ACT or ABSTAIN. The first eight wire attempts completed with
HTTP 200. Wire attempt 9 ended with upstream HTTP 520 and
`failure_class=provider_http_error`, with no provider request ID, token usage, or
cost on that failed row. The run then ended incomplete with terminal phase
`invalid` and `after_agent complete=false`.

This is a provider-interrupted engineering negative, not evidence that the ME8
navigation mechanism failed. The exact ME8 ID is frozen and must never resume;
its model-boundary marker, request audit, diagnostics, and lifecycle records
remain immutable evidence.

## Exact accounting

The append-only proxy audit contains nine unique logical request identities and
nine unique request identities, all at retry index 0. Eight rows are HTTP 200
and carry eight unique provider request IDs. Their measured totals are:

- input tokens: `211,435`
- output tokens: `10,681`
- total tokens: `222,116`
- provider cost: USD `0.0141870232`

The ninth row is HTTP 520 with null usage, cost, and provider request ID. The
audit interval runs from `2026-08-11T04:38:09.230000+00:00` through
`2026-08-11T04:39:51.235307+00:00`.

## Mechanism progress before interruption

ME8 recorded one real schema-1 probe,
`eval-sig-target-vs-protection`, and one probe-bound non-ready `CONTINUE`
checkpoint. The checkpoint left both hypotheses open and did not open the
decision phase. There was no ACT, ABSTAIN, decision state, candidate write,
diff, validation, admission, proposal report, pilot report, or candidate
evaluation.

The candidate tree remained exactly
`4ad9cd8d8450dabc845e7bbc6467127d2405f2db156da2d89f152f06887ac46c`.
Therefore the run supplies neither ACT-path evidence nor candidate-benefit
evidence.

## Containment and replacement boundary

The proxy network, proxy sandbox, and Evolver sandbox were cleaned by exact ID;
the final Podman and Docker container counts for this run ID were zero. The
service and health timer were inactive and disabled at audit time.

A fresh ME8B may repeat the same engineering mechanism because the interruption
occurred at the provider boundary. ME8B must use byte-identical runner and nine
overlay files, the same answer-free evidence, model/provider route, budgets, and
isolation. Only the fresh run/unit/watch/mirror identity may change. This
replacement remains engineering-only and cannot silently inherit ME8 progress.

Machine-readable evidence:
`output/qfbench-supervisor/a6-d5d954b0c404e6f4-r11-me8-continuation/r11-me8-engineering-provider-negative-20260811.json`.
