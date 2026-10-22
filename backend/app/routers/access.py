"""M14 – Users, roles and data scope; audit log; settings (readiness formula); DPDP data requests."""
import re
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, User
from ..models_p1 import DataRequest, Entrepreneur, MasterItem, Setting
from ..programme import readiness
from ..programme.export import person_export
from ..programme.service import delete_photo
from ..roles import ACCESS_ADMIN, ROLE_LABELS, STAFF_ROLES
from ..security import hash_secret, require_roles

router = APIRouter(prefix="/api/v1/admin", tags=["access"])
admin_only = require_roles(*ACCESS_ADMIN)
managers = require_roles("admin", "programme_manager")


def _now():
    return datetime.now(UTC).replace(tzinfo=None)


def _audit(db, user, action, entity, entity_id=None, detail=None):
    db.add(AuditLog(user_id=user.id, action=action, entity=entity, entity_id=entity_id, detail=detail))


# ---------------------------------------------------------------- staff users
class StaffIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=190)
    role: str
    districts: list[str] = []
    sectors: list[str] = []
    active: bool = True
    password: Optional[str] = Field(default=None, min_length=8, max_length=72)
    phone: Optional[str] = Field(default=None, max_length=15)  # contact number shown to entrepreneurs (mentors); not a login

    @field_validator("phone")
    @classmethod
    def v_phone(cls, v):
        v = re.sub(r"\D", "", v or "")[-10:]
        if v and not re.fullmatch(r"[6-9]\d{9}", v):
            raise ValueError("Enter a 10-digit mobile number")
        return v or None

    @field_validator("email")
    @classmethod
    def v_email(cls, v):
        v = v.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("role")
    @classmethod
    def v_role(cls, v):
        if v not in STAFF_ROLES:
            raise ValueError("Unknown role")
        return v


def _staff_out(u: User) -> dict:
    sc = u.scope or {}
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "role_label": ROLE_LABELS.get(u.role, u.role),
            "districts": sc.get("districts", []), "sectors": sc.get("sectors", []), "phone": sc.get("phone"), "active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None}


@router.get("/roles")
def roles(_: User = Depends(require_roles(*STAFF_ROLES))):
    return [{"role": k, "label": v} for k, v in ROLE_LABELS.items()]


@router.get("/staff")
def list_staff(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).where(User.role.in_(STAFF_ROLES)).order_by(User.role, User.name))
    return [_staff_out(u) for u in rows]


def _check_scope(db: Session, body: StaffIn):
    known_d = set(db.scalars(select(MasterItem.code).where(MasterItem.kind == "district")))
    known_s = set(db.scalars(select(MasterItem.code).where(MasterItem.kind == "sector")))
    bad = [d for d in body.districts if d not in known_d] + [s for s in body.sectors if s not in known_s]
    if bad:
        raise HTTPException(422, f"Unknown district or sector: {', '.join(bad)}")


@router.post("/staff")
def create_staff(body: StaffIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    if not body.password:
        raise HTTPException(422, "Set a password of at least 8 characters")
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "This email already has a login")
    _check_scope(db, body)
    u = User(name=body.name, email=body.email, role=body.role, password_hash=hash_secret(body.password), is_active=body.active,
             scope={"districts": body.districts, "sectors": body.sectors, "phone": body.phone})
    db.add(u)
    db.flush()
    _audit(db, user, "staff_create", "user", u.id, {"role": body.role, "districts": body.districts, "sectors": body.sectors})
    db.commit()
    return _staff_out(u)


@router.put("/staff/{uid}")
def update_staff(uid: int, body: StaffIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u or u.role not in STAFF_ROLES:
        raise HTTPException(404, "Staff user not found")
    if u.id == user.id and (body.role != "admin" or not body.active):
        raise HTTPException(422, "You cannot remove your own admin access")
    clash = db.scalar(select(User).where(User.email == body.email, User.id != u.id))
    if clash:
        raise HTTPException(409, "This email already has a login")
    _check_scope(db, body)
    before = _staff_out(u)
    u.name, u.email, u.role, u.is_active = body.name, body.email, body.role, body.active
    u.scope = {"districts": body.districts, "sectors": body.sectors, "phone": body.phone}
    if body.password:
        u.password_hash = hash_secret(body.password)
    _audit(db, user, "staff_update", "user", u.id, {"before": {k: before[k] for k in ("role", "districts", "sectors", "active")},
                                                    "after": {"role": body.role, "districts": body.districts, "sectors": body.sectors,
                                                              "active": body.active}, "password_reset": bool(body.password)})
    db.commit()
    return _staff_out(u)


# ---------------------------------------------------------------- audit log
@router.get("/audit")
def audit_log(action: Optional[str] = None, entity: Optional[str] = None, user_id: Optional[int] = None, q: Optional[str] = None,
              page: int = Query(1, ge=1), _: User = Depends(managers), db: Session = Depends(get_db)):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity:
        stmt = stmt.where(AuditLog.entity.like(f"{entity}%"))
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(db.scalars(stmt.order_by(AuditLog.id.desc()).offset((page - 1) * 50).limit(50)))
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.user_id for r in rows if r.user_id})))}
    actions = list(db.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action)))
    return {"total": total, "page": page, "actions": actions, "rows": [
        {"id": r.id, "at": r.created_at.isoformat() if r.created_at else None, "action": r.action, "entity": r.entity, "entity_id": r.entity_id,
         "detail": r.detail, "user": (users[r.user_id].name or users[r.user_id].email or users[r.user_id].mobile) if r.user_id in users else None,
         "user_role": users[r.user_id].role if r.user_id in users else None} for r in rows]}


# ---------------------------------------------------------------- readiness formula
@router.get("/settings/readiness")
def get_formula(_: User = Depends(require_roles(*STAFF_ROLES)), db: Session = Depends(get_db)):
    s = db.get(Setting, "readiness_formula")
    return s.value if s else readiness.default_formula()


@router.put("/settings/readiness")
def set_formula(body: dict, user: User = Depends(managers), db: Session = Depends(get_db)):
    try:
        readiness.validate_formula(body)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    # Bands are matched from the highest score down, so keep them sorted.
    body["bands"] = sorted(body.get("bands") or readiness.default_formula()["bands"], key=lambda b: -b[0])
    s = db.get(Setting, "readiness_formula")
    body["version"] = int((s.value or {}).get("version", 1)) + 1 if s else 1
    if s:
        s.value = body
    else:
        db.add(Setting(key="readiness_formula", value=body))
    _audit(db, user, "readiness_formula_update", "setting", None, {"version": body["version"]})
    db.commit()
    return body


@router.post("/settings/readiness/reset")
def reset_formula(user: User = Depends(managers), db: Session = Depends(get_db)):
    f = readiness.default_formula()
    s = db.get(Setting, "readiness_formula")
    f["version"] = int((s.value or {}).get("version", 1)) + 1 if s else 1
    if s:
        s.value = f
    else:
        db.add(Setting(key="readiness_formula", value=f))
    _audit(db, user, "readiness_formula_reset", "setting")
    db.commit()
    return f


# ---------------------------------------------------------------- DPDP data requests
def _req_out(r: DataRequest, db: Session) -> dict:
    e = db.scalar(select(Entrepreneur).where(Entrepreneur.user_id == r.user_id)) if r.user_id else None
    return {"id": r.id, "kind": r.kind, "status": r.status, "reason": r.reason, "resolution": r.resolution, "mobile": r.mobile,
            "name": e.full_name if e else None, "created_at": r.created_at.isoformat() if r.created_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None}


@router.get("/data-requests")
def data_requests(status: Optional[str] = "open", _: User = Depends(admin_only), db: Session = Depends(get_db)):
    stmt = select(DataRequest).order_by(DataRequest.id.desc())
    if status:
        stmt = stmt.where(DataRequest.status == status)
    return [_req_out(r, db) for r in db.scalars(stmt.limit(300))]


@router.get("/data-requests/{rid}/export")
def data_request_export(rid: int, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    r = db.get(DataRequest, rid)
    if not r or not r.user_id:
        raise HTTPException(404, "Request not found or the account no longer exists")
    _audit(db, user, "data_export_admin", "data_request", r.id)
    db.commit()
    return person_export(db, db.get(User, r.user_id))


class ResolveIn(BaseModel):
    action: str = Field(pattern="^(done|reject|erase)$")
    note: str = Field(min_length=3, max_length=1000)


@router.post("/data-requests/{rid}/resolve")
def resolve_request(rid: int, body: ResolveIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    """done = handled (e.g. export sent); reject = with reason; erase = delete the person's account and data now."""
    r = db.get(DataRequest, rid)
    if not r or r.status != "open":
        raise HTTPException(404, "Open request not found")
    if body.action == "erase":
        if r.kind != "delete":
            raise HTTPException(422, "Only deletion requests can erase data")
        target = db.get(User, r.user_id) if r.user_id else None
        if target:
            e = db.scalar(select(Entrepreneur).where(Entrepreneur.user_id == target.id))
            if e:
                for gm in e.memberships:  # the group keeps its record; this person's details are removed from it
                    gm.name, gm.mobile, gm.entrepreneur_id = "(removed on request)", None, None
                delete_photo(e.photo)
                from ..models_p2 import ExternalCertificate
                from ..training.service import cert_file_path
                for x in db.scalars(select(ExternalCertificate).where(ExternalCertificate.entrepreneur_id == e.id)):
                    if x.file:
                        cert_file_path(x.file).unlink(missing_ok=True)
                db.delete(e)
            db.flush()
            # The database removes the profile, conversations, documents and requests with the user (ON DELETE CASCADE).
            db.execute(text("DELETE FROM users WHERE id = :id"), {"id": target.id})
        r.user_id = None
        r.status = "done"
    else:
        r.status = "done" if body.action == "done" else "rejected"
    r.resolution, r.resolved_by_id, r.resolved_at = body.note, user.id, _now()
    _audit(db, user, f"data_request_{body.action}", "data_request", r.id, {"kind": r.kind, "mobile": r.mobile})
    db.commit()
    return _req_out(r, db)
