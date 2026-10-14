"""Application settings, read from environment variables (or a .env file)."""
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    APP_NAME = "MIRAI Shakthi – AI Guidance Assistant"
    ENV = os.getenv("APP_ENV", "development")

    # MySQL connection, e.g. mysql+pymysql://user:pass@localhost:3306/mirai_shakthi?charset=utf8mb4
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://mirai:mirai_dev_pw@localhost:3306/mirai_shakthi?charset=utf8mb4",
    )

    JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
    JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days

    # OTP: in development the code is returned in the API response so testing needs no SMS gateway.
    OTP_DEV_MODE = _bool("OTP_DEV_MODE", True)
    OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "5"))
    SMS_PROVIDER = os.getenv("SMS_PROVIDER", "none")  # none | msg91
    MSG91_AUTH_KEY = os.getenv("MSG91_AUTH_KEY", "")
    MSG91_TEMPLATE_ID = os.getenv("MSG91_TEMPLATE_ID", "")

    # AI provider: "anthropic" uses ANTHROPIC_API_KEY; "none" runs the built-in demo composer (no external calls).
    AI_PROVIDER = os.getenv("AI_PROVIDER", "none")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-5-5")
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "1200"))

    # Public address of the site; used in certificate QR codes and check-in links.
    PUBLIC_URL = os.getenv("PUBLIC_URL", "https://miraimsme.com").rstrip("/")

    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]


settings = Settings()
