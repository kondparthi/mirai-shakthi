"""Phase 1 Sprint 6 – daily business management (M9): sales and expenses (Form 9.1) with stock, credit sales to collect,
spoken entries, receipts with UPI QR, orders flowing into the books, summaries, monthly summaries with alerts, EMI
tracker, readiness and access rules."""
from datetime import date, timedelta

from sqlalchemy import select

from app.books.service import month_key
from app.db import SessionLocal
from app.models_p3 import Repayment
from app.models_p4 import Unit
from app.models_p6 import LedgerEntry, MonthlySummary

from .test_market import _unit
from .test_programme import staff
from .test_setup import _sanctioned_unit


def test_books_flow(client):
    h, uid, code = _unit(client, "9500000101", "75000000101")
    other_h, other_uid, _ = _unit(client, "9500000102", "75000000102", name="Other Café")
    far = staff(client, "coord.kurnool.b@mirai.local", "coordinator", ["kurnool"])
    coord = staff(client, "coord.guntur.b@mirai.local", "coordinator", ["guntur"])
    B = "/api/v1/books"

    # Access
    assert client.get(f"{B}/units/{other_uid}/meta", headers=h).status_code == 404
    assert client.get(f"{B}/units/{uid}/meta", headers=far).status_code == 404
    meta = client.get(f"{B}/units/{uid}/meta", headers=h).json()
    assert {c["code"] for c in meta["categories"]["sale"]} >= {"counter", "orders"} and "loan_emi" in {c["code"] for c in meta["categories"]["expense"]}
    assert len(meta["stock"]) == 6  # starter stock from the model
    milk = next(s for s in meta["stock"] if s["name"] == "Milk")
    assert client.get(f"{B}/units/{uid}/meta?lang=te", headers=h).json()["categories"]["sale"][0]["label"] == "కౌంటర్ అమ్మకాలు"

    # Expense with stock: 10 litres of milk comes in
    today = date.today()
    e = lambda b: client.post(f"{B}/units/{uid}/entries", headers=h, json={"on": today.isoformat(), "payment_mode": "cash", **b})  # noqa: E731
    assert e({"kind": "expense", "amount": 500, "category": "nonsense"}).status_code == 422
    assert e({"kind": "expense", "amount": 500, "category": "milk", "payment_mode": "credit"}).status_code == 422
    assert client.post(f"{B}/units/{uid}/entries", headers=h, json={"kind": "sale", "amount": 5, "category": "counter",
                                                                    "on": (today + timedelta(days=1)).isoformat()}).status_code == 422
    assert e({"kind": "expense", "amount": 500, "category": "milk", "stock_item_id": milk["id"]}).status_code == 422  # qty needed
    x1 = e({"kind": "expense", "amount": 500, "category": "milk", "stock_item_id": milk["id"], "qty": 10}).json()
    assert x1["amount"] == 500 and x1["category_label"] == "Milk"
    stock = client.get(f"{B}/units/{uid}/stock", headers=h).json()
    assert next(s for s in stock if s["id"] == milk["id"])["qty"] == 10
    # Use 7 litres → low stock (reorder at 5)
    client.post(f"{B}/stock/{milk['id']}/move", headers=h, json={"kind": "out", "qty": 7})
    assert client.post(f"{B}/stock/{milk['id']}/move", headers=h, json={"kind": "out", "qty": 70}).status_code == 422
    sm = client.get(f"{B}/units/{uid}/summary", headers=h).json()
    assert [s["name"] for s in sm["low_stock"]][:1] and "Milk" in [s["name"] for s in sm["low_stock"]]

    # Sales: cash and UPI; a credit sale needs the customer and is to collect
    e({"kind": "sale", "amount": 1600, "category": "counter"})
    e({"kind": "sale", "amount": 900, "category": "counter", "payment_mode": "upi"})
    assert e({"kind": "sale", "amount": 1200, "category": "catering", "payment_mode": "credit"}).status_code == 422
    cr = e({"kind": "sale", "amount": 1200, "category": "catering", "payment_mode": "credit", "customer": {"name": "Govt school", "mobile": "9849000111"}}).json()
    assert cr["due_date"] == (today + timedelta(days=7)).isoformat()
    # Taken home and EMI are not business costs
    e({"kind": "expense", "amount": 1000, "category": "drawings"})
    sm = client.get(f"{B}/units/{uid}/summary", headers=h).json()
    assert sm["sales"] == 3700 and sm["expenses"] == 500 and sm["profit"] == 3200 and sm["drawings"] == 1000
    assert sm["to_collect"] == 1200 and sm["recorded_today"] and sm["by_category"]
    assert client.get(f"{B}/units/{uid}/summary?period=month", headers=h).json()["daily"]

    # Receivables → WhatsApp reminder with a receipt link; receipt PDF is public with the token only
    rec = client.get(f"{B}/units/{uid}/receivables", headers=h).json()
    assert len(rec) == 1 and rec[0]["reminder_link"].startswith("https://wa.me/919849000111")
    client.put(f"{B}/units/{uid}/settings", headers=h, json={"upi_id": "9500000101@ybl"})
    assert client.put(f"{B}/units/{uid}/settings", headers=h, json={"upi_id": "not a upi"}).status_code == 422
    link = client.post(f"{B}/entries/{cr['id']}/receipt", headers=h).json()
    assert "wa.me/919849000111" in link["share_link"]
    pdf = client.get(link["url"])
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert client.get(f"/api/v1/public/receipts/{cr['id']}.pdf?t=xxxxxxxxxxxx").status_code == 403
    assert client.post(f"{B}/entries/{x1['id']}/receipt", headers=h).status_code == 422  # expenses have no receipt
    assert client.post(f"{B}/entries/{cr['id']}/collect", headers=h, json={"mode": "upi"}).json()["ok"]
    assert client.post(f"{B}/entries/{cr['id']}/collect", headers=h, json={"mode": "upi"}).status_code == 409
    assert client.get(f"{B}/units/{uid}/receivables", headers=h).json() == []

    # Delete reverses the stock movement
    milk_qty = lambda: next(s for s in client.get(f"{B}/units/{uid}/stock", headers=h).json() if s["id"] == milk["id"])["qty"]  # noqa: E731
    x2 = e({"kind": "expense", "amount": 100, "category": "milk", "stock_item_id": milk["id"], "qty": 2}).json()
    assert milk_qty() == 5
    assert client.delete(f"{B}/entries/{x2['id']}", headers=h).json()["ok"] and milk_qty() == 3

    # Spoken entries → a draft to check
    d = client.post(f"{B}/units/{uid}/parse", headers=h, json={"text": "bought 10 litres milk 500 rupees upi"}).json()
    assert d["kind"] == "expense" and d["amount"] == 500 and d["qty"] == 10 and d["category"] == "milk" and d["payment_mode"] == "upi"
    assert d["stock_item_id"] == milk["id"]
    d = client.post(f"{B}/units/{uid}/parse", headers=h, json={"text": "ఈరోజు కౌంటర్ అమ్మకాలు 2400 రూపాయలు వచ్చింది"}).json()
    assert d["kind"] == "sale" and d["amount"] == 2400 and d["category"] == "counter"

    # Orders from the shop flow into the books (M8 → M9)
    lst = client.post(f"/api/v1/market/units/{uid}/listings/from-model", headers=h).json()
    o = client.post(f"/api/v1/market/units/{uid}/orders", headers=h, json={"customer": {"name": "Ramu", "mobile": "9849012399"},
                                                                          "lines": [{"listing_id": lst[0]["id"], "qty": 2}]}).json()
    st = lambda b: client.post(f"/api/v1/market/orders/{o['id']}/status", headers=h, json=b)  # noqa: E731
    st({"status": "delivered", "payment_mode": "credit"})
    with SessionLocal() as db:
        le = db.scalar(select(LedgerEntry).where(LedgerEntry.order_id == o["id"]))
        assert le and le.payment_mode == "credit" and le.category == "orders" and le.source == "order" and le.amount == o["amount"]
    assert client.delete(f"{B}/entries/{le.id}", headers=h).status_code == 409
    st({"status": "paid", "payment_mode": "cash"})
    with SessionLocal() as db:
        assert db.scalar(select(LedgerEntry).where(LedgerEntry.order_id == o["id"])).collected_on == today
    o2 = client.post(f"/api/v1/market/units/{uid}/orders", headers=h, json={"customer": {"name": "Ramu", "mobile": "9849012399"},
                                                                           "lines": [{"listing_id": lst[0]["id"], "qty": 1}], "status": "paid", "payment_mode": "upi"}).json()
    with SessionLocal() as db:
        assert db.scalar(select(LedgerEntry).where(LedgerEntry.order_id == o2["id"])).payment_mode == "upi"

    # Staff in scope can add; other entrepreneurs cannot
    assert client.post(f"{B}/units/{uid}/entries", headers=coord, json={"kind": "sale", "amount": 100, "category": "counter", "on": today.isoformat()}).status_code == 200
    assert client.post(f"{B}/units/{uid}/entries", headers=other_h, json={"kind": "sale", "amount": 100, "category": "counter", "on": today.isoformat()}).status_code == 404

    # Monthly summaries: past months close themselves; this month can be sent from the 25th
    with SessionLocal() as db:
        u = db.get(Unit, uid)
        u.launch_date = (today.replace(day=1) - timedelta(days=40)).replace(day=1)
        last = today.replace(day=1) - timedelta(days=3)
        db.add(LedgerEntry(unit_id=uid, kind="sale", on=last, amount=20000, category="counter", payment_mode="cash", source="manual"))
        db.add(LedgerEntry(unit_id=uid, kind="expense", on=last, amount=26000, category="milk", payment_mode="cash", source="manual"))
        db.commit()
    months = client.get(f"{B}/units/{uid}/months", headers=h).json()
    assert len(months) == 2 and months[0]["month"] == month_key(last) and months[0]["submitted_by"] == "auto"
    codes = {a["code"] for a in months[0]["alerts"]}
    assert "loss" in codes and "few_entries" in codes
    assert {a["code"] for a in months[1]["alerts"]} == {"no_entries"}
    r = client.post(f"{B}/units/{uid}/months/{month_key(last)}/submit", headers=h, json={"note": "Milk prices went up; raising prices next month"}).json()
    assert r["submitted_by"] == "owner" and r["note"].startswith("Milk")
    nxt = month_key(today.replace(day=28) + timedelta(days=10))
    assert client.post(f"{B}/units/{uid}/months/{nxt}/submit", headers=h, json={}).status_code == 422
    assert client.get(f"/api/v1/programme/entrepreneurs/{_eid(uid)}", headers=coord).json()["stage"] >= 6

    # Staff report: the month with alerts; mentor/staff review; out-of-scope staff see nothing
    rep = client.get(f"{B}/reports/months?month={month_key(last)}", headers=coord).json()
    row = next(x for x in rep["rows"] if x["unit"]["id"] == uid)
    assert row["sales"] == 20000 and row["alerts"] and rep["flagged"] >= 1
    assert all(x["unit"]["id"] != uid for x in client.get(f"{B}/reports/months?month={month_key(last)}", headers=far).json()["rows"])
    rv = client.post(f"{B}/months/{row['id']}/review", headers=coord, json={"note": "Visit to look at milk costs"}).json()
    assert rv["reviewed"] and rv["review_note"].startswith("Visit")
    assert client.post(f"{B}/months/{row['id']}/review", headers=far, json={"note": "x y"}).status_code == 404
    assert client.post(f"{B}/months/{row['id']}/review", headers=h, json={"note": "x y"}).status_code == 403
    live = client.get(f"{B}/reports/months?month={month_key(today)}", headers=coord).json()
    assert live["live"] and next(x for x in live["rows"] if x["unit"]["id"] == uid)["sales"] > 0

    # The person's data export includes their books
    body = client.get("/api/v1/enrol/me/export", headers=h).json()
    assert body["business_books"][0]["entries"]


def _eid(uid: int) -> int:
    with SessionLocal() as db:
        return db.get(Unit, uid).entrepreneur_id


def test_emi_tracker_and_readiness(client):
    officer = staff(client, "pm.books@mirai.local", "programme_manager", [])
    eh, eid, uid, d = _sanctioned_unit(client, officer, "9500000201", "75000000201")
    B = "/api/v1/books"
    # Readiness: bookkeeping is automatic now
    item = lambda: next(i for i in client.get(f"/api/v1/setup/units/{uid}", headers=officer).json()["checklist"] if i["key"] == "bookkeeping")  # noqa: E731
    assert item()["kind"] == "auto" and not item()["done"]
    assert client.get(f"{B}/units/{uid}/emi", headers=eh).json() == {"schedule": []}
    client.post(f"{B}/units/{uid}/entries", headers=eh, json={"kind": "expense", "amount": 300, "category": "gas", "on": date.today().isoformat()})
    assert item()["done"]

    # Loan disbursed → EMI tracker
    a = client.get(f"/api/v1/dpr/applications?dpr_id={d['id']}", headers=officer).json()
    aid = (a["rows"] if isinstance(a, dict) else a)[0]["id"]
    today = date.today()
    r = client.post(f"/api/v1/dpr/applications/{aid}/status", headers=officer,
                    json={"status": "disbursed", "on": today.isoformat(), "disbursed_amount": 200000, "interest_pct": 11,
                          "tenure_months": 36, "first_emi_date": (today + timedelta(days=30)).isoformat()})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:  # as if the loan came two months ago: the first EMI is 30 days overdue
        for rp in db.scalars(select(Repayment).where(Repayment.application_id == aid)):
            rp.due_date -= timedelta(days=60)
        db.commit()
    emi = client.get(f"{B}/units/{uid}/emi", headers=eh).json()
    assert emi["total"] == 36 and emi["paid"] == 0 and emi["overdue"] and emi["status"] in ("delayed", "default")
    first = emi["schedule"][0]
    assert client.post(f"{B}/units/{uid}/emi/{first['id']}/paid", headers=eh, json={"on": (today + timedelta(days=1)).isoformat()}).status_code == 422
    r = client.post(f"{B}/units/{uid}/emi/{first['id']}/paid", headers=eh, json={"on": today.isoformat(), "mode": "upi"}).json()
    assert r["paid"] == 1 and not r["overdue"]
    assert client.post(f"{B}/units/{uid}/emi/{first['id']}/paid", headers=eh, json={"on": today.isoformat()}).status_code == 409
    sm = client.get(f"{B}/units/{uid}/summary", headers=eh).json()
    assert sm["emi_paid"] == first["amount"] and sm["expenses"] == 300  # EMI not a business cost
    with SessionLocal() as db:
        assert db.scalar(select(LedgerEntry).where(LedgerEntry.repayment_id == first["id"])).category == "loan_emi"
        assert db.scalar(select(MonthlySummary).where(MonthlySummary.unit_id == uid)) is None  # not launched: nothing frozen
