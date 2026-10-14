"""MicroFin – read a bank statement (Excel, CSV or text PDF) into monthly cash-flow figures (Sprint 5).

The file is read in memory and never stored. Only monthly totals go back to the user, who checks and edits
them in the cash-flow form before anything is saved. Every figure is calculated here – no AI is involved.

How it works
1. Read the rows of the first table-like sheet (CSV, XLSX, XLS, the HTML "XLS" some banks send, or PDF tables).
2. Find the header row and which column holds date, description, debit, credit (or amount + Dr/Cr) and balance.
3. Sort each transaction into a cash-flow head with simple keyword rules (salary → wages, EMI → loan, …).
4. Add up by month. Loan money received, refunds, interest and own-account transfers are not counted as sales;
   EMIs are not counted as expenses but suggested as a loan entry.
"""
import csv
import io
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from html.parser import HTMLParser

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20000


class StatementError(ValueError):
    """A message the user can act on."""


# ---------------------------------------------------------------- 1. reading rows
def _rows_csv(data: bytes) -> list[list]:
    text = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [row for row in csv.reader(io.StringIO(text), dialect)]


def _rows_xlsx(data: bytes) -> list[list]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001 – openpyxl raises many types
        raise StatementError("This Excel file could not be opened. Please download it again from net banking.") from e
    best: list[list] = []
    for ws in wb.worksheets:  # banks sometimes put a cover sheet first: take the sheet with the most rows
        rows = [list(r) for r in ws.iter_rows(values_only=True, max_row=MAX_ROWS)]
        if len(rows) > len(best):
            best = rows
    wb.close()
    return best


def _rows_xls(data: bytes) -> list[list]:
    try:
        import xlrd
    except ImportError as e:
        raise StatementError("Old .xls files need the xlrd package on the server. Please save the file as .xlsx or CSV.") from e
    try:
        book = xlrd.open_workbook(file_contents=data)
    except Exception as e:  # noqa: BLE001
        raise StatementError("This .xls file could not be opened. Please save it as .xlsx or CSV and try again.") from e
    best: list[list] = []
    for sh in book.sheets():
        rows = []
        for i in range(min(sh.nrows, MAX_ROWS)):
            row = []
            for c in sh.row(i):
                if c.ctype == xlrd.XL_CELL_DATE:
                    row.append(xlrd.xldate.xldate_as_datetime(c.value, book.datemode))
                else:
                    row.append(c.value)
            rows.append(row)
        if len(rows) > len(best):
            best = rows
    return best


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, d):
        if self._cell is not None:
            self._cell.append(d)


def _rows_html(data: bytes) -> list[list]:
    p = _TableParser()
    p.feed(data.decode("utf-8", errors="ignore"))
    return p.rows[:MAX_ROWS]


def _rows_pdf(data: bytes, password: str | None) -> list[list]:
    try:
        import pdfplumber
    except ImportError as e:
        raise StatementError("PDF statements need the pdfplumber package on the server. Please upload Excel or CSV.") from e
    try:
        pdf = pdfplumber.open(io.BytesIO(data), password=password or "")
    except Exception as e:  # noqa: BLE001
        why = f"{type(e).__name__} {e!r}".lower()  # pdfplumber wraps pdfminer's PDFPasswordIncorrect
        if "password" in why or "encrypt" in why:
            if password:
                raise StatementError("The PDF password is not correct. Please check it and try again.") from e
            raise StatementError("This PDF is password-protected. Enter the statement password (often given in the "
                                 "bank's e-mail) and try again.") from e
        raise StatementError("This PDF could not be opened. Please download the statement as Excel or CSV.") from e
    rows: list[list] = []
    text_chars = 0
    with pdf:
        if len(pdf.pages) > 60:
            raise StatementError("This PDF has too many pages. Please upload up to 12 months at a time.")
        for page in pdf.pages:
            text_chars += len(page.chars)
            for table in page.extract_tables():
                rows.extend([[c if c is not None else "" for c in r] for r in table])
            if not page.extract_tables():
                # Statements without ruled lines: fall back to splitting text lines on 2+ spaces.
                for line in (page.extract_text(layout=True) or "").splitlines():
                    parts = [p.strip() for p in re.split(r"\s{2,}", line.strip()) if p.strip()]
                    if len(parts) >= 3:
                        rows.append(parts)
    if text_chars == 0:
        raise StatementError("This PDF looks like a scanned image, which cannot be read yet. Please download the "
                             "statement as Excel or CSV from net banking.")
    return rows


def read_rows(filename: str, data: bytes, password: str | None = None) -> list[list]:
    if not data:
        raise StatementError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise StatementError("The file is larger than 5 MB. Please upload up to 12 months at a time.")
    name = (filename or "").lower()
    head = data[:512].lstrip().lower()
    if head.startswith(b"%pdf"):
        return _rows_pdf(data, password)
    if data[:4] == b"PK\x03\x04":
        return _rows_xlsx(data)
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return _rows_xls(data)
    if head.startswith((b"<", b"\xef\xbb\xbf<")) and (b"<table" in data[:200000].lower() or b"<html" in head):
        return _rows_html(data)
    if name.endswith((".csv", ".txt")) or b"," in data[:2048] or b";" in data[:2048] or b"\t" in data[:2048]:
        return _rows_csv(data)
    raise StatementError("Please upload the statement as Excel (.xlsx / .xls), CSV or PDF.")


# ---------------------------------------------------------------- 2. finding columns
def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return " ".join(str(v).replace("\n", " ").split())


def _key(v) -> str:
    return re.sub(r"[^a-z/]+", " ", _cell(v).lower()).strip()


# Order matters: a column is claimed by the first field that matches it, so "Dr / Cr" goes before "Dr".
HEADS = {
    "drcr": ["dr/cr", "cr/dr", "dr / cr", "cr / dr", "debit/credit", "type", "txn type", "transaction type"],
    "date": ["txn date", "transaction date", "tran date", "trans date", "date", "posting date", "value date", "value dt", "txn dt"],
    "desc": ["narration", "description", "particulars", "transaction remarks", "remarks", "details", "transaction details",
             "transaction particulars", "narrative"],
    "debit": ["withdrawal amt", "withdrawal amount", "withdrawal amount inr", "withdrawals", "withdrawal", "debit amount",
              "debit", "debits", "dr amount", "dr", "paid out", "money out"],
    "credit": ["deposit amt", "deposit amount", "deposit amount inr", "deposits", "deposit", "credit amount", "credit",
               "credits", "cr amount", "cr", "paid in", "money in"],
    "amount": ["amount", "transaction amount", "txn amount", "amount inr", "amt"],
    "balance": ["balance", "closing balance", "running balance", "available balance", "balance inr", "bal"],
}


def _match(label: str, names: list[str]) -> int:
    """0 = no match; higher = better (exact beats 'starts with')."""
    for rank, n in enumerate(names):
        if label == n:
            return 200 - rank
    for rank, n in enumerate(names):
        if label.startswith(n + " "):  # whole words only: "dr" must not match "dr/cr"
            return 100 - rank
    return 0


def find_columns(rows: list[list]) -> tuple[int, dict[str, int]]:
    for i, row in enumerate(rows[:60]):
        labels = [_key(c) for c in row]
        cols: dict[str, int] = {}
        for field, names in HEADS.items():
            best, best_score = None, 0
            for j, lab in enumerate(labels):
                if not lab or j in cols.values():
                    continue
                sc = _match(lab, names)
                # "value date" only if there is no transaction date column
                if field == "date" and lab.startswith("value"):
                    sc -= 50
                if sc > best_score:
                    best, best_score = j, sc
            if best is not None:
                cols[field] = best
        if "date" in cols and (("debit" in cols and "credit" in cols) or "amount" in cols):
            return i, cols
    raise StatementError("We could not find the transaction table (date, debit and credit columns) in this file. "
                         "Please upload the statement exactly as downloaded from net banking.")


# ---------------------------------------------------------------- 3. values
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y", "%Y-%m-%d", "%Y/%m/%d",
                "%d-%b-%Y", "%d %b %Y", "%d/%b/%Y", "%d-%b-%y", "%d %b %y", "%b %d, %Y", "%d %B %Y", "%d-%B-%Y"]


def parse_date(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)) and 20000 < v < 80000:  # Excel serial date stored as a number
        return date(1899, 12, 30) + timedelta(days=int(v))
    s = _cell(v)
    if not s:
        return None
    s = re.split(r"\s+\d{1,2}:\d{2}", s)[0].strip()  # drop a time part
    for f in DATE_FORMATS:
        try:
            d = datetime.strptime(s, f).date()
            if 2000 <= d.year <= 2100:
                return d
        except ValueError:
            continue
    return None


def parse_amount(v) -> tuple[float | None, str | None]:
    """Return (amount, 'dr'/'cr' if written in the cell)."""
    if v is None:
        return None, None
    if isinstance(v, (int, float)):
        return (abs(float(v)), "dr" if v < 0 else None) if v else (None, None)
    s = _cell(v).lower().replace("₹", "").replace("inr", "").replace("rs.", "").replace("rs", "")
    side = "cr" if re.search(r"\bcr\.?$", s) else "dr" if re.search(r"\bdr\.?$", s) else None
    neg = s.strip().startswith("-") or (s.strip().startswith("(") and s.strip().endswith(")"))
    num = re.sub(r"[^\d.]", "", s)
    if not num or num.count(".") > 1:
        return None, None
    try:
        x = float(num)
    except ValueError:
        return None, None
    if not x:
        return None, None
    return x, side or ("dr" if neg else None)


# ---------------------------------------------------------------- 4. categories
# (head, label, words). First match wins. Words are matched against the lower-case description.
CREDIT_RULES = [
    ("loan_in", "Loan money received", ["loan disb", "disbursal", "disbursement", "loan a/c", "od limit", "cc limit"]),
    ("refund", "Refunds and reversals", ["reversal", "refund", "rev ", "returned", "chargeback", "rtn"]),
    ("interest", "Interest from bank", ["int.pd", "int pd", "interest", "int.cr", "sb int", "int credit"]),
    ("cash_sales", "Cash deposits", ["cash dep", "by cash", "cash deposit", "cdm", "cash-"]),
    ("own_in", "Transfers from own accounts", ["self", "own a/c", "own account", "from savings", "sweep"]),
]
DEBIT_RULES = [
    ("emi", "Loan EMIs", ["emi", "loan rec", "loan repay", "ach d", "nach", "ecs", "loan inst"]),
    ("wages", "Wages and salaries", ["salary", "salaries", "wages", "wage", "sal ", "payroll", "labour", "labor"]),
    ("rent", "Rent", ["rent"]),
    ("power", "Power and fuel", ["electricity", "apspdcl", "apepdcl", "apcpdcl", "tsspdcl", "tsnpdcl", "power", "eb bill",
                                  "bescom", "fuel", "petrol", "diesel", "hpcl", "iocl", "bpcl", "indian oil", "gas"]),
    ("transport", "Transport and freight", ["transport", "freight", "lorry", "logistics", "courier", "delhivery",
                                             "porter", "toll", "fastag"]),
    ("tax", "Taxes (GST, TDS)", ["gst", "cbdt", "tds", "income tax", "tin-nsdl", "challan", "advance tax"]),
    ("charges", "Bank charges", ["charges", "chrg", "chg", "fee", "sms alert", "annual fee", "gst on chg", "min bal"]),
    ("cash_out", "Cash withdrawals", ["atm", "cash wdl", "cash withdrawal", "self wdl", "by self", "to self", "chq paid self",
                                       "cash paid", "nfs/"]),
    ("own_out", "Transfers to own accounts", ["own a/c", "own account", "to savings", "sweep"]),
]
LABELS = {h: l for rules in (CREDIT_RULES, DEBIT_RULES) for h, l, _ in rules}
LABELS.update({"sales": "Money received from customers", "purchases": "Payments to suppliers / purchases"})
LABELS_TE = {  # draft – MIRAI to review
    "sales": "కస్టమర్ల నుండి వచ్చిన డబ్బు", "cash_sales": "నగదు జమలు", "loan_in": "వచ్చిన రుణం", "refund": "రీఫండ్‌లు / రివర్సల్స్",
    "interest": "బ్యాంకు వడ్డీ", "own_in": "సొంత ఖాతాల నుండి బదిలీలు", "purchases": "సరఫరాదారులకు చెల్లింపులు / కొనుగోళ్లు",
    "emi": "రుణ వాయిదాలు (EMI)", "wages": "జీతాలు, వేతనాలు", "rent": "అద్దె", "power": "విద్యుత్, ఇంధనం", "transport": "రవాణా, సరుకు రవాణా",
    "tax": "పన్నులు (GST, TDS)", "charges": "బ్యాంకు ఛార్జీలు", "cash_out": "నగదు విత్‌డ్రాలు", "own_out": "సొంత ఖాతాలకు బదిలీలు",
}
WARN = {
    "part_start": {"en": "The statement starts on {d}, so {m} is a part month.", "te": "స్టేట్‌మెంట్ {d} నుండి మొదలవుతుంది, కాబట్టి {m} పూర్తి నెల కాదు."},
    "part_end": {"en": "The statement ends on {d}, so {m} is a part month.", "te": "స్టేట్‌మెంట్ {d}తో ముగుస్తుంది, కాబట్టి {m} పూర్తి నెల కాదు."},
    "max24": {"en": "Only the latest 24 months are used.", "te": "చివరి 24 నెలలు మాత్రమే తీసుకున్నాం."},
    "cash_out": {"en": "Cash withdrawals are counted as other expenses. If some were for wages or raw material, move them to the "
                       "right line before making the summary.",
                 "te": "నగదు విత్‌డ్రాలను ఇతర ఖర్చులుగా లెక్కించాం. వాటిలో కొన్ని జీతాలు లేదా ముడి సరుకు కోసం అయితే, సారాంశం "
                       "తయారు చేసే ముందు సరైన వరుసలోకి మార్చండి."},
    "skipped": {"en": "{n} line(s) could not be read and were left out.", "te": "{n} వరుస(లు) చదవలేకపోయాం, వాటిని వదిలేశాం."},
}

# How each category feeds the cash-flow form (MonthRow fields). None = not counted.
TO_FORM = {
    "sales": "cash_sales", "cash_sales": "cash_sales",
    "purchases": "raw_material", "wages": "wages", "rent": "rent", "power": "power", "transport": "transport",
    "tax": "other", "charges": "other", "cash_out": "other",
    "loan_in": None, "refund": None, "interest": None, "own_in": None, "own_out": None, "emi": None,
}


def categorise(desc: str, side: str) -> str:
    d = f" {desc.lower()} "
    for head, _, words in CREDIT_RULES if side == "cr" else DEBIT_RULES:
        if any(w in d for w in words):
            return head
    return "sales" if side == "cr" else "purchases"


def mask(text: str) -> str:
    """Hide account / card / reference numbers: keep only the last 4 digits of long digit runs."""
    return re.sub(r"\d{6,}", lambda m: "XX" + m.group()[-4:], text)[:80]


# ---------------------------------------------------------------- 5. the whole thing
def parse_statement(filename: str, data: bytes, password: str | None = None, lang: str = "en") -> dict:
    w = lambda key, **kw: (WARN[key].get(lang) or WARN[key]["en"]).format(**kw)  # noqa: E731
    label = lambda head: LABELS_TE.get(head, LABELS[head]) if lang == "te" else LABELS[head]  # noqa: E731
    rows = read_rows(filename, data, password)
    hi, cols = find_columns(rows)
    txns = []
    skipped = 0
    header = [_key(c) for c in rows[hi]]
    for row in rows[hi + 1:]:
        if [_key(c) for c in row] == header:  # header repeated on every PDF page
            continue
        get = lambda f: row[cols[f]] if f in cols and cols[f] < len(row) else None  # noqa: E731
        d = parse_date(get("date"))
        if not d:
            # Notes and footers fill one or two cells; a real but unreadable transaction line fills more.
            if sum(1 for c in row if _cell(c)) >= 3:
                skipped += 1
            continue
        desc = _cell(get("desc"))
        if re.search(r"opening balance|closing balance|b/f|brought forward|carried forward", desc.lower()):
            continue
        side, amt = None, None
        if "debit" in cols and "credit" in cols:
            dr, _ = parse_amount(get("debit"))
            cr, _ = parse_amount(get("credit"))
            if dr and not cr:
                side, amt = "dr", dr
            elif cr and not dr:
                side, amt = "cr", cr
        if amt is None and "amount" in cols:
            a, s = parse_amount(get("amount"))
            t = _key(get("drcr")) if "drcr" in cols else ""
            if t in ("c", "cr", "credit", "deposit") or t.startswith("cr"):
                s = "cr"
            elif t in ("d", "dr", "debit", "withdrawal") or t.startswith("dr"):
                s = "dr"
            if a and s:
                side, amt = s, a
        if amt is None:
            skipped += 1
            continue
        txns.append({"date": d, "desc": desc, "side": side, "amount": amt, "head": categorise(desc, side)})

    if not txns:
        raise StatementError("No transactions were found in this file. Please check it is an account statement.")

    # Monthly totals in the cash-flow form's fields
    months: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_head: dict[str, dict] = {}
    emis: list[float] = []
    for t in txns:
        ym = t["date"].strftime("%Y-%m")
        field = TO_FORM[t["head"]]
        if field:
            months[ym][field] += t["amount"]
        else:
            months[ym]  # keep the month even if it only has excluded entries
        h = by_head.setdefault(t["head"], {"head": t["head"], "label": label(t["head"]), "side": t["side"],
                                           "counted_as": field, "amount": 0.0, "count": 0})
        h["amount"] += t["amount"]
        h["count"] += 1
        if t["head"] == "emi":
            emis.append(t["amount"])

    keys = sorted(months)
    form_fields = ["cash_sales", "credit_sales", "raw_material", "wages", "rent", "power", "transport", "other"]
    month_rows = [{"month": k, **{f: round(months[k].get(f, 0.0), 2) for f in form_fields}} for k in keys]

    first, last = min(t["date"] for t in txns), max(t["date"] for t in txns)
    warnings = []
    # Part months at the start or end distort averages.
    if first.day > 5:
        warnings.append(w("part_start", d=f"{first:%d %b %Y}", m=f"{first:%B}"))
    if last.day < 25:
        warnings.append(w("part_end", d=f"{last:%d %b %Y}", m=f"{last:%B}"))
    if len(keys) > 24:
        month_rows = month_rows[-24:]
        warnings.append(w("max24"))
    if "cash_out" in by_head:
        warnings.append(w("cash_out"))
    if skipped:
        warnings.append(w("skipped", n=skipped))

    loans = []
    if emis:
        loans.append({"lender": "Loan EMI seen in bank statement", "outstanding": 0,
                      "emi": round(statistics.median(emis), 2)})

    credits = sum(t["amount"] for t in txns if t["side"] == "cr")
    debits = sum(t["amount"] for t in txns if t["side"] == "dr")
    order = ["sales", "cash_sales", "loan_in", "refund", "interest", "own_in", "purchases", "wages", "rent", "power",
             "transport", "tax", "charges", "cash_out", "own_out", "emi"]
    return {
        "months": month_rows,
        "loans": loans,
        "summary": {
            "from": first.isoformat(), "to": last.isoformat(), "transactions": len(txns),
            "credits": round(credits, 2), "debits": round(debits, 2),
            "by_head": sorted(({**h, "amount": round(h["amount"], 2)} for h in by_head.values()),
                              key=lambda h: order.index(h["head"])),
            "examples": [{"date": t["date"].isoformat(), "desc": mask(t["desc"]), "side": t["side"],
                          "amount": round(t["amount"], 2), "label": label(t["head"])} for t in txns[:8]],
        },
        "warnings": warnings,
    }
