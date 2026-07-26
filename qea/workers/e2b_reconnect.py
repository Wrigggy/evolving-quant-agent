"""Infra-only E2B resilience: reconnect on a sandbox CONNECTION drop and retry
ONLY the failed sandbox command. The LLM conversation is never touched, so the
model's output is produced exactly once (no re-sampling / no best-of-N). This is
the resilience contract: E2B disconnect -> reconnect; LLM -> single attempt.

We reconnect to the SAME sandbox by id (``AsyncSandbox.connect(sandbox_id)``),
which preserves the sandbox filesystem state (files written earlier in the run).
"""
from __future__ import annotations

import asyncio

import httpx

try:
    from stirrup.tools.code_backends.e2b import E2BCodeExecToolProvider
except ModuleNotFoundError as _stirrup_import_error:
    class E2BCodeExecToolProvider:  # type: ignore[no-redef]
        """Import-time shim so the standalone reconnect helper stays testable."""

        def __init__(self, *args, **kwargs) -> None:
            raise ModuleNotFoundError(
                "ReconnectingE2BCodeExecToolProvider requires the optional stirrup extra"
            ) from _stirrup_import_error

# Connection drops we saw through the SOCKS proxy: RemoteProtocolError ("Server
# disconnected"), ReadError, WriteError, ConnectError -- all httpx.TransportError.
# Genuine command timeouts surface as e2b TimeoutException (handled by the base
# class and returned as a CommandResult), so they are NOT caught here.
_DISCONNECT = (httpx.TransportError,)


async def call_with_reconnect(call, reconnect, *, tries: int, backoff: float):
    """Await ``call()``; on a connection drop, ``await reconnect()`` and retry.
    Retries the SANDBOX call only -- never the LLM. Raises the last error if all
    attempts fail. ``tries`` = number of reconnect attempts after the first call."""
    last: Exception | None = None
    for i in range(tries + 1):
        try:
            return await call()
        except _DISCONNECT as exc:
            last = exc
            if i == tries:
                break
            await asyncio.sleep(backoff * (2 ** i))
            await reconnect()
    raise last


class ReconnectingE2BCodeExecToolProvider(E2BCodeExecToolProvider):
    """E2BCodeExecToolProvider that reconnects the sandbox on connection drops."""

    def __init__(self, *args, reconnect_tries: int = 4, reconnect_backoff: float = 2.0, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._reconnect_tries = reconnect_tries
        self._reconnect_backoff = reconnect_backoff
        self._sid: str | None = None

    async def __aenter__(self):
        tool = await super().__aenter__()
        self._sid = getattr(self._sbx, "sandbox_id", None)
        return tool

    async def _reconnect(self) -> None:
        """Reconnect to the same sandbox (state preserved). Best-effort: a failed
        reconnect leaves the old handle so the next attempt re-raises honestly."""
        if not self._sid:
            return
        try:
            from e2b_code_interpreter import AsyncSandbox

            self._sbx = await AsyncSandbox.connect(self._sid)
        except Exception:  # noqa: BLE001 - reconnect failed; caller exhausts + raises original
            pass

    async def run_command(self, cmd: str, *, timeout=None):
        return await call_with_reconnect(
            lambda: super(ReconnectingE2BCodeExecToolProvider, self).run_command(cmd, timeout=timeout),
            self._reconnect,
            tries=self._reconnect_tries,
            backoff=self._reconnect_backoff,
        )
