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
results/quantcodeeval-v2-mechanism-canary-20260812-v4/
```

The exact identities are recorded in the corresponding
[decision](../decisions/2026-08-12-quantcodeeval-v2-variable-full-harness-search.md).

Focused validation after implementation:

```text
87 passed in 2.56s
```

This covered history storage and tamper rejection, v2 evidence projection,
variable-length state transitions, full-candidate admission, Evolver guarded
component tools, component attribution, mutation metrics, and the no-model
end-to-end loop. The complete repository test suite passed `1277 passed, 1
skipped` after installing the declared NexAU and GDPval extras and permitting
test-only loopback binding. The standalone persisted canary additionally
reported:

```text
1 passed in 0.11s
```

The next measured experiment should not be another prompt bundle. It should
first wire the QuantCodeEval adapter through the rootless runtime, then compare
the existing prompt-checkpoint behavior with a deterministic early-checkpoint
middleware candidate. Quant correctness should be a later, separately
attributed tool or validator intervention.
