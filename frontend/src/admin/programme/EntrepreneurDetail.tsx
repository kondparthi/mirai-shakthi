import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, apiUpload, type Assessment, type Entrepreneur } from "../../api";
import { useAuth } from "../../auth";
import EnrolForm, { type EnrolBody } from "../../components/EnrolForm";
import { ReadinessForm, ReadinessResult } from "../../components/Readiness";
import { Modal } from "../ui";
import { Avatar } from "./Entrepreneurs";
import EntrepreneurTraining from "../training/EntrepreneurTraining";

const STAGES = ["Enrol & assess", "Train & certify", "DPR & finance", "Set up enterprise", "Sell & deliver", "Track business", "Mentor & resolve", "Grow & sustain"];
const WRITE = ["admin", "programme_manager", "coordinator", "federation_staff"];
const ASSESS = ["admin", "programme_manager", "coordinator", "mentor"];
const inr = (n: number | null) => (n == null ? "—" : `₹${n.toLocaleString("en-IN")}`);

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="kv"><span>{k}</span><b>{v ?? "—"}</b></div>;
}

export default function EntrepreneurDetail() {
  const { id } = useParams();
  const [sp] = useSearchParams();
  const { user } = useAuth();
  const [e, setE] = useState<Entrepreneur | null>(null);
  const [hist, setHist] = useState<Assessment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<"edit" | "assess" | null>(null);
  const [msg, setMsg] = useState<string | null>(sp.get("new") ? "Enrolled. Add a photo and Aadhaar / bank details if missing, then record the readiness assessment." : null);
  const fileRef = useRef<HTMLInputElement>(null);
  const canWrite = WRITE.includes(user?.role ?? "");

  const load = useCallback(() => {
    api<Entrepreneur>(`/programme/entrepreneurs/${id}?lang=en`).then(setE).catch((x) => setError(x.message));
    api<Assessment[]>(`/programme/entrepreneurs/${id}/readiness`).then(setHist).catch(() => {});
  }, [id]);
  useEffect(load, [load]);

  if (error) return <div className="error">{error}</div>;
  if (!e) return <div className="muted">Loading…</div>;

  const act = async (body: Record<string, unknown>) => {
    setMsg(null);
    try {
      setE(await api<Entrepreneur>(`/programme/entrepreneurs/${e.id}/status`, { body }));
    } catch (x) {
      setMsg((x as Error).message);
    }
  };
  const photo = async (f?: File) => {
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    try {
      setE(await apiUpload<Entrepreneur>(`/programme/entrepreneurs/${e.id}/photo`, fd));
    } catch (x) {
      setMsg((x as Error).message);
    }
    if (fileRef.current) fileRef.current.value = "";
  };
  const save = async (body: EnrolBody) => {
    await api(`/programme/entrepreneurs/${e.id}`, { method: "PUT", body });
    setModal(null);
    load();
  };

  return (
    <div className="stack">
      <Link to="/admin/entrepreneurs" className="small">← Entrepreneurs</Link>
      <div className="card detail-head">
        <Avatar url={e.photo_url} name={e.full_name} size={84} />
        <div style={{ flex: 1, minWidth: 220 }}>
          <h1 style={{ margin: 0 }}>{e.full_name}</h1>
          <div className="small muted">ID {e.id} · {e.mobile} · {e.village_name}, {e.mandal_name}, {e.district_name} ({e.context_tag})</div>
          <div className="chips" style={{ marginTop: 8 }}>
            <span className={`tag ${e.verified ? "ok" : "amber"}`}>{e.verified ? "verified" : "not verified"}</span>
            <span className="tag">Stage {e.stage}: {e.stage_name}</span>
            <span className="tag grey">{e.status}</span>
            <span className="tag grey">joined via {e.source}{e.enrolled_by ? ` (${e.enrolled_by})` : ""}</span>
            {!e.consent && <span className="tag alert">no consent yet</span>}
          </div>
        </div>
        {canWrite && (
          <div className="stack" style={{ gap: 8 }}>
            <input ref={fileRef} type="file" accept="image/*" capture="environment" hidden onChange={(x) => photo(x.target.files?.[0])} />
            <button className="btn secondary small" onClick={() => fileRef.current?.click()}>{e.has_photo ? "Change photo" : "Add photo"}</button>
            <button className="btn secondary small" onClick={() => setModal("edit")}>Edit details</button>
          </div>
        )}
      </div>
      {msg && <div className="notice">{msg}</div>}
      {e.missing.length > 0 && <div className="notice small"><b>Missing before verification:</b> {e.missing.map((m) => m.replace(/_/g, " ")).join(", ")}</div>}

      {canWrite && (
        <div className="card row-gap" style={{ alignItems: "flex-end" }}>
          <label className="field"><span>Lifecycle stage</span>
            <select className="input" value={e.stage} onChange={(x) => act({ stage: Number(x.target.value) })}>
              {STAGES.map((s, i) => <option key={s} value={i + 1}>{i + 1}. {s}</option>)}
            </select></label>
          <label className="field"><span>Status</span>
            <select className="input" value={e.status} onChange={(x) => act({ status: x.target.value })}>
              <option value="active">active</option><option value="paused">paused</option><option value="closed">closed</option>
            </select></label>
          {e.verified
            ? <button className="btn ghost" onClick={() => act({ verified: false })}>Remove verification</button>
            : <button className="btn" disabled={e.missing.length > 0} onClick={() => act({ verified: true })}>Mark verified</button>}
        </div>
      )}

      <div className="grid-2">
        <div className="card">
          <h2>Profile</h2>
          <Row k="Gender" v={e.gender} />
          <Row k="Date of birth" v={e.dob} />
          <Row k="Social category" v={e.social_category_name} />
          <Row k="Education" v={e.education_name} />
          <Row k="Occupation" v={e.occupation_name} />
          <Row k="Skills" v={e.skill_names.join(", ")} />
          <Row k="Interested in" v={e.interest_names.join(", ")} />
          <h2 style={{ marginTop: 18 }}>Money</h2>
          <Row k="Own money available" v={inr(e.investment_available)} />
          <Row k="Household monthly income" v={inr(e.monthly_income)} />
          <Row k="Existing loans" v={e.has_loans ? `Yes – EMI ${inr(e.emi_amount)}` : e.has_loans === false ? "No" : "—"} />
          <h2 style={{ marginTop: 18 }}>IDs & bank</h2>
          <Row k="Aadhaar" v={e.aadhaar_masked} />
          <Row k="PAN" v={e.pan} />
          <Row k="Bank account" v={e.bank_masked ? `${e.bank_masked} · ${e.ifsc}${e.bank_label ? ` · ${e.bank_label}` : ""}` : null} />
          <Row k="Consent" v={e.consent_at ? `${new Date(e.consent_at).toLocaleString()} (${e.consent_version})` : "Not given yet"} />
          {e.groups.length > 0 && (<>
            <h2 style={{ marginTop: 18 }}>Groups</h2>
            {e.groups.map((g) => <Row key={g.id} k={g.role} v={<Link to={`/admin/groups?open=${g.id}`}>{g.name}</Link>} />)}
          </>)}
        </div>
        <div className="card stack">
          <div className="row-between"><h2 style={{ margin: 0 }}>Readiness (Form 1.3)</h2>
            {ASSESS.includes(user?.role ?? "") && <button className="btn small" onClick={() => setModal("assess")}>+ New assessment</button>}</div>
          {hist.length === 0 && <p className="muted small">Not assessed yet.</p>}
          {hist[0] && <ReadinessResult a={hist[0]} lang="en" showBreakdown />}
          {hist.length > 1 && (
            <div><b className="small">Earlier</b>
              {hist.slice(1).map((a) => <div key={a.id} className="row-between small"><span>{a.at ? new Date(a.at).toLocaleDateString() : ""}</span><b>{a.score}</b></div>)}</div>
          )}
        </div>
      </div>

      <EntrepreneurTraining eid={e.id} />

      {modal === "edit" && (
        <Modal title="Edit details" wide onClose={() => setModal(null)}>
          <EnrolForm lang="en" initial={e} onSubmit={save} />
        </Modal>
      )}
      {modal === "assess" && (
        <Modal title={`Readiness – ${e.full_name}`} wide onClose={() => setModal(null)}>
          <ReadinessForm lang="en" staff formPath="/programme/readiness/form?lang=en" submitPath={`/programme/entrepreneurs/${e.id}/readiness?lang=en`}
            onDone={() => { setModal(null); load(); }} />
        </Modal>
      )}
    </div>
  );
}
