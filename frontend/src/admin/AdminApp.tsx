import { lazy, Suspense, useState } from "react";
import {
  Activity, BadgeCheck, BadgeIndianRupee, BookOpen, Boxes, Factory, FileSpreadsheet, HandCoins, Megaphone, ShoppingCart, Store, Wrench, Building2, ChartColumn, Database, ExternalLink, GraduationCap, KeyRound, Landmark, LayoutDashboard, Library,
  ListChecks, Menu, MessagesSquare, PhoneCall, ScrollText, ShieldCheck, SlidersHorizontal, TriangleAlert, Upload, UserRound, Users as UsersIcon, UsersRound,
  type LucideIcon,
} from "lucide-react";
import { Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api, type User } from "../api";
import { useAuth } from "../auth";
import Logo from "../components/Logo";
import UserMenu from "../components/UserMenu";
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
const Dprs = lazy(() => import("./dpr/Dprs"));
const DprBuilder = lazy(() => import("./dpr/DprBuilder"));
const Applications = lazy(() => import("./dpr/Applications"));
const ApplicationDetail = lazy(() => import("./dpr/Applications").then((m) => ({ default: m.ApplicationDetail })));
const Schemes = lazy(() => import("./dpr/Schemes"));
const Models = lazy(() => import("./dpr/Models"));
const FinanceReports = lazy(() => import("./dpr/FinanceReports"));
const SetupReports = lazy(() => import("./setup/SetupReports"));
const Units = lazy(() => import("./setup/Units"));
const UnitDetail = lazy(() => import("./setup/UnitDetail"));
const PurchaseDetail = lazy(() => import("./setup/PurchaseDetail"));
const Suppliers = lazy(() => import("./setup/Suppliers"));
const SalesDashboard = lazy(() => import("./market/SalesDashboard"));
const Enquiries = lazy(() => import("./market/Enquiries"));
const Campaigns = lazy(() => import("./market/Campaigns"));
const UnitShop = lazy(() => import("./market/UnitShop"));

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
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 14 }}><Logo tone="light" size={46} /></div>
        <h1>Staff portal</h1>
        <p className="muted">Sign in with the email and password MIRAI gave you.</p>
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

// Menu by role (spec Section 3). Each entry: path, label, icon, roles that see it.
type NavItem = [string, string, LucideIcon, string[]];
const ALL_READ = ["admin", "programme_manager", "coordinator", "dpr_officer", "procurement", "mentor", "sector_expert", "federation_staff"];
const TRAIN_READ = [...ALL_READ, "trainer"];
const MANAGERS = ["admin", "programme_manager"];
const WRITE = ["admin", "programme_manager", "coordinator", "federation_staff"];
const AI = ["admin", "reviewer"];
const NAV: [string, NavItem[]][] = [
  ["Programme", [
    ["/admin/programme", "Overview", LayoutDashboard, ALL_READ],
    ["/admin/entrepreneurs", "Entrepreneurs", UserRound, ALL_READ],
    ["/admin/groups", "Groups", UsersRound, ALL_READ],
    ["/admin/import", "Bulk import", Upload, WRITE],
  ]],
  ["Training", [
    ["/admin/training/batches", "Batches", GraduationCap, TRAIN_READ],
    ["/admin/training/followups", "Follow-ups", PhoneCall, ["admin", "programme_manager", "coordinator", "mentor"]],
    ["/admin/training/uploaded", "Uploaded certificates", BadgeCheck, ["admin", "programme_manager", "coordinator"]],
    ["/admin/training/courses", "Courses", BookOpen, MANAGERS],
    ["/admin/training/partners", "Training partners", Building2, MANAGERS],
    ["/admin/training/reports", "Training reports", ChartColumn, TRAIN_READ],
  ]],
  ["DPR & finance", [
    ["/admin/finance", "Finance dashboard", BadgeIndianRupee, ALL_READ],
    ["/admin/finance/dprs", "DPRs", FileSpreadsheet, ALL_READ],
    ["/admin/finance/applications", "Loan applications", HandCoins, ALL_READ],
    ["/admin/finance/schemes", "Schemes", Landmark, ALL_READ],
    ["/admin/finance/models", "Enterprise models", Boxes, ALL_READ],
  ]],
  ["Enterprise set-up", [
    ["/admin/setup", "Set-up dashboard", Factory, ALL_READ],
    ["/admin/setup/units", "Units", Wrench, ALL_READ],
    ["/admin/setup/suppliers", "Suppliers", Store, ALL_READ],
  ]],
  ["Sales & marketing", [
    ["/admin/market", "Sales dashboard", ShoppingCart, ALL_READ],
    ["/admin/market/enquiries", "Buyer enquiries", MessagesSquare, ALL_READ],
    ["/admin/market/campaigns", "Campaigns", Megaphone, ALL_READ],
  ]],
  ["AI assistant", [
    ["/admin", "Assistant dashboard", Activity, AI],
    ["/admin/review", "Answer review", TriangleAlert, AI],
    ["/admin/knowledge", "Knowledge library", Library, AI],
    ["/admin/topics", "Topics & rules", ListChecks, AI],
    ["/admin/experts", "Experts", Building2, ["admin"]],
    ["/admin/requests", "Expert requests", MessagesSquare, AI],
    ["/admin/users", "App users", UsersIcon, AI],
  ]],
  ["Settings", [
    ["/admin/masters", "Master data", Database, ["admin", "programme_manager"]],
    ["/admin/readiness", "Readiness formula", SlidersHorizontal, ["admin", "programme_manager"]],
    ["/admin/staff", "Staff & access", ShieldCheck, ["admin"]],
    ["/admin/audit", "Audit log", ScrollText, ["admin", "programme_manager"]],
    ["/admin/data-requests", "Data requests", KeyRound, ["admin"]],
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
  const location = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  if (!user || user.role === "msme") return <AdminLogin />;
  if (user.role === "expert") return <Navigate to="/expert" replace />;
  if (user.role === "supplier") return <Navigate to="/supplier" replace />;
  const can = (roles: string[]) => roles.includes(user.role);
  const sections = NAV.map(([title, items]) => [title, items.filter((i) => can(i[3]))] as const).filter(([, items]) => items.length);
  const home = sections[0]?.[1][0]?.[0] ?? "/admin/welcome";
  const route = (path: string, el: React.ReactNode) => {
    const item = NAV.flatMap(([, i]) => i).find((i) => i[0] === path);
    return item && !can(item[3]) ? <Navigate to={home} replace /> : <Suspense fallback={<Loading />}>{el}</Suspense>;
  };

  const all = NAV.flatMap(([section, items]) => items.map((i) => ({ section, path: i[0], label: i[1] })));
  const here = all.filter((i) => location.pathname === i.path || location.pathname.startsWith(i.path + "/"))
    .sort((x, y) => y.path.length - x.path.length)[0];

  return (
    <div className={`admin ${navOpen ? "nav-open" : ""}`}>
      <aside className="admin-side" aria-label="Main menu">
        <div className="admin-brand"><Logo tone="light" size={38} /><small>Staff portal</small></div>
        <nav onClick={(e) => (e.target as HTMLElement).closest("a") && setNavOpen(false)}>
          {sections.map(([title, items]) => (
            <div key={title} className="nav-group">
              <div className="nav-title">{title}</div>
              {items.map(([to, label, Icon]) => (
                <NavLink key={to} to={to} end={["/admin", "/admin/finance", "/admin/setup", "/admin/market"].includes(to)}>
                  <Icon aria-hidden="true" strokeWidth={1.9} />
                  {label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="admin-side-foot">MIRAI Shakthi · Phase 1</div>
      </aside>
      <div className="side-scrim" onClick={() => setNavOpen(false)} />
      <div className="admin-body">
        <header className="admin-top">
          <button className="burger" aria-label="Open menu" onClick={() => setNavOpen(true)}><Menu /></button>
          <div className="crumb"><small>{here?.section ?? "Staff portal"}</small><b>{here?.label ?? "Welcome"}</b></div>
          <div className="spacer" />
          <UserMenu name={user.name ?? user.email ?? "Staff"} sub={ROLE_LABELS[user.role] ?? user.role}
            detail={`${user.email ?? ""} · ${ROLE_LABELS[user.role] ?? user.role}`} onSignOut={signOut}
            items={<a role="menuitem" href="#/" target="_blank" rel="noreferrer"><ExternalLink aria-hidden="true" />Open the public site</a>} />
        </header>
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
          <Route path="/admin/finance" element={route("/admin/finance", <FinanceReports />)} />
          <Route path="/admin/finance/dprs" element={route("/admin/finance/dprs", <Dprs />)} />
          <Route path="/admin/finance/dprs/:id" element={route("/admin/finance/dprs", <DprBuilder />)} />
          <Route path="/admin/finance/applications" element={route("/admin/finance/applications", <Applications />)} />
          <Route path="/admin/finance/applications/:id" element={route("/admin/finance/applications", <ApplicationDetail />)} />
          <Route path="/admin/finance/schemes" element={route("/admin/finance/schemes", <Schemes />)} />
          <Route path="/admin/finance/models" element={route("/admin/finance/models", <Models />)} />
          <Route path="/admin/setup" element={route("/admin/setup", <SetupReports />)} />
          <Route path="/admin/setup/units" element={route("/admin/setup/units", <Units />)} />
          <Route path="/admin/setup/units/:id" element={route("/admin/setup/units", <UnitDetail />)} />
          <Route path="/admin/setup/units/purchase/:id" element={route("/admin/setup/units", <PurchaseDetail />)} />
          <Route path="/admin/setup/suppliers" element={route("/admin/setup/suppliers", <Suppliers />)} />
          <Route path="/admin/market" element={route("/admin/market", <SalesDashboard />)} />
          <Route path="/admin/market/enquiries" element={route("/admin/market/enquiries", <Enquiries />)} />
          <Route path="/admin/market/campaigns" element={route("/admin/market/campaigns", <Campaigns />)} />
          <Route path="/admin/market/units/:id" element={route("/admin/market", <UnitShop />)} />
          <Route path="/admin/welcome" element={<NotYet />} />
          <Route path="*" element={<Navigate to={home} replace />} />
        </Routes>
      </main>
      </div>
    </div>
  );
}
