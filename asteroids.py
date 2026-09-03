#!/usr/bin/env python3
"""
ASTEROIDS - a terminal space shooter with braille-pixel graphics.

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

Run:  python3 asteroids.py
"""

import curses
import locale
import math
import os
import random
import sys
import time
from itertools import groupby

TAU = math.tau
MIN_W, MIN_H = 48, 16
FPS = 60.0

# Overridable so tests never clobber a real player's save file.
STATE_FILE = os.environ.get(
    "ASTEROIDS_STATE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 ".asteroids_state"))

# ==========================================================================
# Colour
# ==========================================================================
PAL = {}      # name -> curses attribute
RAMPS = {}    # name -> list of attributes, dark end last
_pairs = {}
_next_pair = [1]
_BG = [-1]


def A(name):
    return PAL.get(name, 0)


def ramp(name, t):
    """Sample a colour ramp; t=0 is the hot/bright end, t=1 the cold end."""
    r = RAMPS.get(name)
    if not r:
        return 0
    i = int(t * (len(r) - 1) + 0.5)
    return r[max(0, min(len(r) - 1, i))]


def _mk(color, bold=False):
    """Allocate (and cache) a colour pair for a foreground colour number."""
    if color not in _pairs:
        i = _next_pair[0]
        attr = 0
        if i < min(curses.COLOR_PAIRS, 250):
            try:
                curses.init_pair(i, color, _BG[0])
                attr = curses.color_pair(i)
                _next_pair[0] = i + 1
            except curses.error:
                attr = 0
        _pairs[color] = attr
    return _pairs[color] | (curses.A_BOLD if bold else 0)


def init_colors():
    curses.start_color()
    try:
        curses.use_default_colors()
        _BG[0] = -1
    except curses.error:
        _BG[0] = curses.COLOR_BLACK
    rich = curses.COLORS >= 256

    if rich:
        PAL["ship"] = _mk(51, True)
        PAL["ship_dim"] = _mk(37)
        PAL["bullet"] = _mk(228, True)
        PAL["ast3"] = _mk(146)
        PAL["ast2"] = _mk(180)
        PAL["ast1"] = _mk(210)
        PAL["flash"] = _mk(231, True)
        PAL["foe1"] = _mk(84, True)      # interceptor
        PAL["foe2"] = _mk(215, True)     # gunship
        PAL["foe3"] = _mk(207, True)     # marauder - mini boss
        PAL["foe4"] = _mk(203, True)     # dreadnought - boss
        PAL["foeshot"] = _mk(120)
        PAL["ui"] = _mk(45)
        PAL["ui_hi"] = _mk(87, True)
        PAL["accent"] = _mk(213, True)
        PAL["warn"] = _mk(215, True)
        PAL["dim"] = _mk(240)
        PAL["frame"] = _mk(238)
        RAMPS["fire"] = [_mk(231, True), _mk(228, True), _mk(221), _mk(214),
                         _mk(208), _mk(202), _mk(160), _mk(124), _mk(52)]
        RAMPS["star"] = [_mk(255, True), _mk(252), _mk(245), _mk(240),
                         _mk(238)]
        RAMPS["title"] = [_mk(87, True), _mk(51, True), _mk(45), _mk(39),
                          _mk(69), _mk(105)]
        RAMPS["shock"] = [_mk(231, True), _mk(159), _mk(45), _mk(69),
                          _mk(61), _mk(238)]
    else:
        W, Y, R, C, M, G = (curses.COLOR_WHITE, curses.COLOR_YELLOW,
                            curses.COLOR_RED, curses.COLOR_CYAN,
                            curses.COLOR_MAGENTA, curses.COLOR_GREEN)
        PAL["ship"] = _mk(C, True)
        PAL["ship_dim"] = _mk(C)
        PAL["bullet"] = _mk(Y, True)
        PAL["ast3"] = _mk(W)
        PAL["ast2"] = _mk(Y)
        PAL["ast1"] = _mk(M, True)
        PAL["flash"] = _mk(W, True)
        PAL["foe1"] = _mk(G, True)
        PAL["foe2"] = _mk(Y, True)
        PAL["foe3"] = _mk(M, True)
        PAL["foe4"] = _mk(R, True)
        PAL["foeshot"] = _mk(G)
        PAL["ui"] = _mk(C)
        PAL["ui_hi"] = _mk(C, True)
        PAL["accent"] = _mk(M, True)
        PAL["warn"] = _mk(Y, True)
        PAL["dim"] = _mk(W) | curses.A_DIM
        PAL["frame"] = _mk(W) | curses.A_DIM
        RAMPS["fire"] = [_mk(W, True), _mk(Y, True), _mk(Y), _mk(R, True),
                         _mk(R), _mk(R) | curses.A_DIM]
        RAMPS["star"] = [_mk(W, True), _mk(W), _mk(W) | curses.A_DIM]
        RAMPS["title"] = [_mk(C, True), _mk(C), _mk(M, True), _mk(M)]
        RAMPS["shock"] = [_mk(W, True), _mk(C, True), _mk(C),
                          _mk(C) | curses.A_DIM]


# ==========================================================================
# Screen: braille pixel layer + text layer, blitted once per frame
# ==========================================================================
# Braille dot bits, indexed [x within cell][y within cell].
DOTS = ((0x01, 0x02, 0x04, 0x40), (0x08, 0x10, 0x20, 0x80))
BRAILLE = [chr(0x2800 + i) for i in range(256)]
PX, PY = 2, 4          # dots per cell


class Screen:
    def __init__(self, w, h):
        self.setsize(w, h)

    def setsize(self, w, h):
        self.w, self.h = w, h
        self.clear()

    def clear(self):
        w, h = self.w, self.h
        self.pat = [bytearray(w) for _ in range(h)]      # braille bits
        self.pattr = [[0] * w for _ in range(h)]         # braille colour
        self.prio = [bytearray(w) for _ in range(h)]     # colour ownership
        self.tch = [[None] * w for _ in range(h)]        # text layer
        self.tattr = [[0] * w for _ in range(h)]

    def dot(self, px, py, attr=0, prio=1):
        cx, cy = px >> 1, py >> 2
        if not (0 <= cx < self.w and 0 <= cy < self.h):
            return
        self.pat[cy][cx] |= DOTS[px & 1][py & 3]
        if prio >= self.prio[cy][cx]:
            self.prio[cy][cx] = prio
            self.pattr[cy][cx] = attr

    def text(self, x, y, s, attr=0):
        y = int(y)
        if not 0 <= y < self.h:
            return
        x = int(x)
        row, arow = self.tch[y], self.tattr[y]
        for c in s:
            if 0 <= x < self.w:
                row[x] = c
                arow[x] = attr
            x += 1

    def ctext(self, y, s, attr=0):
        self.text((self.w - len(s)) // 2, y, s, attr)

    def blit(self, stdscr):
        h, w, last = self.h, self.w, self.h - 1
        for y in range(h):
            pat, pattr = self.pat[y], self.pattr[y]
            tch, tattr = self.tch[y], self.tattr[y]
            cells = []
            for x in range(w):
                c = tch[x]
                if c is not None:
                    cells.append((c, tattr[x]))
                else:
                    p = pat[x]
                    cells.append((BRAILLE[p], pattr[x]) if p else (" ", 0))
            x = 0
            for attr, grp in groupby(cells, key=lambda ca: ca[1]):
                seg = "".join(c for c, _ in grp)
                n = len(seg)
                if y == last and x + n >= w:
                    # Writing the bottom-right cell scrolls the screen, so
                    # insert that one character instead of printing it.
                    tail = seg[-1]
                    seg = seg[:w - x - 1]
                    try:
                        stdscr.insstr(last, w - 1, tail, attr)
                    except curses.error:
                        pass
                if seg:
                    try:
                        stdscr.addstr(y, x, seg, attr)
                    except curses.error:
                        pass
                x += n


class Field:
    """Pixel-space view of the play area. Coordinates wrap at its own edges."""

    def __init__(self, screen, cell_x, cell_y, w, h):
        self.s = screen
        self.x0 = cell_x * PX
        self.y0 = cell_y * PY
        self.cx0, self.cy0 = cell_x, cell_y
        self.w, self.h = w, h

    def dot(self, x, y, attr=0, prio=1):
        self.s.dot(int(x) % self.w + self.x0, int(y) % self.h + self.y0,
                   attr, prio)

    def line(self, x0, y0, x1, y1, attr=0, prio=1):
        x0, y0 = int(round(x0)), int(round(y0))
        x1, y1 = int(round(x1)), int(round(y1))
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.dot(x0, y0, attr, prio)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def poly(self, pts, attr=0, prio=1):
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            self.line(x0, y0, x1, y1, attr, prio)

    def arc(self, cx, cy, r, attr=0, prio=1, step=1.1, a0=0.0, a1=TAU):
        n = max(6, int((a1 - a0) * r / step))
        for i in range(n):
            a = a0 + (a1 - a0) * i / n
            self.dot(cx + r * math.cos(a), cy + r * math.sin(a), attr, prio)

    def ellipse(self, cx, cy, rx, ry, attr=0, prio=1, step=1.0):
        n = max(10, int(TAU * max(rx, ry) / step))
        for i in range(n):
            a = TAU * i / n
            self.dot(cx + rx * math.cos(a), cy + ry * math.sin(a), attr, prio)

    def text(self, x, y, s, attr=0):
        """Place text at a pixel position, snapped to the character grid.

        Clamped rather than wrapped: a score pop split across both edges of
        the screen reads as garbage.
        """
        cols = self.w // PX
        cx = int(x) % self.w // PX - len(s) // 2
        cx = max(0, min(cols - len(s), cx))
        cy = int(y) % self.h // PY
        self.s.text(cx + self.cx0, cy + self.cy0, s, attr)


# ==========================================================================
# Entities  (all positions and speeds are in pixels / pixels-per-second)
# ==========================================================================
# Every hull in the game - yours and theirs - is a list of polylines in local
# coordinates: nose along +x, one unit = the ship's radius. One rotate-and-
# scale draws any of them at any size, so a silhouette is designed as a shape
# rather than written as drawing code.
def flip(poly):
    return [(px, -py) for px, py in poly]


def draw_hull(f, x, y, ang, r, parts, attr, prio=4):
    ca, sa = math.cos(ang) * r, math.sin(ang) * r
    for poly in parts:
        px, py = poly[0]
        ax, ay = x + px * ca - py * sa, y + px * sa + py * ca
        for px, py in poly[1:]:
            bx, by = x + px * ca - py * sa, y + px * sa + py * ca
            f.line(ax, ay, bx, by, attr, prio)
            ax, ay = bx, by


# Your ship: one unbroken chevron - a raked nose, kinked shoulders, wings
# swept back to a deep tail notch. Deliberately unlike anything in the fleet,
# because in a crowded field you must never have to wonder which one is you.
#
# It is one outline and a spine, and that is the whole point. A braille cell
# is 2x4 dots, so at the size a fighter actually gets drawn there is only room
# for a silhouette; the nacelles and canopy frames that read beautifully on a
# capital ship just fill in solid on this one. Capital ships get the detail
# because they are three times the size.
PLAYER = [
    [(1.34, 0.0), (0.10, -0.40), (-0.58, -0.84), (-0.34, -0.30),
     (-0.66, 0.0), (-0.34, 0.30), (-0.58, 0.84), (0.10, 0.40), (1.34, 0.0)],
]
PLAYER_TRIM = [
    [(0.52, 0.0), (0.02, 0.0)],                                   # spine
]
PLAYER_ENG = [(-0.58, 0.0), (-0.44, -0.34), (-0.44, 0.34)]


class Ship:
    RADIUS = 3.0           # forgiving: well inside the drawn hull
    TURN = 4.0             # classic: rad/s
    TURN_RESP = 16.0       # classic: how fast rotation spins up and down
    TURN_STIFF = 600.0     # arcade: nose spring toward the heading you press
    TURN_DAMP = 49.0       # ~2*sqrt(TURN_STIFF): critically damped, no wobble
    TURN_MAX = 14.0
    ACC_CLASSIC = 135.0
    DRAG_CLASSIC = 0.5
    MAX_SPEED = 105.0      # classic keeps the faster, driftier ceiling
    # Arcade is direct control, not thrust: the keys command a velocity and
    # the ship takes ARCADE_RESP seconds to match it. Hold and you go, let go
    # and you stop - no momentum to fight, and nothing to cancel afterwards.
    ARCADE_SPEED = 95.0
    ARCADE_RESP = 0.075
    IN_ATTACK = 24.0       # how fast the smoothed stick follows a press...
    IN_RELEASE = 10.0      # ...and how gently it lets go

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.ang = -TAU / 4          # nose up (pixel y grows downward)
        self.omega = 0.0             # angular velocity, rad/s
        self.ix = self.iy = 0.0      # smoothed stick position
        self.thrust = 0.0            # 0..1 visual throttle
        self.invuln = 2.2
        self.warp_cd = 0.0

    def _ease(self, cur, target, dt):
        """Slew a raw 0/1 key state toward its target - fast on, gentle off."""
        rate = self.IN_ATTACK if abs(target) > abs(cur) else self.IN_RELEASE
        return cur + (target - cur) * min(1.0, rate * dt)

    def _steer(self, dt, want):
        """Critically damped spring on the nose: eases in and out, no wobble."""
        if want is None:
            self.omega -= self.omega * min(1.0, self.TURN_DAMP * dt)
        else:
            d = (want - self.ang + math.pi) % TAU - math.pi
            self.omega += (d * self.TURN_STIFF -
                           self.omega * self.TURN_DAMP) * dt
        self.omega = max(-self.TURN_MAX, min(self.TURN_MAX, self.omega))
        self.ang += self.omega * dt

    # -- arcade: an input vector pushes the ship, nose follows the push ----
    def fly_arcade(self, dt, ix, iy, world):
        n = math.hypot(ix, iy)
        if n > 1.0:                              # clamp, don't normalise: a
            ix, iy = ix / n, iy / n              # carried key still counts
        # Slew straight to the commanded velocity. The only lag is one short
        # time constant, so the ship starts and stops with the key.
        k = 1.0 - math.exp(-dt / self.ARCADE_RESP)
        self.vx += (ix * self.ARCADE_SPEED - self.vx) * k
        self.vy += (iy * self.ARCADE_SPEED - self.vy) * k
        # The gun fires itself, but it does not aim itself: the nose follows
        # the way you are flying, so where you point the ship is where the
        # rounds go. Stop, and the nose holds its last heading and keeps
        # firing along it.
        if n > 0.02:
            self.thrust = min(1.0, self.thrust + dt * 8)
            self._steer(dt, math.atan2(iy, ix))
        else:
            self.thrust = max(0.0, self.thrust - dt * 5)
            self._steer(dt, None)
        self.x = (self.x + self.vx * dt) % world[0]
        self.y = (self.y + self.vy * dt) % world[1]
        self.ang %= TAU
        self.invuln = max(0.0, self.invuln - dt)
        self.warp_cd = max(0.0, self.warp_cd - dt)

    # -- classic: rotate, then burn ---------------------------------------
    def fly_classic(self, dt, turn, fwd, back, world):
        # Rotation spins up and coasts down rather than snapping on and off.
        target = -turn * self.TURN
        self.omega += (target - self.omega) * min(1.0, self.TURN_RESP * dt)
        self.ang += self.omega * dt
        acc = 0.0
        if fwd:
            acc = self.ACC_CLASSIC
        elif back:
            acc = -self.ACC_CLASSIC * 0.45
        if acc:
            self.vx += acc * math.cos(self.ang) * dt
            self.vy += acc * math.sin(self.ang) * dt
            self.thrust = min(1.0, self.thrust + dt * 8)
        else:
            self.thrust = max(0.0, self.thrust - dt * 4)
        self._integrate(dt, self.DRAG_CLASSIC, world, self.MAX_SPEED)

    def _integrate(self, dt, drag, world, cap):
        damp = math.exp(-drag * dt)
        self.vx *= damp
        self.vy *= damp
        sp = math.hypot(self.vx, self.vy)
        if sp > cap:
            # Ease down to the limit instead of clipping hard against it.
            k = 1.0 - (1.0 - cap / sp) * min(1.0, 8.0 * dt)
            self.vx *= k
            self.vy *= k
        self.x = (self.x + self.vx * dt) % world[0]
        self.y = (self.y + self.vy * dt) % world[1]
        self.ang %= TAU
        self.invuln = max(0.0, self.invuln - dt)
        self.warp_cd = max(0.0, self.warp_cd - dt)

    def hull(self):
        """Nose, both wingtips and the tail notch, in pixel coords."""
        a = self.ang
        def p(off, d):
            return (self.x + d * math.cos(a + off),
                    self.y + d * math.sin(a + off))
        return p(0, 7.5), p(2.5, 5.6), p(-2.5, 5.6), p(math.pi, 2.4)

    DRAW_R = 10.0          # drawn size; RADIUS above stays the hit radius

    def draw(self, f):
        if self.invuln > 0 and int(self.invuln * 9) % 2 == 0:
            return
        r = self.DRAW_R
        draw_hull(f, self.x, self.y, self.ang, r, PLAYER, A("ship"), 6)
        draw_hull(f, self.x, self.y, self.ang, r, PLAYER_TRIM,
                  A("ship_dim"), 6)
        if self.thrust <= 0.05:
            return
        # A plume off each nozzle, the middle one longest, all of them
        # flickering and growing with the throttle.
        ca, sa = math.cos(self.ang) * r, math.sin(self.ang) * r
        bx, by = -math.cos(self.ang), -math.sin(self.ang)
        for i, (px, py) in enumerate(PLAYER_ENG):
            ex = self.x + px * ca - py * sa
            ey = self.y + px * sa + py * ca
            ln = (3.0 + 5.0 * self.thrust) * random.uniform(0.7, 1.15)
            if i:
                ln *= 0.6
            f.line(ex, ey, ex + bx * ln, ey + by * ln,
                   ramp("fire", random.uniform(0.0, 0.35) + 0.2 * bool(i)), 5)


class Asteroid:
    # size -> (radius px, base speed px/s, points)
    SPECS = {3: (15.0, 17.0, 20), 2: (9.5, 27.0, 50), 1: (5.5, 39.0, 100)}

    def __init__(self, x, y, size, scale, vx=None, vy=None, spread=0.3):
        self.x, self.y, self.size = x, y, size
        self.r, base, self.points = self.SPECS[size]
        if vx is None:
            sp = base * scale * random.uniform(1.0 - spread * 0.5, 1.0 + spread)
            a = random.uniform(0, TAU)
            vx, vy = sp * math.cos(a), sp * math.sin(a)
        self.vx, self.vy = vx, vy
        self.ang = random.uniform(0, TAU)
        self.spin = random.uniform(-1.5, 1.5)
        self.flash = 0.0
        n = random.randint(10, 13) if size == 3 else random.randint(8, 10)
        self.shape = [(i * TAU / n, self.r * random.uniform(0.74, 1.16))
                      for i in range(n)]
        # A couple of interior craters, for texture on the big ones.
        self.craters = []
        if size >= 2:
            for _ in range(size):
                ca = random.uniform(0, TAU)
                cd = self.r * random.uniform(0.15, 0.45)
                self.craters.append((ca, cd, self.r * random.uniform(.12, .22)))

    def update(self, dt, world):
        self.x = (self.x + self.vx * dt) % world[0]
        self.y = (self.y + self.vy * dt) % world[1]
        self.ang = (self.ang + self.spin * dt) % TAU
        self.flash = max(0.0, self.flash - dt)

    def draw(self, f):
        att = A("flash") if self.flash > 0 else A("ast%d" % self.size)
        pts = [(self.x + d * math.cos(self.ang + a),
                self.y + d * math.sin(self.ang + a))
               for a, d in self.shape]
        f.poly(pts, att, 3)
        for ca, cd, cr in self.craters:
            a = self.ang + ca
            f.arc(self.x + cd * math.cos(a), self.y + cd * math.sin(a),
                  cr, att, 3, step=1.4)


class Bullet:
    def __init__(self, x, y, vx, vy, life, hostile=False, dmg=1, kind=None,
                 col=None):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = life
        self.hostile = hostile
        self.dmg = dmg
        self.kind = kind
        self.col = col
        # A lance keeps going through a hull, so it has to remember what it
        # has already gone through or it would chew one ship to pieces.
        self.spent = set() if kind == "pierce" else None

    SPEED = 190.0

    @staticmethod
    def reach(world, speed=None):
        """Time to cross the field corner to corner, plus a margin.

        Bullets are killed by the edge of the field, never by a stopwatch, so
        the range you get is the same fraction of the window at any size.
        """
        return math.hypot(*world) / (speed or Bullet.SPEED) * 1.2

    def update(self, dt, world):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        # Bullets do not wrap - they burn out on the edge of the field.
        if not (0.0 <= self.x < world[0] and 0.0 <= self.y < world[1]):
            self.life = 0.0

    def draw(self, f):
        att = A(self.col) if self.col else (A("foeshot") if self.hostile
                                            else A("bullet"))
        # A tracer streak from where it was to where it is - a lone dot moving
        # four pixels a frame is nearly impossible to follow.
        step = 0.016
        f.line(self.x - self.vx * step, self.y - self.vy * step,
               self.x, self.y, att, 5)
        if self.dmg > 1:            # a gauss slug reads as a heavier bolt
            f.line(self.x - self.vx * step * 2.2,
                   self.y - self.vy * step * 2.2,
                   self.x - self.vx * step, self.y - self.vy * step, att, 5)
        for i in (2, 3, 4):
            f.dot(self.x - self.vx * step * i, self.y - self.vy * step * i,
                  att if (self.hostile or self.col)
                  else ramp("fire", 0.2 + 0.2 * i), 4)


# Salvaged from a wrecked hull: a magazine of something better than the
# ship's own gun. One at a time, and it runs out.
WEAPONS = {
    "spread": dict(tag="S", name="SPREAD", col="foe2", ammo=55, cd=0.17,
                   note="a fan of three"),
    "rapid": dict(tag="R", name="RAPID", col="foe1", ammo=150, cd=0.052,
                  note="three times the cadence"),
    "pierce": dict(tag="P", name="LANCE", col="ui_hi", ammo=60, cd=0.14,
                   note="passes through hulls"),
    "homing": dict(tag="H", name="SEEKER", col="foe3", ammo=55, cd=0.20,
                   note="curves onto its target"),
    "gauss": dict(tag="G", name="GAUSS", col="foe4", ammo=26, cd=0.30,
                  note="three hull points a slug"),
}
WEAPON_KINDS = ("spread", "rapid", "pierce", "homing", "gauss")


class Pickup:
    """A dropped magazine, tumbling where its ship came apart."""

    R = 7.0
    LIFE = 15.0

    def __init__(self, x, y, kind):
        self.x, self.y, self.kind = x, y, kind
        a = random.uniform(0, TAU)
        sp = random.uniform(8.0, 22.0)
        self.vx, self.vy = sp * math.cos(a), sp * math.sin(a)
        self.life = self.LIFE
        self.t = random.uniform(0, TAU)

    def update(self, dt, world):
        self.x = (self.x + self.vx * dt) % world[0]
        self.y = (self.y + self.vy * dt) % world[1]
        k = 0.985 ** (dt * 60)
        self.vx *= k
        self.vy *= k
        self.t += dt
        self.life -= dt

    def draw(self, f):
        if self.life < 4.0 and int(self.life * 7) % 2 == 0:
            return
        spec = WEAPONS[self.kind]
        att = A(spec["col"])
        r = self.R * (1.0 + 0.10 * math.sin(self.t * 4.0))
        pts = [(self.x + r * math.cos(self.t * 1.5 + i * TAU / 6),
                self.y + r * math.sin(self.t * 1.5 + i * TAU / 6))
               for i in range(6)]
        f.poly(pts, att, 5)
        f.text(self.x, self.y, spec["tag"], att)


class Particle:
    def __init__(self, x, y, vx, vy, life, drag=0.9):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.life0 = life
        self.drag = drag

    def update(self, dt, world):
        self.x = (self.x + self.vx * dt) % world[0]
        self.y = (self.y + self.vy * dt) % world[1]
        k = self.drag ** (dt * 60)
        self.vx *= k
        self.vy *= k
        self.life -= dt

    def draw(self, f):
        f.dot(self.x, self.y, ramp("fire", 1.0 - self.life / self.life0), 1)


class Shock:
    """Expanding ring - the punch behind every explosion."""

    def __init__(self, x, y, r0, r1, life, name="shock"):
        self.x, self.y = x, y
        self.r0, self.r1 = r0, r1
        self.life = self.life0 = life
        self.name = name

    def update(self, dt, world):
        self.life -= dt

    def draw(self, f):
        t = 1.0 - self.life / self.life0
        r = self.r0 + (self.r1 - self.r0) * (1.0 - (1.0 - t) ** 2)
        f.arc(self.x, self.y, r, ramp(self.name, t), 2,
              step=1.0 + 1.6 * t)


class Debris:
    """A tumbling line fragment - the ship coming apart."""

    def __init__(self, x, y, vx, vy, length, life):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.len = length
        self.ang = random.uniform(0, TAU)
        self.spin = random.uniform(-4.0, 4.0)
        self.life = self.life0 = life

    def update(self, dt, world):
        self.x = (self.x + self.vx * dt) % world[0]
        self.y = (self.y + self.vy * dt) % world[1]
        self.ang += self.spin * dt
        self.life -= dt

    def draw(self, f):
        t = 1.0 - self.life / self.life0
        dx = self.len * 0.5 * math.cos(self.ang)
        dy = self.len * 0.5 * math.sin(self.ang)
        f.line(self.x - dx, self.y - dy, self.x + dx, self.y + dy,
               ramp("shock", 0.15 + 0.85 * t), 4)


class Pop:
    """Floating score text."""

    def __init__(self, x, y, text, attr):
        self.x, self.y = x, y
        self.text, self.attr = text, attr
        self.life = 0.9

    def update(self, dt, world):
        self.y -= 16.0 * dt
        self.life -= dt

    def draw(self, f):
        if self.life > 0.25 or int(self.life * 14) % 2 == 0:
            f.text(self.x, self.y, self.text, self.attr)


class Star:
    def __init__(self, world):
        self.x = random.uniform(0, world[0])
        self.y = random.uniform(0, world[1])
        self.depth = random.random() ** 1.6      # 0 = near, 1 = far
        self.rate = random.uniform(0.6, 2.4)
        self.ph = random.uniform(0, TAU)

    def update(self, dt, world, ship):
        near = 1.0 - self.depth
        self.x -= (2.0 + 7.0 * near) * dt
        if ship is not None:
            self.x -= ship.vx * dt * 0.05 * near
            self.y -= ship.vy * dt * 0.05 * near
        self.x %= world[0]
        self.y %= world[1]
        self.ph += self.rate * dt

    def draw(self, f):
        tw = 0.5 + 0.5 * math.sin(self.ph)
        f.dot(self.x, self.y,
              ramp("star", 0.25 + 0.7 * self.depth - 0.22 * tw), 0)


# --------------------------------------------------------------------------
# Hostile ships.
#
# Every hull is a list of polylines in local coordinates - nose along +x, one
# unit = the ship's radius - so a single rotate-and-scale draws any of them at
# any size, and a silhouette can be designed as a shape rather than as code.
# --------------------------------------------------------------------------
# Interceptor: a lean dart with closed swept strakes and a tail notch.
_SC_W = [(0.24, -0.19), (-0.32, -0.90), (-0.72, -0.66), (-0.44, -0.15),
         (0.24, -0.19)]
SCOUT = [
    [(1.22, 0.0), (0.32, -0.25), (-0.66, -0.17), (-0.56, 0.0),
     (-0.66, 0.17), (0.32, 0.25), (1.22, 0.0)],
    _SC_W, flip(_SC_W),
]
SCOUT_ENG = [(-0.60, -0.11), (-0.60, 0.11)]

# Gunship: broad shoulders, two stubby outboard nacelles on short pylons.
_GS_N = [(0.30, -0.88), (-0.50, -0.88), (-0.64, -0.62), (0.16, -0.62),
         (0.30, -0.88)]
_GS_S = [(0.14, -0.32), (0.22, -0.66)]
GUNSHIP = [
    [(1.12, 0.0), (0.48, -0.30), (-0.58, -0.38), (-0.84, -0.16),
     (-0.84, 0.16), (-0.58, 0.38), (0.48, 0.30), (1.12, 0.0)],
    _GS_N, flip(_GS_N), _GS_S, flip(_GS_S),
    [(0.64, -0.12), (0.28, -0.12), (0.28, 0.12), (0.64, 0.12)],
]
GUNSHIP_ENG = [(-0.82, -0.10), (-0.82, 0.10), (-0.62, -0.75), (-0.62, 0.75)]

# Marauder: the mini-boss - a raked prow and heavy delta wings.
_MR_W = [(0.34, -0.32), (0.06, -1.08), (-0.68, -1.24), (-0.98, -0.72),
         (-0.62, -0.36)]
_MR_P = [(-0.16, -0.80), (0.06, -0.80)]
MARAUDER = [
    [(1.30, 0.0), (0.78, -0.20), (0.36, -0.36), (-0.72, -0.42),
     (-1.02, -0.22), (-1.02, 0.22), (-0.72, 0.42), (0.36, 0.36),
     (0.78, 0.20), (1.30, 0.0)],
    _MR_W, flip(_MR_W), _MR_P, flip(_MR_P),
    [(0.64, 0.0), (-0.34, 0.0)],
    [(0.12, -0.36), (0.12, 0.36)],
    [(-0.46, -0.36), (-0.46, 0.36)],
]
MARAUDER_ENG = [(-1.00, -0.13), (-1.00, 0.13), (-0.94, -0.92), (-0.94, 0.92)]

# Dreadnought: the wave-ten capital ship. Spinal gun, flanking pods.
_DR_W = [(0.48, -0.42), (0.22, -1.18), (-0.56, -1.38), (-1.06, -1.06),
         (-1.12, -0.56), (-0.76, -0.46)]
_DR_P = [(-0.32, -1.02), (0.02, -1.02), (0.08, -0.80), (-0.36, -0.80),
         (-0.32, -1.02)]
DREADNOUGHT = [
    [(1.50, 0.0), (1.02, -0.22), (0.56, -0.46), (-0.62, -0.54),
     (-1.18, -0.32), (-1.28, 0.0), (-1.18, 0.32), (-0.62, 0.54),
     (0.56, 0.46), (1.02, 0.22), (1.50, 0.0)],
    _DR_W, flip(_DR_W), _DR_P, flip(_DR_P),
    [(0.90, 0.0), (-0.58, 0.0)],
    [(0.32, -0.48), (0.32, 0.48)],
    [(-0.26, -0.52), (-0.26, 0.52)],
    [(-0.82, -0.42), (-0.82, 0.42)],
]
DREADNOUGHT_ENG = [(-1.26, -0.16), (-1.26, 0.16), (-1.08, -0.90),
                   (-1.08, 0.90)]


class Raider:
    """A hostile ship: four classes, one flight brain, four silhouettes.

    They fly to a standoff distance and circle it rather than drifting across
    the screen, so the fight happens around you instead of past you.
    """

    SPECS = {
        "scout": dict(r=8.5, hp=1, speed=64.0, cd=1.9, shots=1, jitter=0.26,
                      bsp=78.0, value=150, shape=SCOUT, eng=SCOUT_ENG,
                      keep=46.0, col="foe1", turn=5.0),
        "gunship": dict(r=12.0, hp=2, speed=46.0, cd=1.7, shots=2, jitter=0.16,
                        bsp=88.0, value=400, shape=GUNSHIP, eng=GUNSHIP_ENG,
                        keep=86.0, col="foe2", turn=3.4),
        "marauder": dict(r=15.0, hp=11, speed=32.0, cd=1.35, shots=4,
                         jitter=0.13, bsp=80.0, value=2500, shape=MARAUDER,
                         eng=MARAUDER_ENG, keep=104.0, col="foe3",
                         turn=2.4),
        "dread": dict(r=24.0, hp=28, speed=23.0, cd=1.15, shots=7, jitter=0.10,
                      bsp=74.0, value=12000, shape=DREADNOUGHT,
                      eng=DREADNOUGHT_ENG, keep=134.0, col="foe4",
                      turn=1.7),
    }
    BOSSES = ("marauder", "dread")

    def __init__(self, kind, x, y, diff, world=None):
        s = self.SPECS[kind]
        self.kind = kind
        # A capital ship has to fit the field it is fighting in: at the 48x16
        # minimum a full-size dreadnought would be most of the screen.
        self.r = s["r"]
        if world is not None:
            self.r = min(self.r, world[0] * 0.115, world[1] * 0.20)
        self.hp = self.hp0 = s["hp"]
        self.speed = s["speed"] * (0.82 + 0.34 * diff)
        self.cd0 = s["cd"] * (1.30 - 0.50 * diff)
        self.shots = s["shots"]
        self.jitter = s["jitter"] * (1.35 - 0.75 * diff)
        self.bsp = s["bsp"] * (0.85 + 0.35 * diff)
        self.value = s["value"]
        self.shape = s["shape"]
        self.eng = s["eng"]
        self.keep = s["keep"]
        self.col = s["col"]
        self.turn = s["turn"]
        self.boss = kind in self.BOSSES
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.ang = random.uniform(0, TAU)
        self.cd = self.cd0 * random.uniform(0.6, 1.4)
        self.orbit = random.choice((-1.0, 1.0))
        self.t = random.uniform(0, TAU)
        self.flash = 0.0
        self.arrive = 0.7          # brief fade-in so they do not pop in

    @staticmethod
    def toward(x1, y1, x2, y2, world):
        """Shortest vector to a point across a wrapping field."""
        w, h = world
        return ((x2 - x1 + w * 0.5) % w - w * 0.5,
                (y2 - y1 + h * 0.5) % h - h * 0.5)

    def update(self, dt, world, ship, bullets):
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        self.arrive = max(0.0, self.arrive - dt)
        if ship is not None:
            dx, dy = self.toward(self.x, self.y, ship.x, ship.y, world)
            d = math.hypot(dx, dy) or 1.0
            ux, uy = dx / d, dy / d
            # Close on the standoff ring, then circle it. Weaving keeps the
            # orbit from reading as a perfect, lifeless circle.
            radial = max(-1.0, min(1.0, (d - self.keep) / 46.0))
            tang = self.orbit * (1.0 - abs(radial))
            tang += 0.25 * math.sin(self.t * 1.7 + self.orbit)
            wx, wy = ux * radial - uy * tang, uy * radial + ux * tang
            n = math.hypot(wx, wy) or 1.0
            wx, wy = wx / n, wy / n
            want = math.atan2(dy, dx)
        else:
            wx, wy = math.cos(self.ang), math.sin(self.ang)
            want, d = self.ang, 1e9
        k = min(1.0, 2.4 * dt)
        self.vx += (wx * self.speed - self.vx) * k
        self.vy += (wy * self.speed - self.vy) * k
        self.x = (self.x + self.vx * dt) % world[0]
        self.y = (self.y + self.vy * dt) % world[1]
        da = (want - self.ang + math.pi) % TAU - math.pi
        self.ang = (self.ang + da * min(1.0, self.turn * dt)) % TAU

        self.cd -= dt
        if self.cd <= 0 and ship is not None and self.arrive <= 0:
            self.cd = self.cd0 * random.uniform(0.85, 1.25)
            self.volley(bullets, world, math.atan2(dy, dx))
        return True

    def volley(self, bullets, world, base):
        n = self.shots
        step = 0.17 if not self.boss else 0.15
        muzzle = self.r * (1.05 if self.boss else 0.9)
        for i in range(n):
            a = base + (i - (n - 1) * 0.5) * step
            a += random.uniform(-self.jitter, self.jitter)
            bullets.append(Bullet(
                (self.x + muzzle * math.cos(self.ang)) % world[0],
                (self.y + muzzle * math.sin(self.ang)) % world[1],
                self.bsp * math.cos(a), self.bsp * math.sin(a),
                Bullet.reach(world, self.bsp), hostile=True))

    def hit(self, dmg=1):
        self.hp -= dmg
        self.flash = 0.09
        return self.hp <= 0

    def draw(self, f):
        if self.arrive > 0 and int(self.arrive * 14) % 2 == 0:
            return
        att = A("flash") if self.flash > 0 else A(self.col)
        draw_hull(f, self.x, self.y, self.ang, self.r, self.shape, att, 4)
        # Engine bloom: a short flare trailing each nozzle, flickering.
        ca, sa = math.cos(self.ang) * self.r, math.sin(self.ang) * self.r
        bx, by = -math.cos(self.ang), -math.sin(self.ang)
        for px, py in self.eng:
            ex = self.x + px * ca - py * sa
            ey = self.y + px * sa + py * ca
            ln = self.r * random.uniform(0.12, 0.30)
            f.line(ex, ey, ex + bx * ln, ey + by * ln,
                   ramp("fire", random.uniform(0.15, 0.55)), 4)
        if self.boss:      # a slow sweeping sensor blip along the spine
            ph = 0.5 + 0.5 * math.sin(self.t * 2.2)
            f.dot(self.x + (0.55 * ph + 0.1) * ca,
                  self.y + (0.55 * ph + 0.1) * sa, A("flash"), 5)


# ==========================================================================
# Game
# ==========================================================================
BAR_FULL, BAR_EMPTY = "▰", "▱"


class Game:
    def __init__(self, w, h, mode="arcade"):
        self.screen = Screen(w, h)
        self.mode = mode
        self.layout(w, h)
        self.high, saved_mode = self.load_state()
        if saved_mode in ("arcade", "classic"):
            self.mode = saved_mode
        self.state = "title"
        self.msg = ""
        self.msg_t = self.msg_t0 = 0.0
        self.timer = 0.0
        self.shake = 0.0
        self.sweep = 0.0
        self.demo_fire = 0.0
        self.reset(full=True)
        self.stars = [Star(self.world) for _ in range(self.star_count())]
        self.spawn_wave()
        self.ship = Ship(self.world[0] * 0.3, self.world[1] * 0.6)
        self.ship.invuln = 0.0

    # -- geometry ---------------------------------------------------------
    def layout(self, w, h):
        self.sw, self.sh = w, h
        self.cell_x, self.cell_y = 1, 1
        self.world = ((w - 2) * PX, (h - 2) * PY)

    def star_count(self):
        return max(24, int(self.world[0] * self.world[1] / 900))

    def resize(self, w, h):
        old = self.world
        self.screen.setsize(w, h)
        self.layout(w, h)
        fx = self.world[0] / max(1, old[0])
        fy = self.world[1] / max(1, old[1])
        for o in self.movers():
            o.x = (o.x * fx) % self.world[0]
            o.y = (o.y * fy) % self.world[1]
        self.stars = [Star(self.world) for _ in range(self.star_count())]

    def movers(self):
        objs = (self.asteroids + self.bullets + self.particles +
                self.shocks + self.debris + self.pops + self.foes +
                self.pickups)
        if self.ship:
            objs.append(self.ship)
        return objs

    # -- difficulty -------------------------------------------------------
    # One dial drives everything: 0.0 on wave 1, 1.0 from wave 10 on. Wave 1
    # is a slow drift you can pick apart; wave 10+ is the old wave-1 pace and
    # then some.
    RAMP_WAVES = 9.0

    def diff(self):
        # Eased rather than linear: the first few waves stay close together
        # and the pressure back-loads onto the later ones.
        t = max(0.0, min(1.0, (self.level - 1) / self.RAMP_WAVES))
        return t ** 1.6

    @staticmethod
    def lerp(a, b, t):
        return a + (b - a) * t

    def rock_scale(self):
        return self.lerp(0.60, 1.80, self.diff())

    def rock_count(self):
        # Rocks are scenery now - something to dodge while you fight, not the
        # objective. A handful, and never a field to grind through.
        return min(2 + self.level // 3, 6)

    MAX_FOES = 7            # on screen at once, boss excepted

    def is_boss_wave(self):
        return self.level % 10 == 0

    def is_mini_wave(self):
        return self.level % 5 == 0 and not self.is_boss_wave()

    def roster(self):
        """The ships that will arrive this wave, in the order they arrive."""
        lv = self.level
        if self.is_boss_wave():
            out = ["dread"] + ["gunship"] * 3 + ["scout"] * 4
        elif self.is_mini_wave():
            out = ["marauder"] + ["gunship"] * 2 + ["scout"] * 4
        else:
            scouts = min(3 + lv // 2, 10)
            guns = min(lv // 3, 5)
            out = ["scout"] * scouts + ["gunship"] * guns
            random.shuffle(out)
            return out
        rest = out[1:]
        random.shuffle(rest)
        return out[:1] + rest      # the capital ship leads

    def home(self, b, dt):
        """Curve a seeker onto the nearest hull it can still reach."""
        best, bd = None, 190.0
        for foe in self.foes:
            if foe.arrive > 0:
                continue
            d = self.wrap_dist(b.x, b.y, foe.x, foe.y)
            if d < bd:
                bd, best = d, foe
        if best is None:
            return
        dx, dy = Raider.toward(b.x, b.y, best.x, best.y, self.world)
        cur = math.atan2(b.vy, b.vx)
        da = (math.atan2(dy, dx) - cur + math.pi) % TAU - math.pi
        cur += max(-7.0 * dt, min(7.0 * dt, da))
        sp = math.hypot(b.vx, b.vy)
        b.vx, b.vy = sp * math.cos(cur), sp * math.sin(cur)

    def wrap_dist(self, x1, y1, x2, y2):
        w, h = self.world
        dx = abs(x1 - x2)
        dy = abs(y1 - y2)
        return math.hypot(min(dx, w - dx), min(dy, h - dy))

    # -- persistence ------------------------------------------------------
    def load_state(self):
        try:
            with open(STATE_FILE) as fh:
                parts = fh.read().split()
            return int(parts[0]), (parts[1] if len(parts) > 1 else "")
        except Exception:
            return 0, ""

    def save_state(self):
        try:
            with open(STATE_FILE, "w") as fh:
                fh.write("%d %s\n" % (self.high, self.mode))
        except Exception:
            pass

    # -- lifecycle --------------------------------------------------------
    def reset(self, full=False):
        self.asteroids = []
        self.bullets = []
        self.particles = []
        self.shocks = []
        self.debris = []
        self.pops = []
        self.foes = []
        self.pickups = []
        self.queue = []            # classes still to arrive this wave
        self.spawn_cd = 0.0
        self.ship = None
        self.fire_cd = 0.0
        self.weapon = None         # None = the ship's own gun
        self.ammo = 0
        if full:
            self.score = 0
            self.lives = 3
            self.level = 0
            self.next_extra = 20000
            self.shots = self.hits = 0

    def start_game(self):
        self.reset(full=True)
        self.state = "play"
        self.spawn_wave()
        self.spawn_ship()
        self.flash("%s FLIGHT" % self.mode.upper(), 1.6)

    def spawn_ship(self):
        w, h = self.world
        self.ship = Ship(w / 2, h / 2)
        if self.level <= 2:
            self.ship.invuln = 3.2
        self.shocks.append(Shock(w / 2, h / 2, 26, 5, 0.5))

    def spawn_wave(self):
        self.level += 1
        w, h = self.world
        d = self.diff()
        scale, spread = self.rock_scale(), 0.15 + 0.35 * d
        for _ in range(max(0, self.rock_count() - len(self.asteroids))):
            while True:
                x, y = random.uniform(0, w), random.uniform(0, h)
                if self.wrap_dist(x, y, w / 2, h / 2) > 60:
                    break
            self.asteroids.append(Asteroid(x, y, 3, scale, spread=spread))
        self.queue = self.roster()
        self.spawn_cd = 1.4
        if self.state != "title":
            if self.is_boss_wave():
                self.flash("WAVE %d  -  DREADNOUGHT" % self.level, 2.4)
            elif self.is_mini_wave():
                self.flash("WAVE %d  -  MARAUDER" % self.level, 2.2)
            else:
                self.flash("WAVE %d" % self.level, 1.8)
            self.sweep = 0.45

    def spawn_gap(self):
        return self.lerp(2.6, 0.9, self.diff()) * random.uniform(0.75, 1.3)

    def spawn_foe(self, kind):
        """Bring one ship in from an edge, away from the player."""
        w, h = self.world
        best = None
        for _ in range(12):
            if random.random() < 0.5:
                x, y = random.uniform(0, w), random.choice((2.0, h - 3.0))
            else:
                x, y = random.choice((2.0, w - 3.0)), random.uniform(0, h)
            d = (self.wrap_dist(x, y, self.ship.x, self.ship.y)
                 if self.ship else 1e9)
            if best is None or d > best[0]:
                best = (d, x, y)
            if d > 70:
                break
        self.foes.append(Raider(kind, best[1], best[2], self.diff(),
                                self.world))
        self.shocks.append(Shock(best[1], best[2], 2, 20, 0.4))

    def flash(self, text, t=1.4):
        self.msg, self.msg_t, self.msg_t0 = text, t, t

    def burst(self, x, y, n, speed, life, drag=0.9):
        for _ in range(n):
            a = random.uniform(0, TAU)
            sp = speed * random.uniform(0.2, 1.0)
            self.particles.append(Particle(x, y, sp * math.cos(a),
                                           sp * math.sin(a),
                                           life * random.uniform(0.45, 1.0),
                                           drag))

    def add_score(self, pts, x=None, y=None, attr=None):
        if self.state == "title":
            return
        self.score += pts
        if x is not None:
            self.pops.append(Pop(x, y, "+%d" % pts, attr or A("ui_hi")))
        if self.score >= self.next_extra:
            self.next_extra += 20000
            self.lives += 1
            self.flash("EXTRA SHIP", 1.6)

    # -- actions ----------------------------------------------------------
    def fire(self):
        s = self.ship
        if s is None or self.fire_cd > 0:
            return
        spec = WEAPONS[self.weapon] if self.weapon else None
        cap = 18 if spec else 8
        if sum(1 for b in self.bullets if not b.hostile) >= cap:
            return
        self.fire_cd = spec["cd"] if spec else 0.14
        sp = Bullet.SPEED * (0.85 if self.weapon == "gauss" else 1.0)
        nose = s.hull()[0]
        x, y = nose[0] % self.world[0], nose[1] % self.world[1]
        angles = [s.ang]
        dmg, kind, col = 1, self.weapon, spec["col"] if spec else None
        if self.weapon == "spread":
            angles = [s.ang - 0.21, s.ang, s.ang + 0.21]
        elif self.weapon == "gauss":
            dmg = 3
        for a in angles:
            self.bullets.append(Bullet(
                x, y, sp * math.cos(a) + s.vx * 0.3,
                sp * math.sin(a) + s.vy * 0.3,
                Bullet.reach(self.world, sp), dmg=dmg, kind=kind, col=col))
        if self.state != "title":
            self.shots += 1
        if spec:
            self.ammo -= 1
            if self.ammo <= 0:
                self.weapon = None
                self.flash("MAGAZINE DRY", 1.1)
        # muzzle flash
        for _ in range(3):
            a = s.ang + random.uniform(-0.4, 0.4)
            self.particles.append(Particle(nose[0], nose[1],
                                           60 * math.cos(a), 60 * math.sin(a),
                                           0.12, 0.8))

    def hyperspace(self):
        s = self.ship
        if s is None or s.warp_cd > 0:
            return
        self.shocks.append(Shock(s.x, s.y, 22, 2, 0.35))
        self.burst(s.x, s.y, 14, 60, 0.4)
        s.x = random.uniform(0, self.world[0])
        s.y = random.uniform(0, self.world[1])
        s.vx = s.vy = 0.0
        s.invuln = max(s.invuln, 0.8)
        s.warp_cd = 3.0
        self.shocks.append(Shock(s.x, s.y, 3, 24, 0.4))
        self.burst(s.x, s.y, 14, 70, 0.45)

    def toggle_mode(self):
        self.mode = "classic" if self.mode == "arcade" else "arcade"
        self.flash("%s FLIGHT" % self.mode.upper(), 1.2)
        self.save_state()

    # -- update -----------------------------------------------------------
    STEP = 1.0 / 120.0     # longest slice the integrator may take
    MAX_FRAME = 0.06       # ignore anything longer (a stall, a resize)

    def advance(self, dt, keys):
        """Step the simulation in slices of at most STEP, totalling exactly dt.

        Capping the slice keeps Euler integration stable when a frame runs
        long. Letting the last slice take the remainder - rather than banking
        it for next frame - means each frame advances by exactly the time it
        took, so motion never beats against the frame rate.
        """
        dt = min(dt, self.MAX_FRAME)
        while dt > 1e-6:
            step = min(self.STEP, dt)
            self.update(step, keys)
            dt -= step

    def update(self, dt, keys):
        self.msg_t = max(0.0, self.msg_t - dt)
        self.shake = max(0.0, self.shake - dt)
        self.sweep = max(0.0, self.sweep - dt)
        self.fire_cd = max(0.0, self.fire_cd - dt)
        for st in self.stars:
            st.update(dt, self.world, self.ship)
        for group in (self.particles, self.shocks, self.debris, self.pops,
                      self.pickups):
            for o in group:
                o.update(dt, self.world)
        self.pickups = [p for p in self.pickups if p.life > 0]
        self.particles = [p for p in self.particles if p.life > 0]
        self.shocks = [s for s in self.shocks if s.life > 0]
        self.debris = [d for d in self.debris if d.life > 0]
        self.pops = [p for p in self.pops if p.life > 0]

        if self.state == "paused":
            return

        if self.state == "title":
            self.update_title(dt)
            return

        if self.state == "over":
            for a in self.asteroids:
                a.update(dt, self.world)
            return

        if self.state == "dead":
            self.timer -= dt
            for a in self.asteroids:
                a.update(dt, self.world)
            for foe in self.foes:
                foe.update(dt, self.world, None, self.bullets)
            for b in self.bullets:
                b.update(dt, self.world)
            self.bullets = [b for b in self.bullets if b.life > 0]
            if self.timer <= 0:
                if self.lives <= 0:
                    self.end_game()
                else:
                    self.state = "play"
                    self.spawn_ship()
            return

        # ---- playing ----
        self.fire()             # the gun runs itself; fire_cd paces it
        s = self.ship
        if s:
            if self.mode == "arcade":
                s.fly_arcade(dt,
                             keys.axis("right") - keys.axis("left"),
                             keys.axis("down") - keys.axis("up"),
                             self.world)
            else:
                turn = keys.axis("left") - keys.axis("right")
                s.fly_classic(dt, turn, keys.held("up"), keys.held("down"),
                              self.world)
            if s.thrust > 0.3 and random.random() < 0.5:
                back = s.ang + math.pi
                self.particles.append(Particle(
                    s.x + 4 * math.cos(back), s.y + 4 * math.sin(back),
                    s.vx * -0.25 + random.uniform(-14, 14),
                    s.vy * -0.25 + random.uniform(-14, 14),
                    random.uniform(0.15, 0.35), 0.93))
        for a in self.asteroids:
            a.update(dt, self.world)
        for b in self.bullets:
            b.update(dt, self.world)
            if b.kind == "homing" and not b.hostile:
                self.home(b, dt)
        self.bullets = [b for b in self.bullets if b.life > 0]

        self.spawn_cd -= dt
        if (self.queue and self.spawn_cd <= 0 and
                len(self.foes) < self.MAX_FOES):
            self.spawn_foe(self.queue.pop(0))
            self.spawn_cd = self.spawn_gap()
        for foe in self.foes:
            foe.update(dt, self.world, self.ship, self.bullets)

        self.collisions()
        # The wave is the fleet. Leftover rocks drift on into the next one.
        if not self.foes and not self.queue:
            self.spawn_wave()

    def update_title(self, dt):
        """Attract mode: a demo ship loops around duelling interceptors."""
        s = self.ship
        if s:
            s.fly_classic(dt, math.sin(time.time() * 0.5) * 0.9, True, False,
                          self.world)
            s.invuln = 0.0
            self.demo_fire -= dt
            if self.demo_fire <= 0:
                self.demo_fire = random.uniform(0.35, 0.8)
                self.fire()
        for a in self.asteroids:
            a.update(dt, self.world)
        for b in self.bullets:
            b.update(dt, self.world)
        self.bullets = [b for b in self.bullets if b.life > 0]
        for b in list(self.bullets):
            for a in list(self.asteroids):
                if self.wrap_dist(b.x, b.y, a.x, a.y) < a.r:
                    self.split(a)
                    if b in self.bullets:
                        self.bullets.remove(b)
                    break
        for foe in self.foes:
            foe.update(dt, self.world, s, self.bullets)
        for b in list(self.bullets):
            if b.hostile:
                continue
            for foe in list(self.foes):
                if self.wrap_dist(b.x, b.y, foe.x, foe.y) < foe.r:
                    if b in self.bullets:
                        self.bullets.remove(b)
                    if foe.hit():
                        self.kill_foe(foe, award=False)
                    break
        w, h = self.world
        if len(self.asteroids) < 3:
            self.asteroids.append(Asteroid(
                w * random.random(), 0 if random.random() < 0.5 else h - 1,
                3, 1.0))
        if len(self.foes) < 2:
            self.spawn_foe("scout" if random.random() < 0.7 else "gunship")

    def collisions(self):
        for b in list(self.bullets):
            if b.hostile:
                continue
            for foe in list(self.foes):          # ships first: they are the
                if foe.arrive > 0:               # point of the wave now
                    continue
                if b.spent is not None and foe in b.spent:
                    continue
                if self.wrap_dist(b.x, b.y, foe.x, foe.y) < foe.r:
                    if b.spent is None:
                        self.bullets.remove(b)
                    else:
                        b.spent.add(foe)         # a lance carries on through
                    self.hits += 1
                    if foe.hit(b.dmg):
                        self.kill_foe(foe)
                    else:
                        self.burst(b.x, b.y, 3, 34, 0.18)
                    break
            else:
                for a in list(self.asteroids):
                    if self.wrap_dist(b.x, b.y, a.x, a.y) < a.r:
                        self.split(a)
                        if b in self.bullets:
                            self.bullets.remove(b)
                        self.hits += 1
                        break

        s = self.ship
        if s is None:
            return
        for pk in list(self.pickups):
            if self.wrap_dist(s.x, s.y, pk.x, pk.y) < Pickup.R + Ship.RADIUS:
                self.pickups.remove(pk)
                spec = WEAPONS[pk.kind]
                # A fresh magazine of the same type tops it up rather than
                # resetting it, so a lucky double drop is not wasted.
                self.ammo = (self.ammo if self.weapon == pk.kind else 0)
                self.ammo += spec["ammo"]
                self.weapon = pk.kind
                self.fire_cd = 0.0
                self.flash(spec["name"], 1.1)
                self.shocks.append(Shock(pk.x, pk.y, 2, 20, 0.35))
                self.burst(pk.x, pk.y, 10, 55, 0.4)
        for a in list(self.asteroids):
            if self.wrap_dist(s.x, s.y, a.x, a.y) < a.r + Ship.RADIUS:
                if s.invuln <= 0:
                    self.kill_ship()
                    self.split(a, award=False)
                return
        for foe in list(self.foes):
            if foe.arrive > 0:
                continue
            if self.wrap_dist(s.x, s.y, foe.x, foe.y) < foe.r * 0.8 + \
                    Ship.RADIUS:
                if s.invuln <= 0:
                    self.kill_ship()
                    # Ramming a capital ship hurts it; it does not kill it.
                    for _ in range(3 if foe.boss else foe.hp):
                        if foe.hit():
                            self.kill_foe(foe, award=False)
                            break
                return
        for b in list(self.bullets):
            if b.hostile and self.wrap_dist(s.x, s.y, b.x, b.y) < Ship.RADIUS + 2:
                self.bullets.remove(b)
                if s.invuln <= 0:
                    self.kill_ship()
                return

    def split(self, a, award=True):
        if award:
            self.add_score(a.points, a.x, a.y, A("ast%d" % a.size))
        self.burst(a.x, a.y, 6 + 7 * a.size, 30 + 22 * a.size, 0.5 + 0.1 * a.size)
        self.shocks.append(Shock(a.x, a.y, a.r * 0.5, a.r * 2.4,
                                 0.22 + 0.08 * a.size))
        self.shake = max(self.shake, 0.05 * a.size)
        self.asteroids.remove(a)
        if a.size > 1:
            d = self.diff()
            for _ in range(2):
                ang = random.uniform(0, TAU)
                sp = (math.hypot(a.vx, a.vy) *
                      random.uniform(1.05, 1.2 + 0.35 * d) +
                      self.lerp(1.5, 5.5, d))
                child = Asteroid(a.x, a.y, a.size - 1, self.rock_scale(),
                                 sp * math.cos(ang), sp * math.sin(ang))
                child.flash = 0.08
                self.asteroids.append(child)

    DROP = {"scout": 0.10, "gunship": 0.26}

    def kill_foe(self, foe, award=True):
        if foe not in self.foes:
            return
        self.foes.remove(foe)
        if award:
            self.add_score(foe.value, foe.x, foe.y, A(foe.col))
            # Wrecks give up their magazines. A capital ship gives up several.
            drops = (3 if foe.kind == "dread" else 2) if foe.boss else (
                1 if random.random() < self.DROP.get(foe.kind, 0.0) else 0)
            for _ in range(drops):
                self.pickups.append(
                    Pickup(foe.x, foe.y, random.choice(WEAPON_KINDS)))
        n = int(18 + foe.r * 2.4)
        self.burst(foe.x, foe.y, n, 70 + foe.r * 3.0, 0.7 + foe.r * 0.03)
        self.shocks.append(Shock(foe.x, foe.y, foe.r * 0.4, foe.r * 3.2,
                                 0.4 + foe.r * 0.012))
        self.shake = max(self.shake, 0.14 + foe.r * 0.012)
        if foe.boss:
            self.shocks.append(Shock(foe.x, foe.y, 2, foe.r * 5.5, 0.9))
            self.flash("%s DOWN" % ("DREADNOUGHT" if foe.kind == "dread"
                                    else "MARAUDER"), 2.0)
            for _ in range(6):     # the hull comes apart
                a = random.uniform(0, TAU)
                sp = random.uniform(18, 55)
                self.debris.append(Debris(
                    foe.x, foe.y, sp * math.cos(a), sp * math.sin(a),
                    foe.r * random.uniform(0.5, 1.1), 1.6))

    def kill_ship(self):
        s = self.ship
        nose, left, right, tail = s.hull()
        for p, q in ((nose, left), (nose, right), (left, tail), (right, tail)):
            a = random.uniform(0, TAU)
            sp = random.uniform(14, 42)
            self.debris.append(Debris((p[0] + q[0]) / 2, (p[1] + q[1]) / 2,
                                      s.vx * 0.4 + sp * math.cos(a),
                                      s.vy * 0.4 + sp * math.sin(a),
                                      math.hypot(p[0] - q[0], p[1] - q[1]),
                                      1.5))
        self.burst(s.x, s.y, 42, 105, 1.1)
        self.shocks.append(Shock(s.x, s.y, 3, 46, 0.65))
        self.shake = 0.45
        self.ship = None
        self.weapon, self.ammo = None, 0     # the magazine goes with the ship
        self.lives -= 1
        self.state = "dead"
        self.timer = 1.7
        self.flash("SHIP LOST" if self.lives > 0 else "GAME OVER", 1.5)

    def end_game(self):
        self.state = "over"
        if self.score > self.high:
            self.high = self.score
        self.save_state()

    # -- render -----------------------------------------------------------
    def draw(self, stdscr):
        sc = self.screen
        sc.clear()
        cx, cy = self.cell_x, self.cell_y
        if self.shake > 0:
            # A decaying oscillation, not per-frame noise: reads as a thump
            # rather than a flicker.
            amp = min(2.0, self.shake * 7.0)
            cx += int(round(amp * math.sin(self.shake * 47.0)))
            cy += int(round(amp * 0.55 * math.sin(self.shake * 39.0 + 1.7)))
        f = Field(sc, cx, cy, *self.world)

        for st in self.stars:
            st.draw(f)
        if self.sweep > 0:
            x = self.world[0] * (1.0 - self.sweep / 0.45)
            for y in range(0, self.world[1], 2):
                f.dot(x, y, ramp("shock", 0.2), 2)
        for p in self.particles:
            p.draw(f)
        for s in self.shocks:
            s.draw(f)
        for d in self.debris:
            d.draw(f)
        for a in self.asteroids:
            a.draw(f)
        for pk in self.pickups:
            pk.draw(f)
        for foe in self.foes:
            foe.draw(f)
        for b in self.bullets:
            b.draw(f)
        if self.ship:
            self.ship.draw(f)
        for p in self.pops:
            p.draw(f)

        self.draw_frame(sc)
        if self.state == "title":
            self.draw_title(sc)
        else:
            self.draw_banner(sc)
        if self.state == "over":
            self.draw_over(sc)
        elif self.state == "paused":
            self.panel(sc, ["PAUSED", "", "P  resume       M  flight model",
                            "R  restart      Q  quit"])
        sc.blit(stdscr)

    # -- chrome -----------------------------------------------------------
    def draw_frame(self, sc):
        w, h = self.sw, self.sh
        fr = A("frame")
        for y in range(1, h - 1):
            sc.text(0, y, "│", fr)
            sc.text(w - 1, y, "│", fr)
        sc.text(0, 0, "╭" + "─" * (w - 2) + "╮", fr)
        sc.text(0, h - 1, "╰" + "─" * (w - 2) + "╯", fr)
        if self.state == "title":
            self.title_bars(sc)
        else:
            self.hud(sc)

    def seg(self, sc, x, y, label, value, vattr):
        """Draw ` LABEL value ` into a bar, return the x after it."""
        sc.text(x, y, " ", 0)
        x += 1
        if label:
            sc.text(x, y, label + " ", A("dim"))
            x += len(label) + 1
        sc.text(x, y, value + " ", vattr)
        return x + len(value) + 2

    def hud(self, sc):
        w = self.sw
        x = self.seg(sc, 2, 0, "SCORE", "%d" % self.score, A("ui_hi"))
        if self.lives > 0 and x + self.lives * 2 + 2 < w - 24:
            sc.text(x, 0, " " + " ".join("▲" * self.lives) + " ", A("ship"))
            x += self.lives * 2 + 2
        boss = next((f for f in self.foes if f.boss), None)
        left_over = len(self.foes) + len(self.queue)
        mid = "WAVE %d" % self.level
        if w > 56:
            mid += "  " + ("▾" * min(left_over, 12) if left_over else "CLEAR")
        if x + len(mid) + 6 < w - 16:
            sc.text((w - len(mid)) // 2 - 1, 0, " " + mid + " ", A("accent"))
        if boss is not None and w > 64:
            self.boss_bar(sc, boss)
        right = "HIGH %d" % max(self.high, self.score)
        if len(right) + 6 < w:
            sc.text(w - len(right) - 3, 0, " " + right + " ", A("ui"))

        # bottom bar: flight model, controls, warp charge - laid out left to
        # right so the segments can never run into each other.
        y = self.sh - 1
        mode = "ARCADE" if self.mode == "arcade" else "CLASSIC"
        sc.text(2, y, " %s " % mode, A("warn"))
        left = 2 + len(mode) + 2
        if self.weapon:
            spec = WEAPONS[self.weapon]
            cells = 6
            full = max(1, int(round(cells * self.ammo / spec["ammo"])))
            full = min(cells, full)
            tag = "%s %s" % (spec["name"],
                             BAR_FULL * full + BAR_EMPTY * (cells - full))
            if left + len(tag) + 2 < self.sw - 26:
                sc.text(left, y, " %s " % tag, A(spec["col"]))
                left += len(tag) + 2
        s = self.ship
        charge = 1.0 if s is None else 1.0 - s.warp_cd / 3.0
        bars = max(0, min(4, int(charge * 4 + 0.001)))
        warp = "WARP " + BAR_FULL * bars + BAR_EMPTY * (4 - bars)
        right = w - 2
        if len(warp) + 12 < w:
            right = w - len(warp) - 3
            sc.text(right, y, " " + warp + " ",
                    A("ui_hi") if bars == 4 else A("dim"))
        hints = [
            ("↑↓←→ hold to fly  YUBN diagonal  guns fire themselves"
             "  X warp  M model  P pause  Q quit"
             if self.mode == "arcade" else
             "←→ turn  ↑ thrust  guns automatic  X warp  M model  Q quit"),
            ("↑↓←→ fly  YUBN diagonal  auto guns  X warp  M model  Q quit"
             if self.mode == "arcade" else
             "←→ turn  ↑ thrust  auto guns  X warp  Q quit"),
            "FLY · WARP",
        ]
        gap = right - left
        for hint in hints:
            if len(hint) + 4 <= gap:
                sc.text(left + (gap - len(hint)) // 2, y, " %s " % hint,
                        A("dim"))
                break

    def boss_bar(self, sc, boss):
        """Hull integrity, on the frame line under the score bar."""
        w = self.sw
        name = "DREADNOUGHT" if boss.kind == "dread" else "MARAUDER"
        cells = max(8, min(28, w // 4))
        full = int(round(cells * max(0.0, boss.hp) / boss.hp0))
        bar = BAR_FULL * full + BAR_EMPTY * (cells - full)
        s = " %s %s " % (name, bar)
        x = max(1, (w - len(s)) // 2)
        sc.text(x, 1, s, A(boss.col) if boss.flash <= 0 else A("flash"))

    def title_bars(self, sc):
        y = self.sh - 1
        tag = " a t t r a c t   m o d e "
        if len(tag) + 6 < self.sw:
            sc.text((self.sw - len(tag)) // 2, y, tag, A("dim"))

    def draw_banner(self, sc):
        if self.msg_t <= 0:
            return
        t = 1.0 - self.msg_t / self.msg_t0
        y = self.sh // 2 - 2
        gap = int(2 + 10 * (1.0 - (1.0 - t) ** 3))
        pad = " " * gap
        line = "«%s%s%s»" % (pad, self.msg, pad)
        attr = A("accent") if self.msg_t > 0.4 or int(self.msg_t * 12) % 2 \
            else A("ui_hi")
        sc.ctext(y, line, attr)

    def panel(self, sc, lines, title_attr=None):
        wide = min(max(len(s) for s in lines) + 8, sc.w - 4)
        high = len(lines) + 2
        x0 = (sc.w - wide) // 2
        y0 = (sc.h - high) // 2
        fr = A("ui")
        sc.text(x0, y0, "╭" + "─" * (wide - 2) + "╮", fr)
        for i, s in enumerate(lines):
            sc.text(x0, y0 + 1 + i, "│" + " " * (wide - 2) + "│", fr)
            attr = (title_attr or A("accent")) if i == 0 else A("ui_hi")
            if s.startswith("·"):
                attr = A("dim")
            sc.text(x0 + (wide - len(s)) // 2, y0 + 1 + i, s, attr)
        sc.text(x0, y0 + high - 1, "╰" + "─" * (wide - 2) + "╯", fr)
        for i in range(1, high + 1):          # drop shadow
            sc.text(x0 + wide, y0 + i, "░", A("frame"))
        sc.text(x0 + 1, y0 + high, "░" * wide, A("frame"))

    BIG = [
        " █████╗ ███████╗████████╗███████╗██████╗  ██████╗ ██╗██████╗ ███████╗",
        "██╔══██╗██╔════╝╚══██╔══╝██╔════╝██╔══██╗██╔═══██╗██║██╔══██╗██╔════╝",
        "███████║███████╗   ██║   █████╗  ██████╔╝██║   ██║██║██║  ██║███████╗",
        "██╔══██║╚════██║   ██║   ██╔══╝  ██╔══██╗██║   ██║██║██║  ██║╚════██║",
        "██║  ██║███████║   ██║   ███████╗██║  ██║╚██████╔╝██║██████╔╝███████║",
        "╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝╚═════╝ ╚══════╝",
    ]
    MID = [
        "╔═╗╔═╗╔╦╗╔═╗╦═╗╔═╗╦╔╦╗╔═╗",
        "╠═╣╚═╗ ║ ║╣ ╠╦╝║ ║║ ║ ╚═╗",
        "╩ ╩╚═╝ ╩ ╚═╝╩╚═╚═╝╩═╩╝╚═╝",
    ]

    @staticmethod
    def matte(sc, y, width, pad=2):
        """Blank a centred strip so text reads clean over the star field."""
        w = min(width + pad * 2, sc.w - 2)
        sc.text((sc.w - w) // 2, y, " " * w, 0)

    def draw_title(self, sc):
        lines = ["A S T E R O I D S"]
        for cand in (self.BIG, self.MID):
            if len(cand[0]) <= sc.w - 6:
                lines = cand
                break
        y = max(1, sc.h // 2 - len(lines) // 2 - 5)
        for i, s in enumerate(lines):
            self.matte(sc, y + i, len(lines[0]), 3)
            sc.ctext(y + i, s, ramp("title", i / max(1, len(lines) - 1) * 0.8))
        y += len(lines) + 1
        mode = "ARCADE" if self.mode == "arcade" else "CLASSIC"
        moves = ("↑ ↓ ← →  fly      Y U B N  diagonals      0  all stop"
                 if self.mode == "arcade"
                 else "← → turn      ↑ thrust      ↓ retro")
        rows = [
            (0, moves, A("ui_hi")),
            (1, ("hold a key to fly - let go and the ship stops"
                 if self.mode == "arcade"
                 else "hold to turn and thrust - there are no brakes"),
             A("dim")),
            (2, "guns fire themselves - fly to aim      X hyperspace",
             A("ui")),
            (3, "M  flight model:  %s" % mode, A("warn")),
            (5, "interceptor 150   gunship 400   rocks 20/50/100", A("dim")),
            (6, "MARAUDER every 5th wave 2500   DREADNOUGHT every 10th 12000",
             A("warn")),
        ]
        if self.high:
            rows.append((7, "high score  %d" % self.high, A("accent")))
        pulse = math.sin(time.time() * 4.0) > 0
        rows.append((9, "───  PRESS  SPACE  TO  LAUNCH  ───",
                     A("warn") if pulse else A("dim")))
        for dy, text, attr in rows:
            self.matte(sc, y + dy, len(text))
            sc.ctext(y + dy, text, attr)

    def draw_over(self, sc):
        acc = (100.0 * self.hits / self.shots) if self.shots else 0.0
        best = "* NEW HIGH SCORE *" if (self.score >= self.high and
                                        self.score > 0) else ""
        self.panel(sc, [
            "GAME OVER", best,
            "score      %d" % self.score,
            "waves      %d" % self.level,
            "accuracy   %.0f%%" % acc,
            "high       %d" % self.high,
            "",
            "R  play again        Q  quit",
        ])


# ==========================================================================
# Main loop
# ==========================================================================
KEYMAP = {
    curses.KEY_LEFT: ("left",), ord("a"): ("left",), ord("A"): ("left",),
    curses.KEY_RIGHT: ("right",), ord("d"): ("right",), ord("D"): ("right",),
    curses.KEY_UP: ("up",), ord("w"): ("up",), ord("W"): ("up",),
    curses.KEY_DOWN: ("down",), ord("s"): ("down",), ord("S"): ("down",),
    # One-key diagonals. Holding two arrows can only ever be approximated
    # (see Keys), but a single held key repeats reliably, so these give a
    # true, indefinitely sustained diagonal.
    ord("u"): ("up", "right"), ord("U"): ("up", "right"),
    ord("y"): ("up", "left"), ord("Y"): ("up", "left"),
    ord("n"): ("down", "right"), ord("N"): ("down", "right"),
    ord("b"): ("down", "left"), ord("B"): ("down", "left"),
    ord("9"): ("up", "right"), ord("7"): ("up", "left"),
    ord("3"): ("down", "right"), ord("1"): ("down", "left"),
}


class Keys:
    """Held-key emulation, because terminals never report a key release.

    Two facts drive the whole design. A terminal sends a keypress and then,
    after the OS "delay until repeat" (~0.5s), a fast repeat train - so a
    press has to be treated as a hold that expires. And the OS auto-repeats
    only the *most recently pressed* key: tap fire while flying and the arrow
    stops repeating; hold two arrows and the first one goes quiet.

    So a press opens a generous window that covers the repeat delay, and any
    other key event keeps recently-used directions alive at reduced strength
    ("carry"). That is what lets you shoot without stalling and hold two
    arrows for a diagonal. Carry is bounded from each direction's own last
    real press, so releasing a key still stops you.
    """

    # A fresh press has to stay "held" until the OS repeat train starts, or
    # the ship stutters; but every millisecond past that is drift after a tap.
    # The delay is a user setting (~0.25-1.0s on macOS), so rather than guess
    # it, watch for the first repeat of a held key and learn it.
    DELAY_GUESS = 0.50  # until the first repeat is seen
    FIRST_MIN = 0.34
    # High enough to cover a slow terminal's delay-until-repeat once that
    # delay has been measured. It only ever costs drift on a machine that
    # actually is that slow, since first tracks the measured delay.
    FIRST_MAX = 1.35
    # Bridges the gap between repeats. Every millisecond of it is drift after
    # you let go, so rather than sit on a worst-case guess it is measured from
    # the repeat train itself, the same way the delay above is.
    REPEAT = 0.16       # until a train has been seen
    REPEAT_MIN = 0.07
    REPEAT_MAX = 0.28
    # Every millisecond of carry is also thrust you did not ask for, if you
    # really did let go. So it is short while you are steering - a ship that
    # keeps flying after you release is the most infuriating thing there is -
    # and longer after a fire or warp press, which says nothing about whether
    # you meant to change direction.
    CARRY = 0.40        # another direction key carries the others this long
    CARRY_OTHER = 1.0   # a fire/warp/pause press carries them this long
    CARRY_HI = 0.50     # carried push right after the last real press...
    CARRY_LO = 0.10     # ...fading to this as the carry window runs out
    DIRS = ("left", "right", "up", "down")
    OPPOSITE = {"left": "right", "right": "left", "up": "down", "down": "up"}

    def __init__(self):
        self.real = dict.fromkeys(self.DIRS, -9.0)    # last genuine press
        self.hold = dict.fromkeys(self.DIRS, -9.0)    # genuine hold expiry
        self.carried = dict.fromkeys(self.DIRS, -9.0)  # carried hold expiry
        self.delay = self.DELAY_GUESS                 # learned repeat delay
        self.gap = self.REPEAT / 2.6                  # learned repeat period
        self.last_gap = dict.fromkeys(self.DIRS, 0.0)  # for spotting a train
        self.now = 0.0

    @property
    def first(self):
        return min(self.FIRST_MAX, max(self.FIRST_MIN, self.delay * 1.12))

    @property
    def window(self):
        """How long one repeat keeps a key alive - and so how long the ship
        keeps going after you let go. Kept at a few repeat periods so a slow
        train still bridges, and no wider."""
        return min(self.REPEAT_MAX, max(self.REPEAT_MIN, self.gap * 2.6))

    def tick(self, now):
        self.now = now

    def brake(self):
        """All stop: forget every direction, held or carried."""
        for name in self.DIRS:
            self.real[name] = self.hold[name] = self.carried[name] = -9.0

    def press(self, names, now):
        for name in names:
            fresh = now >= self.hold[name]
            # A press this soon after the last one is a repeat, whether or not
            # our hold window was still open - and the first repeat of a hold
            # measures this machine's delay-until-repeat. Learning it even
            # after the window lapsed is what stops a too-short guess from
            # making a held key stutter forever.
            gap = now - self.real[name]
            # Only a repeat *train* may teach us anything. A gap on its own
            # says nothing - steering taps land 0.2-0.4 s apart and look
            # exactly like a delay-until-repeat, and letting those through
            # drags the learned delay below the real one, which makes every
            # held key stutter. A train is unmistakable though: a short gap
            # right behind a much longer one. The long gap was the delay, the
            # short one is the period.
            prev = self.last_gap[name]
            if 0.0 < gap < 0.25 and gap * 2.0 < prev < 2.5:
                self.delay = max(min(prev, 1.5), self.delay * 0.98)
                self.gap = max(gap, self.gap * 0.9)
            elif not fresh and 0.0 < gap < 0.25 and 0.0 < prev < 0.25:
                # Two short gaps in a row while the window is still open: we
                # are inside the train, so keep refining the period. Only the
                # period - a steady train says nothing new about the delay.
                self.gap = max(gap, self.gap * 0.9)
            self.last_gap[name] = gap
            self.hold[name] = now + (self.first if fresh else self.window)
            self.real[name] = now
            opp = self.OPPOSITE[name]
            if opp not in names:                       # reversing cancels
                self.real[opp] = self.hold[opp] = self.carried[opp] = -9.0
        self._carry(now, self.CARRY, skip=names)

    def other(self, now, skip=()):
        """Any key event at all keeps recently-pressed directions alive."""
        self._carry(now, self.CARRY_OTHER, skip=skip)

    def _carry(self, now, window, skip=()):
        for name in self.DIRS:
            if name not in skip and now - self.real[name] < window:
                self.carried[name] = max(self.carried[name],
                                         now + self.window)

    def axis(self, name):
        """0.0 not held, 1.0 genuinely held, tapering in between if carried.

        A carried direction fades rather than cutting out: held as half of a
        two-arrow diagonal it reads as a smooth curve, and in the case where
        the key really was released it reads as ordinary drift.
        """
        now = self.now
        live = self.hold[name]
        if now < live:
            v = 1.0
        else:
            # One dropped repeat should dip the throttle, not cut it dead, so
            # the window eases out over a fraction of a repeat period rather
            # than ending on a cliff. A real release still lands inside it.
            fade = self.window * 0.6
            v = max(0.0, 1.0 - (now - live) / fade)
        if now < self.carried[name]:
            t = min(1.0, max(0.0, (now - self.real[name]) / self.CARRY_OTHER))
            v = max(v, self.CARRY_HI + (self.CARRY_LO - self.CARRY_HI) * t)
        return v

    def held(self, name):
        return self.axis(name) > 0.0


class Reader:
    """Drain curses input, re-assembling arrow sequences by hand.

    With nodelay set, ncurses hands back a bare ESC rather than block waiting
    for the rest of a sequence, so on plenty of terminals an arrow key arrives
    as 27 '[' 'C' instead of KEY_RIGHT. Left alone that reads as three unknown
    keys - the ship never moves on arrows, or moves only on the presses that
    happened to be assembled, which is indistinguishable from a stutter.
    """

    ARROW = {65: curses.KEY_UP, 66: curses.KEY_DOWN,
             67: curses.KEY_RIGHT, 68: curses.KEY_LEFT}
    PARTIAL = 0.05          # how long to wait for the rest of a sequence

    def __init__(self, stdscr):
        self.s = stdscr
        self.buf = []
        self.t = 0.0

    def read(self, now):
        while True:
            c = self.s.getch()
            if c == -1:
                break
            self.buf.append(c)
            self.t = now
        out, b, i = [], self.buf, 0
        while i < len(b):
            c = b[i]
            if c != 27:
                out.append(c)
                i += 1
            elif len(b) - i >= 3 and b[i + 1] in (91, 79):
                key = self.ARROW.get(b[i + 2])
                out.append(key if key is not None else 27)
                i += 3 if key is not None else 1
            elif len(b) - i < 3 and now - self.t < self.PARTIAL:
                break                      # still arriving - keep it for next
            else:
                out.append(27)             # a real, lone Escape
                i += 1
        self.buf = b[i:]
        return out


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
    prev_state = game.state
    now = time.perf_counter()
    last = now
    frame = 1.0 / FPS
    while True:
        now = time.perf_counter()
        dt = min(now - last, 0.06)
        last = now

        for c in reader.read(now):
            if c == curses.KEY_RESIZE:
                h, w = stdscr.getmaxyx()
                if w >= MIN_W and h >= MIN_H:
                    game.resize(w, h)
                    stdscr.erase()
                continue
            if c in KEYMAP:
                keys.press(KEYMAP[c], now)
                continue
            # Any other key keeps the current heading alive, so firing,
            # warping or pausing never stalls the ship.
            keys.other(now)
            if c in (ord("q"), ord("Q")):
                if game.score > game.high:
                    game.high = game.score
                game.save_state()
                return
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
            if game.state != "play":
                keys.brake()          # a new ship starts stationary
            prev_state = game.state
        keys.tick(now)
        game.advance(dt, keys)
        game.draw(stdscr)
        stdscr.noutrefresh()
        curses.doupdate()

        slack = frame - (time.perf_counter() - now)
        if slack > 0:
            time.sleep(slack)


def selftest(frames=1500):
    """Headless run: simulate and render every state without a terminal."""
    global STATE_FILE
    STATE_FILE = os.path.join(os.environ.get("TMPDIR", "/tmp"),
                              ".asteroids_selftest_state")
    random.seed(5)
    t0 = time.perf_counter()
    g = Game(110, 34)
    g.start_game()
    keys = Keys()
    draw_ns = 0.0
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
        if i == 250:
            g.toggle_mode()
        if i == 400:
            g.resize(60, 20)
        if i == 800:
            g.resize(160, 46)
        d0 = time.perf_counter()
        g.screen.clear()
        f = Field(g.screen, g.cell_x, g.cell_y, *g.world)
        for st in g.stars:
            st.draw(f)
        for o in g.movers():
            o.draw(f)
        g.draw_frame(g.screen)
        g.draw_banner(g.screen)
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
    t0 = time.perf_counter()
    while True:
        now = time.perf_counter()
        for c in reader.read(now):
            if c in (ord("q"), ord("Q")):
                return delays, periods
            name = named.get(c) or (chr(c) if 32 <= c < 127 else "#%d" % c)
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


def main():
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
    print("Thanks for playing Asteroids.")


if __name__ == "__main__":
    main()
