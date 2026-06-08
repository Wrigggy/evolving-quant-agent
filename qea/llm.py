"""LLM clients: OpenRouter (real) + MockLLM (offline).

Real client bakes in the AHE lessons: pin the native provider via
``provider.order`` (routed providers can return empty/mis-parsed tool calls),
retry with exponential backoff on transient 402/429/5xx, and keep concurrency
small (the loop is sequential in v0; the cap is enforced if you parallelize).
"""

from __future__ import annotations

import os
import time


class MockLLM:
    """Placeholder. Mock paths (quant_agent/evolve_agent/judge) are scripted and
    never actually call an LLM, but a client object is still passed around."""

    def complete(self, prompt: str, *, role: str = "agent") -> str:  # noqa: ARG002
        return ""


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
        order = os.environ.get("QEA_PROVIDER_ORDER", "").strip()
        self.provider_order = [p.strip() for p in order.split(",") if p.strip()]

    def _model(self, role: str) -> str:
        env = self.ROLE_MODEL_ENV.get(role, "QEA_QUANT_AGENT_MODEL")
        return os.environ.get(env, "deepseek/deepseek-v4-pro")

    def complete(self, prompt: str, *, role: str = "agent") -> str:
        extra: dict = {}
        if self.provider_order:
            extra["provider"] = {"order": self.provider_order, "allow_fallbacks": False}
        last: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self._model(role),
                    messages=[{"role": "user", "content": prompt}],
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


def make_llm(mock: bool):
    return MockLLM() if mock else OpenRouterLLM()
