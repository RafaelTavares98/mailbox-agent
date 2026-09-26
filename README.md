# The agent that answers for your mailbox

It reads the mail nobody has filed, fills a table with what it
understood, and asks about what it did not.

The last part is the point. Anyone can append a row. The reason to run
this is that you can stop reading the inbox yourself, and you can only
stop if the software admits its own doubt.

## What it does

```
mailbox -> what kind of mail is this? -> pull out the fields
                                              |
        sure  -> a row in the table           |
        unsure -> a question, in plain words  |
        broken -> its own list, never a row
```

1. Reads every message in the mailbox.
2. Leaves the ones with a file attached. Those belong to the invoice
   pipeline; two readers, one mailbox, no collisions.
3. Works out what kind of mail it is from the words in the subject.
4. Asks the model, once, for the fields that kind carries.
5. Checks what came back: is the required field there, is the date a
   real date, is the amount a number.
6. Sends it down one of three lanes.
7. You answer the questions. It keeps each answer as a rule and does not
   ask again.

## Try it without an account

```bash
pip install -r requirements.txt
python run.py demo
```

That writes ten invented messages into a folder and reads them back.

## Read a real mailbox

```bash
python run.py read --out out
```

It connects over IMAP, read only. Nothing in the mailbox is marked,
moved or deleted.

To pick up the failed checks the invoice pipeline left behind:

```bash
python run.py read --out out --invoices ../invoice-pipeline/out
```

## Talk to it

Answer what it could not settle:

```bash
python run.py questions
```

It puts each one to you in a sentence, and you type `k` to keep the row
anyway, `d` to drop that kind of doubt from now on, or `s` to leave it
open. Every `k` and `d` becomes a rule, and the same question is never
asked twice.

Ask it about what it collected:

```bash
python run.py ask "how much did Costa Verde order?"
```

The table is handed to the model as rows, so an answer can only come
from a row that exists.

## Put it in a Google Sheet

No Google Cloud project, no consent screen, no key. The sheet's own half
is a script that lives inside the spreadsheet.

1. Make a spreadsheet.
2. Extensions → Apps Script. Paste `sheet/Codigo.gs`, and change
   `SHARED_WORD` to something only you know.
3. Deploy → New deployment → Web app. Run as yourself, access "Anyone
   with the link". Copy the URL.

```bash
python run.py connect-sheet "<the url>" --word "<your word>"
```

```bash
python run.py read --out out --sheet
```

Both tabs are written from scratch every run. Appending would double
every row on a second pass, and a sheet nobody can trust is worse than
no sheet.

## The five kinds of mail

They live in `src/message_kinds.json`, as data. A sixth kind is a new
entry in that file, never a change to the code.

| Kind | What is pulled out |
| --- | --- |
| Order | number, customer, product, quantity, total, wanted by |
| Delivery notice | order number, carrier, tracking number, arriving on |
| Quote | number, customer, product, total, valid until |
| Customer question | customer, what they are asking, order number |
| Newsletter | nothing. It is recognised so it can be ignored |

## The three lanes

**Sure.** Every required field is there and every value is the shape it
claims to be. The row goes in the table.

**Unsure.** Something is missing or malformed. No row. A question, naming
the problem: "the total is missing", "there is no such day as
2026-02-30".

**Broken.** The kind was not recognised, or the model would not answer
twice in a row. Its own list, and a sentence a clerk can act on rather
than an error code.

A confidence score is never asked of the model. Asking a model how sure
it is returns a figure produced by the same guess it is meant to judge.
Every doubt here is a fact the code checked itself.

## Measured, not estimated

One run against a real Gmail mailbox, over IMAP, with ten invented
business messages sent to it over real SMTP, alongside six unrelated
messages that were already there:

| | |
| --- | --- |
| Messages seen | 24 |
| Understood, every field correct | 6 |
| Asked about, correctly | 3 |
| Left to the invoice pipeline | 8 |
| Ignored as newsletters | 1 |
| Rows invented | 0 |
| Model calls | 9 |

Every field was compared against what the generator wrote. Order
numbers, customers, products, quantities, totals, carrier, tracking
number and dates all matched.

Two faults were found by running it rather than by guessing:

- **The model answered with nothing.** Once, on one message. It is now
  asked a second time before anyone is troubled, and a message that
  fails twice reaches the queue in plain words rather than as "no JSON
  in the reply".
- **Mail written only in HTML came back empty.** A shop or an automated
  system often sends no plain part at all. The words are now taken out
  of the HTML, with the script and style blocks dropped first.

## One call per message

An agent left to choose its own steps runs up the bill. A comparable
project needed 124 tool calls for a job that wanted three, because it
decoded whole message bodies nobody asked for.

Here the code owns the order of the steps, and the model is asked one
thing: turn this text into these fields. A test counts the calls and
fails if the number grows. A newsletter costs nothing, because it never
reaches the model at all.

## Where the secrets live

The mailbox password and the API key sit in the operating system's own
keychain, encrypted and tied to your login. Never in the code, never in
an environment variable, never in the shell history.

```bash
python -m keyring set invoice-pipeline you@example.com
python -m keyring set deepseek api-key
```

## Requirements

Python 3.10 or newer, and the packages in `requirements.txt`.

The model is passed into the pipeline rather than imported by it, so the
whole test suite runs with no key and no account.

## Tests

```bash
python -m pytest
```

51 tests. One uses the real model and skips itself when no key is
stored. Every expected value comes from the generator, which knows what
it wrote, so no number is typed into a test by hand.

## Layout of the code

```
run.py                     the command line
src/
  message_kinds.json       the five kinds, as data
  message_kinds.py         reading that file
  understood.py            what the agent made of one message
  mail_reader.py           a folder of mail, or a real IMAP server
  sample_messages.py       invented mail, and the right answers
  sample_delivery.py       posting that mail to a real address
  learned_rules.py         the answers it was given, kept
  invoice_findings.py      the bridge to the invoice pipeline
  talking.py               the two conversations
  table_output.py          the two tables
  sheet_writer.py          sending them to a Google Sheet
  run_agent.py             the order the steps run in
  understanding/
    classify_kind.py       what kind of mail is this
    field_reader.py        one model call, one message
    checks.py              what is wrong, in plain sentences
sheet/Codigo.gs            the sheet's own half, pasted into Apps Script
tests/
```

## Decisions worth knowing

**The kinds are data.** Someone who knows what a new kind of mail looks
like is rarely someone who can edit Python.

**The earliest word wins.** "Shipment for order 4417" is a delivery
notice, not an order. A reader that took whichever kind it checked first
got that backwards, and silently.

**A message with a file attached is left alone.** The invoice pipeline
takes those, and it must still find them however often this runs.

**The mailbox is read only.** Nothing is marked, moved or deleted.

**A rule is matched on the kind and the doubt, not the sender.** A
ruling about orders says nothing about deliveries, and a test proves it.

**Every rule is a row you can read and delete.** A memory nobody can
read is a memory nobody can correct.
