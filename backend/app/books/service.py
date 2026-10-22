"""Daily business management (M9): entries and stock, period summaries, receivables, EMI tracker, monthly summaries with
rule-based business alerts, sync from orders (M8), and a simple parser for spoken entries."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models_p3 import LoanApplication
from ..models_p4 import Unit
from ..models_p5 import Order
from ..models_p6 import DEFAULT_CATEGORIES, NON_OPERATING, LedgerEntry, MonthlySummary, StockItem, StockMove
from ..training.service import bump_stage
from ..market.service import now


# ---------------------------------------------------------------- categories and stock
def categories(u: Unit, lang: str = "en") -> dict:
    lc = (u.model.ledger_categories if u.model and u.model.ledger_categories else None) or {
        k: [{"code": c, "label": en, "label_te": te} for c, en, te in v] for k, v in DEFAULT_CATEGORIES.items()}
    lab = (lambda x: x.get("label_te") or x["label"]) if lang == "te" else (lambda x: x["label"])
    sale = [{"code": x["code"], "label": lab(x)} for x in lc.get("sale", [])]
    expense = [{"code": x["code"], "label": lab(x)} for x in lc.get("expense", [])]
    expense += [{"code": k, "label": v[1] if lang == "te" else v[0], "non_operating": True} for k, v in NON_OPERATING.items()]
    return {"sale": sale, "expense": expense}


def category_codes(u: Unit, kind: str) -> set[str]:
    return {c["code"] for c in categories(u)[kind]}


def ensure_stock(db: Session, u: Unit) -> None:
    """The first time the books are opened, add the model's starter stock items."""
    if db.scalar(select(StockItem.id).where(StockItem.unit_id == u.id).limit(1)):
        return
    for it in (u.model.stock_template if u.model and u.model.stock_template else []):
        db.add(StockItem(unit_id=u.id, name=it["name"], name_te=it.get("name_te"), measure=it.get("measure", "kg"), qty=0,
                         reorder_level=float(it.get("reorder_level") or 0)))
    db.flush()


def is_low(item: StockItem) -> bool:
    """At or below the reorder level – only once the item has been stocked (a new starter list is not "low")."""
    return bool(item.active and item.reorder_level > 0 and item.qty <= item.reorder_level and item.moves)


def stock_out(item: StockItem, lang: str = "en") -> dict:
    return {"id": item.id, "name": (item.name_te or item.name) if lang == "te" else item.name, "name_en": item.name, "name_te": item.name_te,
            "measure": item.measure, "qty": round(item.qty, 3), "reorder_level": item.reorder_level, "cost": item.cost, "active": item.active,
            "low": is_low(item),
            "moves": [{"kind": m.kind, "qty": m.qty, "on": m.on.isoformat(), "note": m.note} for m in item.moves[:8]]}


def move_stock(db: Session, item: StockItem, kind: str, qty: float, on: date, note: str | None = None, entry_id: int | None = None) -> None:
    if qty < 0:
        raise HTTPException(422, "Quantity cannot be negative")
    if kind == "in":
        item.qty += qty
    elif kind == "out":
        if qty > item.qty + 1e-9:
            raise HTTPException(422, f"Only {item.qty:g} {item.measure} of {item.name} in stock")
        item.qty -= qty
    else:  # count: what is actually there
        item.qty = qty
    db.add(StockMove(item_id=item.id, kind=kind, qty=qty, on=on, note=note, entry_id=entry_id, at=now()))


# ---------------------------------------------------------------- entries
def entry_out(e: LedgerEntry, cats: dict | None = None, items: dict | None = None) -> dict:
    label = None
    if cats:
        label = next((c["label"] for c in cats.get(e.kind, []) if c["code"] == e.category), e.category)
    return {"id": e.id, "kind": e.kind, "on": e.on.isoformat(), "amount": e.amount, "category": e.category, "category_label": label or e.category,
            "stock_item_id": e.stock_item_id, "stock_item": (items or {}).get(e.stock_item_id), "qty": e.qty, "payment_mode": e.payment_mode,
            "customer": {"id": e.customer.id, "name": e.customer.name, "mobile": e.customer.mobile} if e.customer else None,
            "due_date": e.due_date.isoformat() if e.due_date else None, "collected_on": e.collected_on.isoformat() if e.collected_on else None,
            "collected_mode": e.collected_mode, "outstanding": e.kind == "sale" and e.payment_mode == "credit" and not e.collected_on,
            "overdue": bool(e.kind == "sale" and e.payment_mode == "credit" and not e.collected_on and e.due_date and e.due_date < date.today()),
            "order_id": e.order_id, "note": e.note, "source": e.source, "has_photo": bool(e.photo),
            "created_at": e.created_at.isoformat() if e.created_at else None}


# ---------------------------------------------------------------- orders (M8) → books
def sync_order(db: Session, o: Order) -> None:
    """A delivered or paid order is a sale in the books (credit if delivered unpaid); a cancelled order is removed."""
    e = db.scalar(select(LedgerEntry).where(LedgerEntry.order_id == o.id))
    if o.status == "cancelled":
        if e:
            db.delete(e)
        return
    if o.status not in ("delivered", "paid"):
        return
    if not e:
        u = db.get(Unit, o.unit_id)
        codes = [c["code"] for c in categories(u)["sale"]]
        cat = next((c for c in ("orders", "spraying", "office", "sales") if c in codes), codes[0] if codes else "sales")
        credit = o.status == "delivered"
        e = LedgerEntry(unit_id=o.unit_id, kind="sale", on=o.date if o.date and o.date <= date.today() else date.today(), amount=o.amount,
                        category=cat, payment_mode="credit" if credit else (o.payment_mode or "cash"), customer_id=o.customer_id,
                        due_date=date.today() + timedelta(days=7) if credit else None, order_id=o.id,
                        note=f"Order {o.code}: " + ", ".join(f"{ln['name']} × {ln['qty']:g}" for ln in o.lines)[:280], source="order", created_at=now())
        db.add(e)
    elif o.status == "paid" and e.payment_mode == "credit" and not e.collected_on:
        e.collected_on, e.collected_mode = date.today(), o.payment_mode or "cash"
    db.flush()


# ---------------------------------------------------------------- summaries
def period_bounds(period: str, day: date) -> tuple[date, date]:
    if period == "day":
        return day, day
    if period == "week":
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=6)
    start = day.replace(day=1)
    nxt = (start + timedelta(days=32)).replace(day=1)
    return start, nxt - timedelta(days=1)


def summarise(entries: list[LedgerEntry]) -> dict:
    sales = sum(e.amount for e in entries if e.kind == "sale")
    op = [e for e in entries if e.kind == "expense" and e.category not in NON_OPERATING]
    expenses = sum(e.amount for e in op)
    by_cat: dict[str, float] = defaultdict(float)
    for e in entries:
        by_cat[f"{e.kind}:{e.category}"] += e.amount
    modes: dict[str, float] = defaultdict(float)
    for e in entries:
        if e.kind == "sale":
            modes[e.payment_mode] += e.amount
    return {"sales": round(sales, 2), "expenses": round(expenses, 2), "profit": round(sales - expenses, 2),
            "emi_paid": round(sum(e.amount for e in entries if e.kind == "expense" and e.category == "loan_emi"), 2),
            "drawings": round(sum(e.amount for e in entries if e.kind == "expense" and e.category == "drawings"), 2),
            "equipment": round(sum(e.amount for e in entries if e.kind == "expense" and e.category == "equipment"), 2),
            "entries": len(entries), "days_recorded": len({e.on for e in entries}),
            "by_category": {k: round(v, 2) for k, v in sorted(by_cat.items(), key=lambda x: -x[1])},
            "by_mode": {k: round(v, 2) for k, v in modes.items()}}


def entries_between(db: Session, uid: int, start: date, end: date) -> list[LedgerEntry]:
    return list(db.scalars(select(LedgerEntry).where(LedgerEntry.unit_id == uid, LedgerEntry.on >= start, LedgerEntry.on <= end)
                           .order_by(LedgerEntry.on.desc(), LedgerEntry.id.desc())))


def receivables(db: Session, uid: int) -> list[LedgerEntry]:
    return list(db.scalars(select(LedgerEntry).where(LedgerEntry.unit_id == uid, LedgerEntry.kind == "sale", LedgerEntry.payment_mode == "credit",
                                                     LedgerEntry.collected_on.is_(None)).order_by(LedgerEntry.due_date)))


def loans_of(db: Session, u: Unit) -> list[LoanApplication]:
    if not u.dpr_id:
        return []
    return list(db.scalars(select(LoanApplication).where(LoanApplication.dpr_id == u.dpr_id, LoanApplication.status == "disbursed")))


def emi_status(db: Session, u: Unit, month_end: date | None = None) -> str:
    from ..dpr.service import repayment_state

    t = month_end or date.today()
    reps = [r for a in loans_of(db, u) for r in a.repayments if r.due_date <= t]
    if not reps:
        return "none"
    overdue = sum(1 for r in reps if repayment_state(r, t) == "overdue")
    late = sum(1 for r in reps if repayment_state(r, t) == "late")
    return "default" if overdue >= 3 else "delayed" if overdue or late else "on_time"


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_range(key: str) -> tuple[date, date]:
    y, m = map(int, key.split("-"))
    return period_bounds("month", date(y, m, 1))


def alerts_for(db: Session, u: Unit, key: str, s: dict) -> list[dict]:
    """Rule-based business alerts for the mentor (spec: falling sales, rising costs, missed EMIs, no entries)."""
    out = []
    start, end = month_range(key)
    prev = [db.scalar(select(MonthlySummary).where(MonthlySummary.unit_id == u.id, MonthlySummary.month == month_key(start - timedelta(days=d))))
            for d in (1, 32)]
    prev = [p for p in prev if p and p.entries]
    if s["entries"] == 0:
        out.append({"code": "no_entries", "level": "high", "text": "No sales or expenses recorded this month"})
    elif s["days_recorded"] < 8:
        out.append({"code": "few_entries", "level": "medium", "text": f"Records on only {s['days_recorded']} days"})
    if prev and s["entries"]:
        avg = sum(p.sales for p in prev) / len(prev)
        if avg > 0 and s["sales"] < 0.8 * avg:
            out.append({"code": "sales_down", "level": "high", "text": f"Sales down {round(100 * (1 - s['sales'] / avg))}% on the previous months"})
        pr = [p.expenses / p.sales for p in prev if p.sales]
        if pr and s["sales"] and s["expenses"] / s["sales"] > sum(pr) / len(pr) + 0.10:
            out.append({"code": "costs_up", "level": "medium", "text": f"Costs are {round(100 * s['expenses'] / s['sales'])}% of sales (was {round(100 * sum(pr) / len(pr))}%)"})
    if s["entries"] and s["profit"] < 0:
        out.append({"code": "loss", "level": "high", "text": "Loss this month"})
    st = emi_status(db, u, end)
    if st in ("delayed", "default"):
        out.append({"code": "emi", "level": "high" if st == "default" else "medium", "text": "Loan EMIs overdue" if st == "default" else "Loan EMI paid late or overdue"})
    rec = sum(e.amount for e in receivables(db, u.id) if e.on <= end)
    if s["sales"] and rec > 0.3 * s["sales"]:
        out.append({"code": "credit_high", "level": "medium", "text": f"₹{rec:,.0f} still to collect from credit sales"})
    return out


def freeze_month(db: Session, u: Unit, key: str, by: str = "auto", note: str | None = None) -> MonthlySummary:
    start, end = month_range(key)
    s = summarise(entries_between(db, u.id, start, end))
    ms = db.scalar(select(MonthlySummary).where(MonthlySummary.unit_id == u.id, MonthlySummary.month == key))
    if not ms:
        ms = MonthlySummary(unit_id=u.id, month=key)
        db.add(ms)
    ms.sales, ms.expenses, ms.profit, ms.emi_paid, ms.drawings = s["sales"], s["expenses"], s["profit"], s["emi_paid"], s["drawings"]
    ms.entries, ms.days_recorded, ms.by_category = s["entries"], s["days_recorded"], s["by_category"]
    ms.receivables = round(sum(e.amount for e in receivables(db, u.id) if e.on <= end), 2)
    ms.emi_status = emi_status(db, u, end)
    ms.alerts = alerts_for(db, u, key, s)
    ms.submitted_by, ms.submitted_at = by, now()
    if note is not None:
        ms.note = note
    if s["entries"]:
        o = u.entrepreneur or u.group
        if o is not None:
            bump_stage(o, 6)  # tracking the business every month
    db.flush()
    return ms


def auto_close(db: Session, u: Unit) -> None:
    """Freeze every finished month since launch that has no summary yet ("submitted automatically")."""
    if u.status not in ("launched", "paused") or not u.launch_date:
        return
    first = u.launch_date.replace(day=1)
    this = date.today().replace(day=1)
    have = set(db.scalars(select(MonthlySummary.month).where(MonthlySummary.unit_id == u.id)))
    d = first
    while d < this:
        k = month_key(d)
        if k not in have:
            freeze_month(db, u, k)
        d = (d + timedelta(days=32)).replace(day=1)


def summary_out(ms: MonthlySummary) -> dict:
    return {"id": ms.id, "unit_id": ms.unit_id, "month": ms.month, "sales": ms.sales, "expenses": ms.expenses, "profit": ms.profit,
            "emi_paid": ms.emi_paid, "drawings": ms.drawings, "receivables": ms.receivables, "entries": ms.entries,
            "days_recorded": ms.days_recorded, "emi_status": ms.emi_status, "by_category": ms.by_category, "alerts": ms.alerts, "note": ms.note,
            "submitted_by": ms.submitted_by, "submitted_at": ms.submitted_at.isoformat() if ms.submitted_at else None,
            "reviewed": bool(ms.reviewed_at), "review_note": ms.review_note, "reviewed_at": ms.reviewed_at.isoformat() if ms.reviewed_at else None}


# ---------------------------------------------------------------- spoken entries
NUM_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100, "thousand": 1000,
             "ఒకటి": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5, "పది": 10, "ఇరవై": 20, "యాభై": 50, "వంద": 100, "వెయ్యి": 1000}
SALE_WORDS = ("sold", "sale", "sales", "sell", "got", "received", "income", "అమ్మ", "అమ్మకం", "అమ్మాను", "వచ్చింది", "ఆదాయం")
EXPENSE_WORDS = ("bought", "buy", "paid", "spent", "expense", "purchase", "కొన్న", "కొనుగోలు", "ఖర్చు", "చెల్లించ", "కట్టాను")
MODES = {"upi": ("upi", "phonepe", "gpay", "google pay", "paytm", "యూపీఐ", "ఫోన్‌పే", "ఫోన్ పే"), "credit": ("credit", "udhaar", "later", "అప్పు", "ఉద్దెర", "తర్వాత"),
         "cash": ("cash", "నగదు", "క్యాష్")}


def parse_spoken(text: str, u: Unit, items: list[StockItem]) -> dict:
    """Turn "sold 40 plates snacks 1600 rupees cash" / "పాలు 10 లీటర్లు 500 రూపాయలు కొన్నాను" into a draft entry.
    Always shown to the person to check before saving."""
    t = (text or "").lower().strip()
    out: dict = {"kind": None, "amount": None, "qty": None, "category": None, "stock_item_id": None, "payment_mode": "cash", "note": text.strip()[:300]}
    if any(w in t for w in EXPENSE_WORDS):
        out["kind"] = "expense"
    elif any(w in t for w in SALE_WORDS):
        out["kind"] = "sale"
    for mode, words in MODES.items():
        if any(w in t for w in words):
            out["payment_mode"] = mode
            break
    nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", t)]
    if not nums:
        nums = [float(v) for k, v in NUM_WORDS.items() if re.search(rf"(^|\s){re.escape(k)}($|\s)", t)]
    # The amount is the number next to rupees / రూపాయలు / ₹, else the largest number; another number is the quantity.
    m = re.search(r"(?:₹|rs\.?|rupees?)\s*(\d[\d,]*(?:\.\d+)?)|(\d[\d,]*(?:\.\d+)?)\s*(?:₹|rs\.?|rupees?|రూపాయ|రూ)", t)
    if m:
        out["amount"] = float((m.group(1) or m.group(2)).replace(",", ""))
    elif nums:
        out["amount"] = max(nums)
    rest = [n for n in nums if n != out["amount"]]
    if rest:
        out["qty"] = rest[0]
    cats = categories(u, "en")
    cats_te = categories(u, "te")
    for kind in ([out["kind"]] if out["kind"] else ["expense", "sale"]):
        for c_en, c_te in zip(cats[kind], cats_te[kind]):
            words = [w for w in re.split(r"[\s/&,()]+", c_en["label"].lower()) + re.split(r"[\s/&,()]+", c_te["label"]) if len(w) > 2]
            if any(w in t for w in words):
                out["category"], out["kind"] = c_en["code"], kind
                break
        if out["category"]:
            break
    for it in items:  # a purchase may name part of the item ("bought milk"); a sale must name it fully (selling "millet snacks" is not "millet flour")
        partial = out["kind"] == "expense" and any(w in t for w in it.name.lower().split() if len(w) > 3)
        if it.name.lower() in t or (it.name_te and it.name_te in t) or partial:
            out["stock_item_id"] = it.id
            break
    if out["kind"] is None and out["amount"]:
        out["kind"] = "sale"
    if out["kind"] and not out["category"]:
        out["category"] = cats[out["kind"]][0]["code"] if cats[out["kind"]] else None
    return out

