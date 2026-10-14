// Assisted enrolment by a Field Navigator: the entrepreneur receives an OTP and reads it out – that is their consent.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError, type Entrepreneur } from "../../api";
import EnrolForm, { type EnrolBody } from "../../components/EnrolForm";

type Dup = { id: number; full_name: string; mobile: string; district_name: string | null; village_name: string | null; reason: string };

export default function AssistedEnrol() {
  const navigate = useNavigate();
  const [mobile, setMobile] = useState("");
  const [sent, setSent] = useState<{ dev_code?: string } | null>(null);
  const [otp, setOtp] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dups, setDups] = useState<{ list: Dup[]; body: EnrolBody } | null>(null);

  const sendOtp = async () => {
    setBusy(true);
    setError(null);
    try {
      setSent(await api<{ dev_code?: string }>("/programme/enrol/otp", { body: { mobile } }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const enrol = async (body: EnrolBody, force = false) => {
    if (otp.length < 4) throw new Error("Enter the OTP the entrepreneur received");
    try {
      const e = await api<Entrepreneur>("/programme/entrepreneurs", { body: { mobile, otp, data: body, force } });
      navigate(`/admin/entrepreneurs/${e.id}?new=1`);
    } catch (err) {
      const d = (err as ApiError).detail as { duplicates?: Dup[] } | undefined;
      if (d?.duplicates) setDups({ list: d.duplicates, body });
      throw err;
    }
  };

  return (
    <div className="stack" style={{ maxWidth: 760 }}>
      <div><Link to="/admin/entrepreneurs" className="small">← Entrepreneurs</Link><h1>Enrol an entrepreneur</h1>
        <p className="muted small" style={{ margin: 0 }}>Assisted enrolment (Form 1.1). An OTP goes to the entrepreneur's phone; when they read it to you, they agree to join and to MIRAI keeping their details.</p></div>

      <div className="card stack">
        <h3 style={{ margin: 0 }}>1. Entrepreneur's mobile</h3>
        <div className="row-gap">
          <label className="field" style={{ flex: 1, minWidth: 200 }}><span>Mobile number</span>
            <input className="input" inputMode="numeric" maxLength={10} value={mobile} disabled={!!sent}
              onChange={(e) => setMobile(e.target.value.replace(/\D/g, ""))} /></label>
          {!sent ? <button className="btn" disabled={busy || mobile.length !== 10} onClick={sendOtp}>Send OTP</button>
            : <button className="btn ghost" onClick={() => { setSent(null); setOtp(""); }}>Change</button>}
        </div>
        {sent && (
          <>
            <label className="field"><span>OTP the entrepreneur received</span>
              <input className="input" inputMode="numeric" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))} /></label>
            <p className="small muted" style={{ margin: 0 }}>Before asking for the OTP, read out: “MIRAI will keep your details to train and support you. You can see them or ask for them to be deleted at any time.”
              {sent.dev_code && <> <b>Test mode OTP: {sent.dev_code}</b></>}</p>
          </>
        )}
        {error && <div className="error">{error}</div>}
      </div>

      {sent && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>2. Details</h3>
          <EnrolForm lang="en" submitLabel="Enrol" onSubmit={(b) => enrol(b)} />
        </div>
      )}

      {dups && (
        <div className="card stack dup-box" role="alert">
          <b>Possible duplicate</b>
          {dups.list.map((d) => (
            <div key={d.id} className="row-between small">
              <span><Link to={`/admin/entrepreneurs/${d.id}`}>{d.full_name}</Link> · {d.mobile} · {d.village_name}, {d.district_name}<div className="muted">{d.reason}</div></span>
            </div>
          ))}
          <div className="row-gap">
            <button className="btn secondary" onClick={() => setDups(null)}>Check details again</button>
            <button className="btn danger" onClick={() => enrol(dups.body, true).catch((e) => setError((e as Error).message))}>They are a different person – enrol anyway</button>
          </div>
        </div>
      )}
    </div>
  );
}
