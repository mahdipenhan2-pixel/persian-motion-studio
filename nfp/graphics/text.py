"""NFP Graphics - G2: text rules (standard library; no measuring, no process).

  direction(text, default)   reading direction of a text: from its first STRONG character (Unicode bidi class R / AL ->
                             rtl, L -> ltr); digits (Persian or Latin) and punctuation are not strong; no strong
                             character -> default. (Same rule as nfp/mapmotion/labels.direction, repeated here so the
                             Graphics core imports no other engine.)
  units(text)                the unbreakable pieces of one paragraph, joined by ordinary spaces into lines:
                             - only an ordinary space (U+0020) is a break opportunity: never a zero-width non-joiner
                               (U+200C, the Persian half-space: می‌شود stays whole), a no-break space (U+00A0, U+202F)
                               or anything else;
                             - a piece that is only punctuation / symbols, or the Persian object marker «را», never
                               starts a line: it stays with the piece before it.
  paragraphs(text, multiline) explicit line breaks (body only) split paragraphs.
  format_number(value, decimals, digits, unit)   the text of a number:
                             - rounded half away from zero to `decimals` places (exact decimal arithmetic);
                             - thousands grouped from 1 000 up;  fa: ۰-۹, ٬ (U+066C) and ٫ (U+066B);  en: 0-9 , .
                             - a negative value starts with the minus sign U+2212;
                             - unit "%" -> ٪ (U+066A) in fa / % in en, directly after the number; any other unit after a
                               no-break space (number and unit never split across lines);
                             - a Persian number (sign, digits, separators, ٪) is wrapped in a left-to-right isolate
                               (U+2066 ... U+2069): without it the Unicode bidi algorithm draws the same number differently
                               by context (rule W2: after a Persian letter the digits become "Arabic numbers" and the ٪
                               moves to the other side; checked in Chromium, G2). Isolated, it is always drawn
                               −۱٬۲۳۴٫۵٪ (sign left, ٪ right), as in a table. The unit word stays outside the isolate.
"""
import decimal
import unicodedata

ZWNJ, NBSP, NNBSP = "‌", " ", " "
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
SEP = {"fa": ("٬", "٫", "٪"), "en": (",", ".", "%")}
MINUS = "−"
LRI, PDI = "\u2066", "\u2069"          # left-to-right isolate ... pop directional isolate
GLUE_WORDS = {"را"}
LABEL = {"fa": {"source": "منبع: ", "draft": "پیش‌نویس", "dash": "— ", "quote": ("«", "»")},
         "en": {"source": "Source: ", "draft": "DRAFT", "dash": "— ", "quote": ("“", "”")}}


def direction(text, default="ltr"):
    for ch in text:
        b = unicodedata.bidirectional(ch)
        if b in ("R", "AL"):
            return "rtl"
        if b == "L":
            return "ltr"
    return default


def _glue(piece):
    return piece in GLUE_WORDS or all(unicodedata.category(ch)[0] in "PS" for ch in piece)


def units(paragraph):
    out = []
    for piece in paragraph.split(" "):
        if not piece:
            continue
        if out and _glue(piece):
            out[-1] = out[-1] + " " + piece
        else:
            out.append(piece)
    return out


def paragraphs(text, multiline):
    return text.split("\n") if multiline else [text]


def format_number(value, decimals=0, digits="en", unit=None):
    q = decimal.Decimal(1).scaleb(-decimals)
    d = decimal.Decimal(repr(float(value))).quantize(q, rounding=decimal.ROUND_HALF_UP)
    neg = d < 0 and d != 0
    s = f"{abs(d):f}"
    whole, _, frac = s.partition(".")
    grp = f"{int(whole):,}" if len(whole) > 3 else whole
    thou, dec, pct = SEP["fa" if digits == "fa" else "en"]
    grp = grp.replace(",", thou)
    out = grp + (dec + frac if frac else "")
    if digits == "fa":
        out = out.translate(FA_DIGITS)
    out = (MINUS if neg else "") + out + (pct if unit == "%" else "")
    if digits == "fa":
        out = LRI + out + PDI          # one unit, the same in every context (see the module doc)
    return out + (NBSP + unit if unit and unit != "%" else "")
