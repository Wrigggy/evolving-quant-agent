#!/usr/bin/env python3
"""Select the highest safe QFBench evolution scheduler canary tier."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping


MODEL = "deepseek/deepseek-v4-flash-0731"
PROVIDER = "deepseek"
TIERS = ((20, 3), (16, 3), (12, 3))
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class EvolutionTierError(RuntimeError):
    """No canary tier supplies complete, safe, identity-bound evidence."""


def _canonical_digest(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            dict(payload),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvolutionTierError(f"{label} is invalid")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise EvolutionTierError(f"{label} is invalid")
    return parsed


@dataclass(frozen=True)
class TierAcceptance:
    source_run_id: str
    source_panel_sha256: str
    worker_concurrency: int
    verifier_concurrency: int
    worker_overlap: int
    worker_launch_interval_seconds: int
    lease_timeout_seconds: int
    scheduler_identity_digest: str
    upstream_base_url: str
    allowed_path_prefix: str
    model: str
    provider: str
    fallbacks_allowed: bool
    min_available_memory_mb: int
    max_observed_load_1m: float
    digest: str

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": 1, **asdict(self)}


def _accept_panel(panel: Mapping[str, object]) -> TierAcceptance:
    if panel.get("schema_version") != 1:
        raise EvolutionTierError("canary schema is unsupported")
    run_id = panel.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise EvolutionTierError("canary run identity is missing")
    workers = panel.get("worker_concurrency")
    verifiers = panel.get("verifier_concurrency")
    if (workers, verifiers) not in TIERS:
        raise EvolutionTierError("canary concurrency is outside the tier ladder")
    if panel.get("executor") != "rootless-docker":
        raise EvolutionTierError("canary executor is not rootless Docker")
    if panel.get("formal_scoring_eligible") is not True:
        raise EvolutionTierError("canary is not formal-scoring eligible")
    if panel.get("worker_overlap") != workers:
        raise EvolutionTierError("observed worker overlap did not reach the tier")
    if panel.get("worker_launch_interval_seconds") != 2:
        raise EvolutionTierError("worker launch ramp differs from the formal policy")
    if panel.get("lease_timeout_seconds") != 6000:
        raise EvolutionTierError("lease timeout differs from bounded queueing policy")

    route = panel.get("model_route")
    if not isinstance(route, Mapping):
        raise EvolutionTierError("model provider route evidence is missing")
    upstream = route.get("upstream_base_url")
    prefix = route.get("allowed_path_prefix")
    if upstream != "https://openrouter.ai/api/v1" or prefix != "/v1":
        raise EvolutionTierError("model provider route endpoint differs")
    if route.get("model") != MODEL:
        raise EvolutionTierError("model provider route model differs")
    if route.get("provider") != PROVIDER:
        raise EvolutionTierError("model provider route provider differs")
    if route.get("fallbacks_allowed") is not False:
        raise EvolutionTierError("model provider fallbacks are not disabled")

    scheduler_digest = panel.get("scheduler_identity_digest")
    if not isinstance(scheduler_digest, str) or not _SHA256.fullmatch(
        scheduler_digest
    ):
        raise EvolutionTierError("scheduler identity digest is invalid")
    failures = panel.get("failure_counts")
    expected_failures = {
        "resource_lease_timeout",
        "provider",
        "http_429",
        "replay",
        "coordinator_crash",
    }
    if (
        not isinstance(failures, Mapping)
        or set(failures) != expected_failures
        or any(type(failures[key]) is not int for key in expected_failures)
        or any(failures[key] != 0 for key in expected_failures)
    ):
        raise EvolutionTierError("canary contains a lease/provider/replay failure")

    lifecycle = panel.get("lifecycle_audit")
    if not isinstance(lifecycle, Mapping):
        raise EvolutionTierError("canary lifecycle audit is missing")
    if lifecycle.get("verifier_networkless") is not True:
        raise EvolutionTierError("verifier network isolation failed")
    if lifecycle.get("worker_proxy_only") is not True:
        raise EvolutionTierError("worker proxy isolation failed")
    if lifecycle.get("cleaned_up") is not True:
        raise EvolutionTierError("canary lifecycle cleanup failed")
    if panel.get("residual_resource_count") != 0:
        raise EvolutionTierError("canary has residual resources")

    samples = panel.get("host_samples")
    if not isinstance(samples, list) or not samples:
        raise EvolutionTierError("host memory/load samples are missing")
    available_values: list[int] = []
    load_values: list[float] = []
    for sample in samples:
        if not isinstance(sample, Mapping):
            raise EvolutionTierError("host memory/load sample is invalid")
        available = sample.get("available_memory_mb")
        if type(available) is not int or available < 16_384:
            raise EvolutionTierError("host available memory fell below 16384 MiB")
        load = _number(sample.get("load_1m"), label="host load")
        max_load = _number(sample.get("max_load_1m"), label="safe host load")
        if load < 0 or max_load <= 0 or load > max_load:
            raise EvolutionTierError("host load exceeded the safe threshold")
        available_values.append(available)
        load_values.append(load)

    panel_payload = dict(panel)
    source_digest = _canonical_digest(panel_payload)
    identity: dict[str, object] = {
        "schema_version": 1,
        "source_run_id": run_id,
        "source_panel_sha256": source_digest,
        "worker_concurrency": workers,
        "verifier_concurrency": verifiers,
        "worker_overlap": panel["worker_overlap"],
        "worker_launch_interval_seconds": panel[
            "worker_launch_interval_seconds"
        ],
        "lease_timeout_seconds": panel["lease_timeout_seconds"],
        "scheduler_identity_digest": scheduler_digest,
        "upstream_base_url": upstream,
        "allowed_path_prefix": prefix,
        "model": MODEL,
        "provider": PROVIDER,
        "fallbacks_allowed": False,
        "min_available_memory_mb": min(available_values),
        "max_observed_load_1m": max(load_values),
    }
    return TierAcceptance(
        **{key: value for key, value in identity.items() if key != "schema_version"},
        digest=_canonical_digest(identity),
    )


def accept_tiers(panels: Iterable[Mapping[str, object]]) -> TierAcceptance:
    """Return the first passing panel in the preregistered descending ladder."""

    by_tier: dict[tuple[int, int], Mapping[str, object]] = {}
    for panel in panels:
        if not isinstance(panel, Mapping):
            raise EvolutionTierError("canary panel must be an object")
        tier = (panel.get("worker_concurrency"), panel.get("verifier_concurrency"))
        if tier in by_tier:
            raise EvolutionTierError(f"duplicate canary tier: {tier}")
        if tier in TIERS:
            by_tier[tier] = panel
    failures = []
    for tier in TIERS:
        panel = by_tier.get(tier)
        if panel is None:
            failures.append(f"{tier[0]}/{tier[1]} missing")
            continue
        try:
            return _accept_panel(panel)
        except EvolutionTierError as exc:
            failures.append(f"{tier[0]}/{tier[1]}: {exc}")
    raise EvolutionTierError("no safe evolution tier: " + "; ".join(failures))


def load_tier_acceptance(path: str | Path) -> TierAcceptance:
    source = Path(path).expanduser().resolve()
    try:
        payload = json.loads(source.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise EvolutionTierError(f"tier acceptance is unreadable: {exc}") from exc
    fields = {field.name for field in TierAcceptance.__dataclass_fields__.values()}
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or set(payload) != fields | {"schema_version"}
    ):
        raise EvolutionTierError("tier acceptance schema is invalid")
    digest = payload.get("digest")
    identity = {key: value for key, value in payload.items() if key != "digest"}
    if not isinstance(digest, str) or digest != _canonical_digest(identity):
        raise EvolutionTierError("tier acceptance digest mismatch")
    try:
        artifact = TierAcceptance(
            **{key: payload[key] for key in fields}
        )
    except TypeError as exc:
        raise EvolutionTierError("tier acceptance field types are invalid") from exc
    if (artifact.worker_concurrency, artifact.verifier_concurrency) not in TIERS:
        raise EvolutionTierError("accepted scheduler tier is invalid")
    return artifact


def write_tier_acceptance(path: str | Path, artifact: TierAcceptance) -> None:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(artifact.to_dict(), sort_keys=True, indent=2) + "\n")
    os.replace(temporary, destination)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select the highest safe QFBench evolution concurrency tier"
    )
    parser.add_argument("--panel", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    panels = []
    for path in args.panel:
        try:
            panel = json.loads(path.expanduser().resolve().read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise EvolutionTierError(f"cannot load canary panel {path}: {exc}") from exc
        panels.append(panel)
    accepted = accept_tiers(panels)
    write_tier_acceptance(args.output, accepted)
    print(json.dumps(accepted.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

