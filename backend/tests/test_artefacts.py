from datetime import date, timedelta

from app.artefacts.cashflow import CashflowIn, calculate, inr

from .conftest import PROFILE, login


def _download(client, h, aid):
    link = client.post(f"/api/v1/artefacts/{aid}/link", headers=h).json()["url"]
    return client.get(link)


def test_inr_grouping():
    assert inr(1234567) == "12,34,567" and inr(999) == "999" and inr(-150000) == "-1,50,000" and inr(100000) == "1,00,000"


def test_cashflow_calculations():
    today = date(2026, 10, 1)
    data = CashflowIn(as_of=today, stock_value=20000, months=[
        {"month": "2026-08", "cash_sales": 60000, "credit_sales": 40000, "raw_material": 50000, "wages": 20000, "rent": 5000},
        {"month": "2026-07", "cash_sales": 50000, "credit_sales": 50000, "raw_material": 70000, "wages": 20000, "rent": 5000, "power": 10000},
    ], receivables=[{"customer": "Shop A", "amount": 30000, "invoice_date": today - timedelta(days=70)},
                    {"customer": "Shop B", "amount": 10000, "invoice_date": today - timedelta(days=10)}],
        payables=[{"supplier": "Mill", "amount": 15000, "due_date": today + timedelta(days=10)}],
        loans=[{"lender": "Bank", "outstanding": 200000, "emi": 8000}])
    o = calculate(data)
    assert [m["month"] for m in o["months"]] == ["2026-07", "2026-08"]            # sorted
    assert o["totals"] == {"sales": 200000, "expenses": 180000, "profit": 20000, "cash_sales": 110000, "credit_sales": 90000}
    assert o["months"][0]["profit"] == -5000                                       # July loss
    assert o["ratios"]["margin_pct"] == 10.0 and o["ratios"]["credit_share_pct"] == 45.0
    assert o["receivables"]["ageing"] == {"0-30": 10000, "31-60": 0, "61-90": 30000, "90+": 0}
    assert o["receivables"]["overdue"][0]["customer"] == "Shop A"
    assert o["working_capital"]["net"] == 20000 + 40000 - 15000
    assert o["ratios"]["emi_to_profit_pct"] == 80.0                                # 8000 / 10000 average profit
    levels = {i["level"] for i in o["insights"]}
    assert "alert" in levels                                                       # overdue + EMI burden
    assert any("Loss in 1 month" in i["text"] for i in o["insights"])


def test_roadmap_checklist_and_pdf_download(client):
    h = login(client, "9200000001")
    client.put("/api/v1/profile", json=PROFILE, headers=h)
    ans = client.post("/api/v1/guidance/ask", json={"question": "Which registrations do I need?"}, headers=h).json()
    sid = ans["session_id"]
    client.patch(f"/api/v1/guidance/sessions/{sid}/gaps/udyam", json={"status": "done"}, headers=h)
    r = client.post("/api/v1/artefacts/roadmap", json={"session_id": sid}, headers=h).json()
    assert r["kind"] == "roadmap" and any(s["done"] for s in r["outputs"]["steps"])
    c = client.post("/api/v1/artefacts/checklist", json={"session_id": sid}, headers=h).json()
    names = [d["name"].lower() for d in c["outputs"]["documents"]]
    assert any("aadhaar" in n for n in names)
    for aid in (r["id"], c["id"]):
        res = _download(client, h, aid)
        assert res.status_code == 200 and res.headers["content-type"] == "application/pdf" and res.content[:4] == b"%PDF"
    assert len(client.get("/api/v1/artefacts", headers=h).json()) == 2


def test_cashflow_and_jd_pdfs(client):
    h = login(client, "9200000002")
    client.put("/api/v1/profile", json=PROFILE, headers=h)
    cf = client.post("/api/v1/artefacts/cashflow", headers=h, json={
        "months": [{"month": f"2026-0{m}", "cash_sales": 30000 + m * 1000, "credit_sales": 10000, "raw_material": 18000, "wages": 9000}
                   for m in range(4, 10)],
        "receivables": [{"customer": "Hotel", "amount": 12000, "invoice_date": "2026-07-01"}], "stock_value": 15000}).json()
    assert cf["outputs"]["totals"]["sales"] > 0
    assert _download(client, h, cf["id"]).content[:4] == b"%PDF"
    roles = client.get("/api/v1/artefacts/roles", headers=h).json()
    tpl = next(x for x in roles if x["key"] == "sales_executive")
    jd = client.post("/api/v1/artefacts/jd", headers=h, json={**{k: tpl[k] for k in ("title", "purpose", "duties", "skills", "qualification")},
                                                               "role_key": "sales_executive", "openings": 2, "pay": "Rs. 12,000 + incentive"}).json()
    assert jd["outputs"]["onboarding"]
    assert _download(client, h, jd["id"]).content[:4] == b"%PDF"
    # invalid month format is rejected
    assert client.post("/api/v1/artefacts/cashflow", headers=h, json={"months": [{"month": "July"}]}).status_code == 422


def test_download_links_are_private(client):
    h1 = login(client, "9200000003")
    client.put("/api/v1/profile", json=PROFILE, headers=h1)
    cf = client.post("/api/v1/artefacts/cashflow", headers=h1, json={"months": [{"month": "2026-09", "cash_sales": 1000}]}).json()
    h2 = login(client, "9200000004")
    assert client.post(f"/api/v1/artefacts/{cf['id']}/link", headers=h2).status_code == 404
    link = client.post(f"/api/v1/artefacts/{cf['id']}/link", headers=h1).json()["url"]
    other_id = link.replace(f"/artefacts/{cf['id']}/", f"/artefacts/{cf['id'] + 999}/")
    assert client.get(other_id).status_code in (403, 404)
    assert client.get(f"/api/v1/artefacts/{cf['id']}/pdf?t=not-a-valid-token").status_code == 401
