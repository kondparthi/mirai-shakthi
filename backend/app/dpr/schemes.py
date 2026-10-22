"""Scheme eligibility (M6) – rules only, no AI guessing. Every check gives a reason the officer can read.

Rule keys a scheme may have (all optional):
  min_age, max_age                 applicant age in years
  activities, sectors              allowed activity types / sector codes (empty = all)
  requires_any                     at least one of: women, sc, st, obc, minority
  new_unit_only                    new (greenfield) units only
  min_project_cost, max_project_cost   number, or {activity: number}
  min_loan, max_loan               bank loan limits
  min_education, education_above_cost  education level needed when the project cost is above the limit for the activity
  own_pct                          {general, special} minimum own contribution, % of project cost
  subsidy_pct                      {general_urban, general_rural, special_urban, special_rural} % of the subsidy base
  subsidy_on                       project_cost | capital (capital = equipment + contingency, without working capital)
  subsidy_cap                      maximum subsidy in ₹
  tiers                            [{name, max}] loan categories (e.g. Mudra Shishu / Kishore / Tarun)
"""
from __future__ import annotations

from datetime import date

from ..models_p1 import EGroup, Entrepreneur
from ..models_p3 import Dpr, EnterpriseModel, Scheme

EDU_ORDER = ["none", "primary", "secondary", "intermediate", "iti", "graduate", "postgraduate"]
SPECIAL = {"sc", "st", "obc", "minority"}
# Standard bank documents, used when no scheme is chosen and as the base of each scheme's list.
DOCS_BASE = [
    {"code": "aadhaar", "label": "Aadhaar", "when": "always"},
    {"code": "pan", "label": "PAN card", "when": "always"},
    {"code": "photo", "label": "Passport-size photos", "when": "always"},
    {"code": "bank_passbook", "label": "Bank passbook / statement (6 months)", "when": "always"},
    {"code": "quotation", "label": "Supplier quotations for equipment", "when": "always"},
    {"code": "dpr", "label": "Detailed Project Report (approved)", "when": "always"},
]
CATEGORY_LABEL = {"women": "women", "sc": "SC", "st": "ST", "obc": "OBC", "minority": "minority"}


def _age(dob: date | None) -> int | None:
    if not dob:
        return None
    t = date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


def _limit(v, activity: str):
    if isinstance(v, dict):
        return v.get(activity, v.get("all"))
    return v


def person_facts(e: Entrepreneur | None, g: EGroup | None) -> dict:
    """What the rules need to know about the applicant. Groups are checked by staff for person rules."""
    if e:
        cats = set()
        if e.gender == "female":
            cats.add("women")
        if e.social_category in SPECIAL:
            cats.add(e.social_category)
        return {"kind": "person", "age": _age(e.dob), "categories": cats, "education": e.education,
                "rural": (e.context_tag or "rural") != "urban", "special": bool(cats)}
    return {"kind": "group", "age": None, "categories": None, "education": None,
            "rural": (g.context_tag if g else "rural") != "urban", "special": None}


def check(scheme: Scheme, facts: dict, *, activity: str, sector: str | None, model: EnterpriseModel | None,
          project_cost: float, capital: float, loan: float) -> dict:
    r = scheme.rules or {}
    checks: list[dict] = []

    def add(ok, text):
        checks.append({"ok": ok, "text": text})  # ok: True pass, False fail, None = staff to check

    if model is not None:
        listed = scheme.code in (model.schemes or [])
        add(listed, f"{'Listed' if listed else 'Not listed'} for the {model.name_en} model")
    if r.get("activities"):
        ok = activity in r["activities"]
        add(ok, f"Activity: {activity.replace('_', ' ')}" + ("" if ok else f" (scheme covers {', '.join(a.replace('_', ' ') for a in r['activities'])})"))
    if r.get("sectors"):
        ok = sector in r["sectors"]
        add(ok, f"Sector {'is covered' if ok else 'is not covered'} ({', '.join(r['sectors'])})")
    age = facts["age"]
    if r.get("min_age") or r.get("max_age"):
        if age is None:
            add(None, "Age: check for the group's applicant")
        else:
            ok = age >= (r.get("min_age") or 0) and (not r.get("max_age") or age <= r["max_age"])
            add(ok, f"Age {age}" + ("" if ok else f" (needs {r.get('min_age') or 0}–{r.get('max_age') or 'no upper limit'})"))
    if r.get("requires_any"):
        names = " / ".join(CATEGORY_LABEL.get(c, c) for c in r["requires_any"])
        if facts["categories"] is None:
            add(None, f"Only for {names} entrepreneurs (groups: 51% holding) – staff to check")
        else:
            ok = bool(facts["categories"] & set(r["requires_any"]))
            add(ok, f"{'Is' if ok else 'Not'} a {names} entrepreneur")
    if r.get("new_unit_only"):
        add(True, "New unit (this DPR is for a new enterprise)")
    lo, hi = _limit(r.get("min_project_cost"), activity), _limit(r.get("max_project_cost"), activity)
    if hi:
        ok = project_cost <= hi
        add(ok, f"Project cost ₹{project_cost:,.0f} {'within' if ok else 'above'} the limit of ₹{hi:,.0f}")
    if lo:
        ok = project_cost >= lo
        add(ok, f"Project cost ₹{project_cost:,.0f} {'meets' if ok else 'below'} the minimum of ₹{lo:,.0f}")
    if r.get("min_loan") or r.get("max_loan"):
        ok = (not r.get("min_loan") or loan >= r["min_loan"]) and (not r.get("max_loan") or loan <= r["max_loan"])
        rng = f"₹{r.get('min_loan') or 0:,.0f}–₹{r.get('max_loan'):,.0f}" if r.get("max_loan") else f"at least ₹{r['min_loan']:,.0f}"
        add(ok, f"Loan ₹{loan:,.0f} {'within' if ok else 'outside'} {rng}")
    edu_min = r.get("min_education")
    if edu_min:
        above = _limit(r.get("education_above_cost"), activity)
        if above is None or project_cost > above:
            if facts["education"] is None:
                add(None, f"Education: {edu_min} or above – staff to check")
            else:
                have = EDU_ORDER.index(facts["education"]) if facts["education"] in EDU_ORDER else -1
                ok = have >= EDU_ORDER.index(edu_min)
                add(ok, f"Education {'meets' if ok else 'below'} the minimum ({edu_min.replace('_', ' ')})")

    special = bool(facts["special"])
    own_rule = r.get("own_pct") or {}
    own_pct = own_rule.get("special" if special else "general", own_rule.get("general", 0)) or 0
    sub_rule = r.get("subsidy_pct") or {}
    key = f"{'special' if special else 'general'}_{'rural' if facts['rural'] else 'urban'}"
    subsidy_pct = sub_rule.get(key, 0) or 0
    base = capital if r.get("subsidy_on") == "capital" else project_cost
    subsidy = base * subsidy_pct / 100
    if r.get("subsidy_cap"):
        subsidy = min(subsidy, r["subsidy_cap"])
    tier = None
    for t in r.get("tiers") or []:
        if loan <= t["max"]:
            tier = t["name"]
            break
    fails = [c for c in checks if c["ok"] is False]
    unsure = [c for c in checks if c["ok"] is None]
    return {
        "code": scheme.code, "name": scheme.name, "name_te": scheme.name_te, "kind": scheme.kind, "url": scheme.url,
        "eligible": not fails, "needs_check": bool(unsure) and not fails, "checks": checks,
        "own_pct": own_pct, "own_amount": round(project_cost * own_pct / 100, 2),
        "subsidy_pct": subsidy_pct, "subsidy": round(subsidy, 2), "subsidy_on": r.get("subsidy_on") or "project_cost",
        "tier": tier, "category": "special" if special else "general", "area": "rural" if facts["rural"] else "urban",
        "sample": scheme.sample, "verified_on": scheme.verified_on.isoformat() if scheme.verified_on else None, "notes": r.get("notes"),
    }


def eligibility(schemes: list[Scheme], dpr: Dpr | None, *, e: Entrepreneur | None = None, g: EGroup | None = None,
                model: EnterpriseModel | None = None, summary: dict | None = None) -> list[dict]:
    """All active schemes, eligible ones first."""
    e = e or (dpr.entrepreneur if dpr else None)
    g = g or (dpr.group if dpr else None)
    model = model or (dpr.model if dpr else None)
    s = summary or {}
    facts = person_facts(e, g)
    activity = dpr.activity if dpr else (model.activity if model else "service")
    sector = model.sector if model else None
    out = [check(sc, facts, activity=activity, sector=sector, model=model, project_cost=s.get("project_cost", 0.0),
                 capital=s.get("capital", 0.0) + s.get("contingency", 0.0), loan=s.get("loan", 0.0))
           for sc in schemes if sc.active]
    return sorted(out, key=lambda x: (not x["eligible"], x["needs_check"], -x["subsidy"]))


def documents_for(scheme: Scheme | None, facts: dict) -> list[dict]:
    """Checklist for an application: the scheme's documents (or the standard bank set) that apply to this applicant."""
    docs = scheme.documents if scheme and scheme.documents else DOCS_BASE
    out, seen = [], set()
    for d in docs:
        when = d.get("when", "always")
        if when == "special" and facts.get("special") is False:
            continue
        if when == "rural" and not facts.get("rural"):
            continue
        if d["code"] in seen:
            continue
        seen.add(d["code"])
        out.append({"code": d["code"], "label": d["label"], "have": False, "file": None, "note": None})
    return out
