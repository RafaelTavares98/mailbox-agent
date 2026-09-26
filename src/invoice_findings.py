"""The bridge back to the invoice pipeline.

Project 1 writes a file of every check that failed, and until now
nobody read it. Each of those lines is a question somebody has to
answer: the invoice is four dollars short, so is it accepted or sent
back?

This turns that file into questions of the same shape the agent already
asks, so one queue holds everything waiting on a person.
"""

import csv
from pathlib import Path
from typing import List

from understood import UNSURE, Understood

#: What project 1 calls its file of failed checks.
FINDINGS_FILE = "findings.csv"

#: The kind these questions carry, so a rule learned about an invoice
#: check is never applied to an order email.
KIND = "invoice_check"


def read_findings(folder: Path) -> List[Understood]:
    """Turn every failed check into a question the agent can ask."""
    path = Path(folder) / FINDINGS_FILE
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [_as_question(row) for row in _by_invoice(rows)]


def _by_invoice(rows: List[dict]) -> List[dict]:
    """One entry per invoice, carrying all of its failed checks.

    An invoice that broke three rules is one conversation, not three.
    """
    gathered = {}
    for row in rows:
        number = row.get("invoice_number") or row.get("source_file") or "?"
        held = gathered.setdefault(
            number,
            {"number": number, "source": row.get("source_file", ""),
             "rules": [], "messages": []},
        )
        held["rules"].append(row.get("rule", ""))
        held["messages"].append(row.get("message", ""))
    return list(gathered.values())


def _as_question(held: dict) -> Understood:
    """One invoice, and everything wrong with it, as one question."""
    return Understood(
        message_id=held["number"],
        sender=held["source"],
        subject=f"Invoice {held['number']}",
        kind=KIND,
        lane=UNSURE,
        reasons=[m for m in held["messages"] if m],
    )
