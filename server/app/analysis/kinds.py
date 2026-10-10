"""Analysis kinds on PF6's queue (contract render-jobs §5.1; PF11).

| Kind      | Class  | Feature          | Required                                 | `params` |
|-----------|--------|------------------|------------------------------------------|----------|
| wind      | cpu-8  | analysis.reports | inputs.files.geometry (binary STL, m)    | speed_ms, direction_deg, reference_height_m, terrain, comfort |
| energy    | cpu-8  | analysis.reports | inputs.files.model (epJSON), params.weather | weather, period |
| acoustics | cpu-8  | analysis.reports | inputs.files.rooms (JSON)                | sources, bands, rays, receiver_grid_m, receiver_height_m |
| texture   | gpu-ai | ai.metered       | params.prompt (AI_TEXTURE_ENABLED only)  | prompt, size, seamless, maps |

`acoustics` and `texture` are the MINOR additions PF11 proposes for
render-jobs.md; `texture` stays an unknown kind until AI_TEXTURE_ENABLED.
Optional wind files (AN3's proposal): `entities` (16 bytes per triangle),
`surroundings` and `terrain` (binary STL). The solver profile each job runs
with (profiles.json, GD2 placeholders) travels in the claim as `job.profile`.
"""

import json
import math
import re
from pathlib import Path

from ..config import get_settings
from ..render import quotas
from ..render.quotas import Kind
from .validation import invalid

PROFILES = json.loads(Path(__file__).with_name("profiles.json").read_text(encoding="utf-8"))
FEATURE = "analysis.reports"
ANALYSIS = ("wind", "energy", "acoustics")
TEXTURE = "texture"
KINDS: dict[str, Kind] = {
    "wind": Kind("wind", FEATURE, "cpu-8", "run"),
    "energy": Kind("energy", FEATURE, "cpu-8", "run"),
    "acoustics": Kind("acoustics", FEATURE, "cpu-8", "run"),
    TEXTURE: Kind(TEXTURE, "ai.metered", "gpu-ai", "run"),
}
REQUIRED_FILES = {"wind": "geometry", "energy": "model", "acoustics": "rooms"}
OPTIONAL_FILES = {"wind": ("entities", "surroundings", "terrain")}
TERRAIN = PROFILES["wind"]["terrain"]
_WEATHER_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")


def texture_enabled() -> bool:
    return bool(get_settings().ai_texture_enabled)


def sync() -> None:
    """Register the analysis kinds with PF6's queue (`quotas.KINDS`); `texture`
    only while AI_TEXTURE_ENABLED. Called at import and by tests that flip it."""
    for name in ANALYSIS:
        quotas.KINDS[name] = KINDS[name]
    if texture_enabled():
        quotas.KINDS[TEXTURE] = KINDS[TEXTURE]
    else:
        quotas.KINDS.pop(TEXTURE, None)
    for name, kind in KINDS.items():
        quotas.KIND_CLASSES[name] = kind.worker_class


def handles(kind: object) -> bool:
    return isinstance(kind, str) and (kind in ANALYSIS or (kind == TEXTURE and texture_enabled()))


def is_analysis(kind: str) -> bool:
    """Any kind whose output is a PF11 result (texture included, flag or not)."""
    return kind in KINDS


def profile(kind: str) -> dict:
    return dict(PROFILES.get(kind) or {})


# --- params ---------------------------------------------------------------------------------


def _number(params: dict, key: str, low: float, high: float, default: float | None, *, below: bool = False) -> float:
    value = params.get(key, default)
    if value is None:
        raise invalid(f"params.{key}", "required")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise invalid(f"params.{key}", "a number")
    if value < low or (value >= high if below else value > high):
        raise invalid(f"params.{key}", f"{low} to {high}{' (not included)' if below else ''}")
    return float(value) if isinstance(value, float) else value


def _wind(params: dict) -> dict:
    terrain = params.get("terrain", "suburban")
    if terrain not in TERRAIN:
        raise invalid("params.terrain", f"one of {', '.join(TERRAIN)}", terrain=list(TERRAIN))
    comfort = params.get("comfort", "lawson")
    if comfort != "lawson":
        raise invalid("params.comfort", "lawson")
    return {
        "speed_ms": _number(params, "speed_ms", 0.5, 60, 5),
        "direction_deg": _number(params, "direction_deg", 0, 360, 0, below=True),
        "reference_height_m": _number(params, "reference_height_m", 1, 300, 10),
        "terrain": terrain,
        "comfort": comfort,
    }


def _energy(params: dict, known_weather) -> dict:
    weather = params.get("weather")
    if not isinstance(weather, str) or not _WEATHER_ID.match(weather):
        raise invalid("params.weather", "a weather id of GET /analysis/catalogue")
    if not known_weather(weather):
        raise invalid("params.weather", "a weather id of GET /analysis/catalogue (this one is not in the library)", weather=weather)
    period = params.get("period", "annual")
    if period != "annual":
        raise invalid("params.period", "annual")
    return {"weather": weather, "period": period}


def _acoustics(params: dict) -> dict:
    p = PROFILES["acoustics"]
    bands = params.get("bands", p["bands_default"])
    if not isinstance(bands, list) or not bands or any(b not in p["bands_hz"] for b in bands) or len(set(bands)) != len(bands):
        raise invalid("params.bands", f"octave bands from {p['bands_hz']}")
    bands = sorted(bands)
    sources = params.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 8:
        raise invalid("params.sources", "1 to 8 sources: {position_m: [x, y, z], power_db}")
    out_sources = []
    for i, s in enumerate(sources):
        pos = s.get("position_m") if isinstance(s, dict) else None
        if not isinstance(pos, list) or len(pos) != 3 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in pos):
            raise invalid(f"params.sources[{i}].position_m", "[x, y, z] in metres")
        power = s.get("power_db", 94)
        if isinstance(power, list):
            if len(power) != len(bands) or not all(isinstance(v, (int, float)) and 0 <= v <= 160 for v in power):
                raise invalid(f"params.sources[{i}].power_db", "one level per band, 0 to 160 dB")
        elif not isinstance(power, (int, float)) or isinstance(power, bool) or not 0 <= power <= 160:
            raise invalid(f"params.sources[{i}].power_db", "0 to 160 dB, or one level per band")
        entry = {"position_m": list(pos), "power_db": power}
        if isinstance(s.get("id"), str):
            entry["id"] = s["id"][:64]
        out_sources.append(entry)
    rays = params.get("rays", p["rays_default"])
    if not isinstance(rays, int) or isinstance(rays, bool) or not 1000 <= rays <= p["rays_max"]:
        raise invalid("params.rays", f"1000 to {p['rays_max']}")
    return {
        "sources": out_sources,
        "bands": bands,
        "rays": rays,
        "receiver_grid_m": _number(params, "receiver_grid_m", 0.25, 5, 1.0),
        "receiver_height_m": _number(params, "receiver_height_m", 0.1, 3, 1.2),
    }


def _texture(params: dict) -> dict:
    p = PROFILES["texture"]
    prompt = params.get("prompt")
    if not isinstance(prompt, str) or not 3 <= len(prompt.strip()) <= 1000:
        raise invalid("params.prompt", "3 to 1000 characters")
    size = params.get("size", 1024)
    if size not in p["sizes"]:
        raise invalid("params.size", f"one of {p['sizes']}")
    seamless = params.get("seamless", True)
    if not isinstance(seamless, bool):
        raise invalid("params.seamless", "true or false")
    maps = params.get("maps", p["maps"])
    if not isinstance(maps, list) or not maps or any(m not in p["maps"] for m in maps):
        raise invalid("params.maps", f"one or more of {p['maps']}")
    return {"prompt": prompt.strip(), "size": size, "seamless": seamless, "maps": [m for m in p["maps"] if m in maps]}


def validate_params(kind: str, params: object, *, known_weather=lambda _id: False) -> dict:
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise invalid("params", "an object")
    if kind == "wind":
        return _wind(params)
    if kind == "energy":
        return _energy(params, known_weather)
    if kind == "acoustics":
        return _acoustics(params)
    return _texture(params)


sync()
