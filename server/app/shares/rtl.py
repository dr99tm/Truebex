"""Right-to-left text for the link-preview card (PF5a): Arabic shaping and
the Unicode Bidirectional Algorithm, in pure Python on the standard
library's Unicode data, so the card comes out the same on every machine.

Pillow lays text out right to left only through libraqm, whose wheels load
FriBiDi at runtime; neither the Windows PC that runs the tests nor the API
image has it. So the card does both steps here and Pillow only draws glyphs
left to right (`ImageFont.Layout.BASIC`):

* `shape()` joins Arabic letters into their presentation forms (isolated,
  final, initial, medial, and the lam-alef ligatures), read from the
  compatibility decompositions of U+FB50-U+FDFF and U+FE70-U+FEFF. That
  covers Arabic and the Persian and Urdu letters; a letter with no
  presentation forms (most of Arabic Supplement and Extended-A) answers None,
  so the card leaves the title off rather than draw it unjoined.
* `levels()` and `display()` run the Unicode Bidirectional Algorithm
  (UAX #9: P2-P3, W1-W7, N0-N2, I1-I2, L1, L2 and L4 mirroring) for one
  paragraph without explicit embeddings, so digits and Latin words inside an
  Arabic title keep their order. `clean()` drops the explicit embedding and
  isolate controls first. Checked against Unicode's BidiCharacterTest.txt and
  BidiTest.txt (docs/roadmap/40/PF5a-arabic-share-titles.md, As-built).
"""

import unicodedata

ISOLATED, FINAL, INITIAL, MEDIAL = "isolated", "final", "initial", "medial"
LAM = "\u0644"
ALEFS = "\u0622\u0623\u0625\u0627"  # with madda, hamza above, hamza below, plain: the lam-alef ligatures
TATWEEL, ZWNJ, ZWJ = "\u0640", "\u200c", "\u200d"
# LRE, RLE, PDF, LRO, RLO and LRI, RLI, FSI, PDI: not run here (no X1-X8), so dropped.
EXPLICIT = frozenset("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x0870, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))

# Bidi_Paired_Bracket pairs (BidiBrackets.txt, Unicode 15.0), opening then closing.
_BRACKET_PAIRS = (
    "()[]{}༺༻༼༽᚛᚜⁅⁆⁽⁾₍₎⌈⌉⌊⌋〈〉❨❩❪❫❬❭❮❯❰❱❲❳❴❵⟅⟆⟦⟧⟨⟩⟪⟫⟬⟭⟮⟯⦃⦄⦅⦆⦇⦈⦉⦊⦋⦌⦍⦐⦏⦎⦑⦒⦓⦔⦕⦖⦗⦘⧘⧙⧚⧛⧼⧽"
    "⸢⸣⸤⸥⸦⸧⸨⸩⹕⹖⹗⹘⹙⹚⹛⹜〈〉《》「」『』【】〔〕〖〗〘〙〚〛﹙﹚﹛﹜﹝﹞（）［］｛｝｟｠｢｣"
)
# Bidi_Mirroring_Glyph pairs drawn at an odd level (L4): the brackets and the
# other mirrored pairs the card's two fonts can draw.
_MIRROR_PAIRS = _BRACKET_PAIRS + "<>«»‹›≤≥"


def _canonical(ch: str) -> str:
    """U+2329 / U+232A compare equal to U+3008 / U+3009 (BD16)."""
    d = unicodedata.decomposition(ch)
    return chr(int(d, 16)) if d and " " not in d and not d.startswith("<") else ch


_OPENING = {_canonical(o): _canonical(c) for o, c in zip(_BRACKET_PAIRS[::2], _BRACKET_PAIRS[1::2])}
_CLOSING = set(_OPENING.values())
_MIRROR = {**dict(zip(_MIRROR_PAIRS[::2], _MIRROR_PAIRS[1::2])), **dict(zip(_MIRROR_PAIRS[1::2], _MIRROR_PAIRS[::2]))}


def _presentation_forms() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    forms: dict[str, dict[str, str]] = {}
    lam_alef: dict[str, dict[str, str]] = {}
    for cp in (*range(0xFB50, 0xFE00), *range(0xFE70, 0xFF00)):
        parts = unicodedata.decomposition(chr(cp)).split()
        if len(parts) < 2 or parts[0].strip("<>") not in (ISOLATED, FINAL, INITIAL, MEDIAL):
            continue
        form, base = parts[0].strip("<>"), [chr(int(p, 16)) for p in parts[1:]]
        if len(base) == 1:
            forms.setdefault(base[0], {}).setdefault(form, chr(cp))
        elif len(base) == 2 and base[0] == LAM and base[1] in ALEFS:
            lam_alef.setdefault(base[1], {}).setdefault(form, chr(cp))
    return forms, lam_alef


_FORMS, _LAM_ALEF = _presentation_forms()
# Where the forms Unicode encodes do not tell the joining type (ArabicShaping.txt):
# noon ghunna joins on both sides and U with hamza above on the right (their
# missing forms make a joined use answer None); the number signs join neither side.
_JOINING = {"\u06ba": "D", "\u0677": "R", **dict.fromkeys("\u0600\u0601\u0602\u0603\u0604\u0605\u06dd\u0890\u0891\u08e2", "U")}


def arabic(ch: str) -> bool:
    """True for a character of the Arabic blocks (letters, digits, punctuation, forms)."""
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in ARABIC_RANGES)


def bidi_class(ch: str) -> str:
    return unicodedata.bidirectional(ch) or "L"


def invisible(ch: str) -> bool:
    """A format character (LRM, RLM, ALM, ZWJ ...): steers the layout, never drawn."""
    return unicodedata.category(ch) == "Cf"


def needs_bidi(text: str) -> bool:
    """True when the text holds right-to-left letters or Arabic digits."""
    return any(bidi_class(ch) in ("R", "AL", "AN") for ch in text)


def clean(text: str) -> str:
    """NFC; combining marks (harakat, points) and explicit bidi controls dropped."""
    text = unicodedata.normalize("NFC", text)
    return "".join(ch for ch in text if ch not in EXPLICIT and unicodedata.category(ch) not in ("Mn", "Me"))


def _joining(ch: str) -> str:
    """Joining type: D dual, R right, C join-causing, U non-joining, T transparent,
    "?" an Arabic letter with no presentation forms (cannot be joined here)."""
    if ch in (TATWEEL, ZWJ):
        return "C"
    if ch in _JOINING:
        return _JOINING[ch]
    forms = _FORMS.get(ch)
    if forms and arabic(ch):
        if INITIAL in forms or MEDIAL in forms:
            return "D"
        return "R" if FINAL in forms else "U"
    category = unicodedata.category(ch)
    if category in ("Mn", "Me") or (category == "Cf" and ch != ZWNJ):
        return "T"
    if arabic(ch) and category == "Lo":
        return "?"
    return "U"


def shape(text: str) -> str | None:
    """Arabic letters in their joined presentation forms, in logical order;
    None when a letter cannot be joined (no presentation forms for it)."""
    kinds = [_joining(ch) for ch in text]
    if "?" in kinds:
        return None

    def neighbour(i: int, step: int) -> int | None:
        i += step
        while 0 <= i < len(text) and kinds[i] == "T":
            i += step
        return i if 0 <= i < len(text) else None

    out: list[str] = []
    skip = -1
    for i, ch in enumerate(text):
        if i == skip or ch in (ZWJ, ZWNJ):
            continue
        kind = kinds[i]
        if kind not in ("D", "R"):
            out.append(ch)
            continue
        before, after = neighbour(i, -1), neighbour(i, 1)
        joins_before = before is not None and kinds[before] in ("D", "C")
        joins_after = kind == "D" and after is not None and kinds[after] in ("D", "R", "C")
        if ch == LAM and after is not None and text[after] in _LAM_ALEF:
            form = FINAL if joins_before else ISOLATED
            ligature = _LAM_ALEF[text[after]].get(form)
            if ligature is None:
                return None
            out.append(ligature)
            skip = after
            continue
        form = (MEDIAL if joins_after else FINAL) if joins_before else (INITIAL if joins_after else ISOLATED)
        glyph = _FORMS.get(ch, {}).get(form)
        if glyph is None:
            return None
        out.append(glyph)
    return "".join(out)


def base_rtl(text: str) -> bool:
    """The paragraph's direction (P2-P3): its first strong character, else left to right."""
    for ch in text:
        kind = bidi_class(ch)
        if kind == "L":
            return False
        if kind in ("R", "AL"):
            return True
    return False


def _strong(kind: str) -> str | None:
    """L or R for N0-N2, where European and Arabic numbers count as R."""
    if kind == "L":
        return "L"
    return "R" if kind in ("R", "EN", "AN") else None


def resolve(classes: list[str], text: str | None, rtl: bool) -> list[int | None]:
    """Embedding levels (W1-I2, then L1) of one line laid out as one paragraph
    with no explicit embeddings; None for boundary neutrals (BN), which X9
    removes. `text` gives the brackets for N0 (None: no bracket pairs)."""
    para = 1 if rtl else 0
    e = "R" if rtl else "L"  # embedding direction, also sos and eos
    keep = [i for i, kind in enumerate(classes) if kind != "BN"]
    first = [classes[i] for i in keep]
    types = list(first)
    n = len(types)

    prev = e  # W1
    for k in range(n):
        if types[k] == "NSM":
            types[k] = prev
        prev = types[k]
    last = e  # W2
    for k in range(n):
        if types[k] in ("L", "R", "AL"):
            last = types[k]
        elif types[k] == "EN" and last == "AL":
            types[k] = "AN"
    types = ["R" if t == "AL" else t for t in types]  # W3
    for k in range(1, n - 1):  # W4
        if types[k] == "ES" and types[k - 1] == types[k + 1] == "EN":
            types[k] = "EN"
        elif types[k] == "CS" and types[k - 1] == types[k + 1] and types[k - 1] in ("EN", "AN"):
            types[k] = types[k - 1]
    k = 0  # W5
    while k < n:
        if types[k] != "ET":
            k += 1
            continue
        j = k
        while j < n and types[j] == "ET":
            j += 1
        if (k > 0 and types[k - 1] == "EN") or (j < n and types[j] == "EN"):
            types[k:j] = ["EN"] * (j - k)
        k = j
    types = ["ON" if t in ("ES", "ET", "CS") else t for t in types]  # W6
    last = e  # W7
    for k in range(n):
        if types[k] in ("L", "R"):
            last = types[k]
        elif types[k] == "EN" and last == "L":
            types[k] = "L"

    if text is not None:  # N0: bracket pairs (BD16), in order of their opening bracket
        pairs, stack = [], []
        for k in range(n):
            ch = _canonical(text[keep[k]])
            if types[k] != "ON":
                continue
            if ch in _OPENING:
                if len(stack) == 63:
                    break
                stack.append((_OPENING[ch], k))
            elif ch in _CLOSING:
                for s in range(len(stack) - 1, -1, -1):
                    if stack[s][0] == ch:
                        pairs.append((stack[s][1], k))
                        del stack[s:]
                        break
        for o, c in sorted(pairs):
            inside = {_strong(types[k]) for k in range(o + 1, c)} - {None}
            if e in inside:
                new = e
            elif inside:
                new = next((s for s in map(_strong, reversed(types[:o])) if s), e)
            else:
                continue
            for b in (o, c):
                types[b] = new
                k = b + 1
                while k < n and first[k] == "NSM":
                    types[k] = new
                    k += 1

    neutral = ("B", "S", "WS", "ON", "LRI", "RLI", "FSI", "PDI")
    k = 0  # N1, N2
    while k < n:
        if types[k] not in neutral:
            k += 1
            continue
        j = k
        while j < n and types[j] in neutral:
            j += 1
        before = e if k == 0 else _strong(types[k - 1])
        after = e if j == n else _strong(types[j])
        types[k:j] = [before if before == after else e] * (j - k)
        k = j

    levels: list[int | None] = [None] * len(classes)
    for k, t in enumerate(types):  # I1, I2
        if para == 0:
            levels[keep[k]] = 1 if t == "R" else 2 if t in ("AN", "EN") else 0
        else:
            levels[keep[k]] = 2 if t in ("L", "EN", "AN") else 1

    trailing = True  # L1: separators, and whitespace before them or at the end, at the paragraph level
    for i in range(len(classes) - 1, -1, -1):
        kind = classes[i]
        if kind in ("S", "B"):
            levels[i] = para
            trailing = True
        elif kind in ("WS", "LRI", "RLI", "FSI", "PDI", "BN"):
            if trailing and levels[i] is not None:
                levels[i] = para
        else:
            trailing = False
    return levels


def levels(text: str, rtl: bool) -> list[int | None]:
    return resolve([bidi_class(ch) for ch in text], text, rtl)


def reorder(levels: list[int | None]) -> list[int]:
    """L2: the logical indices in display order (left to right), BN left out."""
    order = [i for i, lvl in enumerate(levels) if lvl is not None]
    lv = [levels[i] for i in order]
    odd = [lvl for lvl in lv if lvl % 2]
    if not odd:
        return order
    for level in range(max(lv), min(odd) - 1, -1):
        k = 0
        while k < len(order):
            if lv[k] < level:
                k += 1
                continue
            j = k
            while j < len(order) and lv[j] >= level:
                j += 1
            order[k:j], lv[k:j] = order[k:j][::-1], lv[k:j][::-1]
            k = j
    return order


def display(text: str, rtl: bool) -> list[tuple[int, str]]:
    """(logical index, character to draw) left to right: reordered (L2) and
    mirrored at odd levels (L4); format characters (LRM, RLM, ZWJ) left out."""
    lv = levels(text, rtl)
    out = []
    for i in reorder(lv):
        ch = text[i]
        if invisible(ch):
            continue
        out.append((i, _MIRROR.get(ch, ch) if lv[i] % 2 else ch))
    return out


def visual(text: str, rtl: bool) -> str:
    """The text as drawn left to right."""
    return "".join(ch for _, ch in display(text, rtl))
