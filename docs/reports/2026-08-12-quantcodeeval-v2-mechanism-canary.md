# QuantCodeEval v2 mechanism canary result

> Date: 2026-08-12
>
> Result: PASS for deterministic search mechanics; no live model call and no
> QuantCodeEval score measurement

The v2 canary verified the specific mechanism requested after the original
five-round prompt-mutation run. Search is now variable-length, the mutation
surface is the full NexAU worker harness, and prior rejected edits are exposed
to the next Evolver as exact source and diff evidence.

The canary executed two fixture rounds. Round 1 made a prompt-only change and
was rejected because the fixture exposed no new property-family information.
Round 2 inspected the immutable round-1 patch, selected a deterministic tool
mechanism, added the tool implementation, description, and agent registration,
passed independent full-harness admission, and reached the fixture target. The
outer search stopped after two rounds rather than consuming a fixed five-round
schedule.

This result establishes plumbing and state semantics only. The `[1, 0] ->
[1, 1]` vectors in `SEARCH-STATE.json` are deterministic fixture values, not
measured T16/T24 rewards. Model-request counts are also fixture accounting and
cost is zero because no provider was called.

Evidence is retained under the ignored generated-results root and force-added
to Git for this specific canary:

```text
results/quantcodeeval-v2-mechanism-canary-20260812-v5/
```

The exact identities are recorded in the corresponding
[decision](../decisions/2026-08-12-quantcodeeval-v2-variable-full-harness-search.md).

Focused validation after the original implementation passed 87 tests. After
binding every component smoke to the exact candidate digest and adding the
real activation-canary wiring, the focused suite passed:

```text
51 passed in 5.76s
```

This covered history storage and tamper rejection, v2 evidence projection,
variable-length state transitions, full-candidate admission, Evolver guarded
component tools, component attribution, mutation metrics, and the no-model
end-to-end loop. The earlier complete repository test suite passed `1277
passed, 1 skipped`. After activation wiring, a complete rerun passed `1280
passed, 1 skipped` with one proxy retry timing test flaky; that exact test
passed immediately in isolation. The standalone persisted canary additionally
reported:

```text
1 passed in 0.11s
```

The real one-round activation runner is now implemented in
`scripts/run_quantcodeeval_v2_activation.py`. It revalidates the published
release and H0, reuses H0 without resampling, runs one isolated real Evolver
round, and stops before candidate T16/T24 evaluation. It treats prompt-only
output as an activation failure and requires an executable primary component's
last passed smoke to match the final candidate digest. A full candidate panel
should be run only after this gate demonstrates a usable component mutation.
