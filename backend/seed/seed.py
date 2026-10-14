"""Create tables and load starter data.  Usage:  python -m seed.seed  [--reset]

--reset drops all tables first (development only).
Admin login is created from ADMIN_EMAIL / ADMIN_PASSWORD (defaults printed below).
"""
import os
import sys
from datetime import date, timedelta

from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import Expert, Intent, KbItem, RequirementRule, User
from app.security import hash_secret
from seed.data import EXPERTS, INTENTS, KB, SAMPLE_VERIFIER
from seed.data_te import REMOVED_KEYWORDS, REPLACED_QUESTIONS, TE_KB, TE_KEYWORDS, TE_QUESTIONS, TE_RULES


def ensure_database() -> None:
    """Create the MySQL database named in DATABASE_URL if it does not exist yet."""
    from sqlalchemy import URL, create_engine, text

    url = engine.url  # keep the URL object: str() would hide the password
    name = url.database
    if not name or not url.drivername.startswith("mysql"):
        return
    # Same server and login, but no database selected (URL.set ignores None, so build it fresh).
    server_url = URL.create(url.drivername, url.username, url.password, url.host, url.port, None, url.query)
    server = create_engine(server_url, future=True)
    with server.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    server.dispose()


def ensure_columns() -> None:
    """Add columns introduced in later sprints to tables that already exist (create_all only makes new tables)."""
    from sqlalchemy import inspect, text
    from sqlalchemy.schema import CreateColumn

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have:
                    ddl = CreateColumn(col).compile(dialect=engine.dialect)
                    conn.execute(text(f"ALTER TABLE `{table.name}` ADD COLUMN {ddl}"))
                    print(f"Added column {table.name}.{col.name}")


def load_telugu(db) -> None:
    """Sprint 5: Telugu keywords, sample questions, requirement texts and knowledge items (draft, MIRAI to review).
    Only fills what is empty, so edits made in the admin portal are kept."""
    for it in db.scalars(select(Intent)):
        drop = REMOVED_KEYWORDS.get(it.code, [])
        if any(k in (it.keywords or []) for k in drop):
            it.keywords = [k for k in it.keywords if k not in drop]
        if any(q in REPLACED_QUESTIONS for q in it.sample_questions or []):
            it.sample_questions = [REPLACED_QUESTIONS.get(q, q) for q in it.sample_questions]
        extra = [k for k in TE_KEYWORDS.get(it.code, []) if k not in (it.keywords or [])]
        if extra:
            it.keywords = list(it.keywords or []) + extra
        q = TE_QUESTIONS.get(it.code)
        if q and q not in (it.sample_questions or []):
            it.sample_questions = list(it.sample_questions or []) + [q]
    for r in db.scalars(select(RequirementRule)):
        title, why = TE_RULES.get(r.item_code, (None, None))
        if title and not r.title_te:
            r.title_te = title
        if why and not r.why_te:
            r.why_te = why
    today = date.today()
    for title, module, intent_code, body, url in TE_KB:
        if not db.scalar(select(KbItem).where(KbItem.title == title)):
            db.add(KbItem(title=title, module=module, intent_code=intent_code, body=body, source_url=url,
                          verified_by=SAMPLE_VERIFIER, verified_on=today, review_due=today + timedelta(days=365),
                          status="published", language="te"))


def load_masters(db) -> None:
    """Phase 1: starter master data and the default readiness formula. Adds only what is missing."""
    from app.models_p1 import MasterItem, Setting
    from app.programme.readiness import default_formula
    from seed.data_p1 import CONTEXT_TAGS, DISTRICTS, GUNTUR_MANDALS, SAMPLE_VILLAGES, SECTORS, SIMPLE

    have = {(m.kind, m.code): m for m in db.scalars(select(MasterItem))}

    def add(kind, code, en, te, parent=None, data=None, sort=100):
        if (kind, code) in have:
            return have[(kind, code)]
        m = MasterItem(kind=kind, code=code, name_en=en, name_te=te, parent_id=parent.id if parent else None, data=data, sort=sort)
        db.add(m)
        db.flush()
        have[(kind, code)] = m
        return m

    for i, (c, en, te) in enumerate(CONTEXT_TAGS):
        add("context_tag", c, en, te, sort=i)
    for c, en, te, tag in DISTRICTS:
        add("district", c, en, te, data={"context_tag": tag})
    guntur = have[("district", "guntur")]
    for c, en, te in GUNTUR_MANDALS:
        add("mandal", c, en, te, parent=guntur, data={"starter": True})
    for mandal, c, en, te, tag in SAMPLE_VILLAGES:
        add("village", c, en, te, parent=have[("mandal", mandal)], data={"context_tag": tag, "starter": True})
    for i, (c, en, te, desc, tags, status, ws, icon) in enumerate(SECTORS):
        add("sector", c, en, te, data={"description": desc, "context_tags": tags, "activation": status, "workspace": ws, "icon": icon}, sort=i)
    for kind, rows in SIMPLE.items():
        for i, (c, en, te) in enumerate(rows):
            add(kind, c, en, te, sort=i)
    if not db.get(Setting, "readiness_formula"):
        db.add(Setting(key="readiness_formula", value=default_formula()))


def main(reset: bool = False) -> None:
    ensure_database()
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    ensure_columns()
    db = SessionLocal()
    try:
        email = os.getenv("ADMIN_EMAIL", "admin@mirai.local").lower()
        password = os.getenv("ADMIN_PASSWORD", "ChangeMe@123")
        if not db.scalar(select(User).where(User.email == email)):
            db.add(User(email=email, name="MIRAI Admin", role="admin", password_hash=hash_secret(password)))
            print(f"Admin created: {email} / {password}  (change this password)")

        for spec in INTENTS:
            spec = dict(spec)
            rules = spec.pop("rules", [])
            it = db.scalar(select(Intent).where(Intent.code == spec["code"]))
            if it:
                # Already loaded: only add new starter keywords; never remove or overwrite admin edits.
                extra = [k for k in spec.get("keywords", []) if k not in (it.keywords or [])]
                if extra:
                    it.keywords = list(it.keywords or []) + extra
                continue
            it = Intent(**spec)
            db.add(it)
            db.flush()
            for r in rules:
                db.add(RequirementRule(intent_id=it.id, **{k: v for k, v in r.items() if v is not None or k == "condition"}))

        today = date.today()
        for title, module, intent_code, body, url in KB:
            if db.scalar(select(KbItem).where(KbItem.title == title)):
                continue
            db.add(KbItem(title=title, module=module, intent_code=intent_code, body=body, source_url=url,
                          verified_by=SAMPLE_VERIFIER, verified_on=today, review_due=today + timedelta(days=365),
                          status="published", language="en"))

        for e in EXPERTS:
            if not db.scalar(select(Expert).where(Expert.name == e["name"])):
                db.add(Expert(**e))
        db.flush()
        load_telugu(db)
        load_masters(db)
        # Demo portal login for one sample expert (screen E1). Change or remove before go-live.
        demo = db.scalar(select(Expert).where(Expert.name == "Sample CA – Guntur"))
        demo_email = os.getenv("DEMO_EXPERT_EMAIL", "ca.guntur@mirai.local")
        if demo and not demo.user_id and not db.scalar(select(User).where(User.email == demo_email)):
            login = User(email=demo_email, name=demo.name, role="expert",
                         password_hash=hash_secret(os.getenv("DEMO_EXPERT_PASSWORD", "Expert@123")))
            db.add(login)
            db.flush()
            demo.user_id = login.id
            print(f"Demo expert login: {demo_email} / {os.getenv('DEMO_EXPERT_PASSWORD', 'Expert@123')}")
        db.commit()
        print(f"Seed complete: {len(INTENTS)} topics, {len(KB)} English + {len(TE_KB)} Telugu knowledge items, {len(EXPERTS)} experts.")
    finally:
        db.close()


if __name__ == "__main__":
    main(reset="--reset" in sys.argv)
