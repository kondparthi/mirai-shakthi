// DPDP Act – see / download my data, ask for it to be deleted.
import { useEffect, useState } from "react";
import { api, saveBlob } from "../api";
import { pt } from "../components/programmeText";
import { useLang } from "../i18n";

type Req = { id: number; kind: string; status: "open" | "done" | "rejected"; reason: string | null; resolution: string | null; at: string | null };

export default function MyData() {
  const { lang } = useLang();
  const t = pt(lang);
  const [reqs, setReqs] = useState<Req[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => api<Req[]>("/enrol/me/data-requests").then(setReqs).catch(() => {});
  useEffect(() => {
    load();
  }, []);

  const download = async () => {
    setBusy(true);
    try {
      const data = await api("/enrol/me/export");
      saveBlob(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }), "mirai-my-data.json");
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const askDelete = async () => {
    if (!window.confirm(t("deleteConfirm"))) return;
    setBusy(true);
    setMsg(null);
    try {
      await api("/enrol/me/data-request", { body: { kind: "delete", reason: reason || null } });
      setReason("");
      load();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const openDelete = reqs.some((r) => r.kind === "delete" && r.status === "open");

  return (
    <div className="stack">
      <h1 style={{ margin: 0 }}>{t("myData")}</h1>
      <p className="muted small" style={{ margin: 0 }}>{t("myDataIntro")}</p>
      <div className="card stack">
        <b>{t("download")}</b>
        <span className="small muted">{t("downloadHint")}</span>
        <button className="btn secondary" disabled={busy} onClick={download}>{t("download")}</button>
      </div>
      <div className="card stack">
        <b>{t("deleteTitle")}</b>
        <span className="small muted">{t("deleteHint")}</span>
        {!openDelete && (
          <>
            <label className="field"><span>{t("deleteReason")}</span>
              <textarea className="input" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} /></label>
            <button className="btn danger" disabled={busy} onClick={askDelete}>{t("deleteBtn")}</button>
          </>
        )}
      </div>
      {msg && <div className="error">{msg}</div>}
      {reqs.length > 0 && (
        <div className="card">
          <b className="small">{t("requests")}</b>
          {reqs.map((r) => (
            <div key={r.id} className="row-between small">
              <span>{r.kind === "delete" ? t("deleteTitle") : t("download")} · {r.at ? new Date(r.at).toLocaleDateString() : ""}
                {r.resolution && <div className="muted">{r.resolution}</div>}</span>
              <span className={`tag ${r.status === "done" ? "ok" : r.status === "open" ? "amber" : "grey"}`}>{t(r.status)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
