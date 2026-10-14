"""Artefacts (usable documents) – Sprint 3.

Roadmap and document checklist come from a guidance conversation; the cash-flow summary (MicroFin, Form G-2)
and job description (SkillsPro) come from their own forms. PDFs are rendered on download via a short-lived link,
so they also open from the Android app.
"""
import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artefacts import pdf
from ..artefacts.cashflow import CashflowIn, calculate
from ..artefacts.statement import MAX_BYTES, StatementError, parse_statement
from ..artefacts.jobs import ONBOARDING, ROLES, JdIn
from ..config import settings
from ..db import get_db
from ..guidance.engine import profile_dict, profile_summary
from ..models import Artefact, AuditLog, GuidanceMessage, GuidanceSession, User
from ..security import ALGO, require_roles

router = APIRouter(prefix="/api/v1/artefacts", tags=["artefacts"])
msme = require_roles("msme")
LINK_MINUTES = 10


class SessionRef(BaseModel):
    session_id: int


def _business(user: User) -> str:
    p = user.profile
    if not p:
        return user.name or ""
    parts = [p.business_name or p.owner_name or user.name or "", p.product or "", p.district or ""]
    return " · ".join(x for x in parts if x)


def _out(a: Artefact, full: bool = False) -> dict:
    d = {"id": a.id, "kind": a.kind, "title": a.title, "session_id": a.session_id,
         "created_at": a.created_at.isoformat() if a.created_at else None}
    if full:
        d["inputs"], d["outputs"] = a.inputs, a.outputs
    return d


def _latest_guidance(db: Session, user: User, session_id: int) -> tuple[GuidanceSession, dict]:
    s = db.get(GuidanceSession, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    msg = db.scalar(select(GuidanceMessage).where(GuidanceMessage.session_id == s.id, GuidanceMessage.role == "assistant")
                    .order_by(GuidanceMessage.id.desc()).limit(1))
    if not msg or not msg.payload or not (msg.payload.get("guidance") or {}).get("steps"):
        raise HTTPException(422, "This conversation has no next steps to put in a document yet")
    return s, msg.payload


@router.get("/roles")
def roles(_: User = Depends(msme)):
    return [{"key": k, **v} for k, v in ROLES.items()]


@router.post("/roadmap")
def make_roadmap(body: SessionRef, user: User = Depends(msme), db: Session = Depends(get_db)):
    s, payload = _latest_guidance(db, user, body.session_id)
    done = {g.item_code for g in s.gaps if g.status == "done"}
    topic = payload["understanding"].get("intent_title") or "My business"
    steps = [{"n": i + 1, "code": st["code"], "title": st["title"], "why": st.get("why"), "documents": st.get("documents"),
              "time": st.get("time"), "cost": st.get("cost"), "link": st.get("link"), "done": st["code"] in done}
             for i, st in enumerate(payload["guidance"]["steps"])]
    outputs = {"topic": topic, "steps": steps, "have": [h["title"] for h in payload["identification"]["have"]],
               "sources": payload["information"].get("sources", []), "profile_summary": profile_summary(profile_dict(user.profile))}
    a = Artefact(user_id=user.id, session_id=s.id, kind="roadmap", title=f"Roadmap – {topic}", outputs=outputs)
    db.add(a)
    db.commit()
    return _out(a, True)


def _split_docs(text: str) -> list[str]:
    # "PAN, Aadhaar, photo, address proof" -> separate documents; keep "(linked mobile)" style notes attached.
    parts = re.split(r",(?![^()]*\))|;| and (?=[A-Z])", text)
    return [x.strip().rstrip(".") for x in parts if x.strip()]


SYNONYMS = {"bank account": "bank details", "bank certificate or cancelled cheque": "bank details",
            "photo id": "id proof", "address": "address proof", "business address proof": "address proof"}


def _doc_key(d: str) -> str:
    key = re.sub(r"\([^)]*\)", "", d.lower())          # drop notes in brackets
    key = re.sub(r"\W+", " ", key).strip()
    return SYNONYMS.get(key, key)


@router.post("/checklist")
def make_checklist(body: SessionRef, user: User = Depends(msme), db: Session = Depends(get_db)):
    s, payload = _latest_guidance(db, user, body.session_id)
    docs: dict[str, dict] = {}
    for st in payload["guidance"]["steps"]:
        for d in _split_docs(st.get("documents") or ""):
            key = _doc_key(d)
            entry = docs.setdefault(key, {"name": d[0].upper() + d[1:], "for": []})
            if len(d) > len(entry["name"]):  # keep the most descriptive wording, e.g. "Aadhaar (linked mobile)"
                entry["name"] = d[0].upper() + d[1:]
            if st["title"] not in entry["for"]:
                entry["for"].append(st["title"])
    if not docs:
        raise HTTPException(422, "No documents are listed for these steps")
    topic = payload["understanding"].get("intent_title") or "My business"
    outputs = {"topic": topic, "documents": sorted(docs.values(), key=lambda d: (-len(d["for"]), d["name"])),
               "profile_summary": profile_summary(profile_dict(user.profile))}
    a = Artefact(user_id=user.id, session_id=s.id, kind="checklist", title=f"Document checklist – {topic}", outputs=outputs)
    db.add(a)
    db.commit()
    return _out(a, True)


@router.post("/cashflow")
def make_cashflow(body: CashflowIn, user: User = Depends(msme), db: Session = Depends(get_db)):
    outputs = calculate(body)
    first, last = body.months[0].month, body.months[-1].month
    a = Artefact(user_id=user.id, kind="cashflow", title=f"Cash-flow summary {first} to {last}" if first != last else f"Cash-flow summary {first}",
                 inputs=body.model_dump(mode="json"), outputs=outputs)
    db.add(a)
    db.commit()
    return _out(a, True)


@router.post("/cashflow/statement")
async def read_statement(file: UploadFile = File(...), password: str | None = Form(default=None), lang: str = Form(default="en"),
                         user: User = Depends(msme), db: Session = Depends(get_db)):
    """Form G-2 helper: turn a bank statement into monthly figures for the user to check.
    The file is read in memory and not stored; only counts are written to the audit log."""
    data = await file.read(MAX_BYTES + 1)
    try:
        result = parse_statement(file.filename or "", data, password or None, "te" if lang == "te" else "en")
    except StatementError as e:
        raise HTTPException(422, str(e)) from e
    finally:
        del data
    s = result["summary"]
    db.add(AuditLog(user_id=user.id, action="statement_import", entity="artefact", entity_id=None,
                    detail={"transactions": s["transactions"], "months": len(result["months"]), "from": s["from"], "to": s["to"]}))
    db.commit()
    return result


@router.post("/jd")
def make_jd(body: JdIn, user: User = Depends(msme), db: Session = Depends(get_db)):
    outputs = {**body.model_dump(), "onboarding": ONBOARDING}
    a = Artefact(user_id=user.id, kind="jd", title=f"Job description – {body.title}", inputs=body.model_dump(), outputs=outputs)
    db.add(a)
    db.commit()
    return _out(a, True)


@router.get("")
def my_artefacts(user: User = Depends(msme), db: Session = Depends(get_db)):
    rows = db.scalars(select(Artefact).where(Artefact.user_id == user.id).order_by(Artefact.id.desc()).limit(100))
    return [_out(a) for a in rows]


def _own(db: Session, user: User, artefact_id: int) -> Artefact:
    a = db.get(Artefact, artefact_id)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Document not found")
    return a


@router.get("/{artefact_id}")
def artefact(artefact_id: int, user: User = Depends(msme), db: Session = Depends(get_db)):
    return _out(_own(db, user, artefact_id), True)


@router.delete("/{artefact_id}")
def delete_artefact(artefact_id: int, user: User = Depends(msme), db: Session = Depends(get_db)):
    db.delete(_own(db, user, artefact_id))
    db.commit()
    return {"ok": True}


@router.post("/{artefact_id}/link")
def download_link(artefact_id: int, user: User = Depends(msme), db: Session = Depends(get_db)):
    a = _own(db, user, artefact_id)
    exp = datetime.now(UTC) + timedelta(minutes=LINK_MINUTES)
    token = jwt.encode({"sub": str(user.id), "aid": a.id, "purpose": "download", "exp": exp}, settings.JWT_SECRET, algorithm=ALGO)
    return {"url": f"/api/v1/artefacts/{a.id}/pdf?t={token}", "expires_in_minutes": LINK_MINUTES}


@router.get("/{artefact_id}/pdf")
def download_pdf(artefact_id: int, t: str = Query(min_length=10), db: Session = Depends(get_db)):
    try:
        claims = jwt.decode(t, settings.JWT_SECRET, algorithms=[ALGO])
    except JWTError:
        raise HTTPException(401, "This download link has expired. Please download again from the app.")
    if claims.get("purpose") != "download" or claims.get("aid") != artefact_id:
        raise HTTPException(403, "Invalid download link")
    a = db.get(Artefact, artefact_id)
    if not a or str(a.user_id) != claims.get("sub"):
        raise HTTPException(404, "Document not found")
    user = db.get(User, a.user_id)
    data = pdf.RENDERERS[a.kind](a.title, a.outputs or {}, _business(user))
    name = re.sub(r"[^A-Za-z0-9]+", "-", a.title).strip("-").lower()[:80] or "document"
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}.pdf"', "Cache-Control": "no-store"})
