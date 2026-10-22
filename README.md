# MIRAI Shakthi – Phase 0: MSME AI Guidance Assistant

Challenge prototype – Sprint 5 (MSME app in English and Telugu with voice input, admin portal, documents, bank-statement upload, expert requests). An MSME owner logs in with their mobile number, fills a one-minute
business profile, and asks a question. The assistant answers in five steps:

**Understanding → Identification (gaps) → Information (verified content) → Guidance (next steps) → Connect (experts)**

| Part | Technology |
|---|---|
| Web app / Android app | React 18 + TypeScript (Vite). Android via Capacitor (same code). |
| Backend API | Python 3.12+, FastAPI, SQLAlchemy 2 |
| Database | MySQL 8 (MariaDB 10.6+ also works) – utf8mb4, FULLTEXT search |
| AI | Pluggable. `AI_PROVIDER=none` runs a built-in demo composer with no external calls; `AI_PROVIDER=anthropic` uses Claude with an API key. |

## What works in Sprint 1

- Mobile OTP login with consent (development mode shows the OTP on screen; MSG91 SMS ready to switch on).
- Quick MSME profile (Form G-1) as a 5-card wizard.
- Home screen with ask box, the five module cards (MicroFin, MarketKonnect, Launch Pad / Export Ready, SkillsPro, Handholding) and popular questions.
- Five-step answer for every question:
  1. **Understanding** – detects module and topic (18 topics), shows the profile it used.
  2. **Identification** – rule engine compares the profile with each topic's requirement list → "What you have / What is missing".
  3. **Information** – answer built only from published, in-date knowledge items, with numbered sources.
  4. **Guidance** – numbered next steps with documents, time, cost and official link; tick off as done.
  5. **Connect** – matched experts by service, district and language.
- "Your question also touches" chips when a question covers more than one topic.
- Conversation history, follow-up questions, 👍/👎 rating (👎 flags the answer for review).
- English / Telugu interface (Telugu labels are a first draft for MIRAI to review; fonts bundled for offline use).
- Personal data (Aadhaar, PAN, phone, account numbers, email) is masked before any text goes to an AI provider.
- 10 automated API tests on MySQL.

> **All knowledge content, rules and experts in `backend/seed/data.py` are SAMPLE data** written to demonstrate the flow.
> They are labelled "Sample content" in the app. MIRAI must verify or replace them before showing real users.

## Admin portal (Sprint 2)

Open **http://localhost:5173/#/admin** and sign in with the admin user created by the seed
(`ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env`; default `admin@mirai.local` / `ChangeMe@123` – change it).

| Screen | What staff can do |
|---|---|
| Dashboard | Users, questions, helpful rating, answers needing review, content due for review, most asked topics, conversations by module |
| Answer review (A6) | Answers rated 👎, with no verified source, or with no recognised topic → fix content, mark done |
| Knowledge library (A1) | Add / edit / publish / archive content; "Mark verified today"; review-due dates (expired content is hidden from answers) |
| Topics & rules (A2) | Edit keywords and sample questions; add / edit / delete requirements with a visual condition builder (JSON for advanced cases) |
| Experts (A4) | Add experts, approve / suspend; only approved experts appear in Handholding |
| MSME users | List with business profile summary and conversation count (mobile numbers partly hidden) |

Publishing content requires "verified by" and "verified on". Every admin change is written to `audit_logs`.
Re-running `python -m seed.seed` on an existing database never overwrites admin edits; it only adds new starter keywords.

The MSME app now has a desktop layout (side menu, two-column answers) on screens 1024 px and wider.

## Documents (Sprint 3)

| Document | Where | What it contains |
|---|---|---|
| Roadmap (PDF) | Any answer → Next steps → “Roadmap (PDF)” | Numbered steps with documents, time, cost, official links, done ticks and sources |
| Document checklist (PDF) | Any answer → “Document checklist (PDF)” | Every document needed across the steps, de-duplicated, with what each is for |
| Cash-flow summary (PDF) | Documents → Cash-flow summary (MicroFin, Form G-2) | Sales, expenses, profit and margin by month, chart, expense heads, money owed with ageing (45-day MSMED flag), payables, working capital, EMI burden, plain-language insights and data gaps |
| Job description (PDF) | Documents → Job description (SkillsPro) | Role templates (helper, sales, accounts, delivery, machine operator, cook) → editable JD with onboarding checklist and minimum-wage note |

All figures are calculated in Python (`app/artefacts/cashflow.py`), never by the AI. PDFs are made with ReportLab when
downloaded (nothing stored on disk) through a 10-minute download link, so downloads also work in the Android app.
PDFs are in English for now (ReportLab cannot shape Telugu script); amounts are shown as “Rs.” because standard PDF
fonts have no ₹ sign. Run `python -m seed.seed` once after updating – it creates the new `artefacts` table.

## Handholding – expert requests (Sprint 4)

| Who | Where | What they can do |
|---|---|---|
| MSME user | Any answer → step 5 → “Request help” (Form G-6) | Check the service, edit the case summary written from the conversation, choose which documents to share, preferred contact and budget, and give consent before sending |
| MSME user | Bottom menu → **Requests** (screen G10) | Track status (Sent → Accepted → Quote → In progress → Done), accept or decline a quote, message the expert, cancel, rate the expert after completion |
| Expert | `#/expert` – expert workspace (screen E1) | See new and open cases with reply-by time, accept or decline with a reason, send a quote, start and complete work, message the client, download shared PDFs |
| MIRAI admin | Admin → **Expert requests** (screen A5) | “Needs attention” queue (declined or past the reply time), reassign to another approved expert offering the service, message both sides, cancel |
| MIRAI admin | Admin → Experts → open an expert → **Expert workspace login** | Create or reset the expert's email and password |

Privacy: the expert sees the client's mobile number only after accepting the case; shared PDFs open through a
10-minute download link. Every consent, reassignment, cancellation and login change is written to the audit log.
Ratings update the expert's average rating shown to users.

**Demo expert login** (created by the seed for “Sample CA – Guntur”): `ca.guntur@mirai.local` / `Expert@123` at
`http://localhost:5173/#/expert`. Change it from the admin Experts screen, or set `DEMO_EXPERT_EMAIL` /
`DEMO_EXPERT_PASSWORD` before seeding. Remove sample experts before go-live.

After updating, run `py -m seed.seed` once – it creates the new `connect_updates` table and the demo expert login.

## Telugu, voice and bank statements (Sprint 5)

**Telugu answers.** With the app set to తె, the whole answer is in Telugu: topic, gaps, next steps (title and
“why”), the answer text, sources, profile summary, home-screen questions and the profile form. The seed adds Telugu
keywords, sample questions, requirement texts and 18 Telugu knowledge items (`seed/data_te.py`). Telugu questions
match topics even with word endings (ఎగుమతి → ఎగుమతులకు, రుణం → రుణానికి). English users never see Telugu sources;
Telugu users see English sources only for topics with no Telugu item yet. Admins edit Telugu in Knowledge library
(language = Telugu) and in Topics & rules (“Why it matters (Telugu)”). **All Telugu text is a draft – MIRAI's native
speakers must review it before real users see it.**

**Voice input.** A mic button next to the ask boxes. Spoken words go into the box so the owner can check them before
asking. In the Android app it uses the phone's Google voice typing (Telugu `te-IN` and English `en-IN`); in Chrome
and Edge it uses the browser's speech recognition. Where neither exists the button is hidden. Voice needs internet
unless the phone has the offline Telugu voice pack.

**Bank statement upload (MicroFin).** Documents → Cash-flow summary → “Fill from your bank statement”. Accepts Excel
(.xlsx, .xls and the HTML “.xls” some banks send), CSV and text PDFs, including password-protected PDFs. It finds the
table, sorts every entry (customer receipts and cash deposits → sales; suppliers, wages, rent, power, transport,
taxes, charges, cash withdrawals → expenses; loan money, refunds, interest and own transfers → not counted; EMIs →
loan) and adds up by month. The owner sees what was found, then fills the form with one tap and can edit anything.
The file is read in memory and **never stored**; account numbers are hidden; only counts go to the audit log.
Scanned (photo) PDFs are not supported yet. Five sample statements in different bank layouts:
`py -m seed.sample_statements` → `backend/seed/sample_statements/` (the PDF password is `MIRAI123`).

**Low-end phones.** Admin, expert workspace and tools load only when opened (start-up code 95 KB → 73 KB gzip),
only Latin and Telugu fonts are packed (web files in the APK 2.1 MB → 1.2 MB), and the nginx config now compresses
API answers and caches app files. Measured on a simulated low-end phone on 3G: Home ready in about 1.9 s (was 2.3 s).
Checked at 320 px width in Telugu. Real-phone test plan: [`docs/ANDROID_TEST_CHECKLIST.md`](docs/ANDROID_TEST_CHECKLIST.md).

**Demo data and script.** `py -m seed.demo` adds six fictional MSME owners (two in Telugu) with conversations,
ratings, documents, a cash-flow summary from a bank statement, and expert requests in every state (completed and
rated, quote waiting, in progress, declined, overdue), plus portal logins for all sample experts (`Expert@123`).
Remove it with `py -m seed.demo --remove`. Walkthrough for presenting to MIRAI: [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

### Updating from Sprint 4

```powershell
cd M:\backup\mirai-shakthi\backend
py -m pip install -r requirements.txt     # new: python-multipart, openpyxl, xlrd, pdfplumber
py -m seed.seed                           # adds the why_te column and the Telugu content
py -m seed.demo                           # optional: demo data
cd ..\frontend
npm install                               # new: speech recognition plugin for the Android app
npx cap sync android                      # registers the plugin and microphone permission in the Android project
```

## Phase 1, Sprint 1 – Enrolment, masters and access

**Staff portal** (`#/admin`) now shows a menu for each role. Programme screens: Overview, Entrepreneurs, Groups, Bulk import.
Settings: Master data, Readiness formula, Staff & access, Audit log, Data requests.

| Role | Sees |
|---|---|
| Super Admin | Everything |
| Programme Manager | All districts; masters, readiness formula, audit log |
| District Coordinator / Field Navigator, SHG Federation Staff | Enrol and edit entrepreneurs and groups in their districts |
| Mentor, Trainer, DPR officer, Procurement, Sector expert | Read entrepreneurs and groups in their districts (mentors also record readiness) |
| Content Reviewer | AI assistant review screens (Phase 0) |

Staff with no districts set see only the records they enrolled.

- **Entrepreneur profile (Form 1.1).** Self-enrolment in the app (Home → *MIRAI enterprise programme*, step by step, English/Telugu, camera photo), or assisted by a Field Navigator: an OTP goes to the entrepreneur's phone and reading it out is their consent.
  - Aadhaar is checked (Verhoeff) and **only the last 4 digits are stored**. The bank account number is **encrypted** (`DATA_KEY`). Both are always shown masked.
  - Duplicates are checked on mobile number, and on Aadhaar last 4 + name + date of birth (staff can override after checking).
  - Staff can mark a profile *verified* only when nothing is missing (photo, Aadhaar, bank account, consent, …).
- **Group profile (Form 1.2).** SHG / JLG / producer group with members; exactly one leader, one secretary and one treasurer. Members whose mobile is enrolled are linked to their profile.
- **Readiness (Form 1.3).** Score 0–100 from 8 questions plus own funds; strengths, gaps with advice, recommended training. Repeatable. The formula (weights, points, advice, bands) is editable under Settings → Readiness formula.
- **Bulk import** of entrepreneurs from CSV (template provided) with a preview of every problem before anything is saved. Imported people confirm their details and give consent the first time they open the app.
- **Master data**: 26 AP districts, starter Guntur mandals and sample villages (load the full LGD list by CSV), context tags, 9 sectors with Catalogue / Pilot / Active status, skills, education, occupation, social category, document types, banks. Every list has CSV export and import.
- **DPDP**: people download their data and ask for deletion in the app (Profile → *My data & privacy*). Admins see the requests, download the data, and erase the account (photo, enrolment, conversations, documents).
- **Audit log** of every change: who, what, when.

### Updating to Phase 1 Sprint 1

1. Copy the changed files over the project.
2. Back end:
   - `py -m pip install -r requirements.txt` (adds Pillow).
   - `py -m seed.seed` (adds the `users.scope` column, the new tables, master data and the default readiness formula).
3. Front end: `npm run build` (no new packages).
4. Server, once: add `DATA_KEY` to `backend/.env`.
   - Generate it with `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
   - Keep a copy somewhere safe and **never change it**: bank numbers saved with it cannot be read without it.
   - Photos are stored in `backend/storage/photos`. Include that folder in backups.

## Phase 1, Sprint 2 – Training & certification (M4)

Staff portal → **Training**. Entrepreneur app → Programme → **My training**.

| Who | Can |
|---|---|
| Programme Manager / Admin | Courses (curriculum), training partners, everything below |
| District Coordinator | Plan batches, add trainees, confirm app requests, verify uploaded certificates, follow-ups |
| Trainer | *My batches* only: sessions, attendance (list or QR), session photos, results |
| Mentor | Needs assessments and 30 / 90 / 180-day follow-ups for their trainees |

- **Courses** for the six tracks (Awareness EDP, Core EDP, Skill-based, On-the-job, Exposure visit, Refresher). Each course has sessions (English and Telugu), outcomes, pass mark, minimum attendance, a practical checklist, and a business-plan score for Core EDP. Eight starter courses are loaded; MIRAI can edit them.
- **Batches (Form 4.1)**: course, partner, trainers, mentors, mode, dates, venue or host unit, seats and sponsor (CSR / government / self). Sessions are planned automatically over the dates.
- **Trainees**:
  - Staff add people from a list that shows who is *recommended*, based on the readiness check or needs assessment.
  - Entrepreneurs can also request a seat in an open batch from the app.
  - Mentors are shared among trainees automatically, as the spec says the mentor is assigned at the EDP.
- **Attendance (Form 4.2)**:
  - The trainer ticks names on a phone.
  - Or the trainer shows a **QR code / 6-digit code** that trainees scan or type to mark themselves present.
  - Session photos record the location.
- **Results**:
  - The system suggests Pass or Re-assess from attendance, quiz, practical checklist and business-plan score.
  - The trainer decides. **Pass issues the certificate.**
  - Core EDP graduates move to stage 3 (DPR & finance).
- **Certificates**:
  - A PDF in English and Telugu (names in Telugu are drawn correctly) with a QR code and check code.
  - Anyone (a bank, a CSR partner) can scan it to see that it is genuine at `#/verify`, without logging in.
- **Uploaded certificates**: DGCA Remote Pilot, FSSAI and partner certificates are uploaded in the app and verified by staff.
- **Needs assessment (Form 4.3)** on the entrepreneur page suggests tracks from the skill ratings.
- **Follow-ups (Form 4.5)** at 30, 90 and 180 days after certification are listed for the mentor.
- **Feedback** (1–5 stars) from trainees feeds the partner rating.
- **Reports** by course, sponsor and district, plus a trainee-level CSV for sponsors.

### Updating to Phase 1 Sprint 2

1. Copy the changed files over the project.
2. Back end:
   - `py -m pip install -r requirements.txt` (adds `segno` for QR codes).
   - `py -m seed.seed` (new training tables and the starter courses).
3. Front end: `npm run build`.
4. Server, once: check that Pillow can shape Telugu.
   - `python -c "from PIL import features; print(features.check('raqm'))"` must print `True`.
   - If it prints `False`, run `apt install -y libfribidi0 libraqm0`.
5. Optional: `PUBLIC_URL` in `.env` (default `https://miraimsme.com`) is the address printed in certificate and check-in QR codes.
6. Back up `backend/storage/` (photos and uploaded certificates).

## Phase 1, Sprint 3 – DPR & finance (M5, M6)

Staff portal → **DPR & finance**. Entrepreneur app → Programme → **My business plan & loan** (shown from stage 3).

| Who | Can |
|---|---|
| DPR & Credit Officer, Programme Manager, Admin | Prepare, review and approve DPRs; loan applications, status updates, EMI tracking; edit schemes |
| Sector Expert | Edit enterprise models (DPR templates) |
| Coordinator, Mentor and other programme staff | See DPRs and applications in their districts |

- **Enterprise models (Form 3.1)** are the DPR templates: equipment list, working capital, sales and expense defaults, eligible schemes, jobs, payback. Three starter models: mobile millet café, tea stall, drone spraying.
- **DPR builder (Form 5.1)**:
  - "New DPR" from the entrepreneur page (or DPRs → New) fills equipment, sales and expenses from the model; own money from what the person said they have.
  - Inputs: capital items, contingency, pre-operative costs, working capital, own / subsidy / grant (the loan is the balance), sales items, expenses, loan terms with moratorium, owner's drawings, depreciation, tax, 3–5 years.
  - Every figure is calculated by the server (`app/dpr/finance.py`) as you type: project cost, means of finance, 5-year profit and loss, cash flow, DSCR (after owner's drawings), break-even, payback, EMI and repayment schedule.
  - Warnings in plain language; errors (e.g. DSCR below 1, over-funding) block approval.
- **Schemes (M6)**: PMEGP, PMFME, MUDRA, Stand-Up India with rules for age, category, activity, sector, cost and loan limits, education, own contribution and subsidy rates, plus document lists. The check is rules only, with a reason for each result. "Use this scheme" sets the subsidy and raises own money to the minimum. **The starter rules are marked "starter data – verify"; the DPR officer checks them against the current guidelines and sets "Verified on".**
- **Narrative**: officer's notes + figures → AI drafts promoter, business, market, operations, SWOT, risks and conclusion (a template drafts them when `AI_PROVIDER=none`). The officer edits every section.
- **Review / approve / reopen**: approved DPRs are locked; reopening makes a new version. Every review, approval and reopen keeps a copy, and each version's PDF can be downloaded.
- **PDF**: bank format (cover, project at a glance, cost, means of finance, sales, expenses, profitability with chart, cash flow, DSCR, break-even, repayment, SWOT, sign-off, monthly schedule annexure). Drafts carry a "DRAFT – NOT APPROVED" watermark. Amounts print as "Rs." (the bundled font has no ₹ sign); Telugu names are drawn correctly.
- **Loan applications (Forms 6.1, 6.2)** from an approved DPR: bank and branch, scheme (eligible only), document checklist (DPR and MIRAI EDP certificate ticked automatically; uploads; extra documents the bank asks for), status Draft → Submitted → Bank query → Sanctioned → Disbursed / Rejected with dates, query and response log.
- **Disbursement** creates the EMI schedule (the bank's EMI or calculated); staff mark EMIs paid; on time / delayed / default-risk (3+ overdue) is shown.
- **Lifecycle**: creating a DPR moves the person to stage 3; sanction (or an approved DPR with no loan – own funds) moves them to stage 4.
- **Entrepreneur app**: key figures in English / Telugu, approved DPR download, loan status and history, upload missing documents with the phone camera, next EMI and the schedule.
- **Finance dashboard** and CSV of all applications (for banks / sponsors).

### Updating to Phase 1 Sprint 3

1. Copy the changed files over the project.
2. Back end: `py -m seed.seed` (new tables, three enterprise models, four schemes). No new packages.
3. Front end: `npm run build`.
4. Back up `backend/storage/loan_docs` with the other storage folders.

## Phase 1, Sprint 4 – Enterprise set-up & procurement (M7)

Staff portal → **Enterprise set-up**. Supplier portal → **#/supplier**. Entrepreneur app → Programme → **My enterprise set-up** (from stage 4).

| Who | Can |
|---|---|
| Procurement Officer, Programme Manager, Admin | Suppliers and their portal logins, purchases, quotations, purchase orders |
| District Coordinator, DPR officer | Delivery, installation photos and handover, assets, registrations, readiness checklist |
| Coordinator, Procurement, Programme Manager, Admin | Launch a unit |
| Supplier (portal login) | See requests sent to them, send quotations (with a file), confirm orders, report delivery |

- **Unit**: created automatically when a loan is sanctioned (or an own-funds DPR is approved); approved DPRs without a unit can be started by hand. Registrations needed come from the enterprise model (e.g. Udyam, FSSAI, trade licence; drone UIN, RPC, insurance). A DGCA RPC or FSSAI certificate verified during training counts as done.
- **Suppliers (Form 7.1)**: GSTIN check, items supplied (same names as the model's equipment list, so suppliers are matched automatically), models, districts, rate card with validity, approval, delivery record (orders, on-time %). **The four starter suppliers are samples – replace them.**
- **Purchase (Form 7.2)**: starts from the approved DPR's equipment list → ask approved suppliers in the district to quote → quotations side by side (lowest per item and in total, % against the DPR estimate, delivery days, warranty, file) → choose. Choosing other than the lowest, or with only one quotation, needs a written reason, kept on the record. → **Purchase order PDF** (PO number, delivery address, terms) with payment source → supplier confirms → delivered → installation photos + handover note → the items go into the **asset register** with serial numbers and warranty dates.
- **Asset register** per unit: serial number, value, warranty, insurance, status; group units hold shared assets. Equipment the person already owns can be added by hand.
- **Readiness checklist (Form 7.3)**: equipment (every DPR item installed or in the asset register), registrations and training (MIRAI certificate or verified external certificate) are checked automatically; working capital, bookkeeping and the model's own items (branding, menu board, hygiene check, test flight…) are ticked with an optional photo. **Launch** needs every item done; the unit becomes *Launched* and the entrepreneur moves to stage 5 (Sell & deliver).
- **Entrepreneur app**: what is being bought and when it arrives, registrations (upload a document from the phone), the checklist, and their equipment with warranty dates – English / Telugu.
- **Set-up dashboard**: units setting up / launched, purchases by stage, amount ordered vs the DPR estimate, days from order to installation, pending registrations, supplier delivery record, late deliveries, units ready to launch.

### Updating to Phase 1 Sprint 4

1. Copy the changed files over the project, `git push`, then `mirai-update` on the server (it runs the seed: new tables, two new columns on enterprise models, sample suppliers). No new packages.
2. Back up `backend/storage/setup` (quotation files, installation photos, registration documents).
3. Create supplier portal logins from Enterprise set-up → Suppliers → key icon. Suppliers sign in at `https://<your site>/#/supplier`.

## Phase 1, Sprint 5 – Marketing, sales & orders (M8)

Entrepreneur app → **My shop & sales** (from stage 5). Staff portal → **Sales & marketing**, and Units → *Shop & orders*.
Customers use the **public shop** `#/shop/<unit code>` and the **order tracking** link – no login.

| Who | Can |
|---|---|
| Entrepreneur (their own or their group's unit) | Products & services, sales and orders, bookings, customers and follow-ups, posters and messages, answer buyer enquiries |
| Coordinator, Programme Manager, Admin, SHG Federation staff, Mentor | The same for units in their districts (to help), buyer enquiries, campaigns |
| Other programme staff | See shops, sales and reports in their districts |
| Customer | Order or book on the shop page, follow the order, rate it |

- **Customers** are kept separately from entrepreneurs (spec 2.2): one profile per mobile number, shared by every unit they buy from.
- **Products & services (Form 8.1)**: start from the business plan's products and DPR prices, add photos (up to 3), price per unit, availability, a daily limit and, for services, time slots with capacity (e.g. drone spraying 20 acres a slot, lunch tiffins 40 plates).
- **Orders & bookings (Form 8.2)**: quick sale on the phone (tap quantities, mobile number fills the name for known customers), status New → Confirmed → Delivered → Paid / Cancelled, cash / UPI / credit. Credit sales show as *money to collect* until paid. Bookings check the slot capacity. Online orders arrive as *New*.
- **Public shop and tracking**: launched units only, Telugu / English, shop prices only (the customer cannot change them), at most 5 online orders a day per mobile number. The customer gets a tracking link and can rate the order after delivery; ratings show on the shop.
- **Repeat-customer follow-ups**: customers who bought before and have not ordered for 14 days, with a ready WhatsApp message; *Done* hides them until their next order.
- **Posters and messages**: a 1080 × 1350 poster (PNG, with a QR code to the shop) and a WhatsApp message in Telugu or English, made from the unit's real products and prices. With an AI key the AI writes the words; otherwise a template does. Prices print as "రూ." / "Rs." on the poster.
- **Buyer enquiries**: staff record enquiries from schools, offices, hostels, caterers and market partners, see matching launched units (same district first, with ratings) and send the enquiry to them. The unit answers in the app (interested with a price, or not now); the buyer's number is shown to the unit once it is interested. "Buyer agreed – make order" creates the order; the enquiry is won and the other units are told it is closed.
- **Campaigns (Form 8.3)**: fairs, festivals, WhatsApp and institutional drives across units; units tag sales made at the campaign; results (enquiries, orders, sales) count automatically, plus numbers entered by hand for sales outside the app; a campaign message drafted from the units' products; materials upload.
- **Sales dashboard**: sales this month, units selling, credit to collect, customers and repeat %, rating, weekly sales, top units, sales by model, where orders come from, launched units with no sales yet.
- Fix: editing a training session's date (Sprint 2) now saves the date.

### Updating to Phase 1 Sprint 5

1. Copy the changed files over the project, `git push`, then `mirai-update` on the server (new tables; no new packages).
2. Back up `backend/storage/market` (product photos, posters, campaign materials).
3. `PUBLIC_URL` in `.env` must be the site address (e.g. `https://miraimsme.com`) – it is used in shop links, tracking links and poster QR codes.

## Phase 1, Sprint 6 – Daily business management (M9)

Entrepreneur app → **My accounts** (from stage 4, so bookkeeping can start before launch). Staff portal → **Sales & marketing → Business tracking**, and Units → *Accounts*.

| Who | Can |
|---|---|
| Entrepreneur (their own or their group's unit) | Record sales and expenses, stock, money to collect, receipts, EMIs paid, send monthly summaries with a note |
| Coordinator, Programme Manager, Admin, SHG Federation staff, Mentor | The same for units in their districts (to help), review monthly summaries |
| Other programme staff | See accounts and business tracking in their districts |

- **Sales and expenses (Form 9.1)**: two big buttons; amount, category from the enterprise model (millet café, tea stall, drone services – Telugu labels are a first draft), date, cash / UPI / credit, customer for credit sales (due in 7 days by default), stock item and quantity, note, bill photo. Entries can be added up to 90 days back; the entrepreneur can remove an entry within 2 days (staff later).
- **Speak or type**: "sold 40 plates for 1600 rupees cash" / "పాలు 10 లీటర్లు 520 రూపాయలు కొన్నాను" fills the form, which the person checks before saving. Rules do this without AI; with an AI key the AI helps when the rules miss the amount or type.
- **Revenue and profit kept apart**: loan EMIs, money taken home and new equipment are recorded but not counted as business costs.
- **Orders flow in (M8 → M9)**: a delivered order becomes a credit sale, a paid order a cash / UPI sale, a cancelled order is removed – no double entry.
- **Money to collect**: credit sales with due dates, overdue marked, WhatsApp reminder with the receipt link, *Got it – cash / UPI*.
- **Receipts**: A5 PDF (Telugu-safe) with a UPI QR code for unpaid amounts when the unit has a UPI ID; shared on WhatsApp by a signed link valid 60 days.
- **Stock**: starter items from the model; buying with a stock item adds stock, selling takes it out; *Used / Received / Counted*; low-stock alert once an item has been stocked.
- **Summaries**: today / this week / this month with the change against the same days before, daily bars, where the money came from and went.
- **EMI tracker**: the loan schedule from M6, next EMI, overdue EMIs; *I paid this EMI* marks the repayment and writes it in the books.
- **Monthly summary**: finished months are frozen and sent automatically (from the launch month); the entrepreneur can add a note and send again, and can send the current month from the 25th. The first summary with entries moves the entrepreneur to lifecycle stage 6.
- **Business alerts** (to the mentor and Business tracking): no entries, records on fewer than 8 days, sales down 20 % on the previous months, costs up 10 points, a loss, EMIs late or overdue, a lot of credit still to collect. Staff and mentors add a review note.
- **Readiness**: *Bookkeeping set up in the app* is now automatic – done after the first entry (an earlier tick still counts).
- The person's data export now includes their books.

### Updating to Phase 1 Sprint 6

1. Copy the changed files over the project, `git push`, then `mirai-update` on the server (new tables and columns; no new packages).
2. Units still setting up need one entry in *My accounts* before launch (bookkeeping is now an automatic readiness item).

## Phase 1, Sprint 7 – Mentoring & two-year handholding (M10)

Staff portal → **Mentoring & support** (Caseload, Support tickets, Peer cohorts, Mentoring dashboard), and Units → *Mentoring*.
Entrepreneur app → **My mentor & support** (from stage 4).

| Who | Can |
|---|---|
| Mentor | Their own units: monthly reviews, field visits, growth plans, tickets; peer sessions for their batches |
| Coordinator, Programme Manager, Admin | The same for units in their districts; assign / change mentors; close handholding; supervise and pass on tickets |
| Staff a ticket is assigned or referred to (procurement, DPR officer, sector expert …) | Work and resolve that ticket |
| Entrepreneur | See their mentor (call / WhatsApp), tick agreed actions, ask for help, confirm a fix and rate it |

- **Mentor assignment**: every unit gets a mentorship when it is created; the mentor from the person's training batch (Core EDP) is carried over. Coordinators assign or change the mentor; the history is kept. Mentors see the units they mentor even outside their districts.
- **24-month timeline** from the launch date, coloured by each month's review health, with visit markers.
- **What the mentor knows from before**: training results, skill gaps, readiness score and gaps, and the business plan (expected sales, loan, EMI).
- **Monthly review (Form 10.1)**: sales and expenses pulled from the books (M9) – the mentor can correct them (marked as corrected); loan repayment status; jobs (family / hired); Green / Amber / Red; scores 1–5; issues; actions with due dates (open actions carry over); training needed (refresher / advanced / skill upgrade – listed on the dashboard for the training team). A red rating needs at least one action. Saving marks the M9 monthly summary as reviewed.
- **Field visits** with geo-tagged photos: the phone's location when allowed, else the location the camera wrote into the photo; distance from the unit is shown.
- **Support tickets (Form 10.2)** from the app (type or speak, add a photo), a call, the navigator or the mentor. Assigned automatically by category to staff covering the district (equipment → procurement, finance → DPR officer, market / registration → coordinator, technical → sector expert, other → mentor), with the fewest open tickets; due in 2 / 5 / 10 days by priority. Referrals to sector experts, BDSPs, CA / CS, banks, suppliers. The entrepreneur confirms the fix with a rating or re-opens it; resolved tickets close themselves after 7 days. Resolution time is reported.
- **Growth plans (Form 10.3)**: goal, target and date, support needed, progress notes, achieved / dropped.
- **Peer cohorts**: monthly mentor-led sessions for each training batch, with attendance.
- **Final assessment** in the last two months (or when a unit closes): outcome, score, jobs, note; first-3 vs last-3 months' sales are recorded.
- **Lifecycle**: first review → stage 7 (Mentor & resolve); first growth plan or final assessment → stage 8 (Grow & sustain).
- Staff logins have an optional **phone** (Settings → Staff) – shown to entrepreneurs for their mentor.
- The person's data export includes their support tickets and growth plans.

### Updating to Phase 1 Sprint 7

1. Copy the changed files over the project, `git push`, then `mirai-update` on the server (new tables; existing units get their mentorship during the seed; no new packages).
2. Add each mentor's phone number in Settings → Staff, and assign mentors to launched units from the Caseload (filter "Without a mentor").

## Run it on your computer

Requirements: Python 3.12+ (3.14 works), Node 20+, MySQL 8. On Windows use `py -m pip …` and `py -m …` so packages and commands use the same Python.

```bash
# 1. Database
mysql -uroot -p -e "CREATE DATABASE mirai_shakthi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE USER 'mirai'@'localhost' IDENTIFIED BY 'your_password';
  GRANT ALL ON mirai_shakthi.* TO 'mirai'@'localhost';"

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # set DATABASE_URL password and JWT_SECRET
python -m seed.seed                                      # creates tables + starter data + admin user
uvicorn app.main:app --reload --port 8000                # API docs: http://localhost:8000/docs

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                                              # open http://localhost:5173
```

Log in with any 10-digit mobile starting 6–9; the OTP is shown on screen in development mode.

**Tests:** create an empty `mirai_test` database for the same MySQL user, then `cd backend && python -m pytest -q`.

**Turn on AI answers:** in `backend/.env` set `AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=...`, then restart.
Topic detection and answers will use the model; the rule engine and sources stay the same. If the AI call fails, the app falls back to the demo composer automatically.

## Android app

The Android project is in `frontend/android` (Capacitor). On a computer with Android Studio:

```bash
cd frontend
cp .env.android.example .env.production     # set VITE_API_BASE to your live API, e.g. https://app.your-domain.in
npm run build
npx cap sync android
npx cap open android                        # Android Studio → Build → Build APK(s)
```

Add `capacitor://localhost` and `https://localhost` to `CORS_ORIGINS` in the backend `.env` (already in the example).

## Deploy on the Hostinger KVM VPS (Ubuntu)

1. Install `python3-venv`, `mysql-server`, `nginx`, `nodejs`, `certbot`.
2. Copy the project to `/opt/mirai-shakthi`; create the database and `.env` as above with `APP_ENV=production`,
   `OTP_DEV_MODE=false`, MSG91 keys, a long `JWT_SECRET`, and a strong `ADMIN_PASSWORD`.
3. `python -m seed.seed`, then install `deploy/mirai-api.service` as a systemd service.
4. `cd frontend && npm ci && npm run build`; install `deploy/nginx-mirai.conf`; run certbot for HTTPS.
5. Set MySQL time zone to UTC (`default-time-zone='+00:00'`) so stored times are consistent.

## Project layout

```
backend/
  app/
    main.py               FastAPI app and routers
    models.py             MySQL tables (users, profiles, intents, rules, knowledge, sessions, experts…)
    guidance/engine.py    the five-step flow
    guidance/intents.py   topic detection (keywords, or AI when enabled)
    guidance/rules.py     safe condition language for requirement rules
    guidance/retrieval.py MySQL FULLTEXT search over published, in-date content
    guidance/llm.py       AI provider wrapper + personal-data masking
    artefacts/statement.py bank statement reader (Excel, CSV, PDF)
    connect/              Handholding workflow (statuses, transitions, reply-by time) and shared request view
    routers/              auth, profile, guidance, admin, artefacts, connect (user), expert APIs
  seed/                   starter (sample) data and loader
  schema.sql              same tables as plain SQL
  tests/                  API tests
frontend/
  src/pages/              Login, Profile wizard, Home, Chat, History, Documents, Requests
  src/expert/ExpertApp.tsx  expert workspace (#/expert)
  src/admin/              admin portal (#/admin)
  src/voice.ts            voice input (Android plugin or browser speech recognition)
  src/components/GuidanceView.tsx   renders the five steps
  android/                Capacitor Android project
docs/                     demo script and Android test checklist
deploy/                   systemd service and nginx config
```

## Phase 0 sprints

| Sprint | Scope |
|---|---|
| ~~2~~ | ✅ Done – admin portal and desktop layout |
| ~~3~~ | ✅ Done – roadmap, checklist, cash-flow summary and job description PDFs (bank-statement upload moves to Sprint 5) |
| ~~4~~ | ✅ Done – Handholding: send case to expert (G-6), expert workspace (E1), request queue (A5), status tracking (G10) |
| ~~5~~ | ✅ Done – Telugu content and voice input, bank-statement / Excel / PDF upload for MicroFin, low-end phone optimisation and APK test checklist, demo data and script |
