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
        from ..models_p2 import ExternalCertificate, Trainee
        out["training"] = [{"course": t.batch.course.name_en, "batch": t.batch.code, "dates": f"{t.batch.start_date} – {t.batch.end_date}",
                            "status": t.status, "result": t.result, "certificate_no": t.certificate_no, "feedback": t.feedback_rating}
                           for t in db.scalars(select(Trainee).where(Trainee.entrepreneur_id == e.id))]
        out["external_certificates"] = [{"title": x.title, "number": x.number, "issuer": x.issuer, "status": x.status}
                                        for x in db.scalars(select(ExternalCertificate).where(ExternalCertificate.entrepreneur_id == e.id))]
        from ..models_p3 import Dpr, LoanApplication
        out["business_plans"] = [{"code": d.code, "unit": d.unit_name, "status": d.status, "version": d.version, "figures": d.results}
                                 for d in db.scalars(select(Dpr).where(Dpr.entrepreneur_id == e.id))]
        out["loan_applications"] = [{"code": a.code, "bank": a.bank, "branch": a.branch, "amount_requested": a.amount_requested,
                                     "status": a.status, "sanctioned": a.sanctioned_amount, "disbursed": a.disbursed_amount,
                                     "emi": a.emi_amount, "repayments": [{"n": r.n, "due": _iso(r.due_date), "amount": r.amount,
                                                                           "paid_on": _iso(r.paid_on)} for r in a.repayments]}
                                    for a in db.scalars(select(LoanApplication).where(LoanApplication.entrepreneur_id == e.id))]
        from ..models_p4 import Unit
        from ..models_p5 import Order
        out["enterprise_units"] = [{"code": u.code, "name": u.name, "status": u.status, "launch_date": _iso(u.launch_date),
                                    "assets": [{"item": a.item, "serial_no": a.serial_no, "value": a.value} for a in u.assets],
                                    "registrations": [{"kind": r.kind, "status": r.status, "number": r.number} for r in u.registrations]}
                                   for u in db.scalars(select(Unit).where(Unit.entrepreneur_id == e.id))]
        out["enterprise_sales"] = [{"unit": u.code, "orders": len(u_orders), "sales": round(sum(o.amount for o in u_orders if o.status in ("delivered", "paid")), 2)}
                                   for u in db.scalars(select(Unit).where(Unit.entrepreneur_id == e.id))
                                   for u_orders in [list(db.scalars(select(Order).where(Order.unit_id == u.id)))]]
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
