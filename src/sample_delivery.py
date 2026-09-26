"""Posting the invented mail to a real mailbox.

The folder proves the code works. A real server proves it works where
the client's mail lives, with the same headers, the same encodings and
the same surprises.

Each sample keeps its own sender name. The address underneath is the one
real account, tagged, because a free account cannot send from a domain
it does not own.
"""

import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from typing import List, Optional

from sample_messages import SAMPLES, Sample

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

#: The account is not a secret, so an environment variable is its home.
ACCOUNT = "INVOICE_SMTP_USER"

#: Where the mailbox password is filed, alongside the invoice pipeline's.
KEYCHAIN_SERVICE = "invoice-pipeline"

#: A mark in the subject, so a test run can be told from real mail and
#: cleaned up afterwards.
MARK = "[sample]"


class MissingAccount(RuntimeError):
    """The sending account was never set."""


def send_samples(recipient: Optional[str] = None) -> List[str]:
    """Mail every sample, and return the subjects that went out."""
    import keyring

    account = os.environ.get(ACCOUNT)
    if not account:
        raise MissingAccount(f"Set {ACCOUNT} to the sending address.")
    password = keyring.get_password(KEYCHAIN_SERVICE, account)
    if not password:
        raise MissingAccount("No mailbox password in the keychain.")
    recipient = recipient or account

    sent = []
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
    try:
        server.starttls(context=ssl.create_default_context())
        server.login(account, password)
        for sample in SAMPLES:
            mail = build_mail(sample, account, recipient)
            server.send_message(mail)
            sent.append(mail["Subject"])
    finally:
        server.quit()
    return sent


def build_mail(sample: Sample, account: str, recipient: str):
    """One sample as a real mail, under its own sender name."""
    mail = EmailMessage()
    mail["From"] = _sender_for(sample, account)
    mail["To"] = recipient
    mail["Subject"] = f"{MARK} {sample.subject}"
    mail.set_content(sample.body)
    return mail


def _sender_for(sample: Sample, account: str) -> str:
    """The sample's own name, over the one real address."""
    name, domain = account.split("@", 1)
    return f"{_display_name(sample)} <{name}+{sample.identifier}@{domain}>"


def _display_name(sample: Sample) -> str:
    """The company the sample claims to be, without its address."""
    return re.sub(r"\s*<[^>]*>", "", sample.sender).strip()
