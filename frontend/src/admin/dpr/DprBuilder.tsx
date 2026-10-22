// DPR builder (Form 5.1): inputs on the left, live figures on the right (calculated by the server as you type),
// scheme eligibility with reasons, AI-drafted narrative, review / approve / reopen with versions, PDF, and loan applications.
import {
  AlertTriangle, BadgeCheck, CalendarClock, CheckCircle2, Download, FileClock, Gauge, IndianRupee, Info, Landmark, Plus, RotateCcw, Save, Scale,
  Sparkles, Trash2, TrendingUp,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, openLink } from "../../api";
import { Panel, StatTile } from "../../components/charts";
import { useMaster } from "../../components/masters";
import { Field, Modal } from "../ui";
import {
  APP_TAG, DPR_TAG, type DprDetail, type DprMeta, type Inputs, Num, type Result, type SchemeCheck, fmtDay, inr, inrShort, pct, ratio, useDprMeta,
} from "./common";

const TABS = [["unit", "Unit & model"], ["cost", "Project cost"], ["finance", "Finance & loan"], ["sales", "Sales"], ["expenses", "Expenses"],
  ["narrative", "Narrative"], ["versions", "Versions"]] as const;
type Tab = (typeof TABS)[number][0];
const EXP: [keyof Inputs["expenses"], string][] = [["salaries", "Salaries and wages"], ["rent", "Rent / spot fee"], ["fuel", "Fuel, power and gas"],
  ["maintenance", "Repairs and maintenance"], ["other", "Other expenses"]];

type Form = Pick<DprDetail, "unit_name" | "model_id" | "district" | "mandal" | "village" | "address" | "activity" | "scheme_code" | "narrative" | "narrative_notes"> & { inputs: Inputs };

function toForm(d: DprDetail): Form {
  return { unit_name: d.unit_name, model_id: d.model_id, district: d.district, mandal: d.mandal, village: d.village, address: d.address,
    activity: d.activity, scheme_code: d.scheme_code, narrative: { ...d.narrative }, narrative_notes: { ...d.narrative_notes }, inputs: structuredClone(d.inputs) };
}

/** Sales and net profit for each projected year (values printed on the bars). */
function YearBars({ r }: { r: Result }) {
  const max = Math.max(1, ...r.pl.map((p) => Math.max(p.sales, Math.abs(p.pat))));
  const h = 120;
  return (
    <div className="yearbars" style={{ ["--n" as string]: r.pl.length }} role="img" aria-label={r.pl.map((p) => `Year ${p.year}: sales ${inr(p.sales)}, profit ${inr(p.pat)}`).join("; ")}>
      {r.pl.map((p) => (
        <div key={p.year} className="yb-col">
          <div className="yb-bars" style={{ height: h }}>
            <span className="yb s" style={{ height: `${(100 * p.sales) / max}%` }} title={`Sales ${inr(p.sales)}`} />
            <span className={`yb p ${p.pat < 0 ? "neg" : ""}`} style={{ height: `${(100 * Math.abs(p.pat)) / max}%` }} title={`Net profit ${inr(p.pat)}`} />
          </div>
          <b>{inrShort(p.sales)}</b><small>{inrShort(p.pat)}</small><span>Year {p.year}</span>
        </div>
      ))}
      <div className="yb-legend small"><span><i className="s" />Sales</span><span><i className="p" />Net profit</span></div>
    </div>
  );
}

function FinanceBar({ s }: { s: Result["summary"] }) {
  const parts = [["Own", s.own, "#16825d"], ["Subsidy", s.subsidy, "#cf8508"], ["Grant", s.grant, "#8e5bd6"], ["Bank loan", s.loan, "#3270bd"]] as const;
  const total = Math.max(1, s.own + s.subsidy + s.grant + s.loan);
  return (
    <div>
      <div className="finbar" role="img" aria-label={parts.map(([l, v]) => `${l} ${inr(v)}`).join(", ")}>
        {parts.filter(([, v]) => v > 0).map(([l, v, c]) => <span key={l} style={{ width: `${(100 * v) / total}%`, background: c }} title={`${l} ${inr(v)}`} />)}
      </div>
      <div className="finbar-legend small">{parts.filter(([, v]) => v > 0).map(([l, v, c]) => (
        <span key={l}><i style={{ background: c }} />{l} <b>{inr(v)}</b> ({Math.round((100 * v) / total)}%)</span>))}</div>
    </div>
  );
}

function Schemes({ list, current, canEdit, onUse }: { list: SchemeCheck[]; current: string | null; canEdit: boolean; onUse: (code: string | null) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="scheme-list">
      {list.map((s) => (
        <div key={s.code} className={`scheme ${s.eligible ? "yes" : "no"} ${current === s.code ? "current" : ""}`}>
          <button className="scheme-head" onClick={() => setOpen(open === s.code ? null : s.code)} aria-expanded={open === s.code}>
            <span className={`tag ${s.eligible ? (s.needs_check ? "amber" : "ok") : "grey"}`}>{s.eligible ? (s.needs_check ? "check" : "eligible") : "not eligible"}</span>
            <b>{s.name.split(" – ")[0]}</b>
            <span className="small muted">{s.subsidy ? `subsidy ${inr(s.subsidy)} (${s.subsidy_pct}%)` : s.tier ? s.tier : "no subsidy"} · own ≥ {s.own_pct}%</span>
          </button>
          {open === s.code && (
            <div className="scheme-body small">
              <ul className="checks">{s.checks.map((c, i) => (
                <li key={i} className={c.ok === true ? "ok" : c.ok === false ? "bad" : "unk"}>{c.ok === true ? "✓" : c.ok === false ? "✗" : "?"} {c.text}</li>))}</ul>
              <div className="muted">{s.category} category · {s.area} area{s.notes ? ` · ${s.notes}` : ""}</div>
              {s.sample && <div className="muted">Starter rules – the DPR officer should verify them (Schemes page).</div>}
              {s.url && <a href={s.url} target="_blank" rel="noreferrer">Official site</a>}
            </div>
          )}
          {canEdit && s.eligible && current !== s.code && <button className="btn small secondary" onClick={() => onUse(s.code)}>Use this scheme</button>}
          {canEdit && current === s.code && <button className="btn small ghost" onClick={() => onUse(null)}>Remove scheme</button>}
        </div>
      ))}
    </div>
  );
}

function ApplicationForm({ d, meta, onDone }: { d: DprDetail; meta: DprMeta; onDone: (id: number) => void }) {
  const eligible = d.eligibility.filter((s) => s.eligible);
  const [f, setF] = useState({ bank: meta.banks[0]?.code ?? "", branch: "", ifsc: "", scheme_code: d.scheme_code ?? "", amount_requested: d.result.summary.loan, app_number: "", portal: "" });
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    setError(null);
    try {
      const r = await api<{ id: number }>("/dpr/applications", { body: { ...f, dpr_id: d.id, ifsc: f.ifsc || null, scheme_code: f.scheme_code || null,
        app_number: f.app_number || null, portal: f.portal || null } });
      onDone(r.id);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="stack">
      <div className="grid-2">
        <Field label="Bank"><select className="input" value={f.bank} onChange={(e) => setF({ ...f, bank: e.target.value })}>
          {meta.banks.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}</select></Field>
        <Field label="Branch"><input className="input" value={f.branch} onChange={(e) => setF({ ...f, branch: e.target.value })} /></Field>
        <Field label="IFSC (optional)"><input className="input" value={f.ifsc} maxLength={11} onChange={(e) => setF({ ...f, ifsc: e.target.value.toUpperCase() })} /></Field>
        <Field label="Scheme" hint="Eligible schemes only">
          <select className="input" value={f.scheme_code} onChange={(e) => setF({ ...f, scheme_code: e.target.value })}>
            <option value="">Bank loan only (no scheme)</option>{eligible.map((s) => <option key={s.code} value={s.code}>{s.name.split(" – ")[0]}</option>)}</select></Field>
        <Field label="Loan amount requested (₹)" hint={`From the DPR: ${inr(d.result.summary.loan)}`}>
          <Num value={f.amount_requested} onChange={(v) => setF({ ...f, amount_requested: v })} /></Field>
        <Field label="Portal / bank application number (optional)"><input className="input" value={f.app_number} onChange={(e) => setF({ ...f, app_number: e.target.value })} /></Field>
      </div>
      {error && <div className="error">{error}</div>}
      <div><button className="btn" disabled={!f.branch.trim()} onClick={save}>Create application</button></div>
    </div>
  );
}

export default function DprBuilder() {
  const { id } = useParams();
  const navigate = useNavigate();
  const meta = useDprMeta();
  const [d, setD] = useState<DprDetail | null>(null);
  const [f, setF] = useState<Form | null>(null);
  const [live, setLive] = useState<{ result: Result; eligibility: SchemeCheck[] } | null>(null);
  const [tab, setTab] = useState<Tab>("unit");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [modal, setModal] = useState<"apply" | "reopen" | null>(null);
  const [reason, setReason] = useState("");
  const districts = useMaster("district");
  const mandals = useMaster("mandal", f?.district, !!f?.district);
  const villages = useMaster("village", f?.mandal, !!f?.mandal);
  const seq = useRef(0);

  const take = (x: DprDetail) => {
    setD(x);
    setF(toForm(x));
    setLive({ result: x.result, eligibility: x.eligibility });
    setDirty(false);
  };
  useEffect(() => {
    api<DprDetail>(`/dpr/dprs/${id}`).then(take).catch((e) => setMsg({ kind: "err", text: e.message }));
  }, [id]);

  // Live figures: recalculate on the server shortly after each change.
  useEffect(() => {
    if (!f || !d || !dirty) return;
    const n = ++seq.current;
    const t = setTimeout(() => {
      api<{ result: Result; eligibility: SchemeCheck[] }>(`/dpr/dprs/${d.id}/calc`, { body: { inputs: f.inputs, activity: f.activity, model_id: f.model_id } })
        .then((r) => n === seq.current && setLive(r)).catch(() => {});
    }, 350);
    return () => clearTimeout(t);
  }, [f, d, dirty]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const edit = useCallback((fn: (x: Form) => void) => {
    setF((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      fn(next);
      return next;
    });
    setDirty(true);
  }, []);

  const run = async (label: string, fn: () => Promise<DprDetail | void>, okText?: string) => {
    setBusy(label);
    setMsg(null);
    try {
      const r = await fn();
      if (r) take(r);
      if (okText) setMsg({ kind: "ok", text: okText });
    } catch (e) {
      setMsg({ kind: "err", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };
  const saveBody = () => f && ({ ...f, unit_name: f.unit_name.trim(), district: f.district ?? "" });
  const save = () => run("save", () => api<DprDetail>(`/dpr/dprs/${d!.id}`, { method: "PUT", body: saveBody() }), "Saved.");
  const saveFirst = async () => {
    if (dirty) take(await api<DprDetail>(`/dpr/dprs/${d!.id}`, { method: "PUT", body: saveBody() }));
  };

  const r = live?.result ?? d?.result;
  const s = r?.summary;
  const errors = useMemo(() => r?.warnings.filter((w) => w.level === "error") ?? [], [r]);
  if (!d || !f || !r || !s || !meta) return msg ? <div className="error">{msg.text}</div> : <div className="muted">Loading…</div>;

  const canEdit = d.can.edit;
  const inp = f.inputs;
  const model = meta.models.find((m) => m.id === f.model_id);
  const emptySections = d.sections.filter((x) => !(f.narrative[x.key] ?? "").trim());

  return (
    <div className="stack dpr">
      <Link to="/admin/finance/dprs" className="small">← DPRs</Link>
      <div className="card detail-head dpr-head">
        <div style={{ flex: 1, minWidth: 240 }}>
          <div className="chips" style={{ marginBottom: 6 }}>
            <span className={`tag ${DPR_TAG[d.status]}`}>{d.status}</span>
            <span className="tag grey">{d.code} · version {d.version}</span>
            {d.scheme_code && <span className="tag">{d.scheme_code.toUpperCase()}</span>}
            {dirty && <span className="tag amber">unsaved changes</span>}
          </div>
          <h1 style={{ margin: 0 }}>{f.unit_name || "Unit name"}</h1>
          <div className="small muted">
            {d.owner.type === "entrepreneur" ? <Link to={`/admin/entrepreneurs/${d.owner.id}`}>{d.owner.name}</Link> : <Link to={`/admin/groups?open=${d.owner.id}`}>{d.owner.name}</Link>}
            {" · "}{model?.name_en ?? "No model"} · {d.district_name}
            {d.approved_by && ` · approved by ${d.approved_by} on ${fmtDay(d.approved_at)}`}
            {!d.approved_by && d.reviewed_by && ` · reviewed by ${d.reviewed_by}`}
          </div>
        </div>
        <div className="row-gap dpr-actions">
          {canEdit && <button className="btn" disabled={!dirty || !!busy} onClick={save}><Save size={16} /> Save</button>}
          <button className="btn secondary" disabled={!!busy} onClick={() => run("pdf", async () => { await saveFirst(); await openLink(`/dpr/dprs/${d.id}/pdf-link`); })}>
            <Download size={16} /> {d.status === "approved" ? "DPR (PDF)" : "Draft PDF"}</button>
          {d.can.approve && d.status === "draft" && (
            <button className="btn secondary" disabled={!!busy || errors.length > 0 || emptySections.length > 0}
              title={errors.length ? "Fix the errors first" : emptySections.length ? "Write the narrative first" : ""}
              onClick={() => run("review", async () => { await saveFirst(); return api<DprDetail>(`/dpr/dprs/${d.id}/status`, { body: { action: "review" } }); }, "Marked reviewed.")}>
              <BadgeCheck size={16} /> Mark reviewed</button>)}
          {d.can.approve && d.status !== "approved" && (
            <button className="btn" disabled={!!busy || errors.length > 0 || emptySections.length > 0}
              onClick={() => run("approve", async () => { await saveFirst(); return api<DprDetail>(`/dpr/dprs/${d.id}/status`, { body: { action: "approve" } }); }, "Approved. The DPR can now be downloaded and used for a loan application.")}>
              <CheckCircle2 size={16} /> Approve</button>)}
          {d.can.approve && d.status === "approved" && <button className="btn ghost" onClick={() => setModal("reopen")}><RotateCcw size={16} /> Reopen</button>}
          {d.can.apply && <button className="btn" onClick={() => setModal("apply")}><Landmark size={16} /> Loan application</button>}
        </div>
      </div>
      {msg && <div className={msg.kind === "ok" ? "notice ok-notice" : "error"}>{msg.text}</div>}
      {d.status === "approved" && <div className="notice small">Approved DPRs are locked. Reopen to make version {d.version + 1}; version {d.version} stays in the history.</div>}
      {r.warnings.length > 0 && (
        <div className="warn-list">{r.warnings.map((w) => (
          <div key={w.code} className={`warn-item ${w.level}`}>{w.level === "info" ? <Info size={16} /> : <AlertTriangle size={16} />}{w.text}</div>))}</div>
      )}

      <div className="stats six">
        <StatTile icon={<IndianRupee />} label="Project cost" value={inrShort(s.project_cost)} note={`Equipment ${inrShort(s.capital)} · WC ${inrShort(s.working_capital)}`} />
        <StatTile icon={<Landmark />} tone="blue" label="Bank loan" value={inrShort(s.loan)} note={s.loan ? `EMI ${inr(s.emi)} × ${s.emi_months}` : "No loan needed"} ratio={s.loan_pct / 100} />
        <StatTile icon={<Gauge />} tone={s.min_dscr != null && s.min_dscr < 1.25 ? "red" : "emerald"} label="Average DSCR" value={ratio(s.avg_dscr)}
          note={s.min_dscr != null ? `Lowest ${ratio(s.min_dscr)} · banks look for 1.25+` : "No loan"} warn={s.min_dscr != null && s.min_dscr < 1.25} />
        <StatTile icon={<Scale />} tone="amber" label="Break-even (year 1)" value={pct(s.bep_pct_y1)} note={`${inr(s.bep_sales_y1)} of sales`}
          ratio={s.bep_pct_y1 != null ? s.bep_pct_y1 / 100 : undefined} warn={(s.bep_pct_y1 ?? 0) > 80} />
        <StatTile icon={<TrendingUp />} tone="violet" label="Profit a month (yr 1)" value={inr(s.monthly_profit_y1)} note={`Sales ${inr(s.monthly_sales_y1)} a month`} />
        <StatTile icon={<CalendarClock />} tone="teal" label="Payback" value={s.payback_months ? `${s.payback_months} months` : "—"} note="After drawings, before EMIs" />
      </div>

      <div className="dpr-grid">
        <div className="card stack dpr-form">
          <div className="tabs">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}
            {k === "narrative" && emptySections.length > 0 && <span className="dot" aria-label="needs attention" />}</button>)}</div>

          {tab === "unit" && (
            <div className="grid-2">
              <Field label="Unit name"><input className="input" disabled={!canEdit} value={f.unit_name} maxLength={160} onChange={(e) => edit((x) => { x.unit_name = e.target.value; })} /></Field>
              <Field label="Enterprise model" hint="Changing the model does not change the figures already entered">
                <select className="input" disabled={!canEdit} value={f.model_id ?? ""} onChange={(e) => edit((x) => { x.model_id = e.target.value ? Number(e.target.value) : null; })}>
                  <option value="">No model</option>{meta.models.map((m) => <option key={m.id} value={m.id}>{m.name_en}</option>)}</select></Field>
              <Field label="Activity" hint="Decides scheme limits (e.g. PMEGP manufacturing / service)">
                <select className="input" disabled={!canEdit} value={f.activity} onChange={(e) => edit((x) => { x.activity = e.target.value; })}>
                  {meta.activities.map((a) => <option key={a.code} value={a.code}>{a.label}</option>)}</select></Field>
              <Field label="District"><select className="input" disabled={!canEdit} value={f.district ?? ""} onChange={(e) => edit((x) => { x.district = e.target.value; x.mandal = null; x.village = null; })}>
                {districts.map((o) => <option key={o.code} value={o.code}>{o.name_en}</option>)}</select></Field>
              <Field label="Mandal"><select className="input" disabled={!canEdit} value={f.mandal ?? ""} onChange={(e) => edit((x) => { x.mandal = e.target.value || null; x.village = null; })}>
                <option value="">—</option>{mandals.map((o) => <option key={o.code} value={o.code}>{o.name_en}</option>)}
                {f.mandal && !mandals.some((o) => o.code === f.mandal) && <option value={f.mandal}>{f.mandal}</option>}</select></Field>
              <Field label="Village / ward"><select className="input" disabled={!canEdit} value={f.village ?? ""} onChange={(e) => edit((x) => { x.village = e.target.value || null; })}>
                <option value="">—</option>{villages.map((o) => <option key={o.code} value={o.code}>{o.name_en}</option>)}
                {f.village && !villages.some((o) => o.code === f.village) && <option value={f.village}>{f.village}</option>}</select></Field>
              <Field label="Address / spot of the unit"><input className="input" disabled={!canEdit} value={f.address ?? ""} maxLength={255} onChange={(e) => edit((x) => { x.address = e.target.value; })} /></Field>
              <Field label="Projection years"><select className="input" disabled={!canEdit} value={inp.years} onChange={(e) => edit((x) => { x.inputs.years = Number(e.target.value); })}>
                {[3, 4, 5].map((y) => <option key={y} value={y}>{y} years</option>)}</select></Field>
            </div>
          )}

          {tab === "cost" && (
            <div className="stack">
              <div className="table-wrap">
                <table className="table compact edit-table">
                  <thead><tr><th>Item</th><th>Specification</th><th className="num">Qty</th><th className="num">Rate (₹)</th><th className="num">Amount</th><th /></tr></thead>
                  <tbody>
                    {inp.capital_items.map((it, i) => (
                      <tr key={i}>
                        <td><input className="input" aria-label={`Item ${i + 1}`} disabled={!canEdit} value={it.item} onChange={(e) => edit((x) => { x.inputs.capital_items[i].item = e.target.value; })} /></td>
                        <td><input className="input" aria-label={`Specification ${i + 1}`} disabled={!canEdit} value={it.spec} onChange={(e) => edit((x) => { x.inputs.capital_items[i].spec = e.target.value; })} /></td>
                        <td className="num"><Num width={70} label={`Quantity ${i + 1}`} disabled={!canEdit} value={it.qty} onChange={(v) => edit((x) => { x.inputs.capital_items[i].qty = v; })} /></td>
                        <td className="num"><Num width={110} label={`Rate ${i + 1}`} disabled={!canEdit} value={it.rate} onChange={(v) => edit((x) => { x.inputs.capital_items[i].rate = v; })} /></td>
                        <td className="num">{inr(it.qty * it.rate)}</td>
                        <td>{canEdit && <button className="btn ghost small danger" aria-label={`Remove item ${i + 1}`} onClick={() => edit((x) => { x.inputs.capital_items.splice(i, 1); })}><Trash2 size={15} /></button>}</td>
                      </tr>
                    ))}
                    <tr className="total-row"><td colSpan={4}>Equipment and assets</td><td className="num">{inr(s.capital)}</td><td /></tr>
                  </tbody>
                </table>
              </div>
              {canEdit && <div><button className="btn secondary small" onClick={() => edit((x) => { x.inputs.capital_items.push({ item: "", spec: "", qty: 1, rate: 0 }); })}><Plus size={15} /> Add item</button></div>}
              <div className="grid-3">
                <Field label="Contingency (% of equipment)"><Num disabled={!canEdit} max={20} value={inp.contingency_pct} onChange={(v) => edit((x) => { x.inputs.contingency_pct = v; })} /></Field>
                <Field label="Pre-operative (₹)" hint="Licences, registration, deposits"><Num disabled={!canEdit} value={inp.preoperative} onChange={(v) => edit((x) => { x.inputs.preoperative = v; })} /></Field>
                <Field label="Working capital (₹)" hint="Stock, cash and credit to start"><Num disabled={!canEdit} value={inp.working_capital} onChange={(v) => edit((x) => { x.inputs.working_capital = v; })} /></Field>
              </div>
              <div className="kv"><span>Total project cost</span><b>{inr(s.project_cost)}</b></div>
            </div>
          )}

          {tab === "finance" && (
            <div className="stack">
              <div className="grid-3">
                <Field label="Own contribution (₹)" hint={`${pct(s.own_pct, 1)} of the project cost`}><Num disabled={!canEdit} value={inp.finance.own} onChange={(v) => edit((x) => { x.inputs.finance.own = v; })} /></Field>
                <Field label="Subsidy (₹)" hint="Set by choosing a scheme"><Num disabled={!canEdit} value={inp.finance.subsidy} onChange={(v) => edit((x) => { x.inputs.finance.subsidy = v; })} /></Field>
                <Field label="Grant (₹)" hint="CSR or other grant"><Num disabled={!canEdit} value={inp.finance.grant} onChange={(v) => edit((x) => { x.inputs.finance.grant = v; })} /></Field>
              </div>
              <div className="kv"><span>Bank loan (project cost − own − subsidy − grant)</span><b>{inr(s.loan)}</b></div>
              <FinanceBar s={s} />
              <h3>Loan terms</h3>
              <div className="grid-3">
                <Field label="Interest (% a year)"><Num disabled={!canEdit} max={40} value={inp.loan.interest_pct} onChange={(v) => edit((x) => { x.inputs.loan.interest_pct = v; })} /></Field>
                <Field label="Tenure (months)" hint="Including moratorium"><Num disabled={!canEdit} min={1} max={180} step={1} value={inp.loan.tenure_months} onChange={(v) => edit((x) => { x.inputs.loan.tenure_months = Math.round(v); })} /></Field>
                <Field label="Moratorium (months)" hint="Interest only"><Num disabled={!canEdit} max={36} step={1} value={inp.loan.moratorium_months} onChange={(v) => edit((x) => { x.inputs.loan.moratorium_months = Math.round(v); })} /></Field>
              </div>
              <div className="grid-3">
                <Field label="Owner's drawings (₹ a month)" hint="What the family takes home"><Num disabled={!canEdit} value={inp.drawings_monthly} onChange={(v) => edit((x) => { x.inputs.drawings_monthly = v; })} /></Field>
                <Field label="Depreciation (% WDV)"><Num disabled={!canEdit} max={100} value={inp.depreciation_pct} onChange={(v) => edit((x) => { x.inputs.depreciation_pct = v; })} /></Field>
                <Field label="Income tax (% of profit)"><Num disabled={!canEdit} max={50} value={inp.tax_pct} onChange={(v) => edit((x) => { x.inputs.tax_pct = v; })} /></Field>
              </div>
            </div>
          )}

          {tab === "sales" && (
            <div className="stack">
              <div className="table-wrap">
                <table className="table compact edit-table">
                  <thead><tr><th>Product / service</th><th>Unit</th><th className="num">Units a day</th><th className="num">Price (₹)</th><th className="num">A month</th><th /></tr></thead>
                  <tbody>
                    {inp.sales.items.map((it, i) => (
                      <tr key={i}>
                        <td><input className="input" aria-label={`Product ${i + 1}`} disabled={!canEdit} value={it.name} onChange={(e) => edit((x) => { x.inputs.sales.items[i].name = e.target.value; })} /></td>
                        <td><input className="input" aria-label={`Unit ${i + 1}`} style={{ width: 90 }} disabled={!canEdit} value={it.unit} onChange={(e) => edit((x) => { x.inputs.sales.items[i].unit = e.target.value; })} /></td>
                        <td className="num"><Num width={80} label={`Units a day ${i + 1}`} disabled={!canEdit} value={it.units_per_day} onChange={(v) => edit((x) => { x.inputs.sales.items[i].units_per_day = v; })} /></td>
                        <td className="num"><Num width={90} label={`Price ${i + 1}`} disabled={!canEdit} value={it.price} onChange={(v) => edit((x) => { x.inputs.sales.items[i].price = v; })} /></td>
                        <td className="num">{inr(it.units_per_day * it.price * inp.sales.working_days)}</td>
                        <td>{canEdit && <button className="btn ghost small danger" aria-label={`Remove product ${i + 1}`} onClick={() => edit((x) => { x.inputs.sales.items.splice(i, 1); })}><Trash2 size={15} /></button>}</td>
                      </tr>
                    ))}
                    <tr className="total-row"><td colSpan={4}>Sales in the first month</td><td className="num">{inr(s.monthly_sales_start)}</td><td /></tr>
                  </tbody>
                </table>
              </div>
              {canEdit && <div><button className="btn secondary small" onClick={() => edit((x) => { x.inputs.sales.items.push({ name: "", unit: "unit", units_per_day: 0, price: 0 }); })}><Plus size={15} /> Add product</button></div>}
              <div className="grid-3">
                <Field label="Working days a month"><Num disabled={!canEdit} max={31} value={inp.sales.working_days} onChange={(v) => edit((x) => { x.inputs.sales.working_days = v; })} /></Field>
                <Field label="Growth a month in year 1 (%)" hint="Customers building up"><Num disabled={!canEdit} min={-20} max={20} value={inp.sales.monthly_growth_pct} onChange={(v) => edit((x) => { x.inputs.sales.monthly_growth_pct = v; })} /></Field>
                <Field label="Growth a year after that (%)"><Num disabled={!canEdit} min={-50} max={50} value={inp.sales.yearly_growth_pct} onChange={(v) => edit((x) => { x.inputs.sales.yearly_growth_pct = v; })} /></Field>
              </div>
            </div>
          )}

          {tab === "expenses" && (
            <div className="stack">
              <div className="grid-3">
                <Field label="Raw material (% of sales)"><Num disabled={!canEdit} max={100} value={inp.expenses.raw_material_pct} onChange={(v) => edit((x) => { x.inputs.expenses.raw_material_pct = v; })} /></Field>
                {EXP.map(([k, l]) => (
                  <Field key={k} label={`${l} (₹ a month)`}><Num disabled={!canEdit} value={inp.expenses[k]} onChange={(v) => edit((x) => { x.inputs.expenses[k] = v; })} /></Field>))}
                <Field label="Expenses rise a year (%)"><Num disabled={!canEdit} max={50} value={inp.expenses.yearly_increase_pct} onChange={(v) => edit((x) => { x.inputs.expenses.yearly_increase_pct = v; })} /></Field>
              </div>
              <div className="kv"><span>Fixed expenses in the first month</span><b>{inr(EXP.reduce((a, [k]) => a + inp.expenses[k], 0))}</b></div>
            </div>
          )}

          {tab === "narrative" && (
            <div className="stack">
              <p className="small muted" style={{ margin: 0 }}>Write notes from the visit; {meta.ai ? "the AI drafts" : "a template drafts (AI is off on this server)"} each section using these notes and the calculated figures. Read and edit every section before approving.</p>
              <div className="grid-2">{d.note_fields.map((n) => (
                <Field key={n.key} label={n.label} hint={n.hint}>
                  <textarea className="input" rows={3} disabled={!canEdit} value={f.narrative_notes[n.key] ?? ""} onChange={(e) => edit((x) => { x.narrative_notes[n.key] = e.target.value; })} /></Field>))}</div>
              {canEdit && (
                <div className="row-gap">
                  <button className="btn" disabled={!!busy} onClick={() => {
                    if (Object.values(f.narrative).some((v) => v?.trim()) && !window.confirm("Replace the current text of all sections with a new draft?")) return;
                    run("draft", async () => { await saveFirst(); return api<DprDetail>(`/dpr/dprs/${d.id}/narrative`, { body: { narrative_notes: f.narrative_notes } }); }, "Draft written. Read and edit each section.");
                  }}><Sparkles size={16} /> {busy === "draft" ? "Writing…" : meta.ai ? "Draft with AI" : "Draft the sections"}</button>
                  {d.narrative_source && <span className="small muted">Last draft: {d.narrative_source === "ai" ? "AI" : d.narrative_source === "template" ? "template" : "edited by staff"}</span>}
                </div>)}
              {d.sections.map((x) => (
                <Field key={x.key} label={x.label}>
                  <textarea className="input" rows={x.key === "swot" ? 5 : 4} disabled={!canEdit} value={f.narrative[x.key] ?? ""}
                    placeholder="Not written yet" onChange={(e) => edit((y) => { y.narrative[x.key] = e.target.value; })} /></Field>))}
            </div>
          )}

          {tab === "versions" && (
            <div className="stack">
              {d.versions.length === 0 && <p className="muted small">A version is saved each time the DPR is reviewed, approved or reopened.</p>}
              {d.versions.map((v) => (
                <div key={v.id} className="row-between version-row">
                  <div><b>Version {v.version}</b> <span className={`tag ${DPR_TAG[v.status] ?? "grey"}`}>{v.status}</span>
                    <div className="small muted">{v.note} · {v.by} · {fmtDay(v.at)}</div></div>
                  <button className="btn ghost small" onClick={() => openLink(`/dpr/dprs/${d.id}/pdf-link?version_id=${v.id}`)}><FileClock size={15} /> PDF</button>
                </div>
              ))}
            </div>
          )}
          {canEdit && dirty && <div className="sticky-save"><span className="small">Unsaved changes</span><button className="btn small" disabled={!!busy} onClick={save}><Save size={15} /> Save</button></div>}
        </div>

        <div className="stack dpr-side">
          <Panel title="Sales and profit">
            <YearBars r={r} />
          </Panel>
          <Panel title="Schemes" action={<span className="small muted">rules only – no guessing</span>}>
            <Schemes list={live?.eligibility ?? d.eligibility} current={f.scheme_code} canEdit={canEdit}
              onUse={(code) => run("scheme", async () => { await saveFirst(); return api<DprDetail>(`/dpr/dprs/${d.id}/scheme`, { body: { code } }); },
                code ? "Scheme applied: subsidy and own contribution updated." : "Scheme removed.")} />
          </Panel>
        </div>
      </div>

      <Panel title="Projections">
        <div className="table-wrap">
          <table className="table compact proj">
            <thead><tr><th>₹</th>{r.pl.map((p) => <th key={p.year} className="num">Year {p.year}</th>)}</tr></thead>
            <tbody>
              <tr><td>Sales</td>{r.pl.map((p) => <td key={p.year} className="num">{inr(p.sales)}</td>)}</tr>
              <tr><td>Raw material</td>{r.pl.map((p) => <td key={p.year} className="num">{inr(p.raw_material)}</td>)}</tr>
              <tr><td>Fixed expenses</td>{r.pl.map((p) => <td key={p.year} className="num">{inr(p.fixed)}</td>)}</tr>
              <tr><td>Depreciation</td>{r.pl.map((p) => <td key={p.year} className="num">{inr(p.depreciation)}</td>)}</tr>
              <tr><td>Interest</td>{r.pl.map((p) => <td key={p.year} className="num">{inr(p.interest)}</td>)}</tr>
              <tr className="total-row"><td>Net profit</td>{r.pl.map((p) => <td key={p.year} className={`num ${p.pat < 0 ? "neg" : ""}`}>{inr(p.pat)}</td>)}</tr>
              <tr><td>Net profit % of sales</td>{r.pl.map((p) => <td key={p.year} className="num">{pct(p.pat_pct, 1)}</td>)}</tr>
              <tr><td>Closing cash</td>{r.cash_flow.map((c) => <td key={c.year} className={`num ${c.closing < 0 ? "neg" : ""}`}>{inr(c.closing)}</td>)}</tr>
              <tr><td>Loan repaid (principal)</td>{r.cash_flow.map((c) => <td key={c.year} className="num">{inr(c.principal)}</td>)}</tr>
              <tr className="total-row"><td>DSCR</td>{r.dscr.map((x) => <td key={x.year} className={`num ${x.dscr != null && x.dscr < 1.25 ? "neg" : ""}`}>{ratio(x.dscr)}</td>)}</tr>
              <tr><td>Break-even % of sales</td>{r.dscr.map((x) => <td key={x.year} className="num">{pct(x.bep_pct, 1)}</td>)}</tr>
            </tbody>
          </table>
        </div>
        <p className="small muted" style={{ marginBottom: 0 }}>DSCR = (net profit + depreciation + interest − owner's drawings) ÷ (interest + principal). The PDF has the full statements and the month-by-month repayment schedule.</p>
      </Panel>

      {d.applications.length > 0 && (
        <Panel title="Loan applications from this DPR">
          {d.applications.map((a) => (
            <Link key={a.id} to={`/admin/finance/applications/${a.id}`} className="row-between">
              <span><b>{a.bank_name}</b>, {a.branch} <span className="small muted">{a.code}</span></span>
              <span><span className={`tag ${APP_TAG[a.status]}`}>{a.status_label}</span> {inr(a.sanctioned_amount ?? a.amount_requested)}</span>
            </Link>))}
        </Panel>
      )}

      {modal === "apply" && (
        <Modal title="New loan / scheme application (Form 6.1)" wide onClose={() => setModal(null)}>
          <ApplicationForm d={d} meta={meta} onDone={(aid) => navigate(`/admin/finance/applications/${aid}`)} />
        </Modal>
      )}
      {modal === "reopen" && (
        <Modal title={`Reopen – this makes version ${d.version + 1}`} onClose={() => setModal(null)}>
          <div className="stack">
            <Field label="Why is the DPR being reopened?"><textarea className="input" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            <div><button className="btn" disabled={reason.trim().length < 3} onClick={() => { setModal(null);
              run("reopen", () => api<DprDetail>(`/dpr/dprs/${d.id}/status`, { body: { action: "reopen", note: reason } }), `Reopened as version ${d.version + 1}.`); setReason(""); }}>Reopen</button></div>
          </div>
        </Modal>
      )}
    </div>
  );
}
