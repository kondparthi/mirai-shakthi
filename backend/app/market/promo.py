"""Promotional materials (M8): a WhatsApp message and a poster (PNG, 1080 × 1350) in Telugu or English.
The AI writes the title, tagline and message from the unit's real listings and prices; it must not invent offers or
prices. Without AI a template writes them. Prices print as "రూ." / "Rs." (the bundled fonts have no ₹ sign)."""
from __future__ import annotations

import io
import json

from PIL import Image, ImageDraw

from ..guidance import llm
from ..training.certificate import GOLD, _qr, _text

W, H = 1080, 1350
FOREST, EMERALD, CREAM, INK, INK2 = "#0f3d2e", "#16825d", "#fbf8f1", "#1b2420", "#4c5a53"
OCCASIONS = {
    "launch": ("Now open!", "కొత్తగా ప్రారంభం!"),
    "daily": ("Today's special", "ఈరోజు ప్రత్యేకం"),
    "festival": ("Festival special", "పండుగ ప్రత్యేకం"),
    "bulk": ("Orders for offices, schools and events", "ఆఫీసులు, పాఠశాలలు, వేడుకలకు ఆర్డర్లు"),
    "booking": ("Book now", "ఇప్పుడే బుక్ చేసుకోండి"),
}
UNIT_WORD = {"plate": "ప్లేట్", "glass": "గ్లాస్", "cup": "కప్", "kg": "కిలో", "litre": "లీటర్", "acre": "ఎకరం", "pack": "ప్యాక్",
             "each": "ఒక్కటి", "hour": "గంట", "day": "రోజు", "piece": "ఒక్కటి"}


def price(v: float, unit: str, lang: str) -> str:
    n = f"{v:,.0f}" if v == int(v) else f"{v:,.2f}"
    return f"రూ. {n} / {UNIT_WORD.get(unit, unit)}" if lang == "te" else f"Rs. {n} / {unit}"


def template(ctx: dict, lang: str, occasion: str) -> dict:
    te = lang == "te"
    title = OCCASIONS.get(occasion, OCCASIONS["daily"])[1 if te else 0]
    items = ctx["items"][:6]
    lines = "\n".join(f"• {(i.get('name_te') or i['name']) if te else i['name']} – {price(i['price'], i['unit'], lang)}" for i in items)
    where = ctx.get("place") or ""
    if te:
        tagline = f"{where}లో తాజాగా, శుభ్రంగా – మిరాయ్ శక్తి వ్యాపారం" if where else "తాజాగా, శుభ్రంగా – మిరాయ్ శక్తి వ్యాపారం"
        msg = f"*{ctx['unit']}* – {title}\n{tagline}\n\n{lines}\n\nఆర్డర్ కోసం కాల్ / వాట్సాప్: {ctx['mobile']}"
        if ctx.get("shop_url"):
            msg += f"\nఆన్‌లైన్‌లో ఆర్డర్ / బుక్ చేయండి: {ctx['shop_url']}"
    else:
        tagline = f"Fresh and clean, in {where} – a MIRAI Shakthi enterprise" if where else "Fresh and clean – a MIRAI Shakthi enterprise"
        msg = f"*{ctx['unit']}* – {title}\n{tagline}\n\n{lines}\n\nCall / WhatsApp to order: {ctx['mobile']}"
        if ctx.get("shop_url"):
            msg += f"\nOrder or book online: {ctx['shop_url']}"
    return {"title": title, "tagline": tagline, "message": msg}


SYSTEM = ("You write short promotional text for a small rural business in Andhra Pradesh, run by a woman entrepreneur supported by "
          "MIRAI Shakthi. Write in {lang}. Warm, simple words that village and town customers use. Use ONLY the products, prices "
          "and contact given; never invent discounts, offers, awards, health claims or prices. Prices are written exactly as given. "
          "Return JSON with: title (max 6 words), tagline (max 14 words), message (a WhatsApp message under 90 words that lists the "
          "items with prices and ends with the contact and the online link if given).")


def draft(ctx: dict, lang: str, occasion: str) -> tuple[dict, str]:
    base = template(ctx, lang, occasion)
    facts = {"unit": ctx["unit"], "place": ctx.get("place"), "occasion": OCCASIONS.get(occasion, OCCASIONS["daily"])[0],
             "items": [{"name": (i.get("name_te") or i["name"]) if lang == "te" else i["name"], "price": price(i["price"], i["unit"], lang)} for i in ctx["items"][:6]],
             "contact": ctx["mobile"], "online_link": ctx.get("shop_url")}
    got = llm.complete_json(SYSTEM.format(lang="Telugu (Telugu script)" if lang == "te" else "English"), json.dumps(facts, ensure_ascii=False), max_tokens=700)
    if not got:
        return base, "template"
    out = {k: (str(got.get(k)).strip() if isinstance(got.get(k), str) and got.get(k).strip() else base[k]) for k in ("title", "tagline", "message")}
    out["title"], out["tagline"] = out["title"][:60], out["tagline"][:160]
    return out, "ai"


def poster(ctx: dict, text: dict, lang: str) -> bytes:
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    # header band with a soft gradient
    for y in range(0, 520):
        t = y / 520
        r = int(0x16 + (0x0f - 0x16) * t)
        g = int(0x82 + (0x3d - 0x82) * t)
        b = int(0x5d + (0x2e - 0x5d) * t)
        d.line((0, y, W, y), fill=(r, g, b))
    d.ellipse((W - 260, -160, W + 160, 260), fill="#2a9a72")
    d.ellipse((W - 200, 300, W + 40, 540), fill="#f6a821")
    _text(d, (70, 90), "MIRAI Shakthi · మిరాయ్ శక్తి", 30, True, "#ffd27a", anchor="lm")
    _text(d, (70, 190), ctx["unit"], 64, True, "#ffffff", anchor="lm", max_w=W - 260)
    _text(d, (70, 290), text["title"], 58, True, "#ffe7b0", anchor="lm", max_w=W - 200)
    _text(d, (70, 375), text["tagline"], 32, False, "#e6f3ed", anchor="lm", max_w=W - 330)
    if ctx.get("place") and ctx["place"] not in text["tagline"]:
        _text(d, (70, 450), ctx["place"], 28, False, "#cfe8dc", anchor="lm", max_w=W - 320)
    # items
    y = 600
    for i in ctx["items"][:5]:
        name = (i.get("name_te") or i["name"]) if lang == "te" else i["name"]
        d.rounded_rectangle((60, y - 48, W - 60, y + 48), radius=24, fill="#ffffff", outline="#e3ece7", width=2)
        _text(d, (100, y), name, 38, True, INK, anchor="lm", max_w=560)
        p = price(i["price"], i["unit"], lang)
        _text(d, (680, y), p, 36, True, EMERALD, anchor="lm", max_w=340)
        y += 118
    # contact + QR
    base = H - 290
    d.rounded_rectangle((60, base, W - 60, H - 60), radius=28, fill=FOREST)
    _text(d, (100, base + 70), "ఆర్డర్ / బుకింగ్" if lang == "te" else "Order / booking", 34, True, "#ffd27a", anchor="lm")
    _text(d, (100, base + 140), ctx["mobile"], 64, True, "#ffffff", anchor="lm")
    _text(d, (100, base + 200), "కాల్ లేదా వాట్సాప్ చేయండి" if lang == "te" else "Call or WhatsApp", 30, False, "#cfe8dc", anchor="lm")
    if ctx.get("shop_url"):
        q = 168
        img.paste(_qr(ctx["shop_url"], q), (W - 60 - 40 - q, base + 16))
        _text(d, (W - 100 - q // 2, base + q + 38), "స్కాన్ చేసి ఆర్డర్" if lang == "te" else "Scan to order", 22, False, "#cfe8dc")
    d.line((60, H - 40, W - 60, H - 40), fill=GOLD, width=4)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()
