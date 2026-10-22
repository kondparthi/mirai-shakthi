"""Phase 1, Sprint 3 tables: DPR & finance.
- Enterprise model master (Form 3.1, the fields the DPR template needs)
- Scheme library (M6) with structured eligibility rules
- DPR builder (M5, Form 5.1) with version history
- Credit / scheme applications (Forms 6.1, 6.2), their history and the EMI repayment schedule."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ACTIVITIES = {"manufacturing": "Manufacturing / processing", "service": "Service", "trading": "Trading", "agri_allied": "Agri-allied"}
DPR_STATUS = ("draft", "reviewed", "approved")
LOAN_STATUS = {
    "draft": ("Draft", "డ్రాఫ్ట్"),
    "submitted": ("Submitted", "సమర్పించారు"),
    "query": ("Bank query", "బ్యాంకు ప్రశ్న"),
    "sanctioned": ("Sanctioned", "మంజూరైంది"),
    "disbursed": ("Disbursed", "రుణం విడుదలైంది"),
    "rejected": ("Rejected", "తిరస్కరించారు"),
    "withdrawn": ("Withdrawn", "ఉపసంహరించారు"),
}
# Allowed moves in the status flow (Draft → Submitted → Bank query → Sanctioned → Disbursed / Rejected).
LOAN_FLOW = {
    "draft": ("submitted", "withdrawn"),
    "submitted": ("query", "sanctioned", "rejected", "withdrawn"),
    "query": ("submitted", "sanctioned", "rejected", "withdrawn"),
    "sanctioned": ("disbursed", "withdrawn"),
    "disbursed": (),
    "rejected": (),
    "withdrawn": (),
}


class EnterpriseModel(Base):
    """Form 3.1 – an enterprise model and its DPR template (equipment, sales and expense defaults)."""
    __tablename__ = "enterprise_models"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    sector: Mapped[str] = mapped_column(String(40), index=True)
    name_en: Mapped[str] = mapped_column(String(160))
    name_te: Mapped[Optional[str]] = mapped_column(String(160))
    description: Mapped[Optional[str]] = mapped_column(Text)
    activity: Mapped[str] = mapped_column(String(14), default="service")   # manufacturing | service | trading | agri_allied
    context_tags: Mapped[list] = mapped_column(JSON, default=list)
    investment_min: Mapped[Optional[float]] = mapped_column(Float)
    investment_max: Mapped[Optional[float]] = mapped_column(Float)
    working_capital: Mapped[float] = mapped_column(Float, default=0)
    equipment: Mapped[list] = mapped_column(JSON, default=list)      # [{item, spec, qty, rate, suppliers}]
    infrastructure: Mapped[list] = mapped_column(JSON, default=list)  # space, power, water, licences
    skills: Mapped[list] = mapped_column(JSON, default=list)
    schemes: Mapped[list] = mapped_column(JSON, default=list)         # scheme codes this model can use
    sales_template: Mapped[dict] = mapped_column(JSON, default=dict)    # {items:[{name, unit, units_per_day, price}], working_days, ...}
    expense_template: Mapped[dict] = mapped_column(JSON, default=dict)  # {raw_material_pct, salaries, rent, fuel, maintenance, other}
    # Sprint 4 (M7): registrations the unit needs and model-specific readiness items (Form 7.3). Nullable: added to an existing table.
    registrations: Mapped[Optional[list]] = mapped_column(JSON)       # codes from models_p4.REGISTRATIONS
    readiness_items: Mapped[Optional[list]] = mapped_column(JSON)     # extra checklist items, e.g. "Branding done"
    # Sprint 6 (M9): bookkeeping categories {sale: [{code, label, label_te}], expense: [...]} and starter stock items.
    ledger_categories: Mapped[Optional[dict]] = mapped_column(JSON)
    stock_template: Mapped[Optional[list]] = mapped_column(JSON)      # [{name, name_te, measure, reorder_level}]
    expected_monthly_sales: Mapped[Optional[float]] = mapped_column(Float)
    jobs: Mapped[Optional[int]] = mapped_column(SmallInteger)
    payback_months: Mapped[Optional[int]] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(12), default="catalogue")  # catalogue | pilot | active
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Scheme(Base):
    """M6 scheme library. Eligibility is checked with these rules only (no AI)."""
    __tablename__ = "schemes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    name_te: Mapped[Optional[str]] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(10), default="central")   # central | state | bank | csr
    agency: Mapped[Optional[str]] = mapped_column(String(160))
    description: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(String(255))
    rules: Mapped[dict] = mapped_column(JSON, default=dict)            # see app/dpr/schemes.py for the keys
    documents: Mapped[list] = mapped_column(JSON, default=list)        # [{code, label, when}]
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    verified_on: Mapped[Optional[date]] = mapped_column(Date)
    sample: Mapped[bool] = mapped_column(Boolean, default=True)        # starter data MIRAI must verify
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Dpr(Base):
    """Form 5.1 – a Detailed Project Report. Inputs are stored as entered; all figures are calculated by app/dpr/finance.py."""
    __tablename__ = "dprs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    entrepreneur_id: Mapped[Optional[int]] = mapped_column(ForeignKey("entrepreneurs.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[Optional[int]] = mapped_column(ForeignKey("enterprise_models.id", ondelete="SET NULL"))
    unit_name: Mapped[str] = mapped_column(String(160))
    district: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    mandal: Mapped[Optional[str]] = mapped_column(String(80))
    village: Mapped[Optional[str]] = mapped_column(String(120))
    address: Mapped[Optional[str]] = mapped_column(String(255))
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lng: Mapped[Optional[float]] = mapped_column(Float)
    activity: Mapped[str] = mapped_column(String(14), default="service")
    scheme_code: Mapped[Optional[str]] = mapped_column(String(30))
    inputs: Mapped[dict] = mapped_column(JSON)
    narrative: Mapped[dict] = mapped_column(JSON, default=dict)        # section -> text
    narrative_notes: Mapped[dict] = mapped_column(JSON, default=dict)  # officer's notes the AI drafts from
    narrative_source: Mapped[Optional[str]] = mapped_column(String(10))  # ai | template | staff
    results: Mapped[Optional[dict]] = mapped_column(JSON)              # cached headline figures for lists and reports
    status: Mapped[str] = mapped_column(String(10), default="draft")   # draft | reviewed | approved
    version: Mapped[int] = mapped_column(SmallInteger, default=1)
    prepared_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    model: Mapped[Optional[EnterpriseModel]] = relationship()
    entrepreneur = relationship("Entrepreneur")
    group = relationship("EGroup")
    versions: Mapped[list["DprVersion"]] = relationship(back_populates="dpr", cascade="all, delete-orphan", order_by="DprVersion.id.desc()")


class DprVersion(Base):
    """A frozen copy of a DPR, saved when it is reviewed, approved or reopened."""
    __tablename__ = "dpr_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dpr_id: Mapped[int] = mapped_column(ForeignKey("dprs.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(10))
    snapshot: Mapped[dict] = mapped_column(JSON)
    note: Mapped[Optional[str]] = mapped_column(String(255))
    saved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    dpr: Mapped[Dpr] = relationship(back_populates="versions")


class LoanApplication(Base):
    """Form 6.1 / 6.2 – a credit or scheme application made from an approved DPR."""
    __tablename__ = "loan_applications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    dpr_id: Mapped[int] = mapped_column(ForeignKey("dprs.id", ondelete="CASCADE"), index=True)
    dpr_version: Mapped[int] = mapped_column(SmallInteger, default=1)
    entrepreneur_id: Mapped[Optional[int]] = mapped_column(ForeignKey("entrepreneurs.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    district: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    scheme_code: Mapped[Optional[str]] = mapped_column(String(30))
    bank: Mapped[str] = mapped_column(String(40))                     # bank master code
    branch: Mapped[str] = mapped_column(String(160))
    ifsc: Mapped[Optional[str]] = mapped_column(String(11))
    amount_requested: Mapped[float] = mapped_column(Float)
    app_number: Mapped[Optional[str]] = mapped_column(String(60))
    portal: Mapped[Optional[str]] = mapped_column(String(80))
    submitted_on: Mapped[Optional[date]] = mapped_column(Date)
    documents: Mapped[list] = mapped_column(JSON, default=list)       # [{code, label, have, file, note}]
    status: Mapped[str] = mapped_column(String(10), default="draft")
    sanctioned_amount: Mapped[Optional[float]] = mapped_column(Float)
    subsidy_amount: Mapped[Optional[float]] = mapped_column(Float)
    sanctioned_on: Mapped[Optional[date]] = mapped_column(Date)
    disbursed_on: Mapped[Optional[date]] = mapped_column(Date)
    disbursed_amount: Mapped[Optional[float]] = mapped_column(Float)
    interest_pct: Mapped[Optional[float]] = mapped_column(Float)
    emi_amount: Mapped[Optional[float]] = mapped_column(Float)
    tenure_months: Mapped[Optional[int]] = mapped_column(SmallInteger)
    first_emi_date: Mapped[Optional[date]] = mapped_column(Date)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(40))
    rejection_note: Mapped[Optional[str]] = mapped_column(String(255))
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    dpr: Mapped[Dpr] = relationship()
    entrepreneur = relationship("Entrepreneur")
    group = relationship("EGroup")
    events: Mapped[list["LoanEvent"]] = relationship(back_populates="application", cascade="all, delete-orphan", order_by="LoanEvent.id")
    repayments: Mapped[list["Repayment"]] = relationship(back_populates="application", cascade="all, delete-orphan", order_by="Repayment.n")


class LoanEvent(Base):
    """History of an application: status changes, bank queries and responses, notes."""
    __tablename__ = "loan_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))                     # status | query | response | note
    status: Mapped[Optional[str]] = mapped_column(String(10))
    text: Mapped[Optional[str]] = mapped_column(Text)
    on: Mapped[Optional[date]] = mapped_column(Date)
    by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    application: Mapped[LoanApplication] = relationship(back_populates="events")


class Repayment(Base):
    """One EMI in the repayment schedule, created at disbursement."""
    __tablename__ = "loan_repayments"
    __table_args__ = (UniqueConstraint("application_id", "n", name="uq_repayment_n"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id", ondelete="CASCADE"), index=True)
    n: Mapped[int] = mapped_column(SmallInteger)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Float)
    principal: Mapped[float] = mapped_column(Float)
    interest: Mapped[float] = mapped_column(Float)
    balance: Mapped[float] = mapped_column(Float)
    paid_amount: Mapped[Optional[float]] = mapped_column(Float)
    paid_on: Mapped[Optional[date]] = mapped_column(Date)
    note: Mapped[Optional[str]] = mapped_column(String(160))

    application: Mapped[LoanApplication] = relationship(back_populates="repayments")
