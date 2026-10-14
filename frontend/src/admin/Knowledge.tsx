import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Field, Modal, MODULES, moduleName, StatusTag } from "./ui";

type Kb = {
  id?: number; title: string; module: string; intent_code: string | null; language: string; body: string;
  source_url: string | null; verified_by: string | null; verified_on: string | null; review_due: string | null;
  status: string; updated_at?: string;
};
type Topic = { code: string; title_en: string; module: string };

const today = () => new Date().toISOString().slice(0, 10);
const inYear = () => { const d = new Date(); d.setFullYear(d.getFullYear() + 1); return d.toISOString().slice(0, 10); };
const EMPTY: Kb = { title: "", module: "launchpad", intent_code: null, language: "en", body: "", source_url: "", verified_by: "",
  verified_on: null, review_due: inYear(), status: "draft" };

function Editor({ item, topics, onClose, onSaved }: { item: Kb; topics: Topic[]; onClose: () => void; onSaved: () => void }) {
  const [k, setK] = useState<Kb>(item);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (f: keyof Kb) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setK({ ...k, [f]: e.target.value || null });

  const save = async (status?: string) => {
    setBusy(true);
    setError(null);
    const body = { ...k, status: status ?? k.status, title: k.title ?? "", body: k.body ?? "" };
    try {
      await api(k.id ? `/admin/kb/${k.id}` : "/admin/kb", { method: k.id ? "PUT" : "POST", body });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const markVerified = () => setK({ ...k, verified_on: today(),
    verified_by: !k.verified_by || k.verified_by.startsWith("Sample") ? "MIRAI content team" : k.verified_by });

  return (
    <Modal title={k.id ? "Edit content" : "Add content"} onClose={onClose} wide>
      <div className="form-grid">
        <Field label="Title"><input className="input" value={k.title} onChange={set("title")} /></Field>
        <Field label="Module">
          <select className="input" value={k.module} onChange={set("module")}>
            {MODULES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
        </Field>
        <Field label="Topic (optional)" hint="Content linked to a topic is shown first for that topic.">
          <select className="input" value={k.intent_code ?? ""} onChange={set("intent_code")}>
            <option value="">— any question in this module —</option>
            {topics.filter((t) => t.module === k.module).map((t) => <option key={t.code} value={t.code}>{t.title_en}</option>)}
          </select>
        </Field>
        <Field label="Language">
          <select className="input" value={k.language} onChange={set("language")}>
            <option value="en">English</option><option value="te">Telugu</option>
          </select>
        </Field>
      </div>
      <Field label="Content" hint="Plain, verified text. The assistant answers only from published content like this.">
        <textarea className="input" rows={9} value={k.body} onChange={set("body")} />
      </Field>
      <div className="form-grid">
        <Field label="Official source URL"><input className="input" placeholder="https://" value={k.source_url ?? ""} onChange={set("source_url")} /></Field>
        <Field label="Verified by"><input className="input" value={k.verified_by ?? ""} onChange={set("verified_by")} /></Field>
        <Field label="Verified on"><input className="input" type="date" value={k.verified_on ?? ""} onChange={set("verified_on")} /></Field>
        <Field label="Review due" hint="Content is hidden from answers after this date until re-verified.">
          <input className="input" type="date" value={k.review_due ?? ""} onChange={set("review_due")} />
        </Field>
      </div>
      {k.verified_by?.startsWith("Sample") && (
        <div className="notice">This is sample content. Check it against the official source, then click “Mark verified today”.</div>
      )}
      {error && <div className="error">{error}</div>}
      <div className="modal-actions">
        <span className="muted small">Status: <StatusTag status={k.status} /></span>
        <span style={{ flex: 1 }} />
        <button className="btn secondary" onClick={markVerified} disabled={busy}>Mark verified today</button>
        {k.status === "published" && <button className="btn secondary" onClick={() => save("archived")} disabled={busy}>Archive</button>}
        <button className="btn secondary" onClick={() => save("draft")} disabled={busy}>Save as draft</button>
        <button className="btn" onClick={() => save("published")} disabled={busy}>Publish</button>
      </div>
    </Modal>
  );
}

export default function Knowledge() {
  const [items, setItems] = useState<Kb[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [module, setModule] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<Kb | null>(null);

  const load = useCallback(() => {
    const p = new URLSearchParams();
    if (module) p.set("module", module);
    if (status) p.set("status", status);
    if (q.trim()) p.set("q", q.trim());
    api<Kb[]>(`/admin/kb?${p}`).then(setItems).catch(() => setItems([]));
  }, [module, status, q]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { api<Topic[]>("/admin/intents").then(setTopics).catch(() => {}); }, []);

  const due = (d: string | null) => d && d < new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10);

  return (
    <div className="stack">
      <div className="page-head">
        <div><h1>Knowledge library</h1><p className="muted small">Verified content the assistant uses for answers (screen A1).</p></div>
        <button className="btn" onClick={() => setEditing({ ...EMPTY })}>+ Add content</button>
      </div>
      <div className="filters">
        <input className="input" placeholder="Search title or text" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="input" value={module} onChange={(e) => setModule(e.target.value)}>
          <option value="">All modules</option>
          {MODULES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
        </select>
        <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option><option value="published">Published</option><option value="draft">Draft</option><option value="archived">Archived</option>
        </select>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Title</th><th>Module</th><th>Topic</th><th>Verified</th><th>Review due</th><th>Status</th></tr></thead>
          <tbody>
            {items.map((k) => (
              <tr key={k.id} onClick={() => setEditing(k)} className="clickable">
                <td><b>{k.title}</b></td>
                <td>{moduleName(k.module)}</td>
                <td className="muted">{topics.find((t) => t.code === k.intent_code)?.title_en ?? "—"}</td>
                <td>{k.verified_by?.startsWith("Sample") ? <span className="tag amber">Sample</span> : k.verified_on ?? "—"}</td>
                <td className={due(k.review_due) ? "warn-text" : ""}>{k.review_due ?? "—"}</td>
                <td><StatusTag status={k.status} /></td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={6} className="muted">No content found.</td></tr>}
          </tbody>
        </table>
      </div>
      {editing && <Editor item={editing} topics={topics} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}
