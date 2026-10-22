"""M7 – enterprise establishment & procurement for staff: units (from approved DPRs), suppliers (Form 7.1), purchases with
quotations and purchase orders (Form 7.2), delivery / installation with photos, asset register, registrations, readiness
checklist (Form 7.3) and launch, reports."""
import re
from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import User
from ..models_p3 import Dpr, EnterpriseModel, LoanApplication
from ..models_p4 import PAYMENT_SOURCES, PURCHASE_STATUS, REGISTRATIONS, Asset, Purchase, Quotation, Registration, Supplier, Unit
from ..programme.service import Masters
from ..roles import LAUNCH, PROCURE, SETUP_READ, SETUP_WRITE
from ..security import ALGO, hash_secret, require_roles
from ..training.service import audit, bump_stage
from ..setup import po
from ..setup.service import (can_see_unit, checklist, ensure_unit, file_path, get_purchase, get_unit, now, po_link, purchase_out,
                             rate_for, save_file, supplier_matches, supplier_out, supplier_stats, unit_out)

router = APIRouter(prefix="/api/v1/setup", tags=["setup"])
reader = require_roles(*SETUP_READ)
writer = require_roles(*SETUP_WRITE)
buyer = require_roles(*PROCURE)
launcher = require_roles(*LAUNCH)


# ================================================================ meta
@router.get("/meta")
def meta(user: User = Depends(reader)):
    return {"registrations": [{"code": k, "label": v[0]} for k, v in REGISTRATIONS.items()],
            "purchase_status": [{"code": k, "label": v} for k, v in PURCHASE_STATUS.items()],
            "payment_sources": [{"code": k, "label": v} for k, v in PAYMENT_SOURCES.items()],
            "can": {"write": user.role in SETUP_WRITE, "procure": user.role in PROCURE, "launch": user.role in LAUNCH}}


# ================================================================ suppliers (Form 7.1)
class RateIn(BaseModel):
    item: str = Field(min_length=2, max_length=160)
    rate: float = Field(gt=0, le=100_000_000)
    unit: str = Field(default="each", max_length=20)
    valid_till: Optional[date] = None


class SupplierIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    gstin: Optional[str] = Field(default=None, max_length=15)
    contact_name: str = Field(min_length=2, max_length=120)
    mobile: str
    email: Optional[str] = Field(default=None, max_length=190)
    address: str = Field(min_length=3, max_length=255)
    categories: list[str] = Field(default_factory=list, max_length=30)
    items: list[str] = Field(min_length=1, max_length=200)
    models: list[str] = []
    rate_card: list[RateIn] = []
    districts: list[str] = []
    approved: bool = False
    note: Optional[str] = Field(default=None, max_length=255)

    @field_validator("mobile")
    @classmethod
    def v_mobile(cls, v):
        v = re.sub(r"\D", "", v or "")[-10:]
        if not re.fullmatch(r"[6-9]\d{9}", v):
            raise ValueError("Enter a 10-digit mobile number")
        return v

    @field_validator("gstin")
    @classmethod
    def v_gstin(cls, v):
        if not v:
            return None
        v = v.strip().upper()
        if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]", v):
            raise ValueError("GSTIN must be 15 characters, like 37ABCDE1234F1Z5")
        return v

    @field_validator("items", "categories")
    @classmethod
    def v_list(cls, v):
        return list(dict.fromkeys(x.strip() for x in v if x and x.strip()))


def _check_supplier(db: Session, body: SupplierIn):
    m = Masters(db)
    bad = [d for d in body.districts if not m.has("district", d)]
    known = set(db.scalars(select(EnterpriseModel.code)))
    bad += [x for x in body.models if x not in known]
    if bad:
        raise HTTPException(422, f"Unknown district or model: {', '.join(bad)}")


@router.get("/suppliers")
def list_suppliers(q: Optional[str] = None, approved: Optional[bool] = None, _: User = Depends(reader), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Supplier).order_by(Supplier.approved.desc(), Supplier.name)))
    if approved is not None:
        rows = [s for s in rows if s.approved == approved]
    if q:
        ql = q.lower()
        rows = [s for s in rows if ql in s.name.lower() or any(ql in i.lower() for i in s.items or []) or ql in (s.gstin or "").lower()]
    stats = supplier_stats(db)
    return [supplier_out(s, stats=stats) for s in rows]


@router.post("/suppliers")
def create_supplier(body: SupplierIn, user: User = Depends(buyer), db: Session = Depends(get_db)):
    _check_supplier(db, body)
    if body.gstin and db.scalar(select(Supplier).where(Supplier.gstin == body.gstin)):
        raise HTTPException(409, "A supplier with this GSTIN exists")
    s = Supplier(**body.model_dump(exclude={"rate_card"}), rate_card=[r.model_dump(mode="json") for r in body.rate_card])
    db.add(s)
    db.flush()
    audit(db, user, "supplier_create", "supplier", s.id, {"name": s.name})
    db.commit()
    return supplier_out(s, db, full=True)


@router.put("/suppliers/{sid}")
def update_supplier(sid: int, body: SupplierIn, user: User = Depends(buyer), db: Session = Depends(get_db)):
    s = db.get(Supplier, sid)
    if not s:
        raise HTTPException(404, "Supplier not found")
    _check_supplier(db, body)
    if body.gstin and db.scalar(select(Supplier).where(Supplier.gstin == body.gstin, Supplier.id != sid)):
        raise HTTPException(409, "A supplier with this GSTIN exists")
    was = s.approved
    for k, v in body.model_dump(exclude={"rate_card"}).items():
        setattr(s, k, v)
    s.rate_card = [r.model_dump(mode="json") for r in body.rate_card]
    audit(db, user, "supplier_update", "supplier", s.id, {"approved": s.approved} if was != s.approved else None)
    db.commit()
    return supplier_out(s, db, full=True)


class LoginIn(BaseModel):
    email: str = Field(min_length=5, max_length=190, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=72)


@router.post("/suppliers/{sid}/login")
def supplier_login(sid: int, body: LoginIn, user: User = Depends(buyer), db: Session = Depends(get_db)):
    """Create or reset the supplier's limited portal login (submit quotations, confirm orders and deliveries)."""
    s = db.get(Supplier, sid)
    if not s:
        raise HTTPException(404, "Supplier not found")
    if not s.approved:
        raise HTTPException(409, "Approve the supplier first")
    email = body.email.strip().lower()
    login = db.get(User, s.user_id) if s.user_id else None
    clash = db.scalar(select(User).where(User.email == email))
    if clash and (not login or clash.id != login.id):
        raise HTTPException(409, "This email is already used by another login")
    if not login:
        login = User(email=email, name=s.name, role="supplier")
        db.add(login)
        db.flush()
        s.user_id = login.id
    login.email, login.password_hash, login.is_active = email, hash_secret(body.password), True
    audit(db, user, "supplier_login_set", "supplier", s.id, {"email": email})
    db.commit()
    return supplier_out(s, db, full=True)


# ================================================================ units
def _visible(db: Session, user: User) -> list[Unit]:
    return [u for u in db.scalars(select(Unit).order_by(Unit.updated_at.desc(), Unit.id.desc())) if can_see_unit(user, u)]


@router.get("/units")
def list_units(status: Optional[str] = None, q: Optional[str] = None, entrepreneur_id: Optional[int] = None,
               user: User = Depends(reader), db: Session = Depends(get_db)):
    rows = _visible(db, user)
    counts = {s: sum(1 for u in rows if u.status == s) for s in ("setting_up", "launched", "paused", "closed")}
    if entrepreneur_id:
        rows = [u for u in rows if u.entrepreneur_id == entrepreneur_id]
    if status:
        rows = [u for u in rows if u.status == status]
    if q:
        ql = q.lower()
        rows = [u for u in rows if ql in u.name.lower() or ql in (u.code or "").lower()
                or (u.entrepreneur and ql in u.entrepreneur.full_name.lower()) or (u.group and ql in u.group.name.lower())]
    m = Masters(db)
    ready = [d for d in db.scalars(select(Dpr).where(Dpr.status == "approved")) if not db.scalar(select(Unit.id).where(Unit.dpr_id == d.id))]
    from ..dpr.service import can_see_dpr

    return {"counts": counts, "rows": [unit_out(db, u, m) for u in rows[:300]],
            "waiting": [{"dpr_id": d.id, "code": d.code, "unit_name": d.unit_name, "owner": (d.entrepreneur.full_name if d.entrepreneur else d.group.name if d.group else "—"),
                         "loan": (d.results or {}).get("loan", 0),
                         "sanctioned": bool(db.scalar(select(LoanApplication.id).where(LoanApplication.dpr_id == d.id,
                                                                                       LoanApplication.status.in_(("sanctioned", "disbursed")))))}
                        for d in ready if can_see_dpr(user, d)][:50]}


class UnitCreate(BaseModel):
    dpr_id: int


@router.post("/units")
def create_unit(body: UnitCreate, user: User = Depends(writer), db: Session = Depends(get_db)):
    from ..dpr.service import get_dpr

    d = get_dpr(db, user, body.dpr_id)
    if d.status != "approved":
        raise HTTPException(409, "The DPR must be approved first")
    u = ensure_unit(db, d, user)
    bump_stage(d.entrepreneur or d.group, 4)
    audit(db, user, "unit_create", "unit", u.id, {"code": u.code})
    db.commit()
    db.refresh(u)
    return unit_out(db, u, full=True)


@router.get("/units/{uid}")
def get_one(uid: int, lang: Optional[str] = None, user: User = Depends(reader), db: Session = Depends(get_db)):
    return unit_out(db, get_unit(db, user, uid), full=True, lang=lang if lang in ("en", "te") else "en")


class UnitEdit(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    address: Optional[str] = Field(default=None, max_length=255)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    status: Optional[Literal["setting_up", "launched", "paused", "closed"]] = None


@router.put("/units/{uid}")
def edit_unit(uid: int, body: UnitEdit, user: User = Depends(writer), db: Session = Depends(get_db)):
    u = get_unit(db, user, uid)
    u.name, u.address = body.name.strip(), body.address
    if body.lat is not None:
        u.lat, u.lng = body.lat, body.lng
    if body.status and body.status != u.status:
        allowed = {("launched", "paused"), ("paused", "launched"), ("setting_up", "closed"), ("launched", "closed"), ("paused", "closed")}
        if (u.status, body.status) not in allowed:
            raise HTTPException(422, "Use Launch after the readiness checklist is complete" if body.status == "launched"
                                else f"A unit cannot go from {u.status.replace('_', ' ')} to {body.status.replace('_', ' ')}")
        u.status = body.status
    u.updated_at = now()
    audit(db, user, "unit_update", "unit", u.id)
    db.commit()
    return unit_out(db, u, full=True)


# ================================================================ purchases (Form 7.2)
class ItemIn(BaseModel):
    item: str = Field(min_length=2, max_length=160)
    spec: Optional[str] = Field(default="", max_length=200)
    qty: float = Field(gt=0, le=10000)
    est_rate: float = Field(default=0, ge=0, le=100_000_000)


class PurchaseIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    items: list[ItemIn] = Field(min_length=1, max_length=60)
    invited: list[int] = []
    quote_by: Optional[date] = None


@router.get("/units/{uid}/suppliers")
def suggest_suppliers(uid: int, items: str = "", user: User = Depends(reader), db: Session = Depends(get_db)):
    """Approved suppliers serving the unit's district, with the purchase items each deals in and rate-card prices."""
    u = get_unit(db, user, uid)
    names = [x for x in items.split("|") if x.strip()] or [i["item"] for i in unit_out(db, u, full=True)["dpr_items"]]
    out = []
    for s in db.scalars(select(Supplier).where(Supplier.approved.is_(True)).order_by(Supplier.name)):
        hits = supplier_matches(s, names, u.district, u.model.code if u.model else None)
        if hits or (u.model and u.model.code in (s.models or []) and (not s.districts or u.district in s.districts)):
            out.append({"id": s.id, "name": s.name, "matches": hits, "covers": len(hits), "of": len(names),
                        "rates": {h: rate_for(s, h) for h in hits if rate_for(s, h)}, "has_login": bool(s.user_id), "mobile": s.mobile})
    return sorted(out, key=lambda x: -x["covers"])


def _check_invited(db: Session, ids: list[int]):
    ok = {s.id for s in db.scalars(select(Supplier).where(Supplier.id.in_(ids or [0]), Supplier.approved.is_(True)))}
    bad = [i for i in ids if i not in ok]
    if bad:
        raise HTTPException(422, "Only approved suppliers can be asked to quote")


@router.post("/units/{uid}/purchases")
def create_purchase(uid: int, body: PurchaseIn, user: User = Depends(buyer), db: Session = Depends(get_db)):
    u = get_unit(db, user, uid)
    if u.status in ("closed",):
        raise HTTPException(409, "This unit is closed")
    _check_invited(db, body.invited)
    p = Purchase(unit_id=u.id, title=body.title.strip(), items=[i.model_dump() for i in body.items], invited=list(dict.fromkeys(body.invited)),
                 quote_by=body.quote_by, status="rfq" if body.invited else "draft", created_by_id=user.id, photos=[], created_at=now(), updated_at=now())
    db.add(p)
    db.flush()
    u.updated_at = now()
    audit(db, user, "purchase_create", "purchase", p.id, {"unit": u.code, "invited": p.invited})
    db.commit()
    db.refresh(p)
    return purchase_out(db, p, full=True)


@router.get("/purchases/{pid}")
def purchase_detail(pid: int, user: User = Depends(reader), db: Session = Depends(get_db)):
    p = get_purchase(db, user, pid)
    out = purchase_out(db, p, full=True)
    out["unit"] = {"id": p.unit.id, "code": p.unit.code, "name": p.unit.name}
    return out


@router.put("/purchases/{pid}")
def edit_purchase(pid: int, body: PurchaseIn, user: User = Depends(buyer), db: Session = Depends(get_db)):
    p = get_purchase(db, user, pid)
    if p.status not in ("draft", "rfq"):
        raise HTTPException(409, "The order is placed; the items cannot be changed")
    _check_invited(db, body.invited)
    p.title, p.items, p.quote_by = body.title.strip(), [i.model_dump() for i in body.items], body.quote_by
    p.invited = list(dict.fromkeys(body.invited))
    if p.invited and p.status == "draft":
        p.status = "rfq"
    p.updated_at = now()
    db.commit()
    return purchase_detail(pid, user, db)


class LineIn(BaseModel):
    item: str = Field(min_length=1, max_length=160)
    qty: float = Field(gt=0, le=10000)
    rate: float = Field(ge=0, le=100_000_000)


class QuoteIn(BaseModel):
    supplier_id: int
    lines: list[LineIn] = Field(min_length=1, max_length=60)
    amount: Optional[float] = Field(default=None, gt=0, le=1_000_000_000)
    gst_included: bool = True
    delivery_days: Optional[int] = Field(default=None, ge=0, le=365)
    warranty_months: Optional[int] = Field(default=None, ge=0, le=120)
    valid_till: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=500)


def save_quote(db: Session, p: Purchase, s: Supplier, body: QuoteIn, source: str) -> Quotation:
    if p.status not in ("draft", "rfq"):
        raise HTTPException(409, "Quotations are closed – the order is placed")
    if body.valid_till and body.valid_till < date.today():
        raise HTTPException(422, "This quotation has already expired")
    q = db.scalar(select(Quotation).where(Quotation.purchase_id == p.id, Quotation.supplier_id == s.id))
    total = round(sum(ln.qty * ln.rate for ln in body.lines), 2)
    data = dict(lines=[ln.model_dump() for ln in body.lines], amount=body.amount or total, gst_included=body.gst_included,
                delivery_days=body.delivery_days, warranty_months=body.warranty_months, valid_till=body.valid_till, note=body.note, source=source)
    if q:
        for k, v in data.items():
            setattr(q, k, v)
        q.created_at = now()
    else:
        q = Quotation(purchase_id=p.id, supplier_id=s.id, created_at=now(), **data)
        db.add(q)
    if s.id not in (p.invited or []):
        p.invited = list(p.invited or []) + [s.id]
    p.status = "rfq"
    p.updated_at = now()
    db.flush()
    return q


@router.post("/purchases/{pid}/quotes")
def add_quote(pid: int, body: QuoteIn, user: User = Depends(buyer), db: Session = Depends(get_db)):
    p = get_purchase(db, user, pid)
    s = db.get(Supplier, body.supplier_id)
    if not s or not s.approved:
        raise HTTPException(422, "Choose an approved supplier")
    q = save_quote(db, p, s, body, "staff")
    audit(db, user, "quote_save", "purchase", p.id, {"supplier": s.id, "amount": q.amount})
    db.commit()
    return purchase_detail(pid, user, db)


@router.post("/quotes/{qid}/file")
async def quote_file(qid: int, file: UploadFile = File(...), user: User = Depends(buyer), db: Session = Depends(get_db)):
    q = db.get(Quotation, qid)
    if not q:
        raise HTTPException(404, "Quotation not found")
    p = get_purchase(db, user, q.purchase_id)
    q.file = save_file(await file.read(10 * 1024 * 1024 + 1), file.content_type or "")
    db.commit()
    return purchase_detail(p.id, user, db)


@router.delete("/quotes/{qid}")
def delete_quote(qid: int, user: User = Depends(buyer), db: Session = Depends(get_db)):
    q = db.get(Quotation, qid)
    if not q:
        raise HTTPException(404, "Quotation not found")
    p = get_purchase(db, user, q.purchase_id)
    if p.status not in ("draft", "rfq"):
        raise HTTPException(409, "The order is placed")
    db.delete(q)
    db.commit()
    db.refresh(p)
    return purchase_detail(p.id, user, db)


class OrderIn(BaseModel):
    quote_id: int
    reason: Optional[str] = Field(default=None, max_length=500)
    payment_source: Literal["loan", "own", "grant", "subsidy", "mixed"]
    expected_delivery: Optional[date] = None


@router.post("/purchases/{pid}/order")
def place_order(pid: int, body: OrderIn, user: User = Depends(buyer), db: Session = Depends(get_db)):
    """Select a quotation and issue the purchase order. Choosing other than the lowest, or with fewer than two quotations,
    needs a reason (kept on the record)."""
    p = get_purchase(db, user, pid)
    if p.status not in ("draft", "rfq"):
        raise HTTPException(409, "The order is already placed")
    q = next((x for x in p.quotes if x.id == body.quote_id), None)
    if not q:
        raise HTTPException(422, "Choose one of the quotations")
    if q.valid_till and q.valid_till < date.today():
        raise HTTPException(422, "This quotation has expired – ask the supplier to confirm the price")
    lowest = min(x.amount for x in p.quotes)
    reason = (body.reason or "").strip()
    if len(p.quotes) < 2 and len(reason) < 10:
        raise HTTPException(422, "Only one quotation: write why the order is placed without comparison")
    if q.amount > lowest + 0.5 and len(reason) < 10:
        raise HTTPException(422, "This is not the lowest quotation: write the reason for choosing it")
    if body.expected_delivery and body.expected_delivery < date.today():
        raise HTTPException(422, "The delivery date is in the past")
    p.selected_quote_id, p.selection_reason, p.payment_source = q.id, reason or "Lowest quotation", body.payment_source
    p.po_date, p.po_amount = date.today(), q.amount
    p.expected_delivery = body.expected_delivery or (date.today() + timedelta(days=q.delivery_days) if q.delivery_days else None)
    p.status = "ordered"
    db.flush()
    p.po_number = f"PO-{date.today().year}-{p.id:05d}"
    p.updated_at = now()
    audit(db, user, "purchase_order", "purchase", p.id, {"po": p.po_number, "supplier": q.supplier_id, "amount": q.amount})
    db.commit()
    return purchase_detail(pid, user, db)


@router.post("/purchases/{pid}/po-link")
def po_pdf_link(pid: int, user: User = Depends(reader), db: Session = Depends(get_db)):
    p = get_purchase(db, user, pid)
    if not p.po_number:
        raise HTTPException(409, "No purchase order yet")
    return {"url": po_link(p.id)}


def render_po(db: Session, p: Purchase) -> bytes:
    q = db.get(Quotation, p.selected_quote_id)
    s = q.supplier
    u = p.unit
    o = unit_out(db, u)
    spec = {i["item"]: i.get("spec") for i in p.items}
    issuer = db.get(User, p.created_by_id) if p.created_by_id else None
    return po.render({
        "po_number": p.po_number, "po_date": p.po_date.strftime("%d %b %Y"),
        "supplier": {"name": s.name, "gstin": s.gstin, "address": s.address, "contact": s.contact_name, "mobile": s.mobile},
        "unit": {"name": u.name, "code": u.code, "location": o["location"], "owner": o["owner"]["name"], "mobile": o["owner"].get("mobile")},
        "lines": [{**ln, "spec": spec.get(ln["item"], "")} for ln in q.lines], "amount": q.amount, "gst_included": q.gst_included,
        "expected_delivery": p.expected_delivery.strftime("%d %b %Y") if p.expected_delivery else None,
        "payment": PAYMENT_SOURCES.get(p.payment_source or "", ""), "warranty_months": q.warranty_months,
        "reference": f"{u.dpr.code} (approved DPR)" if u.dpr else None, "issued_by": f"{issuer.name or issuer.email}, MIRAI Shakthi" if issuer else None,
    })


class DeliveredIn(BaseModel):
    on: date
    note: Optional[str] = Field(default=None, max_length=500)


def mark_delivered(p: Purchase, on: date, note: Optional[str]):
    if p.status != "ordered":
        raise HTTPException(409, "Only an ordered purchase can be marked delivered")
    if on > date.today() or (p.po_date and on < p.po_date):
        raise HTTPException(422, "The delivery date must be between the order date and today")
    p.status, p.delivered_on = "delivered", on
    if note:
        p.handover_note = ((p.handover_note or "") + f"\nDelivery: {note}").strip()
    p.updated_at = now()


@router.post("/purchases/{pid}/delivered")
def delivered(pid: int, body: DeliveredIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    p = get_purchase(db, user, pid)
    mark_delivered(p, body.on, body.note)
    audit(db, user, "purchase_delivered", "purchase", p.id)
    db.commit()
    return purchase_detail(pid, user, db)


@router.post("/purchases/{pid}/photos")
async def purchase_photo(pid: int, file: UploadFile = File(...), caption: Optional[str] = Form(default=None, max_length=160),
                         user: User = Depends(writer), db: Session = Depends(get_db)):
    p = get_purchase(db, user, pid)
    if p.status not in ("ordered", "delivered", "installed"):
        raise HTTPException(409, "Add photos after the order is placed")
    name = save_file(await file.read(10 * 1024 * 1024 + 1), file.content_type or "", images_only=True)
    p.photos = list(p.photos or []) + [{"file": name, "caption": caption, "at": now().isoformat()}]
    p.updated_at = now()
    db.commit()
    return purchase_detail(pid, user, db)


class AssetLine(BaseModel):
    item: str
    serial_no: Optional[str] = Field(default=None, max_length=80)
    warranty_until: Optional[date] = None


class InstalledIn(BaseModel):
    on: date
    handover_note: str = Field(min_length=5, max_length=2000)
    assets: list[AssetLine] = []


@router.post("/purchases/{pid}/installed")
def installed(pid: int, body: InstalledIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    """Installation and handover: needs at least one photo; adds the items to the unit's asset register."""
    p = get_purchase(db, user, pid)
    if p.status != "delivered":
        raise HTTPException(409, "Mark the delivery first")
    if not p.photos:
        raise HTTPException(422, "Add at least one installation photo")
    if body.on > date.today() or (p.delivered_on and body.on < p.delivered_on):
        raise HTTPException(422, "The installation date must be between the delivery date and today")
    q = db.get(Quotation, p.selected_quote_id)
    extra = {a.item: a for a in body.assets}
    spec = {i["item"]: i.get("spec") for i in p.items}
    warranty = (body.on + timedelta(days=round(30.44 * q.warranty_months))) if q.warranty_months else None
    for ln in q.lines:
        a = extra.get(ln["item"])
        db.add(Asset(unit_id=p.unit_id, purchase_id=p.id, supplier_id=q.supplier_id, item=ln["item"], spec=spec.get(ln["item"]), qty=ln["qty"],
                     value=round(ln["qty"] * ln["rate"], 2), serial_no=a.serial_no if a else None,
                     warranty_until=(a.warranty_until if a and a.warranty_until else warranty), shared=bool(p.unit.group_id),
                     photo=(p.photos[0]["file"] if p.photos else None), created_at=now()))
    p.status, p.installed_on = "installed", body.on
    p.handover_note = ((p.handover_note or "") + "\nHandover: " + body.handover_note.strip()).strip()
    p.updated_at = p.unit.updated_at = now()
    audit(db, user, "purchase_installed", "purchase", p.id)
    db.commit()
    return purchase_detail(pid, user, db)


@router.post("/purchases/{pid}/cancel")
def cancel_purchase(pid: int, user: User = Depends(buyer), db: Session = Depends(get_db)):
    p = get_purchase(db, user, pid)
    if p.status in ("delivered", "installed"):
        raise HTTPException(409, "Delivered items cannot be cancelled here")
    p.status, p.updated_at = "cancelled", now()
    audit(db, user, "purchase_cancel", "purchase", p.id)
    db.commit()
    return purchase_detail(pid, user, db)


# ================================================================ assets
class AssetIn(BaseModel):
    item: str = Field(min_length=2, max_length=160)
    spec: Optional[str] = Field(default=None, max_length=200)
    qty: float = Field(default=1, gt=0)
    value: float = Field(default=0, ge=0)
    serial_no: Optional[str] = Field(default=None, max_length=80)
    warranty_until: Optional[date] = None
    insurance_policy: Optional[str] = Field(default=None, max_length=80)
    insurance_until: Optional[date] = None
    shared: bool = False
    status: Literal["working", "repair", "disposed"] = "working"


@router.post("/units/{uid}/assets")
def add_asset(uid: int, body: AssetIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    u = get_unit(db, user, uid)
    db.add(Asset(unit_id=u.id, created_at=now(), **body.model_dump()))
    u.updated_at = now()
    db.commit()
    db.refresh(u)
    return unit_out(db, u, full=True)


@router.put("/assets/{aid}")
def edit_asset(aid: int, body: AssetIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    a = db.get(Asset, aid)
    if not a:
        raise HTTPException(404, "Asset not found")
    u = get_unit(db, user, a.unit_id)
    for k, v in body.model_dump().items():
        setattr(a, k, v)
    u.updated_at = now()
    audit(db, user, "asset_update", "asset", a.id)
    db.commit()
    db.refresh(u)
    return unit_out(db, u, full=True)


# ================================================================ registrations
class RegistrationIn(BaseModel):
    status: Literal["todo", "applied", "done", "not_needed"]
    number: Optional[str] = Field(default=None, max_length=60)
    applied_on: Optional[date] = None
    issued_on: Optional[date] = None
    valid_until: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=255)


@router.post("/units/{uid}/registrations")
def add_registration(uid: int, kind: str = Query(...), user: User = Depends(writer), db: Session = Depends(get_db)):
    u = get_unit(db, user, uid)
    if kind not in REGISTRATIONS:
        raise HTTPException(422, "Unknown registration")
    if any(r.kind == kind for r in u.registrations):
        raise HTTPException(409, "Already in the list")
    db.add(Registration(unit_id=u.id, kind=kind, status="todo"))
    db.commit()
    db.refresh(u)
    return unit_out(db, u, full=True)


@router.put("/registrations/{rid}")
def edit_registration(rid: int, body: RegistrationIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    r = db.get(Registration, rid)
    if not r:
        raise HTTPException(404, "Not found")
    u = get_unit(db, user, r.unit_id)
    if body.status == "done" and not (body.number or "").strip() and r.kind not in ("drone_insurance",):
        raise HTTPException(422, "Enter the registration number")
    if body.status == "not_needed" and not (body.note or "").strip():
        raise HTTPException(422, "Say why it is not needed")
    for d in (body.applied_on, body.issued_on):
        if d and d > date.today():
            raise HTTPException(422, "Dates cannot be in the future")
    for k, v in body.model_dump().items():
        setattr(r, k, v.strip() if isinstance(v, str) else v)
    u.updated_at = now()
    audit(db, user, "registration_update", "unit", u.id, {"kind": r.kind, "status": r.status})
    db.commit()
    db.refresh(u)
    return unit_out(db, u, full=True)


@router.post("/registrations/{rid}/file")
async def registration_file(rid: int, file: UploadFile = File(...), user: User = Depends(writer), db: Session = Depends(get_db)):
    r = db.get(Registration, rid)
    if not r:
        raise HTTPException(404, "Not found")
    u = get_unit(db, user, r.unit_id)
    r.file = save_file(await file.read(10 * 1024 * 1024 + 1), file.content_type or "")
    db.commit()
    db.refresh(u)
    return unit_out(db, u, full=True)


# ================================================================ readiness (Form 7.3) and launch
class TickIn(BaseModel):
    done: bool
    note: Optional[str] = Field(default=None, max_length=255)


@router.put("/units/{uid}/readiness/{key}")
def tick(uid: int, key: str, body: TickIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    u = get_unit(db, user, uid)
    item = next((i for i in checklist(db, u) if i["key"] == key), None)
    if not item:
        raise HTTPException(404, "Not in the checklist")
    if item["kind"] == "auto":
        raise HTTPException(422, "This item is checked automatically")
    r = dict(u.readiness or {})
    r[key] = {**(r.get(key) or {}), "done": body.done, "note": body.note, "by": user.name or user.email, "at": now().isoformat()}
    u.readiness, u.updated_at = r, now()
    db.commit()
    db.refresh(u)
    return unit_out(db, u, full=True)


@router.post("/units/{uid}/readiness/{key}/photo")
async def tick_photo(uid: int, key: str, file: UploadFile = File(...), user: User = Depends(writer), db: Session = Depends(get_db)):
    u = get_unit(db, user, uid)
    if not any(i["key"] == key for i in checklist(db, u)):
        raise HTTPException(404, "Not in the checklist")
    name = save_file(await file.read(10 * 1024 * 1024 + 1), file.content_type or "", images_only=True)
    r = dict(u.readiness or {})
    r[key] = {**(r.get(key) or {}), "photo": name}
    u.readiness, u.updated_at = r, now()
    db.commit()
    db.refresh(u)
    return unit_out(db, u, full=True)


class LaunchIn(BaseModel):
    launch_date: date


@router.post("/units/{uid}/launch")
def launch(uid: int, body: LaunchIn, user: User = Depends(launcher), db: Session = Depends(get_db)):
    """Form 7.3 – all items done: the unit is launched and the entrepreneur moves to stage 5 (Sell & deliver)."""
    u = get_unit(db, user, uid)
    if u.status != "setting_up":
        raise HTTPException(409, "This unit is already launched")
    if body.launch_date > date.today() + timedelta(days=30) or body.launch_date < date.today() - timedelta(days=365):
        raise HTTPException(422, "Choose a launch date within the last year or the next 30 days")
    pending = [i["label"] for i in checklist(db, u) if not i["done"]]
    if pending:
        raise HTTPException(422, "Still to do: " + "; ".join(pending))
    u.status, u.launch_date, u.launched_by_id, u.updated_at = "launched", body.launch_date, user.id, now()
    o = u.entrepreneur or u.group
    if o is not None:
        bump_stage(o, 5)
    audit(db, user, "unit_launch", "unit", u.id, {"date": body.launch_date.isoformat()})
    db.commit()
    db.refresh(u)
    return unit_out(db, u, full=True)


# ================================================================ files
@router.get("/files/{name}")
def setup_file(name: str, t: str = Query(min_length=10)):
    if not re.fullmatch(r"[0-9a-f]{32}\.(pdf|jpg|png|webp)", name):
        raise HTTPException(404, "Not found")
    try:
        claims = jwt.decode(t, settings.JWT_SECRET, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(403, "Link expired") from e
    if claims.get("purpose") != "setupfile" or claims.get("f") != name:
        raise HTTPException(403, "Link not valid")
    p = file_path(name)
    if not p.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(p, headers={"Cache-Control": "private, max-age=600"})


@router.get("/files/po/{pid}.pdf")
def po_pdf(pid: int, t: str = Query(min_length=10), db: Session = Depends(get_db)):
    try:
        claims = jwt.decode(t, settings.JWT_SECRET, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(403, "Link expired – open the purchase again") from e
    if claims.get("purpose") != "po" or claims.get("p") != pid:
        raise HTTPException(403, "Link not valid")
    p = db.get(Purchase, pid)
    if not p or not p.po_number:
        raise HTTPException(404, "Not found")
    return Response(render_po(db, p), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{p.po_number}.pdf"', "Cache-Control": "private, no-store"})


# ================================================================ reports
@router.get("/reports/summary")
def report(user: User = Depends(reader), db: Session = Depends(get_db)):
    units = _visible(db, user)
    purchases = [p for u in units for p in u.purchases if p.status != "cancelled"]
    ordered = [p for p in purchases if p.po_amount]
    est = sum(sum(float(i.get("qty") or 0) * float(i.get("est_rate") or 0) for i in p.items) for p in ordered)
    days = [(p.installed_on - p.po_date).days for p in ordered if p.installed_on and p.po_date]
    regs: dict[str, dict] = {}
    for u in units:
        for r in u.registrations:
            x = regs.setdefault(r.kind, {"kind": r.kind, "label": REGISTRATIONS.get(r.kind, (r.kind,))[0], "done": 0, "pending": 0})
            x["done" if r.status in ("done", "not_needed") else "pending"] += 1
    stats = supplier_stats(db)
    sup_ids = {db.get(Quotation, p.selected_quote_id).supplier_id for p in ordered if p.selected_quote_id}
    sups = [supplier_out(s, stats=stats) for s in db.scalars(select(Supplier).where(Supplier.id.in_(sup_ids or {0})))]
    today = date.today()
    m = Masters(db)
    by_model: dict[str, dict] = {}
    for u in units:
        k = u.model.name_en if u.model else "Own enterprise"
        x = by_model.setdefault(k, {"label": k, "setting_up": 0, "launched": 0})
        if u.status in ("setting_up", "launched"):
            x[u.status] += 1
    return {
        "units": {s: sum(1 for u in units if u.status == s) for s in ("setting_up", "launched", "paused", "closed")},
        "launched_this_month": sum(1 for u in units if u.launch_date and u.launch_date.year == today.year and u.launch_date.month == today.month),
        "purchases": {s: sum(1 for p in purchases if p.status == s) for s in PURCHASE_STATUS if s != "cancelled"},
        "ordered_value": round(sum(p.po_amount or 0 for p in ordered), 2), "estimate_value": round(est, 2),
        "saving": round(est - sum(p.po_amount or 0 for p in ordered), 2) if est else None,
        "avg_days_to_install": round(sum(days) / len(days), 1) if days else None,
        "late_deliveries": [purchase_out(db, p) | {"unit": p.unit.name} for p in purchases
                            if p.status == "ordered" and p.expected_delivery and p.expected_delivery < today][:20],
        "registrations": sorted(regs.values(), key=lambda x: -x["pending"]),
        "suppliers": sorted(sups, key=lambda s: -s["value"]),
        "by_model": list(by_model.values()),
        "ready_to_launch": [unit_out(db, u, m) for u in units if u.status == "setting_up"
                            and all(i["done"] for i in checklist(db, u))][:20],
    }
