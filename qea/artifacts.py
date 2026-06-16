"""Artifact handling for the B-pile worker: extract the worker's openpyxl code,
render a produced .xlsx to faithful text, and orchestrate produce->capture->render.

The text rendering is the interim grader bridge (sub-project 1): it makes artifact
rubric criteria creditable by the existing text SoftJudge. NOTE (known v0.1 limit):
openpyxl-written formulas carry no computed value, so we render the formula STRING +
literal values, not formula results — value computation is sub-project 3."""
from __future__ import annotations

from pathlib import Path


def extract_openpyxl_code(text: str) -> str | None:
    """Return the first ```python code block that builds + saves a workbook
    (mentions openpyxl AND saves), else None (text deliverable)."""
    if "```" not in text:
        return None
    parts = text.split("```")
    for i in range(1, len(parts), 2):           # odd indices are fenced blocks
        block = parts[i]
        if block.startswith("python"):
            block = block[len("python"):]
        if "openpyxl" in block and ".save(" in block:
            return block.strip()
    return None


def _strip_code_blocks(text: str) -> str:
    """Drop fenced ``` blocks, leaving the narrative."""
    if "```" not in text:
        return text.strip()
    parts = text.split("```")
    return "".join(parts[i] for i in range(0, len(parts), 2)).strip()


def render_xlsx(path, max_rows: int = 100, max_cols: int = 30) -> str:
    """Faithful text dump of a workbook: filename + per-sheet name/dims + a bounded
    grid of non-empty cells (literal values, and formula strings for formula cells)."""
    import openpyxl  # lazy: keeps qea.artifacts importable without the [artifacts] extra
    wb = openpyxl.load_workbook(path, data_only=False)
    lines = [f"[ARTIFACT FILE: {Path(path).name}]"]
    for ws in wb.worksheets:
        lines.append(f'Sheet "{ws.title}" ({ws.max_row}x{ws.max_column}):')
        for row in ws.iter_rows(max_row=min(ws.max_row, max_rows),
                                max_col=min(ws.max_column, max_cols)):
            for cell in row:
                if cell.value is not None:
                    lines.append(f"  {cell.coordinate}: {cell.value!r}")
        if ws.max_row > max_rows or ws.max_column > max_cols:
            lines.append(f"  ...(truncated to {max_rows}x{max_cols})")
    return "\n".join(lines)
