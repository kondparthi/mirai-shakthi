"""Phase 1, Sprint 6 tables: daily business management (spec M9).
- Ledger entries (Form 9.1): sales and expenses, with payment mode; credit sales are receivables with a due date
- Stock items and movements for product businesses (low-stock alert)
- Monthly summaries sent to the mentor and programme reports, with rule-based business alerts."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# Used when the enterprise model has no categories of its own.
DEFAULT_CATEGORIES = {
    "sale": [("sales", "Sales", "అమ్మకాలు"), ("service", "Service charges", "సేవా రుసుము"), ("other_income", "Other income", "ఇతర ఆదాయం")],
    "expense": [("raw_material", "Raw material", "ముడి సరుకు"), ("packing", "Packing", "ప్యాకింగ్"), ("fuel", "Fuel / gas / power", "ఇంధనం / గ్యాస్ / కరెంటు"),
                ("transport", "Transport", "రవాణా"), ("wages", "Wages", "కూలీ / జీతం"), ("rent", "Rent / spot fee", "అద్దె"),
                ("repairs", "Repairs", "మరమ్మతులు"), ("other", "Other", "ఇతర")],
}
# Not operating costs: shown apart from profit.
NON_OPERATING = {"loan_emi": ("Loan EMI", "రుణ వాయిదా"), "drawings": ("Taken home", "ఇంటికి తీసుకున్నది"), "equipment": ("New equipment", "కొత్త పరికరాలు")}


class LedgerEntry(Base):
    """Form 9.1 – one sale or expense."""
    __tablename__ = "ledger_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(8))                       # sale | expense
    on: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(30))
    stock_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stock_items.id", ondelete="SET NULL"))
    qty: Mapped[Optional[float]] = mapped_column(Float)
    payment_mode: Mapped[str] = mapped_column(String(8), default="cash")  # cash | upi | credit
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date)             # credit sales: receivable
    collected_on: Mapped[Optional[date]] = mapped_column(Date)
    collected_mode: Mapped[Optional[str]] = mapped_column(String(8))
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), unique=True)
    repayment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("loan_repayments.id", ondelete="SET NULL"))
    photo: Mapped[Optional[str]] = mapped_column(String(120))
    note: Mapped[Optional[str]] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(8), default="manual")   # manual | voice | order | staff
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    customer = relationship("Customer")


class StockItem(Base):
    __tablename__ = "stock_items"
    __table_args__ = (UniqueConstraint("unit_id", "name", name="uq_stock_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    name_te: Mapped[Optional[str]] = mapped_column(String(80))
    measure: Mapped[str] = mapped_column(String(12), default="kg")      # kg, litre, pcs, pack, cylinder
    qty: Mapped[float] = mapped_column(Float, default=0)
    reorder_level: Mapped[float] = mapped_column(Float, default=0)
    cost: Mapped[Optional[float]] = mapped_column(Float)               # last purchase price per measure
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    moves: Mapped[list["StockMove"]] = relationship(back_populates="item", cascade="all, delete-orphan", order_by="StockMove.id.desc()")


class StockMove(Base):
    __tablename__ = "stock_moves"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("stock_items.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(6))                       # in | out | count
    qty: Mapped[float] = mapped_column(Float)                          # in / out amount, or the counted stock
    on: Mapped[date] = mapped_column(Date)
    entry_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ledger_entries.id", ondelete="CASCADE"))
    note: Mapped[Optional[str]] = mapped_column(String(160))
    at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    item: Mapped[StockItem] = relationship(back_populates="moves")


class MonthlySummary(Base):
    """A unit's month, frozen when submitted (by the entrepreneur, or automatically after the month ends). Feeds the
    mentor's monthly review (M10) and programme reports (M13)."""
    __tablename__ = "monthly_summaries"
    __table_args__ = (UniqueConstraint("unit_id", "month", name="uq_unit_month"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)          # YYYY-MM
    sales: Mapped[float] = mapped_column(Float, default=0)
    expenses: Mapped[float] = mapped_column(Float, default=0)
    profit: Mapped[float] = mapped_column(Float, default=0)
    emi_paid: Mapped[float] = mapped_column(Float, default=0)
    drawings: Mapped[float] = mapped_column(Float, default=0)
    receivables: Mapped[float] = mapped_column(Float, default=0)
    entries: Mapped[int] = mapped_column(Integer, default=0)
    days_recorded: Mapped[int] = mapped_column(Integer, default=0)
    emi_status: Mapped[Optional[str]] = mapped_column(String(10))      # on_time | delayed | default | none
    by_category: Mapped[dict] = mapped_column(JSON, default=dict)
    alerts: Mapped[list] = mapped_column(JSON, default=list)            # [{code, level, text}]
    note: Mapped[Optional[str]] = mapped_column(Text)
    submitted_by: Mapped[str] = mapped_column(String(10), default="auto")  # owner (the entrepreneur) | auto | staff
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    review_note: Mapped[Optional[str]] = mapped_column(Text)

    unit = relationship("Unit")
