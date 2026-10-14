from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..guidance import engine
from ..models import GuidanceMessage, GuidanceSession, Intent, SessionGap, User
from ..schemas import AskIn, GapUpdate, RateIn
from ..security import require_roles

router = APIRouter(prefix="/api/v1/guidance", tags=["guidance"])
msme = require_roles("msme")


@router.get("/modules")
def modules(lang: str = "en", db: Session = Depends(get_db)):
    """Home screen: the five module cards with popular questions (in Telugu when lang=te)."""
    out = []
    for code, label in engine.MODULE_LABELS.items():
        its = list(db.scalars(select(Intent).where(Intent.module == code, Intent.active.is_(True)).order_by(Intent.id)))
        questions = [engine.sample_question(it, lang) for it in its][:4]
        out.append({"code": code, "name": label["en"], "name_te": label["te"], "area": label["area"], "area_te": label.get("area_te"),
                    "topics": [{"code": it.code, "title": it.title_en, "title_te": it.title_te} for it in its],
                    "popular_questions": questions})
    return out


def _session_out(s: GuidanceSession, with_messages: bool = False) -> dict:
    data = {"id": s.id, "title": s.title, "module": s.module, "intent_code": s.intent_code,
            "current_step": s.current_step, "updated_at": s.updated_at.isoformat() if s.updated_at else None}
    if with_messages:
        data["messages"] = [{"id": m.id, "role": m.role, "content": m.content, "payload": m.payload, "rating": m.rating}
                            for m in s.messages]
        data["gaps"] = [{"code": g.item_code, "title": g.title, "status": g.status} for g in s.gaps]
    return data


def _own_session(db: Session, user: User, session_id: int) -> GuidanceSession:
    s = db.get(GuidanceSession, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return s


@router.post("/ask")
def ask(body: AskIn, user: User = Depends(msme), db: Session = Depends(get_db)):
    lang = body.language or user.language or "en"
    session = _own_session(db, user, body.session_id) if body.session_id else None
    module = body.module or (session.module if session else None)

    result = engine.run(db, body.question, user.profile, lang, module)

    if not session:
        session = GuidanceSession(user_id=user.id, language=lang, title=body.question[:200])
        db.add(session)
        db.flush()
    u = result["understanding"]
    session.module = u["module"] or session.module
    session.intent_code = u["intent_code"] or session.intent_code
    session.current_step = result["current_step"]
    db.add(GuidanceMessage(session_id=session.id, role="user", content=body.question))
    answer_text = result.get("information", {}).get("answer") or result.get("message", "")
    msg = GuidanceMessage(session_id=session.id, role="assistant", content=answer_text, payload=result,
                          flagged=bool(result.get("information") and not result["information"]["grounded"]))
    db.add(msg)

    # Keep the session's gap list in step with the latest identification.
    if "identification" in result:
        existing = {g.item_code: g for g in session.gaps}
        for status, items in (("have", result["identification"]["have"]), ("missing", result["identification"]["missing"])):
            for it in items:
                g = existing.get(it["code"])
                if g is None:
                    db.add(SessionGap(session_id=session.id, item_code=it["code"], title=it["title"], status=status))
                elif g.status != "done":
                    g.status = status
    db.commit()
    return {"session_id": session.id, "message_id": msg.id, **result}


@router.get("/sessions")
def sessions(user: User = Depends(msme), db: Session = Depends(get_db)):
    rows = db.scalars(select(GuidanceSession).where(GuidanceSession.user_id == user.id)
                      .order_by(GuidanceSession.updated_at.desc()).limit(50))
    return [_session_out(s) for s in rows]


@router.get("/sessions/{session_id}")
def session_detail(session_id: int, user: User = Depends(msme), db: Session = Depends(get_db)):
    return _session_out(_own_session(db, user, session_id), with_messages=True)


@router.post("/messages/{message_id}/rate")
def rate(message_id: int, body: RateIn, user: User = Depends(msme), db: Session = Depends(get_db)):
    m = db.get(GuidanceMessage, message_id)
    if not m or m.session.user_id != user.id or m.role != "assistant":
        raise HTTPException(404, "Message not found")
    m.rating = body.rating
    if body.rating < 0:
        m.flagged = True  # goes to conversation review (admin screen A6)
    db.commit()
    return {"ok": True}


@router.patch("/sessions/{session_id}/gaps/{item_code}")
def update_gap(session_id: int, item_code: str, body: GapUpdate, user: User = Depends(msme), db: Session = Depends(get_db)):
    s = _own_session(db, user, session_id)
    g = next((g for g in s.gaps if g.item_code == item_code), None)
    if not g:
        raise HTTPException(404, "Step not found")
    g.status = body.status
    db.commit()
    return {"code": g.item_code, "status": g.status}
