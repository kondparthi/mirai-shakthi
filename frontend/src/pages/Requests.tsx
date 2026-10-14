// Screen G10 – My requests, and one request's detail.
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type ConnectRequest } from "../api";
import { MessageBox, rupees, StatusSteps, StatusTag, Timeline, when } from "../components/Timeline";
import { useLang } from "../i18n";

export function RequestList() {
  const { t } = useLang();
  const [items, setItems] = useState<ConnectRequest[] | null>(null);
  useEffect(() => { api<ConnectRequest[]>("/connect/requests").then(setItems).catch(() => setItems([])); }, []);
  return (
    <div className="stack">
      <div><h1>{t("myRequests")}</h1><p className="muted small" style={{ margin: 0 }}>{t("requestsIntro")}</p></div>
      {items === null && <div className="muted">Loading…</div>}
      {items?.length === 0 && <div className="card muted">{t("noRequests")}</div>}
      {items?.map((r) => (
        <Link key={r.id} to={`/requests/${r.id}`} className="card history-item">
          <div className="row-between" style={{ padding: 0 }}>
            <b>{r.service_label}</b>
            <StatusTag r={{ ...r, overdue: false }} />
          </div>
          <div className="small muted" style={{ marginTop: 4 }}>
            {r.expert?.name} · {when(r.last_update ?? r.created_at)}
            {r.quote && r.status === "quoted" && <> · <b style={{ color: "var(--amber)" }}>{t("quote")} {rupees(r.quote.amount)}</b></>}
          </div>
        </Link>
      ))}
    </div>
  );
}

export function RequestDetail() {
  const { t } = useLang();
  const { requestId } = useParams();
  const [r, setR] = useState<ConnectRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stars, setStars] = useState(0);
  const [comment, setComment] = useState("");

  const load = useCallback(() => { api<ConnectRequest>(`/connect/requests/${requestId}`).then(setR).catch((e) => setError(e.message)); }, [requestId]);
  useEffect(() => { load(); }, [load]);

  const act = async (path: string, body?: unknown) => {
    setError(null);
    try { setR(await api<ConnectRequest>(`/connect/requests/${requestId}/${path}`, { method: "POST", body: body ?? {} })); }
    catch (e) { setError((e as Error).message); }
  };

  if (!r) return <div className="muted">{error ?? "Loading…"}</div>;
  const can = (a: string) => r.actions?.includes(a);

  return (
    <div className="stack">
      <Link to="/requests" className="small">← {t("myRequests")}</Link>
      <div>
        <h1 style={{ marginBottom: 2 }}>{r.service_label}</h1>
        <div className="small muted">{r.expert?.name}{r.expert?.organisation ? ` · ${r.expert.organisation}` : ""} · {t("replyIn")} {r.response_hours} {t("hours")}</div>
      </div>
      <StatusSteps status={r.status} />

      {r.status === "quoted" && r.quote && (
        <div className="card quote-card">
          <div className="small muted">{t("quoteFromExpert")}</div>
          <div className="quote-amount">{rupees(r.quote.amount)}</div>
          {r.quote.note && <p style={{ margin: "4px 0 12px" }}>{r.quote.note}</p>}
          <div className="wizard-actions" style={{ marginTop: 0 }}>
            <button className="btn secondary" onClick={() => act("quote", { accept: false })}>{t("declineQuote")}</button>
            <button className="btn" onClick={() => act("quote", { accept: true })}>{t("acceptQuote")}</button>
          </div>
        </div>
      )}

      {can("rate") && (
        <div className="card stack">
          <b>{t("rateExpert")}</b>
          <div className="stars" role="radiogroup" aria-label={t("rateExpert")}>
            {[1, 2, 3, 4, 5].map((n) => <button key={n} role="radio" aria-checked={stars === n} className={n <= stars ? "on" : ""} onClick={() => setStars(n)}>★</button>)}
          </div>
          <input className="input" placeholder={t("rateComment")} value={comment} onChange={(e) => setComment(e.target.value)} />
          <button className="btn" disabled={!stars} onClick={() => act("rate", { stars, comment: comment || null })}>{t("submitRating")}</button>
        </div>
      )}
      {r.rating && <div className="insight good">{t("youRated")} {"★".repeat(r.rating.stars)}{r.rating.comment ? ` – ${r.rating.comment}` : ""}</div>}

      <div className="card stack">
        <h2 style={{ margin: 0 }}>{t("updates")}</h2>
        <Timeline updates={r.updates ?? []} me="msme" />
        {can("message") && <MessageBox placeholder={t("messageExpert")} onSend={(text) => act("message", { text })} />}
      </div>

      <details className="card">
        <summary><b>{t("whatYouSent")}</b></summary>
        <pre className="summary-text">{r.summary}</pre>
        {r.shared_documents && r.shared_documents.length > 0 && <div className="small muted">{t("sharedDocs")}: {r.shared_documents.map((d) => d.title).join(", ")}</div>}
      </details>

      {error && <div className="error">{error}</div>}
      {can("cancel") && <button className="btn ghost danger" onClick={() => confirm(t("cancelConfirm")) && act("cancel")}>{t("cancelRequest")}</button>}
    </div>
  );
}
