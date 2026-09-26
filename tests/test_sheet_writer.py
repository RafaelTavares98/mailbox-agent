"""Sending the tables to the sheet.

No test here reaches Google. What is tested is what goes on the wire:
the whole table, every run, so a second run cannot double the rows.
"""

import json

import pytest

import sheet_writer
from sheet_writer import QUESTIONS_TAB, ROWS_TAB, SheetRefused, send_tables
from table_output import all_columns
from understood import CONFIDENT, UNSURE, Understood


def understood_pair():
    """One message understood, one still in doubt."""
    sure = Understood(
        message_id="a", sender="s", subject="Order 1", kind="order",
        lane=CONFIDENT, fields={"order_number": "1", "total": "10.00"},
    )
    doubtful = Understood(
        message_id="b", sender="s", subject="Order 2", kind="order",
        lane=UNSURE, reasons=["the total is missing"],
    )
    return [sure, doubtful]


@pytest.fixture
def wire(monkeypatch):
    """Catch what would have been posted, and answer as the sheet."""
    posted = []

    def fake_post(address, word, tab, columns, rows):
        posted.append(
            {"address": address, "word": word, "tab": tab,
             "columns": columns, "rows": rows}
        )
        return len(rows)

    monkeypatch.setattr(
        sheet_writer, "_account", lambda: ("https://x.invalid", "w")
    )
    monkeypatch.setattr(sheet_writer, "_post", fake_post)
    return posted


def test_both_tabs_are_sent(wire):
    send_tables(understood_pair())

    assert [one["tab"] for one in wire] == [ROWS_TAB, QUESTIONS_TAB]


def test_only_the_sure_ones_become_rows(wire):
    written = send_tables(understood_pair())

    assert written[ROWS_TAB] == 1
    assert wire[0]["rows"][0]["order_number"] == "1"


def test_the_doubtful_one_becomes_a_question(wire):
    written = send_tables(understood_pair())

    assert written[QUESTIONS_TAB] == 1
    assert "total is missing" in wire[1]["rows"][0]["question"]


def test_the_whole_table_goes_every_run(wire):
    """The sheet replaces the tab, so a second run cannot double it."""
    send_tables(understood_pair())
    send_tables(understood_pair())

    assert wire[0]["rows"] == wire[2]["rows"]


def test_every_column_is_named_even_when_empty(wire):
    send_tables(understood_pair())

    assert wire[0]["columns"] == all_columns()
    assert "tracking_number" in wire[0]["columns"]


def test_a_sheet_nobody_connected_says_how_to_connect(monkeypatch):
    import keyring

    monkeypatch.setattr(keyring, "get_password", lambda *a: None)

    with pytest.raises(SheetRefused) as refused:
        send_tables(understood_pair())

    assert "keyring set" in str(refused.value)


def test_the_shared_word_travels_with_the_rows(wire):
    """A stranger with the address writes nothing."""
    send_tables(understood_pair())

    assert all(one["word"] == "w" for one in wire)
