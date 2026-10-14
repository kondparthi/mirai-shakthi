import { BadgeCheck, ClipboardCheck, GraduationCap, Hourglass, Sparkles, UserRound, UsersRound, Venus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { Donut, HBars, Panel, StatTile } from "../../components/charts";

type Stats = {
  total: number; verified: number; pending_consent: number; women: number; groups: number; assessed: number;
  avg_readiness: number | null; ready: number;
  by_stage: { stage: number; name: string; count: number }[];
  by_district: { district: string; name: string; count: number }[];
  by_source: Record<string, number>;
};
type Training = { batches: number; running: number; upcoming: number; trainees: number; certified: number;
  by_course: { key: string; trainees: number; certified: number }[] };
const SOURCES: [string, string][] = [["self", "Self (app)"], ["navigator", "Field navigator"], ["import", "Bulk import"], ["partner", "Partner"], ["campaign", "Campaign"]];
const WRITE = ["admin", "programme_manager", "coordinator", "federation_staff"];
const pct = (a: number, b: number) => (b ? Math.round((100 * a) / b) : 0);

export default function Overview() {
  const { user } = useAuth();
  const [s, setS] = useState<Stats | null>(null);
  const [tr, setTr] = useState<Training | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<Stats>("/programme/stats").then(setS).catch((e) => setError(e.message));
    api<Training>("/training/reports/summary").then(setTr).catch(() => {});
  }, []);
  if (error) return <div className="error">{error}</div>;
  if (!s) return <div className="muted">Loading…</div>;
  const scope = user?.scope?.districts?.length && !["admin", "programme_manager"].includes(user.role)
    ? `${user.scope.districts.length} district(s) in your area` : ["admin", "programme_manager"].includes(user?.role ?? "") ? "All districts" : "People you enrolled";
  const hour = new Date().getHours();

  return (
    <div className="stack">
      <section className="welcome">
        <h1>{hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"}, {(user?.name ?? "").split(" ")[0] || "team"}</h1>
        <p>Enrolment, readiness and training across the programme · {scope}</p>
        {WRITE.includes(user?.role ?? "") && (
          <div className="row-gap">
            <Link className="btn accent" to="/admin/entrepreneurs/new">+ Enrol entrepreneur</Link>
            <Link className="btn secondary" to="/admin/groups?new=1">+ Enrol group</Link>
            <Link className="btn secondary" to="/admin/training/batches">Training batches</Link>
          </div>
        )}
      </section>

      <div className="stats">
        <StatTile icon={<UserRound />} label="Entrepreneurs enrolled" value={s.total.toLocaleString("en-IN")} to="/admin/entrepreneurs"
          note={`${s.groups} group(s) as well`} />
        <StatTile icon={<Venus />} tone="violet" label="Women" value={`${pct(s.women, s.total)}%`} ratio={s.total ? s.women / s.total : 0} note={`${s.women} of ${s.total}`} />
        <StatTile icon={<BadgeCheck />} tone="teal" label="Profiles verified" value={s.verified} ratio={s.total ? s.verified / s.total : 0}
          note={`${pct(s.verified, s.total)}% of enrolled`} to="/admin/entrepreneurs?verified=true" />
        <StatTile icon={<Hourglass />} tone="amber" label="Waiting for consent" value={s.pending_consent} warn={s.pending_consent > 0}
          note="Imported people who have not opened the app yet" to="/admin/entrepreneurs?source=import" />
        <StatTile icon={<ClipboardCheck />} tone="blue" label="Readiness checked" value={s.assessed} ratio={s.total ? s.assessed / s.total : 0}
          note={s.avg_readiness != null ? `Average score ${s.avg_readiness} / 100` : "No checks yet"} />
        <StatTile icon={<Sparkles />} tone="emerald" label="Ready to start (70+)" value={s.ready} note={`${pct(s.ready, s.assessed)}% of those checked`} />
        {tr && <StatTile icon={<GraduationCap />} tone="teal" label="In training" value={tr.trainees} note={`${tr.running} batch(es) running · ${tr.upcoming} upcoming`} to="/admin/training/batches" />}
        {tr && <StatTile icon={<UsersRound />} tone="violet" label="Certified" value={tr.certified} ratio={tr.trainees ? tr.certified / tr.trainees : 0}
          note={`${pct(tr.certified, tr.trainees)}% of trainees`} to="/admin/training/reports" />}
      </div>

      <div className="dash-grid">
        <Panel title="Where people are in the journey" className="span-7"
          action={<Link className="btn ghost small" to="/admin/entrepreneurs">See all</Link>}>
          <HBars rows={s.by_stage.map((x) => ({ key: String(x.stage), label: `${x.stage}. ${x.name}`, value: x.count, to: `/admin/entrepreneurs?stage=${x.stage}` }))} total={s.total} />
        </Panel>
        <Panel title="How they joined" className="span-5">
          <Donut centerLabel="enrolled" slices={SOURCES.map(([k, l]) => ({ key: k, label: l, value: s.by_source[k] ?? 0 }))} />
        </Panel>
        <Panel title="By district" className="span-6">
          <HBars empty="No entrepreneurs yet." total={s.total}
            rows={s.by_district.slice(0, 10).map((x) => ({ key: x.district, label: x.name, value: x.count, to: `/admin/entrepreneurs?district=${x.district}`, color: "#3270bd" }))} />
        </Panel>
        <Panel title="Training by course" className="span-6" action={<Link className="btn ghost small" to="/admin/training/reports">Reports</Link>}>
          <HBars empty="No training batches yet."
            rows={(tr?.by_course ?? []).slice(0, 8).map((c) => ({ key: c.key, label: c.key, value: c.trainees, color: "#1e9c88", hint: `${c.trainees} trainees · ${c.certified} certified` }))} />
        </Panel>
      </div>
    </div>
  );
}
