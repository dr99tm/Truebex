"""Outgoing mail every feature codes against (PF14 Plumbing).

    send_mail(to, template, data, *, reply_to=None) -> Message

Templates live in app/mail/templates/<name>.subject.txt, <name>.txt and
<name>.html, rendered with `string.Template` (`$name`); values are HTML-escaped
in the .html part. MAIL_BACKEND picks the adapter: `console` (kept in OUTBOX,
logged and printed to stderr; development and tests) or `smtp` (the provider's relay; SPF, DKIM
and DMARC records live in infra/tofu).
"""

import html
import logging
import sys
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
    subject = _read(template, ".subject.txt").safe_substitute(values).strip()
    return Message(
        to="",
        subject=subject,
        text=_read(template, ".txt").safe_substitute(values),
        html=_read(template, ".html").safe_substitute(escaped),
        sender=settings.mail_from,
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
        # The console backend prints the whole text part, so links in mail
        # (project invitations) can be followed in local testing.
        print(f"--- mail to {to}: {msg.subject}\n{msg.text}\n--- end of mail", file=sys.stderr, flush=True)
    return msg
