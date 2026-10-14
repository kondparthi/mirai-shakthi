import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

type Stats = {
  msme_users: number; profiles: number; conversations: number; questions: number; questions_7d: number;
  unmatched: number; flagged: number; helpful: number; not_helpful: number; kb_published: number; kb_review_due: number;
  experts_pending: number; requests_open?: number; requests_attention?: number; documents?: Record<string, number>; top_topics: { code: string; title: string; count: number }[];
  by_module: { module: string; name: string; count: number }[];
};

function Tile({ label, value, note, to, warn }: { label: string; value: number | string; note?: string; to?: string; warn?: boolean }) {
  const body = (
    <div className={`tile ${warn ? "warn" : ""}`}>
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {note && <div className="tile-note">{note}</div>}
    </div>
  );
  return to ? <Link to={to} className="tile-link">{body}</Link> : body;
}

export default function Dashboard() {
  const [s, setS] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<Stats>("/admin/stats").then(setS).catch((e) => setError(e.message));
  }, []);
  if (error) return <div className="error">{error}</div>;
  if (!s) return <div className="muted">Loading…</div>;

  const rated = s.helpful + s.not_helpful;
  const maxTopic = Math.max(1, ...s.top_topics.map((t) => t.count));
  const maxModule = Math.max(1, ...s.by_module.map((m) => m.count));

  return (
    <div className="stack">
      <div>
        <h1>Dashboard</h1>
        <p className="muted small">How MSMEs are using the AI Guidance Assistant.</p>
      </div>
      <div className="tiles">
        <Tile label="MSME users" value={s.msme_users} note={`${s.profiles} with a business profile`} to="/admin/users" />
        <Tile label="Questions asked" value={s.questions} note={`${s.questions_7d} in the last 7 days`} />
        <Tile label="Answers needing review" value={s.flagged} note="Not helpful or no verified source" to="/admin/review" warn={s.flagged > 0} />
        <Tile label="Helpful rating" value={rated ? `${Math.round((s.helpful / rated) * 100)}%` : "—"} note={`${rated} answers rated`} />
        <Tile label="Published content" value={s.kb_published} note={`${s.kb_review_due} due for review in 30 days`} to="/admin/knowledge" warn={s.kb_review_due > 0} />
        <Tile label="Experts awaiting approval" value={s.experts_pending} to="/admin/experts" warn={s.experts_pending > 0} />
        <Tile label="Open expert requests" value={s.requests_open ?? 0} note="Sent to experts and not yet closed" to="/admin/requests" />
        <Tile label="Requests needing attention" value={s.requests_attention ?? 0} note="Declined or past the reply time" to="/admin/requests" warn={(s.requests_attention ?? 0) > 0} />
        <Tile label="Documents created" value={Object.values(s.documents ?? {}).reduce((a, b) => a + b, 0)}
          note={["roadmap", "checklist", "cashflow", "jd"].map((k) => `${s.documents?.[k] ?? 0} ${{ roadmap: "roadmaps", checklist: "checklists", cashflow: "cash-flow", jd: "job desc." }[k]}`).join(" · ")} />
      </div>

      <div className="grid-2">
        <div className="card">
          <h2>Most asked topics</h2>
          {s.top_topics.length === 0 && <p className="muted small">No questions yet.</p>}
          {s.top_topics.map((t) => (
            <div key={t.code} className="bar-row">
              <span className="bar-label">{t.title}</span>
              <span className="bar"><span style={{ width: `${(t.count / maxTopic) * 100}%` }} /></span>
              <span className="bar-num">{t.count}</span>
            </div>
          ))}
          {s.unmatched > 0 && <p className="small muted" style={{ marginTop: 8 }}>{s.unmatched} conversation(s) did not match any topic – see Answer review.</p>}
        </div>
        <div className="card">
          <h2>Conversations by module</h2>
          {s.by_module.length === 0 && <p className="muted small">No conversations yet.</p>}
          {s.by_module.map((m) => (
            <div key={m.module} className="bar-row">
              <span className="bar-label">{m.name}</span>
              <span className={`bar m-${m.module}`}><span style={{ width: `${(m.count / maxModule) * 100}%` }} /></span>
              <span className="bar-num">{m.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
