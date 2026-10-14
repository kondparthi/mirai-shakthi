import logging
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import AuditLog, OtpCode, User
from ..schemas import OtpRequest, OtpVerify, StaffLogin
from ..security import create_token, current_user, hash_secret, verify_secret

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
log = logging.getLogger("mirai.auth")
CONSENT_VERSION = "2026-10"


def _now() -> datetime:
    """Naive UTC time (database columns store UTC without timezone)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _send_sms(mobile: str, code: str) -> None:
    if settings.SMS_PROVIDER == "msg91" and settings.MSG91_AUTH_KEY:
        httpx.post(
            "https://control.msg91.com/api/v5/otp",
            params={"template_id": settings.MSG91_TEMPLATE_ID, "mobile": f"91{mobile}", "otp": code},
            headers={"authkey": settings.MSG91_AUTH_KEY},
            timeout=10,
        ).raise_for_status()
    else:
        log.info("OTP for %s: %s (SMS provider not configured)", mobile, code)


def _user_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "mobile": u.mobile, "email": u.email, "role": u.role,
            "language": u.language, "has_profile": u.profile is not None, "scope": u.scope or {}}


def issue_otp(db: Session, mobile: str) -> dict:
    """Create and send a one-time code. Also used for assisted enrolment (the entrepreneur's OTP is their consent)."""
    since = _now() - timedelta(minutes=15)
    recent = db.scalar(select(func.count()).select_from(OtpCode).where(OtpCode.mobile == mobile, OtpCode.created_at >= since))
    if recent >= 5:
        raise HTTPException(429, "Too many OTP requests. Please try again after 15 minutes.")
    code = f"{secrets.randbelow(10**6):06d}"
    db.add(OtpCode(mobile=mobile, code_hash=hash_secret(code), created_at=_now(),
                   expires_at=_now() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)))
    db.commit()
    _send_sms(mobile, code)
    out = {"sent": True, "expires_in_minutes": settings.OTP_EXPIRE_MINUTES}
    if settings.OTP_DEV_MODE:
        out["dev_code"] = code  # development only – never enable in production
    return out


def check_otp(db: Session, mobile: str, code: str) -> None:
    """Raise 400 unless `code` is the latest unused OTP for `mobile`; marks it used."""
    otp = db.scalar(select(OtpCode).where(OtpCode.mobile == mobile, OtpCode.used.is_(False))
                    .order_by(OtpCode.id.desc()).limit(1))
    if not otp or otp.expires_at < _now():
        raise HTTPException(400, "OTP expired. Please request a new one.")
    if otp.attempts >= 5:
        raise HTTPException(400, "Too many wrong attempts. Please request a new OTP.")
    if not verify_secret(code, otp.code_hash):
        otp.attempts += 1
        db.commit()
        raise HTTPException(400, "Wrong OTP. Please check and try again.")
    otp.used = True


@router.post("/otp/request")
def request_otp(body: OtpRequest, db: Session = Depends(get_db)):
    return issue_otp(db, body.mobile)


@router.post("/otp/verify")
def verify_otp(body: OtpVerify, db: Session = Depends(get_db)):
    check_otp(db, body.mobile, body.code)
    user = db.scalar(select(User).where(User.mobile == body.mobile))
    if not user:
        if not body.consent:
            db.commit()
            raise HTTPException(400, "Please accept the terms and data consent to continue.")
        user = User(mobile=body.mobile, role="msme", language=body.language,
                    consent_version=CONSENT_VERSION, consent_at=_now())
        db.add(user)
        db.flush()
        db.add(AuditLog(user_id=user.id, action="register", entity="user", entity_id=user.id,
                        detail={"consent_version": CONSENT_VERSION}))
    else:
        user.language = body.language
    db.commit()
    db.refresh(user)
    return {"token": create_token(user), "user": _user_out(user)}


@router.post("/staff/login")
def staff_login(body: StaffLogin, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not user or not user.password_hash or not verify_secret(body.password, user.password_hash) or user.role == "msme":
        raise HTTPException(401, "Wrong email or password")
    return {"token": create_token(user), "user": _user_out(user)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _user_out(user)
