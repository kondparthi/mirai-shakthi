# Android APK – test checklist for low-end phones (Sprint 5)

Use this to test the APK on real phones before the demo and before go-live. Tick each row on each phone and note the
phone model, Android version and RAM in the results table at the end.

## 1. Phones to test

Test on at least one phone from each row. Borrow from staff or family if needed – most MSME owners use phones like these.

| Type | Examples | Why |
|---|---|---|
| Entry level, 2–3 GB RAM, Android 9–11 | Redmi 9A / 9i, Samsung Galaxy M02 / A03 Core, realme C11, itel / Tecno budget models | Slow CPU, small memory, older WebView |
| Mid range, 4 GB RAM, Android 12–14 | Redmi Note 10/11, Samsung Galaxy M13 / A14, realme Narzo | The most common phones |
| Small screen (5.5″ or 720 px wide) | Any older phone | Checks layout at 320–360 px width |

The app needs Android 6.0 or newer (`minSdkVersion 23`). Update **Android System WebView** and **Google** app from the
Play Store first – voice input and page display come from them.

## 2. Build the test APK

```powershell
cd M:\backup\mirai-shakthi\frontend
copy .env.android.example .env.production     # set VITE_API_BASE=https://app.your-domain.in (the live server)
npm install
npm run build
npx cap sync android
npx cap open android                           # Android Studio → Build → Build APK(s) → app-debug.apk
```

Test against the live server over **https** (deploy to the Hostinger VPS first). Android blocks plain `http://`
addresses, so a laptop address like `http://192.168.1.5:8000` will not work from the APK without extra settings.

Install: copy `app-debug.apk` to the phone (WhatsApp to yourself or USB) → open → allow "Install unknown apps".

## 3. What to test

Network: do every test once on Wi-Fi and once on **mobile data with 3G/4G only**
(Settings → Mobile network → Preferred network type). Use a SIM with low signal if you can.

| # | Test | Expected result | Pass? |
|---|---|---|---|
| 1 | Install and open the app | Opens to the login screen in under 3 seconds; APK about 5–7 MB | |
| 2 | Log in with mobile number and OTP | OTP arrives by SMS (or shows on screen in development mode); profile wizard opens | |
| 3 | Tap **తె** on the login screen and finish the profile in Telugu | All profile questions and choices in Telugu; Telugu letters look correct (no boxes or broken letters) | |
| 4 | Home in Telugu | Module cards, popular questions and bottom menu in Telugu | |
| 5 | Tap the **mic** and say “నాకు బ్యాంకు లోన్ కావాలి” | Phone asks for microphone permission once; Google voice popup appears; text appears in the box in Telugu; tap అడగండి | |
| 6 | Mic in English: “How do I get GST registration?” | English text appears; answer is about GST | |
| 7 | Deny microphone permission, then tap the mic again | Clear message to allow the microphone; app does not crash | |
| 8 | Mic with mobile data off | Message that voice needs internet (or offline Telugu voice works if downloaded in Google settings) | |
| 9 | Ask 3 questions in a row | Each answer in under 5 seconds on 4G; scrolling is smooth | |
| 10 | Answer → **Roadmap (PDF)** | PDF downloads and opens in the phone's PDF viewer | |
| 11 | Documents → Cash-flow summary → **Choose file** → pick a bank statement (Excel/CSV/PDF) from Downloads or WhatsApp | File picker opens; “What we found” table shows; “Use these figures” fills the months | |
| 12 | Password-protected PDF statement | Asks for the password, then reads it | |
| 13 | Make my summary → Download PDF | Summary and PDF work | |
| 14 | Answer → expert → **Request help** → send | Request appears under **Requests** | |
| 15 | Phone **Back** button on each screen | Goes to the previous screen; on Home it closes the app | |
| 16 | Turn on **Large font** (Settings → Display → Font size → largest) | Text gets bigger; nothing overlaps or gets cut off | |
| 17 | Rotate the phone | Layout adjusts (portrait is the main use) | |
| 18 | Open the camera or WhatsApp for 2 minutes, then come back | App is where you left it (or reopens logged in) | |
| 19 | Airplane mode, then ask a question | Message “No internet connection…”, no crash | |
| 20 | Log out and log in again | Works; previous conversations are in History | |

## 4. Speed measured in the browser (Sprint 5)

Measured with Chrome's phone emulation set to a low-end phone (CPU 6× slower) on a 3G connection (1.6 Mbps, 150 ms),
first visit with an empty cache. In the APK the app files are on the phone, so only the API calls use the network.

| Screen | Before Sprint 5 | After Sprint 5 |
|---|---|---|
| App code downloaded at start (gzip) | 95 KB | 73 KB (admin, expert and tools load only when opened) |
| Web files packed in the APK | 2.1 MB | 1.2 MB (only Latin and Telugu fonts) |
| Login screen ready | 1.2 s | 1.2 s |
| Home ready (signed in) | 2.3 s | 1.9 s |
| Layout at 320 px width (smallest phones), Telugu | – | No sideways scrolling on Home, answer, statement upload, requests |

## 5. Results

| Phone | Android | RAM | Tests failed (numbers) | Notes | Tested by / date |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |
