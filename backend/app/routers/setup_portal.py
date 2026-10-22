"""Limited portals for M7:
- Supplier (role "supplier"): see requests for quotation sent to them, submit quotations, confirm orders, mark delivery.
- Entrepreneur (role "msme"): follow their unit's set-up – purchases, registrations, readiness, assets – and upload documents."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..models_p1 import Entrepreneur, GroupMember
from ..models_p4 import PURCHASE_STATUS, Purchase, Quotation, Registration, Supplier, Unit
from ..programme.service import Masters
from ..security import require_roles
from ..training.service import audit
from ..setup.service import file_link, now, save_file, unit_out
from .setup import LineIn, QuoteIn, mark_delivered, save_quote

supplier_router = APIRouter(prefix="/api/v1/supplier", tags=["supplier"])
me_router = APIRouter(prefix="/api/v1/setup/me", tags=["setup-me"])
supplier_only = require_roles("supplier")
msme = require_roles("msme")


# ================================================================ supplier portal
def _supplier(db: Session, user: User) -> Supplier:
    s = db.scalar(select(Supplier).where(Supplier.user_id == user.id))
    if not s or not s.approved:
        raise HTTPException(403, "Your supplier account is not active. Contact MIRAI.")
    return s


def _rfq_out(db: Session, p: Purchase, s: Supplier, m: Masters) -> dict:
    mine = next((q for q in p.quotes if q.supplier_id == s.id), None)
    won = p.selected_quote_id is not None and mine is not None and p.selected_quote_id == mine.id
    u = p.unit
    out = {"id": p.id, "title": p.title, "unit": u.name, "unit_code": u.code, "district": m.name("district", u.district),
           "items": [{k: i.get(k) for k in ("item", "spec", "qty")} for i in p.items], "quote_by": p.quote_by.isoformat() if p.quote_by else None,
           "status": p.status if won or p.status in ("rfq", "draft") else "closed",
           "status_label": PURCHASE_STATUS.get(p.status, p.status) if won or p.status in ("rfq", "draft") else "Closed – another quotation chosen",
           "my_quote": {"amount": mine.amount, "lines": mine.lines, "delivery_days": mine.delivery_days, "warranty_months": mine.warranty_months,
                        "valid_till": mine.valid_till.isoformat() if mine.valid_till else None, "note": mine.note, "file_url": file_link(mine.file)} if mine else None,
           "won": won}
    if won:  # the delivery address only for the supplier who got the order
        o = unit_out(db, u, m)
        out |= {"po_number": p.po_number, "po_date": p.po_date.isoformat() if p.po_date else None, "po_amount": p.po_amount,
                "expected_delivery": p.expected_delivery.isoformat() if p.expected_delivery else None, "confirmed": bool(p.supplier_confirmed_at),
                "deliver_to": o["location"], "contact": f"{o['owner']['name']}" + (f" · {o['owner'].get('mobile')}" if o["owner"].get("mobile") else ""),
                "delivered_on": p.delivered_on.isoformat() if p.delivered_on else None, "installed_on": p.installed_on.isoformat() if p.installed_on else None}
    return out


def _mine(db: Session, s: Supplier) -> list[Purchase]:
    rows = [p for p in db.scalars(select(Purchase).where(Purchase.status != "cancelled").order_by(Purchase.id.desc())) if s.id in (p.invited or [])]
    return rows


@supplier_router.get("/me")
def supplier_me(user: User = Depends(supplier_only), db: Session = Depends(get_db)):
    s = _supplier(db, user)
    m = Masters(db)
    rows = [_rfq_out(db, p, s, m) for p in _mine(db, s)]
    return {"supplier": {"id": s.id, "name": s.name, "items": s.items, "districts": [m.name("district", d) for d in s.districts or []]},
            "open": [r for r in rows if r["status"] == "rfq"], "orders": [r for r in rows if r["won"]],
            "closed": [r for r in rows if r["status"] == "closed"]}


class SupplierQuoteIn(BaseModel):
    lines: list[LineIn]
    gst_included: bool = True
    delivery_days: Optional[int] = None
    warranty_months: Optional[int] = None
    valid_till: Optional[date] = None
    note: Optional[str] = None


@supplier_router.post("/rfqs/{pid}/quote")
def supplier_quote(pid: int, body: SupplierQuoteIn, user: User = Depends(supplier_only), db: Session = Depends(get_db)):
    s = _supplier(db, user)
    p = db.get(Purchase, pid)
    if not p or s.id not in (p.invited or []):
        raise HTTPException(404, "Not found")
    if p.quote_by and p.quote_by < date.today():
        raise HTTPException(409, "The last date for quotations has passed")
    wanted = {i["item"] for i in p.items}
    q_in = QuoteIn(supplier_id=s.id, **body.model_dump())
    if any(ln.item not in wanted for ln in q_in.lines):
        raise HTTPException(422, "Quote only for the items asked")
    save_quote(db, p, s, q_in, "supplier")
    audit(db, user, "quote_submit", "purchase", p.id, {"supplier": s.id})
    db.commit()
    return supplier_me(user, db)


@supplier_router.post("/rfqs/{pid}/quote/file")
async def supplier_quote_file(pid: int, file: UploadFile = File(...), user: User = Depends(supplier_only), db: Session = Depends(get_db)):
    s = _supplier(db, user)
    q = db.scalar(select(Quotation).where(Quotation.purchase_id == pid, Quotation.supplier_id == s.id))
    if not q:
        raise HTTPException(404, "Submit the quotation first")
    if q.purchase.status not in ("draft", "rfq"):
        raise HTTPException(409, "Quotations are closed")
    q.file = save_file(await file.read(10 * 1024 * 1024 + 1), file.content_type or "")
    db.commit()
    return supplier_me(user, db)


def _won(db: Session, s: Supplier, pid: int) -> Purchase:
    p = db.get(Purchase, pid)
    q = db.get(Quotation, p.selected_quote_id) if p and p.selected_quote_id else None
    if not p or not q or q.supplier_id != s.id:
        raise HTTPException(404, "Not found")
    return p


class ConfirmIn(BaseModel):
    expected_delivery: date


@supplier_router.post("/orders/{pid}/confirm")
def confirm_order(pid: int, body: ConfirmIn, user: User = Depends(supplier_only), db: Session = Depends(get_db)):
    s = _supplier(db, user)
    p = _won(db, s, pid)
    if p.status != "ordered":
        raise HTTPException(409, "This order is not open")
    if body.expected_delivery < date.today():
        raise HTTPException(422, "The delivery date is in the past")
    p.supplier_confirmed_at, p.expected_delivery, p.updated_at = now(), body.expected_delivery, now()
    audit(db, user, "po_confirm", "purchase", p.id)
    db.commit()
    return supplier_me(user, db)


class DeliverIn(BaseModel):
    on: date
    note: Optional[str] = None


@supplier_router.post("/orders/{pid}/delivered")
def supplier_delivered(pid: int, body: DeliverIn, user: User = Depends(supplier_only), db: Session = Depends(get_db)):
    s = _supplier(db, user)
    p = _won(db, s, pid)
    mark_delivered(p, body.on, f"reported by supplier. {body.note or ''}".strip())
    audit(db, user, "po_delivered_supplier", "purchase", p.id)
    db.commit()
    return supplier_me(user, db)


@supplier_router.post("/orders/{pid}/po-link")
def supplier_po(pid: int, user: User = Depends(supplier_only), db: Session = Depends(get_db)):
    from ..setup.service import po_link

    s = _supplier(db, user)
    _won(db, s, pid)
    return {"url": po_link(pid)}


# ================================================================ entrepreneur view
def _my_units(db: Session, user: User) -> list[Unit]:
    e = db.scalar(select(Entrepreneur).where(Entrepreneur.user_id == user.id))
    if not e:
        return []
    gids = [gm.group_id for gm in db.scalars(select(GroupMember).where(GroupMember.entrepreneur_id == e.id))]
    q = select(Unit).where((Unit.entrepreneur_id == e.id) | (Unit.group_id.in_(gids or [0]))).order_by(Unit.id.desc())
    return list(db.scalars(q))


@me_router.get("")
def my_units(lang: Optional[str] = None, user: User = Depends(msme), db: Session = Depends(get_db)):
    lang = lang if lang in ("en", "te") else (user.language or "en")
    m = Masters(db)
    out = []
    for u in _my_units(db, user):
        d = unit_out(db, u, m, full=True, lang=lang)
        for p in d["purchase_list"]:
            p.pop("selection_reason", None)
        out.append(d)
    return {"units": out}


@me_router.post("/registrations/{rid}/file")
async def my_registration_file(rid: int, file: UploadFile = File(...), number: Optional[str] = Form(default=None, max_length=60),
                               user: User = Depends(msme), db: Session = Depends(get_db)):
    r = db.get(Registration, rid)
    if not r or r.unit_id not in {u.id for u in _my_units(db, user)}:
        raise HTTPException(404, "Not found")
    r.file = save_file(await file.read(10 * 1024 * 1024 + 1), file.content_type or "")
    if number:
        r.number = number.strip()
    if r.status == "todo":
        r.status = "applied"
    r.note = "Document uploaded by the entrepreneur – staff to check"
    audit(db, user, "registration_upload_self", "unit", r.unit_id, {"kind": r.kind})
    db.commit()
    return my_units(None, user, db)
