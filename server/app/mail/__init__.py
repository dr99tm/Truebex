"""Outgoing e-mail behind one interface (PF14 §Design Plumbing; first user PF3).

    send_mail("a@example.test", "org_invite", {"org_name": "Studio North", …})

Templates live in `templates/<name>.subject.txt`, `.txt` and `.html` and are
rendered with `string.Template` (`$name`); values are HTML-escaped for the
HTML part. MAIL_BACKEND picks the adapter: `console` (dev and tests: the
message is logged and appended to `OUTBOX`) or `smtp` (PF14).
"""

import html
import logging
from dataclasses import dataclass
from pathlib import Path
from string import Template

log = logging.getLogger("truebex.mail")

TEMPLATES = Path(__file__).with_name("templates")


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    text: str
    html: str
    template: str
    sender: str
    reply_to: str | None = None


# Every message the console adapter "sent", oldest first (tests read it).
OUTBOX: list[Message] = []


def render(template: str, data: dict) -> tuple[str, str, str]:
    """(subject, text, html) of a template; a missing $name raises KeyError."""
    values = {k: "" if v is None else str(v) for k, v in data.items()}
    escaped = {k: html.escape(v) for k, v in values.items()}

    def part(suffix: str, vals: dict) -> str:
        return Template((TEMPLATES / f"{template}{suffix}").read_text(encoding="utf-8")).substitute(vals)

    return part(".subject.txt", values).strip(), part(".txt", values), part(".html", escaped)


def send_mail(to: str, template: str, data: dict, *, reply_to: str | None = None) -> Message:
    from ..config import get_settings

    settings = get_settings()
    subject, text, body_html = render(template, data)
    msg = Message(to, subject, text, body_html, template, settings.mail_from, reply_to)
    if settings.mail_backend == "console":
        OUTBOX.append(msg)
        log.warning("mail (console) to %s: %s\n%s", to, subject, text)
        print(f"\n--- mail to {to}: {subject}\n{text}\n---", flush=True)
        return msg
    raise RuntimeError(f"MAIL_BACKEND={settings.mail_backend!r} is not available here (PF14 adds smtp)")


def try_send(to: str, template: str, data: dict, **kw) -> Message | None:
    """send_mail that never fails the request: a mail outage is logged, not raised."""
    try:
        return send_mail(to, template, data, **kw)
    except Exception:  # noqa: BLE001
        log.exception("mail %s to %s failed", template, to)
        return None
