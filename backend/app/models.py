"""Database tables for Phase 0 (AI Guidance Assistant). MySQL 8 / MariaDB 10.6+, utf8mb4."""
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, SmallInteger,
                        String, Text, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

MODULES = ("microfin", "marketkonnect", "launchpad", "skillspro", "handholding")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(15), unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(190), unique=True)
    name: Mapped[Optional[str]] = mapped_column(String(120))
    # msme | expert | staff roles in app/roles.py (admin, programme_manager, coordinator, trainer, mentor, ...)
    role: Mapped[str] = mapped_column(String(20), default="msme", index=True)
    # Phase 1 data scope for staff: {"districts": [...], "sectors": [...]}. Empty = see only own records (admin sees all).
    scope: Mapped[Optional[dict]] = mapped_column(JSON)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(5), default="en")  # en | te
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_version: Mapped[Optional[str]] = mapped_column(String(20))
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    profile: Mapped[Optional["MsmeProfile"]] = relationship(back_populates="user", uselist=False)


class OtpCode(Base):
    __tablename__ = "otp_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mobile: Mapped[str] = mapped_column(String(15), index=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MsmeProfile(TimestampMixin, Base):
    """Form G-1 – Quick MSME Profile."""
    __tablename__ = "msme_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(120))
    business_name: Mapped[Optional[str]] = mapped_column(String(160))
    stage: Mapped[Optional[str]] = mapped_column(String(20))          # planning | lt1 | 1to3 | gt3
    business_type: Mapped[Optional[str]] = mapped_column(String(20))  # manufacturing | trading | services
    sector: Mapped[Optional[str]] = mapped_column(String(60))
    product: Mapped[Optional[str]] = mapped_column(String(255))
    district: Mapped[Optional[str]] = mapped_column(String(80))
    mandal: Mapped[Optional[str]] = mapped_column(String(80))
    ownership: Mapped[Optional[str]] = mapped_column(String(20))      # proprietor | partnership | llp | company | shg
    turnover_band: Mapped[Optional[int]] = mapped_column(SmallInteger)  # 0..5, see TURNOVER_BANDS
    employees: Mapped[Optional[int]] = mapped_column(Integer)
    registrations: Mapped[list] = mapped_column(JSON, default=list)  # udyam, gst, fssai, trade, iec, shop_est
    channels: Mapped[list] = mapped_column(JSON, default=list)       # local, wholesale, online, government, export, interstate
    books_kept: Mapped[Optional[str]] = mapped_column(String(20))     # none | notebook | excel | software
    has_loan: Mapped[Optional[bool]] = mapped_column(Boolean)
    flags: Mapped[list] = mapped_column(JSON, default=list)          # women_led, sc_st, first_gen
    user: Mapped[User] = relationship(back_populates="profile")


TURNOVER_BANDS = {
    0: "Nil / not started",
    1: "Up to ₹10 lakh",
    2: "₹10–40 lakh",
    3: "₹40 lakh – ₹1 crore",
    4: "₹1–5 crore",
    5: "Above ₹5 crore",
}


class Intent(Base):
    """A question type the assistant understands, grouped by guidance module."""
    __tablename__ = "intents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    module: Mapped[str] = mapped_column(String(20), index=True)
    title_en: Mapped[str] = mapped_column(String(160))
    title_te: Mapped[Optional[str]] = mapped_column(String(160))
    description: Mapped[Optional[str]] = mapped_column(String(500))
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    sample_questions: Mapped[list] = mapped_column(JSON, default=list)
    connect_service: Mapped[Optional[str]] = mapped_column(String(60))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    rules: Mapped[list["RequirementRule"]] = relationship(back_populates="intent", order_by="RequirementRule.step_order")


class RequirementRule(TimestampMixin, Base):
    """Admin screen A2 – what is required for an intent, and when it applies."""
    __tablename__ = "requirement_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intent_id: Mapped[int] = mapped_column(ForeignKey("intents.id", ondelete="CASCADE"), index=True)
    item_code: Mapped[str] = mapped_column(String(60))
    title_en: Mapped[str] = mapped_column(String(200))
    title_te: Mapped[Optional[str]] = mapped_column(String(200))
    why_en: Mapped[Optional[str]] = mapped_column(Text)
    why_te: Mapped[Optional[str]] = mapped_column(Text)  # Sprint 5
    condition: Mapped[Optional[dict]] = mapped_column(JSON)   # when the item applies (empty = always)
    have_check: Mapped[Optional[dict]] = mapped_column(JSON)  # when the user already has it
    step_order: Mapped[int] = mapped_column(SmallInteger, default=10)
    documents: Mapped[Optional[str]] = mapped_column(String(500))
    time_estimate: Mapped[Optional[str]] = mapped_column(String(80))
    cost_note: Mapped[Optional[str]] = mapped_column(String(160))
    official_link: Mapped[Optional[str]] = mapped_column(String(300))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    intent: Mapped[Intent] = relationship(back_populates="rules")


class KbItem(TimestampMixin, Base):
    """Admin screen A1 / Form G-8 – verified knowledge content used for answers."""
    __tablename__ = "kb_items"
    __table_args__ = (Index("ft_kb_title_body", "title", "body", mysql_prefix="FULLTEXT"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    module: Mapped[str] = mapped_column(String(20), index=True)
    intent_code: Mapped[Optional[str]] = mapped_column(String(60), index=True)
    language: Mapped[str] = mapped_column(String(5), default="en")
    body: Mapped[str] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String(300))
    verified_by: Mapped[Optional[str]] = mapped_column(String(120))
    verified_on: Mapped[Optional[date]] = mapped_column(Date)
    review_due: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(15), default="draft")  # draft | published | archived


class GuidanceSession(TimestampMixin, Base):
    __tablename__ = "guidance_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    module: Mapped[Optional[str]] = mapped_column(String(20))
    intent_code: Mapped[Optional[str]] = mapped_column(String(60))
    title: Mapped[Optional[str]] = mapped_column(String(200))
    current_step: Mapped[int] = mapped_column(SmallInteger, default=1)
    language: Mapped[str] = mapped_column(String(5), default="en")
    messages: Mapped[list["GuidanceMessage"]] = relationship(back_populates="session", order_by="GuidanceMessage.id")
    gaps: Mapped[list["SessionGap"]] = relationship(back_populates="session")


class GuidanceMessage(Base):
    __tablename__ = "guidance_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("guidance_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    payload: Mapped[Optional[dict]] = mapped_column(JSON)  # structured five-step result
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger)  # 1 = helpful, -1 = not helpful
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    session: Mapped[GuidanceSession] = relationship(back_populates="messages")


class SessionGap(Base):
    __tablename__ = "session_gaps"
    __table_args__ = (UniqueConstraint("session_id", "item_code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("guidance_sessions.id", ondelete="CASCADE"))
    item_code: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(10))  # have | missing | done
    session: Mapped[GuidanceSession] = relationship(back_populates="gaps")


class Expert(TimestampMixin, Base):
    """Form G-7 – expert / institution directory used by Handholding."""
    __tablename__ = "experts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    organisation: Mapped[Optional[str]] = mapped_column(String(160))
    expert_type: Mapped[str] = mapped_column(String(30))  # ca | cs | bdsp | bank | nbfc | specialist | govt | trainer
    services: Mapped[list] = mapped_column(JSON, default=list)
    reg_no: Mapped[Optional[str]] = mapped_column(String(60))
    districts: Mapped[list] = mapped_column(JSON, default=list)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    fee_note: Mapped[Optional[str]] = mapped_column(String(160))
    response_hours: Mapped[int] = mapped_column(SmallInteger, default=48)
    rating: Mapped[Optional[float]] = mapped_column()
    status: Mapped[str] = mapped_column(String(15), default="pending")  # pending | approved | suspended
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class ConnectRequest(TimestampMixin, Base):
    """Form G-6 – request sent from the assistant to an expert (full workflow in Sprint 4)."""
    __tablename__ = "connect_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("guidance_sessions.id", ondelete="SET NULL"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expert_id: Mapped[Optional[int]] = mapped_column(ForeignKey("experts.id", ondelete="SET NULL"), index=True)
    service: Mapped[str] = mapped_column(String(60))
    summary: Mapped[str] = mapped_column(Text)
    preferred_contact: Mapped[Optional[str]] = mapped_column(String(20))
    budget: Mapped[Optional[str]] = mapped_column(String(30))
    consent_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(15), default="sent")  # see app/connect/workflow.py
    updates: Mapped[list["ConnectUpdate"]] = relationship(back_populates="request", order_by="ConnectUpdate.id")
    expert: Mapped[Optional["Expert"]] = relationship()
    user: Mapped["User"] = relationship()


class ConnectUpdate(Base):
    """Timeline of a Handholding request: messages, status changes, quotes, shared documents and the rating."""
    __tablename__ = "connect_updates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("connect_requests.id", ondelete="CASCADE"), index=True)
    author_role: Mapped[str] = mapped_column(String(10))  # msme | expert | admin | system
    author_id: Mapped[Optional[int]] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))  # message | status | quote | share | rating
    status: Mapped[Optional[str]] = mapped_column(String(15))  # new status, for kind = status
    text: Mapped[Optional[str]] = mapped_column(Text)
    amount: Mapped[Optional[float]] = mapped_column()  # quote amount (Rs.) or rating (1-5)
    data: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    request: Mapped[ConnectRequest] = relationship(back_populates="updates")


class Artefact(Base):
    """Documents the assistant generates for a user (roadmap, checklist, cash-flow summary, job description).
    Inputs and computed outputs are stored; the PDF is rendered on download, so no files are kept on disk."""
    __tablename__ = "artefacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("guidance_sessions.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(20), index=True)  # roadmap | checklist | cashflow | jd
    title: Mapped[str] = mapped_column(String(200))
    inputs: Mapped[Optional[dict]] = mapped_column(JSON)
    outputs: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[Optional[str]] = mapped_column(String(60))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    detail: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# Phase 1 tables live in their own module; importing it registers them with the same metadata.
from . import models_p1  # noqa: E402,F401
from . import models_p2  # noqa: E402,F401
