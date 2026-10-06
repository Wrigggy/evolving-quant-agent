"""BacktestBench CampaignBackend adapter for research_campaign.py.

Connects backtestbench_panel.run_backtestbench_panel and
backtestbench_revision.run_backtestbench_revision to the CampaignBackend
protocol so that research_campaign.advance_campaign can run automated
multi-round BacktestBench evolution campaigns.

Contract:
- run_episode: runs a fresh Worker panel via backtestbench_panel
- run_evaluation: grades existing panel results using the official scorer
- active_revision_source_available: checks that train artifacts are present
- run_revision: runs one Evolver call via backtestbench_revision
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Mapping, Sequence

from .backtestbench_panel import (
    RESULT_FILE as PANEL_RESULT_FILE,
    STATE_FILE as PANEL_STATE_FILE,
    run_backtestbench_panel,
)
from .backtestbench_revision import (
    RESULT_FILE as REVISION_RESULT_FILE,
    run_backtestbench_revision,
)
from .benchmarks.backtestbench import (
    OFFICIAL_CATEGORIES,
    grade_submission,
    project_public_task,
)
from .research_campaign import (
    EpisodeEvidence,
    EpisodeRequest,
    EvaluationRequest,
    HarnessRef,
    OfficialEvaluation,
    ResearchCampaignError,
    RevisionOutcome,
    RevisionRequest,
    TaskMetric,
    _json_copy,
    _read_object,
    _text,
    _write_or_reuse,
    EPISODE_FILE,
    EVALUATION_FILE,
)


_PROTOCOL_EPISODE = "research-campaign-backtestbench-episode-v1"
_PROTOCOL_EVALUATION = "research-campaign-backtestbench-evaluation-v1"
_PROTOCOL_REVISION = "research-campaign-backtestbench-revision-v1"

_SELECTION_POLICY = (
    "backtestbench_binary_successes_then_equal_task_category_fraction_then_earlier"
)


class BacktestBenchBackendError(ValueError):
    """A BacktestBench backend operation violates the campaign contract."""


def _read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise BacktestBenchBackendError(
            f"required file is missing or unsafe: {path.name}"
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BacktestBenchBackendError("expected a JSON object")
    return value


def _zero_accounting(*, wall_time_seconds: float = 0.0) -> dict:
    """Return a zero-cost accounting block for evaluator-only stages."""
    return {
        "provider_requests": 0,
        "completed_requests": 0,
        "logical_requests": 0,
        "provider_retries": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "turns": 0,
        "tool_calls": 0,
        "tool_errors": 0,
        "component_checks": 0,
        "wall_time_seconds": round(wall_time_seconds, 6),
        "provider_cost_usd": 0.0,
        "cost_complete": True,
        "zero_model_requests": True,
    }


def _panel_accounting(panel_result: Mapping) -> dict:
    """Extract Worker cost from a completed panel result."""
    raw = panel_result.get("accounting") or {}
    if not isinstance(raw, Mapping):
        return _zero_accounting()
    return {
        "provider_requests": int(raw.get("provider_requests", 0)),
        "completed_requests": int(raw.get("completed_requests", 0)),
        "logical_requests": int(raw.get("logical_requests", 0)),
        "provider_retries": int(raw.get("provider_retries", 0)),
        "input_tokens": int(raw.get("input_tokens", 0)),
        "output_tokens": int(raw.get("output_tokens", 0)),
        "total_tokens": int(raw.get("total_tokens", 0)),
        "turns": int(raw.get("turns", 0)),
        "tool_calls": int(raw.get("tool_calls", 0)),
        "tool_errors": int(raw.get("tool_errors", 0)),
        "component_checks": 0,
        "wall_time_seconds": float(raw.get("wall_time_seconds", 0.0)),
        "provider_cost_usd": float(raw.get("provider_cost_usd", 0.0))
        if raw.get("cost_complete") is True
        else None,
        "accounted_provider_cost_usd": float(
            raw.get("accounted_provider_cost_usd", raw.get("provider_cost_usd", 0.0))
        ),
        "cost_complete": raw.get("cost_complete") is True,
    }


def _revision_accounting(revision_result: Mapping) -> dict:
    """Extract Evolver cost from a completed revision result."""
    raw = revision_result.get("accounting") or {}
    if not isinstance(raw, Mapping):
        return _zero_accounting()
    return {
        "provider_requests": int(raw.get("provider_requests", raw.get("completed_requests", 0))),
        "completed_requests": int(raw.get("completed_requests", 0)),
        "logical_requests": int(raw.get("logical_requests", 0)),
        "provider_retries": int(raw.get("provider_retries", 0)),
        "input_tokens": int(raw.get("input_tokens", 0)),
        "output_tokens": int(raw.get("output_tokens", 0)),
        "total_tokens": int(raw.get("total_tokens", 0)),
        "turns": int(raw.get("turns", 0)),
        "tool_calls": int(raw.get("tool_calls", 0)),
        "tool_errors": int(raw.get("tool_errors", 0)),
        "component_checks": int(raw.get("component_checks", 0)),
        "wall_time_seconds": float(raw.get("wall_time_seconds", 0.0)),
        "provider_cost_usd": float(raw.get("provider_cost_usd", 0.0))
        if raw.get("cost_complete") is True
        else None,
        "accounted_provider_cost_usd": float(
            raw.get("accounted_provider_cost_usd", raw.get("provider_cost_usd", 0.0))
        ),
        "cost_complete": raw.get("cost_complete") is True,
    }


class BacktestBenchBackend:
    """CampaignBackend adapter for BacktestBench.

    Connects backtestbench_panel and backtestbench_revision to the
    research_campaign CampaignBackend protocol. Handles:
    - run_episode: runs Workers on declared tasks via backtestbench_panel
    - run_evaluation: grades results with the official BacktestBench scorer
    - active_revision_source_available: checks train artifacts are present
    - run_revision: runs one Evolver call via backtestbench_revision

    Config keys:
        config_path: path to the rootless infrastructure config
        evolver_config_path: path to the Evolver model config
        public_root: path to the public BacktestBench task data
        trusted_root: path to the trusted answer store (never sent to Workers)
        worker_image_ref: container image for Worker sandboxes
        evolver_image_ref: container image for Evolver sandbox
        proxy_image_ref: container image for credential proxy
        run_root: base directory for this campaign's artefacts
        concurrency: Worker concurrency (default 4)
        scoring_mode: BacktestBench scoring mode (default "official")
    """

    backend_id: str = "backtestbench"

    def __init__(
        self,
        *,
        config: Mapping[str, object],
        run_root: str | Path,
        condition_id: str,
    ) -> None:
        self.config = dict(config)
        self.run_root = Path(run_root).expanduser().resolve()
        self.condition_id = condition_id
        self.run_root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        value = self.config.get(key)
        if not isinstance(value, str) or not value.strip():
            raise BacktestBenchBackendError(
                f"BacktestBenchBackend config missing required key: {key}"
            )
        return Path(value).expanduser().resolve()

    def _grade_panel_result(
        self, panel_result: Mapping, task_ids: Sequence[str]
    ) -> dict[str, TaskMetric]:
        """Grade all scored tasks in a completed panel result."""
        tasks_data = panel_result.get("tasks", {})
        if not isinstance(tasks_data, Mapping):
            raise BacktestBenchBackendError(
                "panel result has no tasks mapping"
            )
        metrics: dict[str, TaskMetric] = {}
        for task_id in task_ids:
            cell = tasks_data.get(task_id)
            if not isinstance(cell, Mapping):
                continue  # unscored — caller handles missing
            result = cell.get("result")
            if not isinstance(result, Mapping):
                continue
            if result.get("status") != "scored":
                continue
            reward = result.get("reward")
            if reward not in {0, 0.0, 1, 1.0}:
                continue
            score = result.get("official_evaluation") or {}
            passed = int(score.get("passed", 0))
            failed = int(score.get("failed", 0))
            errors = int(score.get("errors", 0))
            skipped = int(score.get("skipped", 0))
            total = passed + failed + errors + skipped
            # Category breakdown for BacktestBench (one category per task)
            task_record = cell.get("public_task", {})
            category = str(
                task_record.get("strategy_type", task_record.get("category", "unknown"))
            )
            families = {category: {
                "passed": passed, "failed": failed,
                "errors": errors, "skipped": skipped, "total": total,
            }}
            metrics[task_id] = TaskMetric(
                task_id=task_id,
                binary_reward=int(reward),
                passed=passed,
                failed=failed,
                errors=errors,
                skipped=skipped,
                total=max(total, 1),  # avoid zero-division in selection key
                contract_adjusted=False,
                zero_model_requests=True,
                result_uri=(
                    self.run_root
                    / "panels"
                    / f"{task_id}.json"
                ).as_posix(),
                families=families,
            )
        return metrics

    def _selection_projection(
        self,
        metrics: Mapping[str, TaskMetric],
        task_ids: Sequence[str],
    ) -> tuple[str, tuple[tuple[int, int], ...], dict[str, object]]:
        """Compute BacktestBench selection key: binary_successes then equal mean."""
        selected = tuple(metrics[task_id] for task_id in task_ids)
        binary_successes = sum(m.binary_reward for m in selected)
        equal_mean = sum(
            (Fraction(m.passed, m.total) for m in selected), Fraction()
        ) / len(selected)
        summary: dict[str, object] = {
            "binary_successes": binary_successes,
            "task_count": len(selected),
            "equal_task_mean": {
                "numerator": equal_mean.numerator,
                "denominator": equal_mean.denominator,
                "decimal": float(equal_mean),
            },
            "per_task": {
                m.task_id: {
                    "binary_reward": m.binary_reward,
                    "passed": m.passed,
                    "total": m.total,
                }
                for m in selected
            },
        }
        key: tuple[tuple[int, int], ...] = (
            (binary_successes, len(selected)),
            (equal_mean.numerator, equal_mean.denominator),
        )
        return _SELECTION_POLICY, key, summary

    # ------------------------------------------------------------------
    # CampaignBackend protocol
    # ------------------------------------------------------------------

    def run_episode(self, request: EpisodeRequest) -> EpisodeEvidence:
        """Run a BacktestBench Worker panel for the declared task set."""
        worker = Path(request.harness.artifact_uri).expanduser().resolve()
        panel_root = (
            self.run_root / "episodes" / request.stage_id
        )
        result_path = panel_root / EPISODE_FILE
        request_payload = {
            "campaign_id": request.campaign_id,
            "stage_id": request.stage_id,
            "backend_id": request.backend_id,
            "harness_id": request.harness.harness_id,
            "task_ids": list(request.task_ids),
            "purpose": request.purpose,
            "frozen": request.frozen,
        }

        if result_path.exists() and not result_path.is_symlink():
            retained = _read_object(result_path, label="BacktestBench episode")
            if retained.get("request") != request_payload:
                raise ResearchCampaignError(
                    "retained BacktestBench episode request differs"
                )
            return _episode_from_record(retained["episode"])

        panel_run_dir = panel_root / "panel"
        run_backtestbench_panel(
            config_path=self._path("config_path"),
            public_root=self._path("public_root"),
            trusted_root=self._path("trusted_root"),
            run_dir=panel_run_dir,
            worker_dir=worker,
            task_ids=list(request.task_ids),
            worker_image_ref=_text(
                self.config.get("worker_image_ref"), label="worker_image_ref"
            ),
            proxy_image_ref=_text(
                self.config.get("proxy_image_ref"), label="proxy_image_ref"
            ),
            concurrency=int(self.config.get("concurrency", 4)),
            scoring_mode=str(self.config.get("scoring_mode", "official")),
        )

        panel_result = _read(panel_run_dir / PANEL_RESULT_FILE)
        panel_status = panel_result.get("status", "")
        scored_tasks = [
            task_id
            for task_id in request.task_ids
            if isinstance(panel_result.get("tasks", {}).get(task_id), Mapping)
            and panel_result["tasks"][task_id].get("result", {}).get("status")
            == "scored"
        ]
        missing = [t for t in request.task_ids if t not in scored_tasks]
        status = "complete" if not missing else "partial"
        cells = {
            task_id: {
                "native": panel_result.get("tasks", {}).get(task_id, {}),
            }
            for task_id in request.task_ids
        }
        failure = (
            {
                "kind": "backtestbench_panel_partial",
                "missing_task_ids": missing,
                "panel_status": panel_status,
            }
            if missing
            else None
        )
        episode = EpisodeEvidence(
            stage_id=request.stage_id,
            backend_id=self.backend_id,
            harness=request.harness,
            task_ids=request.task_ids,
            condition_id=self.condition_id,
            status=status,
            cells=cells,
            accounting=_panel_accounting(panel_result),
            result_uri=result_path.as_posix(),
            failure=failure,
        )
        _write_or_reuse(
            result_path,
            {
                "schema_version": 1,
                "protocol": _PROTOCOL_EPISODE,
                "request": request_payload,
                "panel_run_dir": panel_run_dir.as_posix(),
                "episode": asdict(episode),
            },
            label="BacktestBench episode evidence",
        )
        return episode

    def run_evaluation(self, request: EvaluationRequest) -> OfficialEvaluation:
        """Grade a BacktestBench episode using official panel results."""
        if request.backend_id != self.backend_id:
            raise ResearchCampaignError(
                "BacktestBench evaluation requires a BacktestBench episode"
            )
        root = self.run_root / "evaluations" / request.stage_id
        result_path = root / EVALUATION_FILE
        request_payload = {
            "campaign_id": request.campaign_id,
            "stage_id": request.stage_id,
            "backend_id": request.backend_id,
            "episode_stage_id": request.episode.stage_id,
            "harness_id": request.episode.harness.harness_id,
            "task_ids": list(request.episode.task_ids),
            "condition_id": request.episode.condition_id,
        }
        if result_path.exists() and not result_path.is_symlink():
            retained = _read_object(result_path, label="BacktestBench evaluation")
            if retained.get("request") != request_payload:
                raise ResearchCampaignError(
                    "retained BacktestBench evaluation request differs"
                )
            return _evaluation_from_record(retained["evaluation"])

        started = time.perf_counter()
        # Recover panel result from the episode's stored panel_run_dir.
        episode_result_path = Path(request.episode.result_uri).expanduser()
        episode_record = _read_object(
            episode_result_path, label="BacktestBench episode for evaluation"
        )
        panel_run_dir = Path(
            str(episode_record.get("panel_run_dir", ""))
        ).expanduser().resolve()
        panel_result = _read(panel_run_dir / PANEL_RESULT_FILE)
        metrics = self._grade_panel_result(panel_result, request.episode.task_ids)
        missing_tasks = [
            t for t in request.episode.task_ids if t not in metrics
        ]

        if missing_tasks:
            selection_key: tuple[tuple[int, int], ...] = ()
            selection_summary: dict[str, object] = {
                "selectable": False,
                "full_window_measurement_complete": False,
                "declared_task_ids": list(request.episode.task_ids),
                "scored_task_ids": list(metrics),
                "missing_task_ids": missing_tasks,
                "missing_official_metrics": {t: None for t in missing_tasks},
            }
            status = "partial"
            failure: dict | None = {
                "kind": "backtestbench_evaluation_partial_coverage",
                "missing_task_ids": missing_tasks,
            }
            policy = _SELECTION_POLICY
        else:
            policy, selection_key, selection_summary = self._selection_projection(
                metrics, request.episode.task_ids
            )
            selection_summary = {
                **selection_summary,
                "selectable": True,
                "full_window_measurement_complete": True,
                "declared_task_ids": list(request.episode.task_ids),
                "scored_task_ids": list(request.episode.task_ids),
                "missing_task_ids": [],
                "missing_official_metrics": {},
            }
            status = "complete"
            failure = None

        evaluation = OfficialEvaluation(
            stage_id=request.stage_id,
            backend_id=self.backend_id,
            harness=request.episode.harness,
            episode_stage_id=request.episode.stage_id,
            task_ids=request.episode.task_ids,
            condition_id=request.episode.condition_id,
            status=status,
            metrics={task_id: asdict(m) for task_id, m in metrics.items()},
            selection_policy=policy,
            selection_key=selection_key,
            selection_summary=selection_summary,
            accounting=_zero_accounting(
                wall_time_seconds=time.perf_counter() - started
            ),
            result_uri=result_path.as_posix(),
            failure=failure,
        )
        root.mkdir(parents=True, exist_ok=True)
        _write_or_reuse(
            result_path,
            {
                "schema_version": 1,
                "protocol": _PROTOCOL_EVALUATION,
                "request": request_payload,
                "evaluation": asdict(evaluation),
            },
            label="BacktestBench official evaluation",
        )
        return evaluation

    def active_revision_source_available(
        self,
        *,
        episode: EpisodeEvidence,
        evaluation: OfficialEvaluation,
        task_id: str,
        parent_harness: HarnessRef,
    ) -> bool:
        """Return True when the active task's train artifacts are present."""
        if task_id not in episode.task_ids:
            return False
        cell = episode.cells.get(task_id)
        if not isinstance(cell, Mapping):
            return False
        native = cell.get("native", {})
        if not isinstance(native, Mapping):
            return False
        # Need a delivered, scored Worker result to build revision evidence.
        result = native.get("result", {})
        if not isinstance(result, Mapping):
            return False
        return (
            result.get("status") == "scored"
            and result.get("reward") in {0, 0.0, 1, 1.0}
        )

    def run_revision(self, request: RevisionRequest) -> RevisionOutcome:
        """Run one BacktestBench Evolver call on the active task."""
        if request.backend_id != self.backend_id:
            raise ResearchCampaignError(
                "BacktestBench revision requires a BacktestBench backend"
            )
        revision_root = (
            self.run_root / "revisions" / request.stage_id
        )
        result_path = revision_root / REVISION_RESULT_FILE
        request_payload = {
            "campaign_id": request.campaign_id,
            "stage_id": request.stage_id,
            "backend_id": request.backend_id,
            "parent_harness_id": request.parent_harness.harness_id,
            "active_task_id": request.active_task_id,
        }

        if result_path.exists() and not result_path.is_symlink():
            retained = _read_object(result_path, label="BacktestBench revision")
            if retained.get("request") != request_payload:
                raise ResearchCampaignError(
                    "retained BacktestBench revision request differs"
                )
            return _revision_outcome_from_record(
                retained, request.parent_harness
            )

        # Recover panel run dir from the parent episode.
        parent_episode = request.parent_episode
        episode_record = _read_object(
            Path(parent_episode.result_uri).expanduser(),
            label="BacktestBench parent episode for revision",
        )
        panel_run_dir = Path(
            str(episode_record.get("panel_run_dir", ""))
        ).expanduser().resolve()

        # Train tasks = comparison window tasks.
        evidence_task_ids = list(request.parent_episode.task_ids)
        worker_dir = Path(
            request.parent_harness.artifact_uri
        ).expanduser().resolve()

        # Research memory: use latest retained if available.
        memory_path: Path
        if request.research_memory is not None:
            memory_path = Path(
                request.research_memory.artifact_uri
            ).expanduser().resolve()
        else:
            # Fall back to initial empty memory snapshot next to worker.
            memory_path = worker_dir / "memory" / "research-operation-memory.json"
            if not memory_path.exists():
                memory_path.parent.mkdir(parents=True, exist_ok=True)
                memory_path.write_text(
                    '{"schema_version": 1, "operations": [], "experiences": []}',
                    encoding="utf-8",
                )

        revision_result = run_backtestbench_revision(
            config_path=self._path("config_path"),
            evolver_config_path=self._path("evolver_config_path"),
            panel_run_dir=panel_run_dir,
            revision_run_dir=revision_root,
            worker_dir=worker_dir,
            active_task_id=request.active_task_id,
            evidence_task_ids=evidence_task_ids,
            research_memory_path=memory_path,
            evolver_image_ref=_text(
                self.config.get("evolver_image_ref"), label="evolver_image_ref"
            ),
            proxy_image_ref=_text(
                self.config.get("proxy_image_ref"), label="proxy_image_ref"
            ),
        )

        outcome = _revision_outcome_from_record(
            revision_result, request.parent_harness
        )
        _write_or_reuse(
            result_path,
            {
                "schema_version": 1,
                "protocol": _PROTOCOL_REVISION,
                "request": request_payload,
                **revision_result,
            },
            label="BacktestBench revision result",
        )
        return outcome


# ------------------------------------------------------------------
# Internal record → dataclass converters
# ------------------------------------------------------------------

def _episode_from_record(record: Mapping) -> EpisodeEvidence:
    return EpisodeEvidence(
        stage_id=_text(record.get("stage_id"), label="episode stage_id"),
        backend_id=_text(record.get("backend_id"), label="episode backend_id"),
        harness=HarnessRef(
            harness_id=_text(
                record.get("harness", {}).get("harness_id"),
                label="episode harness_id",
            ),
            artifact_uri=_text(
                record.get("harness", {}).get("artifact_uri"),
                label="episode artifact_uri",
            ),
            revision_uri=record.get("harness", {}).get("revision_uri"),
            worker_role=str(
                record.get("harness", {}).get("worker_role", "candidate")
            ),
        ),
        task_ids=tuple(record.get("task_ids", [])),
        condition_id=_text(record.get("condition_id"), label="episode condition_id"),
        status=_text(record.get("status"), label="episode status"),
        cells=dict(record.get("cells", {})),
        accounting=dict(record.get("accounting", {})),
        result_uri=_text(record.get("result_uri"), label="episode result_uri"),
        failure=record.get("failure") if isinstance(record.get("failure"), Mapping) else None,
    )


def _evaluation_from_record(record: Mapping) -> OfficialEvaluation:
    raw_key = record.get("selection_key") or []
    selection_key: tuple[tuple[int, int], ...] = tuple(
        tuple(component) for component in raw_key  # type: ignore[misc]
    )
    return OfficialEvaluation(
        stage_id=_text(record.get("stage_id"), label="evaluation stage_id"),
        backend_id=_text(record.get("backend_id"), label="evaluation backend_id"),
        harness=HarnessRef(
            harness_id=_text(
                record.get("harness", {}).get("harness_id"),
                label="evaluation harness_id",
            ),
            artifact_uri=_text(
                record.get("harness", {}).get("artifact_uri"),
                label="evaluation artifact_uri",
            ),
            revision_uri=record.get("harness", {}).get("revision_uri"),
            worker_role=str(
                record.get("harness", {}).get("worker_role", "candidate")
            ),
        ),
        episode_stage_id=_text(
            record.get("episode_stage_id"), label="evaluation episode_stage_id"
        ),
        task_ids=tuple(record.get("task_ids", [])),
        condition_id=_text(record.get("condition_id"), label="evaluation condition_id"),
        status=_text(record.get("status"), label="evaluation status"),
        metrics=dict(record.get("metrics", {})),
        selection_policy=_text(
            record.get("selection_policy"), label="evaluation selection_policy"
        ),
        selection_key=selection_key,
        selection_summary=dict(record.get("selection_summary", {})),
        accounting=dict(record.get("accounting", {})),
        result_uri=_text(record.get("result_uri"), label="evaluation result_uri"),
        failure=record.get("failure") if isinstance(record.get("failure"), Mapping) else None,
    )


def _revision_outcome_from_record(
    record: Mapping, parent_harness: HarnessRef
) -> RevisionOutcome:
    """Convert a backtestbench_revision result dict to a RevisionOutcome."""
    decision = record.get("decision")
    stage_id = _text(record.get("stage_id", record.get("revision_run_id", "")), label="revision stage_id")
    backend_id = "backtestbench"
    status = str(record.get("status", "complete"))

    candidate_harness: HarnessRef | None = None
    if decision == "ACT":
        candidate_dir = record.get("candidate_dir") or record.get(
            "prepared", {}
        ).get("candidate_dir")
        if isinstance(candidate_dir, str) and candidate_dir:
            from .worker_identity import hash_worker_directory as _hash_dir

            candidate_hash = _hash_dir(Path(candidate_dir))
            candidate_harness = HarnessRef(
                harness_id=candidate_hash,
                artifact_uri=candidate_dir,
                revision_uri=str(
                    Path(candidate_dir).parent / REVISION_RESULT_FILE
                ),
                worker_role="candidate",
            )

    retained_memory: object = None
    memory_path = record.get("research_memory_result_path")
    if isinstance(memory_path, str) and memory_path:
        from .research_campaign import MemoryRef

        retained_memory = MemoryRef(
            artifact_uri=memory_path,
            source_stage_id=stage_id,
        )

    return RevisionOutcome(
        stage_id=stage_id,
        backend_id=backend_id,
        parent_harness=parent_harness,
        status=status,
        decision=decision,
        candidate_harness=candidate_harness,
        retained_memory=retained_memory,  # type: ignore[arg-type]
        accounting=_revision_accounting(record),
        result_uri=str(record.get("result_uri", "")),
        component_checks=tuple(record.get("component_checks", [])),
        public_probe_refs=tuple(record.get("public_probe_refs", [])),
        failure=record.get("failure") if isinstance(record.get("failure"), Mapping) else None,
    )
