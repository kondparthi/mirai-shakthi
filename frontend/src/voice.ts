// Voice input (Sprint 5). In the Android app it uses the phone's speech recogniser through the Capacitor plugin
// (Google voice typing – supports Telugu and English). In a browser it uses the Web Speech API where available
// (Chrome and Edge). Where neither exists the mic button is hidden.
import { Capacitor } from "@capacitor/core";

type Lang = "en" | "te";
const LOCALE: Record<Lang, string> = { en: "en-IN", te: "te-IN" };

export type VoiceErrorCode = "denied" | "no-speech" | "unavailable" | "network" | "failed";
export class VoiceError extends Error {
  code: VoiceErrorCode;
  constructor(code: VoiceErrorCode) {
    super(code);
    this.code = code;
  }
}

// Minimal typing for the browser API (not in TypeScript's DOM library).
type WebRecognition = {
  lang: string; interimResults: boolean; continuous: boolean; maxAlternatives: number;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void; stop(): void; abort(): void;
};
const WebSR = (): (new () => WebRecognition) | undefined => {
  const w = window as unknown as { SpeechRecognition?: new () => WebRecognition; webkitSpeechRecognition?: new () => WebRecognition };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
};

export const isNative = () => Capacitor.isNativePlatform();

/** Can this device take voice input at all? (Native availability is confirmed when listening starts.) */
export function voiceSupported(): boolean {
  return isNative() ? Capacitor.isPluginAvailable("SpeechRecognition") : !!WebSR();
}

let current: WebRecognition | null = null;

/** Listen once and return what was said. onPartial receives the text so far (browser only). */
export async function listen(lang: Lang, onPartial?: (text: string) => void, prompt?: string): Promise<string> {
  if (isNative()) {
    const { SpeechRecognition } = await import("@capacitor-community/speech-recognition");
    const { available } = await SpeechRecognition.available().catch(() => ({ available: false }));
    if (!available) throw new VoiceError("unavailable");
    let perm = await SpeechRecognition.checkPermissions();
    if (perm.speechRecognition !== "granted") perm = await SpeechRecognition.requestPermissions();
    if (perm.speechRecognition !== "granted") throw new VoiceError("denied");
    try {
      // The Google voice popup is the most reliable option on low-end phones and shows its own "listening" state.
      const r = await SpeechRecognition.start({ language: LOCALE[lang], maxResults: 1, popup: true, partialResults: false, prompt });
      const text = r?.matches?.[0]?.trim() ?? "";
      if (!text) throw new VoiceError("no-speech");
      return text;
    } catch (e) {
      if (e instanceof VoiceError) throw e;
      const msg = String((e as Error)?.message ?? e).toLowerCase();
      throw new VoiceError(msg.includes("no match") || msg.includes("no speech") ? "no-speech" : msg.includes("network") ? "network" : "failed");
    }
  }

  const SR = WebSR();
  if (!SR) throw new VoiceError("unavailable");
  return new Promise<string>((resolve, reject) => {
    const rec = new SR();
    current = rec;
    rec.lang = LOCALE[lang];
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    let finalText = "";
    let failed: VoiceError | null = null;
    rec.onresult = (e) => {
      let interim = "";
      finalText = "";
      for (let i = 0; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) finalText += res[0].transcript;
        else interim += res[0].transcript;
      }
      onPartial?.((finalText + interim).trim());
    };
    rec.onerror = (e) => {
      failed = new VoiceError(e.error === "not-allowed" || e.error === "service-not-allowed" ? "denied"
        : e.error === "no-speech" ? "no-speech" : e.error === "network" ? "network" : e.error === "aborted" ? "no-speech" : "failed");
    };
    rec.onend = () => {
      current = null;
      if (finalText.trim()) resolve(finalText.trim());
      else reject(failed ?? new VoiceError("no-speech"));
    };
    try {
      rec.start();
    } catch {
      current = null;
      reject(new VoiceError("failed"));
    }
  });
}

/** Stop listening early (browser); the words heard so far are kept. */
export async function stopListening() {
  if (isNative()) {
    const { SpeechRecognition } = await import("@capacitor-community/speech-recognition");
    await SpeechRecognition.stop().catch(() => {});
  } else current?.stop();
}
