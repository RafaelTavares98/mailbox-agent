"""The one command that runs the agent.

    python run.py demo
    python run.py read --out out
    python run.py ask "how much did Costa Verde order?"
    python run.py questions

`demo` fills a folder with invented mail and reads it back, so the whole
thing can be shown without an account anywhere.

`read` does the same against the real mailbox over IMAP, and can also
pick up the failed checks the invoice pipeline left behind.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import run_agent  # noqa: E402
import sheet_writer  # noqa: E402
import talking  # noqa: E402
from invoice_findings import read_findings  # noqa: E402
from mail_reader import ImapMailbox, LocalMailbox  # noqa: E402
from sample_messages import fill_mailbox  # noqa: E402
from table_output import write_questions, write_rows  # noqa: E402
from understanding.field_reader import (  # noqa: E402
    ModelRefused, deepseek_reader, deepseek_talker,
)
from understood import CONFIDENT  # noqa: E402

#: The account is not a secret, so an environment variable is its home.
ACCOUNT = "INVOICE_SMTP_USER"
IMAP_HOST = "imap.gmail.com"

#: Where the answers already given are kept.
MEMORY = "memory"


def main(argv=None) -> int:
    """Read the arguments, do the one thing, print what happened."""
    arguments = build_parser().parse_args(argv)
    if arguments.command == "demo":
        return run_demo(Path(arguments.workdir))
    if arguments.command == "read":
        return read_real(arguments)
    if arguments.command == "ask":
        return ask_one(arguments)
    if arguments.command == "connect-sheet":
        return connect_sheet(arguments)
    return walk_questions(Path(arguments.out))


def connect_sheet(arguments) -> int:
    """Remember where the deployed script lives."""
    sheet_writer.store(arguments.url, arguments.word)
    print("sheet connected. Add --sheet to a read to fill it.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Every way the command can be called."""
    parser = argparse.ArgumentParser(prog="mailbox agent")
    commands = parser.add_subparsers(dest="command", required=True)

    demo = commands.add_parser("demo", help="invent mail and read it back")
    demo.add_argument("--workdir", default="demo")

    real = commands.add_parser("read", help="read the real mailbox")
    real.add_argument("--out", default="out")
    real.add_argument(
        "--invoices", default="",
        help="folder holding the invoice pipeline's findings.csv",
    )
    real.add_argument(
        "--sheet", action="store_true",
        help="also put both tables in the connected Google Sheet",
    )

    connect = commands.add_parser(
        "connect-sheet", help="remember a deployed Apps Script address"
    )
    connect.add_argument("url")
    connect.add_argument("--word", default="change-me")

    question = commands.add_parser("ask", help="ask about the table")
    question.add_argument("question")
    question.add_argument("--out", default="out")

    open_ones = commands.add_parser(
        "questions", help="answer what the agent could not settle"
    )
    open_ones.add_argument("--out", default="out")
    return parser


def run_demo(workdir: Path) -> int:
    """Fill a folder with invented mail, then read it."""
    inbox = workdir / "inbox"
    written = fill_mailbox(inbox)
    print(f"wrote {len(written)} messages into {inbox}")
    report(
        run_agent.run(
            mailbox=LocalMailbox(inbox),
            output=workdir / "out",
            ask_model=deepseek_reader,
            memory=workdir / MEMORY,
        )
    )
    return 0


def read_real(arguments) -> int:
    """Read the real mailbox over IMAP, and the invoice findings too."""
    import keyring

    output = Path(arguments.out)
    account = os.environ.get(ACCOUNT)
    if not account:
        print(f"Set {ACCOUNT} to the mailbox address.")
        return 1
    password = keyring.get_password("invoice-pipeline", account)
    if not password:
        print("No mailbox password in the keychain.")
        return 1
    result = run_agent.run(
        mailbox=ImapMailbox(IMAP_HOST, account, password),
        output=output,
        ask_model=deepseek_reader,
        memory=output / MEMORY,
    )
    if arguments.invoices:
        found = read_findings(Path(arguments.invoices))
        result.understood.extend(found)
        write_rows(result.understood, result.rows_csv)
        write_questions(result.understood, result.questions_csv)
        print(f"picked up {len(found)} invoice checks to ask about")
    if arguments.sheet:
        try:
            written = sheet_writer.send_tables(result.understood)
            print(f"sheet      -> {written}")
        except sheet_writer.SheetRefused as refused:
            print(refused)
    report(result)
    return 0


def ask_one(arguments) -> int:
    """Answer one question about the table.

    A service that will not answer is a sentence, never a stack trace.
    The person asking is not the person who wrote this.
    """
    try:
        print(talking.answer(arguments.question, Path(arguments.out),
                             deepseek_talker))
    except ModelRefused as refused:
        print(refused)
        return 1
    return 0


def walk_questions(output: Path) -> int:
    """Go through the open questions and keep what is decided."""
    learned = talking.walk_questions(
        folder=output,
        memory=output / MEMORY,
        read_line=input,
        say=print,
    )
    print(f"\nlearned {learned} rules. They apply from the next run.")
    return 0


def report(result) -> None:
    """Say what the run did, in the order a reader cares about."""
    print(f"messages seen  {result.seen}")
    print(f"understood     {result.confident}")
    print(f"needs a person {result.unsure}")
    print(f"could not read {result.broken}")
    print(f"nothing to log {result.ignored}")
    print(f"model calls    {result.model_calls}")
    print(f"rows      -> {result.rows_csv}")
    print(f"questions -> {result.questions_csv}")
    for one in result.understood:
        if one.lane != CONFIDENT:
            print(f"  ? {one.question}")


if __name__ == "__main__":
    sys.exit(main())
