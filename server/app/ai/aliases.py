"""The alias table (contract ai-proxy §6.1): alias -> (adapter, provider model,
effort, credit rates). Platform configuration in aliases.json (or the file
AI_ALIASES_PATH names), re-read whenever the file changes, so moving an alias
to another model changes `served_by` with no app release and no restart.

    table = current()
    alias = table.get("truebex-assist")        # None when unknown or switched off
    alias.rates                                 # credits per million tokens
    table.rates_for("claude-opus-5")            # a fallback model's own rates
"""

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

from ..config import get_settings

DEFAULT_PATH = Path(__file__).with_name("aliases.json")
RATE_KEYS = ("input", "output", "cache_read", "cache_write")
ADAPTERS = ("anthropic", "selfhosted")


@dataclass(frozen=True)
class Alias:
    name: str
    adapter: str
    provider: str
    model: str
    enabled: bool
    context_tokens: int
    max_output_tokens: int
    vision: bool
    rates: dict[str, int]
    effort: str | None = None
    fallbacks: str | None = None
    fallback_alias: str | None = None
    # Plans that may use it (empty = every plan holding ai.metered).
    plans: tuple[str, ...] = ()


@dataclass(frozen=True)
class Table:
    default: str
    aliases: dict[str, Alias]
    model_rates: dict[str, dict[str, int]] = field(default_factory=dict)
    provider_usd: dict[str, dict[str, float]] = field(default_factory=dict)

    def get(self, name: str | None, *, include_disabled: bool = False) -> Alias | None:
        alias = self.aliases.get(name or "")
        if alias is None or (not alias.enabled and not include_disabled):
            return None
        return alias

    def usable(self, plan_id: str) -> list[Alias]:
        return [a for a in self.aliases.values() if a.enabled and (not a.plans or plan_id in a.plans)]

    def rates_for(self, model: str | None, alias: Alias) -> dict[str, int]:
        """The rates a turn is charged at: the answering model's own when the
        table lists it (a refusal fallback), else the alias's."""
        return self.model_rates.get(model or "", alias.rates)

    def usd_for(self, model: str | None) -> dict[str, float]:
        return self.provider_usd.get(model or "", {k: 0.0 for k in RATE_KEYS})


def _rates(raw: dict, where: str) -> dict[str, int]:
    out = {}
    for key in RATE_KEYS:
        value = (raw or {}).get(key)
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"{where}: credits_per_mtok.{key} must be a number of credits, 0 or more")
        out[key] = int(value)
    return out


def parse(raw: dict) -> Table:
    aliases = {}
    for name, a in (raw.get("aliases") or {}).items():
        if a.get("adapter") not in ADAPTERS:
            raise ValueError(f"alias {name}: adapter must be one of {', '.join(ADAPTERS)}")
        aliases[name] = Alias(
            name=name,
            adapter=a["adapter"],
            provider=str(a.get("provider") or a["adapter"]),
            model=str(a["model"]),
            enabled=bool(a.get("enabled", True)),
            context_tokens=int(a.get("context_tokens") or 200_000),
            max_output_tokens=int(a.get("max_output_tokens") or 8192),
            vision=bool(a.get("vision", False)),
            rates=_rates(a.get("credits_per_mtok"), f"alias {name}"),
            effort=a.get("effort"),
            fallbacks=a.get("fallbacks"),
            fallback_alias=a.get("fallback_alias"),
            plans=tuple(a.get("plans") or ()),
        )
    default = raw.get("default") or next(iter(aliases), "")
    return Table(
        default=default,
        aliases=aliases,
        model_rates={m: _rates(r, f"model {m}") for m, r in (raw.get("model_credits_per_mtok") or {}).items()},
        provider_usd={
            m: {k: float((r or {}).get(k) or 0.0) for k in RATE_KEYS} for m, r in (raw.get("provider_usd_per_mtok") or {}).items()
        },
    )


_lock = threading.Lock()
_cache: dict[str, tuple[float, int, Table]] = {}


def path() -> Path:
    configured = get_settings().ai_aliases_path
    return Path(configured) if configured else DEFAULT_PATH


def current() -> Table:
    """The table as the file says now (re-parsed when its mtime or size moves)."""
    p = path()
    st = os.stat(p)
    key = str(p.resolve())
    with _lock:
        hit = _cache.get(key)
        if hit is not None and hit[0] == st.st_mtime and hit[1] == st.st_size:
            return hit[2]
        table = parse(json.loads(p.read_text(encoding="utf-8")))
        _cache[key] = (st.st_mtime, st.st_size, table)
        return table


def reset() -> None:
    with _lock:
        _cache.clear()
