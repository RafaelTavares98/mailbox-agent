"""The two files the agent leaves behind.

One row per message it understood, and one row per message it wants to
ask about. Nothing is dropped: a message the agent could not read still
appears, in the second file, with the reason.
"""

import csv
from pathlib import Path
from typing import List

from message_kinds import every_field_name
from understood import CONFIDENT, Understood

ROWS_FILE = "rows.csv"
QUESTIONS_FILE = "questions.csv"

#: Windows writes a carriage return that a reader elsewhere sees as a
#: blank row. Pin the terminator so the file travels.
LINE_TERMINATOR = "\n"

FIXED_COLUMNS = ("message_id", "sender", "subject", "kind")
QUESTION_COLUMNS = (
    "message_id", "sender", "subject", "kind", "question", "reasons",
)


def all_columns() -> List[str]:
    """Every column of the table of understood messages."""
    return list(FIXED_COLUMNS) + every_field_name()


def rows_for(understood: List[Understood]) -> List[dict]:
    """Every message the agent was sure about, as rows.

    Separate from the writing, because the same rows go to a file and to
    a sheet. Building them twice is how two outputs start disagreeing.
    """
    columns = all_columns()
    return [
        {
            "message_id": one.message_id,
            "sender": one.sender,
            "subject": one.subject,
            "kind": one.kind,
            **{k: v for k, v in one.fields.items() if k in columns},
        }
        for one in understood
        if one.lane == CONFIDENT
    ]


def questions_for(understood: List[Understood]) -> List[dict]:
    """Every message the agent wants a person to settle, as rows."""
    return [
        {
            "message_id": one.message_id,
            "sender": one.sender,
            "subject": one.subject,
            "kind": one.kind,
            "question": one.question,
            "reasons": "; ".join(one.reasons),
        }
        for one in understood
        if one.lane != CONFIDENT
    ]


def write_rows(understood: List[Understood], target: Path) -> Path:
    """Every message the agent was sure about, one row each."""
    return _write(rows_for(understood), all_columns(), target)


def write_questions(understood: List[Understood], target: Path) -> Path:
    """Every message the agent wants a person to settle."""
    return _write(
        questions_for(understood), list(QUESTION_COLUMNS), target
    )


def _write(rows: List[dict], columns: List[str], target: Path) -> Path:
    """One table, as a file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, lineterminator=LINE_TERMINATOR
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return target
