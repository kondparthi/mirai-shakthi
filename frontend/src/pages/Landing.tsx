// Public landing page (first screen for visitors who are not logged in).
// Explains the service from the MSME owner's point of view and leads to Register / Log in (the mobile + OTP screen).
// Telugu copy is a draft for MIRAI's team to review, like the rest of the app.
import {
  ArrowRight, BadgeCheck, Briefcase, CheckCircle2, ChevronDown, ClipboardList, Coffee, FileSpreadsheet, FileText, Fish,
  GraduationCap, HandHeart, Handshake, Hotel, IndianRupee, Languages, Laptop, ListChecks, Lock, Menu, Mic, Palette,
  Rocket, Scissors, Search, ShieldCheck, Shirt, ShoppingBag, Smartphone, Sparkles, Sprout, Star, Store, Truck, Users,
  Utensils, Wallet, Wrench, X, type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { LangToggle } from "../App";
import Logo from "../components/Logo";
import { useLang } from "../i18n";
import "../landing.css";

/* ------------------------------------------------------------------ copy */
type Copy = typeof EN;

const EN = {
  nav: { how: "How it works", services: "Services", tools: "Tools", experts: "Experts", faq: "FAQ", login: "Log in", register: "Register", menu: "Menu" },
  hero: {
    badge: "For small businesses in Andhra Pradesh",
    title: "Your business questions, answered step by step.",
    lead: "Registrations, loans, cash flow, selling, staff and schemes. Ask in Telugu or English, by typing or speaking, and get clear next steps and the right expert.",
    register: "Register with your mobile",
    login: "Log in",
    note: "Only your mobile number and an OTP. No password.",
    trust: ["Telugu & English", "Ask by voice", "Works on any phone", "Private & secure"],
  },
  phone: {
    question: "Do I need GST registration?",
    steps: [["Understanding", "GST registration · Launch Pad"], ["What you have", "Missing: GST, Udyam"], ["Information", "Needed above the turnover limit and for sales to other states."], ["Next steps", "1. Udyam – same day, free\n2. GST – about 1–2 weeks"], ["Talk to an expert", ""]] as [string, string][],
    expert: "CA · Guntur · replies in 24 hours",
    request: "Request help",
    float: ["Speak in Telugu", "Expert accepted your case", "Quote ₹1,500"],
  },
  stats: [["5", "service areas"], ["18", "business topics"], ["2", "languages"], ["5", "steps in every answer"]] as [string, string][],
  sectors: { title: "Built for every kind of small business", items: ["Food processing", "Tailoring & garments", "Handloom", "Agri & drone services", "Repairs", "Shops & trading", "Beauty & wellness", "Transport", "Tea & food stalls", "Fisheries", "Crafts", "Homestays", "Digital services"] },
  how: {
    kicker: "How it works",
    title: "Every answer follows the same five steps",
    lead: "You always know what applies to your business, what is missing and what to do next.",
    steps: [
      ["We understand your question", "The topic is found and your business details are used: what you make, where, how big, and what you already have."],
      ["We check what is missing", "For example: you have Udyam, but GST and an FSSAI licence are still missing for your food business."],
      ["You get verified information", "Answers come only from information checked by the MIRAI team, with the source shown."],
      ["You get clear next steps", "Documents to keep ready, the time it takes, the cost and the official website. Tick them off as you go."],
      ["An expert can do it for you", "Send your case to a CA, consultant, bank or trainer near you, and follow it until it is done."],
    ] as [string, string][],
  },
  services: {
    kicker: "Services",
    title: "One place for every business question",
    lead: "Five service areas, built around what small business owners ask most.",
    items: [
      { code: "microfin", name: "MicroFin", what: "Money and loans", topics: ["Cash flow & profit", "Bank loans", "Working capital", "Unpaid customers"] },
      { code: "marketkonnect", name: "MarketKonnect", what: "Selling more", topics: ["Amazon & ONDC", "Government buyers (GeM)", "Labels & packaging", "Finding buyers"] },
      { code: "launchpad", name: "Launch Pad / Export Ready", what: "Registrations, schemes & export", topics: ["Udyam, GST, FSSAI", "Government schemes", "Start exporting"] },
      { code: "skillspro", name: "SkillsPro", what: "Staff and training", topics: ["Hiring workers", "PF, ESI & labour rules", "EDP & skill training"] },
      { code: "handholding", name: "Handholding", what: "Experts and mentors", topics: ["Project report (DPR)", "Talk to a CA", "Banks & consultants"] },
    ],
  },
  tools: {
    kicker: "Tools",
    title: "Papers you can make in a few minutes",
    items: [
      { title: "Cash-flow summary from your bank statement", body: "Upload the statement from net banking: Excel, CSV or PDF, even password-protected. Sales, expenses and profit are worked out month by month. The file is never saved.", points: ["Loan money and interest are not counted as sales", "EMIs are added as loans automatically", "Download a PDF for your bank or CA"] },
      { title: "Roadmap and document checklist", body: "Turn any answer into a printable plan: every step with documents, time, cost and official links, plus one checklist of all documents.", points: ["No repeated documents", "Tick off steps as you finish", "Share with your CA on WhatsApp"] },
      { title: "Job description for new staff", body: "Pick a role, add pay and hours, and share a clear job description with the people you want to hire, with a first-week plan.", points: ["Helper, sales, accounts, delivery and more", "Minimum wage reminder", "Ready to print or share"] },
    ],
    mock: { file: "statement.xlsx", found: "145 transactions read", sales: "Sales", expenses: "Expenses", roadmap: "Roadmap – GST registration", jd: "Drone spraying assistant", pay: "₹12,000 / month", pdf: "PDF" },
  },
  experts: {
    kicker: "Experts",
    title: "When you need a person, not just an answer",
    lead: "Send your case to an expert approved by MIRAI and follow every step on your phone, like tracking a parcel.",
    types: ["Chartered Accountants", "Company Secretaries", "Banks", "Business consultants", "Trainers", "Legal advisors"],
    promises: [
      ["You decide what to share", "Nothing goes to an expert without your consent."],
      ["Your number stays private", "The expert sees your mobile number only after accepting your case."],
      ["No case is left waiting", "If an expert declines or does not reply in time, MIRAI moves your case to another expert."],
    ] as [string, string][],
    track: { title: "GST registration", who: "CA · Guntur", steps: ["Case sent", "Expert accepted", "Quote ₹1,500 accepted", "Work completed"], rated: "You rated 5 stars" },
  },
  made: {
    kicker: "Made for you",
    title: "Simple enough for a busy day",
    items: [
      ["Telugu or English", "Switch the whole app with one tap. Speak your question if typing is hard."],
      ["Works on any phone", "Android app and website. Light enough for basic phones and slow mobile data."],
      ["Your information stays yours", "Your details are used only to guide you. Account numbers in bank statements are hidden."],
    ] as [string, string][],
  },
  faq: {
    kicker: "FAQ",
    title: "Common questions",
    items: [
      ["Who is MIRAI Shakthi for?", "Micro and small business owners, and people planning to start one: food units, tailoring, handloom, repairs, agriculture services, shops and more."],
      ["Do I need any documents to start?", "No. Register with your mobile number and answer a few questions about your business. It takes about a minute."],
      ["Will the answers fit my business?", "Yes. The steps change with your business type, district, size and the registrations you already have."],
      ["Are the experts real people?", "Yes. Experts and institutions are approved by the MIRAI team before you see them, and owners rate them after each case."],
      ["Can I use it in Telugu?", "Yes. The whole app works in Telugu and English, and you can speak your question in either language."],
    ] as [string, string][],
  },
  end: { title: "Start with one question", lead: "Register with your mobile number. Your first answer is a minute away.", register: "Register now", login: "I already have an account" },
  footer: { tagline: "Step-by-step guidance and trusted experts for small businesses in Andhra Pradesh.", explore: "Explore", portals: "Portals", experts: "Expert login", team: "MIRAI team login", rights: "MIRAI Shakthi. All rights reserved." },
};

const TE: Copy = {
  nav: { how: "ఎలా పని చేస్తుంది", services: "సేవలు", tools: "సాధనాలు", experts: "నిపుణులు", faq: "ప్రశ్నలు", login: "లాగిన్", register: "నమోదు", menu: "మెనూ" },
  hero: {
    badge: "ఆంధ్రప్రదేశ్ చిన్న వ్యాపారుల కోసం",
    title: "మీ వ్యాపార ప్రశ్నలకు దశలవారీ సమాధానాలు.",
    lead: "రిజిస్ట్రేషన్లు, రుణాలు, నగదు ప్రవాహం, అమ్మకాలు, సిబ్బంది, పథకాలు. తెలుగులో లేదా ఇంగ్లీషులో టైప్ చేసి లేదా మాట్లాడి అడగండి – స్పష్టమైన తదుపరి దశలు, సరైన నిపుణుడు మీకు దొరుకుతారు.",
    register: "మొబైల్‌తో నమోదు చేసుకోండి",
    login: "లాగిన్",
    note: "మొబైల్ నంబర్, OTP మాత్రమే. పాస్‌వర్డ్ లేదు.",
    trust: ["తెలుగు & ఇంగ్లీషు", "మాట్లాడి అడగండి", "ఏ ఫోన్‌లోనైనా", "సురక్షితం"],
  },
  phone: {
    question: "నాకు జీఎస్టీ రిజిస్ట్రేషన్ అవసరమా?",
    steps: [["అవగాహన", "జీఎస్టీ రిజిస్ట్రేషన్ · లాంచ్ ప్యాడ్"], ["మీ దగ్గర ఉన్నవి", "లేనివి: జీఎస్టీ, ఉద్యమ్"], ["సమాచారం", "టర్నోవర్ పరిమితి దాటితే, ఇతర రాష్ట్రాలకు అమ్మితే అవసరం."], ["తదుపరి దశలు", "1. ఉద్యమ్ – అదే రోజు, ఉచితం\n2. జీఎస్టీ – సుమారు 1–2 వారాలు"], ["నిపుణుడితో మాట్లాడండి", ""]],
    expert: "సీఏ · గుంటూరు · 24 గంటల్లో స్పందన",
    request: "సహాయం అడగండి",
    float: ["తెలుగులో మాట్లాడండి", "నిపుణుడు అంగీకరించారు", "కొటేషన్ ₹1,500"],
  },
  stats: [["5", "సేవా విభాగాలు"], ["18", "వ్యాపార అంశాలు"], ["2", "భాషలు"], ["5", "ప్రతి సమాధానంలో దశలు"]],
  sectors: { title: "అన్ని రకాల చిన్న వ్యాపారాల కోసం", items: ["ఆహార తయారీ", "టైలరింగ్ & దుస్తులు", "చేనేత", "వ్యవసాయ & డ్రోన్ సేవలు", "మరమ్మతులు", "దుకాణాలు & వ్యాపారం", "బ్యూటీ & వెల్‌నెస్", "రవాణా", "టీ & ఫుడ్ స్టాల్స్", "మత్స్య", "హస్తకళలు", "హోమ్‌స్టేలు", "డిజిటల్ సేవలు"] },
  how: {
    kicker: "ఎలా పని చేస్తుంది",
    title: "ప్రతి సమాధానం ఒకే ఐదు దశల్లో",
    lead: "మీ వ్యాపారానికి ఏది వర్తిస్తుంది, ఏది లేదు, తర్వాత ఏమి చేయాలి – ఎప్పుడూ స్పష్టంగా తెలుస్తుంది.",
    steps: [
      ["మీ ప్రశ్నను అర్థం చేసుకుంటాం", "అంశాన్ని గుర్తించి మీ వ్యాపార వివరాలు వాడతాం: మీరు ఏమి తయారు చేస్తారు, ఎక్కడ, ఎంత పెద్దది, మీ దగ్గర ఏమి ఉంది."],
      ["ఏమి లేదో చూస్తాం", "ఉదాహరణకు: మీకు ఉద్యమ్ ఉంది, కానీ మీ ఆహార వ్యాపారానికి జీఎస్టీ, ఎఫ్ఎస్ఎస్ఏఐ లైసెన్స్ ఇంకా లేవు."],
      ["ధృవీకరించిన సమాచారం", "మిరాయ్ బృందం తనిఖీ చేసిన సమాచారం నుండి మాత్రమే సమాధానం, మూలంతో సహా."],
      ["స్పష్టమైన తదుపరి దశలు", "కావలసిన పత్రాలు, పట్టే సమయం, ఖర్చు, అధికారిక వెబ్‌సైట్. పూర్తయినవి టిక్ చేసుకోండి."],
      ["నిపుణుడు చేసి పెడతారు", "మీ దగ్గరలోని సీఏ, కన్సల్టెంట్, బ్యాంకు లేదా శిక్షకుడికి మీ కేసు పంపి, పూర్తయ్యే వరకు చూసుకోండి."],
    ],
  },
  services: {
    kicker: "సేవలు",
    title: "ప్రతి వ్యాపార ప్రశ్నకు ఒకే చోటు",
    lead: "చిన్న వ్యాపారులు ఎక్కువగా అడిగే వాటి చుట్టూ ఐదు సేవా విభాగాలు.",
    items: [
      { code: "microfin", name: "మైక్రోఫిన్", what: "డబ్బు, రుణాలు", topics: ["నగదు ప్రవాహం & లాభం", "బ్యాంకు రుణాలు", "వర్కింగ్ క్యాపిటల్", "చెల్లించని కస్టమర్లు"] },
      { code: "marketkonnect", name: "మార్కెట్ కనెక్ట్", what: "ఎక్కువ అమ్మకాలు", topics: ["అమెజాన్ & ఓఎన్‌డీసీ", "ప్రభుత్వ కొనుగోలు (జెమ్)", "లేబుల్ & ప్యాకేజింగ్", "కొనుగోలుదారులు"] },
      { code: "launchpad", name: "లాంచ్ ప్యాడ్ / ఎగుమతి", what: "రిజిస్ట్రేషన్లు, పథకాలు, ఎగుమతి", topics: ["ఉద్యమ్, జీఎస్టీ, ఎఫ్ఎస్ఎస్ఏఐ", "ప్రభుత్వ పథకాలు", "ఎగుమతి ప్రారంభం"] },
      { code: "skillspro", name: "స్కిల్స్ ప్రో", what: "సిబ్బంది, శిక్షణ", topics: ["పనివారి నియామకం", "పీఎఫ్, ఈఎస్ఐ & కార్మిక నియమాలు", "ఈడీపీ & నైపుణ్య శిక్షణ"] },
      { code: "handholding", name: "హ్యాండ్‌హోల్డింగ్", what: "నిపుణులు, మెంటార్లు", topics: ["ప్రాజెక్ట్ రిపోర్ట్ (డీపీఆర్)", "సీఏతో మాట్లాడండి", "బ్యాంకులు & కన్సల్టెంట్లు"] },
    ],
  },
  tools: {
    kicker: "సాధనాలు",
    title: "కొన్ని నిమిషాల్లో తయారు చేసుకునే పత్రాలు",
    items: [
      { title: "బ్యాంకు స్టేట్‌మెంట్ నుండి నగదు ప్రవాహ సారాంశం", body: "నెట్ బ్యాంకింగ్ స్టేట్‌మెంట్ (ఎక్సెల్, CSV లేదా PDF – పాస్‌వర్డ్ ఉన్నా) అప్‌లోడ్ చేయండి. నెలవారీ అమ్మకాలు, ఖర్చులు, లాభం లెక్కిస్తాం. ఫైల్ ఎప్పుడూ సేవ్ చేయము.", points: ["రుణ డబ్బు, వడ్డీ అమ్మకాలుగా లెక్కించము", "ఈఎంఐలు రుణాలుగా ఆటోమేటిక్‌గా జోడిస్తాం", "బ్యాంకు లేదా సీఏ కోసం PDF"] },
      { title: "రోడ్‌మ్యాప్, పత్రాల జాబితా", body: "ఏ సమాధానాన్నైనా ప్రింట్ చేయగల ప్రణాళికగా మార్చండి: పత్రాలు, సమయం, ఖర్చు, అధికారిక లింకులతో ప్రతి దశ, అన్ని పత్రాల ఒకే జాబితా.", points: ["పత్రాలు రెండుసార్లు రావు", "పూర్తయిన దశలు టిక్ చేసుకోండి", "వాట్సాప్‌లో సీఏకి పంపండి"] },
      { title: "కొత్త సిబ్బందికి ఉద్యోగ వివరణ", body: "పని ఎంచుకుని, జీతం, వేళలు జోడించి, మొదటి వారం ప్రణాళికతో స్పష్టమైన ఉద్యోగ వివరణ పంపండి.", points: ["హెల్పర్, సేల్స్, అకౌంట్స్, డెలివరీ మరిన్ని", "కనీస వేతనం గుర్తు", "ప్రింట్ లేదా షేర్ చేయడానికి సిద్ధం"] },
    ],
    mock: { file: "statement.xlsx", found: "145 లావాదేవీలు చదివాం", sales: "అమ్మకాలు", expenses: "ఖర్చులు", roadmap: "రోడ్‌మ్యాప్ – జీఎస్టీ రిజిస్ట్రేషన్", jd: "డ్రోన్ స్ప్రేయింగ్ సహాయకుడు", pay: "₹12,000 / నెల", pdf: "PDF" },
  },
  experts: {
    kicker: "నిపుణులు",
    title: "సమాధానం కాదు, మనిషి సహాయం కావాలంటే",
    lead: "మిరాయ్ ఆమోదించిన నిపుణుడికి మీ కేసు పంపి, పార్సెల్ ట్రాక్ చేసినట్టు ప్రతి దశను మీ ఫోన్‌లో చూసుకోండి.",
    types: ["చార్టర్డ్ అకౌంటెంట్లు", "కంపెనీ సెక్రటరీలు", "బ్యాంకులు", "వ్యాపార కన్సల్టెంట్లు", "శిక్షకులు", "న్యాయ సలహాదారులు"],
    promises: [
      ["ఏమి పంచుకోవాలో మీరే నిర్ణయిస్తారు", "మీ అనుమతి లేకుండా ఏదీ నిపుణుడికి వెళ్లదు."],
      ["మీ నంబర్ సురక్షితం", "కేసు అంగీకరించిన తర్వాతే నిపుణుడికి మీ మొబైల్ నంబర్ కనిపిస్తుంది."],
      ["ఏ కేసూ ఆగిపోదు", "నిపుణుడు తిరస్కరించినా, సమయానికి స్పందించకపోయినా, మిరాయ్ మీ కేసును మరో నిపుణుడికి మారుస్తుంది."],
    ],
    track: { title: "జీఎస్టీ రిజిస్ట్రేషన్", who: "సీఏ · గుంటూరు", steps: ["కేసు పంపారు", "నిపుణుడు అంగీకరించారు", "₹1,500 కొటేషన్ అంగీకరించారు", "పని పూర్తయింది"], rated: "మీరు 5 నక్షత్రాలు ఇచ్చారు" },
  },
  made: {
    kicker: "మీ కోసం",
    title: "బిజీ రోజులోనూ సులభంగా",
    items: [
      ["తెలుగు లేదా ఇంగ్లీషు", "ఒక్క నొక్కుతో యాప్ భాష మార్చండి. టైప్ చేయడం కష్టమైతే మాట్లాడి అడగండి."],
      ["ఏ ఫోన్‌లోనైనా", "ఆండ్రాయిడ్ యాప్, వెబ్‌సైట్. సాధారణ ఫోన్లు, నెమ్మదైన డేటాలోనూ పనిచేస్తుంది."],
      ["మీ సమాచారం మీదే", "మీకు దారి చూపడానికి మాత్రమే మీ వివరాలు వాడతాం. బ్యాంకు స్టేట్‌మెంట్‌లో ఖాతా నంబర్లు దాచబడతాయి."],
    ],
  },
  faq: {
    kicker: "ప్రశ్నలు",
    title: "తరచుగా అడిగే ప్రశ్నలు",
    items: [
      ["మిరాయ్ శక్తి ఎవరి కోసం?", "సూక్ష్మ, చిన్న వ్యాపారులు, వ్యాపారం ప్రారంభించాలనుకునే వారు: ఆహార యూనిట్లు, టైలరింగ్, చేనేత, మరమ్మతులు, వ్యవసాయ సేవలు, దుకాణాలు మొదలైనవి."],
      ["ప్రారంభించడానికి పత్రాలు కావాలా?", "అక్కర్లేదు. మొబైల్ నంబర్‌తో నమోదు చేసుకుని, మీ వ్యాపారం గురించి కొన్ని ప్రశ్నలకు జవాబివ్వండి. సుమారు ఒక నిమిషం."],
      ["సమాధానాలు నా వ్యాపారానికి సరిపోతాయా?", "అవును. మీ వ్యాపార రకం, జిల్లా, పరిమాణం, మీ దగ్గర ఉన్న రిజిస్ట్రేషన్లను బట్టి దశలు మారుతాయి."],
      ["నిపుణులు నిజమైన వ్యక్తులేనా?", "అవును. మీకు చూపే ముందు మిరాయ్ బృందం నిపుణులను ఆమోదిస్తుంది. ప్రతి కేసు తర్వాత వ్యాపారులు రేటింగ్ ఇస్తారు."],
      ["తెలుగులో వాడవచ్చా?", "అవును. యాప్ మొత్తం తెలుగు, ఇంగ్లీషులో పనిచేస్తుంది. రెండు భాషల్లోనూ మాట్లాడి అడగవచ్చు."],
    ],
  },
  end: { title: "ఒక్క ప్రశ్నతో మొదలుపెట్టండి", lead: "మొబైల్ నంబర్‌తో నమోదు చేసుకోండి. మీ మొదటి సమాధానం ఒక్క నిమిషం దూరంలో.", register: "ఇప్పుడే నమోదు చేసుకోండి", login: "నాకు ఇప్పటికే ఖాతా ఉంది" },
  footer: { tagline: "ఆంధ్రప్రదేశ్ చిన్న వ్యాపారులకు దశలవారీ మార్గదర్శనం, నమ్మకమైన నిపుణులు.", explore: "చూడండి", portals: "పోర్టల్స్", experts: "నిపుణుల లాగిన్", team: "మిరాయ్ బృందం లాగిన్", rights: "మిరాయ్ శక్తి. సర్వహక్కులు ప్రత్యేకించబడినవి." },
};

/* ------------------------------------------------------------------ icons per item */
const TRUST_ICONS: LucideIcon[] = [Languages, Mic, Smartphone, Lock];
const SECTOR_ICONS: LucideIcon[] = [Utensils, Scissors, Shirt, Sprout, Wrench, Store, Sparkles, Truck, Coffee, Fish, Palette, Hotel, Laptop];
const STEP_ICONS: LucideIcon[] = [Search, ListChecks, BadgeCheck, ClipboardList, Handshake];
const SERVICE_ICONS: Record<string, LucideIcon> = { microfin: Wallet, marketkonnect: ShoppingBag, launchpad: Rocket, skillspro: GraduationCap, handholding: HandHeart };
const MADE_ICONS: LucideIcon[] = [Languages, Smartphone, ShieldCheck];
const EXPERT_ICONS: LucideIcon[] = [Briefcase, FileText, IndianRupee, Users, GraduationCap, ShieldCheck];

/* ------------------------------------------------------------------ helpers */
/** Fades a block in the first time it scrolls into view (skipped when the visitor prefers reduced motion). */
function Reveal({ children, className = "", delay = 0, as: Tag = "div" }: { children: ReactNode; className?: string; delay?: number; as?: "div" | "li" | "section" }) {
  const ref = useRef<HTMLElement | null>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") { setShown(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setShown(true); io.disconnect(); } }, { threshold: 0.15, rootMargin: "0px 0px -40px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return <Tag ref={ref as never} className={`lp-reveal ${shown ? "in" : ""} ${className}`} style={{ transitionDelay: `${delay}ms` }}>{children}</Tag>;
}

const goTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

function SectionHead({ kicker, title, lead, light = false, center = false }: { kicker: string; title: string; lead?: string; light?: boolean; center?: boolean }) {
  return (
    <Reveal className={`lp-head ${light ? "light" : ""} ${center ? "center" : ""}`}>
      <span className="lp-kicker">{kicker}</span>
      <h2>{title}</h2>
      {lead && <p>{lead}</p>}
    </Reveal>
  );
}

/* ------------------------------------------------------------------ hero visual */
function PhoneDemo({ c }: { c: Copy["phone"] }) {
  const cls = ["s1", "s2", "s3", "s4", "s5"];
  return (
    <div className="lp-visual" aria-label={`${c.question} – ${c.steps.map(([h]) => h).join(", ")}`} role="img">
      <div className="lp-glow" aria-hidden="true" />
      <div className="lp-phone" aria-hidden="true">
        <div className="lp-notch" />
        <div className="lp-phone-screen">
          <div className="lp-q"><span className="lp-mic"><Mic size={14} /></span>{c.question}</div>
          <ol className="lp-answer">
            {c.steps.map(([head, body], i) => (
              <li key={head} className={`lp-a ${cls[i]}`} style={{ animationDelay: `${0.5 + i * 0.3}s` }}>
                <b>{i + 1} · {head}</b>
                {body && <span>{body}</span>}
                {i === 4 && (
                  <span className="lp-expert"><span className="lp-avatar">CA</span><span className="lp-expert-name">{c.expert}</span><span className="lp-chip">{c.request}</span></span>
                )}
              </li>
            ))}
          </ol>
        </div>
      </div>
      <div className="lp-float f1" aria-hidden="true"><span className="ico red"><Mic size={16} /></span>{c.float[0]}</div>
      <div className="lp-float f2" aria-hidden="true"><span className="ico green"><CheckCircle2 size={16} /></span>{c.float[1]}</div>
      <div className="lp-float f3" aria-hidden="true"><span className="ico gold"><IndianRupee size={16} /></span>{c.float[2]}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ tool mock-ups */
function CashflowMock({ m }: { m: Copy["tools"]["mock"] }) {
  const months = [[69, 86], [82, 87], [78, 91], [77, 87], [79, 87], [80, 92]];
  return (
    <div className="lp-mock" aria-hidden="true">
      <div className="lp-mock-file"><span className="ico green"><FileSpreadsheet size={18} /></span><div><b>{m.file}</b><small>{m.found}</small></div><CheckCircle2 size={20} className="ok" /></div>
      <div className="lp-bars">
        {months.map(([s, e], i) => (
          <div key={i} className="lp-bar-pair"><span className="bs" style={{ height: `${s}%` }} /><span className="be" style={{ height: `${e}%` }} /></div>
        ))}
      </div>
      <div className="lp-legend"><span><i className="bs" />{m.sales}</span><span><i className="be" />{m.expenses}</span></div>
    </div>
  );
}
function RoadmapMock({ m }: { m: Copy["tools"]["mock"] }) {
  return (
    <div className="lp-mock lp-doc" aria-hidden="true">
      <div className="lp-doc-head"><b>{m.roadmap}</b><span className="lp-pdf">{m.pdf}</span></div>
      {["Udyam", "GST", "Bank account", "FSSAI"].map((x, i) => (
        <div key={x} className={`lp-doc-row ${i < 2 ? "done" : ""}`}><span className="box">{i < 2 && <CheckCircle2 size={14} />}</span><span className="line" style={{ width: `${86 - i * 9}%` }} /></div>
      ))}
      <div className="lp-doc-foot"><span /><span /><span /></div>
    </div>
  );
}
function JdMock({ m }: { m: Copy["tools"]["mock"] }) {
  return (
    <div className="lp-mock lp-jd" aria-hidden="true">
      <div className="lp-jd-top"><span className="ico gold"><Briefcase size={18} /></span><div><b>{m.jd}</b><small>{m.pay}</small></div></div>
      <div className="lp-jd-chips"><span>6 am – 2 pm</span><span>Guntur</span><span>2 openings</span></div>
      <div className="lp-jd-lines"><span /><span /><span /></div>
    </div>
  );
}

/* ------------------------------------------------------------------ FAQ item with a smooth open/close */
function Faq({ q, a, open, onToggle, id }: { q: string; a: string; open: boolean; onToggle: () => void; id: string }) {
  return (
    <div className={`lp-faq-item ${open ? "open" : ""}`}>
      <button className="lp-faq-q" aria-expanded={open} aria-controls={id} onClick={onToggle}>
        <span>{q}</span><ChevronDown size={20} aria-hidden="true" />
      </button>
      <div className="lp-faq-a" id={id} role="region"><div><p>{a}</p></div></div>
    </div>
  );
}

/* ------------------------------------------------------------------ page */
export default function Landing() {
  const { lang } = useLang();
  const c = lang === "te" ? TE : EN;
  const [scrolled, setScrolled] = useState(false);
  const [menu, setMenu] = useState(false);
  const [openFaq, setOpenFaq] = useState(0);

  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 24);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  useEffect(() => { document.body.style.overflow = menu ? "hidden" : ""; return () => { document.body.style.overflow = ""; }; }, [menu]);

  const nav: [string, string][] = [["how", c.nav.how], ["services", c.nav.services], ["tools", c.nav.tools], ["experts", c.nav.experts], ["faq", c.nav.faq]];
  const jump = (id: string) => { setMenu(false); setTimeout(() => goTo(id), 10); };
  const sectorRow = c.sectors.items.map((s, i) => ({ s, Icon: SECTOR_ICONS[i] ?? Store }));

  return (
    <div className="lp">
      {/* ------------------------------------------------ navigation */}
      <header className={`lp-nav ${scrolled || menu ? "solid" : ""}`}>
        <div className="lp-wrap lp-nav-in">
          <button className="lp-logo-btn" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} aria-label="MIRAI Shakthi – top">
            <Logo tone={scrolled || menu ? "dark" : "light"} size={38} />
          </button>
          <nav className="lp-links" aria-label="Sections">
            {nav.map(([id, label]) => <button key={id} onClick={() => goTo(id)}>{label}</button>)}
          </nav>
          <div className="lp-nav-actions">
            <span className="lp-lang"><LangToggle /></span>
            <Link to="/login" className="lp-nav-login">{c.nav.login}</Link>
            <Link to="/login?new=1" className="lp-cta small">{c.nav.register}</Link>
            <button className="lp-burger" aria-label={c.nav.menu} aria-expanded={menu} onClick={() => setMenu(!menu)}>{menu ? <X size={24} /> : <Menu size={24} />}</button>
          </div>
        </div>
        {menu && (
          <div className="lp-mobile-menu">
            {nav.map(([id, label]) => <button key={id} onClick={() => jump(id)}>{label}</button>)}
            <Link to="/login" className="lp-ghost-btn">{c.nav.login}</Link>
            <Link to="/login?new=1" className="lp-cta">{c.hero.register}</Link>
          </div>
        )}
      </header>

      <main>
        {/* ------------------------------------------------ hero */}
        <section className="lp-hero">
          <div className="lp-aurora" aria-hidden="true"><span className="a1" /><span className="a2" /><span className="a3" /><span className="lp-grid" /></div>
          <div className="lp-wrap lp-hero-in">
            <div className="lp-hero-text">
              <span className="lp-badge"><Sparkles size={15} />{c.hero.badge}</span>
              <h1>{c.hero.title}</h1>
              <p className="lp-lead">{c.hero.lead}</p>
              <div className="lp-ctas">
                <Link to="/login?new=1" className="lp-cta">{c.hero.register}<ArrowRight size={18} aria-hidden="true" /></Link>
                <Link to="/login" className="lp-glass-btn">{c.hero.login}</Link>
              </div>
              <p className="lp-note">{c.hero.note}</p>
              <ul className="lp-trust">
                {c.hero.trust.map((t, i) => { const Icon = TRUST_ICONS[i] ?? Lock; return <li key={t}><Icon size={17} aria-hidden="true" />{t}</li>; })}
              </ul>
            </div>
            <PhoneDemo c={c.phone} />
          </div>
          <svg className="lp-wave" viewBox="0 0 1440 90" preserveAspectRatio="none" aria-hidden="true"><path d="M0 60C240 100 480 20 720 40s480 60 720 20V90H0z" fill="#fff" /></svg>
        </section>

        {/* ------------------------------------------------ stats */}
        <section className="lp-stats-wrap">
          <div className="lp-wrap">
            <Reveal className="lp-stats">
              {c.stats.map(([n, l]) => <div key={l}><b>{n}</b><span>{l}</span></div>)}
            </Reveal>
          </div>
        </section>

        {/* ------------------------------------------------ sectors marquee */}
        <section className="lp-sectors" aria-label={c.sectors.title}>
          <p className="lp-sectors-title">{c.sectors.title}</p>
          <div className="lp-marquee">
            <div className="lp-track">
              {[0, 1].map((k) => (
                <ul key={k} aria-hidden={k === 1}>
                  {sectorRow.map(({ s, Icon }) => <li key={s}><Icon size={18} aria-hidden="true" />{s}</li>)}
                </ul>
              ))}
            </div>
          </div>
        </section>

        {/* ------------------------------------------------ how it works */}
        <section className="lp-section" id="how">
          <div className="lp-wrap">
            <SectionHead kicker={c.how.kicker} title={c.how.title} lead={c.how.lead} center />
            <ol className="lp-steps">
              {c.how.steps.map(([h, b], i) => {
                const Icon = STEP_ICONS[i] ?? Search;
                return (
                  <Reveal as="li" key={h} className={`lp-step s${i + 1}`} delay={i * 90}>
                    <span className="lp-step-icon"><Icon size={26} aria-hidden="true" /><em>{i + 1}</em></span>
                    <h3>{h}</h3>
                    <p>{b}</p>
                  </Reveal>
                );
              })}
            </ol>
          </div>
        </section>

        {/* ------------------------------------------------ services */}
        <section className="lp-section soft" id="services">
          <div className="lp-wrap">
            <SectionHead kicker={c.services.kicker} title={c.services.title} lead={c.services.lead} center />
            <div className="lp-services">
              {c.services.items.map((s, i) => {
                const Icon = SERVICE_ICONS[s.code];
                return (
                  <Reveal key={s.code} className={`lp-service ${s.code}`} delay={i * 80}>
                    <span className="lp-service-icon"><Icon size={28} aria-hidden="true" /></span>
                    <h3>{s.name}</h3>
                    <p className="lp-service-what">{s.what}</p>
                    <ul>{s.topics.map((t) => <li key={t}><CheckCircle2 size={15} aria-hidden="true" />{t}</li>)}</ul>
                  </Reveal>
                );
              })}
              <Reveal className="lp-service ask" delay={400}>
                <span className="lp-service-icon"><Mic size={28} aria-hidden="true" /></span>
                <h3>{lang === "te" ? "మీ ప్రశ్న అడగండి" : "Just ask"}</h3>
                <p className="lp-service-what">{lang === "te" ? "ఏ విభాగమో తెలియకపోయినా పర్వాలేదు – మీ మాటల్లో అడగండి, సరైన అంశాన్ని యాప్ కనుగొంటుంది." : "Not sure which area? Ask in your own words and the app finds the right topic."}</p>
                <Link to="/login?new=1" className="lp-cta small">{c.nav.register}<ArrowRight size={16} aria-hidden="true" /></Link>
              </Reveal>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------ tools */}
        <section className="lp-section" id="tools">
          <div className="lp-wrap">
            <SectionHead kicker={c.tools.kicker} title={c.tools.title} center />
            <div className="lp-tools">
              {c.tools.items.map((t, i) => (
                <div key={t.title} className={`lp-tool ${i % 2 ? "flip" : ""}`}>
                  <Reveal className="lp-tool-visual">{i === 0 ? <CashflowMock m={c.tools.mock} /> : i === 1 ? <RoadmapMock m={c.tools.mock} /> : <JdMock m={c.tools.mock} />}</Reveal>
                  <Reveal className="lp-tool-text" delay={120}>
                    <h3>{t.title}</h3>
                    <p>{t.body}</p>
                    <ul>{t.points.map((p) => <li key={p}><CheckCircle2 size={18} aria-hidden="true" />{p}</li>)}</ul>
                  </Reveal>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ------------------------------------------------ experts */}
        <section className="lp-section dark" id="experts">
          <div className="lp-aurora soft" aria-hidden="true"><span className="a1" /><span className="a2" /></div>
          <div className="lp-wrap lp-experts">
            <div>
              <SectionHead kicker={c.experts.kicker} title={c.experts.title} lead={c.experts.lead} light />
              <Reveal className="lp-expert-types">
                {c.experts.types.map((t, i) => { const Icon = EXPERT_ICONS[i] ?? Users; return <span key={t}><Icon size={16} aria-hidden="true" />{t}</span>; })}
              </Reveal>
              <div className="lp-promises">
                {c.experts.promises.map(([h, b], i) => (
                  <Reveal key={h} className="lp-promise" delay={i * 100}>
                    <span className="lp-promise-icon"><ShieldCheck size={22} aria-hidden="true" /></span>
                    <div><b>{h}</b><p>{b}</p></div>
                  </Reveal>
                ))}
              </div>
            </div>
            <Reveal className="lp-track-card" delay={150}>
              <div className="lp-track-head">
                <span className="lp-avatar big">CA</span>
                <div><b>{c.experts.track.title}</b><small>{c.experts.track.who}</small></div>
              </div>
              <ol>
                {c.experts.track.steps.map((s) => <li key={s}><span className="lp-tdot"><CheckCircle2 size={16} /></span>{s}</li>)}
              </ol>
              <div className="lp-rated">{[0, 1, 2, 3, 4].map((i) => <Star key={i} size={18} fill="currentColor" aria-hidden="true" />)}<span>{c.experts.track.rated}</span></div>
            </Reveal>
          </div>
        </section>

        {/* ------------------------------------------------ made for you */}
        <section className="lp-section">
          <div className="lp-wrap">
            <SectionHead kicker={c.made.kicker} title={c.made.title} center />
            <div className="lp-made">
              {c.made.items.map(([h, b], i) => {
                const Icon = MADE_ICONS[i] ?? Lock;
                return (
                  <Reveal key={h} className="lp-made-card" delay={i * 100}>
                    <span className="lp-made-icon"><Icon size={26} aria-hidden="true" /></span>
                    <h3>{h}</h3>
                    <p>{b}</p>
                  </Reveal>
                );
              })}
            </div>
          </div>
        </section>

        {/* ------------------------------------------------ FAQ */}
        <section className="lp-section soft" id="faq">
          <div className="lp-wrap lp-faq-wrap">
            <SectionHead kicker={c.faq.kicker} title={c.faq.title} />
            <Reveal className="lp-faq">
              {c.faq.items.map(([q, a], i) => <Faq key={q} id={`faq-${i}`} q={q} a={a} open={openFaq === i} onToggle={() => setOpenFaq(openFaq === i ? -1 : i)} />)}
            </Reveal>
          </div>
        </section>

        {/* ------------------------------------------------ closing banner */}
        <section className="lp-end-wrap">
          <div className="lp-wrap">
            <Reveal className="lp-end">
              <div className="lp-end-art" aria-hidden="true"><span className="r1" /><span className="r2" /><span className="r3" /></div>
              <div className="lp-end-text">
                <h2>{c.end.title}</h2>
                <p>{c.end.lead}</p>
              </div>
              <div className="lp-end-ctas">
                <Link to="/login?new=1" className="lp-cta">{c.end.register}<ArrowRight size={18} aria-hidden="true" /></Link>
                <Link to="/login" className="lp-glass-btn">{c.end.login}</Link>
              </div>
            </Reveal>
          </div>
        </section>
      </main>

      {/* ------------------------------------------------ footer */}
      <footer className="lp-foot">
        <div className="lp-wrap lp-foot-grid">
          <div className="lp-foot-brand">
            <Logo tone="light" size={40} />
            <p>{c.footer.tagline}</p>
          </div>
          <div>
            <b>{c.footer.explore}</b>
            {nav.map(([id, label]) => <button key={id} onClick={() => goTo(id)}>{label}</button>)}
          </div>
          <div>
            <b>{c.footer.portals}</b>
            <Link to="/login">{c.nav.login}</Link>
            <Link to="/expert">{c.footer.experts}</Link>
            <Link to="/admin">{c.footer.team}</Link>
          </div>
        </div>
        <div className="lp-wrap lp-foot-bottom">© {new Date().getFullYear()} {c.footer.rights}</div>
      </footer>
    </div>
  );
}
