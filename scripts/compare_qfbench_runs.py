#!/usr/bin/env python3
"""Compare two complete QFBench resume checkpoints."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qea.qfbench_comparison import (
    compare_qfbench_results,
    render_qfbench_comparison_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="complete baseline run resume.json",
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="complete candidate run resume.json",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="optional path for the machine-readable comparison",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        help="optional path for the Markdown comparison report",
    )
    return parser


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    comparison = compare_qfbench_results(
        _load_json(args.baseline.resolve()),
        _load_json(args.candidate.resolve()),
    )
    json_payload = json.dumps(comparison, sort_keys=True, indent=2) + "\n"
    markdown = render_qfbench_comparison_markdown(comparison)
    if args.json_output:
        _write(args.json_output.resolve(), json_payload)
    if args.markdown_output:
        _write(args.markdown_output.resolve(), markdown)
    if not args.json_output and not args.markdown_output:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
