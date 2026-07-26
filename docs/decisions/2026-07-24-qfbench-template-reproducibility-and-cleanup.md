# Decision Record: QFBench Template Reproducibility and Cleanup

> Date: 2026-07-24
> Status: accepted for implementation; E2B validation pending explicit paid-run authorization
> Supersedes: only the template reproducibility and orphan-cleanup details of the [2026-07-23 implementation decision](2026-07-23-qfbench-e2b-template-and-pilot-adjustments.md)

## Decision

Keep the registered five-task split, official rewards, local coordinator, in-E2B NexAU worker, and independent no-network verifier unchanged. Harden the E2B boundary as follows:

1. Parse `agent_timeout_sec`, `verifier_timeout_sec`, `build_timeout_sec`, CPU, and memory directly from every pinned `task.toml`. Record them in task manifests and reject runtime manifest mismatches.
2. Treat a base or task manifest as publish-once. Its identity covers the benchmark commit, context hashes, base identity, validated operations, role dependencies, verifier dependency declaration, and resources. Reuse a matching published identity; reject rebinding changed inputs to its template/build IDs.
3. Pin verifier cache locations to `/opt/qea/uv-cache`, `/opt/qea/uv-tools`, and `/opt/qea/uv-bin`. Warm each exact official `uvx` declaration and save its actual installed environment to `/opt/qea/verifier-requirements.lock`; the direct-Python option verifier writes the same path with `pip freeze`. Preserve the base image's separate `/opt/qea/base-requirements.lock` as well.
4. Persist a sandbox lifecycle manifest immediately after each worker, oracle, or verifier sandbox is created. Normal termination finalizes it; interrupted runs are handled only by an exact-ID reaper that is dry-run by default and refuses duplicate IDs.

These controls do not alter QFBench test code, assertions, expected values, or reward computation.

## Evidence Boundary

The extended local environment passes `128 passed, 1 skipped`. Both registry-digest and E2B-base dry paths generate ten task-role manifests with the pinned resources and identity hashes. All five verifier manifests generate a dependency lock, and runtime treats a missing lock as an infrastructure error. A local `UV_OFFLINE=1` canary resolves all three distinct official `uvx` declarations and exercises the generated dependency-lock command. This is local engineering evidence only: no E2B template has been published, no Linux no-network parity has been measured, and no sandbox has yet been force-killed and resumed in E2B.

The official unpinned declaration used by `historical-var-data-prep` and `momentum-backtest` resolved locally to NumPy 2.4.6 and pandas 3.0.5 on this date. A published build ID plus its in-image lock is authoritative for a run; rebuilding later without review is not equivalent.
