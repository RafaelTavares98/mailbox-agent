"""Deciding what kind of message this is.

Rules first. A subject that says "Purchase order 4417" needs no model to
read, and paying one to read it is money spent on a solved problem. The
model is asked only about the mail the words could not settle.
"""

import re
from typing import Optional

from message_kinds import UNKNOWN, all_kinds



def classify(subject: str, body: str, ask_model=None) -> str:
    """Return the code of the kind, or `UNKNOWN`.

    `ask_model` is called only when the words decided nothing, and only
    when a caller supplied one. Without it the answer is `UNKNOWN`, which
    is honest: nothing here recognised the message.
    """
    by_words = classify_by_words(subject, body)
    if by_words:
        return by_words
    if ask_model is None:
        return UNKNOWN
    answered = ask_model(subject, body)
    return answered if answered in all_kinds() else UNKNOWN


def classify_by_words(subject: str, body: str) -> Optional[str]:
    """The kind whose words appear in the subject, or in the body.

    The subject is trusted over the body. A body can quote another mail,
    and a quoted order does not make the reply an order.
    """
    for where in (subject, body):
        found = _first_match(where or "")
        if found:
            return found
    return None


def _first_match(text: str) -> Optional[str]:
    """The kind whose word comes first in this text.

    Earliest wins, and a longer word beats a shorter one at the same
    spot. "Shipment for order 4417" is a delivery notice, not an order:
    the writer said what the mail was before saying what it was about.
    A reader that took whichever kind it happened to check first got
    that backwards, and silently.
    """
    lowered = text.lower()
    best = None
    for code, kind in all_kinds().items():
        for word in kind.subject_words:
            wanted = word.strip()
            found = re.search(
                rf"(?<![a-z]){re.escape(wanted)}", lowered
            )
            if not found:
                continue
            score = (found.start(), -len(wanted))
            if best is None or score < best[0]:
                best = (score, code)
    return best[1] if best else None
