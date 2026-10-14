"""Shared training logic (M4): scope, outputs, attendance, result suggestion, certificates and lifecycle."""
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuditLog, User
from ..models_p1 import Entrepreneur, ReadinessAssessment
from ..models_p2 import READINESS_TRACK, TRACKS, Batch, BatchSession, Course, NeedsAssessment, Trainee
from ..programme.service import STORAGE, Masters, photo_url
from ..roles import ALL_SCOPE
from ..security import ALGO

FOLLOWUP_POINTS = (30, 90, 180)


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def audit(db: Session, user: User, action: str, entity: str, entity_id=None, detail=None):
    db.add(AuditLog(user_id=user.id, action=action, entity=entity, entity_id=entity_id, detail=detail))


def track_label(track: str, lang: str = "en") -> str:
    t = TRACKS.get(track, (track, track))
    return t[1] if lang == "te" else t[0]


# ---------------------------------------------------------------- scope
def can_see_batch(user: User, b: Batch) -> bool:
    if user.role in ALL_SCOPE:
        return True
    if user.role == "trainer":
        return user.id in (b.trainer_ids or [])
    if user.role == "mentor" and user.id in (b.mentor_ids or []):
        return True
    districts = (user.scope or {}).get("districts") or []
    if districts:
        return b.district in districts or (b.district is None and b.mode == "online")
    return b.created_by_id == user.id


def get_batch(db: Session, user: User, bid: int) -> Batch:
    b = db.get(Batch, bid)
    if not b or not can_see_batch(user, b):
        raise HTTPException(404, "Batch not found")
    return b


def can_run(user: User, b: Batch) -> bool:
    """Trainers run only their own batches; coordinators and managers any batch they can see."""
    return user.role != "trainer" or user.id in (b.trainer_ids or [])


# ---------------------------------------------------------------- attendance and results
def attendance(t: Trainee, b: Batch) -> tuple[int, int, int]:
    """(sessions attended, sessions held so far, total sessions)."""
    held = [s for s in b.sessions if s.done]
    attended = sum(1 for s in b.sessions for a in s.attendance if a.trainee_id == t.id and a.present)
    return attended, len(held), len(b.sessions)


def suggest_result(t: Trainee, b: Batch) -> tuple[str, list[str]]:
    """Pass when attendance, quiz, practical checklist and business-plan score all meet the course rules."""
    c: Course = b.course
    att, _, total = attendance(t, b)
    pct = round(100 * att / total) if total else 0
    why = []
    if pct < c.min_attendance:
        why.append(f"Attendance {pct}% (needs {c.min_attendance}%)")
    if b.pass_mark > 0 and (t.quiz_score is None or t.quiz_score < b.pass_mark):
        why.append(f"Quiz {'not entered' if t.quiz_score is None else f'{t.quiz_score:g}%'} (pass mark {b.pass_mark}%)")
    missing = [i for i in (c.practical_checklist or []) if not (t.practical or {}).get(i)]
    if missing:
        why.append(f"Practical not signed off: {', '.join(missing)}")
    if c.business_plan_score and (t.bp_score is None or t.bp_score < b.pass_mark):
        why.append("Business-plan presentation below the pass mark" if t.bp_score is not None else "Business-plan score not entered")
    return ("pass" if not why else "reassess"), why


def issue_certificate(t: Trainee, b: Batch) -> None:
    if t.certificate_no:
        return
    t.certificate_code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
    t.certified_at = now()
    t.certificate_no = f"MS-{b.course.track.upper()[:4]}-{t.certified_at:%Y}-{t.id:05d}"


def verify_url(t: Trainee) -> str:
    return f"{settings.PUBLIC_URL}/#/verify/{t.certificate_no}?c={t.certificate_code}"


def certificate_data(t: Trainee) -> dict:
    b, c, e = t.batch, t.batch.course, t.entrepreneur
    m_place = ", ".join(x for x in (b.venue, ) if x) or None
    return {
        "name": e.full_name, "course_en": c.name_en, "course_te": c.name_te, "track_en": track_label(c.track), "track_te": track_label(c.track, "te"),
        "start": b.start_date, "end": b.end_date, "hours": sum(float(s.hours or 0) for s in b.sessions) or None, "place": m_place,
        "certificate_no": t.certificate_no, "check_code": t.certificate_code, "issued": t.certified_at.date() if t.certified_at else date.today(), "verify_url": verify_url(t),
        "sponsor": b.sponsor_name if b.sponsor_type in ("csr", "govt") and b.sponsor_name else None,
    }


def certificate_link(t: Trainee) -> str:
    token = jwt.encode({"purpose": "certificate", "tid": t.id, "exp": datetime.now(UTC) + timedelta(minutes=10)},
                       settings.JWT_SECRET, algorithm=ALGO)
    return f"/api/v1/training/certificates/{t.id}.pdf?t={token}"


def bump_stage(e: Entrepreneur, stage: int) -> None:
    """Lifecycle moves forward only."""
    if (e.stage or 1) < stage:
        e.stage = stage


# ---------------------------------------------------------------- recommended tracks
def recommended_tracks(db: Session, e: Entrepreneur) -> list[str]:
    """From the latest training-needs assessment (Form 4.3), else from the readiness assessment's recommendation."""
    na = db.scalar(select(NeedsAssessment).where(NeedsAssessment.entrepreneur_id == e.id).order_by(NeedsAssessment.id.desc()).limit(1))
    if na:
        return list(na.recommended_tracks or [])
    ra = db.scalar(select(ReadinessAssessment).where(ReadinessAssessment.entrepreneur_id == e.id).order_by(ReadinessAssessment.id.desc()).limit(1))
    if ra:
        return list(dict.fromkeys(READINESS_TRACK[r] for r in ra.recommended or [] if r in READINESS_TRACK))
    return ["awareness"]


def suggest_tracks(business_skills: dict, technical_level: int, prior: list, readiness_rec: list[str] | None = None) -> list[str]:
    """Form 4.3 rule: no prior training → Awareness; business skills below 4 on average → Core EDP;
    technical skill below 3 → Skill-based (and On-the-job / Exposure when very low)."""
    tracks = []
    if not prior:
        tracks.append("awareness")
    vals = [v for v in business_skills.values() if isinstance(v, (int, float))]
    if not vals or sum(vals) / len(vals) < 4:
        tracks.append("core")
    if technical_level < 3:
        tracks.append("skill")
        tracks.append("exposure")
    if technical_level <= 1:
        tracks.append("ojt")
    if vals and min(vals) <= 2 and business_skills.get("digital", 5) <= 2:
        tracks.append("refresher")
    for r in readiness_rec or []:
        if r not in tracks:
            tracks.append(r)
    order = list(TRACKS)
    return sorted(dict.fromkeys(tracks), key=order.index)


# ---------------------------------------------------------------- outputs
def course_out(c: Course, lang: str = "en", full: bool = False) -> dict:
    te = lang == "te"
    d = {"id": c.id, "code": c.code, "track": c.track, "track_label": track_label(c.track, lang),
         "name": (c.name_te if te and c.name_te else c.name_en), "name_en": c.name_en, "name_te": c.name_te,
         "duration_days": c.duration_days, "sectors": c.sectors or [], "active": c.active,
         "sessions_count": len(c.sessions or []), "external_certificate": c.external_certificate}
    if full:
        d.update({"description_en": c.description_en, "description_te": c.description_te, "sessions": c.sessions or [],
                  "outcomes": c.outcomes or [], "pass_mark": c.pass_mark, "min_attendance": c.min_attendance,
                  "practical_checklist": c.practical_checklist or [], "business_plan_score": c.business_plan_score})
    else:
        d["description"] = (c.description_te if te and c.description_te else c.description_en)
    return d


def user_names(db: Session, ids) -> dict[int, str]:
    ids = {i for i in ids if i}
    return {u.id: (u.name or u.email or str(u.id)) for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}


def batch_out(db: Session, b: Batch, m: Masters, lang: str = "en", names: dict | None = None) -> dict:
    names = names if names is not None else user_names(db, list(b.trainer_ids or []) + list(b.mentor_ids or []))
    active = [t for t in b.trainees if t.status in ("confirmed", "completed")]
    return {
        "id": b.id, "code": b.code, "course": course_out(b.course, lang), "partner": b.partner.name if b.partner else None,
        "partner_id": b.partner_id, "trainer_ids": b.trainer_ids or [], "mentor_ids": b.mentor_ids or [],
        "trainers": [names.get(i, "") for i in b.trainer_ids or []], "mentors": [names.get(i, "") for i in b.mentor_ids or []],
        "mode": b.mode, "start_date": b.start_date.isoformat(), "end_date": b.end_date.isoformat(), "venue": b.venue, "host_unit": b.host_unit,
        "district": b.district, "district_name": m.name("district", b.district, lang), "seats": b.seats, "filled": len(active),
        "requested": sum(1 for t in b.trainees if t.status == "requested"), "sponsor_type": b.sponsor_type, "sponsor_name": b.sponsor_name,
        "pass_mark": b.pass_mark, "status": b.status, "sessions_total": len(b.sessions), "sessions_done": sum(1 for s in b.sessions if s.done),
        "certified": sum(1 for t in b.trainees if t.certificate_no),
    }


def trainee_out(t: Trainee, b: Batch, m: Masters, names: dict, lang: str = "en") -> dict:
    e = t.entrepreneur
    att, held, total = attendance(t, b)
    sug, why = suggest_result(t, b)
    return {
        "id": t.id, "status": t.status, "source": t.source, "mentor_id": t.mentor_id, "mentor": names.get(t.mentor_id),
        "entrepreneur": {"id": e.id, "full_name": e.full_name, "mobile": e.mobile, "village_name": m.name("village", e.village, lang),
                         "district_name": m.name("district", e.district, lang), "photo_url": photo_url(e.photo), "stage": e.stage},
        "attended": att, "held": held, "total": total, "attendance_pct": round(100 * att / total) if total else 0,
        "quiz_score": t.quiz_score, "practical": t.practical or {}, "practical_hours": t.practical_hours, "bp_score": t.bp_score,
        "result": t.result, "suggested": sug, "suggested_why": why, "certificate_no": t.certificate_no,
        "certified_at": t.certified_at.isoformat() if t.certified_at else None,
        "feedback_rating": t.feedback_rating, "feedback_text": t.feedback_text,
    }


def session_out(s: BatchSession, lang: str = "en") -> dict:
    return {"id": s.id, "n": s.n, "date": s.date.isoformat() if s.date else None,
            "topic": (s.topic_te if lang == "te" and s.topic_te else s.topic), "topic_en": s.topic, "topic_te": s.topic_te, "hours": s.hours,
            "done": s.done, "present": sum(1 for a in s.attendance if a.present),
            "present_ids": [a.trainee_id for a in s.attendance if a.present], "photo_url": photo_url(s.photo),
            "lat": s.lat, "lng": s.lng, "checkin_open": s.checkin_open}


def plan_sessions(b: Batch, c: Course) -> None:
    """Create the batch's sessions from the course, spread over the batch dates."""
    days = max(1, (b.end_date - b.start_date).days + 1)
    items = c.sessions or [{"topic_en": c.name_en, "topic_te": c.name_te, "hours": 3}]
    for i, s in enumerate(items):
        b.sessions.append(BatchSession(n=i + 1, date=b.start_date + timedelta(days=(i * days) // len(items)),
                                       topic=s.get("topic_en") or f"Session {i + 1}", topic_te=s.get("topic_te"), hours=s.get("hours")))


# ---------------------------------------------------------------- files (external certificates)
CERT_DIR = STORAGE / "certificates"
CERT_TYPES = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def save_cert_file(data: bytes, content_type: str) -> str:
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "The file is larger than 10 MB")
    ext = CERT_TYPES.get((content_type or "").split(";")[0])
    if not ext or (ext == ".pdf" and not data.startswith(b"%PDF")):
        raise HTTPException(422, "Upload a PDF or a photo (JPG / PNG)")
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (CERT_DIR / name).write_bytes(data)
    return name


def cert_file_link(name: str) -> str:
    token = jwt.encode({"purpose": "certfile", "f": name, "exp": datetime.now(UTC) + timedelta(minutes=30)}, settings.JWT_SECRET, algorithm=ALGO)
    return f"/api/v1/files/certificate/{name}?t={token}"


def cert_file_path(name: str) -> Path:
    return CERT_DIR / name
