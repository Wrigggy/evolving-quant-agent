#!/usr/bin/env python3
"""Check TLS and header-injected model egress without making a completion call."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.executors.e2b_nexau import build_worker_network, sanitize_worker_env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)

    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    base_url = os.environ.get(
        "LLM_BASE_URL",
        os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )
    if not api_key:
        raise SystemExit("LLM_API_KEY or OPENROUTER_API_KEY is required")
    model_env = {
        "LLM_API_KEY": api_key,
        "LLM_BASE_URL": base_url,
        "LLM_MODEL": os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-pro"),
    }

    from e2b import Sandbox

    sandbox = Sandbox.create(
        template=args.template,
        timeout=180,
        metadata={
            "qea_role": "model-egress-canary",
            "qea_run_id": args.run_id,
            "qea_task_id": args.task,
        },
        envs=sanitize_worker_env(model_env),
        secure=True,
        allow_internet_access=True,
        network=build_worker_network(model_env),
    )
    try:
        result = sandbox.commands.run(
            "/opt/qea/nexau-venv/bin/python -c "
            "\"import httpx, os; "
            "response = httpx.get(os.environ['LLM_BASE_URL'].rstrip('/') + '/models', "
            "timeout=30); print(response.status_code); response.raise_for_status()\"",
            timeout=60,
            envs=sanitize_worker_env(model_env),
        )
        print(json.dumps({
            "sandbox_id": str(sandbox.sandbox_id),
            "exit_code": int(result.exit_code),
            "stdout": str(result.stdout or ""),
            "stderr": str(result.stderr or ""),
        }, sort_keys=True, indent=2))
        return int(result.exit_code)
    finally:
        sandbox.kill()


if __name__ == "__main__":
    raise SystemExit(main())
