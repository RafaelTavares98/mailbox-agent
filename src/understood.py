"""What the agent made of one message.

Three lanes and nothing else. A message is understood, or it raises a
question, or it could not be read at all. There is no fourth state, and
no state that quietly means "probably fine".
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

CONFIDENT = "confident"
UNSURE = "unsure"
BROKEN = "broken"

#: Not a fourth lane. This is what a message becomes after a person said
#: to ignore this kind of doubt, and the agent obeyed.
DROPPED = "dropped"


@dataclass
class Understood:
    """One message, after the agent has had a look at it."""

    message_id: str
    sender: str
    subject: str
    kind: str
    lane: str
    fields: Dict[str, str] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    answered_by_rule: Optional[str] = None

    @property
    def question(self) -> str:
        """What the agent would ask a person about this message.

        One sentence, naming the message and the doubt. "Low confidence"
        tells the reader nothing they can act on.
        """
        if not self.reasons:
            return ""
        return (
            f"{self.subject} — {'; '.join(self.reasons)}. "
            f"What should I do with it?"
        )
