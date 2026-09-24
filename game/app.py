"""The frame loop: read input, step the sim, draw, sleep the remainder."""

import curses
import os
import time

from . import config
from .colors import init_colors
from .config import FPS, MIN_H, MIN_W
from .game import Game
from .input import (KEYMAP, KITTY_POP, KITTY_PUSH, PRESS, Keys, Reader,
                    kitty_probe, tty_write)


def run(stdscr):
    curses.curs_set(0)
    init_colors()
    stdscr.nodelay(True)
    stdscr.keypad(True)

    h, w = stdscr.getmaxyx()
    if w < MIN_W or h < MIN_H:
        stdscr.nodelay(False)
        stdscr.addstr(0, 0, "Need a terminal of at least %dx%d (this one is "
                            "%dx%d).\nResize, then run again.  "
                            "Press any key." % (MIN_W, MIN_H, w, h))
        stdscr.getch()
        return

    game = Game(w, h)
    keys = Keys()
    reader = Reader(stdscr)
    if kitty_probe(stdscr):
        tty_write(KITTY_PUSH)
        keys.exact = game.exact_keys = True
    try:
        loop(stdscr, game, keys, reader)
    finally:
        tty_write(KITTY_POP)


def cramped_notice(stdscr, w, h):
    """The terminal has been shrunk under the minimum: say so, instead of
    drawing a frame that no longer fits."""
    stdscr.erase()
    for i, line in enumerate(("SPACE WAR", "needs %dx%d" % (MIN_W, MIN_H),
                              "this is %dx%d" % (w, h), "", "paused")):
        if i < h:
            try:
                stdscr.addstr(i, 0, line[:max(0, w - 1)])
            except curses.error:
                pass


# Terminals that fall behind without ever blocking the write. The pacer
# below can only see a draw that takes long; macOS Terminal.app takes the
# bytes at once and then renders them late, braille slowest of all, since
# its default font has no braille glyphs and every cell falls back to
# another face. It gets half rate by default; --fps 60 asks for more.
SLOW_TERMINALS = {"Apple_Terminal": 240.0}


def default_draw_fps(env=os.environ):
    """The draw rate to use when none is asked for: None means adaptive."""
    return SLOW_TERMINALS.get(env.get("TERM_PROGRAM", ""))


class Pacer:
    """Decides which frames get drawn.

    The simulation runs every frame regardless; this only rations the
    drawing. Putting a frame on the terminal is the one cost the game does
    not control - a slow emulator blocks the write, the frame runs long,
    and the next step of the simulation has to cover the lost time in one
    jump, which is what a stutter is. So the cost of each draw is watched,
    and when its running average eats most of the frame budget the game
    draws every other frame instead: the terminal gets twice as long per
    picture, the simulation keeps its 60 steps a second, and the controls
    feel the same. It goes back to every frame once the terminal is idle
    again, with enough gap between the two thresholds not to flap.
    """

    SLOW = 0.70     # of the frame budget: a draw this costly drops to 1/2
    FAST = 0.30     # and one this cheap, on average, goes back to every frame

    def __init__(self, frame, pin=None):
        self.frame = frame
        self.every = max(1, int(round(FPS / pin))) if pin else 1
        self.pinned = pin is not None
        self.cost = 0.0             # running average of one draw's cost
        self.n = 0

    def due(self):
        """Whether this frame is one that gets drawn."""
        return self.n % self.every == 0

    def tick(self, drew, spent):
        """Account for a frame: `drew` says whether it was drawn, `spent`
        is how long the draw took if so."""
        self.n += 1
        if not drew or self.pinned:
            return
        self.cost = spent if self.cost == 0.0 else self.cost * 0.85 + spent * 0.15
        if self.every == 1 and self.cost > self.frame * self.SLOW:
            self.every = 2
        elif self.every == 2 and self.cost < self.frame * self.FAST:
            self.every = 1

    @property
    def fps(self):
        return FPS / self.every


def loop(stdscr, game, keys, reader):
    prev_state = game.state
    now = time.perf_counter()
    last = now
    frame = 1.0 / FPS
    pacer = Pacer(frame, config.DRAW_FPS or default_draw_fps())
    cramped = None          # (w, h) while the terminal is below the minimum
    while True:
        now = time.perf_counter()
        dt = min(now - last, 0.06)
        last = now

        for c, ev in reader.read(now):
            if c == curses.KEY_RESIZE:
                h, w = stdscr.getmaxyx()
                if w >= MIN_W and h >= MIN_H:
                    game.resize(w, h)
                    stdscr.erase()
                    cramped = None
                else:
                    # Too small to play in. Hold the game where it is - a
                    # ship lost to a window you were dragging is not a fair
                    # death - and wait for room.
                    cramped = (w, h)
                    if game.state == "play":
                        game.state = "paused"
                continue
            if c in KEYMAP:
                keys.press(KEYMAP[c], now, ev)
                continue
            # Of anything else only a fresh press counts: a held P must not
            # flicker the pause, and a release is not a press at all.
            if ev != PRESS:
                continue
            # Any other key keeps the current heading alive, so firing,
            # warping or pausing never stalls the ship.
            keys.other(now)
            if c in (ord("q"), ord("Q"), 3):     # 3: ctrl-C, when the
                if game.score > game.high:       # terminal hands it to us
                    game.high = game.score       # as a key, not a signal
                game.save_state()
                return
            elif c in (ord("z"), ord("Z")):
                game.bomb()
            elif c in (ord("-"), ord("_")):
                game.zoom(-1)
            elif c in (ord("="), ord("+")):
                game.zoom(1)
            elif c in (ord("p"), ord("P")):
                if game.state == "play":
                    game.state = "paused"
                elif game.state == "paused":
                    game.state = "play"
            elif c in (ord("m"), ord("M")):
                game.toggle_mode()
            elif c in (ord("."), ord(","), ord("0"), ord("5")):
                keys.brake()
            elif c in (ord("x"), ord("X")):
                if game.state == "play":
                    game.hyperspace()
            elif c in (ord("r"), ord("R")):
                if game.state in ("over", "paused", "title"):
                    game.start_game()
            elif c in (ord(" "), curses.KEY_ENTER, 10, 13):
                if game.state in ("title", "over"):
                    game.start_game()
                elif game.state == "play":
                    game.fire()

        if game.state != prev_state:
            # A new ship starts stationary - when holds are inferred, since
            # what is left over may be stale carry. Exact holds are the truth
            # about the keyboard: if you are still holding Right when the
            # ship comes back, or the pause lifts, it flies right.
            if game.state != "play" and not keys.exact:
                keys.brake()
            prev_state = game.state
        keys.tick(now)
        game.advance(dt, keys)
        drew = cramped or pacer.due()
        t0 = time.perf_counter()
        if cramped:
            cramped_notice(stdscr, *cramped)
        elif drew:
            game.draw_fps = pacer.fps
            game.draw(stdscr)
        if drew:
            stdscr.noutrefresh()
            curses.doupdate()
        pacer.tick(drew, time.perf_counter() - t0)

        slack = frame - (time.perf_counter() - now)
        if slack > 0:
            time.sleep(slack)
