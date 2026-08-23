#!/usr/bin/env python3
"""Run one batched Candidate Information-Set Reviewer canary."""

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

from qea.candidate_information_set_review import (  # noqa: E402
    run_candidate_information_set_review,
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
    """Fetch OpenRouter accounting without repeating the Reviewer request."""

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
        except Exception:  # Accounting failure must not repeat the model call.
            continue
    return {"status": "unavailable"}


def _openrouter_complete(
    prompt: str,
    *,
    model: str,
    provider: str | None,
    token: str,
    request_record: dict[str, object],
) -> str:
    """Issue the one canary request using the standard library HTTP client."""

    base_url = os.environ.get(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    ).rstrip("/")
    payload: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    if provider:
        payload["provider"] = {"order": [provider], "allow_fallbacks": False}
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    timeout = float(os.environ.get("QEA_REQUEST_TIMEOUT", "90"))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read())
    request_id = result.get("id")
    choices = result.get("choices")
    content = (
        choices[0].get("message", {}).get("content")
        if isinstance(choices, list) and choices
        else None
    )
    if not isinstance(request_id, str) or not request_id:
        raise RuntimeError("Reviewer response contained no request ID")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Reviewer response contained no text")
    request_record["request_count"] = 1
    request_record["request_id"] = request_id
    request_record["requested_model"] = model
    request_record["required_provider"] = provider
    request_record["response_usage"] = result.get("usage")
    request_record["accounting"] = _generation_metadata(request_id, token)
    return content


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
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

    from qea.llm import make_llm, provider_for, resolve_provider_map

    llm = None if args.backend == "openrouter" else make_llm(False)
    review_package = json.loads(args.input.read_text(encoding="utf-8"))
    request: dict[str, object] = {"request_count": 0}

    def complete(prompt: str) -> str:
        started = time.monotonic()
        if args.backend != "openrouter":
            request["request_count"] = 1
            assert llm is not None
            content = llm.complete(prompt, role="evolve_agent")
            request["wall_seconds"] = round(time.monotonic() - started, 3)
            request["accounting"] = {"status": "unavailable"}
            return content

        model = os.environ.get(
            "QEA_EVOLVE_AGENT_MODEL", "deepseek/deepseek-v4-pro"
        )
        provider = provider_for(model, resolve_provider_map())
        token = os.environ.get("OPENROUTER_API_KEY", "")
        if not token:
            raise RuntimeError("OPENROUTER_API_KEY not set (real mode)")
        content = _openrouter_complete(
            prompt,
            model=model,
            provider=provider,
            token=token,
            request_record=request,
        )
        request["wall_seconds"] = round(time.monotonic() - started, 3)
        return content

    review = run_candidate_information_set_review(
        review_package, complete=complete
    )
    result = {
        "schema_version": 1,
        "status": "complete",
        "review_scope": "answer_rich_evolver_candidate_information_set",
        "model": os.environ.get(
            "QEA_EVOLVE_AGENT_MODEL", "deepseek/deepseek-v4-pro"
        ),
        "backend": args.backend,
        "source_input": str(args.input),
        "request": request,
        "review": review,
        "worker_visible": False,
        "promotion_authority": False,
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
