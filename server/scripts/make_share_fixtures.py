"""Write the share-bundle contract fixtures (share-bundle.md v1.0.0, §9).

    .venv\\Scripts\\python.exe scripts\\make_share_fixtures.py [--out DIR]

Deterministic: re-running reproduces the JSON byte for byte, and the images
and the PDF too with the same Pillow build. Until the app repo carries them
in `Docs/roadmap/fixtures/contracts/share-bundle/`, this script is their
source; from then on the platform keeps a copy, copied, never edited.

Files:
    pano-2048.jpg, pano-2048-kitchen.jpg, pano-2048-hall.jpg
        2048 x 1024 equirectangular rooms drawn by ray casting a box room:
        N / E / S / W painted at their true bearings, a doorway where each
        hotspot points, so the viewer's bearings can be checked by eye
    render-640.jpg      640 x 360 "Street view"
    sheets-2p.pdf       a two-page vector PDF (plan + sections), Helvetica
    manifest-house.json a valid truebex-share/1 manifest of the files above
    manifest-invalid.json  cases: each manifest and the data.errors[] it earns
    visits.json         visits to replay and the 5.7 `visits` they produce
"""

import argparse
import copy
import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SERVER = Path(__file__).resolve().parents[1]
OUT = SERVER / "tests" / "contracts" / "share-bundle"
FONT = SERVER / "app" / "shares" / "assets" / "OpenSans-Bold.ttf"

PANO_W, PANO_H = 2048, 1024
BUNDLE_ID = "4f2a9c1e7b3d4e5f8a6b0c2d1e3f5a7b"


# --- equirectangular rooms ------------------------------------------------------


def _mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


class Room:
    """A box room: x east, y north, z up (metres); doors and windows on walls."""

    def __init__(self, name, size, eye, wall, floor, accent, center_bearing):
        self.name = name
        self.w, self.d, self.h = size
        self.eye = eye
        self.wall = wall
        self.floor = floor
        self.accent = accent
        self.center = center_bearing
        self.openings = []  # (wall, s0, s1, z0, z1, kind, colour)
        self.bands = []  # (walls, z0, z1, colour): counters, cabinets

    def wall_point(self, bearing):
        """Which wall the horizontal ray at `bearing` hits, and where along it."""
        b = math.radians(bearing)
        dx, dy = math.sin(b), math.cos(b)
        return self._hit(dx, dy, 0.0)[:2]

    def door(self, bearing, width=0.9, colour=(70, 64, 58)):
        wall, s = self.wall_point(bearing)
        self.openings.append((wall, s - width / 2, s + width / 2, 0.0, 2.1, "door", colour))

    def window(self, bearing, width, z0=0.9, z1=2.2):
        wall, s = self.wall_point(bearing)
        self.openings.append((wall, s - width / 2, s + width / 2, z0, z1, "window", None))

    def _hit(self, dx, dy, dz):
        ex, ey, ez = self.eye
        x0, x1, y0, y1 = -self.w / 2, self.w / 2, -self.d / 2, self.d / 2
        best = (math.inf, None)
        if dx > 1e-9:
            best = min(best, ((x1 - ex) / dx, "E"))
        elif dx < -1e-9:
            best = min(best, ((x0 - ex) / dx, "W"))
        if dy > 1e-9:
            best = min(best, ((y1 - ey) / dy, "N"))
        elif dy < -1e-9:
            best = min(best, ((y0 - ey) / dy, "S"))
        if dz > 1e-9:
            best = min(best, ((self.h - ez) / dz, "C"))
        elif dz < -1e-9:
            best = min(best, ((0.0 - ez) / dz, "F"))
        t, surface = best
        px, py, pz = ex + t * dx, ey + t * dy, ez + t * dz
        # Position along the wall, left to right as seen from inside.
        s = {"N": px, "S": -px, "E": -py, "W": py}.get(surface, 0.0)
        return surface, s, pz, px, py, t

    def shade(self, dx, dy, dz, lat):
        surface, s, z, px, py, t = self._hit(dx, dy, dz)
        if surface == "F":
            plank = math.floor((px + 10) / 0.19)
            tint = ((plank * 7919) % 13) / 13.0
            col = _mix(self.floor, (self.floor[0] * 0.8, self.floor[1] * 0.78, self.floor[2] * 0.75), tint)
            if ((px + 10) / 0.19) % 1.0 < 0.04:
                col = _mix(col, (40, 30, 22), 0.5)
            return _mix(col, (20, 20, 20), min(0.35, t / 25))
        if surface == "C":
            return _mix((236, 234, 230), (200, 198, 194), min(1.0, t / 8))
        for wall, s0, s1, z0, z1, kind, colour in self.openings:
            if wall == surface and s0 <= s <= s1 and z0 <= z <= z1:
                frame = min(s - s0, s1 - s, z - z0 if z0 > 0 else 1, z1 - z)
                if frame < 0.06:
                    return (58, 58, 60)
                if kind == "door":
                    return _mix(colour, (25, 25, 25), 0.25 + 0.5 * (z / 2.1))
                if abs(s - (s0 + s1) / 2) < 0.025:
                    return (58, 58, 60)
                if lat >= 0:
                    return _mix((214, 232, 248), (120, 170, 225), min(1.0, lat / 0.6))
                return _mix((120, 150, 96), (78, 104, 62), min(1.0, -lat / 0.4))
        for walls, z0, z1, colour in self.bands:
            if surface in walls and z0 <= z <= z1:
                return colour
        light = {"N": 1.0, "E": 0.94, "S": 0.86, "W": 0.9}[surface]
        col = tuple(c * light for c in self.wall)
        if z < 0.1:
            col = (235, 233, 228)  # skirting
        corner = min(abs(self.w / 2 - abs(px)), abs(self.d / 2 - abs(py)), z, self.h - z)
        return _mix(col, (60, 58, 55), max(0.0, 0.18 - corner * 0.25))


def render_room(room: Room, labels: list[tuple[float, float, str, int]]) -> Image.Image:
    buf = bytearray(PANO_W * PANO_H * 3)
    i = 0
    for v in range(PANO_H):
        lat = math.pi / 2 - (v + 0.5) / PANO_H * math.pi
        cl, sl = math.cos(lat), math.sin(lat)
        for u in range(PANO_W):
            bearing = math.radians(room.center) + (u + 0.5) / PANO_W * 2 * math.pi - math.pi
            r, g, b = room.shade(math.sin(bearing) * cl, math.cos(bearing) * cl, sl, lat)
            buf[i] = int(r)
            buf[i + 1] = int(g)
            buf[i + 2] = int(b)
            i += 3
    img = Image.frombytes("RGB", (PANO_W, PANO_H), bytes(buf))
    draw = ImageDraw.Draw(img)
    for bearing, pitch, text, size in labels:
        font = ImageFont.truetype(str(FONT), size)
        rel = ((bearing - room.center + 180) % 360) - 180
        x = (rel + 180) / 360 * PANO_W
        y = (90 - pitch) / 180 * PANO_H
        box = draw.textbbox((0, 0), text, font=font)
        draw.text((x - (box[2] - box[0]) / 2, y - (box[3] - box[1]) / 2), text, font=font, fill=(64, 62, 60))
    return img


def compass() -> list[tuple[float, float, str, int]]:
    return [(b, 22, t, 44) for b, t in ((0, "N"), (90, "E"), (180, "S"), (270, "W"))]


def living_room() -> Image.Image:
    room = Room("Living room", (6.0, 4.8, 2.7), (-0.5, 0.3, 1.6), (226, 214, 196), (168, 124, 84), None, 0)
    room.window(10, 2.0)
    room.window(75, 1.2, 1.0, 2.2)
    room.door(132.5, colour=(150, 176, 150))  # to the kitchen
    room.door(270, colour=(150, 160, 178))  # to the hall
    return render_room(room, compass() + [(100, 8, "Living room", 36), (132.5, 4, "Kitchen", 26), (270, 4, "Hall", 26)])


def kitchen() -> Image.Image:
    room = Room("Kitchen", (4.0, 3.6, 2.7), (0.0, 0.0, 1.6), (196, 214, 194), (196, 196, 190), None, 90)
    room.door(340, colour=(226, 214, 196))  # back to the living room
    room.window(100, 1.4, 1.05, 2.0)
    room.bands = [("ES", 0.86, 0.92, (52, 52, 54)), ("ES", 0.1, 0.86, (238, 238, 236)), ("E", 1.5, 2.25, (238, 238, 236))]
    return render_room(room, compass() + [(120, 30, "Kitchen", 36), (340, 4, "Living room", 26)])


def hall() -> Image.Image:
    room = Room("Hall", (2.0, 5.0, 2.7), (0.0, 0.0, 1.6), (194, 202, 214), (150, 112, 78), None, 0)
    room.door(73, colour=(226, 214, 196))  # to the living room
    room.door(180, 1.0, colour=(90, 110, 140))  # front door
    return render_room(room, compass() + [(0, 8, "Hall", 36), (73, 4, "Living room", 26)])


def street_view() -> Image.Image:
    img = Image.new("RGB", (640, 360))
    d = ImageDraw.Draw(img)
    for y in range(360):
        t = y / 360
        d.line([(0, y), (640, y)], fill=tuple(int(c) for c in _mix((150, 190, 232), (226, 236, 246), t)))
    d.rectangle((0, 280, 640, 360), fill=(108, 136, 86))
    d.rectangle((0, 300, 640, 312), fill=(120, 120, 118))
    d.rectangle((150, 150, 490, 290), fill=(232, 226, 214))
    d.polygon([(130, 152), (320, 70), (510, 152)], fill=(86, 74, 70))
    for x in (180, 270, 380):
        d.rectangle((x, 180, x + 60, 230), fill=(120, 160, 205))
        d.line([(x + 30, 180), (x + 30, 230)], fill=(240, 240, 240), width=3)
    d.rectangle((300, 236, 340, 290), fill=(70, 64, 58))
    font = ImageFont.truetype(str(FONT), 18)
    d.text((16, 14), "Street view", font=font, fill=(40, 40, 40))
    return img


def jpeg(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


# --- the sheet PDF (hand-written, vector) -------------------------------------------


def _pdf(pages: list[bytes]) -> bytes:
    objs: list[bytes] = []
    n_pages = len(pages)
    font_regular = 3 + 2 * n_pages
    font_bold = font_regular + 1
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    for i, content in enumerate(pages):
        objs.append(
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] "
                f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R >> >> "
                f"/Contents {4 + 2 * i} 0 R >>"
            ).encode()
        )
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for n, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _text(x, y, size, text, bold=False) -> str:
    return f"BT /{'F2' if bold else 'F1'} {size} Tf {x} {y} Td ({text}) Tj ET\n"


def _title_block(number: str, title: str) -> str:
    s = "0.2 G 1 w 20 20 802 555 re S\n"
    s += "562 20 260 90 re S 562 70 m 822 70 l S\n"
    s += _text(574, 84, 16, number, True) + _text(640, 84, 12, title)
    s += _text(574, 48, 10, "House") + _text(574, 32, 9, "Scale 1:50 at A3") + _text(720, 32, 9, "Drawn in Truebex")
    return s


def sheets_pdf() -> bytes:
    plan = _title_block("A-101", "Ground floor plan")
    plan += "0.15 g\n"
    # Outer walls (300 mm) and partitions (100 mm), 1:50 at 1 pt = 1 mm / 50 * 2.83.
    for x, y, w, h in ((80, 140, 420, 12), (80, 140, 12, 300), (80, 428, 420, 12), (488, 140, 12, 300), (300, 152, 6, 276), (92, 300, 208, 6)):
        plan += f"{x} {y} {w} {h} re f\n"
    plan += "1 g 400 140 50 12 re f 300 220 6 40 re f 0.15 g\n"  # door openings
    plan += _text(360, 300, 14, "Living room", True) + _text(150, 220, 12, "Kitchen", True) + _text(160, 370, 12, "Hall", True)
    plan += "0.4 G 0.5 w 80 110 m 500 110 l S 80 104 m 80 116 l S 500 104 m 500 116 l S\n"
    plan += _text(270, 114, 9, "7 400")
    sections = _title_block("A-102", "Sections")
    sections += "0.15 g 80 140 440 10 re f 80 150 10 200 re f 510 150 10 200 re f\n"
    sections += "0.15 g 70 350 460 10 re f\n0.5 G 1 w 70 360 m 300 470 l 530 360 l S\n"
    sections += _text(240, 250, 14, "Section A-A", True) + _text(100, 160, 9, "FFL +0.000") + _text(100, 336, 9, "Ceiling +2.700")
    return _pdf([plan.encode(), sections.encode()])


# --- manifests ----------------------------------------------------------------


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def house_manifest(files: dict[str, bytes]) -> dict:
    h = {name: sha(data) for name, data in files.items()}
    return {
        "schema": "truebex-share/1",
        "bundle_id": BUNDLE_ID,
        "created_at": "2026-10-09T10:00:00Z",
        "app_version": "1.1.0",
        "watermark": True,
        "project": {"title": "House", "project_id": None, "units": "metric", "region": "GB"},
        "start": "p1",
        "panoramas": [
            {
                "id": "p1", "title": "Living room", "file": h["pano-2048.jpg"], "width": 2048, "height": 1024,
                "storey": "Ground", "eye_mm": [4200, 1800, 1600], "center_bearing_deg": 0,
                "start_bearing_deg": 90, "start_pitch_deg": 0, "start_hfov_deg": 75,
                "hotspots": [
                    {"target": "p2", "bearing_deg": 132.5, "pitch_deg": -8, "label": "Kitchen"},
                    {"target": "p3", "bearing_deg": 270, "pitch_deg": -8, "label": "Hall"},
                ],
            },
            {
                "id": "p2", "title": "Kitchen", "file": h["pano-2048-kitchen.jpg"], "width": 2048, "height": 1024,
                "storey": "Ground", "eye_mm": [8100, 600, 1600], "center_bearing_deg": 90,
                "start_bearing_deg": 120, "start_pitch_deg": -5, "start_hfov_deg": 80,
                "hotspots": [{"target": "p1", "bearing_deg": 340, "pitch_deg": -8, "label": "Living room"}],
            },
            {
                "id": "p3", "title": "Hall", "file": h["pano-2048-hall.jpg"], "width": 2048, "height": 1024,
                "storey": "Ground", "eye_mm": [1000, 2100, 1600], "center_bearing_deg": 0,
                "start_bearing_deg": 73, "start_pitch_deg": 0, "start_hfov_deg": 75,
                "hotspots": [{"target": "p1", "bearing_deg": 73, "pitch_deg": -8, "label": "Living room"}],
            },
        ],
        "renders": [{"id": "r1", "title": "Street view", "file": h["render-640.jpg"], "width": 640, "height": 360}],
        "sheets": {"file": h["sheets-2p.pdf"], "pages": 2, "titles": ["A-101 Ground floor plan", "A-102 Sections"]},
        "files": [
            {"sha256": h["pano-2048.jpg"], "bytes": len(files["pano-2048.jpg"]), "content_type": "image/jpeg", "name": "living-room.jpg"},
            {"sha256": h["pano-2048-kitchen.jpg"], "bytes": len(files["pano-2048-kitchen.jpg"]), "content_type": "image/jpeg", "name": "kitchen.jpg"},
            {"sha256": h["pano-2048-hall.jpg"], "bytes": len(files["pano-2048-hall.jpg"]), "content_type": "image/jpeg", "name": "hall.jpg"},
            {"sha256": h["render-640.jpg"], "bytes": len(files["render-640.jpg"]), "content_type": "image/jpeg", "name": "street-view.jpg"},
            {"sha256": h["sheets-2p.pdf"], "bytes": len(files["sheets-2p.pdf"]), "content_type": "application/pdf", "name": "drawings.pdf"},
        ],
    }


def invalid_cases(valid: dict) -> dict:
    other = "0" * 63 + "1"

    def case(name, note, edit, errors):
        m = copy.deepcopy(valid)
        edit(m)
        return {"name": name, "note": note, "manifest": m,
                "expect": {"status": 422, "code": "manifest_invalid", "errors": [{"path": p, "rule": r} for p, r in errors]}}

    def unreferenced(m):
        m["files"].append({"sha256": other, "bytes": 10, "content_type": "image/png", "name": "extra.png"})

    def sheets_png(m):
        m["files"][4]["content_type"] = "image/png"

    cases = [
        case("pano-3-to-1", "a 3:1 panorama", lambda m: m["panoramas"][1].update(width=3072, height=1024),
             [("panoramas[1].width", "pano_size")]),
        case("hotspot-missing-target", "a hotspot to a missing id",
             lambda m: m["panoramas"][0]["hotspots"][0].update(target="p9"),
             [("panoramas[0].hotspots[0].target", "hotspot_target")]),
        case("file-not-listed", "a file not listed", lambda m: m["renders"].append(
             {"id": "r2", "title": "Garden", "file": other, "width": 640, "height": 360}),
             [("renders[1].file", "file_listed")]),
        case("schema-major", "a MAJOR this server does not read", lambda m: m.update(schema="truebex-share/2"),
             [("schema", "schema")]),
        case("title-too-long", "project title over 120 characters", lambda m: m["project"].update(title="T" * 121),
             [("project.title", "text_length")]),
        case("label-too-long", "hotspot label over 60 characters",
             lambda m: m["panoramas"][0]["hotspots"][0].update(label="L" * 61),
             [("panoramas[0].hotspots[0].label", "text_length")]),
        case("bearing-out-of-range", "a start bearing of 400 degrees",
             lambda m: m["panoramas"][0].update(start_bearing_deg=400), [("panoramas[0].start_bearing_deg", "bearing")]),
        case("pitch-out-of-range", "a hotspot below straight down",
             lambda m: m["panoramas"][0]["hotspots"][1].update(pitch_deg=-95),
             [("panoramas[0].hotspots[1].pitch_deg", "pitch")]),
        case("render-too-large", "a render wider than 8192 px", lambda m: m["renders"][0].update(width=9000, height=5000),
             [("renders[0].width", "render_size")]),
        case("sheets-not-pdf", "the sheets file is not a PDF", sheets_png, [("sheets.file", "sheets_type")]),
        case("file-unreferenced", "a listed file nothing uses (nothing else travels)", unreferenced,
             [("files[5]", "file_referenced")]),
        case("start-not-a-panorama", "start names a render", lambda m: m.update(start="r1"), [("start", "start")]),
        case("duplicate-id", "two renders share an id", lambda m: m["renders"].append(
             {**m["renders"][0], "title": "Street view again"}),
             [("renders[1].id", "id_unique")]),
        case("path-in-name", "a file name carrying a folder", lambda m: m["files"][0].update(name="C:\\Users\\me\\living.jpg"),
             [("files[0].name", "file_name")]),
    ]
    return {
        "note": "Each case is manifest-house.json with one thing broken; POST /shares answers `expect` "
        "(data.errors[] exactly, in order). Rules are share-bundle.md §6.1, one id per table row.",
        "cases": cases,
    }


def visits() -> dict:
    a, b, c = ("a" * 32, "b" * 32, "c" * 32)
    return {
        "note": "POST /s/{slug}/visits at each `at` (UTC); GET /shares/{id} then reports `expect` as `visits` "
        "(by_day: the last 30 days, oldest first; count = visits, unique = distinct visitors that day).",
        "visits": [
            {"visitor": a, "at": "2026-10-08T21:00:00Z"},
            {"visitor": a, "at": "2026-10-09T08:00:00Z"},
            {"visitor": a, "at": "2026-10-09T08:05:00Z"},
            {"visitor": b, "at": "2026-10-09T09:00:00Z"},
            {"visitor": c, "at": "2026-10-09T23:59:59Z"},
        ],
        "now": "2026-10-10T00:00:00Z",
        "expect": {
            "total": 5,
            "unique": 4,
            "last_at": "2026-10-09T23:59:59Z",
            "by_day": [{"day": "2026-10-08", "count": 1, "unique": 1}, {"day": "2026-10-09", "count": 4, "unique": 3}],
        },
    }


def build() -> dict[str, bytes]:
    files = {
        "pano-2048.jpg": jpeg(living_room()),
        "pano-2048-kitchen.jpg": jpeg(kitchen()),
        "pano-2048-hall.jpg": jpeg(hall()),
        "render-640.jpg": jpeg(street_view()),
        "sheets-2p.pdf": sheets_pdf(),
    }
    house = house_manifest(files)

    def dump(obj) -> bytes:
        return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    out = dict(files)
    out["manifest-house.json"] = dump(house)
    out["manifest-invalid.json"] = dump(invalid_cases(house))
    out["visits.json"] = dump(visits())
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, data in build().items():
        (args.out / name).write_bytes(data)
        print(f"{name:24} {len(data):>8} bytes")


if __name__ == "__main__":
    main()
