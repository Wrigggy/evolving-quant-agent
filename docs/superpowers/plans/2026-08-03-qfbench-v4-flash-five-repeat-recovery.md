# QFBench V4 Flash Five-Repeat Recovery Implementation Plan

> Design: `docs/superpowers/specs/2026-08-03-qfbench-v4-flash-five-repeat-recovery-design.md`

## Task 1: Make replay detection attempt-scoped

- Modify `tests/test_qfbench_baseline.py` first. Add one fixture with the same
  request hash in two distinct repetition attempts and assert that it audits
  successfully; add a second record with the same hash inside one attempt and
  assert a fatal duplicate.
- Run `python3 -m pytest -q tests/test_qfbench_baseline.py -k request_identity`
  and observe the cross-attempt test fail against the run-wide set.
- Modify `qea/qfbench_baseline.py` so duplicate membership is scoped to an
  attempt, while total request/cost accounting remains unchanged.
- Re-run the focused test and all of `tests/test_qfbench_baseline.py`.

## Task 2: Bind proxy completion to downstream delivery

- Add real HTTP integration tests to `tests/test_model_proxy.py`: a normal
  response records completed only after the worker-side write/flush succeeds;
  a deliberately disconnected downstream records a quarantined
  `downstream_delivery` terminal state with the provider status and usage/cost.
- Run `python3 -m pytest -q tests/test_model_proxy.py -k delivery` and observe
  RED.
- Modify `qea/model_proxy.py` to delay the terminal completed audit until after
  the complete response is written and flushed. Preserve accepted response
  accounting when delivery raises and do not emit a second audit record.
- Update the strict cost schema in `qea/qfbench_baseline.py` only as required to
  recognize the new terminal record and fail closed on it. Run the focused proxy
  and cost tests, then both complete test files.

## Task 3: Observe external supervisor exits

- Add schema-v2 tests to `tests/test_qfbench_rootless_sentinel.py` with a run
  directory and a separate exact supervisor directory. Prove a dead coordinator
  plus exit 1 freezes an incident; prove paths outside either root and symlinks
  remain rejected.
- Run the focused sentinel tests and observe RED.
- Extend `scripts/run_qfbench_rootless_sentinel.py` with a separately validated
  `supervisor_dir` for PID/exit/log/completion paths, retaining schema-v1 read
  compatibility.
- Re-run the sentinel tests and `tests/test_repair_supervisor.py`.

## Task 4: Keep the Mac controller and no-sleep assertion alive

- Add tests to `tests/test_qfbench_repair_controller.py` for a bounded poll-loop
  helper: it continues after return code 10, does not overlap because of the
  existing lock, and executes once when `--once` is supplied.
- Run the focused tests and observe RED.
- Add an explicit interval option and long-lived loop to
  `scripts/run_qfbench_repair_controller.py`; preserve current one-shot behavior
  behind `--once`. The launch command will be wrapped by
  `/usr/bin/caffeinate -i` rather than weakening Mac sleep settings globally.
- Re-run all controller and repair-supervisor tests.

## Task 5: Verify, document, commit, and push

- Run:
  `python3 -m pytest -q tests/test_qfbench_baseline.py tests/test_model_proxy.py tests/test_qfbench_rootless_sentinel.py tests/test_qfbench_repair_controller.py tests/test_repair_supervisor.py`.
- Run the broader rootless suite and then `python3 -m pytest -q tests`; run
  `git diff --check`.
- Update `docs/PROJECT_MEMORY.md` with this superseding decision. Stage only the
  exact new memory hunk plus owned source/tests/docs; leave all pre-existing
  dirty report/runbook/decision paths unstaged.
- Commit one or more scoped history-aligned commits and push the feature branch.
  Do not merge.

## Task 6: Deploy exact source and run bounded canaries

- Deploy the pushed exact SHA to `/home/julius/qea/deploy/releases/<sha>` on
  `bc`, refresh the immutable adapter/runtime identity, and leave the prior runs
  untouched.
- Run the no-model in-image adapter test and an offline verifier-only recovery
  canary using one of the four preserved complete worker artifacts.
- Force a disposable coordinator exit under schema-v2 sentinel configuration;
  require one frozen incident and a successful Mac controller dry run. Bind the
  real controller to the new run and start it under continuous `caffeinate`.
- Run one paid V4 Flash worker/verifier canary. Require model
  `deepseek/deepseek-v4-flash`, provider `deepseek`, fallbacks false, unique
  in-attempt requests, downstream-complete audit, official no-network verifier,
  firewall pass, canonical cost, and zero residual resources.

## Task 7: Launch and monitor the clean five-repetition run

- Materialize a new publish-once config for
  `qfbench-rootless-base-85x5-official-deepseek-v4-flash-noreplay-20260803` with
  five repetitions, no early calibration stop, and the previously accepted
  worker/verifier concurrency and resource lease.
- Launch from repetition 01. Immediately verify coordinator PID/command,
  checkpoint identity, supervisor paths, systemd sentinel timer, Mac controller
  run binding, continuous no-sleep assertion, and the first accepted provider
  record.
- Monitor scores, within-attempt replay, accepted-but-undelivered quarantine,
  provider drift, firewall findings, host capacity, exact resource residuals,
  and cost. Autonomous repair is limited to the allowlisted infrastructure
  categories and three cycles; all benchmark-integrity categories hard-stop.
- At completion, audit 425 scores and five complete repetitions, compute task and
  domain means with sample uncertainty, reconcile tokens/costs, stop the
  run-scoped controller/no-sleep assertion, and verify zero residual resources.
