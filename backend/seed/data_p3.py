"""Phase 1 Sprint 3 starter data: the three Phase 1 enterprise models (spec Section 9) with DPR templates, and the
scheme library (M6).

SAMPLE DATA – equipment rates, sales and expense assumptions are indicative figures to show how the DPR works.
Scheme limits, subsidy rates and document lists follow the published guidelines as understood at the time of writing;
MIRAI's DPR & Credit Officer must check each scheme against the current guidelines, then set "Verified on"."""

from app.dpr.schemes import DOCS_BASE

MODELS = [
    {
        "code": "millet_cafe", "sector": "food", "name_en": "Mobile millet café", "name_te": "మొబైల్ మిల్లెట్ కేఫ్",
        "description": "A branded e-cart or kiosk selling millet snacks, millet malt (ambali), tea and packaged millet laddus "
                       "at a busy spot, with orders from offices and schools.",
        "activity": "manufacturing", "context_tags": ["rural", "urban", "tribal", "coastal"],
        "investment_min": 200000, "investment_max": 400000, "working_capital": 30000,
        "equipment": [
            {"item": "Mobile food cart / kiosk with branding", "spec": "Steel body, canopy, storage, MIRAI branding", "qty": 1, "rate": 150000},
            {"item": "Commercial gas stove with hood", "spec": "2 burners", "qty": 1, "rate": 18000},
            {"item": "Commercial mixer-grinder", "spec": "2 litre", "qty": 1, "rate": 12000},
            {"item": "Steamer and cookware set", "spec": "Idli / steamer plates, kadai, tawa", "qty": 1, "rate": 15000},
            {"item": "Refrigerator", "spec": "190 litre", "qty": 1, "rate": 18000},
            {"item": "Utensils, serving ware and water dispenser", "spec": "", "qty": 1, "rate": 12000},
            {"item": "Billing phone and UPI sound box", "spec": "", "qty": 1, "rate": 8000},
            {"item": "Folding table and stools", "spec": "", "qty": 1, "rate": 10000},
        ],
        "infrastructure": ["Spot of 50–80 sq ft with permission", "Gas connection (commercial)", "Clean water", "FSSAI basic registration"],
        "skills": ["cooking", "customer_service", "accounts"],
        "schemes": ["pmfme", "pmegp", "mudra"],
        "sales_template": {"items": [
            {"name": "Millet snacks (plate)", "unit": "plate", "units_per_day": 40, "price": 40},
            {"name": "Millet malt / ambali", "unit": "glass", "units_per_day": 40, "price": 20},
            {"name": "Tea / coffee", "unit": "cup", "units_per_day": 60, "price": 12},
            {"name": "Packaged millet laddu", "unit": "pack", "units_per_day": 10, "price": 25},
        ], "working_days": 26, "monthly_growth_pct": 1, "yearly_growth_pct": 6},
        "expense_template": {"raw_material_pct": 50, "salaries": 10000, "rent": 2000, "fuel": 4500, "maintenance": 1000, "other": 1500,
                             "yearly_increase_pct": 5},
        "expected_monthly_sales": 87600, "jobs": 2, "payback_months": 18, "status": "active",
    },
    {
        "code": "tea_stall", "sector": "food", "name_en": "Tea and snacks stall", "name_te": "టీ & స్నాక్స్ స్టాల్",
        "description": "A tea stall with snacks near a bus stand, market or offices, with regular customers and office delivery.",
        "activity": "service", "context_tags": ["rural", "urban", "coastal"],
        "investment_min": 80000, "investment_max": 150000, "working_capital": 15000,
        "equipment": [
            {"item": "Stall / kiosk", "spec": "Steel, with counter and shutter", "qty": 1, "rate": 60000},
            {"item": "Tea boiler", "spec": "Stainless steel, 20 litre", "qty": 1, "rate": 15000},
            {"item": "Utensils and cups", "spec": "", "qty": 1, "rate": 8000},
            {"item": "Snack display box", "spec": "Glass", "qty": 1, "rate": 5000},
            {"item": "Benches / chairs", "spec": "", "qty": 1, "rate": 6000},
        ],
        "infrastructure": ["Spot near footfall (bus stand, market, offices)", "Vendor licence / spot permission", "Water"],
        "skills": ["cooking", "customer_service"],
        "schemes": ["mudra", "pmegp"],
        "sales_template": {"items": [
            {"name": "Tea", "unit": "cup", "units_per_day": 150, "price": 10},
            {"name": "Coffee", "unit": "cup", "units_per_day": 30, "price": 15},
            {"name": "Biscuits and snacks", "unit": "piece", "units_per_day": 60, "price": 10},
        ], "working_days": 28, "monthly_growth_pct": 1, "yearly_growth_pct": 5},
        "expense_template": {"raw_material_pct": 50, "salaries": 0, "rent": 2500, "fuel": 4000, "maintenance": 500, "other": 1000,
                             "yearly_increase_pct": 5},
        "expected_monthly_sales": 71400, "jobs": 1, "payback_months": 12, "status": "active",
    },
    {
        "code": "drone_services", "sector": "agriculture", "name_en": "Drone spraying services (MiraiCrop)",
        "name_te": "డ్రోన్ స్ప్రేయింగ్ సేవలు (మిరాయ్‌క్రాప్)",
        "description": "A certified drone operator sprays crops for farmers who book through MiraiCrop; the farmer supplies the pesticide.",
        "activity": "service", "context_tags": ["rural"],
        "investment_min": 900000, "investment_max": 1400000, "working_capital": 40000,
        "equipment": [
            {"item": "Agricultural spraying drone", "spec": "10 litre tank, DGCA type-certified", "qty": 1, "rate": 650000},
            {"item": "Extra battery set", "spec": "Smart flight batteries (pair)", "qty": 2, "rate": 60000},
            {"item": "Generator and fast charger", "spec": "Portable generator, multi-battery charger", "qty": 1, "rate": 75000},
            {"item": "Transport vehicle", "spec": "Small pick-up / three-wheeler", "qty": 1, "rate": 250000},
        ],
        "infrastructure": ["Storage room for drone and batteries", "Power for charging", "DGCA Remote Pilot Certificate", "Drone UIN and insurance"],
        "skills": ["driving", "smartphone", "farming"],
        "schemes": ["pmegp", "mudra", "standup"],
        "sales_template": {"items": [
            {"name": "Crop spraying", "unit": "acre", "units_per_day": 20, "price": 400},
        ], "working_days": 18, "monthly_growth_pct": 1, "yearly_growth_pct": 5},
        "expense_template": {"raw_material_pct": 10, "salaries": 12000, "rent": 1500, "fuel": 6000, "maintenance": 5000, "other": 2500,
                             "yearly_increase_pct": 5},
        "expected_monthly_sales": 144000, "jobs": 2, "payback_months": 30, "status": "active",
    },
]


SCHEMES = [
    {
        "code": "pmegp", "name": "PMEGP – Prime Minister's Employment Generation Programme",
        "name_te": "పీఎంఈజీపీ – ప్రధానమంత్రి ఉపాధి కల్పన కార్యక్రమం", "kind": "central", "agency": "KVIC / KVIB / District Industries Centre",
        "description": "Credit-linked subsidy (margin money) for new micro enterprises. Apply online on the PMEGP portal; "
                       "the bank sanctions the loan and the subsidy is held for 3 years before adjustment. EDP training is needed before the loan is released.",
        "url": "https://www.kviconline.gov.in/pmegpeportal/",
        "rules": {"min_age": 18, "new_unit_only": True, "activities": ["manufacturing", "service", "agri_allied"],
                  "max_project_cost": {"manufacturing": 5000000, "service": 2000000, "agri_allied": 5000000},
                  "min_education": "secondary", "education_above_cost": {"manufacturing": 1000000, "service": 500000, "agri_allied": 1000000},
                  "own_pct": {"general": 10, "special": 5},
                  "subsidy_pct": {"general_urban": 15, "general_rural": 25, "special_urban": 25, "special_rural": 35},
                  "subsidy_on": "project_cost",
                  "notes": "Special category: SC, ST, OBC, minorities, women (also ex-servicemen, persons with disabilities, NER / hill / border areas). "
                           "Education: at least VIII standard pass above the cost limits."},
        "documents": DOCS_BASE + [
            {"code": "caste_certificate", "label": "Caste certificate", "when": "special"},
            {"code": "education_certificate", "label": "Education certificate (VIII pass)", "when": "always"},
            {"code": "rural_certificate", "label": "Rural area certificate", "when": "rural"},
            {"code": "edp_certificate", "label": "EDP training certificate", "when": "always"},
        ],
    },
    {
        "code": "pmfme", "name": "PMFME – PM Formalisation of Micro Food Processing Enterprises",
        "name_te": "పీఎంఎఫ్ఎంఈ – సూక్ష్మ ఆహార తయారీ సంస్థల పథకం", "kind": "central", "agency": "Ministry of Food Processing Industries / State Nodal Agency",
        "description": "Credit-linked capital subsidy of 35% of the eligible project cost (up to ₹10 lakh) for micro food processing units. "
                       "A District Resource Person helps with the DPR and the online application.",
        "url": "https://pmfme.mofpi.gov.in/",
        "rules": {"min_age": 18, "activities": ["manufacturing"], "sectors": ["food"], "min_education": "secondary",
                  "own_pct": {"general": 10, "special": 10},
                  "subsidy_pct": {"general_urban": 35, "general_rural": 35, "special_urban": 35, "special_rural": 35},
                  "subsidy_cap": 1000000, "subsidy_on": "capital",
                  "notes": "For food processing (millet products, snacks, pickles, bakery). Subsidy is on plant, machinery and technical civil work, "
                           "not on working capital."},
        "documents": DOCS_BASE + [
            {"code": "education_certificate", "label": "Education certificate (VIII pass)", "when": "always"},
            {"code": "fssai", "label": "FSSAI registration (or applied)", "when": "always"},
            {"code": "udyam", "label": "Udyam registration", "when": "always"},
        ],
    },
    {
        "code": "mudra", "name": "PMMY – Pradhan Mantri MUDRA Yojana", "name_te": "ప్రధానమంత్రి ముద్రా యోజన",
        "kind": "central", "agency": "Banks, NBFCs and MFIs",
        "description": "Collateral-free loans for non-farm income-generating micro enterprises: Shishu up to ₹50,000, Kishore up to ₹5 lakh, "
                       "Tarun up to ₹10 lakh (Tarun Plus up to ₹20 lakh for those who repaid a Tarun loan). No subsidy.",
        "url": "https://www.mudra.org.in/",
        "rules": {"min_age": 18, "activities": ["manufacturing", "service", "trading", "agri_allied"], "max_loan": 1000000,
                  "own_pct": {"general": 10, "special": 10},
                  "tiers": [{"name": "Shishu", "max": 50000}, {"name": "Kishore", "max": 500000}, {"name": "Tarun", "max": 1000000}],
                  "notes": "Margin is at the bank's discretion (usually nil for Shishu, about 10–20% above that)."},
        "documents": DOCS_BASE + [{"code": "udyam", "label": "Udyam registration (if available)", "when": "always"}],
    },
    {
        "code": "standup", "name": "Stand-Up India", "name_te": "స్టాండ్-అప్ ఇండియా", "kind": "central", "agency": "Scheduled commercial banks / SIDBI",
        "description": "Bank loans from ₹10 lakh to ₹1 crore for a new (greenfield) enterprise of an SC / ST and / or woman entrepreneur.",
        "url": "https://www.standupmitra.in/",
        "rules": {"min_age": 18, "new_unit_only": True, "requires_any": ["women", "sc", "st"], "min_loan": 1000000, "max_loan": 10000000,
                  "activities": ["manufacturing", "service", "trading", "agri_allied"],
                  "own_pct": {"general": 10, "special": 10},
                  "notes": "Borrower margin at least 10% of the project cost (up to 25% together with any state scheme)."},
        "documents": DOCS_BASE + [{"code": "caste_certificate", "label": "Caste certificate (SC / ST)", "when": "special"}],
    },
]
