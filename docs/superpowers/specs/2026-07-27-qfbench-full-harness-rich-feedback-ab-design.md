# QFBench Full-Harness Rich-Feedback A/B Design

> Date: 2026-07-27
> Status: automatically approved for implementation, paid canaries, and paid full runs
> Benchmark commit: `024921eb507fcc0c4ffe3e0a96802724be1ae84a`

## Objective

Test whether increasing the evidence visible to the evolve agent improves its ability to evolve the NexAU worker on the QFBench optimize tasks. Both arms use the same full-worker mutation surface, task panel, model, seed worker, verifier templates, five-iteration schedule, acceptance rule, and execution budgets. The experimental variable is the proposer-facing feedback contract.

The primary claim is optimize-task adaptation, not unseen-task generalization. Seed/final held-out scoring is retained for longitudinal compatibility and reported as a secondary, non-adaptive outcome. The exact exposure boundary, real-world equivalence, and later held-out protocol remain follow-up discussion topics; they do not block this experiment.

## Fixed Longitudinal Panel and Run Scale

Use `data/qfbench/MANIFEST_30.json` without changing task identities or roles: 20 optimize tasks, 10 seed/final-only held-out tasks, six domains, disjoint lineages, and the pinned public snapshot. Use five outer iterations. Each arm therefore creates exactly 140 scheduled official score records:

```text
20 optimize seed
+ 10 held-out seed
+ 5 x 20 optimize candidates
+ 10 held-out final
= 140 official scoring attempts per arm
```

Run two independent arms, for 280 official scoring attempts total. Each attempt contains one worker sandbox and, unless the worker fails before producing artifacts, one independent verifier sandbox; the preregistered maximum is 560 worker/verifier sandbox lifecycles. The experiment also permits ten evolver model calls/sandboxes, admission canaries, retries classified as infrastructure recovery, and exact-ID reaping/resume.

Use `deepseek/deepseek-v4-pro`, `qea/worker_gdpval_weak`, concurrency 8, global E2B cap 12, `noise_floor=0.02`, and `max_domain_regression=0.0`, matching the 2026-07-25 run. Use the corrected verifier template IDs recorded on 2026-07-26. Do not reuse the three invalid template IDs.

The historical `qfbench-30x5-20260725` run is a contextual third column because it used the same 30-task/5-iteration schedule. It is not the causal control: its mutation surface was effectively prompt-only, and 14 attempts contain known offline verifier-cache zeros. Preserve it unchanged and label all historical comparisons provisional.

## Experimental Arms

### Control: full harness with compressed feedback

The Control arm uses the new full-harness editor but preserves the current compressed feedback semantics. At each proposal it receives:

- current optimize domain-macro and task rewards;
- allowlisted coarse diagnostic tags and pass/fail counts;
- current incumbent manifest and editable worker files;
- prior candidate diffs, keep/rollback decisions, and aggregate domain deltas;
- the answer-free NexAU harness reference.

It does not receive task instructions, task data, raw worker traces, deliverable contents, public criterion text, or criterion-level evaluation evidence through the evolution corpus. The worker still receives the normal public task package during each evaluation.

### Treatment: full harness with rich optimize evidence

The Rich arm receives everything in Control plus, for optimize tasks only:

- complete public `instruction.md`;
- all public task/environment files available to the worker;
- an instruction-derived public rubric with stable criterion IDs;
- complete worker-observable `raw_trace.jsonl`;
- worker final text, process summary, command outcome, and artifact manifest;
- the worker-produced artifacts themselves;
- official scalar reward, test pass/fail counts, and public criterion-level status/evidence;
- all earlier edits and the per-task outcomes of kept and rejected candidates.

“Complete trajectory” means the complete worker-observable trajectory. It excludes the verifier's private trajectory, raw test names/messages/assertions, official solution, verifier-only reference data and exact expected values, credentials, and held-out outcomes.

## Public Rubric and Criterion Feedback

QFBench does not provide a clean standalone public rubric for every task. Create a preregistered `data/qfbench/FEEDBACK_30.json` for the 20 optimize tasks. Each entry contains only requirements recoverable from the public instruction/environment, with stable criterion IDs and public text. A trusted mapping may associate private official test cases with those IDs, but the mapping's private test identities and raw assertions never enter the evolution corpus.

The verifier-facing mapper may emit only:

```json
{
  "criterion_id": "required_output_structure",
  "status": "failed",
  "passed_checks": 1,
  "failed_checks": 2,
  "public_evidence": {
    "kind": "schema_or_structure_mismatch",
    "message": "The requested output structure was not fully satisfied."
  }
}
```

The schema forbids exact expected values, raw actual-versus-expected pairs, test source paths, raw test names, assertion text, solution-derived steps, and unbounded verifier logs. Every emitted field records its provenance (`public_task`, `worker_observation`, `official_scalar`, or `sanitized_verifier`). A canary string placed in private test/reference material must never appear in the proposer message, evidence bundle, candidate, or evolve trace.

## Evidence Corpus and Context Management

Materialize Rich evidence on disk rather than inlining it into one prompt:

```text
evidence/
  contract.json
  tasks/<task-id>/
    instruction.md
    public_rubric.json
    environment/
    attempts/<checkpoint>/
      worker_trace.jsonl
      worker_final.txt
      process_summary.json
      artifact_manifest.json
      artifacts/
      public_evaluation.json
  history/
    iterations.json
    score_matrix.json
    edits/<iteration>.diff
```

The evolve prompt contains the objective, evidence index, current worker path, mutation policy, and required final prediction. Guarded `list`, `read`, `search`, and evidence-query tools provide progressive disclosure. Record every evidence file the evolver reads so the report can distinguish availability from actual use. Large public datasets and binary artifacts remain available as files and are not inlined into the model context.

The corpus contains optimize attempts completed before the current proposal, including rejected candidate behavior. It never contains held-out task IDs, task packages, scores, traces, artifacts, or deltas.

## Full-Harness Mutation Surface

The evolve agent edits a complete snapshot of the incumbent worker. It may change:

- `systemprompt.md`;
- `tool_descriptions/**/*.yaml`;
- `tools/**/*.py` and package initializers;
- the `agent.yaml` tool list and local bindings;
- declared worker-local middleware, skills, validator, memory, and routing text/Python files introduced under approved directories.

For A/B comparability, protected configuration remains fixed in both arms: model/provider/base URL/API-key placeholders, tracer, context/token/turn budgets, temperature, stream/API type, benchmark paths, verifier configuration, E2B network/security configuration, and external credentials. The full harness therefore means prompt, tools, bindings, and worker-control components, not the ability to buy more tokens or weaken the experiment.

Persistent evolver notes live outside the worker snapshot and are never bundled into worker executions. No task-specific answer, reference number, public-data row, or copied deliverable may be embedded into a candidate worker.

## Candidate Admission and Dual Runtime

No candidate reaches paid task evaluation until deterministic admission succeeds:

1. Build a complete manifest and digest of every candidate file.
2. Reject symlinks, absolute/traversal paths, secret-like files, unknown binaries, extensionless executables, file-count/byte-limit violations, and files outside the mutation allowlist.
3. Parse YAML and enforce protected-field equality with the seed contract.
4. Compile all Python and validate every local tool description/binding/function signature.
5. Insert the worker root into `sys.path` before NexAU loads `agent.yaml`.
6. Construct `AgentConfig` in the exact pinned NexAU Python 3.12 environment.
7. Run local-tool imports and smoke calls with enforced wall-clock timeouts and no verifier material.
8. Reject undeclared third-party dependencies not present in the pinned NexAU lock.

The official task runtime remains Python 3.11 and NexAU remains Python 3.12. Worker-local tool modules must import in Python 3.12. Task-specific libraries may be reached only through a bounded subprocess bridge to the task Python 3.11 runtime, using an argv list, fixed cwd, captured output limits, and enforced timeout. Do not collapse the runtimes or dynamically install packages.

Admission failure produces a zero-cost rollback for task scoring, records the exact reason, and allows the next outer iteration to continue. It is not converted into an official benchmark zero because no official scoring attempt occurred.

## Evolver Isolation

Run the evolver only in E2B; disable the old LocalSandbox path for this experiment. The evolver template follows the current worker security posture:

- `secure=True`;
- deny-by-default egress, allowing only the configured model-provider host;
- E2B header-injected model authorization with only a placeholder in process env;
- no `E2B_API_KEY`, unrestricted provider credential, official tests, solutions, reference data, or held-out inputs;
- candidate writes confined to `/qea/candidate`;
- evidence mounted read-only by guarded tool policy;
- no generic absolute-path file tools and no unrestricted shell tool.

Provide guarded candidate file tools plus fixed validation commands. After the evolve process exits, download only the admitted candidate manifest, never an unconstrained VM filesystem tree.

## Checkpoint, Failure, and Resume Semantics

Use separate collision-free run IDs, for example:

```text
qfbench-30x5-full-control-20260727-<suffix>
qfbench-30x5-full-rich-20260727-<suffix>
```

Checkpoint arm identity, feedback-contract digest, public-rubric digest, task manifest digest, template/build IDs, model configuration, seed-worker digest, current phase, current incumbent, candidate admission record, proposal trace URI, completed attempt IDs, score summaries, costs, and sandbox lifecycles. Resume must reject any mismatch in these identities.

Infrastructure failures do not become ordinary official zeros. Record and safely retry E2B creation failures, provider transport errors, missing verifier locks, offline dependency-resolution failures, corrupt bundles, and lost lifecycle records. Worker behavioral timeout remains an official zero under the existing contract. Reap only exact unfinished sandbox IDs after a dry-run report; never perform broad account cleanup.

Run Control and Rich as independent full schedules. Do not share content-addressed seed attempts across arms because run identity and model stochasticity are part of each arm's measured execution. More tasks reduce panel sensitivity but one run per arm does not estimate provider/model stochastic variance; report that limitation.

## Test and Paid Execution Sequence

1. Add dependency-light unit tests for feedback schemas, held-out exclusion, provenance canaries, evidence indexing, mutation policy, path/symlink/binary rejection, protected config, custom local-tool import, Python 3.11 bridge timeout, admission rollback, arm identity, and resume mismatch.
2. Run the full local test suite without credentials.
3. Run a no-model E2B canary that loads and invokes a fixture local `tools.*` binding in the exact worker template.
4. Run one paid rich-evolver canary that receives a synthetic/public evidence corpus, edits a fixture full worker, passes admission, executes one optimize worker, runs one independent verifier, and cleans every sandbox.
5. Dry-run exact-ID reaping and verify no pending IDs.
6. Run the 140-attempt Control arm.
7. Audit completion, cleanup, template IDs, feedback digest, and score count.
8. Run the 140-attempt Rich arm.
9. Audit completion and compare both new arms with the provisional historical 30x5 run.

The user has granted standing paid-evaluation authority for the configured E2B and model-provider accounts; no per-step approval is required. Persist provider token usage, model cost where exposed, E2B execution counts/durations, and any unavailable billing field explicitly.

## Analysis

Primary outcome:

```text
RichFeedbackGain =
  (Rich optimize final - Rich optimize seed)
  - (Control optimize final - Control optimize seed)
```

Also report optimize domain-macro trajectories, candidate-score AUC, first kept iteration, keep/rollback count, per-domain and per-task deltas, improved/regressed task counts, mutation-file categories, custom-tool admission/runtime success, worker timeouts/tool errors, evidence files actually read, tokens, wall time, model cost, and sandbox lifecycles.

Report held-out seed/final results as secondary observations only. Do not feed them back or use them to select mutations. Label the historical 2026-07-25 scores provisional and show which 14 records were verifier-cache contaminated.

## Acceptance Criteria

Implementation and experiment are complete only when:

1. The feedback contract and `FEEDBACK_30.json` pass public/private provenance and coverage tests for all 20 optimize tasks.
2. Control and Rich use identical manifests, models, seed workers, mutation policies, budgets, verifier templates, and five-iteration schedules; their feedback-contract digest is the intended differing identity.
3. Full-harness custom tools load and run in the exact remote NexAU environment, including enforced Python 3.11 bridge timeout behavior.
4. Candidate admission rejects every protected-field, path, symlink, binary, secret, dependency, and import canary before paid scoring.
5. No private verifier or held-out canary appears in any proposer-facing artifact or trace.
6. The paid full-harness canary succeeds and leaves no pending sandbox ID.
7. Each arm has exactly 140 unique scheduled official score records, five iteration records, complete seed/final held-out checkpoints, and a consistent final incumbent.
8. Lifecycle records account for every created evolver, worker, and verifier sandbox; final exact-ID dry-run reapers report no pending IDs.
9. The local test suite passes after implementation.
10. A dated decision, experiment report, comparison artifact, and `docs/PROJECT_MEMORY.md` update preserve the historical run and clearly separate optimize adaptation, held-out observation, infrastructure validity, and cost.
