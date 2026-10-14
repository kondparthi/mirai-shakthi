"""Phase 1, Sprint 2 tables: EDP & skill-based training (spec M4, Forms 4.1–4.5)."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

TRACKS = {
    "awareness": ("Awareness EDP", "అవగాహన ఈడీపీ"),
    "core": ("Core EDP", "కోర్ ఈడీపీ"),
    "skill": ("Skill-based training", "నైపుణ్య శిక్షణ"),
    "ojt": ("On-the-job training", "ఉద్యోగంలో శిక్షణ"),
    "exposure": ("Exposure visit", "అనుభవ సందర్శన"),
    "refresher": ("Refresher", "రిఫ్రెషర్"),
}
# Readiness (Form 1.3) recommends trainings by label; this maps them to tracks.
READINESS_TRACK = {"Awareness EDP": "awareness", "Core EDP": "core", "Sector EDP": "skill", "Refresher": "refresher"}


class Course(Base):
    """Curriculum master: a course in one track, with its sessions, outcomes and assessment."""
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    track: Mapped[str] = mapped_column(String(12), index=True)
    name_en: Mapped[str] = mapped_column(String(160))
    name_te: Mapped[Optional[str]] = mapped_column(String(160))
    description_en: Mapped[Optional[str]] = mapped_column(Text)
    description_te: Mapped[Optional[str]] = mapped_column(Text)
    sectors: Mapped[list] = mapped_column(JSON, default=list)           # sector codes; empty = all sectors
    duration_days: Mapped[int] = mapped_column(SmallInteger, default=1)
    sessions: Mapped[list] = mapped_column(JSON, default=list)          # [{topic_en, topic_te, hours}]
    outcomes: Mapped[list] = mapped_column(JSON, default=list)          # learning outcomes (English)
    pass_mark: Mapped[int] = mapped_column(SmallInteger, default=60)    # quiz / theory %
    min_attendance: Mapped[int] = mapped_column(SmallInteger, default=75)
    practical_checklist: Mapped[list] = mapped_column(JSON, default=list)
    business_plan_score: Mapped[bool] = mapped_column(Boolean, default=False)  # Core EDP presentation
    external_certificate: Mapped[Optional[str]] = mapped_column(String(120))   # e.g. "DGCA Remote Pilot Certificate"
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class TrainingPartner(Base):
    """Form 4.4 – training institute, individual trainer or host unit (for on-the-job training)."""
    __tablename__ = "training_partners"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(12))                       # institute | trainer | host_unit
    contact_name: Mapped[Optional[str]] = mapped_column(String(120))
    mobile: Mapped[Optional[str]] = mapped_column(String(15))
    email: Mapped[Optional[str]] = mapped_column(String(190))
    accreditation: Mapped[Optional[str]] = mapped_column(String(255))
    tracks: Mapped[list] = mapped_column(JSON, default=list)
    sectors: Mapped[list] = mapped_column(JSON, default=list)
    districts: Mapped[list] = mapped_column(JSON, default=list)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    rate_batch: Mapped[Optional[float]] = mapped_column(Float)
    rate_trainee: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default="active")   # active | inactive
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Batch(Base):
    """Form 4.1 – a training batch of one course."""
    __tablename__ = "training_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_partners.id", ondelete="SET NULL"))
    trainer_ids: Mapped[list] = mapped_column(JSON, default=list)       # staff users with role trainer
    mentor_ids: Mapped[list] = mapped_column(JSON, default=list)        # staff users with role mentor
    mode: Mapped[str] = mapped_column(String(12), default="classroom")  # classroom | online | blended | ojt
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    venue: Mapped[Optional[str]] = mapped_column(String(255))
    host_unit: Mapped[Optional[str]] = mapped_column(String(160))
    district: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    seats: Mapped[int] = mapped_column(SmallInteger, default=30)
    sponsor_type: Mapped[str] = mapped_column(String(10), default="self")  # csr | govt | self
    sponsor_name: Mapped[Optional[str]] = mapped_column(String(160))
    pass_mark: Mapped[int] = mapped_column(SmallInteger, default=60)
    status: Mapped[str] = mapped_column(String(12), default="planned")  # planned | open | ongoing | completed | cancelled
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    course: Mapped[Course] = relationship()
    partner: Mapped[Optional[TrainingPartner]] = relationship()
    sessions: Mapped[list["BatchSession"]] = relationship(back_populates="batch", cascade="all, delete-orphan", order_by="BatchSession.n")
    trainees: Mapped[list["Trainee"]] = relationship(back_populates="batch", cascade="all, delete-orphan", order_by="Trainee.id")


class BatchSession(Base):
    __tablename__ = "training_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("training_batches.id", ondelete="CASCADE"), index=True)
    n: Mapped[int] = mapped_column(SmallInteger)
    date: Mapped[Optional[date]] = mapped_column(Date)
    topic: Mapped[str] = mapped_column(String(200))
    topic_te: Mapped[Optional[str]] = mapped_column(String(200))
    hours: Mapped[Optional[float]] = mapped_column(Float)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    photo: Mapped[Optional[str]] = mapped_column(String(120))
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lng: Mapped[Optional[float]] = mapped_column(Float)
    checkin_open: Mapped[bool] = mapped_column(Boolean, default=False)
    checkin_token: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    checkin_code: Mapped[Optional[str]] = mapped_column(String(6))

    batch: Mapped[Batch] = relationship(back_populates="sessions")
    attendance: Mapped[list["Attendance"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Trainee(Base):
    """A person in a batch: nomination, result (Form 4.2), certificate and feedback."""
    __tablename__ = "trainees"
    __table_args__ = (UniqueConstraint("batch_id", "entrepreneur_id", name="uq_trainee_batch_person"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("training_batches.id", ondelete="CASCADE"), index=True)
    entrepreneur_id: Mapped[int] = mapped_column(ForeignKey("entrepreneurs.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="confirmed")  # requested | confirmed | withdrawn | completed
    source: Mapped[str] = mapped_column(String(10), default="staff")       # staff | self
    mentor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    quiz_score: Mapped[Optional[float]] = mapped_column(Float)
    practical: Mapped[Optional[dict]] = mapped_column(JSON)                # {checklist item: true/false}
    practical_hours: Mapped[Optional[float]] = mapped_column(Float)
    bp_score: Mapped[Optional[float]] = mapped_column(Float)
    result: Mapped[Optional[str]] = mapped_column(String(10))              # pass | reassess | fail
    certificate_no: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    certificate_code: Mapped[Optional[str]] = mapped_column(String(8))
    certified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    feedback_rating: Mapped[Optional[int]] = mapped_column(SmallInteger)
    feedback_text: Mapped[Optional[str]] = mapped_column(Text)
    feedback_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    batch: Mapped[Batch] = relationship(back_populates="trainees")
    entrepreneur = relationship("Entrepreneur")
    followups: Mapped[list["FollowUp"]] = relationship(back_populates="trainee", cascade="all, delete-orphan", order_by="FollowUp.point")


class Attendance(Base):
    __tablename__ = "training_attendance"
    __table_args__ = (UniqueConstraint("session_id", "trainee_id", name="uq_attendance"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("training_sessions.id", ondelete="CASCADE"), index=True)
    trainee_id: Mapped[int] = mapped_column(ForeignKey("trainees.id", ondelete="CASCADE"), index=True)
    present: Mapped[bool] = mapped_column(Boolean, default=True)
    method: Mapped[str] = mapped_column(String(8), default="trainer")  # trainer | qr | code
    at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped[BatchSession] = relationship(back_populates="attendance")


class NeedsAssessment(Base):
    """Form 4.3 – training-needs assessment; decides the tracks."""
    __tablename__ = "training_needs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entrepreneur_id: Mapped[int] = mapped_column(ForeignKey("entrepreneurs.id", ondelete="CASCADE"), index=True)
    enterprise_model: Mapped[str] = mapped_column(String(160))
    business_skills: Mapped[dict] = mapped_column(JSON)          # costing, bookkeeping, marketing, digital, banking: 1–5
    technical_level: Mapped[int] = mapped_column(SmallInteger)
    prior_training: Mapped[list] = mapped_column(JSON, default=list)  # [{course, institute, year}]
    preferred_mode: Mapped[str] = mapped_column(String(12))
    preferred_timing: Mapped[str] = mapped_column(String(12))   # weekdays | weekends | any
    constraints: Mapped[list] = mapped_column(JSON, default=list)
    recommended_tracks: Mapped[list] = mapped_column(JSON, default=list)
    assessed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FollowUp(Base):
    """Form 4.5 – mentor follow-up 30 / 90 / 180 days after training."""
    __tablename__ = "training_followups"
    __table_args__ = (UniqueConstraint("trainee_id", "point", name="uq_followup_point"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trainee_id: Mapped[int] = mapped_column(ForeignKey("trainees.id", ondelete="CASCADE"), index=True)
    point: Mapped[int] = mapped_column(SmallInteger)             # 30 | 90 | 180
    status: Mapped[str] = mapped_column(String(14))              # started | in_process | not_started | employed | dropped
    skills_used: Mapped[str] = mapped_column(String(8))          # yes | partly | no
    support: Mapped[list] = mapped_column(JSON, default=list)    # refresher | finance | market | equipment | mentoring
    next_action: Mapped[Optional[str]] = mapped_column(String(255))
    next_date: Mapped[Optional[date]] = mapped_column(Date)
    recorded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    trainee: Mapped[Trainee] = relationship(back_populates="followups")


class ExternalCertificate(Base):
    """Certificates from outside MIRAI (DGCA RPC, FSSAI, partner certificates), uploaded and verified by staff."""
    __tablename__ = "external_certificates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entrepreneur_id: Mapped[int] = mapped_column(ForeignKey("entrepreneurs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(12))                # dgca_rpc | fssai | partner | other
    title: Mapped[str] = mapped_column(String(160))
    number: Mapped[Optional[str]] = mapped_column(String(60))
    issuer: Mapped[Optional[str]] = mapped_column(String(160))
    issued_on: Mapped[Optional[date]] = mapped_column(Date)
    file: Mapped[Optional[str]] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | verified | rejected
    note: Mapped[Optional[str]] = mapped_column(String(255))
    verified_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
