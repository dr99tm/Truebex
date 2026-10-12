r"""Check app/shares/rtl.py (the card's bidi algorithm, PF5a) against Unicode's
conformance files, for the cases it implements: one paragraph without
explicit embeddings, isolates or paragraph separators.

Download BidiTest.txt and BidiCharacterTest.txt of the Unicode version this
Python's `unicodedata` reports (`python -c "import unicodedata;
print(unicodedata.unidata_version)"`) from
https://www.unicode.org/Public/<version>/ucd/ into one folder, then in server/:

    .venv\Scripts\python.exe scripts\bidi_conformance.py <folder>

Prints the cases run and failed in each file; exits 1 on a failure. Run it
when the server moves to a new Python (a new Unicode version).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.shares import rtl  # noqa: E402

SKIP = {"LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI", "B"}


def _paragraph_rtl(classes: list[str]) -> bool:
    for kind in classes:
        if kind == "L":
            return False
        if kind in ("R", "AL"):
            return True
    return False


def _same(classes: list[str], text: str | None, is_rtl: bool, levels: list[str], order: list[str]) -> bool:
    got = rtl.resolve(classes, text, is_rtl)
    if ["x" if v is None else str(v) for v in got] != levels:
        return False
    return [str(i) for i in rtl.reorder(got)] == order


def bidi_test(path: Path) -> tuple[int, list[str]]:
    ran, failed, levels, order = 0, [], [], []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        if line.startswith("@Levels:"):
            levels = line.split(":", 1)[1].split()
        elif line.startswith("@Reorder:"):
            order = line.split(":", 1)[1].split()
        elif not line.startswith("@"):
            classes, bits = line.split(";")
            classes = classes.split()
            if SKIP & set(classes):
                continue
            for bit, mode in ((1, "auto"), (2, "ltr"), (4, "rtl")):
                if int(bits) & bit:
                    ran += 1
                    is_rtl = _paragraph_rtl(classes) if mode == "auto" else mode == "rtl"
                    if not _same(classes, None, is_rtl, levels, order):
                        failed.append(f"{mode}: {raw}")
    return ran, failed


def bidi_character_test(path: Path) -> tuple[int, list[str]]:
    ran, failed = 0, []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        cps, direction, para, levels, order = line.split(";")
        text = "".join(chr(int(c, 16)) for c in cps.split())
        classes = [rtl.bidi_class(ch) for ch in text]
        if SKIP & set(classes):
            continue
        ran += 1
        is_rtl = _paragraph_rtl(classes) if direction == "2" else direction == "1"
        if int(para) != int(is_rtl) or not _same(classes, text, is_rtl, levels.split(), order.split()):
            failed.append(raw)
    return ran, failed


def main(argv: list[str] | None = None) -> int:
    folder = Path((argv or sys.argv[1:] or ["."])[0])
    bad = 0
    for name, check in (("BidiTest.txt", bidi_test), ("BidiCharacterTest.txt", bidi_character_test)):
        ran, failed = check(folder / name)
        print(f"{name}: {ran} cases run, {len(failed)} failed")
        for raw in failed[:10]:
            print(f"  {raw}")
        bad += len(failed)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
