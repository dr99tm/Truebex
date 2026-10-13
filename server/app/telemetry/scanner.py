"""The server's privacy rules (contracts/telemetry.md §6.4).

The app scrubs before anything leaves the machine; the server runs the same
rules again and refuses what slips through (422 `privacy_violation`, naming
the field):

* an email-shaped string anywhere, feedback text included (the app's fixture
  case `email-in-feedback-text`; OP1's own scrubber turns an address a person
  types into `<email>` before sending);
* a path separator in an event prop value, a callstack frame or the
  exception block. §6.4 scopes the separator rule to prop values (1.0.1 adds
  callstack frames), so feedback text may hold a slash ("and/or", "1/2"), as
  the app allows too;
* an event prop value outside §6.1's types: integers, booleans, the listed
  enums, or a short id / version token, never free text. Event names, prop
  keys and enum values match without case: a Shipping build spells an FName
  as the engine first registered it;
* a log tail the scrubber would still change.

`scrub_log` is OP1's scrubber (`TelemetryPrivacy::Scrub`), its rules in its
order: emails, the profile folder, a path ending in a project or export file
(or a bare such file name), the known project folders, the machine name, the
user name. Only the app knows the machine, so production scrubs without a
context: any drive's Users folder entry stands for the profile folder (the
shared Public and Default ones excepted) and the last three rules do
nothing. tests/contracts/telemetry/log-tail-*.txt and scrub-context.json pin
it.
"""

import re
from dataclasses import dataclass
from typing import Any

_SEG = r'[^\\/:*?"<>|\r\n]'
# The profile folder when the machine is unknown: X:\Users\<name>, not the
# shared folders every Windows has.
PROFILE_RE = re.compile(
    r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]"
    r"(?!(?:Public|Default|Default User|All Users)(?!" + _SEG + r"))" + _SEG + r"+",
    re.IGNORECASE,
)
PATH_SEP_RE = re.compile(r"[\\/]")
# OP1's IsEnumOrVersion (letters, digits, _ . + -; 1 to 64), and ':'.
TOKEN_RE = re.compile(r"^[\w.:+\-]{1,64}$")

# The project and export files OP1 replaces, longest first where one is a
# prefix of another (TelemetryPrivacy.cpp `ProjectExts`).
PROJECT_EXTS = (
    ".tbxpack", ".tbxp", ".tbxa", ".tbxm", ".tbxt", ".dxf", ".dwg", ".ifc",
    ".pdf", ".gltf", ".glb", ".obj", ".fbx",
)
# Characters a path never crosses when the scrubber looks for where it starts.
_BREAKS = frozenset("\"'<>|\r\n\t()[]")
# An extension that ends a file name: a name character before it, no word
# character after it.
_PROJECT_FILE_RE = re.compile(
    r"(?<=[^\"'<>|\r\n\t()\[\] \\/])(?:"
    + "|".join(re.escape(ext) for ext in PROJECT_EXTS)
    + r")(?!\w)",
    re.IGNORECASE,
)
_LONGEST_EXT = max(len(ext) for ext in PROJECT_EXTS)

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
    ("export.run", "kind"): ("pdf", "dxf", "dwg", "ifc", "panorama", "video", "share"),
    ("perf.frame", "mode"): ("Unlit", "Lit", "Wireframe"),
    ("error.logged", "verbosity"): ("warning", "error", "ensure"),
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


@dataclass(frozen=True)
class ScrubContext:
    """The machine a log was written on (OP1's `FTelemetryScrubContext`).
    Only the app knows it; the server scrubs without one, and the contract's
    scrub-context.json gives the fixture's."""

    profile_dir: str = ""
    user_name: str = ""
    host_name: str = ""
    project_dirs: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, data: dict) -> "ScrubContext":
        return cls(
            profile_dir=data.get("profile_dir") or "",
            user_name=data.get("user_name") or "",
            host_name=data.get("host_name") or "",
            project_dirs=tuple(data.get("project_dirs") or ()),
        )


# --- the scrubber (OP1's TelemetryPrivacy::Scrub, rule by rule) ----------------------


def _is_word(c: str) -> bool:
    return c.isalnum() or c == "_"


def _email_at(text: str, at: int) -> tuple[int, int] | None:
    """The span of an email around the '@' at `at`, or None (OP1's EmailAt)."""
    start = at
    while start > 0 and (text[start - 1].isalnum() or text[start - 1] in "._%+-"):
        start -= 1
    end = at + 1
    while end < len(text) and (text[end].isalnum() or text[end] in ".-"):
        end += 1
    # Trailing dots and dashes belong to the sentence, not the domain.
    while end > at + 1 and text[end - 1] in ".-":
        end -= 1
    if start == at or end <= at + 1:
        return None
    domain = text[at + 1 : end]
    dot = domain.rfind(".")
    if dot <= 0:
        return None
    tld = domain[dot + 1 :]
    if len(tld) < 2 or not tld.isalpha():
        return None
    return start, end


def has_email(text: str) -> bool:
    at = text.find("@")
    while at >= 0:
        if _email_at(text, at):
            return True
        at = text.find("@", at + 1)
    return False


def replace_emails(text: str) -> str:
    out, copied = [], 0
    at = text.find("@")
    while at >= 0:
        span = _email_at(text, at)
        if span and span[0] >= copied:
            out += [text[copied : span[0]], "<email>"]
            copied = span[1]
            at = text.find("@", copied)
        else:
            at = text.find("@", at + 1)
    out.append(text[copied:])
    return "".join(out)


def _replace_ci(text: str, needle: str, replacement: str) -> str:
    if not needle:
        return text
    return re.sub(re.escape(needle), lambda _m: replacement, text, flags=re.IGNORECASE)


def _replace_path_prefix(text: str, needle: str, replacement: str) -> str:
    """Every occurrence of a folder in its \\ and / spellings, any case."""
    if len(needle) < 3:
        return text
    back = needle.replace("/", "\\").rstrip("\\")
    forward = needle.replace("\\", "/").rstrip("/")
    return _replace_ci(_replace_ci(text, back, replacement), forward, replacement)


def _replace_word(text: str, word: str, replacement: str) -> str:
    """Whole-word, any-case replace (no word character touches either side)."""
    if len(word) < 3:
        return text
    out, copied = [], 0
    for m in re.finditer(re.escape(word), text, re.IGNORECASE):
        a, b = m.span()
        if (a == 0 or not _is_word(text[a - 1])) and (b >= len(text) or not _is_word(text[b])):
            out += [text[copied:a], replacement]
            copied = b
    out.append(text[copied:])
    return "".join(out)


def _path_root_before(text: str, pos: int) -> int | None:
    """Where the path ending at `pos` starts: a drive root (X:\\ X:/), a UNC
    root (\\\\) or %USERPROFILE%, looking back on the same line without
    crossing a break."""
    for i in range(pos - 1, -1, -1):
        c = text[i]
        if c in _BREAKS:
            return None
        if (
            c == ":"
            and i > 0
            and text[i - 1].isalpha()
            and i + 1 < len(text)
            and text[i + 1] in "\\/"
            and (i - 1 == 0 or not text[i - 2].isalnum())
        ):
            return i - 1
        if c == "\\" and i > 0 and text[i - 1] == "\\" and (i - 1 == 0 or not text[i - 2].isalnum()):
            return i - 1
        if c == "%" and text[i : i + 13].upper() == "%USERPROFILE%":
            return i
    return None


def _replace_project_files(text: str) -> str:
    """A path ending in a project or export file, from its root to the
    extension, or a bare such file name -> <project>; the first one in the
    text each time, until none is left."""
    pos = 0
    while True:
        m = _PROJECT_FILE_RE.search(text, pos)
        if m is None:
            return text
        ext_at, end = m.span()
        start = _path_root_before(text, ext_at)
        if start is None:
            # A bare file name: back to the last separator, space or break.
            start = ext_at
            while start > 0 and text[start - 1] not in _BREAKS and text[start - 1] not in " \\/:=":
                start -= 1
        text = text[:start] + "<project>" + text[end:]
        # Only an extension ending right where the text changed can have become
        # a match; everything before it was looked at already.
        pos = max(0, start - _LONGEST_EXT)


def scrub_log(text: str, context: ScrubContext | None = None) -> str:
    text = replace_emails(text)
    if context is None:
        text = PROFILE_RE.sub("%USERPROFILE%", text)
    elif context.profile_dir:
        text = _replace_path_prefix(text, context.profile_dir, "%USERPROFILE%")
    text = _replace_project_files(text)
    if context is None:
        return text
    # Longest folders first, so a folder inside another is not cut in half.
    for folder in sorted(context.project_dirs, key=len, reverse=True):
        if context.profile_dir:
            folder = _replace_path_prefix(folder, context.profile_dir, "%USERPROFILE%")
        text = _replace_path_prefix(text, folder, "<project>")
    if context.host_name:
        text = _replace_word(text, context.host_name, "<host>")
    if context.user_name:
        text = _replace_word(text, context.user_name, "<user>")
    return text


def scan_log(text: str, field: str = "log") -> Violation | None:
    """Refuse a tail the context-free scrubber would change. Each of its rules
    puts something else in place of what it finds, so that is whether any rule
    finds anything: one pass each, however many paths a hostile tail holds."""
    if has_email(text) or PROFILE_RE.search(text) or _PROJECT_FILE_RE.search(text):
        return Violation(field, "log")
    return None


# --- the payload scanner ---------------------------------------------------------------


def _join(base: str, key: Any) -> str:
    if isinstance(key, int):
        return f"{base}[{key}]"
    return f"{base}.{key}" if base else str(key)


def _scan_plain(value: Any, field: str, *, paths: bool = False, skip: frozenset = frozenset()) -> Violation | None:
    """Emails anywhere below `value`; path separators too when `paths`."""
    if isinstance(value, str):
        if has_email(value):
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


def _enum_values(event: Any, key: str) -> tuple[str, ...] | None:
    name = event.lower() if isinstance(event, str) else event
    return ENUM_PROPS.get((name, key.lower()))


def canonical_enum(event: Any, key: str, value: Any) -> str | None:
    """§6.1's spelling of an enum prop's value, matched without case; None when
    the prop is no enum or the value is not one of its values."""
    allowed = _enum_values(event, key)
    if allowed is None or not isinstance(value, str):
        return None
    return next((a for a in allowed if a.lower() == value.lower()), None)


def _scan_prop(event: Any, key: str, value: Any, field: str) -> Violation | None:
    hit = _scan_plain(key, field, paths=True)
    if hit:
        return hit
    k = key.lower()
    enum = _enum_values(event, key) is not None
    if isinstance(value, bool):
        return None if k not in INT_PROPS and not enum else Violation(field, "type")
    if isinstance(value, int):
        return None if k not in BOOL_PROPS and not enum else Violation(field, "type")
    if isinstance(value, str):
        if has_email(value):
            return Violation(field, "email")
        if PATH_SEP_RE.search(value):
            return Violation(field, "path")
        if enum:
            return None if canonical_enum(event, key, value) else Violation(field, "type")
        if k in INT_PROPS or k in BOOL_PROPS or not TOKEN_RE.match(value):
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
    """Emails anywhere, the text a person typed included; no separator rule."""
    return _scan_plain(feedback, "")
