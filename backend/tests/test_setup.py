"""Phase 1 Sprint 4 – enterprise set-up and procurement: unit created at sanction, suppliers, quotations (staff and supplier
portal), selection rules, purchase order PDF, delivery and installation with photos, assets, registrations, readiness, launch."""
import io
from datetime import date, timedelta

from PIL import Image

from app.db import SessionLocal
from app.models_p2 import ExternalCertificate

from .conftest import login
from .test_programme import admin, make_aadhaar, person, staff


def jpeg() -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (800, 600), (40, 120, 90)).save(b, "JPEG")
    return b.getvalue()


def _sanctioned_unit(client, officer, mobile, aadhaar11):
    """Entrepreneur → approved millet-café DPR → loan sanctioned. Returns (entrepreneur headers, entrepreneur id, unit id)."""
    eh = login(client, mobile)
    eid = client.put("/api/v1/enrol/me", headers=eh, json=person(full_name="Padma Rani", aadhaar=make_aadhaar(aadhaar11), consent=True)).json()["entrepreneur"]["id"]
    cafe = next(m for m in client.get("/api/v1/dpr/models", headers=officer).json() if m["code"] == "millet_cafe")
    d = client.post("/api/v1/dpr/dprs", headers=officer, json={"entrepreneur_id": eid, "model_id": cafe["id"]}).json()
    client.post(f"/api/v1/dpr/dprs/{d['id']}/narrative", headers=officer, json={"narrative_notes": {}})
    r = client.post(f"/api/v1/dpr/dprs/{d['id']}/status", headers=officer, json={"action": "approve"})
    assert r.status_code == 200, r.text
    a = client.post("/api/v1/dpr/applications", headers=officer, json={"dpr_id": d["id"], "bank": "sbi", "branch": "Tenali"}).json()
    today = date.today().isoformat()
    client.post(f"/api/v1/dpr/applications/{a['id']}/status", headers=officer, json={"status": "submitted", "on": today})
    r = client.post(f"/api/v1/dpr/applications/{a['id']}/status", headers=officer, json={"status": "sanctioned", "on": today, "sanctioned_amount": a["amount_requested"]})
    assert r.status_code == 200, r.text
    units = client.get(f"/api/v1/setup/units?entrepreneur_id={eid}", headers=officer).json()["rows"]
    assert len(units) == 1  # created automatically at sanction
    return eh, eid, units[0]["id"], d


def test_setup_flow(client):
    h = admin(client)
    officer = staff(client, "dpr.setup@mirai.local", "dpr_officer", ["guntur"])
    buyer = staff(client, "proc.guntur@mirai.local", "procurement", ["guntur"])
    coord = staff(client, "coord.setup@mirai.local", "coordinator", ["guntur"])
    far = staff(client, "proc.kurnool@mirai.local", "procurement", ["kurnool"])
    eh, eid, uid, d = _sanctioned_unit(client, officer, "9400000001", "74000000011")

    u = client.get(f"/api/v1/setup/units/{uid}", headers=buyer).json()
    assert u["code"].startswith("U-") and u["status"] == "setting_up" and u["dpr_code"] == d["code"]
    assert {r["kind"] for r in u["registration_list"]} == {"udyam", "fssai", "trade_licence"}
    assert len(u["dpr_items"]) == 8 and len(u["checklist"]) == 5 + 4
    assert client.get(f"/api/v1/setup/units/{uid}", headers=far).status_code == 404

    # Suppliers (Form 7.1): validation, approval, portal login
    bad = {"name": "X Traders", "contact_name": "Ravi", "mobile": "12345", "address": "Guntur", "items": ["Refrigerator"]}
    assert client.post("/api/v1/setup/suppliers", headers=buyer, json=bad).status_code == 422
    assert client.post("/api/v1/setup/suppliers", headers=coord, json={**bad, "mobile": "9440011111"}).status_code == 403
    sugg = client.get(f"/api/v1/setup/units/{uid}/suppliers?items=Refrigerator|Commercial gas stove with hood", headers=buyer).json()
    names = [s["name"] for s in sugg]
    assert "Sample: Andhra Kitchen Equipment" in names and "Sample: AgriDrone Solutions" not in names
    ake = next(s for s in sugg if s["name"] == "Sample: Andhra Kitchen Equipment")
    assert ake["covers"] == 2 and ake["rates"]["Refrigerator"] == 18500
    vkm = next(s for s in sugg if s["name"] == "Sample: Vijayawada Kitchen Mart")
    new = client.post("/api/v1/setup/suppliers", headers=buyer, json={**bad, "mobile": "9440011111", "gstin": "37ABCDE1234F1Z5"}).json()
    assert new["approved"] is False
    assert client.post(f"/api/v1/setup/suppliers/{new['id']}/login", headers=buyer, json={"email": "x@traders.in", "password": "Supplier@123"}).status_code == 409
    r = client.post(f"/api/v1/setup/suppliers/{ake['id']}/login", headers=buyer, json={"email": "ake@supplier.in", "password": "Supplier@123"})
    assert r.status_code == 200 and r.json()["has_login"]
    sh = {"Authorization": "Bearer " + client.post("/api/v1/auth/staff/login", json={"email": "ake@supplier.in", "password": "Supplier@123"}).json()["token"]}

    # Purchase (Form 7.2): ask two suppliers; one quotes in the portal, staff enter the other
    items = [{"item": "Refrigerator", "spec": "190 litre", "qty": 1, "est_rate": 18000},
             {"item": "Commercial gas stove with hood", "spec": "2 burners", "qty": 1, "est_rate": 18000}]
    assert client.post(f"/api/v1/setup/units/{uid}/purchases", headers=buyer, json={"title": "Kitchen", "items": items, "invited": [new["id"]]}).status_code == 422
    p = client.post(f"/api/v1/setup/units/{uid}/purchases", headers=buyer,
                    json={"title": "Kitchen equipment", "items": items, "invited": [ake["id"], vkm["id"]], "quote_by": (date.today() + timedelta(days=5)).isoformat()}).json()
    pid = p["id"]
    assert p["status"] == "rfq" and p["estimate"] == 36000
    me_s = client.get("/api/v1/supplier/me", headers=sh).json()
    assert me_s["open"][0]["id"] == pid and "deliver_to" not in me_s["open"][0]
    assert client.post(f"/api/v1/supplier/rfqs/{pid}/quote", headers=sh, json={"lines": [{"item": "Sofa", "qty": 1, "rate": 5}]}).status_code == 422
    r = client.post(f"/api/v1/supplier/rfqs/{pid}/quote", headers=sh, json={"lines": [{"item": "Refrigerator", "qty": 1, "rate": 18500},
                    {"item": "Commercial gas stove with hood", "qty": 1, "rate": 17500}], "delivery_days": 7, "warranty_months": 12})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/setup/purchases/{pid}/quotes", headers=buyer, json={"supplier_id": vkm["id"], "lines": [
        {"item": "Refrigerator", "qty": 1, "rate": 17900}, {"item": "Commercial gas stove with hood", "qty": 1, "rate": 17000}], "delivery_days": 20}).json()
    q = {x["supplier"]: x for x in r["quotes"]}
    assert q["Sample: Vijayawada Kitchen Mart"]["lowest"] and q["Sample: Vijayawada Kitchen Mart"]["amount"] == 34900
    assert q["Sample: Andhra Kitchen Equipment"]["vs_estimate_pct"] == 0.0 and q["Sample: Andhra Kitchen Equipment"]["source"] == "supplier"

    # Selection: not the lowest needs a reason; PO number and PDF
    ake_q = q["Sample: Andhra Kitchen Equipment"]["id"]
    assert client.post(f"/api/v1/setup/purchases/{pid}/order", headers=buyer, json={"quote_id": ake_q, "payment_source": "loan"}).status_code == 422
    assert client.post(f"/api/v1/setup/purchases/{pid}/order", headers=coord, json={"quote_id": ake_q, "payment_source": "loan", "reason": "x" * 12}).status_code == 403
    r = client.post(f"/api/v1/setup/purchases/{pid}/order", headers=buyer, json={"quote_id": ake_q, "payment_source": "loan",
                    "reason": "Delivers in 7 days instead of 20, with a 12-month warranty"}).json()
    assert r["status"] == "ordered" and r["po_number"].startswith("PO-") and r["po_amount"] == 36000 and r["supplier"] == "Sample: Andhra Kitchen Equipment"
    assert r["expected_delivery"] == (date.today() + timedelta(days=7)).isoformat()
    pdf = client.get(client.post(f"/api/v1/setup/purchases/{pid}/po-link", headers=buyer).json()["url"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.post(f"/api/v1/setup/purchases/{pid}/quotes", headers=buyer, json={"supplier_id": vkm["id"], "lines": items and [{"item": "Refrigerator", "qty": 1, "rate": 1}]}).status_code == 409

    # Supplier: sees the address only for the order they won; confirms and reports delivery
    order = client.get("/api/v1/supplier/me", headers=sh).json()["orders"][0]
    assert order["won"] and "Kolakaluru" in order["deliver_to"] and order["po_number"] == r["po_number"]
    assert client.post(f"/api/v1/supplier/orders/{pid}/confirm", headers=sh, json={"expected_delivery": (date.today() + timedelta(days=6)).isoformat()}).status_code == 200
    assert client.post(f"/api/v1/supplier/orders/{pid}/delivered", headers=sh, json={"on": date.today().isoformat()}).status_code == 200

    # Installation needs a photo; adds assets with warranty
    inst = {"on": date.today().isoformat(), "handover_note": "Installed and tested at the cart; owner trained on use.",
            "assets": [{"item": "Refrigerator", "serial_no": "RF-2026-778"}]}
    assert client.post(f"/api/v1/setup/purchases/{pid}/installed", headers=coord, json=inst).status_code == 422
    r = client.post(f"/api/v1/setup/purchases/{pid}/photos", headers=coord, files={"file": ("p.jpg", jpeg(), "image/jpeg")}, data={"caption": "Installed"})
    assert r.status_code == 200 and len(r.json()["photos"]) == 1
    assert client.post(f"/api/v1/setup/purchases/{pid}/installed", headers=coord, json=inst).json()["status"] == "installed"
    u = client.get(f"/api/v1/setup/units/{uid}", headers=coord).json()
    fridge = next(a for a in u["assets"] if a["item"] == "Refrigerator")
    assert fridge["serial_no"] == "RF-2026-778" and fridge["value"] == 18500 and fridge["warranty_until"] > date.today().isoformat()
    eq = next(i for i in u["checklist"] if i["key"] == "equipment")
    assert not eq["done"] and eq["note"].startswith("2 of 8 DPR items in place – still to come:")  # the cart etc. are still to come
    for it in u["dpr_items"][:]:
        if it["item"] not in ("Refrigerator", "Commercial gas stove with hood"):
            client.post(f"/api/v1/setup/units/{uid}/assets", headers=coord, json={"item": it["item"], "value": it["est_rate"], "qty": it["qty"]})
    eq = next(i for i in client.get(f"/api/v1/setup/units/{uid}", headers=coord).json()["checklist"] if i["key"] == "equipment")
    assert eq["done"] and eq["kind"] == "auto"

    # Registrations, readiness, launch
    regs = {r["kind"]: r for r in u["registration_list"]}
    assert client.put(f"/api/v1/setup/registrations/{regs['udyam']['id']}", headers=coord, json={"status": "done"}).status_code == 422
    for k, num in (("udyam", "UDYAM-AP-07-0012345"), ("fssai", "20126071000123")):
        assert client.put(f"/api/v1/setup/registrations/{regs[k]['id']}", headers=coord, json={"status": "done", "number": num}).status_code == 200
    r = client.post(f"/api/v1/setup/units/{uid}/launch", headers=coord, json={"launch_date": date.today().isoformat()})
    assert r.status_code == 422 and "Registrations done" in r.json()["detail"] and "Training completed" in r.json()["detail"]
    client.put(f"/api/v1/setup/registrations/{regs['trade_licence']['id']}", headers=coord, json={"status": "done", "number": "TL/TNL/2026/88"})
    with SessionLocal() as db:  # FSSAI certificate uploaded and verified during training counts as training done
        db.add(ExternalCertificate(entrepreneur_id=eid, kind="fssai", title="FSSAI food safety training", status="verified"))
        db.commit()
    assert client.put(f"/api/v1/setup/units/{uid}/readiness/equipment", headers=coord, json={"done": True}).status_code == 422
    u = client.get(f"/api/v1/setup/units/{uid}", headers=coord).json()
    for i in u["checklist"]:
        if i["kind"] == "manual":
            assert client.put(f"/api/v1/setup/units/{uid}/readiness/{i['key']}", headers=coord, json={"done": True}).status_code == 200
    assert client.post(f"/api/v1/setup/units/{uid}/readiness/working_capital/photo", headers=coord,
                       files={"file": ("w.jpg", jpeg(), "image/jpeg")}).json()["checklist"][3]["photo_url"]
    r = client.post(f"/api/v1/setup/units/{uid}/launch", headers=coord, json={"launch_date": date.today().isoformat()})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "launched" and client.get(f"/api/v1/programme/entrepreneurs/{eid}", headers=h).json()["stage"] == 5
    assert client.put(f"/api/v1/setup/units/{uid}", headers=coord, json={"name": u["name"], "status": "setting_up"}).status_code == 422

    # Entrepreneur view and document upload
    me = client.get("/api/v1/setup/me?lang=te", headers=eh).json()["units"][0]
    assert me["status"] == "launched" and me["purchase_list"][0]["status"] == "installed" and "selection_reason" not in me["purchase_list"][0]
    rid = me["registration_list"][0]["id"]
    assert client.post(f"/api/v1/setup/me/registrations/{rid}/file", headers=eh, files={"file": ("u.jpg", jpeg(), "image/jpeg")}).status_code == 200

    # Reports
    rep = client.get("/api/v1/setup/reports/summary", headers=buyer).json()
    assert rep["units"]["launched"] >= 1 and rep["ordered_value"] >= 36000 and rep["avg_days_to_install"] == 0
    assert rep["suppliers"][0]["name"] == "Sample: Andhra Kitchen Equipment" and rep["suppliers"][0]["on_time"] == 1


def test_single_quote_needs_reason_and_cancel(client):
    officer = staff(client, "dpr.setup@mirai.local", "dpr_officer", ["guntur"])
    buyer = staff(client, "proc.guntur@mirai.local", "procurement", ["guntur"])
    _, _, uid, _ = _sanctioned_unit(client, officer, "9400000002", "74000000022")
    sup = client.get("/api/v1/setup/suppliers?approved=true", headers=buyer).json()
    carts = next(s for s in sup if s["name"] == "Sample: Guntur Food Carts & Kiosks")
    p = client.post(f"/api/v1/setup/units/{uid}/purchases", headers=buyer, json={"title": "Cart", "items": [
        {"item": "Mobile food cart / kiosk with branding", "qty": 1, "est_rate": 150000}], "invited": [carts["id"]]}).json()
    r = client.post(f"/api/v1/setup/purchases/{p['id']}/quotes", headers=buyer, json={"supplier_id": carts["id"], "lines": [
        {"item": "Mobile food cart / kiosk with branding", "qty": 1, "rate": 148000}]}).json()
    qid = r["quotes"][0]["id"]
    assert client.post(f"/api/v1/setup/purchases/{p['id']}/order", headers=buyer, json={"quote_id": qid, "payment_source": "loan"}).status_code == 422
    assert client.post(f"/api/v1/setup/purchases/{p['id']}/order", headers=buyer, json={"quote_id": qid, "payment_source": "loan",
                       "reason": "Only approved cart maker in the district"}).json()["status"] == "ordered"
    assert client.post(f"/api/v1/setup/purchases/{p['id']}/cancel", headers=buyer).json()["status"] == "cancelled"
