# QFBench Official-Provider Rerun Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce the first-party DeepSeek provider in the trusted model proxy and restart the frozen 85-task baseline from repetition one under a fresh, auditable run identity.

**Architecture:** Add a host-controlled `required_provider` route policy that rejects worker routing input, injects OpenRouter `only` plus disabled fallbacks, and binds the forwarded bytes and all public/runtime identities. Preserve schema-v1 diagnostic compatibility, require schema v2 for the new formal config, rebuild only the proxy image, then gate a fresh formal repetition through the existing verifier firewall and cleanup audits.

**Tech Stack:** Python 3.10+, pytest, OpenRouter Chat Completions provider routing, QEA rootless Docker backend, JSON/JSONL manifests, SSH to `bc`.

## Global Constraints

- Exact model `deepseek/deepseek-v4-pro`; exact first-party provider slug `deepseek`; `allow_fallbacks=false`.
- Worker/evolver requests cannot supply or override `provider`.
- QFBench commit remains `024921eb507fcc0c4ffe3e0a96802724be1ae84a`; worker remains `qea/worker_gdpval_weak`; task panel remains 77 primary plus eight diagnostic.
- Formal rerun uses a new run ID, no evolver, worker concurrency 4, verifier concurrency 3, and the existing repetition-one gates and USD 60 cap.
- Never expose official tests, references, solutions, raw verifier output, or credentials to worker/evolver containers.
- Preserve existing dirty memory/report/runbook files; do not merge.

---

### Task 1: Trusted Proxy Provider Lock

**Files:**
- Modify: `tests/test_model_proxy.py`
- Modify: `qea/model_proxy.py`
- Modify: `scripts/run_qea_model_proxy.py`

- [ ] **Step 1: Write failing real-behavior tests**

Add tests proving `required_provider="deepseek"` injects exactly
`{"only":["deepseek"],"allow_fallbacks":false}`, rewrites `Content-Length`,
computes the audit request identity over forwarded bytes, rejects any inbound
`provider` before upstream transmission, and rejects unsafe provider slugs.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python3 -m pytest -q tests/test_model_proxy.py -k 'required_provider or provider_routing'`

Expected: FAIL because `ModelProxyConfig` and the CLI do not accept or enforce
`required_provider`.

- [ ] **Step 3: Implement the minimal fail-closed policy**

Validate one bounded provider slug, propagate it through the plan and policy,
reject caller-owned routing, inject the immutable provider object, and use the
forwarded body for length, identity, replay denial, and upstream transmission.
Keep byte-preserving behavior when no provider is required.

- [ ] **Step 4: Run all model-proxy tests and verify GREEN**

Run: `python3 -m pytest -q tests/test_model_proxy.py`

Expected: PASS with loopback access.

### Task 2: Full-Harness and Image Identity Propagation

**Files:**
- Modify: `tests/test_sandbox_proxy.py`
- Modify: `tests/test_rootless_images.py`
- Modify: `tests/test_rootless_full_harness.py`
- Modify: `qea/executors/sandbox_proxy.py`
- Modify: `qea/rootless_images.py`
- Modify: `qea/rootless_full_harness.py`

- [ ] **Step 1: Write failing propagation tests**

Assert the proxy config/plan and entrypoint carry `required_provider`, schema-v2
full-harness config requires it, invalid slugs fail before backend work, and a
provider change alters route/runtime identity without altering scheduler
identity.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python3 -m pytest -q tests/test_sandbox_proxy.py tests/test_rootless_images.py tests/test_rootless_full_harness.py -k 'provider or identity or config'`

Expected: FAIL because the policy is not yet propagated.

- [ ] **Step 3: Implement schema-v2 propagation**

Thread the normalized value into every per-attempt proxy plan and the proxy
image CLI. Accept historical schema v1 without a pin; require the extra field
for schema v2. Include the provider-only/no-fallback object in model-route and
runtime identity payloads.

- [ ] **Step 4: Run focused and broader suites**

Run:

```bash
python3 -m pytest -q \
  tests/test_model_proxy.py tests/test_sandbox_proxy.py \
  tests/test_rootless_images.py tests/test_rootless_full_harness.py
python3 -m pytest -q tests
```

Expected: PASS, apart from documented optional skips.

### Task 3: Build, Canary, and Fresh Repetition One

**Remote artifacts:**
- Create: `/home/julius/qea/runtime/configs/qfbench-base85-official-deepseek-20260801.json`
- Create: `/home/julius/qea/runtime/image-sets/024921eb-base85-official-deepseek.json`
- Create: `/home/julius/qea/runtime/contracts/qfbench-official-deepseek-*-20260801.json`
- Create: `/home/julius/qea/runs/qfbench-route-official-deepseek-credit3-1x-20260801`
- Create: `/home/julius/qea/runs/qfbench-rootless-base-85x5-official-deepseek-20260801`

- [ ] **Step 1: Commit and push the verified implementation**

Stage only the new decision/spec/plan plus named code and test files. Commit
with `feat(proxy): enforce official provider routing` and push the feature
branch without merging.

- [ ] **Step 2: Update the trusted remote worktree and build only the proxy image**

Verify the remote tree is tracked-clean and exact-HEAD, fast-forward it, build
the proxy image with the pinned upstream Python base, and assemble a new 85-task
image-set manifest reusing unchanged role images. Record all image IDs and
manifest SHA-256 values.

- [ ] **Step 3: Run a fresh three-task first-party canary**

Use a new run ID and concurrency 1/1. Accept only complete HTTP/provider audit,
strict provider policy in every public proxy config, three official scores,
zero firewall findings, and zero run-owned residual containers/networks.

- [ ] **Step 4: Run formal repetition one from zero**

Use the new five-repetition run ID and formal concurrency 4/3. Do not import or
resume any default-route or Nitro attempt. Stop at the repetition-one audit
boundary.

- [ ] **Step 5: Apply the preregistered continuation gates**

Require 85/85 official scores, complete successful-request usage/cost, zero
evaluator-firewall findings, zero exact-ID residuals, and projected five-rep
provider cost at most USD 60. If accepted, resume repetitions two through five;
otherwise preserve evidence and stop without ambiguous replay.

- [ ] **Step 6: Record run IDs, digests, cost, scores, and gate result**

Create a new dated report/decision addendum rather than editing historical
results. Leave `docs/PROJECT_MEMORY.md` untouched while its existing user
changes are uncommitted, and report that pending canonical-memory update.
