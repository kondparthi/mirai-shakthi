// DPR list (M5) with status tiles, and "New DPR" – pick the entrepreneur or group and the enterprise model (the DPR template).
import { CheckCircle2, FilePenLine, FileSearch, IndianRupee, Landmark } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, type EntrepreneurRow } from "../../api";
import { StatTile } from "../../components/charts";
import { Field, Modal } from "../ui";
import { DPR_TAG, type DprMeta, type DprRow, fmtDay, inr, inrShort, ratio, useDprMeta } from "./common";

type ListRes = { counts: Record<string, number>; approved_cost: number; approved_loan: number; rows: DprRow[] };
type GroupRow = { id: number; name: string; group_type: string; district_name: string | null; members_count?: number };

export function NewDpr({ meta, owner, onDone }: { meta: DprMeta; owner?: { type: "entrepreneur" | "group"; id: number; name: string }; onDone: (id: number) => void }) {
  const [kind, setKind] = useState<"entrepreneur" | "group">(owner?.type ?? "entrepreneur");
  const [q, setQ] = useState("");
  const [people, setPeople] = useState<EntrepreneurRow[]>([]);
  const [groups, setGroups] = useState<GroupRow[]>([]);
  const [pick, setPick] = useState<{ type: "entrepreneur" | "group"; id: number; name: string } | null>(owner ?? null);
  const models = meta.models;
  const [modelId, setModelId] = useState<number | "">(models.find((m) => m.status === "active")?.id ?? "");
  const [unit, setUnit] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (owner) return;
    const t = setTimeout(() => {
      const p = `q=${encodeURIComponent(q)}&lang=en`;
      if (kind === "entrepreneur") api<{ rows: EntrepreneurRow[] }>(`/programme/entrepreneurs?${p}`).then((r) => setPeople(r.rows)).catch(() => setPeople([]));
      else api<{ rows: GroupRow[] }>(`/programme/groups?${p}`).then((r) => setGroups(r.rows)).catch(() => setGroups([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q, kind, owner]);

  const create = async () => {
    if (!pick) return;
    setBusy(true);
    setError(null);
    try {
      const body = { [pick.type === "entrepreneur" ? "entrepreneur_id" : "group_id"]: pick.id, model_id: modelId || null, unit_name: unit || null };
      const r = await api<{ id: number }>("/dpr/dprs", { body });
      onDone(r.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const model = meta.models.find((m) => m.id === modelId);

  return (
    <div className="stack">
      {!owner && (
        <>
          <div className="tabs">{(["entrepreneur", "group"] as const).map((k) => (
            <button key={k} className={kind === k ? "on" : ""} onClick={() => { setKind(k); setPick(null); }}>{k === "entrepreneur" ? "Entrepreneur" : "Group (SHG / JLG)"}</button>
          ))}</div>
          <input className="input" type="search" placeholder="Search by name or mobile" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
          <div className="pick-list">
            {kind === "entrepreneur" && people.map((p) => (
              <button key={p.id} className={`pick ${pick?.id === p.id ? "on" : ""}`} onClick={() => setPick({ type: "entrepreneur", id: p.id, name: p.full_name })}>
                <b>{p.full_name}</b><small>{p.mobile} · {p.village_name}, {p.district_name} · stage {p.stage}</small></button>
            ))}
            {kind === "group" && groups.map((g) => (
              <button key={g.id} className={`pick ${pick?.id === g.id ? "on" : ""}`} onClick={() => setPick({ type: "group", id: g.id, name: g.name })}>
                <b>{g.name}</b><small>{g.group_type.toUpperCase()} · {g.district_name}</small></button>
            ))}
            {((kind === "entrepreneur" && !people.length) || (kind === "group" && !groups.length)) && <p className="small muted">No matches.</p>}
          </div>
        </>
      )}
      {pick && <div className="notice ok-notice small">For <b>{pick.name}</b></div>}
      <Field label="Enterprise model (DPR template)" hint="Equipment, sales and expenses are filled in from the model; change them in the builder.">
        <select className="input" value={modelId} onChange={(e) => setModelId(e.target.value ? Number(e.target.value) : "")}>
          <option value="">No model – start empty</option>
          {models.map((m) => <option key={m.id} value={m.id}>{m.name_en}{m.status !== "active" ? ` (${m.status})` : ""}</option>)}
        </select></Field>
      {model && <p className="small muted" style={{ margin: 0 }}>Equipment {inr(model.equipment_total)} + working capital {inr(model.working_capital)} · {model.jobs ?? "—"} jobs · schemes: {model.schemes.join(", ").toUpperCase() || "—"}</p>}
      <Field label="Unit name" hint="Leave blank to use the person's name and the model"><input className="input" value={unit} onChange={(e) => setUnit(e.target.value)} maxLength={160} /></Field>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" disabled={!pick || busy} onClick={create}>Create DPR</button></div>
    </div>
  );
}

export default function Dprs() {
  const navigate = useNavigate();
  const [sp, setSp] = useSearchParams();
  const meta = useDprMeta();
  const [res, setRes] = useState<ListRes | null>(null);
  const [status, setStatus] = useState(sp.get("status") ?? "");
  const [q, setQ] = useState("");
  const load = useCallback(() => {
    const p = new URLSearchParams();
    if (status) p.set("status", status);
    if (q) p.set("q", q);
    api<ListRes>(`/dpr/dprs?${p}`).then(setRes).catch(() => setRes({ counts: {}, approved_cost: 0, approved_loan: 0, rows: [] }));
  }, [status, q]);
  useEffect(() => {
    const t = setTimeout(load, 200);
    return () => clearTimeout(t);
  }, [load]);
  const c = res?.counts ?? {};
  const total = (c.draft ?? 0) + (c.reviewed ?? 0) + (c.approved ?? 0);

  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Detailed Project Reports</h1>
          <p className="muted small" style={{ margin: 0 }}>DPR builder (Form 5.1). The system calculates every figure; AI drafts the words; the DPR officer reviews and approves.</p></div>
        {meta?.can.write && <button className="btn" onClick={() => setSp({ new: "1" })}>+ New DPR</button>}
      </div>
      <div className="stats five">
        <StatTile icon={<FilePenLine />} label="In preparation" value={c.draft ?? 0} note="Drafts" tone="blue" />
        <StatTile icon={<FileSearch />} label="Reviewed" value={c.reviewed ?? 0} note="Waiting for approval" tone="amber" />
        <StatTile icon={<CheckCircle2 />} label="Approved" value={c.approved ?? 0} ratio={total ? (c.approved ?? 0) / total : 0} note={`${total ? Math.round((100 * (c.approved ?? 0)) / total) : 0}% of all DPRs`} />
        <StatTile icon={<IndianRupee />} tone="violet" label="Approved project cost" value={inrShort(res?.approved_cost)} note={<>Bank loans {inrShort(res?.approved_loan)}</>} />
        <StatTile icon={<Landmark />} tone="teal" label="Loan applications" value="Track" to="/admin/finance/applications" note="Submitted, sanctioned, disbursed" />
      </div>
      <div className="filters row-gap">
        <input className="input" type="search" placeholder="Search unit, person, code" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
        <div className="tabs">{[["", "All"], ["draft", "Draft"], ["reviewed", "Reviewed"], ["approved", "Approved"]].map(([k, l]) => (
          <button key={k} className={status === k ? "on" : ""} onClick={() => setStatus(k)}>{l}</button>))}</div>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Unit</th><th>Entrepreneur / group</th><th>Model</th><th className="num">Project cost</th><th className="num">Bank loan</th>
            <th className="num">DSCR</th><th>Status</th><th>Updated</th></tr></thead>
          <tbody>
            {res?.rows.map((d) => (
              <tr key={d.id} className="clickable" onClick={() => navigate(`/admin/finance/dprs/${d.id}`)}>
                <td><b>{d.unit_name}</b><div className="small muted">{d.code} · v{d.version}</div></td>
                <td>{d.owner.name}<div className="small muted">{d.district_name}</div></td>
                <td className="small">{d.model ?? "—"}{d.scheme_code && <div><span className="tag grey">{d.scheme_code.toUpperCase()}</span></div>}</td>
                <td className="num">{inr(d.results.project_cost)}</td>
                <td className="num">{inr(d.results.loan)}</td>
                <td className="num">{ratio(d.results.avg_dscr)}</td>
                <td><span className={`tag ${DPR_TAG[d.status]}`}>{d.status}</span>{!!d.results.errors && d.status === "draft" && <div className="small muted">{d.results.errors} to fix</div>}</td>
                <td className="small muted">{fmtDay(d.updated_at)}</td>
              </tr>
            ))}
            {res && !res.rows.length && <tr><td colSpan={8} className="muted">No DPRs {status ? `with status ${status}` : "yet"}.</td></tr>}
          </tbody>
        </table>
      </div>
      {sp.get("new") && meta && (
        <Modal title="New DPR" wide onClose={() => setSp({})}>
          <NewDpr meta={meta} onDone={(id) => navigate(`/admin/finance/dprs/${id}`)} />
        </Modal>
      )}
    </div>
  );
}
