"""DPDP Act 2023 – everything MIRAI holds about one person, as plain JSON (right to access)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Artefact, ConnectRequest, GuidanceSession, MsmeProfile, User
from ..models_p1 import DataRequest, Entrepreneur, GroupMember
from .service import Masters, entrepreneur_out


def _iso(d):
    return d.isoformat() if d else None


def person_export(db: Session, user: User) -> dict:
    m = Masters(db)
    out: dict = {
        "account": {"id": user.id, "mobile": user.mobile, "email": user.email, "name": user.name, "role": user.role,
                    "language": user.language, "consent_version": user.consent_version, "consent_at": _iso(user.consent_at),
                    "created_at": _iso(user.created_at)},
        "note": "Aadhaar and bank account numbers are shown masked. MIRAI stores only the last 4 digits of Aadhaar "
                "and keeps the bank account number encrypted.",
    }
    p = db.scalar(select(MsmeProfile).where(MsmeProfile.user_id == user.id))
    if p:
        out["msme_profile"] = {c.name: getattr(p, c.name) for c in MsmeProfile.__table__.columns
                               if c.name not in ("id", "user_id", "created_at", "updated_at")}
    e = db.scalar(select(Entrepreneur).where(Entrepreneur.user_id == user.id))
    if e:
        out["enrolment"] = entrepreneur_out(e, m, user.language or "en", full=True)
        out["readiness_assessments"] = [
            {"at": _iso(a.created_at), "score": a.score, "strengths": a.strengths, "gaps": a.gaps, "recommended": a.recommended,
             "answers": a.answers} for a in e.assessments]
        out["groups"] = [{"group": gm.group.name, "role": gm.role, "contribution": gm.contribution}
                         for gm in db.scalars(select(GroupMember).where(GroupMember.entrepreneur_id == e.id))]
    sessions = list(db.scalars(select(GuidanceSession).where(GuidanceSession.user_id == user.id).order_by(GuidanceSession.id)))
    out["guidance_sessions"] = [
        {"title": s.title, "module": s.module, "at": _iso(s.created_at),
         "messages": [{"role": msg.role, "text": msg.content, "at": _iso(msg.created_at)} for msg in s.messages]} for s in sessions]
    out["documents"] = [{"kind": a.kind, "title": a.title, "at": _iso(a.created_at)}
                        for a in db.scalars(select(Artefact).where(Artefact.user_id == user.id).order_by(Artefact.id))]
    out["expert_requests"] = [{"service": r.service, "summary": r.summary, "status": r.status, "at": _iso(r.created_at)}
                              for r in db.scalars(select(ConnectRequest).where(ConnectRequest.user_id == user.id))]
    out["data_requests"] = [{"kind": r.kind, "status": r.status, "at": _iso(r.created_at), "resolution": r.resolution}
                            for r in db.scalars(select(DataRequest).where(DataRequest.user_id == user.id))]
    return out
