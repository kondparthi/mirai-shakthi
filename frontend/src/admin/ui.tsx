// Small shared pieces for the admin portal.
import { useEffect, type ReactNode } from "react";

export const MODULES: [string, string][] = [
  ["microfin", "MicroFin"],
  ["marketkonnect", "MarketKonnect"],
  ["launchpad", "Launch Pad / Export Ready"],
  ["skillspro", "SkillsPro"],
  ["handholding", "Handholding"],
];
export const moduleName = (code: string | null | undefined) => MODULES.find(([c]) => c === code)?.[1] ?? code ?? "—";

export function Modal({ title, onClose, children, wide = false }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="btn ghost" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small className="muted">{hint}</small>}
    </label>
  );
}

export function StatusTag({ status }: { status: string }) {
  const cls = status === "published" || status === "approved" ? "ok" : status === "draft" || status === "pending" ? "amber" : "grey";
  return <span className={`tag ${cls}`}>{status}</span>;
}

/** Comma / new-line separated list <-> array */
export const toList = (s: string) => s.split(/[\n,]/).map((x) => x.trim()).filter(Boolean);
