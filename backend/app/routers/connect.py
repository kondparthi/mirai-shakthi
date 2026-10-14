"""Handholding for MSME users (Form G-6, screen G10): send a case to an expert and follow it up."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..connect.views import request_out
from ..connect.workflow import add_message, change_status, draft_summary, recompute_expert_rating
from ..db import get_db
from ..models import Artefact, AuditLog, ConnectRequest, ConnectUpdate, Expert, User
from ..routers.auth import _now
from ..security import require_roles

router = APIRouter(prefix="/api/v1/connect", tags=["handholding"])
msme = require_roles("msme")


class RequestIn(BaseModel):
    expert_id: int
    session_id: Optional[int] = None
    service: str = Field(min_length=2, max_length=60)
    summary: str = Field(min_length=20, max_length=4000)
    preferred_contact: Literal["call", "whatsapp", "visit"] = "call"
    budget: Optional[Literal["free", "upto_2000", "2000_10000", "above_10000"]] = None
    artefact_ids: list[int] = Field(default=[], max_length=10)
    consent: bool


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class QuoteDecision(BaseModel):
    accept: bool
    note: Optional[str] = Field(default=None, max_length=500)


class RateIn(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)


def _own(db: Session, user: User, rid: int) -> ConnectRequest:
    r = db.get(ConnectRequest, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Request not found")
    return r


@router.get("/draft")
def draft(expert_id: int, session_id: Optional[int] = None, user: User = Depends(msme), db: Session = Depends(get_db)):
    e = db.get(Expert, expert_id)
    if not e or e.status != "approved":
        raise HTTPException(404, "Expert not available")
    d = draft_summary(db, user, session_id)
    if d["service"] not in (e.services or []):
        d["service"] = (e.services or ["general_advice"])[0]
    d["expert"] = {"id": e.id, "name": e.name, "organisation": e.organisation, "services": e.services, "fee_note": e.fee_note,
                   "response_hours": e.response_hours}
    d["shared_with_expert"] = ["Your name and business profile", "The case summary below", "Documents you tick",
                               "Your mobile number – only after the expert accepts"]
    return d


@router.post("/requests")
def create(body: RequestIn, user: User = Depends(msme), db: Session = Depends(get_db)):
    if not body.consent:
        raise HTTPException(422, "Please give consent to share these details with the expert")
    e = db.get(Expert, body.expert_id)
    if not e or e.status != "approved":
        raise HTTPException(404, "Expert not available")
    if body.service not in (e.services or []):
        raise HTTPException(422, "This expert does not offer that service")
    open_dup = db.scalar(select(ConnectRequest.id).where(ConnectRequest.user_id == user.id, ConnectRequest.expert_id == e.id,
                                                         ConnectRequest.service == body.service,
                                                         ConnectRequest.status.in_(["sent", "accepted", "quoted", "in_progress"])))
    if open_dup:
        raise HTTPException(409, "You already have an open request with this expert for this service")
    if body.artefact_ids:
        owned = set(db.scalars(select(Artefact.id).where(Artefact.id.in_(body.artefact_ids), Artefact.user_id == user.id)))
        if owned != set(body.artefact_ids):
            raise HTTPException(422, "Some documents could not be shared")
    if body.session_id:
        draft_summary(db, user, body.session_id)  # ownership check
    r = ConnectRequest(user_id=user.id, expert_id=e.id, session_id=body.session_id, service=body.service, summary=body.summary.strip(),
                       preferred_contact=body.preferred_contact, budget=body.budget, consent_at=_now(), status="sent")
    db.add(r)
    db.flush()
    db.add(ConnectUpdate(request_id=r.id, author_role="msme", author_id=user.id, kind="status", status="sent",
                         text="Request sent to the expert"))
    if body.artefact_ids:
        db.add(ConnectUpdate(request_id=r.id, author_role="msme", author_id=user.id, kind="share", data={"artefact_ids": body.artefact_ids}))
    db.add(AuditLog(user_id=user.id, action="connect_consent", entity="connect_request", entity_id=r.id,
                    detail={"expert_id": e.id, "shared": ["profile", "summary", *[f"artefact:{i}" for i in body.artefact_ids]]}))
    db.commit()
    db.refresh(r)
    return request_out(db, r, "msme")


@router.get("/requests")
def mine(user: User = Depends(msme), db: Session = Depends(get_db)):
    rows = db.scalars(select(ConnectRequest).where(ConnectRequest.user_id == user.id).order_by(ConnectRequest.id.desc()).limit(100))
    return [request_out(db, r, "msme", full=False) for r in rows]


@router.get("/requests/{rid}")
def detail(rid: int, user: User = Depends(msme), db: Session = Depends(get_db)):
    return request_out(db, _own(db, user, rid), "msme")


@router.post("/requests/{rid}/message")
def message(rid: int, body: MessageIn, user: User = Depends(msme), db: Session = Depends(get_db)):
    r = _own(db, user, rid)
    add_message(db, r, "msme", user.id, body.text)
    db.commit()
    db.refresh(r)
    return request_out(db, r, "msme")


@router.post("/requests/{rid}/quote")
def quote_decision(rid: int, body: QuoteDecision, user: User = Depends(msme), db: Session = Depends(get_db)):
    r = _own(db, user, rid)
    if r.status != "quoted":
        raise HTTPException(409, "There is no quote waiting for your decision")
    change_status(db, r, "msme", user.id, "in_progress" if body.accept else "accepted",
                  text=body.note or ("Quote accepted – please go ahead" if body.accept else "Quote not accepted"))
    db.commit()
    db.refresh(r)
    return request_out(db, r, "msme")


@router.post("/requests/{rid}/cancel")
def cancel(rid: int, user: User = Depends(msme), db: Session = Depends(get_db)):
    r = _own(db, user, rid)
    change_status(db, r, "msme", user.id, "cancelled", text="Cancelled by the business owner")
    db.commit()
    db.refresh(r)
    return request_out(db, r, "msme")


@router.post("/requests/{rid}/rate")
def rate(rid: int, body: RateIn, user: User = Depends(msme), db: Session = Depends(get_db)):
    r = _own(db, user, rid)
    if r.status != "done":
        raise HTTPException(409, "You can rate once the expert marks the work done")
    if any(u.kind == "rating" for u in r.updates):
        raise HTTPException(409, "You have already rated this request")
    db.add(ConnectUpdate(request_id=r.id, author_role="msme", author_id=user.id, kind="rating", amount=body.stars, text=body.comment))
    db.flush()
    recompute_expert_rating(db, r.expert_id)
    db.commit()
    db.refresh(r)
    return request_out(db, r, "msme")
