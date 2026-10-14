"""Admin portal APIs (screens A1, A2, A4, A6, A7 and MSME users). Admin and reviewer roles only."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..admin_schemas import SERVICES, ExpertIn, ExpertLoginIn, IntentIn, KbIn, ReassignIn, ReviewIn, RuleIn, TextIn
from ..db import get_db
from ..guidance.engine import MODULE_LABELS, profile_dict, profile_summary
from ..connect.views import request_out
from ..connect.workflow import OPEN, add_message, change_status, due_info
from ..models import (Artefact, AuditLog, ConnectRequest, Expert, GuidanceMessage, GuidanceSession, Intent, KbItem, MsmeProfile,
                      RequirementRule, User)
from ..routers.auth import _now
from ..security import hash_secret, require_roles

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
staff = require_roles("admin", "reviewer")
admin_only = require_roles("admin")


def _audit(db: Session, user: User, action: str, entity: str, entity_id: int | None, detail: dict | None = None):
    db.add(AuditLog(user_id=user.id, action=action, entity=entity, entity_id=entity_id, detail=detail))


def _get(db: Session, model, obj_id: int, label: str):
    obj = db.get(model, obj_id)
    if not obj:
        raise HTTPException(404, f"{label} not found")
    return obj


# ---------------------------------------------------------------- dashboard (A7)
@router.get("/meta")
def meta(_: User = Depends(staff)):
    return {"modules": [{"code": k, "name": v["en"]} for k, v in MODULE_LABELS.items()], "services": SERVICES}


@router.get("/stats")
def stats(_: User = Depends(staff), db: Session = Depends(get_db)):
    since = _now() - timedelta(days=7)
    q_all = select(func.count()).select_from(GuidanceMessage).where(GuidanceMessage.role == "user")
    top = db.execute(
        select(GuidanceSession.intent_code, func.count()).where(GuidanceSession.intent_code.is_not(None))
        .group_by(GuidanceSession.intent_code).order_by(func.count().desc()).limit(8)
    ).all()
    titles = dict(db.execute(select(Intent.code, Intent.title_en)).all())
    by_module = db.execute(
        select(GuidanceSession.module, func.count()).where(GuidanceSession.module.is_not(None)).group_by(GuidanceSession.module)
    ).all()
    return {
        "msme_users": db.scalar(select(func.count()).select_from(User).where(User.role == "msme")),
        "profiles": db.scalar(select(func.count()).select_from(MsmeProfile)),
        "conversations": db.scalar(select(func.count()).select_from(GuidanceSession)),
        "questions": db.scalar(q_all),
        "questions_7d": db.scalar(q_all.where(GuidanceMessage.created_at >= since)),
        "unmatched": db.scalar(select(func.count()).select_from(GuidanceSession).where(GuidanceSession.intent_code.is_(None))),
        "flagged": db.scalar(select(func.count()).select_from(GuidanceMessage).where(GuidanceMessage.flagged.is_(True))),
        "helpful": db.scalar(select(func.count()).select_from(GuidanceMessage).where(GuidanceMessage.rating == 1)),
        "not_helpful": db.scalar(select(func.count()).select_from(GuidanceMessage).where(GuidanceMessage.rating == -1)),
        "kb_published": db.scalar(select(func.count()).select_from(KbItem).where(KbItem.status == "published")),
        "kb_review_due": db.scalar(select(func.count()).select_from(KbItem).where(
            KbItem.status == "published", KbItem.review_due.is_not(None), KbItem.review_due < _now().date() + timedelta(days=30))),
        "experts_pending": db.scalar(select(func.count()).select_from(Expert).where(Expert.status == "pending")),
        "documents": dict(db.execute(select(Artefact.kind, func.count()).group_by(Artefact.kind)).all()),
        "requests_open": db.scalar(select(func.count()).select_from(ConnectRequest).where(ConnectRequest.status.in_(OPEN))),
        "requests_attention": sum(1 for r in db.scalars(select(ConnectRequest).where(ConnectRequest.status.in_(["sent", "declined"])))
                                  if r.status == "declined" or due_info(db, r)["overdue"]),
        "top_topics": [{"code": c, "title": titles.get(c, c), "count": n} for c, n in top],
        "by_module": [{"module": m, "name": MODULE_LABELS.get(m, {}).get("en", m), "count": n} for m, n in by_module],
    }


# ---------------------------------------------------------------- knowledge library (A1)
def _kb_out(k: KbItem) -> dict:
    return {c: (getattr(k, c).isoformat() if hasattr(getattr(k, c), "isoformat") else getattr(k, c))
            for c in ("id", "title", "module", "intent_code", "language", "body", "source_url", "verified_by",
                      "verified_on", "review_due", "status", "updated_at")}


@router.get("/kb")
def kb_list(module: str | None = None, status: str | None = None, q: str | None = None,
            _: User = Depends(staff), db: Session = Depends(get_db)):
    stmt = select(KbItem).order_by(KbItem.updated_at.desc(), KbItem.id.desc())
    if module:
        stmt = stmt.where(KbItem.module == module)
    if status:
        stmt = stmt.where(KbItem.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(KbItem.title.like(like), KbItem.body.like(like)))
    return [_kb_out(k) for k in db.scalars(stmt.limit(500))]


def _check_intent(db: Session, code: str | None):
    if code and not db.scalar(select(Intent.id).where(Intent.code == code)):
        raise HTTPException(422, f"Unknown topic code: {code}")


@router.post("/kb")
def kb_create(body: KbIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    _check_intent(db, body.intent_code)
    if body.status == "published" and not (body.verified_by and body.verified_on):
        raise HTTPException(422, "Add 'verified by' and 'verified on' before publishing")
    k = KbItem(**body.model_dump())
    db.add(k)
    db.flush()
    _audit(db, user, "kb_create", "kb_item", k.id, {"status": k.status})
    db.commit()
    return _kb_out(k)


@router.put("/kb/{item_id}")
def kb_update(item_id: int, body: KbIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    k = _get(db, KbItem, item_id, "Content")
    _check_intent(db, body.intent_code)
    if body.status == "published" and not (body.verified_by and body.verified_on):
        raise HTTPException(422, "Add 'verified by' and 'verified on' before publishing")
    for f, v in body.model_dump().items():
        setattr(k, f, v)
    _audit(db, user, "kb_update", "kb_item", k.id, {"status": k.status})
    db.commit()
    db.refresh(k)
    return _kb_out(k)


# ---------------------------------------------------------------- topics and requirement rules (A2)
def _rule_out(r: RequirementRule) -> dict:
    return {c: getattr(r, c) for c in ("id", "item_code", "title_en", "title_te", "why_en", "why_te", "condition", "have_check",
                                       "step_order", "documents", "time_estimate", "cost_note", "official_link", "active")}


def _intent_out(i: Intent, with_rules: bool = False) -> dict:
    d = {c: getattr(i, c) for c in ("id", "code", "module", "title_en", "title_te", "description", "keywords",
                                    "sample_questions", "connect_service", "active")}
    d["rule_count"] = len(i.rules)
    if with_rules:
        d["rules"] = [_rule_out(r) for r in sorted(i.rules, key=lambda r: (r.step_order, r.id))]
    return d


@router.get("/intents")
def intents(_: User = Depends(staff), db: Session = Depends(get_db)):
    return [_intent_out(i) for i in db.scalars(select(Intent).order_by(Intent.module, Intent.id))]


@router.get("/intents/{intent_id}")
def intent_detail(intent_id: int, _: User = Depends(staff), db: Session = Depends(get_db)):
    return _intent_out(_get(db, Intent, intent_id, "Topic"), with_rules=True)


@router.post("/intents")
def intent_create(body: IntentIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.scalar(select(Intent.id).where(Intent.code == body.code)):
        raise HTTPException(409, "A topic with this code already exists")
    i = Intent(**body.model_dump())
    db.add(i)
    db.flush()
    _audit(db, user, "intent_create", "intent", i.id)
    db.commit()
    return _intent_out(i, True)


@router.put("/intents/{intent_id}")
def intent_update(intent_id: int, body: IntentIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    i = _get(db, Intent, intent_id, "Topic")
    clash = db.scalar(select(Intent.id).where(Intent.code == body.code, Intent.id != intent_id))
    if clash:
        raise HTTPException(409, "A topic with this code already exists")
    old_code = i.code
    for f, v in body.model_dump().items():
        setattr(i, f, v)
    if old_code != i.code:  # keep linked content pointing at the topic
        for k in db.scalars(select(KbItem).where(KbItem.intent_code == old_code)):
            k.intent_code = i.code
    _audit(db, user, "intent_update", "intent", i.id)
    db.commit()
    db.refresh(i)
    return _intent_out(i, True)


@router.post("/intents/{intent_id}/rules")
def rule_create(intent_id: int, body: RuleIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    i = _get(db, Intent, intent_id, "Topic")
    r = RequirementRule(intent_id=i.id, **body.model_dump())
    db.add(r)
    db.flush()
    _audit(db, user, "rule_create", "requirement_rule", r.id, {"intent": i.code})
    db.commit()
    return _rule_out(r)


@router.put("/rules/{rule_id}")
def rule_update(rule_id: int, body: RuleIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    r = _get(db, RequirementRule, rule_id, "Rule")
    for f, v in body.model_dump().items():
        setattr(r, f, v)
    _audit(db, user, "rule_update", "requirement_rule", r.id)
    db.commit()
    return _rule_out(r)


@router.delete("/rules/{rule_id}")
def rule_delete(rule_id: int, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    r = _get(db, RequirementRule, rule_id, "Rule")
    _audit(db, user, "rule_delete", "requirement_rule", r.id, _rule_out(r))
    db.delete(r)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- experts (A4)
def _expert_out(e: Expert, db: Session | None = None) -> dict:
    d = {c: getattr(e, c) for c in ("id", "name", "organisation", "expert_type", "services", "reg_no", "districts",
                                    "languages", "fee_note", "response_hours", "rating", "status")}
    login = db.get(User, e.user_id) if (db and e.user_id) else None
    d["login_email"] = login.email if login else None
    return d


@router.get("/experts")
def experts(status: str | None = None, _: User = Depends(staff), db: Session = Depends(get_db)):
    stmt = select(Expert).order_by(Expert.status, Expert.name)
    if status:
        stmt = stmt.where(Expert.status == status)
    return [_expert_out(e, db) for e in db.scalars(stmt)]


@router.post("/experts")
def expert_create(body: ExpertIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    e = Expert(**body.model_dump())
    db.add(e)
    db.flush()
    _audit(db, user, "expert_create", "expert", e.id)
    db.commit()
    return _expert_out(e)


@router.put("/experts/{expert_id}")
def expert_update(expert_id: int, body: ExpertIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    e = _get(db, Expert, expert_id, "Expert")
    for f, v in body.model_dump().items():
        setattr(e, f, v)
    _audit(db, user, "expert_update", "expert", e.id, {"status": e.status})
    db.commit()
    return _expert_out(e, db)


@router.post("/experts/{expert_id}/login")
def expert_login(expert_id: int, body: ExpertLoginIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Create or reset the expert's portal login (screen E1)."""
    e = _get(db, Expert, expert_id, "Expert")
    email = body.email.strip().lower()
    clash = db.scalar(select(User).where(User.email == email))
    login = db.get(User, e.user_id) if e.user_id else None
    if clash and (not login or clash.id != login.id):
        raise HTTPException(409, "This email is already used by another login")
    if not login:
        login = User(email=email, name=e.name, role="expert")
        db.add(login)
        db.flush()
        e.user_id = login.id
    login.email, login.password_hash, login.is_active = email, hash_secret(body.password), True
    _audit(db, user, "expert_login_set", "expert", e.id, {"email": email})
    db.commit()
    return _expert_out(e, db)


# ---------------------------------------------------------------- answer review (A6)
@router.get("/review")
def review_queue(include_resolved: bool = False, _: User = Depends(staff), db: Session = Depends(get_db)):
    stmt = select(GuidanceMessage).where(GuidanceMessage.role == "assistant")
    stmt = stmt.where(or_(GuidanceMessage.flagged.is_(True), GuidanceMessage.rating == -1)) if include_resolved \
        else stmt.where(GuidanceMessage.flagged.is_(True))
    out = []
    for m in db.scalars(stmt.order_by(GuidanceMessage.id.desc()).limit(200)):
        question = db.scalar(select(GuidanceMessage.content).where(
            GuidanceMessage.session_id == m.session_id, GuidanceMessage.role == "user", GuidanceMessage.id < m.id)
            .order_by(GuidanceMessage.id.desc()).limit(1))
        p = m.payload or {}
        u = p.get("understanding", {})
        info = p.get("information", {})
        reason = ("Rated not helpful" if m.rating == -1 else
                  "No verified source found" if info and not info.get("grounded") else
                  "Topic not recognised" if not u.get("intent_code") else "Flagged")
        out.append({
            "id": m.id, "session_id": m.session_id, "question": question, "answer": m.content, "reason": reason,
            "module": u.get("module"), "intent_code": u.get("intent_code"), "intent_title": u.get("intent_title"),
            "confidence": u.get("confidence"), "rating": m.rating, "flagged": m.flagged,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "sources": [s.get("title") for s in info.get("sources", [])],
        })
    return out


@router.post("/review/{message_id}")
def review_resolve(message_id: int, body: ReviewIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    m = _get(db, GuidanceMessage, message_id, "Answer")
    m.flagged = False
    _audit(db, user, "review_" + body.action, "guidance_message", m.id, {"note": body.note})
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- MSME users
@router.get("/users")
def users(q: str | None = Query(default=None, max_length=60), _: User = Depends(staff), db: Session = Depends(get_db)):
    stmt = select(User).where(User.role == "msme").order_by(User.id.desc())
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.outerjoin(MsmeProfile).where(or_(User.mobile.like(like), User.name.like(like),
                                                     MsmeProfile.business_name.like(like), MsmeProfile.district.like(like)))
    counts = dict(db.execute(select(GuidanceSession.user_id, func.count()).group_by(GuidanceSession.user_id)).all())
    out = []
    for u in db.scalars(stmt.limit(500)):
        p = u.profile
        out.append({
            "id": u.id, "name": u.name, "mobile": u.mobile, "language": u.language,
            "joined": u.created_at.isoformat() if u.created_at else None,
            "business_name": p.business_name if p else None, "district": p.district if p else None,
            "sector": p.sector if p else None, "summary": profile_summary(profile_dict(p)) if p else [],
            "conversations": counts.get(u.id, 0),
        })
    return out


# ---------------------------------------------------------------- Handholding request queue (A5)
@router.get("/requests")
def requests_queue(status: str | None = None, attention: bool = False, _: User = Depends(staff), db: Session = Depends(get_db)):
    stmt = select(ConnectRequest).order_by(ConnectRequest.id.desc())
    if status == "open":
        stmt = stmt.where(ConnectRequest.status.in_(OPEN))
    elif status:
        stmt = stmt.where(ConnectRequest.status == status)
    rows = [request_out(db, r, "admin", full=False) for r in db.scalars(stmt.limit(300))]
    if attention:
        rows = [r for r in rows if r["status"] == "declined" or r["overdue"]]
    return rows


@router.get("/requests/{rid}")
def request_detail(rid: int, _: User = Depends(staff), db: Session = Depends(get_db)):
    return request_out(db, _get(db, ConnectRequest, rid, "Request"), "admin")


@router.post("/requests/{rid}/reassign")
def request_reassign(rid: int, body: ReassignIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    r = _get(db, ConnectRequest, rid, "Request")
    e = _get(db, Expert, body.expert_id, "Expert")
    if e.status != "approved":
        raise HTTPException(422, "Choose an approved expert")
    if r.service not in (e.services or []):
        raise HTTPException(422, "This expert does not offer the requested service")
    old = r.expert.name if r.expert else None
    r.expert_id = e.id
    change_status(db, r, "admin", user.id, "sent", text=body.note or f"Reassigned by MIRAI to {e.name}", data={"from": old, "to": e.name})
    _audit(db, user, "request_reassign", "connect_request", r.id, {"from": old, "to": e.name})
    db.commit()
    db.refresh(r)
    return request_out(db, r, "admin")


@router.post("/requests/{rid}/message")
def request_message(rid: int, body: TextIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    r = _get(db, ConnectRequest, rid, "Request")
    add_message(db, r, "admin", user.id, body.text)
    db.commit()
    db.refresh(r)
    return request_out(db, r, "admin")


@router.post("/requests/{rid}/cancel")
def request_cancel(rid: int, body: TextIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    r = _get(db, ConnectRequest, rid, "Request")
    change_status(db, r, "admin", user.id, "cancelled", text=body.text)
    _audit(db, user, "request_cancel", "connect_request", r.id, {"note": body.text})
    db.commit()
    db.refresh(r)
    return request_out(db, r, "admin")
