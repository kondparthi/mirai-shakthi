"""M8 – marketing, sales & orders. Used by the entrepreneur (their own units, in the app) and by staff (units in scope):
listings (Form 8.1), orders and bookings (Form 8.2), customers and repeat follow-ups, AI-assisted posters and messages,
buyer enquiries routed to units, campaigns (Form 8.3), reports. Public shop pages and order tracking need no login."""
import datetime as dt
import re
from urllib.parse import quote
from collections import defaultdict
from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import User
from ..models_p4 import Unit
from ..models_p5 import (CHANNELS, CUSTOMER_KINDS, ORDER_FLOW, ORDER_STATUS, Campaign, Customer, Enquiry, EnquiryRoute, FollowUpNote, Listing,
                         Material, Order)
from ..programme.service import Masters
from ..roles import SETUP_READ
from ..security import ALGO, current_user, require_roles
from ..setup.service import can_see_unit
from ..training.service import audit
from ..market import promo
from ..market.service import (FILE_DIR, MARKET_WRITE, SALE_STATUSES, availability, clean_mobile, file_url, listing_out, masked, my_unit_ids, new_token,
                              now, order_out, remaining, save_bytes, save_photo, shop_url, status_label, track_url, unit_access, unit_summary,
                              upsert_customer, wa_link)

router = APIRouter(prefix="/api/v1/market", tags=["market"])
public = APIRouter(prefix="/api/v1/public", tags=["public"])
staff_read = require_roles(*SETUP_READ)
staff_write = require_roles(*MARKET_WRITE)
PRICE_UNITS = ["each", "plate", "glass", "cup", "pack", "piece", "kg", "litre", "acre", "hour", "day", "trip"]


def _lang(user: User, lang: Optional[str]) -> str:
    return lang if lang in ("en", "te") else (user.language or "en")


@router.get("/meta")
def meta(user: User = Depends(current_user)):
    return {"statuses": [{"code": k, "label": v[0], "label_te": v[1]} for k, v in ORDER_STATUS.items()], "flow": {k: list(v) for k, v in ORDER_FLOW.items()},
            "customer_kinds": [{"code": k, "label": v} for k, v in CUSTOMER_KINDS.items()], "channels": [{"code": k, "label": v} for k, v in CHANNELS.items()],
            "price_units": PRICE_UNITS, "occasions": [{"code": k, "label": v[0], "label_te": v[1]} for k, v in promo.OCCASIONS.items()],
            "can": {"staff": user.role in SETUP_READ, "write": user.role in MARKET_WRITE or user.role == "msme"}}


@router.get("/my-units")
def my_units(lang: Optional[str] = None, user: User = Depends(require_roles("msme")), db: Session = Depends(get_db)):
    lang = _lang(user, lang)
    out = []
    for uid in sorted(my_unit_ids(db, user), reverse=True):
        u = db.get(Unit, uid)
        out.append({"id": u.id, "code": u.code, "name": u.name, "status": u.status, "shop_url": shop_url(u),
                    "model": (u.model.name_te or u.model.name_en) if u.model and lang == "te" else (u.model.name_en if u.model else None),
                    "summary": unit_summary(db, u, 14)})
    return out


@router.get("/units/{uid}/summary")
def summary(uid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid)
    return {"unit": {"id": u.id, "code": u.code, "name": u.name, "status": u.status, "shop_url": shop_url(u)}, **unit_summary(db, u)}


@router.get("/units/{uid}/campaigns")
def unit_campaigns(uid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Running campaigns this unit takes part in (to tag orders made there)."""
    u = unit_access(db, user, uid)
    t = date.today()
    return [{"id": c.id, "name": c.name, "end_date": c.end_date.isoformat()} for c in db.scalars(select(Campaign).where(Campaign.start_date <= t, Campaign.end_date >= t))
            if u.id in (c.unit_ids or [])]


# ================================================================ listings (Form 8.1)
class SlotIn(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    capacity: Optional[float] = Field(default=None, ge=0, le=100000)


class ListingIn(BaseModel):
    kind: Literal["product", "service"]
    name: str = Field(min_length=2, max_length=120)
    name_te: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    price: float = Field(gt=0, le=10_000_000)
    price_unit: str = Field(min_length=1, max_length=20)
    available: bool = True
    daily_capacity: Optional[float] = Field(default=None, gt=0, le=100000)
    slots: list[SlotIn] = Field(default_factory=list, max_length=12)
    sort: int = Field(default=100, ge=0, le=999)


@router.get("/units/{uid}/listings")
def list_listings(uid: int, lang: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid)
    rows = db.scalars(select(Listing).where(Listing.unit_id == u.id).order_by(Listing.sort, Listing.id))
    return [listing_out(li, _lang(user, lang)) for li in rows]


@router.post("/units/{uid}/listings/from-model")
def listings_from_model(uid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Start the catalogue from the enterprise model's sales items (the DPR's products, with the DPR prices)."""
    u = unit_access(db, user, uid, write=True)
    items = ((u.dpr.inputs or {}).get("sales") or {}).get("items") if u.dpr else None
    items = items or ((u.model.sales_template or {}).get("items") if u.model else None) or []
    have = {li.name.lower() for li in db.scalars(select(Listing).where(Listing.unit_id == u.id))}
    service = bool(u.model and u.model.activity == "service" and u.model.sector == "agriculture")
    for i, it in enumerate(items):
        if it.get("name", "").lower() in have or not it.get("price"):
            continue
        db.add(Listing(unit_id=u.id, kind="service" if service else "product", name=it["name"][:120], price=float(it["price"]),
                       price_unit=(it.get("unit") or "each")[:20], available=True, sort=10 * (i + 1), photos=[],
                       daily_capacity=float(it["units_per_day"]) if service and it.get("units_per_day") else None,
                       slots=[{"label": "6–10 AM", "capacity": None}, {"label": "3–6 PM", "capacity": None}] if service else [], created_at=now()))
    db.commit()
    return list_listings(uid, None, user, db)


@router.post("/units/{uid}/listings")
def create_listing(uid: int, body: ListingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid, write=True)
    li = Listing(unit_id=u.id, photos=[], created_at=now(), **body.model_dump(exclude={"slots"}), slots=[s.model_dump() for s in body.slots])
    db.add(li)
    db.flush()
    audit(db, user, "listing_create", "listing", li.id, {"unit": u.code})
    db.commit()
    return listing_out(li, user.language or "en")


def _listing(db: Session, user: User, lid: int, write: bool = True) -> Listing:
    li = db.get(Listing, lid)
    if not li:
        raise HTTPException(404, "Not found")
    unit_access(db, user, li.unit_id, write=write)
    return li


@router.put("/listings/{lid}")
def update_listing(lid: int, body: ListingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    li = _listing(db, user, lid)
    for k, v in body.model_dump(exclude={"slots"}).items():
        setattr(li, k, v)
    li.slots = [s.model_dump() for s in body.slots]
    db.commit()
    return listing_out(li, user.language or "en")


@router.post("/listings/{lid}/photo")
async def listing_photo(lid: int, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    li = _listing(db, user, lid)
    if len(li.photos or []) >= 3:
        raise HTTPException(422, "Up to 3 photos – remove one first")
    li.photos = list(li.photos or []) + [save_photo(await file.read(10 * 1024 * 1024 + 1))]
    db.commit()
    return listing_out(li, user.language or "en")


@router.delete("/listings/{lid}/photo/{n}")
def remove_photo(lid: int, n: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    li = _listing(db, user, lid)
    photos = list(li.photos or [])
    if not 0 <= n < len(photos):
        raise HTTPException(404, "Not found")
    photos.pop(n)
    li.photos = photos
    db.commit()
    return listing_out(li, user.language or "en")


@router.get("/listings/{lid}/availability")
def listing_availability(lid: int, start: Optional[date] = None, days: int = Query(14, ge=1, le=60), user: User = Depends(current_user),
                         db: Session = Depends(get_db)):
    li = _listing(db, user, lid, write=False)
    return availability(db, li, start or date.today(), days)


# ================================================================ orders and bookings (Form 8.2)
class CustomerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    mobile: str
    kind: Literal["household", "shop", "institution", "farmer", "event", "other"] = "household"
    village: Optional[str] = Field(default=None, max_length=120)
    organisation: Optional[str] = Field(default=None, max_length=160)


class LineIn(BaseModel):
    listing_id: int
    qty: float = Field(gt=0, le=100000)
    price: Optional[float] = Field(default=None, ge=0, le=10_000_000)


class OrderIn(BaseModel):
    customer: CustomerIn
    lines: list[LineIn] = Field(min_length=1, max_length=40)
    date: Optional[dt.date] = None  # dt.date: a field named "date" would hide the type
    slot: Optional[str] = Field(default=None, max_length=40)
    status: Literal["new", "confirmed", "delivered", "paid"] = "confirmed"
    payment_mode: Optional[Literal["cash", "upi", "credit"]] = None
    address: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = Field(default=None, max_length=500)
    campaign_id: Optional[int] = None


def build_order(db: Session, u: Unit, body: OrderIn, user: User | None, source: str, fixed_price: bool) -> Order:
    if u.status in ("closed", "paused"):
        raise HTTPException(409, "This unit is not taking orders now")
    listings = {li.id: li for li in db.scalars(select(Listing).where(Listing.unit_id == u.id))}
    lines, booking = [], False
    for ln in body.lines:
        li = listings.get(ln.listing_id)
        if not li:
            raise HTTPException(422, "An item is not from this unit")
        if not li.available:
            raise HTTPException(422, f"{li.name} is not available now")
        booking = booking or li.kind == "service"
        price = li.price if fixed_price or ln.price is None else ln.price
        lines.append({"listing_id": li.id, "name": li.name, "name_te": li.name_te, "qty": ln.qty, "price": price, "unit": li.price_unit})
    if booking:
        if not body.date:
            raise HTTPException(422, "Choose the date for the booking")
        if body.date < date.today() and source == "online":
            raise HTTPException(422, "The date is in the past")
        for ln in lines:
            li = listings[ln["listing_id"]]
            if li.kind == "service":
                left = remaining(db, li, body.date, body.slot if li.slots else None)
                if left is not None and ln["qty"] > left + 1e-9:
                    raise HTTPException(409, f"Only {max(0, left):g} {li.price_unit} left for {li.name} on that {'slot' if li.slots else 'day'}")
    if body.status == "paid" and body.payment_mode in (None, "credit"):
        raise HTTPException(422, "Paid needs the payment mode: cash or UPI")
    if body.campaign_id and not db.get(Campaign, body.campaign_id):
        raise HTTPException(422, "Unknown campaign")
    c = upsert_customer(db, body.customer.mobile, body.customer.name, body.customer.kind, body.customer.village, u.district, body.customer.organisation)
    amount = round(sum(ln["qty"] * ln["price"] for ln in lines), 2)
    who = (user.name or user.email or user.mobile) if user else "Customer (online)"
    o = Order(unit_id=u.id, customer_id=c.id, kind="booking" if booking else "order", lines=lines, amount=amount, date=body.date,
              slot=body.slot if booking else None, status=body.status, payment_mode=body.payment_mode,
              paid_on=date.today() if body.status == "paid" else None, source=source, campaign_id=body.campaign_id, address=body.address,
              note=body.note, track_token=new_token(), events=[{"status": body.status, "at": now().isoformat(), "by": who}],
              created_by_id=user.id if user else None, created_at=now(), updated_at=now())
    o.customer = c
    db.add(o)
    db.flush()
    o.code = f"OR-{date.today().year}-{o.id:05d}"
    return o


@router.get("/units/{uid}/orders")
def list_orders(uid: int, status: Optional[str] = None, when: Optional[Literal["today", "upcoming", "open", "credit"]] = None, q: Optional[str] = None,
                lang: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid)
    rows = list(db.scalars(select(Order).where(Order.unit_id == u.id).order_by(Order.created_at.desc()).limit(500)))
    counts = {s: sum(1 for o in rows if o.status == s) for s in ORDER_STATUS}
    today = date.today()
    if status:
        rows = [o for o in rows if o.status == status]
    if when == "today":
        rows = [o for o in rows if (o.date == today) or (o.created_at.date() == today)]
    elif when == "upcoming":
        rows = sorted([o for o in rows if o.status in ("new", "confirmed") and o.date and o.date >= today], key=lambda o: (o.date, o.slot or ""))
    elif when == "open":
        rows = [o for o in rows if o.status in ("new", "confirmed")]
    elif when == "credit":
        rows = [o for o in rows if o.status == "delivered"]
    if q:
        ql = q.lower()
        rows = [o for o in rows if ql in o.customer.name.lower() or ql in o.customer.mobile or ql in (o.code or "").lower()]
    lg = _lang(user, lang)
    return {"counts": counts, "rows": [order_out(o, lg) for o in rows[:200]]}


@router.post("/units/{uid}/orders")
def create_order(uid: int, body: OrderIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid, write=True)
    o = build_order(db, u, body, user, "unit" if user.role == "msme" else "staff", fixed_price=False)
    audit(db, user, "order_create", "order", o.id, {"unit": u.code, "amount": o.amount})
    db.commit()
    return order_out(o, user.language or "en")


def _order(db: Session, user: User, oid: int) -> Order:
    o = db.get(Order, oid)
    if not o:
        raise HTTPException(404, "Not found")
    unit_access(db, user, o.unit_id, write=True)
    return o


class StatusIn(BaseModel):
    status: Literal["confirmed", "delivered", "paid", "cancelled"]
    payment_mode: Optional[Literal["cash", "upi", "credit"]] = None
    reason: Optional[str] = Field(default=None, max_length=255)


@router.post("/orders/{oid}/status")
def order_status(oid: int, body: StatusIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o = _order(db, user, oid)
    if body.status not in ORDER_FLOW.get(o.status, ()):
        raise HTTPException(409, f"Cannot move from {status_label(o.status)} to {status_label(body.status)}")
    if body.status == "cancelled" and not (body.reason or "").strip():
        raise HTTPException(422, "Write why the order is cancelled")
    if body.status == "paid":
        mode = body.payment_mode or (o.payment_mode if o.payment_mode != "credit" else None)
        if mode not in ("cash", "upi"):
            raise HTTPException(422, "Paid needs the payment mode: cash or UPI")
        o.payment_mode, o.paid_on = mode, date.today()
    elif body.payment_mode:
        o.payment_mode = body.payment_mode
    if body.status == "cancelled":
        o.cancel_reason = body.reason.strip()
    o.status = body.status
    o.events = list(o.events or []) + [{"status": body.status, "at": now().isoformat(), "by": user.name or user.email or user.mobile}]
    o.updated_at = now()
    db.commit()
    return order_out(o, user.language or "en")


@router.get("/orders/{oid}")
def get_order(oid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o = db.get(Order, oid)
    if not o:
        raise HTTPException(404, "Not found")
    unit_access(db, user, o.unit_id)
    d = order_out(o, user.language or "en")
    d["track_url"] = track_url(o)
    d["wa_link"] = wa_link(o.customer.mobile, f"{o.unit.name}: your order {o.code} – {d['status_label']}. Track it here: {track_url(o)}")
    return d


@router.get("/customers/lookup")
def lookup_customer(mobile: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Fill the customer's name when the mobile number is known (to any unit)."""
    if user.role not in SETUP_READ and user.role != "msme":
        raise HTTPException(403, "You do not have access to this")
    c = db.scalar(select(Customer).where(Customer.mobile == clean_mobile(mobile)))
    return {"found": bool(c), "name": c.name if c else None, "kind": c.kind if c else None, "village": c.village if c else None,
            "organisation": c.organisation if c else None}


@router.get("/units/{uid}/customers")
def unit_customers(uid: int, q: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid)
    stats: dict[int, dict] = {}
    for o in db.scalars(select(Order).where(Order.unit_id == u.id, Order.status != "cancelled")):
        s = stats.setdefault(o.customer_id, {"orders": 0, "spend": 0.0, "last": None, "outstanding": 0.0})
        s["orders"] += 1
        if o.status in SALE_STATUSES:
            s["spend"] += o.amount
        if o.status == "delivered":
            s["outstanding"] += o.amount
        d = o.date or o.created_at.date()
        s["last"] = max(s["last"], d) if s["last"] else d
    custs = {c.id: c for c in db.scalars(select(Customer).where(Customer.id.in_(list(stats) or [0])))}
    rows = [{"id": cid, "name": custs[cid].name, "mobile": custs[cid].mobile, "kind": custs[cid].kind, "village": custs[cid].village,
             "organisation": custs[cid].organisation, **{**s, "spend": round(s["spend"], 2), "outstanding": round(s["outstanding"], 2),
                                                          "last": s["last"].isoformat() if s["last"] else None}} for cid, s in stats.items()]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r["name"].lower() or ql in r["mobile"]]
    return sorted(rows, key=lambda r: -r["spend"])


# ================================================================ repeat-customer follow-ups
@router.get("/units/{uid}/followups")
def followups(uid: int, days: int = Query(14, ge=3, le=120), lang: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Customers who bought before and have not ordered for a while (and were not contacted since)."""
    u = unit_access(db, user, uid)
    lg = _lang(user, lang)
    last: dict[int, date] = {}
    count: dict[int, int] = defaultdict(int)
    for o in db.scalars(select(Order).where(Order.unit_id == u.id, Order.status.in_(SALE_STATUSES + ("new", "confirmed")))):
        d = o.date or o.created_at.date()
        last[o.customer_id] = max(last.get(o.customer_id, d), d)
        count[o.customer_id] += 1
    contacted = {}
    for f in db.scalars(select(FollowUpNote).where(FollowUpNote.unit_id == u.id)):
        contacted[f.customer_id] = max(contacted.get(f.customer_id, f.at.date()), f.at.date())
    cut = date.today() - timedelta(days=days)
    out = []
    for cid, d in last.items():
        if d > cut or contacted.get(cid, date.min) >= d:
            continue
        c = db.get(Customer, cid)
        msg = (f"నమస్తే {c.name} గారు! {u.name} నుండి. మీకు మళ్లీ కావాలంటే ఈ నంబర్‌కు ఆర్డర్ చేయండి. ఆన్‌లైన్‌లో: {shop_url(u)}" if lg == "te"
               else f"Hello {c.name}! This is {u.name}. If you would like to order again, reply here or order online: {shop_url(u)}")
        out.append({"customer_id": cid, "name": c.name, "mobile": c.mobile, "kind": c.kind, "orders": count[cid], "last": d.isoformat(),
                    "days": (date.today() - d).days, "wa_link": wa_link(c.mobile, msg)})
    return sorted(out, key=lambda r: (-r["orders"], -r["days"]))


class FollowIn(BaseModel):
    customer_id: int
    note: Optional[str] = Field(default=None, max_length=255)


@router.post("/units/{uid}/followups")
def followup_done(uid: int, body: FollowIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid, write=True)
    if not db.scalar(select(Order.id).where(Order.unit_id == u.id, Order.customer_id == body.customer_id).limit(1)):
        raise HTTPException(404, "Not a customer of this unit")
    db.add(FollowUpNote(unit_id=u.id, customer_id=body.customer_id, note=body.note, at=now()))
    db.commit()
    return {"ok": True}


# ================================================================ promotional materials
class PromoIn(BaseModel):
    lang: Literal["en", "te"] = "te"
    occasion: Literal["launch", "daily", "festival", "bulk", "booking"] = "daily"
    listing_ids: list[int] = []


def material_out(m: Material) -> dict:
    return {"id": m.id, "lang": m.lang, "title": m.title, "tagline": m.tagline, "message": m.message, "poster_url": file_url(m.file),
            "source": m.source, "at": m.created_at.isoformat() if m.created_at else None,
            "share_link": f"https://wa.me/?text={quote(m.message or '')}"}


@router.post("/units/{uid}/promo")
def make_promo(uid: int, body: PromoIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """AI-assisted poster and WhatsApp message from the unit's real listings and prices (template when AI is off)."""
    u = unit_access(db, user, uid, write=True)
    q = select(Listing).where(Listing.unit_id == u.id, Listing.available.is_(True)).order_by(Listing.sort, Listing.id)
    rows = [li for li in db.scalars(q) if not body.listing_ids or li.id in body.listing_ids]
    if not rows:
        raise HTTPException(422, "Add products or services first")
    o = u.entrepreneur
    mobile = o.mobile if o else next((m.mobile for m in (u.group.members if u.group else []) if m.role == "leader" and m.mobile), None)
    mob = f"{mobile[:5]} {mobile[5:]}" if mobile else "—"
    m = Masters(db)
    place = ", ".join(x for x in (m.name("village", u.village, body.lang), m.name("mandal", u.mandal, body.lang)) if x)
    ctx = {"unit": u.name, "place": place, "mobile": mob, "shop_url": shop_url(u) if u.status == "launched" else None,
           "items": [{"name": li.name, "name_te": li.name_te, "price": li.price, "unit": li.price_unit} for li in rows]}
    text, source = promo.draft(ctx, body.lang, body.occasion)
    name = save_bytes(promo.poster(ctx, text, body.lang), ".png")
    mat = Material(unit_id=u.id, lang=body.lang, title=text["title"], tagline=text["tagline"], message=text["message"], file=name, source=source, created_at=now())
    db.add(mat)
    db.commit()
    return material_out(mat)


@router.get("/units/{uid}/promo")
def list_promo(uid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = unit_access(db, user, uid)
    return [material_out(m) for m in db.scalars(select(Material).where(Material.unit_id == u.id).order_by(Material.id.desc()).limit(20))]


# ================================================================ buyer enquiries (staff, and the units they are routed to)
class EnquiryIn(BaseModel):
    customer: CustomerIn
    need: str = Field(min_length=5, max_length=2000)
    sector: Optional[str] = None
    model_code: Optional[str] = None
    district: Optional[str] = None
    quantity: Optional[str] = Field(default=None, max_length=120)
    needed_by: Optional[date] = None
    budget: Optional[float] = Field(default=None, ge=0)
    source: Literal["call", "visit", "campaign", "partner", "online"] = "call"
    campaign_id: Optional[int] = None


def route_out(r: EnquiryRoute) -> dict:
    return {"id": r.id, "unit_id": r.unit_id, "unit": r.unit.name, "unit_code": r.unit.code, "status": r.status, "quote_amount": r.quote_amount,
            "reply": r.reply, "replied_at": r.replied_at.isoformat() if r.replied_at else None}


def enquiry_out(db: Session, e: Enquiry, m: Masters, full_mobile: bool = True) -> dict:
    c = e.customer
    return {"id": e.id, "code": e.code, "need": e.need, "sector": e.sector, "sector_name": m.name("sector", e.sector), "model_code": e.model_code,
            "district": e.district, "district_name": m.name("district", e.district), "quantity": e.quantity,
            "needed_by": e.needed_by.isoformat() if e.needed_by else None, "budget": e.budget, "source": e.source, "campaign_id": e.campaign_id,
            "status": e.status, "note": e.note, "routes": [route_out(r) for r in e.routes],
            "buyer": {"name": c.name, "organisation": c.organisation, "kind": c.kind, "mobile": c.mobile if full_mobile else masked(c.mobile)},
            "created_at": e.created_at.isoformat() if e.created_at else None}


def _visible_enquiry(user: User, e: Enquiry) -> bool:
    if user.role in ("admin", "programme_manager"):
        return True
    ds = (user.scope or {}).get("districts") or []
    return (not ds) or e.district in ds or e.district is None


@router.get("/enquiries")
def list_enquiries(status: Optional[str] = None, user: User = Depends(staff_read), db: Session = Depends(get_db)):
    m = Masters(db)
    rows = [e for e in db.scalars(select(Enquiry).order_by(Enquiry.id.desc()).limit(300)) if _visible_enquiry(user, e)]
    counts = {s: sum(1 for e in rows if e.status == s) for s in ("open", "routed", "won", "lost", "closed")}
    if status:
        rows = [e for e in rows if e.status == status]
    return {"counts": counts, "rows": [enquiry_out(db, e, m) for e in rows]}


@router.post("/enquiries")
def create_enquiry(body: EnquiryIn, user: User = Depends(staff_write), db: Session = Depends(get_db)):
    m = Masters(db)
    if body.district and not m.has("district", body.district):
        raise HTTPException(422, "Choose a district from the list")
    if body.sector and not m.has("sector", body.sector):
        raise HTTPException(422, "Unknown sector")
    c = upsert_customer(db, body.customer.mobile, body.customer.name, body.customer.kind, body.customer.village, body.district, body.customer.organisation)
    e = Enquiry(customer_id=c.id, need=body.need.strip(), sector=body.sector, model_code=body.model_code, district=body.district,
                quantity=body.quantity, needed_by=body.needed_by, budget=body.budget, source=body.source, campaign_id=body.campaign_id,
                created_by_id=user.id, created_at=now(), updated_at=now())
    e.customer = c
    db.add(e)
    db.flush()
    e.code = f"EQ-{date.today().year}-{e.id:05d}"
    audit(db, user, "enquiry_create", "enquiry", e.id)
    db.commit()
    return enquiry_out(db, e, m)


@router.get("/enquiries/{eid}")
def get_enquiry(eid: int, user: User = Depends(staff_read), db: Session = Depends(get_db)):
    e = db.get(Enquiry, eid)
    if not e or not _visible_enquiry(user, e):
        raise HTTPException(404, "Not found")
    m = Masters(db)
    out = enquiry_out(db, e, m)
    # suggested units: launched, in scope, matching sector / model, same district first, with listings
    routed = {r.unit_id for r in e.routes}
    sugg = []
    for u in db.scalars(select(Unit).where(Unit.status == "launched")):
        if u.id in routed or not can_see_unit(user, u):
            continue
        if e.model_code and (not u.model or u.model.code != e.model_code):
            continue
        if e.sector and (not u.model or u.model.sector != e.sector):
            continue
        n = db.scalar(select(func.count()).select_from(Listing).where(Listing.unit_id == u.id, Listing.available.is_(True)))
        sugg.append({"id": u.id, "code": u.code, "name": u.name, "district_name": m.name("district", u.district), "model": u.model.name_en if u.model else None,
                     "same_district": u.district == e.district, "listings": n, "rating": unit_summary(db, u)["rating"]})
    out["suggested"] = sorted(sugg, key=lambda x: (not x["same_district"], -(x["rating"] or 0)))[:20]
    return out


class RouteIn(BaseModel):
    unit_ids: list[int] = Field(min_length=1, max_length=20)


@router.post("/enquiries/{eid}/route")
def route_enquiry(eid: int, body: RouteIn, user: User = Depends(staff_write), db: Session = Depends(get_db)):
    e = db.get(Enquiry, eid)
    if not e or not _visible_enquiry(user, e):
        raise HTTPException(404, "Not found")
    if e.status in ("won", "lost", "closed"):
        raise HTTPException(409, "This enquiry is closed")
    have = {r.unit_id for r in e.routes}
    for uid in body.unit_ids:
        u = db.get(Unit, uid)
        if not u or not can_see_unit(user, u):
            raise HTTPException(422, "Unknown unit")
        if u.status != "launched":
            raise HTTPException(422, f"{u.name} is not launched yet")
        if uid not in have:
            db.add(EnquiryRoute(enquiry_id=e.id, unit_id=uid, created_at=now()))
    e.status, e.updated_at = "routed", now()
    audit(db, user, "enquiry_route", "enquiry", e.id, {"units": body.unit_ids})
    db.commit()
    db.refresh(e)
    return get_enquiry(eid, user, db)


class EnquiryStatusIn(BaseModel):
    status: Literal["lost", "closed", "open"]
    note: Optional[str] = Field(default=None, max_length=500)


@router.post("/enquiries/{eid}/status")
def enquiry_status(eid: int, body: EnquiryStatusIn, user: User = Depends(staff_write), db: Session = Depends(get_db)):
    e = db.get(Enquiry, eid)
    if not e or not _visible_enquiry(user, e):
        raise HTTPException(404, "Not found")
    e.status, e.note, e.updated_at = body.status, body.note or e.note, now()
    db.commit()
    return get_enquiry(eid, user, db)


@router.get("/units/{uid}/enquiries")
def unit_enquiries(uid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Enquiries sent to this unit (the entrepreneur answers them in the app)."""
    u = unit_access(db, user, uid)
    m = Masters(db)
    out = []
    for r in db.scalars(select(EnquiryRoute).where(EnquiryRoute.unit_id == u.id).order_by(EnquiryRoute.id.desc())):
        e = enquiry_out(db, r.enquiry, m, full_mobile=r.status in ("interested", "won"))
        e.pop("routes")
        out.append({**e, "route": route_out(r)})
    return out


class ReplyIn(BaseModel):
    status: Literal["interested", "declined"]
    quote_amount: Optional[float] = Field(default=None, gt=0, le=100_000_000)
    reply: Optional[str] = Field(default=None, max_length=500)


@router.post("/routes/{rid}/reply")
def reply_enquiry(rid: int, body: ReplyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(EnquiryRoute, rid)
    if not r:
        raise HTTPException(404, "Not found")
    unit_access(db, user, r.unit_id, write=True)
    if r.enquiry.status in ("won", "lost", "closed"):
        raise HTTPException(409, "This enquiry is closed")
    r.status, r.quote_amount, r.reply, r.replied_at = body.status, body.quote_amount, body.reply, now()
    db.commit()
    return unit_enquiries(r.unit_id, user, db)


class RouteOrderIn(BaseModel):
    lines: list[LineIn] = Field(min_length=1, max_length=40)
    date: Optional[dt.date] = None  # dt.date: a field named "date" would hide the type
    slot: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=500)


@router.post("/routes/{rid}/order")
def enquiry_to_order(rid: int, body: RouteOrderIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The buyer chose this unit: make the order; the enquiry is won and the other units are told it is closed."""
    r = db.get(EnquiryRoute, rid)
    if not r:
        raise HTTPException(404, "Not found")
    u = unit_access(db, user, r.unit_id, write=True)
    e = r.enquiry
    if e.status in ("won", "lost", "closed"):
        raise HTTPException(409, "This enquiry is closed")
    c = e.customer
    o = build_order(db, u, OrderIn(customer=CustomerIn(name=c.name, mobile=c.mobile, kind=c.kind, village=c.village, organisation=c.organisation),
                                   lines=body.lines, date=body.date or e.needed_by, slot=body.slot, status="confirmed", note=body.note or e.need[:500],
                                   campaign_id=e.campaign_id), user, "enquiry", fixed_price=False)
    o.enquiry_route_id = r.id
    r.status = "won"
    for other in e.routes:
        if other.id != r.id and other.status != "declined":
            other.status = "lost"
    e.status, e.updated_at = "won", now()
    audit(db, user, "enquiry_won", "enquiry", e.id, {"order": o.code})
    db.commit()
    return order_out(o, user.language or "en")


# ================================================================ campaigns (Form 8.3)
class CampaignIn(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    start_date: date
    end_date: date
    sectors: list[str] = Field(min_length=1)
    unit_ids: list[int] = []
    channels: list[Literal["fair", "whatsapp", "social", "institutional"]] = Field(min_length=1)
    venue: Optional[str] = Field(default=None, max_length=200)
    district: Optional[str] = None
    budget: Optional[float] = Field(default=None, ge=0)
    message_en: Optional[str] = Field(default=None, max_length=3000)
    message_te: Optional[str] = Field(default=None, max_length=3000)
    enquiries: Optional[int] = Field(default=None, ge=0)
    manual_orders: Optional[int] = Field(default=None, ge=0)
    manual_sales: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=3000)

    @field_validator("end_date")
    @classmethod
    def v_end(cls, v, info):
        s = info.data.get("start_date")
        if s and v < s:
            raise ValueError("The end date is before the start date")
        return v


def campaign_out(db: Session, c: Campaign, m: Masters, full: bool = False) -> dict:
    orders = list(db.scalars(select(Order).where(Order.campaign_id == c.id, Order.status != "cancelled")))
    sales = sum(o.amount for o in orders if o.status in SALE_STATUSES)
    enq = db.scalar(select(func.count()).select_from(Enquiry).where(Enquiry.campaign_id == c.id)) or 0
    today = date.today()
    d = {"id": c.id, "name": c.name, "start_date": c.start_date.isoformat(), "end_date": c.end_date.isoformat(), "sectors": c.sectors,
         "sector_names": [m.name("sector", s) for s in c.sectors], "unit_ids": c.unit_ids, "channels": c.channels, "venue": c.venue,
         "district": c.district, "district_name": m.name("district", c.district), "budget": c.budget,
         "state": "upcoming" if c.start_date > today else "running" if c.end_date >= today else "done",
         "results": {"enquiries": enq + (c.enquiries or 0), "orders": len(orders) + (c.manual_orders or 0),
                     "sales": round(sales + (c.manual_sales or 0), 2), "app_orders": len(orders), "app_sales": round(sales, 2)},
         "enquiries": c.enquiries, "manual_orders": c.manual_orders, "manual_sales": c.manual_sales}
    if full:
        units = {u.id: u for u in db.scalars(select(Unit).where(Unit.id.in_(c.unit_ids or [0])))}
        by_unit: dict[int, dict] = {}
        for o in orders:
            x = by_unit.setdefault(o.unit_id, {"orders": 0, "sales": 0.0})
            x["orders"] += 1
            if o.status in SALE_STATUSES:
                x["sales"] += o.amount
        d |= {"message_en": c.message_en, "message_te": c.message_te, "note": c.note,
              "materials": [{**x, "url": file_url(x["file"])} for x in c.materials or []],
              "units": [{"id": uid, "name": units[uid].name if uid in units else "?", "code": units[uid].code if uid in units else None,
                         **by_unit.get(uid, {"orders": 0, "sales": 0.0})} for uid in c.unit_ids or []]}
    return d


@router.get("/campaigns")
def list_campaigns(user: User = Depends(staff_read), db: Session = Depends(get_db)):
    m = Masters(db)
    return [campaign_out(db, c, m) for c in db.scalars(select(Campaign).order_by(Campaign.start_date.desc()))]


def _check_campaign(db: Session, user: User, body: CampaignIn):
    m = Masters(db)
    bad = [s for s in body.sectors if not m.has("sector", s)]
    if body.district and not m.has("district", body.district):
        bad.append(body.district)
    for uid in body.unit_ids:
        u = db.get(Unit, uid)
        if not u or not can_see_unit(user, u):
            bad.append(f"unit {uid}")
    if bad:
        raise HTTPException(422, f"Unknown: {', '.join(map(str, bad))}")


@router.post("/campaigns")
def create_campaign(body: CampaignIn, user: User = Depends(staff_write), db: Session = Depends(get_db)):
    _check_campaign(db, user, body)
    c = Campaign(**body.model_dump(), materials=[], created_by_id=user.id, created_at=now())
    db.add(c)
    db.flush()
    audit(db, user, "campaign_create", "campaign", c.id)
    db.commit()
    return campaign_out(db, c, Masters(db), full=True)


@router.get("/campaigns/{cid}")
def get_campaign(cid: int, user: User = Depends(staff_read), db: Session = Depends(get_db)):
    c = db.get(Campaign, cid)
    if not c:
        raise HTTPException(404, "Not found")
    return campaign_out(db, c, Masters(db), full=True)


@router.put("/campaigns/{cid}")
def update_campaign(cid: int, body: CampaignIn, user: User = Depends(staff_write), db: Session = Depends(get_db)):
    c = db.get(Campaign, cid)
    if not c:
        raise HTTPException(404, "Not found")
    _check_campaign(db, user, body)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return campaign_out(db, c, Masters(db), full=True)


@router.post("/campaigns/{cid}/message")
def campaign_message(cid: int, user: User = Depends(staff_write), db: Session = Depends(get_db)):
    """Draft the campaign's WhatsApp message in English and Telugu from the units' real listings."""
    c = db.get(Campaign, cid)
    if not c:
        raise HTTPException(404, "Not found")
    items = []
    for li in db.scalars(select(Listing).where(Listing.unit_id.in_(c.unit_ids or [0]), Listing.available.is_(True)).order_by(Listing.sort)):
        items.append({"name": li.name, "name_te": li.name_te, "price": li.price, "unit": li.price_unit})
    if not items:
        raise HTTPException(422, "The units in this campaign have no products or services yet")
    when = f"{c.start_date:%d %b} – {c.end_date:%d %b %Y}"
    ctx = {"unit": c.name, "place": ", ".join(x for x in (c.venue, when) if x), "mobile": "", "shop_url": None, "items": items[:6]}
    en, _ = promo.draft(ctx, "en", "festival")
    te, _ = promo.draft(ctx, "te", "festival")
    strip = lambda s: re.sub(r"\n[^\n]*(Call / WhatsApp to order|ఆర్డర్ కోసం కాల్)[^\n]*", "", s)  # noqa: E731 – no single contact for a campaign
    c.message_en, c.message_te = strip(en["message"]), strip(te["message"])
    db.commit()
    return campaign_out(db, c, Masters(db), full=True)


@router.post("/campaigns/{cid}/files")
async def campaign_file(cid: int, file: UploadFile = File(...), user: User = Depends(staff_write), db: Session = Depends(get_db)):
    c = db.get(Campaign, cid)
    if not c:
        raise HTTPException(404, "Not found")
    data = await file.read(10 * 1024 * 1024 + 1)
    ct = (file.content_type or "").split(";")[0]
    if ct == "application/pdf" and data.startswith(b"%PDF"):
        name = save_bytes(data, ".pdf")
    elif ct.startswith("image/"):
        name = save_photo(data)
    else:
        raise HTTPException(422, "Upload a PDF or a photo")
    c.materials = list(c.materials or []) + [{"file": name, "title": (file.filename or "Material")[:80], "at": now().isoformat()}]
    db.commit()
    return campaign_out(db, c, Masters(db), full=True)


# ================================================================ reports
@router.get("/reports/summary")
def report(user: User = Depends(staff_read), db: Session = Depends(get_db)):
    m = Masters(db)
    units = [u for u in db.scalars(select(Unit).where(Unit.status.in_(("launched", "paused")))) if can_see_unit(user, u)]
    ids = {u.id for u in units}
    orders = [o for o in db.scalars(select(Order).where(Order.unit_id.in_(ids or {0})))]
    sales = [o for o in orders if o.status in SALE_STATUSES]
    today = date.today()
    month = [o for o in sales if (o.paid_on or o.date or o.created_at.date()).replace(day=1) == today.replace(day=1)]
    by_unit: dict[int, float] = defaultdict(float)
    by_model: dict[str, float] = defaultdict(float)
    by_source: dict[str, int] = defaultdict(int)
    for o in sales:
        by_unit[o.unit_id] += o.amount
    umap = {u.id: u for u in units}
    for uid, v in by_unit.items():
        u = umap[uid]
        by_model[u.model.name_en if u.model else "Other"] += v
    for o in orders:
        if o.status != "cancelled":
            by_source[o.source] += 1
    weeks = []
    for i in range(7, -1, -1):
        start = today - timedelta(days=today.weekday()) - timedelta(weeks=i)
        weeks.append({"week": start.isoformat(), "amount": round(sum(o.amount for o in sales if start <= (o.paid_on or o.date or o.created_at.date()) < start + timedelta(days=7)), 2)})
    custs = defaultdict(int)
    for o in sales:
        custs[o.customer_id] += 1
    rated = [o.rating for o in orders if o.rating]
    enq = [e for e in db.scalars(select(Enquiry)) if _visible_enquiry(user, e)]
    return {
        "units_selling": sum(1 for uid in ids if any(o.unit_id == uid for o in sales)), "units": len(units),
        "sales_total": round(sum(o.amount for o in sales), 2), "sales_month": round(sum(o.amount for o in month), 2), "orders_month": len(month),
        "orders": {s: sum(1 for o in orders if o.status == s) for s in ORDER_STATUS},
        "outstanding": round(sum(o.amount for o in orders if o.status == "delivered"), 2),
        "customers": len(custs), "repeat_pct": round(100 * sum(1 for v in custs.values() if v > 1) / len(custs)) if custs else 0,
        "rating": round(sum(rated) / len(rated), 1) if rated else None, "ratings": len(rated),
        "weekly": weeks,
        "top_units": [{"id": uid, "name": umap[uid].name, "district_name": m.name("district", umap[uid].district), "amount": round(v, 2)}
                      for uid, v in sorted(by_unit.items(), key=lambda x: -x[1])[:10]],
        "by_model": [{"label": k, "amount": round(v, 2)} for k, v in sorted(by_model.items(), key=lambda x: -x[1])],
        "by_source": [{"label": k, "count": v} for k, v in sorted(by_source.items(), key=lambda x: -x[1])],
        "enquiries": {s: sum(1 for e in enq if e.status == s) for s in ("open", "routed", "won", "lost")},
        "not_selling": [{"id": u.id, "name": u.name, "launch_date": u.launch_date.isoformat() if u.launch_date else None}
                        for u in units if not any(o.unit_id == u.id for o in sales)][:20],
    }


# ================================================================ public: shop page and order tracking (no login)
def _shop_unit(db: Session, code: str) -> Unit:
    u = db.scalar(select(Unit).where(Unit.code == code.strip().upper())) if re.fullmatch(r"[A-Za-z0-9\-]{4,30}", code or "") else None
    if not u or u.status != "launched":
        raise HTTPException(404, "This shop is not open")
    return u


@public.get("/shop/{code}")
def shop(code: str, lang: str = "te", db: Session = Depends(get_db)):
    u = _shop_unit(db, code)
    m = Masters(db)
    lang = lang if lang in ("en", "te") else "te"
    rows = db.scalars(select(Listing).where(Listing.unit_id == u.id, Listing.available.is_(True)).order_by(Listing.sort, Listing.id))
    s = unit_summary(db, u, 1)
    return {"code": u.code, "name": u.name, "model": (u.model.name_te or u.model.name_en) if u.model and lang == "te" else (u.model.name_en if u.model else None),
            "place": ", ".join(x for x in (m.name("village", u.village, lang), m.name("mandal", u.mandal, lang), m.name("district", u.district, lang)) if x),
            "rating": s["rating"], "ratings": s["ratings"], "listings": [listing_out(li, lang) for li in rows]}


@public.get("/shop/{code}/availability/{lid}")
def shop_availability(code: str, lid: int, db: Session = Depends(get_db)):
    u = _shop_unit(db, code)
    li = db.get(Listing, lid)
    if not li or li.unit_id != u.id:
        raise HTTPException(404, "Not found")
    return availability(db, li, date.today(), 14)


class PublicOrderIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    mobile: str
    village: Optional[str] = Field(default=None, max_length=120)
    lines: list[LineIn] = Field(min_length=1, max_length=20)
    date: Optional[dt.date] = None  # dt.date: a field named "date" would hide the type
    slot: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = Field(default=None, max_length=300)


@public.post("/shop/{code}/orders")
def shop_order(code: str, body: PublicOrderIn, db: Session = Depends(get_db)):
    u = _shop_unit(db, code)
    mobile = clean_mobile(body.mobile)
    c = db.scalar(select(Customer).where(Customer.mobile == mobile))
    if c:  # a few orders a day per mobile is plenty for a village shop
        recent = db.scalar(select(func.count()).select_from(Order).where(Order.customer_id == c.id, Order.source == "online",
                                                                        Order.created_at >= now() - timedelta(days=1)))
        if recent >= 5:
            raise HTTPException(429, "Too many orders from this number today. Please call the shop.")
    if body.date and body.date > date.today() + timedelta(days=60):
        raise HTTPException(422, "Choose a date in the next two months")
    o = build_order(db, u, OrderIn(customer=CustomerIn(name=body.name, mobile=mobile, village=body.village), lines=body.lines, date=body.date,
                                   slot=body.slot, status="new", address=body.address, note=body.note), None, "online", fixed_price=True)
    db.commit()
    return {"code": o.code, "amount": o.amount, "track_url": f"/track/{o.code}?t={o.track_token}", "token": o.track_token}


def _tracked(db: Session, code: str, t: str) -> Order:
    o = db.scalar(select(Order).where(Order.code == code)) if re.fullmatch(r"OR-\d{4}-\d{5,}", code or "") else None
    if not o or not t or o.track_token != t:
        raise HTTPException(404, "Order not found")
    return o


@public.get("/orders/{code}")
def track(code: str, t: str = "", lang: str = "te", db: Session = Depends(get_db)):
    o = _tracked(db, code, t)
    d = order_out(o, lang if lang in ("en", "te") else "te", full_mobile=False)
    d["unit"] = {"name": o.unit.name, "code": o.unit.code}
    d["can_rate"] = o.status in SALE_STATUSES and not o.rating
    d.pop("events")
    d["events"] = [{"status": e["status"], "label": status_label(e["status"], lang), "at": e["at"]} for e in o.events or []]
    return d


class RateIn(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=500)


@public.post("/orders/{code}/rate")
def rate(code: str, body: RateIn, t: str = "", db: Session = Depends(get_db)):
    o = _tracked(db, code, t)
    if o.status not in SALE_STATUSES:
        raise HTTPException(409, "You can rate after the order is delivered")
    if o.rating:
        raise HTTPException(409, "Already rated – thank you")
    o.rating, o.rating_comment = body.stars, (body.comment or "").strip() or None
    db.commit()
    return {"ok": True}


@public.get("/files/{name}")
def market_file(name: str, t: str = Query(min_length=10)):
    if not re.fullmatch(r"[0-9a-f]{32}\.(jpg|png|pdf)", name):
        raise HTTPException(404, "Not found")
    try:
        claims = jwt.decode(t, settings.JWT_SECRET, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(403, "Link expired") from e
    if claims.get("purpose") != "marketfile" or claims.get("f") != name:
        raise HTTPException(403, "Link not valid")
    p = FILE_DIR / name
    if not p.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})
