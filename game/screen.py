"""Braille pixel layer, background wash, text layer - composited and
blitted once a frame."""

import curses
import math
import random
from itertools import groupby

from .colors import bgramp, on
from .config import TAU


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
        self.bg = [[0] * w for _ in range(h)]            # background wash
        self.bgprio = [bytearray(w) for _ in range(h)]   # wash ownership
        self.haze = [bytearray(w) for _ in range(h)]     # prio-0 tiles
        self.hattr = [[0] * w for _ in range(h)]
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

    def tile(self, cx, cy, bits, attr=0, prio=1):
        """A whole braille cell in one call.

        `dot` is the right size of step for a ship. A haze covers thousands
        of cells a frame, and going through it dot by dot is the difference
        between having a background and having a frame rate.

        At priority 0 the tile is scenery, and it goes to its own layer: a
        cell that anything real is drawn in shows only the real thing. A
        ship flying through cloud is a ship, not a ship-shaped thickening
        of the cloud - which is what OR-ing the two together produced.
        """
        if not (0 <= cx < self.w and 0 <= cy < self.h):
            return
        if prio <= 0:
            self.haze[cy][cx] |= bits
            self.hattr[cy][cx] = attr
            return
        self.pat[cy][cx] |= bits
        if prio >= self.prio[cy][cx]:
            self.prio[cy][cx] = prio
            self.pattr[cy][cx] = attr

    def wash(self, cx, cy, color, prio=1):
        """Lay a background colour behind a cell.

        This is the half of every colour pair the game used to leave at the
        terminal's default. It sits under everything drawn, and `color` is a
        bare colour number - see `colors.on`.
        """
        if not color or not (0 <= cx < self.w and 0 <= cy < self.h):
            return
        if prio >= self.bgprio[cy][cx]:
            self.bgprio[cy][cx] = prio
            self.bg[cy][cx] = color

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
            pat, pattr, bg = self.pat[y], self.pattr[y], self.bg[y]
            prio, haze, hattr = self.prio[y], self.haze[y], self.hattr[y]
            tch, tattr = self.tch[y], self.tattr[y]
            cells = []
            for x in range(w):
                c = tch[x]
                if c is not None:
                    # Text never takes the wash. One rule, and it keeps the
                    # HUD, the frame and every panel legible over haze or
                    # firelight without any of them having to know.
                    cells.append((c, tattr[x]))
                    continue
                p, b = pat[x], bg[x]
                if prio[x] > 0:
                    a = pattr[x]           # something real: haze gives way
                elif p:
                    p |= haze[x]           # stars and haze share a cell
                    a = pattr[x]
                else:
                    p, a = haze[x], hattr[x]
                if p:
                    cells.append((BRAILLE[p], on(a, b) if b else a))
                else:
                    cells.append((" ", on(0, b) if b else 0))
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
    """The play area as the simulation sees it, drawn onto the screen.

    Coordinates are in field units and wrap at the field's own edges. `zoom`
    is how many dots one unit gets: 1.0 on any terminal big enough for the
    designed field, less on a small one, where the same field is drawn onto
    fewer dots. Everything that takes a unit measurement - a radius, an arc
    step, a text position - goes through here, so nothing upstream needs to
    know how many dots it has been given.
    """

    def __init__(self, screen, cell_x, cell_y, w, h, zoom=1.0):
        self.s = screen
        self.x0 = cell_x * PX
        self.y0 = cell_y * PY
        self.cx0, self.cy0 = cell_x, cell_y
        self.w, self.h = w, h                    # field units
        self.z = zoom
        self.pw = max(1, int(round(w * zoom)))   # dots
        self.ph = max(1, int(round(h * zoom)))
        self.cols = max(1, self.pw // PX)        # cells
        self.rows = max(1, self.ph // PY)

    def _dot(self, px, py, attr, prio):
        """A dot in dot space, wrapped at the drawn field's edges."""
        self.s.dot(px % self.pw + self.x0, py % self.ph + self.y0, attr, prio)

    def dot(self, x, y, attr=0, prio=1):
        self._dot(int(x * self.z), int(y * self.z), attr, prio)

    def line(self, x0, y0, x1, y1, attr=0, prio=1):
        # Endpoints go to dot space first, then Bresenham runs there: a line
        # is drawn once per dot it covers, however many units that is.
        z = self.z
        x0, y0 = int(round(x0 * z)), int(round(y0 * z))
        x1, y1 = int(round(x1 * z)), int(round(y1 * z))
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self._dot(x0, y0, attr, prio)
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
        # `step` is the spacing between dots, in dots: the count follows the
        # drawn radius, so a ring is as dense at half zoom as at full.
        n = max(6, int((a1 - a0) * r * self.z / step))
        for i in range(n):
            a = a0 + (a1 - a0) * i / n
            self.dot(cx + r * math.cos(a), cy + r * math.sin(a), attr, prio)

    def ellipse(self, cx, cy, rx, ry, attr=0, prio=1, step=1.0):
        n = max(10, int(TAU * max(rx, ry) * self.z / step))
        for i in range(n):
            a = TAU * i / n
            self.dot(cx + rx * math.cos(a), cy + ry * math.sin(a), attr, prio)

    def disc(self, x, y, r, shade, prio=1, r_in=0.0, fuzz=0.0):
        """A filled disc - the one thing an outline cannot give you.

        `shade` is an attribute, or a function of k (0 at the centre, 1 at
        the rim) that returns one. `r_in` hollows the disc from the middle;
        `fuzz` is the outer fraction of the radius that dithers out to
        nothing, so a fireball gets a ragged edge rather than a coin's. Any
        cell wholly inside the solid part is filled with one call; only the
        rim is worked dot by dot, so a big disc costs its perimeter, not
        its area.
        """
        z = self.z
        R, Rin = r * z, r_in * z
        if R < 0.5:
            return
        px0, py0 = x * z, y * z
        solid = R * (1.0 - fuzz)
        fn = shade if callable(shade) else (lambda k: shade)
        rnd = random.random
        HALF = 1.6            # a cell's centre to its farthest dot
        for cy in range(int((py0 - R) // PY), int((py0 + R) // PY) + 1):
            ymid = cy * PY + 1.5
            for cx in range(int((px0 - R) // PX), int((px0 + R) // PX) + 1):
                d = math.hypot(cx * PX + 0.5 - px0, ymid - py0)
                if d - HALF > R or d + HALF < Rin:
                    continue
                attr = fn(min(1.0, d / R))
                if d + HALF <= solid and d - HALF >= Rin:
                    self.tile(cx, cy, 0xFF, attr, prio)
                    continue
                bits = 0
                for i in range(PX):
                    ddx = cx * PX + i - px0
                    for j in range(PY):
                        dd = math.hypot(ddx, cy * PY + j - py0)
                        if dd < Rin or dd > R:
                            continue
                        if dd > solid and rnd() > (R - dd) / (R - solid):
                            continue
                        bits |= DOTS[i][j]
                if bits:
                    self.tile(cx, cy, bits, attr, prio)

    def tile(self, cx, cy, bits, attr=0, prio=1):
        """A whole braille cell, in the field's own wrapping cell grid."""
        self.s.tile(cx % self.cols + self.cx0, cy % self.rows + self.cy0,
                    bits, attr, prio)

    def wash(self, cx, cy, color, prio=1):
        """A background colour on one cell of the field's cell grid."""
        self.s.wash(cx % self.cols + self.cx0, cy % self.rows + self.cy0,
                    color, prio)

    def glow(self, x, y, r, name, prio=1):
        """Spill light onto the cells around a point, `r` field units out.

        Cells are twice as tall as they are wide in dots, so the falloff is
        measured in cells rather than in units - otherwise a round glow
        would come out as a letterbox.
        """
        cx = int(x * self.z) // PX
        cy = int(y * self.z) // PY
        rx = int(r * self.z / PX)
        ry = int(r * self.z / PY)
        if rx < 1 or ry < 1:
            return
        for dy in range(-ry, ry + 1):
            fy = dy / ry
            for dx in range(-rx, rx + 1):
                fx = dx / rx
                t = math.hypot(fx, fy)
                if t <= 1.0:
                    self.wash(cx + dx, cy + dy, bgramp(name, t), prio)

    def text(self, x, y, s, attr=0):
        """Place text at a pixel position, snapped to the character grid.

        Clamped rather than wrapped: a score pop split across both edges of
        the screen reads as garbage.
        """
        cols = self.pw // PX
        cx = int(x * self.z) % self.pw // PX - len(s) // 2
        cx = max(0, min(cols - len(s), cx))
        cy = int(y * self.z) % self.ph // PY
        self.s.text(cx + self.cx0, cy + self.cy0, s, attr)
