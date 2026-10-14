// Form 1.1 – Individual entrepreneur profile. Shared by self-enrolment (app, step by step, EN/TE) and staff
// (assisted enrolment and edits in the admin portal). Aadhaar and bank numbers are sent once and never shown again in full.
import { useState, type ReactNode } from "react";
import type { Entrepreneur } from "../api";
import type { Lang } from "../i18n";
import { useMaster, useMasterList } from "./masters";
import { mName, pt, type PKey } from "./programmeText";

export type EnrolBody = {
  full_name: string; gender: string; dob: string; social_category: string; education: string; occupation: string;
  district: string; mandal: string; village: string; context_tag: string; skills: string[]; interests: string[];
  investment_available: number; monthly_income: number; has_loans: boolean; emi_amount: number | null;
  aadhaar: string | null; pan: string | null; bank_account: string | null; ifsc: string | null; bank_name: string | null;
};

type F = Omit<EnrolBody, "investment_available" | "monthly_income" | "emi_amount" | "has_loans" | "aadhaar" | "pan" | "bank_account" | "ifsc" | "bank_name"> & {
  investment_available: string; monthly_income: string; emi_amount: string; has_loans: "" | "yes" | "no";
  aadhaar: string; pan: string; bank_account: string; ifsc: string; bank_name: string;
};

const fromInitial = (e?: Partial<Entrepreneur>): F => ({
  full_name: e?.full_name ?? "", gender: e?.gender ?? "", dob: e?.dob ?? "", social_category: e?.social_category ?? "",
  education: e?.education ?? "", occupation: e?.occupation ?? "", district: e?.district ?? "", mandal: e?.mandal ?? "",
  village: e?.village ?? "", context_tag: e?.context_tag ?? "", skills: e?.skills ?? [], interests: e?.interests ?? [],
  investment_available: e?.investment_available != null ? String(e.investment_available) : "",
  monthly_income: e?.monthly_income != null ? String(e.monthly_income) : "",
  has_loans: e?.has_loans == null ? "" : e.has_loans ? "yes" : "no", emi_amount: e?.emi_amount != null ? String(e.emi_amount) : "",
  aadhaar: "", pan: e?.pan ?? "", bank_account: "", ifsc: "", bank_name: e?.bank_name ?? "",
});

const STEPS: { key: PKey; fields: (keyof F)[] }[] = [
  { key: "stepAbout", fields: ["full_name", "gender", "dob", "social_category", "education", "occupation"] },
  { key: "stepPlace", fields: ["district", "mandal", "village", "context_tag"] },
  { key: "stepSkills", fields: ["skills", "interests"] },
  { key: "stepMoney", fields: ["investment_available", "monthly_income", "has_loans"] },
  { key: "stepIds", fields: [] },
];
const FIELD_LABEL: Partial<Record<keyof F, PKey>> = {
  full_name: "fullName", gender: "gender", dob: "dob", social_category: "socialCategory", education: "education", occupation: "occupation",
  district: "district", mandal: "mandal", village: "village", context_tag: "contextTag", skills: "skills", interests: "interests",
  investment_available: "investment", monthly_income: "income", has_loans: "hasLoans", emi_amount: "emi",
};

function Chips({ items, value, onChange, multi }: { items: [string, ReactNode][]; value: string | string[]; onChange: (v: string | string[]) => void; multi?: boolean }) {
  return (
    <div className="chips">
      {items.map(([code, label]) => {
        const on = multi ? (value as string[]).includes(code) : value === code;
        return (
          <button type="button" key={code} className={`chip ${on ? "on" : ""}`} aria-pressed={on}
            onClick={() => onChange(multi ? (on ? (value as string[]).filter((x) => x !== code) : [...(value as string[]), code]) : code)}>
            {label}
          </button>
        );
      })}
    </div>
  );
}

/** A select from a master list, with a "not in the list" option that turns into a text box (villages are still being loaded). */
function MasterSelect({ items, value, onChange, lang, allowOther, label, disabled, loaded = true }: {
  items: { code: string; name_en: string; name_te: string | null }[]; value: string; onChange: (v: string) => void; lang: Lang;
  allowOther?: boolean; label: string; disabled?: boolean; loaded?: boolean;
}) {
  const t = pt(lang);
  const known = !value || items.some((i) => i.code === value);
  const [other, setOther] = useState(false);
  // Free text when chosen, when the saved value is not in the list, or when the list is empty for this place.
  if (allowOther && loaded && (other || !known || (items.length === 0 && !disabled)))
    return (
      <div className="row-gap">
        <input className="input" style={{ flex: 1 }} aria-label={label} placeholder={t("typeName")} value={value} disabled={disabled}
          onChange={(e) => onChange(e.target.value)} />
        {items.length > 0 && <button type="button" className="btn ghost small" onClick={() => { setOther(false); onChange(""); }}>▾</button>}
      </div>
    );
  return (
    <select className="input" aria-label={label} value={value} disabled={disabled}
      onChange={(e) => (e.target.value === "__other" ? (setOther(true), onChange("")) : onChange(e.target.value))}>
      <option value="">—</option>
      {items.map((i) => <option key={i.code} value={i.code}>{mName(i, lang)}</option>)}
      {allowOther && <option value="__other">{t("notInList")}</option>}
    </select>
  );
}

export default function EnrolForm({ lang, initial, stepped = false, consent = false, submitLabel, onSubmit }: {
  lang: Lang; initial?: Partial<Entrepreneur>; stepped?: boolean; consent?: boolean; submitLabel?: string;
  onSubmit: (body: EnrolBody) => Promise<void>;
}) {
  const t = pt(lang);
  const [f, setF] = useState<F>(() => fromInitial(initial));
  const [step, setStep] = useState(0);
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof F>(k: K, v: F[K]) => setF((x) => ({ ...x, [k]: v }));

  const districts = useMaster("district");
  const [mandals, mandalsLoaded] = useMasterList("mandal", f.district, !!f.district);
  const isMandalCode = mandals.some((m) => m.code === f.mandal);
  const [villages, villagesLoaded] = useMasterList("village", f.mandal, isMandalCode);
  const social = useMaster("social_category");
  const education = useMaster("education");
  const occupation = useMaster("occupation");
  const skills = useMaster("skill");
  const sectors = useMaster("sector");
  const banks = useMaster("bank");

  const missingIn = (fields: (keyof F)[]) =>
    fields.filter((k) => (Array.isArray(f[k]) ? (f[k] as string[]).length === 0 : !String(f[k]).trim()))
      .concat(fields.includes("has_loans") && f.has_loans === "yes" && !f.emi_amount ? ["emi_amount"] : []);
  const check = (fields: (keyof F)[]) => {
    const miss = missingIn(fields);
    if (miss.length) {
      setError(t("required") + miss.map((k) => t(FIELD_LABEL[k] ?? "fullName")).join(", "));
      return false;
    }
    setError(null);
    return true;
  };

  const submit = async () => {
    if (!check(STEPS.flatMap((s) => s.fields))) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        full_name: f.full_name, gender: f.gender, dob: f.dob, social_category: f.social_category, education: f.education, occupation: f.occupation,
        district: f.district, mandal: f.mandal.trim(), village: f.village.trim(), context_tag: f.context_tag, skills: f.skills, interests: f.interests,
        investment_available: Number(f.investment_available), monthly_income: Number(f.monthly_income), has_loans: f.has_loans === "yes",
        emi_amount: f.has_loans === "yes" ? Number(f.emi_amount) : null,
        aadhaar: f.aadhaar.replace(/\D/g, "") || null, pan: f.pan.trim().toUpperCase() || null,
        bank_account: f.bank_account.replace(/\s/g, "") || null, ifsc: f.bank_account ? f.ifsc.trim().toUpperCase() || null : null,
        bank_name: f.bank_name || null,
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const num = (k: "investment_available" | "monthly_income" | "emi_amount", label: PKey) => (
    <label className="field"><span>{t(label)}</span>
      <input className="input" inputMode="numeric" value={f[k]} onChange={(e) => set(k, e.target.value.replace(/[^\d.]/g, ""))} /></label>
  );

  const sections: ReactNode[] = [
    <div className="stack" key="about">
      <label className="field"><span>{t("fullName")}</span>
        <input className="input" autoComplete="name" value={f.full_name} onChange={(e) => set("full_name", e.target.value)} /></label>
      <div className="field"><span>{t("gender")}</span>
        <Chips items={[["female", t("female")], ["male", t("male")], ["other", t("other")]]} value={f.gender} onChange={(v) => set("gender", v as string)} /></div>
      <label className="field"><span>{t("dob")}</span>
        <input className="input" type="date" value={f.dob} max={new Date().toISOString().slice(0, 10)} onChange={(e) => set("dob", e.target.value)} />
        <small className="muted">{t("dobHint")}</small></label>
      <label className="field"><span>{t("socialCategory")}</span>
        <MasterSelect items={social} value={f.social_category} onChange={(v) => set("social_category", v)} lang={lang} label={t("socialCategory")} /></label>
      <label className="field"><span>{t("education")}</span>
        <MasterSelect items={education} value={f.education} onChange={(v) => set("education", v)} lang={lang} label={t("education")} /></label>
      <label className="field"><span>{t("occupation")}</span>
        <MasterSelect items={occupation} value={f.occupation} onChange={(v) => set("occupation", v)} lang={lang} label={t("occupation")} /></label>
    </div>,
    <div className="stack" key="place">
      <label className="field"><span>{t("district")}</span>
        <MasterSelect items={districts} value={f.district} lang={lang} label={t("district")}
          onChange={(v) => {
            const tag = districts.find((d) => d.code === v)?.data?.context_tag as string | undefined;
            setF((x) => ({ ...x, district: v, mandal: "", village: "", context_tag: x.context_tag || tag || "" }));
          }} /></label>
      <label className="field"><span>{t("mandal")}</span>
        <MasterSelect key={`m-${f.district}`} items={mandals} value={f.mandal} allowOther disabled={!f.district} loaded={mandalsLoaded} lang={lang} label={t("mandal")}
          onChange={(v) => setF((x) => ({ ...x, mandal: v, village: "" }))} /></label>
      <label className="field"><span>{t("village")}</span>
        <MasterSelect key={`v-${f.mandal}`} items={villages} value={f.village} allowOther disabled={!f.mandal} loaded={villagesLoaded && mandalsLoaded} lang={lang} label={t("village")}
          onChange={(v) => {
            const tag = villages.find((d) => d.code === v)?.data?.context_tag as string | undefined;
            setF((x) => ({ ...x, village: v, context_tag: tag || x.context_tag }));
          }} /></label>
      <div className="field"><span>{t("contextTag")}</span>
        <Chips items={(["rural", "urban", "tribal", "coastal"] as const).map((c) => [c, t(c)])} value={f.context_tag} onChange={(v) => set("context_tag", v as string)} /></div>
    </div>,
    <div className="stack" key="skills">
      <div className="field"><span>{t("skills")}</span>
        <Chips multi items={skills.map((s) => [s.code, mName(s, lang)])} value={f.skills} onChange={(v) => set("skills", v as string[])} /></div>
      <div className="field"><span>{t("interests")}</span>
        <Chips multi value={f.interests} onChange={(v) => set("interests", v as string[])}
          items={sectors.map((s) => {
            const st = s.data?.activation as string | undefined;
            return [s.code, <>{mName(s, lang)}{st === "pilot" ? <small> · {t("pilot")}</small> : st === "catalogue" ? <small className="muted"> · {t("comingSoon")}</small> : null}</>];
          })} /></div>
    </div>,
    <div className="stack" key="money">
      {num("investment_available", "investment")}
      {num("monthly_income", "income")}
      <div className="field"><span>{t("hasLoans")}</span>
        <Chips items={[["yes", t("yes")], ["no", t("no")]]} value={f.has_loans} onChange={(v) => set("has_loans", v as "yes" | "no")} /></div>
      {f.has_loans === "yes" && num("emi_amount", "emi")}
    </div>,
    <div className="stack" key="ids">
      <p className="small muted" style={{ margin: 0 }}>{t("idsLater")}</p>
      <label className="field"><span>{t("aadhaar")}</span>
        <input className="input" inputMode="numeric" autoComplete="off" maxLength={14} placeholder="XXXX XXXX XXXX" value={f.aadhaar}
          onChange={(e) => set("aadhaar", e.target.value.replace(/[^\d ]/g, ""))} />
        <small className="muted">{initial?.aadhaar_masked ? `${t("aadhaarKept")}${initial.aadhaar_masked}. ${t("leaveBlank")}` : t("aadhaarHint")}</small></label>
      <label className="field"><span>{t("pan")}</span>
        <input className="input" autoComplete="off" maxLength={10} value={f.pan} onChange={(e) => set("pan", e.target.value.toUpperCase())} /></label>
      <label className="field"><span>{t("bankAccount")}</span>
        <input className="input" inputMode="numeric" autoComplete="off" maxLength={20} value={f.bank_account} onChange={(e) => set("bank_account", e.target.value.replace(/[^\d]/g, ""))} />
        <small className="muted">{initial?.bank_masked ? `${t("aadhaarKept")}${initial.bank_masked} (${initial.ifsc ?? ""}). ${t("leaveBlank")}` : t("bankHint")}</small></label>
      {f.bank_account && (
        <label className="field"><span>{t("ifsc")}</span>
          <input className="input" autoComplete="off" maxLength={11} placeholder="SBIN0001234" value={f.ifsc} onChange={(e) => set("ifsc", e.target.value.toUpperCase())} /></label>
      )}
      <label className="field"><span>{t("bank")}</span>
        <MasterSelect items={banks} value={f.bank_name} onChange={(v) => set("bank_name", v)} lang={lang} label={t("bank")} /></label>
      {consent && (
        <label className="check">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          <span>{t("consentEnrol")}</span>
        </label>
      )}
    </div>,
  ];

  const last = step === STEPS.length - 1;
  const saveBtn = (
    <button type="button" className="btn" disabled={busy || (consent && !agree)} onClick={submit}>{busy ? t("saving") : submitLabel ?? t("save")}</button>
  );

  if (!stepped)
    return (
      <div className="stack enrol-form">
        {sections.map((s, i) => (
          <section key={i} className="enrol-section">
            <h3>{t(STEPS[i].key)}</h3>
            {s}
          </section>
        ))}
        {error && <div className="error" role="alert">{error}</div>}
        <div>{saveBtn}</div>
      </div>
    );

  return (
    <div className="stack enrol-form">
      <ol className="enrol-steps" aria-label="Steps">
        {STEPS.map((s, i) => (
          <li key={s.key} className={i === step ? "on" : i < step ? "done" : ""} aria-current={i === step ? "step" : undefined}>
            <span>{i + 1}</span><small>{t(s.key)}</small>
          </li>
        ))}
      </ol>
      <section className="card">
        <h2 style={{ marginTop: 0 }}>{t(STEPS[step].key)}</h2>
        {sections[step]}
      </section>
      {error && <div className="error" role="alert">{error}</div>}
      <div className="row-between">
        {step > 0 ? <button type="button" className="btn secondary" onClick={() => { setError(null); setStep(step - 1); }}>{t("back")}</button> : <span />}
        {last ? saveBtn : (
          <button type="button" className="btn" onClick={() => { if (check(STEPS[step].fields)) { setStep(step + 1); window.scrollTo(0, 0); } }}>{t("next")}</button>
        )}
      </div>
    </div>
  );
}
