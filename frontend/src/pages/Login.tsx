import { useState } from "react";
import { api, type User } from "../api";
import { LangToggle } from "../App";
import { useAuth } from "../auth";
import { useLang } from "../i18n";

export default function Login() {
  const { t, lang } = useLang();
  const { signIn } = useAuth();
  const [mobile, setMobile] = useState("");
  const [code, setCode] = useState("");
  const [consent, setConsent] = useState(false);
  const [stage, setStage] = useState<"mobile" | "otp">("mobile");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const requestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const r = await api<{ dev_code?: string }>("/auth/otp/request", { body: { mobile } });
      setDevCode(r.dev_code ?? null);
      setStage("otp");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const verify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const r = await api<{ token: string; user: User }>("/auth/otp/verify", { body: { mobile, code, consent, language: lang } });
      signIn(r.token, r.user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login">
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
        <div style={{ background: "var(--green-800)", borderRadius: 999 }}>
          <LangToggle />
        </div>
      </div>
      <div className="hero">
        <h1>{t("appName")}</h1>
        <p className="muted">{t("tagline")}</p>
      </div>
      {stage === "mobile" ? (
        <form className="card stack" onSubmit={requestOtp}>
          <label className="field">
            <span>{t("mobile")}</span>
            <input className="input" inputMode="numeric" autoComplete="tel" maxLength={10} placeholder="98xxxxxxxx"
              value={mobile} onChange={(e) => setMobile(e.target.value.replace(/\D/g, ""))} />
          </label>
          {error && <div className="error">{error}</div>}
          <button className="btn block" disabled={busy || mobile.length !== 10}>{t("getOtp")}</button>
        </form>
      ) : (
        <form className="card stack" onSubmit={verify}>
          <label className="field">
            <span>{t("enterOtp")}</span>
            <input className="input otp-input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} autoFocus
              value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
          </label>
          {devCode && <div className="devcode">Development OTP: <b>{devCode}</b></div>}
          <label className="check">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>{t("consent")}</span>
          </label>
          {error && <div className="error">{error}</div>}
          <button className="btn block" disabled={busy || code.length !== 6}>{t("verify")}</button>
          <button type="button" className="btn ghost" onClick={() => { setStage("mobile"); setCode(""); setError(null); }}>
            {t("changeNumber")}
          </button>
        </form>
      )}
    </div>
  );
}
