"""The picture search: products found by a photo (or a description) through
an open image-text embedding model.

* `EMBEDDING_MODEL=clip-vit-b32`: OpenAI's CLIP ViT-B/32 (MIT licence) as
  ONNX files, run on the CPU with ONNX Runtime. The weights (about 90 MB per
  quantised model) are fetched once per host by
  `server/scripts/fetch_models.py` into `EMBEDDING_DIR`, never committed and
  never downloaded by tests. A description is embedded by the text model in
  the same space, so "green velvet armchair" finds pictures.
* `EMBEDDING_MODEL=stub`: a deterministic embedder for tests and local trials
  (a 16 × 16 colour thumbnail as a vector): the same picture finds its own
  product first. It has no text model; a description then goes to the text
  index.
* Empty (the default): picture search answers 503 until a model is set.

`market.embeddings` (every 60 s) embeds the first image of newly approved
products. Search is a brute-force cosine over every vector of the model:
fine below 50 000 products; a vector index comes with Postgres (PF14).
"""

import io
import logging
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..storage import get_store
from .models import Product, ProductEmbedding, Supplier

log = logging.getLogger("truebex.market")

MAX_QUERY_IMAGE_BYTES = 5 * 1024 * 1024
CLIP_FILES = ("vision_model_quantized.onnx", "text_model_quantized.onnx", "tokenizer.json")


class Embedder(Protocol):
    model: str

    def embed_image(self, data: bytes) -> np.ndarray: ...

    def embed_text(self, text: str) -> np.ndarray | None: ...


def _normalise(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def _rgb(data: bytes):
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = 50_000_000
    img = Image.open(io.BytesIO(data))
    img.load()
    return img.convert("RGB")


class StubEmbedder:
    model = "stub-16px-v1"

    def embed_image(self, data: bytes) -> np.ndarray:
        from PIL import Image

        img = _rgb(data).resize((16, 16), Image.Resampling.BILINEAR)
        v = np.asarray(img, dtype=np.float32).reshape(-1) / 255.0
        return _normalise(v - v.mean() + 1e-3)

    def embed_text(self, text: str) -> np.ndarray | None:
        return None


class ClipOnnxEmbedder:
    model = "clip-vit-b32"
    _MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
    _STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)

    def __init__(self, folder: Path) -> None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.vision = ort.InferenceSession(str(folder / CLIP_FILES[0]), opts, providers=["CPUExecutionProvider"])
        self.text = None
        self.tokenizer = None
        text_path, tok_path = folder / CLIP_FILES[1], folder / CLIP_FILES[2]
        if text_path.is_file() and tok_path.is_file():
            try:
                from tokenizers import Tokenizer

                self.tokenizer = Tokenizer.from_file(str(tok_path))
                self.text = ort.InferenceSession(str(text_path), opts, providers=["CPUExecutionProvider"])
            except ImportError:  # requirements.txt pins it; a host without it searches descriptions by text
                log.info("tokenizers is not installed: descriptions go to the text index")

    def _pixels(self, data: bytes) -> np.ndarray:
        from PIL import Image

        img = _rgb(data)
        w, h = img.size
        scale = 224 / min(w, h)
        img = img.resize((max(224, round(w * scale)), max(224, round(h * scale))), Image.Resampling.BICUBIC)
        w, h = img.size
        left, top = (w - 224) // 2, (h - 224) // 2
        img = img.crop((left, top, left + 224, top + 224))
        x = (np.asarray(img, dtype=np.float32) / 255.0 - self._MEAN) / self._STD
        return x.transpose(2, 0, 1)[None, ...]

    def embed_image(self, data: bytes) -> np.ndarray:
        outputs = self.vision.run(["image_embeds"], {"pixel_values": self._pixels(data)})
        return _normalise(outputs[0][0])

    def embed_text(self, text: str) -> np.ndarray | None:
        if self.text is None or self.tokenizer is None:
            return None
        # The tokenizer adds CLIP's start and end tokens; 77 is CLIP's context.
        ids = self.tokenizer.encode(text.strip()[:300]).ids[:77]
        if not ids:
            return None
        feeds = {"input_ids": np.array([ids], dtype=np.int64)}
        if "attention_mask" in {i.name for i in self.text.get_inputs()}:
            feeds["attention_mask"] = np.ones((1, len(ids)), dtype=np.int64)
        outputs = self.text.run(["text_embeds"], feeds)
        return _normalise(outputs[0][0])


@lru_cache
def _load(model: str, folder: str) -> Embedder | None:
    if model == "stub":
        return StubEmbedder()
    if model == "clip-vit-b32":
        path = Path(folder) / "clip-vit-b32"
        if not (path / CLIP_FILES[0]).is_file():
            log.warning("EMBEDDING_MODEL=clip-vit-b32 but %s is missing: run scripts/fetch_models.py", path / CLIP_FILES[0])
            return None
        return ClipOnnxEmbedder(path)
    return None


def get_embedder() -> Embedder | None:
    s = get_settings()
    return _load(s.embedding_model.strip(), s.embedding_dir)


# --- Indexing ----------------------------------------------------------------------------


def embed_pending(db: Session, limit: int = 50) -> int:
    """Embed the first image of approved products that have none (or whose
    first image changed)."""
    embedder = get_embedder()
    if embedder is None:
        return 0
    have = {
        pid: sha
        for pid, sha in db.execute(
            select(ProductEmbedding.product_id, ProductEmbedding.image_sha256).where(ProductEmbedding.model == embedder.model)
        )
    }
    store = get_store()
    n = 0
    for product in db.scalars(select(Product).where(Product.status == "approved")):
        if not product.images or have.get(product.product_id) == product.images[0]:
            continue
        try:
            with store.open(f"market/images/{product.images[0]}.jpg") as fh:
                vector = embedder.embed_image(fh.read())
        except Exception:
            log.exception("embedding failed for %s", product.product_id)
            continue
        row = db.scalar(
            select(ProductEmbedding).where(ProductEmbedding.product_id == product.product_id, ProductEmbedding.model == embedder.model)
        ) or ProductEmbedding(product_id=product.product_id, model=embedder.model)
        row.image_sha256 = product.images[0]
        row.vector = vector.astype("<f4").tobytes()
        db.add(row)
        n += 1
        if n >= limit:
            break
    db.commit()
    return n


def nearest(db: Session, embedder: Embedder, query: np.ndarray, limit: int) -> list[tuple[str, float]]:
    rows = db.execute(
        select(ProductEmbedding.product_id, ProductEmbedding.vector)
        .join(Product, Product.product_id == ProductEmbedding.product_id)
        .join(Supplier, Supplier.supplier_id == Product.supplier_id)
        .where(ProductEmbedding.model == embedder.model, Product.status == "approved", Supplier.status == "verified")
    ).all()
    if not rows:
        return []
    ids = [pid for pid, _ in rows]
    matrix = np.stack([np.frombuffer(blob, dtype="<f4") for _, blob in rows])
    if matrix.shape[1] != query.shape[0]:
        return []
    scores = matrix @ query
    order = np.argsort(-scores, kind="stable")[: max(limit * 4, limit)]
    return [(ids[i], float(scores[i])) for i in order]
