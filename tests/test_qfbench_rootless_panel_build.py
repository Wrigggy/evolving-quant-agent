from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest


@dataclass(frozen=True)
class _FakeImagePlan:
    role: str
    task_id: str
    benchmark_commit: str
    cpu_count: int
    memory_mb: int
    build_timeout_seconds: int
    identity_sha256: str

    def manifest_payload(self):
        return {
            "role": self.role,
            "task_id": self.task_id,
            "benchmark_commit": self.benchmark_commit,
            "cpu_count": self.cpu_count,
            "memory_mb": self.memory_mb,
            "build_timeout_seconds": self.build_timeout_seconds,
            "identity_sha256": self.identity_sha256,
        }


def _tasks():
    return (
        SimpleNamespace(
            task_id="task-b",
            cpus=4,
            memory_mb=8192,
            build_timeout_seconds=700,
        ),
        SimpleNamespace(
            task_id="task-a",
            cpus=2,
            memory_mb=4096,
            build_timeout_seconds=600,
        ),
    )


def _neutral_manifests(tmp_path: Path) -> tuple[Path, ...]:
    paths = []
    for role in ("base", "proxy", "evolver"):
        path = tmp_path / f"{role}.json"
        path.write_text(json.dumps({
            "role": role,
            "task_id": None,
            "benchmark_commit": "0" * 40,
            "image_id": "sha256:" + ("b" if role == "base" else "a") * 64,
            "base_image_ref": (
                "sha256:" + ("d" if role == "base" else "b") * 64
            ),
            "identity_kind": "measured-result",
        }))
        paths.append(path)
    return tuple(paths)


def _panel(
    tmp_path: Path,
    *,
    docker_host="unix:///run/user/1000/docker.sock",
    build_concurrency=1,
):
    from scripts.build_qfbench_rootless_panel import prepare_panel_build_plan

    calls = []

    def planner(**kwargs):
        calls.append(kwargs)
        index = len(calls)
        return _FakeImagePlan(
            role=kwargs["role"],
            task_id=kwargs["task_id"],
            benchmark_commit="0" * 40,
            cpu_count=kwargs["cpu_count"],
            memory_mb=kwargs["memory_mb"],
            build_timeout_seconds=kwargs["build_timeout_seconds"],
            identity_sha256=f"{index:x}" * 64,
        )

    panel = prepare_panel_build_plan(
        tasks=_tasks(),
        benchmark_commit="0" * 40,
        public_root=tmp_path / "public",
        trusted_root=tmp_path / "trusted",
        manifest_root=tmp_path / "manifests",
        neutral_manifests=_neutral_manifests(tmp_path),
        docker_host=docker_host,
        expected_uid=1000,
        base_image_ref="sha256:" + "b" * 64,
        nexau_runtime_image_ref="sha256:" + "c" * 64,
        build_network="host",
        build_concurrency=build_concurrency,
        planner=planner,
    )
    return panel, calls


def test_panel_plan_is_sorted_resource_exact_and_does_not_connect_to_docker(
    tmp_path,
) -> None:
    panel, calls = _panel(tmp_path)

    assert [(record.task_id, record.role) for record in panel.records] == [
        ("task-a", "worker"),
        ("task-a", "verifier"),
        ("task-b", "worker"),
        ("task-b", "verifier"),
    ]
    assert [
        (call["cpu_count"], call["memory_mb"], call["build_timeout_seconds"])
        for call in calls
    ] == [(2, 4096, 600), (2, 4096, 600), (4, 8192, 700), (4, 8192, 700)]
    assert calls[0]["trusted_root"] is None
    assert calls[0]["nexau_runtime_image_ref"] == "sha256:" + "c" * 64
    assert calls[1]["trusted_root"] == tmp_path / "trusted"
    assert calls[1]["nexau_runtime_image_ref"] is None
    assert panel.task_role_build_count == 4


def test_existing_panel_plan_rejects_source_resource_or_daemon_identity_drift(
    tmp_path,
) -> None:
    from scripts.build_qfbench_rootless_panel import (
        PanelBuildError,
        persist_panel_build_plan,
    )

    panel, _ = _panel(tmp_path)
    persist_panel_build_plan(panel)
    same, _ = _panel(tmp_path)
    assert persist_panel_build_plan(same).is_file()

    changed, _ = _panel(tmp_path, docker_host="unix:///run/user/1001/docker.sock")
    with pytest.raises(PanelBuildError, match="identity differs"):
        persist_panel_build_plan(changed)

    changed_concurrency, _ = _panel(tmp_path, build_concurrency=4)
    with pytest.raises(PanelBuildError, match="identity differs"):
        persist_panel_build_plan(changed_concurrency)


def test_completed_state_rejects_manifest_with_other_plan_identity(tmp_path) -> None:
    from scripts.build_qfbench_rootless_panel import (
        PanelBuildError,
        validate_completed_build_state,
    )

    panel, _ = _panel(tmp_path)
    manifest = tmp_path / "manifests" / "wrong" / "MANIFEST.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        "role": "worker",
        "task_id": "task-a",
        "plan_identity_sha256": "f" * 64,
        "result_identity_sha256": "e" * 64,
        "identity_kind": "measured-result",
        "docker_version": "fixture",
        "docker_security_options": ["name=rootless"],
    }))
    state = {
        "schema_version": 1,
        "panel_identity_sha256": panel.identity_sha256,
        "completed": {
            "task-a:worker": {
                "manifest_path": str(manifest),
                "plan_identity_sha256": panel.records[0].plan.identity_sha256,
            }
        },
    }
    panel.state_path.parent.mkdir(parents=True, exist_ok=True)
    panel.state_path.write_text(json.dumps(state))

    with pytest.raises(PanelBuildError, match="manifest plan identity"):
        validate_completed_build_state(panel)


def test_build_resumes_completed_roles_and_assembles_only_after_exact_panel(
    tmp_path,
) -> None:
    from scripts.build_qfbench_rootless_panel import execute_panel_build

    panel, _ = _panel(tmp_path)
    built = []
    assembled = []

    def builder(plan, **kwargs):
        built.append((plan.task_id, plan.role))
        output = tmp_path / "manifests" / plan.identity_sha256
        output.mkdir(parents=True)
        manifest = output / "MANIFEST.json"
        manifest.write_text(json.dumps({
            "role": plan.role,
            "task_id": plan.task_id,
            "plan_identity_sha256": plan.identity_sha256,
            "result_identity_sha256": "e" * 64,
            "identity_kind": "measured-result",
            "docker_version": "fixture",
            "docker_security_options": ["name=rootless"],
        }))
        return SimpleNamespace(
            manifest_path=manifest,
            plan_identity_sha256=plan.identity_sha256,
            result_identity_sha256="e" * 64,
        )

    def assembler(**kwargs):
        assembled.append(kwargs)
        return SimpleNamespace(write=lambda path: Path(path))

    output = execute_panel_build(panel, builder=builder, assembler=assembler)
    assert output == panel.output_image_set
    assert built == [
        ("task-a", "worker"),
        ("task-a", "verifier"),
        ("task-b", "worker"),
        ("task-b", "verifier"),
    ]
    assert len(assembled[0]["manifest_paths"]) == 7

    built.clear()
    execute_panel_build(panel, builder=builder, assembler=assembler)
    assert built == []


def test_build_recovers_result_manifest_written_before_state_checkpoint(
    tmp_path,
) -> None:
    from scripts.build_qfbench_rootless_panel import execute_panel_build

    panel, _ = _panel(tmp_path)
    first = panel.records[0]
    recovered = tmp_path / "manifests" / "recovered" / "MANIFEST.json"
    recovered.parent.mkdir(parents=True)
    recovered.write_text(json.dumps({
        "role": first.role,
        "task_id": first.task_id,
        "plan_identity_sha256": first.plan.identity_sha256,
        "result_identity_sha256": "e" * 64,
        "identity_kind": "measured-result",
        "docker_version": "fixture",
        "docker_security_options": ["name=rootless"],
    }))
    built = []

    def builder(plan, **kwargs):
        built.append((plan.task_id, plan.role))
        output = tmp_path / "manifests" / plan.identity_sha256
        output.mkdir(parents=True)
        manifest = output / "MANIFEST.json"
        manifest.write_text(json.dumps({
            "role": plan.role,
            "task_id": plan.task_id,
            "plan_identity_sha256": plan.identity_sha256,
            "result_identity_sha256": "e" * 64,
            "identity_kind": "measured-result",
            "docker_version": "fixture",
            "docker_security_options": ["name=rootless"],
        }))
        return SimpleNamespace(
            manifest_path=manifest,
            plan_identity_sha256=plan.identity_sha256,
            result_identity_sha256="e" * 64,
        )

    execute_panel_build(
        panel,
        builder=builder,
        assembler=lambda **kwargs: SimpleNamespace(write=lambda path: Path(path)),
    )

    assert (first.task_id, first.role) not in built
    assert len(built) == 3
