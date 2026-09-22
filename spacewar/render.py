"""How a Game draws itself: the field, the chrome, the panels.

Split from the simulation as a mixin rather than a separate object, because
every one of these reads the game's own state and nothing else - passing a
dozen fields across a boundary would buy nothing.
"""

import math
import time

from .colors import A, ramp
from .entities import WEAPONS
from .screen import Field
from .sectors import SECTORS

BAR_FULL, BAR_EMPTY = "▰", "▱"


class GameRender:
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
