"""Receipt / invoice for a sale (A5 PDF) with a UPI QR code when the unit has a UPI ID. Same fonts as the DPR; Telugu names
are drawn correctly."""
from __future__ import annotations

import io
from urllib.parse import quote

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.platypus import Image, SimpleDocTemplate, Spacer

from ..dpr.pdf import GOLD, INK2, P, _fonts, _kv, _table, num, rs


def upi_uri(upi_id: str, name: str, amount: float, note: str) -> str:
    return f"upi://pay?pa={quote(upi_id)}&pn={quote(name[:40])}&am={amount:.2f}&cu=INR&tn={quote(note[:40])}"


def _qr_png(data: str, size_mm: float) -> Image:
    import segno

    buf = io.BytesIO()
    segno.make(data, error="m").save(buf, kind="png", scale=8, border=2)
    buf.seek(0)
    return Image(buf, width=size_mm * mm, height=size_mm * mm)


def render(ctx: dict) -> bytes:
    """ctx: number, date, unit {name, place, mobile, upi_id}, customer {name, mobile} | None, lines [{name, qty, price}],
    amount, payment_mode, status ("Paid" / "To pay"), due_date."""
    _fonts()
    u = ctx["unit"]
    w = 128 * mm
    story = [P(u["name"], "big"), P(u.get("place") or "", "sub"), P(f"Phone {u['mobile']}" if u.get("mobile") else "", "sub"), Spacer(1, 4 * mm),
             P("RECEIPT · రసీదు", "h1")]
    rows = [("Receipt no.", ctx["number"]), ("Date", ctx["date"])]
    if ctx.get("customer"):
        rows.append(("Customer", f"{ctx['customer']['name']} · {ctx['customer']['mobile']}"))
    story.append(_kv(rows, widths=(36 * mm, w - 36 * mm)))
    story.append(Spacer(1, 3 * mm))
    t = [["Item", "Qty", "Rate", "Amount"]]
    for ln in ctx["lines"]:
        t.append([ln["name"], f"{float(ln.get('qty') or 1):g}", num(ln.get("price") or ln.get("amount") or 0),
                  num(float(ln.get("qty") or 1) * float(ln.get("price") or 0) if ln.get("price") is not None else ln.get("amount") or 0)])
    t.append(["Total", "", "", num(ctx["amount"])])
    story.append(_table(t, [w - 64 * mm, 14 * mm, 24 * mm, 26 * mm], total_rows={len(t) - 1}))
    story.append(Spacer(1, 3 * mm))
    status = ctx["status"]
    line = f"{status} · {rs(ctx['amount'])}" + (f" · {ctx['payment_mode'].upper()}" if status == "Paid" else "")
    if ctx.get("due_date") and status != "Paid":
        line += f" · due by {ctx['due_date']}"
    story.append(P(line, "h1"))
    if u.get("upi_id") and status != "Paid":
        story += [Spacer(1, 2 * mm), _qr_png(upi_uri(u["upi_id"], u["name"], ctx["amount"], ctx["number"]), 34),
                  P(f"Scan to pay by UPI · {u['upi_id']}", "sub")]
    story += [Spacer(1, 6 * mm), P("Thank you · ధన్యవాదాలు", "sub"), P("A MIRAI Shakthi enterprise", "small")]

    def page(c, doc):
        c.saveState()
        c.setStrokeColor(GOLD)
        c.setLineWidth(1.2)
        c.line(10 * mm, A5[1] - 8 * mm, A5[0] - 10 * mm, A5[1] - 8 * mm)
        c.setFont("Noto", 7)
        c.setFillColor(INK2)
        c.drawString(10 * mm, 6 * mm, f"MIRAI Shakthi · {ctx['number']}")
        c.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A5, leftMargin=10 * mm, rightMargin=10 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                      title=f"Receipt {ctx['number']}", author="MIRAI Shakthi").build(story, onFirstPage=page, onLaterPages=page)
    return buf.getvalue()
