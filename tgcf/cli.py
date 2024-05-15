"""This module implements the command line interface for tgcf."""

import asyncio
import logging
import os
import sys
from enum import Enum
from typing import Optional
import datetime
import typer
from dotenv import load_dotenv
from rich import console, traceback
from rich.logging import RichHandler
from verlat import latest_release
import time
from tgcf import __version__

load_dotenv(".env")

FAKE = bool(os.getenv("FAKE"))
last_execution_date = None
app = typer.Typer(add_completion=False)

con = console.Console()


def topper():
    print("tgcf")
    version_check()
    print("\n")


class Mode(str, Enum):
    """tgcf works in two modes."""

    PAST = "past"
    LIVE = "live"


def verbosity_callback(value: bool):
    """Set logging level."""
    traceback.install()
    if value:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                markup=True,
            )
        ],
    )
    topper()
    logging.info("Verbosity turned on! This is suitable for debugging")


def version_callback(value: bool):
    """Show current version and exit."""

    if value:
        con.print(__version__)
        raise typer.Exit()


def version_check():
    latver = latest_release("tgcf").version
    if __version__ != latver:
        con.print(
            f"tgcf has a newer release {latver} availaible!\
            \nVisit http://bit.ly/update-tgcf",
            style="bold yellow",
        )
    else:
        con.print(f"Running latest tgcf version {__version__}", style="bold green")


def should_run_function_today():
    global last_execution_date

    # Get today's date
    today_date = datetime.date.today()

    # Check if function has already been executed today
    if last_execution_date is None or last_execution_date < today_date:
        return True
    else:
        return False


@app.command()
def main(
        mode: Mode = typer.Argument(
            ..., help="Choose the mode in which you want to run tgcf.", envvar="TGCF_MODE"
        ),
        verbose: Optional[bool] = typer.Option(  # pylint: disable=unused-argument
            None,
            "--loud",
            "-l",
            callback=verbosity_callback,
            envvar="LOUD",
            help="Increase output verbosity.",
        ),
        version: Optional[bool] = typer.Option(  # pylint: disable=unused-argument
            None,
            "--version",
            "-v",
            callback=version_callback,
            help="Show version and exit.",
        ),
):
    """The ultimate tool to automate custom telegram message forwarding.

    Source Code: https://github.com/aahnik/tgcf

    For updates join telegram channel @aahniks_code

    To run web interface run `tgcf-web` command.
    """
    if FAKE:
        logging.critical(f"You are running fake with {mode} mode")
        sys.exit(1)

    if mode == Mode.PAST:
        from tgcf.past import forward_job  # pylint: disable=import-outside-toplevel
        global last_execution_date
        while True:
            if should_run_function_today():
                now = datetime.datetime.now()
                if 9 <= now.hour < 15:  # Check if the current hour is between 9 and 14 (3 PM)
                    logging.info("forward_job started for last one day messages")
                    asyncio.run(forward_job())
                    last_execution_date = datetime.date.today()
            # Sleep for a while before checking again (adjust sleep duration as needed)
            logging.info("sleep for one hour")
            time.sleep(60 * 60)

    else:
        from tgcf.live import start_sync  # pylint: disable=import-outside-toplevel

        asyncio.run(start_sync())

# AAHNIK 2021
