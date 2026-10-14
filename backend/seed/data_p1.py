"""Phase 1 starter master data (M14).

Geography: the 26 districts of Andhra Pradesh, a starter list of Guntur mandals and a few sample villages.
MIRAI should load the full official list (Local Government Directory, lgdirectory.gov.in) through
Admin → Master data → Import CSV. Telugu names are a draft for review.
"""

CONTEXT_TAGS = [("rural", "Rural", "గ్రామీణ"), ("urban", "Urban", "పట్టణ"), ("tribal", "Tribal", "గిరిజన"), ("coastal", "Coastal", "తీర ప్రాంత")]

DISTRICTS = [
    ("alluri_sitharama_raju", "Alluri Sitharama Raju", "అల్లూరి సీతారామరాజు", "tribal"),
    ("anakapalli", "Anakapalli", "అనకాపల్లి", "rural"), ("anantapur", "Anantapur", "అనంతపురం", "rural"),
    ("annamayya", "Annamayya", "అన్నమయ్య", "rural"), ("bapatla", "Bapatla", "బాపట్ల", "coastal"),
    ("chittoor", "Chittoor", "చిత్తూరు", "rural"), ("east_godavari", "East Godavari", "తూర్పు గోదావరి", "rural"),
    ("eluru", "Eluru", "ఏలూరు", "rural"), ("guntur", "Guntur", "గుంటూరు", "rural"),
    ("kakinada", "Kakinada", "కాకినాడ", "coastal"), ("konaseema", "Konaseema", "కోనసీమ", "coastal"),
    ("krishna", "Krishna", "కృష్ణా", "coastal"), ("kurnool", "Kurnool", "కర్నూలు", "rural"),
    ("nandyal", "Nandyal", "నంద్యాల", "rural"), ("ntr", "NTR", "ఎన్టీఆర్", "urban"), ("palnadu", "Palnadu", "పల్నాడు", "rural"),
    ("parvathipuram_manyam", "Parvathipuram Manyam", "పార్వతీపురం మన్యం", "tribal"), ("prakasam", "Prakasam", "ప్రకాశం", "rural"),
    ("nellore", "Sri Potti Sriramulu Nellore", "శ్రీ పొట్టి శ్రీరాములు నెల్లూరు", "coastal"),
    ("sri_sathya_sai", "Sri Sathya Sai", "శ్రీ సత్యసాయి", "rural"), ("srikakulam", "Srikakulam", "శ్రీకాకుళం", "coastal"),
    ("tirupati", "Tirupati", "తిరుపతి", "urban"), ("visakhapatnam", "Visakhapatnam", "విశాఖపట్నం", "urban"),
    ("vizianagaram", "Vizianagaram", "విజయనగరం", "rural"), ("west_godavari", "West Godavari", "పశ్చిమ గోదావరి", "rural"),
    ("ysr_kadapa", "YSR Kadapa", "వైఎస్ఆర్ కడప", "rural"),
]

# Starter list – verify with LGD before use.
GUNTUR_MANDALS = [
    ("guntur_east", "Guntur East", "గుంటూరు తూర్పు"), ("guntur_west", "Guntur West", "గుంటూరు పశ్చిమ"),
    ("tenali", "Tenali", "తెనాలి"), ("duggirala", "Duggirala", "దుగ్గిరాల"), ("kollipara", "Kollipara", "కొల్లిపర"),
    ("mangalagiri", "Mangalagiri", "మంగళగిరి"), ("tadepalli", "Tadepalli", "తాడేపల్లి"), ("pedakakani", "Pedakakani", "పెదకాకాని"),
    ("chebrolu", "Chebrolu", "చేబ్రోలు"), ("ponnur", "Ponnur", "పొన్నూరు"), ("prathipadu", "Prathipadu", "ప్రత్తిపాడు"),
    ("vatticherukuru", "Vatticherukuru", "వట్టిచెరుకూరు"), ("pedanandipadu", "Pedanandipadu", "పెదనందిపాడు"),
    ("kakumanu", "Kakumanu", "కాకుమాను"), ("medikonduru", "Medikonduru", "మేడికొండూరు"), ("phirangipuram", "Phirangipuram", "ఫిరంగిపురం"),
    ("tadikonda", "Tadikonda", "తాడికొండ"), ("thullur", "Thullur", "తుళ్లూరు"),
]
# Sample villages (mandal code, village code, English, Telugu, context tag) – replace with the LGD list.
SAMPLE_VILLAGES = [
    ("tenali", "tenali_town", "Tenali (town)", "తెనాలి (పట్టణం)", "urban"),
    ("tenali", "kolakaluru", "Kolakaluru", "కొలకలూరు", "rural"),
    ("tenali", "angalakuduru", "Angalakuduru", "అంగలకుదురు", "rural"),
    ("mangalagiri", "mangalagiri_town", "Mangalagiri (town)", "మంగళగిరి (పట్టణం)", "urban"),
    ("mangalagiri", "nidamarru", "Nidamarru", "నిడమర్రు", "rural"),
    ("mangalagiri", "chinakakani", "Chinakakani", "చినకాకాని", "rural"),
]

# Spec Section 5 – nine sectors with Phase 1 activation status.
SECTORS = [
    ("agriculture", "Agriculture & agri services", "వ్యవసాయ & వ్యవసాయ సేవలు", "Drone spraying, equipment rental, nurseries, seedling production, custom farm services",
     ["rural", "tribal"], "active", "miraicrop", "Sprout"),
    ("food", "Food processing & food services", "ఆహార తయారీ & ఆహార సేవలు", "Mobile millet café, tea stall, local foods, small food processing",
     ["rural", "urban", "tribal", "coastal"], "active", "millet_cafe", "Utensils"),
    ("livestock", "Livestock & allied", "పశుపోషణ & అనుబంధ", "Dairy, poultry, fodder", ["rural", "tribal"], "catalogue", None, "Milk"),
    ("fisheries", "Fisheries & coastal enterprises", "మత్స్య & తీర ప్రాంత వ్యాపారాలు", "Fish retail, drying, value addition", ["coastal"], "catalogue", None, "Fish"),
    ("ntfp", "NTFP & forest-based products", "అటవీ ఆధారిత ఉత్పత్తులు", "Honey, tamarind, leaf products", ["tribal"], "catalogue", None, "Trees"),
    ("services", "Services & digital livelihoods", "సేవలు & డిజిటల్ జీవనోపాధి", "Repairs, beauty, digital services", ["rural", "urban"], "catalogue", None, "Laptop"),
    ("crafts", "Crafts & small manufacturing", "హస్తకళలు & చిన్న తయారీ", "Handloom, garments, local products", ["rural", "urban", "tribal"], "catalogue", None, "Palette"),
    ("mobility", "Mobility & local logistics", "రవాణా & స్థానిక లాజిస్టిక్స్", "EV services, delivery, rentals", ["rural", "urban"], "catalogue", None, "Truck"),
    ("tourism", "Tourism & community hospitality", "పర్యాటకం & సామాజిక ఆతిథ్యం", "Homestays, guides, local experiences", ["rural", "tribal", "coastal"], "catalogue", None, "Hotel"),
]

SIMPLE = {
    "skill": [("cooking", "Cooking", "వంట"), ("driving", "Driving", "డ్రైవింగ్"), ("tailoring", "Tailoring", "టైలరింగ్"),
              ("machine_operation", "Machine operation", "యంత్రాల నిర్వహణ"), ("accounts", "Accounts", "లెక్కలు"),
              ("sales", "Sales", "అమ్మకాలు"), ("smartphone", "Smartphone use", "స్మార్ట్‌ఫోన్ వాడకం"), ("farming", "Farming", "వ్యవసాయం"),
              ("repairs", "Repairs", "మరమ్మతులు"), ("handicrafts", "Handicrafts", "హస్తకళలు"), ("customer_service", "Customer service", "కస్టమర్ సేవ"),
              ("livestock_care", "Livestock care", "పశువుల సంరక్షణ")],
    "education": [("none", "No schooling", "చదువు లేదు"), ("primary", "Up to 5th class", "5వ తరగతి వరకు"), ("secondary", "6th–10th class", "6–10 తరగతులు"),
                  ("intermediate", "Intermediate", "ఇంటర్మీడియట్"), ("iti", "ITI / Diploma", "ఐటీఐ / డిప్లొమా"), ("graduate", "Graduate", "డిగ్రీ"),
                  ("postgraduate", "Post-graduate", "పీజీ")],
    "occupation": [("homemaker", "Homemaker", "గృహిణి"), ("farmer", "Farmer", "రైతు"), ("agri_labour", "Agricultural labour", "వ్యవసాయ కూలీ"),
                   ("daily_wage", "Daily-wage work", "రోజు కూలీ"), ("self_employed", "Self-employed / small business", "స్వయం ఉపాధి / చిన్న వ్యాపారం"),
                   ("salaried", "Salaried job", "ఉద్యోగం"), ("student", "Student", "విద్యార్థి"), ("unemployed", "Looking for work", "పని వెతుకుతున్నారు"),
                   ("other", "Other", "ఇతర")],
    "social_category": [("general", "General", "జనరల్"), ("obc", "OBC / BC", "ఓబీసీ / బీసీ"), ("sc", "SC", "ఎస్సీ"), ("st", "ST", "ఎస్టీ"),
                        ("minority", "Minority", "మైనారిటీ")],
    "doc_type": [("aadhaar", "Aadhaar", "ఆధార్"), ("pan", "PAN card", "పాన్ కార్డు"), ("bank_passbook", "Bank passbook", "బ్యాంకు పాస్‌బుక్"),
                 ("photo", "Photo", "ఫోటో"), ("caste_certificate", "Caste certificate", "కుల ధృవీకరణ పత్రం"),
                 ("income_certificate", "Income certificate", "ఆదాయ ధృవీకరణ పత్రం"), ("ration_card", "Ration card", "రేషన్ కార్డు"),
                 ("edp_certificate", "EDP certificate", "ఈడీపీ సర్టిఫికేట్"), ("udyam", "Udyam certificate", "ఉద్యమ్ సర్టిఫికేట్"),
                 ("quotation", "Supplier quotation", "సరఫరాదారు కొటేషన్")],
    "bank": [("sbi", "State Bank of India", "స్టేట్ బ్యాంక్ ఆఫ్ ఇండియా"), ("union", "Union Bank of India", "యూనియన్ బ్యాంక్ ఆఫ్ ఇండియా"),
             ("canara", "Canara Bank", "కెనరా బ్యాంక్"), ("bob", "Bank of Baroda", "బ్యాంక్ ఆఫ్ బరోడా"), ("indian", "Indian Bank", "ఇండియన్ బ్యాంక్"),
             ("pnb", "Punjab National Bank", "పంజాబ్ నేషనల్ బ్యాంక్"), ("boi", "Bank of India", "బ్యాంక్ ఆఫ్ ఇండియా"),
             ("rrb", "Regional Rural Bank (Grameena)", "గ్రామీణ బ్యాంకు"), ("other", "Other bank", "ఇతర బ్యాంకు")],
}
