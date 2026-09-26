"""What is sent to the model, and what is made of what comes back.

No test here opens a connection.
"""

import pytest

from message_kinds import kind_for
from understanding.field_reader import (
    UNREADABLE, ModelRefused, build_payload, build_prompt, read_fields,
)

ORDER = kind_for("order")


def test_reading_fields_demands_json():
    assert "response_format" in build_payload("anything", as_json=True)


def test_a_question_does_not_demand_json():
    """The service turns the whole request down when it does."""
    assert "response_format" not in build_payload("anything", False)


def test_the_prompt_names_every_field_of_the_kind():
    prompt = build_prompt("Order 1", "body", ORDER)

    for field in ORDER.fields:
        assert field.name in prompt


def test_a_field_the_model_left_out_comes_back_empty():
    fields = read_fields("s", "b", ORDER, lambda _: '{"customer": "Acme"}')

    assert fields["customer"] == "Acme"
    assert fields["total"] == ""


def test_money_is_written_to_the_cent():
    """A column where the same amount appears two ways cannot be added."""
    fields = read_fields("s", "b", ORDER, lambda _: '{"total": 3480.0}')

    assert fields["total"] == "3480.00"


def test_a_reply_wrapped_in_a_fence_is_still_read():
    answered = '```json\n{"customer": "Acme"}\n```'

    assert read_fields("s", "b", ORDER, lambda _: answered)["customer"] == (
        "Acme"
    )


def test_a_null_is_the_same_as_nothing():
    fields = read_fields("s", "b", ORDER, lambda _: '{"customer": null}')

    assert fields["customer"] == ""


def test_a_reply_with_no_json_is_tried_once_more():
    tries = {"n": 0}

    def flaky(_prompt):
        tries["n"] += 1
        return "" if tries["n"] == 1 else '{"customer": "Acme"}'

    assert read_fields("s", "b", ORDER, flaky)["customer"] == "Acme"
    assert tries["n"] == 2


def test_failing_twice_speaks_to_a_person():
    with pytest.raises(ModelRefused) as refused:
        read_fields("s", "b", ORDER, lambda _: "sorry, I cannot")

    assert str(refused.value) == UNREADABLE
    assert "JSON" not in str(refused.value)


def test_a_kind_with_no_fields_never_reaches_the_model():
    def complain(_prompt):
        raise AssertionError("a newsletter must cost nothing")

    assert read_fields("s", "b", kind_for("newsletter"), complain) == {}
