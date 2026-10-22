"""Shared DPR & credit logic: scope, prefilling from the enterprise model, outputs, versions and EMI schedules."""
from __future__ import annotations

import calendar
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import uuid

from fastapi import HTTPException
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import User
from ..models_p2 import Trainee
from ..models_p3 import LOAN_FLOW, LOAN_STATUS, Dpr, EnterpriseModel, LoanApplication, Repayment, Scheme
from ..programme.service import STORAGE, Masters, can_see
from ..roles import ALL_SCOPE
from ..security import ALGO
from . import finance
from .narrative import NOTE_FIELDS, SECTIONS
from .schemes import person_facts

DOC_DIR = STORAGE / "loan_docs"
DOC_TYPES = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
REJECTION_REASONS = {
    "cibil": "Credit history (CIBIL)", "documents": "Documents incomplete", "viability": "Project not viable",
    "area": "Outside the branch's service area", "target": "Bank target / budget exhausted", "other": "Other",
}


def now():
    return datetime.now(UTC).replace(tzinfo=None)


# ---------------------------------------------------------------- scope
def owner(d: Dpr | LoanApplication):
    return d.entrepreneur or d.group


def can_see_dpr(user: User, d: Dpr | LoanApplication) -> bool:
    if user.role in ALL_SCOPE:
        return True
    o = owner(d)
    if o is not None and can_see(user, o):
        return True
    districts = (user.scope or {}).get("districts") or []
    if districts:
        return d.district in districts
    return getattr(d, "prepared_by_id", None) == user.id or getattr(d, "created_by_id", None) == user.id


def get_dpr(db: Session, user: User, did: int) -> Dpr:
    d = db.get(Dpr, did)
    if not d or not can_see_dpr(user, d):
        raise HTTPException(404, "DPR not found")
    return d


def get_application(db: Session, user: User, aid: int) -> LoanApplication:
    a = db.get(LoanApplication, aid)
    if not a or not can_see_dpr(user, a):
        raise HTTPException(404, "Application not found")
    return a


# ---------------------------------------------------------------- prefilling (DPR template = enterprise model)
def round_up(v: float, step: int = 1000) -> float:
    return float(math.ceil(v / step) * step) if v > 0 else 0.0


def inputs_from_model(m: EnterpriseModel | None, own_available: float | None) -> dict:
    items = [{"item": i.get("item", ""), "spec": i.get("spec", ""), "qty": i.get("qty", 1), "rate": i.get("rate", 0)}
             for i in (m.equipment if m else [])]
    capital = sum(float(i["qty"] or 0) * float(i["rate"] or 0) for i in items)
    wc = float(m.working_capital or 0) if m else 0.0
    want = round_up((capital + wc) * 0.10)
    own = min(want, float(own_available)) if own_available else want
    sales = dict(m.sales_template) if m and m.sales_template else {}
    exp = dict(m.expense_template) if m and m.expense_template else {}
    raw = {"capital_items": items, "preoperative": 0, "contingency_pct": 0, "working_capital": wc,
           "finance": {"own": own, "subsidy": 0, "grant": 0}, "sales": sales, "expenses": exp,
           "loan": exp.pop("loan", None) or {"interest_pct": 11, "tenure_months": 60, "moratorium_months": 6},
           "depreciation_pct": 15, "tax_pct": 0, "drawings_monthly": 8000, "years": 5}
    return finance.normalise(raw)


# ---------------------------------------------------------------- context for narrative and PDF
def _age(dob):
    if not dob:
        return None
    t = date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


def location(m: Masters, d: Dpr) -> str:
    parts = [d.address, m.name("village", d.village) or d.village, m.name("mandal", d.mandal), m.name("district", d.district)]
    return ", ".join(p for p in parts if p) or "—"


def _signed(db: Session, uid, at) -> str:
    if not uid:
        return ""
    u = db.get(User, uid)
    return f"{(u.name or u.email) if u else 'Staff'}{', ' + at.strftime('%d %b %Y') if at else ''}"


def promoter(db: Session, m: Masters, d: Dpr) -> dict:
    e, g = d.entrepreneur, d.group
    if e:
        certs = db.scalars(select(Trainee).where(Trainee.entrepreneur_id == e.id, Trainee.certificate_no.is_not(None)))
        return {"name": e.full_name, "age": _age(e.dob), "gender": e.gender, "education": m.name("education", e.education),
                "occupation": m.name("occupation", e.occupation), "skills": [m.name("skill", s) or s for s in e.skills or []],
                "category": m.name("social_category", e.social_category),
                "home": ", ".join(x for x in (m.name("village", e.village), m.name("mandal", e.mandal), m.name("district", e.district)) if x),
                "training": [t.batch.course.name_en for t in certs]}
    if g:
        lead = next((x for x in g.members if x.role == "leader"), None)
        return {"name": g.name, "age": None, "gender": None, "education": None, "occupation": None, "skills": [],
                "category": f"{g.group_type.upper()} of {len(g.members)} members" + (f", led by {lead.name}" if lead else ""), "training": []}
    return {"name": "—", "training": [], "skills": []}


def context(db: Session, d: Dpr, schemes: dict[str, Scheme] | None = None) -> dict:
    m = Masters(db)
    sc = (schemes or {}).get(d.scheme_code) if schemes is not None else (
        db.scalar(select(Scheme).where(Scheme.code == d.scheme_code)) if d.scheme_code else None)
    return {
        "code": d.code or f"#{d.id}", "version": d.version, "status": d.status, "unit_name": d.unit_name, "location": location(m, d),
        "promoter": promoter(db, m, d),
        "model": {"name": d.model.name_en if d.model else "Own enterprise", "description": d.model.description if d.model else None},
        "activity": d.activity, "scheme": sc.name.split(" – ")[0] if sc else None, "jobs": d.model.jobs if d.model else None,
        "notes": d.narrative_notes or {},
        "prepared_by": _signed(db, d.prepared_by_id, d.created_at), "reviewed": _signed(db, d.reviewed_by_id, d.reviewed_at),
        "approved": _signed(db, d.approved_by_id, d.approved_at), "today": date.today().strftime("%d %b %Y"),
    }


# ---------------------------------------------------------------- outputs
def user_names(db: Session, ids) -> dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: (u.name or u.email or "") for u in db.scalars(select(User).where(User.id.in_(ids)))}


def owner_out(m: Masters, d) -> dict:
    if d.entrepreneur:
        e = d.entrepreneur
        return {"type": "entrepreneur", "id": e.id, "name": e.full_name, "mobile": e.mobile, "stage": e.stage,
                "district_name": m.name("district", e.district)}
    if d.group:
        g = d.group
        return {"type": "group", "id": g.id, "name": g.name, "mobile": None, "stage": g.stage, "district_name": m.name("district", g.district)}
    return {"type": None, "id": None, "name": "—"}


def dpr_out(db: Session, d: Dpr, m: Masters | None = None, names: dict | None = None, full: bool = False) -> dict:
    m = m or Masters(db)
    names = names if names is not None else user_names(db, [d.prepared_by_id, d.reviewed_by_id, d.approved_by_id])
    out = {
        "id": d.id, "code": d.code, "unit_name": d.unit_name, "owner": owner_out(m, d), "status": d.status, "version": d.version,
        "model_id": d.model_id, "model": d.model.name_en if d.model else None, "model_te": d.model.name_te if d.model else None,
        "sector": d.model.sector if d.model else None, "activity": d.activity, "scheme_code": d.scheme_code,
        "district": d.district, "district_name": m.name("district", d.district), "results": d.results or {},
        "prepared_by": names.get(d.prepared_by_id), "reviewed_by": names.get(d.reviewed_by_id), "approved_by": names.get(d.approved_by_id),
        "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None, "approved_at": d.approved_at.isoformat() if d.approved_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None, "created_at": d.created_at.isoformat() if d.created_at else None,
    }
    if full:
        out |= {"mandal": d.mandal, "village": d.village, "address": d.address, "lat": d.lat, "lng": d.lng,
                "location": location(m, d), "inputs": d.inputs, "narrative": d.narrative or {}, "narrative_notes": d.narrative_notes or {},
                "narrative_source": d.narrative_source,
                "sections": [{"key": k, "label": v} for k, v in SECTIONS],
                "note_fields": [{"key": k, "label": v, "hint": h} for k, v, h in NOTE_FIELDS],
                "versions": [{"id": v.id, "version": v.version, "status": v.status, "note": v.note,
                              "by": names.get(v.saved_by_id) or user_names(db, [v.saved_by_id]).get(v.saved_by_id),
                              "at": v.created_at.isoformat() if v.created_at else None} for v in d.versions]}
    return out


def snapshot(d: Dpr) -> dict:
    return {"unit_name": d.unit_name, "district": d.district, "mandal": d.mandal, "village": d.village, "address": d.address,
            "activity": d.activity, "scheme_code": d.scheme_code, "model_id": d.model_id, "inputs": d.inputs,
            "narrative": d.narrative or {}, "status": d.status, "version": d.version,
            "reviewed_by_id": d.reviewed_by_id, "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
            "approved_by_id": d.approved_by_id, "approved_at": d.approved_at.isoformat() if d.approved_at else None}


def from_snapshot(d: Dpr, snap: dict) -> Dpr:
    """A detached copy of the DPR as it was (for the PDF of an old version)."""
    c = Dpr(id=d.id, code=d.code, entrepreneur_id=d.entrepreneur_id, group_id=d.group_id, prepared_by_id=d.prepared_by_id,
            created_at=d.created_at)
    c.entrepreneur, c.group = d.entrepreneur, d.group
    for k in ("unit_name", "district", "mandal", "village", "address", "activity", "scheme_code", "inputs", "narrative", "status",
              "version", "reviewed_by_id", "approved_by_id"):
        setattr(c, k, snap.get(k))
    c.model = d.model if snap.get("model_id") == d.model_id else None
    c.reviewed_at = datetime.fromisoformat(snap["reviewed_at"]) if snap.get("reviewed_at") else None
    c.approved_at = datetime.fromisoformat(snap["approved_at"]) if snap.get("approved_at") else None
    c.narrative_notes = {}
    return c


def pdf_link(did: int, version: int | None = None) -> str:
    token = jwt.encode({"purpose": "dpr", "d": did, "v": version, "exp": datetime.now(UTC) + timedelta(minutes=10)},
                       settings.JWT_SECRET, algorithm=ALGO)
    return f"/api/v1/dpr/files/{did}.pdf?t={token}"


# ---------------------------------------------------------------- applications
def facts_for(d: Dpr | LoanApplication) -> dict:
    return person_facts(d.entrepreneur, d.group)


def status_label(s: str, lang: str = "en") -> str:
    v = LOAN_STATUS.get(s, (s, s))
    return v[1] if lang == "te" else v[0]


def repayment_state(r: Repayment, today: date | None = None) -> str:
    t = today or date.today()
    if r.paid_on:
        return "paid" if r.paid_on <= r.due_date + timedelta(days=5) else "late"
    return "overdue" if r.due_date < t else "due" if r.due_date <= t + timedelta(days=30) else "upcoming"


def repayment_summary(a: LoanApplication, today: date | None = None) -> dict | None:
    if not a.repayments:
        return None
    states = [repayment_state(r, today) for r in a.repayments]
    nxt = next((r for r, s in zip(a.repayments, states) if s in ("due", "upcoming", "overdue")), None)
    overdue = [r for r, s in zip(a.repayments, states) if s == "overdue"]
    paid = [r for r in a.repayments if r.paid_on]
    return {"total": len(states), "paid": len(paid), "on_time": states.count("paid"), "late": states.count("late"),
            "overdue": len(overdue), "overdue_amount": round(sum(r.amount for r in overdue), 2),
            "paid_amount": round(sum(r.paid_amount or 0 for r in paid), 2),
            "next": {"n": nxt.n, "due_date": nxt.due_date.isoformat(), "amount": nxt.amount} if nxt else None,
            "health": "default" if len(overdue) >= 3 else "delayed" if overdue or states.count("late") else "on_time"}


def doc_link(name: str) -> str:
    token = jwt.encode({"purpose": "loandoc", "f": name, "exp": datetime.now(UTC) + timedelta(minutes=30)}, settings.JWT_SECRET, algorithm=ALGO)
    return f"/api/v1/dpr/files/doc/{name}?t={token}"


def save_doc(data: bytes, content_type: str) -> str:
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "The file is larger than 10 MB")
    ext = DOC_TYPES.get((content_type or "").split(";")[0])
    if not ext or (ext == ".pdf" and not data.startswith(b"%PDF")):
        raise HTTPException(422, "Upload a PDF or a photo (JPG / PNG)")
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (DOC_DIR / name).write_bytes(data)
    return name


def doc_path(name: str) -> Path:
    return DOC_DIR / name


def application_out(db: Session, a: LoanApplication, m: Masters | None = None, full: bool = False, lang: str = "en",
                    names: dict | None = None) -> dict:
    m = m or Masters(db)
    docs = a.documents or []
    out = {
        "id": a.id, "code": a.code, "dpr_id": a.dpr_id, "dpr_code": a.dpr.code if a.dpr else None, "dpr_version": a.dpr_version,
        "unit_name": a.dpr.unit_name if a.dpr else None, "owner": owner_out(m, a), "scheme_code": a.scheme_code,
        "bank": a.bank, "bank_name": m.name("bank", a.bank, lang) or a.bank, "branch": a.branch, "ifsc": a.ifsc,
        "district_name": m.name("district", a.district, lang),
        "amount_requested": a.amount_requested, "app_number": a.app_number, "portal": a.portal,
        "submitted_on": a.submitted_on.isoformat() if a.submitted_on else None,
        "status": a.status, "status_label": status_label(a.status, lang), "next": list(LOAN_FLOW.get(a.status, ())),
        "sanctioned_amount": a.sanctioned_amount, "subsidy_amount": a.subsidy_amount,
        "sanctioned_on": a.sanctioned_on.isoformat() if a.sanctioned_on else None,
        "disbursed_on": a.disbursed_on.isoformat() if a.disbursed_on else None, "disbursed_amount": a.disbursed_amount,
        "interest_pct": a.interest_pct, "emi_amount": a.emi_amount, "tenure_months": a.tenure_months,
        "first_emi_date": a.first_emi_date.isoformat() if a.first_emi_date else None,
        "rejection_reason": a.rejection_reason, "rejection_label": REJECTION_REASONS.get(a.rejection_reason or "", None),
        "rejection_note": a.rejection_note,
        "docs_total": len(docs), "docs_have": sum(1 for x in docs if x.get("have")),
        "missing_docs": [x["label"] for x in docs if not x.get("have")],
        "repayment": repayment_summary(a),
        "updated_at": a.updated_at.isoformat() if a.updated_at else None, "created_at": a.created_at.isoformat() if a.created_at else None,
    }
    if full:
        names = names if names is not None else user_names(db, [ev.by_id for ev in a.events])
        out["documents"] = [{**x, "url": doc_link(x["file"]) if x.get("file") else None} for x in docs]
        out["events"] = [{"id": ev.id, "kind": ev.kind, "status": ev.status, "status_label": status_label(ev.status, lang) if ev.status else None,
                          "text": ev.text, "on": ev.on.isoformat() if ev.on else None, "by": names.get(ev.by_id),
                          "at": ev.at.isoformat() if ev.at else None} for ev in a.events]
        out["schedule"] = [{"id": r.id, "n": r.n, "due_date": r.due_date.isoformat(), "amount": r.amount, "principal": r.principal,
                            "interest": r.interest, "balance": r.balance, "paid_amount": r.paid_amount,
                            "paid_on": r.paid_on.isoformat() if r.paid_on else None, "note": r.note, "state": repayment_state(r)}
                           for r in a.repayments]
    return out


def add_months(d: date, n: int) -> date:
    y, mth = divmod(d.month - 1 + n, 12)
    y += d.year
    mth += 1
    return date(y, mth, min(d.day, calendar.monthrange(y, mth)[1]))


def emi_rows(principal: float, annual_pct: float, months: int, first: date, emi_amount: float | None = None) -> list[dict]:
    """EMI schedule after disbursement. Uses the bank's EMI when given (the last instalment clears the balance)."""
    if principal <= 0 or months <= 0:
        return []
    r = annual_pct / 1200
    inst = emi_amount or finance.emi(principal, annual_pct, months)
    rows, bal = [], principal
    for n in range(1, months + 1):
        interest = round(bal * r, 2)
        prin = round(bal if n == months else min(bal, inst - interest), 2)
        pay = round(prin + interest, 2)
        bal = round(bal - prin, 2)
        rows.append({"n": n, "due_date": add_months(first, n - 1), "amount": pay, "principal": prin, "interest": interest, "balance": max(0.0, bal)})
        if bal <= 0:
            break
    return rows
