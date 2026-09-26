"""Answering the agent, and asking it things.

Nothing here reaches a model or a keyboard. Both are passed in, so the
conversation can be driven by a test exactly as a person drives it.
"""

from pathlib import Path

import pytest

import run_agent
import talking
from learned_rules import DROP, KEEP, read_rules, remember
from mail_reader import LocalMailbox
from sample_messages import fill_mailbox
from tests_support import honest_model


@pytest.fixture
def after_a_run(tmp_path):
    """A run already done, with its two files on disk."""
    folder = tmp_path / "inbox"
    fill_mailbox(folder)
    out = tmp_path / "out"
    run_agent.run(LocalMailbox(folder), out, honest_model,
                  memory=tmp_path / "memory")
    return folder, out, tmp_path / "memory"


def typed(*answers):
    """A person at a keyboard, typing these in order."""
    given = list(answers)

    def read_line(_prompt):
        return given.pop(0) if given else "s"

    return read_line


def test_every_open_question_is_put_to_the_person(after_a_run):
    _, out, memory = after_a_run
    said = []

    talking.walk_questions(out, memory, typed(), said.append)

    asked = [line for line in said if "What should I do" in line]
    assert len(asked) == 4


def test_an_answer_becomes_a_rule(after_a_run):
    _, out, memory = after_a_run

    learned = talking.walk_questions(out, memory, typed("k"), lambda _: None)

    assert learned == 1
    assert read_rules(memory)[0].decision == KEEP


def test_skipping_keeps_nothing(after_a_run):
    _, out, memory = after_a_run

    learned = talking.walk_questions(out, memory, typed("s", "s", "s"),
                                     lambda _: None)

    assert learned == 0
    assert read_rules(memory) == []


def test_a_kept_answer_stops_the_question_coming_back(after_a_run):
    """The whole point. Answer once, and it is settled."""
    folder, out, memory = after_a_run
    before = run_agent.run(LocalMailbox(folder), out, honest_model,
                           memory=memory)
    talking.walk_questions(out, memory, typed("k", "k", "k"),
                           lambda _: None)

    after = run_agent.run(LocalMailbox(folder), out, honest_model,
                          memory=memory)

    assert before.unsure > 0
    assert after.unsure == 0
    assert after.confident > before.confident


def test_a_dropped_answer_takes_the_message_off_the_list(after_a_run):
    folder, out, memory = after_a_run
    before = run_agent.run(LocalMailbox(folder), out, honest_model,
                           memory=memory)
    remember(memory, "order", "these are missing: quantity, total", DROP)

    after = run_agent.run(LocalMailbox(folder), out, honest_model,
                          memory=memory)

    assert len(after.understood) == len(before.understood) - 1


def test_a_rule_does_not_leak_to_another_kind(after_a_run):
    """A ruling about orders says nothing about deliveries."""
    folder, out, memory = after_a_run
    remember(memory, "order", "the arriving on is missing", KEEP)

    after = run_agent.run(LocalMailbox(folder), out, honest_model,
                          memory=memory)
    delivery = [u for u in after.understood if u.message_id == "s05"][0]

    assert delivery.lane == "unsure"


def test_a_rule_can_be_taken_back(after_a_run):
    from learned_rules import forget

    _, out, memory = after_a_run
    remember(memory, "order", "a doubt", KEEP)

    assert forget(memory, "order", "a doubt") is True
    assert read_rules(memory) == []


def test_a_question_is_answered_from_the_rows_only(after_a_run):
    _, out, _ = after_a_run
    seen = {}

    def fake_model(prompt):
        seen["prompt"] = prompt
        return "3480.00"

    said = talking.answer("how much was order 4417?", out, fake_model)

    assert said == "3480.00"
    assert "3480.00" in seen["prompt"]
    assert "answer only from the rows given" in seen["prompt"].lower()


def test_an_empty_table_is_admitted(tmp_path):
    said = talking.answer("anything?", tmp_path, lambda _: "should not run")

    assert "nothing in the table" in said
