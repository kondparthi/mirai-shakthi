"""Form 1.3 – Enterprise readiness assessment.

The score (0–100) is a plain weighted sum that MIRAI can see and change (Admin → Readiness formula):
each question has options, each option earns points, and the question's maximum is its weight. No AI is involved.
"""
from copy import deepcopy

# Each question: label, options {code: (label_en, label_te, points)}, gap advice and the training it suggests.
DEFAULT_FORMULA = {
    "version": 1,
    "questions": {
        "motivation": {
            "label": "Motivation (why they want to start or grow a business)", "label_te": "ప్రేరణ (వ్యాపారం ఎందుకు ప్రారంభించాలనుకుంటున్నారు)",
            "kind": "text", "max": 10, "points_if_given": 10,
            "gap": "Talk through goals and expectations in a counselling session.", "gap_te": "కౌన్సెలింగ్‌లో లక్ష్యాలు, అంచనాలు మాట్లాడండి.",
            "training": "Awareness EDP",
        },
        "experience": {
            "label": "Prior business or sector experience", "label_te": "వ్యాపారం / రంగంలో అనుభవం",
            "options": {"none": ["None", "లేదు", 0], "lt1": ["Less than 1 year", "1 సంవత్సరం లోపు", 5],
                        "1to3": ["1–3 years", "1–3 సంవత్సరాలు", 10], "gt3": ["More than 3 years", "3 సంవత్సరాలకు పైగా", 15]},
            "max": 15, "gap": "Little business experience – start with the Core EDP and an exposure visit to a running unit.",
            "gap_te": "వ్యాపార అనుభవం తక్కువ – కోర్ ఈడీపీ, నడుస్తున్న యూనిట్ సందర్శనతో ప్రారంభించండి.", "training": "Core EDP",
        },
        "time": {
            "label": "Time available for the business", "label_te": "వ్యాపారానికి అందుబాటులో ఉన్న సమయం",
            "options": {"part": ["Part-time", "పార్ట్‌టైమ్", 7], "full": ["Full-time", "ఫుల్‌టైమ్", 15]},
            "max": 15, "gap": "Only part-time – choose a model that fits fewer hours, or plan family help.",
            "gap_te": "పార్ట్‌టైమ్ మాత్రమే – తక్కువ సమయానికి సరిపడే మోడల్ ఎంచుకోండి.", "training": None,
        },
        "family_support": {
            "label": "Family support", "label_te": "కుటుంబ సహకారం",
            "options": {"yes": ["Yes", "ఉంది", 15], "partial": ["Partial", "కొంత", 8], "no": ["No", "లేదు", 0]},
            "max": 15, "gap": "Limited family support – invite the family to an orientation session.",
            "gap_te": "కుటుంబ సహకారం తక్కువ – కుటుంబాన్ని అవగాహన సమావేశానికి ఆహ్వానించండి.", "training": "Awareness EDP",
        },
        "work_space": {
            "label": "Work space available", "label_te": "పని స్థలం",
            "options": {"own": ["Own", "సొంతం", 10], "rented": ["Rented", "అద్దె", 7], "none": ["None", "లేదు", 0]},
            "max": 10, "gap": "No work space yet – include space in the model choice and DPR.",
            "gap_te": "పని స్థలం లేదు – మోడల్ ఎంపిక, డీపీఆర్‌లో స్థలాన్ని చేర్చండి.", "training": None,
        },
        "digital": {
            "label": "Smartphone and digital payment use", "label_te": "స్మార్ట్‌ఫోన్, డిజిటల్ చెల్లింపుల వాడకం",
            "options": {"daily": ["Uses daily", "రోజూ వాడతారు", 10], "sometimes": ["Sometimes", "అప్పుడప్పుడు", 5], "no": ["Does not use", "వాడరు", 0]},
            "max": 10, "gap": "Low digital use – add digital payments and app training.",
            "gap_te": "డిజిటల్ వాడకం తక్కువ – డిజిటల్ చెల్లింపులు, యాప్ శిక్షణ జోడించండి.", "training": "Refresher",
        },
        "credit_history": {
            "label": "Credit history", "label_te": "రుణ చరిత్ర",
            "options": {"none": ["No loans", "రుణాలు లేవు", 5], "repaid": ["Repaid loans", "రుణాలు తీర్చారు", 10],
                        "current": ["Current loan, paying on time", "ప్రస్తుత రుణం, సమయానికి చెల్లిస్తున్నారు", 7], "default": ["Defaulted", "బకాయి పడ్డారు", 0]},
            "max": 10, "gap": "Credit history needs care – include financial literacy before a bank application.",
            "gap_te": "రుణ చరిత్ర జాగ్రత్త – బ్యాంకు దరఖాస్తుకు ముందు ఆర్థిక అక్షరాస్యత శిక్షణ.", "training": "Core EDP",
        },
        "risk": {
            "label": "Risk appetite", "label_te": "రిస్క్ తీసుకునే సామర్థ్యం",
            "options": {"low": ["Low", "తక్కువ", 2], "medium": ["Medium", "మధ్యస్థం", 5], "high": ["High", "ఎక్కువ", 5]},
            "max": 5, "gap": "Low risk appetite – start with a low-investment model.",
            "gap_te": "రిస్క్ సామర్థ్యం తక్కువ – తక్కువ పెట్టుబడి మోడల్‌తో ప్రారంభించండి.", "training": None,
        },
        "investment": {
            "label": "Own funds available (from profile)", "label_te": "సొంత పెట్టుబడి (ప్రొఫైల్ నుండి)",
            "kind": "investment", "max": 10, "bands": [[50000, 10], [10000, 6], [1, 3]],
            "gap": "Little own contribution – plan a scheme with subsidy or a group enterprise.",
            "gap_te": "సొంత పెట్టుబడి తక్కువ – సబ్సిడీ పథకం లేదా గ్రూప్ వ్యాపారం ప్లాన్ చేయండి.", "training": None,
        },
    },
    # Readiness bands for the overall score.
    "bands": [[70, "Ready", "సిద్ధం"], [45, "Nearly ready", "దాదాపు సిద్ధం"], [0, "Needs preparation", "సన్నద్ధత అవసరం"]],
}
QUESTION_ORDER = ["motivation", "experience", "time", "family_support", "work_space", "digital", "credit_history", "risk", "investment"]


def default_formula() -> dict:
    return deepcopy(DEFAULT_FORMULA)


def validate_formula(f: dict) -> None:
    qs = f.get("questions") or {}
    if set(qs) != set(QUESTION_ORDER):
        raise ValueError("The formula must keep all nine questions")
    total = 0
    for code, q in qs.items():
        mx = q.get("max")
        if not isinstance(mx, (int, float)) or mx < 0 or mx > 100:
            raise ValueError(f"{code}: weight must be between 0 and 100")
        for opt, val in (q.get("options") or {}).items():
            if not (isinstance(val, list) and len(val) == 3 and 0 <= val[2] <= mx):
                raise ValueError(f"{code}/{opt}: points must be between 0 and the question's weight ({mx})")
        total += mx
    if round(total) != 100:
        raise ValueError(f"Question weights must add up to 100 (now {total:g})")


def score(answers: dict, investment: float | None, formula: dict, lang: str = "en") -> dict:
    """Return {score, band, breakdown, strengths, gaps, recommended}."""
    te = lang == "te"
    breakdown, strengths, gaps, rec = [], [], [], []
    total = 0.0
    for code in QUESTION_ORDER:
        q = formula["questions"][code]
        mx = float(q["max"])
        if q.get("kind") == "text":
            pts = float(q.get("points_if_given", mx)) if len((answers.get(code) or "").strip()) >= 10 else 0.0
            shown = (answers.get(code) or "").strip()[:80]
        elif q.get("kind") == "investment":
            pts, shown = 0.0, investment
            for limit, p in q.get("bands", []):
                if (investment or 0) >= limit:
                    pts = float(min(p, mx))
                    break
        else:
            opt = (q.get("options") or {}).get(answers.get(code) or "")
            pts = float(opt[2]) if opt else 0.0
            shown = (opt[1] if te else opt[0]) if opt else None
        pts = min(pts, mx)
        total += pts
        label = q.get("label_te") if te and q.get("label_te") else q["label"]
        breakdown.append({"code": code, "label": label, "answer": shown, "points": round(pts, 1), "max": mx})
        if mx and pts >= 0.7 * mx:
            strengths.append(label)
        elif mx and pts < 0.5 * mx:
            gaps.append({"code": code, "label": label, "advice": (q.get("gap_te") if te and q.get("gap_te") else q.get("gap"))})
            if q.get("training") and q["training"] not in rec:
                rec.append(q["training"])
    s = int(round(total))
    band = next((b for b in formula.get("bands", []) if s >= b[0]), [0, "", ""])
    return {"score": s, "band": band[2] if te else band[1], "breakdown": breakdown, "strengths": strengths, "gaps": gaps,
            "recommended": rec or ["Core EDP"]}


def questions_for_form(formula: dict, lang: str = "en") -> list[dict]:
    """The questions as the forms show them (option labels in the user's language)."""
    te = lang == "te"
    out = []
    for code in QUESTION_ORDER:
        q = formula["questions"][code]
        if q.get("kind") == "investment":
            continue
        out.append({"code": code, "label": q.get("label_te") if te and q.get("label_te") else q["label"], "kind": q.get("kind", "choice"),
                    "options": [[k, v[1] if te else v[0]] for k, v in (q.get("options") or {}).items()]})
    return out
