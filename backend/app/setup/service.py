"""Shared logic for enterprise set-up (M7): units, readiness checklist, supplier matching, outputs and files."""
from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import User
from ..models_p1 import GroupMember
from ..models_p2 import ExternalCertificate, Trainee
from ..models_p3 import Dpr
from ..models_p4 import PAYMENT_SOURCES, PURCHASE_STATUS, REGISTRATIONS, Asset, Purchase, Quotation, Registration, Supplier, Unit
from ..programme.service import STORAGE, Masters, can_see
from ..roles import ALL_SCOPE
from ..security import ALGO

FILE_DIR = STORAGE / "setup"
TYPES = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
STANDARD_ITEMS = [
    ("equipment", "Equipment installed and tested", "auto"),
    ("registrations", "Registrations done", "auto"),
    ("training", "Training completed (certificate)", "auto"),
    ("working_capital", "Working capital available", "manual"),
    ("bookkeeping", "Bookkeeping set up in the app", "manual"),
]
STANDARD_TE = {
    "equipment": "పరికరాలు అమర్చి పరీక్షించారు", "registrations": "నమోదులు పూర్తయ్యాయి", "training": "శిక్షణ పూర్తయింది (సర్టిఫికేట్)",
    "working_capital": "వర్కింగ్ క్యాపిటల్ అందుబాటులో ఉంది", "bookkeeping": "యాప్‌లో లెక్కల నిర్వహణ ఏర్పాటు",
}


def now():
    return datetime.now(UTC).replace(tzinfo=None)


# ---------------------------------------------------------------- scope
def owner(u: Unit):
    return u.entrepreneur or u.group


def can_see_unit(user: User, u: Unit) -> bool:
    if user.role in ALL_SCOPE:
        return True
    o = owner(u)
    if o is not None and can_see(user, o):
        return True
    districts = (user.scope or {}).get("districts") or []
    return u.district in districts if districts else u.created_by_id == user.id


def get_unit(db: Session, user: User, uid: int) -> Unit:
    u = db.get(Unit, uid)
    if not u or not can_see_unit(user, u):
        raise HTTPException(404, "Unit not found")
    return u


def get_purchase(db: Session, user: User, pid: int) -> Purchase:
    p = db.get(Purchase, pid)
    if not p or not can_see_unit(user, p.unit):
        raise HTTPException(404, "Purchase not found")
    return p


# ---------------------------------------------------------------- unit creation
def _external(db: Session, entrepreneur_ids: list[int], kind: str) -> ExternalCertificate | None:
    if not entrepreneur_ids:
        return None
    return db.scalar(select(ExternalCertificate).where(ExternalCertificate.entrepreneur_id.in_(entrepreneur_ids), ExternalCertificate.kind == kind,
                                                        ExternalCertificate.status == "verified").limit(1))


def people(u: Unit) -> list[int]:
    """Entrepreneur ids behind the unit (the person, or the group's enrolled members)."""
    if u.entrepreneur_id:
        return [u.entrepreneur_id]
    if u.group:
        return [m.entrepreneur_id for m in u.group.members if m.entrepreneur_id]
    return []


def ensure_unit(db: Session, d: Dpr, user: User | None) -> Unit:
    """The unit for an approved DPR (one per DPR). Registrations come from the enterprise model; a verified DGCA RPC or FSSAI
    certificate uploaded in training counts as done."""
    u = db.scalar(select(Unit).where(Unit.dpr_id == d.id))
    if u:
        return u
    u = Unit(entrepreneur_id=d.entrepreneur_id, group_id=d.group_id, dpr_id=d.id, model_id=d.model_id, name=d.unit_name, district=d.district,
             mandal=d.mandal, village=d.village, address=d.address, lat=d.lat, lng=d.lng, readiness={}, created_by_id=user.id if user else None,
             created_at=now(), updated_at=now())
    u.entrepreneur, u.group, u.dpr, u.model = d.entrepreneur, d.group, d, d.model
    db.add(u)
    db.flush()
    u.code = f"U-{date.today().year}-{u.id:05d}"
    ids = people(u)
    for kind in (d.model.registrations if d.model and d.model.registrations else ["udyam"]):
        r = Registration(unit_id=u.id, kind=kind, status="todo")
        ext = _external(db, ids, {"rpc": "dgca_rpc", "fssai": "fssai"}.get(kind, "-"))
        if ext:
            r.status, r.number, r.issued_on, r.note = "done", ext.number, ext.issued_on, "Verified certificate from training"
        db.add(r)
    db.flush()
    return u


# ---------------------------------------------------------------- readiness (Form 7.3)
def checklist(db: Session, u: Unit, lang: str = "en") -> list[dict]:
    live = [p for p in u.purchases if p.status != "cancelled"]
    regs = [r for r in u.registrations]
    ids = people(u)
    cert = db.scalar(select(Trainee).where(Trainee.entrepreneur_id.in_(ids), Trainee.certificate_no.is_not(None)).limit(1)) if ids else None
    ext = db.scalar(select(ExternalCertificate).where(ExternalCertificate.entrepreneur_id.in_(ids), ExternalCertificate.status == "verified").limit(1)) if ids else None
    # Equipment: every purchase installed, and every DPR item either installed through a purchase or in the asset register.
    names = {norm(i.get("item", "")): i["item"] for i in ((u.dpr.inputs or {}).get("capital_items") or [] if u.dpr else []) if i.get("item")}
    planned = set(names)
    have = {norm(i["item"]) for p in live if p.status == "installed" for i in p.items} | {norm(a.item) for a in u.assets}
    missing = sorted(planned - have)
    eq_done = bool(live or u.assets) and all(p.status == "installed" for p in live) and not missing
    left = f" – still to come: {', '.join(names[x] for x in missing[:3])}{' …' if len(missing) > 3 else ''}" if missing else ""
    eq_note = (f"{len(planned) - len(missing)} of {len(planned)} DPR items in place{left}" if planned else
               f"{sum(p.status == 'installed' for p in live)} of {len(live)} purchases installed") if (live or u.assets) else "No purchase yet"
    auto = {
        "equipment": (eq_done, eq_note),
        "registrations": (bool(regs) and all(r.status in ("done", "not_needed") for r in regs),
                          f"{sum(r.status in ('done', 'not_needed') for r in regs)} of {len(regs)} done"),
        "training": (bool(cert or ext), f"Certificate {cert.certificate_no}" if cert else (ext.title if ext else "No certificate yet")),
    }
    out = []
    for key, label, kind in STANDARD_ITEMS:
        st = (u.readiness or {}).get(key) or {}
        done, note = auto[key] if kind == "auto" else (bool(st.get("done")), st.get("note"))
        out.append({"key": key, "label": STANDARD_TE[key] if lang == "te" else label, "kind": kind, "done": done, "note": note,
                    "photo": st.get("photo"), "photo_url": file_link(st.get("photo")), "at": st.get("at"), "by": st.get("by")})
    for i, label in enumerate((u.model.readiness_items if u.model and u.model.readiness_items else [])):
        key = f"m{i}_{re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_')[:24]}"
        st = (u.readiness or {}).get(key) or {}
        out.append({"key": key, "label": label, "kind": "manual", "done": bool(st.get("done")), "note": st.get("note"),
                    "photo": st.get("photo"), "photo_url": file_link(st.get("photo")), "at": st.get("at"), "by": st.get("by")})
    return out


# ---------------------------------------------------------------- suppliers
def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def supplier_matches(s: Supplier, items: list[str], district: str | None, model_code: str | None) -> list[str]:
    """Purchase items this supplier deals in (exact or contained name, or the supplier lists the unit's model)."""
    if s.districts and district and district not in s.districts:
        return []
    have = [norm(x) for x in s.items or []]
    hits = [i for i in items if any(norm(i) == h or (len(h) > 4 and (h in norm(i) or norm(i) in h)) for h in have)]
    return hits


def rate_for(s: Supplier, item: str) -> float | None:
    for r in s.rate_card or []:
        if norm(r.get("item", "")) == norm(item):
            v = r.get("valid_till")
            if not v or date.fromisoformat(v) >= date.today():
                return r.get("rate")
    return None


def supplier_out(s: Supplier, db: Session | None = None, full: bool = False, stats: dict | None = None) -> dict:
    d = {"id": s.id, "name": s.name, "gstin": s.gstin, "contact_name": s.contact_name, "mobile": s.mobile, "email": s.email,
         "address": s.address, "categories": s.categories or [], "items": s.items or [], "models": s.models or [], "districts": s.districts or [],
         "rate_card": s.rate_card or [], "approved": s.approved, "note": s.note, "has_login": bool(s.user_id),
         "sample": s.name.startswith("Sample:")}
    if stats is not None:
        d |= stats.get(s.id, {"orders": 0, "delivered": 0, "on_time": 0, "value": 0.0})
    if full and db and s.user_id:
        u = db.get(User, s.user_id)
        d["login_email"] = u.email if u else None
    return d


def supplier_stats(db: Session) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for p in db.scalars(select(Purchase).where(Purchase.selected_quote_id.is_not(None), Purchase.status != "cancelled")):
        q = db.get(Quotation, p.selected_quote_id)
        if not q:
            continue
        st = out.setdefault(q.supplier_id, {"orders": 0, "delivered": 0, "on_time": 0, "value": 0.0})
        st["orders"] += 1
        st["value"] += p.po_amount or 0
        if p.delivered_on:
            st["delivered"] += 1
            if not p.expected_delivery or p.delivered_on <= p.expected_delivery:
                st["on_time"] += 1
    return out


# ---------------------------------------------------------------- files
def save_file(data: bytes, content_type: str, images_only: bool = False) -> str:
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "The file is larger than 10 MB")
    ext = TYPES.get((content_type or "").split(";")[0])
    if not ext or (images_only and ext == ".pdf") or (ext == ".pdf" and not data.startswith(b"%PDF")):
        raise HTTPException(422, "Upload a photo (JPG / PNG)" if images_only else "Upload a PDF or a photo (JPG / PNG)")
    FILE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    if ext != ".pdf":  # shrink big phone photos
        try:
            import io

            from PIL import Image, ImageOps

            im = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
            im.thumbnail((1600, 1600))
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=82)
            data, name = buf.getvalue(), name.rsplit(".", 1)[0] + ".jpg"
        except Exception as exc:
            raise HTTPException(422, "This photo could not be read") from exc
    (FILE_DIR / name).write_bytes(data)
    return name


def file_link(name: str | None) -> str | None:
    if not name:
        return None
    token = jwt.encode({"purpose": "setupfile", "f": name, "exp": datetime.now(UTC) + timedelta(minutes=60)}, settings.JWT_SECRET, algorithm=ALGO)
    return f"/api/v1/setup/files/{name}?t={token}"


def file_path(name: str) -> Path:
    return FILE_DIR / name


def po_link(pid: int) -> str:
    token = jwt.encode({"purpose": "po", "p": pid, "exp": datetime.now(UTC) + timedelta(minutes=10)}, settings.JWT_SECRET, algorithm=ALGO)
    return f"/api/v1/setup/files/po/{pid}.pdf?t={token}"


# ---------------------------------------------------------------- outputs
def owner_out(m: Masters, u) -> dict:
    if u.entrepreneur:
        e = u.entrepreneur
        return {"type": "entrepreneur", "id": e.id, "name": e.full_name, "mobile": e.mobile, "stage": e.stage}
    if u.group:
        return {"type": "group", "id": u.group.id, "name": u.group.name, "mobile": None, "stage": u.group.stage}
    return {"type": None, "id": None, "name": "—"}


def quote_out(q: Quotation, lowest: float | None, estimate: float) -> dict:
    return {"id": q.id, "supplier_id": q.supplier_id, "supplier": q.supplier.name, "lines": q.lines, "amount": q.amount,
            "gst_included": q.gst_included, "delivery_days": q.delivery_days, "warranty_months": q.warranty_months,
            "valid_till": q.valid_till.isoformat() if q.valid_till else None, "file_url": file_link(q.file), "note": q.note, "source": q.source,
            "lowest": lowest is not None and abs(q.amount - lowest) < 0.5,
            "vs_estimate_pct": round((q.amount - estimate) / estimate * 100, 1) if estimate else None,
            "at": q.created_at.isoformat() if q.created_at else None}


def purchase_out(db: Session, p: Purchase, full: bool = False) -> dict:
    estimate = sum(float(i.get("qty") or 0) * float(i.get("est_rate") or 0) for i in p.items or [])
    quotes = list(p.quotes)
    lowest = min((q.amount for q in quotes), default=None)
    sel = next((q for q in quotes if q.id == p.selected_quote_id), None)
    d = {"id": p.id, "unit_id": p.unit_id, "title": p.title, "items": p.items, "estimate": round(estimate, 2), "status": p.status,
         "status_label": PURCHASE_STATUS.get(p.status, p.status), "invited": p.invited or [], "quote_by": p.quote_by.isoformat() if p.quote_by else None,
         "quotes_count": len(quotes), "lowest": lowest, "supplier": sel.supplier.name if sel else None, "supplier_id": sel.supplier_id if sel else None,
         "selected_quote_id": p.selected_quote_id, "selection_reason": p.selection_reason, "po_number": p.po_number,
         "po_date": p.po_date.isoformat() if p.po_date else None, "po_amount": p.po_amount, "payment_source": p.payment_source,
         "payment_label": PAYMENT_SOURCES.get(p.payment_source or "", None),
         "expected_delivery": p.expected_delivery.isoformat() if p.expected_delivery else None,
         "supplier_confirmed": bool(p.supplier_confirmed_at), "delivered_on": p.delivered_on.isoformat() if p.delivered_on else None,
         "installed_on": p.installed_on.isoformat() if p.installed_on else None, "handover_note": p.handover_note,
         "late": bool(p.expected_delivery and not p.delivered_on and p.expected_delivery < date.today() and p.status == "ordered"),
         "photos": [{"url": file_link(x["file"]), "caption": x.get("caption"), "at": x.get("at")} for x in p.photos or []]}
    if full:
        d["quotes"] = [quote_out(q, lowest, estimate) for q in quotes]
        names = {s.id: s.name for s in db.scalars(select(Supplier).where(Supplier.id.in_(p.invited or [0])))}
        d["invited_suppliers"] = [{"id": i, "name": names.get(i, "?"), "quoted": any(q.supplier_id == i for q in quotes)} for i in p.invited or []]
    return d


def registration_out(r: Registration, lang: str = "en") -> dict:
    lab = REGISTRATIONS.get(r.kind, (r.kind, r.kind))
    return {"id": r.id, "kind": r.kind, "label": lab[1] if lang == "te" else lab[0], "status": r.status, "number": r.number,
            "applied_on": r.applied_on.isoformat() if r.applied_on else None, "issued_on": r.issued_on.isoformat() if r.issued_on else None,
            "valid_until": r.valid_until.isoformat() if r.valid_until else None, "file_url": file_link(r.file), "note": r.note,
            "expiring": bool(r.valid_until and r.valid_until <= date.today() + timedelta(days=60))}


def asset_out(a: Asset, suppliers: dict[int, str] | None = None) -> dict:
    return {"id": a.id, "item": a.item, "spec": a.spec, "qty": a.qty, "value": a.value, "serial_no": a.serial_no,
            "warranty_until": a.warranty_until.isoformat() if a.warranty_until else None, "insurance_policy": a.insurance_policy,
            "insurance_until": a.insurance_until.isoformat() if a.insurance_until else None, "shared": a.shared, "status": a.status,
            "photo_url": file_link(a.photo), "purchase_id": a.purchase_id, "supplier": (suppliers or {}).get(a.supplier_id)}


def progress(db: Session, u: Unit) -> dict:
    items = checklist(db, u)
    return {"done": sum(1 for i in items if i["done"]), "total": len(items)}


def unit_out(db: Session, u: Unit, m: Masters | None = None, full: bool = False, lang: str = "en") -> dict:
    m = m or Masters(db)
    live = [p for p in u.purchases if p.status != "cancelled"]
    items = checklist(db, u, lang)
    d = {"id": u.id, "code": u.code, "name": u.name, "owner": owner_out(m, u), "status": u.status, "dpr_id": u.dpr_id,
         "dpr_code": u.dpr.code if u.dpr else None, "model": (u.model.name_te or u.model.name_en) if u.model and lang == "te" else (u.model.name_en if u.model else None),
         "model_code": u.model.code if u.model else None, "district": u.district, "district_name": m.name("district", u.district, lang),
         "location": ", ".join(x for x in (u.address, m.name("village", u.village, lang), m.name("mandal", u.mandal, lang), m.name("district", u.district, lang)) if x),
         "launch_date": u.launch_date.isoformat() if u.launch_date else None,
         "readiness": {"done": sum(1 for i in items if i["done"]), "total": len(items)},
         "purchases": {"total": len(live), "installed": sum(p.status == "installed" for p in live), "ordered_value": round(sum(p.po_amount or 0 for p in live), 2)},
         "registrations": {"total": len(u.registrations), "done": sum(r.status in ("done", "not_needed") for r in u.registrations)},
         "created_at": u.created_at.isoformat() if u.created_at else None, "updated_at": u.updated_at.isoformat() if u.updated_at else None}
    if full:
        sup = {s.id: s.name for s in db.scalars(select(Supplier))}
        d |= {"mandal": u.mandal, "village": u.village, "address": u.address, "checklist": items,
              "purchase_list": [purchase_out(db, p) for p in u.purchases], "assets": [asset_out(a, sup) for a in u.assets],
              "registration_list": [registration_out(r, lang) for r in u.registrations],
              "dpr_items": [{"item": i.get("item"), "spec": i.get("spec"), "qty": i.get("qty"), "est_rate": i.get("rate")}
                            for i in ((u.dpr.inputs or {}).get("capital_items") or [] if u.dpr else [])],
              "is_group": bool(u.group_id), "members": [{"name": gm.name, "role": gm.role} for gm in (u.group.members if u.group else [])]}
    return d


def group_members(db: Session, gid: int) -> list[GroupMember]:
    return list(db.scalars(select(GroupMember).where(GroupMember.group_id == gid)))
