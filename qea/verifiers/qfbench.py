"""Parse QFBench's official reward without forwarding assertion diagnostics."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..evaluation import EvaluationContractError, OfficialTaskScore


_KNOWN_UV_BOOTSTRAP_LINES = frozenset({
    "curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh",
    "curl -LsSf https://astral.sh/uv/0.9.5/install.sh -o /tmp/install-uv.sh",
    "curl -Lsf https://astral.sh/uv/0.9.5/install.sh -o /tmp/uv_install.sh",
    (
        'echo "8402ab80d2ef54d7044a71ea4e4e1e8db3b20c87c7bffbc30bff59f1e80ebbd5  '
        '/tmp/install-uv.sh" | sha256sum -c - || exit 1'
    ),
    (
        'echo "8402ab80d2ef54d7044a71ea4e4e1e8db3b20c87c7bffbc30bff59f1e80ebbd5  '
        '/tmp/uv_install.sh" | sha256sum -c -'
    ),
    "sh /tmp/install-uv.sh",
    "sh /tmp/uv_install.sh",
    "source $HOME/.local/bin/env",
    'source "$HOME/.local/bin/env"',
})


def prepare_offline_verifier_script(official_script: str) -> str:
    """Remove only QFBench's pinned uv bootstrap; preserve its test/reward body."""

    retained: list[str] = []
    for line in official_script.splitlines():
        stripped = line.strip()
        if stripped in _KNOWN_UV_BOOTSTRAP_LINES:
            continue
        if (
            "astral.sh/uv/" in stripped
            or "install-uv.sh" in stripped
            or "uv_install.sh" in stripped
            or ".local/bin/env" in stripped
        ):
            raise ValueError(f"unsupported uv bootstrap line: {stripped}")
        retained.append(line)

    exports = [
        "export UV_OFFLINE=1",
        'export UV_CACHE_DIR="/opt/qea/uv-cache"',
        'export UV_TOOL_DIR="/opt/qea/uv-tools"',
        'export UV_TOOL_BIN_DIR="/opt/qea/uv-bin"',
        'export PATH="/opt/qea/uv-bin:/root/.local/bin:/usr/local/bin:${PATH}"',
    ]
    if retained and retained[0].startswith("#!"):
        lines = [retained[0], *exports, *retained[1:]]
    else:
        lines = ["#!/bin/bash", *exports, *retained]
    return "\n".join(lines).rstrip() + "\n"


def _nonnegative_int(summary: dict, key: str) -> int:
    value = summary.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        raise EvaluationContractError(f"CTRF summary {key!r} must be an integer")
    integer = int(value)
    if integer < 0:
        raise EvaluationContractError(f"CTRF summary {key!r} must be non-negative")
    return integer


def parse_official_qfbench_score(
    *,
    task_id: str,
    domain: str,
    reward_path: str | Path,
    ctrf_path: str | Path | None,
    verifier_exit_code: int,
    log_uri: str | None = None,
    pytest_output: str | None = None,
) -> OfficialTaskScore:
    """Return the official scalar and coarse tags, never raw test messages."""

    try:
        reward = float(Path(reward_path).read_text().strip())
    except (OSError, ValueError) as exc:
        raise EvaluationContractError(f"cannot parse official QFBench reward: {exc}") from exc
    if not 0.0 <= reward <= 1.0:
        raise EvaluationContractError("official reward must be in [0, 1]")
    if pytest_output and all(
        marker in pytest_output
        for marker in (
            "No solution found when resolving tool dependencies",
            "Packages were unavailable because the network was disabled",
        )
    ):
        raise EvaluationContractError(
            "offline verifier dependency resolution failed"
        )

    passed = 0
    failed = 0
    if ctrf_path is not None:
        try:
            payload = json.loads(Path(ctrf_path).read_text())
            summary = payload["results"]["summary"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise EvaluationContractError(f"cannot parse QFBench CTRF summary: {exc}") from exc
        if not isinstance(summary, dict):
            raise EvaluationContractError("QFBench CTRF summary must be an object")
        passed = _nonnegative_int(summary, "passed")
        failed = _nonnegative_int(summary, "failed")
    if pytest_output:
        passed_matches = [int(value) for value in re.findall(r"\b(\d+)\s+passed\b", pytest_output)]
        failed_matches = [int(value) for value in re.findall(r"\b(\d+)\s+failed\b", pytest_output)]
        if passed_matches or failed_matches:
            passed = sum(passed_matches)
            failed = sum(failed_matches)

    tags: list[str] = []
    if failed:
        tags.append("tests_failed")
    elif verifier_exit_code != 0:
        tags.append("verifier_error")
    return OfficialTaskScore(
        task_id=task_id,
        domain=domain,
        reward=reward,
        diagnostic_tags=tuple(tags),
        verifier_exit_code=verifier_exit_code,
        tests_passed=passed,
        tests_failed=failed,
        log_uri=log_uri,
    )
