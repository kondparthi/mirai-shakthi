// DPR & finance dashboard: DPR pipeline, loan pipeline, money sanctioned and disbursed, banks, schemes, repayment health.
import { BadgeIndianRupee, Banknote, CheckCircle2, Clock4, FileText, HandCoins, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiDownload } from "../../api";
import { useAuth } from "../../auth";
import { Donut, HBars, Panel, StatTile } from "../../components/charts";
import { type AppRow, inr, inrShort, useDprMeta } from "./common";

type S = {
  dprs: Record<string, number>; approved_cost: number; approved_loan: number; by_model: { label: string; value: number }[];
  applications: Record<string, number>; requested: number; sanctioned_amount: number; subsidy_amount: number; disbursed_amount: number;
  avg_days_to_sanction: number | null; by_bank: { code: string; name: string; applications: number; sanctioned: number; amount: number }[];
  by_scheme: { code: string; applications: number; sanctioned: number; subsidy: number }[];
  repayment: { on_time: number; delayed: number; default: number }; overdue_amount: number; open_queries: AppRow[];
};

export default function FinanceReports() {
  const { user } = useAuth();
  const meta = useDprMeta();
  const [s, setS] = useState<S | null>(null);
  useEffect(() => {
    api<S>("/dpr/reports/summary").then(setS).catch(() => {});
  }, []);
  if (!s) return <div className="muted">Loading…</div>;
  const a = s.applications;
  const sent = (a.submitted ?? 0) + (a.query ?? 0) + (a.sanctioned ?? 0) + (a.disbursed ?? 0) + (a.rejected ?? 0);
  const sanctionedN = (a.sanctioned ?? 0) + (a.disbursed ?? 0);
  const decided = sanctionedN + (a.rejected ?? 0);
  const schemeName = (c: string) => (c === "none" ? "Bank loan only" : meta?.schemes.find((x) => x.code === c)?.name.split(" – ")[0] ?? c.toUpperCase());
  const loans = (a.disbursed ?? 0);
  return (
    <div className="stack">
      <div className="welcome">
        <h1>DPR & finance</h1>
        <p>{["admin", "programme_manager"].includes(user?.role ?? "") ? "All districts" : "Your districts"} · from project report to sanctioned loan and repayment.</p>
      </div>
      <div className="row-between" style={{ justifyContent: "flex-end" }}>
        <button className="btn secondary" onClick={() => apiDownload("/dpr/reports/applications.csv", "loan_applications.csv")}>Download applications (CSV)</button>
      </div>
      <div className="stats six">
        <StatTile icon={<FileText />} label="DPRs approved" value={s.dprs.approved ?? 0} note={`${s.dprs.draft ?? 0} draft · ${s.dprs.reviewed ?? 0} reviewed`} to="/admin/finance/dprs" />
        <StatTile icon={<BadgeIndianRupee />} tone="violet" label="Approved project cost" value={inrShort(s.approved_cost)} note={`Loans in DPRs ${inrShort(s.approved_loan)}`} />
        <StatTile icon={<CheckCircle2 />} tone="emerald" label="Sanctioned" value={inrShort(s.sanctioned_amount)}
          note={`${sanctionedN} of ${decided} decided (${decided ? Math.round((100 * sanctionedN) / decided) : 0}%)`} ratio={decided ? sanctionedN / decided : 0} />
        <StatTile icon={<Banknote />} tone="blue" label="Disbursed" value={inrShort(s.disbursed_amount)} note={`Subsidy sanctioned ${inrShort(s.subsidy_amount)}`} />
        <StatTile icon={<Clock4 />} tone="amber" label="Days to sanction" value={s.avg_days_to_sanction ?? "—"} note="Average, from submission" />
        <StatTile icon={<TriangleAlert />} tone="red" label="EMIs overdue" value={inrShort(s.overdue_amount)} note={`${s.repayment.delayed + s.repayment.default} of ${loans} loans`} warn={s.overdue_amount > 0} />
      </div>
      <div className="dash-grid">
        <Panel title="Applications by status" className="span-5">
          <Donut centerLabel="sent to banks" slices={[
            { key: "submitted", label: "With the bank", value: (a.submitted ?? 0) + (a.query ?? 0) },
            { key: "sanctioned", label: "Sanctioned", value: a.sanctioned ?? 0 },
            { key: "disbursed", label: "Disbursed", value: a.disbursed ?? 0 },
            { key: "rejected", label: "Rejected", value: a.rejected ?? 0 },
          ]} />
          <p className="small muted" style={{ marginBottom: 0 }}>{sent} sent · {a.draft ?? 0} drafts not yet sent</p>
        </Panel>
        <Panel title="Sanctioned by bank" className="span-7">
          <HBars format={inrShort} empty="Nothing sanctioned yet." rows={s.by_bank.filter((b) => b.amount > 0).map((b) => ({
            key: b.code, label: b.name, value: b.amount, hint: `${inr(b.amount)} · ${b.sanctioned} of ${b.applications} applications sanctioned` }))} />
        </Panel>
        <Panel title="Applications by scheme" className="span-6">
          <HBars empty="No applications yet." rows={s.by_scheme.map((x) => ({ key: x.code, label: schemeName(x.code), value: x.applications, color: "#3270bd",
            hint: `${x.applications} applications · ${x.sanctioned} sanctioned · subsidy ${inr(x.subsidy)}` }))} />
        </Panel>
        <Panel title="Repayment health" className="span-6">
          <Donut centerLabel="loans" slices={[
            { key: "on_time", label: "On time", value: s.repayment.on_time },
            { key: "delayed", label: "Delayed", value: s.repayment.delayed },
            { key: "default", label: "Default risk (3+ overdue)", value: s.repayment.default },
          ]} />
        </Panel>
        <Panel title="DPRs by enterprise model" className="span-6">
          <HBars empty="No DPRs yet." rows={s.by_model.map((x) => ({ key: x.label, label: x.label, value: x.value, color: "#8e5bd6" }))} />
        </Panel>
        <Panel title="Open bank queries" className="span-6" action={<HandCoins size={18} aria-hidden="true" />}>
          {s.open_queries.length === 0 && <p className="small muted" style={{ margin: 0 }}>No open queries.</p>}
          {s.open_queries.map((q) => (
            <Link key={q.id} to={`/admin/finance/applications/${q.id}`} className="row-between">
              <span><b>{q.owner.name}</b> <span className="small muted">{q.bank_name}, {q.branch}</span></span><span className="tag amber">query</span>
            </Link>))}
        </Panel>
      </div>
    </div>
  );
}
