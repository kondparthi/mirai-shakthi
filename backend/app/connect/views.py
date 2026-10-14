"""Shared JSON shape of a Handholding request for the user, expert and admin screens."""
from sqlalchemy.orm import Session

from ..guidance.engine import profile_dict, profile_summary
from ..models import Artefact, ConnectRequest
from .workflow import (CONTACT_VISIBLE, SERVICE_LABELS, STATUS_LABELS, TRANSITIONS, due_info, latest_quote,
                       rating_of, shared_artefact_ids)


def _iso(dt):
    return dt.isoformat() if dt else None


def actions_for(req: ConnectRequest, role: str) -> list[str]:
    nxt = TRANSITIONS.get(role, {}).get(req.status, set())
    acts = []
    if role == "expert":
        acts += [a for a, s in (("accept", "accepted"), ("decline", "declined"), ("quote", "quoted"),
                                ("start", "in_progress"), ("complete", "done")) if s in nxt]
    elif role == "msme":
        if req.status == "quoted":
            acts += ["accept_quote", "decline_quote"]
        if "cancelled" in nxt:
            acts.append("cancel")
        if req.status == "done" and not rating_of(req):
            acts.append("rate")
    elif role == "admin":
        if "sent" in nxt:
            acts.append("reassign")
        if "cancelled" in nxt:
            acts.append("cancel")
    if req.status not in {"cancelled"}:
        acts.append("message")
    return acts


def request_out(db: Session, req: ConnectRequest, role: str, full: bool = True) -> dict:
    e = req.expert
    d = {
        "id": req.id, "status": req.status, "status_label": STATUS_LABELS.get(req.status, req.status),
        "service": req.service, "service_label": SERVICE_LABELS.get(req.service, req.service),
        "created_at": _iso(req.created_at), "updated_at": _iso(req.updated_at), "session_id": req.session_id,
        "expert": {"id": e.id, "name": e.name, "organisation": e.organisation, "type": e.expert_type, "fee_note": e.fee_note,
                   "response_hours": e.response_hours, "rating": e.rating} if e else None,
        "quote": latest_quote(req), "rating": rating_of(req), **due_info(db, req),
        "last_update": _iso(req.updates[-1].created_at) if req.updates else None,
    }
    if role in ("expert", "admin"):
        u, p = req.user, req.user.profile
        d["client"] = {
            "name": (p.owner_name if p else None) or u.name, "business": p.business_name if p else None,
            "district": p.district if p else None, "language": u.language,
            "mobile": u.mobile if (role == "admin" or req.status in CONTACT_VISIBLE) else None,
            "profile": profile_summary(profile_dict(p)) if p else [],
        }
    if full:
        d["summary"] = req.summary
        d["preferred_contact"] = req.preferred_contact
        d["budget"] = req.budget
        ids = shared_artefact_ids(req)
        arts = [db.get(Artefact, i) for i in ids]
        d["shared_documents"] = [{"id": a.id, "kind": a.kind, "title": a.title} for a in arts if a and a.user_id == req.user_id]
        d["updates"] = [{"id": u.id, "role": u.author_role, "kind": u.kind, "status": u.status,
                         "status_label": STATUS_LABELS.get(u.status) if u.status else None, "text": u.text,
                         "amount": u.amount, "at": _iso(u.created_at)} for u in req.updates if u.kind != "share"]
        d["actions"] = actions_for(req, role)
    return d
