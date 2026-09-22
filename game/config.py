"""Tunables, and the few things every other module reaches for."""

import curses
import math
import os


TAU = math.tau
MIN_W, MIN_H = 48, 16
FPS = 60.0

# A handful of moments ring the terminal bell - a boss down, a ship lost, an
# extra ship earned - and no more: a beep per shot would be unbearable.
# --mute silences even those.
SOUND = [True]


def beep():
    if not SOUND[0]:
        return
    try:
        curses.beep()
    except curses.error:
        pass

# Overridable so tests never clobber a real player's save file.
STATE_FILE = os.environ.get(
    "SPACEWAR_STATE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 ".spacewar_state"))


def wrap_delta(x1, y1, x2, y2, world):
    """Shortest vector from one point to another across a wrapping field.

    The field is a torus, so the way to a target is not always the way it
    looks: something just off the left edge is close, not a screen away.
    Every chase, every orbit and every pull in the game goes through here.
    """
    w, h = world
    return ((x2 - x1 + w * 0.5) % w - w * 0.5,
            (y2 - y1 + h * 0.5) % h - h * 0.5)
