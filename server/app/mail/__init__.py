"""Outgoing mail every feature codes against (PF14 Plumbing).

    send_mail(to, template, data, *, reply_to=None) -> Message
    try_send(to, template, data, ...) -> Message | None   # never raises

Templates live in app/mail/templates/<name>.subject.txt, <name>.txt and
<name>.html, rendered with `string.Template` (`$name`; a missing value raises
KeyError); values are HTML-escaped in the .html part. MAIL_BACKEND picks the
adapter: `console` (kept in OUTBOX, logged and printed in the API console;
development and tests) or `smtp` (the provider's relay; SPF, DKIM and DMARC
records live in infra/tofu).
"""

import html
import logging
from dataclasses import dataclass
from pathlib import Path
from string import Template

from ..config import get_settings

log = logging.getLogger("truebex.mail")
settings = get_settings()

TEMPLATES = Path(__file__).parent / "templates"


@dataclass
class Message:
    to: str
    subject: str
    text: str
    html: str
    sender: str
    reply_to: str | None = None
    template: str = ""


# Mail the console backend "sent", newest last.
OUTBOX: list[Message] = []


def _read(name: str, suffix: str) -> Template:
    path = TEMPLATES / f"{name}{suffix}"
    if not path.is_file():
        raise KeyError(f"no mail template {name}{suffix}")
    return Template(path.read_text(encoding="utf-8"))


def render(template: str, data: dict) -> Message:
    values = {k: "" if v is None else str(v) for k, v in data.items()}
    escaped = {k: html.escape(v) for k, v in values.items()}
    subject = _read(template, ".subject.txt").substitute(values).strip()
    return Message(
        to="",
        subject=subject,
        text=_read(template, ".txt").substitute(values),
        html=_read(template, ".html").substitute(escaped),
        sender=settings.mail_from,
        template=template,
    )


def send_mail(to: str, template: str, data: dict, *, reply_to: str | None = None) -> Message:
    msg = render(template, data)
    msg.to = to
    msg.reply_to = reply_to
    if settings.mail_backend == "smtp":
        from . import smtp

        smtp.send(msg)
    else:
        OUTBOX.append(msg)
        log.info("mail to %s: %s", to, msg.subject)
        # The console backend is the local stand-in for an inbox (invite links).
        print(f"\n--- mail to {to}: {msg.subject}\n{msg.text}\n---", flush=True)
    return msg


def try_send(to: str, template: str, data: dict, **kw) -> Message | None:
    """send_mail that never fails the request: a mail outage is logged, not raised."""
    try:
        return send_mail(to, template, data, **kw)
    except Exception:  # noqa: BLE001
        log.exception("mail %s to %s failed", template, to)
        return None
