"""Entrepreneur app – "My business plan & loan": DPR status and key figures, the approved DPR as PDF, loan application
status with history, documents still needed (upload from the phone) and the EMI schedule."""
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..models_p1 import Entrepreneur
from ..models_p3 import Dpr, LoanApplication
from ..programme.service import Masters
from ..security import require_roles
from ..training.service import audit
from ..dpr import finance
from ..dpr.service import application_out, pdf_link, save_doc
from .dpr import attach_file

router = APIRouter(prefix="/api/v1/dpr/me", tags=["dpr-me"])
msme = require_roles("msme")
STATUS_TE = {"draft": "తయారవుతోంది", "reviewed": "పరిశీలించారు", "approved": "ఆమోదించారు"}


def _me(db: Session, user: User) -> Optional[Entrepreneur]:
    return db.scalar(select(Entrepreneur).where(Entrepreneur.user_id == user.id))


def _lg(user: User, lang: Optional[str]) -> str:
    return lang if lang in ("en", "te") else (user.language or "en")


@router.get("")
def my_plan(lang: Optional[str] = None, user: User = Depends(msme), db: Session = Depends(get_db)):
    lang = _lg(user, lang)
    e = _me(db, user)
    if not e:
        return {"enrolled": False, "dprs": [], "applications": []}
    m = Masters(db)
    dprs = []
    for d in db.scalars(select(Dpr).where(Dpr.entrepreneur_id == e.id).order_by(Dpr.id.desc())):
        s = finance.calculate(d.inputs)["summary"]
        dprs.append({
            "id": d.id, "code": d.code, "unit_name": d.unit_name, "version": d.version, "status": d.status,
            "status_label": STATUS_TE.get(d.status, d.status) if lang == "te" else d.status.capitalize(),
            "model": (d.model.name_te or d.model.name_en) if d.model and lang == "te" else (d.model.name_en if d.model else None),
            "scheme_code": d.scheme_code, "can_download": d.status == "approved",
            "figures": {k: round(s[k], 2) if isinstance(s[k], float) else s[k] for k in
                        ("project_cost", "own", "loan", "subsidy", "grant", "emi", "emi_months", "monthly_sales_start", "monthly_profit_y1",
                         "bep_pct_y1", "payback_months")},
        })
    apps = []
    for a in db.scalars(select(LoanApplication).where(LoanApplication.entrepreneur_id == e.id).order_by(LoanApplication.id.desc())):
        o = application_out(db, a, m, full=True, lang=lang, names={})
        o["events"] = [x for x in o["events"] if x["kind"] in ("status", "query", "response")]
        o["documents"] = [{k: x[k] for k in ("code", "label", "have", "note")} for x in o["documents"]]
        apps.append(o)
    return {"enrolled": True, "stage": e.stage, "dprs": dprs, "applications": apps}


@router.post("/dprs/{did}/pdf-link")
def my_pdf(did: int, user: User = Depends(msme), db: Session = Depends(get_db)):
    e = _me(db, user)
    d = db.get(Dpr, did)
    if not e or not d or d.entrepreneur_id != e.id:
        raise HTTPException(404, "Not found")
    if d.status != "approved":
        raise HTTPException(409, "The DPR can be downloaded after the DPR officer approves it")
    return {"url": pdf_link(d.id)}


@router.post("/applications/{aid}/documents/{code}")
async def my_document(aid: int, code: str, file: UploadFile = File(...), user: User = Depends(msme), db: Session = Depends(get_db)):
    e = _me(db, user)
    a = db.get(LoanApplication, aid)
    if not e or not a or a.entrepreneur_id != e.id:
        raise HTTPException(404, "Not found")
    if a.status in ("disbursed", "rejected", "withdrawn"):
        raise HTTPException(409, "This application is closed")
    name = save_doc(await file.read(10 * 1024 * 1024 + 1), file.content_type or "")
    attach_file(a, code, name, "Uploaded by the entrepreneur – staff to check")
    audit(db, user, "loan_document_self", "loan_application", a.id, {"code": code})
    db.commit()
    return my_plan(None, user, db)
