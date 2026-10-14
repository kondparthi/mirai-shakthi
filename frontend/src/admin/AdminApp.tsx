import { lazy, Suspense, useState } from "react";
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

// Phase 1 screens load when opened.
const Overview = lazy(() => import("./programme/Overview"));
const Entrepreneurs = lazy(() => import("./programme/Entrepreneurs"));
const EntrepreneurDetail = lazy(() => import("./programme/EntrepreneurDetail"));
const AssistedEnrol = lazy(() => import("./programme/AssistedEnrol"));
const Groups = lazy(() => import("./programme/Groups"));
const Import = lazy(() => import("./programme/Import"));
const Masters = lazy(() => import("./settings/Masters"));
const ReadinessFormula = lazy(() => import("./settings/ReadinessFormula"));
const StaffPage = lazy(() => import("./settings/Staff"));
const Audit = lazy(() => import("./settings/Audit"));
const DataRequests = lazy(() => import("./settings/DataRequests"));
const Batches = lazy(() => import("./training/Batches"));
const BatchDetail = lazy(() => import("./training/BatchDetail"));
const Courses = lazy(() => import("./training/Courses"));
const Partners = lazy(() => import("./training/Partners"));
const FollowUps = lazy(() => import("./training/FollowUps"));
const TrainingReports = lazy(() => import("./training/Reports"));
const ExternalQueue = lazy(() => import("./training/Reports").then((m) => ({ default: m.ExternalQueue })));

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
        <p className="muted">Staff portal – sign in</p>
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

// Menu by role (spec Section 3). Each entry: path, label, icon path, roles that see it.
type NavItem = [string, string, string, string[]];
const ALL_READ = ["admin", "programme_manager", "coordinator", "dpr_officer", "procurement", "mentor", "sector_expert", "federation_staff"];
const TRAIN_READ = [...ALL_READ, "trainer"];
const MANAGERS = ["admin", "programme_manager"];
const WRITE = ["admin", "programme_manager", "coordinator", "federation_staff"];
const AI = ["admin", "reviewer"];
const NAV: [string, NavItem[]][] = [
  ["Programme", [
    ["/admin/programme", "Overview", "M3 13h8V3H3zm0 8h8v-6H3zm10 0h8V11h-8zm0-18v6h8V3z", ALL_READ],
    ["/admin/entrepreneurs", "Entrepreneurs", "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-8 9a8 8 0 0 1 16 0", ALL_READ],
    ["/admin/groups", "Groups", "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm14 10v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8", ALL_READ],
    ["/admin/import", "Bulk import", "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12", WRITE],
  ]],
  ["Training", [
    ["/admin/training/batches", "Batches", "M22 10v6M2 10l10-5 10 5-10 5zM6 12v5c3 3 9 3 12 0v-5", TRAIN_READ],
    ["/admin/training/followups", "Follow-ups", "M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z", ["admin", "programme_manager", "coordinator", "mentor"]],
    ["/admin/training/uploaded", "Uploaded certificates", "M9 12l2 2 4-4M7.8 4.7a3.4 3.4 0 0 0 1.9-.8 3.4 3.4 0 0 1 4.4 0 3.4 3.4 0 0 0 1.9.8 3.4 3.4 0 0 1 3.1 3.1c.1.7.4 1.4.8 1.9a3.4 3.4 0 0 1 0 4.4 3.4 3.4 0 0 0-.8 1.9 3.4 3.4 0 0 1-3.1 3.1 3.4 3.4 0 0 0-1.9.8 3.4 3.4 0 0 1-4.4 0 3.4 3.4 0 0 0-1.9-.8 3.4 3.4 0 0 1-3.1-3.1 3.4 3.4 0 0 0-.8-1.9 3.4 3.4 0 0 1 0-4.4 3.4 3.4 0 0 0 .8-1.9 3.4 3.4 0 0 1 3.1-3.1z", ["admin", "programme_manager", "coordinator"]],
    ["/admin/training/courses", "Courses", "M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5zM4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5", MANAGERS],
    ["/admin/training/partners", "Training partners", "M3 21h18M5 21V7l7-4 7 4v14M9 9h1m-1 4h1m-1 4h1m4-8h1m-1 4h1m-1 4h1", MANAGERS],
    ["/admin/training/reports", "Training reports", "M12 20V10M18 20V4M6 20v-4", TRAIN_READ],
  ]],
  ["AI assistant", [
    ["/admin", "Assistant dashboard", "M22 12h-4l-3 9L9 3l-3 9H2", AI],
    ["/admin/review", "Answer review", "M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z", AI],
    ["/admin/knowledge", "Knowledge library", "M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5zM4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5", AI],
    ["/admin/topics", "Topics & rules", "M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9", AI],
    ["/admin/experts", "Experts", "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z", ["admin"]],
    ["/admin/requests", "Expert requests", "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z", AI],
    ["/admin/users", "App users", "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 0 0", AI],
  ]],
  ["Settings", [
    ["/admin/masters", "Master data", "M4 6h16M4 12h16M4 18h10", ["admin", "programme_manager"]],
    ["/admin/readiness", "Readiness formula", "M12 20V10M18 20V4M6 20v-4", ["admin", "programme_manager"]],
    ["/admin/staff", "Staff & access", "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z", ["admin"]],
    ["/admin/audit", "Audit log", "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zm0 0v6h6M9 13h6M9 17h6", ["admin", "programme_manager"]],
    ["/admin/data-requests", "Data requests", "M12 15v2m-6 4h12a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2zm10-10V7a4 4 0 0 0-8 0v4", ["admin"]],
  ]],
];
const ROLE_LABELS: Record<string, string> = {
  admin: "Super Admin", programme_manager: "Programme Manager", coordinator: "District Coordinator", trainer: "Trainer",
  dpr_officer: "DPR & Credit Officer", procurement: "Procurement Officer", mentor: "Mentor", sector_expert: "Sector Expert",
  federation_staff: "SHG Federation Staff", partner_viewer: "Partner Viewer", reviewer: "Content Reviewer",
};

const Loading = () => <div className="muted">Loading…</div>;

function NotYet() {
  return (
    <div className="card stack" style={{ maxWidth: 560 }}>
      <h1 style={{ margin: 0 }}>Welcome</h1>
      <p className="muted" style={{ margin: 0 }}>The screens for your role arrive in a later Phase 1 sprint. Your login is ready.</p>
    </div>
  );
}

export default function AdminApp() {
  const { user, signOut } = useAuth();
  if (!user || user.role === "msme") return <AdminLogin />;
  if (user.role === "expert") return <Navigate to="/expert" replace />;
  const can = (roles: string[]) => roles.includes(user.role);
  const sections = NAV.map(([title, items]) => [title, items.filter((i) => can(i[3]))] as const).filter(([, items]) => items.length);
  const home = sections[0]?.[1][0]?.[0] ?? "/admin/welcome";
  const route = (path: string, el: React.ReactNode) => {
    const item = NAV.flatMap(([, i]) => i).find((i) => i[0] === path);
    return item && !can(item[3]) ? <Navigate to={home} replace /> : <Suspense fallback={<Loading />}>{el}</Suspense>;
  };

  return (
    <div className="admin">
      <aside className="admin-side">
        <div className="admin-brand">MIRAI Shakthi<small>Staff portal</small></div>
        <nav>
          {sections.map(([title, items]) => (
            <div key={title} className="nav-group">
              <div className="nav-title">{title}</div>
              {items.map(([to, label, d]) => (
                <NavLink key={to} to={to} end={to === "/admin"}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
                  {label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="admin-user">
          <div>{user.name ?? "Staff"}</div>
          <small className="muted">{ROLE_LABELS[user.role] ?? user.role}</small>
          <button className="btn ghost small" onClick={signOut}>Sign out</button>
        </div>
      </aside>
      <main className="admin-main">
        <Routes>
          <Route path="/admin" element={can(AI) ? <Dashboard /> : <Navigate to={home} replace />} />
          <Route path="/admin/review" element={route("/admin/review", <Review />)} />
          <Route path="/admin/knowledge" element={route("/admin/knowledge", <Knowledge />)} />
          <Route path="/admin/topics" element={route("/admin/topics", <Topics />)} />
          <Route path="/admin/topics/:topicId" element={route("/admin/topics", <Topics />)} />
          <Route path="/admin/experts" element={route("/admin/experts", <Experts />)} />
          <Route path="/admin/requests" element={route("/admin/requests", <RequestsQueue />)} />
          <Route path="/admin/users" element={route("/admin/users", <Users />)} />
          <Route path="/admin/programme" element={route("/admin/programme", <Overview />)} />
          <Route path="/admin/entrepreneurs" element={route("/admin/entrepreneurs", <Entrepreneurs />)} />
          <Route path="/admin/entrepreneurs/new" element={route("/admin/import", <AssistedEnrol />)} />
          <Route path="/admin/entrepreneurs/:id" element={route("/admin/entrepreneurs", <EntrepreneurDetail />)} />
          <Route path="/admin/groups" element={route("/admin/groups", <Groups />)} />
          <Route path="/admin/import" element={route("/admin/import", <Import />)} />
          <Route path="/admin/masters" element={route("/admin/masters", <Masters />)} />
          <Route path="/admin/readiness" element={route("/admin/readiness", <ReadinessFormula />)} />
          <Route path="/admin/staff" element={route("/admin/staff", <StaffPage />)} />
          <Route path="/admin/audit" element={route("/admin/audit", <Audit />)} />
          <Route path="/admin/data-requests" element={route("/admin/data-requests", <DataRequests />)} />
          <Route path="/admin/training/batches" element={route("/admin/training/batches", <Batches />)} />
          <Route path="/admin/training/batches/:id" element={route("/admin/training/batches", <BatchDetail />)} />
          <Route path="/admin/training/followups" element={route("/admin/training/followups", <FollowUps />)} />
          <Route path="/admin/training/uploaded" element={route("/admin/training/uploaded", <ExternalQueue />)} />
          <Route path="/admin/training/courses" element={route("/admin/training/courses", <Courses />)} />
          <Route path="/admin/training/partners" element={route("/admin/training/partners", <Partners />)} />
          <Route path="/admin/training/reports" element={route("/admin/training/reports", <TrainingReports />)} />
          <Route path="/admin/welcome" element={<NotYet />} />
          <Route path="*" element={<Navigate to={home} replace />} />
        </Routes>
      </main>
    </div>
  );
}
