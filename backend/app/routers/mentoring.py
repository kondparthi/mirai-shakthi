"""M10 – mentoring and two-year handholding. Mentors keep a caseload of units: monthly reviews (Form 10.1) built on the books
(M9), field visits with geo-tagged photos, support tickets (Form 10.2) routed by category with referrals to sector experts,
growth plans (Form 10.3), peer sessions per training batch, and a final assessment that closes the 24 months.
The entrepreneur sees their mentor, agreed actions, tickets and growth plans in the app."""
import datetime as dt
import re
from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..models_p1 import ReadinessAssessment
from ..models_p2 import Batch, NeedsAssessment, Trainee
from ..models_p4 import Unit
from ..models_p6 import MonthlySummary
from ..models_p7 import (GOALS, ISSUES, OUTCOMES, SUPPORT, TICKET_CATEGORIES, TRAINING_NEEDS, FieldVisit, GrowthPlan, MentorReview, Mentorship,
                         PeerSession, SupportTicket)
from ..programme.service import Masters
from ..roles import MENTOR_ASSIGN, MENTOR_WRITE, SETUP_READ, TICKET_SUPERVISE
from ..security import current_user, require_roles
from ..setup.service import can_see_unit, file_link, people, save_file
from ..training.service import audit, bump_stage
from ..books.service import auto_close, month_key, month_range
from ..market.service import my_unit_ids, now, unit_access, wa_link
from ..mentoring.service import (assign_mentor, auto_close_resolved, books_for, can_see_ticket, can_work_ticket, caseload_row,
                                 distance_m, ensure_mentorship, exif_gps, hours_to_resolve, is_mentor_of, pick_assignee, review_draft, sla_due,
                                 timeline)

router = APIRouter(prefix="/api/v1/mentoring", tags=["mentoring"])
staff = require_roles(*SETUP_READ)
writer = require_roles(*MENTOR_WRITE)
assigner = require_roles(*MENTOR_ASSIGN)
MONTH = re.compile(r"\d{4}-\d{2}")


def _names(db: Session, ids) -> dict[int, str]:
    ids = [i for i in set(ids) if i]
    return {u.id: (u.name or u.email or u.mobile) for u in db.scalars(select(User).where(User.id.in_(ids or [0])))}


def _unit(db: Session, user: User, uid: int) -> Unit:
    u = db.get(Unit, uid)
    if not u or not can_see_unit(user, u):
        raise HTTPException(404, "Unit not found")
    return u


def _may_mentor(user: User, u: Unit) -> None:
    """Mentors write for the units they mentor; coordinators and managers for units in their scope."""
    if user.role == "mentor" and not is_mentor_of(user, u):
        raise HTTPException(403, "You are not this unit's mentor")
    if user.role not in MENTOR_WRITE:
        raise HTTPException(403, "You do not have access to this")


# ================================================================ meta and caseload
@router.get("/meta")
def meta(user: User = Depends(staff), db: Session = Depends(get_db)):
    mentors = list(db.scalars(select(User).where(User.role == "mentor", User.is_active.is_(True)).order_by(User.name)))
    load = dict(db.execute(select(Mentorship.mentor_id, func.count()).where(Mentorship.status == "active").group_by(Mentorship.mentor_id)).all())
    staff_users = list(db.scalars(select(User).where(User.role.in_(SETUP_READ), User.is_active.is_(True)).order_by(User.role, User.name)))
    return {"mentors": [{"id": m.id, "name": m.name or m.email, "units": load.get(m.id, 0), "districts": (m.scope or {}).get("districts") or []} for m in mentors],
            "staff": [{"id": s.id, "name": s.name or s.email, "role": s.role} for s in staff_users],
            "issues": [{"code": k, "label": v[0]} for k, v in ISSUES.items()], "categories": [{"code": k, "label": v[0]} for k, v in TICKET_CATEGORIES.items()],
            "goals": [{"code": k, "label": v[0]} for k, v in GOALS.items()], "support": [{"code": k, "label": v[0]} for k, v in SUPPORT.items()],
            "training": [{"code": k, "label": v} for k, v in TRAINING_NEEDS.items()], "outcomes": [{"code": k, "label": v} for k, v in OUTCOMES.items()],
            "can": {"write": user.role in MENTOR_WRITE, "assign": user.role in MENTOR_ASSIGN, "supervise": user.role in TICKET_SUPERVISE},
            "me": {"id": user.id, "role": user.role}}


@router.get("/caseload")
def caseload(mentor_id: Optional[int] = None, status: Optional[str] = "active", user: User = Depends(staff), db: Session = Depends(get_db)):
    """Mentors: their own units. Others: units in scope, optionally one mentor's (or "0" for units without a mentor)."""
    rows = []
    q = select(Unit).where(Unit.status != "closed") if status == "active" else select(Unit)
    units = [u for u in db.scalars(q.order_by(Unit.name)) if can_see_unit(user, u)]
    names = _names(db, [u.mentorship.mentor_id for u in units if u.mentorship])
    for u in units:
        ms = u.mentorship or ensure_mentorship(db, u)
        if user.role == "mentor" and ms.mentor_id != user.id:
            continue
        auto_close(db, u)
        if mentor_id is not None and (ms.mentor_id or 0) != mentor_id:
            continue
        if status == "active" and ms.status != "active":
            continue
        rows.append(caseload_row(db, u, ms, names))
    db.commit()
    m = Masters(db)
    for r in rows:
        r["unit"]["district_name"] = m.name("district", r["unit"]["district"])
    rank = {"red": 0, "amber": 1, None: 2, "green": 3}
    rows.sort(key=lambda r: (not r["review_due"], rank.get(r["health"], 2), -r["tickets_open"], r["unit"]["name"]))
    return {"rows": rows, "counts": {"units": len(rows), "review_due": sum(r["review_due"] for r in rows),
                                     "red": sum(r["health"] == "red" for r in rows), "amber": sum(r["health"] == "amber" for r in rows),
                                     "tickets_open": sum(r["tickets_open"] for r in rows), "no_mentor": sum(not r["mentor"] for r in rows)}}


# ================================================================ unit mentoring page
def _review_out(r: MentorReview, names: dict) -> dict:
    return {"id": r.id, "month": r.month, "sales": r.sales, "expenses": r.expenses, "profit": r.profit, "corrected": r.corrected, "books": r.books,
            "repayment": r.repayment, "jobs_family": r.jobs_family, "jobs_hired": r.jobs_hired, "health": r.health, "scores": r.scores or {},
            "issues": r.issues or [], "actions": r.actions or [], "training": r.training or [], "training_done": r.training_done, "note": r.note,
            "mentor": names.get(r.mentor_id), "visit_id": r.visit_id, "at": r.created_at.isoformat() if r.created_at else None}


def _visit_out(v: FieldVisit, names: dict) -> dict:
    return {"id": v.id, "on": v.on.isoformat(), "purpose": v.purpose, "notes": v.notes, "lat": v.lat, "lng": v.lng, "distance_m": v.distance_m,
            "photos": [{**p, "url": file_link(p["name"])} for p in v.photos or []], "next_visit": v.next_visit.isoformat() if v.next_visit else None,
            "by": names.get(v.by_id)}


def _ticket_out(t: SupportTicket, names: dict, lang: str = "en") -> dict:
    late = t.status in ("open", "in_progress") and t.due_by and t.due_by < date.today()
    cat = TICKET_CATEGORIES.get(t.category, (t.category, t.category))
    return {"id": t.id, "code": t.code, "unit": {"id": t.unit.id, "name": t.unit.name, "code": t.unit.code}, "category": t.category,
            "category_label": cat[1] if lang == "te" else cat[0], "description": t.description, "photo_url": file_link(t.photo), "priority": t.priority,
            "channel": t.channel, "status": t.status, "assigned_to": {"id": t.assigned_to_id, "name": names.get(t.assigned_to_id)} if t.assigned_to_id else None,
            "due_by": t.due_by.isoformat() if t.due_by else None, "overdue": bool(late), "resolution": t.resolution, "hours": hours_to_resolve(t),
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None, "rating": t.rating, "referrals": t.referrals or [],
            "events": t.events or [], "raised_by": names.get(t.raised_by_id), "created_at": t.created_at.isoformat() if t.created_at else None}


def _growth_out(g: GrowthPlan, lang: str = "en") -> dict:
    lab = GOALS.get(g.goal, (g.goal, g.goal))
    return {"id": g.id, "goal": g.goal, "goal_label": lab[1] if lang == "te" else lab[0], "target": g.target, "target_date": g.target_date.isoformat(),
            "support": g.support or [], "status": g.status, "progress": g.progress or [], "overdue": g.status == "active" and g.target_date < date.today()}


def _profile(db: Session, u: Unit) -> dict:
    """What the mentor should know from before the enterprise: training results, skill gaps, readiness and the plan."""
    ids = people(u)
    tr = list(db.scalars(select(Trainee).where(Trainee.entrepreneur_id.in_(ids or [0])).order_by(Trainee.id.desc())))
    na = db.scalar(select(NeedsAssessment).where(NeedsAssessment.entrepreneur_id.in_(ids or [0])).order_by(NeedsAssessment.id.desc()).limit(1))
    ra = db.scalar(select(ReadinessAssessment).where((ReadinessAssessment.entrepreneur_id.in_(ids or [0])) | (ReadinessAssessment.group_id == u.group_id))
                   .order_by(ReadinessAssessment.id.desc()).limit(1)) if (ids or u.group_id) else None
    e = u.entrepreneur
    plan = (u.dpr.results or {}) if u.dpr else {}
    return {"entrepreneur": {"id": e.id, "name": e.full_name, "mobile": e.mobile, "education": e.education, "stage": e.stage} if e else None,
            "group": {"id": u.group.id, "name": u.group.name} if u.group else None,
            "training": [{"course": t.batch.course.name_en, "batch": t.batch.code, "result": t.result, "quiz": t.quiz_score, "business_plan": t.bp_score,
                          "certificate": t.certificate_no, "mentor_id": t.mentor_id} for t in tr],
            "skill_gaps": [k for k, v in ((na.business_skills or {}) if na else {}).items() if (v or 0) <= 2],
            "skills": (na.business_skills if na else None),
            "readiness": {"score": ra.score, "gaps": [g.get("label", "") if isinstance(g, dict) else str(g) for g in ra.gaps or []],
                          "strengths": [g.get("label", "") if isinstance(g, dict) else str(g) for g in ra.strengths or []]} if ra else None,
            "plan": {"dpr_id": u.dpr_id, "dpr_code": u.dpr.code if u.dpr else None, "monthly_sales": plan.get("monthly_sales_start"),
                     "monthly_profit": plan.get("monthly_profit_y1"), "loan": plan.get("loan"), "emi": plan.get("emi"), "project_cost": plan.get("project_cost")}}


@router.get("/units/{uid}")
def unit_page(uid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    u = _unit(db, user, uid)
    ms = ensure_mentorship(db, u)
    auto_close(db, u)  # finished months of the books are frozen into monthly summaries (M9)
    db.commit()
    reviews = list(db.scalars(select(MentorReview).where(MentorReview.unit_id == u.id).order_by(MentorReview.month.desc())))
    visits = list(db.scalars(select(FieldVisit).where(FieldVisit.unit_id == u.id).order_by(FieldVisit.on.desc())))
    tickets = list(db.scalars(select(SupportTicket).where(SupportTicket.unit_id == u.id).order_by(SupportTicket.id.desc())))
    growth = list(db.scalars(select(GrowthPlan).where(GrowthPlan.unit_id == u.id).order_by(GrowthPlan.id.desc())))
    names = _names(db, [ms.mentor_id] + [r.mentor_id for r in reviews] + [v.by_id for v in visits] + [t.assigned_to_id for t in tickets]
                   + [t.raised_by_id for t in tickets])
    sums = list(db.scalars(select(MonthlySummary).where(MonthlySummary.unit_id == u.id).order_by(MonthlySummary.month.desc()).limit(12)))
    cur = month_key(date.today())
    live = books_for(db, u, cur) if u.status in ("launched", "paused") else None
    m = Masters(db)
    return {"unit": {"id": u.id, "code": u.code, "name": u.name, "status": u.status, "launch_date": u.launch_date.isoformat() if u.launch_date else None,
                     "district_name": m.name("district", u.district), "place": ", ".join(x for x in (m.name("village", u.village), m.name("mandal", u.mandal)) if x),
                     "model": u.model.name_en if u.model else None, "lat": u.lat, "lng": u.lng},
            "mentorship": {"id": ms.id, "mentor": {"id": ms.mentor_id, "name": names.get(ms.mentor_id)} if ms.mentor_id else None, "status": ms.status,
                           "start_date": ms.start_date.isoformat(), "end_date": ms.end_date.isoformat(), "history": ms.history or [],
                           "closed_on": ms.closed_on.isoformat() if ms.closed_on else None, "outcome": ms.outcome, "final_score": ms.final_score,
                           "final": ms.final},
            "timeline": timeline(db, u, ms), "profile": _profile(db, u),
            "books": {"months": [{"month": s.month, "sales": s.sales, "expenses": s.expenses, "profit": s.profit, "days_recorded": s.days_recorded,
                                  "alerts": s.alerts or [], "note": s.note} for s in sums],
                      "current": {"month": cur, **live} if live else None},
            "reviews": [_review_out(r, names) for r in reviews], "visits": [_visit_out(v, names) for v in visits],
            "tickets": [_ticket_out(t, names) for t in tickets], "growth": [_growth_out(g) for g in growth],
            "can": {"write": user.role in MENTOR_WRITE and (user.role != "mentor" or ms.mentor_id == user.id) and ms.status == "active",
                    "assign": user.role in MENTOR_ASSIGN, "close": user.role in MENTOR_ASSIGN and timeline(db, u, ms)["can_close"]}}


class AssignIn(BaseModel):
    mentor_id: Optional[int] = None
    reason: Optional[str] = Field(default=None, max_length=200)


@router.put("/units/{uid}/mentor")
def set_mentor(uid: int, body: AssignIn, user: User = Depends(assigner), db: Session = Depends(get_db)):
    u = _unit(db, user, uid)
    mentor = None
    if body.mentor_id:
        mentor = db.get(User, body.mentor_id)
        if not mentor or mentor.role != "mentor" or not mentor.is_active:
            raise HTTPException(422, "Choose an active mentor")
    ms = assign_mentor(db, u, mentor, user, body.reason)
    audit(db, user, "mentor_assign", "unit", u.id, {"mentor": body.mentor_id})
    db.commit()
    return {"mentor_id": ms.mentor_id, "history": ms.history}


# ================================================================ monthly review (Form 10.1)
@router.get("/units/{uid}/review-draft")
def get_review_draft(uid: int, month: Optional[str] = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    u = _unit(db, user, uid)
    key = month or month_key(date.today().replace(day=1) - timedelta(days=1))
    if not MONTH.fullmatch(key):
        raise HTTPException(422, "Month must look like 2026-10")
    auto_close(db, u)
    db.flush()
    d = review_draft(db, u, key)
    r = db.scalar(select(MentorReview).where(MentorReview.unit_id == u.id, MentorReview.month == key))
    d["existing"] = _review_out(r, _names(db, [r.mentor_id])) if r else None
    return d


class Action(BaseModel):
    text: str = Field(min_length=3, max_length=200)
    due: Optional[dt.date] = None
    done: bool = False
    done_on: Optional[str] = None


class ReviewIn(BaseModel):
    month: str
    sales: float = Field(ge=0)
    expenses: float = Field(ge=0)
    repayment: Literal["on_time", "delayed", "default", "none"]
    jobs_family: int = Field(ge=0, le=500)
    jobs_hired: int = Field(ge=0, le=500)
    health: Literal["green", "amber", "red"]
    scores: dict[Literal["records", "sales", "operations", "money"], int] = {}
    issues: list[Literal["sales", "cash_flow", "equipment", "skills", "family", "compliance"]] = []
    actions: list[Action] = Field(default=[], max_length=12)
    training: list[Literal["refresher", "advanced", "skill_upgrade"]] = []
    note: Optional[str] = Field(default=None, max_length=3000)
    visit_id: Optional[int] = None


@router.post("/units/{uid}/reviews")
def save_review(uid: int, body: ReviewIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    """Create or update the month's review. Figures come from the books; when the mentor changes them it is marked corrected."""
    u = _unit(db, user, uid)
    _may_mentor(user, u)
    ms = ensure_mentorship(db, u)
    if ms.status != "active":
        raise HTTPException(409, "Handholding for this unit is closed")
    if not MONTH.fullmatch(body.month):
        raise HTTPException(422, "Month must look like 2026-10")
    start, end = month_range(body.month)
    if start > date.today():
        raise HTTPException(422, "The month has not started")
    if u.launch_date and end < u.launch_date.replace(day=1):
        raise HTTPException(422, "The unit was not running that month")
    if any(not 1 <= v <= 5 for v in body.scores.values()):
        raise HTTPException(422, "Scores are 1 to 5")
    if body.health == "red" and not body.actions:
        raise HTTPException(422, "A red rating needs at least one agreed action")
    b = books_for(db, u, body.month)
    corrected = abs(body.sales - b["sales"]) > 0.5 or abs(body.expenses - b["expenses"]) > 0.5
    r = db.scalar(select(MentorReview).where(MentorReview.unit_id == u.id, MentorReview.month == body.month))
    if not r:
        r = MentorReview(unit_id=u.id, month=body.month, created_at=now())
        db.add(r)
    vals = body.model_dump(exclude={"actions"})
    for k, v in vals.items():
        setattr(r, k, v)
    r.actions = [a.model_dump(mode="json") for a in body.actions]
    r.profit, r.corrected, r.books = round(body.sales - body.expenses, 2), corrected, {k: b[k] for k in ("sales", "expenses", "profit", "entries", "days_recorded")}
    r.mentor_id, r.updated_at = user.id, now()
    if body.visit_id and not db.scalar(select(FieldVisit.id).where(FieldVisit.id == body.visit_id, FieldVisit.unit_id == u.id)):
        raise HTTPException(422, "Unknown visit")
    # The M9 monthly summary shows as reviewed (Sprint 6 business tracking)
    if b["summary_id"]:
        s = db.get(MonthlySummary, b["summary_id"])
        s.reviewed_by_id, s.reviewed_at = user.id, now()
        s.review_note = f"Mentor review: {body.health.upper()}" + (f" – {body.note.strip()[:300]}" if body.note else "")
    o = u.entrepreneur or u.group
    if o is not None:
        bump_stage(o, 7)  # Mentor & resolve
    audit(db, user, "mentor_review", "unit", u.id, {"month": body.month, "health": body.health})
    db.commit()
    return _review_out(r, _names(db, [r.mentor_id]))


class ActionDone(BaseModel):
    done: bool


@router.put("/reviews/{rid}/actions/{i}")
def action_done(rid: int, i: int, body: ActionDone, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The mentor, staff in scope or the entrepreneur ticks an agreed action."""
    r = db.get(MentorReview, rid)
    if not r:
        raise HTTPException(404, "Not found")
    if user.role == "msme":
        unit_access(db, user, r.unit_id)
    else:
        u = _unit(db, user, r.unit_id)
        _may_mentor(user, u)
    acts = list(r.actions or [])
    if not 0 <= i < len(acts):
        raise HTTPException(404, "No such action")
    acts[i] = {**acts[i], "done": body.done, "done_on": date.today().isoformat() if body.done else None, "by": "entrepreneur" if user.role == "msme" else "mentor"}
    r.actions = acts
    db.commit()
    return {"actions": r.actions}


@router.post("/reviews/{rid}/training-done")
def training_done(rid: int, user: User = Depends(assigner), db: Session = Depends(get_db)):
    r = db.get(MentorReview, rid)
    if not r:
        raise HTTPException(404, "Not found")
    _unit(db, user, r.unit_id)
    r.training_done = True
    db.commit()
    return {"ok": True}


# ================================================================ field visits
class VisitIn(BaseModel):
    on: dt.date
    purpose: Literal["review", "support", "audit", "training", "other"] = "review"
    notes: str = Field(min_length=5, max_length=4000)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    next_visit: Optional[dt.date] = None


@router.post("/units/{uid}/visits")
def add_visit(uid: int, body: VisitIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    u = _unit(db, user, uid)
    _may_mentor(user, u)
    if body.on > date.today() or body.on < date.today() - timedelta(days=60):
        raise HTTPException(422, "The visit date must be within the last 60 days")
    if body.next_visit and body.next_visit <= body.on:
        raise HTTPException(422, "The next visit must be after this one")
    v = FieldVisit(unit_id=u.id, **body.model_dump(), by_id=user.id, photos=[], created_at=now())
    if v.lat is not None and v.lng is not None and u.lat is not None and u.lng is not None:
        v.distance_m = distance_m((v.lat, v.lng), (u.lat, u.lng))
    db.add(v)
    audit(db, user, "field_visit", "unit", u.id, {"on": body.on.isoformat()})
    db.commit()
    return _visit_out(v, _names(db, [user.id]))


@router.post("/visits/{vid}/photos")
async def visit_photo(vid: int, file: UploadFile = File(...), lat: Optional[float] = Form(default=None), lng: Optional[float] = Form(default=None),
                      user: User = Depends(writer), db: Session = Depends(get_db)):
    """A geo-tagged photo: the phone's position when it was taken, else the location the camera wrote into the photo."""
    v = db.get(FieldVisit, vid)
    if not v:
        raise HTTPException(404, "Not found")
    u = _unit(db, user, v.unit_id)
    _may_mentor(user, u)
    if len(v.photos or []) >= 8:
        raise HTTPException(409, "Up to 8 photos a visit")
    data = await file.read(15 * 1024 * 1024 + 1)
    gps = exif_gps(data)
    src = None
    if lat is not None and lng is not None and -90 <= lat <= 90 and -180 <= lng <= 180:
        src = "device"
    elif gps:
        (lat, lng), src = gps, "exif"
    name = save_file(data, file.content_type or "image/jpeg", images_only=True)
    v.photos = list(v.photos or []) + [{"name": name, "lat": lat if src else None, "lng": lng if src else None, "source": src, "at": now().isoformat()}]
    if src and v.lat is None:
        v.lat, v.lng = lat, lng
        if u.lat is not None and u.lng is not None:
            v.distance_m = distance_m((lat, lng), (u.lat, u.lng))
    db.commit()
    return _visit_out(v, _names(db, [v.by_id]))


# ================================================================ support tickets (Form 10.2)
class TicketIn(BaseModel):
    category: Literal["equipment", "finance", "market", "technical", "registration", "other"]
    description: str = Field(min_length=5, max_length=3000)
    priority: Literal["low", "medium", "high"] = "medium"
    channel: Optional[Literal["app", "call", "navigator", "mentor", "review"]] = None


def _new_ticket(db: Session, u: Unit, body: TicketIn, user: User) -> SupportTicket:
    if u.status == "closed":
        raise HTTPException(409, "This unit is closed")
    who = user.name or user.email or user.mobile
    channel = "app" if user.role == "msme" else (body.channel or ("mentor" if user.role == "mentor" else "navigator" if user.role == "coordinator" else "call"))
    to = pick_assignee(db, u, body.category)
    t = SupportTicket(unit_id=u.id, category=body.category, description=body.description.strip(), priority=body.priority, channel=channel,
                      status="open", assigned_to_id=to.id if to else None, due_by=sla_due(body.priority), raised_by_id=user.id,
                      events=[{"at": now().isoformat(), "by": who, "kind": "opened", "text": f"Raised ({channel})"},
                              {"at": now().isoformat(), "by": "System", "kind": "assigned", "text": f"Assigned to {(to.name or to.email) if to else 'nobody yet'}"}],
                      created_at=now(), updated_at=now())
    t.unit = u
    db.add(t)
    db.flush()
    t.code = f"TK-{date.today().year}-{t.id:05d}"
    return t


@router.post("/units/{uid}/tickets")
def raise_ticket(uid: int, body: TicketIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "msme":
        u = unit_access(db, user, uid)
    else:
        if user.role not in SETUP_READ:
            raise HTTPException(403, "You do not have access to this")
        u = _unit(db, user, uid)
    t = _new_ticket(db, u, body, user)
    audit(db, user, "ticket_open", "ticket", t.id, {"category": t.category, "priority": t.priority})
    db.commit()
    return _ticket_out(t, _names(db, [t.assigned_to_id, t.raised_by_id]), user.language or "en")


@router.get("/tickets")
def list_tickets(view: Literal["mine", "all"] = "mine", status: Optional[str] = None, category: Optional[str] = None, unit_id: Optional[int] = None,
                 user: User = Depends(staff), db: Session = Depends(get_db)):
    auto_close_resolved(db)
    db.commit()
    q = select(SupportTicket).order_by(SupportTicket.id.desc()).limit(1000)
    rows = [t for t in db.scalars(q) if can_see_ticket(user, t)]
    if view == "mine":
        rows = [t for t in rows if t.assigned_to_id == user.id or is_mentor_of(user, t.unit) or any(r.get("user_id") == user.id for r in t.referrals or [])]
    counts = {s: sum(1 for t in rows if t.status == s) for s in ("open", "in_progress", "resolved", "closed")}
    if status == "active":
        rows = [t for t in rows if t.status in ("open", "in_progress")]
    elif status:
        rows = [t for t in rows if t.status == status]
    if category:
        rows = [t for t in rows if t.category == category]
    if unit_id:
        rows = [t for t in rows if t.unit_id == unit_id]
    names = _names(db, [t.assigned_to_id for t in rows] + [t.raised_by_id for t in rows])
    pr = {"high": 0, "medium": 1, "low": 2}
    rows.sort(key=lambda t: (t.status not in ("open", "in_progress"), pr.get(t.priority, 1), t.due_by or date.max))
    return {"counts": counts, "overdue": sum(1 for t in rows if t.status in ("open", "in_progress") and t.due_by and t.due_by < date.today()),
            "rows": [_ticket_out(t, names) for t in rows[:300]]}


def _ticket(db: Session, user: User, tid: int) -> SupportTicket:
    t = db.get(SupportTicket, tid)
    if not t:
        raise HTTPException(404, "Not found")
    if user.role == "msme":
        unit_access(db, user, t.unit_id)
    elif not can_see_ticket(user, t):
        raise HTTPException(404, "Not found")
    return t


def _event(t: SupportTicket, user: User, kind: str, text: str) -> None:
    t.events = list(t.events or []) + [{"at": now().isoformat(), "by": user.name or user.email or user.mobile, "kind": kind, "text": text}]
    t.updated_at = now()


class TicketStatusIn(BaseModel):
    status: Literal["in_progress", "resolved", "closed", "open"]
    resolution: Optional[str] = Field(default=None, max_length=3000)
    note: Optional[str] = Field(default=None, max_length=1000)


FLOW = {"open": ("in_progress", "resolved"), "in_progress": ("resolved", "open"), "resolved": ("closed", "open"), "closed": ()}


@router.post("/tickets/{tid}/status")
def ticket_status(tid: int, body: TicketStatusIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = _ticket(db, user, tid)
    if user.role == "msme":  # the entrepreneur confirms the fix or says it is not fixed
        if t.status != "resolved" or body.status not in ("closed", "open"):
            raise HTTPException(409, "You can confirm or re-open a resolved ticket")
        if body.status == "open" and not (body.note or "").strip():
            raise HTTPException(422, "Say what is still not working")
    elif not can_work_ticket(user, t, TICKET_SUPERVISE):
        raise HTTPException(403, "This ticket is assigned to someone else")
    if body.status not in FLOW.get(t.status, ()):
        raise HTTPException(409, f"Cannot move from {t.status} to {body.status}")
    if body.status == "resolved":
        if not (body.resolution or "").strip():
            raise HTTPException(422, "Write how it was resolved")
        t.resolution, t.resolved_at = body.resolution.strip(), now()
    if body.status == "open":
        t.resolved_at, t.due_by = None, sla_due(t.priority)
    if body.status == "closed":
        t.closed_at = now()
    t.status = body.status
    label = {"in_progress": "Working on it", "resolved": "Resolved", "closed": "Closed", "open": "Re-opened"}[body.status]
    _event(t, user, "status", label + (f": {body.note.strip()}" if body.note else "") + (f" – {t.resolution}" if body.status == "resolved" else ""))
    db.commit()
    return _ticket_out(t, _names(db, [t.assigned_to_id, t.raised_by_id]), user.language or "en")


class AssignTicketIn(BaseModel):
    user_id: int
    note: Optional[str] = Field(default=None, max_length=500)


@router.post("/tickets/{tid}/assign")
def ticket_assign(tid: int, body: AssignTicketIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    t = _ticket(db, user, tid)
    if not (user.role in TICKET_SUPERVISE and can_see_unit(user, t.unit)) and t.assigned_to_id != user.id:
        raise HTTPException(403, "Only the person it is assigned to or a coordinator can pass it on")
    to = db.get(User, body.user_id)
    if not to or not to.is_active or to.role not in SETUP_READ:
        raise HTTPException(422, "Choose an active staff member")
    t.assigned_to_id = to.id
    _event(t, user, "assigned", f"Assigned to {to.name or to.email}" + (f" – {body.note}" if body.note else ""))
    db.commit()
    return _ticket_out(t, _names(db, [t.assigned_to_id, t.raised_by_id]))


class ReferIn(BaseModel):
    kind: Literal["sector_expert", "bdsp", "ca_cs", "bank", "supplier", "government", "other"]
    to: str = Field(min_length=2, max_length=160)
    user_id: Optional[int] = None
    note: Optional[str] = Field(default=None, max_length=1000)


@router.post("/tickets/{tid}/refer")
def ticket_refer(tid: int, body: ReferIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Troubleshooting with a sector expert or a referral outside (BDSP, CA, bank, supplier service). A sector expert with a
    login sees the ticket in their own queue."""
    t = _ticket(db, user, tid)
    if not can_work_ticket(user, t, TICKET_SUPERVISE):
        raise HTTPException(403, "This ticket is assigned to someone else")
    if body.user_id:
        x = db.get(User, body.user_id)
        if not x or not x.is_active or x.role not in SETUP_READ:
            raise HTTPException(422, "Choose an active staff member")
    t.referrals = list(t.referrals or []) + [{**body.model_dump(), "at": now().isoformat(), "by": user.name or user.email}]
    if t.status == "open":
        t.status = "in_progress"
    _event(t, user, "referral", f"Referred to {body.to}" + (f": {body.note}" if body.note else ""))
    db.commit()
    return _ticket_out(t, _names(db, [t.assigned_to_id, t.raised_by_id]))


class CommentIn(BaseModel):
    text: str = Field(min_length=2, max_length=1000)


@router.post("/tickets/{tid}/comment")
def ticket_comment(tid: int, body: CommentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = _ticket(db, user, tid)
    if t.status == "closed":
        raise HTTPException(409, "This ticket is closed")
    _event(t, user, "comment", body.text.strip())
    db.commit()
    return _ticket_out(t, _names(db, [t.assigned_to_id, t.raised_by_id]), user.language or "en")


@router.post("/tickets/{tid}/photo")
async def ticket_photo(tid: int, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = _ticket(db, user, tid)
    t.photo = save_file(await file.read(15 * 1024 * 1024 + 1), file.content_type or "image/jpeg", images_only=True)
    db.commit()
    return {"photo_url": file_link(t.photo)}


class RateIn(BaseModel):
    rating: int = Field(ge=1, le=5)


@router.post("/tickets/{tid}/rate")
def ticket_rate(tid: int, body: RateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = _ticket(db, user, tid)
    if user.role != "msme" or t.status not in ("resolved", "closed"):
        raise HTTPException(409, "The entrepreneur rates a resolved ticket")
    t.rating = body.rating
    if t.status == "resolved":
        t.status, t.closed_at = "closed", now()
        _event(t, user, "status", f"Confirmed fixed · {'★' * body.rating}")
    db.commit()
    return _ticket_out(t, _names(db, [t.assigned_to_id, t.raised_by_id]), user.language or "en")


# ================================================================ growth plans (Form 10.3)
class GrowthIn(BaseModel):
    goal: Literal["increase_sales", "new_product", "second_unit", "hire", "expansion_loan"]
    target: str = Field(min_length=3, max_length=255)
    target_date: dt.date
    support: list[Literal["training", "finance", "market", "equipment"]] = []


@router.post("/units/{uid}/growth")
def add_growth(uid: int, body: GrowthIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    u = _unit(db, user, uid)
    _may_mentor(user, u)
    if u.status not in ("launched", "paused"):
        raise HTTPException(409, "Growth plans are for running units")
    if body.target_date <= date.today() or body.target_date > date.today() + timedelta(days=3 * 366):
        raise HTTPException(422, "The target date must be within the next 3 years")
    g = GrowthPlan(unit_id=u.id, **body.model_dump(), progress=[], created_by_id=user.id, created_at=now(), updated_at=now())
    db.add(g)
    o = u.entrepreneur or u.group
    if o is not None:
        bump_stage(o, 8)  # Grow & sustain
    db.commit()
    return _growth_out(g)


class GrowthUpdateIn(BaseModel):
    status: Optional[Literal["active", "achieved", "dropped"]] = None
    note: Optional[str] = Field(default=None, max_length=500)


@router.put("/growth/{gid}")
def update_growth(gid: int, body: GrowthUpdateIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    g = db.get(GrowthPlan, gid)
    if not g:
        raise HTTPException(404, "Not found")
    _may_mentor(user, _unit(db, user, g.unit_id))
    if body.status:
        g.status = body.status
    if body.note or body.status:
        g.progress = list(g.progress or []) + [{"on": date.today().isoformat(), "text": (body.note or "").strip() or f"Marked {body.status}",
                                                "by": user.name or user.email}]
    db.commit()
    return _growth_out(g)


# ================================================================ final assessment
class CloseIn(BaseModel):
    outcome: Literal["thriving", "stable", "struggling", "closed"]
    final_score: int = Field(ge=1, le=5)
    jobs: int = Field(ge=0, le=1000)
    note: str = Field(min_length=10, max_length=3000)


@router.post("/units/{uid}/close")
def close_handholding(uid: int, body: CloseIn, user: User = Depends(assigner), db: Session = Depends(get_db)):
    """The 24 months end with a final assessment (or earlier when the unit closes)."""
    u = _unit(db, user, uid)
    ms = ensure_mentorship(db, u)
    if not timeline(db, u, ms)["can_close"]:
        raise HTTPException(409, f"Handholding runs until {ms.end_date:%d %b %Y}; it can be closed in its last two months or when the unit closes")
    sums = list(db.scalars(select(MonthlySummary).where(MonthlySummary.unit_id == u.id, MonthlySummary.entries > 0).order_by(MonthlySummary.month)))
    first3, last3 = sums[:3], sums[-3:]
    avg = lambda xs, k: round(sum(getattr(x, k) for x in xs) / len(xs), 2) if xs else None  # noqa: E731
    reviews = list(db.scalars(select(MentorReview).where(MentorReview.unit_id == u.id)))
    tickets = list(db.scalars(select(SupportTicket).where(SupportTicket.unit_id == u.id)))
    ms.status, ms.closed_on, ms.outcome, ms.final_score, ms.closed_by_id = "closed", date.today(), body.outcome, body.final_score, user.id
    ms.final = {"note": body.note.strip(), "jobs": body.jobs, "sales_first3": avg(first3, "sales"), "sales_last3": avg(last3, "sales"),
                "profit_last3": avg(last3, "profit"), "reviews": len(reviews), "red_reviews": sum(r.health == "red" for r in reviews),
                "visits": db.scalar(select(func.count()).select_from(FieldVisit).where(FieldVisit.unit_id == u.id)) or 0,
                "tickets": len(tickets), "tickets_resolved": sum(t.status in ("resolved", "closed") for t in tickets),
                "growth_achieved": db.scalar(select(func.count()).select_from(GrowthPlan).where(GrowthPlan.unit_id == u.id, GrowthPlan.status == "achieved")) or 0}
    o = u.entrepreneur or u.group
    if o is not None:
        bump_stage(o, 8)
    audit(db, user, "handholding_close", "unit", u.id, {"outcome": body.outcome, "score": body.final_score})
    db.commit()
    return unit_page(uid, user, db)


# ================================================================ peer sessions per training batch
@router.get("/batches")
def peer_batches(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Completed or running batches the mentor is attached to (staff: in scope), with their monthly peer sessions."""
    out = []
    for b in db.scalars(select(Batch).where(Batch.status.in_(("ongoing", "completed"))).order_by(Batch.end_date.desc())):
        if user.role == "mentor":
            if user.id not in (b.mentor_ids or []) and not any(t.mentor_id == user.id for t in b.trainees):
                continue
        elif user.role not in ("admin", "programme_manager") and b.district not in ((user.scope or {}).get("districts") or []):
            continue
        sessions = list(db.scalars(select(PeerSession).where(PeerSession.batch_id == b.id).order_by(PeerSession.on.desc())))
        people_ = [t for t in b.trainees if t.status != "withdrawn"]
        last = sessions[0].on if sessions else None
        out.append({"id": b.id, "code": b.code, "course": b.course.name_en, "end_date": b.end_date.isoformat(), "status": b.status,
                    "trainees": [{"id": t.id, "name": t.entrepreneur.full_name} for t in people_],
                    "sessions": [{"id": s.id, "on": s.on.isoformat(), "topic": s.topic, "mode": s.mode, "attended": len(s.attendees or []),
                                  "attendees": s.attendees or [], "notes": s.notes} for s in sessions],
                    "due": b.status == "completed" and (not last or last < date.today().replace(day=1))})
    return out


class PeerIn(BaseModel):
    on: dt.date
    topic: str = Field(min_length=3, max_length=200)
    mode: Literal["in_person", "phone", "video"] = "in_person"
    attendees: list[int] = []
    notes: Optional[str] = Field(default=None, max_length=3000)


@router.post("/batches/{bid}/peer-sessions")
def add_peer(bid: int, body: PeerIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    b = db.get(Batch, bid)
    if not b:
        raise HTTPException(404, "Not found")
    if user.role == "mentor" and user.id not in (b.mentor_ids or []) and not any(t.mentor_id == user.id for t in b.trainees):
        raise HTTPException(403, "You are not a mentor of this batch")
    if user.role not in ("admin", "programme_manager", "mentor") and b.district not in ((user.scope or {}).get("districts") or []):
        raise HTTPException(404, "Not found")
    if body.on > date.today() + timedelta(days=60):
        raise HTTPException(422, "Choose a date within the next 60 days")
    ids = {t.id for t in b.trainees}
    if any(a not in ids for a in body.attendees):
        raise HTTPException(422, "Attendees must be from this batch")
    db.add(PeerSession(batch_id=b.id, **body.model_dump(), mentor_id=user.id, created_at=now()))
    db.commit()
    return peer_batches(user, db)


# ================================================================ dashboard
@router.get("/reports/summary")
def summary(user: User = Depends(staff), db: Session = Depends(get_db)):
    units = [u for u in db.scalars(select(Unit).where(Unit.status.in_(("launched", "paused", "closed")))) if can_see_unit(user, u)]
    ids = {u.id for u in units}
    ms = [m for m in db.scalars(select(Mentorship)) if m.unit_id in ids]
    last = month_key(date.today().replace(day=1) - timedelta(days=1))
    due = [u for u in units if u.status in ("launched", "paused") and u.launch_date and u.launch_date < date.today().replace(day=1)]
    reviewed = set(db.scalars(select(MentorReview.unit_id).where(MentorReview.month == last, MentorReview.unit_id.in_(ids or [0]))))
    latest: dict[int, MentorReview] = {}
    for r in db.scalars(select(MentorReview).where(MentorReview.unit_id.in_(ids or [0])).order_by(MentorReview.month)):
        latest[r.unit_id] = r
    tickets = [t for t in db.scalars(select(SupportTicket).where(SupportTicket.unit_id.in_(ids or [0])))]
    active = [t for t in tickets if t.status in ("open", "in_progress")]
    solved = [h for h in (hours_to_resolve(t) for t in tickets) if h is not None]
    month_start = date.today().replace(day=1)
    visits = db.scalar(select(func.count()).select_from(FieldVisit).where(FieldVisit.unit_id.in_(ids or [0]), FieldVisit.on >= month_start)) or 0
    names = _names(db, [m.mentor_id for m in ms])
    by_mentor: dict = {}
    for m in ms:
        if m.status != "active":
            continue
        k = m.mentor_id or 0
        d = by_mentor.setdefault(k, {"mentor_id": k, "name": names.get(k, "No mentor"), "units": 0, "reviewed": 0, "red": 0})
        d["units"] += 1
        d["reviewed"] += m.unit_id in reviewed
        d["red"] += bool(latest.get(m.unit_id) and latest[m.unit_id].health == "red")
    training = []
    for r in db.scalars(select(MentorReview).where(MentorReview.unit_id.in_(ids or [0]), MentorReview.training_done.is_(False))
                        .order_by(MentorReview.month.desc())):
        if r.training:
            training.append({"review_id": r.id, "unit": {"id": r.unit.id, "name": r.unit.name}, "month": r.month, "training": r.training,
                             "entrepreneur_id": r.unit.entrepreneur_id})
    closed = [m for m in ms if m.status == "closed"]
    return {"units": len(units), "mentored": sum(1 for m in ms if m.status == "active" and m.mentor_id), "no_mentor": sum(1 for m in ms if m.status == "active" and not m.mentor_id),
            "review_month": last, "reviews_due": len(due), "reviewed": sum(1 for u in due if u.id in reviewed),
            "health": {h: sum(1 for r in latest.values() if r.health == h) for h in ("green", "amber", "red")},
            "tickets": {"open": len(active), "overdue": sum(1 for t in active if t.due_by and t.due_by < date.today()),
                        "high": sum(1 for t in active if t.priority == "high"), "resolved": len(solved),
                        "avg_hours": round(sum(solved) / len(solved), 1) if solved else None,
                        "rating": round(sum(t.rating for t in tickets if t.rating) / max(1, sum(1 for t in tickets if t.rating)), 1) if any(t.rating for t in tickets) else None,
                        "by_category": [{"code": c, "label": TICKET_CATEGORIES[c][0], "open": sum(1 for t in active if t.category == c),
                                         "total": sum(1 for t in tickets if t.category == c)} for c in TICKET_CATEGORIES]},
            "visits_month": visits, "by_mentor": sorted(by_mentor.values(), key=lambda d: (-d["units"], d["name"] or "")),
            "training_needs": training[:50],
            "closed": {"count": len(closed), "outcomes": {k: sum(1 for m in closed if m.outcome == k) for k in OUTCOMES}}}


# ================================================================ entrepreneur app
@router.get("/me")
def me(lang: Optional[str] = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """My mentor, the actions we agreed, my support requests and growth plans – for each unit I run."""
    if user.role != "msme":
        raise HTTPException(403, "For entrepreneurs")
    lg = lang if lang in ("en", "te") else (user.language or "en")
    auto_close_resolved(db)
    out = []
    for uid in sorted(my_unit_ids(db, user)):
        u = db.get(Unit, uid)
        ms = ensure_mentorship(db, u)
        mentor = db.get(User, ms.mentor_id) if ms.mentor_id else None
        reviews = list(db.scalars(select(MentorReview).where(MentorReview.unit_id == u.id).order_by(MentorReview.month.desc()).limit(6)))
        tickets = list(db.scalars(select(SupportTicket).where(SupportTicket.unit_id == u.id).order_by(SupportTicket.id.desc()).limit(30)))
        growth = list(db.scalars(select(GrowthPlan).where(GrowthPlan.unit_id == u.id, GrowthPlan.status != "dropped").order_by(GrowthPlan.id.desc())))
        names = _names(db, [t.assigned_to_id for t in tickets] + [t.raised_by_id for t in tickets])
        visit = db.scalar(select(FieldVisit).where(FieldVisit.unit_id == u.id).order_by(FieldVisit.on.desc()).limit(1))
        tl = timeline(db, u, ms)
        hello = (f"నమస్తే, నేను {u.name} నుండి మాట్లాడుతున్నాను." if lg == "te" else f"Hello, this is {user.name or ''} from {u.name}.").replace("  ", " ")
        out.append({"unit": {"id": u.id, "name": u.name, "code": u.code, "status": u.status},
                    "mentor": {"name": mentor.name or mentor.email, "mobile": (mentor.scope or {}).get("phone"),
                               "whatsapp": wa_link((mentor.scope or {}).get("phone"), hello) if (mentor.scope or {}).get("phone") else None} if mentor else None,
                    "handholding": {"status": ms.status, "month_no": tl["month_no"], "total": tl["total"], "end": ms.end_date.isoformat(),
                                    "outcome": ms.outcome},
                    "next_visit": visit.next_visit.isoformat() if visit and visit.next_visit and visit.next_visit >= date.today() else None,
                    "reviews": [{"id": r.id, "month": r.month, "health": r.health, "note": r.note,
                                 "actions": [{**a, "i": i} for i, a in enumerate(r.actions or [])]} for r in reviews],
                    "tickets": [_ticket_out(t, names, lg) for t in tickets], "growth": [_growth_out(g, lg) for g in growth]})
    db.commit()
    cats = [{"code": k, "label": v[1] if lg == "te" else v[0]} for k, v in TICKET_CATEGORIES.items()]
    return {"units": out, "categories": cats}
