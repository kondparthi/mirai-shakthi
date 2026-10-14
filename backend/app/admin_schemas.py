"""Input models for the admin portal (Sprint 2)."""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .guidance.rules import validate as validate_condition

Module = Literal["microfin", "marketkonnect", "launchpad", "skillspro", "handholding"]
SERVICES = [
    "registration_filing", "gst_filing", "export_facilitation", "ecommerce_onboarding", "gem_onboarding",
    "marketing_support", "sector_advice", "accounting", "loan_application", "legal_recovery", "hr_support",
    "training", "dpr_preparation", "general_advice",
]


class KbIn(BaseModel):
    """Form G-8 – Knowledge content."""
    title: str = Field(min_length=3, max_length=255)
    module: Module
    intent_code: Optional[str] = Field(default=None, max_length=60)
    language: Literal["en", "te"] = "en"
    body: str = Field(min_length=20, max_length=20000)
    source_url: Optional[str] = Field(default=None, max_length=300)
    verified_by: Optional[str] = Field(default=None, max_length=120)
    verified_on: Optional[date] = None
    review_due: Optional[date] = None
    status: Literal["draft", "published", "archived"] = "draft"

    @field_validator("source_url")
    @classmethod
    def v_url(cls, v):
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Source URL must start with http:// or https://")
        return v or None

    @field_validator("intent_code")
    @classmethod
    def v_intent(cls, v):
        return v or None


class IntentIn(BaseModel):
    code: str = Field(min_length=3, max_length=60, pattern=r"^[a-z0-9_]+$")
    module: Module
    title_en: str = Field(min_length=3, max_length=160)
    title_te: Optional[str] = Field(default=None, max_length=160)
    description: Optional[str] = Field(default=None, max_length=500)
    keywords: list[str] = []
    sample_questions: list[str] = []
    connect_service: Optional[str] = None
    active: bool = True

    @field_validator("keywords", "sample_questions")
    @classmethod
    def v_list(cls, v):
        return [s.strip() for s in v if s and s.strip()]

    @field_validator("connect_service")
    @classmethod
    def v_service(cls, v):
        if v and v not in SERVICES:
            raise ValueError(f"Unknown service: {v}")
        return v or None


class RuleIn(BaseModel):
    """Admin screen A2 – one requirement item for a topic."""
    item_code: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9_]+$")
    title_en: str = Field(min_length=3, max_length=200)
    title_te: Optional[str] = Field(default=None, max_length=200)
    why_en: Optional[str] = Field(default=None, max_length=2000)
    why_te: Optional[str] = Field(default=None, max_length=2000)
    condition: Optional[dict] = None
    have_check: Optional[dict] = None
    step_order: int = Field(default=10, ge=0, le=999)
    documents: Optional[str] = Field(default=None, max_length=500)
    time_estimate: Optional[str] = Field(default=None, max_length=80)
    cost_note: Optional[str] = Field(default=None, max_length=160)
    official_link: Optional[str] = Field(default=None, max_length=300)
    active: bool = True

    @field_validator("condition", "have_check")
    @classmethod
    def v_cond(cls, v):
        if not v:
            return None
        validate_condition(v)
        return v

    @field_validator("official_link")
    @classmethod
    def v_link(cls, v):
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Official link must start with http:// or https://")
        return v or None


class ExpertIn(BaseModel):
    """Form G-7 – Expert / institution directory."""
    name: str = Field(min_length=2, max_length=160)
    organisation: Optional[str] = Field(default=None, max_length=160)
    expert_type: Literal["ca", "cs", "bdsp", "bank", "nbfc", "specialist", "govt", "trainer"]
    services: list[str] = Field(min_length=1)
    reg_no: Optional[str] = Field(default=None, max_length=60)
    districts: list[str] = Field(min_length=1)
    languages: list[Literal["en", "te"]] = Field(min_length=1)
    fee_note: Optional[str] = Field(default=None, max_length=160)
    response_hours: int = Field(default=48, ge=1, le=720)
    status: Literal["pending", "approved", "suspended"] = "pending"

    @field_validator("services")
    @classmethod
    def v_services(cls, v):
        bad = set(v) - set(SERVICES)
        if bad:
            raise ValueError(f"Unknown services: {', '.join(sorted(bad))}")
        return v


class ReviewIn(BaseModel):
    action: Literal["resolved", "content_added", "no_action"]
    note: Optional[str] = Field(default=None, max_length=1000)


class ExpertLoginIn(BaseModel):
    email: str = Field(min_length=5, max_length=190, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=72)


class ReassignIn(BaseModel):
    expert_id: int
    note: Optional[str] = Field(default=None, max_length=500)


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
