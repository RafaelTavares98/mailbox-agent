"""The kinds of mail this agent knows, read from a data file.

A sixth kind is a new entry in `message_kinds.json`. It is never a change
to the code, because the person who knows what a new kind looks like is
rarely the person who can edit Python.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

DEFINITIONS = Path(__file__).with_name("message_kinds.json")

#: The kind for mail that matches nothing. It is not a failure. Most of an
#: inbox is neither an order nor a quote, and saying so is an answer.
UNKNOWN = "unknown"

#: A kind that carries no fields is read and then left alone.
IGNORED = ("newsletter",)


@dataclass(frozen=True)
class Field:
    """One thing to pull out of a message."""

    name: str
    type: str
    required: bool


@dataclass(frozen=True)
class Kind:
    """One kind of mail, and what it is worth pulling out of it."""

    code: str
    name: str
    subject_words: Tuple[str, ...]
    fields: Tuple[Field, ...]

    @property
    def required(self) -> Tuple[str, ...]:
        """The fields without which the row means nothing."""
        return tuple(f.name for f in self.fields if f.required)

    @property
    def worth_reading(self) -> bool:
        """False for the kinds that are read and then dropped."""
        return self.code not in IGNORED and bool(self.fields)


@lru_cache(maxsize=1)
def all_kinds() -> Dict[str, Kind]:
    """Every kind the agent knows."""
    raw = json.loads(DEFINITIONS.read_text(encoding="utf-8"))
    return {code: _build(code, row) for code, row in raw.items()}


def kind_for(code: str) -> Kind:
    """One kind, or a complaint naming the ones that exist."""
    kinds = all_kinds()
    if code not in kinds:
        known = ", ".join(sorted(kinds))
        raise KeyError(f"unknown kind {code!r}, known are {known}")
    return kinds[code]


def field_names(code: str) -> List[str]:
    """The columns one kind of mail fills."""
    return [field.name for field in kind_for(code).fields]


def money_field_names() -> List[str]:
    """Every column that holds an amount.

    A sheet prints 3480.00 as 3480 unless it is told otherwise, and on
    a column of totals that looks like a rounding nobody asked for.
    """
    names = {
        f.name
        for kind in all_kinds().values()
        for f in kind.fields
        if f.type == "money"
    }
    return sorted(names)


def every_field_name() -> List[str]:
    """Every column any kind fills, in a settled order.

    One table holds every kind, so a column belongs to the table even when
    most rows leave it empty. Sorting keeps the file the same shape from
    one run to the next.
    """
    names = {f.name for kind in all_kinds().values() for f in kind.fields}
    return sorted(names)


def _build(code: str, row: dict) -> Kind:
    """Turn one record from the file into a Kind."""
    return Kind(
        code=code,
        name=row["name"],
        subject_words=tuple(row["subject_words"]),
        fields=tuple(Field(**field) for field in row["fields"]),
    )
