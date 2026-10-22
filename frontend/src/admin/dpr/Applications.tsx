// Credit / scheme applications (M6): pipeline by status, and the application page (Forms 6.1, 6.2) with the document checklist,
// query log, status updates, EMI schedule and repayment tracking.
import { AlertTriangle, CheckCircle2, CircleDollarSign, FileCheck2, FileUp, Hourglass, Landmark, MessageSquareWarning, Plus, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, apiUpload, apiUrl } from "../../api";
import { Panel, StatTile } from "../../components/charts";
import { Field, Modal } from "../ui";
import { APP_TAG, type AppDetail, type AppRow, HEALTH, Num, STATE_TAG, fmtDay, inr, inrShort, today, useDprMeta } from "./common";

type ListRes = { counts: Record<string, number>; rows: AppRow[] };
const ORDER = ["draft", "submitted", "query", "sanctioned", "disbursed", "rejected", "withdrawn"];

export default function Applications() {
  const navigate = useNavigate();
  const meta = useDprMeta();
  const [res, setRes] = useState<ListRes | null>(null);
  const [status, setStatus] = useState("");
  const [bank, setBank] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const p = new URLSearchParams();
    if (status) p.set("status", status);
    if (bank) p.set("bank", bank);
    if (q) p.set("q", q);
    const t = setTimeout(() => api<ListRes>(`/dpr/applications?${p}`).then(setRes).catch(() => setRes({ counts: {}, rows: [] })), 200);
    return () => clearTimeout(t);
  }, [status, bank, q]);
  const c = res?.counts ?? {};
  const open = (c.submitted ?? 0) + (c.query ?? 0);
  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Loan & scheme applications</h1>
          <p className="muted small" style={{ margin: 0 }}>Draft → Submitted → Bank query → Sanctioned → Disbursed / Rejected. Start a new application from an approved DPR.</p></div>
        <Link to="/admin/finance/dprs?status=approved" className="btn secondary">Approved DPRs</Link>
      </div>
      <div className="stats">
        <StatTile icon={<Send />} tone="blue" label="With the bank" value={open} note={`${c.submitted ?? 0} submitted · ${c.query ?? 0} with a query`} warn={(c.query ?? 0) > 0} />
        <StatTile icon={<CheckCircle2 />} label="Sanctioned" value={(c.sanctioned ?? 0) + (c.disbursed ?? 0)} note={`${c.disbursed ?? 0} disbursed`} />
        <StatTile icon={<Hourglass />} tone="amber" label="Drafts" value={c.draft ?? 0} note="Documents being collected" />
        <StatTile icon={<AlertTriangle />} tone="red" label="Rejected" value={c.rejected ?? 0} />
      </div>
      <div className="filters row-gap">
        <input className="input" type="search" placeholder="Search name, code, bank number" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
        <select className="input" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
          <option value="">All statuses</option>{ORDER.map((s) => <option key={s} value={s}>{meta?.statuses.find((x) => x.code === s)?.label ?? s} ({c[s] ?? 0})</option>)}</select>
        <select className="input" value={bank} onChange={(e) => setBank(e.target.value)} aria-label="Bank">
          <option value="">All banks</option>{meta?.banks.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}</select>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Entrepreneur / unit</th><th>Bank</th><th>Scheme</th><th className="num">Amount</th><th>Status</th><th>Documents</th><th>Repayment</th></tr></thead>
          <tbody>
            {res?.rows.map((a) => (
              <tr key={a.id} className="clickable" onClick={() => navigate(`/admin/finance/applications/${a.id}`)}>
                <td><b>{a.owner.name}</b><div className="small muted">{a.unit_name} · {a.code}</div></td>
                <td>{a.bank_name}<div className="small muted">{a.branch}</div></td>
                <td>{a.scheme_code ? <span className="tag grey">{a.scheme_code.toUpperCase()}</span> : <span className="small muted">—</span>}</td>
                <td className="num">{inr(a.sanctioned_amount ?? a.amount_requested)}{a.sanctioned_amount != null && <div className="small muted">sanctioned</div>}</td>
                <td><span className={`tag ${APP_TAG[a.status]}`}>{a.status_label}</span><div className="small muted">{fmtDay(a.updated_at)}</div></td>
                <td className="small">{a.docs_have}/{a.docs_total}{a.missing_docs.length > 0 && a.status === "draft" && <div className="muted">{a.missing_docs.length} missing</div>}</td>
                <td className="small">{a.repayment ? <span className={`tag ${HEALTH[a.repayment.health][0]}`}>{HEALTH[a.repayment.health][1]}</span> : "—"}
                  {a.repayment && <div className="muted">{a.repayment.paid}/{a.repayment.total} EMIs</div>}</td>
              </tr>
            ))}
            {res && !res.rows.length && <tr><td colSpan={7} className="muted">No applications yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- one application
type StatusForm = { status: string; on: string; text: string; app_number: string; sanctioned_amount: number; subsidy_amount: number; disbursed_amount: number;
  interest_pct: number; emi_amount: number; tenure_months: number; first_emi_date: string; rejection_reason: string };

export function ApplicationDetail() {
  const { id } = useParams();
  const meta = useDprMeta();
  const [a, setA] = useState<AppDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<"status" | "event" | "edit" | "doc" | null>(null);
  const [sf, setSf] = useState<StatusForm | null>(null);
  const [ev, setEv] = useState({ kind: "response", text: "", on: today() });
  const [newDoc, setNewDoc] = useState("");
  const [pay, setPay] = useState<{ id: number; amount: number; on: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [docFor, setDocFor] = useState<string | null>(null);

  const load = useCallback(() => api<AppDetail>(`/dpr/applications/${id}`).then(setA).catch((e) => setError(e.message)), [id]);
  useEffect(() => {
    load();
  }, [load]);
  const call = async (fn: () => Promise<AppDetail>) => {
    setError(null);
    try {
      setA(await fn());
      setModal(null);
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    }
  };
  if (!a || !meta) return error ? <div className="error">{error}</div> : <div className="muted">Loading…</div>;
  const w = a.can.write;
  const startStatus = (status: string) => {
    setSf({ status, on: today(), text: "", app_number: a.app_number ?? "", sanctioned_amount: a.sanctioned_amount ?? a.amount_requested,
      subsidy_amount: a.subsidy_amount ?? 0, disbursed_amount: a.sanctioned_amount ?? a.amount_requested, interest_pct: a.interest_pct ?? 11,
      emi_amount: 0, tenure_months: 60, first_emi_date: "", rejection_reason: "" });
    setModal("status");
  };
  const sendStatus = () => sf && call(() => api<AppDetail>(`/dpr/applications/${a.id}/status`, { body: {
    status: sf.status, on: sf.on, text: sf.text || null, app_number: sf.app_number || null,
    ...(sf.status === "sanctioned" ? { sanctioned_amount: sf.sanctioned_amount, subsidy_amount: sf.subsidy_amount || null, interest_pct: sf.interest_pct } : {}),
    ...(sf.status === "disbursed" ? { disbursed_amount: sf.disbursed_amount, interest_pct: sf.interest_pct, emi_amount: sf.emi_amount || null,
      tenure_months: sf.tenure_months, first_emi_date: sf.first_emi_date || null } : {}),
    ...(sf.status === "rejected" ? { rejection_reason: sf.rejection_reason || null } : {}),
  } }));
  const upload = async (file?: File) => {
    if (!file || !docFor) return;
    const fd = new FormData();
    fd.append("file", file);
    await call(() => apiUpload<AppDetail>(`/dpr/applications/${a.id}/documents/${docFor}/file`, fd));
    if (fileRef.current) fileRef.current.value = "";
  };
  const label = (s: string) => meta.statuses.find((x) => x.code === s)?.label ?? s;
  const flowIdx = ORDER.indexOf(a.status);
  const steps = ["draft", "submitted", "sanctioned", "disbursed"];

  return (
    <div className="stack">
      <Link to="/admin/finance/applications" className="small">← Applications</Link>
      <div className="card detail-head">
        <div style={{ flex: 1, minWidth: 240 }}>
          <div className="chips" style={{ marginBottom: 6 }}>
            <span className={`tag ${APP_TAG[a.status]}`}>{a.status_label}</span><span className="tag grey">{a.code}</span>
            {a.scheme_code && <span className="tag">{a.scheme_code.toUpperCase()}</span>}
          </div>
          <h1 style={{ margin: 0 }}>{a.bank_name} · {a.branch}</h1>
          <div className="small muted">
            {a.owner.type === "entrepreneur" ? <Link to={`/admin/entrepreneurs/${a.owner.id}`}>{a.owner.name}</Link> : a.owner.name}
            {" · "}<Link to={`/admin/finance/dprs/${a.dpr_id}`}>{a.unit_name} ({a.dpr_code} v{a.dpr_version})</Link>
            {a.app_number && ` · bank no. ${a.app_number}`}
          </div>
        </div>
        {w && (
          <div className="row-gap">
            {a.next.filter((s) => s !== "withdrawn").map((s) => (
              <button key={s} className={`btn ${s === "rejected" ? "ghost danger" : s === "query" ? "secondary" : ""}`} onClick={() => startStatus(s)}>
                {s === "submitted" && a.status === "query" ? "Back to submitted" : label(s)}</button>))}
            {a.status === "query" && <button className="btn secondary" onClick={() => { setEv({ kind: "response", text: "", on: today() }); setModal("event"); }}>Answer query</button>}
            {["draft", "submitted", "query"].includes(a.status) && <button className="btn ghost" onClick={() => setModal("edit")}>Edit</button>}
            {a.next.includes("withdrawn") && <button className="btn ghost small" onClick={() => startStatus("withdrawn")}>Withdraw</button>}
          </div>
        )}
      </div>
      {error && <div className="error">{error}</div>}

      {!["rejected", "withdrawn"].includes(a.status) && (
        <ol className="loan-steps" aria-label="Progress">
          {steps.map((s, i) => {
            const done = ORDER.indexOf(s) < flowIdx || a.status === s || (a.status === "query" && s === "submitted");
            return <li key={s} className={done ? "done" : ""}><span>{i + 1}</span>{label(s)}</li>;
          })}
        </ol>
      )}

      <div className="stats">
        <StatTile icon={<CircleDollarSign />} label="Requested" value={inrShort(a.amount_requested)} note={a.submitted_on ? `Submitted ${fmtDay(a.submitted_on)}` : "Not submitted yet"} />
        <StatTile icon={<CheckCircle2 />} tone="emerald" label="Sanctioned" value={inrShort(a.sanctioned_amount)} note={a.subsidy_amount ? `Subsidy ${inr(a.subsidy_amount)}` : a.sanctioned_on ? fmtDay(a.sanctioned_on) : "—"} />
        <StatTile icon={<Landmark />} tone="blue" label="Disbursed" value={inrShort(a.disbursed_amount)} note={a.emi_amount ? `EMI ${inr(a.emi_amount)} × ${a.tenure_months}` : "—"} />
        <StatTile icon={<FileCheck2 />} tone="amber" label="Documents" value={`${a.docs_have}/${a.docs_total}`} ratio={a.docs_total ? a.docs_have / a.docs_total : 0}
          note={a.missing_docs.length ? `${a.missing_docs.length} missing` : "All in place"} warn={a.missing_docs.length > 0 && a.status === "draft"} />
      </div>
      {a.status === "rejected" && <div className="error">Rejected: {a.rejection_label}{a.rejection_note ? ` – ${a.rejection_note}` : ""}</div>}

      <div className="dash-grid">
        <Panel title="Document checklist" className="span-6" action={w && <button className="btn ghost small" onClick={() => setModal("doc")}><Plus size={14} /> Add</button>}>
          <input ref={fileRef} type="file" accept="application/pdf,image/*" hidden onChange={(e) => upload(e.target.files?.[0])} />
          <ul className="doclist">
            {a.documents.map((x) => (
              <li key={x.code} className={x.have ? "have" : ""}>
                <label className="check"><input type="checkbox" checked={x.have} disabled={!w}
                  onChange={(e) => call(() => api<AppDetail>(`/dpr/applications/${a.id}/documents`, { method: "PUT", body: { code: x.code, have: e.target.checked } }))} />
                  <span><b>{x.label}</b>{x.note && <small className="muted"> · {x.note}</small>}</span></label>
                <span className="row-gap">
                  {x.url && <a className="small" href={apiUrl(x.url)} target="_blank" rel="noreferrer">Open</a>}
                  {w && <button className="btn ghost small" aria-label={`Upload ${x.label}`} onClick={() => { setDocFor(x.code); fileRef.current?.click(); }}><FileUp size={14} /></button>}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="History and bank queries" className="span-6" action={w && <button className="btn ghost small" onClick={() => { setEv({ kind: "note", text: "", on: today() }); setModal("event"); }}><Plus size={14} /> Note</button>}>
          <ol className="loan-timeline">
            {[...a.events].reverse().map((e) => (
              <li key={e.id} className={e.kind}>
                <div className="row-between"><b>{e.kind === "status" ? e.status_label : e.kind === "query" ? "Bank query" : e.kind === "response" ? "Response" : "Note"}</b>
                  <small className="muted">{fmtDay(e.on)}</small></div>
                {e.text && <div className="small">{e.kind === "status" && e.status === "query" && <MessageSquareWarning size={14} />} {e.text}</div>}
                {e.by && <small className="muted">{e.by}</small>}
              </li>))}
          </ol>
        </Panel>
      </div>

      {a.schedule.length > 0 && a.repayment && (
        <Panel title="EMI schedule and repayments" action={<span className={`tag ${HEALTH[a.repayment.health][0]}`}>{HEALTH[a.repayment.health][1]}</span>}>
          <p className="small muted" style={{ marginTop: 0 }}>
            {a.repayment.paid} of {a.repayment.total} paid ({a.repayment.on_time} on time, {a.repayment.late} late) · {a.repayment.overdue} overdue
            {a.repayment.overdue ? ` (${inr(a.repayment.overdue_amount)})` : ""}{a.repayment.next ? ` · next: ${inr(a.repayment.next.amount)} on ${fmtDay(a.repayment.next.due_date)}` : ""}</p>
          <div className="table-wrap emi-table">
            <table className="table compact">
              <thead><tr><th>#</th><th>Due</th><th className="num">EMI</th><th className="num">Interest</th><th className="num">Principal</th><th className="num">Balance</th><th>Status</th><th /></tr></thead>
              <tbody>
                {a.schedule.map((r) => (
                  <tr key={r.id} className={r.state === "overdue" ? "row-bad" : ""}>
                    <td>{r.n}</td><td>{fmtDay(r.due_date)}</td><td className="num">{inr(r.amount)}</td><td className="num">{inr(r.interest)}</td>
                    <td className="num">{inr(r.principal)}</td><td className="num">{inr(r.balance)}</td>
                    <td><span className={`tag ${STATE_TAG[r.state][0]}`}>{STATE_TAG[r.state][1]}</span>{r.paid_on && <div className="small muted">{fmtDay(r.paid_on)}</div>}</td>
                    <td>{w && (r.paid_on
                      ? <button className="btn ghost small" onClick={() => call(() => api<AppDetail>(`/dpr/repayments/${r.id}`, { method: "PUT", body: { paid_on: null } }))}>Undo</button>
                      : ["overdue", "due"].includes(r.state) || r.n === (a.repayment?.next?.n ?? 0)
                        ? <button className="btn small secondary" onClick={() => setPay({ id: r.id, amount: r.amount, on: today() })}>Paid</button> : null)}</td>
                  </tr>))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {modal === "status" && sf && (
        <Modal title={`Update status: ${label(sf.status)} (Form 6.2)`} onClose={() => setModal(null)}>
          <div className="stack">
            <Field label="Date"><input className="input" type="date" max={today()} value={sf.on} onChange={(e) => setSf({ ...sf, on: e.target.value })} /></Field>
            {sf.status === "submitted" && <Field label="Portal / bank application number"><input className="input" value={sf.app_number} onChange={(e) => setSf({ ...sf, app_number: e.target.value })} /></Field>}
            {sf.status === "submitted" && a.missing_docs.length > 0 && <div className="notice small">Still missing: {a.missing_docs.join(", ")}</div>}
            {sf.status === "sanctioned" && (<div className="grid-2">
              <Field label="Sanctioned amount (₹)"><Num value={sf.sanctioned_amount} onChange={(v) => setSf({ ...sf, sanctioned_amount: v })} /></Field>
              <Field label="Subsidy (₹)"><Num value={sf.subsidy_amount} onChange={(v) => setSf({ ...sf, subsidy_amount: v })} /></Field>
              <Field label="Interest (% a year)"><Num value={sf.interest_pct} max={40} onChange={(v) => setSf({ ...sf, interest_pct: v })} /></Field>
            </div>)}
            {sf.status === "disbursed" && (<div className="grid-2">
              <Field label="Disbursed amount (₹)"><Num value={sf.disbursed_amount} onChange={(v) => setSf({ ...sf, disbursed_amount: v })} /></Field>
              <Field label="Interest (% a year)"><Num value={sf.interest_pct} max={40} onChange={(v) => setSf({ ...sf, interest_pct: v })} /></Field>
              <Field label="Number of EMIs"><Num value={sf.tenure_months} min={1} max={180} step={1} onChange={(v) => setSf({ ...sf, tenure_months: Math.round(v) })} /></Field>
              <Field label="First EMI date"><input className="input" type="date" min={sf.on} value={sf.first_emi_date} onChange={(e) => setSf({ ...sf, first_emi_date: e.target.value })} /></Field>
              <Field label="EMI from the bank (₹)" hint="Leave 0 to calculate"><Num value={sf.emi_amount} onChange={(v) => setSf({ ...sf, emi_amount: v })} /></Field>
            </div>)}
            {sf.status === "rejected" && <Field label="Reason"><select className="input" value={sf.rejection_reason} onChange={(e) => setSf({ ...sf, rejection_reason: e.target.value })}>
              <option value="">Choose…</option>{meta.rejection_reasons.map((x) => <option key={x.code} value={x.code}>{x.label}</option>)}</select></Field>}
            <Field label={sf.status === "query" ? "The bank's query" : "Remarks (optional)"}>
              <textarea className="input" rows={3} value={sf.text} onChange={(e) => setSf({ ...sf, text: e.target.value })} /></Field>
            {error && <div className="error">{error}</div>}
            <div><button className="btn" onClick={sendStatus}>Save</button></div>
          </div>
        </Modal>
      )}
      {modal === "event" && (
        <Modal title={ev.kind === "response" ? "Answer the bank's query" : "Add a note"} onClose={() => setModal(null)}>
          <div className="stack">
            <Field label="Date"><input className="input" type="date" max={today()} value={ev.on} onChange={(e) => setEv({ ...ev, on: e.target.value })} /></Field>
            <Field label={ev.kind === "response" ? "What was sent to the bank" : "Note"}><textarea className="input" rows={3} value={ev.text} onChange={(e) => setEv({ ...ev, text: e.target.value })} /></Field>
            {ev.kind === "response" && <p className="small muted" style={{ margin: 0 }}>The application goes back to Submitted.</p>}
            {error && <div className="error">{error}</div>}
            <div><button className="btn" disabled={ev.text.trim().length < 2} onClick={() => call(() => api<AppDetail>(`/dpr/applications/${a.id}/events`, { body: ev }))}>Save</button></div>
          </div>
        </Modal>
      )}
      {modal === "doc" && (
        <Modal title="Add a document the bank asked for" onClose={() => setModal(null)}>
          <div className="stack">
            <Field label="Document"><input className="input" value={newDoc} onChange={(e) => setNewDoc(e.target.value)} /></Field>
            {error && <div className="error">{error}</div>}
            <div><button className="btn" disabled={newDoc.trim().length < 2} onClick={async () => { if (await call(() => api<AppDetail>(`/dpr/applications/${a.id}/documents`, { body: { label: newDoc } }))) setNewDoc(""); }}>Add</button></div>
          </div>
        </Modal>
      )}
      {modal === "edit" && <EditApplication a={a} banks={meta.banks} onSave={(body) => call(() => api<AppDetail>(`/dpr/applications/${a.id}`, { method: "PUT", body }))} onClose={() => setModal(null)} error={error} />}
      {pay && (
        <Modal title="Record EMI payment" onClose={() => setPay(null)}>
          <div className="stack">
            <Field label="Paid on"><input className="input" type="date" max={today()} value={pay.on} onChange={(e) => setPay({ ...pay, on: e.target.value })} /></Field>
            <Field label="Amount (₹)"><Num value={pay.amount} onChange={(v) => setPay({ ...pay, amount: v })} /></Field>
            <div><button className="btn" onClick={async () => { if (await call(() => api<AppDetail>(`/dpr/repayments/${pay.id}`, { method: "PUT", body: { paid_on: pay.on, paid_amount: pay.amount } }))) setPay(null); }}>Save</button></div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function EditApplication({ a, banks, onSave, onClose, error }: { a: AppDetail; banks: { code: string; name: string }[]; onSave: (b: object) => void; onClose: () => void; error: string | null }) {
  const [f, setF] = useState({ bank: a.bank, branch: a.branch, ifsc: a.ifsc ?? "", amount_requested: a.amount_requested, app_number: a.app_number ?? "", portal: a.portal ?? "" });
  return (
    <Modal title="Edit application" onClose={onClose}>
      <div className="stack">
        <div className="grid-2">
          <Field label="Bank"><select className="input" value={f.bank} onChange={(e) => setF({ ...f, bank: e.target.value })}>{banks.map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}</select></Field>
          <Field label="Branch"><input className="input" value={f.branch} onChange={(e) => setF({ ...f, branch: e.target.value })} /></Field>
          <Field label="IFSC"><input className="input" maxLength={11} value={f.ifsc} onChange={(e) => setF({ ...f, ifsc: e.target.value.toUpperCase() })} /></Field>
          <Field label="Amount requested (₹)"><Num value={f.amount_requested} onChange={(v) => setF({ ...f, amount_requested: v })} /></Field>
          <Field label="Application number"><input className="input" value={f.app_number} onChange={(e) => setF({ ...f, app_number: e.target.value })} /></Field>
          <Field label="Portal"><input className="input" value={f.portal} placeholder="e.g. PMEGP e-portal, JanSamarth" onChange={(e) => setF({ ...f, portal: e.target.value })} /></Field>
        </div>
        {error && <div className="error">{error}</div>}
        <div><button className="btn" onClick={() => onSave({ ...f, ifsc: f.ifsc || null, app_number: f.app_number || null, portal: f.portal || null })}>Save</button></div>
      </div>
    </Modal>
  );
}
