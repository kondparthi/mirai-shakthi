"""M9 – daily business management. The entrepreneur keeps their books in the app (typing or speaking); staff and mentors
in scope can see and help: sales and expenses (Form 9.1), stock with low-stock alerts, credit sales to collect with
reminders, receipts (PDF + WhatsApp + UPI QR), EMI tracker, daily / weekly / monthly summaries, and monthly summaries
sent to the mentor and programme reports with rule-based alerts."""
import datetime as dt
import re
from datetime import date, timedelta
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..guidance import llm
from ..models import User
from ..models_p4 import Unit
from ..models_p6 import NON_OPERATING, LedgerEntry, MonthlySummary, StockItem
from ..programme.service import Masters
from ..roles import SETUP_READ
from ..security import ALGO, current_user, require_roles
from ..setup.service import can_see_unit
from ..training.service import audit
from ..books import receipt
from ..books.service import (auto_close, is_low, categories, category_codes, emi_status, ensure_stock, entries_between, entry_out, freeze_month, loans_of,
                             month_key, month_range, move_stock, parse_spoken, period_bounds, receivables, stock_out, summarise, summary_out)
from ..market.service import MARKET_WRITE, now, save_photo, unit_access, upsert_customer, wa_link

router = APIRouter(prefix="/api/v1/books", tags=["books"])
public = APIRouter(prefix="/api/v1/public", tags=["public"])
staff_read = require_roles(*SETUP_READ)


def _lang(user: User, lang: Optional[str]) -> str:
    return lang if lang in ("en", "te") else (user.language or "en")


def _items(db: Session, uid: int, lang: str = "en") -> dict[int, str]:
    return {i.id: ((i.name_te or i.name) if lang == "te" else i.name) for i in db.scalars(select(StockItem).where(StockItem.unit_id == uid))}


@router.get("/units/{uid}/meta")
def meta(uid: int, lang: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid)
    ensure_stock(db, u)
    db.commit()
    lg = _lang(user, lang)
    return {"unit": {"id": u.id, "code": u.code, "name": u.name, "status": u.status, "upi_id": u.upi_id, "launch_date": u.launch_date.isoformat() if u.launch_date else None},
            "categories": categories(u, lg), "non_operating": list(NON_OPERATING),
            "stock": [stock_out(i, lg) for i in db.scalars(select(StockItem).where(StockItem.unit_id == u.id, StockItem.active.is_(True)).order_by(StockItem.name))],
            "can_write": user.role == "msme" or user.role in MARKET_WRITE}


class SettingsIn(BaseModel):
    upi_id: Optional[str] = Field(default=None, max_length=60)


@router.put("/units/{uid}/settings")
def settings_(uid: int, body: SettingsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid, write=True)
    v = (body.upi_id or "").strip()
    if v and not re.fullmatch(r"[\w.\-]{2,}@[a-zA-Z]{2,}", v):
        raise HTTPException(422, "UPI ID looks like name@bank (e.g. 9876543210@ybl)")
    u.upi_id = v or None
    db.commit()
    return {"upi_id": u.upi_id}


# ================================================================ entries (Form 9.1)
class CustomerRef(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    mobile: str


class EntryIn(BaseModel):
    kind: Literal["sale", "expense"]
    on: dt.date
    amount: float = Field(gt=0, le=10_000_000)
    category: str = Field(min_length=2, max_length=30)
    stock_item_id: Optional[int] = None
    qty: Optional[float] = Field(default=None, gt=0, le=1_000_000)
    payment_mode: Literal["cash", "upi", "credit"] = "cash"
    customer: Optional[CustomerRef] = None
    due_date: Optional[dt.date] = None
    note: Optional[str] = Field(default=None, max_length=300)
    source: Literal["manual", "voice"] = "manual"


@router.get("/units/{uid}/entries")
def list_entries(uid: int, start: Optional[date] = None, end: Optional[date] = None, kind: Optional[str] = None, lang: Optional[str] = None,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid)
    end = end or date.today()
    start = start or end - timedelta(days=30)
    rows = entries_between(db, u.id, start, end)
    if kind:
        rows = [e for e in rows if e.kind == kind]
    lg = _lang(user, lang)
    cats, items = categories(u, lg), _items(db, u.id, lg)
    return [entry_out(e, cats, items) for e in rows[:500]]


@router.post("/units/{uid}/entries")
def add_entry(uid: int, body: EntryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid, write=True)
    if body.on > date.today():
        raise HTTPException(422, "The date cannot be in the future")
    if body.on < date.today() - timedelta(days=90):
        raise HTTPException(422, "Entries older than 90 days are added by staff")
    if body.category not in category_codes(u, body.kind):
        raise HTTPException(422, "Choose a category from the list")
    if body.kind == "expense" and body.payment_mode == "credit":
        raise HTTPException(422, "Expenses are paid in cash or UPI")
    cust = None
    if body.payment_mode == "credit":
        if not body.customer:
            raise HTTPException(422, "A credit sale needs the customer's name and mobile")
        cust = upsert_customer(db, body.customer.mobile, body.customer.name, district=u.district)
    elif body.customer:
        cust = upsert_customer(db, body.customer.mobile, body.customer.name, district=u.district)
    item = None
    if body.stock_item_id:
        item = db.get(StockItem, body.stock_item_id)
        if not item or item.unit_id != u.id:
            raise HTTPException(422, "Unknown stock item")
        if not body.qty:
            raise HTTPException(422, "Enter the quantity for the stock item")
    e = LedgerEntry(unit_id=u.id, kind=body.kind, on=body.on, amount=round(body.amount, 2), category=body.category, stock_item_id=item.id if item else None,
                    qty=body.qty, payment_mode=body.payment_mode, customer_id=cust.id if cust else None,
                    due_date=(body.due_date or date.today() + timedelta(days=7)) if body.payment_mode == "credit" else None,
                    note=body.note, source=body.source if user.role == "msme" else "staff", created_by_id=user.id, created_at=now())
    db.add(e)
    db.flush()
    if item:
        if body.kind == "expense":
            move_stock(db, item, "in", body.qty, body.on, "Bought", e.id)
            item.cost = round(body.amount / body.qty, 2)
        else:
            move_stock(db, item, "out", body.qty, body.on, "Sold", e.id)
    db.commit()
    db.refresh(e)
    return entry_out(e, categories(u, _lang(user, None)), _items(db, u.id, _lang(user, None)))


def _entry(db: Session, user: User, eid: int, write: bool = True) -> tuple[LedgerEntry, Unit]:
    e = db.get(LedgerEntry, eid)
    if not e:
        raise HTTPException(404, "Not found")
    return e, unit_access(db, user, e.unit_id, write=write)


@router.delete("/entries/{eid}")
def delete_entry(eid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e, u = _entry(db, user, eid)
    if e.order_id:
        raise HTTPException(409, "This sale comes from an order – cancel the order instead")
    if user.role == "msme" and e.created_at and e.created_at < now() - timedelta(days=2):
        raise HTTPException(409, "Entries older than 2 days can be removed by staff only")
    if e.stock_item_id and e.qty:  # undo the stock movement
        item = db.get(StockItem, e.stock_item_id)
        if item:
            item.qty += -e.qty if e.kind == "expense" else e.qty
    audit(db, user, "ledger_delete", "unit", u.id, {"entry": e.id, "amount": e.amount, "kind": e.kind})
    db.delete(e)
    db.commit()
    return {"ok": True}


@router.post("/entries/{eid}/photo")
async def entry_photo(eid: int, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    e, _ = _entry(db, user, eid)
    e.photo = save_photo(await file.read(10 * 1024 * 1024 + 1))
    db.commit()
    return {"ok": True}


class ParseIn(BaseModel):
    text: str = Field(min_length=2, max_length=500)


@router.post("/units/{uid}/parse")
def parse(uid: int, body: ParseIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """A spoken or typed sentence → a draft entry to check. Rules first; the AI helps when it is switched on."""
    u = unit_access(db, user, uid, write=True)
    items = list(db.scalars(select(StockItem).where(StockItem.unit_id == u.id, StockItem.active.is_(True))))
    draft = parse_spoken(body.text, u, items)
    if llm.enabled() and (not draft["amount"] or not draft["kind"]):
        cats = categories(u, "en")
        got = llm.complete_json("Extract one bookkeeping entry from a small business owner's sentence (Telugu or English). "
                                "Return JSON: kind (sale|expense), amount (number), qty (number or null), category (one of the codes given), "
                                "payment_mode (cash|upi|credit). Use only what is said.",
                                f"Sentence: {body.text}\nSale codes: {[c['code'] for c in cats['sale']]}\nExpense codes: {[c['code'] for c in cats['expense']]}", 200)
        if got:
            for k in ("kind", "amount", "qty", "category", "payment_mode"):
                if got.get(k) and not draft.get(k):
                    draft[k] = got[k]
    if draft["category"] and draft["kind"] and draft["category"] not in category_codes(u, draft["kind"]):
        draft["category"] = None
    return draft


# ================================================================ summaries
@router.get("/units/{uid}/summary")
def summary(uid: int, period: Literal["day", "week", "month"] = "day", on: Optional[date] = None, lang: Optional[str] = None,
            user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid)
    auto_close(db, u)
    db.commit()
    day = on or date.today()
    start, end = period_bounds(period, day)
    s = summarise(entries_between(db, u.id, start, end))
    prev_start, prev_end = period_bounds(period, start - timedelta(days=1))
    if end > date.today():  # a running week / month is compared with the same number of days before it
        prev_end = min(prev_end, prev_start + (date.today() - start))
    p = summarise(entries_between(db, u.id, prev_start, prev_end))
    lg = _lang(user, lang)
    cats = {f"{k}:{c['code']}": c["label"] for k, v in categories(u, lg).items() for c in v}
    daily = []
    if period in ("week", "month"):
        rows = entries_between(db, u.id, start, end)
        d = start
        while d <= min(end, date.today()):
            day_rows = [e for e in rows if e.on == d]
            ss = summarise(day_rows)
            daily.append({"date": d.isoformat(), "sales": ss["sales"], "expenses": ss["expenses"]})
            d += timedelta(days=1)
    rec = receivables(db, u.id)
    low = [stock_out(i, lg) for i in db.scalars(select(StockItem).where(StockItem.unit_id == u.id, StockItem.active.is_(True)))
           if is_low(i)]
    return {"period": period, "start": start.isoformat(), "end": end.isoformat(), **s, "previous": {k: p[k] for k in ("sales", "expenses", "profit", "entries")},
            "by_category": [{"key": k, "label": cats.get(k, k.split(":")[1]), "kind": k.split(":")[0], "amount": v} for k, v in s["by_category"].items()],
            "daily": daily, "to_collect": round(sum(e.amount for e in rec), 2), "overdue": sum(1 for e in rec if e.due_date and e.due_date < date.today()),
            "low_stock": low, "emi": _emi(db, u), "recorded_today": bool(entries_between(db, u.id, date.today(), date.today()))}


# ================================================================ receivables and receipts
@router.get("/units/{uid}/receivables")
def list_receivables(uid: int, lang: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid)
    lg = _lang(user, lang)
    cats, items = categories(u, lg), _items(db, u.id, lg)
    out = []
    for e in receivables(db, u.id):
        d = entry_out(e, cats, items)
        if e.customer:
            msg = (f"నమస్తే {e.customer.name} గారు, {u.name} నుండి. {e.on:%d-%m} నాటి ₹{e.amount:,.0f} బాకీ ఉంది. దయచేసి చెల్లించండి."
                   + (f" UPI: {u.upi_id}" if u.upi_id else "") if lg == "te" else
                   f"Hello {e.customer.name}, this is {u.name}. ₹{e.amount:,.0f} from {e.on:%d %b} is still due. Please pay when you can."
                   + (f" UPI: {u.upi_id}" if u.upi_id else ""))
            d["reminder_link"] = wa_link(e.customer.mobile, msg + f"\n{_receipt_url(e)}")
        out.append(d)
    return out


class CollectIn(BaseModel):
    mode: Literal["cash", "upi"]
    on: Optional[dt.date] = None


@router.post("/entries/{eid}/collect")
def collect(eid: int, body: CollectIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e, u = _entry(db, user, eid)
    if e.kind != "sale" or e.payment_mode != "credit" or e.collected_on:
        raise HTTPException(409, "Nothing to collect on this entry")
    on = body.on or date.today()
    if on > date.today() or on < e.on:
        raise HTTPException(422, "The date must be between the sale and today")
    e.collected_on, e.collected_mode = on, body.mode
    if e.order_id:  # the order is paid too
        from ..models_p5 import Order

        o = db.get(Order, e.order_id)
        if o and o.status == "delivered":
            o.status, o.payment_mode, o.paid_on = "paid", body.mode, on
            o.events = list(o.events or []) + [{"status": "paid", "at": now().isoformat(), "by": user.name or user.mobile}]
    db.commit()
    return {"ok": True}


def _receipt_url(e: LedgerEntry) -> str:
    token = jwt.encode({"purpose": "receipt", "e": e.id, "exp": dt.datetime.now(dt.UTC) + timedelta(days=60)}, settings.JWT_SECRET, algorithm=ALGO)
    return f"{settings.PUBLIC_URL.rstrip('/')}/api/v1/public/receipts/{e.id}.pdf?t={token}"


@router.post("/entries/{eid}/receipt")
def receipt_link(eid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e, u = _entry(db, user, eid, write=False)
    if e.kind != "sale":
        raise HTTPException(422, "Receipts are for sales")
    url = _receipt_url(e)
    mob = e.customer.mobile if e.customer else None
    text = f"{u.name} – receipt ₹{e.amount:,.0f}: {url}"
    return {"url": url.replace(settings.PUBLIC_URL.rstrip("/"), ""), "share_link": wa_link(mob, text) if mob else f"https://wa.me/?text={quote(text)}"}


@public.get("/receipts/{eid}.pdf")
def receipt_pdf(eid: int, t: str = Query(min_length=10), db: Session = Depends(get_db)):
    try:
        claims = jwt.decode(t, settings.JWT_SECRET, algorithms=[ALGO])
    except JWTError as exc:
        raise HTTPException(403, "Link expired") from exc
    if claims.get("purpose") != "receipt" or claims.get("e") != eid:
        raise HTTPException(403, "Link not valid")
    e = db.get(LedgerEntry, eid)
    if not e:
        raise HTTPException(404, "Not found")
    u = db.get(Unit, e.unit_id)
    m = Masters(db)
    lines = None
    if e.order_id:
        from ..models_p5 import Order

        o = db.get(Order, e.order_id)
        lines = [{"name": ln["name"], "qty": ln["qty"], "price": ln["price"]} for ln in o.lines] if o else None
    if not lines:
        cat = next((c["label"] for c in categories(u)["sale"] if c["code"] == e.category), e.category)
        lines = [{"name": e.note or cat, "qty": e.qty or 1, "price": round(e.amount / (e.qty or 1), 2)}]
    paid = e.payment_mode != "credit" or bool(e.collected_on)
    mobile = u.entrepreneur.mobile if u.entrepreneur else None
    pdf = receipt.render({"number": f"R-{u.code}-{e.id}", "date": e.on.strftime("%d %b %Y"),
                          "unit": {"name": u.name, "place": ", ".join(x for x in (m.name("village", u.village), m.name("district", u.district)) if x),
                                   "mobile": mobile, "upi_id": u.upi_id},
                          "customer": {"name": e.customer.name, "mobile": e.customer.mobile} if e.customer else None, "lines": lines, "amount": e.amount,
                          "payment_mode": e.collected_mode or e.payment_mode, "status": "Paid" if paid else "To pay",
                          "due_date": e.due_date.strftime("%d %b %Y") if e.due_date else None})
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="receipt-{e.id}.pdf"'})


# ================================================================ stock
class StockIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    name_te: Optional[str] = Field(default=None, max_length=80)
    measure: str = Field(min_length=1, max_length=12)
    reorder_level: float = Field(default=0, ge=0)
    active: bool = True


@router.get("/units/{uid}/stock")
def list_stock(uid: int, lang: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid)
    ensure_stock(db, u)
    db.commit()
    return [stock_out(i, _lang(user, lang)) for i in db.scalars(select(StockItem).where(StockItem.unit_id == u.id).order_by(StockItem.active.desc(), StockItem.name))]


@router.post("/units/{uid}/stock")
def add_stock_item(uid: int, body: StockIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid, write=True)
    if db.scalar(select(StockItem.id).where(StockItem.unit_id == u.id, StockItem.name == body.name.strip())):
        raise HTTPException(409, "This item is already in the stock list")
    db.add(StockItem(unit_id=u.id, **{**body.model_dump(), "name": body.name.strip()}, qty=0))
    db.commit()
    return list_stock(uid, None, user, db)


@router.put("/stock/{sid}")
def edit_stock_item(sid: int, body: StockIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    it = db.get(StockItem, sid)
    if not it:
        raise HTTPException(404, "Not found")
    unit_access(db, user, it.unit_id, write=True)
    for k, v in body.model_dump().items():
        setattr(it, k, v)
    db.commit()
    return list_stock(it.unit_id, None, user, db)


class MoveIn(BaseModel):
    kind: Literal["in", "out", "count"]
    qty: float = Field(ge=0, le=1_000_000)
    note: Optional[str] = Field(default=None, max_length=160)


@router.post("/stock/{sid}/move")
def stock_move(sid: int, body: MoveIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Stock used today (out), received without a bill (in), or counted (the real quantity)."""
    it = db.get(StockItem, sid)
    if not it:
        raise HTTPException(404, "Not found")
    unit_access(db, user, it.unit_id, write=True)
    move_stock(db, it, body.kind, body.qty, date.today(), body.note)
    db.commit()
    return list_stock(it.unit_id, None, user, db)


# ================================================================ EMI tracker
def _emi(db: Session, u: Unit) -> dict | None:
    from ..dpr.service import repayment_state

    loans = loans_of(db, u)
    if not loans:
        return None
    reps = [r for a in loans for r in a.repayments]
    nxt = next((r for r in reps if not r.paid_on), None)
    return {"status": emi_status(db, u), "emi": loans[0].emi_amount, "bank": loans[0].bank, "paid": sum(1 for r in reps if r.paid_on), "total": len(reps),
            "balance": round(sum(r.principal for r in reps if not r.paid_on), 2),
            "next": {"id": nxt.id, "n": nxt.n, "due_date": nxt.due_date.isoformat(), "amount": nxt.amount, "state": repayment_state(nxt)} if nxt else None,
            "overdue": [{"id": r.id, "n": r.n, "due_date": r.due_date.isoformat(), "amount": r.amount} for r in reps if repayment_state(r) == "overdue"]}


@router.get("/units/{uid}/emi")
def emi(uid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..dpr.service import repayment_state

    u = unit_access(db, user, uid)
    out = _emi(db, u) or {}
    out["schedule"] = [{"id": r.id, "n": r.n, "due_date": r.due_date.isoformat(), "amount": r.amount, "paid_on": r.paid_on.isoformat() if r.paid_on else None,
                        "state": repayment_state(r)} for a in loans_of(db, u) for r in a.repayments]
    return out


class EmiPaidIn(BaseModel):
    on: dt.date
    amount: Optional[float] = Field(default=None, gt=0)
    mode: Literal["cash", "upi"] = "upi"


@router.post("/units/{uid}/emi/{rid}/paid")
def emi_paid(uid: int, rid: int, body: EmiPaidIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The entrepreneur records an EMI they paid: it is marked in the loan schedule (staff can check with the bank) and
    written in the books as a loan EMI (not counted as a business expense)."""
    from ..models_p3 import Repayment

    u = unit_access(db, user, uid, write=True)
    r = db.get(Repayment, rid)
    if not r or r.application.dpr_id != u.dpr_id:
        raise HTTPException(404, "Not found")
    if r.paid_on:
        raise HTTPException(409, "Already marked paid")
    if body.on > date.today():
        raise HTTPException(422, "The date cannot be in the future")
    amount = body.amount or r.amount
    r.paid_on, r.paid_amount, r.note = body.on, amount, "Reported in the app" if user.role == "msme" else r.note
    db.add(LedgerEntry(unit_id=u.id, kind="expense", on=body.on, amount=amount, category="loan_emi", payment_mode=body.mode, repayment_id=r.id,
                       note=f"EMI {r.n}", source="manual" if user.role == "msme" else "staff", created_by_id=user.id, created_at=now()))
    db.commit()
    return _emi(db, u)


# ================================================================ monthly summaries
@router.get("/units/{uid}/months")
def months(uid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid)
    auto_close(db, u)
    db.commit()
    return [summary_out(m) for m in db.scalars(select(MonthlySummary).where(MonthlySummary.unit_id == u.id).order_by(MonthlySummary.month.desc()))]


class SubmitIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=1000)


@router.post("/units/{uid}/months/{key}/submit")
def submit_month(uid: int, key: str, body: SubmitIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid, write=True)
    if not re.fullmatch(r"\d{4}-\d{2}", key):
        raise HTTPException(422, "Month must look like 2026-10")
    start, end = month_range(key)
    today = date.today()
    if start > today or (end > today and today.day < 25):
        raise HTTPException(422, "A month can be sent from the 25th onwards, or after it ends")
    ms = freeze_month(db, u, key, by="owner" if user.role == "msme" else "staff", note=body.note)
    db.commit()
    return summary_out(ms)


class ReviewIn(BaseModel):
    note: str = Field(min_length=2, max_length=2000)


@router.post("/months/{mid}/review")
def review_month(mid: int, body: ReviewIn, user: User = Depends(staff_read), db: Session = Depends(get_db)):
    ms = db.get(MonthlySummary, mid)
    if not ms or not can_see_unit(user, ms.unit):
        raise HTTPException(404, "Not found")
    ms.reviewed_by_id, ms.reviewed_at, ms.review_note = user.id, now(), body.note.strip()
    db.commit()
    return summary_out(ms)


# ================================================================ staff reports
@router.get("/reports/months")
def report_months(month: Optional[str] = None, user: User = Depends(staff_read), db: Session = Depends(get_db)):
    """One line per launched unit for a month, with alerts – the mentor's and programme's view of business tracking."""
    m = Masters(db)
    units = [u for u in db.scalars(select(Unit).where(Unit.status.in_(("launched", "paused")))) if can_see_unit(user, u)]
    last = (date.today().replace(day=1) - timedelta(days=1))
    key = month or month_key(last)
    if not re.fullmatch(r"\d{4}-\d{2}", key):
        raise HTTPException(422, "Month must look like 2026-10")
    current = key == month_key(date.today())
    rows = []
    for u in units:
        auto_close(db, u)
        ms = db.scalar(select(MonthlySummary).where(MonthlySummary.unit_id == u.id, MonthlySummary.month == key))
        if current or not ms:  # the month is still running (or before launch): live figures, not frozen
            start, end = month_range(key)
            if u.launch_date and u.launch_date > end:
                continue
            s = summarise(entries_between(db, u.id, start, end))
            data = {"sales": s["sales"], "expenses": s["expenses"], "profit": s["profit"], "entries": s["entries"], "days_recorded": s["days_recorded"],
                    "emi_status": emi_status(db, u), "alerts": [], "submitted_by": None, "reviewed": False, "id": None, "note": None, "review_note": None}
        else:
            data = summary_out(ms)
        rows.append({"unit": {"id": u.id, "code": u.code, "name": u.name, "owner": u.entrepreneur.full_name if u.entrepreneur else (u.group.name if u.group else "—"),
                              "district_name": m.name("district", u.district), "model": u.model.name_en if u.model else None}, **data})
    db.commit()
    flagged = [r for r in rows if r["alerts"]]
    return {"month": key, "live": current, "units": len(rows),
            "totals": {k: round(sum(r[k] for r in rows), 2) for k in ("sales", "expenses", "profit")},
            "recording": sum(1 for r in rows if r["entries"]), "flagged": len(flagged),
            "rows": sorted(rows, key=lambda r: (-len(r["alerts"]), -r["sales"]))}
