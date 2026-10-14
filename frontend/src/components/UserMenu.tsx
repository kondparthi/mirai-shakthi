// Top-right account menu with Sign out, used by the staff portal and the entrepreneur app.
import { LogOut, UserRound } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

/** Letters for the avatar; empty when the name has no letters (e.g. only a mobile number). */
export const initialsOf = (name?: string | null) =>
  (name || "").trim().split(/\s+/).filter((w) => /^\p{L}/u.test(w)).slice(0, 2).map((w) => [...w][0].toUpperCase()).join("");

export default function UserMenu({ name, sub, detail, items, signOutLabel = "Sign out", onSignOut }: {
  name: string; sub?: string; detail?: string; items?: ReactNode; signOutLabel?: string; onSignOut: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);
  return (
    <div className="usermenu" ref={ref}>
      <button className="usermenu-btn" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)} aria-label={`Account: ${name}`}>
        <span className="initials" aria-hidden="true">{initialsOf(name) || <UserRound size={18} />}</span>
        <span className="who"><b>{name}</b>{sub && <small>{sub}</small>}</span>
      </button>
      {open && (
        <div className="usermenu-pop" role="menu" onClick={(e) => (e.target as HTMLElement).closest("a,button") && setOpen(false)}>
          <div className="head"><b>{name}</b>{detail && <small>{detail}</small>}</div>
          {items}
          <button role="menuitem" className="signout" onClick={onSignOut}><LogOut aria-hidden="true" />{signOutLabel}</button>
        </div>
      )}
    </div>
  );
}
