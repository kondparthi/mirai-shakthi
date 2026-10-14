"""PDF rendering for artefacts (ReportLab – pure Python, works on Windows and Linux).

Note: ReportLab cannot shape Telugu script correctly, so PDFs are produced in English for now.
"""
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from .cashflow import inr

GREEN = colors.HexColor("#1f4d3a")
GREEN_LIGHT = colors.HexColor("#e3eeea")
AMBER = colors.HexColor("#b26a00")
AMBER_BG = colors.HexColor("#fff4e0")
RED = colors.HexColor("#b3261e")
RED_BG = colors.HexColor("#fdecea")
OK = colors.HexColor("#1d7a46")
OK_BG = colors.HexColor("#e5f4ea")
INK = colors.HexColor("#1b2420")
INK2 = colors.HexColor("#4c5a53")
LINE = colors.HexColor("#d8e2dc")
SALES_C = colors.HexColor("#3f6aa8")
EXP_C = colors.HexColor("#c66f2b")

W, H = A4
MARGIN = 16 * mm
CONTENT_W = W - 2 * MARGIN

S = {
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8.2, leading=11, textColor=INK2),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=GREEN, spaceBefore=10, spaceAfter=4),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.8, leading=11.5, textColor=INK, alignment=TA_LEFT),
    "cellb": ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=INK),
    "kpi_label": ParagraphStyle("kl", fontName="Helvetica", fontSize=8, leading=10, textColor=INK2),
    "kpi_value": ParagraphStyle("kv", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=INK),
}


class Checkbox(Flowable):
    """A drawn checkbox (vector), so it shows in every PDF viewer without special fonts."""

    def __init__(self, done: bool = False, size: float = 3.4 * mm):
        super().__init__()
        self.done, self.size = done, size
        self.width = self.height = size

    def draw(self):
        c, s = self.canv, self.size
        c.setStrokeColor(OK if self.done else INK2)
        c.setLineWidth(0.8)
        c.setFillColor(OK_BG if self.done else colors.white)
        c.rect(0, 0, s, s, stroke=1, fill=1)
        if self.done:
            c.setStrokeColor(OK)
            c.setLineWidth(1.3)
            c.line(s * 0.2, s * 0.5, s * 0.42, s * 0.25)
            c.line(s * 0.42, s * 0.25, s * 0.82, s * 0.8)


def clean(text: str) -> str:
    # Standard PDF fonts have no rupee glyph – write "Rs." instead.
    return (text or "").replace("₹ ", "Rs. ").replace("₹", "Rs. ")


def p(text: str | None, style: str = "body") -> Paragraph:
    return Paragraph(escape(clean(text or "")), S[style])


def pm(markup: str, style: str = "body") -> Paragraph:
    """Paragraph from trusted markup (callers escape user text)."""
    return Paragraph(clean(markup), S[style])


def check_list(items: list[str]) -> Table:
    t = Table([[Checkbox(), p(x)] for x in items], colWidths=[7 * mm, CONTENT_W - 7 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def rs(x: float) -> str:
    return f"Rs. {inr(x)}"


def _table(rows, widths, header=True, zebra=False):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), GREEN_LIGHT), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                  ("FONTSIZE", (0, 0), (-1, 0), 8.5), ("TEXTCOLOR", (0, 0), (-1, 0), GREEN)]
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f6f8f7")))
    t.setStyle(TableStyle(style))
    return t


def _callout(text: str, level: str):
    bg, fg = {"good": (OK_BG, OK), "warn": (AMBER_BG, AMBER), "alert": (RED_BG, RED)}.get(level, (GREEN_LIGHT, GREEN))
    label = {"good": "GOOD", "warn": "WATCH", "alert": "ACT NOW"}.get(level, "NOTE")
    t = Table([[pm(f'<font color="{fg.hexval().replace("0x", "#")}"><b>{label}</b></font>', "small"), p(text, "cell")]],
              colWidths=[20 * mm, CONTENT_W - 20 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
    return t


def _build(title: str, subtitle: str, story: list) -> bytes:
    buf = BytesIO()
    generated = datetime.now().strftime("%d %b %Y")

    def page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(GREEN)
        canvas.rect(0, H - 26 * mm, W, 26 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(MARGIN, H - 9 * mm, "MIRAI SHAKTHI  ·  MSME AI GUIDANCE")
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(MARGIN, H - 17 * mm, clean(title)[:70])
        canvas.setFont("Helvetica", 9)
        canvas.drawString(MARGIN, H - 22.5 * mm, clean(subtitle)[:110])
        canvas.drawRightString(W - MARGIN, H - 9 * mm, f"Generated {generated}")
        canvas.setFillColor(INK2)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(MARGIN, 10 * mm, "Guidance only, based on the details you entered and MIRAI's verified content. "
                                            "Check with the official source or a professional before filing.")
        canvas.drawRightString(W - MARGIN, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=32 * mm, bottomMargin=18 * mm,
                            title=title, author="MIRAI Shakthi")
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return buf.getvalue()


def _profile_block(summary: list[str]) -> list:
    if not summary:
        return []
    return [pm("<b>Your business:</b> " + escape(" · ".join(summary)), "small"), Spacer(1, 6)]


# ---------------------------------------------------------------- roadmap
def roadmap(title: str, data: dict, business: str) -> bytes:
    steps = data["steps"]
    story = _profile_block(data.get("profile_summary", []))
    done = sum(1 for s in steps if s.get("done"))
    story.append(p(f"{len(steps)} step(s) to complete, {done} already marked done. Work through them in order; "
                   "each step lists the documents, time and cost involved."))
    if data.get("have"):
        story.append(Spacer(1, 4))
        story.append(pm("<b>Already in place:</b> " + escape(", ".join(data["have"])), "small"))
    story.append(Paragraph("Your step-by-step roadmap", S["h2"]))
    rows = [["", "#", "Step", "Documents", "Time / cost"]]
    for s in steps:
        step = f"<b>{escape(s['title'])}</b>"
        if s.get("why"):
            step += f"<br/><font size='8' color='#4c5a53'>{escape(s['why'])}</font>"
        if s.get("link"):
            step += f"<br/><font size='8' color='#2a6249'>{escape(s['link'])}</font>"
        tc = "<br/>".join(escape(x) for x in [s.get("time") or "", s.get("cost") or ""] if x) or "—"
        rows.append([Checkbox(bool(s.get("done"))), p(str(s["n"]), "cellb"), pm(step, "cell"),
                     p(s.get("documents") or "—", "cell"), pm(tc, "cell")])
    story.append(_table(rows, [8 * mm, 7 * mm, 78 * mm, 50 * mm, CONTENT_W - 143 * mm]))
    if data.get("sources"):
        story.append(Paragraph("Sources", S["h2"]))
        for src in data["sources"]:
            story.append(p(f"[{src['n']}] {src['title']}" + (f" – {src['url']}" if src.get("url") else ""), "small"))
    return _build(title, business, story)


# ---------------------------------------------------------------- document checklist
def checklist(title: str, data: dict, business: str) -> bytes:
    story = _profile_block(data.get("profile_summary", []))
    story.append(p("Collect these documents before you start. Keep a photocopy and a clear phone photo of each; "
                   "carry originals for verification."))
    story.append(Paragraph("Documents to keep ready", S["h2"]))
    rows = [["", "Document", "Needed for"]]
    for d in data["documents"]:
        rows.append([Checkbox(), p(d["name"], "cellb"), p(", ".join(d["for"]), "cell")])
    story.append(_table(rows, [8 * mm, 70 * mm, CONTENT_W - 78 * mm], zebra=True))
    story.append(Spacer(1, 8))
    story.append(p("Tip: names, addresses and dates of birth should match exactly across Aadhaar, PAN and bank records. "
                   "Fix any mismatch first – it is the most common reason applications are delayed.", "small"))
    return _build(title, business, story)


# ---------------------------------------------------------------- cash-flow summary
def _kpis(items: list[tuple[str, str]]):
    cells = [[pm(escape(label), "kpi_label") for label, _ in items], [pm(escape(val), "kpi_value") for _, val in items]]
    t = Table(cells, colWidths=[CONTENT_W / len(items)] * len(items))
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f7f4")),
                           ("LINEABOVE", (0, 0), (-1, 0), 2, GREEN), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, 0), 6), ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                           ("LINEAFTER", (0, 0), (-2, -1), 4, colors.white)]))
    return t


def _chart(months: list[dict]):
    d = Drawing(CONTENT_W, 62 * mm)
    c = VerticalBarChart()
    c.x, c.y, c.width, c.height = 14 * mm, 10 * mm, CONTENT_W - 50 * mm, 46 * mm
    c.data = [[m["sales"] for m in months], [m["expenses"] for m in months]]
    c.categoryAxis.categoryNames = [m["month"] for m in months]
    c.categoryAxis.labels.fontSize = 7
    c.categoryAxis.labels.fontName = "Helvetica"
    c.valueAxis.labels.fontSize = 7
    c.valueAxis.labels.fontName = "Helvetica"
    c.valueAxis.labelTextFormat = lambda v: inr(v)
    c.valueAxis.valueMin = 0
    c.valueAxis.gridStrokeColor = LINE
    c.valueAxis.visibleGrid = True
    c.bars[0].fillColor = SALES_C
    c.bars[1].fillColor = EXP_C
    c.bars.strokeColor = None
    c.groupSpacing = 6
    d.add(c)
    lg = Legend()
    lg.x, lg.y = CONTENT_W - 30 * mm, 50 * mm
    lg.fontName, lg.fontSize = "Helvetica", 8
    lg.colorNamePairs = [(SALES_C, "Sales"), (EXP_C, "Expenses")]
    lg.boxAnchor = "nw"
    d.add(lg)
    return d


def cashflow(title: str, data: dict, business: str) -> bytes:
    o = data
    r = o["ratios"]
    story = []
    story.append(_kpis([
        ("Total sales", rs(o["totals"]["sales"])),
        ("Total expenses", rs(o["totals"]["expenses"])),
        ("Profit", rs(o["totals"]["profit"])),
        ("Profit margin", "—" if r["margin_pct"] is None else f"{r['margin_pct']}%"),
    ]))
    story.append(Spacer(1, 6))
    story.append(p(f"Covers {len(o['months'])} month(s) up to {o['months'][-1]['month']}. "
                   f"Average month: sales {rs(o['averages']['sales'])}, expenses {rs(o['averages']['expenses'])}, "
                   f"profit {rs(o['averages']['profit'])}.", "small"))
    story.append(Paragraph("What the numbers say", S["h2"]))
    for ins in o["insights"]:
        story.append(_callout(ins["text"], ins["level"]))
        story.append(Spacer(1, 3))
    story.append(KeepTogether([Paragraph("Sales and expenses by month", S["h2"]), _chart(o["months"])]))
    rows = [["Month", "Cash sales", "Credit sales", "Total sales", "Expenses", "Profit"]]
    for m in o["months"]:
        rows.append([m["month"], inr(m["cash_sales"]), inr(m["credit_sales"]), inr(m["sales"]), inr(m["expenses"]), inr(m["profit"])])
    t = o["totals"]
    rows.append(["Total", inr(t["cash_sales"]), inr(t["credit_sales"]), inr(t["sales"]), inr(t["expenses"]), inr(t["profit"])])
    tbl = _table(rows, [24 * mm] + [(CONTENT_W - 24 * mm) / 5] * 5, zebra=True)
    extra = [("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("FONTSIZE", (0, 1), (-1, -1), 8.5),
             ("LINEABOVE", (0, -1), (-1, -1), 0.8, GREEN), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]
    extra += [("TEXTCOLOR", (5, i + 1), (5, i + 1), RED) for i, m in enumerate(o["months"]) if m["profit"] < 0]
    tbl.setStyle(TableStyle(extra))
    story.append(Spacer(1, 4))
    story.append(tbl)

    if o["expenses_by_head"]:
        tot = o["totals"]["expenses"] or 1
        rows = [["Expense head", "Amount (Rs.)", "Share"]]
        for e in sorted(o["expenses_by_head"], key=lambda e: e["amount"], reverse=True):
            rows.append([e["label"], inr(e["amount"]), f"{e['amount'] / tot * 100:.0f}%"])
        tb = _table(rows, [70 * mm, 40 * mm, 25 * mm])
        tb.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
        story.append(KeepTogether([Paragraph("Where the money goes", S["h2"]), tb]))

    rc = o["receivables"]
    story.append(Paragraph("Money customers owe you", S["h2"]))
    ag = rc["ageing"]
    rows = [["0–30 days", "31–60 days", "61–90 days", "Over 90 days", "Total"],
            [inr(ag["0-30"]), inr(ag["31-60"]), inr(ag["61-90"]), inr(ag["90+"]), inr(rc["total"])]]
    tb = _table(rows, [CONTENT_W / 5] * 5)
    tb.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BACKGROUND", (2, 1), (3, 1), AMBER_BG)]))
    story.append(tb)
    if rc["overdue"]:
        story.append(Spacer(1, 4))
        rows = [["Customer", "Amount (Rs.)", "Days since invoice"]] + [[x["customer"], inr(x["amount"]), str(x["days"])] for x in rc["overdue"]]
        tb = _table(rows, [80 * mm, 40 * mm, 40 * mm])
        tb.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
        story.append(pm("<b>Follow up first</b> (unpaid for more than 45 days):", "small"))
        story.append(tb)

    wc = o["working_capital"]
    story.append(Paragraph("Working capital and loans", S["h2"]))
    rows = [["Item", "Amount (Rs.)"],
            ["Stock in hand", inr(wc["stock"])], ["Add: money customers owe you", inr(wc["receivables"])],
            ["Less: money you owe suppliers", inr(wc["payables"])],
            ["Money tied up in running the business", inr(wc["net"])],
            ["Supplier payments due in next 30 days", inr(o["payables"]["due_30_days"])],
            ["Supplier payments already overdue", inr(o["payables"]["overdue"])],
            ["Total monthly EMI", inr(o["loans"]["emi_total"])], ["Loans outstanding", inr(o["loans"]["outstanding"])]]
    if r.get("emi_to_profit_pct") is not None:
        rows.append(["EMI as share of average monthly profit", f"{r['emi_to_profit_pct']}%"])
    tb = _table(rows, [110 * mm, 50 * mm])
    tb.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("BACKGROUND", (0, 4), (-1, 4), GREEN_LIGHT),
                            ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold")]))
    story.append(tb)
    if o["data_gaps"]:
        story.append(Paragraph("To make this summary stronger", S["h2"]))
        for g in o["data_gaps"]:
            story.append(pm("• " + escape(g), "small"))
    return _build(title, business, story)


# ---------------------------------------------------------------- job description
def job_description(title: str, data: dict, business: str) -> bytes:
    i = data
    story = []
    facts = [("Openings", str(i.get("openings", 1))), ("Type", i.get("employment_type") or "—"),
             ("Work hours", i.get("work_hours") or "To be discussed"), ("Pay", i.get("pay") or "To be discussed"),
             ("Location", i.get("location") or "—")]
    rows = [[p(k, "small"), p(v, "cellb")] for k, v in facts]
    t = Table(rows, colWidths=[30 * mm, CONTENT_W - 30 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f7f4")), ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.append(t)
    story.append(Paragraph("Purpose of the role", S["h2"]))
    story.append(p(i["purpose"]))
    story.append(Paragraph("Main duties", S["h2"]))
    for d in i["duties"]:
        story.append(pm("• " + escape(d)))
    if i.get("skills"):
        story.append(Paragraph("Skills we are looking for", S["h2"]))
        for s in i["skills"]:
            story.append(pm("• " + escape(s)))
    if i.get("qualification"):
        story.append(Paragraph("Qualification", S["h2"]))
        story.append(p(i["qualification"]))
    if i.get("contact"):
        story.append(Paragraph("How to apply", S["h2"]))
        story.append(p(i["contact"]))
    story.append(Paragraph("Onboarding checklist (for the employer)", S["h2"]))
    story.append(check_list(data.get("onboarding", [])))
    story.append(Spacer(1, 8))
    story.append(_callout("Pay must be at least the minimum wage notified for this type of work in your state. "
                          "Labour registrations (Shop & Establishment, ESI, EPF) depend on how many people you employ – "
                          "ask the assistant about labour compliance.", "warn"))
    return _build(title, business, story)


RENDERERS = {"roadmap": roadmap, "checklist": checklist, "cashflow": cashflow, "jd": job_description}
