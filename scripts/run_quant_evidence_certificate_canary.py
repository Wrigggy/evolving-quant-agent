#!/usr/bin/env python3
"""Run the paired QEC-1 generic-versus-certificate Reviewer canary."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qea.quant_evidence_certificate import (  # noqa: E402
    load_quant_evidence_cases,
    run_reviewer_arm,
    summarize_qec1,
)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/quant_evidence_certificate_canary/cases.json"),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dotenv", type=Path, default=Path(".env"))
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--backend",
        choices=("openrouter", "auto"),
        default="openrouter",
        help="Use the pinned OpenRouter provider path by default; auto may select the configured Anthropic-compatible route.",
    )
    args = parser.parse_args()

    _load_dotenv(args.dotenv)
    if args.model:
        os.environ["QEA_EVOLVE_AGENT_MODEL"] = args.model

    from qea.llm import OpenRouterLLM, make_llm

    llm = OpenRouterLLM() if args.backend == "openrouter" else make_llm(mock=False)
    cases = load_quant_evidence_cases(args.cases)
    results = []
    for case in cases:
        for arm in ("generic", "certificate"):
            print(f"[qec-1] {case.case_id} / {arm}", flush=True)
            results.append(
                run_reviewer_arm(
                    case,
                    arm=arm,
                    complete=lambda prompt: llm.complete(
                        prompt, role="evolve_agent"
                    ),
                )
            )
    payload = summarize_qec1(tuple(results))
    payload["model"] = os.environ.get(
        "QEA_EVOLVE_AGENT_MODEL", "deepseek/deepseek-v4-pro"
    )
    payload["backend"] = args.backend
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "RESULT.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: payload[key] for key in ("model", "metrics", "improved_cases", "regressed_cases", "mechanism_gate")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
