"""The whole chain, from a folder of mail to the two files.

The model is a stand-in that answers from the generator's own record, so
the pipeline can be exercised without an account and without spending
anything. One test at the end uses the real model, and skips itself when
no key is stored.
"""

import csv
from pathlib import Path

import pytest

import run_agent
from mail_reader import LocalMailbox, write_message
from message_kinds import kind_for
from sample_messages import SAMPLES, fill_mailbox, sample_for
from tests_support import honest_model
from understanding.field_reader import (
    KEYCHAIN_ACCOUNT, KEYCHAIN_SERVICE, deepseek_reader,
)
from understood import BROKEN, CONFIDENT, UNSURE


def silent_model(prompt: str) -> str:
    """A model that answers nothing useful."""
    return "{}"


@pytest.fixture
def inbox(tmp_path):
    """A folder holding every invented message."""
    folder = tmp_path / "inbox"
    fill_mailbox(folder)
    return folder, tmp_path / "out"


def read_csv(path: Path):
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_every_message_is_seen(inbox):
    folder, out = inbox

    result = run_agent.run(LocalMailbox(folder), out, honest_model)

    assert result.seen == len(SAMPLES)


def test_the_good_messages_are_understood(inbox):
    folder, out = inbox
    expected = [s for s in SAMPLES if s.fields and not s.doubtful]

    result = run_agent.run(LocalMailbox(folder), out, honest_model)

    assert result.confident == len(expected)


def test_the_broken_messages_raise_a_question(inbox):
    folder, out = inbox
    expected = [s for s in SAMPLES if s.doubtful]

    result = run_agent.run(LocalMailbox(folder), out, honest_model)

    assert result.unsure + result.broken == len(expected)


def test_the_newsletter_is_read_and_dropped(inbox):
    folder, out = inbox

    result = run_agent.run(LocalMailbox(folder), out, honest_model)
    seen = [u.message_id for u in result.understood]

    assert "s09" not in seen
    assert result.ignored == 1


def test_a_message_nobody_recognises_is_not_guessed(inbox):
    folder, out = inbox

    result = run_agent.run(LocalMailbox(folder), out, honest_model)
    stray = [u for u in result.understood if u.message_id == "s10"][0]

    assert stray.lane == BROKEN
    assert stray.kind == "unknown"


def test_the_model_is_asked_once_per_message_at_most(inbox):
    """An agent that picks its own steps runs up the client's bill."""
    folder, out = inbox
    worth_reading = [s for s in SAMPLES if s.fields or s.kind == "order"]

    result = run_agent.run(LocalMailbox(folder), out, honest_model)

    assert result.model_calls <= len(SAMPLES)
    assert result.model_calls == len(worth_reading)


def test_the_newsletter_costs_nothing(inbox):
    """A kind with no fields must never reach the model."""
    folder, out = inbox
    calls = []

    def counting(prompt):
        calls.append(prompt)
        return honest_model(prompt)

    run_agent.run(LocalMailbox(folder), out, counting)

    assert not any("digest" in prompt for prompt in calls)


def test_the_understood_rows_reach_the_table(inbox):
    folder, out = inbox

    result = run_agent.run(LocalMailbox(folder), out, honest_model)
    rows = read_csv(result.rows_csv)

    assert len(rows) == result.confident


def test_every_field_survives_the_round_trip(inbox):
    folder, out = inbox

    result = run_agent.run(LocalMailbox(folder), out, honest_model)

    for one in result.understood:
        if one.lane != CONFIDENT:
            continue
        source = sample_for(one.message_id)
        for name, value in source.fields.items():
            assert one.fields[name] == value


def test_a_question_says_what_is_wrong(inbox):
    folder, out = inbox

    result = run_agent.run(LocalMailbox(folder), out, honest_model)
    rows = read_csv(result.questions_csv)
    asked = {row["message_id"]: row["question"] for row in rows}

    assert "quantity, total" in asked["s03"]


def test_an_impossible_date_is_caught(inbox):
    """The thirtieth of February is not a delivery date."""
    folder, out = inbox

    result = run_agent.run(LocalMailbox(folder), out, honest_model)
    one = [u for u in result.understood if u.message_id == "s05"][0]

    assert one.lane == UNSURE
    assert "arriving on" in " ".join(one.reasons)


def test_an_empty_reply_is_tried_once_more(inbox):
    """A model having a bad moment is not a broken message."""
    tries = {"count": 0}

    def flaky(prompt):
        tries["count"] += 1
        if tries["count"] == 1:
            return ""
        return honest_model(prompt)

    folder, out = inbox

    result = run_agent.run(LocalMailbox(folder), out, flaky)

    assert result.broken == 1
    assert result.model_calls == 9


def test_a_reading_that_fails_twice_speaks_plainly(inbox):
    """The clerk who opens the queue is not a programmer."""
    folder, out = inbox

    def never_answers(prompt):
        return ""

    result = run_agent.run(LocalMailbox(folder), out, never_answers)
    spoken = " ".join(r for u in result.understood for r in u.reasons)

    assert "JSON" not in spoken
    assert "read it yourself" in spoken


def test_a_model_that_says_nothing_never_produces_a_row(inbox):
    """Silence is a question, never an empty row written as fact."""
    folder, out = inbox

    result = run_agent.run(LocalMailbox(folder), out, silent_model)

    assert result.confident == 0
    assert read_csv(result.rows_csv) == []


def test_mail_with_a_file_belongs_to_the_other_reader(tmp_path):
    """The invoice pipeline takes those. Two readers, one mailbox."""
    from email.message import EmailMessage

    folder = tmp_path / "inbox"
    folder.mkdir()
    mail = EmailMessage()
    mail["Subject"] = "Purchase order 9999"
    mail["From"] = "someone@example.invalid"
    mail["Message-ID"] = "<withfile@example.invalid>"
    mail.set_content("Order 9999 attached.")
    mail.add_attachment(
        b"%PDF-1.4", maintype="application", subtype="pdf",
        filename="order.pdf",
    )
    (folder / "withfile.eml").write_bytes(mail.as_bytes())

    result = run_agent.run(
        LocalMailbox(folder), tmp_path / "out", honest_model
    )

    assert result.seen == 1
    assert result.understood == []
    assert result.model_calls == 0


def test_a_second_run_writes_the_same_two_files(inbox):
    folder, out = inbox

    first = run_agent.run(LocalMailbox(folder), out, honest_model)
    first_rows = read_csv(first.rows_csv)
    second = run_agent.run(LocalMailbox(folder), out, honest_model)

    assert read_csv(second.rows_csv) == first_rows


# ------------------------------------------------------- the real model


def has_key() -> bool:
    """Whether an API key is stored on this machine."""
    try:
        import keyring

        return bool(
            keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
        )
    except Exception:
        return False


needs_key = pytest.mark.skipif(not has_key(), reason="no API key stored")


@needs_key
def test_the_real_model_reads_an_order(tmp_path):
    """One call to the paid model, on one message, to prove it reads."""
    from understanding.field_reader import read_fields

    source = sample_for("s01")
    fields = read_fields(
        source.subject, source.body, kind_for("order"), deepseek_reader
    )

    assert fields["order_number"] == source.fields["order_number"]
    assert fields["quantity"] == source.fields["quantity"]
    assert fields["total"] == source.fields["total"]
