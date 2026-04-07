from __future__ import annotations
from collections import defaultdict, Counter
from datetime import datetime
from io import BytesIO

from backend.models import ParsedData


# ─────────────────────────────────────────────
#  Unicode font registration (for PDF Greek support)
# ─────────────────────────────────────────────

_FONT_REGISTERED = False
_BASE_FONT = "Helvetica"
_BASE_FONT_BOLD = "Helvetica-Bold"


def _register_fonts() -> None:
    global _FONT_REGISTERED, _BASE_FONT, _BASE_FONT_BOLD
    if _FONT_REGISTERED:
        return
    _FONT_REGISTERED = True

    import os
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        return

    candidates = [
        # Windows
        ("C:/Windows/Fonts/arial.ttf",    "C:/Windows/Fonts/arialbd.ttf",  "TR-Regular", "TR-Bold"),
        # macOS
        ("/Library/Fonts/Arial.ttf",       "/Library/Fonts/Arial Bold.ttf", "TR-Regular", "TR-Bold"),
        # Linux – Noto Sans
        ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
         "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",   "TR-Regular", "TR-Bold"),
        # Linux – DejaVu
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "TR-Regular", "TR-Bold"),
    ]

    for reg_path, bold_path, name, bold_name in candidates:
        if os.path.exists(reg_path):
            try:
                pdfmetrics.registerFont(TTFont(name, reg_path))
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                else:
                    bold_name = name
                _BASE_FONT = name
                _BASE_FONT_BOLD = bold_name
                return
            except Exception:
                continue


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _fmt(amount: float) -> str:
    return f"{amount:,.2f} €"


def _category_totals(expenses) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for e in expenses:
        totals[e.category] += e.amount
    return dict(totals)


def _filter_expenses(
    data: ParsedData,
    report_mode: str,
    personal_member: str | None,
    exclude_personal_expenses: bool,
):
    """Return filtered expense list and personal-mode stats dict."""
    expenses = [e for e in data.expenses if not e.is_reimbursement]

    if report_mode == "personal" and personal_member:
        all_expense_ids = {e.entry_id for e in expenses}
        member_entry_ids = {
            a.entry_id for a in data.allocations
            if a.participant == personal_member and a.entry_id in all_expense_ids
        }
        if exclude_personal_expenses:
            alloc_count = Counter(
                a.entry_id for a in data.allocations if a.entry_id in all_expense_ids
            )
            member_entry_ids = {eid for eid in member_entry_ids if alloc_count[eid] > 1}
        expenses = [e for e in expenses if e.entry_id in member_entry_ids]

    return expenses


def _personal_stats(data: ParsedData, personal_member: str) -> dict:
    """Compute global comparison stats for a member."""
    all_expenses = [e for e in data.expenses if not e.is_reimbursement]
    all_ids = {e.entry_id for e in all_expenses}
    global_total = sum(e.amount for e in all_expenses)
    n_members = max(len(data.members), 1)
    global_per_person = global_total / n_members
    personal_paid = sum(e.amount for e in all_expenses if e.payer == personal_member)
    personal_share = sum(
        a.share for a in data.allocations
        if a.participant == personal_member and a.entry_id in all_ids
    )
    return {
        "global_total": global_total,
        "global_per_person": global_per_person,
        "n_members": n_members,
        "personal_paid": personal_paid,
        "personal_share": personal_share,
        "diff_from_avg": personal_share - global_per_person,
    }


# ─────────────────────────────────────────────
#  Markdown
# ─────────────────────────────────────────────

def generate_markdown(
    data: ParsedData,
    trip_name: str,
    report_mode: str = "global",
    personal_member: str | None = None,
    exclude_personal_expenses: bool = False,
) -> str:
    expenses = _filter_expenses(data, report_mode, personal_member, exclude_personal_expenses)
    dates = [e.date for e in expenses if e.date]
    date_from = min(dates).strftime("%d %b %Y") if dates else "?"
    date_to   = max(dates).strftime("%d %b %Y") if dates else "?"
    members_str = ", ".join(m.member_name for m in data.members)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines: list[str] = []
    lines.append(f"# {trip_name}")
    lines.append(f"**Generated:** {now}  ")
    lines.append(f"**Period:** {date_from} – {date_to}  ")
    if report_mode == "personal" and personal_member:
        lines.append(f"**Report for:** {personal_member}  ")
        if exclude_personal_expenses:
            lines.append(f"*Purely personal expenses excluded*  ")
    else:
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

    # Personal comparison block
    if report_mode == "personal" and personal_member:
        stats = _personal_stats(data, personal_member)
        diff = stats["diff_from_avg"]
        sign = "+" if diff >= 0 else ""
        lines.append("## Personal vs Global Comparison")
        lines.append("")
        lines.append("| Metric | Amount |")
        lines.append("|--------|--------|")
        lines.append(f"| Global trip total | {_fmt(stats['global_total'])} |")
        lines.append(f"| Fair share per person ({stats['n_members']} members) | {_fmt(stats['global_per_person'])} |")
        lines.append(f"| {personal_member} — total paid | {_fmt(stats['personal_paid'])} |")
        lines.append(f"| {personal_member} — allocated share | {_fmt(stats['personal_share'])} |")
        lines.append(f"| Difference from fair share | {sign}{_fmt(diff)} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Uncategorized warning
    uncategorized = [e for e in expenses if e.category == "UNCATEGORIZED"]
    if uncategorized:
        lines.append(f"> ⚠️ **{len(uncategorized)} expenses still uncategorized** — please review.")
        lines.append("")

    if report_mode == "global":
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


# ─────────────────────────────────────────────
#  PDF  (ReportLab Platypus)
# ─────────────────────────────────────────────

def generate_pdf(
    data: ParsedData,
    trip_name: str,
    report_mode: str = "global",
    personal_member: str | None = None,
    exclude_personal_expenses: bool = False,
) -> bytes:
    _register_fonts()

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
    title_style = ParagraphStyle(
        "TRTitle", parent=styles["Title"],
        fontName=_BASE_FONT_BOLD, fontSize=20, spaceAfter=6,
    )
    h2_style = ParagraphStyle(
        "TRH2", parent=styles["Heading2"],
        fontName=_BASE_FONT_BOLD, fontSize=14, spaceBefore=12, spaceAfter=6,
    )
    h3_style = ParagraphStyle(
        "TRH3", parent=styles["Heading3"],
        fontName=_BASE_FONT_BOLD, fontSize=11, spaceBefore=8, spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "TRBody", parent=styles["Normal"],
        fontName=_BASE_FONT, fontSize=10,
    )

    expenses = _filter_expenses(data, report_mode, personal_member, exclude_personal_expenses)
    dates = [e.date for e in expenses if e.date]
    date_from = min(dates).strftime("%d %b %Y") if dates else "?"
    date_to   = max(dates).strftime("%d %b %Y") if dates else "?"
    members_str = ", ".join(m.member_name for m in data.members)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    totals = _category_totals(expenses)
    grand_total = sum(totals.values())

    story = []

    # ── Header ──
    story.append(Paragraph(trip_name, title_style))
    if report_mode == "personal" and personal_member:
        story.append(Paragraph(f"<b>Report for:</b> {personal_member}", body_style))
        if exclude_personal_expenses:
            story.append(Paragraph("(Purely personal expenses excluded)", body_style))
    else:
        story.append(Paragraph(f"<b>Participants:</b> {members_str}", body_style))
    story.append(Paragraph(f"<b>Period:</b> {date_from} – {date_to}", body_style))
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

    # ── Personal comparison ──
    if report_mode == "personal" and personal_member:
        story.append(Paragraph("Personal vs Global Comparison", h2_style))
        stats = _personal_stats(data, personal_member)
        diff = stats["diff_from_avg"]
        sign = "+" if diff >= 0 else ""
        comp_rows = [
            ["Metric", "Amount (€)"],
            ["Global trip total", f"{stats['global_total']:,.2f}"],
            [f"Fair share per person ({stats['n_members']} members)", f"{stats['global_per_person']:,.2f}"],
            [f"{personal_member} — total paid", f"{stats['personal_paid']:,.2f}"],
            [f"{personal_member} — allocated share", f"{stats['personal_share']:,.2f}"],
            ["Difference from fair share", f"{sign}{abs(diff):,.2f}"],
        ]
        comp_tbl = Table(comp_rows, colWidths=[10 * cm, 3.5 * cm])
        comp_tbl.setStyle(_comparison_table_style(diff))
        story.append(comp_tbl)
        story.append(Spacer(1, 0.5 * cm))

    # ── Balance sheet (global only) ──
    if report_mode == "global":
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
    canvas.setFont(_BASE_FONT, 8)
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
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), _BASE_FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), _BASE_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("FONTNAME", (0, n_rows - 1), (-1, n_rows - 1), _BASE_FONT_BOLD),
        ("BACKGROUND", (0, n_rows - 1), (-1, n_rows - 1), colors.HexColor("#e8e8e8")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, n_rows - 1):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f5f5")))
    return TableStyle(style)


def _balance_table_style(rows: list):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), _BASE_FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), _BASE_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i, row in enumerate(rows[1:], start=1):
        bal_str = row[-1]
        if bal_str.startswith("+") or (not bal_str.startswith("-") and float(bal_str.replace(",", "") or 0) > 0):
            style.append(("TEXTCOLOR", (3, i), (3, i), colors.HexColor("#1a7a3c")))
        elif bal_str.startswith("-"):
            style.append(("TEXTCOLOR", (3, i), (3, i), colors.HexColor("#c0392b")))
    return TableStyle(style)


def _comparison_table_style(diff: float):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    diff_color = colors.HexColor("#1a7a3c") if diff >= 0 else colors.HexColor("#c0392b")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), _BASE_FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), _BASE_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        # Last row is diff — colour it
        ("TEXTCOLOR", (1, -1), (1, -1), diff_color),
        ("FONTNAME", (0, -1), (-1, -1), _BASE_FONT_BOLD),
    ]
    for i in range(1, 6):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f5f5")))
    return TableStyle(style)


def _category_table_style(n_rows: int):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), _BASE_FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), _BASE_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("FONTNAME", (0, n_rows - 1), (-1, n_rows - 1), _BASE_FONT_BOLD),
        ("BACKGROUND", (0, n_rows - 1), (-1, n_rows - 1), colors.HexColor("#e8e8e8")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(1, n_rows - 1):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f5f5")))
    return TableStyle(style)


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[: max_len - 1] + "…"
