"""Handholding request workflow: who can move a request to which status, and shared helpers.

sent ──expert accepts──▶ accepted ──expert quotes──▶ quoted ──user accepts quote──▶ in_progress ──expert──▶ done
  │                         │                          │ user declines quote ──▶ accepted (expert can re-quote)
  │                         └──expert starts (free)──▶ in_progress
  ├──expert declines──▶ declined ──admin reassigns──▶ sent
  └──user cancels (any time before in_progress)──▶ cancelled
"""
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Artefact, ConnectRequest, ConnectUpdate, Expert, GuidanceSession, User

STATUS_LABELS = {
    "sent": "Waiting for the expert",
    "accepted": "Accepted by the expert",
    "quoted": "Quote received",
    "in_progress": "Work in progress",
    "done": "Completed",
    "declined": "Declined by the expert",
    "cancelled": "Cancelled",
}
OPEN = {"sent", "accepted", "quoted", "in_progress"}
CONTACT_VISIBLE = {"accepted", "quoted", "in_progress", "done"}  # expert sees the user's mobile only after accepting

# role -> current status -> allowed new statuses
TRANSITIONS = {
    "expert": {"sent": {"accepted", "declined"}, "accepted": {"quoted", "in_progress", "declined"},
               "quoted": {"quoted"}, "in_progress": {"done"}},
    "msme": {"sent": {"cancelled"}, "accepted": {"cancelled"}, "quoted": {"in_progress", "accepted", "cancelled"}},
    "admin": {"sent": {"sent", "cancelled"}, "declined": {"sent"}, "accepted": {"sent", "cancelled"}},
}

SERVICE_LABELS = {
    "registration_filing": "Registration filing", "gst_filing": "GST registration / filing", "export_facilitation": "Export facilitation",
    "ecommerce_onboarding": "Online selling set-up", "gem_onboarding": "GeM onboarding", "marketing_support": "Marketing support",
    "sector_advice": "Sector advice", "accounting": "Accounting / bookkeeping", "loan_application": "Loan application",
    "legal_recovery": "Payment recovery", "hr_support": "HR and labour compliance", "training": "Training (EDP / skills)",
    "dpr_preparation": "DPR / project report", "general_advice": "General advice",
}


def change_status(db: Session, req: ConnectRequest, role: str, author_id: int | None, new: str,
                  text: str | None = None, amount: float | None = None, data: dict | None = None) -> ConnectUpdate:
    allowed = TRANSITIONS.get(role, {}).get(req.status, set())
    if new not in allowed:
        raise HTTPException(409, f"This request is “{STATUS_LABELS.get(req.status, req.status)}” – that action is not possible now.")
    req.status = new
    u = ConnectUpdate(request_id=req.id, author_role=role, author_id=author_id, kind="quote" if amount is not None and role == "expert" else "status",
                      status=new, text=text, amount=amount, data=data)
    db.add(u)
    return u


def add_message(db: Session, req: ConnectRequest, role: str, author_id: int | None, text: str) -> ConnectUpdate:
    if req.status in {"cancelled"}:
        raise HTTPException(409, "This request is closed.")
    u = ConnectUpdate(request_id=req.id, author_role=role, author_id=author_id, kind="message", text=text.strip())
    db.add(u)
    return u


def shared_artefact_ids(req: ConnectRequest) -> list[int]:
    ids: list[int] = []
    for u in req.updates:
        if u.kind == "share" and u.data:
            ids += [int(i) for i in u.data.get("artefact_ids", [])]
    return ids


def latest_quote(req: ConnectRequest) -> dict | None:
    q = next((u for u in reversed(req.updates) if u.kind == "quote"), None)
    return {"amount": q.amount, "note": q.text, "at": q.created_at.isoformat() if q.created_at else None} if q else None


def rating_of(req: ConnectRequest) -> dict | None:
    r = next((u for u in reversed(req.updates) if u.kind == "rating"), None)
    return {"stars": int(r.amount), "comment": r.text} if r else None


def due_info(db: Session, req: ConnectRequest) -> dict:
    """Response deadline for the expert, using the database clock (same clock as created_at)."""
    hours = req.expert.response_hours if req.expert else 48
    # Clock starts when the request was last sent (or re-sent after reassignment).
    sent_at = next((u.created_at for u in reversed(req.updates) if u.kind == "status" and u.status == "sent"), req.created_at)
    due = sent_at + timedelta(hours=hours) if sent_at else None
    now = db.scalar(select(func.now()))
    overdue = bool(due and req.status == "sent" and now > due)
    return {"respond_by": due.isoformat() if due else None, "overdue": overdue, "response_hours": hours}


def recompute_expert_rating(db: Session, expert_id: int) -> None:
    avg = db.scalar(select(func.avg(ConnectUpdate.amount)).join(ConnectRequest)
                    .where(ConnectRequest.expert_id == expert_id, ConnectUpdate.kind == "rating"))
    e = db.get(Expert, expert_id)
    if e and avg is not None:
        e.rating = round(float(avg), 1)


def draft_summary(db: Session, user: User, session_id: int | None) -> dict:
    """Case summary (Form G-6) the user can edit before sending: profile, question, gaps."""
    from ..guidance.engine import profile_dict, profile_summary  # local import avoids a cycle
    lines = []
    p = user.profile
    if p:
        name = p.business_name or p.owner_name
        lines.append(f"Business: {name} – {p.product} ({p.district})")
        lines.append("Profile: " + "; ".join(profile_summary(profile_dict(p))))
    service = "general_advice"
    artefacts = []
    if session_id:
        s = db.get(GuidanceSession, session_id)
        if not s or s.user_id != user.id:
            raise HTTPException(404, "Conversation not found")
        lines.append(f"Question: {s.title}")
        last = next((m for m in reversed(s.messages) if m.role == "assistant" and m.payload and m.payload.get("identification")), None)
        if last:
            u = last.payload["understanding"]
            if u.get("intent_title"):
                lines.append(f"Topic: {u['intent_title']}")
            done = {g.item_code for g in s.gaps if g.status == "done"}
            missing = [m["title"] for m in last.payload["identification"]["missing"] if m["code"] not in done]
            have = [h["title"] for h in last.payload["identification"]["have"]] + [g.title for g in s.gaps if g.status == "done"]
            if missing:
                lines.append("Still needed: " + ", ".join(missing))
            if have:
                lines.append("Already has: " + ", ".join(dict.fromkeys(have)))
            service = (last.payload.get("connect") or {}).get("service") or service
        artefacts = list(db.scalars(select(Artefact).where(Artefact.user_id == user.id, Artefact.session_id == session_id)))
    others = list(db.scalars(select(Artefact).where(Artefact.user_id == user.id).order_by(Artefact.id.desc()).limit(20)))
    seen = {a.id for a in artefacts}
    choices = artefacts + [a for a in others if a.id not in seen]
    return {
        "service": service,
        "summary": "\n".join(lines),
        "artefacts": [{"id": a.id, "kind": a.kind, "title": a.title, "from_this_conversation": a.id in seen} for a in choices],
    }
