// Sales dashboard (M8): sales this month, orders by status, weekly trend, top units, by model and by channel, enquiries, units not yet selling.
import { HandCoins, IndianRupee, Megaphone, ShoppingCart, Star, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { Donut, HBars, Panel, StatTile } from "../../components/charts";
import { fmtDay, inr, inrShort } from "../dpr/common";

type S = {
  units_selling: number; units: number; sales_total: number; sales_month: number; orders_month: number; orders: Record<string, number>; outstanding: number;
  customers: number; repeat_pct: number; rating: number | null; ratings: number; weekly: { week: string; amount: number }[];
  top_units: { id: number; name: string; district_name: string | null; amount: number }[]; by_model: { label: string; amount: number }[];
  by_source: { label: string; count: number }[]; enquiries: Record<string, number>; not_selling: { id: number; name: string; launch_date: string | null }[];
};
const SOURCE: Record<string, string> = { unit: "Entered by the unit", staff: "Entered by staff", online: "Online shop", enquiry: "Buyer enquiry", campaign: "Campaign" };

export default function SalesDashboard() {
  const { user } = useAuth();
  const [s, setS] = useState<S | null>(null);
  useEffect(() => {
    api<S>("/market/reports/summary").then(setS).catch(() => {});
  }, []);
  if (!s) return <div className="muted">Loading…</div>;
  const max = Math.max(1, ...s.weekly.map((w) => w.amount));
  return (
    <div className="stack">
      <div className="welcome"><h1>Sales & orders</h1><p>{["admin", "programme_manager"].includes(user?.role ?? "") ? "All districts" : "Your districts"} · launched units, their customers and buyers.</p></div>
      <div className="stats six">
        <StatTile icon={<IndianRupee />} label="Sales this month" value={inrShort(s.sales_month)} note={`${s.orders_month} orders · total ${inrShort(s.sales_total)}`} />
        <StatTile icon={<ShoppingCart />} tone="blue" label="Units selling" value={`${s.units_selling}/${s.units}`} ratio={s.units ? s.units_selling / s.units : 0} note="Launched units with sales" />
        <StatTile icon={<HandCoins />} tone="amber" label="Credit to collect" value={inrShort(s.outstanding)} warn={s.outstanding > 0} />
        <StatTile icon={<UsersRound />} tone="violet" label="Customers" value={s.customers} note={`${s.repeat_pct}% bought again`} />
        <StatTile icon={<Star />} tone="teal" label="Customer rating" value={s.rating ? `★ ${s.rating}` : "—"} note={`${s.ratings} ratings`} />
        <StatTile icon={<Megaphone />} tone="red" label="Open enquiries" value={(s.enquiries.open ?? 0) + (s.enquiries.routed ?? 0)} to="/admin/market/enquiries" note={`${s.enquiries.won ?? 0} won`} />
      </div>
      <div className="dash-grid">
        <Panel title="Sales by week" className="span-7">
          <div className="week-bars" role="img" aria-label={s.weekly.map((w) => `${w.week}: ${inr(w.amount)}`).join(", ")}>
            {s.weekly.map((w) => (
              <div key={w.week}><span className="v">{w.amount ? inrShort(w.amount) : ""}</span><span className="b" style={{ height: `${Math.max(2, (100 * w.amount) / max)}%` }} /><small>{fmtDay(w.week).replace(/ \d{4}$/, "")}</small></div>))}
          </div>
        </Panel>
        <Panel title="Orders by status" className="span-5">
          <Donut centerLabel="orders" slices={[{ key: "new", label: "New", value: s.orders.new ?? 0 }, { key: "confirmed", label: "Confirmed", value: s.orders.confirmed ?? 0 },
            { key: "delivered", label: "Delivered (credit)", value: s.orders.delivered ?? 0 }, { key: "paid", label: "Paid", value: s.orders.paid ?? 0 }]} />
        </Panel>
        <Panel title="Top units" className="span-6">
          <HBars format={inrShort} empty="No sales yet." rows={s.top_units.map((u) => ({ key: String(u.id), label: u.name, value: u.amount, to: `/admin/market/units/${u.id}`, hint: `${inr(u.amount)} · ${u.district_name ?? ""}` }))} />
        </Panel>
        <Panel title="Sales by enterprise model" className="span-6">
          <HBars format={inrShort} empty="No sales yet." rows={s.by_model.map((m) => ({ key: m.label, label: m.label, value: m.amount, color: "#3270bd" }))} />
        </Panel>
        <Panel title="Where orders come from" className="span-6">
          <HBars empty="No orders yet." rows={s.by_source.map((x) => ({ key: x.label, label: SOURCE[x.label] ?? x.label, value: x.count, color: "#8e5bd6" }))} />
        </Panel>
        <Panel title="Launched, no sales recorded yet" className="span-6">
          {!s.not_selling.length && <p className="small muted" style={{ margin: 0 }}>Every launched unit has sales.</p>}
          {s.not_selling.map((u) => <Link key={u.id} to={`/admin/market/units/${u.id}`} className="row-between"><span>{u.name}</span><span className="small muted">launched {fmtDay(u.launch_date)}</span></Link>)}
        </Panel>
      </div>
    </div>
  );
}
