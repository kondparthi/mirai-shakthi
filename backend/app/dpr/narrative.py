"""Narrative sections of the DPR (M5). The AI writes words only, from the officer's notes and the figures the finance
engine calculated; it must not invent numbers. Without an AI key (or if the call fails) a template writes a plain draft.
The DPR officer edits and approves every section."""
from __future__ import annotations

from ..guidance import llm

SECTIONS = [
    ("promoter", "Promoter background"),
    ("business", "The business"),
    ("market", "Market and demand"),
    ("operations", "Operations plan"),
    ("swot", "SWOT analysis"),
    ("risks", "Risks and how they are managed"),
    ("conclusion", "Conclusion"),
]
NOTE_FIELDS = [
    ("promoter", "Promoter background", "Family, experience, why this business, training done"),
    ("market", "Market", "Spot, customers, nearby businesses, institutional buyers, prices of others"),
    ("operations", "Operations", "Timings, staff, suppliers, how sales are recorded"),
    ("swot", "Strengths, weaknesses, opportunities, threats", "Anything the officer noticed"),
]

SYSTEM = (
    "You write the narrative sections of a Detailed Project Report (DPR) that an Indian bank will read for a micro-enterprise loan. "
    "Write in clear, formal English for a bank officer, in the third person. Use ONLY the facts and figures given. "
    "Never invent numbers, names, places, customers or approvals; if something is not given, leave it out. "
    "Amounts are in Indian rupees; write them as ₹ with Indian digit grouping exactly as given. Keep each section to 60–140 words. "
    "For swot write four short lines starting 'Strengths:', 'Weaknesses:', 'Opportunities:', 'Threats:'. "
    "Return JSON with the keys: " + ", ".join(k for k, _ in SECTIONS) + "."
)


def inr(v: float | None) -> str:
    """₹ with Indian grouping (12,34,567)."""
    if v is None:
        return "—"
    neg, n = v < 0, int(round(abs(v)))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return f"{'-' if neg else ''}₹{s}"


def facts(ctx: dict, result: dict) -> dict:
    """Everything the writer may use – kept small and free of ID numbers."""
    s = result["summary"]
    return {
        "unit_name": ctx["unit_name"], "location": ctx["location"], "promoter": ctx["promoter"], "model": ctx["model"],
        "activity": ctx["activity"], "scheme": ctx.get("scheme"), "jobs": ctx.get("jobs"),
        "products": [f"{i['name']} – {i['units_per_day']:g} {i['unit']} a day at {inr(i['price'])}" for i in result["sales_table"]],
        "equipment": [f"{i['head']} × {i['qty']:g}" for i in result["cost_table"]],
        "figures": {
            "project_cost": inr(s["project_cost"]), "own_contribution": inr(s["own"]), "bank_loan": inr(s["loan"]),
            "subsidy": inr(s["subsidy"]), "grant": inr(s["grant"]), "monthly_emi": inr(s["emi"]), "emi_months": s["emi_months"],
            "sales_month_1": inr(s["monthly_sales_start"]), "sales_year_1": inr(s["sales_y1"]), "profit_year_1": inr(s["pat_y1"]),
            "average_dscr": f"{s['avg_dscr']:.2f}" if s["avg_dscr"] is not None else None,
            "break_even_pct_of_sales_y1": f"{s['bep_pct_y1']:.0f}%" if s["bep_pct_y1"] is not None else None,
            "payback_months": s["payback_months"],
        },
        "officer_notes": {k: v for k, v in (ctx.get("notes") or {}).items() if v},
    }


def template(f: dict) -> dict:
    """Plain draft used when AI is off."""
    p, fig, notes = f["promoter"], f["figures"], f["officer_notes"]
    bits = [f"{p['name']}"]
    if p.get("age"):
        bits.append(f"aged {p['age']}")
    who = ", ".join(bits)
    edu = f" has studied up to {p['education']}" if p.get("education") else ""
    occ = f" and currently works as {p['occupation'].lower()}" if p.get("occupation") else ""
    skills = f" The promoter has skills in {', '.join(p['skills']).lower()}." if p.get("skills") else ""
    training = f" The promoter has completed {', '.join(p['training'])} under the MIRAI Shakthi programme." if p.get("training") else ""
    promoter = f"{who}, from {p.get('home') or f['location']},{edu}{occ}.{skills}{training}"
    if notes.get("promoter"):
        promoter += " " + notes["promoter"].strip()
    business = (f"{f['unit_name']} is a new {f['model']['name']} unit ({f['activity'].replace('_', ' ')}) at {f['location']}. "
                f"{f['model'].get('description') or ''} The unit will offer: {'; '.join(f['products'])}.").replace("  ", " ")
    market = (f"Sales are planned at {fig['sales_month_1']} in the first month, rising to {fig['sales_year_1']} in the first year. ")
    market += notes.get("market", "").strip() or "Demand at the chosen location was assessed by the MIRAI field team."
    ops = (f"The unit will use {', '.join(f['equipment'])}. ") + (notes.get("operations", "").strip()
                                                                      or "Daily sales and purchases will be recorded in the MIRAI app, with a monthly review by the mentor.")
    if f.get("jobs"):
        ops += f" The unit is expected to provide work for {f['jobs']} people including the promoter."
    swot = ("Strengths: trained promoter, low fixed costs, support from the MIRAI programme.\n"
            "Weaknesses: new business with no trading history.\n"
            "Opportunities: growing demand and orders from local institutions.\n"
            "Threats: competition and price changes of raw materials.")
    if notes.get("swot"):
        swot += "\n" + notes["swot"].strip()
    risks = ("Sales lower than planned – the mentor reviews sales every month and helps with marketing. "
             "Price rise of materials – prices are reviewed every quarter. "
             "Equipment breakdown – equipment is bought from approved suppliers with warranty and insured.")
    funding = f"The project cost of {fig['project_cost']} is met by the promoter's contribution of {fig['own_contribution']}"
    if fig["bank_loan"] != "₹0":
        funding += f" and a bank loan of {fig['bank_loan']}, repaid in {fig['emi_months']} monthly instalments of {fig['monthly_emi']}"
    if fig["subsidy"] != "₹0":
        funding += f", with a subsidy of {fig['subsidy']}" + (f" under {f['scheme']}" if f.get("scheme") else "")
    funding += "."
    tail = []
    if fig["average_dscr"]:
        tail.append(f"an average debt service coverage ratio of {fig['average_dscr']}")
    if fig["break_even_pct_of_sales_y1"]:
        tail.append(f"break-even at {fig['break_even_pct_of_sales_y1']} of first-year sales")
    conclusion = funding + (" The projections show " + " and ".join(tail) + ". " if tail else " ") + \
        "The project is technically feasible and financially viable, and is recommended for financial assistance."
    return {"promoter": promoter, "business": business, "market": market, "operations": ops, "swot": swot, "risks": risks,
            "conclusion": conclusion}


def draft(ctx: dict, result: dict) -> tuple[dict, str]:
    """(sections, source) – source is "ai" or "template"."""
    import json

    f = facts(ctx, result)
    base = template(f)
    got = llm.complete_json(SYSTEM, json.dumps(f, ensure_ascii=False), max_tokens=2200)
    if not got:
        return base, "template"
    def text(v):
        if isinstance(v, dict):  # e.g. {"Strengths": [...], ...}
            return "\n".join(f"{k}: {'; '.join(x) if isinstance(x, list) else x}" for k, x in v.items())
        if isinstance(v, list):
            return "\n".join(str(x) for x in v)
        return str(v or "").strip()

    out = {k: (text(got.get(k)) or base[k]) for k, _ in SECTIONS}
    return out, "ai"
