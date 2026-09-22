"""Headless self-test, and a key-repeat probe for diagnosing input.

Neither is part of playing; both are how you find out whether the thing is
still working on a machine you have never seen.
"""

import curses
import os
import random
import time

from . import config
from .config import FPS
from .game import Game
from .input import (KITTY_POP, KITTY_PUSH, PRESS, RELEASE, Keys, Reader,
                    kitty_probe, tty_write)
from .screen import Field
from .sectors import SECTOR_CYCLE

def selftest(frames=2600):
    """Headless run: simulate and render every state without a terminal."""
    # The save file is redirected so a test never clobbers a real score.
    config.STATE_FILE = os.path.join(os.environ.get("TMPDIR", "/tmp"),
                              ".spacewar_selftest_state")
    random.seed(5)
    t0 = time.perf_counter()
    g = Game(110, 34)
    g.start_game()
    keys = Keys()
    draw_ns = 0.0
    seen = set()
    for i in range(frames):
        t = i / FPS
        keys.tick(t)
        for code, names in ((0, ("right",)), (1, ("up",)), (2, ("up", "right")),
                            (3, ("left",)), (4, ("down",))):
            if (i // 23) % 5 == code:
                keys.press(names, t)
        if i % 97 == 0:                 # two arrows in a row -> a diagonal
            keys.press(("up",), t)
            keys.press(("right",), t + 0.01)
        if i % 8 == 0:
            keys.other(t)
        g.advance(1 / FPS, keys)
        if i % 8 == 0:
            g.fire()
        if i % 300 == 299:
            g.hyperspace()
        if i == 500:                    # jump to a mini-boss wave
            g.level = 4
            g.foes = []
            g.queue = []
        if i == 1100:                   # and to a boss wave
            g.level = 9
            g.foes = []
            g.queue = []
        if i in (1300, 1600, 1900, 2200):   # then through every sector
            if g.state != "play":            # whatever state the run is in
                g.state, g.lives = "play", 3
                if g.ship is None:
                    g.spawn_ship()
            g.level = 10 * (1 + (i - 1300) // 300)
            g.sector_order = list(SECTOR_CYCLE)
            g.foes, g.queue = [], []
            g.begin_break()
            g.break_t = 0.02
        seen.add(g.cur)
        if i == 250:
            g.toggle_mode()
        if i == 350 and g.ship:            # gear: a shield, then a bomb
            g.collect("shield")
            g.collect("bomb")
            g.bomb()
        if i == 400:
            g.resize(60, 20)
        if i == 600:                    # the minimum: same field, zoomed
            g.resize(config.MIN_W, config.MIN_H)
            assert g.fit < 1.0
            assert abs(g.world[0] * g.fit - (config.MIN_W - 2) * 2) < 1.0
        if i == 800:
            g.resize(160, 46)
            assert g.fit == 1.0
        d0 = time.perf_counter()
        g.render()
        g.draw_title(g.screen)
        g.draw_over(g.screen)
        g.panel(g.screen, ["PAUSED", "", "P resume"])
        draw_ns += time.perf_counter() - d0
        if g.state == "over":
            g.start_game()
    wall = time.perf_counter() - t0
    print("selftest ok: %d frames in %.2fs (%.1f fps sim+draw, "
          "%.2f ms/frame draw)" % (frames, wall, frames / wall,
                                   1000 * draw_ns / frames))
    print("            score %d  wave %d  objects %d  mode %s"
          % (g.score, g.level, len(g.movers()), g.mode))
    print("            sectors %s" % " ".join(sorted(seen)))
    small = Game(config.MIN_W, config.MIN_H)
    print("            %dx%d plays a %dx%d field at %.0f%% zoom"
          % (config.MIN_W, config.MIN_H, small.world[0], small.world[1],
             small.fit * 100))


def keytest(stdscr):
    """Show what this terminal really sends while a key is held down.

    Every tuning constant in Keys is a bet about the answer, so when the ship
    stutters this is the thing to look at first.
    """
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)
    named = {curses.KEY_LEFT: "LEFT", curses.KEY_RIGHT: "RIGHT",
             curses.KEY_UP: "UP", curses.KEY_DOWN: "DOWN"}
    log, last, prev_gap = [], {}, {}
    delays, periods = [], []
    reader = Reader(stdscr)
    kitty = kitty_probe(stdscr)
    if kitty:
        tty_write(KITTY_PUSH)
    try:
        return keytest_loop(stdscr, reader, kitty, named, log, last,
                            prev_gap, delays, periods)
    finally:
        tty_write(KITTY_POP)


def keytest_loop(stdscr, reader, kitty, named, log, last, prev_gap, delays,
                 periods):
    t0 = time.perf_counter()
    while True:
        now = time.perf_counter()
        for c, ev in reader.read(now):
            if c in (ord("q"), ord("Q")) and ev == PRESS:
                return delays, periods
            name = named.get(c) or (chr(c) if 32 <= c < 127 else "#%d" % c)
            if ev == RELEASE:
                log.append((now - t0, name + " up", None))
                del log[:-400]
                continue
            gap = now - last[name] if name in last else None
            if gap is not None and 0.0 < gap < 0.25:
                periods.append(gap)
                p = prev_gap.get(name)
                if p and gap * 2.0 < p < 2.5:
                    delays.append(p)
            prev_gap[name] = gap
            last[name] = now
            log.append((now - t0, name, gap))
            del log[:-400]

        stdscr.erase()
        h, w = stdscr.getmaxyx()
        rows = [
            "KEY REPEAT TEST",
            "",
            "Hold ONE arrow key down for about three seconds, then let go.",
            "Do that two or three times, then press Q.",
            "",
        ]
        med = sorted(periods)[len(periods) // 2] if periods else None
        dly = sorted(delays)[len(delays) // 2] if delays else None
        rows.append("key releases  %s" % (
            "reported (kitty keyboard protocol) - holds are exact"
            if kitty else "not reported - holds are inferred from repeats"))
        rows.append("events seen   %d" % len(log))
        rows.append("repeat rate   %s" % (
            "%.0f/s  (one every %.0f ms)" % (1.0 / med, med * 1000)
            if med else "no repeat train seen yet"))
        rows.append("delay first   %s" % (
            "%.0f ms" % (dly * 1000) if dly else "-"))
        rows.append("")
        if not periods:
            rows.append("Keep holding. If this stays empty, your terminal is")
            rows.append("not auto-repeating - hold-to-fly cannot work here.")
        elif dly and dly > Keys.FIRST_MAX:
            rows.append("Repeat starts later than the game waits (%.0f ms)."
                        % (Keys.FIRST_MAX * 1000))
            rows.append("Every held key will stutter once at the start.")
        else:
            rows.append("Looks healthy - hold-to-fly should be smooth.")
        rows.append("")
        rows.append("recent events (gap from the one before it)")
        for t, name, gap in log[-min(10, max(0, h - len(rows) - 3)):]:
            rows.append("   %7.3fs  %-6s %s" % (
                t, name, "%6.0f ms" % (gap * 1000) if gap else "     -"))
        rows.append("")
        rows.append("Q to finish")
        for i, s in enumerate(rows[:h - 1]):
            try:
                stdscr.addstr(i, 1, s[:w - 2])
            except curses.error:
                pass
        stdscr.noutrefresh()
        curses.doupdate()
        time.sleep(1.0 / 60.0)


def report_keytest(delays, periods):
    med = sorted(periods)[len(periods) // 2] if periods else None
    dly = sorted(delays)[len(delays) // 2] if delays else None
    print("key repeat: %s, delay %s  (%d periods, %d delays sampled)" % (
        "%.1f/s (%.0f ms)" % (1.0 / med, med * 1000) if med else "NONE SEEN",
        "%.0f ms" % (dly * 1000) if dly else "unknown",
        len(periods), len(delays)))
    if not med:
        print("Your terminal is not auto-repeating held keys. Arcade flight "
              "needs that;\nturn key repeat back on, or the ship will only "
              "dash once per press.")
