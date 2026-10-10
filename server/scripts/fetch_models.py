"""Fetch the picture-search model once per host (never into git, never in tests).

    cd server
    .venv\\Scripts\\python.exe scripts\\fetch_models.py [--dir ./models]

Downloads OpenAI's CLIP ViT-B/32 (MIT licence), exported to ONNX and
quantised (Xenova/clip-vit-base-patch32 on Hugging Face), into
<dir>/clip-vit-b32/: the vision model (about 90 MB), the text model (about
65 MB) and the tokenizer. Then set EMBEDDING_MODEL=clip-vit-b32 (and
EMBEDDING_DIR when --dir is not ./models) in server/.env and restart the API;
the `market.embeddings` job embeds the approved products within a minute.
A description ("green velvet armchair") is embedded by the text model in the
same space as the pictures.
"""

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
BASE = "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/main"
FILES = {
    "vision_model_quantized.onnx": f"{BASE}/onnx/vision_model_quantized.onnx",
    "text_model_quantized.onnx": f"{BASE}/onnx/text_model_quantized.onnx",
    "tokenizer.json": f"{BASE}/tokenizer.json",
}


def fetch(url: str, dest: Path) -> str:
    part = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=60) as res, part.open("wb") as out:
        while chunk := res.read(1024 * 1024):
            out.write(chunk)
            digest.update(chunk)
    part.replace(dest)
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", default=str(SERVER / "models"))
    ap.add_argument("--only", choices=sorted(FILES), action="append", help="fetch just these files")
    ap.add_argument("--force", action="store_true", help="download again even when present")
    args = ap.parse_args(argv)
    folder = Path(args.dir) / "clip-vit-b32"
    folder.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        if args.only and name not in args.only:
            continue
        dest = folder / name
        if dest.is_file() and not args.force:
            print(f"have {dest} ({dest.stat().st_size:,} bytes)")
            continue
        print(f"fetching {url}")
        sha = fetch(url, dest)
        print(f"  {dest} {dest.stat().st_size:,} bytes sha256 {sha}")
    print(f"done: set EMBEDDING_MODEL=clip-vit-b32 and EMBEDDING_DIR={Path(args.dir).resolve()} in server/.env")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
