// "DPR & finance" panel on the entrepreneur page: their DPRs and loan applications, which schemes fit (rules), and New DPR.
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api";
import { Modal } from "../ui";
import { NewDpr } from "./Dprs";
import { APP_TAG, type AppRow, DPR_TAG, type DprRow, type SchemeCheck, inr, ratio, useDprMeta } from "./common";

export default function EntrepreneurFinance({ eid, name }: { eid: number; name: string }) {
  const meta = useDprMeta();
  const navigate = useNavigate();
  const [dprs, setDprs] = useState<DprRow[] | null>(null);
  const [apps, setApps] = useState<AppRow[]>([]);
  const [modelId, setModelId] = useState<number | "">("");
  const [check, setCheck] = useState<SchemeCheck[] | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api<{ rows: DprRow[] }>(`/dpr/dprs?entrepreneur_id=${eid}`).then((r) => setDprs(r.rows)).catch(() => setDprs([]));
    api<{ rows: AppRow[] }>(`/dpr/applications?entrepreneur_id=${eid}`).then((r) => setApps(r.rows)).catch(() => {});
  }, [eid]);
  useEffect(() => {
    if (!meta) return;
    if (modelId === "" && meta.models.length) {
      setModelId(meta.models.find((m) => m.status === "active")?.id ?? meta.models[0].id);
      return;
    }
    api<{ schemes: SchemeCheck[] }>(`/dpr/eligibility?entrepreneur_id=${eid}${modelId ? `&model_id=${modelId}` : ""}`).then((r) => setCheck(r.schemes)).catch(() => setCheck(null));
  }, [eid, modelId, meta]);
  if (!meta || !dprs) return null;

  return (
    <div className="card stack">
      <div className="row-between"><h2 style={{ margin: 0 }}>DPR & finance</h2>
        {meta.can.write && <button className="btn small" onClick={() => setCreating(true)}>+ New DPR</button>}</div>
      {dprs.length === 0 && <p className="small muted" style={{ margin: 0 }}>No project report yet.</p>}
      {dprs.map((d) => (
        <Link key={d.id} to={`/admin/finance/dprs/${d.id}`} className="row-between">
          <span><b>{d.unit_name}</b> <span className="small muted">{d.code} v{d.version} · {d.model ?? "—"}</span></span>
          <span className="small">{inr(d.results.project_cost)} · loan {inr(d.results.loan)} · DSCR {ratio(d.results.avg_dscr)} <span className={`tag ${DPR_TAG[d.status]}`}>{d.status}</span></span>
        </Link>))}
      {apps.map((a) => (
        <Link key={a.id} to={`/admin/finance/applications/${a.id}`} className="row-between">
          <span>Loan: <b>{a.bank_name}</b>, {a.branch}</span>
          <span className="small">{inr(a.sanctioned_amount ?? a.amount_requested)} <span className={`tag ${APP_TAG[a.status]}`}>{a.status_label}</span></span>
        </Link>))}
      <div className="row-gap" style={{ alignItems: "center" }}>
        <b className="small">Schemes that fit for</b>
        <select className="input" style={{ maxWidth: 260 }} value={modelId} onChange={(e) => setModelId(e.target.value ? Number(e.target.value) : "")} aria-label="Enterprise model">
          {meta.models.map((m) => <option key={m.id} value={m.id}>{m.name_en}</option>)}</select>
      </div>
      {check && (
        <div className="chips small-chips">{check.map((s) => (
          <span key={s.code} className={`tag ${s.eligible ? (s.needs_check ? "amber" : "ok") : "grey"}`}
            title={s.checks.map((c) => `${c.ok === true ? "✓" : c.ok === false ? "✗" : "?"} ${c.text}`).join("\n")}>
            {s.eligible ? "✓" : "✗"} {s.name.split(" – ")[0]}{s.subsidy ? ` · subsidy ${s.subsidy_pct}%` : ""}</span>))}</div>
      )}
      <p className="small muted" style={{ margin: 0 }}>Using the model's template figures. Hover a scheme for the reasons.</p>
      {creating && (
        <Modal title={`New DPR – ${name}`} wide onClose={() => setCreating(false)}>
          <NewDpr meta={meta} owner={{ type: "entrepreneur", id: eid, name }} onDone={(id) => navigate(`/admin/finance/dprs/${id}`)} />
        </Modal>
      )}
    </div>
  );
}
