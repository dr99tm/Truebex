"""The `texture` runner: seamless PBR maps for AI5's materials (PF11; behind
AI_TEXTURE_ENABLED on the platform until its MINOR contract addition lands).

    python3 -m runners.texture /job

An open image model whose licence allows commercial hosting (TEXTURE_MODEL,
a diffusers model id or a local path baked into the image; GD3 names the
gpu-ai class) draws the albedo from `params.prompt` at `params.size`. With
`params.seamless`, every convolution pads circularly, so the image tiles with
no seam. The normal map comes from a height estimate (luminance, Sobel
gradients), the roughness from the inverted, normalised luminance. Output:
`truebex-texture/1` {job_id, kind, params, engine, maps: [{name, sha256,
size_px, content_type: image/png}]}. torch, diffusers, numpy and Pillow exist
only in the texture image, so they are imported inside the functions.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

if __package__ in (None, ""):  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "runners"

from . import common

DEFAULT_MODEL = "/opt/truebex/models/texture"  # baked into the image at build (licence checked then)
STEPS = int(os.environ.get("TEXTURE_STEPS", "30"))


def _seamless(pipe) -> None:
    import torch

    for module in list(pipe.unet.modules()) + list(pipe.vae.modules()):
        if isinstance(module, torch.nn.Conv2d):
            module.padding_mode = "circular"


def albedo(prompt: str, size: int, seamless: bool):
    import torch
    from diffusers import AutoPipelineForText2Image

    model = os.environ.get("TEXTURE_MODEL") or DEFAULT_MODEL
    try:
        pipe = AutoPipelineForText2Image.from_pretrained(model, torch_dtype=torch.float16)
    except (OSError, ValueError) as exc:
        raise common.EngineError(f"the texture model could not be loaded: {exc}") from None
    pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")
    if seamless:
        _seamless(pipe)
    text = f"{prompt}, seamless tileable texture, flat lighting, top-down, physically based albedo"
    return pipe(text, height=size, width=size, num_inference_steps=STEPS).images[0].convert("RGB")


def derived_maps(image):
    """(normal, roughness) PIL images from the albedo."""
    import numpy as np
    from PIL import Image

    rgb = np.asarray(image, dtype=np.float32) / 255.0
    height = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    # Sobel with wrap-around, so the normal map tiles like the albedo.
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * 2 + (np.roll(np.roll(height, -1, 1), 1, 0) - np.roll(np.roll(height, 1, 1), 1, 0)) + (np.roll(np.roll(height, -1, 1), -1, 0) - np.roll(np.roll(height, 1, 1), -1, 0))
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * 2 + (np.roll(np.roll(height, -1, 0), 1, 1) - np.roll(np.roll(height, 1, 0), 1, 1)) + (np.roll(np.roll(height, -1, 0), -1, 1) - np.roll(np.roll(height, 1, 0), -1, 1))
    strength = 2.0
    n = np.stack([-gx * strength, -gy * strength, np.ones_like(height)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    normal = Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8), "RGB")
    span = float(height.max() - height.min()) or 1.0
    rough = 1.0 - (height - height.min()) / span
    roughness = Image.fromarray(((0.35 + 0.6 * rough) * 255).astype(np.uint8), "L")
    return normal, roughness


def png(image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def run(job: common.Job) -> None:
    out = job.out_dir
    p = job.params
    size = int(p.get("size", 1024))
    wanted = list(p.get("maps") or ["albedo", "normal", "roughness"])
    common.progress(out, 0.1, "drawing the albedo")
    base = albedo(str(p.get("prompt", "")), size, bool(p.get("seamless", True)))
    images = {"albedo": base}
    if "normal" in wanted or "roughness" in wanted:
        common.progress(out, 0.8, "deriving normal and roughness")
        images["normal"], images["roughness"] = derived_maps(base)
    maps = []
    for name in wanted:
        sha = common.write_array(out, png(images[name]))
        maps.append({"name": name, "sha256": sha, "size_px": size, "content_type": "image/png"})
    model = os.environ.get("TEXTURE_MODEL") or DEFAULT_MODEL
    result = {
        "schema": common.TEXTURE_SCHEMA, "job_id": job.job_id, "kind": "texture", "params": p,
        "engine": common.engine(Path(model).name or "image-model", os.environ.get("TEXTURE_MODEL_VERSION", "1"), "texture"),
        "maps": maps,
    }
    common.write_result(out, result)
    common.progress(out, 1.0, "done")


if __name__ == "__main__":
    sys.exit(common.main(run))
