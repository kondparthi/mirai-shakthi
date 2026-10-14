// MicroFin – fill the cash-flow form from a bank statement (Sprint 5). The user checks the figures before using them.
import { useRef, useState } from "react";
import { apiUpload, ApiError } from "../api";
import { useLang } from "../i18n";

export type StatementMonth = { month: string; cash_sales: number; credit_sales: number; raw_material: number; wages: number;
  rent: number; power: number; transport: number; other: number };
type Head = { head: string; label: string; side: "cr" | "dr"; counted_as: string | null; amount: number; count: number };
type Result = {
  months: StatementMonth[];
  loans: { lender: string; outstanding: number; emi: number }[];
  summary: { from: string; to: string; transactions: number; credits: number; debits: number; by_head: Head[];
    examples: { date: string; desc: string; side: string; amount: number; label: string }[] };
  warnings: string[];
};

const inr = (x: number) => Math.round(x).toLocaleString("en-IN");
const FIELD_LABEL: Record<string, string> = { cash_sales: "Sales", raw_material: "Raw material / stock", wages: "Wages", rent: "Rent",
  power: "Power & fuel", transport: "Transport", other: "Other expenses" };
const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
const monthName = (ym: string) => new Date(`${ym}-01T00:00:00`).toLocaleDateString("en-IN", { month: "short", year: "numeric" });

export default function StatementImport({ onApply }: { onApply: (r: Pick<Result, "months" | "loans">) => void }) {
  const { t, lang } = useLang();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [needPassword, setNeedPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<Result | null>(null);

  const isPdf = !!file && /\.pdf$/i.test(file.name);

  const upload = async (f: File | null = file) => {
    if (!f) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", f);
    if (password) form.append("password", password);
    form.append("lang", lang);
    try {
      setRes(await apiUpload<Result>("/artefacts/cashflow/statement", form));
    } catch (e) {
      const msg = (e as Error).message;
      if (e instanceof ApiError && e.status === 422 && /password/i.test(msg)) setNeedPassword(true);
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setRes(null); setFile(null); setPassword(""); setNeedPassword(false); setError(null);
    if (input.current) input.current.value = "";
  };

  if (res) {
    const s = res.summary;
    const counted = s.by_head.filter((h) => h.counted_as);
    const left = s.by_head.filter((h) => !h.counted_as);
    return (
      <div className="card stack statement">
        <div>
          <h2 style={{ margin: 0 }}>{t("stmtFound")}</h2>
          <p className="small muted" style={{ margin: "4px 0 0" }}>
            {s.transactions} {t("stmtTxns")} · {day(s.from)} – {day(s.to)} · {t("stmtIn")} ₹{inr(s.credits)} · {t("stmtOut")} ₹{inr(s.debits)}
          </p>
        </div>
        <div className="table-wrap">
          <table className="table compact">
            <thead><tr><th>{t("stmtFrom")}</th><th className="num">₹</th><th>{t("stmtGoesTo")}</th></tr></thead>
            <tbody>
              {counted.map((h) => <tr key={h.head}><td>{h.label} <span className="muted small">({h.count})</span></td>
                <td className="num">{inr(h.amount)}</td><td>{FIELD_LABEL[h.counted_as!] ?? h.counted_as}</td></tr>)}
              {left.map((h) => <tr key={h.head} className="muted"><td>{h.label} <span className="small">({h.count})</span></td>
                <td className="num">{inr(h.amount)}</td><td><i>{h.head === "emi" ? t("stmtAsLoan") : t("stmtNotCounted")}</i></td></tr>)}
            </tbody>
          </table>
        </div>
        <div className="table-wrap">
          <table className="table compact">
            <thead><tr><th>{t("stmtMonth")}</th><th className="num">{t("sales")}</th><th className="num">{t("expenses")}</th></tr></thead>
            <tbody>
              {res.months.map((m) => {
                const exp = m.raw_material + m.wages + m.rent + m.power + m.transport + m.other;
                return <tr key={m.month}><td>{monthName(m.month)}</td><td className="num">{inr(m.cash_sales + m.credit_sales)}</td><td className="num">{inr(exp)}</td></tr>;
              })}
            </tbody>
          </table>
        </div>
        {res.warnings.map((w) => <div key={w} className="insight warn small">{w}</div>)}
        <details className="small"><summary>{t("stmtExamples")}</summary>
          <ul className="examples">{s.examples.map((x, i) => <li key={i}><span className="muted">{day(x.date)}</span> {x.desc} – ₹{inr(x.amount)} → <b>{x.label}</b></li>)}</ul>
        </details>
        <p className="small muted" style={{ margin: 0 }}>{t("stmtCheck")}</p>
        <div className="wizard-actions" style={{ marginTop: 0 }}>
          <button className="btn secondary" onClick={reset}>{t("stmtCancel")}</button>
          <button className="btn" onClick={() => { onApply({ months: res.months, loans: res.loans }); reset(); }}>{t("stmtUse")}</button>
        </div>
      </div>
    );
  }

  return (
    <div className="card stack statement">
      <div>
        <h2 style={{ margin: 0 }}>{t("stmtTitle")}</h2>
        <p className="small muted" style={{ margin: "4px 0 0" }}>{t("stmtIntro")}</p>
      </div>
      <label className="file-pick">
        <input ref={input} type="file" accept=".xlsx,.xls,.csv,.pdf,.txt,application/pdf,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(e) => { const f = e.target.files?.[0] ?? null; setFile(f); setError(null); setNeedPassword(false); if (f && !/\.pdf$/i.test(f.name)) upload(f); }} />
        <span className="btn secondary">{file ? t("stmtChange") : t("stmtChoose")}</span>
        <span className="small muted file-name">{file ? file.name : "Excel · CSV · PDF"}</span>
      </label>
      {(isPdf || needPassword) && (
        <div className="row-gap">
          <label className="field" style={{ flex: 1 }}><span>{t("stmtPassword")}</span>
            <input className="input" type="password" autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          <button className="btn" disabled={busy || !file} onClick={() => upload()}>{t("stmtRead")}</button>
        </div>
      )}
      {busy && <div className="muted small">{t("stmtReading")}</div>}
      {error && <div className="error">{error}</div>}
      <p className="small muted" style={{ margin: 0 }}>🔒 {t("stmtPrivacy")}</p>
    </div>
  );
}
