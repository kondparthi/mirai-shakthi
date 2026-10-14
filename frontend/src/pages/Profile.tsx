import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Option, type Profile, type ProfileOptions } from "../api";
import { useAuth } from "../auth";
import { useLang } from "../i18n";

const EMPTY: Profile = {
  owner_name: "", business_name: "", stage: "", business_type: "", sector: "", product: "", district: "", mandal: "",
  ownership: "", turnover_band: -1, employees: 0, registrations: [], channels: [], books_kept: "", has_loan: null, flags: [],
};

function Chips({ options, value, onChange, multi = false }: {
  options: Option[]; value: string | number | string[]; onChange: (v: never) => void; multi?: boolean;
}) {
  return (
    <div className="chips">
      {options.map(([v, label]) => {
        const on = multi ? (value as string[]).includes(v as string) : value === v;
        return (
          <button key={String(v)} type="button" className={`chip ${on ? "on" : ""}`} aria-pressed={on}
            onClick={() => {
              if (multi) {
                const arr = value as string[];
                onChange((on ? arr.filter((x) => x !== v) : [...arr, v]) as never);
              } else onChange(v as never);
            }}>
            {label}
          </button>
        );
      })}
    </div>
  );
}

export default function ProfilePage() {
  const { t, lang } = useLang();
  const { user, refresh, signOut } = useAuth();
  const navigate = useNavigate();
  const [opts, setOpts] = useState<ProfileOptions | null>(null);
  const [p, setP] = useState<Profile>(EMPTY);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api<ProfileOptions>(`/profile/options?lang=${lang}`).then(setOpts).catch((e) => setError(e.message));
  }, [lang]);
  useEffect(() => {
    api<{ profile: Profile | null }>("/profile").then((r) => r.profile && setP({ ...EMPTY, ...r.profile })).catch(() => {});
  }, []);

  const set = <K extends keyof Profile>(k: K) => (v: Profile[K]) => setP((old) => ({ ...old, [k]: v }));

  const cards = [
    { title: t("pcAbout"), valid: p.owner_name.trim().length >= 2 && p.stage && p.ownership },
    { title: t("pcWhat"), valid: p.business_type && p.sector && p.product.trim().length >= 2 },
    { title: t("pcWhere"), valid: !!p.district },
    { title: t("pcSize"), valid: p.turnover_band >= 0 && p.employees >= 0 && !!p.books_kept },
    { title: t("pcRegs"), valid: true },
  ];

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await api("/profile", { method: "PUT", body: { ...p, business_name: p.business_name || null, mandal: p.mandal || null } });
      await refresh();
      navigate("/");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  if (!opts) return <div className="muted">{error ?? "Loading…"}</div>;
  const last = step === cards.length - 1;

  return (
    <div>
      <h1>{user?.has_profile ? t("profile") : t("tellUs")}</h1>
      <p className="muted small">{t("profileIntro")}</p>
      <div className="progress" aria-hidden="true"><div style={{ width: `${((step + 1) / cards.length) * 100}%` }} /></div>
      <div className="card stack">
        <h2>{step + 1}. {cards[step].title}</h2>

        {step === 0 && (<>
          <label className="field"><span>{t("yourName")}</span>
            <input className="input" value={p.owner_name} onChange={(e) => set("owner_name")(e.target.value)} /></label>
          <label className="field"><span>{t("businessName")}</span>
            <input className="input" value={p.business_name ?? ""} onChange={(e) => set("business_name")(e.target.value)} /></label>
          <div className="field"><span>{t("stage")}</span><Chips options={opts.stage} value={p.stage} onChange={set("stage")} /></div>
          <div className="field"><span>{t("ownership")}</span><Chips options={opts.ownership} value={p.ownership} onChange={set("ownership")} /></div>
        </>)}

        {step === 1 && (<>
          <div className="field"><span>{t("businessType")}</span><Chips options={opts.business_type} value={p.business_type} onChange={set("business_type")} /></div>
          <div className="field"><span>{t("sector")}</span><Chips options={opts.sector.map((s) => [s, opts.labels?.[s] ?? s])} value={p.sector} onChange={set("sector")} /></div>
          <label className="field"><span>{t("mainProduct")}</span>
            <input className="input" placeholder={t("productHint")} value={p.product}
              onChange={(e) => set("product")(e.target.value)} /></label>
        </>)}

        {step === 2 && (<>
          <label className="field"><span>{t("district")}</span>
            <select className="input" value={p.district} onChange={(e) => set("district")(e.target.value)}>
              <option value="">{t("selectDistrict")}</option>
              {opts.districts.map((d) => <option key={d}>{d}</option>)}
            </select></label>
          <label className="field"><span>{t("mandal")}</span>
            <input className="input" value={p.mandal ?? ""} onChange={(e) => set("mandal")(e.target.value)} /></label>
        </>)}

        {step === 3 && (<>
          <div className="field"><span>{t("turnover")}</span><Chips options={opts.turnover_band} value={p.turnover_band} onChange={set("turnover_band")} /></div>
          <label className="field"><span>{t("peopleWorking")}</span>
            <input className="input" type="number" min={0} inputMode="numeric" value={p.employees}
              onChange={(e) => set("employees")(Math.max(0, Number(e.target.value) || 0))} /></label>
          <div className="field"><span>{t("keepAccounts")}</span><Chips options={opts.books_kept} value={p.books_kept} onChange={set("books_kept")} /></div>
          <div className="field"><span>{t("haveLoan")}</span>
            <Chips options={[["yes", t("yes")], ["no", t("no")]]} value={p.has_loan == null ? "" : p.has_loan ? "yes" : "no"}
              onChange={(v: string) => set("has_loan")(v === "yes")} /></div>
        </>)}

        {step === 4 && (<>
          <div className="field"><span>{t("regsHave")}</span>
            <Chips multi options={opts.registrations} value={p.registrations} onChange={set("registrations")} /></div>
          <div className="field"><span>{t("whereSell")}</span>
            <Chips multi options={opts.channels} value={p.channels} onChange={set("channels")} /></div>
          <div className="field"><span>{t("anyApply")}</span>
            <Chips multi options={opts.flags} value={p.flags} onChange={set("flags")} /></div>
        </>)}

        {error && <div className="error">{error}</div>}
        <div className="wizard-actions">
          {step > 0 && <button className="btn secondary" onClick={() => setStep(step - 1)}>{t("back")}</button>}
          {last ? (
            <button className="btn" disabled={saving} onClick={save}>{t("save")}</button>
          ) : (
            <button className="btn" disabled={!cards[step].valid} onClick={() => setStep(step + 1)}>{t("next")}</button>
          )}
        </div>
      </div>
      {user?.has_profile && (
        <button className="btn ghost" style={{ marginTop: 16 }} onClick={signOut}>{t("logout")}</button>
      )}
    </div>
  );
}
