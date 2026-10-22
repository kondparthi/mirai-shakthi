"""Shared logic for marketing, sales & orders (M8): who may use a unit's shop, customers, availability, outputs, files."""
from __future__ import annotations

import re
import secrets
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import User
from ..models_p1 import Entrepreneur, GroupMember
from ..models_p4 import Unit
from ..models_p5 import ORDER_STATUS, Customer, Listing, Order
from ..programme.service import STORAGE
from ..roles import SETUP_READ
from ..security import ALGO
from ..setup.service import can_see_unit

FILE_DIR = STORAGE / "market"
MARKET_WRITE = ("admin", "programme_manager", "coordinator", "federation_staff", "mentor")
SALE_STATUSES = ("delivered", "paid")


def now():
    return datetime.now(UTC).replace(tzinfo=None)


# ---------------------------------------------------------------- access
def my_unit_ids(db: Session, user: User) -> set[int]:
    """Units the entrepreneur runs: their own, or their group's."""
    e = db.scalar(select(Entrepreneur).where(Entrepreneur.user_id == user.id))
    if not e:
        return set()
    gids = [gm.group_id for gm in db.scalars(select(GroupMember).where(GroupMember.entrepreneur_id == e.id))]
    q = select(Unit.id).where((Unit.entrepreneur_id == e.id) | (Unit.group_id.in_(gids or [0])))
    return set(db.scalars(q))


def unit_access(db: Session, user: User, uid: int, write: bool = False) -> Unit:
    u = db.get(Unit, uid)
    if not u:
        raise HTTPException(404, "Unit not found")
    if user.role == "msme":
        if uid not in my_unit_ids(db, user):
            raise HTTPException(404, "Unit not found")
        return u
    if user.role not in SETUP_READ or not can_see_unit(user, u):
        raise HTTPException(404, "Unit not found")
    if write and user.role not in MARKET_WRITE:
        raise HTTPException(403, "You do not have access to this")
    return u


# ---------------------------------------------------------------- customers
def clean_mobile(v: str) -> str:
    v = re.sub(r"\D", "", v or "")[-10:]
    if not re.fullmatch(r"[6-9]\d{9}", v):
        raise HTTPException(422, "Enter the customer's 10-digit mobile number")
    return v


def upsert_customer(db: Session, mobile: str, name: str, kind: str | None = None, village: str | None = None,
                    district: str | None = None, organisation: str | None = None) -> Customer:
    mobile = clean_mobile(mobile)
    c = db.scalar(select(Customer).where(Customer.mobile == mobile))
    name = " ".join((name or "").split())[:120]
    if len(name) < 2:
        raise HTTPException(422, "Enter the customer's name")
    if not c:
        c = Customer(mobile=mobile, name=name, kind=kind or "household", village=village, district=district, organisation=organisation, created_at=now())
        db.add(c)
        db.flush()
    else:  # fill gaps, keep what is known
        c.name = name or c.name
        c.kind = kind or c.kind
        c.village = village or c.village
        c.district = district or c.district
        c.organisation = organisation or c.organisation
    return c


def masked(mobile: str) -> str:
    return f"{mobile[:2]}xxxxxx{mobile[-2:]}"


# ---------------------------------------------------------------- availability
def booked(db: Session, listing_id: int, day: date, slot: str | None) -> float:
    total = 0.0
    for o in db.scalars(select(Order).where(Order.date == day, Order.status != "cancelled", Order.kind == "booking")):
        for ln in o.lines:
            if ln.get("listing_id") == listing_id and (slot is None or o.slot == slot):
                total += float(ln.get("qty") or 0)
    return total


def remaining(db: Session, li: Listing, day: date, slot: str | None) -> float | None:
    """None = no limit."""
    if li.slots:
        s = next((x for x in li.slots if x.get("label") == slot), None)
        if not s:
            raise HTTPException(422, "Choose one of the time slots")
        cap = s.get("capacity")
        return None if cap in (None, "") else float(cap) - booked(db, li.id, day, slot)
    if li.daily_capacity:
        return float(li.daily_capacity) - booked(db, li.id, day, None)
    return None


def availability(db: Session, li: Listing, start: date, days: int) -> list[dict]:
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        if li.slots:
            out.append({"date": d.isoformat(), "slots": [{"label": s["label"], "left": remaining(db, li, d, s["label"])} for s in li.slots]})
        else:
            out.append({"date": d.isoformat(), "slots": [{"label": None, "left": remaining(db, li, d, None)}]})
    return out


# ---------------------------------------------------------------- files
def save_photo(data: bytes) -> str:
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "The photo is larger than 10 MB")
    import io

    from PIL import Image, ImageOps

    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        im.thumbnail((1200, 1200))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=82)
    except Exception as exc:
        raise HTTPException(422, "Upload a photo (JPG / PNG)") from exc
    return save_bytes(buf.getvalue(), ".jpg")


def save_bytes(data: bytes, ext: str) -> str:
    FILE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (FILE_DIR / name).write_bytes(data)
    return name


def file_url(name: str | None) -> str | None:
    """Product photos and posters are public (they appear on the shop page), so the link does not expire quickly."""
    if not name:
        return None
    token = jwt.encode({"purpose": "marketfile", "f": name, "exp": datetime.now(UTC) + timedelta(days=30)}, settings.JWT_SECRET, algorithm=ALGO)
    return f"/api/v1/public/files/{name}?t={token}"


def shop_url(u: Unit) -> str:
    return f"{settings.PUBLIC_URL.rstrip('/')}/#/shop/{u.code}"


def new_token() -> str:
    return secrets.token_urlsafe(12)


def track_url(o: Order) -> str:
    return f"{settings.PUBLIC_URL.rstrip('/')}/#/track/{o.code}?t={o.track_token}"


def wa_link(mobile: str, text: str) -> str:
    from urllib.parse import quote

    return f"https://wa.me/91{mobile}?text={quote(text)}"


# ---------------------------------------------------------------- outputs
def listing_out(li: Listing, lang: str = "en") -> dict:
    return {"id": li.id, "unit_id": li.unit_id, "kind": li.kind, "name": li.name, "name_te": li.name_te,
            "label": (li.name_te or li.name) if lang == "te" else li.name, "description": li.description,
            "photos": [{"name": p, "url": file_url(p)} for p in li.photos or []], "price": li.price, "price_unit": li.price_unit,
            "available": li.available, "daily_capacity": li.daily_capacity, "slots": li.slots or [], "sort": li.sort}


def status_label(s: str, lang: str = "en") -> str:
    v = ORDER_STATUS.get(s, (s, s))
    return v[1] if lang == "te" else v[0]


def order_out(o: Order, lang: str = "en", full_mobile: bool = True) -> dict:
    c = o.customer
    return {"id": o.id, "code": o.code, "unit_id": o.unit_id, "kind": o.kind, "lines": o.lines, "amount": o.amount,
            "date": o.date.isoformat() if o.date else None, "slot": o.slot, "status": o.status, "status_label": status_label(o.status, lang),
            "payment_mode": o.payment_mode, "paid_on": o.paid_on.isoformat() if o.paid_on else None, "source": o.source,
            "campaign_id": o.campaign_id, "address": o.address, "note": o.note, "cancel_reason": o.cancel_reason,
            "rating": o.rating, "rating_comment": o.rating_comment, "events": o.events or [],
            "customer": {"id": c.id, "name": c.name, "mobile": c.mobile if full_mobile else masked(c.mobile), "kind": c.kind,
                         "village": c.village, "organisation": c.organisation},
            "outstanding": o.status == "delivered", "created_at": o.created_at.isoformat() if o.created_at else None}


def unit_summary(db: Session, u: Unit, days: int = 30) -> dict:
    today = date.today()
    orders = list(db.scalars(select(Order).where(Order.unit_id == u.id)))
    sales = [o for o in orders if o.status in SALE_STATUSES]

    def day_of(o: Order) -> date:
        return o.paid_on or o.date or o.created_at.date()

    by_day: dict[str, float] = defaultdict(float)
    for o in sales:
        if day_of(o) >= today - timedelta(days=days - 1):
            by_day[day_of(o).isoformat()] += o.amount
    items: dict[str, float] = defaultdict(float)
    for o in sales:
        for ln in o.lines:
            items[ln.get("name", "?")] += float(ln.get("qty") or 0) * float(ln.get("price") or 0)
    rated = [o.rating for o in orders if o.rating]
    month = [o for o in sales if day_of(o).year == today.year and day_of(o).month == today.month]
    custs = {o.customer_id for o in sales}
    repeat = {cid for cid in custs if sum(1 for o in sales if o.customer_id == cid) > 1}
    return {
        "today": round(sum(o.amount for o in sales if day_of(o) == today), 2),
        "month": round(sum(o.amount for o in month), 2), "month_orders": len(month),
        "new_orders": sum(1 for o in orders if o.status == "new"),
        "upcoming_bookings": sum(1 for o in orders if o.kind == "booking" and o.status in ("new", "confirmed") and o.date and o.date >= today),
        "outstanding": round(sum(o.amount for o in orders if o.status == "delivered"), 2),
        "customers": len(custs), "repeat_customers": len(repeat),
        "rating": round(sum(rated) / len(rated), 1) if rated else None, "ratings": len(rated),
        "daily": [{"date": (today - timedelta(days=i)).isoformat(), "amount": round(by_day.get((today - timedelta(days=i)).isoformat(), 0.0), 2)}
                  for i in range(days - 1, -1, -1)],
        "top_items": [{"name": k, "amount": round(v, 2)} for k, v in sorted(items.items(), key=lambda x: -x[1])[:6]],
    }
