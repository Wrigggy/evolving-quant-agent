# QFBench V4 Flash 0731 Formal Launch

Date: 2026-08-04
Status: formal repetition 01 active under an explicit operator override

## Accepted Evidence

Commit `b8c16dffac06bb786379cf4bef7d6849c7513a42` pins the requested model to
`deepseek/deepseek-v4-flash-0731` and accepts only its canonical metadata ID
`deepseek/deepseek-v4-flash-20260731`. The publish-once official-route canary
`qfbench-v4-flash-0731-official-provider-canary-b8c16df-r1` completed seven
unique HTTP-200 requests through provider `DeepSeek`, passed 12/12 isolated
verifier tests, and left no managed container or network.

The official 12-worker run
`qfbench-v4-flash-0731-official-batch-b8c16df-r1` reached measured worker
overlap 12 and completed 11 worker/verifier pairs. The final `evt-pot-var`
worker remained healthy but was executing a CPU-bound local `solve.py`. At the
user's direction, the run was stopped instead of waiting for its timeout.
Exact-ID cleanup removed the remaining worker, proxy, and internal network.
This run is capacity and partial end-to-end evidence; it is not a passing
12/12 batch and its scores are not part of the formal aggregate.

## Launch Ruling

Start the fresh publish-once formal run
`qfbench-rootless-base-85x5-official-deepseek-v4-flash-0731-20260804` from the
same exact commit, frozen 85-task manifest, base worker, image set, official
verifier inputs, and no-fallback DeepSeek route. Repetition 01 uses the
owner-only schema-4 epoch-1 config (4 workers, 3 verifiers, two-second launch
ramp) and `--stop-after-repetition 1` so it exits at a clean checkpoint rather
than entering repetition 02.

After repetition 01 completes, migrate that clean schema-v1 checkpoint to the
predeclared two-epoch schema-v2 contract. Resume repetitions 02-05 with 12
workers, 3 verifiers, and the same two-second ramp. Preserve independent
attempt IDs and aggregate scores only after all five repetitions. Cost remains
recorded when available but is not a launch, route, scoring, or cleanup gate.
