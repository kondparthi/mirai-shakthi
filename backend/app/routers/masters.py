"""M14 – Master data. Read by every logged-in user (forms need the lists); edited by admin / programme manager."""
import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, User
from ..models_p1 import MasterItem
from ..roles import MASTERS_WRITE
from ..security import current_user, require_roles

router = APIRouter(prefix="/api/v1", tags=["masters"])
editor = require_roles(*MASTERS_WRITE)

KINDS = {
    "district": "Districts", "mandal": "Mandals", "village": "Villages", "context_tag": "Context tags", "sector": "Sectors",
    "skill": "Skills", "education": "Education levels", "occupation": "Occupations", "social_category": "Social categories",
    "doc_type": "Document types", "bank": "Banks",
}
PARENT_KIND = {"mandal": "district", "village": "mandal"}
SECTOR_STATUS = ("catalogue", "pilot", "active")


def _out(m: MasterItem, parents: dict[int, MasterItem] | None = None) -> dict:
    p = parents.get(m.parent_id) if parents and m.parent_id else None
    return {"id": m.id, "kind": m.kind, "code": m.code, "name_en": m.name_en, "name_te": m.name_te, "parent_id": m.parent_id,
            "parent_code": p.code if p else None, "parent_name": p.name_en if p else None, "data": m.data or {}, "active": m.active, "sort": m.sort}


@router.get("/masters")
def read_masters(kind: str, parent: Optional[str] = None, _: User = Depends(current_user), db: Session = Depends(get_db)):
    """Active items of one kind, for forms. `parent` = the parent's code (district code for mandals, mandal code for villages)."""
    if kind not in KINDS:
        raise HTTPException(404, "Unknown list")
    q = select(MasterItem).where(MasterItem.kind == kind, MasterItem.active.is_(True))
    if parent and kind in PARENT_KIND:
        pid = db.scalar(select(MasterItem.id).where(MasterItem.kind == PARENT_KIND[kind], MasterItem.code == parent))
        q = q.where(MasterItem.parent_id == pid)
    return [{"code": m.code, "name_en": m.name_en, "name_te": m.name_te, "data": m.data or {}}
            for m in db.scalars(q.order_by(MasterItem.sort, MasterItem.name_en))]


# ---------------------------------------------------------------- admin
class MasterIn(BaseModel):
    kind: str
    code: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_]+$")
    name_en: str = Field(min_length=1, max_length=160)
    name_te: Optional[str] = Field(default=None, max_length=160)
    parent_code: Optional[str] = None
    data: dict = {}
    active: bool = True
    sort: int = Field(default=100, ge=0, le=100000)


def _validate(db: Session, body: MasterIn) -> Optional[int]:
    if body.kind not in KINDS:
        raise HTTPException(422, "Unknown list")
    if body.kind == "sector" and body.data.get("activation") not in SECTOR_STATUS:
        raise HTTPException(422, "Sector activation must be Catalogue only, Pilot or Active")
    if body.kind in ("district", "village") and body.data.get("context_tag") and body.data["context_tag"] not in (
            "rural", "urban", "tribal", "coastal"):
        raise HTTPException(422, "Context tag must be rural, urban, tribal or coastal")
    if body.kind in PARENT_KIND:
        if not body.parent_code:
            raise HTTPException(422, f"Choose the {PARENT_KIND[body.kind]}")
        pid = db.scalar(select(MasterItem.id).where(MasterItem.kind == PARENT_KIND[body.kind], MasterItem.code == body.parent_code))
        if not pid:
            raise HTTPException(422, f"Unknown {PARENT_KIND[body.kind]}: {body.parent_code}")
        return pid
    return None


@router.get("/admin/masters/kinds")
def kinds(_: User = Depends(current_user)):
    return [{"kind": k, "label": v, "parent": PARENT_KIND.get(k)} for k, v in KINDS.items()]


@router.get("/admin/masters")
def list_masters(kind: str, q: Optional[str] = None, parent: Optional[str] = None, limit: int = Query(500, le=5000),
                 _: User = Depends(require_roles(*MASTERS_WRITE, "coordinator", "mentor", "trainer", "dpr_officer")),
                 db: Session = Depends(get_db)):
    stmt = select(MasterItem).where(MasterItem.kind == kind)
    if q:
        stmt = stmt.where(or_(MasterItem.name_en.ilike(f"%{q}%"), MasterItem.name_te.ilike(f"%{q}%"), MasterItem.code.ilike(f"%{q}%")))
    if parent and kind in PARENT_KIND:
        pid = db.scalar(select(MasterItem.id).where(MasterItem.kind == PARENT_KIND[kind], MasterItem.code == parent))
        stmt = stmt.where(MasterItem.parent_id == pid)
    rows = list(db.scalars(stmt.order_by(MasterItem.sort, MasterItem.name_en).limit(limit)))
    parents = {p.id: p for p in db.scalars(select(MasterItem).where(MasterItem.id.in_({r.parent_id for r in rows if r.parent_id})))}
    return [_out(r, parents) for r in rows]


@router.post("/admin/masters")
def create_master(body: MasterIn, user: User = Depends(editor), db: Session = Depends(get_db)):
    pid = _validate(db, body)
    if db.scalar(select(MasterItem).where(MasterItem.kind == body.kind, MasterItem.code == body.code)):
        raise HTTPException(409, "This code already exists in the list")
    m = MasterItem(kind=body.kind, code=body.code, name_en=body.name_en, name_te=body.name_te or None, parent_id=pid,
                   data=body.data, active=body.active, sort=body.sort)
    db.add(m)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="master_create", entity=f"master:{body.kind}", entity_id=m.id, detail={"code": body.code}))
    db.commit()
    return _out(m)


@router.put("/admin/masters/{mid}")
def update_master(mid: int, body: MasterIn, user: User = Depends(editor), db: Session = Depends(get_db)):
    m = db.get(MasterItem, mid)
    if not m:
        raise HTTPException(404, "Item not found")
    if body.kind != m.kind or body.code != m.code:
        raise HTTPException(422, "The list and code cannot be changed (records refer to the code)")
    pid = _validate(db, body)
    m.name_en, m.name_te, m.parent_id, m.data, m.active, m.sort = body.name_en, body.name_te or None, pid, body.data, body.active, body.sort
    db.add(AuditLog(user_id=user.id, action="master_update", entity=f"master:{m.kind}", entity_id=m.id, detail={"code": m.code}))
    db.commit()
    return _out(m)


CSV_COLUMNS = ["code", "name_en", "name_te", "parent_code", "context_tag", "active"]


@router.get("/admin/masters/export")
def export_masters(kind: str, _: User = Depends(editor), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(MasterItem).where(MasterItem.kind == kind).order_by(MasterItem.sort, MasterItem.name_en)))
    parents = {p.id: p for p in db.scalars(select(MasterItem).where(MasterItem.id.in_({r.parent_id for r in rows if r.parent_id})))}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    for r in rows:
        w.writerow([r.code, r.name_en, r.name_te or "", parents[r.parent_id].code if r.parent_id in parents else "",
                    (r.data or {}).get("context_tag", ""), "yes" if r.active else "no"])
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})


@router.post("/admin/masters/import")
async def import_masters(kind: str, commit: bool = False, file: UploadFile = File(...), user: User = Depends(editor),
                         db: Session = Depends(get_db)):
    """CSV with columns code, name_en, name_te, parent_code, context_tag, active. Preview first (commit=false), then commit.
    Existing codes are updated, new codes are added; nothing is deleted."""
    if kind not in KINDS:
        raise HTTPException(422, "Unknown list")
    raw = (await file.read(5 * 1024 * 1024 + 1))
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "The file is larger than 5 MB")
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    cols = [c.strip().lower() for c in reader.fieldnames or []]
    if "code" not in cols or "name_en" not in cols:
        raise HTTPException(422, "The CSV needs at least the columns code and name_en (download a list to see the format)")
    existing = {m.code: m for m in db.scalars(select(MasterItem).where(MasterItem.kind == kind))}
    parent_kind = PARENT_KIND.get(kind)
    parents = {m.code: m.id for m in db.scalars(select(MasterItem).where(MasterItem.kind == parent_kind))} if parent_kind else {}
    rows, seen = [], set()
    for i, raw_row in enumerate(reader, start=2):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items()}
        err = []
        code = r.get("code", "").lower().replace(" ", "_")
        if not code or not all(ch.isalnum() or ch == "_" for ch in code):
            err.append("code must use letters, numbers and _")
        if code in seen:
            err.append("code repeated in the file")
        seen.add(code)
        if not r.get("name_en"):
            err.append("name_en is empty")
        if parent_kind and r.get("parent_code") not in parents:
            err.append(f"unknown {parent_kind} '{r.get('parent_code', '')}'")
        tag = r.get("context_tag", "").lower()
        if tag and tag not in ("rural", "urban", "tribal", "coastal"):
            err.append("context_tag must be rural, urban, tribal or coastal")
        rows.append({"line": i, "code": code, "name_en": r.get("name_en", ""), "name_te": r.get("name_te", ""), "parent_code": r.get("parent_code", ""),
                     "context_tag": tag, "active": r.get("active", "yes").lower() not in ("no", "false", "0"),
                     "action": "update" if code in existing else "add", "errors": err})
        if len(rows) > 20000:
            raise HTTPException(422, "Please import at most 20,000 rows at a time")
    bad = [r for r in rows if r["errors"]]
    summary = {"rows": len(rows), "add": sum(1 for r in rows if r["action"] == "add" and not r["errors"]),
               "update": sum(1 for r in rows if r["action"] == "update" and not r["errors"]), "errors": len(bad)}
    if not commit:
        return {"summary": summary, "preview": (bad + [r for r in rows if not r["errors"]])[:50]}
    if bad:
        raise HTTPException(422, f"Fix the {len(bad)} row(s) with errors before importing")
    for r in rows:
        m = existing.get(r["code"])
        data = dict(m.data or {}) if m else {}
        if r["context_tag"]:
            data["context_tag"] = r["context_tag"]
        if m:
            m.name_en, m.name_te, m.active, m.data = r["name_en"], r["name_te"] or m.name_te, r["active"], data
            if parent_kind:
                m.parent_id = parents[r["parent_code"]]
        else:
            db.add(MasterItem(kind=kind, code=r["code"], name_en=r["name_en"], name_te=r["name_te"] or None,
                              parent_id=parents.get(r["parent_code"]) if parent_kind else None, data=data, active=r["active"]))
    db.add(AuditLog(user_id=user.id, action="master_import", entity=f"master:{kind}", entity_id=None, detail=summary))
    db.commit()
    return {"summary": summary, "imported": True}
