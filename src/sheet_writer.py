"""Putting the two tables into a Google Sheet.

The sheet's own half is a script that lives inside the spreadsheet, so
there is no Google Cloud project, no consent screen and no key to
manage. It listens on one address, and this posts to it.

The whole table goes every run and the tab is replaced. Appending would
double every row on a second run, and a sheet nobody can trust is worse
than no sheet at all.
"""

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import List

from message_kinds import money_field_names
from table_output import (
    QUESTION_COLUMNS, all_columns, questions_for, rows_for,
)

#: Where the address and the shared word are filed. The keychain, like
#: every other secret here.
KEYCHAIN_SERVICE = "mailbox-agent-sheet"
ADDRESS = "web-app-url"
WORD = "shared-word"

ROWS_TAB = "rows"
QUESTIONS_TAB = "questions"


class SheetRefused(RuntimeError):
    """The sheet could not be reached, or would not take the rows."""


def send_tables(understood) -> dict:
    """Put both tables in the sheet, and say what was written."""
    address, word = _account()
    written = {
        ROWS_TAB: _post(
            address, word, ROWS_TAB, all_columns(), rows_for(understood)
        ),
        QUESTIONS_TAB: _post(
            address, word, QUESTIONS_TAB, list(QUESTION_COLUMNS),
            questions_for(understood),
        ),
    }
    return written


def store(address: str, word: str) -> None:
    """Keep the address and the shared word for later runs."""
    import keyring

    keyring.set_password(KEYCHAIN_SERVICE, ADDRESS, address)
    keyring.set_password(KEYCHAIN_SERVICE, WORD, word)


def is_set_up() -> bool:
    """Whether a sheet has been connected on this machine."""
    import keyring

    return bool(keyring.get_password(KEYCHAIN_SERVICE, ADDRESS))


def _account():
    """The address and the shared word, or how to set them."""
    import keyring

    address = keyring.get_password(KEYCHAIN_SERVICE, ADDRESS)
    word = keyring.get_password(KEYCHAIN_SERVICE, WORD)
    if not address or not word:
        raise SheetRefused(
            "No sheet connected. Deploy sheet/Codigo.gs from the "
            "spreadsheet, then store the address it gives back with: "
            f"python -m keyring set {KEYCHAIN_SERVICE} {ADDRESS}"
        )
    return address, word


def _post(address: str, word: str, tab: str, columns, rows) -> int:
    """Send one table, and return how many rows the sheet took."""
    payload = json.dumps({
        "word": word,
        "tab": tab,
        "columns": list(columns),
        "rows": rows,
        "money": money_field_names(),
    }).encode()
    request = urllib.request.Request(
        address, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as answer:
            said = json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        raise SheetRefused(
            f"The sheet turned the rows down ({refused.code})"
        )
    except urllib.error.URLError:
        raise SheetRefused("I could not reach the sheet")
    if not said.get("ok"):
        raise SheetRefused(f"The sheet said no: {said.get('why')}")
    return said.get("written", 0)
