"""Phase 1, Sprint 1 tables: master data (M14) and entrepreneur / group enrolment (M1)."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

LIFECYCLE = {
    1: "Enrol & assess", 2: "Train & certify", 3: "DPR & finance", 4: "Set up enterprise",
    5: "Sell & deliver", 6: "Track business", 7: "Mentor & resolve", 8: "Grow & sustain",
}
LIFECYCLE_TE = {
    1: "నమోదు & అంచనా", 2: "శిక్షణ & ధృవీకరణ", 3: "డీపీఆర్ & ఆర్థిక సహాయం", 4: "వ్యాపారం ఏర్పాటు",
    5: "అమ్మకం & సేవ", 6: "వ్యాపార లెక్కలు", 7: "మెంటారింగ్ & పరిష్కారం", 8: "వృద్ధి & స్థిరత్వం",
}


class MasterItem(Base):
    """One row of any master list (M14). kind = district | mandal | village | context_tag | sector | skill | education |
    occupation | social_category | doc_type | bank. Villages/mandals point to their parent; extra fields live in `data`."""
    __tablename__ = "master_items"
    __table_args__ = (UniqueConstraint("kind", "code", name="uq_master_kind_code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name_en: Mapped[str] = mapped_column(String(160))
    name_te: Mapped[Optional[str]] = mapped_column(String(160))
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("master_items.id", ondelete="SET NULL"), index=True)
    data: Mapped[Optional[dict]] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=100)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Setting(Base):
    """Admin-editable configuration, e.g. the readiness score formula."""
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Entrepreneur(Base):
    """Form 1.1 – Individual entrepreneur profile."""
    __tablename__ = "entrepreneurs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), unique=True)
    mobile: Mapped[str] = mapped_column(String(15), unique=True)
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    photo: Mapped[Optional[str]] = mapped_column(String(120))          # file name in storage/photos
    gender: Mapped[Optional[str]] = mapped_column(String(10))          # female | male | other
    dob: Mapped[Optional[date]] = mapped_column(Date)
    social_category: Mapped[Optional[str]] = mapped_column(String(30))
    education: Mapped[Optional[str]] = mapped_column(String(30))
    district: Mapped[Optional[str]] = mapped_column(String(80), index=True)   # master codes
    mandal: Mapped[Optional[str]] = mapped_column(String(80))
    village: Mapped[Optional[str]] = mapped_column(String(120))
    context_tag: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    # Only the last 4 digits of Aadhaar are stored (duplicate check). Storing the full number needs an Aadhaar Data Vault.
    aadhaar_last4: Mapped[Optional[str]] = mapped_column(String(4), index=True)
    pan: Mapped[Optional[str]] = mapped_column(String(10))
    bank_account_enc: Mapped[Optional[str]] = mapped_column(String(255))
    bank_last4: Mapped[Optional[str]] = mapped_column(String(4))
    ifsc: Mapped[Optional[str]] = mapped_column(String(11))
    bank_name: Mapped[Optional[str]] = mapped_column(String(80))
    skills: Mapped[list] = mapped_column(JSON, default=list)
    interests: Mapped[list] = mapped_column(JSON, default=list)       # sector codes
    investment_available: Mapped[Optional[float]] = mapped_column(Float)
    has_loans: Mapped[Optional[bool]] = mapped_column(Boolean)
    emi_amount: Mapped[Optional[float]] = mapped_column(Float)
    occupation: Mapped[Optional[str]] = mapped_column(String(40))
    monthly_income: Mapped[Optional[float]] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default="self")   # self | navigator | partner | campaign | import
    enrolled_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    consent_version: Mapped[Optional[str]] = mapped_column(String(20))
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    stage: Mapped[int] = mapped_column(SmallInteger, default=1)
    status: Mapped[str] = mapped_column(String(10), default="active")  # active | paused | closed
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    memberships: Mapped[list["GroupMember"]] = relationship(back_populates="entrepreneur")
    assessments: Mapped[list["ReadinessAssessment"]] = relationship(
        back_populates="entrepreneur", order_by="ReadinessAssessment.id.desc()", cascade="all, delete-orphan")


class EGroup(Base):
    """Form 1.2 – SHG / group profile."""
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    group_type: Mapped[str] = mapped_column(String(20))               # shg | jlg | producer | cooperative | other
    reg_code: Mapped[Optional[str]] = mapped_column(String(60))
    federation: Mapped[Optional[str]] = mapped_column(String(160))    # Village Organisation / Mandal Samakhya
    formation_date: Mapped[Optional[date]] = mapped_column(Date)
    district: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    mandal: Mapped[Optional[str]] = mapped_column(String(80))
    village: Mapped[Optional[str]] = mapped_column(String(120))
    context_tag: Mapped[Optional[str]] = mapped_column(String(20))
    bank_account_enc: Mapped[Optional[str]] = mapped_column(String(255))
    bank_last4: Mapped[Optional[str]] = mapped_column(String(4))
    ifsc: Mapped[Optional[str]] = mapped_column(String(11))
    corpus: Mapped[Optional[float]] = mapped_column(Float)
    existing_activity: Mapped[Optional[str]] = mapped_column(String(255))
    stage: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    members: Mapped[list["GroupMember"]] = relationship(back_populates="group", cascade="all, delete-orphan", order_by="GroupMember.id")
    assessments: Mapped[list["ReadinessAssessment"]] = relationship(
        back_populates="group", order_by="ReadinessAssessment.id.desc()", cascade="all, delete-orphan")


class GroupMember(Base):
    __tablename__ = "group_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    entrepreneur_id: Mapped[Optional[int]] = mapped_column(ForeignKey("entrepreneurs.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    mobile: Mapped[Optional[str]] = mapped_column(String(15))
    role: Mapped[str] = mapped_column(String(12), default="member")   # leader | secretary | treasurer | member
    contribution: Mapped[Optional[float]] = mapped_column(Float)

    group: Mapped[EGroup] = relationship(back_populates="members")
    entrepreneur: Mapped[Optional[Entrepreneur]] = relationship(back_populates="memberships")


class ReadinessAssessment(Base):
    """Form 1.3 – Enterprise readiness assessment (repeatable)."""
    __tablename__ = "readiness_assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entrepreneur_id: Mapped[Optional[int]] = mapped_column(ForeignKey("entrepreneurs.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    answers: Mapped[dict] = mapped_column(JSON)
    score: Mapped[int] = mapped_column(SmallInteger)
    breakdown: Mapped[list] = mapped_column(JSON)
    strengths: Mapped[list] = mapped_column(JSON)
    gaps: Mapped[list] = mapped_column(JSON)
    recommended: Mapped[list] = mapped_column(JSON)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    assessed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entrepreneur: Mapped[Optional[Entrepreneur]] = relationship(back_populates="assessments")
    group: Mapped[Optional[EGroup]] = relationship(back_populates="assessments")


class DataRequest(Base):
    """DPDP Act 2023 – a person's request to export or delete their data."""
    __tablename__ = "data_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(15))
    kind: Mapped[str] = mapped_column(String(10))                     # export | delete
    status: Mapped[str] = mapped_column(String(12), default="open")   # open | done | rejected
    reason: Mapped[Optional[str]] = mapped_column(Text)
    resolution: Mapped[Optional[str]] = mapped_column(Text)
    resolved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
