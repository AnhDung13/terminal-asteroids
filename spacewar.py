#!/usr/bin/env python3
"""
SPACE WAR - a terminal space shooter with braille-pixel graphics.

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

Run:  python3 spacewar.py
"""

import curses
import locale
import math
import os
import random
import re
import sys
import time
from itertools import groupby

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
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 ".spacewar_state"))

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
        PAL["foe5"] = _mk(153)           # tender - unarmed, and not bold
        PAL["foeshot"] = _mk(120)
        PAL["hot"] = _mk(214, True)      # a rock fragment you have launched
        PAL["mine"] = _mk(196, True)
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
        RAMPS["neb"] = [_mk(183, True), _mk(177), _mk(140), _mk(97),
                        _mk(60)]
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
        PAL["foe5"] = _mk(W)
        PAL["foeshot"] = _mk(G)
        PAL["hot"] = _mk(Y, True)
        PAL["mine"] = _mk(R, True)
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
        RAMPS["neb"] = [_mk(M, True), _mk(M), _mk(M) | curses.A_DIM]


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
        self.shield = False          # salvaged: eats one hit, then gone

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
        if self.shield:
            # A slow-breathing ring, drawn sparse so the hull inside it
            # stays legible.
            rr = r * 1.45 + 0.8 * math.sin(time.time() * 5.0)
            f.arc(self.x, self.y, rr, A("ui_hi"), 5, step=2.4)
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
    # A fragment knocked loose by one of your shots flies HOT for a moment:
    # fast, along the shot, and it hurts whatever hull it meets. Then it
    # cools back into weather. That is what makes a boulder between you and
    # a gunship worth shooting rather than flying round.
    HOT = 1.5              # seconds a kicked fragment stays dangerous
    KICK = 135.0           # px/s it is knocked to
    DMG = {3: 3, 2: 2, 1: 1}   # hull points a hot fragment does, by size

    def __init__(self, x, y, size, scale, vx=None, vy=None, spread=0.3):
        self.x, self.y, self.size = x, y, size
        self.r, base, self.points = self.SPECS[size]
        self.cruise = base * scale       # the speed it settles back to
        if vx is None:
            sp = base * scale * random.uniform(1.0 - spread * 0.5, 1.0 + spread)
            a = random.uniform(0, TAU)
            vx, vy = sp * math.cos(a), sp * math.sin(a)
        self.vx, self.vy = vx, vy
        self.hot = 0.0
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
        if self.hot > 0:
            self.hot = max(0.0, self.hot - dt)
        elif self.vx * self.vx + self.vy * self.vy > (self.cruise * 1.3) ** 2:
            # Cooled off: shed the speed the shot gave it, back to a drift.
            k = 1.0 - min(1.0, 1.6 * dt)
            self.vx *= k
            self.vy *= k
        self.x = (self.x + self.vx * dt) % world[0]
        self.y = (self.y + self.vy * dt) % world[1]
        self.ang = (self.ang + self.spin * dt) % TAU
        self.flash = max(0.0, self.flash - dt)

    def kick(self, vx, vy):
        """Knock it flying along a shot. A fragment becomes a projectile."""
        a = math.atan2(vy, vx) + random.uniform(-0.42, 0.42)
        sp = self.KICK * random.uniform(0.85, 1.15)
        self.vx, self.vy = sp * math.cos(a), sp * math.sin(a)
        self.spin = random.uniform(-4.0, 4.0)
        self.hot = self.HOT
        self.flash = 0.08

    def draw(self, f, att=None):
        if att is None:
            att = (A("flash") if self.flash > 0 else
                   A("hot") if self.hot > 0 else A("ast%d" % self.size))
        pts = [(self.x + d * math.cos(self.ang + a),
                self.y + d * math.sin(self.ang + a))
               for a, d in self.shape]
        f.poly(pts, att, 3)
        for ca, cd, cr in self.craters:
            a = self.ang + ca
            f.arc(self.x + cd * math.cos(a), self.y + cd * math.sin(a),
                  cr, att, 3, step=1.4)
        if self.hot > 0:       # a streak behind a hot fragment
            step = 0.03
            for i in (1, 2, 3):
                f.dot(self.x - self.vx * step * i, self.y - self.vy * step * i,
                      ramp("fire", 0.25 + 0.2 * i), 2)


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
# Every cadence here is quoted against Game.GUN_CD, the ship's own gun, so
# that changing how strong the base gun is moves the whole armoury with it.
WEAPONS = {
    "spread": dict(tag="S", name="SPREAD", col="foe2", ammo=55, cd=0.24,
                   note="a fan of three"),
    "rapid": dict(tag="R", name="RAPID", col="foe1", ammo=150, cd=0.07,
                  note="three times the cadence"),
    "pierce": dict(tag="P", name="LANCE", col="ui_hi", ammo=60, cd=0.20,
                   note="passes through hulls"),
    "homing": dict(tag="H", name="SEEKER", col="foe3", ammo=55, cd=0.28,
                   note="curves onto its target"),
    "gauss": dict(tag="G", name="GAUSS", col="foe4", ammo=26, cd=0.40,
                  note="three hull points a slug"),
}
WEAPON_KINDS = ("spread", "rapid", "pierce", "homing", "gauss")

# The rest of the salvage is not a gun. A shield eats one hit, a bomb is held
# until you need it, a spare ship is a spare ship.
GEAR = {
    "shield": dict(tag="O", name="SHIELD", col="ui_hi", note="absorbs one hit"),
    "bomb": dict(tag="*", name="BOMB", col="warn", note="Z to fire it"),
    "life": dict(tag="+", name="EXTRA SHIP", col="ship", note="one more ship"),
}
# kind -> share, among the drops that are gear rather than a magazine
GEAR_ODDS = (("shield", 0.50), ("bomb", 0.35), ("life", 0.15))
ITEMS = dict(WEAPONS)
ITEMS.update(GEAR)


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
        spec = ITEMS[self.kind]
        att = A(spec["col"])
        r = self.R * (1.0 + 0.10 * math.sin(self.t * 4.0))
        # Magazines tumble as hexagons, gear as diamonds: tell them apart
        # before you are close enough to read the letter.
        n = 6 if self.kind in WEAPONS else 4
        pts = [(self.x + r * math.cos(self.t * 1.5 + i * TAU / n),
                self.y + r * math.sin(self.t * 1.5 + i * TAU / n))
               for i in range(n)]
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

    def draw(self, f, name="star"):
        tw = 0.5 + 0.5 * math.sin(self.ph)
        f.dot(self.x, self.y,
              ramp(name, 0.25 + 0.7 * self.depth - 0.22 * tw), 0)


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

# Tender: the fleet's supply hauler - a long plain hull with a cargo pod
# slung either side, a cab bulkhead, and no guns at all. It runs from you,
# and it leaves if you let it.
_TD_P = [(0.36, -0.34), (0.36, -0.80), (-0.56, -0.80), (-0.56, -0.34)]
TENDER = [
    [(0.98, 0.0), (0.72, -0.28), (-0.78, -0.34), (-0.98, -0.14),
     (-0.98, 0.14), (-0.78, 0.34), (0.72, 0.28), (0.98, 0.0)],
    _TD_P, flip(_TD_P),
    [(-0.10, -0.80), (-0.10, -0.34)], [(-0.10, 0.34), (-0.10, 0.80)],
    [(0.72, -0.28), (0.72, 0.28)],
]
TENDER_ENG = [(-0.98, -0.08), (-0.98, 0.08)]


class Raider:
    """A hostile ship: four classes, four silhouettes, four habits.

    All of them fly to a standoff distance and circle it rather than drifting
    across the screen, so the fight happens around you instead of past you.
    On top of that each class has one thing of its own. An interceptor shoots
    at where you are. A gunship shoots at where you are going to be. A
    marauder breaks orbit every few seconds to run straight at you and then
    peels away. A dreadnought, once it is down to half its hull, throws a full
    ring of fire every few seconds on top of its volleys.

    The fifth class does none of that. A tender carries the fleet's stores:
    it has no gun, it runs from you, and it spools a jump drive as it goes.
    Catch it and it always gives up salvage; let it jump and the next wave
    comes with an extra gunship. It is on the field to make you choose.

    Any gunner that leads its target (gunship, dreadnought) shows where the
    volley will land for a moment before it fires - a faint mark at the aim
    point - so the rule "change course after it shoots" can be learned by
    watching rather than by dying.
    """

    # lead: how much of your motion the gunner allows for - 0 fires at where
    # you are, 1 is a clean intercept on a ship that holds its course.
    SPECS = {
        "scout": dict(r=8.5, hp=1, speed=64.0, cd=1.9, shots=1, jitter=0.26,
                      bsp=78.0, value=150, shape=SCOUT, eng=SCOUT_ENG,
                      keep=46.0, col="foe1", turn=5.0, lead=0.0),
        "gunship": dict(r=12.0, hp=2, speed=46.0, cd=1.7, shots=2, jitter=0.16,
                        bsp=88.0, value=400, shape=GUNSHIP, eng=GUNSHIP_ENG,
                        keep=86.0, col="foe2", turn=3.4, lead=1.0),
        "marauder": dict(r=15.0, hp=11, speed=32.0, cd=1.35, shots=4,
                         jitter=0.13, bsp=80.0, value=2500, shape=MARAUDER,
                         eng=MARAUDER_ENG, keep=104.0, col="foe3",
                         turn=2.4, lead=0.0),
        "dread": dict(r=24.0, hp=28, speed=23.0, cd=1.15, shots=7, jitter=0.10,
                      bsp=74.0, value=12000, shape=DREADNOUGHT,
                      eng=DREADNOUGHT_ENG, keep=134.0, col="foe4",
                      turn=1.7, lead=0.6),
        "tender": dict(r=11.0, hp=3, speed=46.0, cd=9.9, shots=0, jitter=0.0,
                       bsp=1.0, value=600, shape=TENDER, eng=TENDER_ENG,
                       keep=0.0, col="foe5", turn=2.6, lead=0.0),
    }
    BOSSES = ("marauder", "dread")
    ESCAPE = 12.0          # tender: seconds from arrival to its jump, wave 1
    AIM_WARN = 0.3         # a leading gunner marks its aim point this long

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
        # Wave 1 used to open its volleys 30% further apart than the class's
        # own figure, which read as a fleet waiting its turn. It now fires at
        # its quoted gap from the start, and closes to two thirds of it.
        self.cd0 = s["cd"] * (1.00 - 0.35 * diff)
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
        self.lead = s["lead"]
        self.phase, self.phase_t = "orbit", random.uniform(2.5, 4.5)
        self.ring_cd = 1.5         # dread: time to the next ring of fire
        self.raged = False         # dread: has the rage been announced
        self.mark = None           # where the next volley is aimed, if shown
        self.escape = None         # tender: seconds until it jumps out
        if kind == "tender":
            self.phase = "flee"
            self.escape = self.escape0 = self.ESCAPE * (1.0 - 0.25 * diff)

    @staticmethod
    def toward(x1, y1, x2, y2, world):
        """Shortest vector to a point across a wrapping field."""
        w, h = world
        return ((x2 - x1 + w * 0.5) % w - w * 0.5,
                (y2 - y1 + h * 0.5) % h - h * 0.5)

    # Marauder: circle, then a straight run at you, then break away.
    CHARGE, RETREAT = 1.5, 1.1                  # seconds in each
    CHARGE_SPEED, RETREAT_SPEED = 2.3, 1.6      # times cruise
    # Dreadnought, under half hull: a ring of fire every so often.
    RING_EVERY, RING_SHOTS = 3.2, 16

    def _cycle(self, dt):
        self.phase_t -= dt
        if self.phase_t > 0:
            return
        if self.phase == "orbit":
            self.phase, self.phase_t = "charge", self.CHARGE
        elif self.phase == "charge":
            self.phase, self.phase_t = "retreat", self.RETREAT
        else:
            self.phase, self.phase_t = "orbit", random.uniform(3.0, 5.0)

    @property
    def enraged(self):
        return self.kind == "dread" and self.hp * 2 <= self.hp0

    def update(self, dt, world, ship, bullets, sun=None):
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        self.arrive = max(0.0, self.arrive - dt)
        self.mark = None
        speed = self.speed
        if ship is not None:
            dx, dy = self.toward(self.x, self.y, ship.x, ship.y, world)
            d = math.hypot(dx, dy) or 1.0
            ux, uy = dx / d, dy / d
            if self.kind == "marauder":
                self._cycle(dt)
            if self.phase == "flee":
                # Straight away from you, weaving, and the drive spooling.
                wob = 0.55 * math.sin(self.t * 1.3)
                wx, wy = -ux - uy * wob, -uy + ux * wob
                n = math.hypot(wx, wy) or 1.0
                wx, wy = wx / n, wy / n
                if self.arrive <= 0:
                    self.escape -= dt
            elif self.phase == "charge":
                wx, wy, speed = ux, uy, speed * self.CHARGE_SPEED
            elif self.phase == "retreat":
                wx, wy, speed = -ux, -uy, speed * self.RETREAT_SPEED
            else:
                # Close on the standoff ring, then circle it. Weaving keeps
                # the orbit from reading as a perfect, lifeless circle.
                radial = max(-1.0, min(1.0, (d - self.keep) / 46.0))
                tang = self.orbit * (1.0 - abs(radial))
                tang += 0.25 * math.sin(self.t * 1.7 + self.orbit)
                wx, wy = ux * radial - uy * tang, uy * radial + ux * tang
                n = math.hypot(wx, wy) or 1.0
                wx, wy = wx / n, wy / n
            # A gunner faces its target; a hauler faces the way it is going.
            want = math.atan2(wy, wx) if self.phase == "flee" else \
                math.atan2(dy, dx)
        else:
            wx, wy = math.cos(self.ang), math.sin(self.ang)
            want = self.ang
        if sun is not None:
            # Nobody flies into the star on purpose: shove the heading away
            # from it, harder the closer the hull gets.
            sx, sy = self.toward(self.x, self.y, sun.x, sun.y, world)
            ds = math.hypot(sx, sy) or 1.0
            edge = sun.r * 3.2 + self.r
            if ds < edge:
                push = 3.0 * (edge - ds) / edge
                wx -= sx / ds * push
                wy -= sy / ds * push
                n = math.hypot(wx, wy) or 1.0
                wx, wy = wx / n, wy / n
                if self.phase == "flee":
                    want = math.atan2(wy, wx)
        k = min(1.0, 2.4 * dt)
        self.vx += (wx * speed - self.vx) * k
        self.vy += (wy * speed - self.vy) * k
        self.x = (self.x + self.vx * dt) % world[0]
        self.y = (self.y + self.vy * dt) % world[1]
        da = (want - self.ang + math.pi) % TAU - math.pi
        self.ang = (self.ang + da * min(1.0, self.turn * dt)) % TAU

        self.cd -= dt
        if ship is None or self.arrive > 0 or not self.shots:
            return True
        if self.lead > 0 and self.cd <= self.AIM_WARN:
            # The tell: where the rounds are going, shown before they go.
            t = d / self.bsp * self.lead
            self.mark = ((ship.x + ship.vx * t) % world[0],
                         (ship.y + ship.vy * t) % world[1])
        if self.cd <= 0:
            self.cd = self.cd0 * random.uniform(0.85, 1.25)
            self.volley(bullets, world, self.aim(dx, dy, d, ship))
        if self.enraged:
            self.ring_cd -= dt
            if self.ring_cd <= 0:
                self.ring_cd = self.RING_EVERY
                self.ring(bullets, world)
        return True

    def aim(self, dx, dy, d, ship):
        """The bearing for a volley: at the ship, or ahead of it by `lead`."""
        if self.lead <= 0:
            return math.atan2(dy, dx)
        t = d / self.bsp * self.lead          # the round's flight time
        return math.atan2(dy + ship.vy * t, dx + ship.vx * t)

    def volley(self, bullets, world, base):
        n = self.shots
        step = 0.17 if not self.boss else 0.15
        muzzle = self.r * (1.05 if self.boss else 0.9)
        ox = self.x + muzzle * math.cos(self.ang)
        oy = self.y + muzzle * math.sin(self.ang)
        for i in range(n):
            a = base + (i - (n - 1) * 0.5) * step
            a += random.uniform(-self.jitter, self.jitter)
            self.shoot(bullets, world, ox, oy, a, self.bsp)

    def ring(self, bullets, world):
        """A full circle of slower rounds, from all round the hull. It is
        dodged by moving, not by luck: the gaps are wide, and they rotate."""
        off = self.t * 0.7
        for i in range(self.RING_SHOTS):
            a = off + i * TAU / self.RING_SHOTS
            self.shoot(bullets, world, self.x + self.r * math.cos(a),
                       self.y + self.r * math.sin(a), a, self.bsp * 0.72)

    def shoot(self, bullets, world, ox, oy, a, sp):
        bullets.append(Bullet(ox % world[0], oy % world[1],
                              sp * math.cos(a), sp * math.sin(a),
                              Bullet.reach(world, sp), hostile=True))

    def hit(self, dmg=1):
        self.hp -= dmg
        self.flash = 0.09
        return self.hp <= 0

    def draw(self, f):
        if self.mark is not None:
            # A faint cross where the volley will land. Dim, under
            # everything else: a hint, not a target reticle.
            mx, my = self.mark
            att = A("dim")
            for o in (2, 3):
                f.dot(mx - o, my, att, 2)
                f.dot(mx + o, my, att, 2)
                f.dot(mx, my - o, att, 2)
                f.dot(mx, my + o, att, 2)
        if self.arrive > 0 and int(self.arrive * 14) % 2 == 0:
            return
        att = A("flash") if self.flash > 0 else A(self.col)
        draw_hull(f, self.x, self.y, self.ang, self.r, self.shape, att, 4)
        spool = 0.0
        if self.escape is not None:
            # The jump drive spooling up: a ring that fills in as the charge
            # builds, and blinks over the last seconds. Read it, and decide.
            spool = 1.0 - max(0.0, self.escape) / self.escape0
            if self.escape > 2.5 or int(self.escape * 8) % 2:
                f.arc(self.x, self.y, self.r * 1.45,
                      ramp("shock", 0.85 - 0.75 * spool), 3,
                      step=3.6 - 2.4 * spool)
        # Engine bloom: a short flare trailing each nozzle, flickering.
        ca, sa = math.cos(self.ang) * self.r, math.sin(self.ang) * self.r
        bx, by = -math.cos(self.ang), -math.sin(self.ang)
        for px, py in self.eng:
            ex = self.x + px * ca - py * sa
            ey = self.y + px * sa + py * ca
            ln = self.r * random.uniform(0.12, 0.30) * (1.0 + 1.5 * spool)
            f.line(ex, ey, ex + bx * ln, ey + by * ln,
                   ramp("fire", random.uniform(0.15, 0.55)), 4)
        if self.boss:      # a slow sweeping sensor blip along the spine
            ph = 0.5 + 0.5 * math.sin(self.t * 2.2)
            f.dot(self.x + (0.55 * ph + 0.1) * ca,
                  self.y + (0.55 * ph + 0.1) * sa, A("flash"), 5)


# ==========================================================================
# Sectors
# ==========================================================================
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
        dx, dy = Raider.toward(x, y, self.x, self.y, world)
        d2 = dx * dx + dy * dy
        if d2 < 1.0:
            return 0.0, 0.0
        d = math.sqrt(d2)
        a = min(self.MAX_PULL, self.G / d2)
        return a * dx / d, a * dy / d

    def inside(self, x, y, world):
        dx, dy = Raider.toward(x, y, self.x, self.y, world)
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
        self.exact_keys = False    # terminal reports key releases (kitty)
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
        if self.sun is not None:
            self.sun.fit(self.world)
        self.stars = [Star(self.world) for _ in range(self.star_count())]

    def movers(self):
        objs = (self.asteroids + self.bullets + self.particles +
                self.shocks + self.debris + self.pops + self.foes +
                self.pickups + self.mines)
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
        k = 1.25 if self.cur == "debris" else 1.0
        return self.lerp(0.60, 1.80, self.diff()) * k

    def rock_count(self):
        # Rocks are scenery now - something to dodge while you fight, not the
        # objective. A handful, and never a field to grind through - except
        # in a debris field, where the field is the point.
        n = min(2 + self.level // 3, 6)
        if self.cur == "debris":
            n = min(n * 2 + 2, 14)
        return n

    ROCK_INFLOW = 4.0       # debris field: seconds between fresh boulders

    def mine_count(self):
        return min(4 + self.level // 10, 9) if self.cur == "mines" else 0

    # -- sectors ----------------------------------------------------------
    def sector_index(self, level=None):
        lv = self.level if level is None else level
        return max(0, (lv - 1) // SECTOR_WAVES)

    def sector(self, level=None):
        i = self.sector_index(level)
        if i == 0:
            return "open"
        return self.sector_order[(i - 1) % len(self.sector_order)]

    def jump_sector(self, name):
        """The fleet has jumped; so have you. New sky, new rule. Salvage
        comes along - it is cargo now - but the rocks and the mines stay
        where they were."""
        self.cur = name
        self.asteroids = []
        self.mines = []
        self.bullets = [b for b in self.bullets if not b.hostile]
        self.sun = Sun(self.world) if name == "star" else None
        w, h = self.world
        self.shocks.append(Shock(w / 2, h / 2, 2, max(w, h) * 0.7, 0.9))
        beep()

    def vis(self):
        """Sensor range in a nebula: anything further off is a blip."""
        return max(48.0, 0.36 * math.hypot(*self.world))

    def fogged(self, x, y):
        if self.cur != "nebula" or self.ship is None:
            return False
        return self.wrap_dist(self.ship.x, self.ship.y, x, y) > self.vis()

    MAX_FOES = 7            # escorts on screen at once; a boss is extra

    def escorts(self):
        return sum(1 for f in self.foes if not f.boss)

    def is_boss_wave(self):
        return self.level % 10 == 0

    def is_mini_wave(self):
        return self.level % 5 == 0 and not self.is_boss_wave()

    TENDER_EVERY = 3        # a tender rides with every third ordinary wave

    def roster(self):
        """The ships that will arrive this wave, in the order they arrive.

        Every tender that got away is paid for here: one more gunship in the
        escort, on whatever wave comes next.
        """
        lv = self.level
        if self.is_boss_wave():
            out = ["dread"] + ["gunship"] * (3 + self.debt) + ["scout"] * 4
        elif self.is_mini_wave():
            out = ["marauder"] + ["gunship"] * (2 + self.debt) + ["scout"] * 4
        else:
            scouts = min(3 + lv // 2, 10)
            guns = min(lv // 3, 5) + self.debt
            out = ["scout"] * scouts + ["gunship"] * guns
            random.shuffle(out)
            if lv >= self.TENDER_EVERY and lv % self.TENDER_EVERY == 0:
                out.insert(len(out) // 2, "tender")     # mid-wave, never first
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
        self.mines = []
        self.queue = []            # classes still to arrive this wave
        self.spawn_cd = 0.0
        self.rock_cd = 0.0
        self.ship = None
        self.break_t = None        # the breath between waves, while it lasts
        self.card = None           # the card shown during it
        self.wave_t = 0.0          # the wave's own ledger, for that card
        self.wave_shots0 = self.wave_hits0 = 0
        self.wave_kills = self.wave_lost = 0
        self.wave_peak = 1
        self.cur = "open"          # the sector you are in
        self.sun = None
        self.sector_order = list(SECTOR_CYCLE)
        random.shuffle(self.sector_order)
        self.clock = 0.0
        self.fire_cd = 0.0
        self.weapon = None         # None = the ship's own gun
        self.ammo = 0
        self.bombs = 0
        self.combo = 0             # ships downed on the current chain
        self.combo_t = 0.0         # time left before the chain lapses
        if full:
            self.score = 0
            self.lives = 3
            self.level = 0
            self.debt = 0          # tenders that jumped out unpaid-for
            self.next_extra = 20000
            self.shots = self.hits = 0
            self.best_combo = 0

    def start_game(self):
        self.reset(full=True)
        self.state = "play"
        self.spawn_wave()
        self.spawn_ship()
        self.flash("%s FLIGHT" % self.mode.upper(), 1.6)

    def spawn_point(self):
        w, h = self.world
        if self.sun is None:
            return w / 2, h / 2
        # Not in the star: above it, outside the pull that matters.
        return w / 2, (h / 2 - max(h * 0.30, self.sun.r * 4.0)) % h

    def spawn_ship(self):
        x, y = self.spawn_point()
        self.ship = Ship(x, y)
        if self.level <= 2:
            self.ship.invuln = 3.2
        self.shocks.append(Shock(x, y, 26, 5, 0.5))

    def clear_spot(self, margin):
        """A random point at least `margin` from the centre and from you."""
        w, h = self.world
        for _ in range(40):
            x, y = random.uniform(0, w), random.uniform(0, h)
            if self.wrap_dist(x, y, w / 2, h / 2) < margin:
                continue
            if self.ship and self.wrap_dist(x, y, self.ship.x,
                                            self.ship.y) < margin:
                continue
            break
        return x, y

    def edge_rock(self):
        """A fresh boulder drifting in off an edge, in a debris field."""
        w, h = self.world
        if random.random() < 0.5:
            x, y = random.uniform(0, w), random.choice((1.0, h - 2.0))
        else:
            x, y = random.choice((1.0, w - 2.0)), random.uniform(0, h)
        return Asteroid(x, y, 3, self.rock_scale(), spread=0.4)

    def spawn_wave(self):
        self.level += 1
        jumped = self.sector() != self.cur
        if jumped:
            self.jump_sector(self.sector())
        d = self.diff()
        scale, spread = self.rock_scale(), 0.15 + 0.35 * d
        for _ in range(max(0, self.rock_count() - len(self.asteroids))):
            x, y = self.clear_spot(60)
            self.asteroids.append(Asteroid(x, y, 3, scale, spread=spread))
        for _ in range(max(0, self.mine_count() - len(self.mines))):
            self.mines.append(Mine(*self.clear_spot(50)))
        self.queue = self.roster()
        self.debt = 0
        self.spawn_cd = 1.4
        self.wave_t = 0.0
        self.wave_shots0, self.wave_hits0 = self.shots, self.hits
        self.wave_kills = self.wave_lost = 0
        self.wave_peak = 1
        if self.state != "title":
            if jumped:
                self.flash("SECTOR %d  -  %s" % (self.sector_index() + 1,
                                                 SECTORS[self.cur]["name"]),
                           2.6)
            elif self.is_boss_wave():
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

    def add_score(self, pts, x=None, y=None, attr=None, tag=""):
        if self.state == "title":
            return
        self.score += pts
        if x is not None:
            self.pops.append(Pop(x, y, "+%d%s" % (pts, tag),
                                 attr or A("ui_hi")))
        if self.score >= self.next_extra:
            self.next_extra += 20000
            self.lives += 1
            self.flash("EXTRA SHIP", 1.6)
            beep()

    # -- the chain --------------------------------------------------------
    # Every ship downed extends the chain, and the chain sets the multiplier
    # on everything you score. Lose a ship, or go COMBO_WINDOW seconds
    # without a kill, and it is gone. That is the reason to press the attack
    # rather than snipe from the far side of the field.
    COMBO_WINDOW = 5.0
    COMBO_STEP = 3             # kills per multiplier step
    COMBO_MAX = 5

    def mult(self):
        return min(1 + self.combo // self.COMBO_STEP, self.COMBO_MAX)

    def chain(self):
        was = self.mult()
        self.combo += 1
        self.combo_t = self.COMBO_WINDOW
        self.best_combo = max(self.best_combo, self.combo)
        if self.mult() > was:
            self.flash("CHAIN  x%d" % self.mult(), 1.0)

    def award(self, base, x, y, attr):
        m = self.mult()
        self.add_score(base * m, x, y, attr, " x%d" % m if m > 1 else "")

    @staticmethod
    def loot():
        """What a wreck gives up: usually a magazine, sometimes gear."""
        if random.random() < 0.70:
            return random.choice(WEAPON_KINDS)
        r = random.random()
        for kind, share in GEAR_ODDS:
            r -= share
            if r < 0:
                return kind
        return GEAR_ODDS[-1][0]

    # -- actions ----------------------------------------------------------
    # The ship's own gun: five rounds a second. It runs on its own and never
    # runs out, so this one number is most of how strong you are - a faster
    # gun and the fleet stops being a threat, a slower one and a wave is a
    # chore. Every magazine is quoted against it.
    GUN_CD = 0.20

    def fire(self):
        s = self.ship
        if s is None or self.fire_cd > 0:
            return
        spec = WEAPONS[self.weapon] if self.weapon else None
        cap = 18 if spec else 8
        if sum(1 for b in self.bullets if not b.hostile) >= cap:
            return
        self.fire_cd = spec["cd"] if spec else self.GUN_CD
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
            self.shots += len(angles)      # a fan is three shots, not one
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
        for _ in range(24):
            x = random.uniform(0, self.world[0])
            y = random.uniform(0, self.world[1])
            if self.sun is not None and self.wrap_dist(
                    x, y, self.sun.x, self.sun.y) < self.sun.r * 4.0:
                continue
            if any(self.wrap_dist(x, y, m.x, m.y) < Mine.TRIG + 12.0
                   for m in self.mines):
                continue
            break
        s.x, s.y = x, y
        s.vx = s.vy = 0.0
        s.invuln = max(s.invuln, 0.8)
        s.warp_cd = 3.0
        self.shocks.append(Shock(s.x, s.y, 3, 24, 0.4))
        self.burst(s.x, s.y, 14, 70, 0.45)

    BOMB_DMG = 4               # kills any escort outright, dents a boss
    BOMB_MAX = 3

    def bomb(self):
        """Spend a held bomb: every hostile round gone, every hull hurt."""
        s = self.ship
        if s is None or self.bombs <= 0 or self.state != "play":
            return
        self.bombs -= 1
        self.bullets = [b for b in self.bullets if not b.hostile]
        self.shocks.append(Shock(s.x, s.y, 4, max(self.world) * 0.8, 0.9))
        self.shocks.append(Shock(s.x, s.y, 2, 40, 0.4))
        self.shake = max(self.shake, 0.4)
        self.flash("BOMB", 0.9)
        beep()
        for foe in list(self.foes):
            if foe.arrive > 0:
                continue
            if foe.hit(self.BOMB_DMG):
                self.kill_foe(foe)
            else:
                self.burst(foe.x, foe.y, 8, 50, 0.3)
                self.rage_check(foe)

    def hurt(self):
        """The ship takes a hit. A shield eats it; otherwise the ship is lost.

        Returns True if the ship was destroyed. Callers check invuln first.
        """
        s = self.ship
        if s.shield:
            s.shield = False
            s.invuln = max(s.invuln, 1.0)
            self.shocks.append(Shock(s.x, s.y, 8, 30, 0.4))
            self.burst(s.x, s.y, 16, 70, 0.4)
            self.shake = max(self.shake, 0.15)
            self.flash("SHIELD DOWN", 1.0)
            return False
        self.kill_ship()
        return True

    def rage_check(self, foe):
        """Announce a dreadnought crossing into its second, angrier half."""
        if foe in self.foes and foe.enraged and not foe.raged:
            foe.raged = True
            self.flash("DREADNOUGHT ENRAGED", 1.6)
            self.shocks.append(Shock(foe.x, foe.y, foe.r, foe.r * 3.0, 0.5))
            beep()

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
        self.clock += dt
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
            for m in self.mines:
                m.update(dt, self.world)
            if self.sun is not None:
                self.sun.update(dt)
            for foe in self.foes:
                foe.update(dt, self.world, None, self.bullets, self.sun)
            for b in self.bullets:
                b.update(dt, self.world)
            self.bullets = [b for b in self.bullets if b.life > 0]
            self.gravity(dt)
            if self.timer <= 0:
                if self.lives <= 0:
                    self.end_game()
                else:
                    self.state = "play"
                    self.spawn_ship()
            return

        # ---- playing ----
        if self.break_t is None:
            self.wave_t += dt
        if self.combo:
            self.combo_t -= dt
            if self.combo_t <= 0:
                self.combo = 0          # went quiet: the chain lapses
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
        for m in self.mines:
            m.update(dt, self.world)
        if self.sun is not None:
            self.sun.update(dt)
        for b in self.bullets:
            b.update(dt, self.world)
            if b.kind == "homing" and not b.hostile:
                self.home(b, dt)
        self.bullets = [b for b in self.bullets if b.life > 0]
        self.gravity(dt)
        if self.cur == "debris":
            self.rock_cd -= dt
            if self.rock_cd <= 0 and len(self.asteroids) < self.rock_count():
                self.rock_cd = self.ROCK_INFLOW
                self.asteroids.append(self.edge_rock())

        self.spawn_cd -= dt
        if (self.queue and self.spawn_cd <= 0 and
                self.escorts() < self.MAX_FOES):
            self.spawn_foe(self.queue.pop(0))
            self.spawn_cd = self.spawn_gap()
        for foe in self.foes:
            foe.update(dt, self.world, self.ship, self.bullets, self.sun)
        for foe in list(self.foes):
            if foe.escape is not None and foe.escape <= 0:
                self.escape_foe(foe)

        self.collisions()
        # The wave is the fleet. When it is gone there is a breath - and the
        # card on the wave just fought - and then the next one. Leftover
        # rocks drift on into it.
        if not self.foes and not self.queue:
            if self.break_t is None:
                self.begin_break()
            else:
                self.break_t -= dt
                if self.break_t <= 0:
                    self.break_t = None
                    self.spawn_wave()

    BREAK = 2.2            # seconds of quiet between waves
    BREAK_JUMP = 4.0       # longer after a boss: the jump drive charging

    def begin_break(self):
        """The fleet is gone. A breath, and a card on the wave just fought."""
        jump = self.is_boss_wave()
        self.break_t = self.BREAK_JUMP if jump else self.BREAK
        shots = self.shots - self.wave_shots0
        hits = self.hits - self.wave_hits0
        acc = 100.0 * hits / shots if shots else 0.0
        lines = ["WAVE %d CLEAR" % self.level,
                 "%.1fs   %d ships   %.0f%% hits   chain x%d"
                 % (self.wave_t, self.wave_kills, acc, self.wave_peak)]
        if self.wave_lost:
            lines.append("· %d ship%s lost" % (self.wave_lost,
                                               "" if self.wave_lost == 1
                                               else "s"))
        if jump:
            nxt = self.sector(self.level + 1)
            lines += ["", "JUMP DRIVE CHARGING",
                      "SECTOR %d  %s" % (self.sector_index(self.level + 1) + 1,
                                         SECTORS[nxt]["name"]),
                      "· " + SECTORS[nxt]["note"]]
        self.card = lines

    ARCADE_DRIFT = 0.55    # arcade: the star's pull, as a drift on the hull

    def gravity(self, dt):
        """The star's pull on everything that moves, and its price."""
        sun = self.sun
        if sun is None:
            return
        w = self.world
        for a in list(self.asteroids):
            ax, ay = sun.pull(a.x, a.y, w)
            a.vx += ax * dt
            a.vy += ay * dt
            if sun.inside(a.x, a.y, w):
                self.asteroids.remove(a)
                self.flare(a.x, a.y, a.r)
        for b in list(self.bullets):
            ax, ay = sun.pull(b.x, b.y, w)
            b.vx += ax * dt
            b.vy += ay * dt
            if sun.inside(b.x, b.y, w):
                self.bullets.remove(b)
        for pk in list(self.pickups):
            ax, ay = sun.pull(pk.x, pk.y, w)
            pk.vx += ax * dt * 0.5
            pk.vy += ay * dt * 0.5
            if sun.inside(pk.x, pk.y, w):
                self.pickups.remove(pk)
                self.flare(pk.x, pk.y, Pickup.R)
        for foe in list(self.foes):
            if foe.arrive > 0:
                continue
            ax, ay = sun.pull(foe.x, foe.y, w)
            foe.vx += ax * dt * 0.6            # engines fight some of it
            foe.vy += ay * dt * 0.6
            if sun.inside(foe.x, foe.y, w):
                self.kill_foe(foe, drops=False)  # you may well have put it there
        s = self.ship
        if s is None:
            return
        ax, ay = sun.pull(s.x, s.y, w)
        if self.mode == "classic":
            s.vx += ax * dt
            s.vy += ay * dt
        else:
            # Arcade flies at a commanded velocity, so a push on that
            # velocity is undone within a few frames. Drag the hull instead:
            # the star is a current you fly against.
            s.x = (s.x + ax * self.ARCADE_DRIFT * dt) % w[0]
            s.y = (s.y + ay * self.ARCADE_DRIFT * dt) % w[1]
        if s.invuln <= 0 and sun.inside(s.x, s.y, w):
            if not self.hurt():                # the shield took it: thrown clear
                dx, dy = Raider.toward(sun.x, sun.y, s.x, s.y, w)
                d = math.hypot(dx, dy) or 1.0
                s.x = (sun.x + dx / d * sun.r * 4.0) % w[0]
                s.y = (sun.y + dy / d * sun.r * 4.0) % w[1]
                s.vx = s.vy = 0.0

    def flare(self, x, y, r):
        """Something fell into the star."""
        self.burst(x, y, int(6 + r), 40 + r * 2, 0.4)
        self.shocks.append(Shock(x, y, 2, r * 2.0, 0.3))

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
                    self.split(a, kick=(b.vx, b.vy))
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
                # Rocks are cover: a round that meets one stops there. Put a
                # boulder between you and a gunship and it has earned its
                # place on the field.
                for a in self.asteroids:
                    if self.wrap_dist(b.x, b.y, a.x, a.y) < a.r:
                        self.bullets.remove(b)
                        a.flash = 0.06
                        self.burst(b.x, b.y, 2, 26, 0.15)
                        break
                continue
            for foe in list(self.foes):          # ships first: they are the
                if foe.arrive > 0:               # point of the wave now
                    continue
                if b.spent is not None and foe in b.spent:
                    continue
                if self.wrap_dist(b.x, b.y, foe.x, foe.y) < foe.r:
                    # One shot scores one hit, however many hulls a lance
                    # threads - or accuracy could read over 100%.
                    if b.spent is None:
                        self.bullets.remove(b)
                        self.hits += 1
                    else:
                        if not b.spent:
                            self.hits += 1
                        b.spent.add(foe)         # a lance carries on through
                    if foe.hit(b.dmg):
                        self.kill_foe(foe)
                    else:
                        self.burst(b.x, b.y, 3, 34, 0.18)
                        self.rage_check(foe)
                    break
            else:
                for a in list(self.asteroids):
                    if self.wrap_dist(b.x, b.y, a.x, a.y) < a.r:
                        self.split(a, kick=(b.vx, b.vy))
                        if b in self.bullets:
                            self.bullets.remove(b)
                        if not b.spent:          # None or empty: first hit
                            self.hits += 1
                        break

        # A hot fragment is your round now: it hurts the first hull it meets.
        for a in list(self.asteroids):
            if a.hot <= 0:
                continue
            for foe in list(self.foes):
                if foe.arrive > 0:
                    continue
                if self.wrap_dist(a.x, a.y, foe.x, foe.y) < a.r + foe.r * 0.8:
                    self.smash(a, foe)
                    break

        # Mines: a shot of yours, or any hull too close, sets one off.
        for m in list(self.mines):
            tripped = False
            for b in list(self.bullets):
                if b.hostile:
                    continue
                if self.wrap_dist(b.x, b.y, m.x, m.y) < Mine.R + 1.5:
                    self.bullets.remove(b)
                    if not b.spent:
                        self.hits += 1
                    tripped = True
                    break
            s = self.ship
            if (not tripped and s is not None and s.invuln <= 0 and
                    self.wrap_dist(s.x, s.y, m.x, m.y) <
                    Mine.TRIG + Ship.RADIUS):
                tripped = True
            if not tripped:
                for foe in self.foes:
                    if foe.arrive <= 0 and self.wrap_dist(
                            foe.x, foe.y, m.x, m.y) < Mine.TRIG + foe.r * 0.6:
                        tripped = True
                        break
            if tripped and m in self.mines:
                self.detonate(m)

        s = self.ship
        if s is None:
            return
        for pk in list(self.pickups):
            if self.wrap_dist(s.x, s.y, pk.x, pk.y) < Pickup.R + Ship.RADIUS:
                self.pickups.remove(pk)
                self.collect(pk.kind)
                self.shocks.append(Shock(pk.x, pk.y, 2, 20, 0.35))
                self.burst(pk.x, pk.y, 10, 55, 0.4)
        for a in list(self.asteroids):
            if self.wrap_dist(s.x, s.y, a.x, a.y) < a.r + Ship.RADIUS:
                if s.invuln <= 0:
                    self.hurt()
                    self.split(a, award=False)
                return
        for foe in list(self.foes):
            if foe.arrive > 0:
                continue
            if self.wrap_dist(s.x, s.y, foe.x, foe.y) < foe.r * 0.8 + \
                    Ship.RADIUS:
                if s.invuln <= 0:
                    self.hurt()
                    # Ramming a capital ship hurts it; it does not kill it.
                    for _ in range(3 if foe.boss else foe.hp):
                        if foe.hit():
                            self.kill_foe(foe, award=False)
                            break
                    self.rage_check(foe)
                return
        for b in list(self.bullets):
            if b.hostile and self.wrap_dist(s.x, s.y, b.x, b.y) < Ship.RADIUS + 2:
                self.bullets.remove(b)
                if s.invuln <= 0:
                    self.hurt()
                return

    def detonate(self, m):
        """A mine goes off. Everything inside the blast pays - the fleet's
        hulls and yours alike - and a mine inside it goes off too."""
        self.mines.remove(m)
        self.shocks.append(Shock(m.x, m.y, 3, Mine.BLAST * 1.15, 0.5))
        self.shocks.append(Shock(m.x, m.y, 2, 14, 0.25))
        self.burst(m.x, m.y, 26, 90, 0.5)
        self.shake = max(self.shake, 0.22)
        for foe in list(self.foes):
            if foe.arrive > 0:
                continue
            if self.wrap_dist(foe.x, foe.y, m.x, m.y) < Mine.BLAST + foe.r * 0.5:
                if foe.hit(Mine.DMG):
                    self.kill_foe(foe)
                else:
                    self.burst(foe.x, foe.y, 6, 44, 0.25)
                    self.rage_check(foe)
        s = self.ship
        if (s is not None and s.invuln <= 0 and
                self.wrap_dist(s.x, s.y, m.x, m.y) < Mine.BLAST):
            self.hurt()
        for other in list(self.mines):
            if other in self.mines and self.wrap_dist(
                    other.x, other.y, m.x, m.y) < Mine.BLAST * 0.8:
                self.detonate(other)

    def collect(self, kind):
        """Take a pickup aboard."""
        spec = ITEMS[kind]
        if kind in WEAPONS:
            # A fresh magazine of the same type tops it up rather than
            # resetting it, so a lucky double drop is not wasted.
            self.ammo = (self.ammo if self.weapon == kind else 0)
            self.ammo += spec["ammo"]
            self.weapon = kind
            self.fire_cd = 0.0
            self.flash(spec["name"], 1.1)
        elif kind == "shield":
            self.ship.shield = True
            self.flash("SHIELD UP", 1.1)
        elif kind == "bomb":
            self.bombs = min(self.BOMB_MAX, self.bombs + 1)
            self.flash("BOMB  x%d" % self.bombs, 1.1)
        elif kind == "life":
            self.lives += 1
            self.flash("EXTRA SHIP", 1.4)
            beep()

    def split(self, a, award=True, kick=None):
        """Break a rock in two. `kick` is the shot's velocity, if a shot did
        it: the fragments then fly off along it, hot."""
        if award:      # rocks ride the multiplier but do not extend the chain
            self.award(a.points, a.x, a.y, A("ast%d" % a.size))
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
                if kick is not None:
                    child.kick(*kick)
                self.asteroids.append(child)

    def smash(self, a, foe):
        """A hot fragment meets a hull: the rock shatters, the hull pays."""
        self.award(a.points, a.x, a.y, A("hot"))
        self.burst(a.x, a.y, 8 + 6 * a.size, 40 + 20 * a.size, 0.45)
        self.shocks.append(Shock(a.x, a.y, a.r * 0.5, a.r * 2.8, 0.3))
        self.shake = max(self.shake, 0.08 + 0.04 * a.size)
        self.asteroids.remove(a)
        if foe.hit(Asteroid.DMG[a.size]):
            self.kill_foe(foe)
        else:
            self.burst(foe.x, foe.y, 6, 44, 0.25)
            self.rage_check(foe)

    DROP = {"scout": 0.10, "gunship": 0.26}
    TENDER_DROPS = 2

    def escape_foe(self, foe):
        """A tender's jump drive fires: it is gone, and the debt is booked."""
        self.foes.remove(foe)
        self.debt += 1
        self.shocks.append(Shock(foe.x, foe.y, foe.r * 1.5, 2, 0.3))
        self.shocks.append(Shock(foe.x, foe.y, 3, foe.r * 4.0, 0.5))
        self.burst(foe.x, foe.y, 16, 60, 0.4)
        self.flash("TENDER ESCAPED  -  ESCORT REINFORCED", 1.8)

    def kill_foe(self, foe, award=True, drops=True):
        if foe not in self.foes:
            return
        self.foes.remove(foe)
        if award:
            self.chain()
            self.award(foe.value, foe.x, foe.y, A(foe.col))
            self.wave_kills += 1
            self.wave_peak = max(self.wave_peak, self.mult())
            # Wrecks give up their salvage. A capital ship gives up several,
            # and a tender - it is nothing but cargo - always does.
            n = ((3 if foe.kind == "dread" else 2) if foe.boss else
                 self.TENDER_DROPS if foe.kind == "tender" else
                 1 if random.random() < self.DROP.get(foe.kind, 0.0) else 0)
            for _ in range(n if drops else 0):
                self.pickups.append(Pickup(foe.x, foe.y, self.loot()))
        n = int(18 + foe.r * 2.4)
        self.burst(foe.x, foe.y, n, 70 + foe.r * 3.0, 0.7 + foe.r * 0.03)
        self.shocks.append(Shock(foe.x, foe.y, foe.r * 0.4, foe.r * 3.2,
                                 0.4 + foe.r * 0.012))
        self.shake = max(self.shake, 0.14 + foe.r * 0.012)
        if foe.boss:
            self.shocks.append(Shock(foe.x, foe.y, 2, foe.r * 5.5, 0.9))
            self.flash("%s DOWN" % ("DREADNOUGHT" if foe.kind == "dread"
                                    else "MARAUDER"), 2.0)
            beep()
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
        # The magazine stays with you. Losing a ship is punishment enough,
        # and a fresh ship with an empty gun is a second death waiting.
        self.combo = 0                        # the chain does not survive it
        self.lives -= 1
        self.wave_lost += 1
        beep()
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
        self.render()
        self.screen.blit(stdscr)

    def render(self):
        """Composite the whole frame into the screen buffer."""
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

        # In a nebula anything past sensor range is a blip: the fleet a
        # blinking dot in its own colour, its rounds the faintest speck,
        # rocks a dim outline. Your own shots you can always see.
        fog = (self.cur == "nebula" and self.ship is not None and
               self.state != "title")
        vis = self.vis()

        def far(o):
            return fog and self.wrap_dist(self.ship.x, self.ship.y,
                                          o.x, o.y) > vis

        neb = "neb" if self.cur == "nebula" else "star"
        for st in self.stars:
            st.draw(f, neb)
        if self.sun is not None:
            self.sun.draw(f)
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
            a.draw(f, A("frame") if far(a) else None)
        for m in self.mines:
            m.draw(f)
        for pk in self.pickups:
            if far(pk):
                f.dot(pk.x, pk.y, A("dim"), 3)
            else:
                pk.draw(f)
        blink = int(self.clock * 3) % 2
        for foe in self.foes:
            if far(foe):
                if blink:
                    f.dot(foe.x, foe.y, A(foe.col), 3)
                    f.dot(foe.x + 1, foe.y, A(foe.col), 3)
            else:
                foe.draw(f)
        for b in self.bullets:
            if b.hostile and far(b):
                f.dot(b.x, b.y, A("frame"), 3)
            else:
                b.draw(f)
        if fog:            # the edge of what you can see
            f.arc(self.ship.x, self.ship.y, vis, A("frame"), 0, step=7.0)
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
        elif (self.state == "play" and self.break_t is not None and
              self.card and (self.break_t > 0.35 or
                             int(self.break_t * 14) % 2)):
            # The wave card sits low, clear of the banner line.
            y0 = sc.h * 2 // 3 - len(self.card) // 2
            y0 = max(2, min(y0, sc.h - len(self.card) - 4))
            self.panel(sc, self.card, y0=y0)

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
        if self.combo and x + 12 < w - 30:
            # The chain: its multiplier, and how long it has left to live.
            m = self.mult()
            cells = 4
            full = int(round(cells * self.combo_t / self.COMBO_WINDOW))
            full = max(0, min(cells, full))
            tag = "x%d %s" % (m, BAR_FULL * full + BAR_EMPTY * (cells - full))
            sc.text(x, 0, " " + tag + " ", A("accent") if m > 1 else A("dim"))
            x += len(tag) + 2
        boss = next((f for f in self.foes if f.boss), None)
        left_over = len(self.foes) + len(self.queue)
        mid = "WAVE %d" % self.level
        if w > 72 and self.cur != "open":
            mid += " · " + SECTORS[self.cur]["name"]
        if w > 56:
            mid += "  " + ("▾" * min(left_over, 12) if left_over else "CLEAR")
        if x + len(mid) + 6 < w - 16:
            sc.text((w - len(mid)) // 2 - 1, 0, " " + mid + " ", A("accent"))
        if boss is not None and w > 64:
            self.boss_bar(sc, boss)
        elif w > 64:
            tender = next((f for f in self.foes if f.escape is not None), None)
            if tender is not None:
                self.tender_bar(sc, tender)
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
        gear = []
        if self.bombs:
            gear.append(("BOMB " + "*" * self.bombs, A("warn")))
        if s is not None and s.shield:
            gear.append(("SHIELD", A("ui_hi")))
        for tag, attr in gear:
            if left + len(tag) + 2 < self.sw - 26:
                sc.text(left, y, " %s " % tag, attr)
                left += len(tag) + 2
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
             "  X warp  Z bomb  M model  P pause  Q quit"
             if self.mode == "arcade" else
             "←→ turn  ↑ thrust  guns automatic  X warp  Z bomb"
             "  M model  Q quit"),
            ("↑↓←→ fly  YUBN diagonal  auto guns  X warp  Z bomb  Q quit"
             if self.mode == "arcade" else
             "←→ turn  ↑ thrust  auto guns  X warp  Z bomb  Q quit"),
            "FLY · WARP · BOMB",
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

    def tender_bar(self, sc, tender):
        """How close the tender is to jumping out - same line as a boss's
        hull, since a wave never has both."""
        w = self.sw
        cells = max(8, min(20, w // 6))
        full = int(round(cells * (1.0 - max(0.0, tender.escape) /
                                  tender.escape0)))
        bar = BAR_FULL * full + BAR_EMPTY * (cells - full)
        s = " TENDER JUMP %s " % bar
        x = max(1, (w - len(s)) // 2)
        late = tender.escape < 2.5 and int(tender.escape * 8) % 2 == 0
        sc.text(x, 1, s, A("warn") if late else A(tender.col))

    def title_bars(self, sc):
        y = self.sh - 1
        tag = " a t t r a c t   m o d e "
        if len(tag) + 6 < self.sw:
            sc.text((self.sw - len(tag)) // 2, y, tag, A("dim"))
        # Whether the terminal tells us about key releases, or we guess.
        keys = " KEYS %s " % ("exact" if self.exact_keys else "inferred")
        if len(tag) + 2 * len(keys) + 8 < self.sw:
            sc.text(2, y, keys, A("ui_hi") if self.exact_keys else A("dim"))

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

    def panel(self, sc, lines, title_attr=None, y0=None):
        wide = min(max(len(s) for s in lines) + 8, sc.w - 4)
        high = len(lines) + 2
        x0 = (sc.w - wide) // 2
        if y0 is None:
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
        "███████╗██████╗  █████╗  ██████╗███████╗   ██╗    ██╗ █████╗ ██████╗ ",
        "██╔════╝██╔══██╗██╔══██╗██╔════╝██╔════╝   ██║    ██║██╔══██╗██╔══██╗",
        "███████╗██████╔╝███████║██║     █████╗     ██║ █╗ ██║███████║██████╔╝",
        "╚════██║██╔═══╝ ██╔══██║██║     ██╔══╝     ██║███╗██║██╔══██║██╔══██╗",
        "███████║██║     ██║  ██║╚██████╗███████╗   ╚███╔███╔╝██║  ██║██║  ██║",
        "╚══════╝╚═╝     ╚═╝  ╚═╝ ╚═════╝╚══════╝    ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝",
    ]
    MID = [
        "╔═╗╔═╗╔═╗╔═╗╔═╗  ╦ ╦╔═╗╦═╗",
        "╚═╗╠═╝╠═╣║  ║╣   ║║║╠═╣╠╦╝",
        "╚═╝╩  ╩ ╩╚═╝╚═╝  ╚╩╝╩ ╩╩╚═",
    ]

    @staticmethod
    def matte(sc, y, width, pad=2):
        """Blank a centred strip so text reads clean over the star field."""
        w = min(width + pad * 2, sc.w - 2)
        sc.text((sc.w - w) // 2, y, " " * w, 0)

    def draw_title(self, sc):
        lines = ["S P A C E   W A R"]
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
            (7, "wrecks drop magazines and gear:  O shield   * bomb (Z)"
                "   + ship", A("dim")),
            (8, "chain kills for up to x5   ·   a new sector every 10 waves",
             A("dim")),
        ]
        if self.high:
            rows.append((9, "high score  %d" % self.high, A("accent")))
        pulse = math.sin(time.time() * 4.0) > 0
        rows.append((11, "───  PRESS  SPACE  TO  LAUNCH  ───",
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
            "chain      %d" % self.best_combo,
            "high       %d" % self.high,
            "",
            "R  play again        Q  quit",
        ])


# ==========================================================================
# Main loop
# ==========================================================================
PRESS, REPEAT, RELEASE = 1, 2, 3        # key event types, kitty numbering

# The kitty keyboard protocol, spoken by kitty, Ghostty, WezTerm, foot, rio
# and others: ask for it and the terminal reports every key as an escape
# sequence with a press/repeat/release type on it. Flags 1|2|8 - disambiguate
# escapes, report event types, report all keys as escape codes. Pushed on the
# way in, popped on the way out so the shell gets its keyboard back.
KITTY_PUSH = "\x1b[>11u"
KITTY_POP = "\x1b[<u"
KITTY_QUERY = "\x1b[?u\x1b[c"


def tty_write(s):
    try:
        sys.stdout.write(s)
        sys.stdout.flush()
    except (OSError, ValueError):
        pass


def kitty_probe(stdscr, wait=0.4):
    """Does this terminal speak the kitty keyboard protocol?

    `CSI ? u` is answered with `CSI ? flags u` by one that does, and ignored
    by one that does not - so it is chased with a primary device attributes
    query, which every terminal answers, and the wait ends on that reply
    rather than on the timeout.
    """
    tty_write(KITTY_QUERY)
    buf, t0 = [], time.perf_counter()
    while time.perf_counter() - t0 < wait:
        c = stdscr.getch()
        if c == -1:
            if buf and buf[-1] == ord("c"):      # the DA reply is in
                break
            time.sleep(0.005)
            continue
        if c < 256:
            buf.append(c)
    return re.search(r"\x1b\[\?\d+u", "".join(map(chr, buf))) is not None


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
        # Under the kitty keyboard protocol none of the guessing above is
        # needed: the terminal says when a key goes up, so a direction is
        # held while any key mapped to it is down, and that is all.
        self.exact = False
        self.down = dict.fromkeys(self.DIRS, 0)       # keys holding each
        self.muted = dict.fromkeys(self.DIRS, False)  # overridden by opposite
        self.seen = dict.fromkeys(self.DIRS, -9.0)    # last press/repeat
        self.last_press = -9.0                        # of any key at all
        self.saw_repeat = False

    # Exact mode: a release can still go missing - focus lost mid-hold, say.
    # Once this terminal has shown it repeats held keys, a key that has gone
    # quiet for far longer than any repeat period is not held any more. But
    # the OS repeats only the *most recently pressed* key, so silence from an
    # older one means nothing - hold Right, tap X, and Right goes quiet while
    # still very much held. Only the newest press can be judged by silence.
    STUCK = 1.5

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
            self.down[name] = 0

    def press(self, names, now, event=PRESS):
        if self.exact:
            self._exact(names, now, event)
            return
        if event == RELEASE:          # cannot happen without the protocol
            return
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

    def _exact(self, names, now, event):
        for name in names:
            opp = self.OPPOSITE[name]
            if event == RELEASE:
                self.down[name] = max(0, self.down[name] - 1)
                if self.down[name] == 0:
                    self.muted[name] = False
                    # Letting go of the newer key hands control back to the
                    # opposite one if it is still held.
                    self.muted[opp] = False
            elif event == REPEAT:
                self.down[name] = max(1, self.down[name])
                self.seen[name] = now
                self.saw_repeat = True
            else:
                self.down[name] += 1
                self.seen[name] = now
                self.last_press = now
                self.muted[name] = False
                # Reversing cancels, as it does without the protocol: two
                # opposed keys would otherwise sum to a dead stop, and rolling
                # from one arrow to the other always overlaps them a little.
                if opp not in names:
                    self.muted[opp] = True

    def other(self, now, skip=()):
        """Any key event at all keeps recently-pressed directions alive."""
        if self.exact:
            self.last_press = now     # nothing to keep alive: holds are real
            return
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
        if self.exact:
            if self.down[name] <= 0 or self.muted[name]:
                return 0.0
            if (self.saw_repeat and self.seen[name] >= self.last_press
                    and now - self.seen[name] > self.STUCK):
                self.down[name] = 0           # a release we never saw
                return 0.0
            return 1.0
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
    """Drain curses input, re-assembling escape sequences by hand.

    With nodelay set, ncurses hands back a bare ESC rather than block waiting
    for the rest of a sequence, so on plenty of terminals an arrow key arrives
    as 27 '[' 'C' instead of KEY_RIGHT. Left alone that reads as three unknown
    keys - the ship never moves on arrows, or moves only on the presses that
    happened to be assembled, which is indistinguishable from a stutter.

    Under the kitty keyboard protocol every key is a CSI sequence too, and it
    carries an event type - press, repeat or release - that ncurses knows
    nothing about. Reassembling here is what makes both work.

    read() yields (key, event) pairs: key is an ncurses code or a codepoint.
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
            if b[i] != 27:
                out.append((b[i], PRESS))
                i += 1
                continue
            got = self._seq(b, i)
            if got is None:                    # still arriving...
                if now - self.t < self.PARTIAL:
                    break                      # ...keep it for next time
                got = (1, 27, PRESS)           # ...or it was a lone Escape
            n, key, ev = got
            if key is not None:
                out.append((key, ev))
            i += n
        self.buf = b[i:]
        return out

    def _seq(self, b, i):
        """Decode one escape sequence starting at b[i] (the ESC).

        Returns (length, key, event) - key None for a sequence to ignore -
        or None when the sequence is not all here yet.
        """
        n = len(b)
        if i + 1 >= n:
            return None
        lead = b[i + 1]
        if lead == 79:                          # SS3: ESC O A on some terms
            if i + 2 >= n:
                return None
            key = self.ARROW.get(b[i + 2])
            return (3, key, PRESS) if key else (1, 27, PRESS)
        if lead != 91:                          # not CSI: a lone Escape
            return (1, 27, PRESS)
        j = i + 2
        while j < n and 0x30 <= b[j] <= 0x3F:   # parameter bytes
            j += 1
        while j < n and 0x20 <= b[j] <= 0x2F:   # intermediate bytes
            j += 1
        if j >= n:
            return None
        final = b[j]
        if not 0x40 <= final <= 0x7E:           # not a sequence after all
            return (1, 27, PRESS)
        params = "".join(map(chr, b[i + 2:j]))
        key, ev = self._decode(params, final)
        return (j - i + 1, key, ev)

    def _decode(self, params, final):
        fields = params.split(";")
        ev, mods = PRESS, 0
        if len(fields) > 1 and fields[1]:       # "mods:event", both optional
            m, _, e = fields[1].partition(":")
            mods = int(m) - 1 if m.isdigit() else 0
            if e.isdigit():
                ev = int(e)
        if final == 117:                        # 'u': CSI codepoint ; mods u
            code = fields[0].partition(":")[0]  # "97:65" is a, shifted to A
            if not code.isdigit():
                return None, ev                 # the protocol reply itself
            code = int(code)
            if mods & 4 and code in (99, 67):   # ctrl-C: a key, not a signal
                code = 3
            return code, ev
        if final in self.ARROW:                 # CSI A, or CSI 1;mods:ev A
            return self.ARROW[final], ev
        return None, ev                         # DA reply, page keys, mice


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


def selftest(frames=2600):
    """Headless run: simulate and render every state without a terminal."""
    global STATE_FILE
    STATE_FILE = os.path.join(os.environ.get("TMPDIR", "/tmp"),
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
        if i == 800:
            g.resize(160, 46)
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


def main():
    if "--mute" in sys.argv:
        SOUND[0] = False
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
    print("Thanks for playing Space War.")


if __name__ == "__main__":
    main()
