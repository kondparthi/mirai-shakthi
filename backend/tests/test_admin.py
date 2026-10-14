from datetime import date

from .conftest import PROFILE, login


def admin_headers(client):
    r = client.post("/api/v1/auth/staff/login", json={"email": "admin@mirai.local", "password": "ChangeMe@123"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_msme_cannot_use_admin(client):
    h = login(client, "9100000001")
    assert client.get("/api/v1/admin/stats", headers=h).status_code == 403
    assert client.get("/api/v1/admin/stats").status_code == 401


def test_stats_and_meta(client):
    h = admin_headers(client)
    s = client.get("/api/v1/admin/stats", headers=h).json()
    assert s["kb_published"] >= 18 and "top_topics" in s
    assert len(client.get("/api/v1/admin/meta", headers=h).json()["modules"]) == 5


def test_kb_publish_requires_verification_and_is_used_in_answers(client):
    h = admin_headers(client)
    body = {"title": "Zebra crossing permit for kiosks", "module": "launchpad", "intent_code": None,
            "body": "Kiosks on footpaths need a zebra permit from the municipal office before opening.",
            "source_url": "https://example.gov.in", "status": "published"}
    assert client.post("/api/v1/admin/kb", json=body, headers=h).status_code == 422  # not verified yet
    body |= {"verified_by": "MIRAI content team", "verified_on": date.today().isoformat()}
    item = client.post("/api/v1/admin/kb", json=body, headers=h).json()
    assert item["status"] == "published"

    u = login(client, "9100000002")
    client.put("/api/v1/profile", json=PROFILE, headers=u)
    ans = client.post("/api/v1/guidance/ask", json={"question": "Do I need a zebra permit for my kiosk?"}, headers=u).json()
    assert any(s["title"] == body["title"] for s in ans["information"]["sources"])

    # Archive it: it must stop appearing
    client.put(f"/api/v1/admin/kb/{item['id']}", json={**body, "status": "archived"}, headers=h)
    ans = client.post("/api/v1/guidance/ask", json={"question": "Do I need a zebra permit for my kiosk?"}, headers=u).json()
    assert all(s["title"] != body["title"] for s in ans["information"]["sources"])


def test_rule_crud_changes_gaps(client):
    h = admin_headers(client)
    topics = client.get("/api/v1/admin/intents", headers=h).json()
    gst = next(t for t in topics if t["code"] == "gst_registration")
    bad = {"item_code": "pan_card", "title_en": "PAN card", "condition": {"oops": 1}}
    assert client.post(f"/api/v1/admin/intents/{gst['id']}/rules", json=bad, headers=h).status_code == 422
    rule = client.post(f"/api/v1/admin/intents/{gst['id']}/rules", headers=h, json={
        "item_code": "pan_card", "title_en": "PAN card of the owner", "step_order": 0,
        "condition": {"field": "ownership", "eq": "proprietor"}}).json()

    u = login(client, "9100000003")
    client.put("/api/v1/profile", json=PROFILE, headers=u)
    ans = client.post("/api/v1/guidance/ask", json={"question": "Do I need GST registration?"}, headers=u).json()
    assert ans["guidance"]["steps"][0]["code"] == "pan_card"

    assert client.delete(f"/api/v1/admin/rules/{rule['id']}", headers=h).status_code == 200
    ans = client.post("/api/v1/guidance/ask", json={"question": "Do I need GST registration?"}, headers=u).json()
    assert all(s["code"] != "pan_card" for s in ans["guidance"]["steps"])


def test_topic_create_and_keywords_route_questions(client):
    h = admin_headers(client)
    r = client.post("/api/v1/admin/intents", headers=h, json={
        "code": "solar_rooftop", "module": "launchpad", "title_en": "Solar rooftop for my unit",
        "keywords": ["solar", "rooftop"], "sample_questions": ["Can I put solar panels on my unit?"],
        "connect_service": "sector_advice"})
    assert r.status_code == 200
    assert client.post("/api/v1/admin/intents", headers=h, json={**r.json(), "code": "solar_rooftop"}).status_code == 409
    u = login(client, "9100000004")
    client.put("/api/v1/profile", json=PROFILE, headers=u)
    ans = client.post("/api/v1/guidance/ask", json={"question": "Can I install rooftop solar?"}, headers=u).json()
    assert ans["understanding"]["intent_code"] == "solar_rooftop"


def test_experts_and_review_queue(client):
    h = admin_headers(client)
    e = client.post("/api/v1/admin/experts", headers=h, json={
        "name": "Test CA", "expert_type": "ca", "services": ["gst_filing"], "districts": ["Guntur"], "languages": ["te"]}).json()
    assert e["status"] == "pending"
    assert client.post("/api/v1/admin/experts", headers=h, json={
        "name": "X", "expert_type": "ca", "services": ["nope"], "districts": ["Guntur"], "languages": ["te"]}).status_code == 422

    u = login(client, "9100000005")
    client.put("/api/v1/profile", json=PROFILE, headers=u)
    ans = client.post("/api/v1/guidance/ask", json={"question": "Do I need GST registration?"}, headers=u).json()
    client.post(f"/api/v1/guidance/messages/{ans['message_id']}/rate", json={"rating": -1}, headers=u)
    queue = client.get("/api/v1/admin/review", headers=h).json()
    item = next(q for q in queue if q["id"] == ans["message_id"])
    assert item["reason"] == "Rated not helpful" and item["question"] == "Do I need GST registration?"
    client.post(f"/api/v1/admin/review/{item['id']}", json={"action": "content_added", "note": "Added FAQ"}, headers=h)
    assert all(q["id"] != item["id"] for q in client.get("/api/v1/admin/review", headers=h).json())

    users = client.get("/api/v1/admin/users?q=Lakshmi", headers=h).json()
    assert users and users[0]["summary"]
