"""Sectors: the rule that changes every tenth wave, and its furniture."""

import math
import random

from .colors import A, ramp
from .config import TAU, wrap_delta


# Every SECTOR_WAVES waves - after each dreadnought - the fleet jumps and you
# follow, into a region of space with one rule of its own. The dial that
# ramps the fleet is flat by wave 10; from there the sector is what changes.
# The four rules come in a different order every run.
SECTOR_WAVES = 10
SECTORS = {
    "open": dict(name="OPEN SPACE", note="the fleet, the rocks, and you"),
    "nebula": dict(name="NEBULA", note="short sensor range - blips beyond it"),
    "debris": dict(name="DEBRIS FIELD",
                   note="rocks everywhere, more keep coming"),
    "mines": dict(name="MINEFIELD", note="proximity mines - shoot to set off"),
    "star": dict(name="GRAVITY WELL",
                 note="a star pulls everything in - keep off"),
}
SECTOR_CYCLE = ("nebula", "debris", "mines", "star")


class Mine:
    """A proximity charge adrift in a minefield sector.

    It goes off when any hull comes close - yours or theirs - or when one of
    your shots finds it, and everything inside the blast pays. The fleet's
    rounds pass it by: a minefield that cleared itself would be scenery.
    Shooting one out from under a gunship is the whole idea.
    """

    R = 3.5            # drawn radius; a shot this close sets it off
    TRIG = 11.0        # a hull this close sets it off
    BLAST = 34.0       # everything this close pays
    DMG = 3

    def __init__(self, x, y):
        self.x, self.y = x, y
        a = random.uniform(0, TAU)
        sp = random.uniform(3.0, 9.0)
        self.vx, self.vy = sp * math.cos(a), sp * math.sin(a)
        self.t = random.uniform(0, TAU)

    def update(self, dt, world):
        self.x = (self.x + self.vx * dt) % world[0]
        self.y = (self.y + self.vy * dt) % world[1]
        self.t += dt

    def draw(self, f):
        att = A("mine")
        f.arc(self.x, self.y, self.R, att, 3, step=1.3)
        for i in range(4):                     # four contact horns
            a = i * TAU / 4 + TAU / 8
            f.line(self.x + self.R * math.cos(a), self.y + self.R * math.sin(a),
                   self.x + (self.R + 2.2) * math.cos(a),
                   self.y + (self.R + 2.2) * math.sin(a), att, 3)
        if int(self.t * 2.5) % 2:              # the arming light
            f.dot(self.x, self.y, A("flash"), 4)


class Sun:
    """The star at the heart of a gravity-well sector.

    It pulls on everything that moves - rocks, rounds, salvage, the fleet
    and you - with an inverse-square field capped so that a close pass is
    survivable and a straight line into it is not. Touch it and you are
    gone. Shots bend round it, so a curved shot past the star is on the
    table; so is the fleet's habit of orbiting you straight through it.
    """

    G = 320000.0        # px^3/s^2: 32 px/s^2 of pull at 100 px
    MAX_PULL = 240.0    # px/s^2, close in

    def __init__(self, world):
        self.t = random.uniform(0, TAU)
        self.fit(world)

    def fit(self, world):
        self.x, self.y = world[0] * 0.5, world[1] * 0.5
        self.r = max(5.0, min(10.0, world[1] * 0.11))

    def pull(self, x, y, world):
        """Acceleration toward the star, for something at (x, y)."""
        dx, dy = wrap_delta(x, y, self.x, self.y, world)
        d2 = dx * dx + dy * dy
        if d2 < 1.0:
            return 0.0, 0.0
        d = math.sqrt(d2)
        a = min(self.MAX_PULL, self.G / d2)
        return a * dx / d, a * dy / d

    def inside(self, x, y, world):
        dx, dy = wrap_delta(x, y, self.x, self.y, world)
        return dx * dx + dy * dy < self.r * self.r

    def update(self, dt):
        self.t += dt

    def draw(self, f):
        # A hard bright core, and a corona of loose arcs turning round it.
        r = self.r
        for k in (1.0, 0.62, 0.3):
            f.arc(self.x, self.y, r * k, A("flash"), 3, step=0.9)
        for i in range(5):
            a0 = self.t * (0.6 + 0.3 * i) + i * 1.3
            a1 = a0 + 1.4 + 0.5 * math.sin(self.t * 1.7 + i * 2.0)
            rr = r * (1.25 + 0.18 * i) + 0.6 * math.sin(self.t * 3.0 + i)
            f.arc(self.x, self.y, rr, ramp("fire", 0.25 + 0.15 * i), 2,
                  step=2.2 + 0.8 * i, a0=a0, a1=a1)
