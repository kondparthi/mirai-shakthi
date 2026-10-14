// MicroFin – Form G-2 (cash-flow data) and the calculated summary.
import { useState } from "react";
import { api, downloadArtefact, type Artefact } from "../api";
import StatementImport from "../components/StatementImport";
import { useLang } from "../i18n";

type Month = { month: string; cash_sales: number; credit_sales: number; raw_material: number; wages: number; rent: number; power: number; transport: number; other: number };
type Rcv = { customer: string; amount: number; invoice_date: string };
type Pay = { supplier: string; amount: number; due_date: string };
type Loan = { lender: string; outstanding: number; emi: number };
type Insight = { level: "good" | "warn" | "alert"; text: string };
type Out = {
  months: (Month & { sales: number; expenses: number; profit: number })[];
  totals: { sales: number; expenses: number; profit: number };
  averages: { sales: number; expenses: number; profit: number };
  ratios: { margin_pct: number | null; credit_share_pct: number | null; emi_to_profit_pct: number | null };
  receivables: { total: number; overdue: { customer: string; amount: number; days: number }[] };
  working_capital: { net: number };
  insights: Insight[];
  data_gaps: string[];
};

const HEADS: [keyof Month, string][] = [["cash_sales", "Cash / UPI sales"], ["credit_sales", "Credit sales"], ["raw_material", "Raw material / stock"],
  ["wages", "Wages"], ["rent", "Rent"], ["power", "Power & fuel"], ["transport", "Transport"], ["other", "Other expenses"]];

export const inr = (x: number) => Math.round(x).toLocaleString("en-IN");

function lastMonths(n: number): Month[] {
  const out: Month[] = [];
  const d = new Date();
  d.setDate(1);
  for (let i = n; i >= 1; i--) {
    const m = new Date(d.getFullYear(), d.getMonth() - i, 1);
    out.push({ month: `${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, "0")}`, cash_sales: 0, credit_sales: 0, raw_material: 0, wages: 0, rent: 0, power: 0, transport: 0, other: 0 });
  }
  return out;
}
const monthName = (ym: string) => new Date(`${ym}-01T00:00:00`).toLocaleDateString("en-IN", { month: "short", year: "numeric" });
const num = (v: string) => Math.max(0, Number(v.replace(/[^\d.]/g, "")) || 0);

function NumberInput({ value, onChange, label }: { value: number; onChange: (n: number) => void; label: string }) {
  return (
    <label className="field">
      <span className="small">{label}</span>
      <input className="input" inputMode="decimal" value={value ? String(value) : ""} placeholder="0" onChange={(e) => onChange(num(e.target.value))} />
    </label>
  );
}

export default function CashflowTool() {
  const { t } = useLang();
  const [months, setMonths] = useState<Month[]>(() => lastMonths(6));
  const [open, setOpen] = useState(0);
  const [stock, setStock] = useState(0);
  const [rcv, setRcv] = useState<Rcv[]>([]);
  const [pay, setPay] = useState<Pay[]>([]);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [purpose, setPurpose] = useState("understand");
  const [result, setResult] = useState<Artefact | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [imported, setImported] = useState(false);

  const setM = (i: number, k: keyof Month, v: number) => setMonths(months.map((m, j) => (j === i ? { ...m, [k]: v } : m)));
  const addEarlierMonth = () => {
    const first = new Date(`${months[0].month}-01T00:00:00`);
    first.setMonth(first.getMonth() - 1);
    const ym = `${first.getFullYear()}-${String(first.getMonth() + 1).padStart(2, "0")}`;
    setMonths([{ month: ym, cash_sales: 0, credit_sales: 0, raw_material: 0, wages: 0, rent: 0, power: 0, transport: 0, other: 0 }, ...months]);
    setOpen(0);
  };

  const submit = async () => {
    setError(null);
    setBusy(true);
    try {
      const r = await api<Artefact>("/artefacts/cashflow", { body: { months, stock_value: stock, receivables: rcv.filter((x) => x.customer && x.amount),
        payables: pay.filter((x) => x.supplier && x.amount), loans: loans.filter((x) => x.lender), purpose } });
      setResult(r);
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    const o = result.outputs as unknown as Out;
    return (
      <div className="stack">
        <div><h1>{t("toolCashflow")}</h1><p className="muted small" style={{ margin: 0 }}>{result.title}</p></div>
        <div className="kpis">
          <div><span>{t("totalSales")}</span><b>₹{inr(o.totals.sales)}</b></div>
          <div><span>{t("totalExpenses")}</span><b>₹{inr(o.totals.expenses)}</b></div>
          <div><span>{t("profit")}</span><b className={o.totals.profit < 0 ? "neg" : ""}>₹{inr(o.totals.profit)}</b></div>
          <div><span>{t("margin")}</span><b>{o.ratios.margin_pct == null ? "—" : `${o.ratios.margin_pct}%`}</b></div>
        </div>
        <div className="card stack">
          <h2>{t("whatNumbersSay")}</h2>
          {o.insights.map((i, k) => <div key={k} className={`insight ${i.level}`}>{i.text.replace(/Rs\. /g, "₹")}</div>)}
        </div>
        <div className="card">
          <h2>{t("byMonth")}</h2>
          <div className="mini-bars">
            {o.months.map((m) => {
              const max = Math.max(1, ...o.months.map((x) => Math.max(x.sales, x.expenses)));
              return (
                <div key={m.month} className="mb-row">
                  <span className="mb-label">{monthName(m.month)}</span>
                  <span className="mb-bars">
                    <span className="mb s" style={{ width: `${(m.sales / max) * 100}%` }} />
                    <span className="mb e" style={{ width: `${(m.expenses / max) * 100}%` }} />
                  </span>
                  <span className={`mb-val ${m.profit < 0 ? "neg" : ""}`}>₹{inr(m.profit)}</span>
                </div>
              );
            })}
            <div className="small muted"><span className="dot-s" /> {t("sales")} &nbsp; <span className="dot-e" /> {t("expenses")} &nbsp; · {t("profitRight")}</div>
          </div>
        </div>
        {o.receivables.overdue.length > 0 && (
          <div className="card">
            <h2>{t("followUpFirst")}</h2>
            {o.receivables.overdue.map((x) => <div key={x.customer} className="row-between"><span>{x.customer}</span><span>₹{inr(x.amount)} · {x.days} {t("days")}</span></div>)}
          </div>
        )}
        {o.data_gaps.length > 0 && <div className="notice">{o.data_gaps.join(" ")}</div>}
        <div className="wizard-actions">
          <button className="btn secondary" onClick={() => setResult(null)}>{t("editFigures")}</button>
          <button className="btn" onClick={() => downloadArtefact(result.id).catch((e) => setError(e.message))}>{t("downloadPdf")}</button>
        </div>
        {error && <div className="error">{error}</div>}
      </div>
    );
  }

  const repeaterRow = <T,>(list: T[], set: (l: T[]) => void, i: number, patch: Partial<T>) => set(list.map((x, j) => (j === i ? { ...x, ...patch } : x)));

  return (
    <div className="stack">
      <div><h1>{t("toolCashflow")}</h1><p className="muted small" style={{ margin: 0 }}>{t("cashflowIntro")}</p></div>

      <StatementImport onApply={(r) => {
        setMonths(r.months);
        // Keep loans the user already typed; add the EMI found in the statement once.
        if (r.loans.length) setLoans([...loans.filter((l) => l.lender && !r.loans.some((x) => x.lender === l.lender)), ...r.loans]);
        setOpen(-1);
        setImported(true);
      }} />
      {imported && <div className="insight good small" role="status">{t("stmtApplied")}</div>}

      <div className="card stack">
        <div className="row-between"><h2 style={{ margin: 0 }}>{t("monthlyFigures")}</h2>
          <button className="btn ghost small" onClick={addEarlierMonth}>+ {t("earlierMonth")}</button></div>
        {months.map((m, i) => {
          const sales = m.cash_sales + m.credit_sales;
          const exp = m.raw_material + m.wages + m.rent + m.power + m.transport + m.other;
          return (
            <div key={m.month} className={`month ${open === i ? "open" : ""}`}>
              <button type="button" className="month-head" onClick={() => setOpen(open === i ? -1 : i)} aria-expanded={open === i}>
                <b>{monthName(m.month)}</b>
                <span className="small muted">{sales || exp ? `${t("sales")} ₹${inr(sales)} · ${t("expenses")} ₹${inr(exp)}` : t("notFilled")}</span>
                <span>{open === i ? "▴" : "▾"}</span>
              </button>
              {open === i && (
                <div className="month-grid">
                  {HEADS.map(([k, label]) => <NumberInput key={k} label={label} value={m[k] as number} onChange={(v) => setM(i, k, v)} />)}
                  {months.length > 1 && <button type="button" className="btn ghost small danger" onClick={() => { setMonths(months.filter((_, j) => j !== i)); setOpen(-1); }}>{t("removeMonth")}</button>}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="card stack">
        <h2 style={{ margin: 0 }}>{t("customersOwe")}</h2>
        {rcv.map((r, i) => (
          <div key={i} className="rep-row">
            <input className="input" placeholder={t("customer")} value={r.customer} onChange={(e) => repeaterRow(rcv, setRcv, i, { customer: e.target.value })} />
            <input className="input" inputMode="decimal" placeholder="₹" value={r.amount || ""} onChange={(e) => repeaterRow(rcv, setRcv, i, { amount: num(e.target.value) })} />
            <input className="input" type="date" aria-label={t("invoiceDate")} value={r.invoice_date} onChange={(e) => repeaterRow(rcv, setRcv, i, { invoice_date: e.target.value })} />
            <button className="btn ghost" aria-label="Remove" onClick={() => setRcv(rcv.filter((_, j) => j !== i))}>✕</button>
          </div>
        ))}
        <button className="btn ghost small" onClick={() => setRcv([...rcv, { customer: "", amount: 0, invoice_date: new Date().toISOString().slice(0, 10) }])}>+ {t("addCustomer")}</button>
      </div>

      <div className="card stack">
        <h2 style={{ margin: 0 }}>{t("youOwe")}</h2>
        {pay.map((r, i) => (
          <div key={i} className="rep-row">
            <input className="input" placeholder={t("supplier")} value={r.supplier} onChange={(e) => repeaterRow(pay, setPay, i, { supplier: e.target.value })} />
            <input className="input" inputMode="decimal" placeholder="₹" value={r.amount || ""} onChange={(e) => repeaterRow(pay, setPay, i, { amount: num(e.target.value) })} />
            <input className="input" type="date" aria-label={t("dueDate")} value={r.due_date} onChange={(e) => repeaterRow(pay, setPay, i, { due_date: e.target.value })} />
            <button className="btn ghost" aria-label="Remove" onClick={() => setPay(pay.filter((_, j) => j !== i))}>✕</button>
          </div>
        ))}
        <button className="btn ghost small" onClick={() => setPay([...pay, { supplier: "", amount: 0, due_date: new Date().toISOString().slice(0, 10) }])}>+ {t("addSupplier")}</button>
      </div>

      <div className="card stack">
        <h2 style={{ margin: 0 }}>{t("loansStock")}</h2>
        <NumberInput label={t("stockValue")} value={stock} onChange={setStock} />
        {loans.map((l, i) => (
          <div key={i} className="rep-row">
            <input className="input" placeholder={t("lender")} value={l.lender} onChange={(e) => repeaterRow(loans, setLoans, i, { lender: e.target.value })} />
            <input className="input" inputMode="decimal" placeholder={t("outstanding")} value={l.outstanding || ""} onChange={(e) => repeaterRow(loans, setLoans, i, { outstanding: num(e.target.value) })} />
            <input className="input" inputMode="decimal" placeholder={t("emi")} value={l.emi || ""} onChange={(e) => repeaterRow(loans, setLoans, i, { emi: num(e.target.value) })} />
            <button className="btn ghost" aria-label="Remove" onClick={() => setLoans(loans.filter((_, j) => j !== i))}>✕</button>
          </div>
        ))}
        <button className="btn ghost small" onClick={() => setLoans([...loans, { lender: "", outstanding: 0, emi: 0 }])}>+ {t("addLoan")}</button>
        <label className="field"><span>{t("purpose")}</span>
          <select className="input" value={purpose} onChange={(e) => setPurpose(e.target.value)}>
            <option value="understand">{t("pUnderstand")}</option><option value="loan">{t("pLoan")}</option>
            <option value="working_capital">{t("pWc")}</option><option value="cash_shortage">{t("pCash")}</option>
          </select></label>
      </div>

      {error && <div className="error">{error}</div>}
      <button className="btn block" disabled={busy} onClick={submit}>{t("makeSummary")}</button>
    </div>
  );
}
