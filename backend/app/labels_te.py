"""Telugu labels for profile choices (Form G-1) and the profile summary. Draft – MIRAI to review.
Keys are the English labels used in routers/profile.py and guidance/engine.py."""

LABELS_TE = {
    # stage
    "Planning to start": "ప్రారంభించాలనుకుంటున్నాను", "Running < 1 year": "1 సంవత్సరం లోపు నడుస్తోంది",
    "Running 1–3 years": "1–3 సంవత్సరాలుగా నడుస్తోంది", "Running > 3 years": "3 సంవత్సరాలకు పైగా నడుస్తోంది",
    # business type
    "Manufacturing": "తయారీ", "Trading": "వ్యాపారం (కొని అమ్మడం)", "Services": "సేవలు",
    # sector
    "Food": "ఆహారం", "Agriculture": "వ్యవసాయం", "Dairy & livestock": "పాడి & పశుపోషణ", "Fisheries": "మత్స్య",
    "Forest products": "అటవీ ఉత్పత్తులు", "Handloom & textiles": "చేనేత & వస్త్రాలు", "Crafts": "హస్తకళలు",
    "Repairs & services": "మరమ్మతులు & సేవలు", "Beauty & wellness": "బ్యూటీ & వెల్‌నెస్", "Mobility & logistics": "రవాణా & లాజిస్టిక్స్",
    "Tourism": "పర్యాటకం", "Digital services": "డిజిటల్ సేవలు", "Other": "ఇతర",
    # ownership
    "Proprietor": "యజమాని (ఒక్కరే)", "Partnership": "భాగస్వామ్యం", "LLP": "ఎల్ఎల్‌పీ", "Company": "కంపెనీ", "SHG / group": "స్వయం సహాయక సంఘం",
    # turnover
    "Nil / not started": "ఇంకా లేదు / ప్రారంభించలేదు", "Up to ₹10 lakh": "₹10 లక్షల వరకు", "₹10–40 lakh": "₹10–40 లక్షలు",
    "₹40 lakh – ₹1 crore": "₹40 లక్షలు – ₹1 కోటి", "₹1–5 crore": "₹1–5 కోట్లు", "Above ₹5 crore": "₹5 కోట్లకు పైగా",
    # registrations
    "Udyam": "ఉద్యమ్", "GST": "జీఎస్టీ", "FSSAI": "ఎఫ్ఎస్ఎస్ఏఐ", "Trade licence": "ట్రేడ్ లైసెన్స్", "IEC (export)": "ఐఈసీ (ఎగుమతి)",
    "IEC": "ఐఈసీ", "Shop & Establishment": "షాప్ & ఎస్టాబ్లిష్‌మెంట్",
    # channels
    "Local customers / shop": "స్థానిక కస్టమర్లు / దుకాణం", "Wholesale": "హోల్‌సేల్", "Online": "ఆన్‌లైన్", "Government": "ప్రభుత్వం",
    "Other states": "ఇతర రాష్ట్రాలు", "Export": "ఎగుమతి",
    # books
    "No records": "లెక్కలు లేవు", "Notebook": "నోట్‌బుక్", "Excel": "ఎక్సెల్", "Accounting software": "అకౌంటింగ్ సాఫ్ట్‌వేర్",
    # flags
    "Women-led": "మహిళల నేతృత్వం", "SC / ST": "ఎస్సీ / ఎస్టీ", "First-generation entrepreneur": "మొదటి తరం వ్యవస్థాపకులు",
}


def te(label: str, lang: str) -> str:
    return LABELS_TE.get(label, label) if lang == "te" else label
