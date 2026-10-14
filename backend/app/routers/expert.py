"""Expert workspace (screen E1): CAs, CSs, BDSPs, banks and specialists handle cases sent through Handholding."""
from datetime import UTC, datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..connect.views import request_out
from ..connect.workflow import CONTACT_VISIBLE, OPEN, add_message, change_status, shared_artefact_ids
from ..db import get_db
from ..models import Artefact, ConnectRequest, Expert, User
from ..security import ALGO, require_roles

router = APIRouter(prefix="/api/v1/expert", tags=["expert"])
expert_user = require_roles("expert")


class Note(BaseModel):
    text: Optional[str] = Field(default=None, max_length=2000)


class QuoteIn(BaseModel):
    amount: float = Field(ge=0, le=10_000_000)
    note: str = Field(min_length=5, max_length=2000)


class StatusIn(BaseModel):
    status: Literal["in_progress", "done"]
    text: Optional[str] = Field(default=None, max_length=2000)


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


def _me(db: Session, user: User) -> Expert:
    e = db.scalar(select(Expert).where(Expert.user_id == user.id))
    if not e:
        raise HTTPException(403, "Your login is not linked to an expert profile. Please contact MIRAI.")
    return e


def _case(db: Session, user: User, rid: int) -> tuple[Expert, ConnectRequest]:
    e = _me(db, user)
    r = db.get(ConnectRequest, rid)
    if not r or r.expert_id != e.id:
        raise HTTPException(404, "Case not found")
    return e, r


def _done(db: Session, r: ConnectRequest) -> dict:
    db.commit()
    db.refresh(r)
    return request_out(db, r, "expert")


@router.get("/me")
def me(user: User = Depends(expert_user), db: Session = Depends(get_db)):
    e = _me(db, user)
    counts = dict(db.execute(select(ConnectRequest.status, func.count()).where(ConnectRequest.expert_id == e.id)
                             .group_by(ConnectRequest.status)).all())
    return {"id": e.id, "name": e.name, "organisation": e.organisation, "type": e.expert_type, "services": e.services,
            "districts": e.districts, "rating": e.rating, "response_hours": e.response_hours, "status": e.status, "counts": counts}


@router.get("/requests")
def cases(status: Optional[str] = None, user: User = Depends(expert_user), db: Session = Depends(get_db)):
    e = _me(db, user)
    stmt = select(ConnectRequest).where(ConnectRequest.expert_id == e.id)
    if status == "open":
        stmt = stmt.where(ConnectRequest.status.in_(OPEN))
    elif status:
        stmt = stmt.where(ConnectRequest.status == status)
    return [request_out(db, r, "expert", full=False) for r in db.scalars(stmt.order_by(ConnectRequest.id.desc()).limit(200))]


@router.get("/requests/{rid}")
def case(rid: int, user: User = Depends(expert_user), db: Session = Depends(get_db)):
    return request_out(db, _case(db, user, rid)[1], "expert")


@router.post("/requests/{rid}/accept")
def accept(rid: int, body: Note, user: User = Depends(expert_user), db: Session = Depends(get_db)):
    _, r = _case(db, user, rid)
    change_status(db, r, "expert", user.id, "accepted", text=body.text or "I can help with this. I will contact you shortly.")
    return _done(db, r)


@router.post("/requests/{rid}/decline")
def decline(rid: int, body: Note, user: User = Depends(expert_user), db: Session = Depends(get_db)):
    _, r = _case(db, user, rid)
    if not body.text:
        raise HTTPException(422, "Please give a short reason so MIRAI can find another expert")
    change_status(db, r, "expert", user.id, "declined", text=body.text)
    return _done(db, r)


@router.post("/requests/{rid}/quote")
def quote(rid: int, body: QuoteIn, user: User = Depends(expert_user), db: Session = Depends(get_db)):
    _, r = _case(db, user, rid)
    change_status(db, r, "expert", user.id, "quoted", text=body.note, amount=body.amount)
    return _done(db, r)


@router.post("/requests/{rid}/status")
def status(rid: int, body: StatusIn, user: User = Depends(expert_user), db: Session = Depends(get_db)):
    _, r = _case(db, user, rid)
    default = "Work has started" if body.status == "in_progress" else "Work completed"
    change_status(db, r, "expert", user.id, body.status, text=body.text or default)
    return _done(db, r)


@router.post("/requests/{rid}/message")
def message(rid: int, body: MessageIn, user: User = Depends(expert_user), db: Session = Depends(get_db)):
    _, r = _case(db, user, rid)
    add_message(db, r, "expert", user.id, body.text)
    return _done(db, r)


@router.post("/requests/{rid}/documents/{aid}/link")
def document_link(rid: int, aid: int, user: User = Depends(expert_user), db: Session = Depends(get_db)):
    _, r = _case(db, user, rid)
    if r.status not in CONTACT_VISIBLE or aid not in shared_artefact_ids(r):
        raise HTTPException(403, "This document is available after you accept the case")
    a = db.get(Artefact, aid)
    if not a or a.user_id != r.user_id:
        raise HTTPException(404, "Document not found")
    exp = datetime.now(UTC) + timedelta(minutes=10)
    token = jwt.encode({"sub": str(a.user_id), "aid": a.id, "purpose": "download", "exp": exp}, settings.JWT_SECRET, algorithm=ALGO)
    return {"url": f"/api/v1/artefacts/{a.id}/pdf?t={token}"}
