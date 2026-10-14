import type { CapacitorConfig } from "@capacitor/cli";

// Android app wraps the same React build (dist/). Set VITE_API_BASE to the live API URL before `npm run build`.
const config: CapacitorConfig = {
  appId: "in.mirai.shakthi",
  appName: "MIRAI Shakthi",
  webDir: "dist",
  android: { allowMixedContent: false },
};

export default config;
