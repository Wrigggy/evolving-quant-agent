# QFBench Official-Provider Route Decision

> Date: 2026-08-01<br>
> Status: approved for implementation and paid execution<br>
> Supersedes: the provider-routing portion of the 2026-07-31 all-task baseline design

## Decision

The repeated 85-task base-worker baseline will use
`deepseek/deepseek-v4-pro` through OpenRouter's first-party DeepSeek endpoint.
The trusted per-attempt model proxy must inject this exact routing object into
every upstream request:

```json
{"provider":{"only":["deepseek"],"allow_fallbacks":false}}
```

`deepseek` is the endpoint tag published for provider `DeepSeek` in the
2026-08-01 OpenRouter endpoint probe. The route is fail-closed: the proxy
rejects a worker-supplied `provider` object, and OpenRouter must return an error
instead of using another provider when the first-party endpoint is unavailable.

## Experiment Boundary

The previous default-route repetitions and the three-task `:nitro` run are
diagnostic only. They do not count as formal repetitions because they do not
prove first-party-provider identity. The rerun starts at repetition one under a
new run ID and retains the frozen QFBench commit, 77 primary plus eight
diagnostic tasks, unchanged `qea/worker_gdpval_weak`, no evolver, worker
concurrency 4, verifier concurrency 3, isolated offline official verifiers,
five-repetition maximum, and USD 60 projected-total-cost gate.

## Evidence and Acceptance

The immutable runtime identity and every proxy public-config identity must bind
the required provider. Repetition one is accepted only when all 85 official
scores, complete proxy cost records, evaluator-firewall scan, and exact-ID
cleanup audit pass. Provider/transport failures are infrastructure failures;
they are never converted to official score zero or silently rerouted.
