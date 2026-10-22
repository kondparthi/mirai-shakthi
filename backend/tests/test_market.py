"""Phase 1 Sprint 5 – marketing, sales & orders: listings, orders and bookings with slot capacity, payment and credit,
public shop + order tracking + rating, repeat-customer follow-ups, posters and messages, enquiries routed to units,
campaigns, reports and access rules."""
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models_p3 import EnterpriseModel
from app.models_p4 import Unit
from app.models_p5 import Order

from .conftest import login
from .test_programme import make_aadhaar, person, staff


def _unit(client, mobile, aadhaar11, model_code="millet_cafe", status="launched", name="Lakshmi Millet Café"):
    h = login(client, mobile)
    eid = client.put("/api/v1/enrol/me", headers=h, json=person(full_name=name.split()[0] + " Devi", aadhaar=make_aadhaar(aadhaar11), consent=True)).json()["entrepreneur"]["id"]
    with SessionLocal() as db:
        m = db.scalar(select(EnterpriseModel).where(EnterpriseModel.code == model_code))
        u = Unit(entrepreneur_id=eid, model_id=m.id, name=name, district="guntur", mandal="tenali", village="kolakaluru", status=status,
                 readiness={}, launch_date=date.today() if status == "launched" else None)
        db.add(u)
        db.flush()
        u.code = f"U-T-{u.id:05d}"
        db.commit()
        return h, u.id, u.code


def test_shop_orders_bookings_public(client):
    h, uid, code = _unit(client, "9500000001", "75000000011")
    other_h, other_uid, _ = _unit(client, "9500000002", "75000000022", name="Other Café")
    far = staff(client, "coord.kurnool.m@mirai.local", "coordinator", ["kurnool"])
    coord = staff(client, "coord.guntur.m@mirai.local", "coordinator", ["guntur"])

    # Access: own unit only; staff in scope
    assert client.get(f"/api/v1/market/units/{other_uid}/listings", headers=h).status_code == 404
    assert client.get(f"/api/v1/market/units/{uid}/listings", headers=far).status_code == 404
    assert client.get(f"/api/v1/market/units/{uid}/listings", headers=coord).status_code == 200
    mine = client.get("/api/v1/market/my-units", headers=h).json()
    assert [u["id"] for u in mine] == [uid] and mine[0]["shop_url"].endswith(f"#/shop/{code}")

    # Listings (Form 8.1): start from the model's products
    items = client.post(f"/api/v1/market/units/{uid}/listings/from-model", headers=h).json()
    assert len(items) == 4 and {i["kind"] for i in items} == {"product"}
    snack = next(i for i in items if i["name"].startswith("Millet snacks"))
    svc = client.post(f"/api/v1/market/units/{uid}/listings", headers=h, json={"kind": "service", "name": "Party catering", "price": 120, "price_unit": "plate",
                                                                           "slots": [{"label": "Lunch", "capacity": 50}, {"label": "Dinner", "capacity": 50}]}).json()
    assert client.post(f"/api/v1/market/units/{uid}/listings", headers=h, json={"kind": "product", "name": "X", "price": 0, "price_unit": "each"}).status_code == 422

    # Walk-in sale paid in cash; "paid" needs the payment mode
    cust = {"name": "Ramu", "mobile": "9849012345"}
    body = {"customer": cust, "lines": [{"listing_id": snack["id"], "qty": 3}], "status": "paid"}
    assert client.post(f"/api/v1/market/units/{uid}/orders", headers=h, json=body).status_code == 422
    o = client.post(f"/api/v1/market/units/{uid}/orders", headers=h, json={**body, "payment_mode": "cash"}).json()
    assert o["amount"] == 120 and o["status"] == "paid" and o["code"].startswith("OR-")
    assert client.get("/api/v1/market/customers/lookup?mobile=9849012345", headers=h).json()["name"] == "Ramu"

    # Booking with slot capacity
    day = (date.today() + timedelta(days=3)).isoformat()
    bk = {"customer": {"name": "Govt school", "mobile": "9849012346", "kind": "institution"}, "lines": [{"listing_id": svc["id"], "qty": 40}], "date": day}
    assert client.post(f"/api/v1/market/units/{uid}/orders", headers=h, json=bk).status_code == 422  # slot needed
    b1 = client.post(f"/api/v1/market/units/{uid}/orders", headers=h, json={**bk, "slot": "Lunch"}).json()
    assert b1["kind"] == "booking" and b1["status"] == "confirmed"
    r = client.post(f"/api/v1/market/units/{uid}/orders", headers=h, json={**bk, "slot": "Lunch", "lines": [{"listing_id": svc["id"], "qty": 20}]})
    assert r.status_code == 409 and "10" in r.json()["detail"]
    av = client.get(f"/api/v1/market/listings/{svc['id']}/availability?start={day}&days=1", headers=h).json()
    assert av[0]["slots"] == [{"label": "Lunch", "left": 10.0}, {"label": "Dinner", "left": 50.0}]

    # Status flow: credit delivery is outstanding until paid; cancel needs a reason
    st = lambda oid, b: client.post(f"/api/v1/market/orders/{oid}/status", headers=h, json=b)  # noqa: E731
    assert st(b1["id"], {"status": "delivered", "payment_mode": "credit"}).json()["outstanding"]
    assert client.get(f"/api/v1/market/units/{uid}/summary", headers=h).json()["outstanding"] == 4800
    assert st(b1["id"], {"status": "paid"}).status_code == 422
    assert st(b1["id"], {"status": "paid", "payment_mode": "upi"}).json()["status"] == "paid"
    assert st(b1["id"], {"status": "cancelled", "reason": "x"}).status_code == 409

    # Public shop: only launched units; prices fixed by the shop; tracking with token; rating after delivery
    with SessionLocal() as db:
        db.get(Unit, other_uid).status = "setting_up"
        db.commit()
    assert client.get(f"/api/v1/public/shop/U-T-{other_uid:05d}").status_code == 404
    shop = client.get(f"/api/v1/public/shop/{code}?lang=te").json()
    assert shop["name"] == "Lakshmi Millet Café" and len(shop["listings"]) == 5
    po = client.post(f"/api/v1/public/shop/{code}/orders", json={"name": "Sita", "mobile": "9849012399", "lines": [{"listing_id": snack["id"], "qty": 2, "price": 1}]}).json()
    assert po["amount"] == 80
    tr = client.get(f"/api/v1/public/orders/{po['code']}?t={po['token']}").json()
    assert tr["status"] == "new" and tr["customer"]["mobile"].startswith("98xx") and tr["status_label"] == "కొత్తది"
    assert client.get(f"/api/v1/public/orders/{po['code']}?t=wrong").status_code == 404
    assert client.post(f"/api/v1/public/orders/{po['code']}/rate?t={po['token']}", json={"stars": 5}).status_code == 409
    oid = next(x["id"] for x in client.get(f"/api/v1/market/units/{uid}/orders?when=open", headers=h).json()["rows"] if x["code"] == po["code"])
    st(oid, {"status": "delivered", "payment_mode": "cash"})
    assert client.post(f"/api/v1/public/orders/{po['code']}/rate?t={po['token']}", json={"stars": 4, "comment": "Tasty"}).json()["ok"]
    assert client.post(f"/api/v1/public/orders/{po['code']}/rate?t={po['token']}", json={"stars": 5}).status_code == 409
    s = client.get(f"/api/v1/market/units/{uid}/summary", headers=h).json()
    assert s["rating"] == 4 and s["customers"] == 3 and s["today"] >= 120

    # Repeat-customer follow-up: Ramu bought 20 days ago
    with SessionLocal() as db:
        first = db.get(Order, o["id"])
        first.created_at = datetime.now() - timedelta(days=20)
        first.paid_on = first.date = date.today() - timedelta(days=20)
        db.commit()
    fu = client.get(f"/api/v1/market/units/{uid}/followups?lang=te", headers=h).json()
    ramu = next(x for x in fu if x["name"] == "Ramu")
    assert ramu["days"] == 20 and ramu["wa_link"].startswith("https://wa.me/919849012345")
    client.post(f"/api/v1/market/units/{uid}/followups", headers=h, json={"customer_id": ramu["customer_id"], "note": "Called"})
    assert not any(x["name"] == "Ramu" for x in client.get(f"/api/v1/market/units/{uid}/followups", headers=h).json())

    # Poster and message from real prices (template when AI is off)
    p = client.post(f"/api/v1/market/units/{uid}/promo", headers=h, json={"lang": "te", "occasion": "launch"}).json()
    assert p["source"] == "template" and "రూ. 40" in p["message"] and code in p["message"]
    img = client.get(p["poster_url"])
    assert img.status_code == 200 and img.content.startswith(b"\x89PNG")
    assert len(client.get(f"/api/v1/market/units/{uid}/promo", headers=h).json()) == 1


def test_enquiries_campaigns_reports(client):
    h, uid, code = _unit(client, "9500000003", "75000000033", name="Ammulu Millet Café")
    coord = staff(client, "coord.guntur.m@mirai.local", "coordinator", ["guntur"])
    trainer = staff(client, "trainer.m@mirai.local", "trainer")
    items = client.post(f"/api/v1/market/units/{uid}/listings/from-model", headers=h).json()
    snack = items[0]

    # Enquiry from a school, routed to the unit; the unit sees the buyer's number once interested
    e = client.post("/api/v1/market/enquiries", headers=coord, json={"customer": {"name": "ZP High School", "mobile": "9849000777", "kind": "institution",
                    "organisation": "ZPHS Tenali"}, "need": "Millet snacks for 120 students every Friday", "sector": "food", "model_code": "millet_cafe",
                    "district": "guntur", "quantity": "120 plates a week", "source": "visit"}).json()
    assert e["code"].startswith("EQ-") and e["status"] == "open"
    assert client.post("/api/v1/market/enquiries", headers=trainer, json={}).status_code == 403
    det = client.get(f"/api/v1/market/enquiries/{e['id']}", headers=coord).json()
    assert any(s["id"] == uid for s in det["suggested"])
    client.post(f"/api/v1/market/enquiries/{e['id']}/route", headers=coord, json={"unit_ids": [uid]})
    got = client.get(f"/api/v1/market/units/{uid}/enquiries", headers=h).json()[0]
    assert got["buyer"]["mobile"].startswith("98xx")
    rid = got["route"]["id"]
    got = client.post(f"/api/v1/market/routes/{rid}/reply", headers=h, json={"status": "interested", "quote_amount": 4200, "reply": "Can supply every Friday"}).json()[0]
    assert got["buyer"]["mobile"] == "9849000777"

    # Campaign (Form 8.3): orders tagged with it count in its results
    c = client.post("/api/v1/market/campaigns", headers=coord, json={"name": "Dasara millet mela", "start_date": date.today().isoformat(),
                    "end_date": (date.today() + timedelta(days=5)).isoformat(), "sectors": ["food"], "unit_ids": [uid], "channels": ["fair", "whatsapp"],
                    "venue": "Tenali market yard", "district": "guntur"}).json()
    assert c["state"] == "running"
    assert client.post("/api/v1/market/campaigns", headers=coord, json={**{k: c[k] for k in ("name", "sectors", "unit_ids", "channels")},
                       "start_date": "2026-11-10", "end_date": "2026-11-01"}).status_code == 422
    o = client.post(f"/api/v1/market/routes/{rid}/order", headers=h, json={"lines": [{"listing_id": snack["id"], "qty": 120, "price": 35}]}).json()
    assert o["source"] == "enquiry" and o["amount"] == 4200
    assert client.get(f"/api/v1/market/enquiries/{e['id']}", headers=coord).json()["status"] == "won"
    fair = client.post(f"/api/v1/market/units/{uid}/orders", headers=h, json={"customer": {"name": "Mela visitor", "mobile": "9849000778"},
                       "lines": [{"listing_id": snack["id"], "qty": 10}], "status": "paid", "payment_mode": "upi", "campaign_id": c["id"]}).json()
    res = client.get(f"/api/v1/market/campaigns/{c['id']}", headers=coord).json()
    assert res["results"]["app_orders"] == 1 and res["results"]["app_sales"] == fair["amount"] and res["units"][0]["sales"] == fair["amount"]
    msg = client.post(f"/api/v1/market/campaigns/{c['id']}/message", headers=coord).json()
    assert "Tenali market yard" in msg["message_en"] and msg["message_te"]

    # Reports
    rep = client.get("/api/v1/market/reports/summary", headers=coord).json()
    assert rep["sales_total"] >= fair["amount"] and rep["enquiries"]["won"] >= 1 and any(t["id"] == uid for t in rep["top_units"])
    assert any(s["label"] == "enquiry" for s in rep["by_source"])
