import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, downloadArtefact, type ArtefactSummary } from "../api";
import { useLang } from "../i18n";

const KIND: Record<string, { label: string; cls: string }> = {
  roadmap: { label: "Roadmap", cls: "launchpad" },
  checklist: { label: "Checklist", cls: "launchpad" },
  cashflow: { label: "MicroFin", cls: "microfin" },
  jd: { label: "SkillsPro", cls: "skillspro" },
};

export default function Documents() {
  const { t } = useLang();
  const [items, setItems] = useState<ArtefactSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api<ArtefactSummary[]>("/artefacts").then(setItems).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const download = async (id: number) => {
    setError(null);
    try { await downloadArtefact(id); } catch (e) { setError((e as Error).message); }
  };
  const remove = async (a: ArtefactSummary) => {
    if (!confirm(`${t("deleteDoc")} “${a.title}”?`)) return;
    await api(`/artefacts/${a.id}`, { method: "DELETE" }).catch(() => {});
    load();
  };

  return (
    <div className="stack">
      <div><h1>{t("documents")}</h1><p className="muted small" style={{ margin: 0 }}>{t("documentsIntro")}</p></div>

      <div className="tools">
        <Link to="/tools/cashflow" className="tool microfin">
          <b>{t("toolCashflow")}</b><span>{t("toolCashflowDesc")}</span>
        </Link>
        <Link to="/tools/jd" className="tool skillspro">
          <b>{t("toolJd")}</b><span>{t("toolJdDesc")}</span>
        </Link>
      </div>
      <p className="small muted" style={{ margin: 0 }}>{t("roadmapHint")}</p>

      {error && <div className="error">{error}</div>}
      <h2 style={{ marginTop: 8 }}>{t("myDocuments")}</h2>
      {items === null && <div className="muted">Loading…</div>}
      {items?.length === 0 && <p className="muted">{t("noDocuments")}</p>}
      {items?.map((a) => (
        <div key={a.id} className="card doc-row">
          <span className={`doc-kind ${KIND[a.kind]?.cls}`}>{KIND[a.kind]?.label ?? a.kind}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="doc-title">{a.title}</div>
            <div className="small muted">{a.created_at ? new Date(a.created_at).toLocaleString() : ""}</div>
          </div>
          <button className="btn secondary small" onClick={() => download(a.id)}>PDF ↓</button>
          <button className="btn ghost small" onClick={() => remove(a)} aria-label={`${t("deleteDoc")} ${a.title}`}>✕</button>
        </div>
      ))}
    </div>
  );
}
