"""PF5a: share titles in Arabic script drawn on the link-preview card (joined,
right to left, right-aligned) and read in their own direction on the share
page; the serve-out.py helper's listen backlog."""

import importlib.util
import io
import re
import socket
import threading
import urllib.request
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat
from sqlalchemy import select

from app.database import SessionLocal
from app.shares import card, rtl
from app.shares.models import Share
from app.storage import get_store

from .licence_helpers import FP2
from .share_helpers import SHARE_FIXTURES, device_token, house, published

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
built = pytest.mark.skipif(not (OUT / "index.html").is_file(), reason="out/ not built (the verify gate builds it first)")

W, H, PAD = card.W, card.H, card.PAD
Y_BRAND = H - PAD - 30  # the mark is 30 px high
BAND = (Y_BRAND - 28 - 2 * card.LINE_PITCH - 20, Y_BRAND)  # two title lines and their descenders
KARRADA = "شقة الكرادة"
REVIEW = "شقة الكرادة — مراجعة العميل"
LONG = (
    "تصميم شقة سكنية حديثة في حي الكرادة ببغداد مع مطبخ مفتوح وغرفتي نوم وحمامين "
    "وشرفة تطل على نهر دجلة"
)


def forms(*codepoints: int) -> str:
    return "".join(map(chr, codepoints))


def ink(a: Image.Image, b: Image.Image) -> tuple[int, int, int, int] | None:
    """The box where two cards differ (None: the same pixels)."""
    return ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox()


def gaps(text: str) -> int:
    """Empty pixel columns inside a word drawn in the card's Arabic face."""
    img = Image.new("L", (1000, 140))
    ImageDraw.Draw(img).text((20, 100), text, font=card._basic(card.ARABIC, card.TITLE_SIZE), fill=255, anchor="ls")
    cols = [img.crop((x, 0, x + 1, 140)).getextrema()[1] > 64 for x in range(img.width)]
    inked = [x for x, c in enumerate(cols) if c]
    return sum(1 for x in range(inked[0], inked[-1]) if not cols[x])


def pf5_title(img: Image.Image, title: str) -> Image.Image:
    """The card's title exactly as PF5 drew it (card.py before PF5a): the oracle
    for "Latin titles render exactly as before"."""
    img = img.copy()
    d = ImageDraw.Draw(img)
    head = ImageFont.truetype(str(card.ASSETS / "OpenSans-Bold.ttf"), 56)
    if not (title and card.drawable(title, head)):
        return img
    width = W - 2 * 64
    words, out, line = title.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if d.textlength(trial, font=head) <= width:
            line = trial
            continue
        if line:
            out.append(line)
        line = word
        if len(out) == 2:
            break
    if line and len(out) < 2:
        out.append(line)
    if len(" ".join(out)) < len(" ".join(words)) and out:
        last = out[-1]
        while last and d.textlength(last + "…", font=head) > width:
            last = last[:-1]
        out[-1] = last.rstrip() + "…"
    y = Y_BRAND - 28 - 68 * len(out)
    for line in out:
        d.text((64, y), line, font=head, fill=card.TEXT)
        y += 68
    return img


@pytest.fixture(scope="module")
def room() -> Image.Image:
    """The house fixture's living room, as the card frames it."""
    pano = Image.open(SHARE_FIXTURES / "pano-2048.jpg").convert("RGB")
    return card.background_for(house(), pano, None)


# --- the card ------------------------------------------------------------------------


def test_pf5a_arabic_title_drawn_right_aligned(room):
    for background in (None, room):
        blank = card.render(background, "")
        box = ink(card.render(background, KARRADA), blank)
        assert box is not None, "the Arabic title is left off"
        left, top, right, bottom = box
        # In the title band, above the mark, and in the right part of it.
        assert BAND[0] <= top and bottom <= Y_BRAND
        assert left > W // 2 and W - PAD - 8 <= right <= W - PAD + 4
    # A Latin title still starts at the left margin.
    left, *_ = ink(card.render(None, "House — client review"), card.render(None, ""))
    assert PAD <= left <= PAD + 8


def test_pf5a_arabic_title_shaped():
    # Joined forms: sheen initial, qaf medial, teh marbuta final.
    assert rtl.shape("شقة") == forms(0xFEB7, 0xFED8, 0xFE94)
    # Lam-alef ligatures, alone and after a joining letter.
    assert rtl.shape("لا") == forms(0xFEFB)
    assert rtl.shape("سلام") == forms(0xFEB3, 0xFEFC, 0xFEE1)
    assert rtl.shape("للإهمال") == forms(0xFEDF, 0xFEFA, 0xFEEB, 0xFEE4, 0xFE8E, 0xFEDD)
    # Persian and Urdu letters; a zero-width non-joiner keeps its break.
    assert rtl.shape("پدری") == forms(0xFB58, 0xFEAA, 0xFEAD, 0xFBFC)
    assert rtl.shape("گھر") == forms(0xFB94, 0xFBAD, 0xFEAE)
    assert rtl.shape("خانه" + chr(0x200C) + "ی") == forms(0xFEA7, 0xFE8E, 0xFEE7, 0xFEEA, 0xFBFC)
    # Harakat are left off; the letters stay joined.
    assert rtl.shape(rtl.clean("شَقَّة")) == forms(0xFEB7, 0xFED8, 0xFE94)
    # The card draws the joined word: one stroke, narrower than its letters apart.
    for word in ("شقة", "بببب"):
        (runs,) = card.title_lines(word)[1]
        joined = rtl.visual(rtl.shape(word), True)
        assert runs == [(joined, card.ARABIC)]
        assert gaps(joined) == 0
        apart = "".join(rtl._FORMS[ch]["isolated"] for ch in reversed(word))
        assert gaps(apart) > 0
        font = card._basic(card.ARABIC, card.TITLE_SIZE)
        assert font.getlength(joined) < font.getlength(apart)


def test_pf5a_long_arabic_title_wraps_with_ellipsis(room):
    rtl_paragraph, lines = card.title_lines(LONG)
    assert rtl_paragraph and len(lines) == 2
    for runs in lines:
        assert card._width(runs) <= W - 2 * PAD
    # The ellipsis ends the second line where it is read last: at its left.
    assert lines[1][0][0].startswith("…") and lines[1][0][1] == card.LATIN
    assert all("…" not in text for text, _ in lines[0])
    # Two lines of ink in the band, the lower ending above the mark.
    diff = ImageChops.difference(card.render(room, LONG), card.render(room, "")).convert("L")
    rows = [y for y in range(H) if diff.crop((0, y, W, y + 1)).getextrema()[1] > 40]
    assert rows and BAND[0] <= rows[0] and rows[-1] < Y_BRAND
    first_line_top = Y_BRAND - 28 - 2 * card.LINE_PITCH
    assert any(y < first_line_top + card.LINE_PITCH - 10 for y in rows)  # line one
    assert any(y > first_line_top + card.LINE_PITCH + 10 for y in rows)  # line two


def test_pf5a_number_keeps_bidi_order():
    karrada = rtl.visual(rtl.shape("شقة"), True)
    assert rtl.visual(rtl.shape("شقة 2"), True) == "2 " + karrada
    (runs,) = card.title_lines("شقة 2")[1]
    assert "".join(text for text, _ in runs) == "2 " + karrada
    # Several digits stay in order; Latin words inside read left to right.
    assert rtl.visual(rtl.shape("شقة 12"), True) == "12 " + karrada
    shown = rtl.visual(rtl.shape("فيلا 3 – Villa 12B"), True)
    assert shown.startswith("Villa 12B – 3 ")
    # Invisible marks pasted with a title (RLM, LRM, ZWJ) steer the order and are never drawn.
    rlm, lrm, zwj = chr(0x200F), chr(0x200E), chr(0x200D)
    assert card.title_lines("شقة" + rlm + " 2" + lrm) == card.title_lines("شقة 2")
    # A zero-width joiner is not drawn, but it joins: the sheen takes its medial form.
    assert card.title_lines(zwj + "شقة 2")[1] == [[("2 " + forms(0xFE94, 0xFED8, 0xFEB8), card.ARABIC)]]
    # Brackets are mirrored where the line runs right to left (L4).
    shown = rtl.visual(rtl.shape("(شقة)"), True)
    assert shown == "(" + karrada + ")"
    # A title that starts in English reads left to right and starts at the left.
    rtl_paragraph, (runs,) = card.title_lines("Villa 12 — " + KARRADA)
    assert not rtl_paragraph
    assert runs == [("Villa 12 — ", card.LATIN), (rtl.visual(rtl.shape(KARRADA), True), card.ARABIC)]
    left, *_ = ink(card.render(None, "Villa 12 — " + KARRADA), card.render(None, ""))
    assert PAD <= left <= PAD + 8


def test_pf5a_latin_title_pixels_unchanged(room):
    titles = [
        "House — client review",
        "Flat <b>& garden</b>",
        "Ünïcödé Ελληνικά Кириллица 12 (draft)",
        "A very long title that keeps going past the edge of the card, so it wraps onto a "
        "second line and then needs an ellipsis because it still has words left over",
    ]
    for background in (None, room):
        blank = card.render(background, "")
        for title in titles:
            assert ink(card.render(background, title), pf5_title(blank, title)) is None, title
    # And the stored JPEG is PF5's encoding of those pixels.
    out = io.BytesIO()
    pf5_title(card.render(room, ""), titles[0]).save(out, format="JPEG", quality=86, optimize=True)
    assert card.compose(room, titles[0]) == out.getvalue()


def test_pf5a_cjk_title_still_left_off():
    blank = card.render(None, "")
    assert card.title_lines("设计图 شقة") is None
    # CJK (alone or with Arabic), a letter neither font has, and an Arabic
    # letter with no joined forms (Kurdish lam with a small v): left off.
    for title in ("設計図", "设计图 شقة", "شقة ★", "ماڵ"):
        assert ink(card.render(None, title), blank) is None, title
    # Hebrew (in Open Sans) is now drawn right to left, right-aligned.
    rtl_paragraph, (runs,) = card.title_lines("שלום עולם")
    assert rtl_paragraph and runs == [("םלוע םולש", card.LATIN)]
    left, _, right, _ = ink(card.render(None, "שלום עולם"), blank)
    assert left > W // 2 and right >= W - PAD - 8


# --- the real publish path ---------------------------------------------------------------


def test_pf5a_publish_arabic_title_card_drawn(client, room):
    token, _ = device_token(client)
    share = published(client, token, title=REVIEW)
    assert share["title"] == REVIEW
    with SessionLocal() as db:
        key = db.scalars(select(Share.card_key).where(Share.share_id == share["share_id"])).one()
    with get_store().open(key) as fh:
        stored = Image.open(io.BytesIO(fh.read())).convert("RGB")
    assert stored.size == (W, H)
    blank = Image.open(io.BytesIO(card.compose(room, ""))).convert("RGB")
    diff = ImageChops.difference(stored, blank).convert("L")
    # The room above the band is untouched; the band's right half carries the title.
    assert ImageStat.Stat(diff.crop((0, 0, W, BAND[0] - 16))).extrema[0][1] <= 2
    assert ImageStat.Stat(diff.crop((W // 2, BAND[0], W - PAD, Y_BRAND))).mean[0] > 8
    assert ImageStat.Stat(diff.crop((0, BAND[0], W // 4, Y_BRAND))).extrema[0][1] <= 24

    # The card route serves it, and the page keeps English as its language.
    res = client.get(f"/s/{share['slug']}/card.jpg")
    assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"
    html = client.get(f"/view/{share['slug']}").text
    assert '<html lang="en">' in html
    assert f'<h1 dir="auto">{REVIEW}</h1>' in html


# --- the share page -------------------------------------------------------------------


@built
def test_pf5a_viewer_names_dir_auto():
    js = OUT / "viewer" / "viewer.js"
    assert js.stat().st_size <= 250 * 1024
    code = js.read_text(encoding="utf-8")
    call = re.search(r'([\w$]+)\("h1","tbx-title",[\w$.]+,"auto"\)', code)
    assert call, "the share title is made without dir=auto"
    name = re.escape(call.group(1))
    assert re.search(rf'function {name}\([^)]*\)\{{[^}}]*\.dir=', code), "el() does not set dir"
    assert re.search(rf'{name}\("button","tbx-chip",[\w$.]+,"auto"\)', code), "room chips"
    for marker in ('createElement("figcaption")', '"tbx-drawings-info"', '"tbx-hotspot-label"'):
        at = code.index(marker)
        assert '.dir="auto"' in code[at : at + 400], marker
    css = (OUT / "viewer" / "viewer.css").read_text(encoding="utf-8")
    assert re.search(r"\.tbx-title\{[^}]*text-align:start", css)
    assert ".tbx-rooms:has(>.tbx-chip:first-child:dir(rtl)){direction:rtl}" in css


# --- scripts/serve-out.py --------------------------------------------------------------------


def test_pf5a_serve_out_backlog(tmp_path):
    spec = importlib.util.spec_from_file_location("serve_out", ROOT / "scripts" / "serve-out.py")
    serve_out = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(serve_out)
    assert serve_out.Server.request_queue_size >= 128
    (tmp_path / "viewer.js").write_text("export {};", encoding="utf-8")
    server = serve_out.make_server("127.0.0.1", 0, str(tmp_path))
    thread = None
    try:
        assert isinstance(server, serve_out.Server)
        port = server.server_address[1]
        # A dashboard's burst: 100 connections queued before the server accepts
        # any. With the standard library's backlog of 5 most are refused.
        burst = [socket.create_connection(("127.0.0.1", port), timeout=10) for _ in range(100)]
        for s in burst:
            s.close()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/viewer.js", timeout=10) as res:
            assert res.headers["Access-Control-Allow-Origin"] == "*"
            assert res.headers["Content-Type"].startswith("text/javascript")
            assert res.read() == b"export {};"
    finally:
        if thread is not None:
            server.shutdown()
        server.server_close()


# --- scripts/demo_share.py --title ----------------------------------------------------------


def test_pf5a_demo_share_title(client, monkeypatch, capsys):
    """The human test's uploader: --title publishes a share of its own with that title."""
    spec = importlib.util.spec_from_file_location("demo_share", Path(__file__).parents[1] / "scripts" / "demo_share.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)

    class _Same:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return client

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(demo.httpx, "Client", _Same)
    token, _ = device_token(client)
    fixture = str(SHARE_FIXTURES / "manifest-house.json")
    argv = ["--token", token, "--fixture", fixture, "--api", "http://testserver", "--title", REVIEW]
    assert demo.main(argv) == 0
    first = capsys.readouterr().out
    assert "5 parts sent" in first and "state live" in first
    assert demo.main(argv) == 0
    second = capsys.readouterr().out
    assert "0 parts sent" in second
    url = [line for line in first.splitlines() if line.startswith("url ")]
    assert url and url == [line for line in second.splitlines() if line.startswith("url ")]
    shares = client.get("/shares", headers={"Authorization": f"Bearer {token}", "X-Truebex-Contract": "share-bundle/1.0"})
    (share,) = shares.json()["shares"]
    assert share["title"] == REVIEW and share["bundle_id"] != house()["bundle_id"]

    # --rooms names the panoramas (and the hotspots that lead to them) in Arabic.
    other, _ = device_token(client, email="rooms@example.com", fingerprint=FP2)
    rooms = "غرفة المعيشة, المطبخ, الممر"
    argv = ["--token", other, "--fixture", fixture, "--api", "http://testserver", "--title", REVIEW, "--rooms", rooms]
    assert demo.main(argv) == 0
    slug = capsys.readouterr().out.split("/view/")[-1].strip()
    data = client.get(f"/s/{slug}", headers={"X-Truebex-Contract": "share-bundle/1.0"}).json()
    panoramas = data["manifest"]["panoramas"]
    assert [p["title"] for p in panoramas] == ["غرفة المعيشة", "المطبخ", "الممر"]
    assert [h["label"] for h in panoramas[0]["hotspots"]] == ["المطبخ", "الممر"]
