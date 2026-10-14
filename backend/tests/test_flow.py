from app.guidance.llm import mask_pii
from app.guidance.rules import evaluate

from .conftest import PROFILE, login


def test_health(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_otp_validation_and_consent(client):
    assert client.post("/api/v1/auth/otp/request", json={"mobile": "12345"}).status_code == 422
    r = client.post("/api/v1/auth/otp/request", json={"mobile": "9000000001"})
    code = r.json()["dev_code"]
    wrong = "000000" if code != "000000" else "111111"
    assert client.post("/api/v1/auth/otp/verify", json={"mobile": "9000000001", "code": wrong, "consent": True}).status_code == 400
    # New users must give consent
    assert client.post("/api/v1/auth/otp/verify", json={"mobile": "9000000001", "code": code, "consent": False}).status_code == 400


def test_staff_login(client):
    assert client.post("/api/v1/auth/staff/login", json={"email": "admin@mirai.local", "password": "bad"}).status_code == 401
    r = client.post("/api/v1/auth/staff/login", json={"email": "admin@mirai.local", "password": "ChangeMe@123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "admin"


def test_profile_required_before_guidance(client):
    h = login(client, "9000000002")
    r = client.post("/api/v1/guidance/ask", json={"question": "Which registrations do I need?"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["current_step"] == 1 and body["understanding"]["missing_profile_fields"]


def test_full_five_step_flow(client):
    h = login(client)
    assert client.put("/api/v1/profile", json=PROFILE, headers=h).status_code == 200

    r = client.post("/api/v1/guidance/ask", headers=h,
                    json={"question": "I make millet snacks. I want to sell on Amazon. What do I need?"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["current_step"] == 5
    assert b["understanding"]["intent_code"] == "sell_online"
    missing = {m["code"] for m in b["identification"]["missing"]}
    assert {"udyam", "gst", "fssai", "label"} <= missing  # food business, nothing registered yet
    assert b["information"]["grounded"] and b["information"]["sources"]
    assert [s["n"] for s in b["guidance"]["steps"]] == list(range(1, len(b["guidance"]["steps"]) + 1))
    assert b["connect"]["experts"], "experts should be matched for Guntur"

    # Session is saved with gaps; user can tick a step done
    sid = b["session_id"]
    s = client.get(f"/api/v1/guidance/sessions/{sid}", headers=h).json()
    assert len(s["messages"]) == 2 and any(g["code"] == "udyam" for g in s["gaps"])
    assert client.patch(f"/api/v1/guidance/sessions/{sid}/gaps/udyam", json={"status": "done"}, headers=h).status_code == 200
    assert client.post(f"/api/v1/guidance/messages/{b['message_id']}/rate", json={"rating": 1}, headers=h).status_code == 200


def test_registered_items_move_to_have(client):
    h = login(client, "9000000003")
    client.put("/api/v1/profile", json={**PROFILE, "registrations": ["udyam", "fssai"]}, headers=h)
    b = client.post("/api/v1/guidance/ask", json={"question": "Which registrations do I need?"}, headers=h).json()
    have = {m["code"] for m in b["identification"]["have"]}
    missing = {m["code"] for m in b["identification"]["missing"]}
    assert {"udyam", "fssai"} <= have and "udyam" not in missing
    assert "gst" not in missing  # local seller below the limit
    assert "iec" not in missing  # not exporting


def test_labour_rules_follow_headcount(client):
    h = login(client, "9000000004")
    client.put("/api/v1/profile", json={**PROFILE, "employees": 25, "business_type": "services"}, headers=h)
    b = client.post("/api/v1/guidance/ask", json={"question": "Do I need PF and ESI for my workers?"}, headers=h).json()
    missing = {m["code"] for m in b["identification"]["missing"]}
    assert {"esi", "epf", "shop_est"} <= missing


def test_other_users_cannot_read_sessions(client):
    h1 = login(client, "9000000005")
    client.put("/api/v1/profile", json=PROFILE, headers=h1)
    sid = client.post("/api/v1/guidance/ask", json={"question": "How do I get a bank loan?"}, headers=h1).json()["session_id"]
    h2 = login(client, "9000000006")
    assert client.get(f"/api/v1/guidance/sessions/{sid}", headers=h2).status_code == 404


def test_rules_engine():
    p = {"turnover_band": 2, "business_type": "services", "channels": ["online"], "registrations": ["udyam"]}
    assert evaluate({"any": [{"field": "turnover_band", "gte": 3}, {"field": "channels", "contains_any": ["online"]}]}, p)
    assert not evaluate({"field": "registrations", "contains": "gst"}, p)
    assert evaluate({"not": {"field": "registrations", "contains": "gst"}}, p)
    assert evaluate(None, p)


def test_pii_masking():
    t = mask_pii("Aadhaar 1234 5678 9012, PAN ABCDE1234F, phone 9876543210, mail a@b.com")
    assert "1234 5678" not in t and "ABCDE1234F" not in t and "9876543210" not in t and "a@b.com" not in t


def test_ai_path_used_when_enabled(client, monkeypatch):
    """With AI switched on, topic detection and the answer come from the model; rules and sources stay the same."""
    from app.guidance import llm
    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: {"intent": "gst_registration", "confidence": 0.9})
    seen = {}

    def fake_complete(system, user, max_tokens=None):
        seen["user"] = user
        return "You need GST registration if you sell to other states [1]."
    monkeypatch.setattr(llm, "complete", fake_complete)

    h = login(client, "9000000007")
    client.put("/api/v1/profile", json=PROFILE, headers=h)
    b = client.post("/api/v1/guidance/ask", json={"question": "tax question, my number is 9876543210"}, headers=h).json()
    assert b["understanding"]["intent_code"] == "gst_registration" and b["understanding"]["method"] == "ai"
    assert b["information"]["method"] == "ai" and "[1]" in b["information"]["answer"]
    assert "Sources:" in seen["user"]


def test_unrelated_follow_up_is_not_forced_into_a_topic(client):
    h = login(client, "9000000008")
    client.put("/api/v1/profile", json=PROFILE, headers=h)
    first = client.post("/api/v1/guidance/ask", json={"question": "Which government schemes can help me?"}, headers=h).json()
    b = client.post("/api/v1/guidance/ask", headers=h,
                    json={"question": "Can I get crop insurance for my mango farm?", "session_id": first["session_id"]}).json()
    assert b["understanding"]["intent_code"] is None
    assert b["connect"]["suggested"] is True
