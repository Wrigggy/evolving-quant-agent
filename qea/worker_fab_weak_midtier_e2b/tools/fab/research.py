"""FAB research tools — NexAU bindings (clean-room, free backends, no paid keys).

Ported from the Stirrup version: official SEC EDGAR (efts.sec.gov / data.sec.gov),
Yahoo/stooq prices, DuckDuckGo. Sync httpx with an explicit proxy (trust_env
mis-routes SEC in this env). Each tool returns {"content": str} per NexAU's
tool contract; params match the tool_descriptions/*.tool.yaml input_schema.
"""
from __future__ import annotations

import os
import warnings
from datetime import datetime, timezone

import httpx

try:
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except Exception:  # noqa: BLE001
    pass

_SEC_UA = os.environ.get("QEA_SEC_USER_AGENT", "QEA research wu2908106939@outlook.com")
_TIMEOUT = float(os.environ.get("QEA_FAB_HTTP_TIMEOUT", "45"))
_PROXY = (os.environ.get("https_proxy") or os.environ.get("http_proxy")
          or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY"))
_MAX = 40000


def _content(s: str) -> dict:
    return {"content": s[:_MAX]}


def _get(url: str, *, sec: bool = False, **kw) -> httpx.Response:
    headers = {"User-Agent": _SEC_UA if sec else "Mozilla/5.0 (QEA research)"}
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=headers,
                      trust_env=False, proxy=_PROXY) as c:
        return c.get(url, **kw)


# --------------------------------------------------------------------------- #
def edgar_search(query: str, forms: str = "") -> dict:
    params = {"q": query}
    if forms.strip():
        params["forms"] = forms.strip()
    try:
        r = _get("https://efts.sec.gov/LATEST/search-index", sec=True, params=params)
        if r.status_code != 200:
            return _content(f"Error: EDGAR FTS {r.status_code}")
        hits = (r.json().get("hits", {}) or {}).get("hits", [])[:10]
    except Exception as exc:  # noqa: BLE001
        return _content(f"Error: {type(exc).__name__}: {exc}")
    if not hits:
        return _content("No EDGAR filings matched.")
    lines = []
    for h in hits:
        s = h.get("_source", {})
        adsh, _, fname = (h.get("_id", "")).partition(":")
        cik_seg = adsh.split("-")[0]
        url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik_seg)}/{adsh.replace('-','')}/{fname}"
               if cik_seg.isdigit() and fname else "")
        lines.append(f"- {'; '.join(s.get('display_names', []) or [])} | {s.get('form','?')} | "
                     f"filed {s.get('file_date','?')}\n  {url}")
    return _content("EDGAR hits:\n" + "\n".join(lines))


_TICKER_CACHE: dict = {}


def _ticker_to_cik(ticker: str) -> str | None:
    if not _TICKER_CACHE:
        r = _get("https://www.sec.gov/files/company_tickers.json", sec=True)
        for row in r.json().values():
            _TICKER_CACHE[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
    return _TICKER_CACHE.get(ticker.upper())


def company_filings(ticker: str, forms: str = "10-K,10-Q") -> dict:
    try:
        cik = _ticker_to_cik(ticker.split(":")[-1].strip())
        if not cik:
            return _content(f"Error: ticker {ticker!r} not found")
        r = _get(f"https://data.sec.gov/submissions/CIK{cik}.json", sec=True)
        rec = r.json().get("filings", {}).get("recent", {})
        keep = {f.strip().upper() for f in forms.split(",") if f.strip()}
        out, n = [], 0
        for form, date, acc, doc in zip(rec.get("form", []), rec.get("filingDate", []),
                                        rec.get("accessionNumber", []), rec.get("primaryDocument", [])):
            if keep and form.upper() not in keep:
                continue
            out.append(f"- {form} | filed {date}\n  https://www.sec.gov/Archives/edgar/data/"
                       f"{int(cik)}/{acc.replace('-','')}/{doc}")
            n += 1
            if n >= 12:
                break
    except Exception as exc:  # noqa: BLE001
        return _content(f"Error: {type(exc).__name__}: {exc}")
    return _content(f"Filings for {ticker} (CIK {cik}):\n" + ("\n".join(out) or "none"))


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


def retrieve_from_filing(url: str, query: str) -> dict:
    try:
        text = _fetch_text(url)
    except Exception as exc:  # noqa: BLE001
        return _content(f"Error: {type(exc).__name__}: {exc}")
    terms = {w for w in "".join(c.lower() if c.isalnum() else " " for c in query).split() if len(w) > 2}
    if not terms:
        return _content(text[:12000])
    win, step, scored = 1600, 1200, []
    for i in range(0, max(1, len(text) - win + 1), step):
        chunk = text[i:i + win]
        sc = sum(chunk.lower().count(t) for t in terms)
        if sc:
            scored.append((sc, i, chunk))
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = sorted(scored[:7], key=lambda x: x[1])
    if not top:
        return _content(f"No passages matched {sorted(terms)} in [{url}] ({len(text)} chars).")
    return _content(f"[{url}] top passages for {sorted(terms)} (doc {len(text)} chars):\n…"
                    + "\n …\n".join(c for _, _, c in top) + "…")


def price_history(ticker: str, start: str, end: str) -> dict:
    sym = ticker.upper().split(":")[-1].strip()
    try:
        t1 = int(datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        t2 = int(datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) + 86400
    except ValueError:
        return _content("Error: dates must be YYYY-MM-DD")
    try:
        r = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={t1}&period2={t2}&interval=1d")
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
                samp = "\n".join(["Date,Open,High,Low,Close,Volume"] + rows[:3]
                                 + (["..."] + rows[-3:] if len(rows) > 6 else rows[3:]))
                return _content(f"Daily OHLCV {sym} {start}..{end} ({len(rows)} rows, Yahoo):\n{samp}")
    except Exception:  # noqa: BLE001
        pass
    return _content(f"Error: no free price data for {sym}")


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
