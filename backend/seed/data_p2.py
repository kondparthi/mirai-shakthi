"""Phase 1 Sprint 2 – starter course catalogue (spec M4, tracks A–F).
MIRAI can change every course in Admin → Training → Courses. Telugu is a draft for review."""


def S(en, te, hours=3):
    return {"topic_en": en, "topic_te": te, "hours": hours}


COURSES = [
    {
        "code": "awareness_edp", "track": "awareness", "name_en": "Awareness EDP", "name_te": "అవగాహన ఈడీపీ",
        "description_en": "Short orientation for new enrollees: entrepreneurship as a career, the MIRAI Shakthi journey, sectors, enterprise models and schemes.",
        "description_te": "కొత్తగా చేరినవారికి చిన్న అవగాహన: వ్యాపారం ఒక వృత్తిగా, MIRAI శక్తి ప్రయాణం, రంగాలు, వ్యాపార నమూనాలు, పథకాలు.",
        "duration_days": 2, "pass_mark": 50, "min_attendance": 75,
        "sessions": [S("Entrepreneurship as a career", "వ్యాపారం ఒక వృత్తిగా"), S("The MIRAI Shakthi journey", "MIRAI శక్తి ప్రయాణం"),
                     S("Sectors and enterprise models", "రంగాలు మరియు వ్యాపార నమూనాలు"), S("Government schemes overview", "ప్రభుత్వ పథకాల పరిచయం")],
        "outcomes": ["Understands what running an enterprise involves", "Knows the MIRAI journey and support", "Has shortlisted 1–2 enterprise models"],
    },
    {
        "code": "core_edp", "track": "core", "name_en": "Core EDP", "name_te": "కోర్ ఈడీపీ",
        "description_en": "Full Entrepreneurship Development Programme, ending with a business-plan presentation that becomes the draft for the DPR.",
        "description_te": "పూర్తి వ్యవస్థాపక అభివృద్ధి కార్యక్రమం. చివరలో వ్యాపార ప్రణాళిక ప్రదర్శన – ఇదే డీపీఆర్‌కు మొదటి రూపం.",
        "duration_days": 10, "pass_mark": 60, "min_attendance": 80, "business_plan_score": True,
        "sessions": [S("Motivation and mindset", "ప్రేరణ మరియు ఆలోచనా విధానం"), S("Opportunity identification", "అవకాశాల గుర్తింపు"),
                     S("Market survey", "మార్కెట్ సర్వే"), S("Costing and pricing", "ఖర్చు లెక్క మరియు ధర నిర్ణయం"),
                     S("Business plan and DPR", "వ్యాపార ప్రణాళిక మరియు డీపీఆర్"), S("Bookkeeping", "లెక్కల పుస్తకాలు"),
                     S("Banking and credit", "బ్యాంకింగ్ మరియు రుణాలు"), S("Schemes, registrations and compliance", "పథకాలు, రిజిస్ట్రేషన్లు, నిబంధనలు"),
                     S("Marketing and digital selling", "మార్కెటింగ్ మరియు డిజిటల్ అమ్మకాలు"), S("Customer service and basic HR", "కస్టమర్ సేవ మరియు సిబ్బంది నిర్వహణ"),
                     S("Business-plan presentation", "వ్యాపార ప్రణాళిక ప్రదర్శన", 4)],
        "outcomes": ["Prepares a costed business plan", "Keeps simple books", "Knows how to apply for a bank loan and schemes"],
    },
    {
        "code": "skill_millet_cafe", "track": "skill", "name_en": "Millet café & food hygiene", "name_te": "చిరుధాన్యాల కేఫ్ & ఆహార పరిశుభ్రత",
        "description_en": "Hands-on training for the mobile millet café model: recipes, food hygiene (FSSAI basics), serving and daily accounts.",
        "description_te": "మొబైల్ చిరుధాన్యాల కేఫ్ నమూనాకు ప్రాక్టికల్ శిక్షణ: వంటకాలు, ఆహార పరిశుభ్రత (FSSAI ప్రాథమికాలు), వడ్డింపు, రోజువారీ లెక్కలు.",
        "sectors": ["food"], "duration_days": 5, "pass_mark": 60, "min_attendance": 80,
        "sessions": [S("Millet basics and sourcing", "చిరుధాన్యాల ప్రాథమికాలు, కొనుగోలు"), S("Recipes I – snacks", "వంటకాలు 1 – స్నాక్స్", 4),
                     S("Recipes II – meals and drinks", "వంటకాలు 2 – భోజనం, పానీయాలు", 4), S("Food hygiene and FSSAI basics", "ఆహార పరిశుభ్రత, FSSAI ప్రాథమికాలు"),
                     S("Serving, pricing and daily accounts", "వడ్డింపు, ధర, రోజువారీ లెక్కలు")],
        "practical_checklist": ["Prepares 5 standard recipes", "Follows the hygiene checklist", "Keeps the daily sales sheet"],
        "outcomes": ["Runs a day of café service on their own"],
    },
    {
        "code": "skill_drone_pilot", "track": "skill", "name_en": "Drone pilot & spraying safety", "name_te": "డ్రోన్ పైలట్ & స్ప్రేయింగ్ భద్రత",
        "description_en": "Agri-drone operation and safe spraying. The DGCA Remote Pilot Certificate is obtained through an approved training organisation (RPTO) and uploaded here.",
        "description_te": "వ్యవసాయ డ్రోన్ నిర్వహణ, సురక్షిత స్ప్రేయింగ్. DGCA రిమోట్ పైలట్ సర్టిఫికేట్ ఆమోదిత శిక్షణ సంస్థ (RPTO) ద్వారా పొంది ఇక్కడ అప్‌లోడ్ చేయాలి.",
        "sectors": ["agriculture"], "duration_days": 7, "pass_mark": 70, "min_attendance": 90,
        "external_certificate": "DGCA Remote Pilot Certificate",
        "sessions": [S("Drone rules and airspace", "డ్రోన్ నిబంధనలు, గగనతలం"), S("Drone parts and pre-flight checks", "డ్రోన్ భాగాలు, ఎగిరే ముందు తనిఖీలు"),
                     S("Flight practice", "ఎగరడం ప్రాక్టీస్", 6), S("Spraying: doses, mixing and safety", "స్ప్రేయింగ్: మోతాదు, కలపడం, భద్రత", 4),
                     S("Field operation and farmer service", "పొలంలో పని, రైతు సేవ", 6), S("Battery, maintenance and logbook", "బ్యాటరీ, నిర్వహణ, లాగ్‌బుక్")],
        "practical_checklist": ["Completes pre-flight checklist", "Flies a supervised spray run", "Uses PPE and safe mixing", "Fills the flight logbook"],
        "outcomes": ["Operates a spraying drone safely under supervision"],
    },
    {
        "code": "skill_tailoring", "track": "skill", "name_en": "Tailoring & garment making", "name_te": "టైలరింగ్ & దుస్తుల తయారీ",
        "description_en": "Measurement, cutting and stitching of common garments, with costing and order handling.",
        "description_te": "కొలతలు, కత్తిరింపు, సాధారణ దుస్తుల కుట్టు; ఖర్చు లెక్క, ఆర్డర్ల నిర్వహణ.",
        "sectors": ["crafts"], "duration_days": 10, "pass_mark": 60, "min_attendance": 80,
        "sessions": [S("Machine use and care", "మెషిన్ వాడకం, సంరక్షణ"), S("Measurements and cutting", "కొలతలు, కత్తిరింపు", 4),
                     S("Blouse and churidar", "బ్లౌజ్, చుడీదార్", 6), S("Children's wear", "పిల్లల దుస్తులు", 4), S("Costing and taking orders", "ఖర్చు లెక్క, ఆర్డర్లు")],
        "practical_checklist": ["Takes accurate measurements", "Stitches a blouse to size", "Prices an order correctly"],
        "outcomes": ["Takes and completes customer orders"],
    },
    {
        "code": "ojt_unit", "track": "ojt", "name_en": "On-the-job days at a running unit", "name_te": "నడుస్తున్న యూనిట్‌లో ఉద్యోగ శిక్షణ",
        "description_en": "Hands-on days at a running MIRAI Shakthi unit or partner business; the host unit records tasks done and skills observed.",
        "description_te": "నడుస్తున్న MIRAI శక్తి యూనిట్ లేదా భాగస్వామి వ్యాపారంలో ప్రాక్టికల్ రోజులు; చేసిన పనులు, నైపుణ్యాలను హోస్ట్ యూనిట్ నమోదు చేస్తుంది.",
        "duration_days": 10, "pass_mark": 0, "min_attendance": 80,
        "sessions": [S(f"Day {i} at the host unit", f"హోస్ట్ యూనిట్‌లో {i}వ రోజు", 6) for i in range(1, 11)],
        "practical_checklist": ["Opens and closes the unit", "Serves customers", "Records sales and stock"],
        "outcomes": ["Has done every daily task of the enterprise"],
    },
    {
        "code": "exposure_visit", "track": "exposure", "name_en": "Exposure visit", "name_te": "అనుభవ సందర్శన",
        "description_en": "Visit to successful units, markets, FPOs or institutions, logged with photos and learnings.",
        "description_te": "విజయవంతమైన యూనిట్లు, మార్కెట్లు, FPOలు లేదా సంస్థల సందర్శన – ఫోటోలు, నేర్చుకున్నవి నమోదు.",
        "duration_days": 1, "pass_mark": 0, "min_attendance": 100,
        "sessions": [S("Visit and discussion", "సందర్శన మరియు చర్చ", 6)],
        "outcomes": ["Has seen a running enterprise of their model"],
    },
    {
        "code": "refresher_digital", "track": "refresher", "name_en": "Refresher: digital payments & online selling", "name_te": "రిఫ్రెషర్: డిజిటల్ చెల్లింపులు & ఆన్‌లైన్ అమ్మకాలు",
        "description_en": "Short module during handholding: UPI and QR payments, WhatsApp catalogue, ONDC and marketplace basics.",
        "description_te": "హ్యాండ్‌హోల్డింగ్ సమయంలో చిన్న మాడ్యూల్: UPI, QR చెల్లింపులు, వాట్సాప్ కేటలాగ్, ONDC ప్రాథమికాలు.",
        "duration_days": 1, "pass_mark": 50, "min_attendance": 100,
        "sessions": [S("UPI and QR payments", "UPI, QR చెల్లింపులు"), S("WhatsApp catalogue and online selling", "వాట్సాప్ కేటలాగ్, ఆన్‌లైన్ అమ్మకాలు")],
        "outcomes": ["Accepts digital payments", "Has a product catalogue online"],
    },
]
