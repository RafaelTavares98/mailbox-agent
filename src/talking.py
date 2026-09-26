"""Talking to the agent in a terminal.

Two conversations, and nothing else. The agent asks about what it could
not settle, and the person asks about what it collected. Both are short
on purpose: this is the part a client watches in a demo, and a demo that
needs explaining has already failed.

The table is handed to the model as text, so an answer can only come
from rows that exist. Nothing is invented from the model's own memory.
"""

import csv
from pathlib import Path
from typing import List

from learned_rules import DECISIONS, DROP, KEEP, remember
from table_output import QUESTIONS_FILE, ROWS_FILE

#: How many rows go to the model when a question is asked. A whole year
#: of mail would cost more than the answer is worth.
ROWS_IN_VIEW = 200

ASKING = (
    "You answer questions about a table of business emails.\n"
    "Answer only from the rows given. If the rows do not say, reply "
    "that the table does not say it.\n"
    "Be short. Give the figure or the name, then one sentence.\n"
)

#: What the person can type when the agent asks about a message.
ANSWERS = {
    "k": KEEP,
    "keep": KEEP,
    "d": DROP,
    "drop": DROP,
    "s": "skip",
    "skip": "skip",
}


def read_table(folder: Path, name: str) -> List[dict]:
    """One of the agent's files, as rows."""
    path = Path(folder) / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def answer(question: str, folder: Path, ask_model) -> str:
    """Answer one question about the table."""
    rows = read_table(folder, ROWS_FILE)
    if not rows:
        return "There is nothing in the table yet."
    return ask_model(build_prompt(question, rows)).strip()


def build_prompt(question: str, rows: List[dict]) -> str:
    """The question, with the rows it may be answered from."""
    columns = list(rows[0])
    lines = ["\t".join(columns)]
    for row in rows[:ROWS_IN_VIEW]:
        lines.append("\t".join(row.get(name, "") for name in columns))
    return f"{ASKING}\nRows:\n" + "\n".join(lines) + f"\n\nQuestion: {question}"


def walk_questions(folder: Path, memory: Path, read_line, say) -> int:
    """Go through the open questions and keep what the person decides.

    `read_line` and `say` are passed in so this can be driven by a test
    as easily as by a person at a keyboard.
    """
    open_ones = read_table(folder, QUESTIONS_FILE)
    if not open_ones:
        say("Nothing to ask about.")
        return 0
    learned = 0
    for row in open_ones:
        say("")
        say(row["question"])
        say("  k = keep it anyway, d = drop this kind, s = skip for now")
        decided = ANSWERS.get((read_line("> ") or "").strip().lower())
        if decided in DECISIONS:
            remember(memory, row["kind"], row["reasons"], decided)
            learned += 1
            say(f"  kept as a rule: {row['reasons']} -> {decided}")
        else:
            say("  left open")
    return learned
