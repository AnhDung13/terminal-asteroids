"""The hostile fleet: four classes, four silhouettes, four habits."""

import math
import random

from .colors import A, ramp
from . import config
from .config import TAU, wrap_delta
from .entities import Bullet
from .hulls import (DREADNOUGHT, DREADNOUGHT_ENG, GUNSHIP, GUNSHIP_ENG,
                    MARAUDER, MARAUDER_ENG, SCOUT, SCOUT_ENG, TENDER,
                    TENDER_ENG, draw_hull)


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
        "scout": dict(r=8.5, hp=1, speed=64.0, cd=1.9, shots=1,
                      jitter=0.26, bsp=78.0, value=150, shape=SCOUT,
                      eng=SCOUT_ENG, keep=46.0, col="foe1", turn=5.0,
                      lead=0.0),
        "gunship": dict(r=12.0, hp=2, speed=46.0, cd=1.7, shots=2,
                        jitter=0.16, bsp=88.0, value=400, shape=GUNSHIP,
                        eng=GUNSHIP_ENG, keep=86.0, col="foe2", turn=3.4,
                        lead=1.0),
        "marauder": dict(r=15.0, hp=11, speed=32.0, cd=1.35, shots=4,
                         jitter=0.13, bsp=80.0, value=2500, shape=MARAUDER,
                         eng=MARAUDER_ENG, keep=104.0, col="foe3",
                         turn=2.4, lead=0.0),
        "dread": dict(r=24.0, hp=28, speed=23.0, cd=1.15, shots=7,
                      jitter=0.10, bsp=74.0, value=12000, shape=DREADNOUGHT,
                      eng=DREADNOUGHT_ENG, keep=134.0, col="foe4",
                      turn=1.7, lead=0.6),
        "tender": dict(r=11.0, hp=3, speed=46.0, cd=9.9, shots=0,
                       jitter=0.0, bsp=1.0, value=600, shape=TENDER,
                       eng=TENDER_ENG, keep=0.0, col="foe5", turn=2.6,
                       lead=0.0),
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
            self.r = min(self.r, world[0] * 0.115 * config.SCALE,
                          world[1] * 0.20 * config.SCALE)
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

    # Kept as a name on the class because that is where the fleet's own code
    # reaches for it; it lives in config because the sun and the seekers
    # need the same answer.
    toward = staticmethod(wrap_delta)

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

    # Rocks. Clearance is part size and part speed: a multiple of the two
    # radii, so it follows SCALE and a dreadnought gets more room than an
    # interceptor, plus however far this hull travels in ROCK_SEE seconds.
    # The speed term is what matters - sizes shrink with SCALE but speeds do
    # not, so a size-only margin leaves a fast ship no room to turn in and it
    # flies into the rock it was trying to miss.
    ROCK_CLEAR = 2.1
    ROCK_SEE = 0.55        # seconds of look-ahead
    ROCK_PUSH = 3.4

    def update(self, dt, world, ship, bullets, sun=None, rocks=()):
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
        # And nobody flies into a boulder on purpose either.
        #
        # Not a repulsion field: those fail exactly when it matters. Pushed
        # away from where a rock *is*, a hull meeting one head-on gets a shove
        # straight backwards, which does not move it off the line at all; and
        # two rocks on opposite sides cancel to nothing and it sails between
        # them into both. So aim at where the rock is going to be instead.
        # For each one, find the moment of closest approach given how the two
        # are moving, and steer off the line that closest approach sits on -
        # which comes out sideways when something is coming at you, because
        # sideways is the way out. Only the most urgent rock is dodged at a
        # time, so the answer is always a direction rather than an average of
        # directions that is no direction at all.
        worst = None
        for a in rocks:
            rx, ry = self.toward(self.x, self.y, a.x, a.y, world)
            rvx, rvy = a.vx - self.vx, a.vy - self.vy
            rv2 = rvx * rvx + rvy * rvy
            t = 0.0 if rv2 < 1e-6 else -(rx * rvx + ry * rvy) / rv2
            t = max(0.0, min(self.ROCK_SEE, t))
            cx, cy = rx + rvx * t, ry + rvy * t      # gap at that moment
            miss = math.hypot(cx, cy)
            need = (a.r + self.r) * self.ROCK_CLEAR
            if miss < need:
                urgency = (need - miss) / need
                if worst is None or urgency > worst[0]:
                    worst = (urgency, cx, cy, rvx, rvy)
        if worst is not None:
            urgency, cx, cy, rvx, rvy = worst
            n = math.hypot(cx, cy)
            if n < 1e-3:         # dead centre: no side to prefer, pick one
                cx, cy = -rvy, rvx
                n = math.hypot(cx, cy) or 1.0
            push = self.ROCK_PUSH * urgency
            wx -= cx / n * push
            wy -= cy / n * push
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
