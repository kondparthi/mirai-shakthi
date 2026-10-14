import { useEffect, useState } from "react";
import { Clock, Landmark, Library, MessageCircleQuestion, MessagesSquare, ThumbsUp, TriangleAlert, Users } from "lucide-react";
import { api } from "../api";
import { Donut, HBars, Panel, StatTile } from "../components/charts";

type Stats = {
  msme_users: number; profiles: number; conversations: number; questions: number; questions_7d: number;
  unmatched: number; flagged: number; helpful: number; not_helpful: number; kb_published: number; kb_review_due: number;
  experts_pending: number; requests_open?: number; requests_attention?: number; documents?: Record<string, number>; top_topics: { code: string; title: string; count: number }[];
  by_module: { module: string; name: string; count: number }[];
};

export default function Dashboard() {
  const [s, setS] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<Stats>("/admin/stats").then(setS).catch((e) => setError(e.message));
  }, []);
  if (error) return <div className="error">{error}</div>;
  if (!s) return <div className="muted">Loading…</div>;

  const rated = s.helpful + s.not_helpful;

  const docs = s.documents ?? {};
  const moduleColor: Record<string, string> = { microfin: "#3f6aa8", marketkonnect: "#c66f2b", launchpad: "#6a3596", skillspro: "#8f7a22", handholding: "#46784e" };

  return (
    <div className="stack">
      <div className="row-between">
        <div><h1>Assistant dashboard</h1>
          <p className="muted small" style={{ margin: 0 }}>How MSMEs are using the AI Guidance Assistant.</p></div>
      </div>
      <div className="stats">
        <StatTile icon={<Users />} label="MSME users" value={s.msme_users} note={`${s.profiles} with a business profile`} to="/admin/users"
          ratio={s.msme_users ? s.profiles / s.msme_users : 0} />
        <StatTile icon={<MessageCircleQuestion />} tone="blue" label="Questions asked" value={s.questions} note={`${s.questions_7d} in the last 7 days`} />
        <StatTile icon={<ThumbsUp />} tone="teal" label="Helpful rating" value={rated ? `${Math.round((s.helpful / rated) * 100)}%` : "—"}
          ratio={rated ? s.helpful / rated : 0} note={`${rated} answers rated`} />
        <StatTile icon={<TriangleAlert />} tone="red" label="Answers needing review" value={s.flagged} note="Not helpful or no verified source" to="/admin/review" warn={s.flagged > 0} />
        <StatTile icon={<Library />} tone="emerald" label="Published content" value={s.kb_published} note={`${s.kb_review_due} due for review in 30 days`} to="/admin/knowledge" warn={s.kb_review_due > 0} />
        <StatTile icon={<Landmark />} tone="violet" label="Experts awaiting approval" value={s.experts_pending} to="/admin/experts" warn={s.experts_pending > 0} />
        <StatTile icon={<MessagesSquare />} tone="blue" label="Open expert requests" value={s.requests_open ?? 0} note="Sent to experts and not yet closed" to="/admin/requests" />
        <StatTile icon={<Clock />} tone="amber" label="Requests needing attention" value={s.requests_attention ?? 0} note="Declined or past the reply time" to="/admin/requests" warn={(s.requests_attention ?? 0) > 0} />
      </div>

      <div className="dash-grid">
        <Panel title="Most asked topics" className="span-7">
          <HBars empty="No questions yet." rows={s.top_topics.map((t) => ({ key: t.code, label: t.title, value: t.count }))} />
          {s.unmatched > 0 && <p className="small muted" style={{ margin: "10px 0 0" }}>{s.unmatched} conversation(s) did not match any topic – see Answer review.</p>}
        </Panel>
        <Panel title="Documents created" className="span-5">
          <Donut centerLabel="documents" slices={[["roadmap", "Roadmaps"], ["checklist", "Checklists"], ["cashflow", "Cash-flow summaries"], ["jd", "Job descriptions"]]
            .map(([k, l]) => ({ key: k, label: l, value: docs[k] ?? 0 }))} />
        </Panel>
        <Panel title="Conversations by module" className="span-12">
          <HBars empty="No conversations yet." rows={s.by_module.map((m) => ({ key: m.module, label: m.name, value: m.count, color: moduleColor[m.module] }))} />
        </Panel>
      </div>
    </div>
  );
}
