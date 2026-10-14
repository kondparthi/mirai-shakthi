// Upload a CSV, see a preview with row errors, then import. Used for entrepreneurs and master lists.
import { useRef, useState } from "react";
import { apiUpload } from "../api";

type Row = Record<string, unknown> & { line: number; errors: string[] };
const LABEL: Record<string, string> = { rows: "rows", ok: "ready", add: "to add", update: "to update", errors: "with problems" };
type Result = { summary: Record<string, number>; preview?: Row[]; imported?: boolean };

export default function CsvImport({ path, columns, onDone }: { path: string; columns: [string, string][]; onDone?: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [res, setRes] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLInputElement>(null);
  const sep = path.includes("?") ? "&" : "?";

  const send = async (commit: boolean, f = file) => {
    if (!f) return;
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await apiUpload<Result>(`${path}${sep}commit=${commit}`, fd);
      setRes(r);
      if (r.imported) {
        setFile(null);
        onDone?.();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const cell = (v: unknown) => (Array.isArray(v) ? v.join("; ") : v === true ? "yes" : v === false ? "no" : v == null ? "" : String(v));
  return (
    <div className="stack">
      <div className="row-gap">
        <input ref={ref} type="file" accept=".csv,text/csv" aria-label="CSV file" style={{ maxWidth: 260 }} onChange={(e) => {
          const f = e.target.files?.[0] ?? null;
          e.target.value = ""; // so choosing the same (corrected) file again is read again
          setFile(f); setRes(null); if (f) send(false, f);
        }} />
        {file && <span className="small">{file.name}</span>}
        {busy && <span className="small muted">Reading…</span>}
      </div>
      {error && <div className="error">{error}</div>}
      {res?.imported && <div className="notice ok-notice">Imported {res.summary.ok ?? (res.summary.add ?? 0) + (res.summary.update ?? 0)} of {res.summary.rows} rows.</div>}
      {res && !res.imported && (
        <>
          <div className="row-gap small">{Object.entries(res.summary).map(([k, v]) => <span key={k} className={`tag ${k === "errors" && v ? "alert" : ""}`}>{v} {LABEL[k] ?? k}</span>)}</div>
          <div className="table-wrap card">
            <table className="table compact">
              <thead><tr><th>Line</th>{columns.map(([, l]) => <th key={l}>{l}</th>)}<th>Problems</th></tr></thead>
              <tbody>
                {res.preview?.map((r) => (
                  <tr key={r.line} className={r.errors.length ? "row-bad" : ""}>
                    <td>{r.line}</td>{columns.map(([k]) => <td key={k}>{cell(r[k])}</td>)}
                    <td className="small">{r.errors.length ? r.errors.join("; ") : <span className="tag ok">ok</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(res.preview?.length ?? 0) >= 50 && <span className="small muted">Showing the first 50 rows (rows with problems first).</span>}
          <div><button className="btn" disabled={busy || !!res.summary.errors || !file} onClick={() => send(true)}>
            {res.summary.errors ? "Fix the rows with problems and choose the file again" : "Import now"}</button></div>
        </>
      )}
    </div>
  );
}
