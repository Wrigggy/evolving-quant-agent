#!/usr/bin/env python3
"""Verify the two Python runtimes in one published QFBench worker template."""

from __future__ import annotations

import argparse
import json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout < 1:
        raise SystemExit("--timeout must be positive")

    from e2b import Sandbox

    sandbox = Sandbox.create(
        template=args.template,
        timeout=args.timeout,
        metadata={
            "qea_role": "template-smoke",
            "qea_run_id": args.run_id,
            "qea_task_id": args.task,
        },
        secure=True,
        allow_internet_access=False,
    )
    try:
        result = sandbox.commands.run(
            "python --version && "
            "/opt/qea/nexau-venv/bin/python --version && "
            "/opt/qea/nexau-venv/bin/python -c "
            "\"import importlib.metadata as m; print(m.version('nexau'))\" && "
            "test -s /opt/qea/nexau-requirements.lock && "
            "sha256sum /opt/qea/nexau-requirements.lock",
            timeout=min(args.timeout, 120),
        )
        payload = {
            "sandbox_id": str(sandbox.sandbox_id),
            "exit_code": int(result.exit_code),
            "stdout": str(result.stdout or ""),
            "stderr": str(result.stderr or ""),
        }
        print(json.dumps(payload, sort_keys=True, indent=2))
        return int(result.exit_code)
    finally:
        sandbox.kill()


if __name__ == "__main__":
    raise SystemExit(main())
