#!/usr/bin/env python3
"""Make one bounded, provider-pinned OpenRouter reasoning-route probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


_ROUTE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_REASONING = frozenset({"minimal", "low", "medium", "high", "xhigh"})
_COMPLETIONS = "https://openrouter.ai/api/v1/chat/completions"
_GENERATION = "https://openrouter.ai/api/v1/generation"


def _private_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, sort_keys=True, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _request(request: urllib.request.Request, *, timeout: int = 60) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
            detail = body.get("error", {}).get("message", "")
        except Exception:  # noqa: BLE001
            detail = ""
        raise RuntimeError(
            f"OpenRouter route probe failed with HTTP {exc.code}: {detail[:500]}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("OpenRouter route probe returned a non-object")
    return payload


def _generation(generation_id: str, token: str) -> dict:
    url = _GENERATION + "?" + urllib.parse.urlencode({"id": generation_id})
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    last_error = "not queried"
    for delay in (0, 2, 4, 8, 12):
        if delay:
            time.sleep(delay)
        try:
            payload = _request(request, timeout=30)
            data = payload.get("data")
            if isinstance(data, dict):
                return data
            last_error = "response has no data object"
        except RuntimeError as exc:
            last_error = str(exc)
    raise RuntimeError(f"generation metadata unavailable: {last_error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--reasoning-effort", choices=sorted(_REASONING), required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approve-external-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.approve_external_run:
        raise ValueError("external model execution was not approved")
    if _ROUTE.fullmatch(args.model) is None or _ROUTE.fullmatch(args.provider) is None:
        raise ValueError("model or provider route is unsafe")
    output = args.output.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"publish-once route probe exists: {output}")
    token = args.token_file.expanduser().resolve().read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("model token file is empty")
    body = {
        "model": args.model,
        "messages": [
            {
                "role": "user",
                "content": "Reply with exactly A4_ROUTE_OK and nothing else.",
            }
        ],
        "max_tokens": 1024,
        "provider": {
            "only": [args.provider],
            "allow_fallbacks": False,
        },
        "reasoning": {
            "effort": args.reasoning_effort,
            "exclude": True,
        },
    }
    request = urllib.request.Request(
        _COMPLETIONS,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    started = time.time()
    response = _request(request, timeout=180)
    generation_id = response.get("id")
    if not isinstance(generation_id, str) or not generation_id:
        raise RuntimeError("route probe response has no generation ID")
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("route probe response has no choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise RuntimeError("route probe response has no message")
    content = str(message.get("content", "") or "")
    metadata = _generation(generation_id, token)
    token = ""
    provider_name = metadata.get("provider_name")
    if not isinstance(provider_name, str) or (
        provider_name.casefold().replace(" ", "")
        != args.provider.casefold().replace(" ", "")
    ):
        raise RuntimeError(f"unexpected resolved provider: {provider_name!r}")
    record = {
        "schema_version": 1,
        "status": "accepted" if content.strip() == "A4_ROUTE_OK" else "unexpected_text",
        "requested_model": args.model,
        "required_provider": args.provider,
        "reasoning_effort": args.reasoning_effort,
        "allow_fallbacks": False,
        "generation_id": generation_id,
        "resolved_model": metadata.get("model"),
        "resolved_provider": provider_name,
        "total_cost": metadata.get("total_cost"),
        "tokens_prompt": metadata.get("tokens_prompt"),
        "tokens_completion": metadata.get("tokens_completion"),
        "response_content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "response_matched": content.strip() == "A4_ROUTE_OK",
        "usage": response.get("usage"),
        "wall_seconds": round(time.time() - started, 3),
    }
    _private_json(output, record)
    print(json.dumps(record, sort_keys=True, indent=2))
    return 0 if record["status"] == "accepted" else 2


if __name__ == "__main__":
    raise SystemExit(main())
