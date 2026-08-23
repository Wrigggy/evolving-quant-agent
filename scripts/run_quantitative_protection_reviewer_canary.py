#!/usr/bin/env python3
"""Run one batched answer-free QPR-1 Reviewer canary."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qea.quantitative_protection_review import (  # noqa: E402
    run_quantitative_regression_review,
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


def _generation_metadata(request_id: str, token: str) -> dict[str, object]:
    """Fetch OpenRouter accounting after the single Reviewer request."""

    url = "https://openrouter.ai/api/v1/generation?" + urllib.parse.urlencode(
        {"id": request_id}
    )
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    for delay in (0, 2, 4, 8):
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read())
            data = payload.get("data")
            if isinstance(data, dict):
                return {
                    "provider": data.get("provider_name"),
                    "resolved_model": data.get("model"),
                    "provider_cost_usd": data.get("total_cost"),
                    "prompt_tokens": data.get("tokens_prompt"),
                    "completion_tokens": data.get("tokens_completion"),
                }
        except Exception:  # Accounting is evidence, not a reason to rerun the model.
            continue
    return {"status": "unavailable"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/breadth/QPR1_REVIEW_CASES.json"),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dotenv", type=Path, default=Path(".env"))
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--backend", choices=("openrouter", "auto"), default="openrouter"
    )
    args = parser.parse_args()

    _load_dotenv(args.dotenv)
    if args.model:
        os.environ["QEA_EVOLVE_AGENT_MODEL"] = args.model

    from qea.llm import OpenRouterLLM, make_llm, provider_for

    llm = OpenRouterLLM() if args.backend == "openrouter" else make_llm(False)
    source = json.loads(args.cases.read_text(encoding="utf-8"))
    cases = source["cases"]
    request_record: dict[str, object] = {"request_count": 0}

    def complete(prompt: str) -> str:
        started = time.monotonic()
        if args.backend != "openrouter":
            request_record["request_count"] = 1
            content = llm.complete(prompt, role="evolve_agent")
            request_record["wall_seconds"] = round(time.monotonic() - started, 3)
            request_record["accounting"] = {"status": "unavailable"}
            return content

        model = llm._model("evolve_agent")
        provider = provider_for(model, llm.provider_map)
        extra = (
            {"provider": {"order": [provider], "allow_fallbacks": False}}
            if provider
            else None
        )
        response = llm.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            extra_body=extra,
        )
        request_record["request_count"] = 1
        request_record["request_id"] = response.id
        request_record["requested_model"] = model
        request_record["required_provider"] = provider
        request_record["wall_seconds"] = round(time.monotonic() - started, 3)
        usage = getattr(response, "usage", None)
        request_record["response_usage"] = (
            usage.model_dump() if usage is not None else None
        )
        token = os.environ.get("OPENROUTER_API_KEY", "")
        request_record["accounting"] = _generation_metadata(response.id, token)
        choices = getattr(response, "choices", None)
        content = choices[0].message.content if choices else None
        if not content:
            raise RuntimeError("Reviewer response contained no text")
        return content

    review = run_quantitative_regression_review(
        cases,
        complete=complete,
    )
    result = {
        "schema_version": 1,
        "status": "complete",
        "review_scope": "answer_free_development_protection",
        "model": os.environ.get(
            "QEA_EVOLVE_AGENT_MODEL", "deepseek/deepseek-v4-pro"
        ),
        "backend": args.backend,
        "source_cases": str(args.cases),
        "request": request_record,
        "review": review,
    }
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "RESULT.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
