"""Minimal stdlib-only .xlsx writer (zipfile + hand-built OOXML). No third-party deps.

write_xlsx(path, sheets) writes a real Excel workbook readable by Excel/LibreOffice:
  sheets = {"Sheet1": [["Header A", "Header B"], [1, 2.5], ["text", 42]], ...}
Cell values: str -> inline string; int/float -> number; None -> empty.
"""
from __future__ import annotations

import zipfile
from xml.sax.saxutils import escape

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
{sheet_overrides}
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>{sheets}</sheets>
</workbook>"""

_WB_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{rels}
</Relationships>"""


def _col_letter(idx: int) -> str:
    s = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def _cell_xml(row_i: int, col_i: int, v) -> str:
    if v is None or v == "":
        return ""
    ref = f"{_col_letter(col_i)}{row_i + 1}"
    if isinstance(v, bool):
        return f'<c r="{ref}" t="b"><v>{int(v)}</v></c>'
    if isinstance(v, (int, float)):
        return f'<c r="{ref}"><v>{v}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'


def _sheet_xml(rows) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
             "<sheetData>"]
    for ri, row in enumerate(rows or []):
        cells = "".join(_cell_xml(ri, ci, v) for ci, v in enumerate(row))
        parts.append(f'<row r="{ri + 1}">{cells}</row>')
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


def write_xlsx(path: str, sheets: dict) -> str:
    """Write `sheets` ({name: rows}) to `path` as a valid .xlsx. Returns the path."""
    if not sheets:
        sheets = {"Sheet1": []}
    names = list(sheets.keys())
    overrides, sheet_tags, rel_tags = [], [], []
    for i, name in enumerate(names, start=1):
        overrides.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                         'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        sheet_tags.append(f'<sheet name="{escape(name)[:31]}" sheetId="{i}" r:id="rId{i}"/>')
        rel_tags.append(f'<Relationship Id="rId{i}" '
                        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                        f'Target="worksheets/sheet{i}.xml"/>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES.format(sheet_overrides="\n".join(overrides)))
        z.writestr("_rels/.rels", _RELS)
        z.writestr("xl/workbook.xml", _WORKBOOK.format(sheets="".join(sheet_tags)))
        z.writestr("xl/_rels/workbook.xml.rels", _WB_RELS.format(rels="\n".join(rel_tags)))
        for i, name in enumerate(names, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(sheets[name]))
    return str(path)


if __name__ == "__main__":
    import sys
    write_xlsx(sys.argv[1] if len(sys.argv) > 1 else "demo.xlsx",
               {"Demo": [["Item", "Amount"], ["Revenue", 1234.5], ["Cost", -200]]})
    print("wrote demo xlsx")
