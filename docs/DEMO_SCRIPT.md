# MIRAI Shakthi – Phase 0 demo script (about 20 minutes)

A step-by-step walkthrough for showing the AI Guidance Assistant to MIRAI. It follows one business owner,
Lakshmi (millet snacks, Guntur), through the five steps, then shows the expert and the MIRAI admin side.

All names, numbers and knowledge content are **sample data**. Say this at the start.

## Before the demo (15 minutes)

1. Start the backend and frontend (README → “Run it on your computer”), or open the live server.
2. Load the demo data once:
   ```powershell
   cd M:\backup\mirai-shakthi\backend
   py -m seed.seed
   py -m seed.demo
   ```
3. Open three browser windows side by side (or three Chrome profiles so the logins do not mix):
   - **Phone view** – `http://localhost:5173` with Chrome DevTools phone mode (F12 → phone icon → 390 × 844), or the APK on a phone
   - **Expert** – `http://localhost:5173/#/expert`
   - **Admin** – `http://localhost:5173/#/admin`
4. Keep `backend\seed\sample_statements\A_sample_statement.xlsx` on the desktop (and copy it to the phone if you use the APK).
5. For voice: use Chrome (desktop or Android) or the APK, allow the microphone, and test once in a quiet room.

| Who | Login | Notes |
|---|---|---|
| New business owner (live demo) | any new mobile, e.g. 9876500001 | OTP shows on screen in development mode |
| Lakshmi (Telugu, finished case) | 9000000101 | GST case done and rated 5★, cash-flow summary from bank statement |
| Ravi / Fatima / Suresh / Padma / Kiran | 9000000102 … 106 | Requests in other states |
| Expert – CA Guntur | ca.guntur@mirai.local / Expert@123 | |
| Expert – Export facilitator | export@mirai.local / Expert@123 | Has a quote waiting |
| MIRAI admin | admin@mirai.local / ChangeMe@123 | Change before go-live |

## Part 1 – The business owner (10 minutes)

| # | Do | Say |
|---|---|---|
| 1 | Phone view → enter a new mobile → Get OTP → enter OTP → tick consent | “Login is mobile + OTP, with data consent recorded – no passwords for MSME owners.” |
| 2 | Tap **తె** | “The whole app works in Telugu and English. Telugu content is a first draft for MIRAI's team to review.” |
| 3 | Fill the 5 short profile cards (Lakshmi, millet snacks, Food, Guntur, up to ₹10 lakh, 3 people, notebook) | “One minute of profile makes every answer specific to this business.” |
| 4 | Home: point at the five module cards | “These are the five MIRAI modules: MicroFin, MarketKonnect, Launch Pad / Export Ready, SkillsPro and Handholding.” |
| 5 | Tap the **mic** and say: “నాకు జీఎస్టీ రిజిస్ట్రేషన్ అవసరమా?” → Ask | “Owners can speak instead of typing.” |
| 6 | Walk down the answer: **1 Understanding → 2 Gaps → 3 Information → 4 Next steps → 5 Connect** | “The five steps from the challenge. Step 2 compares her profile with the rules – she has nothing yet, so GST and Udyam are missing. Step 3 only uses verified content and shows the source. Step 4 gives documents, time, cost and the official link.” |
| 7 | Tap **Roadmap (PDF)** | “A printable plan she can take to a CA or a bank.” |
| 8 | Bottom menu → **Documents** → **Cash-flow summary** → **Choose file** → `A_sample_statement.xlsx` | “Most owners do not keep books, but every owner has a bank statement. Excel, CSV or PDF from net banking.” |
| 9 | Show the “What we found” table | “Each entry is sorted: customer receipts and cash deposits are sales; suppliers, wages, rent, power; the Mudra loan money and interest are *not* counted as sales; the EMI is added as a loan. The file is not saved and account numbers are hidden.” |
| 10 | **Use these figures** → **Make my summary** | “Profit, margin, cash gaps and plain-language warnings. Every number is calculated in Python, not by the AI.” |
| 11 | Back to the GST answer → step 5 → **Request help** on Sample CA – Guntur | “The case summary is written from the conversation; she can edit it, choose documents to share and must give consent.” |
| 12 | Tick consent → **Send request** | “Her mobile number is shown to the expert only after the expert accepts.” |

## Part 2 – The expert (4 minutes)

| # | Do | Say |
|---|---|---|
| 13 | Expert window → log in as the CA → open the new case | “Experts see new cases with the reply-by time, the business profile and the summary.” |
| 14 | **Accept case** → now Call / WhatsApp buttons appear | “Contact details only after accepting.” |
| 15 | Download the shared roadmap PDF | |
| 16 | **Send quote** → ₹1,500, “GST registration in 7 working days” | |
| 17 | Phone view → **Requests** → open it → **Accept quote** | “The owner sees each step, like a parcel tracker.” |
| 18 | Expert → **Mark completed**; phone → rate 5 stars | “Ratings feed the expert's score that other owners see.” |

## Part 3 – MIRAI admin (5 minutes)

| # | Do | Say |
|---|---|---|
| 19 | Admin → **Dashboard** | “Usage, most asked topics, documents made, open requests and what needs attention.” |
| 20 | **Expert requests** → “Needs attention” | “Kiran's case was declined and Ravi's has had no reply for 3 days. MIRAI reassigns them so no one is left waiting.” → open Ravi's case → reassign to Sample CA – Guntur. (Kiran's has no other HR expert yet – a sign MIRAI needs more experts in that service.) |
| 21 | **Answer review** | “Questions with no verified answer or a thumbs-down come here – e.g. ‘weather tomorrow’ – so the team can add content or keywords.” |
| 22 | **Knowledge library** → open an item | “MIRAI controls every fact the assistant uses: who verified it, when, and when it must be reviewed again. Telugu and English items.” |
| 23 | **Topics & rules** → open “GST registration” → a requirement | “Rules like ‘GST is missing if the profile has no GST’ are set here without coding.” |
| 24 | **Experts** → open the CA | “Approve experts, set services and districts, and create their login.” |

## If something goes wrong

| Problem | What to do |
|---|---|
| Voice does not work | Say “voice needs Chrome or the app and internet”, and type the question instead. |
| An answer picks the wrong topic | Use it to show **Answer review** – that is exactly what the admin screen is for. |
| “No internet connection” | The backend is not running – restart `py -m uvicorn app.main:app`. |
| Need fresh demo data | `py -m seed.demo --remove` then `py -m seed.demo`. |

## After the demo – questions to ask MIRAI

1. Who in MIRAI's team will review and approve the knowledge content (English and Telugu)?
2. Which real experts and institutions should replace the sample directory, and what fees do they charge?
3. Which SMS provider and sender ID should be used for OTP (MSG91 is ready)?
4. Which AI provider and budget for live answers (the demo runs without AI calls)?
5. Which districts and sectors for the pilot, and how many MSMEs?
