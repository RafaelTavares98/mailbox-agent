"""Invented mail, so the agent can be tried without a real inbox.

The generator knows what it wrote. Every test compares the agent's
answer against the source, so no expected value is typed by hand and
none goes stale when a message changes.

One message of each kind is deliberately broken, because a reader that
has only ever seen good input has not been tested.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from mail_reader import write_message


@dataclass(frozen=True)
class Sample:
    """One invented message, and what it should come out as."""

    identifier: str
    sender: str
    subject: str
    body: str
    kind: str
    #: What a correct reading gives. Empty for a kind with no fields.
    fields: Dict[str, str]
    #: True when the message is missing something on purpose.
    doubtful: bool = False


SAMPLES = (
    Sample(
        identifier="s01",
        sender="Nordwind Handel GmbH <billing@example.invalid>",
        subject="Purchase order 4417",
        body=(
            "Hello,\n\n"
            "Please treat this as purchase order 4417 for Costa Verde "
            "Importacao Ltda.\n"
            "We need 120 units of Stainless hinge, 40mm.\n"
            "The total is 3480.00 and we want it by 2026-10-14.\n\n"
            "Thank you."
        ),
        kind="order",
        fields={
            "order_number": "4417",
            "customer": "Costa Verde Importacao Ltda",
            "product": "Stainless hinge, 40mm",
            "quantity": "120",
            "total": "3480.00",
            "wanted_by": "2026-10-14",
        },
    ),
    Sample(
        identifier="s02",
        sender="Blue Harbor Supply Co. <sales@example.invalid>",
        subject="Order 5120 confirmation",
        body=(
            "Aurora Nordic Distribution has placed order 5120.\n"
            "Item: Insulated cable reel. Quantity: 40.\n"
            "Order total 1996.00. Required by 2026-11-02."
        ),
        kind="order",
        fields={
            "order_number": "5120",
            "customer": "Aurora Nordic Distribution",
            "product": "Insulated cable reel",
            "quantity": "40",
            "total": "1996.00",
            "wanted_by": "2026-11-02",
        },
    ),
    Sample(
        identifier="s03",
        sender="Meridian Freight Lines <ops@example.invalid>",
        subject="Purchase order 5220, urgent",
        body=(
            "Sunbelt Provisions Inc. would like to order Pallet wrap, "
            "heavy duty.\n"
            "Please send a confirmation as soon as you can."
        ),
        kind="order",
        fields={
            "order_number": "5220",
            "customer": "Sunbelt Provisions Inc.",
            "product": "Pallet wrap, heavy duty",
            "quantity": "",
            "total": "",
            "wanted_by": "",
        },
        doubtful=True,
    ),
    Sample(
        identifier="s04",
        sender="Halden Export Services <dispatch@example.invalid>",
        subject="Shipment for order 4417 has been dispatched",
        body=(
            "Order 4417 left our warehouse today.\n"
            "Carrier: Kuehne Nagel. Tracking number KN4471193882.\n"
            "It should arrive on 2026-10-09."
        ),
        kind="delivery",
        fields={
            "order_number": "4417",
            "carrier": "Kuehne Nagel",
            "tracking_number": "KN4471193882",
            "arriving_on": "2026-10-09",
        },
    ),
    Sample(
        identifier="s05",
        sender="Larkspur Provisions <logistics@example.invalid>",
        subject="Delivery update, tracking attached below",
        body=(
            "Your goods for order 5120 are on the way with DHL.\n"
            "Tracking is DHL88210049.\n"
            "Expected arrival: the 30th of February 2026."
        ),
        kind="delivery",
        fields={
            "order_number": "5120",
            "carrier": "DHL",
            "tracking_number": "DHL88210049",
            "arriving_on": "",
        },
        doubtful=True,
    ),
    Sample(
        identifier="s06",
        sender="Atelier Fenwick <studio@example.invalid>",
        subject="Quotation 881 for Pemberton & Clyde Retail",
        body=(
            "Thank you for asking.\n"
            "Quote 881 covers Packing foam sheet at a total of 742.50.\n"
            "The price holds until 2026-10-31."
        ),
        kind="quote",
        fields={
            "quote_number": "881",
            "customer": "Pemberton & Clyde Retail",
            "product": "Packing foam sheet",
            "total": "742.50",
            "valid_until": "2026-10-31",
        },
    ),
    Sample(
        identifier="s07",
        sender="Eastgate Motor Works <parts@example.invalid>",
        subject="Estimate 902",
        body=(
            "Estimate 902 for Costa Verde Importacao Ltda.\n"
            "Warehouse handling fee. Total: three hundred dollars.\n"
            "Valid until 2026-10-20."
        ),
        kind="quote",
        fields={
            "quote_number": "902",
            "customer": "Costa Verde Importacao Ltda",
            "product": "Warehouse handling fee",
            "total": "",
            "valid_until": "2026-10-20",
        },
        doubtful=True,
    ),
    Sample(
        identifier="s08",
        sender="Kowloon Bay Trading Ltd. <hello@example.invalid>",
        subject="Question about our last order",
        body=(
            "Hello,\n\n"
            "This is Aurora Nordic Distribution.\n"
            "We would like to know when order 5120 will be invoiced.\n\n"
            "Thanks."
        ),
        kind="question",
        fields={
            "customer": "Aurora Nordic Distribution",
            "asking_about": "when order 5120 will be invoiced",
            "order_number": "5120",
        },
    ),
    Sample(
        identifier="s09",
        sender="Trade Weekly <news@example.invalid>",
        subject="Your weekly digest, and how to unsubscribe",
        body=(
            "This week in freight: rates, ports and one very large ship.\n"
            "To stop receiving this, use the unsubscribe link."
        ),
        kind="newsletter",
        fields={},
    ),
    Sample(
        identifier="s10",
        sender="Unknown Sender <someone@example.invalid>",
        subject="hello",
        body="Sent from my phone.",
        kind="unknown",
        fields={},
        doubtful=True,
    ),
)


def fill_mailbox(folder: Path) -> List[Sample]:
    """Write every sample into a folder mailbox."""
    for sample in SAMPLES:
        write_message(
            folder=folder,
            identifier=sample.identifier,
            sender=sample.sender,
            subject=sample.subject,
            body=sample.body,
        )
    return list(SAMPLES)


def sample_for(identifier: str) -> Sample:
    """One sample by its name."""
    for sample in SAMPLES:
        if sample.identifier == identifier:
            return sample
    raise KeyError(f"no sample called {identifier!r}")
