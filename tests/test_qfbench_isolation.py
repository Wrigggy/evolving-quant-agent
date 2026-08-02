import json
import tarfile
from types import SimpleNamespace

import pytest


def _task_fixture(tmp_path):
    root = tmp_path / "task"
    (root / "environment" / "data").mkdir(parents=True)
    (root / "tests" / "reference_data").mkdir(parents=True)
    (root / "solution").mkdir()
    instruction = root / "instruction.md"
    data = root / "environment" / "data" / "input.csv"
    test_file = root / "tests" / "test_outputs.py"
    reference = root / "tests" / "reference_data" / "expected.json"
    solution = root / "solution" / "solve.py"
    instruction.write_text("Create /root/output/results.json\n")
    data.write_text("x\n1\n")
    test_file.write_text("def test_secret_expected_value(): pass\n")
    reference.write_text('{"secret_expected": 17}\n')
    solution.write_text("# oracle solution\n")
    return SimpleNamespace(
        task_id="fixture-task",
        domain="risk",
        root=root,
        instruction_path=instruction,
        worker_files=(data, instruction),
        verifier_files=(reference, test_file),
    )


def _worker_fixture(tmp_path):
    root = tmp_path / "worker"
    (root / "tool_descriptions").mkdir(parents=True)
    (root / "agent.yaml").write_text("name: qf-worker\n")
    (root / "systemprompt.md").write_text("Solve the public task.\n")
    (root / "tool_descriptions" / "shell.tool.yaml").write_text("name: shell\n")
    return root


def _members(path):
    with tarfile.open(path, "r") as archive:
        return tuple(member.name for member in archive.getmembers() if member.isfile())


def test_worker_bundle_is_deterministic_and_excludes_tests_and_solution(tmp_path):
    from qea.executors.bundles import build_worker_bundle

    task = _task_fixture(tmp_path)
    worker = _worker_fixture(tmp_path)

    first = build_worker_bundle(task, worker, tmp_path / "worker-a.tar")
    second = build_worker_bundle(task, worker, tmp_path / "worker-b.tar")

    assert first.sha256 == second.sha256
    assert first.members == second.members
    assert _members(first.path) == (
        "task/environment/data/input.csv",
        "task/instruction.md",
        "worker/agent.yaml",
        "worker/systemprompt.md",
        "worker/tool_descriptions/shell.tool.yaml",
    )
    assert not any("tests" in member or "solution" in member for member in first.members)


def test_verifier_bundle_contains_artifacts_and_tests_but_no_worker_or_solution(tmp_path):
    from qea.executors.bundles import build_verifier_bundle

    task = _task_fixture(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "results.json").write_text('{"answer": 1}\n')

    bundle = build_verifier_bundle(task, artifacts, tmp_path / "verifier.tar")

    assert _members(bundle.path) == (
        "artifacts/results.json",
        "tests/reference_data/expected.json",
        "tests/test_outputs.py",
    )
    assert not any("worker" in member or "solution" in member for member in bundle.members)


def test_verifier_bundle_preserves_declared_python_cache_artifact(tmp_path):
    from qea.executors.bundles import build_verifier_bundle

    task = _task_fixture(tmp_path)
    artifacts = tmp_path / "artifacts"
    cache = artifacts / "__pycache__"
    cache.mkdir(parents=True)
    (artifacts / "function-under-new-api.py").write_text("VALUE = 1\n")
    (cache / "function-under-new-api.cpython-311.pyc").write_bytes(b"pyc")

    bundle = build_verifier_bundle(task, artifacts, tmp_path / "verifier.tar")

    assert "artifacts/function-under-new-api.py" in bundle.members
    assert (
        "artifacts/__pycache__/function-under-new-api.cpython-311.pyc"
        in bundle.members
    )


def test_oracle_bundle_is_trusted_and_contains_solution_but_no_tests(tmp_path):
    from qea.executors.bundles import build_oracle_bundle

    task = _task_fixture(tmp_path)
    bundle = build_oracle_bundle(task, tmp_path / "oracle.tar")

    assert _members(bundle.path) == (
        "solution/solve.py",
        "task/environment/data/input.csv",
        "task/instruction.md",
    )
    assert not any(member.startswith("tests/") for member in bundle.members)


def test_bundle_rejects_secret_named_files_and_limits(tmp_path):
    from qea.executors.bundles import BundleError, build_verifier_bundle

    task = _task_fixture(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / ".env").write_text("API_KEY=secret\n")

    with pytest.raises(BundleError, match="secret-like"):
        build_verifier_bundle(task, artifacts, tmp_path / "secret.tar")

    (artifacts / ".env").unlink()
    (artifacts / "large.bin").write_bytes(b"x" * 32)
    with pytest.raises(BundleError, match="byte limit"):
        build_verifier_bundle(task, artifacts, tmp_path / "large.tar", max_bytes=16)


def test_parse_official_reward_and_ctrf_returns_only_answer_free_tags(tmp_path):
    from qea.verifiers.qfbench import parse_official_qfbench_score

    reward = tmp_path / "reward.txt"
    ctrf = tmp_path / "ctrf.json"
    reward.write_text("0.625\n")
    ctrf.write_text(json.dumps({
        "results": {
            "summary": {"tests": 8, "passed": 5, "failed": 3, "skipped": 0},
            "tests": [{
                "name": "test_outputs.py::test_secret_expected_value",
                "status": "failed",
                "message": "expected secret value 17",
            }],
        }
    }))

    score = parse_official_qfbench_score(
        task_id="evt-pot-var",
        domain="risk",
        reward_path=reward,
        ctrf_path=ctrf,
        verifier_exit_code=1,
        log_uri="runs/r1/verifier.log",
    )

    assert score.reward == 0.625
    assert score.tests_passed == 5
    assert score.tests_failed == 3
    assert score.diagnostic_tags == ("tests_failed",)
    assert "secret" not in repr(score)
    assert "17" not in repr(score)


def test_parse_official_reward_rejects_invalid_or_missing_summary(tmp_path):
    from qea.evaluation import EvaluationContractError
    from qea.verifiers.qfbench import parse_official_qfbench_score

    reward = tmp_path / "reward.txt"
    ctrf = tmp_path / "ctrf.json"
    reward.write_text("1.5\n")
    ctrf.write_text("{}\n")

    with pytest.raises(EvaluationContractError):
        parse_official_qfbench_score(
            task_id="x",
            domain="risk",
            reward_path=reward,
            ctrf_path=ctrf,
            verifier_exit_code=2,
        )


def test_pytest_stdout_count_overrides_collapsed_ctrf_parameterization(tmp_path):
    from qea.verifiers.qfbench import parse_official_qfbench_score

    reward = tmp_path / "reward.txt"
    ctrf = tmp_path / "ctrf.json"
    reward.write_text("1\n")
    ctrf.write_text(json.dumps({
        "results": {"summary": {"tests": 6, "passed": 6, "failed": 0}}
    }))

    score = parse_official_qfbench_score(
        task_id="historical-var-data-prep",
        domain="risk",
        reward_path=reward,
        ctrf_path=ctrf,
        verifier_exit_code=0,
        pytest_output="============ 12 passed in 0.42s ============",
    )

    assert score.tests_passed == 12
    assert score.tests_failed == 0


def test_binary_official_reward_does_not_require_ctrf(tmp_path):
    from qea.verifiers.qfbench import parse_official_qfbench_score

    reward = tmp_path / "reward.txt"
    reward.write_text("1\n")

    score = parse_official_qfbench_score(
        task_id="option-put-call-parity-forward-audit",
        domain="derivatives",
        reward_path=reward,
        ctrf_path=None,
        verifier_exit_code=0,
    )

    assert score.reward == 1.0
    assert score.tests_passed == 0
    assert score.tests_failed == 0
    assert score.diagnostic_tags == ()


def test_offline_dependency_resolution_failure_is_not_an_official_zero(tmp_path):
    from qea.evaluation import EvaluationContractError
    from qea.verifiers.qfbench import parse_official_qfbench_score

    reward = tmp_path / "reward.txt"
    reward.write_text("0\n")

    with pytest.raises(
        EvaluationContractError,
        match="offline verifier dependency resolution failed",
    ):
        parse_official_qfbench_score(
            task_id="delta-hedging-pnl-simulation",
            domain="derivatives",
            reward_path=reward,
            ctrf_path=None,
            verifier_exit_code=0,
            pytest_output=(
                "No solution found when resolving tool dependencies. "
                "Packages were unavailable because the network was disabled."
            ),
        )


def test_offline_verifier_script_removes_only_known_uv_bootstrap():
    from qea.verifiers.qfbench import prepare_offline_verifier_script

    official = """#!/bin/bash
curl -LsSf https://astral.sh/uv/0.9.5/install.sh -o /tmp/install-uv.sh
echo "8402ab80d2ef54d7044a71ea4e4e1e8db3b20c87c7bffbc30bff59f1e80ebbd5  /tmp/install-uv.sh" | sha256sum -c - || exit 1
sh /tmp/install-uv.sh
source $HOME/.local/bin/env
mkdir -p /logs/verifier
uvx -p 3.11 -w pytest==8.4.1 pytest /tests/test_outputs.py
echo 1 > /logs/verifier/reward.txt
"""

    offline = prepare_offline_verifier_script(official)

    assert offline.startswith("#!/bin/bash\nexport UV_OFFLINE=1\n")
    assert 'export UV_CACHE_DIR="/opt/qea/uv-cache"' in offline
    assert 'export UV_TOOL_DIR="/opt/qea/uv-tools"' in offline
    assert 'export UV_TOOL_BIN_DIR="/opt/qea/uv-bin"' in offline
    assert "astral.sh" not in offline
    assert "install-uv.sh" not in offline
    assert "uvx -p 3.11 -w pytest==8.4.1 pytest /tests/test_outputs.py" in offline
    assert "echo 1 > /logs/verifier/reward.txt" in offline


def test_offline_verifier_script_rejects_unknown_installer_rewrite():
    from qea.verifiers.qfbench import prepare_offline_verifier_script

    with pytest.raises(ValueError, match="unsupported uv bootstrap"):
        prepare_offline_verifier_script(
            "curl -LsSf https://astral.sh/uv/latest/install.sh | sh\n"
        )


def test_offline_verifier_script_accepts_quoted_known_uv_source_line():
    from qea.verifiers.qfbench import prepare_offline_verifier_script

    offline = prepare_offline_verifier_script(
        '#!/bin/bash\nsource "$HOME/.local/bin/env"\necho 1\n'
    )

    assert '.local/bin/env' not in offline
    assert "echo 1" in offline


def test_offline_verifier_script_accepts_pinned_uv_underscore_tempfile():
    from qea.verifiers.qfbench import prepare_offline_verifier_script

    official = """#!/bin/bash
curl -Lsf https://astral.sh/uv/0.9.5/install.sh -o /tmp/uv_install.sh
echo "8402ab80d2ef54d7044a71ea4e4e1e8db3b20c87c7bffbc30bff59f1e80ebbd5  /tmp/uv_install.sh" | sha256sum -c -
sh /tmp/uv_install.sh
source $HOME/.local/bin/env
uvx -p 3.11 -w pytest==8.4.1 pytest /tests/test_outputs.py
"""

    offline = prepare_offline_verifier_script(official)

    assert "astral.sh" not in offline
    assert "uv_install.sh" not in offline
    assert "uvx -p 3.11 -w pytest==8.4.1 pytest /tests/test_outputs.py" in offline
