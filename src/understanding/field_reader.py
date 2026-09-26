"""Asking the model to turn one message into the fields of its kind.

One call per message. Not one per field, and not a conversation. An agent
left to pick its own steps ran up 124 calls for a job that needed three,
and the client paid for every one of them.

The model is passed in, never imported. That keeps this testable with no
account, and lets the model change without touching the pipeline.
"""

import json
import re
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Dict

from message_kinds import Kind

#: Where the model lives, and which one answers.
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-flash"

#: Where the key is filed. The keychain, never a file and never the
#: environment, which keeps it out of the registry and the shell history.
KEYCHAIN_SERVICE = "deepseek"
KEYCHAIN_ACCOUNT = "api-key"

#: A reply longer than this is the model talking rather than answering.
REPLY_LIMIT = 700

#: How much of a message is sent. A quoted thread can run for pages, and
#: the fields are always near the top.
BODY_LIMIT = 4000

INSTRUCTION = (
    "You read one business email and return its facts as JSON.\n"
    "Return only a JSON object. No explanation, no markdown fence.\n"
    "Use exactly the keys listed. A fact the email does not state is "
    "null. Never guess, never infer, never carry a value over from "
    "another field.\n"
    "Money is digits and a dot, with no currency sign. A date is "
    "YYYY-MM-DD."
)


#: What the queue says when the reading failed twice.
#:
#: The person who opens that queue is a clerk, not a programmer. "no
#: JSON in the reply" tells them nothing they can act on. This tells
#: them what happened and what to do, in their own words.
UNREADABLE = "I could not make sense of this one. Please read it yourself"


class ModelRefused(RuntimeError):
    """The model could not be reached, or would not answer."""


def read_fields(subject: str, body: str, kind: Kind, ask_model) -> Dict:
    """Turn one message into the fields of its kind.

    Every key of the kind is present in the answer. A key the model left
    out comes back empty, so a missing field is a fact the checks can
    see rather than a key that is absent.

    A model that answers with nothing is not an error in the message. It
    is the model having a bad moment, so it is asked once more before
    anyone is troubled about it. Twice, and it goes to a person.
    """
    if not kind.fields:
        return {}
    prompt = build_prompt(subject, body, kind)
    try:
        found = _as_object(ask_model(prompt))
    except ModelRefused:
        found = _as_object(ask_model(prompt))
    return {
        field.name: _as_cell(found.get(field.name), field.type)
        for field in kind.fields
    }


def build_prompt(subject: str, body: str, kind: Kind) -> str:
    """The one thing the model is asked, with its answer shape in it."""
    wanted = "\n".join(
        f"  {field.name}: {field.type}" for field in kind.fields
    )
    return (
        f"{INSTRUCTION}\n\n"
        f"This email is a {kind.name.lower()}.\n"
        f"Keys to return:\n{wanted}\n\n"
        f"Subject: {subject}\n\n"
        f"Body:\n{body[:BODY_LIMIT]}"
    )


def deepseek_reader(prompt: str) -> str:
    """Ask DeepSeek for the fields of a message, as JSON."""
    return _ask_deepseek(prompt, as_json=True)


def deepseek_talker(prompt: str) -> str:
    """Ask DeepSeek a question that wants a sentence, not a record.

    A separate door on purpose. The reader demands JSON, and the service
    refuses the whole request when a prompt asking for prose carries
    that demand. One reader used for both jobs answers neither.
    """
    return _ask_deepseek(prompt, as_json=False)


def build_payload(prompt: str, as_json: bool) -> dict:
    """What is sent for one call.

    The demand for JSON is only added when JSON is wanted. The service
    turns down the whole request when a prompt asking for a sentence
    carries it, and a turned-down request reads nothing at all.
    """
    asked = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": REPLY_LIMIT,
        "temperature": 0,
    }
    if as_json:
        asked["response_format"] = {"type": "json_object"}
    return asked


def _ask_deepseek(prompt: str, as_json: bool) -> str:
    """One call, with the key taken from the keychain."""
    import keyring

    key = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
    if not key:
        raise ModelRefused(
            "No API key in the keychain. Store one under the service "
            f"{KEYCHAIN_SERVICE!r} and the name {KEYCHAIN_ACCOUNT!r}."
        )
    payload = json.dumps(build_payload(prompt, as_json)).encode()
    request = urllib.request.Request(
        DEEPSEEK_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as answer:
            body = json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        raise ModelRefused(
            f"The reading service turned the request down "
            f"({refused.code}). Nothing was read"
        )
    except urllib.error.URLError:
        raise ModelRefused(
            "I could not reach the reading service. Nothing was read"
        )
    return body["choices"][0]["message"]["content"]


def _as_object(answered: str) -> Dict:
    """Read the model's reply, whatever it wrapped the JSON in.

    A model told to return bare JSON usually does, and sometimes puts a
    fence around it anyway. Reading through the fence is cheaper than one
    failed message.
    """
    text = (answered or "").strip()
    fenced = re.search(r"\{.*\}", text, re.DOTALL)
    if not fenced:
        raise ModelRefused(UNREADABLE)
    try:
        found = json.loads(fenced.group(0))
    except json.JSONDecodeError:
        raise ModelRefused(UNREADABLE)
    if not isinstance(found, dict):
        raise ModelRefused(UNREADABLE)
    return found


def _as_cell(value, kind_of_field: str) -> str:
    """One field, in the shape its type calls for.

    Money is written to the cent. A model that read "3480.00" may hand
    back the number 3480.0, and a column where the same amount appears
    two ways is a column nobody can add up.
    """
    text = _as_text(value)
    if kind_of_field != "money" or not text:
        return text
    try:
        return f"{Decimal(text.replace(',', '')):.2f}"
    except InvalidOperation:
        return text


def _as_text(value) -> str:
    """One field, as it will sit in a cell.

    A null and an empty string mean the same thing here: the email did
    not say. Both come back empty, so one check covers both.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return ""
    return str(value).strip()
