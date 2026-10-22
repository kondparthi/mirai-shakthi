"""Phase 1, Sprint 4 tables: enterprise establishment & procurement (spec M7).
- Unit: the enterprise being set up (from an approved DPR), with its readiness checklist (Form 7.3) and launch
- Supplier register (Form 7.1) with rate card; a supplier may have a limited portal login
- Purchase (Form 7.2): request for quotation → quotations → selection → purchase order → delivery → installation
- Asset register and registrations (Udyam, GST, FSSAI, trade licence, drone UIN / RPC)."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

REGISTRATIONS = {
    "udyam": ("Udyam registration", "ఉద్యమ్ నమోదు"),
    "gst": ("GST registration", "జీఎస్‌టీ నమోదు"),
    "fssai": ("FSSAI registration / licence", "ఎఫ్‌ఎస్‌ఎస్‌ఏఐ నమోదు"),
    "trade_licence": ("Trade licence / spot permission", "ట్రేడ్ లైసెన్స్ / స్థల అనుమతి"),
    "drone_uin": ("Drone UIN (Digital Sky)", "డ్రోన్ యూఐఎన్ (డిజిటల్ స్కై)"),
    "rpc": ("DGCA Remote Pilot Certificate", "డీజీసీఏ రిమోట్ పైలట్ సర్టిఫికేట్"),
    "drone_insurance": ("Drone insurance", "డ్రోన్ బీమా"),
    "other": ("Other", "ఇతర"),
}
PURCHASE_STATUS = {
    "draft": "Draft", "rfq": "Quotations asked", "ordered": "Order placed", "delivered": "Delivered", "installed": "Installed",
    "cancelled": "Cancelled",
}
PAYMENT_SOURCES = {"loan": "Loan disbursement", "own": "Own funds", "grant": "Grant", "subsidy": "Subsidy", "mixed": "Loan + own funds"}


class Supplier(Base):
    """Form 7.1 – supplier register."""
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(15))
    contact_name: Mapped[str] = mapped_column(String(120))
    mobile: Mapped[str] = mapped_column(String(15))
    email: Mapped[Optional[str]] = mapped_column(String(190))
    address: Mapped[str] = mapped_column(String(255))
    categories: Mapped[list] = mapped_column(JSON, default=list)      # e.g. "Food carts", "Drones"
    items: Mapped[list] = mapped_column(JSON, default=list)           # item names, matched with model equipment lists
    models: Mapped[list] = mapped_column(JSON, default=list)          # enterprise model codes
    rate_card: Mapped[list] = mapped_column(JSON, default=list)       # [{item, rate, unit, valid_till}]
    districts: Mapped[list] = mapped_column(JSON, default=list)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), unique=True)
    note: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Unit(Base):
    """The enterprise being set up and run. Created from an approved DPR; launched when the readiness checklist is complete."""
    __tablename__ = "units"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    entrepreneur_id: Mapped[Optional[int]] = mapped_column(ForeignKey("entrepreneurs.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    dpr_id: Mapped[Optional[int]] = mapped_column(ForeignKey("dprs.id", ondelete="SET NULL"), unique=True)
    model_id: Mapped[Optional[int]] = mapped_column(ForeignKey("enterprise_models.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160))
    district: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    mandal: Mapped[Optional[str]] = mapped_column(String(80))
    village: Mapped[Optional[str]] = mapped_column(String(120))
    address: Mapped[Optional[str]] = mapped_column(String(255))
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lng: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(12), default="setting_up")  # setting_up | launched | paused | closed
    readiness: Mapped[dict] = mapped_column(JSON, default=dict)            # manual items: key -> {done, note, photo, by, at}
    launch_date: Mapped[Optional[date]] = mapped_column(Date)
    launched_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    entrepreneur = relationship("Entrepreneur")
    group = relationship("EGroup")
    dpr = relationship("Dpr")
    model = relationship("EnterpriseModel")
    purchases: Mapped[list["Purchase"]] = relationship(back_populates="unit", cascade="all, delete-orphan", order_by="Purchase.id")
    assets: Mapped[list["Asset"]] = relationship(back_populates="unit", cascade="all, delete-orphan", order_by="Asset.id")
    registrations: Mapped[list["Registration"]] = relationship(back_populates="unit", cascade="all, delete-orphan", order_by="Registration.id")


class Purchase(Base):
    """Form 7.2 – one purchase for a unit: items, quotations, selection, purchase order, delivery and installation."""
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    items: Mapped[list] = mapped_column(JSON)                          # [{item, spec, qty, est_rate}]
    invited: Mapped[list] = mapped_column(JSON, default=list)          # supplier ids asked to quote
    quote_by: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="draft")
    selected_quote_id: Mapped[Optional[int]] = mapped_column(Integer)
    selection_reason: Mapped[Optional[str]] = mapped_column(String(500))
    po_number: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    po_date: Mapped[Optional[date]] = mapped_column(Date)
    po_amount: Mapped[Optional[float]] = mapped_column(Float)
    payment_source: Mapped[Optional[str]] = mapped_column(String(10))
    expected_delivery: Mapped[Optional[date]] = mapped_column(Date)
    supplier_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    delivered_on: Mapped[Optional[date]] = mapped_column(Date)
    installed_on: Mapped[Optional[date]] = mapped_column(Date)
    handover_note: Mapped[Optional[str]] = mapped_column(Text)
    photos: Mapped[list] = mapped_column(JSON, default=list)           # [{file, caption, at}]
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    unit: Mapped[Unit] = relationship(back_populates="purchases")
    quotes: Mapped[list["Quotation"]] = relationship(back_populates="purchase", cascade="all, delete-orphan", order_by="Quotation.amount")


class Quotation(Base):
    __tablename__ = "quotations"
    __table_args__ = (UniqueConstraint("purchase_id", "supplier_id", name="uq_quote_supplier"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), index=True)
    lines: Mapped[list] = mapped_column(JSON)                          # [{item, qty, rate}]
    amount: Mapped[float] = mapped_column(Float)                       # total incl. GST
    gst_included: Mapped[bool] = mapped_column(Boolean, default=True)
    delivery_days: Mapped[Optional[int]] = mapped_column(SmallInteger)
    warranty_months: Mapped[Optional[int]] = mapped_column(SmallInteger)
    valid_till: Mapped[Optional[date]] = mapped_column(Date)
    file: Mapped[Optional[str]] = mapped_column(String(120))
    note: Mapped[Optional[str]] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(10), default="staff")   # staff | supplier
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    purchase: Mapped[Purchase] = relationship(back_populates="quotes")
    supplier: Mapped[Supplier] = relationship()


class Asset(Base):
    """Asset register per unit (serial numbers, warranty, insurance); group units hold shared assets."""
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    purchase_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchases.id", ondelete="SET NULL"))
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"))
    item: Mapped[str] = mapped_column(String(160))
    spec: Mapped[Optional[str]] = mapped_column(String(200))
    qty: Mapped[float] = mapped_column(Float, default=1)
    value: Mapped[float] = mapped_column(Float, default=0)
    serial_no: Mapped[Optional[str]] = mapped_column(String(80))
    warranty_until: Mapped[Optional[date]] = mapped_column(Date)
    insurance_policy: Mapped[Optional[str]] = mapped_column(String(80))
    insurance_until: Mapped[Optional[date]] = mapped_column(Date)
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    photo: Mapped[Optional[str]] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(10), default="working")  # working | repair | disposed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    unit: Mapped[Unit] = relationship(back_populates="assets")


class Registration(Base):
    __tablename__ = "unit_registrations"
    __table_args__ = (UniqueConstraint("unit_id", "kind", name="uq_unit_registration"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(10), default="todo")    # todo | applied | done | not_needed
    number: Mapped[Optional[str]] = mapped_column(String(60))
    applied_on: Mapped[Optional[date]] = mapped_column(Date)
    issued_on: Mapped[Optional[date]] = mapped_column(Date)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    file: Mapped[Optional[str]] = mapped_column(String(120))
    note: Mapped[Optional[str]] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    unit: Mapped[Unit] = relationship(back_populates="registrations")
