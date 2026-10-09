"""The server's privacy rules (contracts/telemetry.md §6.4).

The app scrubs before anything leaves the machine; the server runs the same
rules again and refuses what slips through (422 `privacy_violation`, naming
the field):

* an email-shaped string anywhere (feedback text excepted: the person writes it);
* a path separator in an event prop value, a callstack frame or a module name;
* an event prop value outside §6.1's types: integers, booleans, the listed
  enums, or a short id / version token, never free text;
* a log tail the scrubber would still change.

`scrub_log` is the scrubber itself; tests/contracts/telemetry/log-tail-*.txt
pin its output. Order: emails, then project paths, then profile folders.
"""

import re
from dataclasses import dataclass
from typing import Any

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_SEG = r'[^\\/:*?"<>|\r\n]'
# An absolute path (drive, %USERPROFILE% or UNC) ending in a project or asset
# file: the whole path goes, since its folders are often named after the project.
PROJECT_PATH_RE = re.compile(
    r"(?:[A-Za-z]:|%USERPROFILE%|\\\\" + _SEG + r"+)[\\/](?:" + _SEG + r"+[\\/])*"
    + _SEG + r"*?\.(?:tbxp|tbxa|tbxpack)\b",
    re.IGNORECASE,
)
PROFILE_RE = re.compile(
    r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]" + _SEG + r"+", re.IGNORECASE
)
PATH_SEP_RE = re.compile(r"[\\/]")
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+\-]{0,63}$")

INT_PROPS = {
    "cold_start_ms",
    "first_lit_hitch_ms",
    "session_s",
    "ms",
    "pages",
    "p50_ms",
    "p95_ms",
    "count",
    "offline_days",
}
BOOL_PROPS = {"clean", "ok"}
ENUM_PROPS = {
    ("export.run", "kind"): {"pdf", "dxf", "dwg", "ifc", "panorama", "video", "share"},
    ("perf.frame", "mode"): {"Unlit", "Lit", "Wireframe"},
    ("error.logged", "verbosity"): {"warning", "error", "ensure"},
}

MESSAGES = {
    "email": "A value looks like an email address.",
    "path": "A value looks like a file path.",
    "type": "A value is not an id, a whole number or yes / no.",
    "log": "The log still holds a path, a project name or an email address.",
}


@dataclass(frozen=True)
class Violation:
    field: str
    reason: str

    @property
    def message(self) -> str:
        return MESSAGES[self.reason]


def scrub_log(text: str) -> str:
    text = EMAIL_RE.sub("<email>", text)
    text = PROJECT_PATH_RE.sub("<project>", text)
    return PROFILE_RE.sub("%USERPROFILE%", text)


def scan_log(text: str, field: str = "log") -> Violation | None:
    return Violation(field, "log") if scrub_log(text) != text else None


def _join(base: str, key: Any) -> str:
    if isinstance(key, int):
        return f"{base}[{key}]"
    return f"{base}.{key}" if base else str(key)


def _scan_plain(value: Any, field: str, *, paths: bool = False, skip: frozenset = frozenset()) -> Violation | None:
    """Emails anywhere below `value`; path separators too when `paths`."""
    if isinstance(value, str):
        if EMAIL_RE.search(value):
            return Violation(field, "email")
        if paths and PATH_SEP_RE.search(value):
            return Violation(field, "path")
        return None
    if isinstance(value, dict):
        for k, v in value.items():
            if k in skip:
                continue
            hit = _scan_plain(str(k), _join(field, k), paths=paths) or _scan_plain(
                v, _join(field, k), paths=paths
            )
            if hit:
                return hit
    elif isinstance(value, list):
        for i, v in enumerate(value):
            hit = _scan_plain(v, _join(field, i), paths=paths)
            if hit:
                return hit
    return None


def _scan_prop(event: Any, key: str, value: Any, field: str) -> Violation | None:
    hit = _scan_plain(key, field, paths=True)
    if hit:
        return hit
    if isinstance(value, bool):
        return None if key not in INT_PROPS and (event, key) not in ENUM_PROPS else Violation(field, "type")
    if isinstance(value, int):
        return None if key not in BOOL_PROPS and (event, key) not in ENUM_PROPS else Violation(field, "type")
    if isinstance(value, str):
        if EMAIL_RE.search(value):
            return Violation(field, "email")
        if PATH_SEP_RE.search(value):
            return Violation(field, "path")
        allowed = ENUM_PROPS.get((event, key))
        if allowed is not None:
            return None if value in allowed else Violation(field, "type")
        if key in INT_PROPS or key in BOOL_PROPS or not TOKEN_RE.match(value):
            return Violation(field, "type")
        return None
    return Violation(field, "type")  # floats, null, lists, objects


def scan_events(payload: dict) -> Violation | None:
    hit = _scan_plain(payload, "", skip=frozenset({"events"}))
    if hit:
        return hit
    events = payload.get("events")
    if not isinstance(events, list):
        return None
    for i, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        base = f"events[{i}]"
        hit = _scan_plain(event, base, skip=frozenset({"props"}))
        if hit:
            return hit
        props = event.get("props")
        if isinstance(props, dict):
            for key, value in props.items():
                hit = _scan_prop(event.get("name"), str(key), value, f"{base}.props.{key}")
                if hit:
                    return hit
    return None


def scan_crash(report: dict) -> Violation | None:
    hit = _scan_plain(report, "", skip=frozenset({"callstack", "exception"}))
    if hit:
        return hit
    hit = _scan_plain(report.get("exception"), "exception", paths=True)
    if hit:
        return hit
    return _scan_plain(report.get("callstack"), "callstack", paths=True)


def scan_feedback(feedback: dict) -> Violation | None:
    return _scan_plain(feedback, "", skip=frozenset({"text"}))
