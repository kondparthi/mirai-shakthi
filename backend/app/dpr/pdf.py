"""DPR as a PDF in the usual bank / scheme layout (A4, English). Made with ReportLab when downloaded; nothing is stored.
Telugu text (names, places) is drawn as an image with Pillow, which shapes Telugu correctly. The bundled font has no
rupee sign, so amounts are printed as "Rs." – the form banks also use."""
from __future__ import annotations

import io
import re
from datetime import date
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from PIL import ImageDraw
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from ..training.certificate import FONTS, TELUGU, _font, _runs
from .narrative import SECTIONS

GREEN, GREEN_L, INK, INK2, LINE, GOLD = (colors.HexColor(x) for x in ("#1f4d3a", "#e8f2ec", "#1b2420", "#56635c", "#cfd8d2", "#b8913a"))
_REG = False


def _fonts():
    global _REG
    if not _REG:
        pdfmetrics.registerFont(TTFont("Noto", str(FONTS / "NotoSans-400.ttf")))
        pdfmetrics.registerFont(TTFont("Noto-B", str(FONTS / "NotoSans-700.ttf")))
        pdfmetrics.registerFontFamily("Noto", normal="Noto", bold="Noto-B", italic="Noto", boldItalic="Noto-B")
        _REG = True


def rs(v, dec: int = 0) -> str:
    """Rs. with Indian grouping."""
    if v is None:
        return "—"
    neg = v < 0
    n = round(abs(v), dec)
    whole = int(n)
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    if dec:
        s += f"{n - whole:.{dec}f}"[1:]
    return f"{'-' if neg else ''}Rs. {s}"


def num(v, dec: int = 0) -> str:
    return rs(v, dec).replace("Rs. ", "")


def _clean(text: str) -> str:
    return (text or "").replace("₹", "Rs. ").replace("Rs. Rs.", "Rs.")


ST = {}


def _styles():
    if ST:
        return ST
    base = dict(fontName="Noto", textColor=INK, leading=13.5, fontSize=9.6)
    ST["body"] = ParagraphStyle("body", **base, spaceAfter=5)
    ST["small"] = ParagraphStyle("small", **{**base, "fontSize": 8, "leading": 10.5, "textColor": INK2})
    ST["cell"] = ParagraphStyle("cell", **{**base, "fontSize": 8.4, "leading": 10.6})
    ST["cellb"] = ParagraphStyle("cellb", **{**base, "fontName": "Noto-B", "fontSize": 8.4, "leading": 10.6})
    ST["h1"] = ParagraphStyle("h1", **{**base, "fontName": "Noto-B", "fontSize": 13, "leading": 17, "textColor": GREEN, "spaceBefore": 10, "spaceAfter": 6})
    ST["title"] = ParagraphStyle("title", **{**base, "fontName": "Noto-B", "fontSize": 24, "leading": 30, "textColor": GREEN, "alignment": TA_CENTER})
    ST["sub"] = ParagraphStyle("sub", **{**base, "fontSize": 12, "leading": 17, "alignment": TA_CENTER, "textColor": INK2})
    ST["big"] = ParagraphStyle("big", **{**base, "fontName": "Noto-B", "fontSize": 17, "leading": 22, "alignment": TA_CENTER})
    return ST


# ---------------------------------------------------------------- Telugu as images
def _telugu_image(text: str, size_pt: float, width_pt: float, bold=False, align="LEFT") -> Image:
    scale = 4  # pixels per point
    px = int(size_pt * scale)
    words, lines, cur = text.split(), [], ""
    probe = ImageDraw.Draw(PILImage.new("RGB", (10, 10)))

    def width(s):
        return sum(probe.textlength(t, font=_font(px, bold, te)) for t, te in _runs(s))

    for w in words:
        trial = f"{cur} {w}".strip()
        if cur and width(trial) > width_pt * scale:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    lines.append(cur)
    lh = int(px * 1.55)
    img = PILImage.new("RGB", (int(max(width(x) for x in lines)) + 4, lh * len(lines) + 4), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        x = 0
        for t, te in _runs(line):
            f = _font(px, bold, te)
            d.text((x, i * lh + px * 1.15), t, font=f, fill="#1b2420", anchor="ls")
            x += d.textlength(t, font=f)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return Image(buf, width=img.width / scale, height=img.height / scale, hAlign=align)


def P(text, style="body", width=170 * mm):
    st = _styles()[style]
    text = _clean(str(text if text is not None else ""))
    if TELUGU.search(text):
        return _telugu_image(text, st.fontSize, width, bold=st.fontName == "Noto-B", align="CENTER" if st.alignment == TA_CENTER else "LEFT")
    return Paragraph(escape(text).replace("\n", "<br/>"), st)


def _table(rows, widths, header=True, total_rows=(), align_right_from=1, zebra=True):
    def cell(c, r, i, w):
        if not isinstance(c, str):
            return c
        name = "cellb" if (header and r == 0) or r in total_rows else "cell"
        if i >= align_right_from and not TELUGU.search(c):
            st = _styles()[name]
            return Paragraph(escape(_clean(c)), ParagraphStyle(f"{name}-r", parent=st, alignment=2))
        return P(c, name, w - 6)

    data = [[cell(c, r, i, w) for i, (c, w) in enumerate(zip(row, widths))] for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), GREEN_L)]
    for r in total_rows:
        style += [("BACKGROUND", (0, r), (-1, r), colors.HexColor("#f4f1e8"))]
    t.setStyle(TableStyle(style))
    return t


def _kv(pairs, widths=(62 * mm, 108 * mm)):
    return _table([[k, v] for k, v in pairs], list(widths), header=False, align_right_from=99)


def _chart(pl):
    d = Drawing(170 * mm, 62 * mm)
    ch = VerticalBarChart()
    ch.x, ch.y, ch.width, ch.height = 38, 26, 170 * mm - 60, 62 * mm - 44
    ch.data = [[p["sales"] / 100000 for p in pl], [p["pat"] / 100000 for p in pl]]
    ch.categoryAxis.categoryNames = [f"Year {p['year']}" for p in pl]
    ch.categoryAxis.labels.fontName = ch.valueAxis.labels.fontName = "Noto"
    ch.categoryAxis.labels.fontSize = ch.valueAxis.labels.fontSize = 7.5
    ch.valueAxis.valueMin = min(0, min(min(x) for x in ch.data))
    ch.valueAxis.labelTextFormat = "%.1f"
    ch.bars[0].fillColor, ch.bars[1].fillColor = colors.HexColor("#16825d"), colors.HexColor("#cf8508")
    ch.bars.strokeColor = None
    ch.barSpacing, ch.groupSpacing = 1.5, 10
    d.add(ch)
    d.add(String(0, 62 * mm - 10, "Sales and net profit by year (Rs. lakh)", fontName="Noto-B", fontSize=8.5, fillColor=INK))
    d.add(String(170 * mm - 150, 62 * mm - 10, "■ Sales   ", fontName="Noto", fontSize=8, fillColor=colors.HexColor("#16825d")))
    d.add(String(170 * mm - 104, 62 * mm - 10, "■ Net profit", fontName="Noto", fontSize=8, fillColor=colors.HexColor("#cf8508")))
    return d


def render(ctx: dict, result: dict, narrative: dict) -> bytes:
    """ctx: code, version, status, unit_name, location, promoter {name, age, education, occupation, skills, training, category},
    model {name, description}, activity, scheme, jobs, prepared_by, reviewed, approved, today."""
    _fonts()
    s, inp = result["summary"], result["inputs"]
    years = [p["year"] for p in result["pl"]]
    story = []
    draft = ctx["status"] != "approved"

    # ---- cover
    story += [Spacer(1, 18 * mm), P("DETAILED PROJECT REPORT", "title"), Spacer(1, 4 * mm),
              P(ctx["unit_name"], "big"), P(f"{ctx['model']['name']} · {ctx['location']}", "sub"), Spacer(1, 8 * mm),
              P(f"Promoter: {ctx['promoter']['name']}", "sub"),
              P(f"Prepared under the MIRAI Shakthi programme · {ctx['today']}", "sub"),
              P(f"Report {ctx['code']} · version {ctx['version']} · {ctx['status'].upper()}", "sub"), Spacer(1, 12 * mm)]
    key = [("Project cost", rs(s["project_cost"])), ("Promoter's contribution", f"{rs(s['own'])} ({s['own_pct']:.1f}%)"),
           ("Bank loan", rs(s["loan"]))]
    if s["subsidy"]:
        key.append(("Subsidy" + (f" ({ctx['scheme']})" if ctx.get("scheme") else ""), rs(s["subsidy"])))
    if s["grant"]:
        key.append(("Grant", rs(s["grant"])))
    if s["loan"]:
        key += [("Monthly instalment (EMI)", f"{rs(s['emi'])} × {s['emi_months']} months"
                 + (f" after {inp['loan']['moratorium_months']} months' moratorium" if inp['loan']['moratorium_months'] else "")),
                ("Average DSCR", f"{s['avg_dscr']:.2f}" if s["avg_dscr"] is not None else "—")]
    key += [("Break-even (year 1)", f"{s['bep_pct_y1']:.0f}% of sales" if s["bep_pct_y1"] is not None else "—"),
            ("Payback period", f"{s['payback_months']} months" if s["payback_months"] else "beyond the projection period")]
    if ctx.get("jobs"):
        key.append(("Employment", f"{ctx['jobs']} people"))
    story += [_kv(key), PageBreak()]

    n = 0

    def h(title):
        nonlocal n
        n += 1
        story.append(CondPageBreak(40 * mm))
        story.append(P(f"{n}. {title}", "h1"))

    # ---- 1 at a glance
    p = ctx["promoter"]
    h("Project at a glance")
    story.append(_kv([("Name of the unit", ctx["unit_name"]), ("Promoter", p["name"]),
                      ("Age / gender", " / ".join(x for x in (str(p.get("age") or ""), p.get("gender") or "") if x) or "—"),
                      ("Social category", p.get("category") or "—"), ("Address of the unit", ctx["location"]),
                      ("Activity", ctx["activity"].replace("_", " ").capitalize()), ("Enterprise model", ctx["model"]["name"]),
                      ("Scheme", ctx.get("scheme") or "Bank loan (no scheme)"), ("Project cost", rs(s["project_cost"])),
                      ("Bank loan", rs(s["loan"])), ("Employment", f"{ctx['jobs']} people" if ctx.get("jobs") else "—")]))

    def section(key_):
        title = dict(SECTIONS)[key_]
        h(title)
        for para in _clean(narrative.get(key_) or "").split("\n"):
            if para.strip():
                story.append(P(para.strip()))

    for k in ("promoter", "business", "market", "operations"):
        section(k)

    # ---- cost of project
    h("Cost of the project")
    rows = [["Item", "Specification", "Qty", "Rate (Rs.)", "Amount (Rs.)"]]
    rows += [[i["head"], i["spec"] or "", f"{i['qty']:g}", num(i["rate"]), num(i["amount"])] for i in result["cost_table"]]
    rows.append(["A. Equipment and assets", "", "", "", num(s["capital"])])
    extra = []
    if s["contingency"]:
        extra.append([f"B. Contingency ({inp['contingency_pct']:g}%)", "", "", "", num(s["contingency"])])
    if s["preoperative"]:
        extra.append(["C. Pre-operative expenses (licences, registration, deposits)", "", "", "", num(s["preoperative"])])
    extra.append(["D. Working capital", "", "", "", num(s["working_capital"])])
    extra.append(["Total project cost", "", "", "", num(s["project_cost"])])
    rows += extra
    tot = {len(result["cost_table"]) + 1, len(rows) - 1}
    story.append(_table(rows, [58 * mm, 52 * mm, 12 * mm, 22 * mm, 26 * mm], total_rows=tot, align_right_from=2))

    # ---- means of finance
    h("Means of finance")
    pc = s["project_cost"] or 1
    rows = [["Source", "Amount (Rs.)", "% of project cost"], ["Promoter's contribution", num(s["own"]), f"{s['own'] / pc * 100:.1f}%"]]
    if s["subsidy"]:
        rows.append([f"Subsidy{' – ' + ctx['scheme'] if ctx.get('scheme') else ''}", num(s["subsidy"]), f"{s['subsidy'] / pc * 100:.1f}%"])
    if s["grant"]:
        rows.append(["Grant", num(s["grant"]), f"{s['grant'] / pc * 100:.1f}%"])
    rows.append(["Bank term loan", num(s["loan"]), f"{s['loan'] / pc * 100:.1f}%"])
    rows.append(["Total", num(s["project_cost"]), "100%"])
    story.append(_table(rows, [90 * mm, 40 * mm, 40 * mm], total_rows={len(rows) - 1}))
    if s["loan"]:
        story.append(P(f"Loan terms: interest {inp['loan']['interest_pct']:g}% a year, tenure {inp['loan']['tenure_months']} months "
                       f"including a moratorium of {inp['loan']['moratorium_months']} months (interest paid monthly during the moratorium).", "small"))

    # ---- sales
    h("Sales assumptions")
    rows = [["Product / service", "Units a day", "Price (Rs.)", "Sales a day (Rs.)", "Sales a month (Rs.)"]]
    rows += [[f"{i['name']} (per {i['unit']})", f"{i['units_per_day']:g}", num(i["price"], 2 if i["price"] % 1 else 0), num(i["per_day"]),
              num(i["per_month"])] for i in result["sales_table"]]
    rows.append(["Total", "", "", num(sum(i["per_day"] for i in result["sales_table"])), num(s["monthly_sales_start"])])
    story.append(_table(rows, [62 * mm, 22 * mm, 24 * mm, 30 * mm, 32 * mm], total_rows={len(rows) - 1}))
    sa = inp["sales"]
    story.append(P(f"Working days: {sa['working_days']:g} a month. Sales grow {sa['monthly_growth_pct']:g}% a month in year 1 as customers "
                   f"build up, then {sa['yearly_growth_pct']:g}% a year.", "small"))

    # ---- expenses
    h("Operating expenses")
    ex = inp["expenses"]
    from .finance import FIXED_HEADS
    rows = [["Expense", "Per month (Rs.)", "Year 1 (Rs.)"], [f"Raw material ({ex['raw_material_pct']:g}% of sales)", "varies", num(result["pl"][0]["raw_material"])]]
    rows += [[label, num(ex[k]), num(result["pl"][0]["fixed_heads"][k])] for k, label in FIXED_HEADS if ex[k]]
    rows.append(["Total", "", num(result["pl"][0]["raw_material"] + result["pl"][0]["fixed"])])
    story.append(_table(rows, [90 * mm, 40 * mm, 40 * mm], total_rows={len(rows) - 1}))
    story.append(P(f"Fixed expenses rise {ex['yearly_increase_pct']:g}% a year. Depreciation on equipment at {inp['depreciation_pct']:g}% "
                   f"(written-down value); pre-operative expenses written off over {len(years)} years."
                   + (f" Income tax at {inp['tax_pct']:g}% of profit." if inp["tax_pct"] else " No income tax is provided (income below the taxable limit)."), "small"))

    # ---- profitability
    colw = [52 * mm] + [118 * mm / len(years)] * len(years)
    hdr = ["Rs."] + [f"Year {y}" for y in years]
    pl = result["pl"]
    rows = [hdr, ["Sales"] + [num(x["sales"]) for x in pl], ["Raw material"] + [num(x["raw_material"]) for x in pl],
            ["Gross margin"] + [num(x["gross_margin"]) for x in pl]]
    rows += [[label] + [num(x["fixed_heads"][k]) for x in pl] for k, label in FIXED_HEADS if any(x["fixed_heads"][k] for x in pl)]
    rows += [["Operating profit (EBITDA)"] + [num(x["ebitda"]) for x in pl], ["Depreciation and write-off"] + [num(x["depreciation"]) for x in pl],
             ["Interest on loan"] + [num(x["interest"]) for x in pl], ["Profit before tax"] + [num(x["pbt"]) for x in pl],
             ["Tax"] + [num(x["tax"]) for x in pl], ["Net profit"] + [num(x["pat"]) for x in pl],
             ["Net profit % of sales"] + [f"{x['pat_pct']:.1f}%" for x in pl]]
    h("Projected profitability")
    story.append(_table(rows, colw, total_rows={3, len(rows) - 2}))
    story.append(Spacer(1, 4 * mm))
    story.append(_chart(pl))

    # ---- cash flow
    h("Projected cash flow")
    cf = result["cash_flow"]
    rows = [hdr, ["Opening cash and working capital"] + [num(x["opening"]) for x in cf],
            ["Add: net profit + depreciation"] + [num(x["cash_accrual"]) for x in cf],
            ["Less: loan principal repaid"] + [num(x["principal"]) for x in cf],
            ["Less: owner's drawings"] + [num(x["drawings"]) for x in cf],
            ["Closing cash"] + [num(x["closing"]) for x in cf]]
    story.append(_table(rows, colw, total_rows={len(rows) - 1}))

    # ---- DSCR
    h("Debt service coverage ratio (DSCR)")
    dr = result["dscr"]
    rows = [hdr, ["Net profit"] + [num(x["pat"]) for x in dr], ["Add: depreciation"] + [num(x["depreciation"]) for x in dr],
            ["Add: interest"] + [num(x["interest"]) for x in dr], ["Less: owner's drawings"] + [num(x["drawings"]) for x in dr],
            ["A. Available to repay"] + [num(x["available"]) for x in dr],
            ["B. Interest + principal due"] + [num(x["debt_service"]) for x in dr],
            ["DSCR (A ÷ B)"] + [f"{x['dscr']:.2f}" if x["dscr"] is not None else "—" for x in dr]]
    story.append(_table(rows, colw, total_rows={len(rows) - 1}))
    if s["avg_dscr"] is not None:
        story.append(P(f"Average DSCR over the repayment years: {s['avg_dscr']:.2f} (lowest {s['min_dscr']:.2f}).", "body"))

    # ---- break-even
    h("Break-even analysis")
    rows = [hdr, ["Sales"] + [num(x["sales"]) for x in pl],
            ["Variable cost (raw material)"] + [num(x["raw_material"]) for x in pl],
            ["Contribution"] + [num(x["gross_margin"]) for x in pl],
            ["Fixed cost incl. depreciation and interest"] + [num(x["fixed"] + x["depreciation"] + x["interest"]) for x in pl],
            ["Break-even sales"] + [num(x["bep_sales"]) if x["bep_sales"] is not None else "—" for x in dr],
            ["Break-even % of sales"] + [f"{x['bep_pct']:.1f}%" if x["bep_pct"] is not None else "—" for x in dr],
            ["Cash break-even sales"] + [num(x["cash_bep_sales"]) if x["cash_bep_sales"] is not None else "—" for x in dr]]
    story.append(_table(rows, colw, total_rows={6}))

    # ---- repayment
    if s["loan"]:
        h("Loan repayment schedule")
        rows = [["Year", "Opening balance", "Interest", "Principal", "Total paid", "Closing balance"]]
        rows += [[str(x["year"]), num(x["opening"]), num(x["interest"]), num(x["principal"]), num(x["payment"]), num(x["closing"])]
                 for x in result["repayment_yearly"]]
        story.append(_table(rows, [18 * mm, 32 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm]))
        story.append(P("The month-by-month schedule is in Annexure 1.", "small"))

    for k in ("swot", "risks", "conclusion"):
        section(k)

    # ---- sign-off
    story.append(Spacer(1, 6 * mm))
    sign = [["Prepared by", "Reviewed by", "Approved by", "Promoter"],
            [ctx.get("prepared_by") or "", ctx.get("reviewed") or "", ctx.get("approved") or "", p["name"]],
            ["", "", "", "Signature"]]
    t = Table([[P(c, "cellb" if r == 0 else "small", 38 * mm) for c in row] for r, row in enumerate(sign)],
              colWidths=[42.5 * mm] * 4, rowHeights=[None, None, 16 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), GREEN_L)]))
    story.append(KeepTogether([P("Certification", "h1"), P("The figures in this report are calculated by the MIRAI Shakthi system from the "
                                                            "assumptions above. The DPR & Credit Officer has reviewed the report.", "small"),
                               Spacer(1, 3 * mm), t]))

    # ---- annexure
    if s["loan"]:
        story += [PageBreak(), P("Annexure 1 – Monthly repayment schedule", "h1")]
        rows = [["Month", "Opening", "Instalment", "Interest", "Principal", "Closing"]]
        rows += [[str(r["month"]), num(r["opening"]), num(r["payment"]), num(r["interest"]), num(r["principal"]), num(r["closing"])]
                 for r in result["repayment"]]
        story.append(_table(rows, [18 * mm, 31 * mm, 31 * mm, 30 * mm, 30 * mm, 30 * mm], zebra=False))

    def page(c, doc):
        c.saveState()
        c.setFont("Noto", 7.5)
        c.setFillColor(INK2)
        c.drawString(20 * mm, 10 * mm, f"MIRAI Shakthi · DPR {ctx['code']} · version {ctx['version']} · {ctx['status']}")
        c.drawRightString(190 * mm, 10 * mm, f"Page {doc.page}")
        c.setStrokeColor(GOLD)
        c.setLineWidth(1.2)
        c.line(20 * mm, 287 * mm, 190 * mm, 287 * mm)
        if draft:
            c.setFont("Noto-B", 54)
            c.setFillColor(colors.Color(0.82, 0.3, 0.23, alpha=0.13))
            c.translate(105 * mm, 148 * mm)
            c.rotate(40)
            c.drawCentredString(0, 0, "DRAFT – NOT APPROVED")
        c.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"DPR {ctx['code']} – {re.sub(r'[^ -~]', '', ctx['unit_name'])}", author="MIRAI Shakthi")
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return buf.getvalue()


def today_str() -> str:
    return date.today().strftime("%d %b %Y")
