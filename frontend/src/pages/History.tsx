import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type SessionSummary } from "../api";
import { useLang } from "../i18n";

const MODULE_NAMES: Record<string, string> = {
  microfin: "MicroFin", marketkonnect: "MarketKonnect", launchpad: "Launch Pad / Export Ready", skillspro: "SkillsPro", handholding: "Handholding",
};

export default function History() {
  const { t } = useLang();
  const [items, setItems] = useState<SessionSummary[] | null>(null);

  useEffect(() => {
    api<SessionSummary[]>("/guidance/sessions").then(setItems).catch(() => setItems([]));
  }, []);

  if (!items) return <div className="muted">Loading…</div>;
  return (
    <div className="stack">
      <h1>{t("history")}</h1>
      {items.length === 0 && <p className="muted">{t("noHistory")}</p>}
      {items.map((s) => (
        <Link key={s.id} to={`/chat/${s.id}`} className="card history-item">
          <div style={{ fontWeight: 600 }}>{s.title}</div>
          <div className="small muted" style={{ marginTop: 4 }}>
            {s.module && <span className="tag" style={{ marginRight: 6 }}>{MODULE_NAMES[s.module] ?? s.module}</span>}
            {s.updated_at ? new Date(s.updated_at).toLocaleString() : ""}
          </div>
        </Link>
      ))}
    </div>
  );
}
