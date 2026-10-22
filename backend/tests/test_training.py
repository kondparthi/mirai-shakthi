"""Phase 1 Sprint 2 – training: courses, partners, batches, nominations, attendance (trainer + QR), results,
certificates (PDF + public check), needs assessment, follow-ups, external certificates, reports."""
from datetime import date, timedelta

from app.models_p2 import Trainee
from app.training.service import suggest_tracks

from .conftest import login
from .test_programme import admin, make_aadhaar, person, staff

START = date.today() + timedelta(days=3)


def enrol_self(client, mobile, n, **over):
    h = login(client, mobile)
    r = client.put("/api/v1/enrol/me", headers=h, json=person(full_name=f"Trainee {n}", aadhaar=make_aadhaar(f"7{n:010d}"), consent=True, **over))
    assert r.status_code == 200, r.text
    return h, r.json()["entrepreneur"]["id"]


def test_suggest_tracks_rule():
    weak = {"costing": 2, "bookkeeping": 2, "marketing": 3, "digital": 1, "banking": 2}
    assert suggest_tracks(weak, 1, []) == ["awareness", "core", "skill", "ojt", "exposure", "refresher"]
    strong = {k: 5 for k in weak}
    assert suggest_tracks(strong, 4, [{"course": "EDP"}]) == []


def test_training_full_flow(client):
    h = admin(client)
    # Staff: coordinator for Guntur, two trainers, a mentor
    coord = staff(client, "coord.t@mirai.local", "coordinator", ["guntur"])
    tr = staff(client, "trainer.a@mirai.local", "trainer")
    other_tr = staff(client, "trainer.b@mirai.local", "trainer")
    mentor = staff(client, "mentor.a@mirai.local", "mentor", ["guntur"])
    meta = client.get("/api/v1/training/meta", headers=coord).json()
    core = next(c for c in meta["courses"] if c["code"] == "core_edp")
    trainer_id = next(t["id"] for t in meta["trainers"] if t["name"] == "trainer.a")
    mentor_id = meta["mentors"][0]["id"]

    # Courses and partners are admin / programme manager only
    assert client.post("/api/v1/training/partners", headers=coord, json={"name": "X", "kind": "institute", "tracks": ["core"]}).status_code == 403
    p = client.post("/api/v1/training/partners", headers=h, json={"name": "Guntur RSETI", "kind": "institute", "tracks": ["core", "awareness"],
                                                                 "districts": ["guntur"], "mobile": "9440011223"}).json()
    full = client.get("/api/v1/training/courses", headers=h).json()
    assert {c["code"] for c in full} >= {"awareness_edp", "core_edp", "skill_drone_pilot"}

    # Batch (Form 4.1): validation, sessions planned from the course
    base = {"course_id": core["id"], "partner_id": p["id"], "trainer_ids": [trainer_id], "mentor_ids": [mentor_id], "mode": "classroom",
            "start_date": START.isoformat(), "end_date": (START + timedelta(days=9)).isoformat(), "venue": "Tenali RSETI hall",
            "district": "guntur", "seats": 2, "sponsor_type": "csr", "sponsor_name": "SBI Foundation"}
    assert client.post("/api/v1/training/batches", headers=coord, json={**base, "trainer_ids": [mentor_id]}).status_code == 422
    assert client.post("/api/v1/training/batches", headers=coord, json={**base, "district": "krishna"}).status_code == 403
    assert client.post("/api/v1/training/batches", headers=coord, json={**base, "sponsor_name": None}).status_code == 422
    r = client.post("/api/v1/training/batches", headers=coord, json=base)
    assert r.status_code == 200, r.text
    b = r.json()
    assert len(b["sessions"]) == 11 and b["code"].startswith("B") and b["sessions"][-1]["date"] <= base["end_date"]
    bid = b["id"]

    # Trainer sees only their own batches
    assert any(x["id"] == bid for x in client.get("/api/v1/training/batches", headers=tr).json())
    assert not any(x["id"] == bid for x in client.get("/api/v1/training/batches", headers=other_tr).json())
    assert client.get(f"/api/v1/training/batches/{bid}", headers=other_tr).status_code == 404

    # Three entrepreneurs; readiness recommends Core EDP for the first
    h1, e1 = enrol_self(client, "9200000001", 1)
    h2, e2 = enrol_self(client, "9200000002", 2)
    h3, e3 = enrol_self(client, "9200000003", 3)
    client.post("/api/v1/enrol/me/readiness", headers=h1, json={"answers": {"motivation": "Want my own unit", "time": "part"}})
    cand = client.get(f"/api/v1/training/batches/{bid}/candidates", headers=coord).json()
    rec = {c["id"]: c["recommended"] for c in cand}
    assert rec[e1] and not rec[e2]
    assert [c["recommended"] for c in cand] == sorted((c["recommended"] for c in cand), reverse=True)  # recommended first

    # Self request needs an open batch
    assert client.post("/api/v1/training/me/request", headers=h3, json={"batch_id": bid}).status_code == 422
    client.post(f"/api/v1/training/batches/{bid}/status", headers=coord, json={"status": "open"})
    me3 = client.get("/api/v1/training/me", headers=h3).json()
    assert me3["open_batches"][0]["id"] == bid
    assert client.post("/api/v1/training/me/request", headers=h3, json={"batch_id": bid}).status_code == 200

    # Nominate: seat limit, mentor assigned, stage 2
    assert client.post(f"/api/v1/training/batches/{bid}/trainees", headers=coord, json={"entrepreneur_ids": [e1, e2, e3]}).status_code == 422
    d = client.post(f"/api/v1/training/batches/{bid}/trainees", headers=coord, json={"entrepreneur_ids": [e1, e2]}).json()
    t1 = next(t for t in d["trainees"] if t["entrepreneur"]["id"] == e1)
    t2 = next(t for t in d["trainees"] if t["entrepreneur"]["id"] == e2)
    t3 = next(t for t in d["trainees"] if t["entrepreneur"]["id"] == e3)
    assert t1["mentor_id"] == mentor_id and t1["entrepreneur"]["stage"] == 2 and t3["status"] == "requested"
    assert client.put(f"/api/v1/training/trainees/{t3['id']}", headers=coord, json={"status": "confirmed"}).status_code == 422  # full

    # Sessions: QR check-in by trainee, then trainer's attendance list
    s1 = d["sessions"][0]["id"]
    assert client.post(f"/api/v1/training/sessions/{s1}/checkin/open", headers=other_tr, json={}).status_code == 404
    qr = client.post(f"/api/v1/training/sessions/{s1}/checkin/open", headers=tr, json={"origin": "http://localhost:5173"}).json()
    assert qr["url"].startswith("http://localhost:5173/#/checkin/") and "<svg" in qr["svg"] and len(qr["code"]) == 6
    token = qr["url"].rsplit("/", 1)[1]
    assert client.post("/api/v1/training/me/checkin", headers=h3, json={"token": token}).status_code == 404  # only requested
    ok = client.post("/api/v1/training/me/checkin", headers=h1, json={"token": token})
    assert ok.status_code == 200 and ok.json()["n"] == 1
    assert client.post("/api/v1/training/me/checkin", headers=h2, json={"code": qr["code"]}).status_code == 200
    all_ids = [t1["id"], t2["id"]]
    for s in d["sessions"]:
        r = client.post(f"/api/v1/training/sessions/{s['id']}/attendance", headers=tr,
                        json={"present": all_ids if s["n"] <= 10 else [t1["id"]]})
        assert r.status_code == 200
    assert client.post(f"/api/v1/training/sessions/{s1}/attendance", headers=tr, json={"present": [99999]}).status_code == 422
    from io import BytesIO
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (900, 600), (90, 140, 90)).save(buf, "JPEG")
    ph = client.post(f"/api/v1/training/sessions/{s1}/photo", headers=tr, files={"file": ("s.jpg", buf.getvalue(), "image/jpeg")},
                     data={"lat": "16.24", "lng": "80.64"})
    assert ph.status_code == 200 and ph.json()["photo_url"] and ph.json()["lat"] == 16.24

    # Results: suggestion follows the course rules; pass issues a certificate and moves Core EDP graduates to stage 3
    d = client.get(f"/api/v1/training/batches/{bid}", headers=tr).json()
    assert d["status"] == "ongoing"
    t1 = next(t for t in d["trainees"] if t["id"] == t1["id"])
    assert t1["attendance_pct"] == 100 and t1["suggested"] == "reassess" and any("Quiz" in w for w in t1["suggested_why"])
    r = client.put(f"/api/v1/training/trainees/{t1['id']}/assessment", headers=tr, json={"quiz_score": 78, "bp_score": 70, "result": "pass"})
    assert r.status_code == 200 and r.json()["certificate_no"].startswith("MS-CORE-") and r.json()["suggested"] == "pass"
    r2 = client.put(f"/api/v1/training/trainees/{t2['id']}/assessment", headers=tr, json={"quiz_score": 40, "bp_score": 50, "result": "reassess"})
    assert r2.json()["certificate_no"] is None and r2.json()["attendance_pct"] == 91
    assert client.post(f"/api/v1/training/batches/{bid}/status", headers=coord, json={"status": "completed"}).status_code == 200
    assert client.get("/api/v1/enrol/me", headers=h1).json()["entrepreneur"]["stage"] == 3

    # Certificate: entrepreneur downloads the PDF; public check needs the code
    mine = client.get("/api/v1/training/me?lang=te", headers=h1).json()
    my = mine["batches"][0]
    assert my["certificate_no"] and my["attendance_pct"] == 100 and my["course"]["name"] == "కోర్ ఈడీపీ"
    link = client.post(f"/api/v1/training/me/certificate/{my['trainee_id']}/link", headers=h1).json()["url"]
    pdf = client.get(link)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and len(pdf.content) > 50_000
    assert client.post(f"/api/v1/training/me/certificate/{my['trainee_id']}/link", headers=h2).status_code == 404
    from tests.conftest import TEST_DB  # noqa: F401  (same database session as the app)
    from app.db import SessionLocal
    with SessionLocal() as db:
        code = db.get(Trainee, my["trainee_id"]).certificate_code
    assert client.get(f"/api/v1/public/certificates/{my['certificate_no']}").json() == {"valid": False}
    v = client.get(f"/api/v1/public/certificates/{my['certificate_no']}", params={"c": code}).json()
    assert v["valid"] and v["name"] == "Trainee 1" and v["course"] == "Core EDP"

    # Feedback feeds the partner rating
    assert client.post("/api/v1/training/me/feedback", headers=h1, json={"trainee_id": my["trainee_id"], "rating": 5, "text": "Very useful"}).status_code == 200
    assert next(x for x in client.get("/api/v1/training/partners", headers=h).json() if x["id"] == p["id"])["rating"] == 5

    # Follow-up (Form 4.5): due list for the mentor once 30 days have passed
    with SessionLocal() as db:
        t = db.get(Trainee, my["trainee_id"])
        t.certified_at = t.certified_at - timedelta(days=31)
        db.commit()
    due = client.get("/api/v1/training/followups", headers=mentor).json()
    assert due and due[0]["point"] == 30 and due[0]["overdue"]
    body = {"point": 30, "status": "started", "skills_used": "yes", "support": ["finance"], "next_action": "Bank visit"}
    assert client.post(f"/api/v1/training/trainees/{due[0]['trainee_id']}/followups", headers=mentor, json=body).status_code == 200
    assert client.post(f"/api/v1/training/trainees/{due[0]['trainee_id']}/followups", headers=mentor, json=body).status_code == 409
    assert not client.get("/api/v1/training/followups", headers=mentor).json()

    # Reports
    rep = client.get("/api/v1/training/reports/summary", headers=h).json()
    assert rep["certified"] >= 1 and any(x["key"].startswith("SBI Foundation") for x in rep["by_sponsor"])
    csv_text = client.get("/api/v1/training/reports/trainees.csv", headers=h, params={"sponsor": "SBI"}).content.decode("utf-8-sig")
    assert "Trainee 1" in csv_text and "92xxxxx001" in csv_text


def test_needs_assessment_and_external_certificates(client):
    coord = staff(client, "coord.t@mirai.local", "coordinator", ["guntur"])
    h, eid = enrol_self(client, "9200000011", 11)
    needs = {"enterprise_model": "Drone spraying service", "business_skills": {"costing": 2, "bookkeeping": 3, "marketing": 2, "digital": 4, "banking": 3},
             "technical_level": 2, "prior_training": [], "preferred_mode": "classroom", "preferred_timing": "weekends", "constraints": ["travel"]}
    assert client.post(f"/api/v1/training/needs/suggest?eid={eid}", headers=coord, json=needs).json()["tracks"][:3] == ["awareness", "core", "skill"]
    assert client.post(f"/api/v1/training/entrepreneurs/{eid}/needs", headers=coord,
                       json={**needs, "business_skills": {"costing": 9}}).status_code == 422
    r = client.post(f"/api/v1/training/entrepreneurs/{eid}/needs", headers=coord, json={**needs, "recommended_tracks": ["core", "skill"]})
    assert r.json()["recommended_tracks"] == ["core", "skill"]
    assert [x["track"] for x in client.get("/api/v1/training/me", headers=h).json()["recommended"]] == ["core", "skill"]

    pdf = b"%PDF-1.4 test certificate"
    assert client.post("/api/v1/training/me/external", headers=h, data={"kind": "dgca_rpc", "title": "Remote Pilot"},
                       files={"file": ("x.exe", b"MZ...", "application/octet-stream")}).status_code == 422
    x = client.post("/api/v1/training/me/external", headers=h, data={"kind": "dgca_rpc", "title": "DGCA Remote Pilot Certificate", "number": "RPC-123"},
                    files={"file": ("rpc.pdf", pdf, "application/pdf")})
    assert x.status_code == 200 and x.json()["status"] == "pending"
    assert client.get(x.json()["file_url"]).content == pdf
    pending = client.get("/api/v1/training/external-certificates", headers=coord).json()
    xid = next(p["id"] for p in pending if p["entrepreneur"]["id"] == eid)
    assert client.post(f"/api/v1/training/external-certificates/{xid}/verify", headers=coord, json={"status": "rejected"}).status_code == 422
    assert client.post(f"/api/v1/training/external-certificates/{xid}/verify", headers=coord, json={"status": "verified"}).json()["status"] == "verified"
    summary = client.get(f"/api/v1/training/entrepreneurs/{eid}", headers=coord).json()
    assert summary["external"][0]["status"] == "verified" and summary["needs"][0]["enterprise_model"] == "Drone spraying service"


def test_session_edit_accepts_a_date():
    """A field named "date" must not hide the date type (Pydantic would then accept only None)."""
    from app.routers.training import SessionEdit

    assert SessionEdit(date="2026-11-03", topic="Costing").date.isoformat() == "2026-11-03"
