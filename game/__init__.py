"""SPACE WAR - a terminal space shooter with braille-pixel graphics.

You fly one ship against a hostile fleet: interceptors and gunships every
wave, a Marauder every fifth, a Dreadnought every tenth. Wrecks drop special
magazines. The rocks are still out there, but they are weather now.

Rendering: every character cell carries a 2x4 grid of Unicode braille dots,
so the play field is a real pixel buffer - 8 dots per cell, and because cells
are about twice as tall as they are wide, those dots come out square. Circles
look round, rotation is smooth, and motion is sub-character.

Flight models (toggle with M):
  ARCADE  - press a direction, the ship accelerates that way and turns to face
            it. Snappy, 8-way, forgiving. Default.
  CLASSIC - rotate and thrust, Newtonian drift, no brakes. The 1979 feel.

Run:  python3 -m spacewar     (or: python3 spacewar)

The modules, roughly in dependency order - each one only ever imports from
the ones above it, so there is no cycle to unpick:

    config       tunables, the bell, where the save file lives
    colors       named curses attributes and the ramps that shade them
    screen       the braille pixel buffer and the play field's view of it
    hulls        every ship's silhouette, as polylines
    entities     your ship, rocks, rounds, salvage, particles
    fleet        the hostile ships and how each class behaves
    sectors      the rule that changes every tenth wave
    render       how a Game draws itself
    game         the simulation
    input        held keys, from a terminal that will not say
    app          the frame loop
    diagnostics  --selftest and --keytest
"""

from .colors import A, BGS, PAL, RAMPS, bgramp, init_colors, on, ramp
# config and scale are re-exported as modules, never as values: the size
# dial moves while the game runs, so a `from .config import SCALE` here
# would hand everyone the number the game started with.
from . import config, scale
from .config import (FPS, MIN_H, MIN_W, SOUND, STATE_FILE, TAU, beep,
                     wrap_delta)
from .diagnostics import keytest, report_keytest, selftest
from .entities import (GEAR, GEAR_ODDS, ITEMS, WEAPON_KINDS, WEAPONS,
                       Asteroid, Bullet, Debris, Fireball, Particle, Pickup,
                       Pop, Shock, Ship, Star)
from .fleet import Raider
from .game import Game
from .hulls import draw_hull, flip
from .input import (KEYMAP, KITTY_POP, KITTY_PUSH, KITTY_QUERY, PRESS,
                    RELEASE, REPEAT, Keys, Reader, kitty_probe, tty_write)
from .app import Pacer, default_draw_fps, loop, run
from .render import BAR_EMPTY, BAR_FULL, GameRender
from .screen import BRAILLE, DOTS, PX, PY, Field, Screen
from .sectors import (SECTOR_CYCLE, SECTOR_WAVES, SECTORS, Mine, Nebula,
                      Sun)

__all__ = [
    "A", "Asteroid", "BAR_EMPTY", "BAR_FULL", "BGS", "BRAILLE", "Bullet",
    "DOTS", "Debris", "FPS", "Field", "Fireball", "GEAR", "GEAR_ODDS",
    "Game", "GameRender", "ITEMS", "KEYMAP", "KITTY_POP", "KITTY_PUSH",
    "KITTY_QUERY", "Keys", "MIN_H", "MIN_W", "Mine", "Nebula", "PAL",
    "PRESS", "PX", "PY", "Particle", "Pickup", "Pop", "RAMPS", "RELEASE",
    "REPEAT", "Raider", "Reader", "SECTORS", "SECTOR_CYCLE", "SECTOR_WAVES",
    "SOUND", "STATE_FILE", "Screen", "Shock", "Ship", "Star", "Sun", "TAU",
    "WEAPONS", "WEAPON_KINDS", "beep", "bgramp", "draw_hull", "flip",
    "init_colors", "keytest", "kitty_probe", "loop", "on", "ramp",
    "report_keytest", "Pacer", "default_draw_fps", "run", "selftest", "config", "scale", "tty_write",
    "wrap_delta",
]
