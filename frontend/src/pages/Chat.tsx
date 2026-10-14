import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api, type GuidanceResult, type SessionDetail } from "../api";
import GuidanceView from "../components/GuidanceView";
import MicButton from "../components/MicButton";
import { useLang } from "../i18n";

type Msg = { id?: number; role: "user" | "assistant"; content: string; payload?: GuidanceResult | null; rating?: number | null };

export default function Chat() {
  const { t, lang } = useLang();
  const { sessionId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [done, setDone] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [voiceMsg, setVoiceMsg] = useState<string | null>(null);
  const started = useRef(false);
  const bottom = useRef<HTMLDivElement>(null);
  const sid = sessionId ? Number(sessionId) : undefined;

  const send = async (question: string, module?: string, session?: number) => {
    setError(null);
    setBusy(true);
    setMessages((m) => [...m, { role: "user", content: question }]);
    try {
      const r = await api<GuidanceResult>("/guidance/ask", { body: { question, module, session_id: session, language: lang } });
      setMessages((m) => [...m, { id: r.message_id, role: "assistant", content: r.information?.answer ?? r.message ?? "", payload: r }]);
      if (!session && r.session_id) navigate(`/chat/${r.session_id}`, { replace: true, state: null });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // Start a new conversation from Home, or load an existing one.
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const st = location.state as { question?: string; module?: string } | null;
    if (!sid && st?.question) {
      send(st.question, st.module);
    } else if (sid) {
      api<SessionDetail>(`/guidance/sessions/${sid}`)
        .then((s) => {
          setMessages(s.messages.map((m) => ({ id: m.id, role: m.role, content: m.content, payload: m.payload, rating: m.rating })));
          setDone(new Set(s.gaps.filter((g) => g.status === "done").map((g) => g.code)));
        })
        .catch((e) => setError(e.message));
    } else navigate("/", { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const toggleDone = async (code: string, isDone: boolean) => {
    if (!sid) return;
    setDone((d) => {
      const n = new Set(d);
      if (isDone) n.add(code); else n.delete(code);
      return n;
    });
    await api(`/guidance/sessions/${sid}/gaps/${code}`, { method: "PATCH", body: { status: isDone ? "done" : "missing" } }).catch(() => {});
  };

  return (
    <div className="chat" style={{ paddingBottom: 72 }}>
      {messages.map((m, i) =>
        m.role === "user" ? (
          <div key={i} className="bubble-user">{m.content}</div>
        ) : m.payload ? (
          <GuidanceView key={i} result={m.payload} onAsk={busy ? undefined : (question) => send(question, undefined, sid)} sessionId={sid} messageId={m.id} rating={m.rating} doneCodes={done} onToggleDone={toggleDone} />
        ) : (
          <div key={i} className="card">{m.content}</div>
        ),
      )}
      {busy && (
        <div className="typing"><span className="dot" /><span className="dot" /><span className="dot" /> {t("thinking")}</div>
      )}
      {error && <div className="error">{error}</div>}
      <div ref={bottom} />

      {voiceMsg && <div className="notice small composer-note" role="status">{voiceMsg}</div>}
      <form className="composer" onSubmit={(e) => { e.preventDefault(); if (q.trim().length >= 3 && !busy) { send(q.trim(), undefined, sid); setQ(""); } }}>
        <div className="inner">
          <input className="input" placeholder={t("followUp")} value={q} onChange={(e) => setQ(e.target.value)} disabled={busy} />
          <MicButton value={q} onChange={setQ} onError={setVoiceMsg} disabled={busy} />
          <button className="btn" disabled={busy || q.trim().length < 3}>{t("ask")}</button>
        </div>
      </form>
    </div>
  );
}
