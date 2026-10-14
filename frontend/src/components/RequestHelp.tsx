// Form G-6 – send a case to an expert, with an editable summary and explicit consent.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, SERVICE_LABELS, type ConnectRequest } from "../api";
import { useLang } from "../i18n";

type Draft = {
  service: string; summary: string; shared_with_expert: string[];
  artefacts: { id: number; kind: string; title: string; from_this_conversation: boolean }[];
  expert: { id: number; name: string; organisation: string | null; services: string[]; fee_note: string | null; response_hours: number };
};

export default function RequestHelp({ expertId, sessionId, onClose }: { expertId: number; sessionId?: number; onClose: () => void }) {
  const { t } = useLang();
  const navigate = useNavigate();
  const [d, setD] = useState<Draft | null>(null);
  const [service, setService] = useState("");
  const [summary, setSummary] = useState("");
  const [docs, setDocs] = useState<number[]>([]);
  const [contact, setContact] = useState("call");
  const [budget, setBudget] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Draft>(`/connect/draft?expert_id=${expertId}${sessionId ? `&session_id=${sessionId}` : ""}`)
      .then((x) => { setD(x); setService(x.service); setSummary(x.summary); setDocs(x.artefacts.filter((a) => a.from_this_conversation).map((a) => a.id)); })
      .catch((e) => setError(e.message));
  }, [expertId, sessionId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api<ConnectRequest>("/connect/requests", { body: { expert_id: expertId, session_id: sessionId ?? null, service, summary,
        preferred_contact: contact, budget, artefact_ids: docs, consent } });
      navigate(`/requests/${r.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const chip = (on: boolean, label: string, onClick: () => void) => (
    <button type="button" key={label} className={`chip ${on ? "on" : ""}`} aria-pressed={on} onClick={onClick}>{label}</button>
  );

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={t("requestHelp")}>
        <div className="modal-head"><h2>{t("requestHelp")}</h2><button className="btn ghost" onClick={onClose} aria-label="Close">✕</button></div>
        <div className="modal-body">
          {!d && !error && <div className="muted">Loading…</div>}
          {d && (<>
            <div className="expert" style={{ borderTop: 0, padding: 0 }}>
              <div className="avatar">{d.expert.name.replace(/^Sample /, "").slice(0, 1)}</div>
              <div><div style={{ fontWeight: 600 }}>{d.expert.name}</div>
                <div className="small muted">{d.expert.organisation} · {d.expert.fee_note} · {t("replyIn")} {d.expert.response_hours} {t("hours")}</div></div>
            </div>
            <label className="field"><span>{t("serviceNeeded")}</span>
              <select className="input" value={service} onChange={(e) => setService(e.target.value)}>
                {d.expert.services.map((s) => <option key={s} value={s}>{SERVICE_LABELS[s] ?? s}</option>)}
              </select></label>
            <label className="field"><span>{t("caseSummary")}</span>
              <textarea className="input" rows={7} value={summary} onChange={(e) => setSummary(e.target.value)} />
              <small className="muted">{t("caseSummaryHint")}</small></label>
            {d.artefacts.length > 0 && (
              <div className="field"><span>{t("shareDocuments")}</span>
                {d.artefacts.map((a) => (
                  <label key={a.id} className="check" style={{ marginTop: 6 }}>
                    <input type="checkbox" checked={docs.includes(a.id)} onChange={(e) => setDocs(e.target.checked ? [...docs, a.id] : docs.filter((x) => x !== a.id))} />
                    <span>{a.title}</span>
                  </label>
                ))}
              </div>
            )}
            <div className="field"><span>{t("preferredContact")}</span>
              <div className="chips">{[["call", t("call")], ["whatsapp", "WhatsApp"], ["visit", t("visit")]].map(([v, l]) => chip(contact === v, l, () => setContact(v)))}</div></div>
            <div className="field"><span>{t("budget")}</span>
              <div className="chips">{[["free", t("free")], ["upto_2000", "≤ ₹2,000"], ["2000_10000", "₹2,000–10,000"], ["above_10000", "> ₹10,000"]]
                .map(([v, l]) => chip(budget === v, l, () => setBudget(budget === v ? null : v)))}</div></div>
            <div className="notice">
              <b>{t("whatIsShared")}</b>
              <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{d.shared_with_expert.map((x) => <li key={x}>{x}</li>)}</ul>
            </div>
            <label className="check"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} /><span>{t("shareConsent")}</span></label>
          </>)}
          {error && <div className="error">{error}</div>}
          <div className="modal-actions"><span style={{ flex: 1 }} />
            <button className="btn secondary" onClick={onClose}>{t("back")}</button>
            <button className="btn" disabled={!d || !consent || busy || summary.trim().length < 20} onClick={send}>{t("sendRequest")}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
