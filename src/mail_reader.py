"""Where the mail comes from, and what is taken out of it.

Two sources answer the same questions: who sent it, what it says, and
whether anything was attached. One reads a folder of mail files, which
is what the tests use. The other speaks IMAP to a real server.

The invoice pipeline has its own reader, which takes the attachments.
This one takes the words, and reports whether a file was there so the
two never answer for the same message.
"""

import email
import re
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import EmailMessage
from html import unescape
from pathlib import Path
from typing import Iterator, List

MAIL_SUFFIX = ".eml"


@dataclass
class Message:
    """One mail, reduced to what the agent needs from it."""

    identifier: str
    sender: str
    subject: str
    body: str
    attachments: List[str]


class LocalMailbox:
    """A folder of mail files, used by the tests and for a dry run."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def messages(self) -> Iterator[Message]:
        """Every mail in the folder, oldest name first."""
        if not self.folder.exists():
            return
        for path in sorted(self.folder.glob(f"*{MAIL_SUFFIX}")):
            yield read_message(path.read_bytes(), path.stem)


class ImapMailbox:
    """A real mailbox on a real server."""

    def __init__(self, host: str, user: str, password: str,
                 folder: str = "INBOX"):
        self.host = host
        self.user = user
        self.password = password
        self.folder = folder

    def messages(self) -> Iterator[Message]:
        """Every mail in the chosen folder, read without marking it."""
        import imaplib

        server = imaplib.IMAP4_SSL(self.host)
        try:
            server.login(self.user, self.password)
            server.select(self.folder, readonly=True)
            _, found = server.search(None, "ALL")
            for number in found[0].split():
                _, data = server.fetch(number, "(RFC822)")
                yield read_message(data[0][1], number.decode())
        finally:
            server.logout()


def write_message(
    folder: Path, identifier: str, sender: str, subject: str, body: str
) -> Path:
    """Put one mail with no attachment into a folder mailbox."""
    folder.mkdir(parents=True, exist_ok=True)
    mail = EmailMessage()
    mail["Subject"] = subject
    mail["From"] = sender
    mail["To"] = "inbox@example.invalid"
    mail["Message-ID"] = f"<{identifier}@example.invalid>"
    mail.set_content(body)
    target = folder / f"{identifier}{MAIL_SUFFIX}"
    target.write_bytes(mail.as_bytes())
    return target


def read_message(raw: bytes, fallback_id: str) -> Message:
    """Turn raw mail bytes into a Message."""
    parsed = email.message_from_bytes(raw)
    identifier = (parsed.get("Message-ID") or "").strip("<>")
    return Message(
        identifier=identifier.split("@")[0] or fallback_id,
        sender=_readable(parsed.get("From")),
        subject=_readable(parsed.get("Subject")),
        body=_plain_body(parsed),
        attachments=_attached_names(parsed),
    )


def _readable(value) -> str:
    """A header as a person would read it, whatever it was encoded in."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except (UnicodeDecodeError, LookupError, ValueError):
        return value.strip()


def _plain_body(parsed) -> str:
    """The words of the mail, whichever part is carrying them.

    The plain part is preferred, because it is what the writer meant.
    When there is none, the words are pulled out of the HTML. A shop or
    an automated system often sends HTML alone, and a reader that gave
    up there would report every one of those as an empty message.
    """
    if not parsed.is_multipart():
        return _words_of(parsed)
    plain = _first_part(parsed, "text/plain")
    if plain:
        return plain
    return _first_part(parsed, "text/html")


def _first_part(parsed, wanted: str) -> str:
    """The first part of this type that is not an attached file."""
    for part in parsed.walk():
        if part.get_content_type() != wanted or part.get_filename():
            continue
        found = _words_of(part)
        if found.strip():
            return found
    return ""


def _words_of(part) -> str:
    """One part as words, with any markup taken off."""
    text = _decoded(part)
    if part.get_content_type() == "text/html":
        return strip_markup(text)
    return text


def _decoded(part) -> str:
    """One part as text, without failing over an odd character set."""
    payload = part.get_payload(decode=True)
    if payload is None:
        return str(part.get_payload() or "")
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def strip_markup(html: str) -> str:
    """Turn a page of HTML into the words a person would read.

    Script and style blocks go first, whole. Their contents are code,
    and code fed to the model is money spent on noise. A block-level tag
    becomes a line break, so a table of order lines does not come back
    as one long sentence.
    """
    text = re.sub(
        r"<(script|style|head)\b.*?</\1>", " ", html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(
        r"</?(p|div|tr|br|li|h[1-6]|table)\b[^>]*>", "\n", text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"</?(td|th)\b[^>]*>", "  ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def _attached_names(parsed) -> List[str]:
    """The names of the files attached, which may be none."""
    return [
        part.get_filename()
        for part in parsed.walk()
        if part.get_filename()
    ]
