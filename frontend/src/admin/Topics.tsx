import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import ConditionBuilder, { describe } from "./ConditionBuilder";
import { Field, Modal, MODULES, moduleName, toList } from "./ui";

type Rule = {
  id?: number; item_code: string; title_en: string; title_te: string | null; why_en: string | null; why_te?: string | null;
  condition: Record<string, unknown> | null; have_check: Record<string, unknown> | null; step_order: number;
  documents: string | null; time_estimate: string | null; cost_note: string | null; official_link: string | null; active: boolean;
};
type Topic = {
  id?: number; code: string; module: string; title_en: string; title_te: string | null; description: string | null;
  keywords: string[]; sample_questions: string[]; connect_service: string | null; active: boolean; rule_count?: number; rules?: Rule[];
};

const EMPTY_TOPIC: Topic = { code: "", module: "launchpad", title_en: "", title_te: "", description: "", keywords: [], sample_questions: [], connect_service: "general_advice", active: true };
const EMPTY_RULE: Rule = { item_code: "", title_en: "", title_te: "", why_en: "", condition: null, have_check: null, step_order: 10,
  documents: "", time_estimate: "", cost_note: "", official_link: "", active: true };
const nullify = <T extends object>(o: T): T => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, v === "" ? null : v])) as T;

function TopicForm({ topic, services, onClose, onSaved }: { topic: Topic; services: string[]; onClose: () => void; onSaved: (t: Topic) => void }) {
  const [t, setT] = useState(topic);
  const [kw, setKw] = useState(topic.keywords.join(", "));
  const [qs, setQs] = useState(topic.sample_questions.join("\n"));
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    setError(null);
    try {
      const body = nullify({ ...t, keywords: toList(kw), sample_questions: qs.split("\n").map((s) => s.trim()).filter(Boolean) });
      const saved = await api<Topic>(t.id ? `/admin/intents/${t.id}` : "/admin/intents", { method: t.id ? "PUT" : "POST", body });
      onSaved(saved);
    } catch (e) { setError((e as Error).message); }
  };
  return (
    <Modal title={t.id ? "Edit topic" : "New topic"} onClose={onClose} wide>
      <div className="form-grid">
        <Field label="Title (English)"><input className="input" value={t.title_en} onChange={(e) => setT({ ...t, title_en: e.target.value })} /></Field>
        <Field label="Title (Telugu)"><input className="input" value={t.title_te ?? ""} onChange={(e) => setT({ ...t, title_te: e.target.value })} /></Field>
        <Field label="Code" hint="Lowercase letters, numbers and _ only">
          <input className="input mono" value={t.code} onChange={(e) => setT({ ...t, code: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") })} /></Field>
        <Field label="Module">
          <select className="input" value={t.module} onChange={(e) => setT({ ...t, module: e.target.value })}>
            {MODULES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select></Field>
      </div>
      <Field label="Keywords" hint="Words or short phrases in English or Telugu, separated by commas. Phrases count more than single words.">
        <textarea className="input" rows={3} value={kw} onChange={(e) => setKw(e.target.value)} /></Field>
      <Field label="Sample questions" hint="One per line. The first one appears on the app home screen.">
        <textarea className="input" rows={3} value={qs} onChange={(e) => setQs(e.target.value)} /></Field>
      <div className="form-grid">
        <Field label="Expert service for Handholding">
          <select className="input" value={t.connect_service ?? ""} onChange={(e) => setT({ ...t, connect_service: e.target.value || null })}>
            <option value="">— none —</option>
            {services.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
          </select></Field>
        <Field label="Active"><select className="input" value={String(t.active)} onChange={(e) => setT({ ...t, active: e.target.value === "true" })}>
          <option value="true">Active</option><option value="false">Hidden</option></select></Field>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="modal-actions"><span style={{ flex: 1 }} /><button className="btn secondary" onClick={onClose}>Cancel</button><button className="btn" onClick={save}>Save topic</button></div>
    </Modal>
  );
}

function RuleForm({ rule, topicId, onClose, onSaved }: { rule: Rule; topicId: number; onClose: () => void; onSaved: () => void }) {
  const [r, setR] = useState(rule);
  const [error, setError] = useState<string | null>(null);
  const set = (f: keyof Rule) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setR({ ...r, [f]: e.target.value });
  const save = async () => {
    setError(null);
    try {
      await api(r.id ? `/admin/rules/${r.id}` : `/admin/intents/${topicId}/rules`, { method: r.id ? "PUT" : "POST", body: nullify({ ...r, step_order: Number(r.step_order) }) });
      onSaved();
    } catch (e) { setError((e as Error).message); }
  };
  const remove = async () => {
    if (!r.id || !confirm(`Delete “${r.title_en}”? This cannot be undone.`)) return;
    try { await api(`/admin/rules/${r.id}`, { method: "DELETE" }); onSaved(); } catch (e) { setError((e as Error).message); }
  };
  return (
    <Modal title={r.id ? "Edit requirement" : "New requirement"} onClose={onClose} wide>
      <div className="form-grid">
        <Field label="What is required (English)"><input className="input" value={r.title_en} onChange={set("title_en")} /></Field>
        <Field label="Telugu title"><input className="input" value={r.title_te ?? ""} onChange={set("title_te")} /></Field>
        <Field label="Item code" hint="Same code across topics means the same item (e.g. udyam)">
          <input className="input mono" value={r.item_code} onChange={(e) => setR({ ...r, item_code: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") })} /></Field>
        <Field label="Step order" hint="Lower numbers are shown first"><input className="input" type="number" value={r.step_order} onChange={set("step_order")} /></Field>
      </div>
      <div className="form-grid">
        <Field label="Why it matters"><textarea className="input" rows={2} value={r.why_en ?? ""} onChange={set("why_en")} /></Field>
        <Field label="Why it matters (Telugu)"><textarea className="input" rows={2} value={r.why_te ?? ""} onChange={set("why_te")} /></Field>
      </div>
      <div className="form-grid two">
        <div className="field"><span>Applies when…</span>
          <ConditionBuilder value={r.condition} onChange={(c) => setR({ ...r, condition: c })} emptyLabel="Applies to every business." /></div>
        <div className="field"><span>Already has it when…</span>
          <ConditionBuilder value={r.have_check} onChange={(c) => setR({ ...r, have_check: c })} emptyLabel="Always shown as missing (no profile field tells us)." /></div>
      </div>
      <div className="form-grid">
        <Field label="Documents"><input className="input" value={r.documents ?? ""} onChange={set("documents")} /></Field>
        <Field label="Time"><input className="input" value={r.time_estimate ?? ""} onChange={set("time_estimate")} /></Field>
        <Field label="Cost"><input className="input" value={r.cost_note ?? ""} onChange={set("cost_note")} /></Field>
        <Field label="Official link"><input className="input" placeholder="https://" value={r.official_link ?? ""} onChange={set("official_link")} /></Field>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="modal-actions">
        {r.id && <button className="btn ghost danger" onClick={remove}>Delete</button>}
        <span style={{ flex: 1 }} />
        <label className="check" style={{ alignItems: "center" }}><input type="checkbox" checked={r.active} onChange={(e) => setR({ ...r, active: e.target.checked })} /> Active</label>
        <button className="btn secondary" onClick={onClose}>Cancel</button><button className="btn" onClick={save}>Save requirement</button>
      </div>
    </Modal>
  );
}

function TopicDetail({ id, services }: { id: number; services: string[] }) {
  const [t, setT] = useState<Topic | null>(null);
  const [editTopic, setEditTopic] = useState(false);
  const [editRule, setEditRule] = useState<Rule | null>(null);
  const load = useCallback(() => { api<Topic>(`/admin/intents/${id}`).then(setT).catch(() => setT(null)); }, [id]);
  useEffect(() => { load(); }, [load]);
  if (!t) return <div className="muted">Loading…</div>;
  return (
    <div className="stack">
      <Link to="/admin/topics" className="small">← All topics</Link>
      <div className="page-head">
        <div>
          <h1>{t.title_en} {!t.active && <span className="tag grey">hidden</span>}</h1>
          <p className="muted small">{moduleName(t.module)} · <span className="mono">{t.code}</span> · expert service: {t.connect_service?.replace(/_/g, " ") ?? "none"}</p>
        </div>
        <button className="btn secondary" onClick={() => setEditTopic(true)}>Edit topic</button>
      </div>
      <div className="card">
        <h3>Keywords</h3>
        <div className="chips">{t.keywords.map((k) => <span key={k} className="tag">{k}</span>)}</div>
        <h3 style={{ marginTop: 12 }}>Sample questions</h3>
        <ul className="small" style={{ margin: 0 }}>{t.sample_questions.map((q) => <li key={q}>{q}</li>)}</ul>
      </div>
      <div className="page-head">
        <h2 style={{ margin: 0 }}>Requirements ({t.rules?.length ?? 0})</h2>
        <button className="btn" onClick={() => setEditRule({ ...EMPTY_RULE, step_order: ((t.rules?.length ?? 0) + 1) })}>+ Add requirement</button>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>#</th><th>Requirement</th><th>Applies when</th><th>Already has it when</th><th></th></tr></thead>
          <tbody>
            {t.rules?.map((r) => (
              <tr key={r.id} className={`clickable ${r.active ? "" : "dim"}`} onClick={() => setEditRule(r)}>
                <td>{r.step_order}</td>
                <td><b>{r.title_en}</b><div className="small muted mono">{r.item_code}</div></td>
                <td className="small">{describe(r.condition)}</td>
                <td className="small">{r.have_check ? describe(r.have_check) : <span className="muted">—</span>}</td>
                <td>{!r.active && <span className="tag grey">off</span>}</td>
              </tr>
            ))}
            {!t.rules?.length && <tr><td colSpan={5} className="muted">No requirements yet. Answers for this topic will show information only.</td></tr>}
          </tbody>
        </table>
      </div>
      {editTopic && <TopicForm topic={t} services={services} onClose={() => setEditTopic(false)} onSaved={() => { setEditTopic(false); load(); }} />}
      {editRule && <RuleForm rule={editRule} topicId={t.id!} onClose={() => setEditRule(null)} onSaved={() => { setEditRule(null); load(); }} />}
    </div>
  );
}

export default function Topics() {
  const { topicId } = useParams();
  const navigate = useNavigate();
  const [topics, setTopics] = useState<Topic[]>([]);
  const [services, setServices] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [module, setModule] = useState("");

  useEffect(() => {
    api<Topic[]>("/admin/intents").then(setTopics).catch(() => {});
    api<{ services: string[] }>("/admin/meta").then((m) => setServices(m.services)).catch(() => {});
  }, [topicId]);

  if (topicId) return <TopicDetail id={Number(topicId)} services={services} />;

  return (
    <div className="stack">
      <div className="page-head">
        <div><h1>Topics & rules</h1><p className="muted small">What the assistant understands, and what each business needs for it (screen A2).</p></div>
        <button className="btn" onClick={() => setCreating(true)}>+ New topic</button>
      </div>
      <div className="filters">
        <select className="input" value={module} onChange={(e) => setModule(e.target.value)}>
          <option value="">All modules</option>{MODULES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
        </select>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Topic</th><th>Module</th><th>Keywords</th><th>Requirements</th></tr></thead>
          <tbody>
            {topics.filter((t) => !module || t.module === module).map((t) => (
              <tr key={t.id} className={`clickable ${t.active ? "" : "dim"}`} onClick={() => navigate(`/admin/topics/${t.id}`)}>
                <td><b>{t.title_en}</b><div className="small muted">{t.title_te}</div></td>
                <td>{moduleName(t.module)}</td>
                <td className="small muted">{t.keywords.slice(0, 6).join(", ")}{t.keywords.length > 6 ? "…" : ""}</td>
                <td>{t.rule_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {creating && <TopicForm topic={EMPTY_TOPIC} services={services} onClose={() => setCreating(false)}
        onSaved={(t) => { setCreating(false); navigate(`/admin/topics/${t.id}`); }} />}
    </div>
  );
}
