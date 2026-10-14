"""Phase 1 Sprint 1 – masters, staff access, enrolment (self, assisted, import), groups, readiness and DPDP requests."""
import io

from PIL import Image

from app.programme import readiness
from app.programme.service import _D, _P, aadhaar_valid

from .conftest import login


def make_aadhaar(first11: str) -> str:
    """Append the Verhoeff check digit."""
    inv = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]
    c = 0
    for i, ch in enumerate(reversed(first11)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return first11 + str(inv[c])


AADHAAR = make_aadhaar("23456789012")


def admin(client):
    r = client.post("/api/v1/auth/staff/login", json={"email": "admin@mirai.local", "password": "ChangeMe@123"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def staff(client, email, role, districts=(), password="Navigator@123"):
    h = admin(client)
    r = client.post("/api/v1/admin/staff", headers=h, json={"name": email.split("@")[0], "email": email, "role": role,
                                                             "districts": list(districts), "password": password})
    assert r.status_code in (200, 409), r.text
    r = client.post("/api/v1/auth/staff/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def person(**over):
    d = {"full_name": "Lakshmi Devi", "gender": "female", "dob": "1990-05-14", "social_category": "obc", "education": "secondary",
         "district": "guntur", "mandal": "tenali", "village": "kolakaluru", "context_tag": "rural", "aadhaar": AADHAAR,
         "bank_account": "123456789012", "ifsc": "SBIN0001234", "bank_name": "sbi", "skills": ["cooking"], "interests": ["food"],
         "investment_available": 60000, "has_loans": False, "occupation": "homemaker", "monthly_income": 8000}
    d.update(over)
    return d


def jpeg() -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (1600, 1200), (200, 120, 40)).save(b, "JPEG")
    return b.getvalue()


def test_verhoeff():
    assert aadhaar_valid(AADHAAR)
    assert not aadhaar_valid(AADHAAR[:-1] + str((int(AADHAAR[-1]) + 1) % 10))
    assert not aadhaar_valid("123456789012")  # cannot start with 0 or 1


def test_readiness_formula_default_and_validation():
    f = readiness.default_formula()
    readiness.validate_formula(f)
    good = readiness.score({"motivation": "I want my own millet café in town", "experience": "1to3", "time": "full",
                            "family_support": "yes", "work_space": "rented", "digital": "daily", "credit_history": "repaid",
                            "risk": "medium"}, 60000, f)
    assert good["score"] == 92 and good["band"] == "Ready" and not good["gaps"]
    weak = readiness.score({}, 0, f)
    assert weak["score"] == 0 and weak["band"] == "Needs preparation" and "Core EDP" in weak["recommended"]
    f["questions"]["risk"]["max"] = 10
    try:
        readiness.validate_formula(f)
        raise AssertionError("weights must add to 100")
    except ValueError:
        pass


def test_masters_read_crud_import(client):
    h = admin(client)
    u = login(client, "9100000001")
    mandals = client.get("/api/v1/masters", params={"kind": "mandal", "parent": "guntur"}, headers=u).json()
    assert any(x["code"] == "tenali" for x in mandals)
    assert client.post("/api/v1/admin/masters", headers=u, json={"kind": "skill", "code": "x", "name_en": "X"}).status_code == 403
    r = client.post("/api/v1/admin/masters", headers=h, json={"kind": "village", "code": "test_village", "name_en": "Test village",
                                                              "parent_code": "tenali", "data": {"context_tag": "rural"}})
    assert r.status_code == 200, r.text
    assert client.post("/api/v1/admin/masters", headers=h, json={"kind": "sector", "code": "s2", "name_en": "S", "data": {}}).status_code == 422
    csv_text = "code,name_en,name_te,parent_code,context_tag,active\nnew_v,New Village,,tenali,rural,yes\nbad,,,,nowhere,yes\n"
    r = client.post("/api/v1/admin/masters/import", params={"kind": "village"}, headers=h,
                    files={"file": ("v.csv", csv_text.encode(), "text/csv")})
    assert r.json()["summary"] == {"rows": 2, "add": 1, "update": 0, "errors": 1}
    assert client.post("/api/v1/admin/masters/import", params={"kind": "village", "commit": True}, headers=h,
                       files={"file": ("v.csv", csv_text.encode(), "text/csv")}).status_code == 422
    good = "code,name_en,parent_code\nnew_v,New Village,tenali\n"
    r = client.post("/api/v1/admin/masters/import", params={"kind": "village", "commit": True}, headers=h,
                    files={"file": ("v.csv", good.encode(), "text/csv")})
    assert r.json()["imported"]
    out = client.get("/api/v1/admin/masters/export", params={"kind": "village"}, headers=h)
    assert "new_v,New Village" in out.content.decode("utf-8-sig")


def test_self_enrolment_photo_readiness_and_export(client):
    u = login(client, "9100000002")
    assert client.get("/api/v1/enrol/me", headers=u).json() == {"enrolled": False, "needs_consent": True}
    assert client.put("/api/v1/enrol/me", headers=u, json=person()).status_code == 422  # consent required
    bad = client.put("/api/v1/enrol/me", headers=u, json=person(aadhaar="234567890123", consent=True))
    assert bad.status_code == 422 and "Aadhaar" in bad.text
    assert client.put("/api/v1/enrol/me", headers=u, json=person(bank_account="12345678901", ifsc=None, consent=True)).status_code == 422
    assert client.put("/api/v1/enrol/me", headers=u, json=person(dob="2015-01-01", consent=True)).status_code == 422
    r = client.put("/api/v1/enrol/me", headers=u, json=person(consent=True))
    assert r.status_code == 200, r.text
    e = r.json()["entrepreneur"]
    assert e["aadhaar_masked"] == f"XXXX XXXX {AADHAAR[-4:]}" and e["bank_masked"] == "XXXX9012"
    assert AADHAAR not in r.text and "123456789012" not in r.text
    assert e["missing"] == ["photo"] and e["source"] == "self" and e["stage"] == 1

    r = client.post("/api/v1/enrol/me/photo", headers=u, files={"file": ("p.jpg", jpeg(), "image/jpeg")})
    e = r.json()["entrepreneur"]
    assert e["missing"] == [] and e["photo_url"]
    img = client.get(e["photo_url"])
    assert img.status_code == 200 and Image.open(io.BytesIO(img.content)).size == (800, 600)
    assert client.get(e["photo_url"].split("?")[0] + "?t=xxxxxxxxxxxx").status_code == 403
    assert client.post("/api/v1/enrol/me/photo", headers=u, files={"file": ("p.jpg", b"not an image", "image/jpeg")}).status_code == 422

    form = client.get("/api/v1/enrol/readiness/form", headers=u).json()
    assert len(form["questions"]) == 8
    r = client.post("/api/v1/enrol/me/readiness", headers=u, json={"answers": {"motivation": "Start a millet snack unit", "time": "part"}})
    assert r.status_code == 200 and 0 < r.json()["score"] < 45

    exp = client.get("/api/v1/enrol/me/export", headers=u).json()
    assert exp["enrolment"]["full_name"] == "Lakshmi Devi" and len(exp["readiness_assessments"]) == 1
    assert "123456789012" not in str(exp)


def test_duplicate_on_aadhaar_name_dob(client):
    u = login(client, "9100000003")
    r = client.put("/api/v1/enrol/me", headers=u, json=person(consent=True))
    assert r.status_code == 409


def test_staff_scope_and_assisted_enrolment(client):
    h = admin(client)
    nav = staff(client, "nav.guntur@mirai.local", "coordinator", ["guntur"])
    other = staff(client, "nav.krishna@mirai.local", "coordinator", ["krishna"])
    assert client.post("/api/v1/admin/staff", headers=h, json={"name": "X", "email": "x@mirai.local", "role": "coordinator",
                                                               "districts": ["nowhere"], "password": "Password@1"}).status_code == 422
    assert client.get("/api/v1/admin/staff", headers=nav).status_code == 403

    # Assisted: OTP goes to the entrepreneur, navigator enters it
    assert client.post("/api/v1/programme/enrol/otp", headers=nav, json={"mobile": "9100000002"}).status_code == 409  # already enrolled
    code = client.post("/api/v1/programme/enrol/otp", headers=nav, json={"mobile": "9100000010"}).json()["dev_code"]
    p = person(full_name="Sita Kumari", aadhaar=make_aadhaar("34567890123"), bank_account=None, ifsc=None)
    assert client.post("/api/v1/programme/entrepreneurs", headers=other,
                       json={"mobile": "9100000010", "otp": code, "data": p}).status_code == 403  # outside Krishna navigator's area
    assert client.post("/api/v1/programme/entrepreneurs", headers=nav,
                       json={"mobile": "9100000010", "otp": "000000" if code != "000000" else "111111", "data": p}).status_code == 400
    r = client.post("/api/v1/programme/entrepreneurs", headers=nav, json={"mobile": "9100000010", "otp": code, "data": p})
    assert r.status_code == 200, r.text
    sita = r.json()
    assert sita["source"] == "navigator" and sita["consent"] and "bank_account" in sita["missing"]

    # Possible duplicate (same Aadhaar last 4 + name + DOB) needs force
    code = client.post("/api/v1/programme/enrol/otp", headers=nav, json={"mobile": "9100000011"}).json()["dev_code"]
    r = client.post("/api/v1/programme/entrepreneurs", headers=nav, json={"mobile": "9100000011", "otp": code, "data": p})
    assert r.status_code == 409 and r.json()["detail"]["duplicates"][0]["id"] == sita["id"]

    # Scope: Guntur navigator sees Sita; Krishna navigator does not
    assert any(x["id"] == sita["id"] for x in client.get("/api/v1/programme/entrepreneurs", headers=nav).json()["rows"])
    assert client.get("/api/v1/programme/entrepreneurs", headers=other).json()["total"] == 0
    assert client.get(f"/api/v1/programme/entrepreneurs/{sita['id']}", headers=other).status_code == 404

    # Cannot verify with missing items; filters; stats
    r = client.post(f"/api/v1/programme/entrepreneurs/{sita['id']}/status", headers=nav, json={"verified": True})
    assert r.status_code == 422 and "bank account" in r.text
    assert client.get("/api/v1/programme/entrepreneurs", headers=h, params={"sector": "food", "q": "Sita"}).json()["total"] == 1
    st = client.get("/api/v1/programme/stats", headers=nav).json()
    assert st["total"] >= 2 and st["by_stage"][0]["count"] >= 2

    # Staff readiness with remarks
    r = client.post(f"/api/v1/programme/entrepreneurs/{sita['id']}/readiness", headers=nav,
                    json={"answers": {"experience": "gt3", "time": "full", "family_support": "yes"}, "remarks": "Keen"})
    assert r.status_code == 200 and r.json()["score"] == 55

    # Audit shows the actions
    log = client.get("/api/v1/admin/audit", headers=h, params={"action": "enrol_assisted"}).json()
    assert log["total"] >= 1 and log["rows"][0]["user"] == "nav.guntur"


def test_groups(client):
    nav = staff(client, "nav.guntur@mirai.local", "coordinator", ["guntur"])
    members = [{"name": "Lakshmi Devi", "mobile": "9100000002", "role": "leader", "contribution": 2000},
               {"name": "Sita Kumari", "mobile": "9100000010", "role": "secretary"},
               {"name": "Rani", "role": "treasurer"}, {"name": "Padma", "role": "member"}]
    g = {"name": "Sri Lakshmi SHG", "group_type": "shg", "formation_date": "2019-03-01", "district": "guntur", "mandal": "tenali",
         "village": "kolakaluru", "context_tag": "rural", "corpus": 60000, "members": members}
    two_leaders = {**g, "members": [{**members[0]}, {**members[1], "role": "leader"}, members[2], members[3]]}
    assert client.post("/api/v1/programme/groups", headers=nav, json=two_leaders).status_code == 422
    assert client.post("/api/v1/programme/groups", headers=nav, json={**g, "formation_date": "2099-01-01"}).status_code == 422
    r = client.post("/api/v1/programme/groups", headers=nav, json=g)
    assert r.status_code == 200, r.text
    grp = r.json()
    assert grp["leader"] == "Lakshmi Devi" and sum(1 for m in grp["members"] if m["entrepreneur_id"]) == 2
    assert client.post("/api/v1/programme/groups", headers=nav, json=g).status_code == 409
    r = client.post(f"/api/v1/programme/groups/{grp['id']}/readiness", headers=nav, json={"answers": {}})
    assert r.json()["score"] == 10  # investment = corpus ≥ 50,000
    me = client.get("/api/v1/enrol/me", headers=login(client, "9100000002")).json()
    assert me["entrepreneur"]["groups"][0]["role"] == "leader"


def test_bulk_import_and_link_on_login(client):
    nav = staff(client, "nav.guntur@mirai.local", "coordinator", ["guntur"])
    tpl = client.get("/api/v1/programme/import/template", headers=nav).content.decode("utf-8-sig")
    head = tpl.splitlines()[0]
    rows = [head,
            "9100000020,Durga Bhavani,female,14-02-1992,guntur,tenali,angalakuduru,rural,sc,primary,daily_wage,cooking;tailoring,food,5000,6000,no,",
            "9100000021,Bad Row,woman,1992-02-14,krishna,x,y,rural,,,,,,,,,",
            "9100000002,Already,female,1992-02-14,guntur,tenali,y,rural,,,,,,,,,"]
    f = {"file": ("e.csv", "\n".join(rows).encode(), "text/csv")}
    r = client.post("/api/v1/programme/import", headers=nav, files=f).json()
    assert r["summary"] == {"rows": 3, "ok": 1, "errors": 2}
    errs = {x["mobile"]: x["errors"] for x in r["preview"] if x["errors"]}
    assert any("outside your area" in e for e in errs["9100000021"]) and "mobile already enrolled" in errs["9100000002"]
    f = {"file": ("e.csv", "\n".join(rows[:2]).encode(), "text/csv")}
    assert client.post("/api/v1/programme/import", headers=nav, params={"commit": True}, files=f).json()["imported"]

    # The imported person logs in, sees the record, and must consent before it is linked
    u = login(client, "9100000020")
    me = client.get("/api/v1/enrol/me", headers=u).json()
    assert me["enrolled"] and me["needs_consent"] and me["entrepreneur"]["source"] == "import"
    p = person(full_name="Durga Bhavani", dob="1992-02-14", aadhaar=make_aadhaar("45678901234"), village="angalakuduru")
    assert client.put("/api/v1/enrol/me", headers=u, json=p).status_code == 422
    r = client.put("/api/v1/enrol/me", headers=u, json={**p, "consent": True})
    assert r.status_code == 200 and not r.json()["needs_consent"]


def test_dpdp_delete_request_and_erase(client):
    h = admin(client)
    u = login(client, "9100000020")
    assert client.post("/api/v1/enrol/me/data-request", headers=u, json={"kind": "delete", "reason": "Moving away"}).status_code == 200
    assert client.post("/api/v1/enrol/me/data-request", headers=u, json={"kind": "delete"}).status_code == 409
    reqs = client.get("/api/v1/admin/data-requests", headers=h).json()
    rid = next(r["id"] for r in reqs if r["mobile"] == "9100000020")
    assert client.get(f"/api/v1/admin/data-requests/{rid}/export", headers=h).json()["enrolment"]["full_name"] == "Durga Bhavani"
    r = client.post(f"/api/v1/admin/data-requests/{rid}/resolve", headers=h, json={"action": "erase", "note": "Erased as requested"})
    assert r.status_code == 200 and r.json()["status"] == "done"
    assert client.get("/api/v1/enrol/me", headers=u).status_code == 401  # account is gone
    assert client.get("/api/v1/programme/entrepreneurs", headers=h, params={"q": "Durga"}).json()["total"] == 0


def test_staff_management_and_formula(client):
    h = admin(client)
    me = client.get("/api/v1/auth/me", headers=h).json()
    assert client.put(f"/api/v1/admin/staff/{me['id']}", headers=h,
                      json={"name": "Admin", "email": "admin@mirai.local", "role": "trainer"}).status_code == 422
    f = client.get("/api/v1/admin/settings/readiness", headers=h).json()
    f["questions"]["risk"]["max"] = 10
    assert client.put("/api/v1/admin/settings/readiness", headers=h, json=f).status_code == 422
    f["questions"]["risk"]["max"] = 5
    f["questions"]["time"]["options"]["part"][2] = 10
    r = client.put("/api/v1/admin/settings/readiness", headers=h, json=f)
    assert r.status_code == 200 and r.json()["version"] >= 2
    assert client.post("/api/v1/admin/settings/readiness/reset", headers=h).status_code == 200
    roles = client.get("/api/v1/admin/roles", headers=h).json()
    assert len(roles) == 11
