"""Phase 1 Sprint 6 starter data: bookkeeping categories and starter stock items for the three Phase 1 models
(Telugu labels are a first draft for MIRAI to review)."""


def c(code, en, te):
    return {"code": code, "label": en, "label_te": te}


MODEL_BOOKS = {
    "millet_cafe": {
        "ledger_categories": {
            "sale": [c("counter", "Counter sales", "కౌంటర్ అమ్మకాలు"), c("orders", "Orders & delivery", "ఆర్డర్లు & డెలివరీ"),
                     c("catering", "Catering / events", "కేటరింగ్ / వేడుకలు"), c("other_income", "Other income", "ఇతర ఆదాయం")],
            "expense": [c("millet_flour", "Millet flour & grains", "మిల్లెట్ పిండి & ధాన్యాలు"), c("milk", "Milk", "పాలు"),
                        c("sugar_jaggery", "Sugar / jaggery", "చక్కెర / బెల్లం"), c("oil_spices", "Oil, spices, vegetables", "నూనె, మసాలాలు, కూరగాయలు"),
                        c("gas", "Gas", "గ్యాస్"), c("cups_packing", "Cups & packing", "కప్పులు & ప్యాకింగ్"), c("wages", "Helper wages", "సహాయకుల కూలీ"),
                        c("spot_fee", "Spot fee / rent", "స్థలం రుసుము / అద్దె"), c("transport", "Transport", "రవాణా"), c("repairs", "Repairs", "మరమ్మతులు"),
                        c("other", "Other", "ఇతర")],
        },
        "stock_template": [
            {"name": "Millet flour", "name_te": "మిల్లెట్ పిండి", "measure": "kg", "reorder_level": 5},
            {"name": "Milk", "name_te": "పాలు", "measure": "litre", "reorder_level": 5},
            {"name": "Jaggery", "name_te": "బెల్లం", "measure": "kg", "reorder_level": 2},
            {"name": "Gas cylinder", "name_te": "గ్యాస్ సిలిండర్", "measure": "cylinder", "reorder_level": 1},
            {"name": "Paper cups", "name_te": "పేపర్ కప్పులు", "measure": "pcs", "reorder_level": 100},
            {"name": "Packaged millet laddu", "name_te": "మిల్లెట్ లడ్డు ప్యాక్", "measure": "pack", "reorder_level": 10},
        ],
    },
    "tea_stall": {
        "ledger_categories": {
            "sale": [c("counter", "Counter sales", "కౌంటర్ అమ్మకాలు"), c("office", "Office / shop delivery", "ఆఫీస్ / షాప్ డెలివరీ"),
                     c("other_income", "Other income", "ఇతర ఆదాయం")],
            "expense": [c("milk", "Milk", "పాలు"), c("tea_powder", "Tea / coffee powder", "టీ / కాఫీ పొడి"), c("sugar", "Sugar", "చక్కెర"),
                        c("snacks", "Biscuits & snacks bought", "బిస్కెట్లు & స్నాక్స్ కొనుగోలు"), c("gas", "Gas", "గ్యాస్"),
                        c("cups_packing", "Cups", "కప్పులు"), c("rent", "Rent / spot fee", "అద్దె / స్థలం రుసుము"), c("other", "Other", "ఇతర")],
        },
        "stock_template": [
            {"name": "Milk", "name_te": "పాలు", "measure": "litre", "reorder_level": 5},
            {"name": "Tea powder", "name_te": "టీ పొడి", "measure": "kg", "reorder_level": 1},
            {"name": "Sugar", "name_te": "చక్కెర", "measure": "kg", "reorder_level": 2},
            {"name": "Biscuit packets", "name_te": "బిస్కెట్ ప్యాకెట్లు", "measure": "pack", "reorder_level": 20},
        ],
    },
    "drone_services": {
        "ledger_categories": {
            "sale": [c("spraying", "Spraying charges", "స్ప్రేయింగ్ ఛార్జీలు"), c("other_income", "Other income", "ఇతర ఆదాయం")],
            "expense": [c("fuel", "Fuel (generator, vehicle)", "ఇంధనం (జనరేటర్, వాహనం)"), c("charging", "Battery charging / power", "బ్యాటరీ ఛార్జింగ్ / కరెంటు"),
                        c("maintenance", "Maintenance & spares", "నిర్వహణ & విడి భాగాలు"), c("wages", "Assistant wages", "సహాయకుడి కూలీ"),
                        c("transport", "Transport", "రవాణా"), c("insurance", "Insurance & fees", "బీమా & రుసుములు"), c("other", "Other", "ఇతర")],
        },
        "stock_template": [{"name": "Diesel / petrol", "name_te": "డీజిల్ / పెట్రోల్", "measure": "litre", "reorder_level": 10}],
    },
}
