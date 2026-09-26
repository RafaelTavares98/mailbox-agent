"""The stand-in model the tests share.

It answers from the generator's own record, so a test compares the
agent against the source rather than against a number typed by hand,
and costs nothing to run.
"""

import json

from sample_messages import SAMPLES


def honest_model(prompt: str) -> str:
    """Answer the way a perfect reader would, from the source record.

    It finds which sample it was handed by the subject line inside the
    prompt, then returns exactly what the generator wrote. Anything it
    does not recognise comes back empty, which is what an honest reader
    does with a message it cannot read.
    """
    for sample in SAMPLES:
        if f"Subject: {sample.subject}" in prompt:
            return json.dumps(sample.fields)
    return "{}"
