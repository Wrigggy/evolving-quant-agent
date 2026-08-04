from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


FIXTURE = Path(__file__).parent / "fixtures/rootless_host_bc.json"


def _fixture_payload():
    return json.loads(FIXTURE.read_text())


def test_bc_post_bootstrap_fixture_proves_every_required_check():
    from scripts.check_qfbench_rootless_host import evaluate_fixture

    report = evaluate_fixture(_fixture_payload())

    assert report["ready"] is True
    assert report["required_failed"] == 0
    assert report["required_passed"] >= 20
    checks = {item["name"]: item for item in report["checks"]}
    assert checks["docker_endpoint"]["status"] == "pass"
    assert checks["rootless_security"]["status"] == "pass"
    assert checks["git_commit"]["status"] == "pass"
    assert checks["secret_mode"]["status"] == "pass"
    assert checks["fuse_overlayfs"]["status"] == "unnecessary"


@pytest.mark.parametrize(
    ("observation", "replacement", "failed_check"),
    [
        ("uid", "0\n", "uid"),
        ("newuidmap_path", "", "newuidmap"),
        ("newgidmap_path", "", "newgidmap"),
        ("subuid", "julius:886432:1\n", "subuid"),
        ("subgid", "julius:886432:1\n", "subgid"),
        ("max_user_namespaces", "0\n", "user_namespaces"),
        ("cgroup_filesystem", "cgroup\n", "cgroup_v2"),
        ("cgroup_controllers", "cpu memory\n", "cgroup_controllers"),
        ("systemd_user", "offline\n", "user_systemd"),
        ("linger", "no\n", "linger"),
        ("docker_socket_stat", "660:0:socket\n", "docker_endpoint"),
        (
            "docker_info",
            "{\"DockerRootDir\":\"/var/lib/docker\",\"Driver\":\"overlay2\",\"SecurityOptions\":[]}",
            "rootless_security",
        ),
        ("filesystem_free", "/dev/x 1 1 1 1% /\n", "filesystem_space"),
        ("meminfo", "MemTotal: 1024 kB\n", "memory"),
        ("cpu_online", "2\n", "cpu"),
        ("git_head", "0" * 40 + "\n", "git_commit"),
        ("runtime_stat", "755:1013:directory\n", "runtime_mode"),
        ("secret_stat", "644:1013:regular file\n", "secret_mode"),
    ],
)
def test_required_host_drift_fails_closed(observation, replacement, failed_check):
    from scripts.check_qfbench_rootless_host import evaluate_fixture

    payload = copy.deepcopy(_fixture_payload())
    payload["observations"][observation]["stdout"] = replacement
    report = evaluate_fixture(payload)
    checks = {item["name"]: item for item in report["checks"]}

    assert report["ready"] is False
    assert checks[failed_check]["status"] == "fail"


def test_docker_client_server_version_and_git_cleanliness_are_required():
    from scripts.check_qfbench_rootless_host import evaluate_fixture

    for mutate, expected in (
        (
            lambda payload: payload["observations"]["docker_version"].update(
                stdout='{\"Client\":{\"Version\":\"29.4.1\"},\"Server\":{\"Version\":\"28.0.0\"}}'
            ),
            "docker_version",
        ),
        (
            lambda payload: payload["observations"]["git_status"].update(
                stdout=" M qea/rootless_canary.py\n"
            ),
            "git_clean",
        ),
    ):
        payload = copy.deepcopy(_fixture_payload())
        mutate(payload)
        checks = {
            item["name"]: item for item in evaluate_fixture(payload)["checks"]
        }
        assert checks[expected]["status"] == "fail"


def test_systemd_degraded_exit_one_still_proves_user_manager_is_reachable():
    """Catch discarding systemd's valid degraded state solely for exit code 1."""

    from scripts.check_qfbench_rootless_host import evaluate_fixture

    payload = copy.deepcopy(_fixture_payload())
    payload["observations"]["systemd_user"].update(
        exit_code=1,
        stdout="degraded\n",
    )
    checks = {
        item["name"]: item for item in evaluate_fixture(payload)["checks"]
    }

    assert checks["user_systemd"]["status"] == "pass"


def test_rootless_data_root_may_use_a_user_owned_data_filesystem():
    """Catch rejecting a safe rootless data root solely for being outside HOME."""

    from scripts.check_qfbench_rootless_host import evaluate_fixture

    payload = copy.deepcopy(_fixture_payload())
    docker_info = json.loads(payload["observations"]["docker_info"]["stdout"])
    docker_info["DockerRootDir"] = "/data/qea-julius-rootless-docker-20260801"
    payload["observations"]["docker_info"]["stdout"] = json.dumps(docker_info)
    payload["observations"]["docker_root_stat"] = {
        "exit_code": 0,
        "stderr": "",
        "stdout": "710:1013:directory\n",
    }

    checks = {
        item["name"]: item for item in evaluate_fixture(payload)["checks"]
    }

    assert checks["rootless_security"]["status"] == "pass"


def test_rootless_data_root_wrong_owner_fails_closed():
    """Catch trusting a rootless-labelled daemon whose data root is not user-owned."""

    from scripts.check_qfbench_rootless_host import evaluate_fixture

    payload = copy.deepcopy(_fixture_payload())
    payload["observations"]["docker_root_stat"] = {
        "exit_code": 0,
        "stderr": "",
        "stdout": "700:0:directory\n",
    }
    checks = {
        item["name"]: item for item in evaluate_fixture(payload)["checks"]
    }

    assert checks["rootless_security"]["status"] == "fail"


def test_cli_emits_machine_json_and_human_summary_without_writes(tmp_path):
    repository = Path(__file__).resolve().parents[1]
    before = {path: path.stat().st_mtime_ns for path in tmp_path.iterdir()}
    result = subprocess.run(
        (
            sys.executable,
            "scripts/check_qfbench_rootless_host.py",
            "--fixture",
            str(FIXTURE),
        ),
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ready"] is True
    assert "READY" in result.stderr
    assert "read-only" in result.stderr
    assert before == {path: path.stat().st_mtime_ns for path in tmp_path.iterdir()}


def test_fixture_schema_rejects_unknown_fields_and_missing_observations():
    from scripts.check_qfbench_rootless_host import HostCheckError, evaluate_fixture

    payload = _fixture_payload()
    payload["unexpected"] = True
    with pytest.raises(HostCheckError):
        evaluate_fixture(payload)

    payload = _fixture_payload()
    del payload["observations"]["docker_info"]
    with pytest.raises(HostCheckError):
        evaluate_fixture(payload)


def test_checker_exposes_no_mutating_mode_or_command():
    from scripts import check_qfbench_rootless_host as checker

    options = {
        option
        for action in checker.build_parser()._actions
        for option in action.option_strings
    }
    source = Path(checker.__file__).read_text().lower()
    assert "--apply" not in options
    assert "--install" not in options
    assert "docker system prune" not in source
    assert '"create"' not in source
    assert '"start"' not in source


def test_runbook_preserves_transfer_isolation_and_cleanup_boundaries():
    repository = Path(__file__).resolve().parents[1]
    text = (repository / "docs/runbooks/qfbench-rootless-docker-vm.md").read_text()

    for required in (
        "unix:///run/user/1013/docker.sock",
        "dockerd-rootless-setuptool.sh install",
        "systemctl --user status docker",
        "git init --bare",
        "worktree add",
        "--filter=blob:none",
        "--plan-only",
        "force-kill-reap-resume",
        "tmux",
        "EXACT_CONTAINER_ID",
    ):
        assert required in text
    for prohibition in (
        "Never copy the repository recursively",
        "transfer `.env`",
        "Never check out, copy, upload, or run official `solution/` blobs",
        "Never run `docker system prune`",
        "wildcard cleanup",
        "/var/run/docker.sock",
    ):
        assert prohibition in text
