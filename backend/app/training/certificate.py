"""Training certificate as a PDF (A4 landscape), in English and Telugu, with a QR code that opens the public
verification page. Drawn with Pillow, whose HarfBuzz (raqm) layout engine shapes Telugu correctly – ReportLab's
canvas does not – then saved as a single-page PDF."""
import io
import re
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).resolve().parents[1] / "fonts"
W, H = 2339, 1654  # A4 landscape at 200 dpi
GREEN, GREEN2, GOLD, INK, INK2, CREAM = "#1f4d3a", "#2a6249", "#b8913a", "#1b2420", "#4c5a53", "#fbf8f1"
TELUGU = re.compile(r"[ఀ-౿]")


def _font(size: int, bold: bool = False, telugu: bool = False) -> ImageFont.FreeTypeFont:
    name = f"NotoSans{'Telugu' if telugu else ''}-{700 if bold else 400}.ttf"
    try:
        return ImageFont.truetype(str(FONTS / name), size, layout_engine=ImageFont.Layout.RAQM)
    except (OSError, KeyError):  # Pillow without raqm: still draws, Telugu joins less well
        return ImageFont.truetype(str(FONTS / name), size)


def _runs(text: str) -> list[tuple[str, bool]]:
    """Split a line into Telugu / non-Telugu runs (each script needs its own font)."""
    out: list[tuple[str, bool]] = []
    for ch in text or "":
        te = bool(TELUGU.match(ch)) or ch in "\u200c\u200d"
        if out and (ch == " " or out[-1][1] == te):
            out[-1] = (out[-1][0] + ch, out[-1][1])
        else:
            out.append((ch, te))
    return out


def _text(d: ImageDraw.ImageDraw, xy, text: str, size: int, bold=False, fill=INK, anchor="mm", max_w: int | None = None):
    """Draw one line (anchor "mm" = centred, "lm" = left), switching fonts between Telugu and Latin runs,
    and shrinking the size until it fits max_w."""
    runs = _runs(text)
    while True:
        fonts = [_font(size, bold, te) for _, te in runs]
        widths = [d.textlength(t, font=f) for (t, _), f in zip(runs, fonts)]
        if not max_w or size <= 14 or sum(widths) <= max_w:
            break
        size -= 2
    x, y = xy
    if anchor == "mm":
        x -= sum(widths) / 2
    base = y + size * 0.36  # baseline for a vertically centred line
    for (t, _), f, w in zip(runs, fonts, widths):
        d.text((x, base), t, font=f, fill=fill, anchor="ls")
        x += w


def _qr(url: str, box: int) -> Image.Image:
    import segno

    qr = segno.make(url, error="m")
    m = list(qr.matrix_iter(scale=1, border=2))
    n = len(m)
    img = Image.new("RGB", (n, n), "white")
    px = img.load()
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                px[x, y] = (0, 0, 0)
    return img.resize((box, box), Image.NEAREST)


def _leaf(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int):
    """Small brand mark: a rounded square with a sprout."""
    d.rounded_rectangle((cx - r, cy - r, cx + r, cy + r), radius=r // 3, fill=GREEN)
    d.line((cx - r // 2, cy + r // 2, cx, cy - r // 6), fill="#ffffff", width=max(3, r // 9))
    d.line((cx, cy - r // 6, cx + r // 2, cy - r // 2), fill="#ffffff", width=max(3, r // 9))
    d.ellipse((cx + r // 6, cy - r // 1.6, cx + r // 1.6, cy - r // 6), fill=GOLD)


def render(c: dict) -> bytes:
    """c: name, course_en, course_te, track_en, track_te, start, end, place, hours, certificate_no, issued (date),
    verify_url, sponsor (optional), result_note (optional)."""
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    # Frame
    d.rectangle((40, 40, W - 40, H - 40), outline=GREEN, width=14)
    d.rectangle((78, 78, W - 78, H - 78), outline=GOLD, width=4)
    for x, y in ((78, 78), (W - 78, 78), (78, H - 78), (W - 78, H - 78)):
        d.ellipse((x - 18, y - 18, x + 18, y + 18), fill=GOLD)
    # Header
    _leaf(d, W // 2 - 300, 205, 52)
    _text(d, (W // 2 - 220, 190), "MIRAI Shakthi", 64, True, GREEN, anchor="lm")
    _text(d, (W // 2 - 218, 248), "మిరాయ్ శక్తి · Enterprise programme", 30, False, INK2, anchor="lm")
    _text(d, (W // 2, 380), "CERTIFICATE OF COMPLETION", 72, True, GREEN)
    _text(d, (W // 2, 462), "శిక్షణ పూర్తి చేసినట్లు ధృవీకరణ పత్రం", 44, True, GREEN2)
    d.line((W // 2 - 260, 520, W // 2 + 260, 520), fill=GOLD, width=4)
    # Body
    _text(d, (W // 2, 590), "This is to certify that  ·  ఇది ధృవీకరించేది", 36, False, INK2)
    _text(d, (W // 2, 700), c["name"], 96, True, INK, max_w=W - 500)
    d.line((W // 2 - 520, 770, W // 2 + 520, 770), fill="#d8cfb8", width=3)
    _text(d, (W // 2, 840), "has successfully completed the  ·  విజయవంతంగా పూర్తి చేశారు", 36, False, INK2)
    _text(d, (W // 2, 930), c["course_en"], 64, True, GREEN, max_w=W - 500)
    if c.get("course_te"):
        _text(d, (W // 2, 1010), c["course_te"], 46, True, GREEN2, max_w=W - 500)
    period = f"{c['start']:%d %b %Y} – {c['end']:%d %b %Y}" if c["start"] != c["end"] else f"{c['start']:%d %b %Y}"
    details = f"{c['track_en']}  ·  {period}" + (f"  ·  {c['hours']:g} hours" if c.get("hours") else "") + (f"  ·  {c['place']}" if c.get("place") else "")
    _text(d, (W // 2, 1090), details, 34, False, INK, max_w=W - 400)
    if c.get("sponsor"):
        _text(d, (W // 2, 1145), f"Supported by {c['sponsor']}", 30, False, INK2, max_w=W - 400)
    # Signatures
    for x, role in ((560, "Trainer  ·  శిక్షకులు"), (1180, "Programme Manager  ·  ప్రోగ్రామ్ మేనేజర్")):
        d.line((x - 230, 1270, x + 230, 1270), fill=INK2, width=3)
        _text(d, (x, 1305), role, 26, False, INK2)
    # Certificate number and QR
    qr_box = 260
    qx, qy = W - 160 - qr_box, H - 160 - qr_box - 40
    img.paste(_qr(c["verify_url"], qr_box), (qx, qy))
    _text(d, (qx + qr_box // 2, qy + qr_box + 30), "Scan to verify · స్కాన్ చేసి నిర్ధారించండి", 22, False, INK2)
    _text(d, (160, H - 250), f"Certificate no. {c['certificate_no']}", 32, True, INK, anchor="lm")
    _text(d, (160, H - 200), f"Issued on {c['issued']:%d %B %Y}  ·  Check code {c.get('check_code', '')}", 28, False, INK2, anchor="lm")
    _text(d, (160, H - 155), "Verify at " + c["verify_url"].split("?")[0].rsplit("/", 1)[0] + "  (certificate number + check code)", 22, False, INK2, anchor="lm")
    out = io.BytesIO()
    img.save(out, "PDF", resolution=200.0, quality=88, title=f"Certificate {c['certificate_no']}", author="MIRAI Shakthi")
    return out.getvalue()


if __name__ == "__main__":  # quick visual check: python -m app.training.certificate
    pdf = render({"name": "సుజాత శ్రీలక్ష్మి", "course_en": "Core EDP", "course_te": "కోర్ ఈడీపీ", "track_en": "Core EDP",
                  "track_te": "కోర్ ఈడీపీ", "start": date(2026, 11, 2), "end": date(2026, 11, 13), "hours": 37, "place": "Tenali, Guntur",
                  "certificate_no": "MS-CORE-2026-00012", "issued": date(2026, 11, 14),
                  "verify_url": "https://miraimsme.com/#/verify/MS-CORE-2026-00012?c=K7Q2XA", "check_code": "K7Q2XA", "sponsor": "SBI Foundation (CSR)"})
    Path("certificate_sample.pdf").write_bytes(pdf)
    print(len(pdf), "bytes")
