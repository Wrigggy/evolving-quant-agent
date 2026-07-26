# Decision Record: QFBench Verifier Template Repair

> Date: 2026-07-26
> Status: accepted for future runs; historical scores remain provisional
> Supersedes: the three invalid verifier-template IDs identified in the 2026-07-25 result

## Decision

Use the corrected verifier templates below for future runs at QFBench commit `024921eb507fcc0c4ffe3e0a96802724be1ae84a`. Preserve the 2026-07-25 templates, manifests, and run as historical evidence. The 14 contaminated scores have not been repaired and require separately authorized scoring attempts before any superseding performance result.

The user authorized three paid template builds and one verifier-only canary per task, then separately authorized three verifier-only reruns after the first canary exposed an empty-artifact harness bug. No worker, model call, or official solution was used.

| Task | Old template / build | Corrected template / build |
| --- | --- | --- |
| `delta-hedging-pnl-simulation` | `eyssre7yc5lwk8jj9nj3` / `544dc776-cf03-4de7-a39b-167bf9604f3b` | `37im0to9u8zzz8l92pru` / `54e1451f-b320-4b0a-821a-e469e30b7ad8` |
| `swap-curve-bootstrap-ois` | `1u7y6c2vo7yt33b80vr7` / `59ac2d96-0909-4303-8c18-92847e75f0e0` | `1p6n6i63xufgch89p5ut` / `e0590c8e-e201-43d9-8661-9ea12eb506ed` |
| `form4-cross-sectional-sale-pressure` | `e4qt5a74zxs53h3hb44u` / `169e6b2c-0e38-4a56-b445-e4d0feb0e9c3` | `3kwmh06wjw1fthooc6iv` / `45e589b9-ccd4-4bf6-ad68-02e5d4401c6d` |

Exact old/new identities and publication fields are in `results/qfbench_verifier_canary/verifier-cache-20260726-rerun1/template-comparison.json`.

## Cached Official Environments

The build warmed and locked the declarations extracted from the official `if uvx` commands:

```text
delta warm: uvx -p 3.11 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 -w numpy==1.26.4 -w pandas==2.2.3 pytest --version
delta lock: uvx -p 3.11 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 -w numpy==1.26.4 -w pandas==2.2.3 python -c 'import importlib.metadata as m; print("\n".join(sorted(f"{d.metadata.get('Name', 'UNKNOWN')}=={d.version}" for d in m.distributions())))' > /opt/qea/verifier-requirements.lock

swap warm: uvx -p 3.11 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 -w numpy==2.2.6 pytest --version
swap lock: uvx -p 3.11 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 -w numpy==2.2.6 python -c 'import importlib.metadata as m; print("\n".join(sorted(f"{d.metadata.get('Name', 'UNKNOWN')}=={d.version}" for d in m.distributions())))' > /opt/qea/verifier-requirements.lock

form4 warm: uvx -p 3.11 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 -w numpy -w pandas pytest --version
form4 lock: uvx -p 3.11 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 -w numpy -w pandas python -c 'import importlib.metadata as m; print("\n".join(sorted(f"{d.metadata.get('Name', 'UNKNOWN')}=={d.version}" for d in m.distributions())))' > /opt/qea/verifier-requirements.lock
```

## Live Evidence

The first run, `verifier-cache-20260726`, launched and cleaned all three verifier sandboxes and read their dependency locks, but stopped before pytest because an empty archive had no `artifacts/` member. The harness now creates `/qea_verify/artifacts` before copying outputs; a regression test covers this case.

The authorized rerun `verifier-cache-20260726-rerun1` passed the cache canary:

| Task | Passed | Failed | Lock hash | Cleaned |
| --- | ---: | ---: | --- | --- |
| `delta-hedging-pnl-simulation` | 0 | 27 | `f5f71a108ad5379b4d51624d86a2efbbd469a6eb253b28a390c62cb2b14490df` | yes |
| `swap-curve-bootstrap-ois` | 0 | 19 | `209c72eecae6ecaa586f800e9109def0156c78abb8bfba65982e17978df97477` | yes |
| `form4-cross-sectional-sale-pressure` | 0 | 7 | `a353446ff3a2887edc934697633694b15043647b86d7ceef42050947ca0f7897` | yes |

All 53 official tests executed offline. Their expected missing-output failures and reward `0` prove execution, not model quality. The persisted locks match the harness hashes; official/executed script hashes are present; no dependency-resolution marker occurred. The run records `model_calls=0`, `worker_sandboxes=0`, three verifier lifecycles, no worker/oracle lifecycle, and no solution member. Exact-ID cleanup reports `pending_ids=[]`.

E2B billing totals were not emitted and remain **not measured**. Model cost is zero by construction because no model provider was called. Evolve-agent exposure and changes remain deferred until verifier work is complete.
