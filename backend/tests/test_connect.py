from .conftest import PROFILE, login
from .test_admin import admin_headers


def expert_headers(client, email="ca.guntur@mirai.local", password="Expert@123"):
    r = client.post("/api/v1/auth/staff/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _setup(client, mobile):
    h = login(client, mobile)
    client.put("/api/v1/profile", json=PROFILE, headers=h)
    ans = client.post("/api/v1/guidance/ask", json={"question": "Do I need GST registration?"}, headers=h).json()
    expert = next(e for e in ans["connect"]["experts"] if e["name"] == "Sample CA – Guntur")
    return h, ans, expert


def test_full_handholding_lifecycle(client):
    h, ans, expert = _setup(client, "9400000001")
    sid = ans["session_id"]
    roadmap = client.post("/api/v1/artefacts/roadmap", json={"session_id": sid}, headers=h).json()
    d = client.get(f"/api/v1/connect/draft?expert_id={expert['id']}&session_id={sid}", headers=h).json()
    assert "Still needed" in d["summary"] and d["service"] == "gst_filing"
    assert any(a["id"] == roadmap["id"] and a["from_this_conversation"] for a in d["artefacts"])

    body = {"expert_id": expert["id"], "session_id": sid, "service": d["service"], "summary": d["summary"],
            "preferred_contact": "whatsapp", "budget": "upto_2000", "artefact_ids": [roadmap["id"]], "consent": False}
    assert client.post("/api/v1/connect/requests", json=body, headers=h).status_code == 422      # consent required
    req = client.post("/api/v1/connect/requests", json={**body, "consent": True}, headers=h).json()
    assert req["status"] == "sent" and req["shared_documents"][0]["id"] == roadmap["id"]
    assert client.post("/api/v1/connect/requests", json={**body, "consent": True}, headers=h).status_code == 409  # duplicate

    eh = expert_headers(client)
    case = client.get(f"/api/v1/expert/requests/{req['id']}", headers=eh).json()
    assert case["client"]["mobile"] is None                                   # hidden until accepted
    assert client.post(f"/api/v1/expert/requests/{req['id']}/documents/{roadmap['id']}/link", headers=eh).status_code == 403
    case = client.post(f"/api/v1/expert/requests/{req['id']}/accept", json={}, headers=eh).json()
    assert case["status"] == "accepted" and case["client"]["mobile"] == "9400000001"
    link = client.post(f"/api/v1/expert/requests/{req['id']}/documents/{roadmap['id']}/link", headers=eh).json()["url"]
    assert client.get(link).content[:4] == b"%PDF"

    case = client.post(f"/api/v1/expert/requests/{req['id']}/quote", json={"amount": 1500, "note": "GST registration filing, 7 days"}, headers=eh).json()
    assert case["status"] == "quoted" and case["quote"]["amount"] == 1500
    mine = client.get(f"/api/v1/connect/requests/{req['id']}", headers=h).json()
    assert "accept_quote" in mine["actions"]
    mine = client.post(f"/api/v1/connect/requests/{req['id']}/quote", json={"accept": True}, headers=h).json()
    assert mine["status"] == "in_progress"
    client.post(f"/api/v1/connect/requests/{req['id']}/message", json={"text": "Sent PAN copy on WhatsApp"}, headers=h)
    case = client.post(f"/api/v1/expert/requests/{req['id']}/status", json={"status": "done", "text": "GSTIN issued"}, headers=eh).json()
    assert case["status"] == "done" and any(u["text"] == "Sent PAN copy on WhatsApp" for u in case["updates"])

    mine = client.post(f"/api/v1/connect/requests/{req['id']}/rate", json={"stars": 5, "comment": "Quick"}, headers=h).json()
    assert mine["rating"]["stars"] == 5 and "rate" not in mine["actions"]
    assert client.post(f"/api/v1/connect/requests/{req['id']}/rate", json={"stars": 4}, headers=h).status_code == 409
    assert client.get("/api/v1/expert/me", headers=eh).json()["rating"] is not None


def test_wrong_transitions_and_privacy(client):
    h, ans, expert = _setup(client, "9400000002")
    d = client.get(f"/api/v1/connect/draft?expert_id={expert['id']}", headers=h).json()
    req = client.post("/api/v1/connect/requests", headers=h, json={"expert_id": expert["id"], "service": d["service"],
                      "summary": d["summary"], "consent": True}).json()
    eh = expert_headers(client)
    # cannot complete before accepting; user cannot accept a quote that does not exist
    assert client.post(f"/api/v1/expert/requests/{req['id']}/status", json={"status": "done"}, headers=eh).status_code == 409
    assert client.post(f"/api/v1/connect/requests/{req['id']}/quote", json={"accept": True}, headers=h).status_code == 409
    # another user cannot see it; an MSME cannot use the expert API
    h2 = login(client, "9400000003")
    assert client.get(f"/api/v1/connect/requests/{req['id']}", headers=h2).status_code == 404
    assert client.get("/api/v1/expert/requests", headers=h2).status_code == 403
    # decline needs a reason
    assert client.post(f"/api/v1/expert/requests/{req['id']}/decline", json={}, headers=eh).status_code == 422
    assert client.post(f"/api/v1/connect/requests/{req['id']}/cancel", headers=h).json()["status"] == "cancelled"


def test_admin_queue_reassign_and_expert_login(client):
    h, ans, expert = _setup(client, "9400000004")
    d = client.get(f"/api/v1/connect/draft?expert_id={expert['id']}", headers=h).json()
    req = client.post("/api/v1/connect/requests", headers=h, json={"expert_id": expert["id"], "service": "gst_filing",
                      "summary": d["summary"], "consent": True}).json()
    eh = expert_headers(client)
    client.post(f"/api/v1/expert/requests/{req['id']}/decline", json={"text": "Fully booked this month"}, headers=eh)

    ah = admin_headers(client)
    queue = client.get("/api/v1/admin/requests?attention=true", headers=ah).json()
    assert any(q["id"] == req["id"] for q in queue)
    experts = client.get("/api/v1/admin/experts", headers=ah).json()
    other = next(x for x in experts if "gst_filing" not in x["services"] and x["status"] == "approved")
    assert client.post(f"/api/v1/admin/requests/{req['id']}/reassign", json={"expert_id": other["id"]}, headers=ah).status_code == 422
    # give a second expert a login and the service, then reassign
    cs = next(x for x in experts if x["name"] == "Sample CS – Vijayawada")
    upd = {k: cs[k] for k in ("name", "organisation", "expert_type", "reg_no", "districts", "languages", "fee_note", "response_hours", "status")}
    client.put(f"/api/v1/admin/experts/{cs['id']}", json={**upd, "services": cs["services"] + ["gst_filing"]}, headers=ah)
    assert client.post(f"/api/v1/admin/experts/{cs['id']}/login", json={"email": "cs@mirai.local", "password": "short"}, headers=ah).status_code == 422
    out = client.post(f"/api/v1/admin/experts/{cs['id']}/login", json={"email": "cs@mirai.local", "password": "Expert@456"}, headers=ah).json()
    assert out["login_email"] == "cs@mirai.local"
    r = client.post(f"/api/v1/admin/requests/{req['id']}/reassign", json={"expert_id": cs["id"]}, headers=ah).json()
    assert r["status"] == "sent" and r["expert"]["name"] == "Sample CS – Vijayawada"
    ch = expert_headers(client, "cs@mirai.local", "Expert@456")
    assert any(c["id"] == req["id"] for c in client.get("/api/v1/expert/requests?status=open", headers=ch).json())
    # the first expert no longer sees it
    assert client.get(f"/api/v1/expert/requests/{req['id']}", headers=eh).status_code == 404
    assert client.get("/api/v1/admin/stats", headers=ah).json()["requests_open"] >= 1
