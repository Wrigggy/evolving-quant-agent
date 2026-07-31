#!/usr/bin/env python3
"""Plan or build a complete resumable QFBench task-role image panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.benchmarks.qfbench import QFBenchConfigError, _task_resource_contract
from qea.rootless_image_set import RootlessImageSetError
from qea.rootless_images import (
    RootlessImageBuildPlan,
    RootlessImageError,
    execute_rootless_image_build,
    prepare_rootless_image_plan,
)
from scripts.assemble_qfbench_rootless_image_set import assemble_image_set


_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PanelBuildError(RuntimeError):
    """A panel build plan, checkpoint, or result identity is unsafe."""


@dataclass(frozen=True)
class PanelBuildRecord:
    task_id: str
    role: str
    plan: RootlessImageBuildPlan

    @property
    def key(self) -> str:
        return f"{self.task_id}:{self.role}"


@dataclass(frozen=True)
class PanelBuildPlan:
    benchmark_commit: str
    records: tuple[PanelBuildRecord, ...]
    public_root: Path
    trusted_root: Path
    manifest_root: Path
    neutral_manifests: tuple[Path, ...]
    docker_host: str
    expected_uid: int
    base_image_ref: str
    nexau_runtime_image_ref: str
    build_network: str
    build_concurrency: int
    output_image_set: Path
    identity_sha256: str

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(sorted({record.task_id for record in self.records}))

    @property
    def task_role_build_count(self) -> int:
        return len(self.records)

    @property
    def plan_path(self) -> Path:
        return self.manifest_root / "panel-build-plan.json"

    @property
    def state_path(self) -> Path:
        return self.manifest_root / "panel-build-state.json"

    def payload(self) -> dict:
        return {
            "schema_version": 1,
            "benchmark_commit": self.benchmark_commit,
            "task_ids": list(self.task_ids),
            "task_role_build_count": self.task_role_build_count,
            "public_root": str(self.public_root),
            "trusted_root": str(self.trusted_root),
            "manifest_root": str(self.manifest_root),
            "neutral_manifests": [
                {
                    "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for path in self.neutral_manifests
            ],
            "docker_host": self.docker_host,
            "expected_uid": self.expected_uid,
            "base_image_ref": self.base_image_ref,
            "nexau_runtime_image_ref": self.nexau_runtime_image_ref,
            "build_network": self.build_network,
            "build_concurrency": self.build_concurrency,
            "output_image_set": str(self.output_image_set),
            "records": [
                {
                    "key": record.key,
                    "task_id": record.task_id,
                    "role": record.role,
                    "plan": record.plan.manifest_payload(),
                }
                for record in self.records
            ],
            "identity_sha256": self.identity_sha256,
        }


def _canonical_digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _regular_files(paths: Iterable[str | Path]) -> tuple[Path, ...]:
    resolved = tuple(Path(path).expanduser().resolve() for path in paths)
    if len(resolved) != 3 or any(path.is_symlink() or not path.is_file() for path in resolved):
        raise PanelBuildError("exactly three regular neutral manifests are required")
    try:
        roles = [json.loads(path.read_text()).get("role") for path in resolved]
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        raise PanelBuildError(f"cannot read neutral image manifests: {exc}") from exc
    if sorted(roles) != ["base", "evolver", "proxy"]:
        raise PanelBuildError("neutral manifests must contain base, proxy, and evolver")
    return resolved


def _validate_neutral_manifests(
    paths: tuple[Path, ...], *, benchmark_commit: str, base_image_ref: str
) -> None:
    by_role = {}
    for path in paths:
        payload = json.loads(path.read_text())
        role = payload["role"]
        by_role[role] = payload
        if (
            payload.get("benchmark_commit") != benchmark_commit
            or payload.get("task_id") is not None
            or payload.get("identity_kind") != "measured-result"
        ):
            raise PanelBuildError(f"neutral manifest identity differs: {path}")
    if by_role["base"].get("image_id") != base_image_ref:
        raise PanelBuildError("selected base manifest image differs from base_image_ref")
    for role in ("proxy", "evolver"):
        if by_role[role].get("base_image_ref") != base_image_ref:
            raise PanelBuildError(f"{role} manifest derives from a different base image")


def prepare_panel_build_plan(
    *,
    tasks: Iterable,
    benchmark_commit: str,
    public_root: str | Path,
    trusted_root: str | Path,
    manifest_root: str | Path,
    neutral_manifests: Iterable[str | Path],
    docker_host: str,
    expected_uid: int,
    base_image_ref: str,
    nexau_runtime_image_ref: str,
    build_network: str,
    build_concurrency: int = 1,
    output_image_set: str | Path | None = None,
    planner: Callable[..., RootlessImageBuildPlan] = prepare_rootless_image_plan,
) -> PanelBuildPlan:
    """Prepare every task-role plan without connecting to Docker."""

    if not _COMMIT_RE.fullmatch(benchmark_commit):
        raise PanelBuildError("benchmark_commit must be a full lowercase SHA")
    if not _IMAGE_ID_RE.fullmatch(base_image_ref):
        raise PanelBuildError("base_image_ref must be an immutable local image ID")
    if not _IMAGE_ID_RE.fullmatch(nexau_runtime_image_ref):
        raise PanelBuildError(
            "nexau_runtime_image_ref must be an immutable local image ID"
        )
    if type(expected_uid) is not int or expected_uid < 1:
        raise PanelBuildError("expected_uid must be positive")
    if build_network not in {"default", "host"}:
        raise PanelBuildError("build_network must be default or host")
    if type(build_concurrency) is not int or not 1 <= build_concurrency <= 16:
        raise PanelBuildError("build_concurrency must be between 1 and 16")
    public = Path(public_root).expanduser().resolve()
    trusted = Path(trusted_root).expanduser().resolve()
    manifests = Path(manifest_root).expanduser().resolve()
    neutral = _regular_files(neutral_manifests)
    _validate_neutral_manifests(
        neutral,
        benchmark_commit=benchmark_commit,
        base_image_ref=base_image_ref,
    )
    output = Path(
        output_image_set or manifests / "qfbench-rootless-image-set.json"
    ).expanduser().resolve()
    task_tuple = tuple(sorted(tasks, key=lambda task: task.task_id))
    if not task_tuple or len({task.task_id for task in task_tuple}) != len(task_tuple):
        raise PanelBuildError("task panel must be non-empty with unique IDs")

    records = []
    for task in task_tuple:
        for role in ("worker", "verifier"):
            plan = planner(
                role=role,
                task_id=task.task_id,
                public_root=public,
                trusted_root=trusted if role == "verifier" else None,
                base_image_ref=base_image_ref,
                cpu_count=task.cpus,
                memory_mb=task.memory_mb,
                build_timeout_seconds=task.build_timeout_seconds,
                build_network=build_network,
                nexau_runtime_image_ref=(
                    nexau_runtime_image_ref if role == "worker" else None
                ),
            )
            if plan.benchmark_commit != benchmark_commit:
                raise PanelBuildError(
                    f"planned task commit differs for {task.task_id}:{role}"
                )
            records.append(PanelBuildRecord(task.task_id, role, plan))

    unsigned = {
        "schema_version": 1,
        "benchmark_commit": benchmark_commit,
        "public_root": str(public),
        "trusted_root": str(trusted),
        "manifest_root": str(manifests),
        "neutral_manifests": [
            {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in neutral
        ],
        "docker_host": docker_host,
        "expected_uid": expected_uid,
        "base_image_ref": base_image_ref,
        "nexau_runtime_image_ref": nexau_runtime_image_ref,
        "build_network": build_network,
        "build_concurrency": build_concurrency,
        "output_image_set": str(output),
        "records": [
            {
                "key": record.key,
                "plan_identity_sha256": record.plan.identity_sha256,
                "resources": {
                    "cpu_count": record.plan.cpu_count,
                    "memory_mb": record.plan.memory_mb,
                    "build_timeout_seconds": record.plan.build_timeout_seconds,
                },
            }
            for record in records
        ],
    }
    return PanelBuildPlan(
        benchmark_commit=benchmark_commit,
        records=tuple(records),
        public_root=public,
        trusted_root=trusted,
        manifest_root=manifests,
        neutral_manifests=neutral,
        docker_host=docker_host,
        expected_uid=expected_uid,
        base_image_ref=base_image_ref,
        nexau_runtime_image_ref=nexau_runtime_image_ref,
        build_network=build_network,
        build_concurrency=build_concurrency,
        output_image_set=output,
        identity_sha256=_canonical_digest(unsigned),
    )


def persist_panel_build_plan(panel: PanelBuildPlan) -> Path:
    payload = panel.payload()
    path = panel.plan_path
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise PanelBuildError(f"cannot load existing panel plan: {exc}") from exc
        if existing != payload:
            raise PanelBuildError("existing panel plan identity differs")
        return path
    _atomic_json(path, payload)
    return path


def _validate_result_manifest(record: PanelBuildRecord, path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise PanelBuildError(f"completed image manifest is missing: {path}")
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise PanelBuildError(f"invalid completed image manifest {path}: {exc}") from exc
    if payload.get("plan_identity_sha256") != record.plan.identity_sha256:
        raise PanelBuildError(f"manifest plan identity differs for {record.key}")
    if (payload.get("task_id"), payload.get("role")) != (
        record.task_id,
        record.role,
    ):
        raise PanelBuildError(f"manifest task-role identity differs for {record.key}")
    if (
        payload.get("identity_kind") != "measured-result"
        or not _SHA256_RE.fullmatch(str(payload.get("result_identity_sha256", "")))
        or not isinstance(payload.get("docker_version"), str)
        or "name=rootless" not in payload.get("docker_security_options", [])
    ):
        raise PanelBuildError(f"manifest measured identity is incomplete for {record.key}")
    return payload


def validate_completed_build_state(panel: PanelBuildPlan) -> dict:
    if not panel.state_path.exists():
        return {
            "schema_version": 1,
            "panel_identity_sha256": panel.identity_sha256,
            "completed": {},
        }
    try:
        state = json.loads(panel.state_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise PanelBuildError(f"cannot load panel build state: {exc}") from exc
    if (
        state.get("schema_version") != 1
        or state.get("panel_identity_sha256") != panel.identity_sha256
        or not isinstance(state.get("completed"), dict)
    ):
        raise PanelBuildError("panel build state identity differs")
    by_key = {record.key: record for record in panel.records}
    if not set(state["completed"]).issubset(by_key):
        raise PanelBuildError("panel build state contains an unknown task-role")
    daemon_identities = set()
    for key, entry in state["completed"].items():
        if not isinstance(entry, dict) or entry.get("plan_identity_sha256") != (
            by_key[key].plan.identity_sha256
        ):
            raise PanelBuildError(f"completed plan identity differs for {key}")
        manifest_path = Path(str(entry.get("manifest_path", ""))).resolve()
        payload = _validate_result_manifest(by_key[key], manifest_path)
        if entry.get("result_identity_sha256") != payload["result_identity_sha256"]:
            raise PanelBuildError(f"completed result identity differs for {key}")
        daemon_identities.add((
            payload["docker_version"],
            tuple(sorted(payload["docker_security_options"])),
        ))
    if len(daemon_identities) > 1:
        raise PanelBuildError("completed manifests have different daemon identities")
    return state


def _daemon_identity(payload: dict) -> tuple[str, tuple[str, ...]]:
    return (
        payload["docker_version"],
        tuple(sorted(payload["docker_security_options"])),
    )


def _completed_daemon_identity(panel: PanelBuildPlan, state: dict):
    by_key = {record.key: record for record in panel.records}
    identities = {
        _daemon_identity(
            _validate_result_manifest(
                by_key[key], Path(entry["manifest_path"]).resolve()
            )
        )
        for key, entry in state["completed"].items()
    }
    if len(identities) > 1:
        raise PanelBuildError("completed manifests have different daemon identities")
    return next(iter(identities), None)


def _recover_result_manifest(
    panel: PanelBuildPlan, record: PanelBuildRecord
) -> Path | None:
    matches = []
    if not panel.manifest_root.exists():
        return None
    for path in panel.manifest_root.glob("*/MANIFEST.json"):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("plan_identity_sha256") == record.plan.identity_sha256:
            _validate_result_manifest(record, path)
            matches.append(path.resolve())
    if len(matches) > 1:
        raise PanelBuildError(f"multiple measured results found for {record.key}")
    return matches[0] if matches else None


def _checkpoint_result(
    panel: PanelBuildPlan,
    state: dict,
    record: PanelBuildRecord,
    manifest_path: Path,
    *,
    plan_identity_sha256: str,
    result_identity_sha256: str,
) -> None:
    payload = _validate_result_manifest(record, manifest_path)
    if (
        plan_identity_sha256 != record.plan.identity_sha256
        or result_identity_sha256 != payload["result_identity_sha256"]
    ):
        raise PanelBuildError(f"builder result identity differs for {record.key}")
    expected_daemon = _completed_daemon_identity(panel, state)
    if expected_daemon is not None and _daemon_identity(payload) != expected_daemon:
        raise PanelBuildError(f"Docker daemon identity changed before {record.key}")
    state["completed"][record.key] = {
        "manifest_path": str(manifest_path),
        "plan_identity_sha256": plan_identity_sha256,
        "result_identity_sha256": result_identity_sha256,
    }
    _atomic_json(panel.state_path, state)


def execute_panel_build(
    panel: PanelBuildPlan,
    *,
    builder: Callable = execute_rootless_image_build,
    assembler: Callable = assemble_image_set,
) -> Path:
    """Build missing roles, checkpoint each result, then assemble the exact set."""

    persist_panel_build_plan(panel)
    state = validate_completed_build_state(panel)
    by_key = {record.key: record for record in panel.records}
    pending = []
    for record in panel.records:
        if record.key in state["completed"]:
            continue
        recovered = _recover_result_manifest(panel, record)
        if recovered is not None:
            recovered_payload = _validate_result_manifest(record, recovered)
            _checkpoint_result(
                panel,
                state,
                record,
                recovered,
                plan_identity_sha256=record.plan.identity_sha256,
                result_identity_sha256=recovered_payload[
                    "result_identity_sha256"
                ],
            )
            continue
        pending.append(record)

    def build_one(record):
        return record, builder(
            record.plan,
            output_root=panel.manifest_root,
            docker_host=panel.docker_host,
            expected_uid=panel.expected_uid,
        )

    if panel.build_concurrency == 1:
        completed = (build_one(record) for record in pending)
        executor = None
    else:
        executor = ThreadPoolExecutor(max_workers=panel.build_concurrency)
        futures = [executor.submit(build_one, record) for record in pending]
        completed = (future.result() for future in as_completed(futures))
    try:
        for record, result in completed:
            manifest_path = Path(result.manifest_path).resolve()
            _checkpoint_result(
                panel,
                state,
                record,
                manifest_path,
                plan_identity_sha256=result.plan_identity_sha256,
                result_identity_sha256=result.result_identity_sha256,
            )
    finally:
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)

    if set(state["completed"]) != set(by_key):
        raise PanelBuildError("task-role build state is incomplete")
    manifest_paths = [*panel.neutral_manifests]
    manifest_paths.extend(
        Path(state["completed"][record.key]["manifest_path"])
        for record in panel.records
    )
    image_set = assembler(
        benchmark_commit=panel.benchmark_commit,
        task_ids=panel.task_ids,
        manifest_paths=manifest_paths,
    )
    image_set.write(panel.output_image_set)
    return panel.output_image_set


def _load_panel_tasks(path: Path, public_root: Path) -> tuple[str, tuple]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise PanelBuildError(f"cannot load panel manifest: {exc}") from exc
    commit = str(payload.get("commit", ""))
    baseline = payload.get("baseline")
    if not _COMMIT_RE.fullmatch(commit) or not isinstance(baseline, dict):
        raise PanelBuildError("panel manifest is not a pinned baseline")
    entries = [*baseline.get("primary", ()), *baseline.get("diagnostic", ())]
    tasks = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("task_id"), str):
            raise PanelBuildError("panel manifest contains an invalid task")
        task_id = entry["task_id"]
        resource_source = entry.get("resource_source", "upstream")
        fallback = entry.get("resources") if resource_source == "qea_fallback" else None
        resources = _task_resource_contract(
            public_root / "tasks" / task_id,
            task_id,
            fallback=fallback,
        )
        tasks.append(SimpleNamespace(task_id=task_id, **resources))
    if len(tasks) != 85 or len({task.task_id for task in tasks}) != 85:
        raise PanelBuildError("baseline panel must contain exactly 85 unique tasks")
    return commit, tuple(tasks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel-manifest", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    parser.add_argument("--manifest-root", type=Path, required=True)
    parser.add_argument("--neutral-manifest", type=Path, action="append", required=True)
    parser.add_argument("--docker-host", required=True)
    parser.add_argument("--expected-uid", type=int, default=os.getuid())
    parser.add_argument("--base-image-ref", required=True)
    parser.add_argument("--nexau-runtime-image-ref", required=True)
    parser.add_argument("--build-network", choices=("default", "host"), default="host")
    parser.add_argument("--build-concurrency", type=int, default=2)
    parser.add_argument("--output-image-set", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--build", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        public_root = args.public_root.expanduser().resolve()
        commit, tasks = _load_panel_tasks(
            args.panel_manifest.expanduser().resolve(), public_root
        )
        panel = prepare_panel_build_plan(
            tasks=tasks,
            benchmark_commit=commit,
            public_root=public_root,
            trusted_root=args.trusted_root,
            manifest_root=args.manifest_root,
            neutral_manifests=args.neutral_manifest,
            docker_host=args.docker_host,
            expected_uid=args.expected_uid,
            base_image_ref=args.base_image_ref,
            nexau_runtime_image_ref=args.nexau_runtime_image_ref,
            build_network=args.build_network,
            build_concurrency=args.build_concurrency,
            output_image_set=args.output_image_set,
        )
        persist_panel_build_plan(panel)
        print(f"panel identity: {panel.identity_sha256}")
        print(f"tasks: {len(panel.task_ids)}")
        print(f"task-role builds: {panel.task_role_build_count}")
        print(f"plan: {panel.plan_path}")
        if args.build:
            output = execute_panel_build(panel)
            print(f"image set: {output}")
        return 0
    except (
        PanelBuildError,
        QFBenchConfigError,
        RootlessImageError,
        RootlessImageSetError,
    ) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
