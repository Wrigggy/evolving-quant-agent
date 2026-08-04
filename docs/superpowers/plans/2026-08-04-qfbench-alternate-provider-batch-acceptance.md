# QFBench Alternate-Provider Batch Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an infrastructure-only twelve-worker provider-batch canary without weakening the official DeepSeek batch gate, then run it once on Cloudflare.

**Architecture:** Extend the existing full-harness smoke CLI with a separate paid mode that parameterizes only the required provider and result claim metadata. Reuse the exact task panel, evaluator, route rewrite, offline verifier, cost audit, lifecycle audit, and cleanup path; keep formal baseline scheduling and its official provider contract unchanged.

**Tech Stack:** Python 3.12, argparse, pytest, rootless Docker, OpenRouter provider routing, systemd user services.

## Global Constraints

- Benchmark commit remains `024921eb507fcc0c4ffe3e0a96802724be1ae84a`.
- Model remains `deepseek/deepseek-v4-flash`; only the infrastructure canary provider may be `cloudflare`.
- Formal scoring remains provider `deepseek` with fallbacks disabled.
- Worker/verifier concurrency is `12/3` with a two-second worker launch interval.
- Official tests and reference data remain in independent no-network verifiers.
- Sent requests are never replayed within the same attempt; cleanup is exact-ID only.
- Do not stage or alter pre-existing user-owned dirty files.

---

### Task 1: Add a distinct alternate-provider batch contract

**Files:**
- Modify: `tests/test_qfbench_full_harness_scripts.py`
- Modify: `scripts/smoke_qfbench_full_harness.py`

**Interfaces:**
- Consumes: existing `select_paid_baseline_batch_tasks(...)`, `run_paid_baseline_batch(...)`, and rootless CLI path.
- Produces: CLI mode `paid-provider-batch`, argument `--acceptance-provider`, provider-aware selection, and explicit `formal_scoring_eligible` result metadata.

- [ ] **Step 1: Write failing contract tests**

Add tests that call the real selection/CLI functions and prove:

```python
selected = select_paid_baseline_batch_tasks(
    snapshot,
    config=cloudflare_config,
    executor="rootless-docker",
    expected_provider="cloudflare",
    formal_scoring_eligible=False,
)
assert len(selected) == 12

with pytest.raises(ValueError, match="official provider"):
    select_paid_baseline_batch_tasks(
        snapshot,
        config=cloudflare_config,
        executor="rootless-docker",
    )
```

Also assert that `paid-provider-batch` requires a non-DeepSeek
`--acceptance-provider`, builds without an evolver, and emits
`formal_scoring_eligible is False` plus the infrastructure-only claim.

- [ ] **Step 2: Run the focused tests and observe RED**

Run:

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest tests/test_qfbench_full_harness_scripts.py -q
```

Expected: failures because the new mode, argument, function parameters, and
result metadata do not exist.

- [ ] **Step 3: Implement the minimal provider-aware mode**

In `scripts/smoke_qfbench_full_harness.py`:

- keep `paid-baseline-batch` defaulted to provider `deepseek` and formal gate
  semantics;
- add `paid-provider-batch` and `--acceptance-provider`;
- require the alternate provider to be nonempty, not `deepseek`, and equal the
  loaded config's `required_provider`;
- treat both batch modes as paid, baseline-snapshot, rootless-only, and
  `include_evolver=False`;
- pass `mode`, `expected_provider`, and `formal_scoring_eligible` into the
  shared selector/runner;
- persist an infrastructure-only claim boundary when formal eligibility is
  false.

- [ ] **Step 4: Run focused tests and observe GREEN**

Run:

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest tests/test_qfbench_full_harness_scripts.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Run the scheduler and isolation regression panel**

Run:

```bash
/Users/kevinwu/Coding/evolving-quant-agent/.venv-nexau/bin/python -m pytest \
  tests/test_qfbench_full_harness_scripts.py \
  tests/test_rootless_full_harness.py \
  tests/test_model_proxy.py \
  tests/test_sandbox_proxy.py \
  tests/test_qfbench_baseline.py -q
```

Expected: all runnable tests pass; sandbox-restricted loopback failures, if
encountered, are rerun outside the sandbox exactly as in the preceding verified
commit.

- [ ] **Step 6: Commit the implementation**

```bash
git add scripts/smoke_qfbench_full_harness.py \
  tests/test_qfbench_full_harness_scripts.py
git commit -m "feat(canary): add alternate-provider QFBench batch gate"
```

### Task 2: Deploy and run the Cloudflare twelve-worker acceptance

**Files:**
- Create remotely: `/home/julius/qea/runtime/configs/qfbench-base85-v4-flash-cloudflare-alternate-provider-batch.json`
- Create remotely: `/home/julius/qea/runtime/canaries/qfbench-v4-flash-cloudflare-batch-20260804-r1/`
- Create: `docs/decisions/2026-08-04-qfbench-alternate-provider-batch-result.md`

**Interfaces:**
- Consumes: the clean implementation commit, existing immutable image set, owner-only token file, and pinned QFBench source.
- Produces: one publish-once live acceptance artifact and a dated evidence decision.

- [ ] **Step 1: Deploy the exact commit and create an owner-only config**

Push the feature branch to the existing deploy-only remote, materialize a clean
detached release, and derive the config from the current epoch-two schema-4
config with only `required_provider` changed to `cloudflare`. Write it mode 600,
record its SHA-256, and confirm model, concurrency, verifier concurrency, launch
interval, roots, and token path are unchanged.

- [ ] **Step 2: Run zero-spend preflight**

Confirm the run ID does not exist, the official paid-gate timer remains paused,
the configured provider is `cloudflare`, the public endpoint is healthy, and
the global managed container/network inventory is empty.

- [ ] **Step 3: Launch one systemd-owned paid batch**

Run `scripts/smoke_qfbench_full_harness.py` with:

```text
--executor rootless-docker
--mode paid-provider-batch
--acceptance-provider cloudflare
--approve-external-run
```

Use the pinned manifest, source, image set, owner-only config, and publish-once
run ID. Do not automatically replay a failure.

- [ ] **Step 4: Audit acceptance or freeze evidence**

Require the result to show 12 tasks, worker overlap 12, provider `cloudflare`,
model V4 Flash, complete request/cost accounting, networkless verifier
lifecycles, no within-attempt replay, `formal_scoring_eligible=false`, and zero
managed residual resources. If any condition fails, preserve the run and stop.

- [ ] **Step 5: Record and commit the dated result**

Write the exact commit/config/run identities, live provider evidence, task and
request counts, overlap, scores as diagnostic-only, tokens/cost, cleanup, and
the formal DeepSeek boundary to the decision file. Commit only that file.

- [ ] **Step 6: Re-enable formal readiness monitoring without launching formal work**

Keep the zero-call readiness timer active. Re-enable the publish-once official
paid gate only if its old run IDs remain absent and it cannot race with another
manual canary. Formal 85x5 starts only after a successful official one-task and
official twelve-worker gate.
