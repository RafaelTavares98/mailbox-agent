"""The whole chain, from a mailbox to the two files.

This module holds the order of the steps and nothing else, so a change
to any one step never reaches it.

It reads the mail project 1 leaves behind: the messages with no file
attached. Project 1 takes the invoices; this takes the words.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List

from learned_rules import DROP, KEEP, decide, read_rules
from message_kinds import UNKNOWN, kind_for
from table_output import (
    QUESTIONS_FILE, ROWS_FILE, write_questions, write_rows,
)
from understanding.checks import doubts
from understanding.classify_kind import classify
from understanding.field_reader import ModelRefused, read_fields
from understood import BROKEN, CONFIDENT, DROPPED, UNSURE, Understood

#: Mail with a file attached belongs to the invoice pipeline. Reading it
#: here would make two programs answer for the same message.
LEAVE_TO_THE_OTHER_READER = True


@dataclass
class AgentRun:
    """What one pass over the mailbox did."""

    seen: int
    understood: List[Understood] = field(default_factory=list)
    rows_csv: Path = None
    questions_csv: Path = None
    model_calls: int = 0

    @property
    def confident(self) -> int:
        return len([u for u in self.understood if u.lane == CONFIDENT])

    @property
    def unsure(self) -> int:
        return len([u for u in self.understood if u.lane == UNSURE])

    @property
    def broken(self) -> int:
        return len([u for u in self.understood if u.lane == BROKEN])

    @property
    def ignored(self) -> int:
        """Mail that was read and is worth nothing to the table."""
        return self.seen - len(self.understood)


def run(
    mailbox, output: Path, ask_model: Callable[[str], str],
    memory: Path = None,
) -> AgentRun:
    """Read the mailbox and write the two files.

    `memory` is where the answers already given are kept. A doubt that
    was settled once is applied and not asked again.
    """
    output = Path(output)
    rules = read_rules(memory or output)
    result = AgentRun(seen=0)
    counted = _counting(ask_model)
    for message in mailbox.messages():
        result.seen += 1
        if LEAVE_TO_THE_OTHER_READER and message.attachments:
            continue
        one = read_one(message, counted)
        if one is None:
            continue
        _apply_memory(one, rules)
        if one.lane != DROPPED:
            result.understood.append(one)
    result.model_calls = counted.calls
    result.rows_csv = write_rows(result.understood, output / ROWS_FILE)
    result.questions_csv = write_questions(
        result.understood, output / QUESTIONS_FILE
    )
    return result


def read_one(message, ask_model):
    """Make what can be made of one message, or nothing at all."""
    body = _body_of(message)
    code = classify(message.subject, body)
    if code == UNKNOWN:
        return _lane(
            message, code, BROKEN, ["I do not know this kind of mail"]
        )
    kind = kind_for(code)
    if not kind.worth_reading:
        return None
    try:
        fields = read_fields(message.subject, body, kind, ask_model)
    except ModelRefused as refused:
        return _lane(message, code, BROKEN, [str(refused)])
    reasons = doubts(fields, kind)
    lane = UNSURE if reasons else CONFIDENT
    one = _lane(message, code, lane, reasons)
    one.fields = fields
    return one


def _apply_memory(one, rules) -> None:
    """Act on what a person already decided about this exact doubt.

    "Keep" moves the row into the table and records who said so, so the
    file shows a judgement rather than a certainty the agent never had.
    "Drop" takes the message off the list entirely.
    """
    if one.lane != UNSURE:
        return
    decided = decide(rules, one.kind, one.reasons)
    if decided == KEEP:
        one.lane = CONFIDENT
        one.answered_by_rule = "; ".join(one.reasons)
    elif decided == DROP:
        one.lane = DROPPED
        one.answered_by_rule = "; ".join(one.reasons)


def _counting(ask_model):
    """Wrap the model so the run knows what it actually spent.

    Counting the calls is the only honest way to say so. A number worked
    out from the number of messages is a guess, and it stops being true
    the day a message is read twice.
    """

    class Counted:
        calls = 0

        def __call__(self, prompt):
            Counted.calls += 1
            return ask_model(prompt)

    return Counted()


def _lane(message, code, lane, reasons) -> Understood:
    """One reading, in the lane it belongs to."""
    return Understood(
        message_id=message.identifier,
        sender=message.sender,
        subject=message.subject,
        kind=code,
        lane=lane,
        reasons=reasons,
    )


def _body_of(message) -> str:
    """The words of a message, whichever shape it arrived in."""
    return getattr(message, "body", "") or ""
