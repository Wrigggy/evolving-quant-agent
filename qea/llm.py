"""LLM clients: OpenRouter (real) + MockLLM (offline).

Real client bakes in the AHE lessons: pin the native provider via
``provider.order`` (routed providers can return empty/mis-parsed tool calls),
retry with exponential backoff on transient 402/429/5xx, and keep concurrency
small (the loop is sequential in v0; the cap is enforced if you parallelize).
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path


def _encode_image(path) -> str:
    """Local PNG/JPG -> data URL for multimodal message content."""
    p = Path(path)
    mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


class MockLLM:
    """Placeholder. Mock paths (quant_agent/evolve_agent/judge) are scripted and
    never actually call an LLM, but a client object is still passed around."""

    def complete(self, prompt: str, *, role: str = "agent", images=None) -> str:  # noqa: ARG002
        return ""


# Official (native) OpenRouter provider per model prefix — the AHE lesson: routed
# third-party providers return empty/mis-parsed completions, so every model is
# pinned to its official provider with allow_fallbacks=False. Extend/override via
# QEA_PROVIDER_MAP="prefix=provider,..." (e.g. "qwen=alibaba,deepseek=deepseek");
# legacy QEA_PROVIDER_ORDER="p1,p2" entries become identity pins (p=p).
_OFFICIAL_PROVIDERS = {"deepseek": "deepseek", "qwen": "alibaba"}


def resolve_provider_map() -> dict:
    pmap = dict(_OFFICIAL_PROVIDERS)
    for p in os.environ.get("QEA_PROVIDER_ORDER", "").split(","):
        p = p.strip()
        if p:
            pmap.setdefault(p, p)
    for pair in os.environ.get("QEA_PROVIDER_MAP", "").split(","):
        k, _, v = pair.partition("=")
        if k.strip() and v.strip():
            pmap[k.strip()] = v.strip()
    return pmap


def provider_for(model: str, pmap: dict) -> str | None:
    return pmap.get(model.split("/")[0])


class OpenRouterLLM:
    ROLE_MODEL_ENV = {
        "quant_agent": "QEA_QUANT_AGENT_MODEL",
        "evolve_agent": "QEA_EVOLVE_AGENT_MODEL",
        "judge": "QEA_JUDGE_MODEL",
    }

    def __init__(self) -> None:
        try:
            from openai import OpenAI  # optional dep
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("real mode needs `pip install openai`") from exc
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY not set (real mode)")
        base = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        # timeout is CRITICAL: without it a hung connection (e.g. via a flaky SOCKS
        # proxy) blocks forever and silently stalls the whole run. max_retries=0
        # because we do our own retry/backoff below.
        self.timeout = float(os.environ.get("QEA_REQUEST_TIMEOUT", "90"))
        self.client = OpenAI(api_key=key, base_url=base, timeout=self.timeout, max_retries=0)
        self.max_retries = int(os.environ.get("QEA_MAX_RETRIES", "5"))
        self.backoff = float(os.environ.get("QEA_BACKOFF_BASE_SEC", "2.0"))
        self.provider_map = resolve_provider_map()

    def _model(self, role: str) -> str:
        env = self.ROLE_MODEL_ENV.get(role, "QEA_QUANT_AGENT_MODEL")
        return os.environ.get(env, "deepseek/deepseek-v4-pro")

    def complete(self, prompt: str, *, role: str = "agent", images=None) -> str:
        model = self._model(role)
        extra: dict = {}
        # Every model is pinned to ITS OWN official provider (no cross-pinning:
        # a qwen judge must not be forced through deepseek's provider order).
        prov = provider_for(model, self.provider_map)
        if prov:
            extra["provider"] = {"order": [prov], "allow_fallbacks": False}
        if images:
            content = [{"type": "text", "text": prompt}]
            for im in images:
                content.append({"type": "image_url", "image_url": {"url": _encode_image(im)}})
            messages = [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": prompt}]
        last: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    extra_body=extra or None,
                )
                if not getattr(resp, "choices", None):
                    raise RuntimeError("empty choices (provider returned no completion)")
                msg = resp.choices[0].message
                content = getattr(msg, "content", None) if msg else None
                if not content:
                    raise RuntimeError("empty content (provider returned blank message)")
                return content
            except Exception as exc:  # noqa: BLE001 - retry transient errors
                last = exc
                wait = self.backoff * (2 ** attempt)
                print(f"[llm] {role} attempt {attempt + 1} failed ({type(exc).__name__}); retry in {wait:.1f}s")
                time.sleep(wait)
        raise RuntimeError(f"LLM failed after {self.max_retries} retries: {last}")


class AnthropicLLM:
    """Anthropic-Messages-protocol backend (e.g. DashScope's Anthropic-compatible
    gateway at https://dashscope.aliyuncs.com/apps/anthropic). Same per-role model
    resolution + retry/backoff as OpenRouterLLM, but speaks `messages.create`. Auth
    via a Bearer token (ANTHROPIC_AUTH_TOKEN-style), matching the Claude Code config.
    Selected by make_llm when QEA_ANTHROPIC_AUTH_TOKEN (or ANTHROPIC_AUTH_TOKEN) is set."""

    ROLE_MODEL_ENV = {
        "quant_agent": "QEA_QUANT_AGENT_MODEL",
        "evolve_agent": "QEA_EVOLVE_AGENT_MODEL",
        "judge": "QEA_JUDGE_MODEL",
    }

    def __init__(self) -> None:
        try:
            from anthropic import Anthropic  # optional dep
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("anthropic backend needs `pip install anthropic`") from exc
        token = os.environ.get("QEA_ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        if not token:
            raise RuntimeError("QEA_ANTHROPIC_AUTH_TOKEN not set (anthropic backend)")
        base = (os.environ.get("QEA_ANTHROPIC_BASE_URL")
                or os.environ.get("ANTHROPIC_BASE_URL")
                or "https://api.anthropic.com")
        self.timeout = float(os.environ.get("QEA_REQUEST_TIMEOUT", "90"))
        # max_retries=0: we own the retry/backoff loop (parity with OpenRouterLLM).
        self.client = Anthropic(base_url=base, auth_token=token, timeout=self.timeout, max_retries=0)
        self.max_retries = int(os.environ.get("QEA_MAX_RETRIES", "5"))
        self.backoff = float(os.environ.get("QEA_BACKOFF_BASE_SEC", "2.0"))
        self.max_tokens = int(os.environ.get("QEA_ANTHROPIC_MAX_TOKENS", "8192"))

    def _model(self, role: str) -> str:
        env = self.ROLE_MODEL_ENV.get(role, "QEA_QUANT_AGENT_MODEL")
        return os.environ.get(env, "deepseek-v4-pro[1m]")

    def complete(self, prompt: str, *, role: str = "agent", images=None) -> str:
        model = self._model(role)
        if images:
            blocks = [{"type": "text", "text": prompt}]
            for im in images:
                data = base64.b64encode(Path(im).read_bytes()).decode()
                mime = "image/jpeg" if str(im).lower().endswith((".jpg", ".jpeg")) else "image/png"
                blocks.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}})
            msgs = [{"role": "user", "content": blocks}]
        else:
            msgs = [{"role": "user", "content": prompt}]
        last: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self.client.messages.create(
                    model=model,
                    max_tokens=self.max_tokens,
                    temperature=0.2,
                    messages=msgs,
                )
                parts = [b.text for b in getattr(resp, "content", []) if getattr(b, "type", None) == "text"]
                content = "".join(parts).strip()
                if not content:
                    raise RuntimeError("empty content (anthropic endpoint returned no text)")
                return content
            except Exception as exc:  # noqa: BLE001 - retry transient errors
                last = exc
                wait = self.backoff * (2 ** attempt)
                print(f"[llm] {role} attempt {attempt + 1} failed ({type(exc).__name__}); retry in {wait:.1f}s")
                time.sleep(wait)
        raise RuntimeError(f"LLM failed after {self.max_retries} retries: {last}")


def make_llm(mock: bool):
    if mock:
        return MockLLM()
    # Prefer the Anthropic/DashScope backend when its token is configured; else OpenRouter.
    if os.environ.get("QEA_ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return AnthropicLLM()
    return OpenRouterLLM()
