"""Load DEMO data for showing MIRAI Shakthi to the client (Sprint 5).

    py -m seed.seed          # first, once
    py -m seed.demo          # then this; safe to run again (skips demo users that already exist)

Creates six fictional MSME owners with profiles, conversations in English and Telugu, documents, a cash-flow
summary made from a sample bank statement, and expert requests in every state – so the dashboard, answer review
and request queue are not empty during a demo. It goes through the real API, exactly as the app does.

Everything here is fictional. Remove it before go-live:  py -m seed.demo --remove
"""
import sys
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.db import SessionLocal
from app.main import app
from app.models import AuditLog, Expert, User
from app.security import create_token
from seed import sample_statements

EXPERT_PASSWORD = "Expert@123"
EXPERT_LOGINS = {  # demo portal logins for the sample experts (the CA's login is made by seed.seed)
    "Sample CS – Vijayawada": "cs.vijayawada@mirai.local",
    "Sample Export Facilitator": "export@mirai.local",
    "Sample Business Development Centre": "bdc@mirai.local",
    "Sample HR & Labour Consultant": "hr@mirai.local",
    "Sample Bank – MSME Branch": "bank@mirai.local",
    "MIRAI Training Desk": "training@mirai.local",
    "Sample Legal Recovery Advisor": "legal@mirai.local",
}

BASE = {"ownership": "proprietor", "has_loan": False, "flags": [], "mandal": None}
OWNERS = [
    {"mobile": "9000000101", "lang": "te", "profile": {**BASE, "owner_name": "Lakshmi Devi", "business_name": "Lakshmi Millet Snacks",
     "stage": "1to3", "business_type": "manufacturing", "sector": "Food", "product": "Millet snacks and laddus", "district": "Guntur",
     "turnover_band": 1, "employees": 3, "registrations": ["udyam"], "channels": ["local", "wholesale"], "books_kept": "notebook",
     "flags": ["women_led"]},
     "questions": [("నాకు జీఎస్టీ రిజిస్ట్రేషన్ అవసరమా?", 1), ("అమ్మకాలు బాగున్నా నా దగ్గర నగదు ఉండదు. ఎందుకు?", 1),
                   ("How can I sell my snacks on Amazon or ONDC?", 1)],
     "roadmap": 0, "statement": True},
    {"mobile": "9000000102", "lang": "en", "profile": {**BASE, "owner_name": "Ravi Kumar", "business_name": "Ravi Handlooms",
     "stage": "gt3", "business_type": "manufacturing", "sector": "Handloom & textiles", "product": "Cotton handloom sarees", "district": "Krishna",
     "turnover_band": 2, "employees": 8, "registrations": ["udyam", "gst"], "channels": ["local", "interstate"], "books_kept": "excel"},
     "questions": [("Which registrations do I need to start my business?", 1), ("Which government schemes can help my business?", -1)],
     "roadmap": 0},
    {"mobile": "9000000103", "lang": "en", "profile": {**BASE, "owner_name": "Fatima Begum", "business_name": "Fatima Tailoring Unit",
     "stage": "lt1", "business_type": "services", "sector": "Handloom & textiles", "product": "Tailoring and school uniforms", "district": "NTR",
     "turnover_band": 1, "employees": 2, "registrations": [], "channels": ["local"], "books_kept": "none", "flags": ["women_led", "first_gen"]},
     "questions": [("What do I need to get a bank loan?", 1), ("Who can help me prepare a DPR (project report)?", 1)],
     "roadmap": 0},
    {"mobile": "9000000104", "lang": "te", "profile": {**BASE, "owner_name": "Suresh Reddy", "business_name": "Sri Sai Drone Services",
     "stage": "lt1", "business_type": "services", "sector": "Agriculture", "product": "Drone spraying for farmers", "district": "Guntur",
     "turnover_band": 1, "employees": 2, "registrations": ["udyam"], "channels": ["local"], "books_kept": "notebook", "has_loan": True},
     "questions": [("నాకు 3 మంది పనివారు కావాలి. ఎలా మొదలుపెట్టాలి?", 1), ("What is the weather tomorrow in Guntur?", None)],
     "jd": True},
    {"mobile": "9000000105", "lang": "en", "profile": {**BASE, "owner_name": "Padma Rani", "business_name": "Padma Pickles",
     "stage": "gt3", "business_type": "manufacturing", "sector": "Food", "product": "Mango and gongura pickles", "district": "Visakhapatnam",
     "turnover_band": 3, "employees": 12, "registrations": ["udyam", "gst", "fssai"], "channels": ["local", "online", "interstate"],
     "books_kept": "software", "flags": ["women_led"]},
     "questions": [("I want to export my products. What do I need?", 1), ("What must I print on my product label?", 1)],
     "roadmap": 0},
    {"mobile": "9000000106", "lang": "en", "profile": {**BASE, "owner_name": "Kiran Babu", "business_name": "Kiran Auto Works",
     "stage": "1to3", "business_type": "services", "sector": "Repairs & services", "product": "Two-wheeler repairs", "district": "Kurnool",
     "turnover_band": 2, "employees": 11, "registrations": ["udyam", "trade"], "channels": ["local"], "books_kept": "notebook"},
     "questions": [("Do I need PF and ESI for my workers?", 1), ("A buyer has not paid me for 3 months. What can I do?", None)]},
]


def _h(user: User) -> dict:
    return {"Authorization": f"Bearer {create_token(user)}"}


def _ok(r, what: str):
    if r.status_code >= 400:
        raise SystemExit(f"Demo data failed at '{what}': {r.status_code} {r.text[:300]}")
    return r.json()


def remove() -> None:
    db = SessionLocal()
    try:
        users = list(db.scalars(select(User).where(User.mobile.in_([o["mobile"] for o in OWNERS]))))
        for u in users:
            db.execute(delete(AuditLog).where(AuditLog.user_id == u.id))
            # The database removes the profile, conversations, documents and requests with the user (ON DELETE CASCADE).
            db.execute(text("DELETE FROM users WHERE id = :id"), {"id": u.id})
        db.commit()
        print(f"Removed {len(users)} demo MSME users and their data. Demo expert logins are kept (change them in the admin portal).")
    finally:
        db.close()


def main() -> None:
    client = TestClient(app)
    db = SessionLocal()
    try:
        experts = {e.name: e for e in db.scalars(select(Expert))}
        if not experts:
            raise SystemExit("Run `py -m seed.seed` first.")
        admin = db.scalar(select(User).where(User.role == "admin"))

        # Expert logins, so every sample expert can be shown in the expert workspace.
        for name, email in EXPERT_LOGINS.items():
            e = experts.get(name)
            if e and not e.user_id and not db.scalar(select(User).where(User.email == email)):
                _ok(client.post(f"/api/v1/admin/experts/{e.id}/login", headers=_h(admin),
                                json={"email": email, "password": EXPERT_PASSWORD}), f"expert login {email}")
        db.expire_all()

        made = []
        for o in OWNERS:
            u = db.scalar(select(User).where(User.mobile == o["mobile"]))
            if u and u.profile:
                continue
            if not u:
                u = User(mobile=o["mobile"], role="msme", language=o["lang"], consent_version="demo", consent_at=datetime.now())
                db.add(u)
                db.commit()
            h = _h(u)
            _ok(client.put("/api/v1/profile", headers=h, json=o["profile"]), "profile")
            sessions = []
            for q, rating in o["questions"]:
                lang = "te" if any("ఀ" <= ch <= "౿" for ch in q) else "en"
                r = _ok(client.post("/api/v1/guidance/ask", headers=h, json={"question": q, "language": lang}), f"ask {q}")
                sessions.append(r)
                if rating:
                    _ok(client.post(f"/api/v1/guidance/messages/{r['message_id']}/rate", headers=h, json={"rating": rating}), "rate")
            o["_user"], o["_sessions"] = u, sessions
            if "roadmap" in o:
                s = sessions[o["roadmap"]]["session_id"]
                o["_roadmap"] = _ok(client.post("/api/v1/artefacts/roadmap", headers=h, json={"session_id": s}), "roadmap")["id"]
                _ok(client.post("/api/v1/artefacts/checklist", headers=h, json={"session_id": s}), "checklist")
            if o.get("statement"):
                tx = sample_statements.transactions()
                st = _ok(client.post("/api/v1/artefacts/cashflow/statement", headers=h,
                                     files={"file": ("statement.xlsx", sample_statements.layout_a_xlsx(tx))}), "statement")
                months = st["months"]
                for m in months:  # the owner moves part of the cash withdrawals to wages, as the screen suggests
                    m["wages"] += 3000
                    m["other"] = max(0, m["other"] - 3000)
                _ok(client.post("/api/v1/artefacts/cashflow", headers=h, json={
                    "months": months, "loans": st["loans"], "stock_value": 45000, "purpose": "cash_shortage",
                    "receivables": [{"customer": "Sri Sai Hostel", "amount": 26000, "invoice_date": "2026-08-10"},
                                    {"customer": "Guntur Supermarket", "amount": 14500, "invoice_date": "2026-09-12"}]}), "cashflow")
            if o.get("jd"):
                _ok(client.post("/api/v1/artefacts/jd", headers=h, json={
                    "role_key": "custom", "title": "Drone spraying assistant", "purpose": "Help the pilot carry, fill and clean the drone in the field",
                    "duties": ["Carry and set up the drone and batteries", "Mix and fill spray liquid safely", "Clean the drone after each job",
                               "Keep the job register"], "skills": ["Basic reading", "Two-wheeler licence"], "openings": 2,
                    "work_hours": "6 am – 2 pm, 6 days", "pay": "₹12,000 per month", "location": "Guntur and nearby mandals"}), "jd")
            made.append(o)

        def owner(mobile):
            return next((o for o in made if o["mobile"] == mobile), None)

        def send(o, expert_name, service, session_idx=0, budget=None, docs=()):
            e = experts[expert_name]
            d = _ok(client.get(f"/api/v1/connect/draft?expert_id={e.id}&session_id={o['_sessions'][session_idx]['session_id']}",
                               headers=_h(o["_user"])), "draft")
            return _ok(client.post("/api/v1/connect/requests", headers=_h(o["_user"]), json={
                "expert_id": e.id, "session_id": o["_sessions"][session_idx]["session_id"], "service": service, "summary": d["summary"],
                "preferred_contact": "whatsapp", "budget": budget, "artefact_ids": list(docs), "consent": True}), "request")

        def expert_user(name):
            db.expire_all()
            return db.get(User, db.scalar(select(Expert).where(Expert.name == name)).user_id)

        def as_expert(name, rid, path, body=None):
            return _ok(client.post(f"/api/v1/expert/requests/{rid}/{path}", headers=_h(expert_user(name)), json=body or {}), path)

        # 1. Lakshmi → CA: done and rated 5 stars
        if (o := owner("9000000101")):
            r = send(o, "Sample CA – Guntur", "gst_filing", 0, "upto_2000", [o["_roadmap"]])
            as_expert("Sample CA – Guntur", r["id"], "accept", {"text": "Namaste Lakshmi garu, I can do your GST registration. I will call you today."})
            as_expert("Sample CA – Guntur", r["id"], "quote", {"amount": 1500, "note": "GST registration filing with document check. Done in 7 working days."})
            _ok(client.post(f"/api/v1/connect/requests/{r['id']}/quote", headers=_h(o["_user"]), json={"accept": True}), "accept quote")
            as_expert("Sample CA – Guntur", r["id"], "message", {"text": "Please send photos of PAN, Aadhaar and the shop rent agreement on WhatsApp."})
            as_expert("Sample CA – Guntur", r["id"], "status", {"status": "done", "text": "GST registration done. GSTIN sent to you on WhatsApp."})
            _ok(client.post(f"/api/v1/connect/requests/{r['id']}/rate", headers=_h(o["_user"]),
                            json={"stars": 5, "comment": "Very quick and explained everything in Telugu"}), "rate expert")
        # 2. Padma → export facilitator: quote waiting for the owner
        if (o := owner("9000000105")):
            r = send(o, "Sample Export Facilitator", "export_facilitation", 0, "2000_10000", [o["_roadmap"]])
            as_expert("Sample Export Facilitator", r["id"], "accept")
            as_expert("Sample Export Facilitator", r["id"], "quote", {"amount": 8000, "note": "IEC, APEDA RCMC and first shipment documents for pickles to the UAE."})
        # 3. Fatima → business development centre: work in progress
        if (o := owner("9000000103")):
            r = send(o, "Sample Business Development Centre", "dpr_preparation", 1, "free", [o["_roadmap"]])
            as_expert("Sample Business Development Centre", r["id"], "accept", {"text": "We will prepare your DPR free under the MIRAI programme."})
            as_expert("Sample Business Development Centre", r["id"], "status", {"status": "in_progress", "text": "Collecting machine quotations."})
        # 4. Kiran → HR consultant: declined, so it needs attention in the admin queue
        if (o := owner("9000000106")):
            r = send(o, "Sample HR & Labour Consultant", "hr_support", 0)
            as_expert("Sample HR & Labour Consultant", r["id"], "decline", {"text": "I do not cover Kurnool district at present."})
        # 5. Ravi → CS: no reply for 3 days, so it shows as overdue
        if (o := owner("9000000102")):
            r = send(o, "Sample CS – Vijayawada", "registration_filing", 0)
            db.execute(text("UPDATE connect_updates SET created_at = created_at - INTERVAL 3 DAY WHERE request_id = :r"), {"r": r["id"]})
            db.execute(text("UPDATE connect_requests SET created_at = created_at - INTERVAL 3 DAY WHERE id = :r"), {"r": r["id"]})
            db.commit()

        print(f"Demo data loaded for {len(made)} MSME owner(s)." if made else "Demo data is already loaded.")
        print("MSME demo logins (OTP shows on screen in development mode):")
        for o in OWNERS:
            print(f"  {o['mobile']}  {o['profile']['owner_name']} – {o['profile']['business_name']} ({'Telugu' if o['lang'] == 'te' else 'English'})")
        print(f"Expert logins (password {EXPERT_PASSWORD}): ca.guntur@mirai.local, " + ", ".join(EXPERT_LOGINS.values()))
    finally:
        db.close()


if __name__ == "__main__":
    remove() if "--remove" in sys.argv else main()
