import { lazy, Suspense, useEffect } from "react";
import { Navigate, NavLink, Route, Routes, useLocation, useParams } from "react-router-dom";
import { useAuth } from "./auth";
import { GraduationCap, Landmark, ShieldCheck, Sprout, UserRound } from "lucide-react";
import Logo from "./components/Logo";
import UserMenu from "./components/UserMenu";
import { useLang } from "./i18n";
import Chat from "./pages/Chat";
import Home from "./pages/Home";
import Login from "./pages/Login";

// Screens most users open rarely are loaded only when opened, so the app starts faster on low-end phones (Sprint 5).
const AdminApp = lazy(() => import("./admin/AdminApp"));
const ExpertApp = lazy(() => import("./expert/ExpertApp"));
const CashflowTool = lazy(() => import("./pages/CashflowTool"));
const Documents = lazy(() => import("./pages/Documents"));
const History = lazy(() => import("./pages/History"));
const JdTool = lazy(() => import("./pages/JdTool"));
const ProfilePage = lazy(() => import("./pages/Profile"));
const Landing = lazy(() => import("./pages/Landing"));
const Programme = lazy(() => import("./pages/Programme"));
const MyData = lazy(() => import("./pages/MyData"));
const Training = lazy(() => import("./pages/Training"));
const Checkin = lazy(() => import("./pages/Training").then((m) => ({ default: m.Checkin })));
const Verify = lazy(() => import("./pages/Verify"));
const BusinessPlan = lazy(() => import("./pages/BusinessPlan"));

function CheckinRoute() {
  const { token = "" } = useParams();
  return <Checkin token={token} />;
}
const RequestList = lazy(() => import("./pages/Requests").then((m) => ({ default: m.RequestList })));
const RequestDetail = lazy(() => import("./pages/Requests").then((m) => ({ default: m.RequestDetail })));

const Loading = () => <div className="muted" style={{ padding: 16 }} aria-busy="true">Loading…</div>;

const Icon = ({ d }: { d: string }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={d} />
  </svg>
);

export function LangToggle() {
  const { lang, setLang } = useLang();
  return (
    <div className="lang-toggle" role="group" aria-label="Language">
      <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>EN</button>
      <button className={lang === "te" ? "on" : ""} onClick={() => setLang("te")}>తె</button>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const { t, lang } = useLang();
  const { user, signOut } = useAuth();
  const name = user?.name || user?.mobile || "MSME";
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <Logo tone="light" size={32} />
        </div>
        <div className="spacer" />
        <LangToggle />
        <UserMenu name={name} detail={user?.name && user?.mobile ? `+91 ${user.mobile}` : undefined} onSignOut={signOut} signOutLabel={t("logout")}
          items={<>
            <NavLink role="menuitem" to="/profile"><UserRound aria-hidden="true" />{t("profile")}</NavLink>
            <NavLink role="menuitem" to="/programme"><Sprout aria-hidden="true" />{t("programmeCardTitle")}</NavLink>
            <NavLink role="menuitem" to="/training"><GraduationCap aria-hidden="true" />{lang === "te" ? "నా శిక్షణ" : "My training"}</NavLink>
            <NavLink role="menuitem" to="/business-plan"><Landmark aria-hidden="true" />{lang === "te" ? "వ్యాపార ప్రణాళిక & రుణం" : "Business plan & loan"}</NavLink>
            <NavLink role="menuitem" to="/my-data"><ShieldCheck aria-hidden="true" />{t("myDataLink")}</NavLink>
          </>} />
      </header>
      <main className="page">{children}</main>
      <nav className="bottomnav">
        <div className="inner">
          <NavLink to="/" end>
            <Icon d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />
            {t("home")}
          </NavLink>
          <NavLink to="/history">
            <Icon d="M12 8v4l3 2M3 12a9 9 0 1 0 3-6.7M3 4v4h4" />
            {t("history")}
          </NavLink>
          <NavLink to="/documents">
            <Icon d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zm0 0v6h6M9 13h6M9 17h6" />
            {t("documents")}
          </NavLink>
          <NavLink to="/requests">
            <Icon d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm14 10v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" />
            {t("requests")}
          </NavLink>
          <NavLink to="/profile">
            <Icon d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-8 9a8 8 0 0 1 16 0" />
            {t("profile")}
          </NavLink>
        </div>
      </nav>
    </div>
  );
}

export default function App() {
  const { user, loading } = useAuth();
  const { lang } = useLang();
  const location = useLocation();

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  // Public certificate check (QR on certificates) – no login needed.
  if (location.pathname.startsWith("/verify")) return (
    <Suspense fallback={<Loading />}><Routes><Route path="/verify/:number?" element={<Verify />} /></Routes></Suspense>
  );
  if (loading) return <div className="login muted">Loading…</div>;
  // Admin portal lives at #/admin and has its own staff login.
  if (location.pathname.startsWith("/admin")) return <Suspense fallback={<Loading />}><AdminApp /></Suspense>;
  // Expert workspace lives at #/expert and uses the same staff login.
  if (location.pathname.startsWith("/expert")) return <Suspense fallback={<Loading />}><ExpertApp /></Suspense>;
  // Visitors see the landing page; Register / Log in open the mobile + OTP screen at #/login.
  // A training check-in QR opened while logged out: log in first, then the check-in completes on the same address.
  if (!user) return location.pathname.startsWith("/login") || location.pathname.startsWith("/checkin") ? <Login /> : <Suspense fallback={<Loading />}><Landing /></Suspense>;
  if (user.role === "expert") return <Navigate to="/expert" replace />;
  if (user.role !== "msme") return <Navigate to="/admin" replace />;
  // The business profile is needed for guidance; the programme enrolment has its own form, so it is reachable without it.
  const noProfileOk = ["/profile", "/programme", "/my-data", "/training", "/checkin", "/business-plan"].some((p) => location.pathname.startsWith(p));
  if (!user.has_profile && !noProfileOk) return <Navigate to="/profile" replace />;

  return (
    <Shell>
      <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/chat/:sessionId" element={<Chat />} />
        <Route path="/history" element={<History />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/tools/cashflow" element={<CashflowTool />} />
        <Route path="/tools/jd" element={<JdTool />} />
        <Route path="/requests" element={<RequestList />} />
        <Route path="/requests/:requestId" element={<RequestDetail />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/programme" element={<Programme />} />
        <Route path="/my-data" element={<MyData />} />
        <Route path="/training" element={<Training />} />
        <Route path="/business-plan" element={<BusinessPlan />} />
        <Route path="/checkin/:token" element={<CheckinRoute />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </Shell>
  );
}
