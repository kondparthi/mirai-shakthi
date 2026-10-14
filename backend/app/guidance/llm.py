"""AI provider wrapper. Personal identifiers are masked before any text leaves the server.

AI_PROVIDER=none      -> no external calls; the engine uses its built-in composer (demo / offline mode).
AI_PROVIDER=anthropic -> uses the Anthropic Messages API with ANTHROPIC_API_KEY and AI_MODEL.
"""
import json
import logging
import re

from ..config import settings

log = logging.getLogger("mirai.llm")

_PATTERNS = [
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[AADHAAR]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[PAN]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"), "[PHONE]"),
    (re.compile(r"\b\d{9,18}\b"), "[ACCOUNT]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
]


def mask_pii(text: str) -> str:
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text


def enabled() -> bool:
    return settings.AI_PROVIDER == "anthropic" and bool(settings.ANTHROPIC_API_KEY)


def complete(system: str, user: str, max_tokens: int | None = None) -> str | None:
    """Return model text, or None if AI is disabled or the call fails (caller falls back)."""
    if not enabled():
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=45)
        resp = client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=max_tokens or settings.AI_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": mask_pii(user)}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    except Exception as exc:  # network, quota, model errors -> fall back to built-in composer
        log.warning("AI call failed, using fallback: %s", exc)
        return None


def complete_json(system: str, user: str, max_tokens: int = 400) -> dict | None:
    text = complete(system + "\nReply with a single JSON object only.", user, max_tokens)
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
