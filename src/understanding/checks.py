"""Deciding whether the agent is sure, and saying why when it is not.

The confidence is not a number the model invented. Asking a model how
sure it is returns a figure that means nothing, because it was produced
by the same guess it is meant to judge.

Every doubt here is a fact the code checked itself: a field that is not
there, a date that is not a date, an amount that is not a number. Each
one becomes a sentence a person can answer.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Dict, List

from message_kinds import Kind

A_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
A_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")

#: A date this far from today is a typing slip or a year read wrong.
YEARS_EITHER_WAY = 5


def doubts(fields: Dict[str, str], kind: Kind) -> List[str]:
    """Everything wrong with what was read, in plain sentences."""
    found = []
    found.extend(_missing(fields, kind))
    found.extend(_malformed(fields, kind))
    return found


def _missing(fields: Dict[str, str], kind: Kind) -> List[str]:
    """The required fields the message never gave."""
    absent = [
        name for name in kind.required if not (fields.get(name) or "").strip()
    ]
    if not absent:
        return []
    if len(absent) == 1:
        return [f"the {_spoken(absent[0])} is missing"]
    spoken = ", ".join(_spoken(name) for name in absent)
    return [f"these are missing: {spoken}"]


def _malformed(fields: Dict[str, str], kind: Kind) -> List[str]:
    """The fields that are there but are not what they claim to be."""
    found = []
    for field in kind.fields:
        value = (fields.get(field.name) or "").strip()
        if not value:
            continue
        complaint = _wrong_shape(field, value)
        if complaint:
            found.append(complaint)
    return found


def _wrong_shape(field, value: str):
    """One sentence about one bad value, or None when it is fine."""
    if field.type == "date":
        return _bad_date(field, value)
    if field.type in ("money", "number"):
        return _bad_number(field, value)
    return None


def _bad_date(field, value: str):
    if not A_DATE.match(value):
        return f"the {_spoken(field.name)} does not read as a date: {value!r}"
    year, month, day = (int(part) for part in value.split("-"))
    try:
        given = date(year, month, day)
    except ValueError:
        return f"there is no such day as {value}"
    this_year = date.today().year
    if abs(given.year - this_year) > YEARS_EITHER_WAY:
        return f"the {_spoken(field.name)} is {given.year}, which is far off"
    return None


def _bad_number(field, value: str):
    cleaned = value.replace(",", "")
    if not A_NUMBER.match(cleaned):
        return (
            f"the {_spoken(field.name)} does not read as a number: "
            f"{value!r}"
        )
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return f"the {_spoken(field.name)} does not read as a number"
    if amount < 0:
        return f"the {_spoken(field.name)} is negative: {value}"
    if field.type == "number" and amount == 0:
        return f"the {_spoken(field.name)} is zero"
    return None


def _spoken(name: str) -> str:
    """A field name as a person would say it."""
    return name.replace("_", " ")
