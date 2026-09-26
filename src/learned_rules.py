"""What the agent was told once and does not ask again.

An answer is kept as a rule, and a rule is a row in a plain file. A
person can read every decision the agent is acting on, and delete the
one they regret. A memory nobody can read is a memory nobody can
correct.

A rule is matched on the kind of mail and the doubt, not on the message.
"The order total is missing" is the same question whether it arrives
once or fifty times.
"""

import csv
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional

RULES_FILE = "learned_rules.csv"
COLUMNS = ("kind", "doubt", "decision", "learned_on")

#: What a person can decide about a doubtful message.
KEEP = "keep"
DROP = "drop"
DECISIONS = (KEEP, DROP)


@dataclass(frozen=True)
class Rule:
    """One decision, kept so the same question is asked only once."""

    kind: str
    doubt: str
    decision: str
    learned_on: str = ""

    def covers(self, kind: str, doubt: str) -> bool:
        """True when this rule already answers that question."""
        return self.kind == kind and self.doubt == doubt


def read_rules(folder: Path) -> List[Rule]:
    """Every rule the agent has been taught."""
    path = Path(folder) / RULES_FILE
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [Rule(**row) for row in csv.DictReader(handle)]


def remember(folder: Path, kind: str, doubt: str, decision: str) -> Rule:
    """Keep one decision. A rule already known is not written twice."""
    if decision not in DECISIONS:
        raise ValueError(
            f"a decision is {' or '.join(DECISIONS)}, not {decision!r}"
        )
    rule = Rule(kind, doubt, decision, date.today().isoformat())
    known = read_rules(folder)
    if any(one.covers(kind, doubt) for one in known):
        return rule
    write_rules(folder, known + [rule])
    return rule


def forget(folder: Path, kind: str, doubt: str) -> bool:
    """Drop one rule. Returns whether there was one to drop."""
    known = read_rules(folder)
    kept = [one for one in known if not one.covers(kind, doubt)]
    if len(kept) == len(known):
        return False
    write_rules(folder, kept)
    return True


def write_rules(folder: Path, rules: List[Rule]) -> Path:
    """Write the whole set, so the file is never half a thought."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / RULES_FILE
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        for rule in rules:
            writer.writerow(asdict(rule))
    return path


def decide(rules: List[Rule], kind: str, doubts) -> Optional[str]:
    """What a person already said about these doubts, if anything.

    Every doubt must be covered. A message with two problems where only
    one was settled is still a question, because nobody ever ruled on
    the other one.
    """
    if not doubts:
        return None
    answers = {_answer(rules, kind, doubt) for doubt in doubts}
    if None in answers or len(answers) != 1:
        return None
    return answers.pop()


def _answer(rules: List[Rule], kind: str, doubt: str) -> Optional[str]:
    for rule in rules:
        if rule.covers(kind, doubt):
            return rule.decision
    return None
