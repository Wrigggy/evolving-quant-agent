# Repository Guidelines

## Repository Memory & Required Reading

Before changing benchmarks, rewards, evaluator isolation, NexAU execution, or cloud infrastructure, read [`docs/PROJECT_MEMORY.md`](docs/PROJECT_MEMORY.md); it is canonical and supersedes older plans. Details live in the [QFBench/runtime decision](docs/decisions/2026-07-21-qfbench-and-runtime-architecture.md) and [benchmark authority report](docs/reports/2026-07-21-qea-benchmark-authority-screen-report.md). Preserve dated reports; record changed decisions in the memory plus a new superseding record rather than rewriting history.

## Project Structure & Module Organization

Core Python lives in `qea/`; evolution is in `loop.py` and `loop_levelb.py`, with grading and verification under `grading/`, `verifier.py`, and `debugger.py`. NexAU agent directories are `qea/worker*`; code-first Stirrup workers are in `qea/workers/`. Put utilities in `scripts/`, tests in `tests/`, pinned inputs in `data/`, and designs/results in `docs/`. Treat `results/`, `output/`, and `inspection/` as generated unless intentionally documenting a result.

## Build, Test, and Development Commands

- `python3 -m venv .venv && source .venv/bin/activate` creates an isolated environment.
- `pip install -e .` installs the standard-library core in editable mode.
- `pip install -e ".[real,gdpval,artifacts]"` adds OpenRouter, GDPval parquet, and XLSX support.
- `python3 run.py --mock` runs the fast, deterministic evolve/falsify/rollback fixture without credentials.
- `python3 -m pytest tests/test_smoke.py` runs the dependency-light core suite. Use `-k rollback` for a focused check.
- `python3 run.py --real --iters 4 --k 2` launches a networked GDPval experiment; configure `.env` first.

## Coding Style & Naming Conventions

Target Python 3.10+ and PEP 8 with four spaces. Use `snake_case`, `PascalCase`, and `UPPER_SNAKE_CASE` conventionally; preserve type hints and concise public docstrings. Keep benchmark-independent logic in `qea/` and CLI orchestration in `run.py` or `scripts/`. No formatter is enforced; match nearby code and group imports standard-library, third-party, then local.

## Testing and Research Integrity

Pytest files use `test_*.py`; name tests by observable behavior. Prefer deterministic fakes, `tmp_path`, and `monkeypatch`; gate API/E2B tests behind environment flags. Run `python3 -m pytest tests` with NexAU and `[stirrup]` installed. Cover keep/rollback, score boundaries, and firewall invariants. Never expose gold, raw rubric verdicts, keys, or `.env` to proposer prompts. Update `data/gdpval/MANIFEST.md` when refreshing its snapshot.

## Experimental Engineering Priorities

This repository studies harness evolution, not security attack and defense. Keep
validation proportional to realistic experimental risk and do not turn routine
engineering into defensive infrastructure work.

- Optimize first for iteration speed and a flexible mutation surface. Use a
  small smoke test or preflight when it catches a likely failure; add stricter
  checks only after a concrete observed need.
- Do not add new hashes, SHA-256 fields, content-addressed identities, or
  digest-equality gates to code, experiment evidence, or reports.
- Test the happy path and observed failure modes. Do not repeatedly implement
  defenses or regression cases for scenarios that are not realistically
  expected in this experimental setup.
- Preserve enough evidence to reconstruct the setup, candidate change, score,
  cost, and failure. Matching the experimental setup is sufficient for an
  engineering canary; exhaustive equality across every runtime contract is not
  required.
- Retain only the minimum research-integrity boundaries: do not expose verifier
  answers or credentials to the Evolver, fabricate results, or treat an
  obviously invalid run as a benchmark result.

## Commit & Pull Request Guidelines

Use concise history-aligned messages such as `feat(levelb): ...`, `fix(verifier): ...`, `docs: ...`, or `results(fab-weak): ...`. Keep commits scoped. Pull requests should explain the hypothesis/bug, commands, run configuration, metric changes, and relevant specs/issues. Include artifact paths for experiments and screenshots only for rendered-output changes.
