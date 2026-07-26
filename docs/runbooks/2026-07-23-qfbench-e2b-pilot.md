# QFBench E2B Pilot Runbook

This runbook executes the pinned five-task pilot defined in `data/qfbench/MANIFEST.json`: three optimize tasks on every candidate and two lineage-separated promotion-held-out tasks at seed and final checkpoints only. The held-out tasks are `fx-forward-cross-rate` and `option-put-call-parity-forward-audit`. It does not constitute a full QFBench result. The first measured run is documented in the [2026-07-24 live-pilot decision](../decisions/2026-07-24-qfbench-live-e2b-pilot-and-dual-python-runtime.md).

The preregistered 30-task extension uses `data/qfbench/MANIFEST_30.json`. Its measured five-iteration run and the verifier-cache limitation are documented in the [2026-07-25 result decision](../decisions/2026-07-25-qfbench-30-task-five-iteration-result.md). Follow the additional preflight in Section 9 before reusing or extending that panel.

## 1. Prepare the environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[qfbench]"
set -a
source .env
set +a
```

`E2B_API_KEY` and a model credential (`LLM_API_KEY` or `OPENROUTER_API_KEY`) are required for evolution. Oracle parity uses E2B but no model credential.

## 2. Fetch the immutable benchmark

```bash
python scripts/fetch_qfbench.py /absolute/cache/qfbench-024921eb
```

The loader refuses any revision other than `024921eb507fcc0c4ffe3e0a96802724be1ae84a`, dirty tracked files, split lineage overlap, and all eight copy-oracle tasks.

The default is a five-task sparse checkout plus `docker/`; pass `--full` only for a full inventory audit. `sec-8k-event-alpha` is intentionally excluded because its official verifier at the pinned commit raises before emitting `reward.txt`.

## 3. Prepare the shared E2B base

Dry-run the official base build first:

```bash
python scripts/build_qfbench_e2b_base.py \
  --qfbench-root /absolute/cache/qfbench-024921eb \
  --output-dir output/qfbench-e2b-images/20260723_024921eb
```

After the account owner explicitly authorizes paid E2B publication, add `--publish`. Reuse the resulting template/build IDs; do not rebuild it for a run. The uploader stages a two-file context containing only `docker/sandbox.Dockerfile` and `docker/requirements-sandbox.txt`; task tests and solutions cannot enter the base build context. The manifest records both hashes, and the built image stores `/opt/qea/base-requirements.lock`. This freezes the published filesystem, but the upstream `python:3.11-slim` tag and requirement ranges remain mutable at rebuild time. A registry-visible `image@sha256:digest` remains the stronger rebuild-reproducibility route when registry access is available.

## 4. Generate and publish E2B task templates

Inspect the generated overlays first:

```bash
python scripts/build_qfbench_e2b_templates.py \
  --qfbench-root /absolute/cache/qfbench-024921eb \
  --base-manifest output/qfbench-e2b-images/20260723_024921eb/qfbench-base.image.json \
  --output-dir output/qfbench-e2b-images/20260723_024921eb
```

Then explicitly publish the ten worker/verifier templates:

```bash
python scripts/build_qfbench_e2b_templates.py \
  --qfbench-root /absolute/cache/qfbench-024921eb \
  --base-manifest output/qfbench-e2b-images/20260723_024921eb/qfbench-base.image.json \
  --output-dir output/qfbench-e2b-images/20260723_024921eb \
  --publish
```

Each `*.image.json` records an identity hash, upstream/context hashes, base template/build IDs, validated task operations, resource contract, and published task template/build IDs. Publication is idempotent: rerunning the command reuses an already published matching identity and rejects rebinding that manifest to changed inputs. Verifier templates pin `uv==0.9.5`, warm the exact upstream `uvx` dependency declaration using `/opt/qea/uv-cache`, `/opt/qea/uv-tools`, and `/opt/qea/uv-bin`, and save the resolved environment as `/opt/qea/verifier-requirements.lock`. With networking disabled, the trusted runner removes only the five recognized uv installer/bootstrap lines, records official/executed script hashes, and preserves the official test and reward body byte-for-byte otherwise.

Worker templates intentionally contain two runtimes. Official QFBench code remains on base Python 3.11; NexAU 0.3.9 runs with Python 3.12 from `/opt/qea/nexau-venv` and is pinned to VCS commit `35ee1861546db3cb280a6e17e38a74060d7c96c3`. Do not replace this with an unpinned VCS dependency or try to install NexAU into the task interpreter. The worker lock is `/opt/qea/nexau-requirements.lock` and must be copied into every attempt.

The adapter reads resources directly from each pinned `task.toml`; generated manifests and `run.py` reject mismatches:

| Task | Agent / verifier timeout | CPU | Memory | Build timeout |
|---|---:|---:|---:|---:|
| `historical-var-data-prep` | 1800 / 300 s | 4 | 8192 MB | 600 s |
| `momentum-backtest` | 1800 / 300 s | 2 | 4096 MB | 600 s |
| `evt-pot-var` | 1800 / 300 s | 2 | 4096 MB | 600 s |
| `fx-forward-cross-rate` | 2400 / 300 s | 4 | 8192 MB | 600 s |
| `option-put-call-parity-forward-audit` | 1800 / 300 s | 2 | 4096 MB | 600 s |

A local dependency-cache canary has verified all three distinct official `uvx` declarations with `UV_OFFLINE=1`; see the [canary report](../reports/2026-07-24-qfbench-offline-verifier-cache-canary.md). It does not replace the required E2B no-network parity run. The unpinned declarations currently resolve to NumPy 2.4.6 and pandas 3.0.5, so reuse published build IDs rather than rebuilding silently.

## 5. Establish E2B oracle parity

```bash
python scripts/run_qfbench_e2b_oracle.py \
  --qfbench-root /absolute/cache/qfbench-024921eb \
  --template-manifest-dir output/qfbench-e2b-images/20260723_024921eb \
  --approve-paid-e2b
```

Acceptance requires reward `1.0`, 12 passed/0 failed tests, canonical equality with the saved `historical-var-data-prep` oracle outputs, artifact hashes, and sandbox cleanup. Use `--allow-verifier-network` only for a documented dependency-baking canary.

Measured reference: run `qfbench-oracle-20260724T1025` met all acceptance criteria. Its evidence is under `results/qfbench-oracle/qfbench-oracle-20260724T1025/`.

## 6. Run evolution

Three iterations produce 16 task attempts; five produce 22. Each attempt uses a worker sandbox followed by an independent verifier sandbox.

```bash
python run.py --benchmark qfbench --executor e2b \
  --qfbench-root /absolute/cache/qfbench-024921eb \
  --qfbench-manifest data/qfbench/MANIFEST.json \
  --template-manifest-dir output/qfbench-e2b-images/20260723_024921eb \
  --run-id qfbench-pilot-3 --iters 3 --concurrency 3 --global-e2b-cap 12 \
  --results-dir results/qfbench --approve-external-run

python run.py --benchmark qfbench --executor e2b \
  --qfbench-root /absolute/cache/qfbench-024921eb \
  --qfbench-manifest data/qfbench/MANIFEST.json \
  --template-manifest-dir output/qfbench-e2b-images/20260723_024921eb \
  --run-id qfbench-pilot-5 --iters 5 --concurrency 3 --global-e2b-cap 12 \
  --results-dir results/qfbench --approve-external-run
```

The five-iteration command is an example only. It is a separate paid experiment and must not be run without explicit authorization. The five-task measured pilot showed an optimize ceiling and high two-task held-out variance, so expanding the preregistered task set is preferred to merely adding two iterations.

Resume an interrupted run with the identical arguments plus `--resume`. Completed task attempts, official scores, and completed proposals are reused; model calls are not resampled.

## 7. Reap exact orphan IDs

Every created sandbox is immediately recorded in a role-specific `*-sandbox-lifecycle.json`, then marked cleaned after termination. After an interrupted coordinator, preview cleanup from one run directory:

```bash
python scripts/reap_qfbench_e2b.py \
  --results-dir results/qfbench/qfbench-pilot-3
```

Review the exact IDs, then add `--apply`. The reaper never performs broad account cleanup, refuses duplicate IDs, and atomically records `killed`, `already_absent`, or `failed`. Run `--resume` only after cleanup review.

## 8. Inspect evidence

Review `resume.json`, `result.json`, `evaluations/`, content-addressed `attempts/`, every lifecycle manifest, and each verifier dependency lock under the run directory or published template. Report optimize task rewards and domain macro separately from seed-to-final held-out change, plus wall time, model token/cost data when the provider exposes it, E2B failures, and cleanup status. Never feed held-out scores, raw assertions, expected values, tests, solutions, or trusted verifier logs to the proposer.

The measured manifests are under `output/qfbench-e2b-images/20260724T095950+0800_024921eb/`; the measured pilot is `results/qfbench/qfbench-pilot-3-20260724T102755/`. It completed exactly 16 official scores and all 32 worker/verifier lifecycle records are cleaned. If token, provider cost, or E2B billing metadata is absent, report it as unavailable rather than estimating it from wall time.

## 9. Run the 30-task extension

The frozen split contains 20 optimize tasks, 10 seed/final-only held-out tasks, and six domains. Five iterations schedule exactly 140 official score records:

```text
20 optimize seed + 10 held-out seed + (5 × 20 candidates) + 10 held-out final
```

Before any paid publication, verify every official `uvx` script produced a warm command. `option-put-call-parity-forward-audit` is the only direct-Python exception in this panel:

```bash
python -m pytest -q tests/test_qfbench_images.py

for manifest in output/qfbench-e2b-images/<new-dir>/*.verifier.image.json; do
  jq -e '
    if .task_id == "option-put-call-parity-forward-audit"
    then .verifier_uvx_warm_command == null
    else (.verifier_uvx_warm_command | type == "string" and length > 0)
    end
  ' "$manifest"
done
```

Fail the publication if this check fails. The 2026-07-25 directory contains three verifier identities generated before `if uvx ...` was recognized; do **not** reuse the verifier templates for `delta-hedging-pnl-simulation`, `swap-curve-bootstrap-ois`, or `form4-cross-sectional-sale-pressure`.

The measured command was:

```bash
LLM_MODEL=deepseek/deepseek-v4-pro python run.py \
  --benchmark qfbench --executor e2b \
  --qfbench-root /absolute/cache/qfbench-024921eb \
  --qfbench-manifest data/qfbench/MANIFEST_30.json \
  --template-manifest-dir output/qfbench-e2b-images/20260725_30x5_024921eb \
  --run-id qfbench-30x5-20260725 --iters 5 \
  --concurrency 8 --global-e2b-cap 12 \
  --results-dir results/qfbench --approve-external-run
```

Resume only with identical arguments plus `--resume`. Run exact-ID reaper dry-run before resuming after a coordinator/API failure and again after completion. A complete run must have `phase="complete"`, five records, 140 unique attempt directories, 140 `completed-score.json` files, zero active leases, and zero pending reaper IDs. The verifier count may be below 140 when a worker timeout is deliberately normalized to zero before verifier creation.

The measured run completed these structural checks, but 14 scores from the three invalid verifier templates are contaminated by offline dependency-cache failure. Do not describe 140 score files as 140 authoritative task evaluations; repair them in a new, explicitly authorized superseding run.
