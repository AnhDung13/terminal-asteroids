#!/usr/bin/env python3
"""
ASTEROIDS - a terminal space shooter with braille-pixel graphics.

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

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          ".asteroids_state")

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
        PAL["ufo"] = _mk(84, True)
        PAL["ufoshot"] = _mk(120)
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
        PAL["ufo"] = _mk(G, True)
        PAL["ufoshot"] = _mk(G)
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
        """Place text at a pixel position, snapped to the character grid."""
        cx = int(x) % self.w // PX + self.cx0
        cy = int(y) % self.h // PY + self.cy0
        self.s.text(cx - len(s) // 2, cy, s, attr)


# ==========================================================================
# Entities  (all positions and speeds are in pixels / pixels-per-second)
# ==========================================================================
class Ship:
    RADIUS = 3.6
    TURN = 4.0             # classic: rad/s
    TURN_RESP = 16.0       # classic: how fast rotation spins up and down
    TURN_STIFF = 600.0     # arcade: nose spring toward the heading you press
    TURN_DAMP = 49.0       # ~2*sqrt(TURN_STIFF): critically damped, no wobble
    TURN_MAX = 14.0
    ACC_CLASSIC = 135.0
    ACC_ARCADE = 320.0
    DRAG_CLASSIC = 0.5
    DRAG_ARCADE = 2.2      # glide a little, so diagonals hold their line
    MAX_SPEED = 105.0
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
        # Keys are on/off, so ease them into a smoothed stick position first:
        # thrust then ramps in and out instead of stepping between frames.
        self.ix = self._ease(self.ix, ix, dt)
        self.iy = self._ease(self.iy, iy, dt)
        n = math.hypot(self.ix, self.iy)
        if n > 0.02:
            k = (1.0 / n) if n > 1.0 else 1.0    # clamp, don't normalise:
            self.vx += self.ACC_ARCADE * self.ix * k * dt  # a carried key
            self.vy += self.ACC_ARCADE * self.iy * k * dt  # pushes partially
            self.thrust = min(1.0, self.thrust + dt * 8)
            self._steer(dt, math.atan2(self.iy, self.ix))
        else:
            self.thrust = max(0.0, self.thrust - dt * 5)
            self._steer(dt, None)
        self._integrate(dt, self.DRAG_ARCADE, world)

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
        self._integrate(dt, self.DRAG_CLASSIC, world)

    def _integrate(self, dt, drag, world):
        damp = math.exp(-drag * dt)
        self.vx *= damp
        self.vy *= damp
        sp = math.hypot(self.vx, self.vy)
        if sp > self.MAX_SPEED:
            # Ease down to the limit instead of clipping hard against it.
            k = 1.0 - (1.0 - self.MAX_SPEED / sp) * min(1.0, 8.0 * dt)
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

    def draw(self, f):
        if self.invuln > 0 and int(self.invuln * 9) % 2 == 0:
            return
        nose, left, right, tail = self.hull()
        att = A("ship")
        f.line(*nose, *left, att, 6)
        f.line(*nose, *right, att, 6)
        f.line(*left, *tail, A("ship_dim"), 6)
        f.line(*right, *tail, A("ship_dim"), 6)
        if self.thrust > 0.05:
            back = self.ang + math.pi
            length = (3.5 + 4.0 * self.thrust) * random.uniform(0.75, 1.1)
            root = (self.x + 2.6 * math.cos(back), self.y + 2.6 * math.sin(back))
            for k in (-1, 0, 1):
                a = back + 0.30 * k * random.uniform(0.5, 1.1)
                d = length * (1.0 if k == 0 else 0.55)
                f.line(root[0], root[1],
                       self.x + d * math.cos(a), self.y + d * math.sin(a),
                       ramp("fire", random.uniform(0.0, 0.4) + 0.22 * abs(k)),
                       5)


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
    def __init__(self, x, y, vx, vy, life, hostile=False):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = life
        self.hostile = hostile

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
        att = A("ufoshot") if self.hostile else A("bullet")
        # A tracer streak from where it was to where it is - a lone dot moving
        # four pixels a frame is nearly impossible to follow.
        step = 0.016
        f.line(self.x - self.vx * step, self.y - self.vy * step,
               self.x, self.y, att, 5)
        for i in (2, 3, 4):
            f.dot(self.x - self.vx * step * i, self.y - self.vy * step * i,
                  att if self.hostile else ramp("fire", 0.2 + 0.2 * i), 4)


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


class Ufo:
    FIRST_WAVE = 2          # no saucers at all on wave 1
    HUNTER_WAVE = 4         # the small one that aims at you comes later still

    def __init__(self, world, level, diff):
        self.diff = diff
        self.small = (level >= self.HUNTER_WAVE and
                      random.random() < 0.20 + 0.40 * diff)
        self.r = 6.0 if self.small else 9.0
        self.value = 1000 if self.small else 200
        self.y = random.uniform(world[1] * 0.15, world[1] * 0.85)
        right = random.random() < 0.5
        speed = 24.0 + 18.0 * diff
        self.x = 1.0 if right else world[0] - 2.0
        self.vx = (speed if right else -speed) * (1.35 if self.small else 1.0)
        self.t = random.uniform(0, TAU)
        self.shoot_cd = 2.6 - 1.2 * diff

    def update(self, dt, world, ship, bullets):
        self.t += dt
        self.x += self.vx * dt
        self.y = (self.y + math.sin(self.t * 1.6) * 22.0 * dt) % world[1]
        self.shoot_cd -= dt
        if self.shoot_cd <= 0 and ship is not None:
            self.shoot_cd = (2.4 - 1.45 * self.diff) * random.uniform(.85, 1.3)
            if self.small:
                jitter = 0.30 - 0.16 * self.diff
                a = math.atan2(ship.y - self.y, ship.x - self.x)
                a += random.uniform(-jitter, jitter)
            else:
                a = random.uniform(0, TAU)
            sp = 60.0 + 45.0 * self.diff
            bullets.append(Bullet(self.x, self.y, sp * math.cos(a),
                                  sp * math.sin(a),
                                  Bullet.reach(world, sp), hostile=True))
        return -14 < self.x < world[0] + 14

    def draw(self, f):
        att = A("ufo")
        r = self.r
        x, y = self.x, self.y
        # flattened hull, dome on top, tapered underside, running lights
        f.ellipse(x, y, r, r * 0.34, att, 4)
        f.arc(x, y - r * 0.28, r * 0.42, att, 4, step=0.9,
              a0=math.pi * 1.05, a1=TAU * 0.975)
        f.line(x - r * 0.5, y + r * 0.3, x, y + r * 0.62, att, 4)
        f.line(x + r * 0.5, y + r * 0.3, x, y + r * 0.62, att, 4)
        blink = ramp("fire", 0.1 if int(self.t * 6) % 2 else 0.65)
        f.dot(x - r * 0.62, y + r * 0.12, blink, 4)
        f.dot(x + r * 0.62, y + r * 0.12, blink, 4)


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
                self.shocks + self.debris + self.pops)
        if self.ship:
            objs.append(self.ship)
        if self.ufo:
            objs.append(self.ufo)
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
        # Three rocks for the first two waves, then one more each wave.
        return min(3 + int((self.level - 1) * 0.9), 12)

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
        self.ufo = None
        self.ufo_timer = 40.0
        self.ship = None
        self.fire_cd = 0.0
        if full:
            self.score = 0
            self.lives = 3
            self.level = 0
            self.next_extra = 4000
            self.shots = self.hits = 0

    def start_game(self):
        self.reset(full=True)
        self.state = "play"
        self.spawn_wave()
        self.spawn_ship()

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
        for _ in range(self.rock_count()):
            while True:
                x, y = random.uniform(0, w), random.uniform(0, h)
                if self.wrap_dist(x, y, w / 2, h / 2) > 60:
                    break
            self.asteroids.append(Asteroid(x, y, 3, scale, spread=spread))
        self.ufo_timer = min(self.ufo_timer, self.ufo_gap())
        if self.level == Ufo.FIRST_WAVE:
            self.ufo_timer = self.lerp(20.0, 34.0, random.random())
        if self.state != "title":
            self.flash("WAVE %d" % self.level, 1.8)
            self.sweep = 0.45

    def ufo_gap(self):
        return self.lerp(38.0, 12.0, self.diff()) * random.uniform(0.8, 1.25)

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
            self.next_extra += 4000
            self.lives += 1
            self.flash("EXTRA SHIP", 1.6)

    # -- actions ----------------------------------------------------------
    def fire(self):
        s = self.ship
        if s is None or self.fire_cd > 0:
            return
        if sum(1 for b in self.bullets if not b.hostile) >= 8:
            return
        self.fire_cd = 0.14
        sp = Bullet.SPEED
        nose = s.hull()[0]
        self.bullets.append(Bullet(
            nose[0] % self.world[0], nose[1] % self.world[1],
            sp * math.cos(s.ang) + s.vx * 0.3,
            sp * math.sin(s.ang) + s.vy * 0.3,
            Bullet.reach(self.world)))
        if self.state != "title":
            self.shots += 1
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
        for group in (self.particles, self.shocks, self.debris, self.pops):
            for o in group:
                o.update(dt, self.world)
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
        s = self.ship
        if s:
            if self.mode == "arcade":
                ix = keys.axis("right") - keys.axis("left")
                iy = keys.axis("down") - keys.axis("up")
                s.fly_arcade(dt, ix, iy, self.world)
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
        self.bullets = [b for b in self.bullets if b.life > 0]

        if self.ufo is None:
            if self.level >= Ufo.FIRST_WAVE:
                self.ufo_timer -= dt
            if self.ufo_timer <= 0 and self.asteroids:
                self.ufo = Ufo(self.world, self.level, self.diff())
                self.flash("SAUCER", 1.0)
        elif not self.ufo.update(dt, self.world, self.ship, self.bullets):
            self.ufo = None
            self.ufo_timer = self.ufo_gap()

        self.collisions()
        if not self.asteroids and self.ufo is None:
            self.spawn_wave()

    def update_title(self, dt):
        """Attract mode: a ship loops around shooting up the rocks."""
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
        if len(self.asteroids) < 5:
            w, h = self.world
            edge = random.random()
            self.asteroids.append(Asteroid(
                w * edge, 0 if random.random() < 0.5 else h - 1, 3, 1.0))

    def collisions(self):
        for b in list(self.bullets):
            if b.hostile:
                continue
            for a in list(self.asteroids):
                if self.wrap_dist(b.x, b.y, a.x, a.y) < a.r:
                    self.split(a)
                    if b in self.bullets:
                        self.bullets.remove(b)
                    self.hits += 1
                    break
            else:
                u = self.ufo
                if u and self.wrap_dist(b.x, b.y, u.x, u.y) < u.r + 2:
                    self.add_score(u.value, u.x, u.y, A("ufo"))
                    self.burst(u.x, u.y, 34, 95, 0.9)
                    self.shocks.append(Shock(u.x, u.y, 4, 34, 0.5))
                    self.shake = 0.3
                    self.ufo = None
                    self.ufo_timer = self.ufo_gap()
                    self.hits += 1
                    if b in self.bullets:
                        self.bullets.remove(b)

        s = self.ship
        if s is None:
            return
        for a in list(self.asteroids):
            if self.wrap_dist(s.x, s.y, a.x, a.y) < a.r + Ship.RADIUS:
                if s.invuln <= 0:
                    self.kill_ship()
                    self.split(a, award=False)
                return
        u = self.ufo
        if u and self.wrap_dist(s.x, s.y, u.x, u.y) < u.r + Ship.RADIUS:
            if s.invuln <= 0:
                self.kill_ship()
                self.burst(u.x, u.y, 24, 80, 0.8)
                self.shocks.append(Shock(u.x, u.y, 4, 30, 0.5))
                self.ufo = None
                self.ufo_timer = self.ufo_gap()
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
        if self.ufo:
            self.ufo.draw(f)
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
        rocks = len(self.asteroids)
        mid = "WAVE %d" % self.level
        if w > 56:
            mid += "  " + ("◆" * min(rocks, 12) if rocks else "CLEAR")
        if x + len(mid) + 6 < w - 16:
            sc.text((w - len(mid)) // 2 - 1, 0, " " + mid + " ", A("accent"))
        right = "HIGH %d" % max(self.high, self.score)
        if len(right) + 6 < w:
            sc.text(w - len(right) - 3, 0, " " + right + " ", A("ui"))

        # bottom bar: flight model, controls, warp charge
        y = self.sh - 1
        mode = "ARCADE" if self.mode == "arcade" else "CLASSIC"
        sc.text(2, y, " %s " % mode, A("warn"))
        s = self.ship
        charge = 1.0 if s is None else 1.0 - s.warp_cd / 3.0
        bars = max(0, min(4, int(charge * 4 + 0.001)))
        warp = "WARP " + BAR_FULL * bars + BAR_EMPTY * (4 - bars)
        if len(warp) + 12 < w:
            sc.text(w - len(warp) - 3, y, " " + warp + " ",
                    A("ui_hi") if bars == 4 else A("dim"))
        hints = [
            ("↑↓←→ move  YUBN diagonal  SPACE fire  X warp  M model  Q quit"
             if self.mode == "arcade" else
             "←→ turn  ↑ thrust  SPACE fire  X warp  M model  P pause  Q quit"),
            ("↑↓←→ YUBN move  SPACE fire  X warp  Q quit"
             if self.mode == "arcade" else
             "←→ turn  ↑ thrust  SPACE fire  X warp  Q quit"),
            "MOVE · FIRE · WARP",
        ]
        for hint in hints:
            if len(hint) + 26 < w:
                sc.text((w - len(hint)) // 2, y, " %s " % hint, A("dim"))
                break

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
        moves = ("↑ ↓ ← →  fly      Y U B N  diagonals"
                 if self.mode == "arcade"
                 else "← → turn      ↑ thrust      ↓ retro")
        rows = [
            (0, moves, A("ui_hi")),
            (1, "SPACE fire      X hyperspace      P pause", A("ui")),
            (2, "M  flight model:  %s" % mode, A("warn")),
            (4, "rocks 20 / 50 / 100      saucer 200 / 1000", A("dim")),
        ]
        if self.high:
            rows.append((5, "high score  %d" % self.high, A("accent")))
        pulse = math.sin(time.time() * 4.0) > 0
        rows.append((7, "───  PRESS  SPACE  TO  LAUNCH  ───",
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

    FIRST = 0.62        # a fresh press: bridges the OS repeat delay
    REPEAT = 0.26       # a repeat: bridges the gap between repeats
    # Carry has to outlast the OS repeat delay: when you add a second arrow,
    # its repeat train only starts ~0.5s later, and the first arrow has gone
    # quiet by then. 1.25s bridges that gap, and bounds how long a direction
    # can survive if you really did let go.
    CARRY = 1.25        # how long another key may keep a direction alive
    CARRY_HI = 0.70     # carried push right after the last real press...
    CARRY_LO = 0.20     # ...fading to this as the carry window runs out
    DIRS = ("left", "right", "up", "down")
    OPPOSITE = {"left": "right", "right": "left", "up": "down", "down": "up"}

    def __init__(self):
        self.real = dict.fromkeys(self.DIRS, -9.0)    # last genuine press
        self.hold = dict.fromkeys(self.DIRS, -9.0)    # genuine hold expiry
        self.carried = dict.fromkeys(self.DIRS, -9.0)  # carried hold expiry
        self.now = 0.0

    def tick(self, now):
        self.now = now

    def press(self, names, now):
        for name in names:
            fresh = now >= self.hold[name]
            self.hold[name] = now + (self.FIRST if fresh else self.REPEAT)
            self.real[name] = now
            opp = self.OPPOSITE[name]
            if opp not in names:                       # reversing cancels
                self.real[opp] = self.hold[opp] = self.carried[opp] = -9.0
        self.other(now, skip=names)

    def other(self, now, skip=()):
        """Any key event at all keeps recently-pressed directions alive."""
        for name in self.DIRS:
            if name not in skip and now - self.real[name] < self.CARRY:
                self.carried[name] = max(self.carried[name], now + self.REPEAT)

    def axis(self, name):
        """0.0 not held, 1.0 genuinely held, tapering in between if carried.

        A carried direction fades rather than cutting out: held as half of a
        two-arrow diagonal it reads as a smooth curve, and in the case where
        the key really was released it reads as ordinary drift.
        """
        now = self.now
        if now < self.hold[name]:
            return 1.0
        if now < self.carried[name]:
            t = min(1.0, max(0.0, (now - self.real[name]) / self.CARRY))
            return self.CARRY_HI + (self.CARRY_LO - self.CARRY_HI) * t
        return 0.0

    def held(self, name):
        return self.axis(name) > 0.0


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
    now = time.perf_counter()
    last = now
    frame = 1.0 / FPS
    while True:
        now = time.perf_counter()
        dt = min(now - last, 0.06)
        last = now

        while True:
            c = stdscr.getch()
            if c == -1:
                break
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
        if i % 8 == 0:
            keys.other(t)
        g.advance(1 / FPS, keys)
        if i % 8 == 0:
            g.fire()
        if i % 300 == 299:
            g.hyperspace()
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


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    locale.setlocale(locale.LC_ALL, "")
    os.environ.setdefault("ESCDELAY", "25")
    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass
    print("Thanks for playing Asteroids.")


if __name__ == "__main__":
    main()
