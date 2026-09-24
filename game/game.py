"""The simulation: waves, collisions, scoring, and the rules of a sector."""

import math
import random
import time

from . import config, scale
from .colors import A
from .config import TAU, beep, wrap_delta
from .entities import (GEAR_ODDS, ITEMS, WEAPON_KINDS, WEAPONS, Asteroid,
                       Bullet, Debris, Fireball, Particle, Pickup, Pop,
                       Shock, Ship, Star)
from .fleet import Raider
from .render import GameRender
from .screen import PX, PY, Screen
from .sectors import (SECTOR_CYCLE, SECTOR_WAVES, SECTORS, Mine, Nebula,
                      Sun)


class Game(GameRender):
    def __init__(self, w, h, mode="arcade"):
        self.screen = Screen(w, h)
        self.mode = mode
        self.layout(w, h)
        self.high, saved_mode, saved_size = self.load_state()
        if saved_mode in ("arcade", "classic"):
            self.mode = saved_mode
        scale.apply(saved_size)
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
        """Size the field to the terminal - or, on a small terminal, size
        the terminal's dots to the field.

        The field is never smaller than the designed one. A terminal with
        fewer dots than that gets the same field drawn at a zoom below 1,
        so a gunship's standoff still fits on the screen, a mine's blast is
        still a fraction of it, and a round still takes as long to cross it.
        A terminal with more dots gets more field, at zoom 1, as before.
        """
        self.sw, self.sh = w, h
        self.cell_x, self.cell_y = 1, 1
        dots_w, dots_h = (w - 2) * PX, (h - 2) * PY
        self.fit = min(1.0, dots_w / config.DESIGN_W, dots_h / config.DESIGN_H)
        self.fit = max(config.FIT_MIN, self.fit)
        self.world = (int(round(dots_w / self.fit)),
                      int(round(dots_h / self.fit)))

    def star_count(self):
        # Density is per dot, not per unit: a zoomed-out field would
        # otherwise pack four times the stars into the same screen.
        dots = self.world[0] * self.world[1] * self.fit * self.fit
        return max(24, int(dots / 900))

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
                self.shocks + self.fires + self.debris + self.pops +
                self.foes + self.pickups + self.mines)
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
        # Rocks belong to the debris field and nowhere else. Everywhere else
        # the sky is the fleet and you: a boulder drifting through an open
        # fight was one more thing to read on a screen that is already busy,
        # and it blurred what made the debris sector its own place.
        if self.cur != "debris":
            return 0
        return min((1 + self.level // 5) * 2 + 2, 8)

    ROCK_INFLOW = 4.0       # debris field: seconds between fresh boulders

    def mine_count(self):
        return min(4 + self.level // 10, 9) if self.cur == "mines" else 0

    # -- sectors ----------------------------------------------------------
    def sector_index(self, level=None):
        lv = self.level if level is None else level
        return max(0, (lv - 1) // SECTOR_WAVES)

    def sector(self, level=None):
        i = self.sector_index(level)
        start = config.START_SECTOR
        if start and start != "open":
            # Testing a sector: open in it, then tour the others as usual.
            if i == 0:
                return start
            rest = [s for s in self.sector_order if s != start]
            return rest[(i - 1) % len(rest)]
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
        # A fresh seed each jump: two nebulae in one run should not be the
        # same sky. It sizes itself to the field the first time it draws.
        self.haze = Nebula() if name == "nebula" else None
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

    MAX_FOES = 5            # escorts on screen at once; a boss is extra

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
            out = ["dread"] + ["gunship"] * (2 + self.debt) + ["scout"] * 3
        elif self.is_mini_wave():
            out = ["marauder"] + ["gunship"] * (1 + self.debt) + ["scout"] * 3
        else:
            scouts = min(2 + lv // 4, 5)
            guns = min(lv // 5, 2) + self.debt
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
        dx, dy = wrap_delta(b.x, b.y, best.x, best.y, self.world)
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
        """high score, flight model, size dial. Old files have fewer fields;
        anything missing keeps its default rather than failing the load."""
        try:
            with open(config.STATE_FILE) as fh:
                parts = fh.read().split()
            size = (float(parts[2]) if len(parts) > 2
                    else config.SCALE_DEFAULT)
            return int(parts[0]), (parts[1] if len(parts) > 1 else ""), size
        except Exception:
            return 0, "", config.SCALE_DEFAULT

    def save_state(self):
        try:
            with open(config.STATE_FILE, "w") as fh:
                fh.write("%d %s %.2f\n" % (self.high, self.mode,
                                           config.SCALE))
        except Exception:
            pass

    # -- lifecycle --------------------------------------------------------
    def reset(self, full=False):
        self.asteroids = []
        self.bullets = []
        self.particles = []
        self.shocks = []
        self.fires = []
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
        self.draw_fps = config.FPS # what the frame loop is drawing at
        self.sun = None
        self.haze = None           # the nebula's cloud, when there is one
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
        # Not in the star: as far from it as the field allows, out where
        # its pull is a nudge. The spot used to be a third of the way up
        # from the centre, well inside the point of no return - a ship
        # spawned there was lost before its grace period ran out.
        return w * 0.10, h * 0.14

    def sun_edge(self):
        """The star's point of no return for the flight model in use: for
        arcade, where the drift outruns the commanded speed; for classic,
        where the pull outruns the thrust."""
        if self.sun is None:
            return None
        if self.mode == "arcade":
            return self.sun.horizon(Ship.ARCADE_SPEED / self.ARCADE_DRIFT)
        return self.sun.horizon(Ship.ACC_CLASSIC)

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
        """Sparks. Most fly; some are embers, slow and longer lit, so the
        middle of a burst is not empty the moment the fast ones have left."""
        for _ in range(n):
            a = random.uniform(0, TAU)
            if random.random() < 0.72:
                sp, lf = speed * random.uniform(0.25, 1.0), life
            else:
                sp, lf = speed * random.uniform(0.03, 0.3), life * 1.7
            self.particles.append(Particle(x, y, sp * math.cos(a),
                                           sp * math.sin(a),
                                           lf * random.uniform(0.45, 1.0),
                                           drag))

    def wreck(self, foe, n):
        """The hull comes apart along its own lines.

        `n` pieces of the silhouette the ship was drawn with, at the place
        and angle they were drawn, in its colour, thrown out from the centre
        and tumbling. A kill should leave the ship you were shooting at in
        pieces, not swap it for a generic puff."""
        ca, sa = math.cos(foe.ang) * foe.r, math.sin(foe.ang) * foe.r
        segs = []
        for poly in foe.shape:
            for (px, py), (qx, qy) in zip(poly, poly[1:]):
                segs.append((foe.x + px * ca - py * sa,
                             foe.y + px * sa + py * ca,
                             foe.x + qx * ca - qy * sa,
                             foe.y + qx * sa + qy * ca))
        random.shuffle(segs)
        for ax, ay, bx, by in segs[:n]:
            mx, my = (ax + bx) / 2, (ay + by) / 2
            dx, dy = mx - foe.x, my - foe.y
            d = math.hypot(dx, dy) or 1.0
            sp = random.uniform(14, 40)
            self.debris.append(Debris(
                mx, my, foe.vx * 0.5 + dx / d * sp, foe.vy * 0.5 + dy / d * sp,
                math.hypot(bx - ax, by - ay), random.uniform(0.7, 1.2),
                ang=math.atan2(by - ay, bx - ax), attr=A(foe.col)))

    def smoke(self, x, y, n, speed, life):
        """What an explosion leaves behind.

        The sparks are gone in half a second and the ring in less; this is
        the only thing on the field that outlives its own bang, and it is
        what stops a kill from reading as a blink. It is scenery - nothing
        collides with it - so it can afford to be slow.
        """
        for _ in range(n):
            a = random.uniform(0, TAU)
            sp = speed * random.uniform(0.15, 1.0)
            self.particles.append(Particle(
                x, y, sp * math.cos(a), sp * math.sin(a),
                life * random.uniform(0.5, 1.0), 0.955, "smoke"))

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

    # What a drifting rock does to a hull it meets: the same one point as a
    # round from your own gun. It is the mass that hits, not the shot, so it
    # does not care whose hull it is - but a capital ship has to be worn down
    # by rocks exactly as it has to be worn down by fire.
    ROCK_DMG = 1
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
        self.shake = max(self.shake, 0.22)
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
            s.hit_flash = 0.28
            self.shocks.append(Shock(s.x, s.y, 8, 30, 0.4))
            self.burst(s.x, s.y, 16, 70, 0.4)
            self.shake = max(self.shake, 0.10)
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

    def zoom(self, delta):
        """Turn the size dial a notch, and bring the field with it.

        Everything already flying is resized by the same ratio, so the dial
        never leaves you with a small ship among old, large boulders.
        """
        want = scale.step(delta)
        if want == config.SCALE:
            return
        ratio = want / config.SCALE
        scale.apply(want)
        scale.resize(ratio, self.asteroids, self.foes, self.sun, self.world)
        self.flash("SIZE  %d%%" % round(want * 100), 1.0)
        self.save_state()

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
        for group in (self.particles, self.shocks, self.fires, self.debris,
                      self.pops, self.pickups):
            for o in group:
                o.update(dt, self.world)
        self.pickups = [p for p in self.pickups if p.life > 0]
        self.particles = [p for p in self.particles if p.life > 0]
        self.shocks = [s for s in self.shocks if s.life > 0]
        self.fires = [b for b in self.fires if b.life > 0]
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
                foe.update(dt, self.world, None, self.bullets, self.sun,
                           self.asteroids)
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
            foe.update(dt, self.world, self.ship, self.bullets, self.sun,
                       self.asteroids)
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
        if s is None or s.invuln > 0:
            return          # a fresh ship gets its grace from the star too
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
                dx, dy = wrap_delta(sun.x, sun.y, s.x, s.y, w)
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
            foe.update(dt, self.world, s, self.bullets, None, self.asteroids)
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
                # Rocks are cover, but not a wall only they have to respect:
                # a round from either side breaks one. A boulder between you
                # and a gunship still earns its place - it just does not last
                # for ever, and neither of you gets a free shield out of it.
                # The fragments are cold, though: only a rock *you* kicked is
                # a weapon.
                for a in list(self.asteroids):
                    if self.wrap_dist(b.x, b.y, a.x, a.y) < a.r:
                        self.bullets.remove(b)
                        self.split(a, award=False)
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

        # A hot fragment is your round now: it hurts the first hull it meets,
        # and that one scores, because you put it there.
        for a in list(self.asteroids):
            if a.hot <= 0:
                continue
            for foe in list(self.foes):
                if foe.arrive > 0:
                    continue
                if self.wrap_dist(a.x, a.y, foe.x, foe.y) < a.r + foe.r * 0.8:
                    self.smash(a, foe)
                    break

        # A cold rock belongs to nobody, and it hits like one of your rounds:
        # one hull point. An interceptor is gone, a gunship is one scrape from
        # it, a capital ship is dented - the same shape as ramming, where a
        # fighter dies and a Dreadnought does not. It scores nothing, because
        # the rock did it and not you. The rock breaks either way, so a heavy
        # ploughing through a field pays for every fragment it clips.
        for a in list(self.asteroids):
            if a.hot > 0 or a not in self.asteroids:
                continue
            for foe in list(self.foes):
                if foe.arrive > 0:
                    continue
                if self.wrap_dist(a.x, a.y, foe.x, foe.y) < a.r + foe.r * 0.8:
                    if foe.hit(self.ROCK_DMG):
                        self.kill_foe(foe, award=False)
                    else:
                        self.burst(a.x, a.y, 6, 44, 0.25)
                        self.rage_check(foe)
                    self.split(a, award=False)
                    break

        # Mines: a shot of yours, or any hull too close, sets one off.
        for m in list(self.mines):
            tripped = False
            for b in list(self.bullets):
                if b.hostile:
                    continue
                if (self.wrap_dist(b.x, b.y, m.x, m.y) <
                        Mine.R + Bullet.R * 0.75):
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
            if (b.hostile and self.wrap_dist(s.x, s.y, b.x, b.y) <
                    Ship.RADIUS + Bullet.R):
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
        self.fires.append(Fireball(m.x, m.y, Mine.BLAST * 0.5, 0.3))
        self.smoke(m.x, m.y, 9, 26, 1.8)
        self.burst(m.x, m.y, 26, 90, 0.5)
        self.shake = max(self.shake, 0.15)
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
        # A rock is rock: it throws dust, not flame.
        self.smoke(a.x, a.y, 2 + a.size, 15, 1.0)
        self.shocks.append(Shock(a.x, a.y, a.r * 0.5, a.r * 2.4,
                                 0.22 + 0.08 * a.size))
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
        self.smoke(a.x, a.y, 3 + a.size, 20, 1.1)
        self.shocks.append(Shock(a.x, a.y, a.r * 0.5, a.r * 2.8, 0.3))
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
        self.fires.append(Fireball(foe.x, foe.y, foe.r * 1.35,
                                   0.3 + foe.r * 0.012))
        self.smoke(foe.x, foe.y, int(4 + foe.r * 0.45), 24, 1.7)
        self.wreck(foe, 3 if foe.kind == "scout" else 4)
        self.shocks.append(Shock(foe.x, foe.y, foe.r * 0.4, foe.r * 3.2,
                                 0.4 + foe.r * 0.012))
        # A shake moves every cell on the screen, every frame it lasts, and
        # that is the one thing a slow terminal cannot absorb. So it is kept
        # for the moments that earn it - a capital ship, your own death, a
        # bomb, a mine - and a line ship's death is its fireball and flash.
        if foe.boss:
            self.shake = max(self.shake, 0.22)
        if foe.boss:
            self.shocks.append(Shock(foe.x, foe.y, 2, foe.r * 5.5, 0.9))
            # A capital ship gets a second, slower ring inside the first and
            # a fireball that is still burning when the sparks have gone.
            self.shocks.append(Shock(foe.x, foe.y, foe.r * 0.8, foe.r * 2.6,
                                     0.55))
            self.fires.append(Fireball(foe.x, foe.y, foe.r * 2.0, 0.8))
            self.smoke(foe.x, foe.y, 18, 42, 2.6)
            self.flash("%s DOWN" % ("DREADNOUGHT" if foe.kind == "dread"
                                    else "MARAUDER"), 2.0)
            beep()
            self.wreck(foe, 6)     # the rest of the hull comes apart

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
                                      1.5, ang=math.atan2(q[1] - p[1],
                                                          q[0] - p[0]),
                                      attr=A("ship")))
        self.burst(s.x, s.y, 42, 105, 1.1)
        self.fires.append(Fireball(s.x, s.y, 22.0, 0.55))
        self.smoke(s.x, s.y, 14, 30, 2.0)
        self.shocks.append(Shock(s.x, s.y, 3, 46, 0.65))
        self.shake = 0.28
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
