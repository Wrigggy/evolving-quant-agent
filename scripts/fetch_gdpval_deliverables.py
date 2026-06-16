#!/usr/bin/env python3
"""Download the human GOLD deliverable files for every GDPval gold task.

The local fork (`data/gdpval/gdpval_gold.parquet`) ships prompts + rubrics + the
*URLs* of each task's human gold deliverable files, but not the binaries. This
script fetches those binaries (the actual .xlsx/.pptx/.docx/.pdf the human expert
produced) so a file-aware grader can compare a model's output against gold.

Layout written:  data/gdpval/deliverable_files/<task_id>/<basename>
Idempotent: skips files already present. Public HF `resolve` URLs, no auth needed.

Usage:
    python3 scripts/fetch_gdpval_deliverables.py            # all 220 gold tasks
    python3 scripts/fetch_gdpval_deliverables.py --kind reference   # input files instead
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "data" / "gdpval" / "gdpval_gold.parquet"
TIMEOUT = 60.0
RETRIES = 3


def _as_list(v) -> list:
    """The parquet stores list columns as Python-repr strings or arrays."""
    if v is None:
        return []
    if isinstance(v, str):
        try:
            return list(ast.literal_eval(v))
        except Exception:  # noqa: BLE001
            return []
    try:
        return list(v)
    except Exception:  # noqa: BLE001
        return []


def _download(url: str, dest: Path) -> tuple[str, int, str | None]:
    """Return (url, bytes, error). Skips if dest already exists and is non-empty."""
    if dest.exists() and dest.stat().st_size > 0:
        return url, dest.stat().st_size, "skip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
                data = r.read()
            dest.write_bytes(data)
            return url, len(data), None
        except Exception as exc:  # noqa: BLE001
            last = exc
    return url, 0, f"{type(last).__name__}: {last}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch GDPval gold deliverable (or reference) files")
    ap.add_argument("--kind", choices=["deliverable", "reference"], default="deliverable",
                    help="which file set to fetch (default: deliverable = the human gold outputs)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    try:
        import pandas as pd
    except ImportError:
        print("needs pandas/pyarrow: pip install -e '.[gdpval]'", file=sys.stderr)
        return 2
    if not PARQUET.exists():
        print(f"missing {PARQUET} — run scripts/fork_gdpval.py first", file=sys.stderr)
        return 2

    df = pd.read_parquet(PARQUET)
    out_root = ROOT / "data" / "gdpval" / f"{args.kind}_files"
    url_col = f"{args.kind}_file_urls"
    name_col = f"{args.kind}_files"

    # Build the (url -> dest) job list: per task, zip decoded basenames with URLs.
    jobs: list[tuple[str, Path]] = []
    n_tasks_with_files = 0
    for _, row in df.iterrows():
        urls = _as_list(row.get(url_col))
        names = _as_list(row.get(name_col))
        if not urls:
            continue
        n_tasks_with_files += 1
        tid = str(row["task_id"])
        for i, url in enumerate(urls):
            # prefer the decoded human-readable basename from <kind>_files; fall back to URL
            if i < len(names):
                base = Path(str(names[i])).name
            else:
                base = urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name)
            jobs.append((str(url), out_root / tid / base))

    print(f"[fetch] {args.kind}: {len(df)} gold tasks, {n_tasks_with_files} have files, "
          f"{len(jobs)} files to fetch -> {out_root}", flush=True)

    ok = skipped = failed = 0
    total_bytes = 0
    failures: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_download, url, dest): (url, dest) for url, dest in jobs}
        done = 0
        for fut in concurrent.futures.as_completed(futs):
            url, nbytes, err = fut.result()
            done += 1
            if err == "skip":
                skipped += 1
                total_bytes += nbytes
            elif err is None:
                ok += 1
                total_bytes += nbytes
            else:
                failed += 1
                failures.append(f"{url} -> {err}")
            if done % 25 == 0 or done == len(jobs):
                print(f"[fetch] {done}/{len(jobs)}  (new {ok} / skip {skipped} / fail {failed})", flush=True)

    print(f"\n[fetch] DONE: {ok} downloaded, {skipped} already present, {failed} failed; "
          f"~{total_bytes/1e6:.1f} MB total in {out_root}", flush=True)
    if failures:
        print("[fetch] failures:", flush=True)
        for f in failures[:20]:
            print("  -", f, flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
