import json
import os
import subprocess

import pytest


def _identity_payload():
    return {
        "benchmark_commit": "0" * 40,
        "model": "deepseek/deepseek-v4-pro",
        "required_provider": "deepseek",
        "allow_fallbacks": False,
        "image_set_sha256": "2" * 64,
        "runtime_sha256": "3" * 64,
        "scheduler_sha256": "4" * 64,
        "config_sha256": "5" * 64,
        "checkpoint_sha256": "6" * 64,
    }


def _incident_payload(category="artifact_integrity"):
    from qea.repair_supervisor import ExpectedIdentity, Incident

    incident = Incident.create(
        run_id="formal-r1",
        source_commit="1" * 40,
        exit_code=87,
        exit_evidence_sha256="a" * 64,
        failure_signature="verifier artifact integrity mismatch",
        category=category,
        excerpt="verifier artifact integrity mismatch",
        expected_identity=ExpectedIdentity.from_dict(_identity_payload()),
        evidence_hashes={"failure_log": "b" * 64},
    )
    return incident.to_dict()


def _config_payload(tmp_path):
    deploy_adapter = tmp_path / "deploy-exact"
    deploy_adapter.write_text("#!/bin/sh\nexit 0\n")
    os.chmod(deploy_adapter, 0o700)
    return {
        "schema_version": 1,
        "run_id": "formal-r1",
        "ssh_host": "bc",
        "remote_state_dir": "/home/julius/qea/runtime/supervisor",
        "remote_state_helper": "/home/julius/qea/deploy/current/scripts/qfbench_supervisor_state.py",
        "worktree": str(tmp_path / "worktree"),
        "branch": "qfbench-selfhosted-vm-backend",
        "max_repairs": 3,
        "expected_identity": _identity_payload(),
        "protected_dirty_paths": ["docs/PROJECT_MEMORY.md"],
        "owned_paths": ["qea", "scripts", "tests", "deploy"],
        "test_argvs": [["python", "-m", "pytest", "-q", "tests/test_owned.py"]],
        "push_argv": ["git", "push", "origin", "qfbench-selfhosted-vm-backend"],
        "deploy_argv_prefix": [str(deploy_adapter)],
        "canary_argv": ["ssh", "bc", "qea-run-verifier-canary"],
        "resume_argv": ["ssh", "bc", "qea-resume-formal-r1"],
        "state_dir": str(tmp_path / "controller-state"),
        "codex_binary": "/usr/local/bin/codex",
        "command_timeout_seconds": 7200,
    }


def _load_config(tmp_path):
    from scripts.run_qfbench_repair_controller import load_config

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    path = tmp_path / "controller.json"
    path.write_text(json.dumps(_config_payload(tmp_path)))
    os.chmod(path, 0o600)
    return load_config(path)


class FakeRunner:
    def __init__(self, *, category="artifact_integrity", ssh_code=0, codex_code=0):
        self.category = category
        self.ssh_code = ssh_code
        self.codex_code = codex_code
        self.calls = []
        self.head_calls = 0

    def __call__(self, argv, *, cwd=None, input_text=None, timeout=None):
        argv = tuple(argv)
        self.calls.append((argv, cwd, input_text, timeout))
        if argv[0] == "ssh" and "show-active" in argv:
            if self.ssh_code:
                return subprocess.CompletedProcess(argv, self.ssh_code, "", "vpn down")
            return subprocess.CompletedProcess(
                argv,
                0,
                json.dumps(
                    {
                        "incident": _incident_payload(self.category),
                        "snapshot": {
                            "incident_id": _incident_payload(self.category)["incident_id"],
                            "state": "frozen",
                            "repair_count": 0,
                            "history": ["observed", "frozen"],
                        },
                    }
                ),
                "",
            )
        if argv[0] == "/usr/local/bin/codex":
            return subprocess.CompletedProcess(argv, self.codex_code, "codex-result", "")
        if argv[:3] == ("git", "branch", "--show-current"):
            return subprocess.CompletedProcess(
                argv, 0, "qfbench-selfhosted-vm-backend\n", ""
            )
        if argv[:2] == ("git", "status"):
            return subprocess.CompletedProcess(argv, 0, " M docs/PROJECT_MEMORY.md\n", "")
        if argv[:2] == ("git", "rev-parse"):
            self.head_calls += 1
            value = "1" * 40 if self.head_calls == 1 else "9" * 40
            return subprocess.CompletedProcess(argv, 0, value + "\n", "")
        if argv[:3] == ("git", "diff", "--name-only"):
            return subprocess.CompletedProcess(argv, 0, "qea/repair.py\n", "")
        return subprocess.CompletedProcess(argv, 0, "{}\n", "")


def test_codex_argv_uses_supported_unattended_workspace_sandbox(tmp_path):
    from scripts.run_qfbench_repair_controller import build_codex_argv

    config = _load_config(tmp_path)
    argv = build_codex_argv(config)

    assert argv == (
        "/usr/local/bin/codex",
        "exec",
        "--ephemeral",
        "--json",
        "--sandbox",
        "workspace-write",
        "-c",
        'approval_policy="never"',
        "-c",
        "sandbox_workspace_write.network_access=false",
        "-c",
        "agents.enabled=false",
        "-C",
        str(config.worktree),
        "-",
    )
    assert "--full-auto" not in argv
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv


def test_codex_prompt_is_fixed_bounded_and_contains_no_forbidden_material(tmp_path):
    from qea.repair_supervisor import Incident
    from scripts.run_qfbench_repair_controller import build_codex_prompt

    config = _load_config(tmp_path)
    prompt = build_codex_prompt(Incident.from_dict(_incident_payload()), config)

    assert "formal-r1" in prompt
    assert "artifact_integrity" in prompt
    assert "at most one scoped commit" in prompt
    assert "Do not read .env" in prompt
    assert "OPENROUTER_API_KEY" not in prompt
    assert len(prompt) < 8000


def test_controller_lock_is_exclusive(tmp_path):
    from scripts.run_qfbench_repair_controller import controller_lock

    lock_path = tmp_path / "controller.lock"
    with controller_lock(lock_path) as first:
        assert first is True
        with controller_lock(lock_path) as second:
            assert second is False


def test_successful_repair_runs_codex_tests_exact_deploy_canary_and_resume(tmp_path):
    from scripts.run_qfbench_repair_controller import RepairController

    config = _load_config(tmp_path)
    runner = FakeRunner()

    assert RepairController(config, runner=runner).run_once() == 0

    argvs = [call[0] for call in runner.calls]
    codex_calls = [call for call in runner.calls if call[0][0] == "/usr/local/bin/codex"]
    assert len(codex_calls) == 1
    assert codex_calls[0][2].startswith("You are repairing QFBench infrastructure")
    assert config.test_argvs[0] in argvs
    assert config.push_argv in argvs
    assert (*config.deploy_argv_prefix, "9" * 40) in argvs
    assert config.canary_argv in argvs
    assert config.resume_argv in argvs
    assert any("resolved" in argv for argv in argvs if argv[0] == "ssh")


def test_hard_stop_category_never_calls_codex_or_run_commands(tmp_path):
    from scripts.run_qfbench_repair_controller import RepairController

    config = _load_config(tmp_path)
    runner = FakeRunner(category="identity_drift")

    assert RepairController(config, runner=runner).run_once() == 20
    argvs = [call[0] for call in runner.calls]
    assert not any(argv[0] == "/usr/local/bin/codex" for argv in argvs)
    assert config.canary_argv not in argvs
    assert config.resume_argv not in argvs
    assert any("hard_stop" in argv for argv in argvs if argv[0] == "ssh")


def test_transient_ssh_failure_returns_retry_code_without_mutation(tmp_path):
    from scripts.run_qfbench_repair_controller import RepairController

    config = _load_config(tmp_path)
    runner = FakeRunner(ssh_code=255)

    assert RepairController(config, runner=runner).run_once() == 10
    assert len(runner.calls) == 1


def test_codex_failure_consumes_cycle_but_never_deploys_or_resumes(tmp_path):
    from scripts.run_qfbench_repair_controller import RepairController

    config = _load_config(tmp_path)
    runner = FakeRunner(codex_code=1)

    assert RepairController(config, runner=runner).run_once() == 1
    argvs = [call[0] for call in runner.calls]
    assert any("record-repair" in argv for argv in argvs if argv[0] == "ssh")
    assert not any(argv[:3] == config.deploy_argv_prefix for argv in argvs)
    assert config.resume_argv not in argvs


def test_config_rejects_group_readable_file_and_shell_metacharacters(tmp_path):
    from scripts.run_qfbench_repair_controller import ControllerConfigError, load_config

    (tmp_path / "worktree").mkdir()
    path = tmp_path / "controller.json"
    payload = _config_payload(tmp_path)
    path.write_text(json.dumps(payload))
    os.chmod(path, 0o644)
    with pytest.raises(ControllerConfigError, match="mode 600"):
        load_config(path)

    os.chmod(path, 0o600)
    payload["resume_argv"] = ["ssh", "bc; touch /tmp/bad"]
    path.write_text(json.dumps(payload))
    with pytest.raises(ControllerConfigError, match="argument"):
        load_config(path)


def test_config_rejects_unmaterialized_deploy_command_placeholder(tmp_path):
    """Catch enabling launchd with a test-only deploy command name."""

    from scripts.run_qfbench_repair_controller import ControllerConfigError, load_config

    (tmp_path / "worktree").mkdir()
    path = tmp_path / "controller.json"
    payload = _config_payload(tmp_path)
    payload["deploy_argv_prefix"] = ["ssh", "bc", "qea-deploy-exact"]
    path.write_text(json.dumps(payload))
    os.chmod(path, 0o600)

    with pytest.raises(ControllerConfigError, match="deploy adapter"):
        load_config(path)
