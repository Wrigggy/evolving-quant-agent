from __future__ import annotations

import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


STAGES = (
    "daemon",
    "immutable-images",
    "resources-2cpu-4gib",
    "resources-4cpu-8gib",
    "filesystem-and-capabilities",
    "verifier-no-egress",
    "worker-proxy-synthetic",
    "nexau-no-model",
    "force-kill-reap-resume",
    "verifier-replay",
    "historical-var-seed-worker",
)


def _config_payload():
    return {
        "schema_version": 1,
        "run_id": "qfbench-rootless-canary-20260728",
        "benchmark_commit": "024921eb507fcc0c4ffe3e0a96802724be1ae84a",
        "branch": "qfbench-selfhosted-vm-backend",
        "docker_host": "unix:///run/user/1013/docker.sock",
        "expected_uid": 1013,
        "paths": {
            "source_root": "worktrees/qfbench-selfhosted-vm-backend",
            "public_root": "runtime/qfbench-public/024921eb-five-task",
            "trusted_root": "runtime/trusted-verifier/024921eb-five-task",
            "image_manifest_root": "runtime/images",
            "secret_file": "runtime/secrets/model-token",
            "run_output_root": "runs/qfbench-rootless-canary-20260728",
            "historical_artifact_manifest": "runtime/replay/historical-var-artifact.json",
            "historical_e2b_score": "runtime/replay/historical-var-e2b-score.json",
        },
        "task": {
            "task_id": "historical-var-data-prep",
            "domain": "risk_credit",
            "worker_dir": "qea/worker",
            "model_name": "openai/gpt-5",
            "proxy_upstream_base_url": "https://openrouter.ai/api/v1",
            "proxy_allowed_path_prefix": "/v1",
        },
    }


def _write_config(tmp_path, changes=None):
    payload = _config_payload()
    for key, value in (changes or {}).items():
        payload[key] = value
    path = tmp_path / "canary.json"
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    return path


def test_stage_order_is_exact_and_contains_no_formal_scoring_stage():
    from qea.rootless_canary import CANARY_STAGES

    assert CANARY_STAGES == STAGES
    encoded = " ".join(CANARY_STAGES)
    assert "30" not in encoded
    assert "formal" not in encoded
    assert "five-iteration" not in encoded


def test_plan_only_is_side_effect_free_and_redacts_secret_values(tmp_path):
    from qea.rootless_canary import load_canary_config, plan_canary

    config_path = _write_config(tmp_path)
    runtime_root = tmp_path / "remote-runtime"
    config = load_canary_config(config_path, runtime_root=runtime_root)
    plan = plan_canary(config, source_commit="a" * 40)

    assert plan["mode"] == "plan-only"
    assert plan["stages"] == list(STAGES)
    assert plan["source_commit"] == "a" * 40
    assert plan["mutates"] is False
    assert plan["formal_scoring_available"] is False
    assert plan["planned_resources"]["internal_network"] == (
        "qea-qfbench-rootless-canary-20260728-internal"
    )
    assert "qea-proxy-proxy-synthetic" in plan["planned_resources"]["containers"]
    assert str(runtime_root / "runtime/secrets/model-token") not in json.dumps(plan)
    assert not runtime_root.exists()


def test_apply_persists_each_pass_in_order_and_resume_reuses_it(tmp_path):
    from qea.rootless_canary import load_canary_config, run_canary

    config = load_canary_config(
        _write_config(tmp_path), runtime_root=tmp_path / "runtime"
    )
    output = tmp_path / "evidence"
    calls = []

    def gate(stage):
        calls.append(stage)
        return {"gate": stage, "content_sha256": "a" * 64}

    first = run_canary(
        config,
        source_commit="b" * 40,
        output_root=output,
        gate_runner=gate,
    )
    assert tuple(result.stage for result in first) == STAGES
    assert all(result.status == "pass" for result in first)
    assert calls == list(STAGES)
    assert len(tuple(output.glob("[0-9][0-9]-*.json"))) == len(STAGES)

    calls.clear()
    second = run_canary(
        config,
        source_commit="b" * 40,
        output_root=output,
        gate_runner=gate,
    )
    assert calls == []
    assert all(result.status == "pass" and result.reused for result in second)


def test_shorter_resume_boundary_preserves_existing_pass_evidence(tmp_path):
    from qea.rootless_canary import load_canary_config, run_canary

    config = load_canary_config(
        _write_config(tmp_path), runtime_root=tmp_path / "runtime"
    )
    output = tmp_path / "evidence"
    first = run_canary(
        config,
        source_commit="b" * 40,
        output_root=output,
        gate_runner=lambda stage: {"gate": stage},
    )
    original = {
        result.stage: (output / f"{result.sequence:02d}-{result.stage}.json").read_bytes()
        for result in first
    }

    resumed = run_canary(
        config,
        source_commit="b" * 40,
        output_root=output,
        gate_runner=lambda stage: pytest.fail(f"unexpected rerun: {stage}"),
        through_stage="filesystem-and-capabilities",
    )

    assert all(result.status == "pass" and result.reused for result in resumed)
    assert all(
        (output / f"{result.sequence:02d}-{result.stage}.json").read_bytes()
        == original[result.stage]
        for result in resumed
    )


def test_first_failure_marks_all_later_stages_not_run(tmp_path):
    from qea.rootless_canary import CanaryGateError, load_canary_config, run_canary

    config = load_canary_config(
        _write_config(tmp_path), runtime_root=tmp_path / "runtime"
    )
    calls = []

    def gate(stage):
        calls.append(stage)
        if stage == "resources-2cpu-4gib":
            raise CanaryGateError("synthetic cgroup mismatch token-must-not-leak")
        return {"ok": True}

    results = run_canary(
        config,
        source_commit="c" * 40,
        output_root=tmp_path / "evidence",
        gate_runner=gate,
        forbidden_values=("token-must-not-leak",),
    )
    statuses = {result.stage: result.status for result in results}
    assert statuses["daemon"] == "pass"
    assert statuses["immutable-images"] == "pass"
    assert statuses["resources-2cpu-4gib"] == "fail"
    assert all(statuses[stage] == "not_run" for stage in STAGES[3:])
    assert calls == list(STAGES[:3])
    failure = json.loads((tmp_path / "evidence/03-resources-2cpu-4gib.json").read_text())
    assert "token-must-not-leak" not in json.dumps(failure)
    assert "[REDACTED]" in failure["failure"]


@pytest.mark.parametrize(
    "change",
    [
        {"docker_host": "unix:///var/run/docker.sock"},
        {"docker_host": "tcp://127.0.0.1:2375"},
        {"expected_uid": 0},
        {"branch": "main"},
        {
            "paths": {
                **_config_payload()["paths"],
                "public_root": "/absolute/public",
            }
        },
        {
            "paths": {
                **_config_payload()["paths"],
                "trusted_root": "../trusted",
            }
        },
        {
            "paths": {
                **_config_payload()["paths"],
                "historical_artifact_manifest": "runtime/solution/artifact.json",
            }
        },
        {
            "task": {
                **_config_payload()["task"],
                "task_id": "some-other-task",
            }
        },
        {"api_key": "forbidden-secret"},
    ],
)
def test_config_rejects_unsafe_host_paths_scope_and_secret_values(tmp_path, change):
    from qea.rootless_canary import CanaryConfigError, load_canary_config

    with pytest.raises(CanaryConfigError):
        load_canary_config(
            _write_config(tmp_path, change), runtime_root=tmp_path / "runtime"
        )


def test_resource_evidence_requires_exact_cgroup_contract():
    from qea.rootless_canary import CanaryGateError, validate_resource_evidence

    evidence = {
        "cpu.max": "200000 100000",
        "memory.max": str(4096 * 1024 * 1024),
        "memory.swap.max": "0",
        "pids.max": "256",
    }
    validated = validate_resource_evidence(
        evidence,
        cpu_count=2,
        memory_mb=4096,
        pids_limit=256,
    )
    assert validated["cpu_count"] == 2.0
    assert validated["memory_bytes"] == 4096 * 1024 * 1024
    assert validated["swap_bytes"] == 0

    for key, bad in (
        ("cpu.max", "150000 100000"),
        ("memory.max", "max"),
        ("memory.swap.max", "1"),
        ("pids.max", "255"),
    ):
        with pytest.raises(CanaryGateError):
            validate_resource_evidence(
                {**evidence, key: bad},
                cpu_count=2,
                memory_mb=4096,
                pids_limit=256,
            )


def test_daemon_host_evidence_requires_subids_namespaces_and_cgroup_v2():
    from qea.rootless_canary import CanaryGateError, validate_daemon_host_evidence

    evidence = {
        "actual_uid": 1013,
        "max_user_namespaces": 15_495,
        "subuid_range_size": 65_536,
        "subgid_range_size": 65_536,
        "cgroup_v2": True,
        "cgroup_controllers": ["cpu", "io", "memory", "pids"],
    }
    assert validate_daemon_host_evidence(evidence, expected_uid=1013)["host_ready"] is True
    for key, value in (
        ("actual_uid", 0),
        ("max_user_namespaces", 0),
        ("subuid_range_size", 1),
        ("subgid_range_size", 1),
        ("cgroup_v2", False),
        ("cgroup_controllers", ["cpu", "memory"]),
    ):
        with pytest.raises(CanaryGateError):
            validate_daemon_host_evidence(
                {**evidence, key: value}, expected_uid=1013
            )


def test_docker_inspect_contract_rejects_mounts_privilege_and_resource_drift():
    from qea.rootless_canary import (
        CanaryGateError,
        validate_docker_inspect_contract,
    )

    payload = [{
        "Id": "container-1",
        "Config": {
            "Image": "sha256:" + "a" * 64,
            "Labels": {"qea.managed": "true", "qea.backend": "rootless-docker"},
        },
        "HostConfig": {
            "ReadonlyRootfs": True,
            "Privileged": False,
            "Binds": None,
            "CapAdd": None,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "PidMode": "",
            "IpcMode": "private",
            "NetworkMode": "none",
            "NanoCpus": 2_000_000_000,
            "Memory": 4096 * 1024 * 1024,
            "MemorySwap": 4096 * 1024 * 1024,
            "PidsLimit": 256,
        },
        "Mounts": [],
    }]
    result = validate_docker_inspect_contract(
        payload,
        native_id="container-1",
        image_ref="sha256:" + "a" * 64,
        cpu_count=2,
        memory_mb=4096,
        pids_limit=256,
        network_policy="none",
    )
    assert result["control_plane_isolated"] is True
    for mutation in (
        lambda item: item[0].update({"Mounts": [{"Source": "/host"}]}),
        lambda item: item[0]["HostConfig"].update({"Privileged": True}),
        lambda item: item[0]["HostConfig"].update({"Memory": 1}),
        lambda item: item[0]["HostConfig"].update({"NetworkMode": "host"}),
    ):
        changed = json.loads(json.dumps(payload))
        mutation(changed)
        with pytest.raises(CanaryGateError):
            validate_docker_inspect_contract(
                changed,
                native_id="container-1",
                image_ref="sha256:" + "a" * 64,
                cpu_count=2,
                memory_mb=4096,
                pids_limit=256,
                network_policy="none",
            )


def test_filesystem_and_capability_evidence_fails_closed():
    from qea.rootless_canary import (
        CanaryGateError,
        validate_isolation_evidence,
    )

    evidence = {
        "root_read_only": True,
        "no_new_privileges": True,
        "cap_eff": "0000000000000000",
        "uid": 0,
        "gid": 0,
        "docker_socket_present": False,
        "host_mount_present": False,
        "metadata_reachable": False,
        "cross_attempt_marker_present": False,
        "writable_paths": ["/tmp", "/qea"],
        "network_interfaces": ["lo"],
        "status_sha256": "a" * 64,
        "mountinfo_sha256": "b" * 64,
        "route_sha256": "c" * 64,
        "ipv6_route_sha256": "d" * 64,
    }
    assert validate_isolation_evidence(
        evidence, expected_writable_paths=("/tmp", "/qea")
    )["isolated"] is True
    for key in (
        "root_read_only",
        "no_new_privileges",
        "docker_socket_present",
        "host_mount_present",
        "metadata_reachable",
        "cross_attempt_marker_present",
    ):
        bad = dict(evidence)
        bad[key] = not evidence[key]
        with pytest.raises(CanaryGateError):
            validate_isolation_evidence(
                bad, expected_writable_paths=("/tmp", "/qea")
            )
    with pytest.raises(CanaryGateError):
        validate_isolation_evidence(
            {**evidence, "route_sha256": None},
            expected_writable_paths=("/tmp", "/qea"),
        )


def test_network_evidence_requires_all_direct_probes_blocked_and_proxy_success():
    from qea.rootless_canary import CanaryGateError, validate_network_evidence

    blocked = {
        name: False
        for name in (
            "dns",
            "public_ipv4_tcp",
            "public_ipv6_tcp",
            "http",
            "https",
            "github",
            "pypi",
            "model_host",
            "metadata_ipv4",
            "metadata_dns",
            "docker_socket",
        )
    }
    assert validate_network_evidence(blocked, role="verifier")["isolated"] is True
    worker = {**blocked, "proxy_request": True, "secret_exposed": False}
    assert validate_network_evidence(worker, role="worker")["isolated"] is True
    with pytest.raises(CanaryGateError):
        validate_network_evidence({**blocked, "dns": True}, role="verifier")
    with pytest.raises(CanaryGateError):
        validate_network_evidence(
            {**worker, "proxy_request": False}, role="worker"
        )


def test_replay_and_fresh_worker_evidence_are_bounded_and_oracle_free():
    from qea.rootless_canary import (
        CanaryGateError,
        validate_fresh_worker_evidence,
        validate_replay_parity,
    )

    reference = {
        "artifact_sha256": "a" * 64,
        "reward": 1.0,
        "tests_passed": 4,
        "tests_failed": 0,
        "executed_test_sha256": "b" * 64,
        "dependency_lock_sha256": "c" * 64,
    }
    assert validate_replay_parity(reference, dict(reference))["parity"] is True
    with pytest.raises(CanaryGateError):
        validate_replay_parity(reference, {**reference, "reward": 0.0})

    fresh = {
        "task_id": "historical-var-data-prep",
        "worker_sandbox_id": "worker-1",
        "verifier_sandbox_id": "verifier-1",
        "artifact_sha256": "d" * 64,
        "reward": 1.0,
        "tests_passed": 4,
        "tests_failed": 0,
        "worker_network_policy": "worker-proxy-only",
        "verifier_network_policy": "none",
        "solution_members": [],
        "oracle_lifecycles": [],
        "model_identity": "openai/gpt-5",
        "input_tokens": None,
        "output_tokens": None,
        "model_cost_usd": None,
        "sandbox_cost_usd": None,
    }
    assert validate_fresh_worker_evidence(fresh)["oracle_free"] is True
    with pytest.raises(CanaryGateError):
        validate_fresh_worker_evidence(
            {**fresh, "oracle_lifecycles": ["oracle.json"]}
        )


def test_worker_bundle_audit_rejects_test_and_solution_members(tmp_path):
    from qea.rootless_canary import CanaryGateError, audit_worker_bundle

    clean = tmp_path / "clean.tar"
    source = tmp_path / "instruction.md"
    source.write_text("public instruction\n")
    with tarfile.open(clean, "w") as archive:
        archive.add(source, arcname="task/instruction.md")
    assert audit_worker_bundle(clean) == []

    for member in ("task/tests/test_hidden.py", "task/solution/solve.py"):
        unsafe = tmp_path / (member.replace("/", "-") + ".tar")
        with tarfile.open(unsafe, "w") as archive:
            archive.add(source, arcname=member)
        with pytest.raises(CanaryGateError):
            audit_worker_bundle(unsafe)


def test_force_kill_evidence_requires_exact_pid_id_and_zero_duplication():
    from qea.rootless_canary import CanaryGateError, validate_force_kill_evidence

    evidence = {
        "native_id": "container-1",
        "coordinator_pid": 1234,
        "dry_pending_ids": ["container-1"],
        "killed_ids": ["container-1"],
        "cleaned_lifecycle_reused": False,
        "final_pending_ids": [],
        "attempt_identity_sha256": "a" * 64,
        "completed_operation_sha256": "b" * 64,
        "model_calls_duplicated": 0,
        "verifier_calls_duplicated": 0,
    }
    assert validate_force_kill_evidence(evidence)["exact_id_cleanup"] is True
    for key, value in (
        ("coordinator_pid", 0),
        ("dry_pending_ids", ["other"]),
        ("killed_ids", []),
        ("model_calls_duplicated", 1),
    ):
        with pytest.raises(CanaryGateError):
            validate_force_kill_evidence({**evidence, key: value})

    resumed = {
        **evidence,
        "dry_pending_ids": [],
        "killed_ids": [],
        "cleaned_lifecycle_reused": True,
    }
    assert validate_force_kill_evidence(resumed)["resume_reused_cleanup"] is True


def test_cli_defaults_to_plan_only_and_writes_nothing(tmp_path):
    config = _write_config(tmp_path)
    runtime = tmp_path / "runtime"
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        (
            sys.executable,
            "scripts/run_qfbench_rootless_canary.py",
            "--config",
            str(config),
            "--runtime-root",
            str(runtime),
            "--source-commit",
            "e" * 40,
            "--plan-only",
        ),
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "plan-only"
    assert payload["formal_scoring_available"] is False
    assert payload["stages"] == list(STAGES)
    assert not runtime.exists()
    assert "iteration" not in result.stdout.lower()
    assert "30-task" not in result.stdout.lower()
