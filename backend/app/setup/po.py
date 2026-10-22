"""Purchase order as a PDF (A4), made when downloaded. Same fonts and table style as the DPR."""
from __future__ import annotations

import io
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Spacer

from ..dpr.pdf import GOLD, INK2, P, _fonts, _kv, _table, num, rs


def render(ctx: dict) -> bytes:
    """ctx: po_number, po_date, supplier {name, gstin, address, contact, mobile}, unit {name, code, location, owner, mobile},
    lines [{item, spec, qty, rate}], amount, gst_included, expected_delivery, payment, warranty_months, reference, issued_by."""
    _fonts()
    story = [P("PURCHASE ORDER", "title"), P(f"{ctx['po_number']} · {ctx['po_date']}", "sub"), Spacer(1, 6 * mm)]
    s, u = ctx["supplier"], ctx["unit"]
    story.append(_kv([("Supplier", s["name"]), ("GSTIN", s.get("gstin") or "—"), ("Supplier address", s["address"]),
                      ("Contact", f"{s['contact']} · {s['mobile']}"), ("Deliver to", f"{u['name']} ({u['code']})"), ("Delivery address", u["location"]),
                      ("Entrepreneur", f"{u['owner']}" + (f" · {u['mobile']}" if u.get("mobile") else "")),
                      ("Deliver by", ctx.get("expected_delivery") or "As agreed"), ("Payment", ctx.get("payment") or "—"),
                      ("Reference", ctx.get("reference") or "—")]))
    story += [Spacer(1, 5 * mm), P("Items", "h1")]
    rows = [["#", "Item", "Specification", "Qty", "Rate (Rs.)", "Amount (Rs.)"]]
    total = 0.0
    for i, ln in enumerate(ctx["lines"], 1):
        amt = float(ln.get("qty") or 0) * float(ln.get("rate") or 0)
        total += amt
        rows.append([str(i), ln.get("item") or "", ln.get("spec") or "", f"{float(ln.get('qty') or 0):g}", num(ln.get("rate") or 0), num(amt)])
    rows.append(["", f"Total{' (GST included)' if ctx.get('gst_included', True) else ' (GST extra)'}", "", "", "", num(ctx.get("amount") or total)])
    story.append(_table(rows, [8 * mm, 52 * mm, 44 * mm, 14 * mm, 24 * mm, 28 * mm], total_rows={len(rows) - 1}, align_right_from=3))
    story += [Spacer(1, 3 * mm), P(f"Amount in figures: {rs(ctx.get('amount') or total)}", "body"), Spacer(1, 4 * mm), P("Terms", "h1")]
    terms = [
        "Deliver the items to the address above and install them at the unit; the order is complete when the unit owner and MIRAI staff sign the handover.",
        f"Warranty: {ctx['warranty_months']} months from installation." if ctx.get("warranty_months") else "Warranty as per the manufacturer, from the date of installation.",
        "Send the tax invoice in the name of the unit owner, with serial numbers of the equipment.",
        "Payment is released after installation and handover, from the source shown above.",
    ]
    for t in terms:
        story.append(P(f"• {t}", "body"))
    story += [Spacer(1, 10 * mm), _kv([("Issued by", ctx.get("issued_by") or "MIRAI Shakthi"), ("Supplier acceptance", "Signature and seal")])]

    def page(c, doc):
        c.saveState()
        c.setFont("Noto", 7.5)
        c.setFillColor(INK2)
        c.drawString(20 * mm, 10 * mm, f"MIRAI Shakthi · {ctx['po_number']} · generated {date.today().strftime('%d %b %Y')}")
        c.drawRightString(190 * mm, 10 * mm, f"Page {doc.page}")
        c.setStrokeColor(GOLD)
        c.setLineWidth(1.2)
        c.line(20 * mm, 287 * mm, 190 * mm, 287 * mm)
        c.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                      title=ctx["po_number"], author="MIRAI Shakthi").build(story, onFirstPage=page, onLaterPages=page)
    return buf.getvalue()
