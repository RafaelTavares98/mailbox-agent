"""Getting the words out of a mail, whatever shape it arrived in.

A shop or an automated system often sends HTML and nothing else. A
reader that only looked for the plain part would report every one of
those as an empty message, and the agent would ask a person about mail
it could have read perfectly well.
"""

from email.message import EmailMessage

import pytest

from mail_reader import read_message, strip_markup

HTML_ORDER = """
<html><head><style>.x{color:red}</style></head>
<body>
  <script>track('open');</script>
  <h1>Purchase order 4417</h1>
  <p>Customer: Costa Verde Importacao&nbsp;Ltda</p>
  <table>
    <tr><td>Stainless hinge, 40mm</td><td>120</td><td>3480.00</td></tr>
  </table>
  <!-- a comment nobody reads -->
</body></html>
"""


def build(subject: str, plain=None, html=None) -> bytes:
    """One mail, with either part, or both."""
    mail = EmailMessage()
    mail["Subject"] = subject
    mail["From"] = "Someone <someone@example.invalid>"
    mail["Message-ID"] = "<one@example.invalid>"
    if plain is not None:
        mail.set_content(plain)
    if html is not None:
        if plain is None:
            mail.set_content("")
        mail.add_alternative(html, subtype="html")
    return mail.as_bytes()


def test_the_plain_part_is_preferred():
    raw = build("Order", plain="the plain words", html="<p>the html</p>")

    assert "the plain words" in read_message(raw, "x").body


def test_an_html_only_mail_still_gives_words():
    raw = build("Order", html=HTML_ORDER)

    body = read_message(raw, "x").body

    assert "Purchase order 4417" in body
    assert "Costa Verde Importacao Ltda" in body
    assert "3480.00" in body


def test_the_markup_itself_never_reaches_the_model():
    body = read_message(build("Order", html=HTML_ORDER), "x").body

    assert "<" not in body
    assert "color:red" not in body
    assert "track(" not in body


def test_a_comment_is_dropped():
    assert "nobody reads" not in strip_markup(HTML_ORDER)


def test_a_row_of_a_table_stays_on_one_line():
    """A table of order lines must not come back as one sentence."""
    lines = [
        line for line in strip_markup(HTML_ORDER).splitlines() if line
    ]
    row = [line for line in lines if "Stainless hinge" in line]

    assert row
    assert "120" in row[0]
    assert "3480.00" in row[0]


def test_an_escaped_character_comes_back_as_itself():
    assert strip_markup("<p>Pemberton &amp; Clyde</p>") == (
        "Pemberton & Clyde"
    )


def test_an_empty_html_part_is_not_preferred_over_a_plain_one():
    raw = build("Order", plain="the plain words", html="<p></p>")

    assert read_message(raw, "x").body.strip() == "the plain words"


def test_the_sender_is_read_as_a_person_would_see_it():
    assert read_message(build("Order", plain="x"), "y").sender == (
        "Someone <someone@example.invalid>"
    )
