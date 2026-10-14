from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..guidance.engine import profile_summary, profile_dict
from ..labels_te import LABELS_TE
from ..models import AuditLog, MsmeProfile, TURNOVER_BANDS, User
from ..schemas import ProfileIn
from ..security import require_roles

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


def _out(p: MsmeProfile | None) -> dict | None:
    if not p:
        return None
    data = {c: getattr(p, c) for c in ProfileIn.model_fields}
    data["summary"] = profile_summary(profile_dict(p))
    return data


@router.get("/options")
def options(lang: str = "en"):
    """Choices for Form G-1, so the app and the API stay in sync. lang=te returns Telugu labels."""
    data = {
        "stage": [["planning", "Planning to start"], ["lt1", "Running < 1 year"], ["1to3", "Running 1–3 years"], ["gt3", "Running > 3 years"]],
        "business_type": [["manufacturing", "Manufacturing"], ["trading", "Trading"], ["services", "Services"]],
        "sector": ["Food", "Agriculture", "Dairy & livestock", "Fisheries", "Forest products", "Handloom & textiles",
                   "Crafts", "Repairs & services", "Beauty & wellness", "Mobility & logistics", "Tourism", "Digital services", "Other"],
        "ownership": [["proprietor", "Proprietor"], ["partnership", "Partnership"], ["llp", "LLP"], ["company", "Company"], ["shg", "SHG / group"]],
        "turnover_band": [[k, v] for k, v in TURNOVER_BANDS.items()],
        "registrations": [["udyam", "Udyam"], ["gst", "GST"], ["fssai", "FSSAI"], ["trade", "Trade licence"], ["iec", "IEC (export)"], ["shop_est", "Shop & Establishment"]],
        "channels": [["local", "Local customers / shop"], ["wholesale", "Wholesale"], ["online", "Online"], ["government", "Government"], ["interstate", "Other states"], ["export", "Export"]],
        "books_kept": [["none", "No records"], ["notebook", "Notebook"], ["excel", "Excel"], ["software", "Accounting software"]],
        "flags": [["women_led", "Women-led"], ["sc_st", "SC / ST"], ["first_gen", "First-generation entrepreneur"]],
        "districts": ["Alluri Sitharama Raju", "Anakapalli", "Anantapur", "Annamayya", "Bapatla", "Chittoor", "East Godavari",
                      "Eluru", "Guntur", "Kakinada", "Konaseema", "Krishna", "Kurnool", "Nandyal", "NTR", "Palnadu",
                      "Parvathipuram Manyam", "Prakasam", "Sri Potti Sriramulu Nellore", "Sri Sathya Sai", "Srikakulam",
                      "Tirupati", "Visakhapatnam", "Vizianagaram", "West Godavari", "YSR Kadapa", "Other"],
    }
    if lang == "te":
        for k, v in data.items():
            if v and isinstance(v[0], list):
                data[k] = [[val, LABELS_TE.get(label, label)] for val, label in v]
        # Sector values are stored as text, so send their labels separately.
        data["labels"] = {s: LABELS_TE.get(s, s) for s in data["sector"]}
    return data


@router.get("")
def get_profile(user: User = Depends(require_roles("msme"))):
    return {"profile": _out(user.profile)}


@router.put("")
def save_profile(body: ProfileIn, user: User = Depends(require_roles("msme")), db: Session = Depends(get_db)):
    p = user.profile or MsmeProfile(user_id=user.id)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    if not user.name:
        user.name = body.owner_name
    db.add(p)
    db.add(AuditLog(user_id=user.id, action="profile_saved", entity="msme_profile"))
    db.commit()
    db.refresh(p)
    return {"profile": _out(p)}
