"""M10 – mentoring and two-year handholding: mentor assignment (continuing from training), review drafts from the books (M9),
ticket routing, the 24-month timeline, geo-tags and caseload figures."""
from __future__ import annotations

import io
import math
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..books.service import emi_status, entries_between, month_key, month_range, receivables, summarise
from ..models import User
from ..models_p2 import Trainee
from ..models_p4 import Unit
from ..models_p6 import MonthlySummary
from ..models_p7 import (HANDHOLDING_MONTHS, TICKET_ROUTING, TICKET_SLA_DAYS, FieldVisit, GrowthPlan, MentorReview, Mentorship,
                         SupportTicket)
from ..market.service import now
from ..setup.service import can_see_unit, people


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).day
    return date(y, m, min(d.day, last))


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + b.month - a.month


# ---------------------------------------------------------------- mentor assignment
def training_mentor(db: Session, u: Unit) -> int | None:
    """The mentor the person (or a group member) had in training – continuity from the Core EDP."""
    ids = people(u)
    if not ids:
        return None
    return db.scalar(select(Trainee.mentor_id).where(Trainee.entrepreneur_id.in_(ids), Trainee.mentor_id.is_not(None))
                     .order_by(Trainee.certified_at.is_(None), Trainee.id.desc()).limit(1))


def ensure_mentorship(db: Session, u: Unit, by: User | None = None) -> Mentorship:
    """Every unit gets a mentorship when it is created (at sanction); the 24 months run from launch."""
    ms = db.scalar(select(Mentorship).where(Mentorship.unit_id == u.id))
    start = u.launch_date or date.today()
    if not ms:
        mid = training_mentor(db, u)
        ms = Mentorship(unit_id=u.id, mentor_id=mid, start_date=start, end_date=add_months(start, HANDHOLDING_MONTHS), status="active",
                        history=[{"mentor_id": mid, "from": start.isoformat(), "by": (by.name or by.email) if by else "auto",
                                  "reason": "Mentor from training" if mid else "No mentor yet"}], created_at=now())
        db.add(ms)
        db.flush()
    elif u.launch_date and ms.status == "active" and ms.start_date != u.launch_date and not db.scalar(
            select(MentorReview.id).where(MentorReview.unit_id == u.id).limit(1)):
        ms.start_date, ms.end_date = u.launch_date, add_months(u.launch_date, HANDHOLDING_MONTHS)  # the clock starts at launch
    return ms


def assign_mentor(db: Session, u: Unit, mentor: User | None, by: User, reason: str | None) -> Mentorship:
    ms = ensure_mentorship(db, u, by)
    if ms.status != "active":
        raise HTTPException(409, "Handholding for this unit is closed")
    hist = list(ms.history or [])
    if hist and not hist[-1].get("to"):
        hist[-1] = {**hist[-1], "to": date.today().isoformat()}
    hist.append({"mentor_id": mentor.id if mentor else None, "name": (mentor.name or mentor.email) if mentor else None, "from": date.today().isoformat(),
                 "by": by.name or by.email, "reason": reason or ""})
    ms.mentor_id, ms.history = (mentor.id if mentor else None), hist
    # open "other" tickets follow the mentor
    if mentor:
        for t in db.scalars(select(SupportTicket).where(SupportTicket.unit_id == u.id, SupportTicket.category == "other",
                                                        SupportTicket.status.in_(("open", "in_progress")))):
            t.assigned_to_id = mentor.id
    db.flush()
    return ms


def is_mentor_of(user: User, u: Unit) -> bool:
    ms = getattr(u, "mentorship", None)
    return ms is not None and ms.mentor_id == user.id


# ---------------------------------------------------------------- timeline
def timeline(db: Session, u: Unit, ms: Mentorship | None) -> dict:
    if not ms:
        return {"months": [], "month_no": 0, "total": HANDHOLDING_MONTHS}
    reviews = {r.month: r for r in db.scalars(select(MentorReview).where(MentorReview.unit_id == u.id))}
    visits: dict[str, int] = {}
    for v in db.scalars(select(FieldVisit).where(FieldVisit.unit_id == u.id)):
        visits[month_key(v.on)] = visits.get(month_key(v.on), 0) + 1
    out = []
    today = date.today()
    for k in range(HANDHOLDING_MONTHS):
        d = add_months(ms.start_date.replace(day=1), k)
        key = month_key(d)
        r = reviews.get(key)
        out.append({"n": k + 1, "month": key, "past": d <= today, "health": r.health if r else None, "reviewed": bool(r), "visits": visits.get(key, 0)})
    started = u.status in ("launched", "paused", "closed") and ms.start_date <= today
    return {"months": out, "month_no": min(HANDHOLDING_MONTHS, months_between(ms.start_date, today) + 1) if started else 0, "total": HANDHOLDING_MONTHS,
            "start": ms.start_date.isoformat(), "end": ms.end_date.isoformat(), "can_close": ms.status == "active" and (
                today >= ms.end_date - timedelta(days=60) or u.status == "closed")}


# ---------------------------------------------------------------- monthly review draft (from M9)
def books_for(db: Session, u: Unit, key: str) -> dict:
    """The month's figures from the books: frozen monthly summary when there is one, else live."""
    ms = db.scalar(select(MonthlySummary).where(MonthlySummary.unit_id == u.id, MonthlySummary.month == key))
    if ms:
        return {"sales": ms.sales, "expenses": ms.expenses, "profit": ms.profit, "entries": ms.entries, "days_recorded": ms.days_recorded,
                "emi_status": ms.emi_status or "none", "alerts": ms.alerts or [], "receivables": ms.receivables, "note": ms.note, "frozen": True,
                "summary_id": ms.id}
    start, end = month_range(key)
    s = summarise(entries_between(db, u.id, start, end))
    return {"sales": s["sales"], "expenses": s["expenses"], "profit": s["profit"], "entries": s["entries"], "days_recorded": s["days_recorded"],
            "emi_status": emi_status(db, u, min(end, date.today())), "alerts": [], "frozen": False, "summary_id": None, "note": None,
            "receivables": round(sum(e.amount for e in receivables(db, u.id) if e.on <= end), 2)}


def review_draft(db: Session, u: Unit, key: str) -> dict:
    b = books_for(db, u, key)
    prev = db.scalar(select(MentorReview).where(MentorReview.unit_id == u.id, MentorReview.month < key).order_by(MentorReview.month.desc()).limit(1))
    plan = (u.dpr.results or {}) if u.dpr else {}
    alerts = {a["code"] for a in b["alerts"]}
    health = "red" if (b["profit"] < 0 and b["entries"]) or "emi" in alerts and b["emi_status"] == "default" or "no_entries" in alerts else \
        "amber" if alerts else "green"
    issues = sorted({"sales" for a in alerts if a in ("sales_down", "no_entries")} | {"cash_flow" for a in alerts if a in ("credit_high", "loss", "emi")})
    return {"month": key, "books": b, "sales": b["sales"], "expenses": b["expenses"], "profit": b["profit"],
            "repayment": b["emi_status"] if b["emi_status"] in ("on_time", "delayed", "default") else "none",
            "jobs_family": prev.jobs_family if prev else 1, "jobs_hired": prev.jobs_hired if prev else 0, "health": health, "issues": issues,
            "carry_actions": [a for a in (prev.actions if prev else []) if not a.get("done")],
            "plan": {"monthly_sales": plan.get("monthly_sales_start"), "monthly_profit": plan.get("monthly_profit_y1")}}


# ---------------------------------------------------------------- tickets
def pick_assignee(db: Session, u: Unit, category: str) -> User | None:
    """Auto by category (spec Form 10.2): the staff member with that role who covers the unit's district and has the
    fewest open tickets; the unit's mentor for "other" or when nobody is found; then a coordinator; then a programme manager."""
    role = TICKET_ROUTING.get(category, "mentor")
    ms = db.scalar(select(Mentorship).where(Mentorship.unit_id == u.id))
    mentor = db.get(User, ms.mentor_id) if ms and ms.mentor_id else None
    if role == "mentor" and mentor and mentor.is_active:
        return mentor

    def least_busy(r: str) -> User | None:
        cands = [x for x in db.scalars(select(User).where(User.role == r, User.is_active.is_(True)))
                 if u.district in (((x.scope or {}).get("districts")) or [])]
        if not cands:
            return None
        load = dict(db.execute(select(SupportTicket.assigned_to_id, func.count()).where(SupportTicket.status.in_(("open", "in_progress")))
                               .group_by(SupportTicket.assigned_to_id)).all())
        return min(cands, key=lambda x: (load.get(x.id, 0), x.id))

    return least_busy(role) or (mentor if mentor and mentor.is_active else None) or least_busy("coordinator") or db.scalar(
        select(User).where(User.role == "programme_manager", User.is_active.is_(True)).order_by(User.id).limit(1))


def sla_due(priority: str, start: date | None = None) -> date:
    return (start or date.today()) + timedelta(days=TICKET_SLA_DAYS.get(priority, 5))


def can_work_ticket(user: User, t: SupportTicket, supervise: tuple) -> bool:
    return t.assigned_to_id == user.id or is_mentor_of(user, t.unit) or (user.role in supervise and can_see_unit(user, t.unit))


def can_see_ticket(user: User, t: SupportTicket) -> bool:
    return t.assigned_to_id == user.id or can_see_unit(user, t.unit) or any(r.get("user_id") == user.id for r in t.referrals or [])


def hours_to_resolve(t: SupportTicket) -> float | None:
    if not t.resolved_at or not t.created_at:
        return None
    return round((t.resolved_at - t.created_at).total_seconds() / 3600, 1)


def auto_close_resolved(db: Session) -> None:
    """Resolved tickets the entrepreneur has not re-opened close themselves after 7 days."""
    cut = now() - timedelta(days=7)
    for t in db.scalars(select(SupportTicket).where(SupportTicket.status == "resolved", SupportTicket.resolved_at < cut)):
        t.status, t.closed_at = "closed", now()
        t.events = list(t.events or []) + [{"at": now().isoformat(), "by": "System", "kind": "status", "text": "Closed (7 days after resolution)"}]


# ---------------------------------------------------------------- geo
def exif_gps(data: bytes) -> tuple[float, float] | None:
    """Latitude / longitude stored in the photo by the phone camera, if any."""
    try:
        from PIL import Image

        ex = Image.open(io.BytesIO(data)).getexif()
        gps = ex.get_ifd(0x8825)
        if not gps or 2 not in gps or 4 not in gps:
            return None

        def deg(v, ref):
            d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            return -d if ref in ("S", "W") else d

        lat, lng = deg(gps[2], gps.get(1, "N")), deg(gps[4], gps.get(3, "E"))
        return (lat, lng) if -90 <= lat <= 90 and -180 <= lng <= 180 and (lat or lng) else None
    except Exception:
        return None


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(h)), 1)


# ---------------------------------------------------------------- caseload
def caseload_row(db: Session, u: Unit, ms: Mentorship | None, names: dict[int, str]) -> dict:
    today = date.today()
    last_month = month_key(today.replace(day=1) - timedelta(days=1))
    last = db.scalar(select(MentorReview).where(MentorReview.unit_id == u.id).order_by(MentorReview.month.desc()).limit(1))
    visit = db.scalar(select(FieldVisit).where(FieldVisit.unit_id == u.id).order_by(FieldVisit.on.desc()).limit(1))
    tickets = list(db.scalars(select(SupportTicket).where(SupportTicket.unit_id == u.id, SupportTicket.status.in_(("open", "in_progress")))))
    overdue_actions = sum(1 for r in ([last] if last else []) for a in r.actions or [] if not a.get("done") and a.get("due") and a["due"] < today.isoformat())
    summary = db.scalar(select(MonthlySummary).where(MonthlySummary.unit_id == u.id, MonthlySummary.month == last_month))
    launched = u.status in ("launched", "paused") and u.launch_date
    review_due = bool(launched and u.launch_date < today.replace(day=1) and (not last or last.month < last_month) and ms and ms.status == "active")
    growth = db.scalar(select(func.count()).select_from(GrowthPlan).where(GrowthPlan.unit_id == u.id, GrowthPlan.status == "active")) or 0
    o = u.entrepreneur or u.group
    return {"unit": {"id": u.id, "code": u.code, "name": u.name, "status": u.status, "launch_date": u.launch_date.isoformat() if u.launch_date else None,
                     "owner": getattr(o, "full_name", None) or getattr(o, "name", None) or "—", "mobile": getattr(o, "mobile", None) if u.entrepreneur else None,
                     "district": u.district, "model": u.model.name_en if u.model else None},
            "mentor": {"id": ms.mentor_id, "name": names.get(ms.mentor_id)} if ms and ms.mentor_id else None,
            "status": ms.status if ms else None, "month_no": min(HANDHOLDING_MONTHS, months_between(ms.start_date, today) + 1) if ms and launched else 0,
            "end_date": ms.end_date.isoformat() if ms else None,
            "health": last.health if last else None, "last_review": last.month if last else None, "review_due": review_due, "review_month": last_month,
            "last_visit": visit.on.isoformat() if visit else None, "next_visit": visit.next_visit.isoformat() if visit and visit.next_visit else None,
            "tickets_open": len(tickets), "tickets_high": sum(1 for t in tickets if t.priority == "high"),
            "tickets_overdue": sum(1 for t in tickets if t.due_by and t.due_by < today), "actions_overdue": overdue_actions,
            "alerts": (summary.alerts or []) if summary else [], "growth_plans": growth}
