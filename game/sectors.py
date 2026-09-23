"""Sectors: the rule that changes every tenth wave, and its furniture."""

import math
import random

from .colors import A, bgramp, ramp
from . import config
from .config import TAU, wrap_delta
from .screen import DOTS, PX


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


# The order a cell's dots light up in as it fills: scattered rather than
# top to bottom, so a half-full cell reads as an even grey instead of as a
# solid half-block.
_FILL_ORDER = ((0, 0), (1, 2), (1, 0), (0, 3), (0, 2), (1, 1), (1, 3), (0, 1))
# Four rotations of it, so that neighbouring cells at the same density do
# not light the same dot. With one order the thinnest haze - a single dot a
# cell - came out as a regular lattice of top-left dots, which reads as a
# grid laid over the sky rather than as anything in it.
FILL = []
for _v in range(4):
    _order = _FILL_ORDER[_v * 2:] + _FILL_ORDER[:_v * 2]
    _bits = [0]
    for _fx, _fy in _order:
        _bits.append(_bits[-1] | DOTS[_fx][_fy])
    FILL.append(_bits)


class Nebula:
    """The haze a nebula sector is actually made of.

    Braille is a binary medium - a dot is lit or it is not - so shading has
    to come from how many of a cell's eight dots are lit rather than from
    how bright any one of them is. That is the whole trick: a low-frequency
    noise field sampled once per *cell*, turned into a dot count and a
    colour off the `neb` ramp, with a background wash under the thickest of
    it. The count is capped well short of eight and the colour kept to the
    dark half of the ramp: this is weather to see the fight through, and a
    cloud you cannot see a gunship in is not atmosphere, it is a wall.

    The field is built once, in the field's own cell grid, and then scrolled
    - so a screen full of cloud costs one array lookup per cell per frame
    instead of a noise sample per cell per frame. It is rebuilt only when
    the grid changes size, which means the sector survives a resize without
    anyone having to remember to tell it.
    """

    # (lattice across, lattice down, weight). Two octaves: one that decides
    # where the cloud is, one that gives its edges something to fray on.
    OCTAVES = ((5, 3, 1.0), (11, 7, 0.45))
    FLOOR = 0.58       # below this the sky is simply empty
    MAX = 5            # dots per cell at the thickest: a haze, not a wall
    WASH_FROM = 5      # only the thickest cloud gets a background at all
    DRIFT = 1.1        # units/s: slower than the furthest star

    def __init__(self, seed=None):
        self.seed = random.randrange(1 << 30) if seed is None else seed
        self.cols = self.rows = 0
        self.span = []

    def build(self, cols, rows):
        """Sample the noise once, and keep only the cells that are lit.

        Roughly half the sky comes out empty, and skipping those rows-worth
        of nothing is most of what keeps this affordable.
        """
        rnd = random.Random(self.seed)
        acc = [[0.0] * cols for _ in range(rows)]
        for lx, ly, amp in self.OCTAVES:
            g = [[rnd.random() for _ in range(lx)] for _ in range(ly)]
            for cy in range(rows):
                fy = cy * ly / rows
                y0 = int(fy)
                ty = fy - y0
                ty = ty * ty * (3.0 - 2.0 * ty)          # smoothstep
                r0, r1 = g[y0 % ly], g[(y0 + 1) % ly]
                row = acc[cy]
                for cx in range(cols):
                    fx = cx * lx / cols
                    x0 = int(fx)
                    tx = fx - x0
                    tx = tx * tx * (3.0 - 2.0 * tx)
                    i, j = x0 % lx, (x0 + 1) % lx
                    a = r0[i] + (r0[j] - r0[i]) * tx
                    b = r1[i] + (r1[j] - r1[i]) * tx
                    row[cx] += (a + (b - a) * ty) * amp
        # Stretched to the range it actually came out with, not to the range
        # it could theoretically have had. Smoothed noise averaged over two
        # octaves huddles around the middle and never visits its own
        # extremes, so scaling by the sum of the weights would put the top of
        # the ladder - the thickest, brightest cloud, and the only cloud that
        # earns a background - permanently out of reach.
        lo = min(map(min, acc))
        spread = (max(map(max, acc)) - lo) or 1.0
        self.span = []
        for cy in range(rows):
            lit = []
            for cx, v in enumerate(acc[cy]):
                k = ((v - lo) / spread - self.FLOOR) / (1.0 - self.FLOOR)
                if k > 0.0:
                    n = min(self.MAX, int(k ** 0.75 * (self.MAX + 1)))
                    if n:
                        # Which rotation a cell gets is drawn here, off the
                        # same seeded stream, and then kept: anything derived
                        # from the cell's address comes out as a regular
                        # weave, and anything drawn per frame would boil.
                        lit.append((cx, n, FILL[rnd.getrandbits(2)][n]))
            self.span.append(lit)
        self.cols, self.rows = cols, rows

    def draw(self, f, t):
        cols, rows = f.cols, f.rows
        if (cols, rows) != (self.cols, self.rows):
            self.build(cols, rows)
        # Denser cloud is brighter cloud, and the thickest of it also
        # colours the space between its own dots. Both ladders are worked
        # out once a frame rather than once a cell.
        att = [ramp("neb", 1.0 - 0.5 * i / self.MAX) for i in range(9)]
        wash = [bgramp("neb", 0.6) if i >= self.WASH_FROM else 0
                for i in range(9)]
        off = int(t * self.DRIFT * f.z / PX) % cols
        # Straight at the screen, with the field's own offsets folded in:
        # this is the innermost loop in the renderer, and the wrapping and
        # the unit conversion Field would do are both already done here.
        tile, lay = f.s.tile, f.s.wash
        sx, sy = f.cx0, f.cy0
        for cy in range(rows):
            y = cy + sy
            for cx, n, bits in self.span[cy]:
                x = (cx - off) % cols + sx
                tile(x, y, bits, att[n], 0)
                b = wash[n]
                if b:
                    lay(x, y, b, 0)


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
        # A slow proximity pulse gives the minefield a recognizable warning
        # rhythm without competing with the brighter mine body and horns.
        pulse = 0.5 + 0.5 * math.sin(self.t * 2.2)
        rr = self.R + 2.0 + pulse * 2.2
        f.arc(self.x, self.y, rr, ramp("shock", 0.62), 1,
              step=4.8, a0=self.t * 0.35,
              a1=self.t * 0.35 + TAU * (0.48 + 0.22 * pulse))
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
        self.r = max(5.0, min(10.0, world[1] * 0.11)) * config.SCALE

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
        # A hard bright core, and a corona of loose arcs turning round it,
        # standing in a pool of its own light.
        r = self.r
        f.glow(self.x, self.y, r * 2.6, "glow", 1)
        # Broad, broken orbital tracks distinguish the gravity well from a
        # static star. They sit behind the hot corona and stay deliberately
        # sparse so ships and shots remain easy to follow.
        for i, (rx, ry) in enumerate(((2.9, 1.9), (4.1, 2.6))):
            phase = self.t * (0.10 if i == 0 else -0.07) + i * 1.8
            last = None
            for j in range(33):
                a = phase + j * (TAU * 0.72 / 32.0)
                point = (self.x + r * rx * math.cos(a),
                         self.y + r * ry * math.sin(a))
                if last is not None:
                    f.line(last[0], last[1], point[0], point[1],
                           ramp("star", 0.78), 1)
                last = point
        for k in (1.0, 0.62, 0.3):
            f.arc(self.x, self.y, r * k, A("flash"), 3, step=0.9)
        for i in range(5):
            a0 = self.t * (0.6 + 0.3 * i) + i * 1.3
            a1 = a0 + 1.4 + 0.5 * math.sin(self.t * 1.7 + i * 2.0)
            rr = r * (1.25 + 0.18 * i) + 0.6 * math.sin(self.t * 3.0 + i)
            f.arc(self.x, self.y, rr, ramp("fire", 0.25 + 0.15 * i), 2,
                  step=2.2 + 0.8 * i, a0=a0, a1=a1)
