"""Everything that moves and is not hostile: your ship, rocks, rounds,
salvage, and the particle work that sells a hit."""

import math
import random
import time

from .colors import A, ramp
from . import config
from .config import TAU
from .hulls import PLAYER, PLAYER_ENG, PLAYER_TRIM, draw_hull


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
        self.hit_flash = 0.0
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
        self.hit_flash = max(0.0, self.hit_flash - dt)
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
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.warp_cd = max(0.0, self.warp_cd - dt)

    def hull(self):
        """Nose, both wingtips and the tail notch, in pixel coords.

        The nose is also where the gun is: these ride the drawn size, or the
        rounds would leave from a point the ship no longer reaches.
        """
        a = self.ang
        def p(off, d):
            d *= config.SCALE
            return (self.x + d * math.cos(a + off),
                    self.y + d * math.sin(a + off))
        return p(0, 7.5), p(2.5, 5.6), p(-2.5, 5.6), p(math.pi, 2.4)

    DRAW_R = 10.0          # drawn size; RADIUS above stays the hit radius

    def draw(self, f):
        if (self.hit_flash <= 0 and self.invuln > 0 and
                int(self.invuln * 9) % 2 == 0):
            return
        r = self.DRAW_R
        hull_attr = A("flash") if self.hit_flash > 0 else A("ship")
        draw_hull(f, self.x, self.y, self.ang, r, PLAYER, hull_attr, 6)
        draw_hull(f, self.x, self.y, self.ang, r, PLAYER_TRIM,
                  A("flash") if self.hit_flash > 0 else A("ship_dim"), 6)
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
            # Off the drawn size, not a fixed length: a plume longer than the
            # ship it comes out of reads as a bug, not a burn.
            ln = (0.3 + 0.5 * self.thrust) * r * random.uniform(0.7, 1.15)
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
    # A round is drawn as a streak rather than a disc, but it still has to
    # have a size to be hit at. It was a bare +2 at the collision site, which
    # did not follow the size dial: at 50% the hull halved and the margin did
    # not, so the round that visibly missed you still killed you. Anything a
    # round is tested against adds this.
    R = 2.0

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
        # four pixels a frame is nearly impossible to follow. Its length comes
        # from the speed, which the size dial does not touch, so the dial has
        # to be applied here or a round at 50% would be drawn two and a half
        # times the length of the ship that fired it.
        step = 0.016 * config.SCALE
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
    """A spark, or - on the `smoke` ramp, with a long life and heavy drag -
    what is still hanging there once the spark has gone out."""

    def __init__(self, x, y, vx, vy, life, drag=0.9, name="fire"):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.life0 = life
        self.drag = drag
        self.name = name

    def update(self, dt, world):
        self.x = (self.x + self.vx * dt) % world[0]
        self.y = (self.y + self.vy * dt) % world[1]
        k = self.drag ** (dt * 60)
        self.vx *= k
        self.vy *= k
        self.life -= dt

    def draw(self, f):
        t = 1.0 - self.life / self.life0
        if self.name == "smoke":
            # Smoke is what is left once the fire has gone. For its first
            # moments it is still inside the fireball, and drawing it there
            # would put grey in the middle of the heat.
            if self.life0 - self.life < 0.22:
                return
            f.dot(self.x, self.y, ramp("smoke", t), 1)
            return
        sp = math.hypot(self.vx, self.vy)
        if sp > 30.0 and t < 0.6:
            # A fast spark is a streak, not a point: it is drawn back along
            # its own path. One colour for the whole streak - a cell is one
            # colour, and a cooler tail only made the burst read cooler.
            ln = min(4.0, sp * 0.03)
            f.line(self.x - self.vx / sp * ln, self.y - self.vy / sp * ln,
                   self.x, self.y, ramp("fire", t), 1)
        elif t > 0.65 and random.random() < 0.35:
            return                     # an ember flickers as it dies
        f.dot(self.x, self.y, ramp("fire", t), 1)


class Fireball:
    """The heat at the centre of an explosion.

    The shock ring is the punch and the sparks are the shrapnel; this is the
    part that is actually on fire. The first few frames are a flash - white,
    and half again as big as the fire that follows. Then a solid disc opens
    fast to full size, white at the core and orange at a ragged rim, and
    burns out from the middle: a hollow opens, the shell walks down the fire
    ramp, and the rim frays as it goes. It also throws light: the cells
    around it take a background wash, so for a moment the explosion lights
    the space it happens in.
    """

    FLASH = 0.07          # seconds of white before the fire shows

    def __init__(self, x, y, r, life=0.3):
        self.x, self.y = x, y
        self.r = r
        self.life = self.life0 = life

    def update(self, dt, world):
        self.life -= dt

    def draw(self, f):
        t = 1.0 - self.life / self.life0
        age = self.life0 - self.life
        if age < self.FLASH:
            k = age / self.FLASH
            f.disc(self.x, self.y, self.r * (1.7 - 0.5 * k),
                   ramp("fire", 0.0), 5, fuzz=0.5)
            f.glow(self.x, self.y, self.r * 2.2, "glow", 3)
            return
        r = self.r * (1.0 - (1.0 - min(1.0, t / 0.4)) ** 2)   # ease out
        if r < 1.0:
            return
        hollow = max(0.0, (t - 0.45) / 0.55)
        heat = 0.8 * t
        f.disc(self.x, self.y, r,
               lambda k: ramp("fire", min(1.0, heat + 0.45 * k * k)),
               5, r_in=r * hollow ** 1.4 * 0.92, fuzz=0.2 + 0.55 * t)
        f.glow(self.x, self.y, r * 1.5 * (1.0 - hollow), "glow", 2)


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
              step=0.8 + 1.8 * t)


class Debris:
    """A tumbling line fragment - the ship coming apart.

    Given `attr`, it is a piece of hull: it flashes white as it is torn off,
    keeps its ship's colour while it is hot, and cools to grey. Without one
    it is the older, anonymous shard on the shock ramp."""

    def __init__(self, x, y, vx, vy, length, life, ang=None, attr=None):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.len = length
        self.ang = random.uniform(0, TAU) if ang is None else ang
        self.spin = random.uniform(-4.0, 4.0)
        self.life = self.life0 = life
        self.attr = attr

    def update(self, dt, world):
        self.x = (self.x + self.vx * dt) % world[0]
        self.y = (self.y + self.vy * dt) % world[1]
        self.ang += self.spin * dt
        self.life -= dt

    def draw(self, f):
        t = 1.0 - self.life / self.life0
        dx = self.len * 0.5 * math.cos(self.ang)
        dy = self.len * 0.5 * math.sin(self.ang)
        if self.attr is None:
            att = ramp("shock", 0.15 + 0.85 * t)
        elif t < 0.08:
            att = A("flash")
        elif t < 0.35:
            att = self.attr
        else:
            att = ramp("smoke", (t - 0.35) / 0.65)
        f.line(self.x - dx, self.y - dy, self.x + dx, self.y + dy, att, 4)


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
        # Close stars occasionally catch the eye as a tiny four point flare.
        # Restrict it to the brightest part of the twinkle so it stays rare.
        if self.depth < 0.22 and tw > 0.96:
            flare = A("flash")
            f.dot(self.x - 1, self.y, flare, 1)
            f.dot(self.x + 1, self.y, flare, 1)
            f.dot(self.x, self.y - 1, flare, 1)
            f.dot(self.x, self.y + 1, flare, 1)
