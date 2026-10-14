import { useState } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { api, type User } from "../api";
import { useAuth } from "../auth";
import Dashboard from "./Dashboard";
import Experts from "./Experts";
import RequestsQueue from "./Requests";
import Knowledge from "./Knowledge";
import Review from "./Review";
import Topics from "./Topics";
import Users from "./Users";

function AdminLogin() {
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
      <div className="hero">
        <h1>MIRAI Shakthi</h1>
        <p className="muted">Admin portal – staff sign in</p>
      </div>
      <form className="card stack" onSubmit={submit}>
        <label className="field"><span>Email</span>
          <input className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="field"><span>Password</span>
          <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <div className="error">{error}</div>}
        <button className="btn block" disabled={busy || !email || !password}>Sign in</button>
      </form>
      <p className="small muted" style={{ textAlign: "center", marginTop: 16 }}>
        MSME users sign in from the <a href="#/">main app</a>.
      </p>
    </div>
  );
}

const NAV: [string, string, string][] = [
  ["/admin", "Dashboard", "M3 13h8V3H3zm0 8h8v-6H3zm10 0h8V11h-8zm0-18v6h8V3z"],
  ["/admin/review", "Answer review", "M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"],
  ["/admin/knowledge", "Knowledge library", "M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5zM4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"],
  ["/admin/topics", "Topics & rules", "M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9"],
  ["/admin/experts", "Experts", "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm14 10v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"],
  ["/admin/requests", "Expert requests", "M22 12h-4l-3 9L9 3l-3 9H2"],
  ["/admin/users", "MSME users", "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-8 9a8 8 0 0 1 16 0"],
];

export default function AdminApp() {
  const { user, signOut } = useAuth();
  if (!user || user.role === "msme") return <AdminLogin />;
  if (user.role === "expert") return <Navigate to="/expert" replace />;

  return (
    <div className="admin">
      <aside className="admin-side">
        <div className="admin-brand">MIRAI Shakthi<small>Admin portal</small></div>
        <nav>
          {NAV.map(([to, label, d]) => (
            <NavLink key={to} to={to} end={to === "/admin"}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="admin-user">
          <div>{user.name ?? "Staff"}</div>
          <small className="muted">{user.role}</small>
          <button className="btn ghost small" onClick={signOut}>Sign out</button>
        </div>
      </aside>
      <main className="admin-main">
        <Routes>
          <Route path="/admin" element={<Dashboard />} />
          <Route path="/admin/review" element={<Review />} />
          <Route path="/admin/knowledge" element={<Knowledge />} />
          <Route path="/admin/topics" element={<Topics />} />
          <Route path="/admin/topics/:topicId" element={<Topics />} />
          <Route path="/admin/experts" element={<Experts />} />
          <Route path="/admin/requests" element={<RequestsQueue />} />
          <Route path="/admin/users" element={<Users />} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </main>
    </div>
  );
}
