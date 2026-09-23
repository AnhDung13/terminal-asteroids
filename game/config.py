"""Tunables, and the few things every other module reaches for."""

import curses
import math
import os


TAU = math.tau
MIN_W, MIN_H = 40, 12
FPS = 60.0

# The field the game was designed on, in braille dots: a 110x34 terminal. A
# smaller terminal does not get a smaller game - it gets this game seen from
# further away. The simulation runs on a field at least this big, in its own
# units, and the renderer zooms it down by `fit` to the dots it actually has.
# So the standoff a gunship keeps, the reach of a mine, the second it takes a
# round to cross the screen - all of it is the same at 48x16 as at 110x34;
# there are just fewer dots to draw it with. Bigger terminals are not zoomed
# in: they get more field, as they always have.
DESIGN_W, DESIGN_H = 216, 128
FIT_MIN = 0.5           # below this a hull is too few dots to read

# Which sector wave 1 opens in. None is the game as designed: open space,
# then a shuffled tour of the others from wave 11. Set a name - "nebula",
# "debris", "mines" or "star" - to start there instead, with the rest of the
# cycle following; it is how you test a sector without earning it first.
# `--sector NAME` on the command line sets it.
START_SECTOR = None

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

# How big everything on the field is drawn, and is hit. One dial, applied to
# every hull, rock, magazine and mine - the field, the speeds and the standoff
# distances are deliberately left alone, so turning it down does not slow the
# game or spread the fight out: it just gives you more room to fly in and a
# smaller thing to be hit on. This is the player's preference. Fitting the
# game to a small terminal is a different job - see DESIGN_W above - and is
# done by the renderer, not by this number.
#
# Never read this at import time - the player changes it while playing, with
# - and =, so read config.SCALE where you need it and let scale.apply() do
# the rest. Anything that multiplied it into a class attribute once would
# still be holding the size the game started at.
SCALE_DEFAULT = 1.0     # the size the game is designed at
SCALE = SCALE_DEFAULT   # the size it is being played at right now
SCALE_STEPS = (0.5, 0.6, 0.7, 0.85, 1.0, 1.2, 1.4)

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
