"""MicroFin – cash-flow and financial health summary (Form G-2).

All figures are calculated here in plain Python, never by the AI. The insights are simple, explainable rules.
"""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

EXPENSE_HEADS = ["raw_material", "wages", "rent", "power", "transport", "other"]
EXPENSE_LABELS = {"raw_material": "Raw material / stock", "wages": "Wages", "rent": "Rent", "power": "Power & fuel",
                  "transport": "Transport", "other": "Other"}
MSMED_DAYS = 45  # MSMED Act: maximum payment period for buyers of Udyam-registered micro and small units


class MonthRow(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")  # YYYY-MM
    cash_sales: float = Field(default=0, ge=0)
    credit_sales: float = Field(default=0, ge=0)
    raw_material: float = Field(default=0, ge=0)
    wages: float = Field(default=0, ge=0)
    rent: float = Field(default=0, ge=0)
    power: float = Field(default=0, ge=0)
    transport: float = Field(default=0, ge=0)
    other: float = Field(default=0, ge=0)


class Receivable(BaseModel):
    customer: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0)
    invoice_date: date


class Payable(BaseModel):
    supplier: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0)
    due_date: date


class Loan(BaseModel):
    lender: str = Field(min_length=1, max_length=120)
    outstanding: float = Field(default=0, ge=0)
    emi: float = Field(default=0, ge=0)


class CashflowIn(BaseModel):
    months: list[MonthRow] = Field(min_length=1, max_length=24)
    stock_value: float = Field(default=0, ge=0)
    receivables: list[Receivable] = Field(default=[], max_length=200)
    payables: list[Payable] = Field(default=[], max_length=200)
    loans: list[Loan] = Field(default=[], max_length=20)
    purpose: Literal["understand", "loan", "working_capital", "cash_shortage"] = "understand"
    as_of: Optional[date] = None

    @field_validator("months")
    @classmethod
    def unique_sorted(cls, v):
        keys = [m.month for m in v]
        if len(set(keys)) != len(keys):
            raise ValueError("Each month can appear only once")
        return sorted(v, key=lambda m: m.month)


def _r(x: float) -> float:
    return round(x, 2)


def calculate(data: CashflowIn) -> dict:
    as_of = data.as_of or date.today()
    rows = []
    for m in data.months:
        sales = m.cash_sales + m.credit_sales
        expenses = sum(getattr(m, h) for h in EXPENSE_HEADS)
        rows.append({"month": m.month, "cash_sales": _r(m.cash_sales), "credit_sales": _r(m.credit_sales),
                     "sales": _r(sales), "expenses": _r(expenses), "profit": _r(sales - expenses),
                     **{h: _r(getattr(m, h)) for h in EXPENSE_HEADS}})
    n = len(rows)
    total_sales = sum(r["sales"] for r in rows)
    total_exp = sum(r["expenses"] for r in rows)
    total_credit = sum(r["credit_sales"] for r in rows)
    profit = total_sales - total_exp
    by_head = {h: _r(sum(r[h] for r in rows)) for h in EXPENSE_HEADS}

    # Receivables ageing from invoice date
    buckets = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
    overdue = []
    for rcv in data.receivables:
        days = (as_of - rcv.invoice_date).days
        key = "0-30" if days <= 30 else "31-60" if days <= 60 else "61-90" if days <= 90 else "90+"
        buckets[key] += rcv.amount
        if days > MSMED_DAYS:
            overdue.append({"customer": rcv.customer, "amount": _r(rcv.amount), "days": days})
    overdue.sort(key=lambda o: o["days"], reverse=True)
    receivables_total = sum(r.amount for r in data.receivables)
    payables_total = sum(p.amount for p in data.payables)
    payables_30 = sum(p.amount for p in data.payables if 0 <= (p.due_date - as_of).days <= 30)
    payables_overdue = sum(p.amount for p in data.payables if (p.due_date - as_of).days < 0)
    emi_total = sum(lo.emi for lo in data.loans)
    loan_outstanding = sum(lo.outstanding for lo in data.loans)

    avg_sales = total_sales / n
    avg_exp = total_exp / n
    avg_profit = profit / n
    margin = (profit / total_sales * 100) if total_sales else None
    credit_share = (total_credit / total_sales * 100) if total_sales else None
    emi_share = (emi_total / avg_profit * 100) if avg_profit > 0 else None
    nwc = data.stock_value + receivables_total - payables_total  # money tied up in running the business
    # Days of sales stuck with customers (based on average monthly credit sales)
    avg_credit = total_credit / n
    receivable_days = (receivables_total / avg_credit * 30) if avg_credit else None

    insights: list[dict] = []

    def add(level: str, text: str):
        insights.append({"level": level, "text": text})

    loss_months = [r["month"] for r in rows if r["profit"] < 0]
    empty_months = [r["month"] for r in rows if r["sales"] == 0 and r["expenses"] == 0]
    if margin is None:
        add("alert", "No sales were entered, so profit and margins cannot be worked out.")
    elif margin < 0:
        add("alert", f"Expenses were higher than sales over this period (loss of Rs. {inr(-profit)}). Check pricing and the biggest costs.")
    elif margin < 10:
        add("warn", f"Profit margin is thin at {margin:.1f}%. A small rise in costs could cause a loss.")
    else:
        add("good", f"Profit margin is {margin:.1f}% of sales.")
    if loss_months and margin is not None and margin >= 0:
        add("warn", f"Loss in {len(loss_months)} month(s): {', '.join(loss_months)}.")
    if credit_share is not None and credit_share > 40:
        add("warn", f"{credit_share:.0f}% of sales are on credit. Cash comes in late; agree payment dates in writing.")
    if overdue:
        amt = sum(o["amount"] for o in overdue)
        add("alert", f"Rs. {inr(amt)} has been due from {len(overdue)} customer(s) for more than {MSMED_DAYS} days. "
                     "Udyam-registered micro and small units can use the MSME Samadhaan delayed-payment portal.")
    if receivable_days is not None and receivable_days > 60:
        add("warn", f"Money owed by customers equals about {receivable_days:.0f} days of credit sales.")
    if emi_share is not None and emi_share > 50:
        add("alert", f"Loan EMIs take {emi_share:.0f}% of average monthly profit. Avoid new loans until this falls.")
    elif emi_total and avg_profit <= 0:
        add("alert", "Loan EMIs are due but the business is not making a profit on average.")
    if payables_overdue:
        add("warn", f"Rs. {inr(payables_overdue)} owed to suppliers is already past its due date.")
    top_head = max(by_head, key=by_head.get) if total_exp else None
    if top_head and total_exp and by_head[top_head] / total_exp > 0.6:
        add("warn", f"{EXPENSE_LABELS[top_head]} is {by_head[top_head] / total_exp * 100:.0f}% of all expenses – the first place to look for savings.")

    gaps = []
    if empty_months:
        gaps.append(f"No figures entered for {', '.join(empty_months)}.")
    if n < 6:
        gaps.append("Banks usually look at 6–12 months of records; add more months if you have them.")
    if not data.receivables and total_credit > 0:
        gaps.append("Credit sales were entered but no list of customers who owe money.")
    if data.purpose == "loan" and not data.loans:
        gaps.append("For a loan application, also list any existing loans (even informal ones).")

    return {
        "as_of": as_of.isoformat(),
        "months": rows,
        "totals": {"sales": _r(total_sales), "expenses": _r(total_exp), "profit": _r(profit),
                   "cash_sales": _r(total_sales - total_credit), "credit_sales": _r(total_credit)},
        "averages": {"sales": _r(avg_sales), "expenses": _r(avg_exp), "profit": _r(avg_profit)},
        "ratios": {"margin_pct": None if margin is None else round(margin, 1),
                   "credit_share_pct": None if credit_share is None else round(credit_share, 1),
                   "emi_to_profit_pct": None if emi_share is None else round(emi_share, 1),
                   "receivable_days": None if receivable_days is None else round(receivable_days)},
        "expenses_by_head": [{"head": h, "label": EXPENSE_LABELS[h], "amount": by_head[h]} for h in EXPENSE_HEADS if by_head[h]],
        "receivables": {"total": _r(receivables_total), "ageing": {k: _r(v) for k, v in buckets.items()}, "overdue": overdue},
        "payables": {"total": _r(payables_total), "due_30_days": _r(payables_30), "overdue": _r(payables_overdue)},
        "loans": {"emi_total": _r(emi_total), "outstanding": _r(loan_outstanding)},
        "working_capital": {"stock": _r(data.stock_value), "receivables": _r(receivables_total),
                            "payables": _r(payables_total), "net": _r(nwc)},
        "insights": insights,
        "data_gaps": gaps,
    }


def inr(x: float) -> str:
    """Indian digit grouping: 1234567.5 -> 12,34,568"""
    neg = x < 0
    s = str(int(round(abs(x))))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if neg else "") + s
