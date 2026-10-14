import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

MOBILE_RE = re.compile(r"^[6-9]\d{9}$")

REGISTRATIONS = {"udyam", "gst", "fssai", "trade", "iec", "shop_est"}
CHANNELS = {"local", "wholesale", "online", "government", "export", "interstate"}
FLAGS = {"women_led", "sc_st", "first_gen"}


class OtpRequest(BaseModel):
    mobile: str

    @field_validator("mobile")
    @classmethod
    def check_mobile(cls, v: str) -> str:
        v = re.sub(r"\D", "", v)[-10:]
        if not MOBILE_RE.match(v):
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return v


class OtpVerify(OtpRequest):
    code: str = Field(min_length=4, max_length=6)
    language: Literal["en", "te"] = "en"
    consent: bool = False


class StaffLogin(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    owner_name: str = Field(min_length=2, max_length=120)
    business_name: Optional[str] = Field(default=None, max_length=160)
    stage: Literal["planning", "lt1", "1to3", "gt3"]
    business_type: Literal["manufacturing", "trading", "services"]
    sector: str = Field(min_length=2, max_length=60)
    product: str = Field(min_length=2, max_length=255)
    district: str = Field(min_length=2, max_length=80)
    mandal: Optional[str] = Field(default=None, max_length=80)
    ownership: Literal["proprietor", "partnership", "llp", "company", "shg"]
    turnover_band: int = Field(ge=0, le=5)
    employees: int = Field(ge=0, le=100000)
    registrations: list[str] = []
    channels: list[str] = []
    books_kept: Literal["none", "notebook", "excel", "software"]
    has_loan: Optional[bool] = None
    flags: list[str] = []

    @field_validator("registrations")
    @classmethod
    def v_reg(cls, v):
        bad = set(v) - REGISTRATIONS
        if bad:
            raise ValueError(f"Unknown registrations: {', '.join(sorted(bad))}")
        return sorted(set(v))

    @field_validator("channels")
    @classmethod
    def v_ch(cls, v):
        bad = set(v) - CHANNELS
        if bad:
            raise ValueError(f"Unknown channels: {', '.join(sorted(bad))}")
        return sorted(set(v))

    @field_validator("flags")
    @classmethod
    def v_flags(cls, v):
        bad = set(v) - FLAGS
        if bad:
            raise ValueError(f"Unknown flags: {', '.join(sorted(bad))}")
        return sorted(set(v))


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    session_id: Optional[int] = None
    module: Optional[Literal["microfin", "marketkonnect", "launchpad", "skillspro", "handholding"]] = None
    language: Optional[Literal["en", "te"]] = None


class RateIn(BaseModel):
    rating: Literal[1, -1]


class GapUpdate(BaseModel):
    status: Literal["missing", "done"]
