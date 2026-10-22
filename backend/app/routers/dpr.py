"""M5 DPR preparation and M6 credit & scheme facilitation for staff: enterprise models (DPR templates), scheme library,
DPR builder (Form 5.1) with review / approval and versions, credit applications (Forms 6.1, 6.2), EMI repayment tracking,
reports. Every figure comes from app/dpr/finance.py; the AI only drafts the narrative."""
import csv
import io
import re
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import User
from ..models_p1 import EGroup, Entrepreneur, MasterItem
from ..models_p2 import Trainee
from ..models_p3 import ACTIVITIES, LOAN_FLOW, LOAN_STATUS, Dpr, DprVersion, EnterpriseModel, LoanApplication, LoanEvent, Repayment, Scheme
from ..programme.service import Masters, can_see
from ..roles import DPR_APPROVE, DPR_READ, DPR_WRITE, MODELS_WRITE, SCHEMES_WRITE
from ..security import ALGO, require_roles
from ..training.service import audit, bump_stage
from ..dpr import finance, narrative, pdf
from ..guidance import llm
from ..dpr.schemes import documents_for, eligibility
from ..dpr.service import (REJECTION_REASONS, application_out, can_see_dpr, context, doc_path, dpr_out, emi_rows, facts_for,
                           from_snapshot, get_application, get_dpr, inputs_from_model, now, pdf_link, repayment_summary, round_up,
                           save_doc, snapshot, status_label, user_names)

router = APIRouter(prefix="/api/v1/dpr", tags=["dpr"])
reader = require_roles(*DPR_READ)
writer = require_roles(*DPR_WRITE)
approver = require_roles(*DPR_APPROVE)
ACTIVITY = Literal["manufacturing", "service", "trading", "agri_allied"]


def _schemes(db: Session) -> list[Scheme]:
    return list(db.scalars(select(Scheme).order_by(Scheme.id)))


def _scheme(db: Session, code: Optional[str]) -> Optional[Scheme]:
    if not code:
        return None
    s = db.scalar(select(Scheme).where(Scheme.code == code))
    if not s:
        raise HTTPException(422, f"Unknown scheme: {code}")
    return s


# ================================================================ meta
@router.get("/meta")
def meta(user: User = Depends(reader), db: Session = Depends(get_db)):
    banks = db.scalars(select(MasterItem).where(MasterItem.kind == "bank").order_by(MasterItem.sort, MasterItem.name_en))
    return {
        "models": [model_out(x) for x in db.scalars(select(EnterpriseModel).order_by(EnterpriseModel.sector, EnterpriseModel.name_en))],
        "schemes": [scheme_out(x) for x in _schemes(db) if x.active],
        "banks": [{"code": b.code, "name": b.name_en} for b in banks],
        "activities": [{"code": k, "label": v} for k, v in ACTIVITIES.items()],
        "statuses": [{"code": k, "label": v[0]} for k, v in LOAN_STATUS.items()],
        "flow": {k: list(v) for k, v in LOAN_FLOW.items()},
        "rejection_reasons": [{"code": k, "label": v} for k, v in REJECTION_REASONS.items()],
        "sections": [{"key": k, "label": v} for k, v in narrative.SECTIONS],
        "can": {"write": user.role in DPR_WRITE, "approve": user.role in DPR_APPROVE, "models": user.role in MODELS_WRITE,
                "schemes": user.role in SCHEMES_WRITE},
        "ai": llm.enabled(),
    }


# ================================================================ enterprise models (Form 3.1 – DPR templates)
def model_out(x: EnterpriseModel) -> dict:
    cap = sum(float(i.get("qty") or 0) * float(i.get("rate") or 0) for i in x.equipment or [])
    return {"id": x.id, "code": x.code, "sector": x.sector, "name_en": x.name_en, "name_te": x.name_te, "description": x.description,
            "activity": x.activity, "context_tags": x.context_tags or [], "investment_min": x.investment_min, "investment_max": x.investment_max,
            "working_capital": x.working_capital, "equipment": x.equipment or [], "equipment_total": cap, "infrastructure": x.infrastructure or [],
            "skills": x.skills or [], "schemes": x.schemes or [], "sales_template": x.sales_template or {}, "expense_template": x.expense_template or {},
            "expected_monthly_sales": x.expected_monthly_sales, "jobs": x.jobs, "payback_months": x.payback_months, "status": x.status}


class EquipmentIn(BaseModel):
    item: str = Field(min_length=2, max_length=160)
    spec: Optional[str] = Field(default="", max_length=200)
    qty: float = Field(gt=0, le=10000)
    rate: float = Field(ge=0, le=100_000_000)
    suppliers: Optional[str] = Field(default=None, max_length=255)


class SalesItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    unit: str = Field(default="unit", min_length=1, max_length=30)
    units_per_day: float = Field(ge=0, le=100000)
    price: float = Field(ge=0, le=10_000_000)


class SalesIn(BaseModel):
    items: list[SalesItemIn] = Field(default_factory=list, max_length=40)
    working_days: float = Field(default=26, ge=0, le=31)
    monthly_growth_pct: float = Field(default=0, ge=-20, le=20)
    yearly_growth_pct: float = Field(default=5, ge=-50, le=50)


class ExpensesIn(BaseModel):
    raw_material_pct: float = Field(default=0, ge=0, le=100)
    salaries: float = Field(default=0, ge=0)
    rent: float = Field(default=0, ge=0)
    fuel: float = Field(default=0, ge=0)
    maintenance: float = Field(default=0, ge=0)
    other: float = Field(default=0, ge=0)
    yearly_increase_pct: float = Field(default=5, ge=0, le=50)


class ModelIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_]+$")
    sector: str = Field(min_length=2, max_length=40)
    name_en: str = Field(min_length=2, max_length=160)
    name_te: Optional[str] = Field(default=None, max_length=160)
    description: Optional[str] = Field(default=None, max_length=3000)
    activity: ACTIVITY = "service"
    context_tags: list[Literal["rural", "urban", "tribal", "coastal"]] = Field(min_length=1)
    investment_min: float = Field(ge=0)
    investment_max: float = Field(ge=0)
    working_capital: float = Field(ge=0)
    equipment: list[EquipmentIn] = Field(min_length=1, max_length=60)
    infrastructure: list[str] = []
    skills: list[str] = []
    schemes: list[str] = []
    sales_template: SalesIn
    expense_template: ExpensesIn
    expected_monthly_sales: float = Field(ge=0)
    jobs: int = Field(ge=0, le=1000)
    payback_months: int = Field(ge=0, le=240)
    status: Literal["catalogue", "pilot", "active"] = "catalogue"


def _check_model(db: Session, body: ModelIn):
    m = Masters(db)
    errs = []
    if not m.has("sector", body.sector):
        errs.append(f"Unknown sector: {body.sector}")
    errs += [f"Unknown skill: {s}" for s in body.skills if not m.has("skill", s)]
    known = {s.code for s in _schemes(db)}
    errs += [f"Unknown scheme: {s}" for s in body.schemes if s not in known]
    if body.investment_max and body.investment_max < body.investment_min:
        errs.append("Investment maximum is below the minimum")
    if errs:
        raise HTTPException(422, "; ".join(errs))


@router.get("/models")
def list_models(_: User = Depends(reader), db: Session = Depends(get_db)):
    return [model_out(x) for x in db.scalars(select(EnterpriseModel).order_by(EnterpriseModel.sector, EnterpriseModel.name_en))]


@router.post("/models")
def create_model(body: ModelIn, user: User = Depends(require_roles(*MODELS_WRITE)), db: Session = Depends(get_db)):
    if db.scalar(select(EnterpriseModel).where(EnterpriseModel.code == body.code)):
        raise HTTPException(409, "A model with this code exists")
    _check_model(db, body)
    x = EnterpriseModel(**body.model_dump())
    db.add(x)
    db.flush()
    audit(db, user, "model_create", "enterprise_model", x.id, {"code": x.code})
    db.commit()
    return model_out(x)


@router.put("/models/{mid}")
def update_model(mid: int, body: ModelIn, user: User = Depends(require_roles(*MODELS_WRITE)), db: Session = Depends(get_db)):
    x = db.get(EnterpriseModel, mid)
    if not x:
        raise HTTPException(404, "Model not found")
    if body.code != x.code and db.scalar(select(EnterpriseModel).where(EnterpriseModel.code == body.code)):
        raise HTTPException(409, "A model with this code exists")
    _check_model(db, body)
    for k, v in body.model_dump().items():
        setattr(x, k, v)
    audit(db, user, "model_update", "enterprise_model", x.id, {"code": x.code})
    db.commit()
    return model_out(x)


# ================================================================ scheme library (M6)
def scheme_out(s: Scheme) -> dict:
    return {"id": s.id, "code": s.code, "name": s.name, "name_te": s.name_te, "kind": s.kind, "agency": s.agency,
            "description": s.description, "url": s.url, "rules": s.rules or {}, "documents": s.documents or [], "active": s.active,
            "verified_on": s.verified_on.isoformat() if s.verified_on else None, "sample": s.sample}


class DocIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=2, max_length=160)
    when: Literal["always", "special", "rural"] = "always"


class SchemeIn(BaseModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=3, max_length=200)
    name_te: Optional[str] = Field(default=None, max_length=200)
    kind: Literal["central", "state", "bank", "csr"] = "central"
    agency: Optional[str] = Field(default=None, max_length=160)
    description: Optional[str] = Field(default=None, max_length=3000)
    url: Optional[str] = Field(default=None, max_length=255)
    rules: dict = {}
    documents: list[DocIn] = []
    active: bool = True
    verified_on: Optional[date] = None

    @field_validator("rules")
    @classmethod
    def v_rules(cls, v):
        allowed = {"min_age", "max_age", "activities", "sectors", "requires_any", "new_unit_only", "min_project_cost", "max_project_cost",
                   "min_loan", "max_loan", "min_education", "education_above_cost", "own_pct", "subsidy_pct", "subsidy_on", "subsidy_cap",
                   "tiers", "notes"}
        bad = set(v) - allowed
        if bad:
            raise ValueError(f"Unknown rule: {', '.join(sorted(bad))}")
        for k in ("own_pct", "subsidy_pct"):
            for x in (v.get(k) or {}).values():
                if not isinstance(x, (int, float)) or not 0 <= x <= 100:
                    raise ValueError(f"{k.replace('_', ' ')} must be between 0 and 100")
        return v

    @field_validator("verified_on")
    @classmethod
    def v_verified(cls, v):
        if v and v > date.today():
            raise ValueError("Verified on cannot be in the future")
        return v


@router.get("/schemes")
def list_schemes(_: User = Depends(reader), db: Session = Depends(get_db)):
    return [scheme_out(s) for s in _schemes(db)]


@router.post("/schemes")
def create_scheme(body: SchemeIn, user: User = Depends(require_roles(*SCHEMES_WRITE)), db: Session = Depends(get_db)):
    if db.scalar(select(Scheme).where(Scheme.code == body.code)):
        raise HTTPException(409, "A scheme with this code exists")
    s = Scheme(**body.model_dump(exclude={"documents"}), documents=[d.model_dump() for d in body.documents], sample=False)
    db.add(s)
    db.flush()
    audit(db, user, "scheme_create", "scheme", s.id, {"code": s.code})
    db.commit()
    return scheme_out(s)


@router.put("/schemes/{sid}")
def update_scheme(sid: int, body: SchemeIn, user: User = Depends(require_roles(*SCHEMES_WRITE)), db: Session = Depends(get_db)):
    s = db.get(Scheme, sid)
    if not s:
        raise HTTPException(404, "Scheme not found")
    if body.code != s.code:
        raise HTTPException(422, "The scheme code cannot be changed")
    for k, v in body.model_dump(exclude={"documents"}).items():
        setattr(s, k, v)
    s.documents = [d.model_dump() for d in body.documents]
    if body.verified_on:
        s.sample = False
    audit(db, user, "scheme_update", "scheme", s.id, {"code": s.code})
    db.commit()
    return scheme_out(s)


@router.get("/eligibility")
def quick_eligibility(entrepreneur_id: int, model_id: Optional[int] = None, user: User = Depends(reader), db: Session = Depends(get_db)):
    """Which schemes fit this person for a model, using the model's template figures (before a DPR exists)."""
    e = db.get(Entrepreneur, entrepreneur_id)
    if not e or not can_see(user, e):
        raise HTTPException(404, "Entrepreneur not found")
    model = db.get(EnterpriseModel, model_id) if model_id else None
    result = finance.calculate(inputs_from_model(model, e.investment_available))
    return {"summary": _round(result["summary"]), "schemes": eligibility(_schemes(db), None, e=e, model=model, summary=result["summary"])}


# ================================================================ DPRs (Form 5.1)
def _round(s: dict) -> dict:
    return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()}


def _visible_dprs(db: Session, user: User) -> list[Dpr]:
    return [d for d in db.scalars(select(Dpr).order_by(Dpr.updated_at.desc(), Dpr.id.desc())) if can_see_dpr(user, d)]


@router.get("/dprs")
def list_dprs(status: Optional[str] = None, q: Optional[str] = None, entrepreneur_id: Optional[int] = None, group_id: Optional[int] = None,
              user: User = Depends(reader), db: Session = Depends(get_db)):
    rows = _visible_dprs(db, user)
    counts = {s: sum(1 for d in rows if d.status == s) for s in ("draft", "reviewed", "approved")}
    if entrepreneur_id:
        rows = [d for d in rows if d.entrepreneur_id == entrepreneur_id]
    if group_id:
        rows = [d for d in rows if d.group_id == group_id]
    if status:
        rows = [d for d in rows if d.status == status]
    if q:
        ql = q.lower().strip()
        rows = [d for d in rows if ql in (d.unit_name or "").lower() or ql in (d.code or "").lower()
                or (d.entrepreneur and (ql in d.entrepreneur.full_name.lower() or ql in d.entrepreneur.mobile))
                or (d.group and ql in d.group.name.lower())]
    m = Masters(db)
    names = user_names(db, [x for d in rows for x in (d.prepared_by_id, d.reviewed_by_id, d.approved_by_id)])
    approved = [d for d in _visible_dprs(db, user) if d.status == "approved"]
    return {"counts": counts, "approved_cost": round(sum((d.results or {}).get("project_cost", 0) for d in approved), 2),
            "approved_loan": round(sum((d.results or {}).get("loan", 0) for d in approved), 2),
            "rows": [dpr_out(db, d, m, names) for d in rows[:300]]}


class DprCreate(BaseModel):
    entrepreneur_id: Optional[int] = None
    group_id: Optional[int] = None
    model_id: Optional[int] = None
    unit_name: Optional[str] = Field(default=None, max_length=160)


@router.post("/dprs")
def create_dpr(body: DprCreate, user: User = Depends(writer), db: Session = Depends(get_db)):
    if bool(body.entrepreneur_id) == bool(body.group_id):
        raise HTTPException(422, "Choose an entrepreneur or a group")
    e = db.get(Entrepreneur, body.entrepreneur_id) if body.entrepreneur_id else None
    g = db.get(EGroup, body.group_id) if body.group_id else None
    o = e or g
    if not o or not can_see(user, o):
        raise HTTPException(404, "Entrepreneur or group not found")
    model = db.get(EnterpriseModel, body.model_id) if body.model_id else None
    if body.model_id and not model:
        raise HTTPException(422, "Unknown enterprise model")
    own = e.investment_available if e else (g.corpus if g else None)
    inputs = inputs_from_model(model, own)
    default_name = f"{(e.full_name if e else g.name).split()[0]}'s {model.name_en}" if model else (e.full_name if e else g.name)
    d = Dpr(entrepreneur_id=e.id if e else None, group_id=g.id if g else None, model_id=model.id if model else None,
            unit_name=(body.unit_name or default_name)[:160], district=o.district, mandal=o.mandal, village=o.village,
            activity=model.activity if model else "service", inputs=inputs, narrative={}, narrative_notes={},
            prepared_by_id=user.id, created_at=now(), updated_at=now())
    db.add(d)
    db.flush()
    d.code = f"DPR-{date.today().year}-{d.id:05d}"
    result = finance.calculate(inputs)
    d.results = finance.headline(result)
    bump_stage(o, 3)
    audit(db, user, "dpr_create", "dpr", d.id, {"code": d.code, "model": model.code if model else None})
    db.commit()
    return dpr_out(db, d, full=True)


def _detail(db: Session, d: Dpr, user: User) -> dict:
    result = finance.calculate(d.inputs)
    out = dpr_out(db, d, full=True)
    out["result"] = _result_out(result)
    out["eligibility"] = eligibility(_schemes(db), d, summary=result["summary"])
    out["applications"] = [application_out(db, a) for a in db.scalars(select(LoanApplication).where(LoanApplication.dpr_id == d.id))]
    out["can"] = {"edit": user.role in DPR_WRITE and d.status != "approved", "approve": user.role in DPR_APPROVE,
                  "apply": user.role in DPR_WRITE and d.status == "approved"}
    return out


def _result_out(result: dict) -> dict:
    """Rounded result for the screen (the monthly repayment table is left to the PDF)."""
    def r(x):
        if isinstance(x, float):
            return round(x, 2)
        if isinstance(x, dict):
            return {k: r(v) for k, v in x.items()}
        if isinstance(x, list):
            return [r(v) for v in x]
        return x

    return r({k: v for k, v in result.items() if k not in ("repayment", "inputs")}) | {"inputs": result["inputs"]}


@router.get("/dprs/{did}")
def get_one(did: int, user: User = Depends(reader), db: Session = Depends(get_db)):
    return _detail(db, get_dpr(db, user, did), user)


class DprUpdate(BaseModel):
    unit_name: str = Field(min_length=2, max_length=160)
    model_id: Optional[int] = None
    district: str = Field(min_length=2, max_length=80)
    mandal: Optional[str] = Field(default=None, max_length=80)
    village: Optional[str] = Field(default=None, max_length=120)
    address: Optional[str] = Field(default=None, max_length=255)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    activity: ACTIVITY
    scheme_code: Optional[str] = None
    inputs: dict
    narrative: dict = {}
    narrative_notes: dict = {}


def _check_inputs(raw: dict) -> dict:
    """Validate the money fields with the same models as the templates, then normalise."""
    try:
        if "sales" in raw:
            SalesIn(**(raw.get("sales") or {}))
        if "expenses" in raw:
            ExpensesIn(**{k: v for k, v in (raw.get("expenses") or {}).items() if k in ExpensesIn.model_fields})
    except Exception as exc:  # pydantic ValidationError
        raise HTTPException(422, str(exc).split("\n")[0]) from exc
    for i in raw.get("capital_items") or []:
        if not str(i.get("item") or "").strip():
            raise HTTPException(422, "Every capital cost item needs a name")
    return finance.normalise(raw)


@router.put("/dprs/{did}")
def update_dpr(did: int, body: DprUpdate, user: User = Depends(writer), db: Session = Depends(get_db)):
    d = get_dpr(db, user, did)
    if d.status == "approved":
        raise HTTPException(409, "This DPR is approved. Reopen it to make a new version.")
    m = Masters(db)
    if not m.has("district", body.district):
        raise HTTPException(422, "Choose a district from the list")
    if body.model_id and not db.get(EnterpriseModel, body.model_id):
        raise HTTPException(422, "Unknown enterprise model")
    _scheme(db, body.scheme_code)
    keys = {k for k, _ in narrative.SECTIONS}
    d.unit_name, d.model_id, d.district, d.mandal, d.village = body.unit_name.strip(), body.model_id, body.district, body.mandal, body.village
    d.address, d.lat, d.lng, d.activity, d.scheme_code = body.address, body.lat, body.lng, body.activity, body.scheme_code
    d.inputs = _check_inputs(body.inputs)
    new_narr = {k: str(v)[:6000] for k, v in body.narrative.items() if k in keys}
    if new_narr != (d.narrative or {}) and d.narrative_source in ("ai", "template"):
        d.narrative_source = "staff"
    d.narrative = new_narr
    d.narrative_notes = {k: str(v)[:3000] for k, v in body.narrative_notes.items() if k in {f for f, _, _ in narrative.NOTE_FIELDS}}
    if d.status == "reviewed":  # a change after review needs a fresh review
        d.status, d.reviewed_by_id, d.reviewed_at = "draft", None, None
    d.results = finance.headline(finance.calculate(d.inputs))
    d.updated_at = now()
    audit(db, user, "dpr_update", "dpr", d.id)
    db.commit()
    db.refresh(d)
    return _detail(db, d, user)


class CalcIn(BaseModel):
    inputs: dict
    activity: Optional[ACTIVITY] = None
    model_id: Optional[int] = None


@router.post("/dprs/{did}/calc")
def calc(did: int, body: CalcIn, user: User = Depends(reader), db: Session = Depends(get_db)):
    """Live figures while the officer types (nothing is saved)."""
    d = get_dpr(db, user, did)
    result = finance.calculate(body.inputs)
    model = db.get(EnterpriseModel, body.model_id) if body.model_id else d.model
    probe = Dpr(activity=body.activity or d.activity)
    probe.entrepreneur, probe.group, probe.model = d.entrepreneur, d.group, model
    return {"result": _result_out(result), "eligibility": eligibility(_schemes(db), probe, summary=result["summary"])}


class SchemeApply(BaseModel):
    code: Optional[str] = None


@router.post("/dprs/{did}/scheme")
def apply_scheme(did: int, body: SchemeApply, user: User = Depends(writer), db: Session = Depends(get_db)):
    """Choose a scheme: sets the subsidy and raises the own contribution to the scheme's minimum (rules only)."""
    d = get_dpr(db, user, did)
    if d.status == "approved":
        raise HTTPException(409, "This DPR is approved. Reopen it to make a new version.")
    inputs = finance.normalise(d.inputs)
    if not body.code:
        d.scheme_code = None
        inputs["finance"]["subsidy"] = 0.0
    else:
        sc = _scheme(db, body.code)
        res = finance.calculate(inputs)
        el = next(x for x in eligibility([sc], d, summary=res["summary"]))
        if not el["eligible"]:
            raise HTTPException(422, "Not eligible: " + "; ".join(c["text"] for c in el["checks"] if c["ok"] is False))
        d.scheme_code = sc.code
        inputs["finance"]["subsidy"] = el["subsidy"]
        inputs["finance"]["own"] = max(inputs["finance"]["own"], round_up(el["own_amount"], 100))
    d.inputs = inputs
    d.results = finance.headline(finance.calculate(inputs))
    if d.status == "reviewed":
        d.status, d.reviewed_by_id, d.reviewed_at = "draft", None, None
    d.updated_at = now()
    audit(db, user, "dpr_scheme", "dpr", d.id, {"scheme": d.scheme_code})
    db.commit()
    db.refresh(d)
    return _detail(db, d, user)


class NotesIn(BaseModel):
    narrative_notes: dict = {}


@router.post("/dprs/{did}/narrative")
def draft_narrative(did: int, body: NotesIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    """AI drafts the narrative sections from the officer's notes and the calculated figures (template when AI is off)."""
    d = get_dpr(db, user, did)
    if d.status == "approved":
        raise HTTPException(409, "This DPR is approved. Reopen it to make a new version.")
    d.narrative_notes = {k: str(v)[:3000] for k, v in body.narrative_notes.items() if k in {f for f, _, _ in narrative.NOTE_FIELDS}}
    result = finance.calculate(d.inputs)
    sections, source = narrative.draft(context(db, d), result)
    d.narrative, d.narrative_source = sections, source
    if d.status == "reviewed":
        d.status, d.reviewed_by_id, d.reviewed_at = "draft", None, None
    d.updated_at = now()
    audit(db, user, "dpr_narrative", "dpr", d.id, {"source": source})
    db.commit()
    db.refresh(d)
    return _detail(db, d, user)


class StatusIn(BaseModel):
    action: Literal["review", "approve", "reopen"]
    note: Optional[str] = Field(default=None, max_length=255)


def _save_version(db: Session, d: Dpr, user: User, note: Optional[str]):
    db.add(DprVersion(dpr_id=d.id, version=d.version, status=d.status, snapshot=snapshot(d), note=note, saved_by_id=user.id, created_at=now()))


@router.post("/dprs/{did}/status")
def dpr_status(did: int, body: StatusIn, user: User = Depends(approver), db: Session = Depends(get_db)):
    d = get_dpr(db, user, did)
    result = finance.calculate(d.inputs)
    errors = [w["text"] for w in result["warnings"] if w["level"] == "error"]
    if body.action in ("review", "approve"):
        if d.status == "approved":
            raise HTTPException(409, "Already approved")
        if errors:
            raise HTTPException(422, "Fix these first: " + " ".join(errors))
        empty = [label for k, label in narrative.SECTIONS if not (d.narrative or {}).get(k, "").strip()]
        if empty:
            raise HTTPException(422, "Write or draft these sections first: " + ", ".join(empty))
    if body.action == "review":
        if d.status != "draft":
            raise HTTPException(409, "Only a draft can be marked reviewed")
        d.status, d.reviewed_by_id, d.reviewed_at = "reviewed", user.id, now()
        _save_version(db, d, user, body.note or "Reviewed")
    elif body.action == "approve":
        if not d.reviewed_by_id:
            d.reviewed_by_id, d.reviewed_at = user.id, now()
        d.status, d.approved_by_id, d.approved_at = "approved", user.id, now()
        _save_version(db, d, user, body.note or "Approved")
        o = d.entrepreneur or d.group
        if o is not None and result["summary"]["loan"] <= 0:
            bump_stage(o, 4)  # own funds confirmed: stage 3 is complete
            from ..setup.service import ensure_unit
            ensure_unit(db, d, user)  # set-up (M7) starts
    else:
        if d.status == "draft":
            raise HTTPException(409, "This DPR is already a draft")
        if not (body.note or "").strip():
            raise HTTPException(422, "Say why the DPR is being reopened")
        if d.status == "approved":
            d.version += 1
        d.status, d.reviewed_by_id, d.reviewed_at, d.approved_by_id, d.approved_at = "draft", None, None, None, None
        db.add(DprVersion(dpr_id=d.id, version=d.version, status="draft", snapshot=snapshot(d), note=f"Reopened: {body.note.strip()}",
                          saved_by_id=user.id, created_at=now()))
    d.results = finance.headline(result)
    d.updated_at = now()
    audit(db, user, f"dpr_{body.action}", "dpr", d.id, {"version": d.version, "note": body.note})
    db.commit()
    db.refresh(d)
    return _detail(db, d, user)


@router.delete("/dprs/{did}")
def delete_dpr(did: int, user: User = Depends(writer), db: Session = Depends(get_db)):
    d = get_dpr(db, user, did)
    if d.status == "approved" or db.scalar(select(LoanApplication.id).where(LoanApplication.dpr_id == d.id)):
        raise HTTPException(409, "Only a draft without applications can be deleted")
    audit(db, user, "dpr_delete", "dpr", d.id, {"code": d.code})
    db.delete(d)
    db.commit()
    return {"ok": True}


@router.post("/dprs/{did}/pdf-link")
def dpr_pdf_link(did: int, version_id: Optional[int] = None, user: User = Depends(reader), db: Session = Depends(get_db)):
    d = get_dpr(db, user, did)
    if version_id and not db.scalar(select(DprVersion.id).where(DprVersion.id == version_id, DprVersion.dpr_id == d.id)):
        raise HTTPException(404, "Version not found")
    return {"url": pdf_link(d.id, version_id)}


def render_pdf(db: Session, d: Dpr, version_id: Optional[int] = None) -> bytes:
    if version_id:
        v = db.get(DprVersion, version_id)
        if not v or v.dpr_id != d.id:
            raise HTTPException(404, "Version not found")
        d = from_snapshot(d, v.snapshot)
    result = finance.calculate(d.inputs)
    return pdf.render(context(db, d), result, d.narrative or {})


@router.get("/files/{did}.pdf")
def dpr_pdf(did: int, t: str = Query(min_length=10), db: Session = Depends(get_db)):
    try:
        claims = jwt.decode(t, settings.JWT_SECRET, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(403, "Link expired – open the DPR again") from e
    if claims.get("purpose") != "dpr" or claims.get("d") != did:
        raise HTTPException(403, "Link not valid")
    d = db.get(Dpr, did)
    if not d:
        raise HTTPException(404, "Not found")
    data = render_pdf(db, d, claims.get("v"))
    name = re.sub(r"[^A-Za-z0-9-]", "", d.code or f"DPR-{d.id}")
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}.pdf"',
                                                                  "Cache-Control": "private, no-store"})


# ================================================================ credit / scheme applications (Forms 6.1, 6.2)
def _visible_apps(db: Session, user: User) -> list[LoanApplication]:
    return [a for a in db.scalars(select(LoanApplication).order_by(LoanApplication.updated_at.desc(), LoanApplication.id.desc()))
            if can_see_dpr(user, a)]


@router.get("/applications")
def list_applications(status: Optional[str] = None, bank: Optional[str] = None, q: Optional[str] = None, entrepreneur_id: Optional[int] = None,
                      user: User = Depends(reader), db: Session = Depends(get_db)):
    rows = _visible_apps(db, user)
    if entrepreneur_id:
        rows = [a for a in rows if a.entrepreneur_id == entrepreneur_id]
    counts = {s: sum(1 for a in rows if a.status == s) for s in LOAN_STATUS}
    if status:
        rows = [a for a in rows if a.status == status]
    if bank:
        rows = [a for a in rows if a.bank == bank]
    if q:
        ql = q.lower().strip()
        rows = [a for a in rows if ql in (a.code or "").lower() or ql in (a.app_number or "").lower() or ql in a.branch.lower()
                or (a.entrepreneur and (ql in a.entrepreneur.full_name.lower() or ql in a.entrepreneur.mobile))
                or (a.group and ql in a.group.name.lower())]
    m = Masters(db)
    return {"counts": counts, "rows": [application_out(db, a, m) for a in rows[:300]]}


class ApplicationIn(BaseModel):
    dpr_id: int
    scheme_code: Optional[str] = None
    bank: str = Field(min_length=2, max_length=40)
    branch: str = Field(min_length=2, max_length=160)
    ifsc: Optional[str] = Field(default=None, max_length=11)
    amount_requested: Optional[float] = Field(default=None, gt=0, le=100_000_000)
    app_number: Optional[str] = Field(default=None, max_length=60)
    portal: Optional[str] = Field(default=None, max_length=80)

    @field_validator("ifsc")
    @classmethod
    def v_ifsc(cls, v):
        if not v:
            return None
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", v):
            raise ValueError("IFSC must look like SBIN0001234 (11 characters, fifth is zero)")
        return v


def _auto_docs(db: Session, docs: list[dict], d: Dpr) -> list[dict]:
    """Tick what MIRAI already holds: the approved DPR and a MIRAI EDP certificate."""
    cert = None
    if d.entrepreneur_id:
        cert = db.scalar(select(Trainee).where(Trainee.entrepreneur_id == d.entrepreneur_id, Trainee.certificate_no.is_not(None))
                         .order_by(Trainee.certified_at.desc()).limit(1))
    for x in docs:
        if x["code"] == "dpr":
            x["have"], x["note"] = True, f"{d.code} version {d.version} (approved)"
        if x["code"] == "edp_certificate" and cert:
            x["have"], x["note"] = True, f"MIRAI certificate {cert.certificate_no}"
    return docs


@router.post("/applications")
def create_application(body: ApplicationIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    d = get_dpr(db, user, body.dpr_id)
    if d.status != "approved":
        raise HTTPException(409, "Approve the DPR before making an application")
    if not Masters(db).has("bank", body.bank):
        raise HTTPException(422, "Choose a bank from the list")
    code = body.scheme_code if body.scheme_code is not None else d.scheme_code
    sc = _scheme(db, code)
    result = finance.calculate(d.inputs)
    if sc:
        el = eligibility([sc], d, summary=result["summary"])[0]
        if not el["eligible"]:
            raise HTTPException(422, f"Not eligible for {sc.name.split(' – ')[0]}: " + "; ".join(c["text"] for c in el["checks"] if c["ok"] is False))
    amount = body.amount_requested or round(result["summary"]["loan"], 2)
    if amount <= 0:
        raise HTTPException(422, "This DPR needs no bank loan")
    open_ = db.scalar(select(LoanApplication.id).where(LoanApplication.dpr_id == d.id, LoanApplication.bank == body.bank,
                                                      LoanApplication.status.in_(("draft", "submitted", "query", "sanctioned"))))
    if open_:
        raise HTTPException(409, "There is already an open application for this DPR with this bank")
    a = LoanApplication(dpr_id=d.id, dpr_version=d.version, entrepreneur_id=d.entrepreneur_id, group_id=d.group_id, district=d.district,
                        scheme_code=sc.code if sc else None, bank=body.bank, branch=body.branch.strip(), ifsc=body.ifsc,
                        amount_requested=amount, app_number=body.app_number, portal=body.portal,
                        documents=_auto_docs(db, documents_for(sc, facts_for(d)), d), status="draft", created_by_id=user.id,
                        interest_pct=finance.normalise(d.inputs)["loan"]["interest_pct"], created_at=now(), updated_at=now())
    db.add(a)
    db.flush()
    a.code = f"LA-{date.today().year}-{a.id:05d}"
    db.add(LoanEvent(application_id=a.id, kind="status", status="draft", text="Application prepared", on=date.today(), by_id=user.id, at=now()))
    audit(db, user, "loan_create", "loan_application", a.id, {"code": a.code, "dpr": d.code})
    db.commit()
    db.refresh(a)
    return application_out(db, a, full=True)


@router.get("/applications/{aid}")
def get_application_detail(aid: int, user: User = Depends(reader), db: Session = Depends(get_db)):
    a = get_application(db, user, aid)
    out = application_out(db, a, full=True)
    out["can"] = {"write": user.role in DPR_WRITE}
    return out


class ApplicationEdit(BaseModel):
    bank: str = Field(min_length=2, max_length=40)
    branch: str = Field(min_length=2, max_length=160)
    ifsc: Optional[str] = Field(default=None, max_length=11)
    amount_requested: float = Field(gt=0, le=100_000_000)
    app_number: Optional[str] = Field(default=None, max_length=60)
    portal: Optional[str] = Field(default=None, max_length=80)

    @field_validator("ifsc")
    @classmethod
    def v_ifsc(cls, v):
        return ApplicationIn.v_ifsc(v)


@router.put("/applications/{aid}")
def edit_application(aid: int, body: ApplicationEdit, user: User = Depends(writer), db: Session = Depends(get_db)):
    a = get_application(db, user, aid)
    if a.status in ("sanctioned", "disbursed", "rejected", "withdrawn"):
        raise HTTPException(409, "This application can no longer be edited")
    if not Masters(db).has("bank", body.bank):
        raise HTTPException(422, "Choose a bank from the list")
    for k, v in body.model_dump().items():
        setattr(a, k, v.strip() if isinstance(v, str) else v)
    a.updated_at = now()
    audit(db, user, "loan_update", "loan_application", a.id)
    db.commit()
    return get_application_detail(aid, user, db)


class DocTick(BaseModel):
    code: str
    have: bool
    note: Optional[str] = Field(default=None, max_length=160)


@router.put("/applications/{aid}/documents")
def tick_document(aid: int, body: DocTick, user: User = Depends(writer), db: Session = Depends(get_db)):
    a = get_application(db, user, aid)
    docs = [dict(x) for x in a.documents or []]
    x = next((x for x in docs if x["code"] == body.code), None)
    if not x:
        raise HTTPException(404, "Document not in the checklist")
    x["have"], x["note"] = body.have, body.note if body.note is not None else x.get("note")
    a.documents = docs
    a.updated_at = now()
    db.commit()
    return get_application_detail(aid, user, db)


class DocAdd(BaseModel):
    label: str = Field(min_length=2, max_length=160)


@router.post("/applications/{aid}/documents")
def add_document(aid: int, body: DocAdd, user: User = Depends(writer), db: Session = Depends(get_db)):
    """A document the bank asked for that is not in the standard list."""
    a = get_application(db, user, aid)
    docs = [dict(x) for x in a.documents or []]
    code = "extra_" + re.sub(r"[^a-z0-9]+", "_", body.label.lower()).strip("_")[:30]
    if any(x["code"] == code for x in docs):
        raise HTTPException(409, "Already in the checklist")
    docs.append({"code": code, "label": body.label.strip(), "have": False, "file": None, "note": "Asked by the bank"})
    a.documents = docs
    a.updated_at = now()
    db.commit()
    return get_application_detail(aid, user, db)


def attach_file(a: LoanApplication, code: str, name: str, note: str) -> None:
    docs = [dict(x) for x in a.documents or []]
    x = next((x for x in docs if x["code"] == code), None)
    if not x:
        raise HTTPException(404, "Document not in the checklist")
    x["have"], x["file"], x["note"] = True, name, note
    a.documents = docs
    a.updated_at = now()


@router.post("/applications/{aid}/documents/{code}/file")
async def upload_document(aid: int, code: str, file: UploadFile = File(...), user: User = Depends(writer), db: Session = Depends(get_db)):
    a = get_application(db, user, aid)
    name = save_doc(await file.read(10 * 1024 * 1024 + 1), file.content_type or "")
    attach_file(a, code, name, f"Uploaded by {user.name or user.email}")
    audit(db, user, "loan_document", "loan_application", a.id, {"code": code})
    db.commit()
    return get_application_detail(aid, user, db)


@router.get("/files/doc/{name}")
def document_file(name: str, t: str = Query(min_length=10)):
    if not re.fullmatch(r"[0-9a-f]{32}\.(pdf|jpg|png|webp)", name):
        raise HTTPException(404, "Not found")
    try:
        claims = jwt.decode(t, settings.JWT_SECRET, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(403, "Link expired") from e
    if claims.get("purpose") != "loandoc" or claims.get("f") != name:
        raise HTTPException(403, "Link not valid")
    p = doc_path(name)
    if not p.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(p, headers={"Cache-Control": "private, max-age=600"})


class AppStatusIn(BaseModel):
    """Form 6.2 – application status update."""
    status: Literal["submitted", "query", "sanctioned", "disbursed", "rejected", "withdrawn"]
    on: date
    text: Optional[str] = Field(default=None, max_length=2000)
    app_number: Optional[str] = Field(default=None, max_length=60)
    sanctioned_amount: Optional[float] = Field(default=None, gt=0, le=100_000_000)
    subsidy_amount: Optional[float] = Field(default=None, ge=0, le=100_000_000)
    disbursed_amount: Optional[float] = Field(default=None, gt=0, le=100_000_000)
    interest_pct: Optional[float] = Field(default=None, ge=0, le=40)
    emi_amount: Optional[float] = Field(default=None, gt=0, le=10_000_000)
    tenure_months: Optional[int] = Field(default=None, ge=1, le=180)
    first_emi_date: Optional[date] = None
    rejection_reason: Optional[Literal["cibil", "documents", "viability", "area", "target", "other"]] = None

    @field_validator("on")
    @classmethod
    def v_on(cls, v):
        if v > date.today():
            raise ValueError("The date cannot be in the future")
        return v


@router.post("/applications/{aid}/status")
def application_status(aid: int, body: AppStatusIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    a = get_application(db, user, aid)
    if body.status not in LOAN_FLOW.get(a.status, ()):
        raise HTTPException(409, f"Cannot move from {status_label(a.status)} to {status_label(body.status)}")
    # Dates must follow the earlier updates (the "prepared" entry is skipped: an application may be recorded after it was sent).
    last = max([e.on for e in a.events if e.on and e.status != "draft"] or [date.min])
    if body.on < last:
        raise HTTPException(422, f"The date is before the last update ({last.isoformat()})")
    text = (body.text or "").strip() or None
    if body.status == "submitted":
        if body.app_number:
            a.app_number = body.app_number.strip()
        if a.status == "draft":
            a.submitted_on = body.on
    elif body.status == "query":
        if not text:
            raise HTTPException(422, "Write the bank's query")
    elif body.status == "sanctioned":
        if not body.sanctioned_amount:
            raise HTTPException(422, "Enter the sanctioned amount")
        a.sanctioned_amount, a.subsidy_amount, a.sanctioned_on = body.sanctioned_amount, body.subsidy_amount, body.on
        if body.interest_pct is not None:
            a.interest_pct = body.interest_pct
        o = a.entrepreneur or a.group
        if o is not None:
            bump_stage(o, 4)  # funds sanctioned: stage 3 (DPR & finance) is complete
        from ..setup.service import ensure_unit
        ensure_unit(db, a.dpr, user)  # set-up (M7) starts
    elif body.status == "disbursed":
        missing = [n for n, v in (("disbursed amount", body.disbursed_amount), ("tenure", body.tenure_months),
                                  ("first EMI date", body.first_emi_date)) if not v]
        if body.interest_pct is None and a.interest_pct is None:
            missing.append("interest rate")
        if missing:
            raise HTTPException(422, "Enter the " + ", ".join(missing))
        if body.disbursed_amount > (a.sanctioned_amount or 0) + 0.5:
            raise HTTPException(422, "The disbursed amount is more than the sanctioned amount")
        if body.first_emi_date <= body.on:
            raise HTTPException(422, "The first EMI date must be after the disbursement date")
        a.disbursed_on, a.disbursed_amount, a.tenure_months, a.first_emi_date = body.on, body.disbursed_amount, body.tenure_months, body.first_emi_date
        if body.interest_pct is not None:
            a.interest_pct = body.interest_pct
        rows = emi_rows(a.disbursed_amount, a.interest_pct or 0, a.tenure_months, a.first_emi_date, body.emi_amount)
        a.emi_amount = body.emi_amount or (rows[0]["amount"] if rows else None)
        a.repayments = [Repayment(**r) for r in rows]
    elif body.status == "rejected":
        if not body.rejection_reason:
            raise HTTPException(422, "Choose the reason for rejection")
        a.rejection_reason, a.rejection_note = body.rejection_reason, text
    a.status = body.status
    a.updated_at = now()
    db.add(LoanEvent(application_id=a.id, kind="status", status=body.status, text=text, on=body.on, by_id=user.id, at=now()))
    audit(db, user, "loan_status", "loan_application", a.id, {"status": body.status})
    db.commit()
    db.refresh(a)
    return get_application_detail(aid, user, db)


class EventIn(BaseModel):
    kind: Literal["note", "response"]
    text: str = Field(min_length=2, max_length=2000)
    on: date


@router.post("/applications/{aid}/events")
def add_event(aid: int, body: EventIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    """Query resolution log: a response to the bank's query (sends the application back to Submitted), or a note."""
    a = get_application(db, user, aid)
    if body.on > date.today():
        raise HTTPException(422, "The date cannot be in the future")
    db.add(LoanEvent(application_id=a.id, kind=body.kind, text=body.text.strip(), on=body.on, by_id=user.id, at=now()))
    if body.kind == "response" and a.status == "query":
        a.status = "submitted"
        db.add(LoanEvent(application_id=a.id, kind="status", status="submitted", text="Query answered", on=body.on, by_id=user.id, at=now()))
    a.updated_at = now()
    db.commit()
    db.refresh(a)
    return get_application_detail(aid, user, db)


class PaymentIn(BaseModel):
    paid_amount: Optional[float] = Field(default=None, ge=0, le=10_000_000)
    paid_on: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=160)


@router.put("/repayments/{rid}")
def record_payment(rid: int, body: PaymentIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    r = db.get(Repayment, rid)
    if not r:
        raise HTTPException(404, "Instalment not found")
    a = get_application(db, user, r.application_id)
    if body.paid_on and body.paid_on > date.today():
        raise HTTPException(422, "The payment date cannot be in the future")
    if body.paid_on and a.disbursed_on and body.paid_on < a.disbursed_on:
        raise HTTPException(422, "The payment date is before the disbursement")
    r.paid_on = body.paid_on
    r.paid_amount = (body.paid_amount if body.paid_amount is not None else r.amount) if body.paid_on else None
    r.note = body.note
    a.updated_at = now()
    audit(db, user, "loan_repayment", "loan_application", a.id, {"n": r.n, "paid_on": str(body.paid_on) if body.paid_on else None})
    db.commit()
    db.refresh(a)
    return get_application_detail(a.id, user, db)


# ================================================================ reports
@router.get("/reports/summary")
def report_summary(user: User = Depends(reader), db: Session = Depends(get_db)):
    m = Masters(db)
    dprs = _visible_dprs(db, user)
    apps = _visible_apps(db, user)
    sanctioned = [a for a in apps if a.status in ("sanctioned", "disbursed")]
    days = [(a.sanctioned_on - a.submitted_on).days for a in sanctioned if a.sanctioned_on and a.submitted_on]
    by_bank: dict[str, dict] = {}
    for a in apps:
        b = by_bank.setdefault(a.bank, {"code": a.bank, "name": m.name("bank", a.bank), "applications": 0, "sanctioned": 0, "amount": 0.0})
        b["applications"] += 1
        if a in sanctioned:
            b["sanctioned"] += 1
            b["amount"] += a.sanctioned_amount or 0
    by_scheme: dict[str, dict] = {}
    for a in apps:
        k = a.scheme_code or "none"
        s = by_scheme.setdefault(k, {"code": k, "applications": 0, "sanctioned": 0, "subsidy": 0.0})
        s["applications"] += 1
        if a in sanctioned:
            s["sanctioned"] += 1
            s["subsidy"] += a.subsidy_amount or 0
    health = {"on_time": 0, "delayed": 0, "default": 0}
    overdue_amount = 0.0
    for a in apps:
        if a.status == "disbursed" and a.repayments:
            rs = repayment_summary(a)
            health[rs["health"]] += 1
            overdue_amount += rs["overdue_amount"]
    by_model: dict[str, int] = {}
    for d in dprs:
        k = d.model.name_en if d.model else "Own enterprise"
        by_model[k] = by_model.get(k, 0) + 1
    approved = [d for d in dprs if d.status == "approved"]
    return {
        "dprs": {s: sum(1 for d in dprs if d.status == s) for s in ("draft", "reviewed", "approved")},
        "approved_cost": round(sum((d.results or {}).get("project_cost", 0) for d in approved), 2),
        "approved_loan": round(sum((d.results or {}).get("loan", 0) for d in approved), 2),
        "by_model": [{"label": k, "value": v} for k, v in sorted(by_model.items(), key=lambda x: -x[1])],
        "applications": {s: sum(1 for a in apps if a.status == s) for s in LOAN_STATUS},
        "requested": round(sum(a.amount_requested for a in apps if a.status not in ("draft", "withdrawn")), 2),
        "sanctioned_amount": round(sum(a.sanctioned_amount or 0 for a in sanctioned), 2),
        "subsidy_amount": round(sum(a.subsidy_amount or 0 for a in sanctioned), 2),
        "disbursed_amount": round(sum(a.disbursed_amount or 0 for a in apps if a.status == "disbursed"), 2),
        "avg_days_to_sanction": round(sum(days) / len(days), 1) if days else None,
        "by_bank": sorted(by_bank.values(), key=lambda x: -x["amount"]),
        "by_scheme": sorted(by_scheme.values(), key=lambda x: -x["applications"]),
        "repayment": health, "overdue_amount": round(overdue_amount, 2),
        "open_queries": [application_out(db, a, m) for a in apps if a.status == "query"][:20],
    }


@router.get("/reports/applications.csv")
def report_csv(user: User = Depends(reader), db: Session = Depends(get_db)):
    m = Masters(db)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Application", "DPR", "Entrepreneur / group", "District", "Unit", "Scheme", "Bank", "Branch", "Requested", "Status",
                "Submitted on", "Sanctioned on", "Sanctioned", "Subsidy", "Disbursed on", "Disbursed", "EMI", "Tenure (months)",
                "EMIs paid", "EMIs overdue", "Overdue amount", "Repayment"])
    for a in _visible_apps(db, user):
        o = application_out(db, a, m)
        r = o["repayment"] or {}
        w.writerow([a.code, o["dpr_code"], o["owner"]["name"], o["district_name"], o["unit_name"], a.scheme_code or "", o["bank_name"], a.branch,
                    a.amount_requested, o["status_label"], a.submitted_on or "", a.sanctioned_on or "", a.sanctioned_amount or "",
                    a.subsidy_amount or "", a.disbursed_on or "", a.disbursed_amount or "", a.emi_amount or "", a.tenure_months or "",
                    r.get("paid", ""), r.get("overdue", ""), r.get("overdue_amount", ""), r.get("health", "")])
    return Response("﻿" + buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="loan-applications-{date.today().isoformat()}.csv"'})
