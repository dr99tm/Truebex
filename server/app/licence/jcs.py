"""RFC 8785 (JSON Canonicalization Scheme) for the contract's documents.

Signed documents hold only objects, arrays, strings, integers, booleans and
null, and only ASCII keys (licence-api.md §6.2), so JCS reduces to: keys
sorted by UTF-16 code units, no whitespace, strings escaping only `"`, `\\`
and U+0000-U+001F (`\\b \\t \\n \\f \\r`, else `\\u00xx`), every other
character as UTF-8, integers in plain decimal. Floats are refused rather than
guessed at. The fixtures' `canonical` strings are the referee: the app's
canonicaliser must produce the same bytes.
"""

from typing import Any

_SHORT = {0x08: "\\b", 0x09: "\\t", 0x0A: "\\n", 0x0C: "\\f", 0x0D: "\\r"}


def _string(s: str) -> str:
    out = ['"']
    for ch in s:
        code = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif code < 0x20:
            out.append(_SHORT.get(code) or f"\\u{code:04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _value(v: Any) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return _string(v)
    if isinstance(v, dict):
        keys = sorted(v, key=lambda k: k.encode("utf-16-be"))
        if any(not isinstance(k, str) for k in keys):
            raise TypeError("JCS object keys must be strings")
        return "{" + ",".join(_string(k) + ":" + _value(v[k]) for k in keys) + "}"
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(_value(x) for x in v) + "]"
    raise TypeError(f"JCS: unsupported type {type(v).__name__} (no floats in signed documents)")


def canonicalize(doc: Any) -> str:
    """The canonical JSON text of `doc`."""
    return _value(doc)


def canonical_bytes(doc: Any) -> bytes:
    """The UTF-8 bytes that get signed."""
    return canonicalize(doc).encode("utf-8")
