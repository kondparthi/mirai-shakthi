"""Step 1 – Understanding: decide which module and intent a question belongs to."""
import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Intent
from . import llm

WORD = re.compile(r"[\wఀ-౿]+", re.U)
TELUGU = re.compile(r"[ఀ-౿]")


def norm(text: str) -> str:
    """Lower-case and drop zero-width joiners, which Telugu words often contain (ఆన్‌లైన్ = ఆన్లైన్)."""
    return text.lower().replace("\u200c", "").replace("\u200d", "")


def _tokens(text: str) -> set[str]:
    return set(WORD.findall(norm(text)))


# Telugu vowel signs, virama and nasal marks: an inflection usually changes these at the end of the word.
TE_TAIL = "\u0c01\u0c02\u0c03\u0c3e\u0c3f\u0c40\u0c41\u0c42\u0c43\u0c44\u0c46\u0c47\u0c48\u0c4a\u0c4b\u0c4c\u0c4d\u0c55\u0c56"


def _kw_hits(kw: str, q: str, qtok: set[str]) -> set[str]:
    """Return the question tokens a keyword matches (phrases match as a whole).
    A stem also matches longer words: "export" → "exporting"; Telugu "ఎగుమతి" → "ఎగుమతులకు", "రుణం" → "రుణానికి"."""
    if " " in kw:
        return {kw} if kw in q else set()
    if TELUGU.search(kw):
        stem = kw.rstrip(TE_TAIL)
        return {t for t in qtok if t == kw or (len(stem) >= 3 and t.startswith(stem))}
    return {t for t in qtok if t == kw or (len(kw) >= 5 and t.startswith(kw))}


def keyword_scores(question: str, intents: list[Intent], module: str | None = None) -> list[tuple[float, Intent]]:
    q = " ".join(WORD.findall(norm(question)))
    qtok = _tokens(question)
    n = max(len(intents), 1)
    # Rarer keywords (used by fewer intents) are stronger signals.
    df: dict[str, int] = {}
    for it in intents:
        for kw in {norm(k) for k in it.keywords or []}:
            df[kw] = df.get(kw, 0) + 1
    scored = []
    for it in intents:
        matched: dict[str, float] = {}
        for kw in {norm(k) for k in it.keywords or []}:
            weight = (2.0 if " " in kw else 1.0) * (1 + math.log(n / df[kw]))
            for hit in _kw_hits(kw, q, qtok):
                # Each token counts once per intent; an exact word counts a little more than a stem match.
                matched[hit] = max(matched.get(hit, 0), weight if hit == kw else weight * 0.9)
        score = sum(matched.values())
        if score and module and it.module == module:
            score += 1.0
        if score:
            scored.append((score, it))
    scored.sort(key=lambda s: s[0], reverse=True)
    return scored


def related(db: Session, question: str, chosen: Intent | None, limit: int = 2) -> list[Intent]:
    """Other topics the question also touches (e.g. 'sell on Amazon and export')."""
    intents = list(db.scalars(select(Intent).where(Intent.active.is_(True))))
    scored = keyword_scores(question, intents)
    if not scored:
        return []
    top = scored[0][0]
    return [it for sc, it in scored if (chosen is None or it.id != chosen.id) and sc >= 0.5 * top][:limit]


def classify(db: Session, question: str, module: str | None = None) -> tuple[Intent | None, float, str]:
    """Return (intent, confidence 0..1, method)."""
    intents = list(db.scalars(select(Intent).where(Intent.active.is_(True))))
    if llm.enabled():
        catalogue = "\n".join(f"- {i.code} ({i.module}): {i.title_en}" for i in intents)
        result = llm.complete_json(
            "You route questions from Indian MSME owners to one intent from a fixed list. "
            "If none fits, use intent \"none\". Confidence is 0 to 1.",
            f"Intents:\n{catalogue}\n\nPreferred module: {module or 'any'}\nQuestion: {question}\n"
            'JSON format: {"intent": "<code>", "confidence": 0.0}',
        )
        if result:
            code = result.get("intent")
            match = next((i for i in intents if i.code == code), None)
            if match:
                return match, float(result.get("confidence", 0.7)), "ai"
    scored = keyword_scores(question, intents, module)
    if not scored:
        # Unrecognised questions stay unmatched: the user is offered an expert and the
        # question appears in Answer review so staff can add a topic or keywords.
        return None, 0.0, "keywords"
    top, best = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0
    margin = (top - second) / top
    confidence = min(0.95, 0.3 + 0.08 * top + 0.3 * margin)
    return best, round(confidence, 2), "keywords"
