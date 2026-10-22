"""Phase 1, Sprint 5 tables: marketing, sales & orders (spec M8).
- Customer profiles, kept apart from entrepreneur profiles (spec 2.2)
- Product / service listings per unit with availability and booking slots (Form 8.1)
- Orders and bookings (Form 8.2), with status history, payment and customer rating
- Buyer enquiries from institutions and market partners, routed to units
- Marketing campaigns across units (Form 8.3) and promotional materials (AI-assisted posters and messages)
- Repeat-customer follow-ups."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ORDER_STATUS = {
    "new": ("New", "కొత్తది"), "confirmed": ("Confirmed", "నిర్ధారించారు"), "delivered": ("Delivered", "అందించారు"),
    "paid": ("Paid", "చెల్లించారు"), "cancelled": ("Cancelled", "రద్దు"),
}
ORDER_FLOW = {"new": ("confirmed", "delivered", "paid", "cancelled"), "confirmed": ("delivered", "paid", "cancelled"),
              "delivered": ("paid", "cancelled"), "paid": (), "cancelled": ()}
CUSTOMER_KINDS = {"household": "Household", "shop": "Shop / retailer", "institution": "Institution (school, office, hostel)",
                  "farmer": "Farmer", "event": "Event / caterer", "other": "Other"}
CHANNELS = {"fair": "Fair / mela", "whatsapp": "WhatsApp", "social": "Social media", "institutional": "Institutional buyers"}


class Customer(Base):
    """A person or business buying from units. One profile per mobile, shared by all units they buy from."""
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mobile: Mapped[str] = mapped_column(String(15), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(12), default="household")
    organisation: Mapped[Optional[str]] = mapped_column(String(160))
    village: Mapped[Optional[str]] = mapped_column(String(120))
    district: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Listing(Base):
    """Form 8.1 – a product or service a unit sells."""
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(8), default="product")      # product | service
    name: Mapped[str] = mapped_column(String(120))
    name_te: Mapped[Optional[str]] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(String(500))
    photos: Mapped[list] = mapped_column(JSON, default=list)             # file names (max 3)
    price: Mapped[float] = mapped_column(Float)
    price_unit: Mapped[str] = mapped_column(String(20), default="each")   # each, plate, kg, litre, acre, hour, day, pack
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_capacity: Mapped[Optional[float]] = mapped_column(Float)        # e.g. 20 acres a day; None = no limit
    slots: Mapped[list] = mapped_column(JSON, default=list)              # services: [{label, capacity}]
    sort: Mapped[int] = mapped_column(SmallInteger, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Campaign(Base):
    """Form 8.3 – a collective marketing campaign across units."""
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    sectors: Mapped[list] = mapped_column(JSON, default=list)
    unit_ids: Mapped[list] = mapped_column(JSON, default=list)
    channels: Mapped[list] = mapped_column(JSON, default=list)
    venue: Mapped[Optional[str]] = mapped_column(String(200))
    district: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    budget: Mapped[Optional[float]] = mapped_column(Float)
    message_en: Mapped[Optional[str]] = mapped_column(Text)
    message_te: Mapped[Optional[str]] = mapped_column(Text)
    materials: Mapped[list] = mapped_column(JSON, default=list)          # [{file, title, kind, at}]
    enquiries: Mapped[Optional[int]] = mapped_column(Integer)           # results entered by staff (fairs, calls)
    manual_orders: Mapped[Optional[int]] = mapped_column(Integer)
    manual_sales: Mapped[Optional[float]] = mapped_column(Float)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Enquiry(Base):
    """A buyer enquiry from an institution or market partner, routed to one or more units."""
    __tablename__ = "enquiries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    need: Mapped[str] = mapped_column(Text)
    sector: Mapped[Optional[str]] = mapped_column(String(40))
    model_code: Mapped[Optional[str]] = mapped_column(String(40))
    district: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    quantity: Mapped[Optional[str]] = mapped_column(String(120))
    needed_by: Mapped[Optional[date]] = mapped_column(Date)
    budget: Mapped[Optional[float]] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(12), default="call")      # call | visit | campaign | partner | online
    campaign_id: Mapped[Optional[int]] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(10), default="open")     # open | routed | won | lost | closed
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    customer: Mapped[Customer] = relationship()
    routes: Mapped[list["EnquiryRoute"]] = relationship(back_populates="enquiry", cascade="all, delete-orphan", order_by="EnquiryRoute.id")


class EnquiryRoute(Base):
    """An enquiry sent to one unit, and the unit's answer."""
    __tablename__ = "enquiry_routes"
    __table_args__ = (UniqueConstraint("enquiry_id", "unit_id", name="uq_enquiry_unit"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enquiry_id: Mapped[int] = mapped_column(ForeignKey("enquiries.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="sent")     # sent | interested | declined | won | lost
    quote_amount: Mapped[Optional[float]] = mapped_column(Float)
    reply: Mapped[Optional[str]] = mapped_column(String(500))
    replied_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    enquiry: Mapped[Enquiry] = relationship(back_populates="routes")
    unit = relationship("Unit")


class Order(Base):
    """Form 8.2 – an order (products) or booking (service, with date and slot)."""
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(8), default="order")        # order | booking
    lines: Mapped[list] = mapped_column(JSON)                            # [{listing_id, name, qty, price, unit}]
    amount: Mapped[float] = mapped_column(Float)
    date: Mapped[Optional[date]] = mapped_column(Date, index=True)       # delivery or booking date
    slot: Mapped[Optional[str]] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(10), default="new", index=True)
    payment_mode: Mapped[Optional[str]] = mapped_column(String(8))       # cash | upi | credit
    paid_on: Mapped[Optional[date]] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(10), default="unit")      # unit | staff | online | enquiry | campaign
    campaign_id: Mapped[Optional[int]] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"), index=True)
    enquiry_route_id: Mapped[Optional[int]] = mapped_column(ForeignKey("enquiry_routes.id", ondelete="SET NULL"))
    address: Mapped[Optional[str]] = mapped_column(String(255))
    note: Mapped[Optional[str]] = mapped_column(String(500))
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(255))
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger)
    rating_comment: Mapped[Optional[str]] = mapped_column(String(500))
    track_token: Mapped[Optional[str]] = mapped_column(String(24))
    events: Mapped[list] = mapped_column(JSON, default=list)            # [{status, at, by}]
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    customer: Mapped[Customer] = relationship()
    unit = relationship("Unit")


class FollowUpNote(Base):
    """A repeat-customer follow-up done by the unit (call / WhatsApp)."""
    __tablename__ = "customer_followups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    note: Mapped[Optional[str]] = mapped_column(String(255))
    at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Material(Base):
    """A promotional poster or message made for a unit or a campaign."""
    __tablename__ = "promo_materials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[Optional[int]] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    lang: Mapped[str] = mapped_column(String(2), default="te")
    title: Mapped[str] = mapped_column(String(160))
    tagline: Mapped[Optional[str]] = mapped_column(String(255))
    message: Mapped[Optional[str]] = mapped_column(Text)
    file: Mapped[Optional[str]] = mapped_column(String(120))            # poster PNG
    source: Mapped[str] = mapped_column(String(10), default="template")  # ai | template
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
