"""Fetch GDPval reference INPUT files for the finance tasks into the local fork.

GDPval ships each task's input attachments in `reference_file_urls`; the worker
needs them to do the task faithfully (instead of improvising data). Saves to
data/gdpval/reference_files/<task_id>/<basename> so qea.tasks._local_reference_files
can resolve them. Idempotent (skips existing). Uses httpx (SOCKS-proxy aware).

    .venv312/bin/python scripts/fetch_gdpval_reference_files.py
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "data" / "gdpval" / "gdpval_gold.parquet"
REF_DIR = ROOT / "data" / "gdpval" / "reference_files"
FIN_OCC = (
    "Accountants and Auditors", "Financial Managers",
    "Financial and Investment Analysts", "Personal Financial Advisors",
    "Securities", "Real Estate Brokers",
)


def main() -> None:
    df = pd.read_parquet(PARQUET)
    sel = df[df["occupation"].apply(lambda o: any(s in str(o) for s in FIN_OCC))]
    client = httpx.Client(timeout=180, follow_redirects=True)
    got = skipped = failed = 0
    for _, row in sel.iterrows():
        tid = str(row["task_id"])
        _u = row.get("reference_file_urls")
        _r = row.get("reference_files")
        urls = list(_u) if _u is not None else []
        refs = list(_r) if _r is not None else []
        for i, url in enumerate(urls):
            name = unquote(str(refs[i]).split("/")[-1] if i < len(refs) else str(url).split("/")[-1])
            dest = REF_DIR / tid / name
            if dest.exists():
                skipped += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                r = client.get(url)
                r.raise_for_status()
                dest.write_bytes(r.content)
                got += 1
                print(f"got  {tid[:8]} {name} ({len(r.content)} B)")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"FAIL {tid[:8]} {name}: {type(exc).__name__}: {exc}")
    client.close()
    print(f"\ndone: {got} downloaded, {skipped} already present, {failed} failed")
    def _has_ref(r):
        v = r.get("reference_files")
        return v is not None and len(list(v)) > 0
    n_tasks_with_refs = sum(1 for _, r in sel.iterrows() if _has_ref(r))
    print(f"finance tasks with >=1 reference file: {n_tasks_with_refs}/{len(sel)}")


if __name__ == "__main__":
    main()
