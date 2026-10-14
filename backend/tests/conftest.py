"""Tests run against a separate MySQL database (TEST_DATABASE_URL), recreated for each test session."""
import os

TEST_DB = os.getenv("TEST_DATABASE_URL",
                    "mysql+pymysql://mirai:mirai_dev_pw@localhost:3306/mirai_test?charset=utf8mb4")
os.environ["DATABASE_URL"] = TEST_DB
os.environ["AI_PROVIDER"] = "none"
os.environ["OTP_DEV_MODE"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from seed.seed import main as seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _db():
    seed(reset=True)
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def login(client, mobile="9876543210", consent=True):
    r = client.post("/api/v1/auth/otp/request", json={"mobile": mobile})
    assert r.status_code == 200, r.text
    code = r.json()["dev_code"]
    r = client.post("/api/v1/auth/otp/verify", json={"mobile": mobile, "code": code, "consent": consent})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


PROFILE = {
    "owner_name": "Lakshmi", "business_name": "Lakshmi Millet Snacks", "stage": "1to3",
    "business_type": "manufacturing", "sector": "Food", "product": "Millet snacks", "district": "Guntur",
    "ownership": "proprietor", "turnover_band": 1, "employees": 3, "registrations": [],
    "channels": ["local"], "books_kept": "notebook", "flags": ["women_led"],
}
