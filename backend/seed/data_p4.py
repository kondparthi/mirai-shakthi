"""Phase 1 Sprint 4 starter data: registrations and readiness items for the three Phase 1 models, and SAMPLE suppliers
(names start with "Sample:" – replace them with MIRAI's real approved suppliers before go-live)."""

MODEL_SETUP = {
    "millet_cafe": {
        "registrations": ["udyam", "fssai", "trade_licence"],
        "readiness_items": ["Cart branded with the MIRAI design", "Menu card and price board ready", "Gas connection and fire extinguisher in place",
                            "Hygiene check passed (mentor)"],
    },
    "tea_stall": {
        "registrations": ["udyam", "fssai", "trade_licence"],
        "readiness_items": ["Stall placed at the agreed spot", "Price board ready", "Hygiene check passed (mentor)"],
    },
    "drone_services": {
        "registrations": ["udyam", "drone_uin", "rpc", "drone_insurance"],
        "readiness_items": ["Test flight done with the trainer", "Operator set up in MiraiCrop", "Safety kit (PPE, first aid) ready"],
    },
}

SUPPLIERS = [
    {"name": "Sample: Guntur Food Carts & Kiosks", "gstin": "37AAAAA0000A1Z5", "contact_name": "Ramesh", "mobile": "9440000101",
     "address": "Auto Nagar, Guntur", "categories": ["Food carts", "Kiosks", "Furniture"],
     "items": ["Mobile food cart / kiosk with branding", "Stall / kiosk", "Folding table and stools", "Benches / chairs"],
     "models": ["millet_cafe", "tea_stall"], "districts": ["guntur", "krishna", "ntr", "bapatla", "palnadu"],
     "rate_card": [{"item": "Mobile food cart / kiosk with branding", "rate": 148000, "unit": "each", "valid_till": None},
                   {"item": "Stall / kiosk", "rate": 58000, "unit": "each", "valid_till": None}]},
    {"name": "Sample: Andhra Kitchen Equipment", "gstin": "37BBBBB0000B1Z5", "contact_name": "Lakshmi Prasad", "mobile": "9440000102",
     "address": "Brodipet, Guntur", "categories": ["Kitchen equipment", "Refrigeration", "Utensils"],
     "items": ["Commercial gas stove with hood", "Commercial mixer-grinder", "Steamer and cookware set", "Refrigerator",
               "Utensils, serving ware and water dispenser", "Tea boiler", "Utensils and cups", "Snack display box"],
     "models": ["millet_cafe", "tea_stall"], "districts": ["guntur", "krishna", "ntr", "bapatla"],
     "rate_card": [{"item": "Commercial gas stove with hood", "rate": 17500, "unit": "each", "valid_till": None},
                   {"item": "Refrigerator", "rate": 18500, "unit": "each", "valid_till": None}]},
    {"name": "Sample: Vijayawada Kitchen Mart", "gstin": "37CCCCC0000C1Z5", "contact_name": "Suresh", "mobile": "9440000103",
     "address": "Governorpet, Vijayawada", "categories": ["Kitchen equipment", "Food carts"],
     "items": ["Mobile food cart / kiosk with branding", "Commercial gas stove with hood", "Commercial mixer-grinder", "Steamer and cookware set",
               "Refrigerator", "Tea boiler"],
     "models": ["millet_cafe", "tea_stall"], "districts": ["krishna", "ntr", "guntur", "eluru"], "rate_card": []},
    {"name": "Sample: AgriDrone Solutions", "gstin": "36DDDDD0000D1Z5", "contact_name": "Kiran", "mobile": "9440000104",
     "address": "Kukatpally, Hyderabad (serves AP)", "categories": ["Drones", "Batteries", "Generators"],
     "items": ["Agricultural spraying drone", "Extra battery set", "Generator and fast charger"],
     "models": ["drone_services"], "districts": [], "rate_card": [{"item": "Agricultural spraying drone", "rate": 640000, "unit": "each", "valid_till": None}]},
]
