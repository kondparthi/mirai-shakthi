import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type ModuleCard, type SessionSummary } from "../api";
import { useAuth } from "../auth";
import MicButton from "../components/MicButton";
import { useLang } from "../i18n";

export default function Home() {
  const { t, lang } = useLang();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [modules, setModules] = useState<ModuleCard[]>([]);
  const [recent, setRecent] = useState<SessionSummary | null>(null);
  const [selected, setSelected] = useState<ModuleCard | null>(null);
  const [q, setQ] = useState("");
  const [voiceMsg, setVoiceMsg] = useState<string | null>(null);

  useEffect(() => {
    api<ModuleCard[]>(`/guidance/modules?lang=${lang}`).then(setModules).catch(() => {});
  }, [lang]);
  useEffect(() => {
    api<SessionSummary[]>("/guidance/sessions").then((s) => setRecent(s[0] ?? null)).catch(() => {});
  }, []);

  const ask = (question: string, module?: string) => {
    if (question.trim().length < 3) return;
    navigate("/chat", { state: { question: question.trim(), module } });
  };

  const popular = selected ? selected.topics.map((tp) => (lang === "te" && tp.title_te) || tp.title) : modules.flatMap((m) => m.popular_questions.slice(0, 1));

  return (
    <div className="stack">
      <div>
        <h1>{user?.name ? `${t("namaste")}, ${user.name.split(" ")[0]}` : t("appName")}</h1>
        <p className="muted small" style={{ margin: 0 }}>{t("tagline")}</p>
      </div>

      <form className="askbox" onSubmit={(e) => { e.preventDefault(); ask(q, selected?.code); }}>
        <textarea className="input" rows={2} placeholder={t("askPlaceholder")} value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(q, selected?.code); } }} />
        <MicButton value={q} onChange={setQ} onError={setVoiceMsg} />
        <button className="btn" disabled={q.trim().length < 3}>{t("ask")}</button>
      </form>
      {voiceMsg && <div className="notice small" role="status">{voiceMsg}</div>}

      <div className="modules">
        {modules.map((m) => (
          <button key={m.code} className={`module ${m.code}`} onClick={() => setSelected(selected?.code === m.code ? null : m)}
            aria-pressed={selected?.code === m.code} style={selected && selected.code !== m.code ? { opacity: 0.55 } : undefined}>
            <b>{lang === "te" ? m.name_te : m.name}</b>
            <span>{lang === "te" && m.area_te ? m.area_te : m.area}</span>
          </button>
        ))}
      </div>

      {recent && (
        <Link to={`/chat/${recent.id}`} className="card history-item">
          <div className="small muted">{t("continue")}</div>
          <div style={{ fontWeight: 600, marginTop: 4 }}>{recent.title}</div>
        </Link>
      )}

      <div className="qlist">
        <h2>{selected ? (lang === "te" ? selected.name_te : selected.name) : t("popular")}</h2>
        {popular.map((pq) => (
          <button key={pq} onClick={() => ask(pq, selected?.code)}>{pq}</button>
        ))}
      </div>
    </div>
  );
}
