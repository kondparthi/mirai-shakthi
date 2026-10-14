"""Shared enrolment logic (M1) used by self-enrolment, assisted enrolment and import."""
import io
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import crypto
from ..config import settings
from ..models import User
from ..models_p1 import LIFECYCLE, LIFECYCLE_TE, EGroup, Entrepreneur, MasterItem
from ..roles import ALL_SCOPE

MOBILE_RE = re.compile(r"^[6-9]\d{9}$")
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
STORAGE = Path(__file__).resolve().parents[2] / "storage"

# ----------------------------------------------------------------- Aadhaar (Verhoeff checksum); only the last 4 digits are kept
_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
      [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1], [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
      [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
      [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1], [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]


def aadhaar_valid(num: str) -> bool:
    if not re.fullmatch(r"[2-9]\d{11}", num):
        return False
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def age_on(dob: date, today: date | None = None) -> int:
    t = today or date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


def _clean_account(v):
    if not v:
        return None
    v = re.sub(r"\s", "", v)
    if not re.fullmatch(r"\d{9,18}", v):
        raise ValueError("Bank account number must be 9 to 18 digits")
    return v


def _clean_ifsc(v):
    if not v:
        return None
    v = v.strip().upper()
    if not IFSC_RE.match(v):
        raise ValueError("IFSC must look like SBIN0001234 (11 characters, fifth is zero)")
    return v


# ----------------------------------------------------------------- input
class EntrepreneurIn(BaseModel):
    """Form 1.1. Sensitive numbers are accepted here and never sent back in full."""
    full_name: str = Field(min_length=2, max_length=120)
    gender: Literal["female", "male", "other"]
    dob: date
    social_category: str = Field(min_length=2, max_length=30)
    education: str = Field(min_length=2, max_length=30)
    district: str = Field(min_length=2, max_length=80)
    mandal: str = Field(min_length=1, max_length=80)
    village: str = Field(min_length=1, max_length=120)
    context_tag: Literal["rural", "urban", "tribal", "coastal"]
    aadhaar: Optional[str] = None          # 12 digits; only the last 4 are stored
    pan: Optional[str] = None
    bank_account: Optional[str] = None
    ifsc: Optional[str] = None
    bank_name: Optional[str] = Field(default=None, max_length=80)
    skills: list[str] = Field(min_length=1)
    interests: list[str] = Field(min_length=1)
    investment_available: float = Field(ge=0, le=100_000_000)
    has_loans: bool
    emi_amount: Optional[float] = Field(default=None, ge=0)
    occupation: str = Field(min_length=2, max_length=40)
    monthly_income: float = Field(ge=0, le=10_000_000)

    @field_validator("full_name")
    @classmethod
    def v_name(cls, v):
        return " ".join(v.split())

    @field_validator("dob")
    @classmethod
    def v_dob(cls, v):
        if not 18 <= age_on(v) <= 60:
            raise ValueError("Age must be between 18 and 60")
        return v

    @field_validator("aadhaar")
    @classmethod
    def v_aadhaar(cls, v):
        if not v:
            return None
        v = re.sub(r"\D", "", v)
        if not aadhaar_valid(v):
            raise ValueError("Aadhaar number is not valid – please check the 12 digits")
        return v

    @field_validator("pan")
    @classmethod
    def v_pan(cls, v):
        if not v:
            return None
        v = v.strip().upper()
        if not PAN_RE.match(v):
            raise ValueError("PAN must look like ABCDE1234F")
        return v

    @field_validator("bank_account")
    @classmethod
    def v_acct(cls, v):
        return _clean_account(v)

    @field_validator("ifsc")
    @classmethod
    def v_ifsc(cls, v):
        return _clean_ifsc(v)

    @model_validator(mode="after")
    def v_bank_pair(self):
        if bool(self.bank_account) != bool(self.ifsc):
            raise ValueError("Enter both the bank account number and the IFSC")
        if self.has_loans and self.emi_amount is None:
            raise ValueError("Enter the monthly EMI amount for existing loans")
        return self


class MemberIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    mobile: Optional[str] = None
    role: Literal["leader", "secretary", "treasurer", "member"] = "member"
    contribution: Optional[float] = Field(default=None, ge=0)

    @field_validator("mobile")
    @classmethod
    def v_mobile(cls, v):
        if not v:
            return None
        v = re.sub(r"\D", "", v)[-10:]
        if not MOBILE_RE.match(v):
            raise ValueError("Member mobile must be a valid 10-digit number")
        return v


class GroupIn(BaseModel):
    """Form 1.2."""
    name: str = Field(min_length=2, max_length=160)
    group_type: Literal["shg", "jlg", "producer", "cooperative", "other"]
    reg_code: Optional[str] = Field(default=None, max_length=60)
    federation: Optional[str] = Field(default=None, max_length=160)
    formation_date: date
    district: str = Field(min_length=2, max_length=80)
    mandal: str = Field(min_length=1, max_length=80)
    village: str = Field(min_length=1, max_length=120)
    context_tag: Literal["rural", "urban", "tribal", "coastal"]
    bank_account: Optional[str] = None
    ifsc: Optional[str] = None
    corpus: Optional[float] = Field(default=None, ge=0)
    existing_activity: Optional[str] = Field(default=None, max_length=255)
    members: list[MemberIn] = Field(min_length=2, max_length=60)

    @field_validator("bank_account")
    @classmethod
    def v_acct(cls, v):
        return _clean_account(v)

    @field_validator("ifsc")
    @classmethod
    def v_ifsc(cls, v):
        return _clean_ifsc(v)

    @field_validator("formation_date")
    @classmethod
    def v_formed(cls, v):
        if v > date.today():
            raise ValueError("Formation date cannot be in the future")
        return v

    @model_validator(mode="after")
    def v_roles(self):
        roles = [m.role for m in self.members]
        for r in ("leader", "secretary", "treasurer"):
            if roles.count(r) != 1:
                raise ValueError(f"Choose exactly one {r}")
        mobiles = [m.mobile for m in self.members if m.mobile]
        if len(mobiles) != len(set(mobiles)):
            raise ValueError("The same mobile number appears twice in the members list")
        return self


# ----------------------------------------------------------------- masters lookup
class Masters:
    """Small per-request cache of master names, to validate codes and show names."""

    def __init__(self, db: Session):
        self.rows = {(m.kind, m.code): m for m in db.scalars(select(MasterItem))}

    def has(self, kind: str, code: str) -> bool:
        return (kind, code) in self.rows

    def name(self, kind: str, code: str | None, lang: str = "en") -> str | None:
        if not code:
            return None
        m = self.rows.get((kind, code))
        if not m:
            return code  # free-text village or mandal not in the master yet
        return (m.name_te if lang == "te" and m.name_te else m.name_en)

    def check(self, body: "EntrepreneurIn | GroupIn"):
        errors = []
        if not self.has("district", body.district):
            errors.append("Choose a district from the list")
        checks = [("social_category", getattr(body, "social_category", None)), ("education", getattr(body, "education", None)),
                  ("occupation", getattr(body, "occupation", None))]
        errors += [f"Unknown {k.replace('_', ' ')}: {v}" for k, v in checks if v and not self.has(k, v)]
        errors += [f"Unknown skill: {s}" for s in getattr(body, "skills", []) if not self.has("skill", s)]
        errors += [f"Unknown sector: {s}" for s in getattr(body, "interests", []) if not self.has("sector", s)]
        if errors:
            raise HTTPException(422, "; ".join(errors))


# ----------------------------------------------------------------- duplicates
def find_duplicates(db: Session, mobile: str | None, aadhaar_last4: str | None, full_name: str | None, dob: date | None,
                    exclude_id: int | None = None) -> list[Entrepreneur]:
    """Spec M1: duplicate check on mobile, and on Aadhaar last 4 + name + date of birth."""
    conds = []
    if mobile:
        conds.append(Entrepreneur.mobile == mobile)
    if aadhaar_last4 and full_name and dob:
        conds.append((Entrepreneur.aadhaar_last4 == aadhaar_last4) & (Entrepreneur.dob == dob)
                     & (Entrepreneur.full_name == " ".join(full_name.split())))
    if not conds:
        return []
    q = select(Entrepreneur).where(or_(*conds))
    if exclude_id:
        q = q.where(Entrepreneur.id != exclude_id)
    return list(db.scalars(q))


# ----------------------------------------------------------------- apply input
def apply_entrepreneur(e: Entrepreneur, body: EntrepreneurIn) -> None:
    # Aadhaar and bank account are never sent back to the form, so leaving them blank on an edit keeps what is stored.
    data = body.model_dump(exclude={"aadhaar", "bank_account", "consent"} | (set() if body.bank_account else {"ifsc"}))
    for k, v in data.items():
        setattr(e, k, v)
    if not body.has_loans:
        e.emi_amount = None
    if body.aadhaar:
        e.aadhaar_last4 = body.aadhaar[-4:]
    if body.bank_account:
        e.bank_account_enc = crypto.encrypt(body.bank_account)
        e.bank_last4 = body.bank_account[-4:]


def missing_items(e: Entrepreneur) -> list[str]:
    """Required items (Form 1.1) still to be given before staff can verify the profile."""
    out = []
    if not e.photo:
        out.append("photo")
    if not e.aadhaar_last4:
        out.append("aadhaar")
    if not e.bank_account_enc:
        out.append("bank_account")
    if not e.consent_at:
        out.append("consent")
    for f in ("gender", "dob", "social_category", "education", "district", "mandal", "village", "occupation"):
        if not getattr(e, f):
            out.append(f)
    if not e.skills:
        out.append("skills")
    if not e.interests:
        out.append("interests")
    return out


# ----------------------------------------------------------------- data scope
def scoped(stmt, user: User, model):
    """Limit a query to the staff member's districts / sectors (Spec Section 3). Admin and programme managers see all;
    staff with no districts set see only the records they created."""
    if user.role in ALL_SCOPE:
        return stmt
    sc = user.scope or {}
    if sc.get("districts"):
        stmt = stmt.where(model.district.in_(sc["districts"]))
    elif model is Entrepreneur:
        stmt = stmt.where(Entrepreneur.enrolled_by_id == user.id)
    else:
        stmt = stmt.where(EGroup.created_by_id == user.id)
    return stmt


def can_see(user: User, obj) -> bool:
    if user.role in ALL_SCOPE:
        return True
    sc = user.scope or {}
    if sc.get("districts"):
        return obj.district in sc["districts"]
    owner = obj.enrolled_by_id if isinstance(obj, Entrepreneur) else obj.created_by_id
    return owner == user.id


# ----------------------------------------------------------------- output
def entrepreneur_out(e: Entrepreneur, m: Masters, lang: str = "en", full: bool = True) -> dict:
    latest = e.assessments[0] if e.assessments else None
    d = {
        "id": e.id, "full_name": e.full_name, "mobile": e.mobile, "gender": e.gender,
        "district": e.district, "district_name": m.name("district", e.district, lang),
        "mandal": e.mandal, "mandal_name": m.name("mandal", e.mandal, lang),
        "village": e.village, "village_name": m.name("village", e.village, lang),
        "context_tag": e.context_tag, "stage": e.stage, "stage_name": (LIFECYCLE_TE if lang == "te" else LIFECYCLE).get(e.stage),
        "status": e.status, "verified": e.verified, "source": e.source,
        "interests": e.interests or [], "interest_names": [m.name("sector", s, lang) for s in e.interests or []],
        "readiness": {"score": latest.score, "at": latest.created_at.isoformat() if latest.created_at else None} if latest else None,
        "has_photo": bool(e.photo), "photo_url": photo_url(e.photo), "consent": bool(e.consent_at),
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }
    if full:
        d.update({
            "dob": e.dob.isoformat() if e.dob else None, "social_category": e.social_category, "education": e.education,
            "social_category_name": m.name("social_category", e.social_category, lang), "education_name": m.name("education", e.education, lang),
            "occupation_name": m.name("occupation", e.occupation, lang), "bank_label": m.name("bank", e.bank_name, lang),
            "aadhaar_masked": f"XXXX XXXX {e.aadhaar_last4}" if e.aadhaar_last4 else None, "pan": e.pan,
            "bank_masked": crypto.mask(e.bank_last4) if e.bank_last4 else None, "ifsc": e.ifsc, "bank_name": e.bank_name,
            "skills": e.skills or [], "skill_names": [m.name("skill", s, lang) for s in e.skills or []],
            "investment_available": e.investment_available, "has_loans": e.has_loans, "emi_amount": e.emi_amount,
            "occupation": e.occupation, "monthly_income": e.monthly_income,
            "consent_version": e.consent_version, "consent_at": e.consent_at.isoformat() if e.consent_at else None,
            "groups": [{"id": gm.group.id, "name": gm.group.name, "role": gm.role} for gm in e.memberships],
            "missing": missing_items(e),
        })
    return d


def group_out(g: EGroup, m: Masters, lang: str = "en", full: bool = True) -> dict:
    latest = g.assessments[0] if g.assessments else None
    d = {"id": g.id, "name": g.name, "group_type": g.group_type, "district": g.district, "district_name": m.name("district", g.district, lang),
         "mandal": g.mandal, "mandal_name": m.name("mandal", g.mandal, lang), "village": g.village, "village_name": m.name("village", g.village, lang),
         "context_tag": g.context_tag, "stage": g.stage, "members_count": len(g.members),
         "leader": next((x.name for x in g.members if x.role == "leader"), None),
         "readiness": {"score": latest.score} if latest else None}
    if full:
        d.update({"reg_code": g.reg_code, "federation": g.federation, "formation_date": g.formation_date.isoformat() if g.formation_date else None,
                  "bank_masked": crypto.mask(g.bank_last4) if g.bank_last4 else None, "ifsc": g.ifsc, "corpus": g.corpus,
                  "existing_activity": g.existing_activity,
                  "members": [{"id": x.id, "name": x.name, "mobile": x.mobile, "role": x.role, "contribution": x.contribution,
                               "entrepreneur_id": x.entrepreneur_id} for x in g.members]})
    return d


# ----------------------------------------------------------------- photos
def save_photo(data: bytes) -> str:
    """Store a profile photo as a JPEG of at most 800 px (small enough for low-end phones). Returns the file name."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "The photo is larger than 8 MB")
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(422, "Please upload a photo (JPG or PNG)") from e
    img.thumbnail((800, 800))
    folder = STORAGE / "photos"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jpg"
    img.save(folder / name, "JPEG", quality=82, optimize=True)
    return name


def delete_photo(name: str | None) -> None:
    if name:
        (STORAGE / "photos" / name).unlink(missing_ok=True)


def photo_token(name: str) -> str:
    from datetime import UTC, datetime, timedelta
    from jose import jwt
    from ..security import ALGO
    return jwt.encode({"purpose": "photo", "f": name, "exp": datetime.now(UTC) + timedelta(hours=2)}, settings.JWT_SECRET, algorithm=ALGO)


def photo_url(name: str | None) -> str | None:
    """Relative URL an <img> can load without the login header (token valid 2 hours)."""
    return f"/api/v1/files/photo/{name}?t={photo_token(name)}" if name else None
