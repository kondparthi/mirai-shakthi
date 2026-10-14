"""Sprint 5 – Telugu questions, answers and profile labels."""
import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.guidance import intents
from app.models import Intent

from .conftest import PROFILE, login

TELUGU = intents.TELUGU


def test_every_sample_question_finds_its_topic():
    db = SessionLocal()
    try:
        for it in db.scalars(select(Intent).where(Intent.active.is_(True))):
            for q in it.sample_questions or []:
                got, _, _ = intents.classify(db, q)
                assert got and got.code == it.code, f"{q!r} → {got.code if got else None}, expected {it.code}"
    finally:
        db.close()


@pytest.mark.parametrize("question,code", [
    ("ఎగుమతులకు ఏమి కావాలి", "export_start"),              # inflected form of ఎగుమతి
    ("రుణానికి ఏ పత్రాలు కావాలి", "loan_readiness"),          # రుణం → రుణానికి
    ("అమెజాన్‌లో ఎలా అమ్మాలి", "sell_online"),                # zero-width joiner inside the word
    ("ఉత్పత్తి లేబుల్‌పై ఏమి ముద్రించాలి", "packaging_labelling"),  # "print" must not match the Mudra scheme
    ("పనివారికి పీఎఫ్ అవసరమా", "labour_compliance"),
])
def test_free_telugu_questions(question, code):
    db = SessionLocal()
    try:
        got, _, _ = intents.classify(db, question)
        assert got and got.code == code
    finally:
        db.close()


def test_answer_in_telugu_with_telugu_sources(client):
    h = login(client, "9000005001")
    client.put("/api/v1/profile", json=PROFILE, headers=h)
    r = client.post("/api/v1/guidance/ask", headers=h, json={"question": "నాకు జీఎస్టీ రిజిస్ట్రేషన్ అవసరమా?", "language": "te"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["understanding"]["intent_code"] == "gst_registration"
    assert TELUGU.search(b["understanding"]["intent_title"])
    assert TELUGU.search(b["information"]["answer"])
    # Telugu source for the topic, and no English duplicate of the same topic
    titles = [s["title"] for s in b["information"]["sources"]]
    assert titles and TELUGU.search(titles[0])
    assert "GST registration basics for small businesses" not in titles
    # Next steps and profile summary in Telugu
    assert all(TELUGU.search(s["title"]) and TELUGU.search(s["why"] or "") for s in b["guidance"]["steps"])
    assert any(TELUGU.search(x) for x in b["understanding"]["profile_summary"])


def test_english_user_never_sees_telugu_sources(client):
    h = login(client, "9000005002")
    client.put("/api/v1/profile", json=PROFILE, headers=h)
    b = client.post("/api/v1/guidance/ask", headers=h, json={"question": "Do I need GST registration?", "language": "en"}).json()
    assert b["information"]["sources"]
    assert not any(TELUGU.search(s["title"]) for s in b["information"]["sources"])
    assert not TELUGU.search(b["information"]["answer"])


def test_telugu_profile_options_and_home_questions(client):
    o = client.get("/api/v1/profile/options?lang=te").json()
    assert dict(o["stage"])["planning"] == "ప్రారంభించాలనుకుంటున్నాను"
    assert o["labels"]["Food"] == "ఆహారం"
    assert dict(client.get("/api/v1/profile/options").json()["stage"])["planning"] == "Planning to start"
    mods = client.get("/api/v1/guidance/modules?lang=te").json()
    assert all(TELUGU.search(q) for m in mods for q in m["popular_questions"])
