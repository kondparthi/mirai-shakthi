"""Step 3 – Information: find verified content. Uses MySQL FULLTEXT search, filtered to
published items that are not past their review date."""
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.dialects.mysql import match as mysql_match
from sqlalchemy.orm import Session

from ..models import KbItem


def search(db: Session, question: str, module: str | None, intent_code: str | None, limit: int = 4,
           lang: str = "en") -> list[KbItem]:
    """English users see English content only. Telugu users see Telugu content first and English content
    only for topics that have no Telugu item yet."""
    today = date.today()
    langs = ["te", "en"] if lang == "te" else ["en"]
    base = select(KbItem).where(
        KbItem.status == "published",
        KbItem.language.in_(langs),
        or_(KbItem.review_due.is_(None), KbItem.review_due >= today),
    )
    results: list[KbItem] = []
    # 1. Content written for this exact intent comes first, in the user's language when available.
    if intent_code:
        items = list(db.scalars(base.where(KbItem.intent_code == intent_code).order_by(KbItem.id)))
        own = [i for i in items if i.language == lang]
        results.extend((own or items)[:limit])
    # 2. Full-text match within the module, then across all modules.
    if len(results) < limit:
        match = mysql_match(KbItem.title, KbItem.body, against=question).in_natural_language_mode()
        q = base.where(match).order_by(match.desc())
        if module:
            q = q.where(KbItem.module == module)
        for item in db.scalars(q.limit(limit)):
            if item not in results:
                results.append(item)
    if lang == "te":
        # Drop an English item when the same topic is already covered in Telugu.
        te_topics = {r.intent_code for r in results if r.language == "te" and r.intent_code}
        results = [r for r in results if r.language == "te" or r.intent_code not in te_topics]
    return results[:limit]
