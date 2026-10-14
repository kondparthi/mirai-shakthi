// Public certificate check (no login): opened from the QR code on a MIRAI Shakthi certificate.
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import Logo from "../components/Logo";

type R = { valid: boolean; certificate_no?: string; name?: string; course?: string; course_te?: string | null; track?: string; start_date?: string;
  end_date?: string; issued_on?: string | null; district?: string | null };
const d = (s?: string | null) => (s ? new Date(s + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" }) : "—");

export default function Verify() {
  const { number = "" } = useParams();
  const loc = useLocation();
  const navigate = useNavigate();
  const [no, setNo] = useState(number);
  const [code, setCode] = useState(new URLSearchParams(loc.search).get("c") ?? "");
  const [r, setR] = useState<R | null>(null);
  const [busy, setBusy] = useState(false);
  const check = async (n = no, c = code) => {
    if (!n || !c) return;
    setBusy(true);
    try {
      setR(await api<R>(`/public/certificates/${encodeURIComponent(n.trim())}?c=${encodeURIComponent(c.trim())}`));
    } catch {
      setR({ valid: false });
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    if (number && code) check(number, code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="verify-page stack">
      <div style={{ display: "flex", justifyContent: "center" }}><Logo size={40} /></div>
      <h1 style={{ textAlign: "center", margin: 0 }}>Certificate check</h1>
      {r?.valid && (
        <div className="card stack" style={{ textAlign: "center" }}>
          <div className="verify-badge" style={{ background: "var(--ok)" }}>✓</div>
          <b style={{ color: "var(--ok)" }}>Genuine MIRAI Shakthi certificate</b>
          <div style={{ fontSize: 24, fontWeight: 700 }}>{r.name}</div>
          <div>completed <b>{r.course}</b>{r.course_te && <span lang="te"> ({r.course_te})</span>}</div>
          <div className="small muted">{r.track} · {d(r.start_date)} – {d(r.end_date)}{r.district ? ` · ${r.district}` : ""}</div>
          <div className="small">Certificate no. <b>{r.certificate_no}</b> · issued {d(r.issued_on)}</div>
        </div>
      )}
      {r && !r.valid && (
        <div className="card stack" style={{ textAlign: "center" }}>
          <div className="verify-badge" style={{ background: "var(--danger)" }}>!</div>
          <b>No certificate matches this number and code.</b>
          <span className="small muted">Check both and try again. If it still fails, the certificate may have been withdrawn – contact MIRAI.</span>
        </div>
      )}
      <form className="card stack" onSubmit={(e) => { e.preventDefault(); navigate(`/verify/${encodeURIComponent(no.trim())}?c=${encodeURIComponent(code.trim())}`, { replace: true }); check(); }}>
        <label className="field"><span>Certificate number</span><input className="input" placeholder="MS-CORE-2026-00012" value={no} onChange={(e) => setNo(e.target.value.toUpperCase())} /></label>
        <label className="field"><span>Check code (6 letters, printed with the QR)</span><input className="input" maxLength={8} value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} /></label>
        <button className="btn" disabled={busy || !no || !code}>Check</button>
      </form>
      <p className="small muted" style={{ textAlign: "center" }}><a href="#/">miraimsme.com</a></p>
    </div>
  );
}
