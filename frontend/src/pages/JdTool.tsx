// SkillsPro – job description generator from role templates.
import { useEffect, useState } from "react";
import { api, downloadArtefact, type Artefact } from "../api";
import { useAuth } from "../auth";
import { useLang } from "../i18n";

type Role = { key: string; title: string; purpose: string; duties: string[]; skills: string[]; qualification: string };
type Jd = { role_key: string; title: string; purpose: string; duties: string; skills: string; qualification: string; openings: number;
  employment_type: string; work_hours: string; pay: string; location: string; contact: string };

const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

export default function JdTool() {
  const { t } = useLang();
  const { user } = useAuth();
  const [roles, setRoles] = useState<Role[]>([]);
  const [jd, setJd] = useState<Jd | null>(null);
  const [made, setMade] = useState<Artefact | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api<Role[]>("/artefacts/roles").then(setRoles).catch((e) => setError(e.message)); }, []);

  const pick = (r: Role) => setJd({
    role_key: r.key, title: r.title, purpose: r.purpose, duties: r.duties.join("\n"), skills: r.skills.join("\n"), qualification: r.qualification,
    openings: 1, employment_type: "Full-time", work_hours: "", pay: "", location: "", contact: user?.name ? `Contact ${user.name}` : "",
  });
  const set = (k: keyof Jd) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setJd(jd && { ...jd, [k]: k === "openings" ? Math.max(1, Number(e.target.value) || 1) : e.target.value });

  const generate = async () => {
    if (!jd) return;
    setError(null);
    try {
      const body = { ...jd, duties: lines(jd.duties), skills: lines(jd.skills), qualification: jd.qualification || null,
        work_hours: jd.work_hours || null, pay: jd.pay || null, location: jd.location || null, contact: jd.contact || null };
      setMade(await api<Artefact>("/artefacts/jd", { body }));
    } catch (e) { setError((e as Error).message); }
  };

  if (made) return (
    <div className="stack">
      <h1>{t("toolJd")}</h1>
      <div className="card stack">
        <div className="insight good">{t("jdReady")} – {made.title}</div>
        <div className="wizard-actions">
          <button className="btn secondary" onClick={() => setMade(null)}>{t("edit")}</button>
          <button className="btn" onClick={() => downloadArtefact(made.id).catch((e) => setError(e.message))}>{t("downloadPdf")}</button>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
    </div>
  );

  return (
    <div className="stack">
      <div><h1>{t("toolJd")}</h1><p className="muted small" style={{ margin: 0 }}>{t("jdIntro")}</p></div>
      <div className="chips">
        {roles.map((r) => (
          <button key={r.key} className={`chip ${jd?.role_key === r.key ? "on" : ""}`} onClick={() => pick(r)}>{r.key === "custom" ? t("otherRole") : r.title}</button>
        ))}
      </div>
      {jd && (
        <div className="card stack">
          <label className="field"><span>{t("jobTitle")}</span><input className="input" value={jd.title} onChange={set("title")} /></label>
          <label className="field"><span>{t("rolePurpose")}</span><textarea className="input" rows={2} value={jd.purpose} onChange={set("purpose")} /></label>
          <label className="field"><span>{t("duties")}</span><textarea className="input" rows={5} value={jd.duties} onChange={set("duties")} />
            <small className="muted">{t("onePerLine")}</small></label>
          <label className="field"><span>{t("skills")}</span><textarea className="input" rows={3} value={jd.skills} onChange={set("skills")} /></label>
          <div className="form-grid">
            <label className="field"><span>{t("qualification")}</span><input className="input" value={jd.qualification} onChange={set("qualification")} /></label>
            <label className="field"><span>{t("openings")}</span><input className="input" type="number" min={1} value={jd.openings} onChange={set("openings")} /></label>
            <label className="field"><span>{t("jobType")}</span>
              <select className="input" value={jd.employment_type} onChange={set("employment_type")}>
                <option>Full-time</option><option>Part-time</option><option>Contract</option><option>Apprentice</option></select></label>
            <label className="field"><span>{t("workHours")}</span><input className="input" placeholder="e.g. 9 am – 6 pm, Sunday off" value={jd.work_hours} onChange={set("work_hours")} /></label>
            <label className="field"><span>{t("pay")}</span><input className="input" placeholder="e.g. Rs. 12,000 per month" value={jd.pay} onChange={set("pay")} /></label>
            <label className="field"><span>{t("location")}</span><input className="input" value={jd.location} onChange={set("location")} /></label>
          </div>
          <label className="field"><span>{t("howToApply")}</span><input className="input" value={jd.contact} onChange={set("contact")} /></label>
          <div className="notice">{t("minWageNote")}</div>
          {error && <div className="error">{error}</div>}
          <button className="btn" onClick={generate}>{t("makeJd")}</button>
        </div>
      )}
    </div>
  );
}
