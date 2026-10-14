"""M1 – Self-enrolment for entrepreneurs (role msme): Form 1.1, photo, self readiness check, and DPDP rights."""
from datetime import UTC, datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, User
from ..models_p1 import DataRequest, Entrepreneur
from ..programme import readiness
from ..programme.export import person_export
from ..programme.service import EntrepreneurIn, Masters, apply_entrepreneur, delete_photo, entrepreneur_out, find_duplicates, save_photo
from ..security import require_roles
from .auth import CONSENT_VERSION
from .programme import ReadinessIn, _assessment_out, _formula, record_readiness

router = APIRouter(prefix="/api/v1/enrol", tags=["enrol"])
msme = require_roles("msme")


def _now():
    return datetime.now(UTC).replace(tzinfo=None)


def _lg(user: User, lang: Optional[str]) -> str:
    """The language the app is showing now (the toggle), else the one saved at login."""
    return lang if lang in ("en", "te") else (user.language or "en")


def _mine(db: Session, user: User) -> Entrepreneur | None:
    """The person's enrolment: linked by account, or an imported record waiting for them (same mobile)."""
    e = db.scalar(select(Entrepreneur).where(Entrepreneur.user_id == user.id))
    if not e and user.mobile:
        e = db.scalar(select(Entrepreneur).where(Entrepreneur.mobile == user.mobile))
        if e and e.user_id and e.user_id != user.id:
            return None
    return e


@router.get("/me")
def my_enrolment(lang: Optional[str] = None, user: User = Depends(msme), db: Session = Depends(get_db)):
    e = _mine(db, user)
    lang = _lg(user, lang)
    if not e:
        return {"enrolled": False, "needs_consent": True}
    d = entrepreneur_out(e, Masters(db), lang)
    d["assessments"] = [_assessment_out(a) for a in e.assessments]
    return {"enrolled": True, "needs_consent": not e.consent_at, "entrepreneur": d}


class SelfIn(EntrepreneurIn):
    consent: bool = False


@router.put("/me")
def save_enrolment(body: SelfIn, lang: Optional[str] = None, user: User = Depends(msme), db: Session = Depends(get_db)):
    m = Masters(db)
    m.check(body)
    e = _mine(db, user)
    if (not e or not e.consent_at) and not body.consent:
        raise HTTPException(422, "Please agree to the data consent to join the programme")
    dups = find_duplicates(db, None, body.aadhaar[-4:] if body.aadhaar else None, body.full_name, body.dob, exclude_id=e.id if e else None)
    if dups:
        raise HTTPException(409, "Someone with the same Aadhaar, name and date of birth is already enrolled. "
                                 "Please contact your MIRAI coordinator.")
    created = not e
    if created:
        e = Entrepreneur(mobile=user.mobile, source="self")
        db.add(e)
    e.user_id = user.id
    if not e.consent_at:
        e.consent_version, e.consent_at = CONSENT_VERSION, _now()
    apply_entrepreneur(e, body)
    if not user.name:
        user.name = body.full_name
    db.flush()
    db.add(AuditLog(user_id=user.id, action="enrol_self" if created else "enrol_self_update", entity="entrepreneur", entity_id=e.id))
    db.commit()
    db.refresh(e)
    return my_enrolment(lang, user, db)


@router.post("/me/photo")
async def my_photo(file: UploadFile = File(...), lang: Optional[str] = None, user: User = Depends(msme), db: Session = Depends(get_db)):
    e = _mine(db, user)
    if not e or not e.consent_at:
        raise HTTPException(422, "Please save your details first")
    name = save_photo(await file.read(8 * 1024 * 1024 + 1))
    old, e.photo = e.photo, name
    db.commit()
    delete_photo(old)
    return my_enrolment(lang, user, db)


@router.get("/readiness/form")
def readiness_form(lang: Optional[str] = None, user: User = Depends(msme), db: Session = Depends(get_db)):
    f = _formula(db)
    return {"version": f.get("version", 1), "questions": readiness.questions_for_form(f, _lg(user, lang))}


@router.post("/me/readiness")
def my_readiness(body: ReadinessIn, lang: Optional[str] = None, user: User = Depends(msme), db: Session = Depends(get_db)):
    e = _mine(db, user)
    if not e or not e.consent_at:
        raise HTTPException(422, "Please join the programme first")
    return record_readiness(db, user, body, e.investment_available, _lg(user, lang), entrepreneur=e)


# ---------------------------------------------------------------- DPDP rights
@router.get("/me/export")
def my_export(user: User = Depends(msme), db: Session = Depends(get_db)):
    db.add(AuditLog(user_id=user.id, action="data_export_self", entity="user", entity_id=user.id))
    db.commit()
    return person_export(db, user)


class RequestIn(BaseModel):
    kind: Literal["delete", "export"] = "delete"
    reason: Optional[str] = Field(default=None, max_length=1000)


@router.post("/me/data-request")
def data_request(body: RequestIn, user: User = Depends(msme), db: Session = Depends(get_db)):
    open_ = db.scalar(select(DataRequest).where(DataRequest.user_id == user.id, DataRequest.kind == body.kind,
                                                DataRequest.status == "open"))
    if open_:
        raise HTTPException(409, "You already have an open request. MIRAI will reply within 30 days.")
    r = DataRequest(user_id=user.id, mobile=user.mobile, kind=body.kind, reason=body.reason, created_at=_now())
    db.add(r)
    db.flush()
    db.add(AuditLog(user_id=user.id, action=f"data_request_{body.kind}", entity="data_request", entity_id=r.id))
    db.commit()
    return {"id": r.id, "kind": r.kind, "status": r.status}


@router.get("/me/data-requests")
def my_requests(user: User = Depends(msme), db: Session = Depends(get_db)):
    return [{"id": r.id, "kind": r.kind, "status": r.status, "reason": r.reason, "resolution": r.resolution,
             "at": r.created_at.isoformat() if r.created_at else None}
            for r in db.scalars(select(DataRequest).where(DataRequest.user_id == user.id).order_by(DataRequest.id.desc()))]
