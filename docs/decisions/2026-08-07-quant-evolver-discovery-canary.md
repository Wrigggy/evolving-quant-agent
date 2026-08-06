# 2026-08-07 — Quant Evolver Discovery Canary

Status: **implemented locally; paid rootless canary pending**.

This decision extends the full-harness exposure work in
[2026-08-05 evolver exposure and scheduler capacity](2026-08-05-evolver-exposure-and-scheduler-capacity.md)
and preserves the removal of the forced two-rejection component switch in
[2026-08-06 component-switch prior v2.1](2026-08-06-evolver-component-switch-prior-v2-1.md).
It does not reinstate a fixed component schedule.

## Decision

Treat a strong, tool-using evolver as the engineering baseline rather than as an
experimental optimization. For the immediate exploratory canary:

1. run the evolver with GPT-5.4, `xhigh` reasoning, a 200-turn cap, and the
   existing 200k context;
2. give it quant-specific evidence navigation and candidate component/binding
   inspection, not unrestricted host shell or network access;
3. require an evidence-backed discovery contract before candidate writes;
4. use a deterministic debugger only as an evidence index and anomaly graph;
5. compare raw and indexed evidence arms once each on the same post-A3 state;
6. evaluate admitted candidates separately using the unchanged pinned DeepSeek
   V4 Flash 0731 worker/provider route and official isolated verifier;
7. record the result as exploratory; do not add it to the paper without a later
   explicit reporting decision.

## Why proposal and scoring are separate runs

The current rootless full-harness config has one model route shared by evolver
and worker. A production dual-route change is reasonable but unnecessary for
this mechanism canary. The proposal-only discovery runner uses a GPT-5.4/OpenAI
route, creates and admits the candidate, and makes no worker call. A second
component-pilot run uses the existing DeepSeek route to score the common A3
backbone and both proposals. Exact run identities and costs remain separate and
auditable.

This is an exploratory engineering shortcut, not the final formal evolution
architecture. If the mechanism works and is adopted for a new formal evolution,
the coordinator must gain explicit role-specific model-route identities rather
than relying on two manually linked runs.

## Implemented surfaces

- `qea/evolve_agent_full/agent.yaml`: 200-turn cap and xhigh reasoning request.
- `qea/evolve_agent_full/systemprompt.md`: discovery-first quant loop with no
  prescribed component.
- `qea/evolve_agent_full/tools/guarded_workspace.py`: evidence map, trace slice,
  evidence comparison, candidate graph/validation, and write unlock.
- `qea/evolver_discovery.py`: deterministic discovery-process measurements.
- `scripts/build_qfbench_discovery_evidence.py`: matched raw/indexed post-A3
  evidence construction without held-out or private verifier material.
- `scripts/run_qfbench_discovery_pilot.py`: proposal-only rootless canary.

## Safety boundary

The evidence contract still rejects private evaluator path components,
secret-like files, symlinks, and non-UTF-8 payloads. The post-A3 builder copies
only sanitized public scalar summaries, worker traces/finals/process summaries,
candidate history, and candidate diffs. It removes trusted verifier log paths
from public score records and copies no CTRF, official tests, reference inputs,
solutions, credentials, or held-out feedback.

The evolver retains no unrestricted shell or network. Candidate admission,
protected worker model/resource/security fields, official rewards, and verifier
isolation are unchanged.

## Interpretation boundary

Unit tests establish that the discovery interface is bounded, audited, and
fail-closed; that writes require previously inspected exact evidence; that the
raw/indexed evidence arms share identical raw files; and that process metrics do
not count a directory listing as grounded evidence use. They do not establish
that the model's diagnosis is correct.

The paid canary will answer only whether the mechanism works well enough in this
concrete post-A3 case to justify further engineering. It is not sized for a
generalization or statistical-significance claim.

