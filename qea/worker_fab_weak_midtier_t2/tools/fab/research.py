"""Worker research tools — NexAU bindings (free backends, no paid keys).

Two generic web primitives. Sync httpx with an explicit proxy (trust_env mis-routes in
this env). Each tool returns {"content": str} per NexAU's tool contract; params match the
tool_descriptions/*.tool.yaml input_schema.
"""
from __future__ import annotations

import os
import warnings

import httpx

try:
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except Exception:  # noqa: BLE001
    pass

_UA = os.environ.get("QEA_SEC_USER_AGENT", "QEA research wu2908106939@outlook.com")
_TIMEOUT = float(os.environ.get("QEA_FAB_HTTP_TIMEOUT", "45"))
_PROXY = (os.environ.get("https_proxy") or os.environ.get("http_proxy")
          or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY"))
_MAX = 40000


def _content(s: str) -> dict:
    return {"content": s[:_MAX]}


def _get(url: str, *, sec: bool = False, **kw) -> httpx.Response:
    headers = {"User-Agent": _UA if sec else "Mozilla/5.0 (QEA research)"}
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=headers,
                      trust_env=False, proxy=_PROXY) as c:
        return c.get(url, **kw)


def _fetch_text(url: str) -> str:
    from bs4 import BeautifulSoup
    r = _get(url, sec=("sec.gov" in url))
    if r.status_code != 200:
        raise RuntimeError(f"fetch {r.status_code}")
    soup = BeautifulSoup(r.text, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    return " ".join(soup.get_text(" ").split())


def fetch_page(url: str) -> dict:
    try:
        return _content(f"[{url}]\n{_fetch_text(url)}")
    except Exception as exc:  # noqa: BLE001
        return _content(f"Error: {type(exc).__name__}: {exc}")


def web_search(query: str) -> dict:
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS(proxy=_PROXY) as ddgs:
            res = list(ddgs.text(query, max_results=8))
    except Exception as exc:  # noqa: BLE001
        return _content(f"Error: {type(exc).__name__}: {exc}")
    if not res:
        return _content("No web results.")
    return _content("Web results:\n" + "\n".join(
        f"- {r.get('title','')}\n  {r.get('href','')}\n  {r.get('body','')[:200]}" for r in res))
