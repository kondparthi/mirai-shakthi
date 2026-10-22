"""Phase 1 Sprint 7 – mentoring and two-year handholding (M10): mentor assignment and scope, caseload, monthly review from the
books (Form 10.1), agreed actions, field visits with geo-tagged photos, support tickets routed by category with referrals
and resolution time (Form 10.2), growth plans (Form 10.3), peer sessions, final assessment, entrepreneur view, reports."""
import io
from datetime import date, timedelta

from PIL import Image
from sqlalchemy import select

from app.books.service import month_key
from app.db import SessionLocal
from app.models import User
from app.models_p1 import Entrepreneur
from app.models_p2 import Batch, Course, Trainee
from app.models_p4 import Unit
from app.models_p6 import LedgerEntry
from app.models_p7 import Mentorship

from .test_programme import admin, staff
from .test_setup import _sanctioned_unit

M = "/api/v1/mentoring"


def _uid(email: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(User.id).where(User.email == email))


def _gps_jpeg(lat=16.2431, lng=80.6400) -> bytes:
    im = Image.new("RGB", (640, 480), (90, 140, 60))
    ex = Image.Exif()
    dms = lambda v: (int(v), int(v * 60 % 60), round(v * 3600 % 60, 2))  # noqa: E731
    ex[0x8825] = {1: "N", 2: dms(lat), 3: "E", 4: dms(lng)}
    b = io.BytesIO()
    im.save(b, "JPEG", exif=ex)
    return b.getvalue()


def test_mentoring_flow(client):
    pm = staff(client, "pm.mentor@mirai.local", "programme_manager")
    coord = staff(client, "coord.guntur.mt@mirai.local", "coordinator", ["guntur"])
    far = staff(client, "coord.kurnool.mt@mirai.local", "coordinator", ["kurnool"])
    mentor = staff(client, "mentor.padma@mirai.local", "mentor")
    other_mentor = staff(client, "mentor.other@mirai.local", "mentor")
    dpro = staff(client, "dpro.guntur.mt@mirai.local", "dpr_officer", ["guntur"])
    expert = staff(client, "expert.food@mirai.local", "sector_expert")
    mid, xid = _uid("mentor.padma@mirai.local"), _uid("expert.food@mirai.local")
    eh, eid, uid, d = _sanctioned_unit(client, pm, "9600000301", "76000000301")

    # A mentorship exists from sanction; nobody mentored this person in training, so no mentor yet
    page = client.get(f"{M}/units/{uid}", headers=coord).json()
    assert page["mentorship"]["mentor"] is None and page["mentorship"]["status"] == "active"
    assert client.get(f"{M}/units/{uid}", headers=mentor).status_code == 404  # mentors see their own units only
    assert client.get(f"{M}/units/{uid}", headers=far).status_code == 404
    assert client.put(f"{M}/units/{uid}/mentor", headers=mentor, json={"mentor_id": mid}).status_code == 403
    assert client.put(f"{M}/units/{uid}/mentor", headers=coord, json={"mentor_id": _uid("coord.guntur.mt@mirai.local")}).status_code == 422
    r = client.put(f"{M}/units/{uid}/mentor", headers=coord, json={"mentor_id": mid, "reason": "Food sector mentor for Tenali"}).json()
    assert r["mentor_id"] == mid and len(r["history"]) == 2
    assert client.get(f"{M}/units/{uid}", headers=mentor).status_code == 200
    assert client.get(f"/api/v1/books/units/{uid}/meta", headers=mentor).status_code == 200  # the books too

    # Launched two months ago with books last month
    today = date.today()
    launch = (today.replace(day=1) - timedelta(days=40)).replace(day=1)
    last = today.replace(day=1) - timedelta(days=5)
    with SessionLocal() as db:
        u = db.get(Unit, uid)
        u.status, u.launch_date, u.lat, u.lng = "launched", launch, 16.2430, 80.6401
        for k in range(10):
            db.add(LedgerEntry(unit_id=uid, kind="sale", on=last - timedelta(days=k), amount=2000, category="counter", payment_mode="cash", source="manual"))
        db.add(LedgerEntry(unit_id=uid, kind="expense", on=last, amount=26000, category="milk", payment_mode="cash", source="manual"))
        db.commit()
    page = client.get(f"{M}/units/{uid}", headers=mentor).json()
    assert page["mentorship"]["start_date"] == launch.isoformat() and page["timeline"]["month_no"] == 3 and len(page["timeline"]["months"]) == 24
    assert page["profile"]["plan"]["dpr_code"] == d["code"] and page["can"]["write"]
    client.get(f"/api/v1/books/units/{uid}/months", headers=eh)  # past months close themselves (M9)

    cl = client.get(f"{M}/caseload", headers=mentor).json()
    row = next(x for x in cl["rows"] if x["unit"]["id"] == uid)
    assert row["review_due"] and row["review_month"] == month_key(last) and {a["code"] for a in row["alerts"]} >= {"loss"}
    assert all(x["mentor"]["id"] == mid for x in cl["rows"])
    assert any(x["unit"]["id"] == uid for x in client.get(f"{M}/caseload?mentor_id={mid}", headers=coord).json()["rows"])

    # Monthly review (Form 10.1) from the books
    dr = client.get(f"{M}/units/{uid}/review-draft", headers=mentor).json()
    assert dr["month"] == month_key(last) and dr["sales"] == 20000 and dr["expenses"] == 26000 and dr["health"] == "red" and "cash_flow" in dr["issues"]
    body = {"month": dr["month"], "sales": 20000, "expenses": 26000, "repayment": "none", "jobs_family": 2, "jobs_hired": 1, "health": "red",
            "scores": {"records": 4, "sales": 2}, "issues": ["cash_flow", "sales"], "training": ["refresher"], "note": "Milk bought at retail price"}
    assert client.post(f"{M}/units/{uid}/reviews", headers=mentor, json=body).status_code == 422  # red needs an action
    assert client.post(f"{M}/units/{uid}/reviews", headers=other_mentor, json=body).status_code == 404
    body["actions"] = [{"text": "Buy milk from the dairy society", "due": (today + timedelta(days=10)).isoformat()},
                       {"text": "Add ragi malt to the menu", "due": (today + timedelta(days=20)).isoformat()}]
    rv = client.post(f"{M}/units/{uid}/reviews", headers=mentor, json=body).json()
    assert rv["profit"] == -6000 and not rv["corrected"] and rv["books"]["sales"] == 20000
    rv = client.post(f"{M}/units/{uid}/reviews", headers=mentor, json={**body, "sales": 21500}).json()  # mentor corrects a missed sale
    assert rv["corrected"] and rv["profit"] == -4500
    assert client.post(f"{M}/units/{uid}/reviews", headers=mentor, json={**body, "month": month_key(today + timedelta(days=40))}).status_code == 422
    months = client.get(f"/api/v1/books/units/{uid}/months", headers=eh).json()
    assert next(m for m in months if m["month"] == dr["month"])["review_note"].startswith("Mentor review: RED")
    with SessionLocal() as db:
        assert db.get(Entrepreneur, eid).stage >= 7

    # The entrepreneur sees the mentor (contact number from the staff record), the actions, and ticks one
    a = admin(client)
    me_staff = next(s for s in client.get("/api/v1/admin/staff", headers=a).json() if s["id"] == mid)
    assert client.put(f"/api/v1/admin/staff/{mid}", headers=a, json={**{k: me_staff[k] for k in ("name", "email", "role", "districts", "sectors", "active")},
                                                                    "phone": "12345"}).status_code == 422
    client.put(f"/api/v1/admin/staff/{mid}", headers=a, json={**{k: me_staff[k] for k in ("name", "email", "role", "districts", "sectors", "active")},
                                                              "phone": "+91 98490 11111"})
    me = client.get(f"{M}/me", headers=eh).json()
    mine = me["units"][0]
    assert mine["mentor"]["mobile"] == "9849011111" and mine["mentor"]["whatsapp"].startswith("https://wa.me/919849011111")
    assert mine["handholding"]["month_no"] == 3 and mine["reviews"][0]["health"] == "red"
    assert client.put(f"{M}/reviews/{rv['id']}/actions/0", headers=eh, json={"done": True}).json()["actions"][0]["done"]
    assert client.put(f"{M}/reviews/{rv['id']}/actions/5", headers=eh, json={"done": True}).status_code == 404

    # Field visit with geo-tagged photos (camera EXIF, or the phone's position)
    assert client.post(f"{M}/units/{uid}/visits", headers=mentor, json={"on": (today + timedelta(days=1)).isoformat(), "notes": "x" * 10}).status_code == 422
    v = client.post(f"{M}/units/{uid}/visits", headers=mentor, json={"on": today.isoformat(), "purpose": "review", "notes": "Checked the stall and the stock register.",
                                                                   "next_visit": (today + timedelta(days=30)).isoformat()}).json()
    v = client.post(f"{M}/visits/{v['id']}/photos", headers=mentor, files={"file": ("a.jpg", _gps_jpeg(), "image/jpeg")}).json()
    assert v["photos"][0]["source"] == "exif" and abs(v["photos"][0]["lat"] - 16.2431) < 0.001 and v["distance_m"] < 50
    v = client.post(f"{M}/visits/{v['id']}/photos", headers=mentor, data={"lat": "16.3", "lng": "80.45"},
                    files={"file": ("b.jpg", _gps_jpeg(), "image/jpeg")}).json()
    assert v["photos"][1]["source"] == "device" and v["photos"][1]["url"]
    assert client.post(f"{M}/visits/{v['id']}/photos", headers=other_mentor, files={"file": ("c.jpg", _gps_jpeg(), "image/jpeg")}).status_code == 404

    # Support tickets (Form 10.2): routed by category in the unit's district
    t = client.post(f"{M}/units/{uid}/tickets", headers=eh, json={"category": "finance", "description": "Bank has not released the subsidy", "priority": "high"}).json()
    assert t["code"].startswith("TK-") and t["channel"] == "app" and t["due_by"] == (today + timedelta(days=2)).isoformat()
    with SessionLocal() as db:
        assert db.get(User, t["assigned_to"]["id"]).role == "dpr_officer"
    t2 = client.post(f"{M}/units/{uid}/tickets", headers=eh, json={"category": "other", "description": "Need help with pricing", "priority": "low"}).json()
    assert t2["assigned_to"]["id"] == mid
    t3 = client.post(f"{M}/units/{uid}/tickets", headers=coord, json={"category": "technical", "description": "Millet malt goes sour by noon"}).json()
    assert t3["channel"] == "navigator"
    assert client.post(f"{M}/units/{uid}/tickets", headers=far, json={"category": "other", "description": "xxxxxx"}).status_code == 404
    assert client.post(f"{M}/tickets/{t['id']}/assign", headers=eh, json={"user_id": 1}).status_code == 403
    client.post(f"{M}/tickets/{t['id']}/assign", headers=coord, json={"user_id": _uid("dpro.guntur.mt@mirai.local"), "note": "Knows the Tenali branch"})
    mine_q = client.get(f"{M}/tickets?view=mine&status=active", headers=dpro).json()
    assert any(x["id"] == t["id"] for x in mine_q["rows"])

    st = lambda h, tid, b: client.post(f"{M}/tickets/{tid}/status", headers=h, json=b)  # noqa: E731
    assert st(other_mentor, t["id"], {"status": "in_progress"}).status_code == 404
    assert st(eh, t["id"], {"status": "closed"}).status_code == 409  # not resolved yet
    assert st(dpro, t["id"], {"status": "in_progress"}).json()["status"] == "in_progress"
    assert st(dpro, t["id"], {"status": "resolved"}).status_code == 422
    assert st(dpro, t["id"], {"status": "resolved", "resolution": "Called the branch; subsidy credited"}).json()["hours"] is not None
    assert st(eh, t["id"], {"status": "open"}).status_code == 422
    assert st(eh, t["id"], {"status": "open", "note": "Only half the subsidy came"}).json()["status"] == "open"
    st(dpro, t["id"], {"status": "resolved", "resolution": "Second instalment released"})
    r = client.post(f"{M}/tickets/{t['id']}/rate", headers=eh, json={"rating": 5}).json()
    assert r["status"] == "closed" and r["rating"] == 5 and [e["kind"] for e in r["events"]].count("status") >= 5

    # Referral to a sector expert: it shows in the expert's queue
    r = client.post(f"{M}/tickets/{t3['id']}/refer", headers=coord, json={"kind": "sector_expert", "to": "Food technologist", "user_id": xid,
                                                                         "note": "Shelf life of millet malt"}).json()
    assert r["status"] == "in_progress" and r["referrals"][0]["user_id"] == xid
    assert any(x["id"] == t3["id"] for x in client.get(f"{M}/tickets?view=mine", headers=expert).json()["rows"])
    assert client.post(f"{M}/tickets/{t3['id']}/comment", headers=expert, json={"text": "Boil and cool quickly; add jaggery after cooling"}).status_code == 200
    assert client.post(f"{M}/tickets/{t3['id']}/assign", headers=coord, json={"user_id": mid}).json()["assigned_to"]["id"] == mid

    # Growth plan (Form 10.3) → stage 8
    g = client.post(f"{M}/units/{uid}/growth", headers=mentor, json={"goal": "new_product", "target": "Ragi malt, 30 glasses a day",
                                                                   "target_date": (today + timedelta(days=90)).isoformat(), "support": ["training", "market"]}).json()
    assert g["goal_label"] == "New product / service"
    assert client.put(f"{M}/growth/{g['id']}", headers=mentor, json={"note": "Trial started; 12 glasses a day"}).json()["progress"]
    with SessionLocal() as db:
        assert db.get(Entrepreneur, eid).stage == 8

    # Dashboard: review done, red health, tickets, the training need from the review
    s = client.get(f"{M}/reports/summary", headers=coord).json()
    assert s["health"]["red"] >= 1 and s["tickets"]["resolved"] >= 1 and any(x["review_id"] == rv["id"] for x in s["training_needs"])
    assert client.post(f"{M}/reviews/{rv['id']}/training-done", headers=coord).json()["ok"]
    assert all(x["review_id"] != rv["id"] for x in client.get(f"{M}/reports/summary", headers=coord).json()["training_needs"])
    assert not any(x["unit"]["id"] == uid for x in client.get(f"{M}/caseload", headers=far).json()["rows"])

    # Final assessment closes the 24 months (only near the end, or when the unit closes)
    close = {"outcome": "stable", "final_score": 4, "jobs": 3, "note": "Running steadily; repays on time; new product added."}
    assert client.post(f"{M}/units/{uid}/close", headers=coord, json=close).status_code == 409
    with SessionLocal() as db:
        ms = db.scalar(select(Mentorship).where(Mentorship.unit_id == uid))
        ms.end_date = today + timedelta(days=20)
        db.commit()
    assert client.post(f"{M}/units/{uid}/close", headers=mentor, json=close).status_code == 403
    p = client.post(f"{M}/units/{uid}/close", headers=coord, json=close).json()
    assert p["mentorship"]["status"] == "closed" and p["mentorship"]["final"]["sales_last3"] == 20000 and p["mentorship"]["final"]["tickets"] == 3
    assert client.post(f"{M}/units/{uid}/reviews", headers=mentor, json=body).status_code == 409

    # The person's data export includes tickets
    assert client.get("/api/v1/enrol/me/export", headers=eh).json()["support_tickets"]


def test_mentor_from_training_and_peer_sessions(client):
    pm = staff(client, "pm.mentor2@mirai.local", "programme_manager")
    mentor = staff(client, "mentor.ravi@mirai.local", "mentor")
    mid = _uid("mentor.ravi@mirai.local")
    eh = None
    # The person had this mentor in training → the unit gets the same mentor at sanction
    from .conftest import login
    from .test_programme import make_aadhaar, person
    eh = login(client, "9600000401")
    eid = client.put("/api/v1/enrol/me", headers=eh, json=person(full_name="Kavitha", aadhaar=make_aadhaar("76000000401"), consent=True)).json()["entrepreneur"]["id"]
    with SessionLocal() as db:
        c = db.scalar(select(Course).where(Course.track == "core"))
        b = Batch(course_id=c.id, mentor_ids=[mid], start_date=date.today() - timedelta(days=60), end_date=date.today() - timedelta(days=50),
                  district="guntur", status="completed")
        db.add(b)
        db.flush()
        b.code = f"B-T-{b.id}"
        tr = Trainee(batch_id=b.id, entrepreneur_id=eid, mentor_id=mid, status="completed", result="pass")
        db.add(tr)
        db.commit()
        bid, tid = b.id, tr.id
    cafe = next(m for m in client.get("/api/v1/dpr/models", headers=pm).json() if m["code"] == "millet_cafe")
    d = client.post("/api/v1/dpr/dprs", headers=pm, json={"entrepreneur_id": eid, "model_id": cafe["id"]}).json()
    client.post(f"/api/v1/dpr/dprs/{d['id']}/narrative", headers=pm, json={"narrative_notes": {}})
    client.post(f"/api/v1/dpr/dprs/{d['id']}/status", headers=pm, json={"action": "approve"})
    a = client.post("/api/v1/dpr/applications", headers=pm, json={"dpr_id": d["id"], "bank": "sbi", "branch": "Tenali"}).json()
    client.post(f"/api/v1/dpr/applications/{a['id']}/status", headers=pm, json={"status": "submitted", "on": date.today().isoformat()})
    client.post(f"/api/v1/dpr/applications/{a['id']}/status", headers=pm, json={"status": "sanctioned", "on": date.today().isoformat(),
                                                                               "sanctioned_amount": a["amount_requested"]})
    uid = client.get(f"/api/v1/setup/units?entrepreneur_id={eid}", headers=pm).json()["rows"][0]["id"]
    page = client.get(f"{M}/units/{uid}", headers=mentor).json()
    assert page["mentorship"]["mentor"]["id"] == mid and page["profile"]["training"][0]["batch"].startswith("B-T-")
    assert client.get(f"{M}/me", headers=eh).json()["units"][0]["mentor"]["name"]
    # not launched yet: no review due, cannot add a growth plan
    row = next(x for x in client.get(f"{M}/caseload", headers=mentor).json()["rows"] if x["unit"]["id"] == uid)
    assert not row["review_due"] and row["month_no"] == 0
    assert client.post(f"{M}/units/{uid}/growth", headers=mentor, json={"goal": "hire", "target": "One helper",
                                                                      "target_date": (date.today() + timedelta(days=60)).isoformat()}).status_code == 409

    # Peer sessions for the batch
    bs = client.get(f"{M}/batches", headers=mentor).json()
    b = next(x for x in bs if x["id"] == bid)
    assert b["due"] and b["trainees"][0]["id"] == tid
    assert client.post(f"{M}/batches/{bid}/peer-sessions", headers=mentor, json={"on": date.today().isoformat(), "topic": "Pricing", "attendees": [999999]}).status_code == 422
    bs = client.post(f"{M}/batches/{bid}/peer-sessions", headers=mentor, json={"on": date.today().isoformat(), "topic": "Pricing and costing", "mode": "phone",
                                                                             "attendees": [tid], "notes": "Shared their first month's numbers"}).json()
    b = next(x for x in bs if x["id"] == bid)
    assert not b["due"] and b["sessions"][0]["attended"] == 1
    other = staff(client, "mentor.none@mirai.local", "mentor")
    assert all(x["id"] != bid for x in client.get(f"{M}/batches", headers=other).json())
    assert client.post(f"{M}/batches/{bid}/peer-sessions", headers=other, json={"on": date.today().isoformat(), "topic": "x y z"}).status_code == 403
