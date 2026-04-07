from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from io import BytesIO

from backend.models import ParsedData


# ─────────────────────────────────────────────
#  Markdown
# ─────────────────────────────────────────────

def generate_markdown(data: ParsedData, trip_name: str) -> str:
    expenses = [e for e in data.expenses if not e.is_reimbursement]
    dates = [e.date for e in expenses if e.date]
    date_from = min(dates).strftime("%d %b %Y") if dates else "?"
    date_to = max(dates).strftime("%d %b %Y") if dates else "?"
    members_str = ", ".join(m.member_name for m in data.members)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines: list[str] = []
    lines.append(f"# {trip_name}")
    lines.append(f"**Generated:** {now}  ")
    lines.append(f"**Period:** {date_from} – {date_to}  ")
    lines.append(f"**Participants:** {members_str}  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary by category
    lines.append("## Summary by Category")
    lines.append("")
    totals = _category_totals(expenses)
    grand_total = sum(totals.values())
    lines.append("| Category | Amount | % | # Items |")
    lines.append("|----------|--------|---|---------|")
    for cat, total in sorted(totals.items(), key=lambda x: -x[1]):
        pct = (total / grand_total * 100) if grand_total else 0
        count = sum(1 for e in expenses if e.category == cat)
        lines.append(f"| {cat} | {_fmt(total)} | {pct:.1f}% | {count} |")
    lines.append(f"| **TOTAL** | **{_fmt(grand_total)}** | **100%** | **{len(expenses)}** |")
    lines.append("")

    # Uncategorized warning
    uncategorized = [e for e in expenses if e.category == "UNCATEGORIZED"]
    if uncategorized:
        lines.append(f"> ⚠️ **{len(uncategorized)} expenses still uncategorized** — please review.")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Balance sheet
    lines.append("## Balance Sheet")
    lines.append("")
    paid_by: dict[str, float] = defaultdict(float)
    for e in expenses:
        paid_by[e.payer] += e.amount
    share_per = grand_total / len(data.members) if data.members else 0
    lines.append("| Participant | Paid | Fair Share | Balance |")
    lines.append("|-------------|------|------------|---------|")
    for b in data.balances:
        paid = paid_by.get(b.member, 0.0)
        balance_val = paid - share_per
        sign = "+" if balance_val >= 0 else ""
        lines.append(f"| {b.member} | {_fmt(paid)} | {_fmt(share_per)} | {sign}{_fmt(balance_val)} |")
    lines.append("")

    lines.append("---")
    lines.append("")

    # Expenses by category
    lines.append("## Expenses by Category")
    lines.append("")
    by_cat: dict[str, list] = defaultdict(list)
    for e in expenses:
        by_cat[e.category].append(e)

    for cat in sorted(by_cat.keys()):
        cat_expenses = sorted(by_cat[cat], key=lambda e: e.date)
        subtotal = sum(e.amount for e in cat_expenses)
        lines.append(f"### {cat}")
        lines.append("")
        lines.append("| Date | Description | Paid by | Amount |")
        lines.append("|------|-------------|---------|--------|")
        for e in cat_expenses:
            d = e.date.strftime("%d %b") if e.date else "?"
            lines.append(f"| {d} | {e.description} | {e.payer} | {_fmt(e.amount)} |")
        lines.append(f"| | **Subtotal** | | **{_fmt(subtotal)}** |")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Chronological full list
    lines.append("## All Expenses (Chronological)")
    lines.append("")
    lines.append("| Date | Description | Category | Paid by | Amount |")
    lines.append("|------|-------------|----------|---------|--------|")
    for e in sorted(expenses, key=lambda e: e.date or datetime.min):
        d = e.date.strftime("%d %b %Y") if e.date else "?"
        lines.append(f"| {d} | {e.description} | {e.category} | {e.payer} | {_fmt(e.amount)} |")
    lines.append("")

    return "\n".join(lines)


def _fmt(amount: float) -> str:
    return f"{amount:,.2f} €"


def _category_totals(expenses) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for e in expenses:
        totals[e.category] += e.amount
    return dict(totals)


# ─────────────────────────────────────────────
#  PDF  (ReportLab Platypus)
# ─────────────────────────────────────────────

def generate_pdf(data: ParsedData, trip_name: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=20, spaceAfter=6)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, spaceBefore=12, spaceAfter=6)
    h3_style = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=4)
    body_style = styles["Normal"]

    expenses = [e for e in data.expenses if not e.is_reimbursement]
    dates = [e.date for e in expenses if e.date]
    date_from = min(dates).strftime("%d %b %Y") if dates else "?"
    date_to = max(dates).strftime("%d %b %Y") if dates else "?"
    members_str = ", ".join(m.member_name for m in data.members)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    totals = _category_totals(expenses)
    grand_total = sum(totals.values())

    story = []

    # ── Header ──
    story.append(Paragraph(trip_name, title_style))
    story.append(Paragraph(f"<b>Period:</b> {date_from} – {date_to}", body_style))
    story.append(Paragraph(f"<b>Participants:</b> {members_str}", body_style))
    story.append(Paragraph(f"<b>Generated:</b> {now}", body_style))
    story.append(Spacer(1, 0.5 * cm))

    # ── Summary table ──
    story.append(Paragraph("Summary by Category", h2_style))

    header = ["Category", "Amount (€)", "%", "# Items"]
    rows = [header]
    for cat, total in sorted(totals.items(), key=lambda x: -x[1]):
        pct = (total / grand_total * 100) if grand_total else 0
        count = sum(1 for e in expenses if e.category == cat)
        rows.append([cat, f"{total:,.2f}", f"{pct:.1f}%", str(count)])
    rows.append(["TOTAL", f"{grand_total:,.2f}", "100%", str(len(expenses))])

    col_widths = [9 * cm, 3.5 * cm, 2 * cm, 2 * cm]
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(_summary_table_style(len(rows)))
    story.append(tbl)
    story.append(Spacer(1, 0.5 * cm))

    # ── Balance sheet ──
    story.append(Paragraph("Balance Sheet", h2_style))

    paid_by: dict[str, float] = defaultdict(float)
    for e in expenses:
        paid_by[e.payer] += e.amount
    share_per = grand_total / len(data.members) if data.members else 0

    bal_header = ["Participant", "Paid (€)", "Fair Share (€)", "Balance (€)"]
    bal_rows = [bal_header]
    for b in data.balances:
        paid = paid_by.get(b.member, 0.0)
        bal = paid - share_per
        sign = "+" if bal >= 0 else ""
        bal_rows.append([b.member, f"{paid:,.2f}", f"{share_per:,.2f}", f"{sign}{bal:,.2f}"])

    bal_tbl = Table(bal_rows, colWidths=[5 * cm, 3.5 * cm, 4 * cm, 4 * cm])
    bal_tbl.setStyle(_balance_table_style(bal_rows))
    story.append(bal_tbl)

    story.append(PageBreak())

    # ── Per-category sections ──
    story.append(Paragraph("Expenses by Category", h2_style))

    by_cat: dict[str, list] = defaultdict(list)
    for e in expenses:
        by_cat[e.category].append(e)

    for cat in sorted(by_cat.keys()):
        cat_expenses = sorted(by_cat[cat], key=lambda e: e.date)
        subtotal = sum(e.amount for e in cat_expenses)
        story.append(Paragraph(cat, h3_style))

        cat_header = ["Date", "Description", "Paid by", "Amount (€)"]
        cat_rows = [cat_header]
        for e in cat_expenses:
            d = e.date.strftime("%d %b") if e.date else "?"
            cat_rows.append([d, _truncate(e.description, 40), e.payer, f"{e.amount:,.2f}"])
        cat_rows.append(["", "Subtotal", "", f"{subtotal:,.2f}"])

        cat_tbl = Table(cat_rows, colWidths=[2.5 * cm, 8.5 * cm, 3 * cm, 2.5 * cm])
        cat_tbl.setStyle(_category_table_style(len(cat_rows)))
        story.append(cat_tbl)
        story.append(Spacer(1, 0.3 * cm))

    doc.build(story, onFirstPage=_footer_canvas, onLaterPages=_footer_canvas)
    return buffer.getvalue()


def _footer_canvas(canvas, doc):
    from reportlab.lib import colors as _colors
    from reportlab.lib.units import cm as _cm
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(_colors.grey)
    canvas.drawRightString(
        doc.pagesize[0] - 2 * _cm,
        1.2 * _cm,
        f"Page {doc.page}",
    )
    canvas.restoreState()


def _summary_table_style(n_rows: int):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        # Last row (total) bold
        ("FONTNAME", (0, n_rows - 1), (-1, n_rows - 1), "Helvetica-Bold"),
        ("BACKGROUND", (0, n_rows - 1), (-1, n_rows - 1), colors.HexColor("#eaf0fb")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    # Alternating rows
    for i in range(1, n_rows - 1):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f7f9fc")))
    return TableStyle(style)


def _balance_table_style(rows: list):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    # Color balance column green/red
    for i, row in enumerate(rows[1:], start=1):
        bal_str = row[-1]
        if bal_str.startswith("+") or (not bal_str.startswith("-") and float(bal_str.replace(",", "") or 0) > 0):
            style.append(("TEXTCOLOR", (3, i), (3, i), colors.HexColor("#27ae60")))
        elif bal_str.startswith("-"):
            style.append(("TEXTCOLOR", (3, i), (3, i), colors.HexColor("#e74c3c")))
    return TableStyle(style)


def _category_table_style(n_rows: int):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("FONTNAME", (0, n_rows - 1), (-1, n_rows - 1), "Helvetica-Bold"),
        ("BACKGROUND", (0, n_rows - 1), (-1, n_rows - 1), colors.HexColor("#eaf0fb")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(1, n_rows - 1):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f7f9fc")))
    return TableStyle(style)


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[: max_len - 1] + "…"
