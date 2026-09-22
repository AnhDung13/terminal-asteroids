"""The frame loop: read input, step the sim, draw, sleep the remainder."""

import curses
import time

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


def loop(stdscr, game, keys, reader):
    prev_state = game.state
    now = time.perf_counter()
    last = now
    frame = 1.0 / FPS
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
        game.draw(stdscr)
        stdscr.noutrefresh()
        curses.doupdate()

        slack = frame - (time.perf_counter() - now)
        if slack > 0:
            time.sleep(slack)
