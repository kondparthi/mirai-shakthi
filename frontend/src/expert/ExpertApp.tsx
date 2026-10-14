// Expert workspace (screen E1): accept, quote and update cases sent through Handholding.
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { api, openDownload, type ConnectRequest, type User } from "../api";
import { useAuth } from "../auth";
import { MessageBox, rupees, StatusSteps, StatusTag, Timeline, when } from "../components/Timeline";

type Me = { id: number; name: string; organisation: string | null; type: string; services: string[]; districts: string[];
  rating: number | null; response_hours: number; status: string; counts: Record<string, number> };

const CONTACT: Record<string, string> = { call: "Phone call", whatsapp: "WhatsApp", visit: "Office visit" };
const BUDGET: Record<string, string> = { free: "Free only", upto_2000: "Up to ₹2,000", "2000_10000": "₹2,000–10,000", above_10000: "Above ₹10,000" };

function ExpertLogin() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ token: string; user: User }>("/auth/staff/login", { body: { email, password } });
      signIn(r.token, r.user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="login">
      <div className="hero"><h1>MIRAI Shakthi</h1><p className="muted">Expert workspace – sign in</p></div>
      <form className="card stack" onSubmit={submit}>
        <label className="field"><span>Email</span>
          <input className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="field"><span>Password</span>
          <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <div className="error">{error}</div>}
        <button className="btn block" disabled={busy || !email || !password}>Sign in</button>
      </form>
      <p className="small muted" style={{ textAlign: "center", marginTop: 16 }}>Your login is created by the MIRAI team when your profile is approved.</p>
    </div>
  );
}

function CaseList({ me }: { me: Me | null }) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState("open");
  const [rows, setRows] = useState<ConnectRequest[] | null>(null);
  useEffect(() => {
    let live = true;
    setRows(null);
    api<ConnectRequest[]>(`/expert/requests${filter ? `?status=${filter}` : ""}`).then((r) => live && setRows(r)).catch(() => live && setRows([]));
    return () => { live = false; };
  }, [filter]);
  const c = me?.counts ?? {};
  return (
    <div className="stack">
      <div><h1>My cases</h1><p className="muted small">Cases MSMEs sent to you. Reply within {me?.response_hours ?? 48} hours – the client's mobile number is shown once you accept.</p></div>
      <div className="tiles">
        <div className={`tile ${c.sent ? "warn" : ""}`}><div className="tile-label">New – waiting for you</div><div className="tile-value">{c.sent ?? 0}</div></div>
        <div className="tile"><div className="tile-label">Quoted</div><div className="tile-value">{c.quoted ?? 0}</div></div>
        <div className="tile"><div className="tile-label">Accepted / in progress</div><div className="tile-value">{(c.accepted ?? 0) + (c.in_progress ?? 0)}</div></div>
        <div className="tile"><div className="tile-label">Completed</div><div className="tile-value">{c.done ?? 0}</div>{me?.rating ? <div className="tile-note">Rating ★ {me.rating}</div> : null}</div>
      </div>
      <div className="filters">
        <select className="input" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter cases">
          <option value="open">Open cases</option><option value="sent">New</option><option value="done">Completed</option><option value="">All cases</option>
        </select>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>#</th><th>Client</th><th>Service</th><th>Received</th><th>Status</th></tr></thead>
          <tbody>
            {rows === null && <tr><td colSpan={5} className="muted">Loading…</td></tr>}
            {rows?.length === 0 && <tr><td colSpan={5} className="muted">No cases here.</td></tr>}
            {rows?.map((r) => (
              <tr key={r.id} className="clickable" onClick={() => navigate(`/expert/cases/${r.id}`)}>
                <td>{r.id}</td>
                <td><b>{r.client?.business || r.client?.name || "MSME"}</b><div className="small muted">{r.client?.district}</div></td>
                <td>{r.service_label}</td>
                <td className="small">{when(r.created_at)}{r.status === "sent" && r.respond_by && <div className="muted">Reply by {when(r.respond_by)}</div>}</td>
                <td><StatusTag r={r} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CaseDetail() {
  const { caseId } = useParams();
  const [r, setR] = useState<ConnectRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"" | "decline" | "quote">("");
  const [text, setText] = useState("");
  const [amount, setAmount] = useState("");

  const load = useCallback(() => { api<ConnectRequest>(`/expert/requests/${caseId}`).then(setR).catch((e) => setError(e.message)); }, [caseId]);
  useEffect(() => { load(); }, [load]);

  const act = async (path: string, body: unknown = {}) => {
    setError(null);
    try {
      setR(await api<ConnectRequest>(`/expert/requests/${caseId}/${path}`, { body }));
      setMode("");
      setText("");
      setAmount("");
    } catch (e) { setError((e as Error).message); }
  };
  const download = async (aid: number) => {
    setError(null);
    try { openDownload((await api<{ url: string }>(`/expert/requests/${caseId}/documents/${aid}/link`, { method: "POST" })).url); }
    catch (e) { setError((e as Error).message); }
  };

  if (!r) return <div className="muted">{error ?? "Loading…"}</div>;
  const can = (a: string) => r.actions?.includes(a);
  const cl = r.client;
  const digits = cl?.mobile?.replace(/\D/g, "");

  return (
    <div className="stack">
      <Link to="/expert" className="small">← My cases</Link>
      <div className="page-head">
        <div><h1 style={{ marginBottom: 2 }}>Case #{r.id} · {r.service_label}</h1>
          <div className="small muted">Received {when(r.created_at)}{r.status === "sent" && r.respond_by ? ` · reply by ${when(r.respond_by)}` : ""}</div></div>
        <StatusTag r={r} />
      </div>
      <StatusSteps status={r.status} />

      <div className="grid-2">
        <div className="stack">
          <div className="card stack">
            <h2 style={{ margin: 0 }}>Client</h2>
            <div><b>{cl?.business || cl?.name || "MSME"}</b><div className="small muted">{cl?.business ? `${cl?.name} · ` : ""}{cl?.district} · prefers {cl?.language === "te" ? "Telugu" : "English"}</div></div>
            {cl?.mobile ? (
              <div className="chips">
                <a className="btn secondary" href={`tel:${cl.mobile}`}>Call {cl.mobile}</a>
                <a className="btn secondary" href={`https://wa.me/91${digits?.slice(-10)}`} target="_blank" rel="noreferrer">WhatsApp</a>
              </div>
            ) : <div className="notice small">The mobile number is shown after you accept the case.</div>}
            <div className="small">Preferred contact: <b>{CONTACT[r.preferred_contact ?? ""] ?? "—"}</b> · Budget: <b>{BUDGET[r.budget ?? ""] ?? "Not given"}</b></div>
            {cl?.profile && cl.profile.length > 0 && <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{cl.profile.map((p) => <li key={p}>{p}</li>)}</ul>}
          </div>
          <div className="card stack">
            <h2 style={{ margin: 0 }}>Case summary</h2>
            <pre className="summary-text">{r.summary}</pre>
            {r.shared_documents && r.shared_documents.length > 0 && (
              <div className="stack" style={{ gap: 6 }}>
                <b className="small">Shared documents</b>
                {r.shared_documents.map((d) => (
                  <button key={d.id} className="btn ghost small" style={{ justifyContent: "flex-start" }} onClick={() => download(d.id)}>⬇ {d.title} (PDF)</button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="stack">
          {(can("accept") || can("quote") || can("start") || can("complete") || can("decline")) && (
            <div className="card stack">
              <h2 style={{ margin: 0 }}>Next step</h2>
              <div className="chips">
                {can("accept") && <button className="btn" onClick={() => act("accept", { text: null })}>Accept case</button>}
                {can("quote") && <button className="btn secondary" onClick={() => setMode("quote")}>Send quote</button>}
                {can("start") && <button className="btn" onClick={() => act("status", { status: "in_progress" })}>Start work</button>}
                {can("complete") && <button className="btn" onClick={() => act("status", { status: "done" })}>Mark completed</button>}
                {can("decline") && <button className="btn ghost danger" onClick={() => setMode("decline")}>Decline</button>}
              </div>
              {mode === "quote" && (
                <div className="stack">
                  <label className="field"><span>Fee (₹)</span>
                    <input className="input" type="number" min={0} value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
                  <label className="field"><span>What is included</span>
                    <textarea className="input" rows={3} value={text} placeholder="e.g. GST registration filing, 2 follow-ups, done within 7 working days" onChange={(e) => setText(e.target.value)} /></label>
                  {amount && <div className="small muted">The client sees: <b>{rupees(Number(amount))}</b></div>}
                  <div className="chips"><button className="btn" disabled={!amount || text.trim().length < 5} onClick={() => act("quote", { amount: Number(amount), note: text.trim() })}>Send quote</button>
                    <button className="btn ghost" onClick={() => setMode("")}>Cancel</button></div>
                </div>
              )}
              {mode === "decline" && (
                <div className="stack">
                  <label className="field"><span>Reason (shown to the client and MIRAI)</span>
                    <textarea className="input" rows={2} value={text} onChange={(e) => setText(e.target.value)} /></label>
                  <div className="chips"><button className="btn danger" disabled={!text.trim()} onClick={() => act("decline", { text: text.trim() })}>Decline case</button>
                    <button className="btn ghost" onClick={() => setMode("")}>Cancel</button></div>
                </div>
              )}
            </div>
          )}
          {r.quote && <div className="card quote-card"><div className="small muted">Your latest quote</div><div className="quote-amount">{rupees(r.quote.amount)}</div>{r.quote.note && <p style={{ margin: 0 }}>{r.quote.note}</p>}</div>}
          {r.rating && <div className="insight good">Client rated {"★".repeat(r.rating.stars)}{r.rating.comment ? ` – ${r.rating.comment}` : ""}</div>}
          <div className="card stack">
            <h2 style={{ margin: 0 }}>Updates</h2>
            <Timeline updates={r.updates ?? []} me="expert" />
            {can("message") && <MessageBox placeholder="Message the client" onSend={(t) => act("message", { text: t })} />}
          </div>
          {error && <div className="error">{error}</div>}
        </div>
      </div>
    </div>
  );
}

export default function ExpertApp() {
  const { user, signOut } = useAuth();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (user?.role === "expert") api<Me>("/expert/me").then(setMe).catch((e) => setError(e.message));
  }, [user]);

  if (!user || user.role === "msme") return <ExpertLogin />;
  if (user.role !== "expert") return <Navigate to="/admin" replace />;

  return (
    <div className="admin">
      <aside className="admin-side">
        <div className="admin-brand">MIRAI Shakthi<small>Expert workspace</small></div>
        <nav>
          <NavLink to="/expert" end>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" /></svg>
            My cases
          </NavLink>
        </nav>
        <div className="admin-user">
          <div>{me?.name ?? user.name ?? "Expert"}</div>
          <small className="muted">{me?.organisation ?? "expert"}</small>
          <button className="btn ghost small" onClick={signOut}>Sign out</button>
        </div>
      </aside>
      <main className="admin-main">
        {error && <div className="error">{error}</div>}
        <Routes>
          <Route path="/expert" element={<CaseList me={me} />} />
          <Route path="/expert/cases/:caseId" element={<CaseDetail />} />
          <Route path="*" element={<Navigate to="/expert" replace />} />
        </Routes>
      </main>
    </div>
  );
}
