"""The five-step guidance flow: Understanding → Identification → Information → Guidance → Connect."""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..labels_te import LABELS_TE, te
from ..models import TURNOVER_BANDS, Expert, Intent, KbItem, MsmeProfile
from . import intents as intent_mod
from . import llm, retrieval
from .intents import TELUGU
from .rules import evaluate

MODULE_LABELS = {
    "microfin": {"en": "MicroFin", "te": "మైక్రోఫిన్", "area": "Financial management, cash flow & receivables", "area_te": "ఆర్థిక నిర్వహణ, నగదు ప్రవాహం & బకాయిలు"},
    "marketkonnect": {"en": "MarketKonnect", "te": "మార్కెట్ కనెక్ట్", "area": "Sales & market enablement", "area_te": "అమ్మకాలు & మార్కెట్ అవకాశాలు"},
    "launchpad": {"en": "Launch Pad / Export Ready", "te": "లాంచ్ ప్యాడ్ / ఎగుమతి", "area": "Compliance, schemes & export", "area_te": "అనుమతులు, పథకాలు & ఎగుమతి"},
    "skillspro": {"en": "SkillsPro", "te": "స్కిల్స్ ప్రో", "area": "Human resources, workforce & training", "area_te": "సిబ్బంది, ఉద్యోగులు & శిక్షణ"},
    "handholding": {"en": "Handholding", "te": "హ్యాండ్‌హోల్డింగ్", "area": "Mentors, experts & institutions", "area_te": "మెంటార్లు, నిపుణులు & సంస్థలు"},
}

STAGE_LABELS = {"planning": "Planning to start", "lt1": "Running < 1 year", "1to3": "Running 1–3 years", "gt3": "Running > 3 years"}
REG_LABELS = {"udyam": "Udyam", "gst": "GST", "fssai": "FSSAI", "trade": "Trade licence", "iec": "IEC", "shop_est": "Shop & Establishment"}

# Fixed sentences of the built-in composer. Telugu is a draft for MIRAI to review.
TEXT = {
    "no_source": {
        "en": "I could not find verified information on this yet. You can rephrase the question, pick a topic "
              "below, or ask an expert through Handholding.",
        "te": "దీనిపై ధృవీకరించిన సమాచారం ఇంకా దొరకలేదు. ప్రశ్నను మరోలా అడగండి, కింద ఒక అంశం ఎంచుకోండి, "
              "లేదా హ్యాండ్‌హోల్డింగ్ ద్వారా నిపుణుడిని అడగండి.",
    },
    "gaps": {
        "en": "For “{t}”, you have {h} of {n} basic items; the {m} missing item(s) are listed as next steps below.",
        "te": "“{t}” కోసం {n} ప్రాథమిక అంశాల్లో మీ దగ్గర {h} ఉన్నాయి; లేని {m} అంశాలు కింద తదుపరి దశలుగా ఉన్నాయి.",
    },
    "all_done": {
        "en": "For “{t}”, you already have everything on the basic list.",
        "te": "“{t}” కోసం ప్రాథమిక జాబితాలోని అన్నీ మీ దగ్గర ఇప్పటికే ఉన్నాయి.",
    },
    "profile_first": {
        "en": "Please complete your business profile first so the advice fits your business.",
        "te": "సలహా మీ వ్యాపారానికి సరిపడేలా ఉండాలంటే ముందుగా మీ వ్యాపార వివరాలు పూర్తి చేయండి.",
    },
    "r_no_source": {"en": "We could not find verified information for this.", "te": "దీనికి ధృవీకరించిన సమాచారం దొరకలేదు."},
    "r_many": {"en": "An expert can do these steps for you.", "te": "ఈ దశలను నిపుణుడు మీ కోసం చేయగలరు."},
    "r_default": {"en": "Talk to an expert for help with this.", "te": "దీనిలో సహాయానికి నిపుణుడితో మాట్లాడండి."},
}


def tr(key: str, lang: str, **kw) -> str:
    d = TEXT[key]
    return (d.get(lang) or d["en"]).format(**kw)


def intent_title(intent: Intent, lang: str) -> str:
    return intent.title_te if lang == "te" and intent.title_te else intent.title_en


def sample_question(intent: Intent, lang: str) -> str:
    """First sample question in the user's language (Telugu questions are stored in the same list)."""
    qs = intent.sample_questions or []
    want_te = lang == "te"
    for q in qs:
        if bool(TELUGU.search(q)) == want_te:
            return q
    return qs[0] if qs else intent_title(intent, lang)


REQUIRED_PROFILE = ("stage", "business_type", "sector", "district", "turnover_band", "employees")


def profile_dict(p: MsmeProfile | None) -> dict:
    if not p:
        return {}
    return {
        "stage": p.stage, "business_type": p.business_type, "sector": (p.sector or "").lower(),
        "product": p.product, "district": p.district, "mandal": p.mandal, "ownership": p.ownership,
        "turnover_band": p.turnover_band, "employees": p.employees,
        "registrations": p.registrations or [], "channels": p.channels or [],
        "books_kept": p.books_kept, "has_loan": p.has_loan, "flags": p.flags or [],
    }


def profile_summary(pd: dict, lang: str = "en") -> list[str]:
    if not pd:
        return []
    L = lambda x: te(x, lang)  # noqa: E731
    sector = pd.get("sector") or ""
    sector_label = next((k for k in LABELS_TE if k.lower() == sector), sector.capitalize())
    regs = ", ".join(L(REG_LABELS.get(r, r)) for r in pd.get("registrations") or []) or ("లేవు" if lang == "te" else "none")
    people = pd.get("employees")
    out = [
        L(STAGE_LABELS.get(pd.get("stage") or "", "")),
        L((pd.get("business_type") or "").capitalize()),
        L(sector_label),
        pd.get("district") or "",
        L(TURNOVER_BANDS.get(pd.get("turnover_band"), "")),
        (f"{people} మంది పని చేస్తున్నారు" if lang == "te" else f"{people} people working") if people is not None else "",
        ("రిజిస్ట్రేషన్లు: " if lang == "te" else "Registrations: ") + regs,
    ]
    return [x for x in out if x]


def missing_profile_fields(pd: dict) -> list[str]:
    return [f for f in REQUIRED_PROFILE if pd.get(f) in (None, "")]


def identify_gaps(intent: Intent, pd: dict, lang: str) -> tuple[list[dict], list[dict]]:
    have, missing = [], []
    for r in intent.rules:
        if not r.active or not evaluate(r.condition, pd):
            continue
        item = {
            "code": r.item_code,
            "title": (r.title_te if lang == "te" and r.title_te else r.title_en),
            "why": (r.why_te if lang == "te" and r.why_te else r.why_en),
            "order": r.step_order,
            "documents": r.documents,
            "time": r.time_estimate,
            "cost": r.cost_note,
            "link": r.official_link,
        }
        (have if r.have_check and evaluate(r.have_check, pd) else missing).append(item)
    return have, missing


def _first_sentences(text: str, n: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n])


def compose_answer(question: str, intent: Intent | None, pd: dict, have: list, missing: list,
                   sources: list[KbItem], lang: str) -> tuple[str, str]:
    """Return (answer text, method). Uses AI when enabled, otherwise a built-in composer."""
    if sources and llm.enabled():
        src = "\n\n".join(f"[{i + 1}] {s.title}\n{s.body}" for i, s in enumerate(sources))
        gaps = "\n".join(f"- missing: {m['title']}" for m in missing) or "- none"
        system = (
            "You are the MIRAI Shakthi MSME guidance assistant for small businesses in India. "
            "Answer ONLY from the numbered sources provided; cite them like [1]. If the sources do not answer "
            "the question, say so plainly and suggest talking to an expert. Use simple words, short sentences, "
            "at most 150 words. Do not give final legal or tax advice; say when a professional should confirm. "
            f"Reply in {'Telugu' if lang == 'te' else 'English'}."
        )
        user = (
            f"Business profile: {'; '.join(profile_summary(pd))}\n"
            f"Topic: {intent.title_en if intent else 'general'}\nGaps found:\n{gaps}\n\n"
            f"Sources:\n{src}\n\nQuestion: {question}"
        )
        text = llm.complete(system, user)
        if text:
            return text, "ai"
    # Built-in composer (demo / offline mode): grounded only in the retrieved sources.
    if not sources:
        return tr("no_source", lang), "fallback"
    lines = []
    if intent and missing:
        lines.append(tr("gaps", lang, t=intent_title(intent, lang), h=len(have), n=len(have) + len(missing), m=len(missing)))
    elif intent and have:
        lines.append(tr("all_done", lang, t=intent_title(intent, lang)))
    for i, s in enumerate(sources[:2]):
        lines.append(f"{_first_sentences(s.body)} [{i + 1}]")
    return "\n\n".join(lines), "composer"


def match_experts(db: Session, service: str | None, pd: dict, lang: str, limit: int = 3) -> list[dict]:
    if not service:
        return []
    district = (pd.get("district") or "").lower()
    scored = []
    for e in db.scalars(select(Expert).where(Expert.status == "approved")):
        if service not in (e.services or []):
            continue
        dists = [d.lower() for d in e.districts or []]
        if district and district not in dists and "all" not in dists:
            continue
        score = (2 if district in dists else 0) + (1 if lang in (e.languages or []) else 0) + (e.rating or 0) / 5
        scored.append((score, e))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [
        {"id": e.id, "name": e.name, "organisation": e.organisation, "type": e.expert_type,
         "fee_note": e.fee_note, "response_hours": e.response_hours, "rating": e.rating,
         "languages": e.languages}
        for _, e in scored[:limit]
    ]


def run(db: Session, question: str, profile: MsmeProfile | None, lang: str = "en",
        module: str | None = None) -> dict:
    pd = profile_dict(profile)

    # 1. Understanding
    need_fields = missing_profile_fields(pd)
    intent, confidence, method = intent_mod.classify(db, question, module)
    mod = intent.module if intent else module
    understanding = {
        "module": mod,
        "module_label": MODULE_LABELS.get(mod, {}).get(lang if lang == "te" else "en") if mod else None,
        "intent_code": intent.code if intent else None,
        "intent_title": intent_title(intent, lang) if intent else None,
        "confidence": confidence,
        "method": method,
        "profile_summary": profile_summary(pd, lang),
        "missing_profile_fields": need_fields,
    }
    if need_fields:
        return {"current_step": 1, "understanding": understanding,
                "message": tr("profile_first", lang)}

    # 2. Identification
    have, missing = identify_gaps(intent, pd, lang) if intent else ([], [])

    # 3. Information
    sources = retrieval.search(db, question, mod, intent.code if intent else None, lang=lang)
    answer, answer_method = compose_answer(question, intent, pd, have, missing, sources, lang)
    information = {
        "answer": answer,
        "method": answer_method,
        "grounded": bool(sources),
        "sources": [{"n": i + 1, "title": s.title, "url": s.source_url,
                     "verified_on": s.verified_on.isoformat() if s.verified_on else None,
                     "verified_by": s.verified_by} for i, s in enumerate(sources)],
    }

    # 4. Guidance
    steps = sorted(missing, key=lambda m: m["order"])
    guidance = {"steps": [{**s, "n": i + 1} for i, s in enumerate(steps)]}

    # 5. Connect
    service = intent.connect_service if intent else "general_advice"
    suggest = (not sources) or confidence < 0.5 or len(missing) >= 3 or (intent and intent.module == "handholding")
    connect = {"service": service, "suggested": bool(suggest),
               "reason": tr("r_no_source" if not sources else "r_many" if len(missing) >= 3 else "r_default", lang),
               "experts": match_experts(db, service, pd, lang)}

    understanding["related"] = [
        {"code": r.code, "title": intent_title(r, lang), "question": sample_question(r, lang)}
        for r in intent_mod.related(db, question, intent)
    ]
    return {
        "current_step": 5,
        "understanding": understanding,
        "identification": {"have": have, "missing": missing},
        "information": information,
        "guidance": guidance,
        "connect": connect,
    }
