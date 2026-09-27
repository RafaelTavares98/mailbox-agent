# The agent that answers for your mailbox

It reads the mail nobody has filed, fills a table with what it
understood, and asks about what it did not.

The last part is the point. Anyone can append a row. You can only stop
reading the inbox if the software admits its own doubt.

## What it does

```
mailbox -> what kind of mail -> pull out the fields -> sure   -> a row
                                                       unsure -> a question
                                                       broken -> its own list
```

The kind comes from the subject. The fields come from one model call. The
lane comes from checks the code runs itself: required field there, date a
real date, amount a number. Mail with a file attached is left to the
invoice pipeline.

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

It connects over IMAP, read only. Nothing is marked, moved or deleted.

To pick up the failed checks the invoice pipeline left behind:

```bash
python run.py read --out out --invoices ../invoice-pipeline/out
```

## Talk to it

Answer what it could not settle:

```bash
python run.py questions
```

Each doubt comes as a sentence. Type `k` to keep the row, `d` to drop that
kind of doubt from now on, or `s` to leave it open. Every `k` and `d`
becomes a rule, asked once.

Ask it about what it collected:

```bash
python run.py ask "how much did Costa Verde order?"
```

The table is handed over as rows, so an answer can only come from a real
row.

## Put it in a Google Sheet

No Google Cloud project, no consent screen, no key. The sheet's own half
is a script that lives inside the spreadsheet.

1. Extensions → Apps Script. Paste `sheet/Codigo.gs`, and change
   `SHARED_WORD` to something only you know.
2. Deploy → New deployment → Web app. Run as yourself, access "Anyone
   with the link". Copy the URL.

```bash
python run.py connect-sheet "<the url>" --word "<your word>"
python run.py read --out out --sheet
```

Both tabs are rewritten every run. Appending would double every row.

## The five kinds of mail

They live in `src/message_kinds.json`, as data. A sixth kind is an entry in
that file, not new code.

| Kind | What is pulled out |
| --- | --- |
| Order | number, customer, product, quantity, total, wanted by |
| Delivery notice | order number, carrier, tracking number, arriving on |
| Quote | number, customer, product, total, valid until |
| Customer question | customer, what they are asking, order number |
| Newsletter | nothing. It is recognised so it can be ignored |

## The three lanes

**Sure.** Every required field is there and the right shape. The row goes
in the table.

**Unsure.** Something is missing or malformed. No row, and a question
naming the problem: "there is no such day as 2026-02-30".

**Broken.** The kind was not recognised, or the model would not answer.
Its own list, in a sentence a clerk can act on.

A confidence score is never asked of the model. That figure is made by the
same guess it is meant to judge. Every doubt here is a fact the code
checked itself.

## Measured, not estimated

One run against a real Gmail mailbox, over IMAP, with ten invented business
messages sent to it over real SMTP:

| | |
| --- | --- |
| Messages seen | 24 |
| Understood, every field correct | 6 |
| Asked about, correctly | 3 |
| Left to the invoice pipeline | 8 |
| Ignored as newsletters | 1 |
| Rows invented | 0 |
| Model calls | 9 |

Every field was compared against what the generator wrote. Numbers,
customers, products, quantities, totals, carrier, tracking and dates all
matched.

Two faults were found by running it rather than by guessing:

- **The model answered with nothing.** It is now asked a second time, and
  a message that fails twice reaches the queue in plain words rather than
  as "no JSON in the reply".
- **Mail written only in HTML came back empty.** Automated senders often
  post no plain part at all. The words are now taken out of the HTML,
  script and style blocks dropped first.

## One call per message

An agent left to choose its own steps runs up the bill. Here the code owns
the order, and the model is asked one thing: turn this text into these
fields. A test counts the calls and fails if the number grows. A newsletter
costs nothing, because it never reaches the model.

## Where the secrets live

The mailbox password and the API key sit in the operating system's own
keychain, tied to your login. Never in the code or the shell history.

```bash
python -m keyring set invoice-pipeline you@example.com
python -m keyring set deepseek api-key
```

## Requirements

Python 3.10 or newer, and the packages in `requirements.txt`. The model is
passed in rather than imported, so the test suite runs with no key.

## Tests

```bash
python -m pytest
```

51 tests. One uses the real model and skips itself when no key is set.

## Layout of the code

```
run.py                     the command line
src/
  message_kinds.json       the five kinds, as data
  mail_reader.py           a folder of mail, or a real IMAP server
  sample_messages.py       invented mail, and the right answers
  learned_rules.py         the answers it was given, kept
  invoice_findings.py      the bridge to the invoice pipeline
  talking.py               the two conversations
  table_output.py          the two tables
  run_agent.py             the order the steps run in
  understanding/           classify, read the fields, check them
sheet/Codigo.gs            the sheet's own half
tests/
```

## Decisions worth knowing

**The kinds are data.** Someone who knows what a new kind of mail looks
like is rarely someone who can edit Python.

**The earliest word wins.** "Shipment for order 4417" is a delivery
notice, not an order. A reader that took whichever kind it checked first
got that backwards, and silently.

**A rule is matched on the kind and the doubt, not the sender.** A ruling
about orders says nothing about deliveries, and a test proves it.

**Every rule is a row you can read and delete.** A memory nobody can read
is a memory nobody can correct.

