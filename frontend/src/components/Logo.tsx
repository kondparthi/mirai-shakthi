// MIRAI Shakthi logo: a sprout rising from a growth step inside a gradient tile, and the wordmark in Anek,
// a typeface with matching Latin and Telugu letters so the brand looks the same in both languages.
import "@fontsource-variable/anek-latin/wght.css";
import "@fontsource-variable/anek-telugu/wght.css";
import { useId } from "react";
import { useLang } from "../i18n";

export function LogoMark({ size = 36 }: { size?: number }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" className="logo-mark">
      <defs>
        <linearGradient id={`lg-${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1FA187" />
          <stop offset="1" stopColor="#0C4A37" />
        </linearGradient>
        <linearGradient id={`lf-${id}`} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#F6B23A" />
          <stop offset="1" stopColor="#FFD77A" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="13" fill={`url(#lg-${id})`} />
      {/* growth steps */}
      <path d="M11 36h8v-6h8v-6h10" fill="none" stroke="#fff" strokeOpacity="0.55" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {/* sprout */}
      <path d="M27 24c0-7 4-11 11-12-0.5 7-4.5 11-11 12z" fill={`url(#lf-${id})`} />
      <path d="M27 24c-1-5-4-8-9-8 0.3 5 3.5 8 9 8z" fill="#fff" />
    </svg>
  );
}

export default function Logo({ tone = "dark", size = 36 }: { tone?: "dark" | "light"; size?: number }) {
  const { lang } = useLang();
  return (
    <span className={`logo logo-${tone}`} style={{ fontSize: size * 0.62 }}>
      <LogoMark size={size} />
      <span className="logo-word">
        {lang === "te" ? <>మిరాయ్ <b>శక్తి</b></> : <>MIRAI <b>Shakthi</b></>}
      </span>
    </span>
  );
}
