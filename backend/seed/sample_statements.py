"""Make SAMPLE bank statements in the layouts Indian banks commonly use (fictional data, for demos and tests).

    python -m seed.sample_statements          # writes files to seed/sample_statements/

The account, names and numbers are made up. Layouts are modelled on common net-banking downloads:
  A – Excel with account details above the table, Debit / Credit columns, "01 Apr 2026" dates
  B – CSV with Withdrawal Amt. / Deposit Amt. columns, dd/mm/yy dates
  C – HTML saved as .xls (several banks send this), Withdrawal / Deposit Amount (INR) columns
  D – CSV with one Amount column and a Dr / Cr column
  E – password-protected PDF with a ruled table (password: MIRAI123)
"""
import csv
import io
import random
from datetime import date, timedelta
from pathlib import Path

PDF_PASSWORD = "MIRAI123"


def transactions(start: date = date(2026, 4, 1), months: int = 6, seed: int = 7) -> list[dict]:
    """A millet-snacks unit: UPI and cash sales, suppliers, wages, rent, power, EMI, charges."""
    rnd = random.Random(seed)
    out = []
    bal = 85000.0

    def add(d, desc, dr=0.0, cr=0.0):
        nonlocal bal
        bal += cr - dr
        out.append({"date": d, "desc": desc, "debit": round(dr, 2), "credit": round(cr, 2), "balance": round(bal, 2)})

    for m in range(months):
        y, mo = start.year + (start.month - 1 + m) // 12, (start.month - 1 + m) % 12 + 1
        first = date(y, mo, 1)
        if m == 1:
            add(first + timedelta(days=2), "LOAN DISB MUDRA 50023418871", cr=150000)
        for day in range(1, 28, 3):  # customer receipts
            d = first + timedelta(days=day)
            add(d, f"UPI/{rnd.randint(400000000000, 499999999999)}/SRI SAI HOSTEL/upi@okaxis", cr=rnd.randint(4000, 9000))
            if day % 2:
                add(d, "CASH DEPOSIT BY SELF CDM GUNTUR", cr=rnd.randint(3000, 6000))
        add(first + timedelta(days=4), f"NEFT/N0{rnd.randint(10**9, 10**10)}/KRISHNA MILLET TRADERS", dr=rnd.randint(26000, 34000))
        add(first + timedelta(days=17), "IMPS/P2A/VIJAYA PACKAGING", dr=rnd.randint(3000, 5000))
        add(first + timedelta(days=6), "SALARY MAY STAFF 3 NOS" if mo == 5 else "SALARY STAFF 3 NOS", dr=36000)
        add(first + timedelta(days=5), "RENT FOR SHED", dr=8000)
        add(first + timedelta(days=11), f"APSPDCL ELECTRICITY BILL {rnd.randint(10**8, 10**9)}", dr=rnd.randint(2200, 3400))
        add(first + timedelta(days=13), "DIESEL HPCL PUMP GUNTUR", dr=rnd.randint(1500, 2500))
        add(first + timedelta(days=15), "FREIGHT - SRI RAMA TRANSPORT", dr=rnd.randint(1800, 2600))
        if m >= 2:
            add(first + timedelta(days=9), "NACH DR MUDRA LOAN EMI 50023418871", dr=4850)
        add(first + timedelta(days=19), "ATM WDL NFS GUNTUR MAIN RD", dr=5000)
        add(first + timedelta(days=24), "SMS ALERT CHARGES", dr=17.7)
        if mo in (6, 9):
            add(first + timedelta(days=27), "SB INT CREDIT", cr=rnd.randint(150, 260))
    out.sort(key=lambda t: t["date"])
    # recompute running balance in date order
    bal = 85000.0
    for t in out:
        bal += t["credit"] - t["debit"]
        t["balance"] = round(bal, 2)
    return out


def _amt(x: float) -> str:
    return f"{x:,.2f}" if x else ""


def layout_a_xlsx(tx: list[dict]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Statement"
    for r in [["Account Name", "LAKSHMI MILLET SNACKS"], ["Account Number", "00000041234567890"], ["Branch", "GUNTUR MAIN"],
              ["Statement From", "01-04-2026 To 30-09-2026"], [], []]:
        ws.append(r)
    ws.append(["Txn Date", "Value Date", "Description", "Ref No./Cheque No.", "Debit", "Credit", "Balance"])
    for t in tx:
        ws.append([t["date"].strftime("%d %b %Y"), t["date"].strftime("%d %b %Y"), t["desc"], "",
                   _amt(t["debit"]) or " ", _amt(t["credit"]) or " ", _amt(t["balance"])])
    ws.append([])
    ws.append(["**This is a computer generated statement**"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def layout_b_csv(tx: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"])
    for t in tx:
        w.writerow([t["date"].strftime("%d/%m/%y"), t["desc"], f"{random.Random(t['desc']).randint(10**11, 10**12):016d}",
                    t["date"].strftime("%d/%m/%y"), f"{t['debit']:.2f}" if t["debit"] else "", f"{t['credit']:.2f}" if t["credit"] else "",
                    f"{t['balance']:.2f}"])
    return buf.getvalue().encode()


def layout_c_html_xls(tx: list[dict]) -> bytes:
    rows = "".join(
        f"<tr><td>{i + 1}</td><td>{t['date']:%d/%m/%Y}</td><td>{t['date']:%d/%m/%Y}</td><td></td><td>{t['desc']}</td>"
        f"<td>{t['debit']:.2f}</td><td>{t['credit']:.2f}</td><td>{t['balance']:.2f}</td></tr>" for i, t in enumerate(tx))
    html = ("<html><body><table><tr><td>Account Number</td><td>XXXXXXXX4521</td></tr></table><table>"
            "<tr><th>S No.</th><th>Value Date</th><th>Transaction Date</th><th>Cheque Number</th><th>Transaction Remarks</th>"
            "<th>Withdrawal Amount (INR )</th><th>Deposit Amount (INR )</th><th>Balance (INR )</th></tr>"
            f"{rows}</table></body></html>")
    return html.encode()


def layout_d_drcr_csv(tx: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Sl. No.", "Date", "Description", "Amount", "Dr / Cr", "Balance"])
    for i, t in enumerate(tx):
        dr = t["debit"] > 0
        w.writerow([i + 1, t["date"].strftime("%d-%m-%Y"), t["desc"], f"{(t['debit'] or t['credit']):,.2f}", "DR" if dr else "CR",
                    f"{t['balance']:,.2f}"])
    return buf.getvalue().encode()


def layout_e_pdf(tx: list[dict], password: str = PDF_PASSWORD) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib.pdfencrypt import StandardEncryption

    buf = io.BytesIO()
    enc = StandardEncryption(password, canPrint=1) if password else None
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                            encrypt=enc)
    st = getSampleStyleSheet()
    data = [["Date", "Particulars", "Withdrawals", "Deposits", "Balance"]]
    for t in tx:
        data.append([t["date"].strftime("%d-%m-%Y"), t["desc"][:42], _amt(t["debit"]), _amt(t["credit"]), _amt(t["balance"])])
    tbl = Table(data, colWidths=[22 * mm, 82 * mm, 26 * mm, 26 * mm, 28 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                             ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("ALIGN", (2, 1), (-1, -1), "RIGHT")]))
    doc.build([Paragraph("SAMPLE BANK – Statement of Account (fictional, for demonstration)", st["Heading4"]),
               Paragraph("Account: LAKSHMI MILLET SNACKS · XXXXXXXX7788", st["Normal"]), Spacer(1, 6), tbl])
    return buf.getvalue()


FILES = {
    "A_sample_statement.xlsx": layout_a_xlsx,
    "B_sample_statement.csv": layout_b_csv,
    "C_sample_statement.xls": layout_c_html_xls,
    "D_sample_statement_drcr.csv": layout_d_drcr_csv,
    "E_sample_statement_password_MIRAI123.pdf": layout_e_pdf,
}


def main() -> None:
    out = Path(__file__).parent / "sample_statements"
    out.mkdir(exist_ok=True)
    tx = transactions()
    for name, fn in FILES.items():
        (out / name).write_bytes(fn(tx))
        print("wrote", out / name)


if __name__ == "__main__":
    main()
