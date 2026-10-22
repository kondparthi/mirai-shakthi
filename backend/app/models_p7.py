"""Phase 1, Sprint 7 tables: mentoring and two-year handholding (spec M10).
- Mentorship: a mentor for a unit over 24 months, closed with a final assessment
- Monthly review (Form 10.1) with health rating, issues, agreed actions and training needs
- Field visits with geo-tagged photos
- Support tickets (Form 10.2) with category routing, priority, referrals and resolution time
- Growth plans (Form 10.3)
- Monthly mentor-led peer sessions for each training batch."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .models_p4 import Unit

HANDHOLDING_MONTHS = 24
ISSUES = {"sales": ("Sales", "అమ్మకాలు"), "cash_flow": ("Cash flow", "నగదు ప్రవాహం"), "equipment": ("Equipment", "పరికరాలు"),
          "skills": ("Skills", "నైపుణ్యాలు"), "family": ("Family", "కుటుంబం"), "compliance": ("Compliance", "నిబంధనలు")}
TICKET_CATEGORIES = {"equipment": ("Equipment", "పరికరాలు"), "finance": ("Finance / loan", "ఆర్థికం / రుణం"), "market": ("Market / sales", "మార్కెట్ / అమ్మకాలు"),
                     "technical": ("Technical / sector", "సాంకేతిక"), "registration": ("Registration / licence", "నమోదు / లైసెన్స్"), "other": ("Other", "ఇతర")}
# Who a new ticket goes to (in the unit's district); the unit's mentor when nobody with that role is found.
TICKET_ROUTING = {"equipment": "procurement", "finance": "dpr_officer", "market": "coordinator", "technical": "sector_expert",
                  "registration": "coordinator", "other": "mentor"}
TICKET_SLA_DAYS = {"high": 2, "medium": 5, "low": 10}
GOALS = {"increase_sales": ("Increase sales", "అమ్మకాలు పెంచడం"), "new_product": ("New product / service", "కొత్త ఉత్పత్తి / సేవ"),
         "second_unit": ("Second unit", "రెండో యూనిట్"), "hire": ("Hire people", "ఉద్యోగులను నియమించడం"), "expansion_loan": ("Expansion loan", "విస్తరణ రుణం")}
SUPPORT = {"training": ("Training", "శిక్షణ"), "finance": ("Finance", "ఆర్థిక సహాయం"), "market": ("Market linkage", "మార్కెట్ అనుసంధానం"),
           "equipment": ("Equipment", "పరికరాలు")}
TRAINING_NEEDS = {"refresher": "Refresher", "advanced": "Advanced", "skill_upgrade": "Skill upgrade"}
OUTCOMES = {"thriving": "Thriving – growing", "stable": "Stable – running", "struggling": "Struggling – needs support", "closed": "Closed down"}


class Mentorship(Base):
    """A mentor's two-year handholding of one unit (re-assignment keeps the history)."""
    __tablename__ = "mentorships"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), unique=True)
    mentor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)                      # start + 24 months
    status: Mapped[str] = mapped_column(String(10), default="active")  # active | closed
    history: Mapped[list] = mapped_column(JSON, default=list)          # [{mentor_id, name, from, to, by, reason}]
    # final assessment
    closed_on: Mapped[Optional[date]] = mapped_column(Date)
    outcome: Mapped[Optional[str]] = mapped_column(String(12))
    final_score: Mapped[Optional[int]] = mapped_column(SmallInteger)   # 1–5
    final: Mapped[Optional[dict]] = mapped_column(JSON)                # {sales_first, sales_last, jobs, note, ...}
    closed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    unit: Mapped[Unit] = relationship()
    mentor = relationship("User", foreign_keys=[mentor_id])


class MentorReview(Base):
    """Form 10.1 – the mentor's monthly review of a unit."""
    __tablename__ = "mentor_reviews"
    __table_args__ = (UniqueConstraint("unit_id", "month", name="uq_review_month"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)          # YYYY-MM
    sales: Mapped[float] = mapped_column(Float, default=0)
    expenses: Mapped[float] = mapped_column(Float, default=0)
    profit: Mapped[float] = mapped_column(Float, default=0)
    corrected: Mapped[bool] = mapped_column(default=False)             # mentor changed the figures from M9
    books: Mapped[Optional[dict]] = mapped_column(JSON)                # the M9 figures at the time of the review
    repayment: Mapped[str] = mapped_column(String(10), default="none")  # on_time | delayed | default | none
    jobs_family: Mapped[int] = mapped_column(SmallInteger, default=0)
    jobs_hired: Mapped[int] = mapped_column(SmallInteger, default=0)
    health: Mapped[str] = mapped_column(String(6))                     # green | amber | red
    scores: Mapped[dict] = mapped_column(JSON, default=dict)           # records, sales, operations, money: 1–5
    issues: Mapped[list] = mapped_column(JSON, default=list)
    actions: Mapped[list] = mapped_column(JSON, default=list)          # [{text, due, done, done_on}]
    training: Mapped[list] = mapped_column(JSON, default=list)         # refresher | advanced | skill_upgrade
    training_done: Mapped[bool] = mapped_column(default=False)         # staff have acted on the training need
    note: Mapped[Optional[str]] = mapped_column(Text)
    mentor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("field_visits.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    unit: Mapped[Unit] = relationship()


class FieldVisit(Base):
    __tablename__ = "field_visits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    on: Mapped[date] = mapped_column(Date, index=True)
    purpose: Mapped[str] = mapped_column(String(14))                   # review | support | audit | training | other
    notes: Mapped[str] = mapped_column(Text)
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lng: Mapped[Optional[float]] = mapped_column(Float)
    distance_m: Mapped[Optional[float]] = mapped_column(Float)         # from the unit's location, when both are known
    photos: Mapped[list] = mapped_column(JSON, default=list)           # [{name, lat, lng, source: device|exif, at}]
    next_visit: Mapped[Optional[date]] = mapped_column(Date)
    by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    unit: Mapped[Unit] = relationship()


class SupportTicket(Base):
    """Form 10.2 – a problem raised by the entrepreneur, navigator or mentor."""
    __tablename__ = "support_tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(14), index=True)
    description: Mapped[str] = mapped_column(Text)
    photo: Mapped[Optional[str]] = mapped_column(String(120))
    priority: Mapped[str] = mapped_column(String(8), default="medium")  # low | medium | high
    channel: Mapped[str] = mapped_column(String(10), default="app")     # app | call | navigator | mentor | review
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)  # open | in_progress | resolved | closed
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    due_by: Mapped[Optional[date]] = mapped_column(Date)
    resolution: Mapped[Optional[str]] = mapped_column(Text)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger)        # entrepreneur, 1–5
    referrals: Mapped[list] = mapped_column(JSON, default=list)        # [{kind, to, user_id, note, at, by}]
    events: Mapped[list] = mapped_column(JSON, default=list)           # [{at, by, kind, text}]
    raised_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    unit: Mapped[Unit] = relationship()
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])


class GrowthPlan(Base):
    """Form 10.3."""
    __tablename__ = "growth_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    goal: Mapped[str] = mapped_column(String(16))
    target: Mapped[str] = mapped_column(String(255))
    target_date: Mapped[date] = mapped_column(Date)
    support: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(10), default="active")  # active | achieved | dropped
    progress: Mapped[list] = mapped_column(JSON, default=list)         # [{on, text, by}]
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PeerSession(Base):
    """Monthly mentor-led peer cohort session for a training batch."""
    __tablename__ = "peer_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("training_batches.id", ondelete="CASCADE"), index=True)
    on: Mapped[date] = mapped_column(Date)
    topic: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(10), default="in_person")  # in_person | phone | video
    attendees: Mapped[list] = mapped_column(JSON, default=list)        # trainee ids
    notes: Mapped[Optional[str]] = mapped_column(Text)
    mentor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# A unit's mentorship, for scope checks (mentors see the units they mentor).
Unit.mentorship = relationship(Mentorship, uselist=False, viewonly=True)
