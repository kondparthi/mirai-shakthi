"""Sprint 5 – bank statement upload for MicroFin."""
import io
from collections import defaultdict

import pytest

from app.artefacts.cashflow import CashflowIn, calculate
from app.artefacts.statement import StatementError, mask, parse_amount, parse_date, parse_statement
from seed import sample_statements as ss

from .conftest import PROFILE, login

TX = ss.transactions()
CREDITS = round(sum(t["credit"] for t in TX), 2)
DEBITS = round(sum(t["debit"] for t in TX), 2)

LAYOUTS = [
    ("a.xlsx", ss.layout_a_xlsx, None),
    ("b.csv", ss.layout_b_csv, None),
    ("c.xls", ss.layout_c_html_xls, None),
    ("d.csv", ss.layout_d_drcr_csv, None),
    ("e.pdf", ss.layout_e_pdf, ss.PDF_PASSWORD),
]


@pytest.mark.parametrize("name,make,password", LAYOUTS)
def test_every_layout_reads_all_transactions(name, make, password):
    r = parse_statement(name, make(TX), password)
    s = r["summary"]
    assert s["transactions"] == len(TX)
    assert s["credits"] == CREDITS and s["debits"] == DEBITS
    assert [m["month"] for m in r["months"]] == ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]


def test_categories_and_what_is_not_counted():
    r = parse_statement("a.xlsx", ss.layout_a_xlsx(TX))
    heads = {h["head"]: h for h in r["summary"]["by_head"]}
    assert heads["loan_in"]["counted_as"] is None and heads["loan_in"]["amount"] == 150000
    assert heads["emi"]["counted_as"] is None and heads["emi"]["count"] == 4
    assert heads["wages"]["amount"] == 36000 * 6
    assert heads["rent"]["amount"] == 8000 * 6
    assert heads["cash_sales"]["counted_as"] == "cash_sales"  # "CASH DEPOSIT BY SELF" is a cash sale, not a transfer
    # Sales in the form = customer receipts + cash deposits, without the loan or interest
    expected_sales = defaultdict(float)
    for t in TX:
        if t["credit"] and "LOAN" not in t["desc"] and "INT" not in t["desc"]:
            expected_sales[t["date"].strftime("%Y-%m")] += t["credit"]
    for m in r["months"]:
        assert m["cash_sales"] == pytest.approx(expected_sales[m["month"]])
    # Suggested loan from the EMIs
    assert r["loans"] == [{"lender": "Loan EMI seen in bank statement", "outstanding": 0, "emi": 4850.0}]
    # The months go straight into the cash-flow calculation
    out = calculate(CashflowIn(months=r["months"], loans=r["loans"]))
    assert out["totals"]["sales"] > 0 and len(out["months"]) == 6


def test_telugu_labels():
    r = parse_statement("b.csv", ss.layout_b_csv(TX), lang="te")
    assert {h["head"]: h["label"] for h in r["summary"]["by_head"]}["wages"] == "జీతాలు, వేతనాలు"
    assert any("నగదు విత్‌డ్రాల" in x for x in r["warnings"])


def test_account_numbers_are_masked_in_examples():
    r = parse_statement("b.csv", ss.layout_b_csv(TX))
    for ex in r["summary"]["examples"]:
        assert not any(len(run) >= 6 for run in "".join(c if c.isdigit() else " " for c in ex["desc"]).split())
    assert mask("NEFT/N0123456789/ABC") == "NEFT/NXX6789/ABC"


def test_values():
    assert parse_amount("1,23,456.50 Cr") == (123456.5, "cr")
    assert parse_amount("₹ 2,000.00") == (2000.0, None)
    assert parse_amount("(500.00)") == (500.0, "dr")
    assert parse_amount("") == (None, None)
    assert str(parse_date("05/04/26")) == "2026-04-05"
    assert str(parse_date("05-Apr-2026")) == "2026-04-05"
    assert str(parse_date("2026-04-05 10:22:01")) == "2026-04-05"
    assert parse_date("Opening Balance") is None


def test_helpful_errors():
    with pytest.raises(StatementError, match="password"):
        parse_statement("e.pdf", ss.layout_e_pdf(TX))  # no password given
    with pytest.raises(StatementError, match="not correct"):
        parse_statement("e.pdf", ss.layout_e_pdf(TX), "wrong")
    with pytest.raises(StatementError, match="transaction table"):
        parse_statement("x.csv", b"name,city\nLakshmi,Guntur\n")
    with pytest.raises(StatementError, match="Excel"):
        parse_statement("photo.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    # A scanned PDF (no text layer)
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.rect(50, 50, 400, 600, fill=1)
    c.showPage()
    c.save()
    with pytest.raises(StatementError, match="scanned"):
        parse_statement("scan.pdf", buf.getvalue())


def test_upload_endpoint_stores_nothing(client):
    h = login(client, "9000006001")
    client.put("/api/v1/profile", json=PROFILE, headers=h)
    before = client.get("/api/v1/artefacts", headers=h).json()
    r = client.post("/api/v1/artefacts/cashflow/statement", headers=h,
                    files={"file": ("statement.xlsx", ss.layout_a_xlsx(TX), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200, r.text
    assert len(r.json()["months"]) == 6
    assert client.get("/api/v1/artefacts", headers=h).json() == before
    # Password-protected PDF: helpful 422 without the password, works with it
    pdf = ss.layout_e_pdf(TX)
    r = client.post("/api/v1/artefacts/cashflow/statement", headers=h, files={"file": ("s.pdf", pdf, "application/pdf")})
    assert r.status_code == 422 and "password" in r.json()["detail"]
    r = client.post("/api/v1/artefacts/cashflow/statement", headers=h, files={"file": ("s.pdf", pdf, "application/pdf")},
                    data={"password": ss.PDF_PASSWORD})
    assert r.status_code == 200 and r.json()["summary"]["transactions"] == len(TX)
    # Only MSME users
    assert client.post("/api/v1/artefacts/cashflow/statement", files={"file": ("s.csv", b"a", "text/csv")}).status_code == 401
