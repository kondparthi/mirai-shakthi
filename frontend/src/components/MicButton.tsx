// Mic button for the ask boxes. Spoken words are put in the box so the user can check them before sending.
import { useEffect, useState } from "react";
import { useLang } from "../i18n";
import { listen, stopListening, VoiceError, voiceSupported } from "../voice";

export default function MicButton({ value, onChange, onError, disabled }: {
  value: string; onChange: (text: string) => void; onError: (message: string | null) => void; disabled?: boolean;
}) {
  const { t, lang } = useLang();
  const [on, setOn] = useState(false);
  const [supported] = useState(voiceSupported);
  useEffect(() => () => { if (on) stopListening(); }, [on]);
  if (!supported) return null;

  const click = async () => {
    if (on) { stopListening(); return; }
    onError(null);
    setOn(true);
    // Spoken words are added after anything already typed.
    const base = value.trim();
    const join = (spoken: string) => (base ? `${base} ${spoken}` : spoken);
    try {
      const text = await listen(lang, (partial) => onChange(join(partial)), t("speakNow"));
      onChange(join(text));
    } catch (e) {
      onChange(value);
      const code = e instanceof VoiceError ? e.code : "failed";
      onError(t(code === "denied" ? "micDenied" : code === "no-speech" ? "micNoSpeech" : code === "network" ? "micNetwork"
        : code === "unavailable" ? "micUnavailable" : "micFailed"));
    } finally {
      setOn(false);
    }
  };

  return (
    <button type="button" className={`mic ${on ? "on" : ""}`} onClick={click} disabled={disabled}
      aria-pressed={on} aria-label={on ? t("micStop") : t("micStart")} title={on ? t("micStop") : t("micStart")}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z" /><path d="M19 11a7 7 0 0 1-14 0M12 18v3" />
      </svg>
    </button>
  );
}
