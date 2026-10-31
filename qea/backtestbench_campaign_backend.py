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

import hashlib
import json
import os
import time
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Mapping, Sequence

from .backtestbench_panel import (
    RESULT_FILE as PANEL_RESULT_FILE,
    run_backtestbench_panel,
)
from .backtestbench_revision import (
    RESULT_FILE as REVISION_RESULT_FILE,
    run_backtestbench_revision,
)
from .worker_identity import hash_worker_directory, is_worker_content_digest
from .research_operation_memory import (
    empty_research_operation_memory, load_research_operation_memory,
)
from .research_campaign import (
    EpisodeEvidence,
    EpisodeRequest,
    EvaluationRequest,
    HarnessRef,
    MemoryRef,
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
    EVIDENCE_RECORD_PROTOCOL,
)


CAMPAIGN_REVISION_FILE = "CAMPAIGN-REVISION-EVIDENCE.json"

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
    """Project native summary and sealed per-attempt cost; unknown stays unknown."""
    summary = panel_result.get("summary") or {}
    tasks = panel_result.get("tasks") or {}
    costs = [((cell.get("result") or {}).get("proxy_cost") or {})
             for cell in tasks.values()]
    def complete_sum(field):
        values = [cost.get(field) for cost in costs]
        if not values or any(type(v) not in (int, float) for v in values):
            return None
        if any(cost.get("cost_complete") is not True for cost in costs):
            return None
        return sum(values)
    return {
        "provider_requests": summary.get("request_count"),
        "completed_requests": complete_sum("completed_request_count"),
        "logical_requests": None,
        "provider_retries": None,
        "input_tokens": complete_sum("input_tokens"),
        "output_tokens": complete_sum("output_tokens"),
        "total_tokens": complete_sum("total_tokens"),
        "turns": None, "tool_calls": None, "tool_errors": None,
        "component_checks": 0, "wall_time_seconds": None,
        "provider_cost_usd": (summary.get("provider_cost_usd")
                              if summary.get("cost_complete") is True else None),
        "accounted_provider_cost_usd": summary.get("known_provider_cost_usd"),
        "cost_complete": summary.get("cost_complete") is True,
    }


def _revision_accounting(revision_result: Mapping) -> dict:
    """Keep native accounting, including nullable fields and completeness flags."""
    raw = revision_result.get("accounting")
    if not isinstance(raw, Mapping):
        return {"provider_cost_usd": None, "cost_complete": False}
    return _json_copy(dict(raw), label="BacktestBench revision accounting")


def _retained_artifact(root: Path, uri: object) -> Path:
    value = _text(uri, label="native retained artifact")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise BacktestBenchBackendError("native artifact must be retained inside revision")
    path = root / relative
    if any((root / Path(*relative.parts[:i])).is_symlink()
           for i in range(1, len(relative.parts) + 1)):
        raise BacktestBenchBackendError("native artifact contains a symlink")
    if not path.exists():
        raise BacktestBenchBackendError(f"native artifact is missing: {value}")
    return path.resolve()


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

    def _context(self) -> dict:
        config = _json_copy(self.config, label="BacktestBench runtime config")
        hashes = {key: hashlib.sha256(self._path(key).read_bytes()).hexdigest()
                  for key in ("config_path", "evolver_config_path")}
        package = Path(__file__).parent
        source_paths = (
            "backtestbench_campaign_backend.py", "backtestbench_panel.py", "backtestbench_revision.py",
            "research_campaign.py", "campaign_continuation.py", "backtestbench_continuation_review.py",
            "backtestbench_review_continuation.py",
            "continuation_reviewer/tools.py", "continuation_reviewer/middleware.py",
            "continuation_reviewer/submit_review.tool.yaml",
            "backtestbench_research_index.py", "evolve_agent_full/tools/guarded_workspace.py",
            "evolve_agent_full/profiles/early_intervention_full_harness_v1/systemprompt.md",
            "evolve_agent_full/profiles/early_intervention_full_harness_v1/agent.yaml",
            "evolve_agent_full/profiles/early_intervention_full_harness_v1/tool_descriptions/search_research_units.tool.yaml",
            "evolve_agent_full/profiles/early_intervention_full_harness_v1/tool_descriptions/execute_public_artifact_probe.tool.yaml",
            "evolve_agent_full/profiles/intervention_directed_full_harness_v1/tool_descriptions/smoke_candidate_component.tool.yaml",
        )
        context = {"condition_id": self.condition_id, "config": config,
                   "config_content_sha256": hashes,
                   "runtime_source_sha256": {name:hashlib.sha256((package/name).read_bytes()).hexdigest()
                                             for name in source_paths}}
        _write_or_reuse(self.run_root / "BACKEND-CONTEXT.json", context,
                        label="BacktestBench campaign-wide runtime binding")
        return context

    def _stage_root(self, kind: str, stage_id: str) -> Path:
        if Path(stage_id).name != stage_id or stage_id in {".", "..", ""}:
            raise BacktestBenchBackendError("stage_id must be a single safe path component")
        root = self.run_root / kind / stage_id
        if root.is_symlink() or root.parent.is_symlink():
            raise BacktestBenchBackendError("campaign stage root is unsafe")
        return root

    def _bind_request(self, root: Path, payload: Mapping) -> None:
        root.mkdir(parents=True, exist_ok=True)
        _write_or_reuse(root / "CAMPAIGN-REQUEST.json", payload,
                        label="BacktestBench native request binding")

    @staticmethod
    def _harness_digest(harness: HarnessRef) -> str:
        digest = hash_worker_directory(harness.artifact_uri)
        # Native legacy harness IDs can be names; SHA identities must match bytes.
        if is_worker_content_digest(harness.harness_id) and harness.harness_id != digest:
            raise BacktestBenchBackendError("harness content differs from declared digest")
        return digest

    def _evidence_record(self, *, cell: Mapping, panel_root: Path, stage_id: str, task_id: str):
        execution = (cell.get("result") or {}).get("worker_execution")
        attempt_id = (cell.get("attempt") or {}).get("attempt_id")
        if not isinstance(execution, Mapping) or not isinstance(attempt_id, str):
            return None
        if Path(attempt_id).name != attempt_id or Path(task_id).name != task_id:
            raise BacktestBenchBackendError("unsafe native task or attempt identity")
        attempt_root = panel_root / "attempts" / attempt_id
        if not (attempt_root / "worker-execution.json").is_file():
            return None
        projection = panel_root / "campaign-evidence" / task_id
        _write_or_reuse(projection / "process-summary.json", execution.get("summary") or {}, label="Worker process summary")
        _write_or_reuse(projection / "artifact-manifest.json", {"artifacts":execution.get("artifacts") or []}, label="Worker artifact manifest")
        members = {
            "attempt_identity": attempt_root / "attempt.json",
            "artifact_root": attempt_root / "artifacts",
            "artifact_manifest": projection / "artifact-manifest.json",
            "public_data": self._path("public_root") / "tasks" / task_id / "environment/data",
            "worker_trace": attempt_root / "raw-trace.jsonl",
            "worker_final": attempt_root / "final.txt",
            "process_summary": projection / "process-summary.json",
        }
        if any(not path.exists() or path.is_symlink() for path in members.values()):
            raise BacktestBenchBackendError("delivered Worker evidence member is unavailable")
        return {
            "schema_version":1, "protocol":EVIDENCE_RECORD_PROTOCOL, "backend_id":self.backend_id,
            "task_id":task_id, "stage_id":stage_id,
            "root_uri":os.path.commonpath([str(path) for path in members.values()]),
            "members":{name:str(path) for name,path in members.items()},
            "public_probe_refs":["artifact_root","public_data"], "official_evaluation_included":False,
        }

    def _grade_panel_result(
        self, panel_result: Mapping, task_ids: Sequence[str], *, result_uri: str
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
            if (score.get("scored") is not True or score.get("reward") != reward
                    or result.get("failure") is not None):
                continue
            # Campaign comparison uses a one-decision projection, not native test counts.
            passed, failed = int(reward), 1 - int(reward)
            errors, skipped, total = 0, 0, 1
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
                total=total,
                contract_adjusted=False,
                zero_model_requests=True,
                result_uri=result_uri,
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
            "metric_projection": "one_official_binary_task_decision_not_native_test_counts",
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
        if request.backend_id != self.backend_id:
            raise ResearchCampaignError("BacktestBench episode backend differs")
        digest = self._harness_digest(request.harness)
        panel_root = self._stage_root("episodes", request.stage_id)
        result_path = panel_root / EPISODE_FILE
        request_payload = {
            "campaign_id": request.campaign_id,
            "stage_id": request.stage_id,
            "backend_id": request.backend_id,
            "harness": asdict(request.harness),
            "harness_digest": digest,
            "context": self._context(),
            "task_ids": list(request.task_ids),
            "purpose": request.purpose,
            "frozen": request.frozen,
        }

        if result_path.exists() or result_path.is_symlink():
            retained = _read_object(result_path, label="BacktestBench episode")
            if retained.get("request") != request_payload:
                raise ResearchCampaignError(
                    "retained BacktestBench episode request differs"
                )
            return _episode_from_record(retained["episode"])

        self._bind_request(panel_root, request_payload)
        panel_run_dir = panel_root / (request.stage_id + "-panel")
        run_backtestbench_panel(
            config_path=self._path("config_path"),
            public_root=self._path("public_root"),
            trusted_root=self._path("trusted_root"),
            run_dir=panel_run_dir,
            worker_dir=worker,
            task_ids=list(request.task_ids),
            benchmark_commit=_text(self.config.get("benchmark_commit"), label="benchmark_commit"),
            harness_id=request.harness.harness_id,
            split="evaluation" if request.frozen else "development",
            checkpoint=request.purpose,
            worker_timeout_seconds=self.config.get("worker_timeout_seconds"),
            worker_image_ref=_text(
                self.config.get("worker_image_ref"), label="worker_image_ref"
            ),
            proxy_image_ref=_text(
                self.config.get("proxy_image_ref"), label="proxy_image_ref"
            ),
            concurrency=int(self.config.get("concurrency", 4)),
            scoring_mode=str(self.config.get("scoring_mode", "official")),
        )

        if self._harness_digest(request.harness) != digest:
            raise BacktestBenchBackendError("Worker panel changed its parent harness")
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
                "evidence_record": self._evidence_record(
                    cell=panel_result.get("tasks", {}).get(task_id, {}), panel_root=panel_run_dir,
                    stage_id=request.stage_id, task_id=task_id,
                ),
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
        root = self._stage_root("evaluations", request.stage_id)
        result_path = root / EVALUATION_FILE
        request_payload = {
            "campaign_id": request.campaign_id,
            "stage_id": request.stage_id,
            "backend_id": request.backend_id,
            "episode": asdict(request.episode),
            "context": self._context(),
            "episode_stage_id": request.episode.stage_id,
            "harness_id": request.episode.harness.harness_id,
            "task_ids": list(request.episode.task_ids),
            "condition_id": request.episode.condition_id,
        }
        request_payload = _json_copy(request_payload, label="BacktestBench evaluation request")
        if result_path.exists() or result_path.is_symlink():
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
        metrics = self._grade_panel_result(
            panel_result, request.episode.task_ids,
            result_uri=(panel_run_dir / PANEL_RESULT_FILE).as_posix(),
        )
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
        if (task_id not in episode.task_ids or episode.harness != parent_harness
                or evaluation.harness != parent_harness
                or evaluation.episode_stage_id != episode.stage_id
                or evaluation.task_ids != episode.task_ids
                or episode.backend_id != self.backend_id
                or evaluation.backend_id != self.backend_id
                or episode.condition_id != self.condition_id
                or evaluation.condition_id != self.condition_id):
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
            and native.get("public_task", {}).get("source_split") == "train"
            and isinstance(result.get("worker_execution"), Mapping)
        )

    def record_development_pair(self, request: Mapping) -> dict:
        """Index a measured pair even when its selection review is deferred."""
        from .backtestbench_research_index import ingest_development_pair
        self._context()
        return ingest_development_pair(self.run_root / "research-index", request)

    def run_continuation_review(self, request: Mapping) -> dict:
        from .campaign_continuation import run_durable_review
        from .backtestbench_continuation_review import execute_review, prepare_review_input
        indexed = self.record_development_pair(request.get("current_pair", request))
        prepared = self.run_root / "research-index/objects" / indexed["pair_id"]
        root = self._stage_root("reviews", str(request["stage_id"]))
        self._bind_request(root, {"request": request, "context": self._context()})
        if "selection_window" in request or "prior_incomplete_review" in request:
            prepared = root / "selection-window-input"
            prepare_review_input(request, prepared)
        return run_durable_review(
            root=root, request=request,
            execute=lambda payload, directory: execute_review(payload, directory, config=self.config, prepared_input=prepared),
        )

    def run_revision(self, request: RevisionRequest) -> RevisionOutcome:
        """Run one BacktestBench Evolver call on the active task."""
        if request.backend_id != self.backend_id:
            raise ResearchCampaignError(
                "BacktestBench revision requires a BacktestBench backend"
            )
        if not self.active_revision_source_available(
            episode=request.parent_episode, evaluation=request.parent_evaluation,
            task_id=request.active_task_id, parent_harness=request.parent_harness,
        ):
            raise ResearchCampaignError("BacktestBench active source lacks matched train evidence")
        iteration = request.options.get("iteration", 1)
        if type(iteration) is not int or iteration < 1:
            raise ResearchCampaignError("BacktestBench iteration must be positive")
        if request.seed_related_completed_rounds:
            raise ResearchCampaignError("external seed rounds require explicit research-index ingestion")
        if request.related_completed_round and not (self.run_root / "research-index/RESEARCH-UNIT-INDEX.json").is_file():
            raise ResearchCampaignError("completed round has not entered the original research index")
        digest = self._harness_digest(request.parent_harness)
        revision_root = self._stage_root("revisions", request.stage_id)
        result_path = revision_root / CAMPAIGN_REVISION_FILE
        if request.research_memory is not None:
            memory_path = Path(request.research_memory.artifact_uri).expanduser().resolve()
        else:
            memory_path = revision_root / "campaign-inputs" / "research-memory.json"
            _write_or_reuse(memory_path, empty_research_operation_memory(),
                            label="initial external research memory")
        load_research_operation_memory(memory_path)
        request_payload = {
            "request": asdict(request), "context": self._context(),
            "parent_content_sha256": digest,
            "memory_content_sha256": hashlib.sha256(memory_path.read_bytes()).hexdigest(),
        }
        request_payload = _json_copy(request_payload, label="BacktestBench revision request")
        self._bind_request(revision_root, request_payload)
        if result_path.exists() or result_path.is_symlink():
            retained = _read_object(result_path, label="BacktestBench revision")
            if retained.get("request") != request_payload:
                raise ResearchCampaignError("retained BacktestBench revision request differs")
            outcome = _revision_outcome_from_record(
                _read(revision_root / REVISION_RESULT_FILE), request.parent_harness,
                root=revision_root, stage_id=request.stage_id,
            )
            if _json_copy(asdict(outcome), label="outcome") != retained.get("outcome"):
                raise ResearchCampaignError("retained BacktestBench revision artifacts changed")
            return outcome

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

        option_names = {
            "completed_pair", "readable_trace_task_ids", "selected_research_units",
            "training_scalar_supervision_path", "continuation_context",
            "memory_index_mode", "candidate_components",
        }
        native_options = {key: request.options[key] for key in option_names
                          if request.options.get(key) is not None}

        index_root = self.run_root / "research-index"
        if (index_root / "RESEARCH-UNIT-INDEX.json").is_file():
            native_options["research_index_path"] = index_root
        revision_result = run_backtestbench_revision(
            config_path=self._path("config_path"),
            evolver_config_path=self._path("evolver_config_path"),
            panel_run_dir=panel_run_dir,
            revision_run_dir=revision_root,
            worker_dir=worker_dir,
            active_task_id=request.active_task_id,
            evidence_task_ids=evidence_task_ids,
            iteration=iteration,
            **native_options,
            research_memory_path=memory_path,
            evolver_image_ref=_text(
                self.config.get("evolver_image_ref"), label="evolver_image_ref"
            ),
            proxy_image_ref=_text(
                self.config.get("proxy_image_ref"), label="proxy_image_ref"
            ),
        )

        if self._harness_digest(request.parent_harness) != digest:
            raise BacktestBenchBackendError("Evolver changed its parent harness")
        outcome = _revision_outcome_from_record(
            revision_result, request.parent_harness,
            root=revision_root, stage_id=request.stage_id,
        )
        _write_or_reuse(
            result_path,
            {
                "schema_version": 1,
                "protocol": _PROTOCOL_REVISION,
                "request": request_payload,
                "native_result_uri": (revision_root / REVISION_RESULT_FILE).as_posix(),
                "outcome": asdict(outcome),
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
    record: Mapping, parent_harness: HarnessRef, *, root: Path, stage_id: str,
) -> RevisionOutcome:
    """Resolve native receipt paths and qualify the complete returned H and R."""
    if record.get("run_id") != root.name:
        raise BacktestBenchBackendError("native revision run identity differs")
    qualification = record.get("qualification") or {}
    decision_payload = qualification.get("decision") or {}
    decision = decision_payload.get("decision")
    status = _text(record.get("status"), label="native revision status")
    candidate = None
    if status == "revised_unscored":
        if (decision != "ACT" or qualification.get("status") != status
                or record.get("failure") is not None):
            raise BacktestBenchBackendError("native revised result is inconsistent")
        candidate_dir = _retained_artifact(root, (record.get("candidate_harness") or {}).get("artifact_uri"))
        candidate = HarnessRef(
            harness_id=hash_worker_directory(candidate_dir),
            artifact_uri=candidate_dir.as_posix(),
            revision_uri=(root / REVISION_RESULT_FILE).as_posix(),
            worker_role="candidate",
        )
    retained_memory = None
    memory = record.get("research_memory")
    if isinstance(memory, Mapping):
        memory_path = _retained_artifact(root, memory.get("artifact_uri"))
        load_research_operation_memory(memory_path)
        retained_memory = MemoryRef(artifact_uri=memory_path.as_posix(), source_stage_id=stage_id)
    return RevisionOutcome(
        stage_id=stage_id, backend_id="backtestbench", parent_harness=parent_harness,
        status=status, decision=decision, candidate_harness=candidate,
        retained_memory=retained_memory, accounting=_revision_accounting(record),
        result_uri=(root / REVISION_RESULT_FILE).as_posix(),
        component_checks=tuple(qualification.get("component_tests") or ()),
        public_probe_refs=tuple(record.get("public_probe_refs") or ()),
        failure=record.get("failure") if isinstance(record.get("failure"), Mapping) else None,
    )
