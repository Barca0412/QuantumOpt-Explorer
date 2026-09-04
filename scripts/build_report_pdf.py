#!/usr/bin/env python3
"""Render the judge-facing Markdown report to a polished, deterministic PDF."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


INK = colors.HexColor("#13213C")
BLUE = colors.HexColor("#176B87")
CYAN = colors.HexColor("#64CCC5")
PALE = colors.HexColor("#EAF6F6")
MUTED = colors.HexColor("#52606D")
GRID = colors.HexColor("#C9D5DC")


def inline_markup(text: str) -> str:
    value = html.escape(text.strip())
    value = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2" color="#176B87"><u>\1</u></a>',
        value,
    )
    value = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", value)
    return value


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=31,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=MUTED,
            spaceAfter=10,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            textColor=INK,
            spaceBefore=15,
            spaceAfter=7,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=16,
            textColor=BLUE,
            spaceBefore=11,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "H3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=INK,
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=13.2,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.9,
            leading=12.5,
            textColor=INK,
            leftIndent=3,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=7.8,
            leading=10,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceBefore=3,
            spaceAfter=8,
        ),
        "table": ParagraphStyle(
            "TableText",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9,
            textColor=INK,
        ),
        "table_head": ParagraphStyle(
            "TableHead",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9,
            textColor=colors.white,
        ),
        "code": ParagraphStyle(
            "Code",
            fontName="Courier",
            fontSize=7.4,
            leading=10,
            textColor=INK,
            backColor=colors.HexColor("#F3F6F8"),
            borderColor=GRID,
            borderWidth=0.5,
            borderPadding=7,
            spaceBefore=4,
            spaceAfter=8,
        ),
    }


def parse_table(lines: list[str], style: dict[str, ParagraphStyle]) -> Table:
    rows: list[list[Paragraph]] = []
    for index, line in enumerate(lines):
        if index == 1 and re.fullmatch(r"[| :\-]+", line.strip()):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        cell_style = style["table_head"] if not rows else style["table"]
        rows.append([Paragraph(inline_markup(cell), cell_style) for cell in cells])
    count = max(len(row) for row in rows)
    page_width = A4[0] - 38 * mm
    widths = [page_width / count] * count
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("GRID", (0, 0), (-1, -1), 0.35, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
            ]
        )
    )
    return table


def add_image(story: list, source: Path, caption: str, style: dict[str, ParagraphStyle]) -> None:
    if not source.is_file():
        story.append(Paragraph(f"[Missing figure: {inline_markup(str(source))}]", style["body"]))
        return
    image = Image(str(source))
    max_width = A4[0] - 42 * mm
    max_height = 91 * mm
    scale = min(max_width / image.imageWidth, max_height / image.imageHeight, 1.0)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    image.hAlign = "CENTER"
    story.append(KeepTogether([image, Paragraph(inline_markup(caption), style["caption"])]))


def markdown_story(markdown_path: Path) -> list:
    style = styles()
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    story: list = []
    paragraph: list[str] = []
    bullets: list[str] = []
    table_lines: list[str] = []
    code_lines: list[str] = []
    in_code = False
    title_seen = False

    def flush_paragraph() -> None:
        if paragraph:
            story.append(Paragraph(inline_markup(" ".join(paragraph)), style["body"]))
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            story.append(
                ListFlowable(
                    [ListItem(Paragraph(inline_markup(item), style["bullet"])) for item in bullets],
                    bulletType="bullet",
                    start="circle",
                    leftIndent=15,
                    bulletFontName="Helvetica",
                    bulletFontSize=7,
                    spaceAfter=5,
                )
            )
            bullets.clear()

    def flush_table() -> None:
        if table_lines:
            story.append(parse_table(table_lines, style))
            story.append(Spacer(1, 7))
            table_lines.clear()

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("```"):
            flush_paragraph()
            flush_bullets()
            flush_table()
            if in_code:
                story.append(Preformatted("\n".join(code_lines), style["code"]))
                code_lines.clear()
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        image_match = re.fullmatch(r"!\[([^]]*)\]\(([^)]+)\)", line.strip())
        if image_match:
            flush_paragraph()
            flush_bullets()
            flush_table()
            add_image(
                story,
                (markdown_path.parent / image_match.group(2)).resolve(),
                image_match.group(1),
                style,
            )
            continue
        if line.startswith("|") and line.endswith("|"):
            flush_paragraph()
            flush_bullets()
            table_lines.append(line)
            continue
        flush_table()
        if not line.strip():
            flush_paragraph()
            flush_bullets()
            continue
        if line == "---":
            flush_paragraph()
            flush_bullets()
            story.append(HRFlowable(width="100%", thickness=0.7, color=CYAN, spaceBefore=4, spaceAfter=7))
            continue
        if line.startswith("# "):
            flush_paragraph()
            flush_bullets()
            if title_seen:
                story.append(PageBreak())
                story.append(Paragraph(inline_markup(line[2:]), style["h1"]))
            else:
                story.append(Spacer(1, 10 * mm))
                story.append(Paragraph(inline_markup(line[2:]), style["title"]))
                story.append(HRFlowable(width="100%", thickness=2.2, color=CYAN, spaceAfter=11))
                title_seen = True
            continue
        if line.startswith("## "):
            flush_paragraph()
            flush_bullets()
            story.append(Paragraph(inline_markup(line[3:]), style["h1"]))
            continue
        if line.startswith("### "):
            flush_paragraph()
            flush_bullets()
            story.append(Paragraph(inline_markup(line[4:]), style["h2"]))
            continue
        if line.startswith("#### "):
            flush_paragraph()
            flush_bullets()
            story.append(Paragraph(inline_markup(line[5:]), style["h3"]))
            continue
        if re.match(r"^[-*] ", line):
            flush_paragraph()
            bullets.append(re.sub(r"^[-*] ", "", line))
            continue
        numbered = re.match(r"^\d+[.)] (.+)", line)
        if numbered:
            flush_paragraph()
            bullets.append(numbered.group(1))
            continue
        if line.startswith("> "):
            flush_paragraph()
            flush_bullets()
            story.append(
                Paragraph(
                    inline_markup(line[2:]),
                    ParagraphStyle(
                        "Quote",
                        parent=style["body"],
                        leftIndent=10,
                        borderColor=CYAN,
                        borderWidth=0,
                        borderPadding=7,
                        backColor=PALE,
                    ),
                )
            )
            continue
        paragraph.append(line.strip())

    flush_paragraph()
    flush_bullets()
    flush_table()
    return story


def draw_page(canvas, document) -> None:
    canvas.saveState()
    width, height = A4
    if document.page > 1:
        canvas.setStrokeColor(CYAN)
        canvas.setLineWidth(0.7)
        canvas.line(19 * mm, height - 15 * mm, width - 19 * mm, height - 15 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(19 * mm, height - 11.5 * mm, "QuantumOpt-Explorer | GOAI AI for Research")
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(width / 2, 11 * mm, f"{document.page}")
    canvas.restoreState()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="SEMIFINAL_REPORT.md")
    parser.add_argument("--output", default="output/pdf/QuantumOpt-Explorer_Semifinal_Report.pdf")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source = (root / args.input).resolve()
    output = (root / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=19 * mm,
        leftMargin=19 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title="QuantumOpt-Explorer Semifinal Report",
        author="Haoming Chen",
        subject="GOAI AI for Research - Open Exploration",
    )
    document.build(markdown_story(source), onFirstPage=draw_page, onLaterPages=draw_page)
    print(output)


if __name__ == "__main__":
    main()
