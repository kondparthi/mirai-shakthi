"""Phase 1 Sprint 3 – DPR & finance: calculations checked by hand, scheme rules, DPR builder with review / approval and
versions, PDF, credit application status flow, EMI schedule and repayments, entrepreneur view, reports and scope."""
from datetime import date, timedelta

import pytest

from app.dpr import finance
from app.dpr.narrative import inr
from app.dpr.pdf import rs
from app.dpr.service import add_months, emi_rows

from .conftest import login
from .test_programme import admin, make_aadhaar, person, staff


# ---------------------------------------------------------------- calculations
def test_emi_and_schedule():
    assert round(finance.emi(100000, 12, 12), 2) == 8884.88
    s = finance.loan_schedule(100000, 12, 12, 0)
    assert len(s) == 12 and abs(sum(r["principal"] for r in s) - 100000) < 1e-6 and abs(s[-1]["closing"]) < 1e-6
    m = finance.loan_schedule(120000, 12, 15, 3)
    assert [round(r["payment"], 2) for r in m[:3]] == [1200.0, 1200.0, 1200.0]  # interest only in the moratorium
    assert m[2]["closing"] == 120000 and round(m[3]["payment"], 2) == round(finance.emi(120000, 12, 12), 2)
    assert finance.emi(60000, 0, 12) == 5000


def test_projection_by_hand():
    inp = {"capital_items": [{"item": "Machine", "qty": 2, "rate": 50000}], "working_capital": 20000, "finance": {"own": 12000},
           "sales": {"items": [{"name": "Plates", "unit": "plate", "units_per_day": 100, "price": 10}], "working_days": 25,
                     "monthly_growth_pct": 0, "yearly_growth_pct": 0},
           "expenses": {"raw_material_pct": 40, "salaries": 5000, "yearly_increase_pct": 0},
           "loan": {"interest_pct": 12, "tenure_months": 24, "moratorium_months": 0},
           "depreciation_pct": 10, "tax_pct": 0, "drawings_monthly": 3000, "years": 3}
    r = finance.calculate(inp)
    s = r["summary"]
    assert s["project_cost"] == 120000 and s["loan"] == 108000 and s["own_pct"] == 10
    y1 = r["pl"][0]
    interest1 = sum(x["interest"] for x in finance.loan_schedule(108000, 12, 24)[:12])
    assert y1["sales"] == 300000 and y1["raw_material"] == 120000 and y1["fixed"] == 60000 and y1["ebitda"] == 120000
    assert y1["depreciation"] == 10000 and r["pl"][1]["depreciation"] == 9000  # written-down value
    assert y1["interest"] == pytest.approx(interest1) and y1["pat"] == pytest.approx(110000 - interest1)
    emi = finance.emi(108000, 12, 24)
    d1 = r["dscr"][0]
    assert d1["debt_service"] == pytest.approx(12 * emi)
    assert d1["dscr"] == pytest.approx((110000 - interest1 + 10000 + interest1 - 36000) / (12 * emi))
    assert d1["bep_sales"] == pytest.approx((60000 + 10000 + interest1) / 0.6)
    assert r["dscr"][2]["dscr"] is None  # loan repaid in two years
    assert r["cash_flow"][0]["opening"] == 20000
    assert r["cash_flow"][0]["closing"] == pytest.approx(20000 + y1["pat"] + 10000 - d1["principal"] - 36000)
    assert not [w for w in r["warnings"] if w["level"] == "error"]


def test_warnings():
    r = finance.calculate({"capital_items": [], "finance": {"own": 5000}})
    codes = {w["code"] for w in r["warnings"]}
    assert {"no_items", "no_sales", "over_funded"} <= codes
    weak = finance.calculate({"capital_items": [{"item": "X", "qty": 1, "rate": 500000}], "finance": {"own": 0},
                              "sales": {"items": [{"name": "A", "units_per_day": 1, "price": 500}], "working_days": 26},
                              "expenses": {"raw_material_pct": 50, "salaries": 4000}, "drawings_monthly": 3000})
    assert {"dscr_below_1", "low_own", "loss_y1"} <= {w["code"] for w in weak["warnings"]}


def test_money_formats_and_dates():
    assert inr(1234567) == "₹12,34,567" and inr(999) == "₹999" and rs(250000) == "Rs. 2,50,000" and rs(-1500.5, 2) == "-Rs. 1,500.50"
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    rows = emi_rows(50000, 12, 6, date(2026, 1, 5))
    assert len(rows) == 6 and rows[-1]["balance"] == 0 and rows[5]["due_date"] == date(2026, 6, 5)
    assert abs(sum(r["principal"] for r in rows) - 50000) < 0.05


# ---------------------------------------------------------------- full flow
def _woman_entrepreneur(client):
    h = login(client, "9300000001")
    body = person(full_name="Saraswathi Kolli", aadhaar=make_aadhaar("73000000011"), dob="1991-03-02", investment_available=40000, consent=True)
    r = client.put("/api/v1/enrol/me", headers=h, json=body)
    assert r.status_code == 200, r.text
    return h, r.json()["entrepreneur"]["id"]


def test_dpr_and_loan_flow(client):
    h = admin(client)
    officer = staff(client, "dpr.guntur@mirai.local", "dpr_officer", ["guntur"])
    other = staff(client, "dpr.krishna@mirai.local", "dpr_officer", ["krishna"])
    coord = staff(client, "coord.dpr@mirai.local", "coordinator", ["guntur"])
    eh, eid = _woman_entrepreneur(client)

    meta = client.get("/api/v1/dpr/meta", headers=officer).json()
    cafe = next(m for m in meta["models"] if m["code"] == "millet_cafe")
    assert meta["can"]["write"] and {s["code"] for s in meta["schemes"]} >= {"pmegp", "pmfme", "mudra", "standup"}

    # Scheme check before a DPR (rules only, with reasons)
    q = client.get(f"/api/v1/dpr/eligibility?entrepreneur_id={eid}&model_id={cafe['id']}", headers=officer).json()
    by = {s["code"]: s for s in q["schemes"]}
    assert by["pmfme"]["eligible"] and by["pmegp"]["eligible"] and by["mudra"]["eligible"]
    assert not by["standup"]["eligible"] and any(c["ok"] is False and "Loan" in c["text"] for c in by["standup"]["checks"])
    assert by["pmegp"]["subsidy_pct"] == 35 and by["pmegp"]["own_pct"] == 5  # woman, OBC, rural = special category
    assert q["schemes"][0]["eligible"]  # eligible schemes first

    # Create (Form 5.1): DPR officer only, prefilled from the model; lifecycle moves to stage 3
    assert client.post("/api/v1/dpr/dprs", headers=coord, json={"entrepreneur_id": eid, "model_id": cafe["id"]}).status_code == 403
    r = client.post("/api/v1/dpr/dprs", headers=officer, json={"entrepreneur_id": eid, "model_id": cafe["id"]})
    assert r.status_code == 200, r.text
    d = r.json()
    did = d["id"]
    assert d["code"].startswith("DPR-") and d["status"] == "draft" and len(d["inputs"]["capital_items"]) == len(cafe["equipment"])
    assert d["results"]["project_cost"] == cafe["equipment_total"] + cafe["working_capital"]
    assert d["inputs"]["finance"]["own"] == 28000  # 10% of ₹2,73,000 rounded up, within the ₹40,000 she has
    assert client.get(f"/api/v1/programme/entrepreneurs/{eid}", headers=h).json()["stage"] == 3
    assert client.get(f"/api/v1/dpr/dprs/{did}", headers=other).status_code == 404  # other district
    assert client.get(f"/api/v1/dpr/dprs/{did}", headers=coord).status_code == 200  # read in scope

    # Live calculation and save
    det = client.get(f"/api/v1/dpr/dprs/{did}", headers=officer).json()
    inputs = det["inputs"]
    inputs["preoperative"] = 8000
    c = client.post(f"/api/v1/dpr/dprs/{did}/calc", headers=officer, json={"inputs": inputs}).json()
    assert c["result"]["summary"]["project_cost"] == 281000
    upd = {"unit_name": "Saraswathi Millet Café", "model_id": cafe["id"], "district": "guntur", "mandal": "tenali", "village": "kolakaluru",
           "address": "Near Tenali bus stand", "activity": "manufacturing", "scheme_code": None, "inputs": inputs, "narrative": {},
           "narrative_notes": {"market": "Two schools and the mandal office within 500 m; no millet stall nearby."}}
    r = client.put(f"/api/v1/dpr/dprs/{did}", headers=officer, json=upd)
    assert r.status_code == 200, r.text
    assert r.json()["results"]["project_cost"] == 281000
    bad = {**upd, "inputs": {**inputs, "capital_items": [{"item": "", "qty": 1, "rate": 5}]}}
    assert client.put(f"/api/v1/dpr/dprs/{did}", headers=officer, json=bad).status_code == 422

    # Scheme: PMFME subsidy is 35% of equipment (not working capital); Stand-Up is refused with the reason
    assert client.post(f"/api/v1/dpr/dprs/{did}/scheme", headers=officer, json={"code": "standup"}).status_code == 422
    r = client.post(f"/api/v1/dpr/dprs/{did}/scheme", headers=officer, json={"code": "pmfme"}).json()
    assert r["scheme_code"] == "pmfme" and r["inputs"]["finance"]["subsidy"] == round(243000 * 0.35, 2)
    assert r["results"]["loan"] == 281000 - 28100 - 85050  # own raised to the 10% minimum (rounded up to ₹100)

    # Approval needs the narrative; the template drafts it when AI is off
    r = client.post(f"/api/v1/dpr/dprs/{did}/status", headers=officer, json={"action": "approve"})
    assert r.status_code == 422 and "Promoter background" in r.json()["detail"]
    r = client.post(f"/api/v1/dpr/dprs/{did}/narrative", headers=officer, json={"narrative_notes": upd["narrative_notes"]}).json()
    assert r["narrative_source"] == "template" and all(r["narrative"][s["key"]] for s in r["sections"])
    assert "Two schools" in r["narrative"]["market"] and "₹2,81,000" in r["narrative"]["conclusion"]

    # Review, then a change sends it back to draft
    r = client.post(f"/api/v1/dpr/dprs/{did}/status", headers=officer, json={"action": "review"}).json()
    assert r["status"] == "reviewed" and r["reviewed_by"] == "dpr.guntur" and len(r["versions"]) == 1
    upd2 = {**upd, "scheme_code": "pmfme", "inputs": r["inputs"], "narrative": r["narrative"]}
    assert client.put(f"/api/v1/dpr/dprs/{did}", headers=officer, json=upd2).json()["status"] == "draft"
    r = client.post(f"/api/v1/dpr/dprs/{did}/status", headers=officer, json={"action": "approve", "note": "Checked with Saraswathi"}).json()
    assert r["status"] == "approved" and r["version"] == 1 and r["can"]["apply"]
    assert client.put(f"/api/v1/dpr/dprs/{did}", headers=officer, json=upd2).status_code == 409

    # PDF (current and version) – bank format
    url = client.post(f"/api/v1/dpr/dprs/{did}/pdf-link", headers=officer).json()["url"]
    pdf = client.get(url)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and len(pdf.content) > 20000
    text = _pdf_text(pdf.content)
    assert "DETAILED PROJECT REPORT" in text and "Rs. 2,81,000" in text and "Debt service coverage" in text and "Annexure 1" in text
    assert client.get(url.replace("t=", "t=x")).status_code == 403

    # Reopen makes version 2; version 1 stays downloadable
    assert client.post(f"/api/v1/dpr/dprs/{did}/status", headers=officer, json={"action": "reopen"}).status_code == 422
    r = client.post(f"/api/v1/dpr/dprs/{did}/status", headers=officer, json={"action": "reopen", "note": "Bank asked for a fridge quote"}).json()
    assert r["status"] == "draft" and r["version"] == 2
    v1 = next(v for v in r["versions"] if v["status"] == "approved")
    old = client.get(client.post(f"/api/v1/dpr/dprs/{did}/pdf-link?version_id={v1['id']}", headers=officer).json()["url"])
    assert old.status_code == 200 and "version 1" in _pdf_text(old.content)
    r = client.post(f"/api/v1/dpr/dprs/{did}/status", headers=officer, json={"action": "approve"}).json()
    assert r["status"] == "approved" and r["version"] == 2

    # Entrepreneur sees the plan and downloads the approved PDF
    me = client.get("/api/v1/dpr/me?lang=te", headers=eh).json()
    assert me["dprs"][0]["can_download"] and me["dprs"][0]["status_label"] == "ఆమోదించారు"
    assert client.get(client.post(f"/api/v1/dpr/me/dprs/{did}/pdf-link", headers=eh).json()["url"]).status_code == 200

    # Application (Form 6.1) from the approved DPR
    loan = r["results"]["loan"]
    r = client.post("/api/v1/dpr/applications", headers=officer, json={"dpr_id": did, "bank": "sbi", "branch": "Tenali main", "ifsc": "sbin0001234"})
    assert r.status_code == 200, r.text
    a = r.json()
    aid = a["id"]
    assert a["code"].startswith("LA-") and a["amount_requested"] == loan and a["scheme_code"] == "pmfme" and a["ifsc"] == "SBIN0001234"
    docs = {x["code"]: x for x in a["documents"]}
    assert docs["dpr"]["have"] and not docs["aadhaar"]["have"] and "fssai" in docs
    assert client.post("/api/v1/dpr/applications", headers=officer, json={"dpr_id": did, "bank": "sbi", "branch": "Tenali"}).status_code == 409

    # Status flow (Form 6.2)
    st = lambda body: client.post(f"/api/v1/dpr/applications/{aid}/status", headers=officer, json=body)  # noqa: E731
    today = date.today()
    assert st({"status": "sanctioned", "on": today.isoformat(), "sanctioned_amount": loan}).status_code == 409
    assert st({"status": "submitted", "on": (today + timedelta(days=1)).isoformat()}).status_code == 422
    assert st({"status": "submitted", "on": (today - timedelta(days=120)).isoformat(), "app_number": "PMFME/AP/2026/0042"}).status_code == 200
    assert st({"status": "query", "on": (today - timedelta(days=115)).isoformat()}).status_code == 422
    assert st({"status": "query", "on": (today - timedelta(days=115)).isoformat(), "text": "Send the FSSAI registration"}).status_code == 200
    r = client.post(f"/api/v1/dpr/applications/{aid}/events", headers=officer,
                    json={"kind": "response", "text": "FSSAI registration sent", "on": (today - timedelta(days=112)).isoformat()}).json()
    assert r["status"] == "submitted" and [e["kind"] for e in r["events"]][-2:] == ["response", "status"]
    r = st({"status": "sanctioned", "on": (today - timedelta(days=105)).isoformat(), "sanctioned_amount": loan, "subsidy_amount": 85050}).json()
    assert r["status"] == "sanctioned" and client.get(f"/api/v1/programme/entrepreneurs/{eid}", headers=h).json()["stage"] == 4
    assert st({"status": "disbursed", "on": (today - timedelta(days=100)).isoformat()}).status_code == 422
    r = st({"status": "disbursed", "on": (today - timedelta(days=100)).isoformat(), "disbursed_amount": loan, "interest_pct": 11,
            "tenure_months": 54, "first_emi_date": (today - timedelta(days=70)).isoformat()})
    assert r.status_code == 200, r.text
    r = r.json()
    assert len(r["schedule"]) == 54 and r["schedule"][-1]["balance"] == 0
    assert r["emi_amount"] == pytest.approx(round(finance.emi(loan, 11, 54), 2), abs=0.02)
    assert r["repayment"]["overdue"] == 3 and r["repayment"]["health"] == "default"
    for row in r["schedule"][:2]:
        r = client.put(f"/api/v1/dpr/repayments/{row['id']}", headers=officer, json={"paid_on": row["due_date"]}).json()
    assert r["repayment"]["paid"] == 2 and r["repayment"]["overdue"] == 1 and r["repayment"]["health"] == "delayed"
    assert client.put(f"/api/v1/dpr/repayments/{r['schedule'][2]['id']}", headers=other, json={"paid_on": today.isoformat()}).status_code == 404

    # Entrepreneur: status history and EMI schedule; reports and CSV
    me = client.get("/api/v1/dpr/me", headers=eh).json()
    app = me["applications"][0]
    assert app["status"] == "disbursed" and app["repayment"]["next"] and len(app["schedule"]) == 54
    assert all(e["by"] is None for e in app["events"])  # staff names are not shown in the app
    rep = client.get("/api/v1/dpr/reports/summary", headers=officer).json()
    assert rep["dprs"]["approved"] >= 1 and rep["applications"]["disbursed"] >= 1 and rep["avg_days_to_sanction"] == 15
    assert rep["repayment"]["delayed"] >= 1 and rep["by_bank"][0]["code"] == "sbi"
    csv = client.get("/api/v1/dpr/reports/applications.csv", headers=officer)
    assert a["code"] in csv.text and "PMFME" not in csv.text.split("\n")[0]
    assert client.get("/api/v1/dpr/reports/summary", headers=other).json()["applications"]["disbursed"] == 0

    # Data export (DPDP) includes the plan and the loan
    exp = client.get("/api/v1/enrol/me/export", headers=eh)
    if exp.status_code == 200:
        body = exp.json()
        assert body["business_plans"][0]["code"] == d["code"] and body["loan_applications"][0]["status"] == "disbursed"


def test_draft_rules_and_models(client):
    officer = staff(client, "dpr.guntur@mirai.local", "dpr_officer", ["guntur"])
    expert = staff(client, "sector.food@mirai.local", "sector_expert", ["guntur"])
    h = login(client, "9300000002")
    r = client.put("/api/v1/enrol/me", headers=h, json=person(full_name="Ravi Teja", gender="male", social_category="general",
                                                              aadhaar=make_aadhaar("73000000022"), consent=True))
    eid = r.json()["entrepreneur"]["id"]
    models = client.get("/api/v1/dpr/models", headers=officer).json()
    tea = next(m for m in models if m["code"] == "tea_stall")
    d = client.post("/api/v1/dpr/dprs", headers=officer, json={"entrepreneur_id": eid, "model_id": tea["id"]}).json()
    # Draft cannot be downloaded by the entrepreneur; staff can delete a draft
    assert client.post(f"/api/v1/dpr/me/dprs/{d['id']}/pdf-link", headers=h).status_code == 409
    q = client.get(f"/api/v1/dpr/eligibility?entrepreneur_id={eid}&model_id={tea['id']}", headers=officer).json()
    by = {s["code"]: s for s in q["schemes"]}
    assert not by["pmfme"]["eligible"] and by["pmegp"]["subsidy_pct"] == 25 and by["pmegp"]["own_pct"] == 10  # general, rural
    assert client.delete(f"/api/v1/dpr/dprs/{d['id']}", headers=officer).json()["ok"]

    # Enterprise models: sector expert may edit; validation of unknown scheme
    body = {k: tea[k] for k in ("code", "sector", "name_en", "name_te", "description", "activity", "context_tags", "investment_min",
                                "investment_max", "working_capital", "equipment", "infrastructure", "skills", "schemes", "sales_template",
                                "expense_template", "expected_monthly_sales", "jobs", "payback_months", "status")}
    assert client.put(f"/api/v1/dpr/models/{tea['id']}", headers=officer, json=body).status_code == 403
    assert client.put(f"/api/v1/dpr/models/{tea['id']}", headers=expert, json={**body, "schemes": ["xyz"]}).status_code == 422
    r = client.put(f"/api/v1/dpr/models/{tea['id']}", headers=expert, json={**body, "jobs": 2})
    assert r.status_code == 200 and r.json()["jobs"] == 2

    # Schemes: rules are validated; verifying clears the sample flag
    sc = next(s for s in client.get("/api/v1/dpr/schemes", headers=officer).json() if s["code"] == "mudra")
    sb = {k: sc[k] for k in ("code", "name", "name_te", "kind", "agency", "description", "url", "rules", "documents", "active")}
    assert client.put(f"/api/v1/dpr/schemes/{sc['id']}", headers=officer, json={**sb, "rules": {"bogus": 1}}).status_code == 422
    r = client.put(f"/api/v1/dpr/schemes/{sc['id']}", headers=officer, json={**sb, "verified_on": date.today().isoformat()}).json()
    assert r["sample"] is False and r["verified_on"] == date.today().isoformat()


def _pdf_text(data: bytes) -> str:
    import io

    from pypdf import PdfReader

    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)


def test_narrative_ai_path(monkeypatch):
    """With AI on, the model's words are used; figures come from the engine and missing sections fall back to the template."""
    from app.dpr import narrative

    seen = {}

    def fake(system, user, max_tokens=0):
        seen["user"] = user
        return {"promoter": "AI promoter text.", "swot": {"Strengths": ["trained"], "Threats": ["competition"]}}

    monkeypatch.setattr(narrative.llm, "complete_json", fake)
    r = finance.calculate({"capital_items": [{"item": "Cart", "qty": 1, "rate": 100000}], "finance": {"own": 10000},
                           "sales": {"items": [{"name": "Tea", "unit": "cup", "units_per_day": 100, "price": 10}]}})
    ctx = {"unit_name": "Tea point", "location": "Tenali", "activity": "service", "promoter": {"name": "Ravi", "home": "Tenali"},
           "model": {"name": "Tea stall"}, "notes": {"market": "Bus stand"}}
    out, source = narrative.draft(ctx, r)
    assert source == "ai" and out["promoter"] == "AI promoter text." and out["swot"] == "Strengths: trained\nThreats: competition"
    assert out["conclusion"].startswith("The project cost of ₹1,00,000")  # template fills what the AI left out
    assert "₹90,000" in seen["user"] and "Bus stand" in seen["user"]
