"""Command line: python3 -m spacewar, or python3 spacewar."""

import curses
import locale
import os
import sys

from . import config
from .app import run
from .config import SOUND
from .diagnostics import keytest, report_keytest, selftest
from .sectors import SECTORS


def main():
    if "--mute" in sys.argv:
        SOUND[0] = False
    if "--sector" in sys.argv:
        i = sys.argv.index("--sector")
        name = sys.argv[i + 1].lower() if i + 1 < len(sys.argv) else ""
        if name not in SECTORS:
            sys.exit("--sector needs one of: %s" % ", ".join(SECTORS))
        config.START_SECTOR = name
    if "--selftest" in sys.argv:
        selftest()
        return
    locale.setlocale(locale.LC_ALL, "")
    os.environ.setdefault("ESCDELAY", "25")
    if "--keytest" in sys.argv:
        report_keytest(*curses.wrapper(keytest))
        return
    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass
    print("Thanks for playing Space War.")


if __name__ == "__main__":
    main()
