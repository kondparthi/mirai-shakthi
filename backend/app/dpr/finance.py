"""DPR calculations (M5). Every figure in a DPR comes from here – the AI only writes words.

Inputs (all money in rupees):
  capital_items     [{item, spec, qty, rate}]       amount = qty × rate
  preoperative      registrations, licences, deposits (amortised over the projection years)
  contingency_pct   % on capital items
  working_capital   stock, cash and credit to start running
  finance           {own, subsidy, grant}            bank loan = project cost − own − subsidy − grant
  sales             {items:[{name, unit, units_per_day, price}], working_days, monthly_growth_pct, yearly_growth_pct}
                    year 1 grows month by month (ramp-up); years 2–5 grow once a year
  expenses          {raw_material_pct, salaries, rent, fuel, maintenance, other, yearly_increase_pct}  (monthly ₹)
  loan              {interest_pct, tenure_months, moratorium_months}   interest is paid during the moratorium,
                    then equal monthly instalments (EMI) for the rest of the tenure
  depreciation_pct  written-down value rate on capital items
  tax_pct, drawings_monthly (owner's household drawings: taken out of cash flow, DSCR and payback), years (3–5)
"""
from __future__ import annotations

import math

DEFAULTS = {
    "capital_items": [],
    "preoperative": 0.0,
    "contingency_pct": 0.0,
    "working_capital": 0.0,
    "finance": {"own": 0.0, "subsidy": 0.0, "grant": 0.0},
    "sales": {"items": [], "working_days": 26, "monthly_growth_pct": 0.0, "yearly_growth_pct": 5.0},
    "expenses": {"raw_material_pct": 0.0, "salaries": 0.0, "rent": 0.0, "fuel": 0.0, "maintenance": 0.0, "other": 0.0,
                 "yearly_increase_pct": 5.0},
    "loan": {"interest_pct": 11.0, "tenure_months": 60, "moratorium_months": 6},
    "depreciation_pct": 15.0,
    "tax_pct": 0.0,
    "drawings_monthly": 0.0,
    "years": 5,
}
FIXED_HEADS = (("salaries", "Salaries and wages"), ("rent", "Rent"), ("fuel", "Fuel, power and gas"),
               ("maintenance", "Repairs and maintenance"), ("other", "Other expenses"))


def _f(v, default=0.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default


def normalise(raw: dict | None) -> dict:
    """Fill defaults and coerce numbers, so the engine never fails on a half-filled form."""
    raw = raw or {}
    d = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    for k in ("preoperative", "contingency_pct", "working_capital", "depreciation_pct", "tax_pct", "drawings_monthly"):
        d[k] = max(0.0, _f(raw.get(k), DEFAULTS[k]))
    d["years"] = int(min(5, max(3, _f(raw.get("years"), 5))))
    d["capital_items"] = [
        {"item": str(i.get("item") or "").strip(), "spec": str(i.get("spec") or "").strip(),
         "qty": max(0.0, _f(i.get("qty"), 1)), "rate": max(0.0, _f(i.get("rate")))}
        for i in raw.get("capital_items") or [] if isinstance(i, dict)]
    for i in d["capital_items"]:
        i["amount"] = round(i["qty"] * i["rate"], 2)
    fin = raw.get("finance") or {}
    d["finance"] = {k: max(0.0, _f(fin.get(k))) for k in ("own", "subsidy", "grant")}
    s = raw.get("sales") or {}
    d["sales"] = {
        "items": [{"name": str(i.get("name") or "").strip(), "unit": str(i.get("unit") or "unit").strip(),
                   "units_per_day": max(0.0, _f(i.get("units_per_day"))), "price": max(0.0, _f(i.get("price")))}
                  for i in s.get("items") or [] if isinstance(i, dict)],
        "working_days": min(31.0, max(0.0, _f(s.get("working_days"), 26))),
        "monthly_growth_pct": min(20.0, max(-20.0, _f(s.get("monthly_growth_pct")))),
        "yearly_growth_pct": min(50.0, max(-50.0, _f(s.get("yearly_growth_pct"), 5))),
    }
    e = raw.get("expenses") or {}
    d["expenses"] = {k: max(0.0, _f(e.get(k), DEFAULTS["expenses"][k])) for k in DEFAULTS["expenses"]}
    d["expenses"]["raw_material_pct"] = min(100.0, d["expenses"]["raw_material_pct"])
    ln = raw.get("loan") or {}
    tenure = int(min(180, max(1, _f(ln.get("tenure_months"), 60))))
    d["loan"] = {"interest_pct": min(40.0, max(0.0, _f(ln.get("interest_pct"), 11))), "tenure_months": tenure,
                 "moratorium_months": int(min(tenure - 1, max(0, _f(ln.get("moratorium_months"), 0))))}
    return d


def emi(principal: float, annual_pct: float, months: int) -> float:
    if principal <= 0 or months <= 0:
        return 0.0
    r = annual_pct / 1200
    if r == 0:
        return principal / months
    return principal * r * (1 + r) ** months / ((1 + r) ** months - 1)


def loan_schedule(principal: float, annual_pct: float, tenure_months: int, moratorium_months: int = 0) -> list[dict]:
    """Month-by-month: interest only during the moratorium, then EMI. The last instalment clears the balance exactly."""
    rows: list[dict] = []
    if principal <= 0:
        return rows
    r = annual_pct / 1200
    bal = principal
    n_emi = tenure_months - moratorium_months
    inst = emi(principal, annual_pct, n_emi)
    for m in range(1, tenure_months + 1):
        interest = bal * r
        if m <= moratorium_months:
            pay, prin = interest, 0.0
        elif m == tenure_months:
            prin = bal
            pay = prin + interest
        else:
            pay = inst
            prin = pay - interest
        rows.append({"month": m, "opening": bal, "payment": pay, "interest": interest, "principal": prin, "closing": bal - prin})
        bal -= prin
    return rows


def calculate(raw: dict | None) -> dict:
    d = normalise(raw)
    years = d["years"]
    months = years * 12

    # ---- project cost and means of finance
    capital = sum(i["amount"] for i in d["capital_items"])
    contingency = capital * d["contingency_pct"] / 100
    preop = d["preoperative"]
    wc = d["working_capital"]
    project_cost = capital + contingency + preop + wc
    fin = d["finance"]
    funded = fin["own"] + fin["subsidy"] + fin["grant"]
    loan = max(0.0, project_cost - funded)
    excess = max(0.0, funded - project_cost)

    # ---- loan
    ln = d["loan"]
    sched = loan_schedule(loan, ln["interest_pct"], ln["tenure_months"], ln["moratorium_months"])
    n_emi = ln["tenure_months"] - ln["moratorium_months"]
    emi_amount = emi(loan, ln["interest_pct"], n_emi)

    # ---- monthly operations
    s, e = d["sales"], d["expenses"]
    base = sum(i["units_per_day"] * i["price"] for i in s["items"]) * s["working_days"]
    g_m, g_y, inc = s["monthly_growth_pct"] / 100, s["yearly_growth_pct"] / 100, e["yearly_increase_pct"] / 100
    rm_pct = e["raw_material_pct"] / 100
    fixed_month = {k: e[k] for k, _ in FIXED_HEADS}
    monthly = []
    for m in range(1, months + 1):
        y = (m - 1) // 12 + 1
        sales = base * (1 + g_m) ** (m - 1) if y == 1 else base * (1 + g_m) ** 11 * (1 + g_y) ** (y - 1)
        fixed = {k: v * (1 + inc) ** (y - 1) for k, v in fixed_month.items()}
        row = sched[m - 1] if m - 1 < len(sched) else None
        monthly.append({"month": m, "year": y, "sales": sales, "raw_material": sales * rm_pct, "fixed": fixed,
                        "interest": row["interest"] if row else 0.0, "principal": row["principal"] if row else 0.0})

    # ---- depreciation (written-down value) and amortisation of pre-operative expenses
    dep_base = capital + contingency
    wdv, dep_years = dep_base, []
    for _ in range(years):
        dep = wdv * d["depreciation_pct"] / 100
        dep_years.append(dep)
        wdv -= dep
    amort = preop / years

    # ---- yearly statements
    pl, cash, dscr_rows = [], [], []
    closing_cash = wc  # working capital is funded at the start and held as stock / cash
    for y in range(1, years + 1):
        ms = [x for x in monthly if x["year"] == y]
        sales = sum(x["sales"] for x in ms)
        rm = sum(x["raw_material"] for x in ms)
        heads = {k: sum(x["fixed"][k] for x in ms) for k, _ in FIXED_HEADS}
        fixed = sum(heads.values())
        ebitda = sales - rm - fixed
        dep = dep_years[y - 1] + amort
        interest = sum(x["interest"] for x in ms)
        principal = sum(x["principal"] for x in ms)
        pbt = ebitda - dep - interest
        tax = max(0.0, pbt) * d["tax_pct"] / 100
        pat = pbt - tax
        accrual = pat + dep
        drawings = d["drawings_monthly"] * 12
        debt = interest + principal
        # Proprietor's household drawings come out of the profit before the bank is paid, so DSCR is after drawings.
        available = accrual + interest - drawings
        dscr = available / debt if debt > 0 else None
        contribution = sales - rm
        cr = contribution / sales if sales else 0.0
        bep_fixed = fixed + dep + interest
        bep_sales = bep_fixed / cr if cr > 0 else None
        cash_bep = (fixed + interest) / cr if cr > 0 else None
        pl.append({"year": y, "sales": sales, "raw_material": rm, "gross_margin": contribution, "fixed_heads": heads, "fixed": fixed,
                   "ebitda": ebitda, "depreciation": dep, "interest": interest, "pbt": pbt, "tax": tax, "pat": pat,
                   "pat_pct": (pat / sales * 100) if sales else 0.0})
        opening = closing_cash
        closing_cash = opening + accrual - principal - drawings
        cash.append({"year": y, "opening": opening, "cash_accrual": accrual, "principal": principal, "drawings": drawings,
                     "closing": closing_cash})
        dscr_rows.append({"year": y, "pat": pat, "depreciation": dep, "interest": interest, "principal": principal,
                          "drawings": drawings, "available": available, "debt_service": debt, "dscr": dscr,
                          "bep_sales": bep_sales, "bep_pct": (bep_sales / sales * 100) if bep_sales is not None and sales else None,
                          "cash_bep_sales": cash_bep})

    with_debt = [r["dscr"] for r in dscr_rows if r["dscr"] is not None]
    avg_dscr = (sum(r["available"] for r in dscr_rows if r["dscr"] is not None) /
                sum(r["debt_service"] for r in dscr_rows if r["dscr"] is not None)) if with_debt else None
    min_dscr = min(with_debt) if with_debt else None

    # ---- payback: months until cash from operations (after tax and drawings, before loan repayment) covers the project cost
    payback, cum = None, 0.0
    for x in monthly:
        y = x["year"]
        dep_m = (dep_years[y - 1] + amort) / 12
        op = x["sales"] - x["raw_material"] - sum(x["fixed"].values())
        pbt_m = op - dep_m - x["interest"]
        cum += op - max(0.0, pbt_m) * d["tax_pct"] / 100 - d["drawings_monthly"]
        if payback is None and project_cost > 0 and cum >= project_cost:
            payback = x["month"]

    y1 = pl[0]
    first_full = monthly[0]
    m_fixed1 = sum(first_full["fixed"].values())
    summary = {
        "project_cost": project_cost, "capital": capital, "contingency": contingency, "preoperative": preop, "working_capital": wc,
        "own": fin["own"], "subsidy": fin["subsidy"], "grant": fin["grant"], "loan": loan, "excess_funding": excess,
        "own_pct": (fin["own"] / project_cost * 100) if project_cost else 0.0,
        "loan_pct": (loan / project_cost * 100) if project_cost else 0.0,
        "emi": emi_amount, "emi_months": n_emi if loan > 0 else 0,
        "monthly_sales_start": base, "monthly_sales_y1": y1["sales"] / 12,
        "monthly_profit_y1": y1["pat"] / 12, "monthly_fixed_start": m_fixed1,
        "sales_y1": y1["sales"], "pat_y1": y1["pat"], "avg_dscr": avg_dscr, "min_dscr": min_dscr,
        "bep_pct_y1": dscr_rows[0]["bep_pct"], "bep_sales_y1": dscr_rows[0]["bep_sales"],
        "payback_months": payback, "years": years,
        "min_cash": min(c["closing"] for c in cash) if cash else 0.0,
    }
    yearly_sched = []
    for y in range(1, math.ceil(ln["tenure_months"] / 12) + 1 if loan > 0 else 1):
        rows = [r for r in sched if (r["month"] - 1) // 12 + 1 == y]
        if rows:
            yearly_sched.append({"year": y, "opening": rows[0]["opening"], "interest": sum(r["interest"] for r in rows),
                                 "principal": sum(r["principal"] for r in rows), "payment": sum(r["payment"] for r in rows),
                                 "closing": rows[-1]["closing"]})
    return {
        "inputs": d,
        "summary": summary,
        "cost_table": [{"head": i["item"] or "Item", "spec": i["spec"], "qty": i["qty"], "rate": i["rate"], "amount": i["amount"]}
                       for i in d["capital_items"]],
        "sales_table": [{"name": i["name"], "unit": i["unit"], "units_per_day": i["units_per_day"], "price": i["price"],
                         "per_day": i["units_per_day"] * i["price"], "per_month": i["units_per_day"] * i["price"] * s["working_days"]}
                        for i in s["items"]],
        "pl": pl, "cash_flow": cash, "dscr": dscr_rows,
        "repayment": sched, "repayment_yearly": yearly_sched,
        "monthly_y1": [{"month": x["month"], "sales": x["sales"],
                        "profit": x["sales"] - x["raw_material"] - sum(x["fixed"].values()) - x["interest"] - (dep_years[0] + amort) / 12}
                       for x in monthly[:12]],
        "warnings": warnings(d, summary, dscr_rows),
    }


def warnings(d: dict, s: dict, dscr_rows: list[dict]) -> list[dict]:
    """Plain-language checks the DPR officer sees before approving. level: error blocks approval; warn and info do not."""
    out = []

    def add(level, code, text):
        out.append({"level": level, "code": code, "text": text})

    if not d["capital_items"]:
        add("error", "no_items", "Add at least one capital cost item.")
    if not d["sales"]["items"] or s["monthly_sales_start"] <= 0:
        add("error", "no_sales", "Add the sales assumptions (units per day and price).")
    if s["excess_funding"] > 0.5:
        add("error", "over_funded", f"Own money, subsidy and grant are more than the project cost by ₹{s['excess_funding']:,.0f}. Reduce them.")
    if s["project_cost"] > 0 and s["own_pct"] < 5 and s["loan"] > 0:
        add("warn", "low_own", f"Own contribution is {s['own_pct']:.1f}% of the project cost; banks usually expect 5–10% or more.")
    if s["min_dscr"] is not None:
        if s["min_dscr"] < 1.0:
            add("error", "dscr_below_1", f"In some years the business cannot pay the loan instalments (lowest DSCR {s['min_dscr']:.2f}).")
        elif s["min_dscr"] < 1.25:
            add("warn", "dscr_low", f"Lowest DSCR is {s['min_dscr']:.2f}; banks usually look for 1.25 or more.")
    if s["avg_dscr"] is not None and s["avg_dscr"] >= 1.25 and (s["min_dscr"] or 0) >= 1.25:
        add("info", "dscr_ok", f"Average DSCR {s['avg_dscr']:.2f} – comfortable for a bank.")
    bep = s["bep_pct_y1"]
    if bep is not None and bep > 80:
        add("warn", "bep_high", f"Break-even is {bep:.0f}% of year-1 sales – little room if sales are lower than planned.")
    if s["pat_y1"] < 0:
        add("warn", "loss_y1", "The business makes a loss in year 1. Check prices, quantities and expenses.")
    if s["min_cash"] < 0:
        add("warn", "cash_negative", "Cash runs out in a later year after loan repayment and drawings. Lower the drawings or extend the tenure.")
    if d["drawings_monthly"] == 0 and s["loan"] > 0:
        add("warn", "no_drawings", "Owner's household drawings are ₹0. Add what the family needs each month, or the DSCR looks better than it is.")
    if d["sales"]["monthly_growth_pct"] > 5:
        add("warn", "growth_high", f"Monthly sales growth of {d['sales']['monthly_growth_pct']:g}% in year 1 is optimistic.")
    if d["expenses"]["raw_material_pct"] == 0 and d["sales"]["items"]:
        add("warn", "rm_zero", "Raw material is 0% of sales – check whether materials are needed.")
    return out


def headline(result: dict) -> dict:
    """Small set of rounded figures kept on the DPR row for lists and reports."""
    s = result["summary"]
    keys = ("project_cost", "loan", "own", "subsidy", "grant", "emi", "sales_y1", "pat_y1", "avg_dscr", "min_dscr", "bep_pct_y1",
            "payback_months", "monthly_sales_start", "monthly_profit_y1")
    return {k: (round(s[k], 2) if isinstance(s[k], float) else s[k]) for k in keys} | {
        "errors": sum(1 for w in result["warnings"] if w["level"] == "error")}
