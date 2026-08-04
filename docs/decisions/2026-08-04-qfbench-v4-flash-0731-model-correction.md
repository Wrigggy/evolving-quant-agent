# QFBench V4 Flash 0731 Model Correction

Date: 2026-08-04  
Status: accepted; supersedes every prior decision that names the moving
`deepseek/deepseek-v4-flash` alias as the formal model. Scheduling, scoring,
isolation, no-replay, and five-independent-repetition requirements remain.

## Evidence

OpenRouter currently registers the requested model as
`deepseek/deepseek-v4-flash-0731` with canonical slug
`deepseek/deepseek-v4-flash-20260731`. Its endpoint registry exposes an official
`DeepSeek` FP8 route. By contrast, the former
`deepseek/deepseek-v4-flash` alias resolves to the 2026-04-23 model.

The official recovery probe
`qfbench-v4-flash-official-recovery-probe-cdaacdb-r2` therefore exercised the
wrong release. It completed eight HTTP-200 model calls, produced a valid worker
artifact, and passed all 12 isolated verifier tests, but post-hoc metadata
reported `deepseek/deepseek-v4-flash-20260423`. The earlier Cloudflare and
DigitalOcean provider-batch runs used the same wrong alias. Preserve all three
runs as infrastructure evidence and exclude their scores from formal results.
The DigitalOcean run was stopped at 11/12 scores and exact-ID cleanup removed
its final two containers and internal network.

## Decision

All new paid gates and formal runs must request exactly
`deepseek/deepseek-v4-flash-0731`, require provider `deepseek`, and set
`allow_fallbacks=false`. Post-hoc generation metadata may report only the
registered ID or canonical `deepseek/deepseek-v4-flash-20260731`; the 0423
alias, canonical ID, `latest`, and every non-DeepSeek provider fail closed.

Use fresh publish-once run IDs, configs, route identities, summaries, and
monitor units. Do not resume or import any attempt from a 0423 run. Before the
new 85-by-5 baseline starts, require a passing single-task official-route
canary and a passing 12-worker official-provider batch with isolated,
networkless verifiers, no within-attempt replay, and zero residual resources.

Retain the repetition barrier: repetition 01 uses its frozen epoch-1 scheduler;
repetitions 02-05 use the accepted 12/3 scheduler and two-second worker launch
ramp. Scores aggregate only after all five independent repetitions complete.
Cost remains a secondary audit field and does not gate scoring or launch when
request completion, route identity, isolation, and cleanup evidence are valid.
