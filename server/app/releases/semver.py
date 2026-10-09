"""SemVer 2.0.0: parsing and precedence (release feeds sort newest first)."""

import re

_ID = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
_SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    rf"(?:-({_ID}(?:\.{_ID})*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def is_valid(version: str) -> bool:
    return isinstance(version, str) and len(version) <= 64 and bool(_SEMVER.match(version))


def is_prerelease(version: str) -> bool:
    m = _SEMVER.match(version)
    return bool(m and m.group(4))


def key(version: str) -> tuple:
    """Sort key by SemVer precedence (build metadata ignored)."""
    m = _SEMVER.match(version)
    if m is None:
        raise ValueError(f"not a SemVer version: {version!r}")
    major, minor, patch, pre = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
    if pre is None:
        pre_key: tuple = (1,)  # a release outranks any of its pre-releases
    else:
        pre_key = (0, *((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split(".")))
    return (major, minor, patch, pre_key)
