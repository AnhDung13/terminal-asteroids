"""Braille pixel layer + text layer, composited and blitted once a frame."""

import curses
import math
from itertools import groupby

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
