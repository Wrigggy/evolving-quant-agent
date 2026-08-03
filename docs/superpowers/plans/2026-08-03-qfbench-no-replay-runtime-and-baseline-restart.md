# QFBench No-Replay Runtime and Baseline Restart Plan

> Design: `docs/superpowers/specs/2026-08-03-qfbench-no-replay-runtime-and-baseline-restart-design.md`

1. Preserve and hash the old formal run; enumerate its completed duplicate
   identities and record that repetition 02 is blocked.
2. Add failing unit tests around the remote NexAU adapter for SDK retry zero,
   one outer attempt, the 360-second timeout floor, and post-construction drift.
3. Implement the adapter-only no-replay invariant without changing candidate
   worker bytes or official scoring behavior.
4. Run focused tests, all rootless/baseline/supervisor tests, then the complete
   local suite and `git diff --check`.
5. Add a dated superseding decision and update `docs/PROJECT_MEMORY.md` without
   rewriting the old run or prior decisions. Commit and push; do not merge.
6. Deploy the exact commit to `bc`; run the no-model NexAU adapter canary and
   the old-run duplicate/resource audit.
7. Run one paid worker/verifier canary. Require a unique accepted-request set,
   official provider pin, offline verifier, clean firewall scan, and cleanup.
8. Materialize a publish-once launch configuration for a new run identity,
   preserving all experiment inputs except the recorded runtime source commit.
9. Run repetitions 01 and 02, monitor autonomously, and stop on identity,
   provider, firewall, verifier, host-capacity, or cleanup failure.
10. Audit 170 scores, per-repetition metrics, costs/lower bounds, no replay,
    historical-run immutability, and zero residual resources. Do not start
    repetition 03.
