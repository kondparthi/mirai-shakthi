"""M1 – Entrepreneur & group enrolment for staff (Forms 1.1, 1.2, 1.3), assisted enrolment, bulk import and stats."""
import csv
import io
import re
from datetime import UTC, date, datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import crypto
from ..config import settings
from ..db import get_db
from ..models import AuditLog, User
from ..models_p1 import LIFECYCLE, EGroup, Entrepreneur, GroupMember, ReadinessAssessment, Setting
from ..programme import readiness
from ..programme.service import (MOBILE_RE, STORAGE, EntrepreneurIn, GroupIn, Masters, age_on, apply_entrepreneur, can_see,
                                 delete_photo, entrepreneur_out, find_duplicates, group_out, missing_items, save_photo, scoped)
from ..roles import PROGRAMME_READ, PROGRAMME_WRITE, READINESS_WRITE
from ..security import ALGO, require_roles
from .auth import CONSENT_VERSION, check_otp, issue_otp

router = APIRouter(prefix="/api/v1/programme", tags=["programme"])
files = APIRouter(prefix="/api/v1/files", tags=["files"])
reader = require_roles(*PROGRAMME_READ)
writer = require_roles(*PROGRAMME_WRITE)
assessor = require_roles(*READINESS_WRITE)
PAGE = 25


def _now():
    return datetime.now(UTC).replace(tzinfo=None)


def _lang(user: User, lang: Optional[str]) -> str:
    return lang if lang in ("en", "te") else (user.language or "en")


def _audit(db, user, action, entity, entity_id=None, detail=None):
    db.add(AuditLog(user_id=user.id, action=action, entity=entity, entity_id=entity_id, detail=detail))


def _mobile(v: str) -> str:
    v = re.sub(r"\D", "", v or "")[-10:]
    if not MOBILE_RE.match(v):
        raise HTTPException(422, "Enter a valid 10-digit mobile number")
    return v


def _formula(db: Session) -> dict:
    s = db.get(Setting, "readiness_formula")
    return s.value if s else readiness.default_formula()


def _get_entrepreneur(db: Session, user: User, eid: int) -> Entrepreneur:
    e = db.get(Entrepreneur, eid)
    if not e or not can_see(user, e):
        raise HTTPException(404, "Entrepreneur not found")
    return e


def _get_group(db: Session, user: User, gid: int) -> EGroup:
    g = db.get(EGroup, gid)
    if not g or not can_see(user, g):
        raise HTTPException(404, "Group not found")
    return g


def _dup_reasons(rows: list[Entrepreneur], mobile: str | None, m: Masters) -> list[dict]:
    return [{"id": d.id, "full_name": d.full_name, "mobile": d.mobile, "district_name": m.name("district", d.district),
             "village_name": m.name("village", d.village),
             "reason": "Same mobile number" if mobile and d.mobile == mobile else "Same Aadhaar (last 4), name and date of birth"}
            for d in rows]


# ================================================================ stats
@router.get("/stats")
def stats(user: User = Depends(reader), db: Session = Depends(get_db)):
    m = Masters(db)
    base = scoped(select(Entrepreneur), user, Entrepreneur).subquery()
    total = db.scalar(select(func.count()).select_from(base)) or 0
    by_stage = dict(db.execute(select(base.c.stage, func.count()).group_by(base.c.stage)).all())
    by_district = db.execute(select(base.c.district, func.count()).group_by(base.c.district).order_by(func.count().desc())).all()
    by_source = dict(db.execute(select(base.c.source, func.count()).group_by(base.c.source)).all())
    verified = db.scalar(select(func.count()).select_from(base).where(base.c.verified.is_(True))) or 0
    no_consent = db.scalar(select(func.count()).select_from(base).where(base.c.consent_at.is_(None))) or 0
    women = db.scalar(select(func.count()).select_from(base).where(base.c.gender == "female")) or 0
    groups = db.scalar(select(func.count()).select_from(scoped(select(EGroup), user, EGroup).subquery())) or 0
    # Latest readiness score of each entrepreneur in scope
    latest = (select(ReadinessAssessment.entrepreneur_id, func.max(ReadinessAssessment.id).label("mid"))
              .where(ReadinessAssessment.entrepreneur_id.in_(select(base.c.id))).group_by(ReadinessAssessment.entrepreneur_id).subquery())
    scores = list(db.scalars(select(ReadinessAssessment.score).join(latest, ReadinessAssessment.id == latest.c.mid)))
    return {
        "total": total, "verified": verified, "pending_consent": no_consent, "women": women, "groups": groups,
        "assessed": len(scores), "avg_readiness": round(sum(scores) / len(scores)) if scores else None,
        "ready": sum(1 for s in scores if s >= 70),
        "by_stage": [{"stage": k, "name": v, "count": by_stage.get(k, 0)} for k, v in LIFECYCLE.items()],
        "by_district": [{"district": d, "name": m.name("district", d), "count": c} for d, c in by_district],
        "by_source": by_source,
    }


# ================================================================ entrepreneurs
@router.get("/entrepreneurs")
def list_entrepreneurs(q: Optional[str] = None, district: Optional[str] = None, mandal: Optional[str] = None, stage: Optional[int] = None,
                       source: Optional[str] = None, tag: Optional[str] = None, sector: Optional[str] = None,
                       verified: Optional[bool] = None, page: int = Query(1, ge=1), lang: Optional[str] = None,
                       user: User = Depends(reader), db: Session = Depends(get_db)):
    stmt = scoped(select(Entrepreneur), user, Entrepreneur)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Entrepreneur.full_name.ilike(like), Entrepreneur.mobile.like(like)))
    for col, val in ((Entrepreneur.district, district), (Entrepreneur.mandal, mandal), (Entrepreneur.stage, stage),
                     (Entrepreneur.source, source), (Entrepreneur.context_tag, tag), (Entrepreneur.verified, verified)):
        if val is not None and val != "":
            stmt = stmt.where(col == val)
    if sector:
        stmt = stmt.where(func.json_contains(Entrepreneur.interests, f'"{sector}"'))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Entrepreneur.id.desc()).offset((page - 1) * PAGE).limit(PAGE))
    m = Masters(db)
    lg = _lang(user, lang)
    return {"total": total, "page": page, "pages": max(1, -(-total // PAGE)), "rows": [entrepreneur_out(e, m, lg, full=False) for e in rows]}


@router.get("/entrepreneurs/{eid}")
def get_entrepreneur(eid: int, lang: Optional[str] = None, user: User = Depends(reader), db: Session = Depends(get_db)):
    e = _get_entrepreneur(db, user, eid)
    d = entrepreneur_out(e, Masters(db), _lang(user, lang))
    d["enrolled_by"] = (db.get(User, e.enrolled_by_id).name if e.enrolled_by_id and db.get(User, e.enrolled_by_id) else None)
    d["linked_account"] = bool(e.user_id)
    return d


class DupCheck(BaseModel):
    mobile: Optional[str] = None
    aadhaar: Optional[str] = None
    full_name: Optional[str] = None
    dob: Optional[date] = None
    exclude_id: Optional[int] = None


@router.post("/duplicates")
def duplicates(body: DupCheck, _: User = Depends(writer), db: Session = Depends(get_db)):
    mobile = _mobile(body.mobile) if body.mobile else None
    last4 = re.sub(r"\D", "", body.aadhaar or "")[-4:] or None
    rows = find_duplicates(db, mobile, last4, body.full_name, body.dob, body.exclude_id)
    return {"duplicates": _dup_reasons(rows, mobile, Masters(db))}


class OtpFor(BaseModel):
    mobile: str


@router.post("/enrol/otp")
def assisted_otp(body: OtpFor, user: User = Depends(writer), db: Session = Depends(get_db)):
    """Step 1 of assisted enrolment: an OTP goes to the entrepreneur's phone. Reading it out to the navigator is their consent."""
    mobile = _mobile(body.mobile)
    existing = db.scalar(select(Entrepreneur).where(Entrepreneur.mobile == mobile))
    if existing:
        raise HTTPException(409, f"This mobile is already enrolled ({existing.full_name}, ID {existing.id})")
    u = db.scalar(select(User).where(User.mobile == mobile))
    if u and u.role != "msme":
        raise HTTPException(409, "This mobile belongs to a staff or expert login")
    return issue_otp(db, mobile)


class AssistedIn(BaseModel):
    mobile: str
    otp: str = Field(min_length=4, max_length=8)
    data: EntrepreneurIn
    force: bool = False  # enrol even if a possible duplicate (same Aadhaar last 4 + name + DOB) was found


@router.post("/entrepreneurs")
def assisted_enrol(body: AssistedIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    mobile = _mobile(body.mobile)
    m = Masters(db)
    m.check(body.data)
    if user.role not in ("admin", "programme_manager") and (user.scope or {}).get("districts") \
            and body.data.district not in user.scope["districts"]:
        raise HTTPException(403, "This district is outside your area")
    dups = find_duplicates(db, mobile, body.data.aadhaar[-4:] if body.data.aadhaar else None, body.data.full_name, body.data.dob)
    if any(d.mobile == mobile for d in dups):
        raise HTTPException(409, "This mobile is already enrolled")
    if dups and not body.force:
        raise HTTPException(409, {"message": "A possible duplicate was found", "duplicates": _dup_reasons(dups, mobile, m)})
    check_otp(db, mobile, body.otp)
    acct = db.scalar(select(User).where(User.mobile == mobile))
    if acct and acct.role != "msme":
        raise HTTPException(409, "This mobile belongs to a staff or expert login")
    if not acct:
        acct = User(mobile=mobile, role="msme", name=body.data.full_name, language=user.language or "en",
                    consent_version=CONSENT_VERSION, consent_at=_now())
        db.add(acct)
        db.flush()
    elif not acct.name:
        acct.name = body.data.full_name
    e = Entrepreneur(mobile=mobile, user_id=acct.id, source="navigator", enrolled_by_id=user.id,
                     consent_version=f"{CONSENT_VERSION}-assisted-otp", consent_at=_now())
    apply_entrepreneur(e, body.data)
    db.add(e)
    db.flush()
    _audit(db, user, "enrol_assisted", "entrepreneur", e.id, {"mobile": mobile, "duplicate_override": bool(dups)})
    db.commit()
    db.refresh(e)
    return entrepreneur_out(e, m, user.language or "en")


@router.put("/entrepreneurs/{eid}")
def update_entrepreneur(eid: int, body: EntrepreneurIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    e = _get_entrepreneur(db, user, eid)
    m = Masters(db)
    m.check(body)
    dups = find_duplicates(db, None, body.aadhaar[-4:] if body.aadhaar else None, body.full_name, body.dob, exclude_id=e.id)
    if dups:
        raise HTTPException(409, {"message": "Another entrepreneur has the same Aadhaar (last 4), name and date of birth",
                                  "duplicates": _dup_reasons(dups, None, m)})
    apply_entrepreneur(e, body)
    if missing_items(e):
        e.verified = False
    _audit(db, user, "entrepreneur_update", "entrepreneur", e.id)
    db.commit()
    db.refresh(e)
    return entrepreneur_out(e, m, user.language or "en")


@router.post("/entrepreneurs/{eid}/photo")
async def upload_photo(eid: int, file: UploadFile = File(...), user: User = Depends(writer), db: Session = Depends(get_db)):
    e = _get_entrepreneur(db, user, eid)
    name = save_photo(await file.read(8 * 1024 * 1024 + 1))
    old, e.photo = e.photo, name
    _audit(db, user, "entrepreneur_photo", "entrepreneur", e.id)
    db.commit()
    delete_photo(old)
    db.refresh(e)
    return entrepreneur_out(e, Masters(db), user.language or "en")


class StatusIn(BaseModel):
    stage: Optional[int] = Field(default=None, ge=1, le=8)
    status: Optional[Literal["active", "paused", "closed"]] = None
    verified: Optional[bool] = None
    note: Optional[str] = Field(default=None, max_length=500)


@router.post("/entrepreneurs/{eid}/status")
def change_status(eid: int, body: StatusIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    e = _get_entrepreneur(db, user, eid)
    if body.verified:
        miss = missing_items(e)
        if miss:
            raise HTTPException(422, f"Cannot verify yet – still missing: {', '.join(x.replace('_', ' ') for x in miss)}")
    before = {"stage": e.stage, "status": e.status, "verified": e.verified}
    if body.stage is not None:
        e.stage = body.stage
    if body.status:
        e.status = body.status
    if body.verified is not None:
        e.verified = body.verified
    _audit(db, user, "entrepreneur_status", "entrepreneur", e.id,
           {"before": before, "after": {"stage": e.stage, "status": e.status, "verified": e.verified}, "note": body.note})
    db.commit()
    db.refresh(e)
    return entrepreneur_out(e, Masters(db), user.language or "en")


# ================================================================ readiness (Form 1.3)
@router.get("/readiness/form")
def readiness_form(lang: Optional[str] = None, user: User = Depends(reader), db: Session = Depends(get_db)):
    f = _formula(db)
    return {"version": f.get("version", 1), "questions": readiness.questions_for_form(f, _lang(user, lang))}


class ReadinessIn(BaseModel):
    answers: dict[str, str]
    remarks: Optional[str] = Field(default=None, max_length=2000)


def _assessment_out(a: ReadinessAssessment) -> dict:
    return {"id": a.id, "score": a.score, "breakdown": a.breakdown, "strengths": a.strengths, "gaps": a.gaps,
            "recommended": a.recommended, "remarks": a.remarks, "answers": a.answers,
            "at": a.created_at.isoformat() if a.created_at else None}


def record_readiness(db: Session, by: User, body: ReadinessIn, investment: float | None, lang: str,
                     entrepreneur: Entrepreneur | None = None, group: EGroup | None = None) -> dict:
    f = _formula(db)
    allowed = set(readiness.QUESTION_ORDER) - {"investment"}
    answers = {k: (v or "").strip()[:1000] for k, v in body.answers.items() if k in allowed}
    res = readiness.score(answers, investment, f, lang)
    a = ReadinessAssessment(entrepreneur_id=entrepreneur.id if entrepreneur else None, group_id=group.id if group else None,
                            answers={**answers, "_formula_version": f.get("version", 1)}, score=res["score"], breakdown=res["breakdown"],
                            strengths=res["strengths"], gaps=res["gaps"], recommended=res["recommended"], remarks=body.remarks,
                            assessed_by_id=by.id, created_at=_now())
    db.add(a)
    db.flush()
    _audit(db, by, "readiness_record", "group" if group else "entrepreneur", (group or entrepreneur).id, {"score": res["score"]})
    db.commit()
    return {**_assessment_out(a), "band": res["band"]}


@router.post("/entrepreneurs/{eid}/readiness")
def assess_entrepreneur(eid: int, body: ReadinessIn, lang: Optional[str] = None, user: User = Depends(assessor), db: Session = Depends(get_db)):
    e = _get_entrepreneur(db, user, eid)
    return record_readiness(db, user, body, e.investment_available, _lang(user, lang), entrepreneur=e)


@router.get("/entrepreneurs/{eid}/readiness")
def entrepreneur_readiness(eid: int, user: User = Depends(reader), db: Session = Depends(get_db)):
    return [_assessment_out(a) for a in _get_entrepreneur(db, user, eid).assessments]


# ================================================================ groups (Form 1.2)
@router.get("/groups")
def list_groups(q: Optional[str] = None, district: Optional[str] = None, group_type: Optional[str] = None, page: int = Query(1, ge=1),
                lang: Optional[str] = None, user: User = Depends(reader), db: Session = Depends(get_db)):
    stmt = scoped(select(EGroup), user, EGroup)
    if q:
        stmt = stmt.where(EGroup.name.ilike(f"%{q.strip()}%"))
    if district:
        stmt = stmt.where(EGroup.district == district)
    if group_type:
        stmt = stmt.where(EGroup.group_type == group_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(EGroup.id.desc()).offset((page - 1) * PAGE).limit(PAGE))
    m = Masters(db)
    lg = _lang(user, lang)
    return {"total": total, "page": page, "pages": max(1, -(-total // PAGE)), "rows": [group_out(g, m, lg, full=False) for g in rows]}


@router.get("/groups/{gid}")
def get_group(gid: int, lang: Optional[str] = None, user: User = Depends(reader), db: Session = Depends(get_db)):
    g = _get_group(db, user, gid)
    d = group_out(g, Masters(db), _lang(user, lang))
    d["assessments"] = [_assessment_out(a) for a in g.assessments]
    return d


def _apply_group(db: Session, g: EGroup, body: GroupIn) -> None:
    for k, v in body.model_dump(exclude={"bank_account", "members"}).items():
        setattr(g, k, v)
    if body.bank_account:
        g.bank_account_enc, g.bank_last4 = crypto.encrypt(body.bank_account), body.bank_account[-4:]
    g.members.clear()
    db.flush()
    by_mobile = {e.mobile: e.id for e in db.scalars(
        select(Entrepreneur).where(Entrepreneur.mobile.in_([x.mobile for x in body.members if x.mobile])))}
    for x in body.members:
        g.members.append(GroupMember(name=" ".join(x.name.split()), mobile=x.mobile, role=x.role, contribution=x.contribution,
                                     entrepreneur_id=by_mobile.get(x.mobile)))


def _check_group(db: Session, user: User, body: GroupIn, m: Masters):
    m.check(body)
    if user.role not in ("admin", "programme_manager") and (user.scope or {}).get("districts") \
            and body.district not in user.scope["districts"]:
        raise HTTPException(403, "This district is outside your area")


@router.post("/groups")
def create_group(body: GroupIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    m = Masters(db)
    _check_group(db, user, body, m)
    clash = db.scalar(select(EGroup).where(EGroup.name == body.name, EGroup.village == body.village))
    if clash:
        raise HTTPException(409, f"A group with this name is already enrolled in this village (ID {clash.id})")
    g = EGroup(created_by_id=user.id)
    db.add(g)
    _apply_group(db, g, body)
    db.flush()
    _audit(db, user, "group_create", "group", g.id, {"members": len(body.members)})
    db.commit()
    db.refresh(g)
    return group_out(g, m, user.language or "en")


@router.put("/groups/{gid}")
def update_group(gid: int, body: GroupIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    g = _get_group(db, user, gid)
    m = Masters(db)
    _check_group(db, user, body, m)
    _apply_group(db, g, body)
    _audit(db, user, "group_update", "group", g.id, {"members": len(body.members)})
    db.commit()
    db.refresh(g)
    return group_out(g, m, user.language or "en")


@router.post("/groups/{gid}/readiness")
def assess_group(gid: int, body: ReadinessIn, lang: Optional[str] = None, user: User = Depends(assessor), db: Session = Depends(get_db)):
    g = _get_group(db, user, gid)
    return record_readiness(db, user, body, g.corpus, _lang(user, lang), group=g)


# ================================================================ bulk import
IMPORT_COLUMNS = ["mobile", "full_name", "gender", "dob", "district", "mandal", "village", "context_tag", "social_category",
                  "education", "occupation", "skills", "interests", "investment_available", "monthly_income", "has_loans", "emi_amount"]
IMPORT_SAMPLE = ["9876500001", "Lakshmi Devi", "female", "1990-05-14", "guntur", "tenali", "kolakaluru", "rural", "obc", "secondary",
                 "homemaker", "cooking;sales", "food", "20000", "8000", "no", ""]


@router.get("/import/template")
def import_template(_: User = Depends(writer)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(IMPORT_COLUMNS)
    w.writerow(IMPORT_SAMPLE)
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="entrepreneurs_template.csv"'})


def _parse_date(v: str) -> date:
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise ValueError


def _num(v: str) -> float | None:
    v = (v or "").replace(",", "").strip()
    return float(v) if v else None


@router.post("/import")
async def import_entrepreneurs(commit: bool = False, source: Literal["import", "partner", "campaign"] = "import",
                               file: UploadFile = File(...), user: User = Depends(writer), db: Session = Depends(get_db)):
    """CSV of entrepreneurs (template above). Aadhaar and bank details are not imported – they are added later, in person.
    Imported people give their own consent the first time they log in with their mobile."""
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "The file is larger than 5 MB")
    rdr = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
    cols = {(c or "").strip().lower() for c in rdr.fieldnames or []}
    need = {"mobile", "full_name", "gender", "dob", "district", "mandal", "village", "context_tag"}
    if not need <= cols:
        raise HTTPException(422, f"Missing columns: {', '.join(sorted(need - cols))} (download the template)")
    m = Masters(db)
    known = set(db.scalars(select(Entrepreneur.mobile)))
    scope_d = (user.scope or {}).get("districts") if user.role not in ("admin", "programme_manager") else None
    rows, seen = [], set()
    for i, r0 in enumerate(rdr, start=2):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r0.items()}
        err, rec = [], {}
        mob = re.sub(r"\D", "", r.get("mobile", ""))[-10:]
        if not MOBILE_RE.match(mob):
            err.append("mobile is not a valid 10-digit number")
        elif mob in known:
            err.append("mobile already enrolled")
        elif mob in seen:
            err.append("mobile repeated in the file")
        seen.add(mob)
        name = " ".join(r.get("full_name", "").split())
        if len(name) < 2:
            err.append("full_name is empty")
        g = r.get("gender", "").lower()
        if g not in ("female", "male", "other"):
            err.append("gender must be female, male or other")
        dob = None
        try:
            dob = _parse_date(r.get("dob", ""))
            if not 18 <= age_on(dob) <= 60:
                err.append("age must be 18–60")
        except ValueError:
            err.append("dob must be YYYY-MM-DD or DD-MM-YYYY")
        if not m.has("district", r.get("district", "")):
            err.append(f"unknown district '{r.get('district', '')}'")
        elif scope_d and r["district"] not in scope_d:
            err.append("district is outside your area")
        if not r.get("mandal") or not r.get("village"):
            err.append("mandal and village are required")
        if r.get("context_tag", "").lower() not in ("rural", "urban", "tribal", "coastal"):
            err.append("context_tag must be rural, urban, tribal or coastal")
        for kind in ("social_category", "education", "occupation"):
            if r.get(kind) and not m.has(kind, r[kind]):
                err.append(f"unknown {kind.replace('_', ' ')} '{r[kind]}'")
        skills = [s.strip() for s in re.split(r"[;|]", r.get("skills", "")) if s.strip()]
        interests = [s.strip() for s in re.split(r"[;|]", r.get("interests", "")) if s.strip()]
        err += [f"unknown skill '{s}'" for s in skills if not m.has("skill", s)]
        err += [f"unknown sector '{s}'" for s in interests if not m.has("sector", s)]
        try:
            inv, inc, emi = _num(r.get("investment_available", "")), _num(r.get("monthly_income", "")), _num(r.get("emi_amount", ""))
        except ValueError:
            inv = inc = emi = None
            err.append("amounts must be numbers")
        loans = r.get("has_loans", "").lower()
        rec = {"line": i, "mobile": mob, "full_name": name, "gender": g, "dob": dob.isoformat() if dob else r.get("dob"),
               "district": r.get("district"), "mandal": r.get("mandal"), "village": r.get("village"),
               "context_tag": r.get("context_tag", "").lower(), "social_category": r.get("social_category") or None,
               "education": r.get("education") or None, "occupation": r.get("occupation") or None, "skills": skills,
               "interests": interests, "investment_available": inv, "monthly_income": inc,
               "has_loans": True if loans in ("yes", "y", "true", "1") else False if loans in ("no", "n", "false", "0") else None,
               "emi_amount": emi, "errors": err}
        rows.append(rec)
        if len(rows) > 5000:
            raise HTTPException(422, "Please import at most 5,000 people at a time")
    bad = [r for r in rows if r["errors"]]
    summary = {"rows": len(rows), "ok": len(rows) - len(bad), "errors": len(bad)}
    if not commit:
        return {"summary": summary, "preview": (bad + [r for r in rows if not r["errors"]])[:50]}
    if bad:
        raise HTTPException(422, f"Fix the {len(bad)} row(s) with errors before importing")
    for r in rows:
        d = {k: v for k, v in r.items() if k not in ("line", "errors")}
        d["dob"] = date.fromisoformat(d["dob"])
        acct = db.scalar(select(User.id).where(User.mobile == d["mobile"], User.role == "msme"))
        db.add(Entrepreneur(**d, user_id=acct, source=source, enrolled_by_id=user.id))
    _audit(db, user, "entrepreneur_import", "entrepreneur", None, {**summary, "source": source})
    db.commit()
    return {"summary": summary, "imported": True}


# ================================================================ photo files (for <img> tags; short-lived token in the URL)
@files.get("/photo/{name}")
def photo_file(name: str, t: str = Query(min_length=10)):
    if not re.fullmatch(r"[0-9a-f]{32}\.jpg", name):
        raise HTTPException(404, "Not found")
    try:
        claims = jwt.decode(t, settings.JWT_SECRET, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(403, "Link expired") from e
    if claims.get("purpose") != "photo" or claims.get("f") != name:
        raise HTTPException(403, "Link not valid")
    path = STORAGE / "photos" / name
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
