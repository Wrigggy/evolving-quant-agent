#!/usr/bin/env python3
"""Fork the openai/gdpval gold dataset (v2: prompts + rubrics + deliverable URLs)
into data/gdpval/ so runs are pinned + offline-reproducible, with optional push
to the Hugging Face Hub.

    python scripts/fork_gdpval.py                       # local snapshot only
    python scripts/fork_gdpval.py --push USER/gdpval-rubrics-fork   # also push to HF

Writes:
    data/gdpval/gdpval_gold.parquet   full 220-task gold parquet (verbatim copy)
    data/gdpval/rubrics.jsonl         per-task rubric extract (task_id, sector,
                                      occupation, rubric_pretty, rubric_json)
    data/gdpval/MANIFEST.md           provenance: source URL, fetch date, SHA256s

The push uses HF_TOKEN (or huggingface-cli login) and creates a public dataset
repo unless --private is given. GDPval is published by OpenAI under its dataset
license; the fork keeps the content verbatim and records provenance.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://huggingface.co/datasets/openai/gdpval/resolve/main/data/train-00000-of-00001.parquet"
)
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "gdpval"


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch() -> bytes:
    print(f"[fork] downloading {SOURCE_URL}")
    with urllib.request.urlopen(SOURCE_URL, timeout=120) as resp:
        return resp.read()


def write_snapshot(raw: bytes) -> dict:
    import pandas as pd

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pq = DATA_DIR / "gdpval_gold.parquet"
    pq.write_bytes(raw)

    df = pd.read_parquet(io.BytesIO(raw))
    jl = DATA_DIR / "rubrics.jsonl"
    with jl.open("w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            f.write(json.dumps({
                "task_id": str(row["task_id"]),
                "sector": str(row["sector"]),
                "occupation": str(row["occupation"]),
                "rubric_pretty": str(row.get("rubric_pretty", "")),
                "rubric_json": str(row.get("rubric_json", "")),
            }, ensure_ascii=False) + "\n")

    manifest = {
        "source": SOURCE_URL,
        "fetched_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "n_tasks": int(len(df)),
        "columns": list(df.columns),
        "sha256": {
            "gdpval_gold.parquet": _sha256(raw),
            "rubrics.jsonl": _sha256(jl.read_bytes()),
        },
    }
    (DATA_DIR / "MANIFEST.md").write_text(
        "# GDPval gold snapshot (local fork)\n\n"
        f"- source: {manifest['source']}\n"
        f"- fetched (UTC): {manifest['fetched_utc']}\n"
        f"- tasks: {manifest['n_tasks']}\n"
        f"- columns: {', '.join(manifest['columns'])}\n"
        f"- sha256 gdpval_gold.parquet: {manifest['sha256']['gdpval_gold.parquet']}\n"
        f"- sha256 rubrics.jsonl: {manifest['sha256']['rubrics.jsonl']}\n\n"
        "Verbatim copy of the openai/gdpval gold subset (v2 release: rubrics + human\n"
        "deliverable URLs). Loaders in qea/tasks.py read this snapshot first and only\n"
        "fall back to the network when it is missing.\n",
        encoding="utf-8",
    )
    print(f"[fork] wrote {pq} ({len(raw)/1e6:.1f} MB), {jl}, MANIFEST.md")
    return manifest


def push(repo_id: str, private: bool) -> None:
    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo_id, repo_type="dataset", private=private, exist_ok=True)
    api.upload_folder(folder_path=str(DATA_DIR), repo_id=repo_id, repo_type="dataset")
    print(f"[fork] pushed to https://huggingface.co/datasets/{repo_id}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--push", metavar="REPO_ID", help="also push the fork to this HF dataset repo")
    ap.add_argument("--private", action="store_true", help="make the HF repo private")
    args = ap.parse_args()

    raw = fetch()
    write_snapshot(raw)
    if args.push:
        push(args.push, args.private)
    return 0


if __name__ == "__main__":
    sys.exit(main())
