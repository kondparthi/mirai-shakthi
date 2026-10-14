import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { moduleName } from "./ui";

type Item = {
  id: number; session_id: number; question: string | null; answer: string; reason: string; module: string | null;
  intent_code: string | null; intent_title: string | null; confidence: number | null; rating: number | null;
  flagged: boolean; created_at: string | null; sources: string[];
};

const HELP: Record<string, string> = {
  "Rated not helpful": "Read the answer. Fix the content in the Knowledge library or the requirements of the topic.",
  "No verified source found": "Add published content that answers this question, linked to the right topic.",
  "Topic not recognised": "Add keywords to an existing topic, or create a new topic for this kind of question.",
};

export default function Review() {
  const [items, setItems] = useState<Item[]>([]);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const load = useCallback(() => {
    setLoading(true);
    api<Item[]>("/admin/review").then(setItems).catch(() => setItems([])).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const resolve = async (id: number, action: string) => {
    await api(`/admin/review/${id}`, { body: { action, note: notes[id] || null } });
    setItems((xs) => xs.filter((x) => x.id !== id));
  };

  return (
    <div className="stack">
      <div><h1>Answer review</h1><p className="muted small">Answers rated 👎, with no verified source, or with an unrecognised topic (screen A6). Fix the content, then mark the item done.</p></div>
      {loading && <div className="muted">Loading…</div>}
      {!loading && items.length === 0 && <div className="card">Nothing to review. 🎉</div>}
      {items.map((it) => (
        <div key={it.id} className="card stack">
          <div className="review-head">
            <span className="tag amber">{it.reason}</span>
            <span className="small muted">{it.intent_title ?? "No topic"} · {moduleName(it.module)}{it.confidence != null ? ` · confidence ${Math.round(it.confidence * 100)}%` : ""}</span>
            <span className="small muted" style={{ marginLeft: "auto" }}>{it.created_at ? new Date(it.created_at).toLocaleString() : ""}</span>
          </div>
          <div><div className="small muted">Question</div><div style={{ fontWeight: 600 }}>{it.question}</div></div>
          <div><div className="small muted">Answer given</div><div className="answer small">{it.answer}</div></div>
          {it.sources.length > 0 && <div className="small muted">Sources used: {it.sources.join(" · ")}</div>}
          <div className="notice">{HELP[it.reason] ?? "Check the answer and fix the content if needed."}{" "}
            <Link to="/admin/knowledge">Knowledge library</Link> · <Link to="/admin/topics">Topics & rules</Link></div>
          <input className="input" placeholder="Note (optional) – what you changed" value={notes[it.id] ?? ""} onChange={(e) => setNotes({ ...notes, [it.id]: e.target.value })} />
          <div className="modal-actions">
            <span style={{ flex: 1 }} />
            <button className="btn secondary" onClick={() => resolve(it.id, "no_action")}>No change needed</button>
            <button className="btn" onClick={() => resolve(it.id, "content_added")}>Fixed – mark done</button>
          </div>
        </div>
      ))}
    </div>
  );
}
