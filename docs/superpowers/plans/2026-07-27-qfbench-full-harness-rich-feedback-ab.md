# QFBench Full-Harness Rich-Feedback A/B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a secure full-worker NexAU evolution path and run matched Control and Rich 30-task, five-iteration QFBench experiments that differ only in proposer-facing evidence.

**Architecture:** A typed feedback contract and instruction-derived public rubric feed a filesystem evidence corpus. A secure E2B evolver edits a jailed worker snapshot; deterministic admission validates every candidate in the pinned NexAU environment before the existing isolated worker/verifier evaluator scores it. The benchmark loop checkpoints the feedback-contract digest, proposal evidence, candidate admission, costs, and lifecycles so two independent 140-attempt arms can resume and be compared.

**Tech Stack:** Python 3.10+ coordinator, NexAU 0.3.9 on pinned Python 3.12, QFBench task Python 3.11, pytest, PyYAML, E2B templates/SDK, JSON/JSONL/tar artifacts.

## Global Constraints

- Benchmark commit is `024921eb507fcc0c4ffe3e0a96802724be1ae84a`.
- Use `data/qfbench/MANIFEST_30.json`: exactly 20 optimize and 10 seed/final-only held-out tasks for five iterations.
- Each arm schedules exactly 140 official score records; Control and Rich together schedule 280.
- Use `deepseek/deepseek-v4-pro`, `qea/worker_gdpval_weak`, concurrency 8, global E2B cap 12, `noise_floor=0.02`, and `max_domain_regression=0.0`.
- Use only corrected verifier template IDs; never reuse the three invalid 2026-07-25 verifier IDs.
- Keep official rewards byte-for-byte unchanged and keep verifier sandboxes independent and offline.
- Never expose official solutions, verifier-only reference values, raw tests/assertions, credentials, or held-out inputs/results to the evolver.
- Rich may receive optimize public instructions/environment, complete worker-observable traces/artifacts, public rubric, sanitized criterion results, and edit/outcome history.
- Full harness may change prompt, tool descriptions, local tools/bindings, middleware, skills, validator, memory, and routing; model/provider/credentials and experiment resource budgets remain protected.
- Run the evolver only in secure E2B with provider-host-only egress and header-injected authorization.
- Do not merge. Make focused commits; preserve the original 2026-07-25 result and dated reports.

---

## File Map

- `qea/evolution_feedback.py`: typed Control/Rich contracts, public rubric loading, trusted CTRF-to-public-criterion sanitization, contract digests.
- `data/qfbench/FEEDBACK_30.json`: public criteria for all 20 optimize tasks.
- `data/qfbench/VERIFIER_CRITERIA_30.json`: trusted test-name-to-public-criterion mapping; never bundled to worker/evolver.
- `qea/evolution_evidence.py`: deterministic evidence corpus and read-audit index.
- `qea/candidate_admission.py`: mutation allowlist, protected-config equality, manifest/digest, compile/import/binding checks, timeout policy.
- `qea/evolve_agent_full/`: secure NexAU evolver config, prompt, guarded tools, descriptions, and harness-format reference.
- `qea/executors/e2b_evolver.py`: secure sandbox lifecycle, bundle upload, remote execution, candidate-only download, cost/trace records.
- `qea/executors/remote_evolver.py`: in-sandbox NexAU evolver entrypoint.
- `qea/executors/remote_nexau_worker.py`: worker-root import path and task-Python bridge environment.
- `qea/executors/bundles.py`: deterministic evolver input and candidate output bundles.
- `qea/loop_benchmark.py`: feedback mode, evidence/history construction, admission gate, identity-safe resume.
- `run.py`: feedback-mode/evolver-template CLI and A/B-safe configuration.
- `scripts/build_qfbench_e2b_evolver.py`: immutable generic NexAU evolver template publication.
- `scripts/smoke_qfbench_full_harness.py`: no-model import canary and one paid rich-evolver end-to-end canary.
- `scripts/compare_qfbench_feedback_ab.py`: Control/Rich/historical comparison and completion audit.
- `tests/test_qfbench_feedback_contract.py`, `tests/test_evolution_evidence.py`, `tests/test_candidate_admission.py`, `tests/test_e2b_evolver.py`, `tests/test_qfbench_feedback_ab.py`: focused contract and integration tests.

---

### Task 1: Typed Feedback Contract and Public Rubric

**Files:**
- Create: `qea/evolution_feedback.py`
- Create: `data/qfbench/FEEDBACK_30.json`
- Create: `data/qfbench/VERIFIER_CRITERIA_30.json`
- Create: `tests/test_qfbench_feedback_contract.py`

**Interfaces:**
- Produces: `FeedbackMode`, `PublicCriterion`, `PublicCriterionResult`, `TaskEvolutionFeedback`, `FeedbackContract`, `load_feedback_manifest()`, `load_verifier_mapping()`, `sanitize_ctrf_feedback()`, and `feedback_contract_digest()`.
- Consumes: QFBench CTRF JSON already persisted under trusted verifier directories.

- [ ] **Step 1: Write failing schema and firewall tests**

```python
def test_feedback_manifest_covers_exact_optimize_panel():
    manifest = load_feedback_manifest(Path("data/qfbench/FEEDBACK_30.json"))
    qf = json.loads(Path("data/qfbench/MANIFEST_30.json").read_text())
    assert set(manifest) == {x["task_id"] for x in qf["pilot"]["optimize"]}

def test_sanitized_criterion_feedback_never_forwards_private_fields(tmp_path):
    ctrf = tmp_path / "ctrf.json"
    ctrf.write_text(json.dumps({"results": {"tests": [{
        "name": "test_private_canary_DO_NOT_EXPOSE",
        "status": "failed",
        "message": "expected 123.456, got 7.0"
    }]}}))
    mapping = {"test_private_canary_DO_NOT_EXPOSE": "required_output"}
    result = sanitize_ctrf_feedback(ctrf, mapping, {
        "required_output": PublicCriterion("required_output", "Produce the requested output.")
    })
    encoded = json.dumps([asdict(item) for item in result])
    assert "DO_NOT_EXPOSE" not in encoded
    assert "123.456" not in encoded
    assert result[0].criterion_id == "required_output"
    assert result[0].status == "failed"
```

- [ ] **Step 2: Run focused tests and confirm the module/files are absent**

Run: `.venv-nexau/bin/python -m pytest -q tests/test_qfbench_feedback_contract.py`

Expected: collection/import failure for `qea.evolution_feedback`.

- [ ] **Step 3: Implement immutable public types and fail-closed loaders**

```python
class FeedbackMode(str, Enum):
    CONTROL = "control"
    RICH = "rich"

@dataclass(frozen=True)
class PublicCriterion:
    criterion_id: str
    requirement: str

@dataclass(frozen=True)
class PublicCriterionResult:
    criterion_id: str
    status: str
    passed_checks: int
    failed_checks: int
    evidence_kind: str
    public_message: str

def feedback_contract_digest(mode: FeedbackMode, rubric_path: Path) -> str:
    payload = {"schema_version": 1, "mode": mode.value,
               "rubric_sha256": hashlib.sha256(rubric_path.read_bytes()).hexdigest()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
```

Validate IDs with `^[a-z][a-z0-9_]*$`, reject duplicate/empty criteria, require all 20 optimize task IDs and no held-out IDs, and allow only fixed public evidence kinds such as `requirement_not_satisfied`, `schema_or_structure_mismatch`, `numeric_or_method_mismatch`, `missing_output`, and `runtime_failure`. Build criterion status only from mapped test status/count; never forward test names/messages.

- [ ] **Step 4: Populate both 30-task feedback manifests from the pinned public instructions and trusted CTRF names**

For every optimize task, record at least one instruction-derived criterion. Keep `FEEDBACK_30.json` free of test names and exact reference values. Put exact CTRF test-name keys only in `VERIFIER_CRITERIA_30.json`, and require every mapped value to exist in that task's public criterion set.

- [ ] **Step 5: Run contract tests**

Run: `.venv-nexau/bin/python -m pytest -q tests/test_qfbench_feedback_contract.py tests/test_qfbench_pilot_contract.py`

Expected: all tests pass and the private canary is absent from serialized public feedback.

- [ ] **Step 6: Commit**

```bash
git add qea/evolution_feedback.py data/qfbench/FEEDBACK_30.json \
  data/qfbench/VERIFIER_CRITERIA_30.json tests/test_qfbench_feedback_contract.py
git commit -m "feat(feedback): define QFBench evolution evidence contract"
```

### Task 2: Deterministic Rich Evidence Corpus

**Files:**
- Create: `qea/evolution_evidence.py`
- Create: `tests/test_evolution_evidence.py`
- Modify: `qea/loop_benchmark.py`

**Interfaces:**
- Consumes: `FeedbackMode`, task objects, `run_dir/attempts/*/attempt.json`, worker execution manifests, trusted verifier outputs, public rubric/mapping, and prior iteration records.
- Produces: `EvidenceRecord(root: Path, sha256: str, members: tuple[str, ...])` and `build_evolution_evidence(...) -> EvidenceRecord`.

- [ ] **Step 1: Write failing corpus-layout and held-out-canary tests**

```python
def test_rich_corpus_contains_optimize_trace_artifacts_and_no_holdout(tmp_path):
    record = build_evolution_evidence(
        mode=FeedbackMode.RICH,
        optimize_tasks=(optimize_task,),
        held_out_task_ids={"holdout-secret"},
        run_dir=fixture_run(tmp_path),
        destination=tmp_path / "evidence",
        feedback_manifest=public_manifest,
        verifier_mapping=private_mapping,
        history=(),
    )
    assert (record.root / "tasks/optimize-1/instruction.md").is_file()
    assert (record.root / "tasks/optimize-1/attempts/seed-optimize/worker_trace.jsonl").is_file()
    text = "\n".join(p.read_text(errors="replace") for p in record.root.rglob("*") if p.is_file())
    assert "holdout-secret" not in text
    assert "PRIVATE_VERIFIER_CANARY" not in text
```

- [ ] **Step 2: Run the test and confirm missing implementation**

Run: `.venv-nexau/bin/python -m pytest -q tests/test_evolution_evidence.py`

Expected: import failure for `qea.evolution_evidence`.

- [ ] **Step 3: Persist attempt identity before worker execution**

In `QFBenchE2BEvaluator._score_task`, atomically write `attempt.json` from `asdict(attempt)` before loading/executing the worker. This gives the corpus builder trusted split/checkpoint/task provenance without reconstructing SHA identities.

- [ ] **Step 4: Implement mode-specific corpus materialization**

Control writes only `contract.json`, aggregate/task scalar feedback, diagnostic counts, and `history/`. Rich additionally copies optimize public task files, worker trace/final/summary/artifacts, public rubric, and sanitized criterion results. Use deterministic sorted traversal, normalized JSON, file/byte caps, and SHA-256 over relative path plus payload. Reject any attempt record whose split is not `optimize` or whose task ID is not in the optimize manifest.

- [ ] **Step 5: Add evidence read-audit support**

Write `access_log.jsonl` through the guarded tools in Task 5, with fields `timestamp`, `operation`, `source`, `relative_path`, and `bytes_returned`. The builder creates an empty file and includes its path in `contract.json` but excludes its changing bytes from the immutable input digest.

- [ ] **Step 6: Run focused tests and commit**

Run: `.venv-nexau/bin/python -m pytest -q tests/test_evolution_evidence.py tests/test_qfbench_evolution.py`

```bash
git add qea/evolution_evidence.py qea/loop_benchmark.py tests/test_evolution_evidence.py
git commit -m "feat(evidence): build optimize-only evolution corpus"
```

### Task 3: Full-Worker Candidate Admission

**Files:**
- Create: `qea/candidate_admission.py`
- Create: `tests/test_candidate_admission.py`

**Interfaces:**
- Produces: `AdmissionPolicy`, `CandidateFile`, `CandidateAdmissionRecord`, `admit_candidate(seed_dir, candidate_dir, policy, *, exact_runtime=None)`.
- Used by: the benchmark loop before any candidate task evaluation and the E2B canary.

- [ ] **Step 1: Write failing mutation/firewall tests**

Cover accepted `systemprompt.md`, new `tools/pkg/calc.py`, tool description and `agent.yaml` binding; reject changed model/base URL/API key/max iterations/max tokens/temperature, symlink, `.env`, extensionless executable, binary, `../` archive path, undeclared import, syntax error, binding import failure, missing timeout in subprocess tool, and task-specific answer canary.

```python
def test_rejects_protected_model_change(seed_candidate):
    seed, candidate = seed_candidate
    path = candidate / "agent.yaml"
    path.write_text(path.read_text().replace("${env.LLM_MODEL}", "other/model"))
    with pytest.raises(CandidateAdmissionError, match="protected field llm_config.model"):
        admit_candidate(seed, candidate, AdmissionPolicy.qfbench_full())
```

- [ ] **Step 2: Run the tests and confirm missing implementation**

Run: `.venv-nexau/bin/python -m pytest -q tests/test_candidate_admission.py`

Expected: import failure for `qea.candidate_admission`.

- [ ] **Step 3: Implement manifest and mutation policy**

Allow only UTF-8 text under `agent.yaml`, `systemprompt.md`, `tool_descriptions/`, `tools/`, `middleware/`, `skills/`, `validator/`, `memory/`, and `routing/`. Reject symlinks, devices, secret-like names, non-UTF-8/binary content, unknown top-level paths, and size/count cap violations. Compare protected YAML paths against the seed using explicit dotted paths; only the `tools` list and approved local component sections may differ.

- [ ] **Step 4: Implement Python, binding, dependency, and timeout validation**

Use `compile()`/`py_compile`, AST import collection, an allowlist derived from stdlib plus `/opt/qea/nexau-requirements.lock`, and `importlib` in a bounded subprocess. Validate every `binding: module:function`, every tool-description YAML, unique tool names, and callable signatures. For code invoking `subprocess.run` or `Popen`, require a literal or bounded `timeout` path and reject `shell=True`.

- [ ] **Step 5: Produce a complete admission record**

```python
@dataclass(frozen=True)
class CandidateAdmissionRecord:
    admitted: bool
    candidate_digest: str
    policy_digest: str
    files: tuple[CandidateFile, ...]
    checks: tuple[str, ...]
    failure: str | None = None
```

Persist it before scoring and make admission failure a proposal rollback, not an official task score.

- [ ] **Step 6: Run tests and commit**

Run: `.venv-nexau/bin/python -m pytest -q tests/test_candidate_admission.py tests/test_evaluation_contract.py`

```bash
git add qea/candidate_admission.py tests/test_candidate_admission.py
git commit -m "feat(admission): validate full-worker candidates"
```

### Task 4: Worker-Local Tool Loading and Dual Runtime

**Files:**
- Modify: `qea/executors/remote_nexau_worker.py`
- Create: `qea/runtime_bridge.py`
- Modify: `tests/test_e2b_nexau_executor.py`
- Modify: `tests/test_candidate_admission.py`

**Interfaces:**
- Produces: `task_python(argv: list[str], *, cwd: Path, timeout_seconds: int, max_output_bytes: int) -> dict` for generated tools to copy/use through an approved binding or reference.
- Ensures: worker root is importable before `AgentConfig.from_yaml()`.

- [ ] **Step 1: Add a failing remote-runner import test**

Construct a fixture worker with `binding: tools.fixture:echo`, load the uploaded remote runner in a subprocess without pre-setting `PYTHONPATH`, and assert `AgentConfig.from_yaml` can resolve the module only after the worker root is inserted.

- [ ] **Step 2: Add failing bridge safety tests**

Assert argv-list execution succeeds under Python 3.11, timeout kills a sleeping process, output beyond the cap is rejected, absolute/outside cwd is rejected, and no `shell=True` path exists.

- [ ] **Step 3: Insert the worker root before config loading**

```python
worker_root = worker_dir.resolve()
if str(worker_root) not in sys.path:
    sys.path.insert(0, str(worker_root))
config = AgentConfig.from_yaml(config_path=worker_root / "agent.yaml")
```

- [ ] **Step 4: Implement the bounded task-Python bridge**

Use `subprocess.run(["/usr/local/bin/python3", *argv], cwd=resolved_cwd, timeout=timeout_seconds, capture_output=True, env=minimal_env, check=False)`. Enforce positive timeout, maximum 1 MiB combined output, cwd beneath `/app`, and JSON-safe return values.

- [ ] **Step 5: Run tests and commit**

Run: `.venv-nexau/bin/python -m pytest -q tests/test_e2b_nexau_executor.py tests/test_candidate_admission.py`

```bash
git add qea/executors/remote_nexau_worker.py qea/runtime_bridge.py \
  tests/test_e2b_nexau_executor.py tests/test_candidate_admission.py
git commit -m "fix(worker): load local tools across pinned runtimes"
```

### Task 5: Guarded Full-Harness Evolver Agent

**Files:**
- Create: `qea/evolve_agent_full/agent.yaml`
- Create: `qea/evolve_agent_full/systemprompt.md`
- Create: `qea/evolve_agent_full/tools/guarded_workspace.py`
- Create: `qea/evolve_agent_full/tools/__init__.py`
- Create: `qea/evolve_agent_full/tool_descriptions/*.tool.yaml`
- Copy and harden: `qea/evolve_agent_full/reference/NEXAU_GUIDE.md`
- Create: `tests/test_evolver_guarded_tools.py`

**Interfaces:**
- Produces guarded NexAU bindings `list_workspace`, `read_workspace`, `search_evidence`, `write_candidate`, `replace_candidate`, and `smoke_candidate_tool`.
- Consumes environment roots `QEA_CANDIDATE_ROOT`, `QEA_EVIDENCE_ROOT`, and `QEA_ACCESS_LOG`.

- [ ] **Step 1: Write failing jail and audit tests**

Test normal candidate read/write, evidence read, access-log append, and rejection of absolute paths, `..`, symlinks, writes to evidence, candidate-root deletion, and reads outside both roots.

- [ ] **Step 2: Implement one resolver used by every tool**

```python
def _resolve(root: Path, relative: str, *, must_exist: bool) -> Path:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ValueError("unsafe relative path")
    target = (root / Path(*rel.parts)).resolve(strict=must_exist)
    target.relative_to(root.resolve())
    if target.is_symlink() or any(parent.is_symlink() for parent in target.parents if parent != root):
        raise ValueError("symlinks are forbidden")
    return target
```

- [ ] **Step 3: Implement bounded tools without unrestricted shell**

Cap each read/search response, reject non-UTF-8 edits, atomically write candidate files, enforce unique replacement counts, and log all evidence reads. `smoke_candidate_tool` accepts only a `tools.*` module, identifier function name, JSON args, and timeout at most 120 seconds.

- [ ] **Step 4: Configure and prompt the evolver**

Use the six guarded tools only. The prompt requires evidence inspection, a general worker-process change, tool self-test, no task-answer embedding, and final JSON with `predicted_fixes`, `risk_tasks`, `evidence_used`, and rationale. It explains protected fields and the full mutation allowlist.

- [ ] **Step 5: Run tests and commit**

Run: `.venv-nexau/bin/python -m pytest -q tests/test_evolver_guarded_tools.py`

```bash
git add qea/evolve_agent_full tests/test_evolver_guarded_tools.py
git commit -m "feat(evolver): add jailed full-harness editing agent"
```

### Task 6: Secure E2B Evolver Executor and Template

**Files:**
- Modify: `qea/executors/bundles.py`
- Create: `qea/executors/e2b_evolver.py`
- Create: `qea/executors/remote_evolver.py`
- Create: `scripts/build_qfbench_e2b_evolver.py`
- Create: `tests/test_e2b_evolver.py`
- Modify: `tests/test_qfbench_images.py`

**Interfaces:**
- Produces: `E2BEvolverConfig`, `E2BEvolverResult`, `E2BFullHarnessProposer.propose(candidate_dir, diagnosis, iteration, run_dir) -> dict`.
- Consumes: candidate/evidence directories, model env, shared E2B lease, generic evolver template ID, and Task 3 admission.

- [ ] **Step 1: Write failing bundle/network/lifecycle tests**

Assert the evolver bundle contains only `candidate/`, `evidence/`, and `evolve_agent/`; raw API key is absent from env/files/logs; E2B network allows only the model host with header injection; `secure=True`; candidate output rejects traversal/symlinks; sandbox cleanup is recorded on success and exception.

- [ ] **Step 2: Add deterministic evolver bundles**

Add `build_evolver_input_bundle()` and `extract_candidate_archive()` with the same deterministic tar metadata, secret checks, file/byte limits, and path safety as worker bundles.

- [ ] **Step 3: Implement remote evolver entrypoint**

Insert the uploaded evolver asset root into `sys.path`, set candidate/evidence roots, load `AgentConfig`, run NexAU, render a capped full trace, write final/prediction/access summary, and tar only `/qea/candidate`. Never enumerate/download the full VM filesystem.

- [ ] **Step 4: Implement secure executor**

Reuse `sanitize_worker_env()` and `build_worker_network()`, set role metadata `evolver`, use the global lease, persist lifecycle before interaction, upload input/entrypoint, run with the pinned NexAU Python, extract the candidate safely, and always kill the sandbox. Persist model usage fields when returned; otherwise record `null` with reason.

- [ ] **Step 5: Implement immutable evolver-template publication**

Create one template from the published QFBench base template/build, install `NEXAU_WORKER_DEPENDENCY` into the pinned Python 3.12 runtime, persist dependency lock, and write `evolver.image.json` with identity/published template/build IDs. Dry-run is default; `--publish` performs the paid build and reuses an identical published identity.

- [ ] **Step 6: Run tests and commit**

Run: `.venv-nexau/bin/python -m pytest -q tests/test_e2b_evolver.py tests/test_qfbench_images.py tests/test_e2b_nexau_executor.py`

```bash
git add qea/executors/bundles.py qea/executors/e2b_evolver.py \
  qea/executors/remote_evolver.py scripts/build_qfbench_e2b_evolver.py \
  tests/test_e2b_evolver.py tests/test_qfbench_images.py
git commit -m "feat(evolver): run full-harness edits in secure E2B"
```

### Task 7: Feedback-Aware Benchmark Loop and Resume

**Files:**
- Modify: `qea/loop_benchmark.py`
- Create: `tests/test_qfbench_feedback_ab.py`
- Modify: `tests/test_qfbench_evolution.py`
- Modify: `tests/test_levelb_resume.py`

**Interfaces:**
- Extends `BenchmarkEvolutionConfig` with `feedback_mode`, `feedback_contract_digest`, `public_rubric_path`, `verifier_mapping_path`, and `admission_policy_digest`.
- Proposer receives an `EvolutionProposalContext` containing candidate, evidence record, diagnosis, iteration, and history.

- [ ] **Step 1: Write failing A/B identity and isolation tests**

Assert Control corpus lacks instructions/traces/artifacts, Rich includes them, held-out canary is absent in both, both use identical task calls and mutation policy, admission failure skips evaluator calls, history contains rejected edits, and resume rejects feedback/rubric/admission digest changes.

- [ ] **Step 2: Version checkpoint schema**

Set `schema_version=2` and persist run ID, arm, benchmark/task-manifest/feedback/rubric/admission digests, model identity, seed digest, template identity digest, phase, iteration, candidate/admission records, proposals, costs, and lifecycles. Validate every immutable identity before resume.

- [ ] **Step 3: Integrate evidence and full proposer**

Before each proposal, build the mode-specific corpus from completed optimize attempts and history. Pass its path/digest to `E2BFullHarnessProposer`. Persist proposal prediction/trace/access summary. Compute complete directory diff and candidate digest, run admission, and only then evaluate optimize tasks.

- [ ] **Step 4: Preserve keep/rollback and held-out isolation**

Keep existing `gain > 0.02` and no-domain-regression behavior. Append rejected signatures/history. Evaluate held-out only at seed/final and never pass those attempts to corpus construction. Keep admission rejection distinct from an official zero.

- [ ] **Step 5: Run tests and commit**

Run: `.venv-nexau/bin/python -m pytest -q tests/test_qfbench_feedback_ab.py tests/test_qfbench_evolution.py tests/test_levelb_resume.py tests/test_evaluation_contract.py`

```bash
git add qea/loop_benchmark.py tests/test_qfbench_feedback_ab.py \
  tests/test_qfbench_evolution.py tests/test_levelb_resume.py
git commit -m "feat(qfbench): integrate full-harness feedback arms"
```

### Task 8: CLI, Canaries, and A/B Comparison

**Files:**
- Modify: `run.py`
- Create: `scripts/smoke_qfbench_full_harness.py`
- Create: `scripts/compare_qfbench_feedback_ab.py`
- Modify: `tests/test_run_cli.py`
- Create: `tests/test_qfbench_full_harness_scripts.py`

**Interfaces:**
- CLI adds `--feedback-mode {control,rich}`, `--evolver-template-manifest`, `--feedback-manifest`, and `--verifier-criteria-map`.
- Comparison script consumes two completed result roots and optional historical result, producing JSON and Markdown.

- [ ] **Step 1: Write failing CLI and schedule tests**

Assert 20/10/5 estimates 140 for either arm; rich/control require evolver template and feedback files; resume requires the same arm; QFBench refuses local evolver; and the comparison refuses incomplete/mismatched 30x5 runs.

- [ ] **Step 2: Wire CLI to secure proposer**

Load the immutable evolver template manifest, model env, feedback manifests, and shared lease. Construct the feedback-aware config and E2B proposer. Print arm, contract digest, 140-attempt schedule, max lifecycle count, template IDs, and output path before the paid gate.

- [ ] **Step 3: Implement two canary modes**

`--mode import` creates a fixture worker with a local `tools.fixture:echo` binding and verifies it in an exact worker template without model calls. `--mode paid-rich` builds a public synthetic evidence corpus, invokes one E2B evolver, admits the edit, runs one selected optimize worker plus independent verifier, records every lifecycle, and exact-ID reaps only its run root.

- [ ] **Step 4: Implement completion audit and comparison**

Require five records, 140 unique completed scores, expected seed/candidate/final checkpoints, consistent final incumbent, all lifecycle cleanups, no private canary, and no pending exact IDs. Compute `RichFeedbackGain`, trajectories/AUC, keep rates, domain/task deltas, edit categories, evidence-read counts, timeouts/errors, tokens/cost, and historical provisional annotations.

- [ ] **Step 5: Run tests and commit**

Run: `.venv-nexau/bin/python -m pytest -q tests/test_run_cli.py tests/test_qfbench_full_harness_scripts.py tests/test_qfbench_comparison.py`

```bash
git add run.py scripts/smoke_qfbench_full_harness.py \
  scripts/compare_qfbench_feedback_ab.py tests/test_run_cli.py \
  tests/test_qfbench_full_harness_scripts.py
git commit -m "feat(qfbench): add feedback A/B execution and audit"
```

### Task 9: Local Verification and Paid Canaries

**Files:**
- Update only if failures prove a defect in Tasks 1-8.
- Generate: `output/qfbench-e2b-images/evolver.image.json`
- Generate: `results/qfbench_full_harness_canary/<run-id>/`

**Interfaces:**
- Consumes current configured E2B/model accounts and existing corrected task-role templates.
- Produces an immutable evolver template ID/build ID and clean canary artifacts.

- [ ] **Step 1: Run dependency-light and full local verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-nexau/bin/python -m pytest -q -p no:cacheprovider tests
.venv-nexau/bin/python -m compileall -q qea scripts run.py
git diff --check
```

Expected: all tests pass, compile succeeds, and diff check is empty.

- [ ] **Step 2: Prepare and publish the evolver template**

Run the new builder first without `--publish`, inspect its identity/commands, then rerun with `--publish`. Record template/build IDs immediately and do not rebuild an identical published identity.

- [ ] **Step 3: Run the no-model import canary**

Use one corrected worker template and verify the local tool binding imports/executes in NexAU Python 3.12. Require zero model calls, one cleaned worker sandbox, and no pending exact IDs.

- [ ] **Step 4: Run the paid Rich end-to-end canary**

Use `historical-var-data-prep`, one evolver call, one worker, and one independent offline verifier. Require admitted non-empty edit, worker execution, official verifier execution, lifecycle cleanup, no private canary leakage, and final reaper `pending_ids=[]`.

- [ ] **Step 5: Commit implementation fixes and canary identities**

Do not commit bulky generated run artifacts. Commit the immutable evolver template manifest and any code/test fix proven necessary.

### Task 10: Two Full Paid 30x5 Runs and Reporting

**Files:**
- Generate: `results/qfbench/<control-run-id>/`
- Generate: `results/qfbench/<rich-run-id>/`
- Generate: `results/qfbench_feedback_ab/<comparison-id>.{json,md}`
- Create: `docs/decisions/2026-07-27-qfbench-full-harness-feedback-ab-result.md`
- Create: `docs/reports/2026-07-27-qfbench-full-harness-feedback-ab-report.md`
- Modify: `docs/PROJECT_MEMORY.md`

**Interfaces:**
- Consumes admitted implementation, corrected templates, fixed panel, model credentials, E2B account, and exact-ID resume/reaper.
- Produces two complete 140-score arms and a validity-audited comparison.

- [ ] **Step 1: Launch the Control arm**

Use a collision-free `qfbench-30x5-full-control-20260727-*` run ID, `--feedback-mode control`, `--iters 5`, concurrency 8, cap 12, `MANIFEST_30.json`, corrected task-role templates, and the immutable evolver template. Preserve the command and resolved config in the run root.

- [ ] **Step 2: Audit or resume Control**

If interrupted, dry-run exact-ID reaping, kill only reviewed pending IDs, and rerun the identical command with `--resume`. Do not change identities or budgets. Require five records and 140 completed score records before proceeding.

- [ ] **Step 3: Launch the Rich arm**

Use a collision-free `qfbench-30x5-full-rich-20260727-*` run ID and the identical command/config except `--feedback-mode rich` and its resulting contract digest.

- [ ] **Step 4: Audit or resume Rich**

Apply the same exact-ID recovery. Require five records, 140 completed scores, full evidence/access/admission artifacts, and no held-out/private canary in proposer-facing files.

- [ ] **Step 5: Generate comparison and validity audit**

Run `scripts/compare_qfbench_feedback_ab.py` with both new roots and `results/qfbench/qfbench-30x5-20260725`. Verify both new runs match manifest, model, seed, templates, budgets, admission policy, and schedule. The intended feedback-contract digest/mode is the only experimental identity difference.

- [ ] **Step 6: Write decision, experiment report, and memory update**

Record process/data, optimize results, RichFeedbackGain, per-domain/task analysis, evidence utilization, held-out secondary observations, infrastructure/cost audit, limitations, exposure-boundary discussion, and next-week plan. Preserve the historical report and label its 14 affected scores provisional.

- [ ] **Step 7: Final verification and commit**

Run the full local suite, comparison completion audit, and exact-ID dry-run reapers for canary/Control/Rich. Confirm root worktree has only intentional report/manifest changes, then commit scoped documentation and small comparison artifacts without merging.
