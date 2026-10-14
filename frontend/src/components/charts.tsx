// Small, dependency-free dashboard pieces: stat tiles, horizontal bar lists and a donut.
// Palette validated for colour-blind separation (emerald, amber, blue, red, violet – fixed order, never cycled).
// Every chart shows its values as text, so colour is never the only way to read it.
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

export const SERIES = ["#16825d", "#cf8508", "#3270bd", "#d24e3a", "#8e5bd6"];
export type Tone = "emerald" | "amber" | "blue" | "violet" | "red" | "teal";

export function StatTile({ icon, label, value, note, to, tone = "emerald", ratio, warn }: {
  icon: ReactNode; label: string; value: ReactNode; note?: ReactNode; to?: string; tone?: Tone; ratio?: number; warn?: boolean;
}) {
  const body = (
    <div className={`stat ${warn ? "warn" : ""}`}>
      <div className="stat-top">
        <span className={`stat-icon ${tone}`} aria-hidden="true">{icon}</span>
        <span className="stat-label">{label}</span>
      </div>
      <div className="stat-value">{value}</div>
      {ratio !== undefined && (
        <div className="stat-meter" role="img" aria-label={`${Math.round(ratio * 100)}%`}><span style={{ width: `${Math.max(0, Math.min(1, ratio)) * 100}%` }} /></div>
      )}
      {note && <div className="stat-note">{note}</div>}
    </div>
  );
  return to ? <Link to={to} className="stat-link">{body}</Link> : body;
}

export type BarRow = { key: string; label: ReactNode; value: number; to?: string; color?: string; hint?: string };

/** Horizontal bars for magnitude by category; values printed at the end of each bar. */
export function HBars({ rows, empty = "No data yet.", format = (v: number) => v.toLocaleString("en-IN"), total }: {
  rows: BarRow[]; empty?: string; format?: (v: number) => string; total?: number;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  const sum = total ?? rows.reduce((a, r) => a + r.value, 0);
  if (!rows.length) return <p className="muted small" style={{ margin: 0 }}>{empty}</p>;
  return (
    <div className="hbars" role="list">
      {rows.map((r) => {
        const pct = sum ? Math.round((100 * r.value) / sum) : 0;
        const inner = (
          <>
            <span className="hbar-label">{r.label}</span>
            <span className="hbar-track"><span className="hbar-fill" style={{ width: `${(100 * r.value) / max}%`, background: r.color }} /></span>
            <span className="hbar-value">{format(r.value)}</span>
            <span className="hbar-tip" role="tooltip">{r.hint ?? `${format(r.value)} · ${pct}% of total`}</span>
          </>
        );
        return r.to
          ? <Link key={r.key} to={r.to} className="hbar" role="listitem">{inner}</Link>
          : <div key={r.key} className="hbar" role="listitem" tabIndex={0}>{inner}</div>;
      })}
    </div>
  );
}

/** Donut for parts of a whole (≤ 5 parts). Legend with values is always shown; hovering a part shows it in the middle. */
export function Donut({ slices, centerLabel, size = 168 }: { slices: { key: string; label: string; value: number }[]; centerLabel: string; size?: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const total = slices.reduce((a, s) => a + s.value, 0);
  const r = 62, c = 2 * Math.PI * r, gap = total && slices.filter((s) => s.value).length > 1 ? 2.2 : 0;
  let acc = 0;
  const shown = hover !== null ? slices[hover] : null;
  return (
    <div className="donut">
      <svg width={size} height={size} viewBox="0 0 160 160" role="img" aria-label={slices.map((s) => `${s.label} ${s.value}`).join(", ")}>
        <circle cx="80" cy="80" r={r} fill="none" stroke="var(--track)" strokeWidth="18" />
        {total > 0 && slices.map((s, i) => {
          const len = (c * s.value) / total;
          const el = s.value > 0 && (
            <circle key={s.key} cx="80" cy="80" r={r} fill="none" stroke={SERIES[i]} strokeWidth={hover === i ? 22 : 18}
              strokeDasharray={`${Math.max(0, len - gap)} ${c}`} strokeDashoffset={-acc} transform="rotate(-90 80 80)"
              onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} style={{ transition: "stroke-width .15s" }} />
          );
          acc += len;
          return el;
        })}
        <text x="80" y="78" textAnchor="middle" className="donut-num">{shown ? shown.value : total}</text>
        <text x="80" y="98" textAnchor="middle" className="donut-cap">{shown ? `${total ? Math.round((100 * shown.value) / total) : 0}%` : centerLabel}</text>
      </svg>
      <ul className="legend">
        {slices.map((s, i) => (
          <li key={s.key} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} className={hover === i ? "on" : ""}>
            <span className="sw" style={{ background: SERIES[i] }} />
            <span className="lg-label">{s.label}</span>
            <b>{s.value}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A titled panel. */
export function Panel({ title, action, children, className = "" }: { title: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-head"><h2>{title}</h2>{action}</header>
      {children}
    </section>
  );
}
