#!/usr/bin/env python3
"""Run one official-provider QFBench canary for V4 Flash 0731."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
from pathlib import Path

from qea.benchmarks.qfbench import load_qfbench_baseline_snapshot
from qea.qfbench_baseline import audit_baseline_proxy_costs
from qea.rootless_full_harness import (
    build_rootless_full_harness_runtime,
    load_rootless_full_harness_config,
    rootless_model_route_identity,
)


MODEL = "deepseek/deepseek-v4-flash-0731"
CANONICAL_MODEL = "deepseek/deepseek-v4-flash-20260731"
PROVIDER = "deepseek"
GENERATION_ENDPOINT = "https://openrouter.ai/api/v1/generation"


def private_json(path: Path, payload: object) -> None:
    """Atomically write an owner-only JSON artifact."""

    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, sort_keys=True, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def validate_generation_route(*, provider: object, model: object) -> None:
    """Require the official provider and the exact 0731 model identity."""

    if not isinstance(provider, str) or provider.casefold() != PROVIDER:
        raise RuntimeError(f"unexpected provider metadata: {provider!r}")
    if model not in {MODEL, CANONICAL_MODEL}:
        raise RuntimeError(f"unexpected model metadata: {model!r}")


def completed_generation_ids(run_dir: Path) -> tuple[str, ...]:
    """Return unique IDs for completed, successful proxy calls only."""

    identifiers = []
    for audit in sorted((run_dir / "attempts").glob("*/proxy-audit.jsonl")):
        for line in audit.read_text().splitlines():
            record = json.loads(line)
            if record.get("request_state") != "completed":
                raise RuntimeError(f"non-completed proxy record: {audit}")
            if record.get("upstream_status_code") != 200:
                raise RuntimeError(f"non-200 proxy record: {audit}")
            value = record.get("provider_request_id")
            if not isinstance(value, str) or not value:
                raise RuntimeError("completed call has no OpenRouter generation ID")
            identifiers.append(value)
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise RuntimeError("generation IDs are empty or duplicated")
    return tuple(identifiers)


def generation_metadata(generation_id: str, token: str) -> dict[str, object]:
    """Fetch and validate one OpenRouter generation-routing record."""

    url = GENERATION_ENDPOINT + "?" + urllib.parse.urlencode({"id": generation_id})
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    last_error = None
    for delay in (0, 2, 4, 8, 12):
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read())
            data = payload.get("data")
            if not isinstance(data, dict):
                raise RuntimeError("generation metadata response lacks data")
            provider = data.get("provider_name")
            model = data.get("model")
            validate_generation_route(provider=provider, model=model)
            return {
                "generation_id": generation_id,
                "provider_name": provider,
                "resolved_model": model,
                "total_cost": data.get("total_cost"),
                "tokens_prompt": data.get("tokens_prompt"),
                "tokens_completion": data.get("tokens_completion"),
            }
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if exc.code not in {404, 425, 429}:
                raise RuntimeError(
                    f"generation metadata query failed: {last_error}"
                ) from exc
        except urllib.error.URLError as exc:
            last_error = str(exc.reason)
    raise RuntimeError(
        f"generation metadata did not become available: {last_error}"
    )


def secondary_cost_audit(run_dir: Path) -> dict[str, object]:
    """Collect cost diagnostics without making them an acceptance gate."""

    try:
        return {
            "status": "available",
            "data": audit_baseline_proxy_costs(run_dir, expected_attempts=1),
        }
    except Exception as exc:  # Cost observability is intentionally non-blocking.
        return {
            "status": "unavailable",
            "error_type": type(exc).__name__,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--image-set", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--qfbench-root", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task", required=True)
    args = parser.parse_args()

    snapshot = load_qfbench_baseline_snapshot(
        args.qfbench_root,
        manifest_path=args.manifest,
    )
    task = snapshot.task(args.task)
    if task.task_id not in set(snapshot.primary.task_ids):
        raise ValueError("provider canary task must be in the primary panel")
    config = load_rootless_full_harness_config(args.config)
    if config.allowed_model != MODEL or config.required_provider != PROVIDER:
        raise ValueError("canary config is not strict official DeepSeek 0731")
    if config.worker_concurrency != 1 or config.verifier_concurrency != 1:
        raise ValueError("provider canary concurrency must be 1/1")
    run_dir = args.results_root.resolve() / args.run_id
    if run_dir.exists() or run_dir.is_symlink():
        raise FileExistsError(f"publish-once canary already exists: {run_dir}")

    runtime = build_rootless_full_harness_runtime(
        config=config,
        image_set_manifest=args.image_set,
        benchmark_commit=snapshot.commit,
        tasks=snapshot.tasks,
        run_id=args.run_id,
        results_root=args.results_root,
    )
    try:
        summary = runtime.evaluator.evaluate(
            worker_dir=Path("qea/worker_gdpval_weak"),
            tasks=(task,),
            split="baseline_primary",
            checkpoint="repetition-01-primary",
            run_dir=run_dir,
        )
        runtime_identity = runtime.runtime_identity_digest
        scheduler_identity = runtime.scheduler_identity_digest
        image_identity = runtime.image_identity_digest
    finally:
        runtime.close()

    generation_ids = completed_generation_ids(run_dir)
    token = config.token_file.read_text().strip()
    if not token:
        raise RuntimeError("model token file is empty")
    metadata = [generation_metadata(item, token) for item in generation_ids]
    token = ""
    payload = {
        "schema_version": 2,
        "status": "accepted",
        "claim_boundary": "one-task 0731 route canary; not a formal repetition",
        "run_id": args.run_id,
        "benchmark_commit": snapshot.commit,
        "requested_model": MODEL,
        "canonical_model": CANONICAL_MODEL,
        "required_provider": PROVIDER,
        "allow_fallbacks": False,
        "generation_metadata_endpoint": GENERATION_ENDPOINT,
        "generation_metadata": metadata,
        "model_route_identity": rootless_model_route_identity(
            upstream_base_url=config.upstream_base_url,
            allowed_path_prefix=config.allowed_path_prefix,
            allowed_model=config.allowed_model,
            required_provider=config.required_provider,
        ),
        "task_ids": [task.task_id],
        "runtime_task_count": len(snapshot.tasks),
        "scheduled_task_count": 1,
        "worker_concurrency": 1,
        "verifier_concurrency": 1,
        "image_identity_digest": image_identity,
        "scheduler_identity_digest": scheduler_identity,
        "runtime_identity_digest": runtime_identity,
        "score_summary": {
            "task_rewards": summary.task_rewards,
            "domain_scores": summary.domain_scores,
            "task_mean": summary.task_mean,
            "overall": summary.overall,
            "scores": [asdict(score) for score in summary.scores],
        },
        "cost_audit": secondary_cost_audit(run_dir),
    }
    private_json(run_dir / "canary-summary.json", payload)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
