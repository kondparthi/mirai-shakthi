// Set-up dashboard: units setting up / launched, purchase pipeline, money ordered vs DPR estimate, days to install,
// pending registrations, supplier delivery record, late deliveries and units ready to launch.
import { Clock4, IndianRupee, PiggyBank, Rocket, Truck, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { Donut, HBars, Panel, StatTile } from "../../components/charts";
import { fmtDay, inr, inrShort } from "../dpr/common";
import type { PurchaseRow, Supplier, UnitRow } from "./common";

type S = {
  units: Record<string, number>; launched_this_month: number; purchases: Record<string, number>; ordered_value: number; estimate_value: number;
  saving: number | null; avg_days_to_install: number | null; late_deliveries: (PurchaseRow & { unit: string })[];
  registrations: { kind: string; label: string; done: number; pending: number }[]; suppliers: Supplier[];
  by_model: { label: string; setting_up: number; launched: number }[]; ready_to_launch: UnitRow[];
};

export default function SetupReports() {
  const { user } = useAuth();
  const [s, setS] = useState<S | null>(null);
  useEffect(() => {
    api<S>("/setup/reports/summary").then(setS).catch(() => {});
  }, []);
  if (!s) return <div className="muted">Loading…</div>;
  const p = s.purchases;
  return (
    <div className="stack">
      <div className="welcome"><h1>Enterprise set-up</h1>
        <p>{["admin", "programme_manager"].includes(user?.role ?? "") ? "All districts" : "Your districts"} · from sanctioned plan to a launched unit.</p></div>
      <div className="stats six">
        <StatTile icon={<Wrench />} tone="amber" label="Setting up" value={s.units.setting_up ?? 0} to="/admin/setup/units" />
        <StatTile icon={<Rocket />} label="Launched" value={s.units.launched ?? 0} note={`${s.launched_this_month} this month`} />
        <StatTile icon={<IndianRupee />} tone="violet" label="Ordered" value={inrShort(s.ordered_value)} note={`DPR estimate ${inrShort(s.estimate_value)}`} />
        <StatTile icon={<PiggyBank />} tone="teal" label="Saved vs DPR" value={s.saving == null ? "—" : inrShort(s.saving)} warn={(s.saving ?? 0) < 0}
          note={s.saving != null && s.estimate_value ? `${((100 * s.saving) / s.estimate_value).toFixed(1)}% of the estimate` : "From quotations"} />
        <StatTile icon={<Clock4 />} tone="blue" label="Order → installed" value={s.avg_days_to_install == null ? "—" : `${s.avg_days_to_install} days`} note="Average" />
        <StatTile icon={<Truck />} tone="red" label="Late deliveries" value={s.late_deliveries.length} warn={s.late_deliveries.length > 0} />
      </div>
      <div className="dash-grid">
        <Panel title="Purchases by stage" className="span-5">
          <Donut centerLabel="purchases" slices={[
            { key: "rfq", label: "Asking quotations", value: (p.rfq ?? 0) + (p.draft ?? 0) },
            { key: "ordered", label: "Ordered", value: p.ordered ?? 0 },
            { key: "delivered", label: "Delivered", value: p.delivered ?? 0 },
            { key: "installed", label: "Installed", value: p.installed ?? 0 },
          ]} />
        </Panel>
        <Panel title="Registrations pending" className="span-7">
          <HBars empty="Nothing pending." rows={s.registrations.filter((r) => r.pending).map((r) => ({ key: r.kind, label: r.label, value: r.pending, color: "#cf8508", hint: `${r.pending} pending · ${r.done} done` }))} />
        </Panel>
        <Panel title="Units by enterprise model" className="span-6">
          <HBars empty="No units yet." rows={s.by_model.map((m) => ({ key: m.label, label: m.label, value: m.setting_up + m.launched, hint: `${m.launched} launched · ${m.setting_up} setting up` }))} />
        </Panel>
        <Panel title="Ready to launch" className="span-6">
          {!s.ready_to_launch.length && <p className="small muted" style={{ margin: 0 }}>No unit has finished its checklist yet.</p>}
          {s.ready_to_launch.map((u) => <Link key={u.id} to={`/admin/setup/units/${u.id}`} className="row-between"><span><b>{u.name}</b> <span className="small muted">{u.owner.name}</span></span><span className="tag ok">ready</span></Link>)}
        </Panel>
        <Panel title="Suppliers – orders and delivery" className="span-12">
          <div className="table-wrap"><table className="table compact">
            <thead><tr><th>Supplier</th><th className="num">Orders</th><th className="num">Value</th><th className="num">Delivered</th><th className="num">On time</th></tr></thead>
            <tbody>{s.suppliers.map((x) => (
              <tr key={x.id}><td>{x.name}</td><td className="num">{x.orders}</td><td className="num">{inr(x.value ?? 0)}</td><td className="num">{x.delivered}</td>
                <td className="num">{x.delivered ? `${Math.round((100 * (x.on_time ?? 0)) / x.delivered)}%` : "—"}</td></tr>))}
              {!s.suppliers.length && <tr><td colSpan={5} className="muted">No orders yet.</td></tr>}</tbody>
          </table></div>
        </Panel>
        {s.late_deliveries.length > 0 && (
          <Panel title="Late deliveries" className="span-12">
            {s.late_deliveries.map((d) => <Link key={d.id} to={`/admin/setup/units/purchase/${d.id}`} className="row-between"><span><b>{d.unit}</b> · {d.title} <span className="small muted">{d.supplier}</span></span>
              <span className="tag alert">due {fmtDay(d.expected_delivery)}</span></Link>)}
          </Panel>)}
      </div>
    </div>
  );
}
