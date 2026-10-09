"""Ed25519 signatures over canonical JSON (licence-api.md §6.2, §6.4).

An envelope is `{"document": {…}, "signature": {"alg": "Ed25519", "kid": …,
"value": <base64url, 86 chars>}}`; a release keeps its `manifest` under that
name instead of `document`. The signed bytes are the RFC 8785 form (jcs.py).

Keys: the `lic-*` seed lives only in server/.env (LICENCE_SIGNING_KEY); the
`rel-*` seed never reaches the API host (publish_release.py reads it from a
file the owner keeps). Only public keys are published (5.12).

CLI (run in server/):
    python -m app.licence.signing verify envelope.json [--keys keys.json|URL]
prints "valid · plan free · expires …" or "INVALID: …" (exit code 1).
"""

import base64
import json
import sys
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from .jcs import canonical_bytes

ALG = "Ed25519"


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    text = text.strip()
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def private_key_from_seed(seed_b64url: str) -> Ed25519PrivateKey:
    raw = b64url_decode(seed_b64url)
    if len(raw) != 32:
        raise ValueError("an Ed25519 seed is 32 bytes (43 base64url characters)")
    return Ed25519PrivateKey.from_private_bytes(raw)


def public_key_b64url(key: Ed25519PrivateKey | Ed25519PublicKey) -> str:
    pub = key.public_key() if isinstance(key, Ed25519PrivateKey) else key
    return b64url_encode(pub.public_bytes(Encoding.Raw, PublicFormat.Raw))


def new_seed() -> str:
    from cryptography.hazmat.primitives.serialization import NoEncryption, PrivateFormat

    key = Ed25519PrivateKey.generate()
    return b64url_encode(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))


def sign(doc: Any, key: Ed25519PrivateKey, kid: str) -> dict[str, str]:
    """The detached signature block for `doc`."""
    return {"alg": ALG, "kid": kid, "value": b64url_encode(key.sign(canonical_bytes(doc)))}


def sign_envelope(doc: dict, key: Ed25519PrivateKey, kid: str, *, field: str = "document") -> dict:
    return {field: doc, "signature": sign(doc, key, kid)}


def verify(doc: Any, signature: dict, public_keys: dict[str, str]) -> bool:
    """True when `signature` is a valid Ed25519 signature of `doc` by a known kid."""
    if not isinstance(signature, dict) or signature.get("alg") != ALG:
        return False
    pub = public_keys.get(str(signature.get("kid")))
    if not pub:
        return False
    try:
        raw_sig = b64url_decode(str(signature.get("value", "")))
        Ed25519PublicKey.from_public_bytes(b64url_decode(pub)).verify(raw_sig, canonical_bytes(doc))
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


@dataclass(frozen=True)
class PublishedKey:
    kid: str
    use: str  # "entitlement" | "release"
    public_key: str

    def as_json(self) -> dict[str, str]:
        return {"kid": self.kid, "alg": ALG, "use": self.use, "public_key": self.public_key}


def parse_key_list(text: str) -> dict[str, str]:
    """`kid:public_key,kid:public_key` (the RELEASE_PUBLIC_KEYS / SIGNING_KEYS_EXTRA form)."""
    out: dict[str, str] = {}
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        kid, sep, pub = part.partition(":")
        if not sep or not kid.strip() or not pub.strip():
            raise ValueError(f"expected kid:public_key, got {part!r}")
        out[kid.strip()] = pub.strip()
    return out


def published_keys() -> list[PublishedKey]:
    """Every public key this server publishes (5.12), from settings."""
    from ..config import get_settings

    s = get_settings()
    keys: list[PublishedKey] = []
    if s.licence_signing_key:
        keys.append(PublishedKey(s.licence_key_id, "entitlement", public_key_b64url(licence_private_key())))
    for kid, pub in parse_key_list(s.signing_keys_extra).items():
        if all(k.kid != kid for k in keys):
            keys.append(PublishedKey(kid, "entitlement", pub))
    for kid, pub in parse_key_list(s.release_public_keys).items():
        keys.append(PublishedKey(kid, "release", pub))
    return keys


def licence_private_key() -> Ed25519PrivateKey:
    """The `lic-*` signing key from server/.env. Raises LookupError when unset."""
    from ..config import get_settings

    seed = get_settings().licence_signing_key
    if not seed:
        raise LookupError("LICENCE_SIGNING_KEY is not set")
    return _cached_key(seed)


_KEY_CACHE: dict[str, Ed25519PrivateKey] = {}


def _cached_key(seed: str) -> Ed25519PrivateKey:
    key = _KEY_CACHE.get(seed)
    if key is None:
        key = _KEY_CACHE[seed] = private_key_from_seed(seed)
    return key


def keys_by_use(use: str | None = None) -> dict[str, str]:
    return {k.kid: k.public_key for k in published_keys() if use is None or k.use == use}


# --- CLI ----------------------------------------------------------------------


def _load_keys(source: str | None) -> dict[str, str]:
    if not source:
        return keys_by_use()
    if source.startswith(("http://", "https://")):
        import httpx

        data = httpx.get(source, timeout=15).json()
    else:
        with open(source, encoding="utf-8") as fh:
            data = json.load(fh)
    return {k["kid"]: k["public_key"] for k in data.get("keys", [])}


def _find_envelope(data: dict) -> tuple[str, dict]:
    """Accept a bare envelope, a 5.4 / 5.5 / 5.6 response, a fixture or a feed entry."""
    for candidate in (data, data.get("entitlement"), data.get("envelope")):
        if isinstance(candidate, dict) and "signature" in candidate:
            for field in ("document", "manifest"):
                if isinstance(candidate.get(field), dict):
                    return field, candidate
    raise ValueError("no envelope (document or manifest plus signature) in this file")


def _cli(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m app.licence.signing")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="verify a signed entitlement or release manifest")
    v.add_argument("file")
    v.add_argument("--keys", help="a /licence/keys JSON file or URL (default: this server's settings)")
    args = ap.parse_args(argv)

    with open(args.file, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    try:
        field, env = _find_envelope(data)
    except ValueError as exc:
        print(f"INVALID: {exc}")
        return 1
    keys = _load_keys(args.keys)
    if not verify(env[field], env["signature"], keys):
        kid = env["signature"].get("kid") if isinstance(env["signature"], dict) else None
        why = "unknown kid " + repr(kid) if kid not in keys else "signature does not match"
        print(f"INVALID: {why}")
        return 1
    doc = env[field]
    if field == "document":
        print(f"valid · plan {doc.get('plan')} · expires {doc.get('expires_at')}")
    else:
        print(f"valid · release {doc.get('version')} · {doc.get('platform')} · {doc.get('channel')}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli(sys.argv[1:]))
