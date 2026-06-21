"""Free-backend financial research tools for the FAB v2 base test, exposed as
Stirrup ``Tool`` objects. Clean-room implementations against FREE data sources
(no paid keys): official SEC EDGAR (efts.sec.gov full-text search + data.sec.gov
submissions), stooq for prices, DuckDuckGo for web search.

SEC requires a descriptive User-Agent with a contact email (politeness policy);
set QEA_SEC_USER_AGENT or it defaults to the configured contact.
"""
from __future__ import annotations

import os
import warnings
from typing import Annotated

import httpx
from pydantic import BaseModel, Field

try:
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except Exception:  # noqa: BLE001
    pass

from stirrup.core.models import Tool, ToolResult, ToolUseCountMetadata

_SEC_UA = os.environ.get("QEA_SEC_USER_AGENT", "QEA research wu2908106939@outlook.com")
_TIMEOUT = float(os.environ.get("QEA_FAB_HTTP_TIMEOUT", "45"))
# trust_env mis-routes some hosts (SEC -> TLS EOF) in this env; pass the HTTP proxy
# explicitly. https_proxy/http_proxy here are the http://host:port form that works.
_PROXY = os.environ.get("https_proxy") or os.environ.get("http_proxy") or \
    os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
_R = ToolUseCountMetadata


def _ok(content: str) -> ToolResult:
    return ToolResult(content=content[:40000], metadata=_R())


def _err(msg: str) -> ToolResult:
    return ToolResult(content=f"Error: {msg}", success=False, metadata=_R())


async def _get(url: str, *, sec: bool = False, **kw) -> httpx.Response:
    headers = {"User-Agent": _SEC_UA} if sec else {"User-Agent": "Mozilla/5.0 (QEA research)"}
    cli = httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True, headers=headers,
                            trust_env=False, proxy=_PROXY)
    async with cli as c:
        return await c.get(url, **kw)


# --------------------------------------------------------------------------- #
# 1. EDGAR full-text search                                                   #
# --------------------------------------------------------------------------- #
class EdgarSearchParams(BaseModel):
    query: Annotated[str, Field(description="Full-text query, e.g. 'CrowdStrike Charlotte AI'. "
                                            "Use quotes inside for exact phrases.")]
    forms: Annotated[str, Field(description="Optional comma-separated form types to filter, "
                                            "e.g. '10-K,10-Q'. Empty for all.")] = ""


async def _edgar_search(p: EdgarSearchParams) -> ToolResult:
    params = {"q": p.query}
    if p.forms.strip():
        params["forms"] = p.forms.strip()
    try:
        r = await _get("https://efts.sec.gov/LATEST/search-index", sec=True, params=params)
        if r.status_code != 200:
            return _err(f"EDGAR FTS {r.status_code}")
        hits = (r.json().get("hits", {}) or {}).get("hits", [])[:10]
    except Exception as exc:  # noqa: BLE001
        return _err(f"{type(exc).__name__}: {exc}")
    if not hits:
        return _ok("No EDGAR filings matched.")
    lines = []
    for h in hits:
        s = h.get("_source", {})
        adsh, _, fname = (h.get("_id", "")).partition(":")
        # accession = <filer-CIK-zeropadded>-<yy>-<seq>; first segment IS the CIK
        cik_seg = adsh.split("-")[0]
        acc = adsh.replace("-", "")
        url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik_seg)}/{acc}/{fname}"
               if cik_seg.isdigit() and acc and fname else "")
        names = "; ".join(s.get("display_names", []) or [])
        lines.append(f"- {names} | {s.get('form','?')} | filed {s.get('file_date','?')}\n  {url}")
    return _ok("EDGAR hits:\n" + "\n".join(lines))


# --------------------------------------------------------------------------- #
# 2. Company filings (ticker -> recent filings via data.sec.gov)              #
# --------------------------------------------------------------------------- #
_TICKER_CACHE: dict = {}


async def _ticker_to_cik(ticker: str) -> str | None:
    if not _TICKER_CACHE:
        r = await _get("https://www.sec.gov/files/company_tickers.json", sec=True)
        for row in r.json().values():
            _TICKER_CACHE[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
    return _TICKER_CACHE.get(ticker.upper())


class CompanyFilingsParams(BaseModel):
    ticker: Annotated[str, Field(description="Stock ticker, e.g. 'CRWD' (strip exchange prefix).")]
    forms: Annotated[str, Field(description="Comma-separated form types to keep, e.g. '10-K,10-Q'.")] = "10-K,10-Q"


async def _company_filings(p: CompanyFilingsParams) -> ToolResult:
    try:
        cik = await _ticker_to_cik(p.ticker.split(":")[-1].strip())
        if not cik:
            return _err(f"ticker {p.ticker!r} not found in SEC ticker map")
        r = await _get(f"https://data.sec.gov/submissions/CIK{cik}.json", sec=True)
        rec = r.json().get("filings", {}).get("recent", {})
        keep = {f.strip().upper() for f in p.forms.split(",") if f.strip()}
        out, n = [], 0
        for form, date, acc, doc in zip(rec.get("form", []), rec.get("filingDate", []),
                                        rec.get("accessionNumber", []), rec.get("primaryDocument", [])):
            if keep and form.upper() not in keep:
                continue
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{doc}"
            out.append(f"- {form} | filed {date}\n  {url}")
            n += 1
            if n >= 12:
                break
    except Exception as exc:  # noqa: BLE001
        return _err(f"{type(exc).__name__}: {exc}")
    return _ok(f"Filings for {p.ticker} (CIK {cik}):\n" + ("\n".join(out) or "none"))


# --------------------------------------------------------------------------- #
# 3. Fetch + extract page text (filings / web pages)                          #
# --------------------------------------------------------------------------- #
async def _fetch_text(url: str) -> str:
    """Full extracted text of a page (no truncation). Raises on HTTP error."""
    from bs4 import BeautifulSoup
    r = await _get(url, sec=("sec.gov" in url))
    if r.status_code != 200:
        raise RuntimeError(f"fetch {r.status_code}")
    soup = BeautifulSoup(r.text, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    return " ".join(soup.get_text(" ").split())


class FetchPageParams(BaseModel):
    url: Annotated[str, Field(description="URL to fetch (e.g. a small page). Returns extracted text "
                                          "(<=40k chars). For LARGE SEC filings use retrieve_from_filing instead.")]


async def _fetch_page(p: FetchPageParams) -> ToolResult:
    try:
        text = await _fetch_text(p.url)
    except Exception as exc:  # noqa: BLE001
        return _err(f"{type(exc).__name__}: {exc}")
    return _ok(f"[{p.url}] ({len(text)} chars; first 40k)\n{text}")


class RetrieveParams(BaseModel):
    url: Annotated[str, Field(description="URL of a (possibly large) filing/page.")]
    query: Annotated[str, Field(description="What to find, e.g. 'artificial intelligence risks tailwind Charlotte AI'. "
                                            "Returns the most relevant passages from the document.")]


async def _retrieve(p: RetrieveParams) -> ToolResult:
    """Keyword-window retrieval over a large document: fetch full text, return the
    passages most overlapping the query (lets the agent read deep sections of a 10-K
    without dumping the whole filing)."""
    try:
        text = await _fetch_text(p.url)
    except Exception as exc:  # noqa: BLE001
        return _err(f"{type(exc).__name__}: {exc}")
    terms = {w for w in "".join(c.lower() if c.isalnum() else " " for c in p.query).split() if len(w) > 2}
    if not terms:
        return _ok(text[:12000])
    win, step = 1600, 1200
    scored = []
    for i in range(0, max(1, len(text) - win + 1), step):
        chunk = text[i:i + win]
        low = chunk.lower()
        score = sum(low.count(t) for t in terms)
        if score:
            scored.append((score, i, chunk))
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = scored[:7]
    if not top:
        return _ok(f"No passages matched {sorted(terms)} in [{p.url}] ({len(text)} chars).")
    top.sort(key=lambda x: x[1])  # restore document order
    body = "\n …\n".join(c for _, _, c in top)
    return _ok(f"[{p.url}] top passages for {sorted(terms)} (doc {len(text)} chars):\n…{body}…")


# --------------------------------------------------------------------------- #
# 4. Price history (stooq, free)                                              #
# --------------------------------------------------------------------------- #
class PriceHistoryParams(BaseModel):
    ticker: Annotated[str, Field(description="Ticker, e.g. 'AAPL'.")]
    start: Annotated[str, Field(description="Start date YYYY-MM-DD.")]
    end: Annotated[str, Field(description="End date YYYY-MM-DD.")]


async def _price_history(p: PriceHistoryParams) -> ToolResult:
    """Free pricing via Yahoo chart API (JSON); stooq CSV as fallback."""
    from datetime import datetime, timezone
    sym = p.ticker.upper().split(":")[-1].strip()
    try:
        t1 = int(datetime.strptime(p.start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        t2 = int(datetime.strptime(p.end, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) + 86400
    except ValueError:
        return _err("dates must be YYYY-MM-DD")
    # Yahoo chart (primary)
    try:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
               f"?period1={t1}&period2={t2}&interval=1d")
        r = await _get(url)
        res = (r.json().get("chart", {}).get("result") or [None])[0]
        if res:
            ts = res.get("timestamp", []) or []
            q = (res.get("indicators", {}).get("quote") or [{}])[0]
            rows = []
            for i, t in enumerate(ts):
                d = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
                def g(k):
                    v = (q.get(k) or [None] * len(ts))[i]
                    return f"{v:.2f}" if isinstance(v, (int, float)) else ""
                rows.append(f"{d},{g('open')},{g('high')},{g('low')},{g('close')},{g('volume')}")
            if rows:
                head = "Date,Open,High,Low,Close,Volume"
                samp = "\n".join([head] + rows[:3] + (["..."] + rows[-3:] if len(rows) > 6 else rows[3:]))
                return _ok(f"Daily OHLCV {sym} {p.start}..{p.end} ({len(rows)} rows, Yahoo):\n{samp}")
    except Exception:  # noqa: BLE001
        pass
    # stooq fallback
    try:
        r = await _get(f"https://stooq.com/q/d/l/?s={sym.lower()}.us"
                       f"?d1={p.start.replace('-','')}&d2={p.end.replace('-','')}&i=d")
        body = r.text.strip()
        if body and not body.lower().startswith("<") and "Date" in body.splitlines()[0]:
            rows = body.splitlines()
            return _ok(f"Daily OHLCV {sym} (stooq, {len(rows)-1} rows):\n" + "\n".join(rows[:7]))
    except Exception:  # noqa: BLE001
        pass
    return _err(f"no free price data available for {sym}")


# --------------------------------------------------------------------------- #
# 5. Web search (DuckDuckGo, free)                                            #
# --------------------------------------------------------------------------- #
class WebSearchParams(BaseModel):
    query: Annotated[str, Field(description="Web search query.")]


def _web_search(p: WebSearchParams) -> ToolResult:
    try:
        try:
            from ddgs import DDGS  # package renamed
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS(proxy=_PROXY) as ddgs:
            res = list(ddgs.text(p.query, max_results=8))
    except Exception as exc:  # noqa: BLE001
        return _err(f"{type(exc).__name__}: {exc}")
    if not res:
        return _ok("No web results.")
    lines = [f"- {r.get('title','')}\n  {r.get('href','')}\n  {r.get('body','')[:200]}" for r in res]
    return _ok("Web results:\n" + "\n".join(lines))


def fab_tools() -> list:
    """The free-backend FAB research toolset as Stirrup Tools."""
    return [
        Tool[EdgarSearchParams, _R](name="edgar_search",
            description="Full-text search SEC EDGAR filings (free official API). Returns matching "
                        "filings with company, form, date, and document URL.",
            parameters=EdgarSearchParams, executor=_edgar_search),
        Tool[CompanyFilingsParams, _R](name="company_filings",
            description="List a company's recent SEC filings by ticker (resolves ticker->CIK). "
                        "Use to find a specific 10-K/10-Q URL.",
            parameters=CompanyFilingsParams, executor=_company_filings),
        Tool[FetchPageParams, _R](name="fetch_page",
            description="Fetch a URL and return its extracted text (<=40k chars). For LARGE filings "
                        "prefer retrieve_from_filing.",
            parameters=FetchPageParams, executor=_fetch_page),
        Tool[RetrieveParams, _R](name="retrieve_from_filing",
            description="Retrieve the most relevant passages from a large filing/page by query "
                        "(keyword search inside the document). Use this to read specific topics in a 10-K/10-Q.",
            parameters=RetrieveParams, executor=_retrieve),
        Tool[PriceHistoryParams, _R](name="price_history",
            description="Daily OHLCV price history for an equity ticker (free, via stooq).",
            parameters=PriceHistoryParams, executor=_price_history),
        Tool[WebSearchParams, _R](name="web_search",
            description="General web search (free, via DuckDuckGo). Returns titles, URLs, snippets.",
            parameters=WebSearchParams, executor=_web_search),
    ]
