"""M4 – training for entrepreneurs (app): my training, open batches, QR check-in, feedback, certificates,
external certificate upload; and the public certificate check used by the QR on every certificate."""
import re
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..models_p1 import Entrepreneur
from ..models_p2 import Attendance, Batch, BatchSession, ExternalCertificate, Trainee
from ..programme.service import Masters
from ..security import require_roles
from ..training.service import (attendance, audit, bump_stage, certificate_link, course_out, now, recommended_tracks, save_cert_file,
                                track_label, verify_url)
from .training import ext_cert_out

router = APIRouter(prefix="/api/v1/training/me", tags=["training-me"])
public = APIRouter(prefix="/api/v1/public", tags=["public"])
msme = require_roles("msme")


def _lg(user: User, lang: Optional[str]) -> str:
    return lang if lang in ("en", "te") else (user.language or "en")


def _me(db: Session, user: User) -> Entrepreneur:
    e = db.scalar(select(Entrepreneur).where(Entrepreneur.user_id == user.id))
    if not e or not e.consent_at:
        raise HTTPException(422, "Please join the MIRAI programme first")
    return e


def _open_batches(db: Session, e: Entrepreneur, taken: set[int]) -> list[Batch]:
    out = []
    for b in db.scalars(select(Batch).where(Batch.status == "open", Batch.end_date >= date.today()).order_by(Batch.start_date)):
        if b.id in taken:
            continue
        if b.mode != "online" and b.district != e.district:
            continue
        if sum(1 for t in b.trainees if t.status in ("confirmed", "completed")) >= b.seats:
            continue
        out.append(b)
    return out


@router.get("")
def my_training(lang: Optional[str] = None, user: User = Depends(msme), db: Session = Depends(get_db)):
    lg = _lg(user, lang)
    e = db.scalar(select(Entrepreneur).where(Entrepreneur.user_id == user.id))
    if not e or not e.consent_at:
        return {"enrolled": False}
    m = Masters(db)
    rec = recommended_tracks(db, e)
    mine = list(db.scalars(select(Trainee).where(Trainee.entrepreneur_id == e.id).order_by(Trainee.id.desc())))
    batches = []
    for t in mine:
        b = t.batch
        att, held, total = attendance(t, b)
        present = {a.session_id for s in b.sessions for a in s.attendance if a.trainee_id == t.id and a.present}
        batches.append({
            "trainee_id": t.id, "status": t.status, "batch_status": b.status, "code": b.code, "course": course_out(b.course, lg),
            "start_date": b.start_date.isoformat(), "end_date": b.end_date.isoformat(), "mode": b.mode, "venue": b.venue or b.host_unit,
            "district_name": m.name("district", b.district, lg), "attended": att, "held": held, "total": total,
            "attendance_pct": round(100 * att / total) if total else 0, "result": t.result, "certificate_no": t.certificate_no,
            "verify_url": verify_url(t) if t.certificate_no else None, "feedback_rating": t.feedback_rating,
            "sessions": [{"n": s.n, "date": s.date.isoformat() if s.date else None, "topic": (s.topic_te if lg == "te" and s.topic_te else s.topic),
                          "done": s.done, "present": s.id in present, "checkin_open": s.checkin_open and t.status == "confirmed"} for s in b.sessions],
        })
    taken = {t.batch_id for t in mine if t.status != "withdrawn"}
    open_ = sorted(_open_batches(db, e, taken), key=lambda b: (b.course.track not in rec, b.start_date))
    return {
        "enrolled": True, "stage": e.stage,
        "recommended": [{"track": k, "label": track_label(k, lg)} for k in rec],
        "batches": batches,
        "open_batches": [{"id": b.id, "code": b.code, "course": course_out(b.course, lg), "start_date": b.start_date.isoformat(),
                          "end_date": b.end_date.isoformat(), "mode": b.mode, "venue": b.venue or b.host_unit,
                          "district_name": m.name("district", b.district, lg),
                          "seats_left": b.seats - sum(1 for t in b.trainees if t.status in ("confirmed", "completed")),
                          "recommended": b.course.track in rec, "sponsor": b.sponsor_name if b.sponsor_type != "self" else None}
                         for b in open_[:20]],
        "external": [ext_cert_out(x) for x in db.scalars(select(ExternalCertificate).where(ExternalCertificate.entrepreneur_id == e.id)
                                                         .order_by(ExternalCertificate.id.desc()))],
    }


class JoinIn(BaseModel):
    batch_id: int


@router.post("/request")
def request_seat(body: JoinIn, user: User = Depends(msme), db: Session = Depends(get_db)):
    e = _me(db, user)
    mine = {t.batch_id: t for t in db.scalars(select(Trainee).where(Trainee.entrepreneur_id == e.id))}
    b = db.get(Batch, body.batch_id)
    if not b or b.id not in {x.id for x in _open_batches(db, e, {k for k, t in mine.items() if t.status != "withdrawn"})}:
        raise HTTPException(422, "This batch is not open for you (full, closed or in another district)")
    t = mine.get(b.id)
    if t:
        t.status, t.source = "requested", "self"
    else:
        db.add(Trainee(batch_id=b.id, entrepreneur_id=e.id, status="requested", source="self"))
    audit(db, user, "training_request", "batch", b.id)
    db.commit()
    return {"ok": True}


class WithdrawIn(BaseModel):
    trainee_id: int


@router.post("/withdraw")
def withdraw(body: WithdrawIn, user: User = Depends(msme), db: Session = Depends(get_db)):
    e = _me(db, user)
    t = db.get(Trainee, body.trainee_id)
    if not t or t.entrepreneur_id != e.id or t.status != "requested":
        raise HTTPException(422, "Only a pending request can be cancelled here – please call your coordinator")
    t.status = "withdrawn"
    db.commit()
    return {"ok": True}


class CheckinIn(BaseModel):
    token: Optional[str] = Field(default=None, max_length=40)
    code: Optional[str] = Field(default=None, max_length=6)


@router.post("/checkin")
def checkin(body: CheckinIn, lang: Optional[str] = None, user: User = Depends(msme), db: Session = Depends(get_db)):
    """Mark myself present by scanning the trainer's QR code (token) or typing the 6-digit code."""
    e = _me(db, user)
    mine = {t.batch_id: t for t in db.scalars(select(Trainee).where(Trainee.entrepreneur_id == e.id, Trainee.status == "confirmed"))}
    q = select(BatchSession).where(BatchSession.checkin_open.is_(True))
    if body.token and re.fullmatch(r"[0-9a-f]{32}", body.token):
        q = q.where(BatchSession.checkin_token == body.token)
    elif body.code and re.fullmatch(r"\d{6}", body.code):
        q = q.where(BatchSession.checkin_code == body.code)
    else:
        raise HTTPException(422, "Scan the QR code or type the 6-digit code")
    s = next((x for x in db.scalars(q) if x.batch_id in mine), None)
    if not s:
        raise HTTPException(404, "Check-in is not open for a batch you are in. Ask your trainer.")
    t = mine[s.batch_id]
    a = next((x for x in s.attendance if x.trainee_id == t.id), None)
    if a:
        a.present, a.method = True, "qr" if body.token else "code"
    else:
        s.attendance.append(Attendance(trainee_id=t.id, present=True, method="qr" if body.token else "code", at=now()))
    bump_stage(e, 2)
    db.commit()
    lg = _lg(user, lang)
    return {"ok": True, "course": course_out(s.batch.course, lg)["name"], "session": (s.topic_te if lg == "te" and s.topic_te else s.topic), "n": s.n}


class FeedbackIn(BaseModel):
    trainee_id: int
    rating: int = Field(ge=1, le=5)
    text: Optional[str] = Field(default=None, max_length=1000)


@router.post("/feedback")
def feedback(body: FeedbackIn, user: User = Depends(msme), db: Session = Depends(get_db)):
    e = _me(db, user)
    t = db.get(Trainee, body.trainee_id)
    if not t or t.entrepreneur_id != e.id or t.status not in ("confirmed", "completed"):
        raise HTTPException(404, "Not found")
    if not attendance(t, t.batch)[0]:
        raise HTTPException(422, "You can give feedback after attending a session")
    t.feedback_rating, t.feedback_text, t.feedback_at = body.rating, body.text, now()
    db.commit()
    return {"ok": True}


@router.post("/certificate/{tid}/link")
def my_certificate(tid: int, user: User = Depends(msme), db: Session = Depends(get_db)):
    e = _me(db, user)
    t = db.get(Trainee, tid)
    if not t or t.entrepreneur_id != e.id or not t.certificate_no:
        raise HTTPException(404, "No certificate")
    return {"url": certificate_link(t)}


@router.post("/external")
async def upload_external(kind: Literal["dgca_rpc", "fssai", "partner", "other"] = Form(...), title: str = Form(..., min_length=2, max_length=160),
                          number: Optional[str] = Form(default=None, max_length=60), issuer: Optional[str] = Form(default=None, max_length=160),
                          issued_on: Optional[date] = Form(default=None), file: UploadFile = File(...),
                          user: User = Depends(msme), db: Session = Depends(get_db)):
    e = _me(db, user)
    if issued_on and issued_on > date.today():
        raise HTTPException(422, "The issue date cannot be in the future")
    name = save_cert_file(await file.read(10 * 1024 * 1024 + 1), file.content_type or "")
    x = ExternalCertificate(entrepreneur_id=e.id, kind=kind, title=title, number=number or None, issuer=issuer or None, issued_on=issued_on,
                            file=name, created_at=now())
    db.add(x)
    db.flush()
    audit(db, user, "external_certificate_upload", "external_certificate", x.id)
    db.commit()
    return ext_cert_out(x)


# ---------------------------------------------------------------- public certificate check (no login)
@public.get("/certificates/{number}")
def verify_certificate(number: str, c: str = "", db: Session = Depends(get_db)):
    """Opened from the QR code on a certificate. Needs the number and the 6-character check code printed with it."""
    t = db.scalar(select(Trainee).where(Trainee.certificate_no == number.strip().upper())) if re.fullmatch(r"[A-Za-z0-9\-]{6,30}", number) else None
    if not t or not c or (t.certificate_code or "") != c.strip().upper():
        return {"valid": False}
    b = t.batch
    return {"valid": True, "certificate_no": t.certificate_no, "name": t.entrepreneur.full_name, "course": b.course.name_en,
            "course_te": b.course.name_te, "track": track_label(b.course.track), "start_date": b.start_date.isoformat(),
            "end_date": b.end_date.isoformat(), "issued_on": t.certified_at.date().isoformat() if t.certified_at else None,
            "district": Masters(db).name("district", b.district), "issuer": "MIRAI Shakthi"}
