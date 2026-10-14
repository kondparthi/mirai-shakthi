"""M4 – EDP & skill-based training for staff: courses, partners, batches (Form 4.1), attendance and assessment
(Form 4.2), needs assessment (4.3), partners (4.4), follow-ups (4.5), certificates and reports."""
import csv
import io
import re
import secrets
from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import User
from ..models_p1 import Entrepreneur, MasterItem
from ..models_p2 import (TRACKS, Attendance, Batch, BatchSession, Course, ExternalCertificate, FollowUp, NeedsAssessment, Trainee,
                         TrainingPartner)
from ..programme.service import Masters, can_see, delete_photo, photo_url, save_photo, scoped
from ..roles import (BATCH_WRITE, FOLLOWUP_WRITE, TRAINING_ADMIN, TRAINING_READ, TRAINING_RUN)
from ..security import ALGO, require_roles
from ..training import certificate
from ..training.service import attendance as att_of
from ..training.service import (FOLLOWUP_POINTS, audit, batch_out, bump_stage, can_run, can_see_batch, cert_file_link, cert_file_path,
                                certificate_data, certificate_link, course_out, get_batch, issue_certificate, now, plan_sessions,
                                recommended_tracks, session_out, suggest_tracks, trainee_out, track_label, user_names)

router = APIRouter(prefix="/api/v1/training", tags=["training"])
files = APIRouter(prefix="/api/v1/files", tags=["files"])
reader = require_roles(*TRAINING_READ)
admin = require_roles(*TRAINING_ADMIN)
planner = require_roles(*BATCH_WRITE)
runner = require_roles(*TRAINING_RUN)
followup_writer = require_roles(*FOLLOWUP_WRITE)
TRACK = Literal["awareness", "core", "skill", "ojt", "exposure", "refresher"]


def _lang(user: User, lang: Optional[str]) -> str:
    return lang if lang in ("en", "te") else (user.language or "en")


# ================================================================ meta
@router.get("/meta")
def meta(_: User = Depends(reader), db: Session = Depends(get_db)):
    """Lists the training forms need: tracks, trainers, mentors, active courses and partners."""
    staff = list(db.scalars(select(User).where(User.role.in_(("trainer", "mentor")), User.is_active.is_(True)).order_by(User.name)))
    return {
        "tracks": [{"code": k, "label": v[0], "label_te": v[1]} for k, v in TRACKS.items()],
        "trainers": [{"id": u.id, "name": u.name or u.email} for u in staff if u.role == "trainer"],
        "mentors": [{"id": u.id, "name": u.name or u.email} for u in staff if u.role == "mentor"],
        "courses": [course_out(c) for c in db.scalars(select(Course).where(Course.active.is_(True)).order_by(Course.track, Course.name_en))],
        "partners": [{"id": p.id, "name": p.name, "kind": p.kind} for p in
                     db.scalars(select(TrainingPartner).where(TrainingPartner.status == "active").order_by(TrainingPartner.name))],
    }


# ================================================================ courses (curriculum master)
class SessionIn(BaseModel):
    topic_en: str = Field(min_length=2, max_length=200)
    topic_te: Optional[str] = Field(default=None, max_length=200)
    hours: Optional[float] = Field(default=None, ge=0, le=24)


class CourseIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_]+$")
    track: TRACK
    name_en: str = Field(min_length=2, max_length=160)
    name_te: Optional[str] = Field(default=None, max_length=160)
    description_en: Optional[str] = Field(default=None, max_length=2000)
    description_te: Optional[str] = Field(default=None, max_length=2000)
    sectors: list[str] = []
    duration_days: int = Field(ge=1, le=365)
    sessions: list[SessionIn] = Field(min_length=1, max_length=120)
    outcomes: list[str] = []
    pass_mark: int = Field(ge=0, le=100)
    min_attendance: int = Field(ge=0, le=100)
    practical_checklist: list[str] = []
    business_plan_score: bool = False
    external_certificate: Optional[str] = Field(default=None, max_length=120)
    active: bool = True


@router.get("/courses")
def list_courses(track: Optional[str] = None, all: bool = False, _: User = Depends(reader), db: Session = Depends(get_db)):
    q = select(Course).order_by(Course.track, Course.name_en)
    if track:
        q = q.where(Course.track == track)
    if not all:
        q = q.where(Course.active.is_(True))
    return [course_out(c, full=True) for c in db.scalars(q)]


def _check_sectors(db: Session, codes: list[str]):
    known = set(db.scalars(select(MasterItem.code).where(MasterItem.kind == "sector")))
    bad = [c for c in codes if c not in known]
    if bad:
        raise HTTPException(422, f"Unknown sector: {', '.join(bad)}")


@router.post("/courses")
def create_course(body: CourseIn, user: User = Depends(admin), db: Session = Depends(get_db)):
    if db.scalar(select(Course).where(Course.code == body.code)):
        raise HTTPException(409, "A course with this code exists")
    _check_sectors(db, body.sectors)
    c = Course(**body.model_dump(exclude={"sessions"}), sessions=[s.model_dump() for s in body.sessions])
    db.add(c)
    db.flush()
    audit(db, user, "course_create", "course", c.id, {"code": c.code})
    db.commit()
    return course_out(c, full=True)


@router.put("/courses/{cid}")
def update_course(cid: int, body: CourseIn, user: User = Depends(admin), db: Session = Depends(get_db)):
    c = db.get(Course, cid)
    if not c:
        raise HTTPException(404, "Course not found")
    if body.code != c.code:
        raise HTTPException(422, "The course code cannot be changed")
    _check_sectors(db, body.sectors)
    for k, v in body.model_dump(exclude={"sessions"}).items():
        setattr(c, k, v)
    c.sessions = [s.model_dump() for s in body.sessions]
    audit(db, user, "course_update", "course", c.id, {"code": c.code})
    db.commit()
    return course_out(c, full=True)


# ================================================================ training partners (Form 4.4)
class PartnerIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    kind: Literal["institute", "trainer", "host_unit"]
    contact_name: Optional[str] = Field(default=None, max_length=120)
    mobile: Optional[str] = None
    email: Optional[str] = Field(default=None, max_length=190)
    accreditation: Optional[str] = Field(default=None, max_length=255)
    tracks: list[TRACK] = Field(min_length=1)
    sectors: list[str] = []
    districts: list[str] = []
    languages: list[str] = []
    rate_batch: Optional[float] = Field(default=None, ge=0)
    rate_trainee: Optional[float] = Field(default=None, ge=0)
    status: Literal["active", "inactive"] = "active"

    @field_validator("mobile")
    @classmethod
    def v_mobile(cls, v):
        if not v:
            return None
        v = re.sub(r"\D", "", v)[-10:]
        if not re.fullmatch(r"[6-9]\d{9}", v):
            raise ValueError("Enter a valid 10-digit mobile number")
        return v


def _partner_ratings(db: Session) -> dict[int, tuple[float, int]]:
    rows = db.execute(select(Batch.partner_id, func.avg(Trainee.feedback_rating), func.count(Trainee.feedback_rating))
                      .join(Trainee, Trainee.batch_id == Batch.id).where(Trainee.feedback_rating.is_not(None))
                      .group_by(Batch.partner_id)).all()
    return {pid: (round(float(avg), 1), n) for pid, avg, n in rows if pid}


def _partner_out(p: TrainingPartner, ratings: dict) -> dict:
    r = ratings.get(p.id)
    return {"id": p.id, "name": p.name, "kind": p.kind, "contact_name": p.contact_name, "mobile": p.mobile, "email": p.email,
            "accreditation": p.accreditation, "tracks": p.tracks or [], "sectors": p.sectors or [], "districts": p.districts or [],
            "languages": p.languages or [], "rate_batch": p.rate_batch, "rate_trainee": p.rate_trainee, "status": p.status,
            "rating": r[0] if r else None, "ratings": r[1] if r else 0}


@router.get("/partners")
def list_partners(_: User = Depends(reader), db: Session = Depends(get_db)):
    ratings = _partner_ratings(db)
    return [_partner_out(p, ratings) for p in db.scalars(select(TrainingPartner).order_by(TrainingPartner.status, TrainingPartner.name))]


@router.post("/partners")
def create_partner(body: PartnerIn, user: User = Depends(admin), db: Session = Depends(get_db)):
    _check_sectors(db, body.sectors)
    p = TrainingPartner(**body.model_dump())
    db.add(p)
    db.flush()
    audit(db, user, "training_partner_create", "training_partner", p.id)
    db.commit()
    return _partner_out(p, {})


@router.put("/partners/{pid}")
def update_partner(pid: int, body: PartnerIn, user: User = Depends(admin), db: Session = Depends(get_db)):
    p = db.get(TrainingPartner, pid)
    if not p:
        raise HTTPException(404, "Partner not found")
    _check_sectors(db, body.sectors)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    audit(db, user, "training_partner_update", "training_partner", p.id)
    db.commit()
    return _partner_out(p, _partner_ratings(db))


# ================================================================ batches (Form 4.1)
class BatchIn(BaseModel):
    course_id: int
    partner_id: Optional[int] = None
    trainer_ids: list[int] = Field(min_length=1)
    mentor_ids: list[int] = []
    mode: Literal["classroom", "online", "blended", "ojt"]
    start_date: date
    end_date: date
    venue: Optional[str] = Field(default=None, max_length=255)
    host_unit: Optional[str] = Field(default=None, max_length=160)
    district: Optional[str] = None
    seats: int = Field(ge=1, le=500)
    sponsor_type: Literal["csr", "govt", "self"] = "self"
    sponsor_name: Optional[str] = Field(default=None, max_length=160)
    pass_mark: Optional[int] = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def v_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("The end date is before the start date")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("A batch can run for at most a year")
        if self.mode != "online" and not (self.venue or self.host_unit):
            raise ValueError("Enter the venue (or host unit for on-the-job training)")
        if self.mode != "online" and not self.district:
            raise ValueError("Choose the district")
        if self.sponsor_type in ("csr", "govt") and not self.sponsor_name:
            raise ValueError("Enter the sponsor's name")
        return self


def _check_batch(db: Session, user: User, body: BatchIn) -> Course:
    c = db.get(Course, body.course_id)
    if not c or not c.active:
        raise HTTPException(422, "Choose an active course")
    if body.partner_id and not db.get(TrainingPartner, body.partner_id):
        raise HTTPException(422, "Unknown training partner")
    roles = dict(db.execute(select(User.id, User.role).where(User.id.in_(body.trainer_ids + body.mentor_ids))).all())
    if any(roles.get(i) != "trainer" for i in body.trainer_ids):
        raise HTTPException(422, "Trainers must be staff logins with the Trainer role")
    if any(roles.get(i) != "mentor" for i in body.mentor_ids):
        raise HTTPException(422, "Mentors must be staff logins with the Mentor role")
    if body.district and not db.scalar(select(MasterItem.id).where(MasterItem.kind == "district", MasterItem.code == body.district)):
        raise HTTPException(422, "Unknown district")
    districts = (user.scope or {}).get("districts") or []
    if user.role not in ("admin", "programme_manager") and districts and body.district and body.district not in districts:
        raise HTTPException(403, "This district is outside your area")
    return c


@router.get("/batches")
def list_batches(status: Optional[str] = None, course_id: Optional[int] = None, track: Optional[str] = None, district: Optional[str] = None,
                 q: Optional[str] = None, lang: Optional[str] = None, user: User = Depends(reader), db: Session = Depends(get_db)):
    stmt = select(Batch).order_by(Batch.start_date.desc(), Batch.id.desc())
    if status:
        stmt = stmt.where(Batch.status == status)
    if course_id:
        stmt = stmt.where(Batch.course_id == course_id)
    if track:
        stmt = stmt.where(Batch.course_id.in_(select(Course.id).where(Course.track == track)))
    if district:
        stmt = stmt.where(Batch.district == district)
    if q:
        stmt = stmt.where(or_(Batch.code.ilike(f"%{q}%"), Batch.venue.ilike(f"%{q}%"), Batch.sponsor_name.ilike(f"%{q}%")))
    rows = [b for b in db.scalars(stmt.limit(500)) if can_see_batch(user, b)]
    m = Masters(db)
    names = user_names(db, [i for b in rows for i in (b.trainer_ids or []) + (b.mentor_ids or [])])
    return [batch_out(db, b, m, _lang(user, lang), names) for b in rows]


@router.post("/batches")
def create_batch(body: BatchIn, user: User = Depends(planner), db: Session = Depends(get_db)):
    c = _check_batch(db, user, body)
    b = Batch(**body.model_dump(exclude={"pass_mark"}), pass_mark=body.pass_mark if body.pass_mark is not None else c.pass_mark,
              created_by_id=user.id, status="planned")
    b.course = c
    db.add(b)
    plan_sessions(b, c)
    db.flush()
    b.code = f"B{b.start_date:%y%m}-{b.id:04d}"
    audit(db, user, "batch_create", "batch", b.id, {"course": c.code, "seats": b.seats})
    db.commit()
    return batch_detail(b.id, None, user, db)


@router.put("/batches/{bid}")
def update_batch(bid: int, body: BatchIn, user: User = Depends(planner), db: Session = Depends(get_db)):
    b = get_batch(db, user, bid)
    if b.status in ("completed", "cancelled"):
        raise HTTPException(422, "This batch is closed")
    c = _check_batch(db, user, body)
    if body.course_id != b.course_id and any(s.done for s in b.sessions):
        raise HTTPException(422, "The course cannot be changed after sessions have been held")
    filled = sum(1 for t in b.trainees if t.status in ("confirmed", "completed"))
    if body.seats < filled:
        raise HTTPException(422, f"{filled} people are already in the batch – seats cannot be fewer")
    replan = body.course_id != b.course_id or body.start_date != b.start_date or body.end_date != b.end_date
    for k, v in body.model_dump(exclude={"pass_mark"}).items():
        setattr(b, k, v)
    b.course = c
    if body.pass_mark is not None:
        b.pass_mark = body.pass_mark
    if replan and not any(s.done for s in b.sessions):
        b.sessions.clear()
        db.flush()
        plan_sessions(b, c)
    audit(db, user, "batch_update", "batch", b.id)
    db.commit()
    return batch_detail(b.id, None, user, db)


class StatusIn(BaseModel):
    status: Literal["planned", "open", "ongoing", "completed", "cancelled"]


@router.post("/batches/{bid}/status")
def batch_status(bid: int, body: StatusIn, user: User = Depends(planner), db: Session = Depends(get_db)):
    b = get_batch(db, user, bid)
    if b.status in ("completed", "cancelled") and body.status != b.status:
        raise HTTPException(422, "This batch is closed")
    if body.status == "completed":
        pending = [t.entrepreneur.full_name for t in b.trainees if t.status == "confirmed" and not t.result]
        if pending:
            raise HTTPException(422, f"Enter results for everyone first: {', '.join(pending[:5])}{'…' if len(pending) > 5 else ''}")
        for t in b.trainees:
            if t.status == "confirmed":
                t.status = "completed"
    b.status = body.status
    audit(db, user, "batch_status", "batch", b.id, {"status": body.status})
    db.commit()
    return batch_detail(b.id, None, user, db)


@router.get("/batches/{bid}")
def batch_detail(bid: int, lang: Optional[str] = None, user: User = Depends(reader), db: Session = Depends(get_db)):
    b = get_batch(db, user, bid)
    lg = _lang(user, lang)
    m = Masters(db)
    names = user_names(db, list(b.trainer_ids or []) + list(b.mentor_ids or []) + [t.mentor_id for t in b.trainees])
    d = batch_out(db, b, m, lg, names)
    d["course"] = course_out(b.course, lg, full=True)
    d["sessions"] = [session_out(s, lg) for s in b.sessions]
    d["trainees"] = [trainee_out(t, b, m, names, lg) for t in b.trainees]
    d["can_run"] = can_run(user, b) and user.role in TRAINING_RUN
    d["can_plan"] = user.role in BATCH_WRITE
    return d


# ---------------------------------------------------------------- nominations
@router.get("/batches/{bid}/candidates")
def candidates(bid: int, q: Optional[str] = None, all_districts: bool = False, user: User = Depends(planner), db: Session = Depends(get_db)):
    """Enrolled entrepreneurs who could join: not already in the batch, consent given, recommended first."""
    b = get_batch(db, user, bid)
    taken = {t.entrepreneur_id for t in b.trainees if t.status != "withdrawn"}
    stmt = scoped(select(Entrepreneur), user, Entrepreneur).where(Entrepreneur.status == "active", Entrepreneur.consent_at.is_not(None))
    if b.district and b.mode != "online" and not all_districts:
        stmt = stmt.where(Entrepreneur.district == b.district)
    if q:
        stmt = stmt.where(or_(Entrepreneur.full_name.ilike(f"%{q.strip()}%"), Entrepreneur.mobile.like(f"%{q.strip()}%")))
    m = Masters(db)
    out = []
    for e in db.scalars(stmt.order_by(Entrepreneur.id.desc()).limit(400)):
        if e.id in taken:
            continue
        rec = b.course.track in recommended_tracks(db, e)
        sector_fit = not b.course.sectors or bool(set(b.course.sectors) & set(e.interests or []))
        out.append({"id": e.id, "full_name": e.full_name, "mobile": e.mobile, "village_name": m.name("village", e.village),
                    "district_name": m.name("district", e.district), "stage": e.stage, "recommended": rec, "sector_fit": sector_fit})
    out.sort(key=lambda x: (not x["recommended"], not x["sector_fit"], x["full_name"]))
    return out[:100]


class NominateIn(BaseModel):
    entrepreneur_ids: list[int] = Field(min_length=1, max_length=500)


@router.post("/batches/{bid}/trainees")
def nominate(bid: int, body: NominateIn, user: User = Depends(planner), db: Session = Depends(get_db)):
    b = get_batch(db, user, bid)
    if b.status in ("completed", "cancelled"):
        raise HTTPException(422, "This batch is closed")
    existing = {t.entrepreneur_id: t for t in b.trainees}
    filled = sum(1 for t in b.trainees if t.status in ("confirmed", "completed"))
    new = [i for i in dict.fromkeys(body.entrepreneur_ids) if i not in existing or existing[i].status in ("withdrawn", "requested")]
    if filled + len(new) > b.seats:
        raise HTTPException(422, f"Only {b.seats - filled} seat(s) left in this batch")
    mentors = list(b.mentor_ids or [])
    for k, eid in enumerate(new):
        e = db.get(Entrepreneur, eid)
        if not e or not can_see(user, e) or not e.consent_at:
            raise HTTPException(422, f"Entrepreneur {eid} cannot be added (not found, outside your area, or consent pending)")
        t = existing.get(eid)
        if t:
            t.status = "confirmed"
        else:
            t = Trainee(batch=b, entrepreneur_id=eid, status="confirmed", source="staff")
            db.add(t)
        if not t.mentor_id and mentors:  # spec: the mentor is assigned at the EDP – share batch mentors round-robin
            t.mentor_id = mentors[(filled + k) % len(mentors)]
        bump_stage(e, 2)
    audit(db, user, "batch_nominate", "batch", b.id, {"added": len(new)})
    db.commit()
    return batch_detail(b.id, None, user, db)


class TraineeIn(BaseModel):
    status: Optional[Literal["confirmed", "withdrawn"]] = None
    mentor_id: Optional[int] = None


@router.put("/trainees/{tid}")
def update_trainee(tid: int, body: TraineeIn, user: User = Depends(planner), db: Session = Depends(get_db)):
    t = db.get(Trainee, tid)
    if not t:
        raise HTTPException(404, "Not found")
    b = get_batch(db, user, t.batch_id)
    if body.status == "confirmed" and t.status != "confirmed":
        filled = sum(1 for x in b.trainees if x.status in ("confirmed", "completed"))
        if filled >= b.seats:
            raise HTTPException(422, "The batch is full")
        bump_stage(t.entrepreneur, 2)
    if body.status:
        if t.certificate_no and body.status == "withdrawn":
            raise HTTPException(422, "This person already has a certificate")
        t.status = body.status
    if body.mentor_id is not None:
        if body.mentor_id and db.scalar(select(User.role).where(User.id == body.mentor_id)) != "mentor":
            raise HTTPException(422, "Choose a staff login with the Mentor role")
        t.mentor_id = body.mentor_id or None
    audit(db, user, "trainee_update", "trainee", t.id, body.model_dump(exclude_none=True))
    db.commit()
    return batch_detail(b.id, None, user, db)


# ---------------------------------------------------------------- sessions and attendance (Form 4.2)
def _session(db: Session, user: User, sid: int) -> tuple[BatchSession, Batch]:
    s = db.get(BatchSession, sid)
    if not s:
        raise HTTPException(404, "Session not found")
    b = get_batch(db, user, s.batch_id)
    if not can_run(user, b):
        raise HTTPException(403, "Only this batch's trainers can do this")
    if b.status in ("completed", "cancelled"):
        raise HTTPException(422, "This batch is closed")
    return s, b


class SessionEdit(BaseModel):
    date: Optional[date] = None
    topic: str = Field(min_length=2, max_length=200)
    hours: Optional[float] = Field(default=None, ge=0, le=24)


@router.put("/sessions/{sid}")
def edit_session(sid: int, body: SessionEdit, user: User = Depends(runner), db: Session = Depends(get_db)):
    s, b = _session(db, user, sid)
    s.date, s.topic, s.hours = body.date, body.topic, body.hours
    db.commit()
    return session_out(s)


class AttendanceIn(BaseModel):
    present: list[int]  # trainee ids present; everyone else in the batch is marked absent


@router.post("/sessions/{sid}/attendance")
def mark_attendance(sid: int, body: AttendanceIn, user: User = Depends(runner), db: Session = Depends(get_db)):
    s, b = _session(db, user, sid)
    active = {t.id for t in b.trainees if t.status in ("confirmed", "completed")}
    bad = set(body.present) - active
    if bad:
        raise HTTPException(422, "Some people are not in this batch")
    rows = {a.trainee_id: a for a in s.attendance}
    for tid in active:
        a = rows.get(tid)
        present = tid in body.present
        if a:  # the trainer's list is final (the screen starts with self check-ins already ticked)
            a.present = present
        else:
            s.attendance.append(Attendance(trainee_id=tid, present=present, method="trainer", at=now()))
    s.done = True
    s.checkin_open = False
    if b.status in ("planned", "open"):
        b.status = "ongoing"
    audit(db, user, "attendance_mark", "session", s.id, {"present": len(body.present), "of": len(active)})
    db.commit()
    return session_out(s)


@router.post("/sessions/{sid}/photo")
async def session_photo(sid: int, file: UploadFile = File(...), lat: Optional[float] = Form(default=None), lng: Optional[float] = Form(default=None),
                        user: User = Depends(runner), db: Session = Depends(get_db)):
    s, _ = _session(db, user, sid)
    name = save_photo(await file.read(8 * 1024 * 1024 + 1))
    old, s.photo = s.photo, name
    if lat is not None and lng is not None and -90 <= lat <= 90 and -180 <= lng <= 180:
        s.lat, s.lng = lat, lng
    db.commit()
    delete_photo(old)
    return session_out(s)


class CheckinOpenIn(BaseModel):
    origin: Optional[str] = None  # the site address the QR should open (defaults to PUBLIC_URL)


@router.post("/sessions/{sid}/checkin/open")
def open_checkin(sid: int, body: CheckinOpenIn, user: User = Depends(runner), db: Session = Depends(get_db)):
    """Show a QR code (and a 6-digit code) that trainees scan with their phone to mark themselves present."""
    import segno

    s, b = _session(db, user, sid)
    s.checkin_open = True
    s.checkin_token = secrets.token_hex(16)
    s.checkin_code = f"{secrets.randbelow(10**6):06d}"
    db.commit()
    origin = (body.origin or settings.PUBLIC_URL).rstrip("/")
    if not re.fullmatch(r"https?://[\w.\-:]+", origin):
        origin = settings.PUBLIC_URL
    url = f"{origin}/#/checkin/{s.checkin_token}"
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=8, border=2, xmldecl=False, svgns=True)
    return {"url": url, "code": s.checkin_code, "svg": buf.getvalue().decode()}


@router.post("/sessions/{sid}/checkin/close")
def close_checkin(sid: int, user: User = Depends(runner), db: Session = Depends(get_db)):
    s, _ = _session(db, user, sid)
    s.checkin_open = False
    db.commit()
    return session_out(s)


# ---------------------------------------------------------------- assessment and results (Form 4.2)
class AssessIn(BaseModel):
    quiz_score: Optional[float] = Field(default=None, ge=0, le=100)
    practical: dict[str, bool] = {}
    practical_hours: Optional[float] = Field(default=None, ge=0, le=2000)
    bp_score: Optional[float] = Field(default=None, ge=0, le=100)
    result: Optional[Literal["pass", "reassess", "fail"]] = None


@router.put("/trainees/{tid}/assessment")
def assess(tid: int, body: AssessIn, user: User = Depends(runner), db: Session = Depends(get_db)):
    t = db.get(Trainee, tid)
    if not t:
        raise HTTPException(404, "Not found")
    b = get_batch(db, user, t.batch_id)
    if not can_run(user, b):
        raise HTTPException(403, "Only this batch's trainers can do this")
    if t.status not in ("confirmed", "completed"):
        raise HTTPException(422, "This person is not confirmed in the batch")
    checklist = b.course.practical_checklist or []
    t.quiz_score, t.practical_hours, t.bp_score = body.quiz_score, body.practical_hours, body.bp_score
    t.practical = {k: bool(body.practical.get(k)) for k in checklist}
    before = t.result
    t.result = body.result
    if body.result == "pass":
        issue_certificate(t, b)
        if b.course.track == "core":
            bump_stage(t.entrepreneur, 3)  # Core EDP done → DPR & finance
    elif t.certificate_no:
        audit(db, user, "certificate_withdrawn", "trainee", t.id, {"certificate_no": t.certificate_no})
        t.certificate_no = t.certificate_code = None
        t.certified_at = None
    audit(db, user, "trainee_assess", "trainee", t.id, {"result": body.result, "before": before, "quiz": body.quiz_score})
    db.commit()
    names = user_names(db, [t.mentor_id])
    return trainee_out(t, b, Masters(db), names)


@router.post("/trainees/{tid}/certificate/link")
def staff_certificate_link(tid: int, user: User = Depends(reader), db: Session = Depends(get_db)):
    t = db.get(Trainee, tid)
    if not t or not t.certificate_no:
        raise HTTPException(404, "No certificate")
    get_batch(db, user, t.batch_id)
    return {"url": certificate_link(t)}


@router.get("/certificates/{tid}.pdf")
def certificate_pdf(tid: int, t_: str = Query(alias="t", min_length=10), db: Session = Depends(get_db)):
    try:
        claims = jwt.decode(t_, settings.JWT_SECRET, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(403, "Link expired – open the certificate again") from e
    if claims.get("purpose") != "certificate" or claims.get("tid") != tid:
        raise HTTPException(403, "Link not valid")
    t = db.get(Trainee, tid)
    if not t or not t.certificate_no:
        raise HTTPException(404, "No certificate")
    m = Masters(db)
    data = certificate_data(t)
    data["place"] = ", ".join(x for x in (t.batch.venue, m.name("district", t.batch.district)) if x) or None
    return Response(certificate.render(data), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{t.certificate_no}.pdf"'})


# ================================================================ entrepreneur training summary + needs assessment (Form 4.3)
def _entrepreneur(db: Session, user: User, eid: int) -> Entrepreneur:
    e = db.get(Entrepreneur, eid)
    if not e or not can_see(user, e):
        raise HTTPException(404, "Entrepreneur not found")
    return e


def _needs_out(n: NeedsAssessment, names: dict) -> dict:
    return {"id": n.id, "enterprise_model": n.enterprise_model, "business_skills": n.business_skills, "technical_level": n.technical_level,
            "prior_training": n.prior_training, "preferred_mode": n.preferred_mode, "preferred_timing": n.preferred_timing,
            "constraints": n.constraints, "recommended_tracks": n.recommended_tracks, "by": names.get(n.assessed_by_id),
            "at": n.created_at.isoformat() if n.created_at else None}


def ext_cert_out(x: ExternalCertificate) -> dict:
    return {"id": x.id, "kind": x.kind, "title": x.title, "number": x.number, "issuer": x.issuer,
            "issued_on": x.issued_on.isoformat() if x.issued_on else None, "status": x.status, "note": x.note,
            "file_url": cert_file_link(x.file) if x.file else None, "at": x.created_at.isoformat() if x.created_at else None}


@router.get("/entrepreneurs/{eid}")
def entrepreneur_training(eid: int, user: User = Depends(reader), db: Session = Depends(get_db)):
    e = _entrepreneur(db, user, eid)
    needs = list(db.scalars(select(NeedsAssessment).where(NeedsAssessment.entrepreneur_id == e.id).order_by(NeedsAssessment.id.desc())))
    trainees = list(db.scalars(select(Trainee).where(Trainee.entrepreneur_id == e.id).order_by(Trainee.id.desc())))
    names = user_names(db, [n.assessed_by_id for n in needs] + [t.mentor_id for t in trainees])
    m = Masters(db)
    return {
        "recommended": [{"track": k, "label": track_label(k)} for k in recommended_tracks(db, e)],
        "needs": [_needs_out(n, names) for n in needs],
        "trainings": [{**trainee_out(t, t.batch, m, names), "batch": {"id": t.batch.id, "code": t.batch.code, "status": t.batch.status,
                                                                       "course": t.batch.course.name_en, "track": t.batch.course.track,
                                                                       "start_date": t.batch.start_date.isoformat()},
                       "followups": [{"point": f.point, "status": f.status} for f in t.followups]} for t in trainees],
        "external": [ext_cert_out(x) for x in db.scalars(select(ExternalCertificate).where(ExternalCertificate.entrepreneur_id == e.id)
                                                         .order_by(ExternalCertificate.id.desc()))],
    }


class PriorIn(BaseModel):
    course: str = Field(min_length=2, max_length=160)
    institute: Optional[str] = Field(default=None, max_length=160)
    year: Optional[int] = Field(default=None, ge=1970, le=2100)


SKILL_AREAS = ("costing", "bookkeeping", "marketing", "digital", "banking")


class NeedsIn(BaseModel):
    enterprise_model: str = Field(min_length=2, max_length=160)
    business_skills: dict[str, int]
    technical_level: int = Field(ge=1, le=5)
    prior_training: list[PriorIn] = []
    preferred_mode: Literal["classroom", "online", "blended"]
    preferred_timing: Literal["weekdays", "weekends", "any"]
    constraints: list[Literal["travel", "childcare", "phone", "language"]] = []
    recommended_tracks: list[TRACK] = []

    @field_validator("business_skills")
    @classmethod
    def v_skills(cls, v):
        if set(v) != set(SKILL_AREAS) or any(not 1 <= x <= 5 for x in v.values()):
            raise ValueError("Rate each business skill (costing, bookkeeping, marketing, digital, banking) from 1 to 5")
        return v


@router.post("/needs/suggest")
def needs_suggest(body: NeedsIn, eid: Optional[int] = None, user: User = Depends(reader), db: Session = Depends(get_db)):
    rec = recommended_tracks(db, _entrepreneur(db, user, eid)) if eid else []
    return {"tracks": suggest_tracks(body.business_skills, body.technical_level, body.prior_training, rec if "awareness" not in rec or len(rec) > 1 else [])}


@router.post("/entrepreneurs/{eid}/needs")
def save_needs(eid: int, body: NeedsIn, user: User = Depends(require_roles(*FOLLOWUP_WRITE)), db: Session = Depends(get_db)):
    e = _entrepreneur(db, user, eid)
    tracks = body.recommended_tracks or suggest_tracks(body.business_skills, body.technical_level, body.prior_training)
    n = NeedsAssessment(entrepreneur_id=e.id, **body.model_dump(exclude={"recommended_tracks", "prior_training"}),
                        prior_training=[p.model_dump() for p in body.prior_training], recommended_tracks=tracks, assessed_by_id=user.id,
                        created_at=now())
    db.add(n)
    db.flush()
    audit(db, user, "training_needs", "entrepreneur", e.id, {"tracks": tracks})
    db.commit()
    return _needs_out(n, {user.id: user.name})


# ================================================================ follow-ups (Form 4.5)
@router.get("/followups")
def followups_due(user: User = Depends(followup_writer), db: Session = Depends(get_db)):
    """Follow-ups that are due (within 7 days) or overdue for certified trainees. Mentors see their own trainees."""
    stmt = select(Trainee).where(Trainee.certified_at.is_not(None))
    if user.role == "mentor":
        stmt = stmt.where(Trainee.mentor_id == user.id)
    today = date.today()
    out = []
    m = Masters(db)
    for t in db.scalars(stmt):
        if user.role != "mentor" and not can_see(user, t.entrepreneur):
            continue
        done = {f.point for f in t.followups}
        for p in FOLLOWUP_POINTS:
            due = t.certified_at.date() + timedelta(days=p)
            if p not in done and due <= today + timedelta(days=7):
                e = t.entrepreneur
                out.append({"trainee_id": t.id, "point": p, "due": due.isoformat(), "overdue": due < today, "name": e.full_name, "mobile": e.mobile,
                            "entrepreneur_id": e.id, "village_name": m.name("village", e.village), "course": t.batch.course.name_en,
                            "batch": t.batch.code})
                break  # one open follow-up per person at a time
    out.sort(key=lambda x: x["due"])
    return out


class FollowUpIn(BaseModel):
    point: Literal[30, 90, 180]
    status: Literal["started", "in_process", "not_started", "employed", "dropped"]
    skills_used: Literal["yes", "partly", "no"]
    support: list[Literal["refresher", "finance", "market", "equipment", "mentoring"]] = []
    next_action: Optional[str] = Field(default=None, max_length=255)
    next_date: Optional[date] = None


@router.post("/trainees/{tid}/followups")
def record_followup(tid: int, body: FollowUpIn, user: User = Depends(followup_writer), db: Session = Depends(get_db)):
    t = db.get(Trainee, tid)
    if not t or not t.certified_at:
        raise HTTPException(404, "Certified trainee not found")
    if user.role == "mentor" and t.mentor_id != user.id:
        raise HTTPException(403, "This trainee has another mentor")
    if user.role != "mentor" and not can_see(user, t.entrepreneur):
        raise HTTPException(404, "Not found")
    if any(f.point == body.point for f in t.followups):
        raise HTTPException(409, f"The {body.point}-day follow-up is already recorded")
    t.followups.append(FollowUp(**body.model_dump(), recorded_by_id=user.id, created_at=now()))
    if body.status == "started":
        bump_stage(t.entrepreneur, 4)
    audit(db, user, "training_followup", "trainee", t.id, {"point": body.point, "status": body.status})
    db.commit()
    return {"ok": True}


# ================================================================ external certificates (DGCA RPC, FSSAI, partner)
@router.get("/external-certificates")
def external_list(status: Optional[str] = "pending", user: User = Depends(planner), db: Session = Depends(get_db)):
    stmt = select(ExternalCertificate).order_by(ExternalCertificate.id.desc())
    if status:
        stmt = stmt.where(ExternalCertificate.status == status)
    m = Masters(db)
    out = []
    for x in db.scalars(stmt.limit(300)):
        e = db.get(Entrepreneur, x.entrepreneur_id)
        if e and can_see(user, e):
            out.append({**ext_cert_out(x), "entrepreneur": {"id": e.id, "full_name": e.full_name, "district_name": m.name("district", e.district)}})
    return out


class VerifyIn(BaseModel):
    status: Literal["verified", "rejected"]
    note: Optional[str] = Field(default=None, max_length=255)


@router.post("/external-certificates/{xid}/verify")
def external_verify(xid: int, body: VerifyIn, user: User = Depends(planner), db: Session = Depends(get_db)):
    x = db.get(ExternalCertificate, xid)
    if not x or not can_see(user, db.get(Entrepreneur, x.entrepreneur_id)):
        raise HTTPException(404, "Not found")
    if body.status == "rejected" and not body.note:
        raise HTTPException(422, "Say why it was rejected")
    x.status, x.note, x.verified_by_id, x.verified_at = body.status, body.note, user.id, now()
    audit(db, user, f"external_certificate_{body.status}", "external_certificate", x.id)
    db.commit()
    return ext_cert_out(x)


@files.get("/certificate/{name}")
def external_file(name: str, t: str = Query(min_length=10)):
    if not re.fullmatch(r"[0-9a-f]{32}\.(pdf|jpg|png|webp)", name):
        raise HTTPException(404, "Not found")
    try:
        claims = jwt.decode(t, settings.JWT_SECRET, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(403, "Link expired") from e
    if claims.get("purpose") != "certfile" or claims.get("f") != name:
        raise HTTPException(403, "Link not valid")
    p = cert_file_path(name)
    if not p.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(p, headers={"Cache-Control": "private, max-age=600"})


# ================================================================ reports
def _visible_batches(db: Session, user: User) -> list[Batch]:
    return [b for b in db.scalars(select(Batch).where(Batch.status != "cancelled")) if can_see_batch(user, b)]


@router.get("/reports/summary")
def report_summary(user: User = Depends(reader), db: Session = Depends(get_db)):
    batches = _visible_batches(db, user)
    m = Masters(db)

    def agg(key):
        groups: dict = {}
        for b in batches:
            k = key(b)
            g = groups.setdefault(k, {"key": k, "batches": 0, "trainees": 0, "completed": 0, "certified": 0, "ratings": []})
            g["batches"] += 1
            for t in b.trainees:
                if t.status in ("confirmed", "completed"):
                    g["trainees"] += 1
                    g["completed"] += t.status == "completed"
                    g["certified"] += bool(t.certificate_no)
                    if t.feedback_rating:
                        g["ratings"].append(t.feedback_rating)
        out = []
        for g in groups.values():
            r = g.pop("ratings")
            g["rating"] = round(sum(r) / len(r), 1) if r else None
            g["cert_rate"] = round(100 * g["certified"] / g["trainees"]) if g["trainees"] else 0
            out.append(g)
        return sorted(out, key=lambda x: -x["trainees"])

    by_course = agg(lambda b: b.course.name_en)
    by_sponsor = agg(lambda b: f"{b.sponsor_name} ({b.sponsor_type.upper()})" if b.sponsor_type != "self" and b.sponsor_name else "Self-funded")
    by_district = agg(lambda b: m.name("district", b.district) or "Online")
    trainees = [t for b in batches for t in b.trainees if t.status in ("confirmed", "completed")]
    return {
        "batches": len(batches), "running": sum(1 for b in batches if b.status == "ongoing"),
        "upcoming": sum(1 for b in batches if b.status in ("planned", "open")), "trainees": len(trainees),
        "women": sum(1 for t in trainees if t.entrepreneur.gender == "female"), "certified": sum(1 for t in trainees if t.certificate_no),
        "by_course": by_course, "by_sponsor": by_sponsor, "by_district": by_district,
    }


@router.get("/reports/trainees.csv")
def report_csv(sponsor: Optional[str] = None, user: User = Depends(reader), db: Session = Depends(get_db)):
    """Trainee-level export for sponsor reports (CSR / scheme). Mobile numbers are partly hidden."""
    m = Masters(db)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["batch", "course", "track", "start", "end", "district", "sponsor", "name", "gender", "mobile", "attendance_%", "quiz_%",
                "result", "certificate_no", "feedback"])
    for b in _visible_batches(db, user):
        sp = b.sponsor_name or "Self-funded"
        if sponsor and sponsor.lower() not in sp.lower():
            continue
        for t in b.trainees:
            if t.status not in ("confirmed", "completed"):
                continue
            att, _, total = att_of(t, b)
            e = t.entrepreneur
            w.writerow([b.code, b.course.name_en, track_label(b.course.track), b.start_date, b.end_date, m.name("district", b.district) or "Online",
                        sp, e.full_name, e.gender, f"{e.mobile[:2]}xxxxx{e.mobile[-3:]}", round(100 * att / total) if total else 0,
                        t.quiz_score if t.quiz_score is not None else "", t.result or "", t.certificate_no or "", t.feedback_rating or ""])
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="training_trainees.csv"'})
