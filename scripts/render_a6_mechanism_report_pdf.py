#!/usr/bin/env python3
"""Render audited QEA experiment syntheses as polished PDFs."""

from __future__ import annotations

import argparse
import hashlib
import html
import re
from pathlib import Path
from typing import Any, Iterable

import mistune
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


PAGE_WIDTH, PAGE_HEIGHT = A4
NAVY = colors.HexColor("#18324A")
BLUE = colors.HexColor("#236A8D")
TEAL = colors.HexColor("#16817A")
PALE_BLUE = colors.HexColor("#EAF3F7")
PALE_TEAL = colors.HexColor("#EAF6F3")
PALE_GRAY = colors.HexColor("#F3F5F7")
MID_GRAY = colors.HexColor("#65727D")
LIGHT_GRAY = colors.HexColor("#D9E0E5")
TEXT = colors.HexColor("#17242E")
WHITE = colors.white

ASCII_DASHES = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
    }
)


def ascii_dashes(value: str) -> str:
    """Normalize Unicode dash variants for reliable embedded-font rendering."""
    return value.translate(ASCII_DASHES)


def register_fonts(chinese: bool = False) -> None:
    font_root = Path("/System/Library/Fonts")
    if chinese:
        pdfmetrics.registerFont(
            TTFont("ReportArial", str(font_root / "STHeiti Light.ttc"), subfontIndex=0)
        )
        pdfmetrics.registerFont(
            TTFont(
                "ReportArial-Bold",
                str(font_root / "STHeiti Medium.ttc"),
                subfontIndex=0,
            )
        )
        pdfmetrics.registerFont(
            TTFont(
                "ReportArial-Italic",
                str(font_root / "STHeiti Light.ttc"),
                subfontIndex=0,
            )
        )
        pdfmetrics.registerFont(
            TTFont(
                "ReportArial-BoldItalic",
                str(font_root / "STHeiti Medium.ttc"),
                subfontIndex=0,
            )
        )
    else:
        pdfmetrics.registerFont(
            TTFont("ReportArial", str(font_root / "Supplemental/Arial.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont("ReportArial-Bold", str(font_root / "Supplemental/Arial Bold.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont("ReportArial-Italic", str(font_root / "Supplemental/Arial Italic.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont(
                "ReportArial-BoldItalic",
                str(font_root / "Supplemental/Arial Bold Italic.ttf"),
            )
        )
    pdfmetrics.registerFont(TTFont("ReportMono", str(font_root / "SFNSMono.ttf")))
    pdfmetrics.registerFont(
        TTFont("ReportMono-Italic", str(font_root / "SFNSMonoItalic.ttf"))
    )
    pdfmetrics.registerFontFamily(
        "ReportArial",
        normal="ReportArial",
        bold="ReportArial-Bold",
        italic="ReportArial-Italic",
        boldItalic="ReportArial-BoldItalic",
    )


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {}
    styles["body"] = ParagraphStyle(
        "ReportBody",
        parent=base["BodyText"],
        fontName="ReportArial",
        fontSize=9.0,
        leading=12.6,
        textColor=TEXT,
        spaceAfter=4.8,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )
    styles["body_small"] = ParagraphStyle(
        "ReportBodySmall",
        parent=styles["body"],
        fontSize=8.1,
        leading=10.6,
        spaceAfter=3,
    )
    styles["cover_title"] = ParagraphStyle(
        "CoverTitle",
        parent=base["Title"],
        fontName="ReportArial-Bold",
        fontSize=26,
        leading=31,
        textColor=NAVY,
        alignment=TA_LEFT,
        spaceAfter=8,
        wordWrap="CJK",
    )
    styles["cover_kicker"] = ParagraphStyle(
        "CoverKicker",
        parent=styles["body"],
        fontName="ReportArial-Bold",
        fontSize=9,
        leading=11,
        textColor=TEAL,
        spaceAfter=8,
    )
    styles["cover_subtitle"] = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["body"],
        fontSize=12.5,
        leading=17,
        textColor=MID_GRAY,
        spaceAfter=10,
    )
    styles["cover_meta"] = ParagraphStyle(
        "CoverMeta",
        parent=styles["body"],
        fontSize=8.5,
        leading=12,
        textColor=MID_GRAY,
    )
    styles["section"] = ParagraphStyle(
        "SectionHeading",
        parent=base["Heading1"],
        fontName="ReportArial-Bold",
        fontSize=16,
        leading=19,
        textColor=NAVY,
        spaceBefore=12,
        spaceAfter=7,
        keepWithNext=True,
        wordWrap="CJK",
    )
    styles["subsection"] = ParagraphStyle(
        "SubsectionHeading",
        parent=base["Heading2"],
        fontName="ReportArial-Bold",
        fontSize=11.5,
        leading=14.5,
        textColor=BLUE,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True,
        wordWrap="CJK",
    )
    styles["toc_title"] = ParagraphStyle(
        "TOCTitle",
        parent=styles["section"],
        fontSize=20,
        leading=24,
        spaceBefore=0,
        spaceAfter=12,
    )
    styles["quote"] = ParagraphStyle(
        "Quote",
        parent=styles["body"],
        fontSize=9.2,
        leading=13,
        textColor=NAVY,
        spaceAfter=0,
    )
    styles["code"] = ParagraphStyle(
        "Code",
        parent=base["Code"],
        fontName="ReportMono",
        fontSize=7.1,
        leading=9.4,
        textColor=colors.HexColor("#26343E"),
        leftIndent=0,
        rightIndent=0,
        spaceBefore=3,
        spaceAfter=5,
        wordWrap="CJK",
    )
    styles["table"] = ParagraphStyle(
        "TableCell",
        parent=styles["body_small"],
        fontSize=7.8,
        leading=9.7,
        spaceAfter=0,
        wordWrap="CJK",
    )
    styles["table_header"] = ParagraphStyle(
        "TableHeader",
        parent=styles["table"],
        fontName="ReportArial-Bold",
        textColor=WHITE,
    )
    styles["metric_value"] = ParagraphStyle(
        "MetricValue",
        parent=styles["body"],
        fontName="ReportArial-Bold",
        fontSize=15,
        leading=18,
        textColor=NAVY,
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    styles["metric_label"] = ParagraphStyle(
        "MetricLabel",
        parent=styles["body_small"],
        fontSize=7.4,
        leading=9.2,
        textColor=MID_GRAY,
        alignment=TA_CENTER,
        spaceAfter=0,
    )
    styles["footer"] = ParagraphStyle(
        "Footer",
        parent=styles["body_small"],
        fontSize=7.2,
        leading=8,
        textColor=MID_GRAY,
    )
    return styles


def plain_text(nodes: Iterable[dict[str, Any]]) -> str:
    parts: list[str] = []
    for node in nodes:
        node_type = node.get("type")
        if node_type in {"text", "codespan"}:
            parts.append(node.get("raw", ""))
        elif node_type in {"softbreak", "linebreak"}:
            parts.append(" ")
        elif node.get("children"):
            parts.append(plain_text(node["children"]))
    return ascii_dashes("".join(parts)).strip()


class MarkdownRenderer:
    def __init__(self, styles: dict[str, ParagraphStyle], source_dir: Path) -> None:
        self.styles = styles
        self.source_dir = source_dir
        self.heading_index = 0

    def inline(self, nodes: Iterable[dict[str, Any]]) -> str:
        parts: list[str] = []
        for node in nodes:
            node_type = node.get("type")
            if node_type == "text":
                parts.append(html.escape(ascii_dashes(node.get("raw", ""))))
            elif node_type in {"softbreak", "linebreak"}:
                parts.append(" ")
            elif node_type == "strong":
                parts.append(f"<b>{self.inline(node.get('children', []))}</b>")
            elif node_type == "emphasis":
                parts.append(f"<i>{self.inline(node.get('children', []))}</i>")
            elif node_type == "codespan":
                raw = html.escape(ascii_dashes(node.get("raw", "")))
                parts.append(f'<font name="ReportMono" color="#7A3650">{raw}</font>')
            elif node_type == "link":
                label = self.inline(node.get("children", []))
                url = ascii_dashes(str(node.get("attrs", {}).get("url", "")))
                if url.startswith(("http://", "https://")):
                    parts.append(
                        f'<link href="{html.escape(url, quote=True)}" color="#236A8D">'
                        f"<u>{label}</u></link>"
                    )
                else:
                    parts.append(f'<font color="#236A8D"><u>{label}</u></font>')
            elif node_type == "image":
                alt = html.escape(ascii_dashes(node.get("attrs", {}).get("alt", "image")))
                parts.append(f"[Image: {alt}]")
            elif node.get("children"):
                parts.append(self.inline(node["children"]))
        return "".join(parts)

    def paragraph(self, node: dict[str, Any], style: str = "body") -> Paragraph:
        return Paragraph(self.inline(node.get("children", [])), self.styles[style])

    def quote(self, node: dict[str, Any]) -> Table:
        content: list[Any] = []
        for child in node.get("children", []):
            if child.get("type") == "paragraph":
                content.append(self.paragraph(child, "quote"))
            elif child.get("type") == "block_text":
                content.append(self.paragraph(child, "quote"))
        cell = Table([[content]], colWidths=[165 * mm])
        cell.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9EC0CF")),
                    ("LINEBEFORE", (0, 0), (0, -1), 3.2, TEAL),
                    ("LEFTPADDING", (0, 0), (-1, -1), 11),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        cell.spaceBefore = 4
        cell.spaceAfter = 8
        return cell

    def list_flowable(self, node: dict[str, Any]) -> ListFlowable:
        ordered = bool(node.get("attrs", {}).get("ordered", False))
        items: list[ListItem] = []
        for list_item in node.get("children", []):
            item_content: list[Any] = []
            for child in list_item.get("children", []):
                child_type = child.get("type")
                if child_type in {"block_text", "paragraph"}:
                    item_content.append(self.paragraph(child))
                elif child_type == "list":
                    item_content.append(self.list_flowable(child))
            items.append(
                ListItem(item_content, leftIndent=9, value=None, spaceAfter=1.5)
            )
        list_options: dict[str, Any] = {
            "bulletType": "1" if ordered else "bullet",
            "leftIndent": 18,
            "bulletFontName": "ReportArial-Bold",
            "bulletFontSize": 8,
            "bulletColor": TEAL,
            "bulletOffsetY": 1,
            "spaceBefore": 1,
            "spaceAfter": 4,
        }
        if ordered:
            list_options["start"] = "1"
        return ListFlowable(items, **list_options)

    def table(self, node: dict[str, Any]) -> Table:
        head_rows: list[list[Any]] = []
        body_rows: list[list[Any]] = []
        for section in node.get("children", []):
            if section.get("type") == "table_head":
                target = head_rows
                raw_rows = [section]
            elif section.get("type") == "table_body":
                target = body_rows
                raw_rows = section.get("children", [])
            else:
                continue
            for raw_row in raw_rows:
                if raw_row.get("type") == "table_head":
                    cells = raw_row.get("children", [])
                else:
                    cells = raw_row.get("children", [])
                row: list[Any] = []
                for cell in cells:
                    style = "table_header" if target is head_rows else "table"
                    row.append(Paragraph(self.inline(cell.get("children", [])), self.styles[style]))
                if row:
                    target.append(row)
        data = head_rows + body_rows
        if not data:
            return Table([[Paragraph("Empty table", self.styles["table"])]] )
        columns = max(len(row) for row in data)
        for row in data:
            row.extend([""] * (columns - len(row)))
        if columns == 2:
            col_widths = [103 * mm, 62 * mm]
        else:
            col_widths = [165 * mm / columns] * columns
        table = Table(data, colWidths=col_widths, repeatRows=len(head_rows) or 1, hAlign="LEFT")
        commands: list[tuple[Any, ...]] = [
            ("BACKGROUND", (0, 0), (-1, len(head_rows) - 1), NAVY),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.35, LIGHT_GRAY),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for row_index in range(len(head_rows), len(data)):
            commands.append(
                (
                    "BACKGROUND",
                    (0, row_index),
                    (-1, row_index),
                    WHITE if (row_index - len(head_rows)) % 2 == 0 else PALE_GRAY,
                )
            )
        table.setStyle(TableStyle(commands))
        table.spaceBefore = 4
        table.spaceAfter = 8
        return table

    def heading(self, node: dict[str, Any]) -> Paragraph:
        level = int(node.get("attrs", {}).get("level", 2))
        title_markup = self.inline(node.get("children", []))
        title_plain = plain_text(node.get("children", []))
        self.heading_index += 1
        anchor = f"heading-{self.heading_index}"
        style_key = "section" if level <= 2 else "subsection"
        paragraph = Paragraph(
            f'<a name="{anchor}"/>{title_markup}', self.styles[style_key]
        )
        paragraph._bookmarkName = anchor  # type: ignore[attr-defined]
        paragraph._tocLevel = 0 if level <= 2 else 1  # type: ignore[attr-defined]
        paragraph._tocText = title_plain  # type: ignore[attr-defined]
        return paragraph

    def render(self, ast: list[dict[str, Any]]) -> list[Any]:
        flowables: list[Any] = []
        skipped_title = False
        for node in ast:
            node_type = node.get("type")
            if node_type in {"blank_line", "thematic_break"}:
                if node_type == "thematic_break":
                    flowables.append(
                        HRFlowable(
                            width="100%",
                            thickness=0.5,
                            color=LIGHT_GRAY,
                            spaceBefore=5,
                            spaceAfter=7,
                        )
                    )
                continue
            if node_type == "heading":
                level = int(node.get("attrs", {}).get("level", 1))
                if level == 1 and not skipped_title:
                    skipped_title = True
                    continue
                flowables.append(self.heading(node))
            elif node_type == "paragraph":
                flowables.append(self.paragraph(node))
            elif node_type == "block_quote":
                flowables.append(self.quote(node))
            elif node_type == "list":
                flowables.append(self.list_flowable(node))
            elif node_type == "table":
                flowables.append(self.table(node))
            elif node_type == "block_code":
                raw = ascii_dashes(node.get("raw", "")).rstrip()
                pre = Preformatted(raw, self.styles["code"], maxLineLength=115)
                box = Table([[pre]], colWidths=[165 * mm])
                box.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), PALE_GRAY),
                            ("BOX", (0, 0), (-1, -1), 0.4, LIGHT_GRAY),
                            ("LEFTPADDING", (0, 0), (-1, -1), 7),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )
                box.spaceBefore = 4
                box.spaceAfter = 7
                flowables.append(box)
        return flowables


class ReportDocTemplate(BaseDocTemplate):
    def __init__(
        self,
        filename: str,
        styles: dict[str, ParagraphStyle],
        language: str = "en",
        header_left: str = "QFBench A6 R11 | ME1-ME10",
        header_right: str | None = None,
        footer_text: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(filename, **kwargs)
        self.styles = styles
        self.language = language
        self.header_left = header_left
        self.header_right = header_right or (
            "Engineering mechanism validation | 中文版"
            if language == "zh"
            else "Engineering mechanism validation"
        )
        self.footer_text = footer_text or (
            "基于 2026-08-11 已审计 synthesis 生成"
            if language == "zh"
            else "Generated from the audited 2026-08-11 synthesis"
        )
        cover_frame = Frame(
            22 * mm,
            18 * mm,
            PAGE_WIDTH - 44 * mm,
            PAGE_HEIGHT - 36 * mm,
            id="cover",
            showBoundary=0,
        )
        body_frame = Frame(
            22 * mm,
            19 * mm,
            PAGE_WIDTH - 44 * mm,
            PAGE_HEIGHT - 36 * mm,
            id="body",
            showBoundary=0,
        )
        self.addPageTemplates(
            [
                PageTemplate(id="Cover", frames=[cover_frame], onPage=self.cover_page),
                PageTemplate(id="Body", frames=[body_frame], onPage=self.body_page),
            ]
        )

    def cover_page(self, canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_HEIGHT - 8 * mm, PAGE_WIDTH, 8 * mm, fill=1, stroke=0)
        canvas.setFillColor(TEAL)
        canvas.rect(0, 0, PAGE_WIDTH, 5 * mm, fill=1, stroke=0)
        canvas.restoreState()

    def body_page(self, canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(LIGHT_GRAY)
        canvas.setLineWidth(0.45)
        canvas.line(22 * mm, PAGE_HEIGHT - 14 * mm, PAGE_WIDTH - 22 * mm, PAGE_HEIGHT - 14 * mm)
        canvas.setFont("ReportArial-Bold", 7.2)
        canvas.setFillColor(MID_GRAY)
        canvas.drawString(22 * mm, PAGE_HEIGHT - 11 * mm, self.header_left)
        canvas.setFont("ReportArial", 7.2)
        canvas.drawRightString(
            PAGE_WIDTH - 22 * mm,
            PAGE_HEIGHT - 11 * mm,
            self.header_right,
        )
        canvas.line(22 * mm, 14 * mm, PAGE_WIDTH - 22 * mm, 14 * mm)
        canvas.setFont("ReportArial", 7.2)
        canvas.drawString(22 * mm, 9.5 * mm, self.footer_text)
        canvas.drawRightString(PAGE_WIDTH - 22 * mm, 9.5 * mm, f"Page {doc.page}")
        canvas.restoreState()

    def afterFlowable(self, flowable: Any) -> None:
        if isinstance(flowable, Paragraph) and hasattr(flowable, "_bookmarkName"):
            key = flowable._bookmarkName
            text = flowable._tocText
            level = flowable._tocLevel
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=False)
            self.notify("TOCEntry", (level, text, self.page, key))


def make_metric_cell(value: str, label: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    return [
        Paragraph(value, styles["metric_value"]),
        Paragraph(label, styles["metric_label"]),
    ]


def cover_story(
    styles: dict[str, ParagraphStyle],
    source_sha: str,
    source_name: str,
    language: str,
    profile: str,
) -> list[Any]:
    if profile == "two-week" and language == "zh":
        kicker = "QEA EXPERIMENT PROGRAM | TWO-WEEK SYNTHESIS"
        cover_title = "QEA 近两周实验综述<br/>From Baseline to A6"
        cover_subtitle = (
            "2026-07-30 至 2026-08-11：从 execution foundation、fixed-worker "
            "Baseline 与 component activation，推进到 calibrated ABSTAIN。"
        )
        outcome = (
            "<b>Outcome：</b>execution foundation PASS，discovery-control mechanism PASS，"
            "calibrated ABSTAIN PASS。Productive ACT 尚未证明：没有 legal ACT、non-empty "
            "full-harness diff、candidate validation、admission 或 candidate panel。"
        )
        source_label = "中文源稿"
        date_line = "报告周期：2026-07-30 至 2026-08-11 | Scope：experimental synthesis"
        metric_rows = [
            [
                ("425", "Baseline official scores"),
                ("A1-A6", "Discovery stages"),
                ("2", "Valid terminal ABSTAINs"),
            ],
            [
                ("0", "Validated candidate gains"),
                ("16", "A6 panel tasks"),
                ("13 days", "Measured period"),
            ],
        ]
        contract = (
            "<b>Program boundary</b><br/>answer-free worker evidence | isolated offline "
            "verifier | exact-ID accounting | measured-vs-proposed claims"
        )
    elif profile == "two-week":
        kicker = "QEA EXPERIMENT PROGRAM | TWO-WEEK SYNTHESIS"
        cover_title = "QEA Two-Week Experiment Review<br/>From Baseline to A6"
        cover_subtitle = (
            "2026-07-30 to 2026-08-11: execution foundation, fixed-worker baseline, "
            "component activation, and calibrated abstention."
        )
        outcome = (
            "<b>Outcome:</b> execution foundation PASS, discovery-control mechanism PASS, "
            "and calibrated ABSTAIN PASS. Productive ACT remains unproven."
        )
        source_label = "Source"
        date_line = "Period: 2026-07-30 to 2026-08-11 | Scope: experimental synthesis"
        metric_rows = [
            [("425", "Baseline official scores"), ("A1-A6", "Discovery stages"), ("2", "Valid terminal ABSTAINs")],
            [("0", "Validated candidate gains"), ("16", "A6 panel tasks"), ("13 days", "Measured period")],
        ]
        contract = (
            "<b>Program boundary</b><br/>answer-free worker evidence | isolated offline "
            "verifier | exact-ID accounting | measured-vs-proposed claims"
        )
    elif language == "zh":
        kicker = "QFBENCH A6 | R11 ENGINEERING SYNTHESIS"
        cover_title = "ME1-ME10<br/>Engineering Mechanism Validation<br/>综合报告"
        cover_subtitle = (
            "从 multi-epoch control-flow failures 到 truthful、checkpoint-bound "
            "calibrated abstention 的完整 repair sequence。"
        )
        outcome = (
            "<b>Outcome：</b>terminal mechanism PASS，calibrated ABSTAIN PASS。"
            "ACT-to-candidate engineering feasibility 仍未证明：没有 legal ACT、non-empty "
            "harness diff、candidate validation、admission 或 candidate panel。"
        )
        source_label = "中文源稿"
        date_line = "报告日期：2026-08-11 | Scope：engineering mechanism validation only"
        metric_rows = [
            [("12", "Mechanism attempts"), ("174", "Wire attempts"), ("170", "HTTP-200 responses")],
            [(">= 5.80M", "Known accepted tokens"), (">= $0.3520", "Known provider cost"), ("2", "Valid terminal ABSTAINs")],
        ]
        contract = (
            "<b>Execution contract</b><br/>deepseek/deepseek-v4-flash-0731 | "
            "DeepSeek required | high reasoning | no fallback | same-ID zero-model preflight"
        )
    else:
        kicker = "QFBENCH A6 | R11 ENGINEERING SYNTHESIS"
        cover_title = "ME1-ME10 Engineering<br/>Mechanism Validation"
        cover_subtitle = (
            "A consolidated record of the repair sequence from multi-epoch control-flow "
            "failures to truthful, checkpoint-bound calibrated abstention."
        )
        outcome = (
            "<b>Outcome:</b> terminal mechanism PASS and calibrated ABSTAIN PASS. "
            "ACT-to-candidate engineering feasibility remains unproven: no legal ACT, "
            "non-empty harness diff, candidate validation, admission, or candidate panel occurred."
        )
        source_label = "Source"
        date_line = "Report date: 2026-08-11 | Scope: engineering mechanism validation only"
        metric_rows = [
            [("12", "Mechanism attempts"), ("174", "Wire attempts"), ("170", "HTTP-200 responses")],
            [(">= 5.80M", "Known accepted tokens"), (">= $0.3520", "Known provider cost"), ("2", "Valid terminal ABSTAINs")],
        ]
        contract = (
            "<b>Execution contract</b><br/>deepseek/deepseek-v4-flash-0731 | "
            "DeepSeek required | high reasoning | no fallback | same-ID zero-model preflight"
        )
    story: list[Any] = [
        Spacer(1, 10 * mm),
        Paragraph(kicker, styles["cover_kicker"]),
        Paragraph(cover_title, styles["cover_title"]),
        Paragraph(cover_subtitle, styles["cover_subtitle"]),
        HRFlowable(width="100%", thickness=1.2, color=TEAL, spaceBefore=4, spaceAfter=10),
    ]
    claim = Table(
        [[
            Paragraph(outcome, styles["quote"])
        ]],
        colWidths=[165 * mm],
    )
    claim.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_TEAL),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#91C5BA")),
                ("LINEBEFORE", (0, 0), (0, -1), 4, TEAL),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.extend([claim, Spacer(1, 8 * mm)])
    metrics = Table(
        [[make_metric_cell(value, label, styles) for value, label in row] for row in metric_rows],
        colWidths=[55 * mm] * 3,
        rowHeights=[25 * mm, 25 * mm],
    )
    metrics.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend(
        [
            metrics,
            Spacer(1, 14 * mm),
            Paragraph(contract, styles["cover_meta"]),
            Spacer(1, 3 * mm),
            Paragraph(
                f"{source_label}: {html.escape(source_name)}<br/>"
                f"Source SHA-256: <font name=\"ReportMono\">{source_sha}</font><br/>"
                + date_line,
                styles["cover_meta"],
            ),
            NextPageTemplate("Body"),
            PageBreak(),
        ]
    )
    return story


def toc_story(
    styles: dict[str, ParagraphStyle], language: str, profile: str
) -> list[Any]:
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "TOCLevel1",
            fontName="ReportArial-Bold",
            fontSize=9.3,
            leading=13,
            leftIndent=0,
            firstLineIndent=0,
            textColor=NAVY,
            spaceBefore=2,
        ),
        ParagraphStyle(
            "TOCLevel2",
            fontName="ReportArial",
            fontSize=8.2,
            leading=11,
            leftIndent=12,
            firstLineIndent=0,
            textColor=MID_GRAY,
            spaceBefore=1,
        ),
    ]
    return [
        Paragraph("目录" if language == "zh" else "Contents", styles["toc_title"]),
        Paragraph(
            (
                (
                    "按 experiment stage 组织的 Purpose、What we did、Measured data 与 Conclusion。"
                    if profile == "two-week"
                    else "已审计 synthesis 的章节与逐实验记录。"
                )
                if language == "zh"
                else "Sections and experiment records in the audited synthesis."
            ),
            styles["body"],
        ),
        Spacer(1, 4 * mm),
        toc,
        PageBreak(),
    ]


def render(
    source: Path,
    output: Path,
    language: str = "auto",
    profile: str = "me",
) -> None:
    if language == "auto":
        language = "zh" if source.stem.endswith("-zh") else "en"
    register_fonts(chinese=language == "zh")
    styles = build_styles()
    raw = source.read_text(encoding="utf-8")
    source_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    markdown = mistune.create_markdown(renderer="ast", plugins=["table"])
    ast = markdown(raw)

    output.parent.mkdir(parents=True, exist_ok=True)
    renderer = MarkdownRenderer(styles, source.parent)
    story = cover_story(styles, source_sha, source.name, language, profile)
    story.extend(toc_story(styles, language, profile))
    story.extend(renderer.render(ast))

    is_two_week = profile == "two-week"
    doc = ReportDocTemplate(
        str(output),
        styles,
        language=language,
        header_left=(
            "QEA Experiment Program | 2026-07-30 to 2026-08-11"
            if is_two_week
            else "QFBench A6 R11 | ME1-ME10"
        ),
        header_right=(
            "From Baseline to A6 | 中文版"
            if is_two_week and language == "zh"
            else "From Baseline to A6"
            if is_two_week
            else None
        ),
        footer_text=(
            "基于 frozen experiment records 生成"
            if is_two_week and language == "zh"
            else "Generated from frozen experiment records"
            if is_two_week
            else None
        ),
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=18 * mm,
        bottomMargin=19 * mm,
        title=(
            "QEA 近两周 A1-A6 实验综合报告"
            if is_two_week and language == "zh"
            else "QEA Two-Week A1-A6 Experiment Synthesis"
            if is_two_week
            else "QFBench A6 R11 ME1-ME10 Engineering Mechanism Validation 中文综合报告"
            if language == "zh"
            else "QFBench A6 R11 ME1-ME10 Engineering Mechanism Validation"
        ),
        author="QEA Engineering Research",
        subject=(
            "Two-week experiment synthesis from execution foundation to A6"
            if is_two_week
            else "Consolidated mechanism-validation synthesis"
        ),
        creator="ReportLab PDF renderer",
    )
    doc.multiBuild(story)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--language", choices=("auto", "en", "zh"), default="auto")
    parser.add_argument("--profile", choices=("me", "two-week"), default="me")
    args = parser.parse_args()
    render(args.source.resolve(), args.output.resolve(), args.language, args.profile)


if __name__ == "__main__":
    main()
