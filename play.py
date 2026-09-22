#!/usr/bin/env python3
"""Launcher, so the game is still one file you can point python at.

The game itself lives in the spacewar package next door; `python3 -m spacewar`
does exactly the same thing. This exists because `python3 <something>.py` is
the command people already have in their fingers.
"""

from spacewar.__main__ import main

if __name__ == "__main__":
    main()
