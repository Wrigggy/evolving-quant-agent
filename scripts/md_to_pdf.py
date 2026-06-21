"""Minimal Markdown -> PDF (styled HTML rendered by headless Chrome).

    .venv312/bin/python scripts/md_to_pdf.py <input.md> <output.pdf>

Chrome path via CHROME_BIN env, else the macOS default. Handles unicode (✓ · −).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import markdown

CSS = """
body{font-family:-apple-system,Helvetica,Arial,sans-serif;font-size:11px;line-height:1.45;color:#222}
h1{font-size:21px;margin:0 0 6px} h2{font-size:16px;border-bottom:1px solid #ccc;padding-bottom:3px;margin:22px 0 8px}
h3{font-size:13px;margin:16px 0 4px;color:#147a3d}
table{border-collapse:collapse;font-size:9.5px;margin:6px 0} th,td{border:1px solid #bbb;padding:2px 5px;text-align:left}
th{background:#f0f0f0}
code{font-family:Menlo,Consolas,monospace;font-size:9.5px;background:#f4f4f4;padding:1px 3px;border-radius:3px;word-break:break-all}
ul{margin:4px 0 8px;padding-left:20px} li{margin:1px 0}
@page{size:A4;margin:13mm}
"""

CHROME = os.environ.get("CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def main() -> None:
    src, dst = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    body = markdown.markdown(src.read_text(),
                             extensions=["tables", "fenced_code", "sane_lists", "toc"])
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    html_path = dst.with_suffix(".html")
    html_path.write_text(html)
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={dst}", html_path.as_uri()],
        check=True, capture_output=True, timeout=180)
    print(f"wrote {dst} ({dst.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
