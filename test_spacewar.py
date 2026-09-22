#!/usr/bin/env python3
"""Unit tests for spacewar.py.

    python3 -m unittest test_spacewar

Headless: no terminal is needed, and the save file goes to a temp path.
"""
import os
import random
import tempfile
import unittest

os.environ["SPACEWAR_STATE"] = os.path.join(tempfile.gettempdir(),
                                            ".spacewar_test_state")

import curses                                                   # noqa: E402
import spacewar as ast                                          # noqa: E402
from spacewar import (Game, Keys, Reader, Bullet, Raider, Ship,    # noqa: E402
                      Asteroid, Mine, Sun, SECTORS, SECTOR_CYCLE,
                      PRESS, REPEAT, RELEASE)


class FakeScreen:
    """Stands in for a curses window: hands out codes, then -1."""

    def __init__(self, codes):
        self.codes = list(codes)

    def getch(self):
        return self.codes.pop(0) if self.codes else -1


def game():
    g = Game(110, 34)
    g.start_game()
    return g


def hold(g):
    """Park the wave: no fleet on the field, one still to come, never
    arriving - so nothing spawns and no wave ends under the test."""
    g.foes, g.queue, g.spawn_cd = [], ["scout"], 99.0
    g.asteroids, g.bullets, g.pickups, g.mines = [], [], [], []
    g.ship.x, g.ship.y = 150.0, 100.0
    g.ship.invuln = 0.0
    return g


def seq(s):
    return [ord(c) for c in s]


class DifficultyTests(unittest.TestCase):
    def test_diff_endpoints(self):
        g = game()
        g.level = 1
        self.assertEqual(g.diff(), 0.0)
        g.level = 10
        self.assertEqual(g.diff(), 1.0)
        g.level = 30
        self.assertEqual(g.diff(), 1.0)

    def test_diff_monotonic(self):
        g = game()
        prev = -1.0
        for lv in range(1, 15):
            g.level = lv
            self.assertGreaterEqual(g.diff(), prev)
            prev = g.diff()

    def test_roster(self):
        g = game()
        g.level = 10
        r = g.roster()
        self.assertEqual(r[0], "dread")
        self.assertEqual(len(r), 8)
        g.level = 5
        r = g.roster()
        self.assertEqual(r[0], "marauder")
        self.assertNotIn("dread", r)
        g.level = 1
        self.assertEqual(sorted(g.roster()), ["scout"] * 3)

    def test_boss_is_not_an_escort(self):
        g = game()
        g.foes = [Raider("dread", 10, 10, 1.0, g.world)]
        g.foes += [Raider("scout", 10, 10, 0.0, g.world) for _ in range(6)]
        self.assertEqual(g.escorts(), 6)
        self.assertLess(g.escorts(), g.MAX_FOES)


class BulletTests(unittest.TestCase):
    def test_reach_scales_with_field(self):
        self.assertAlmostEqual(Bullet.reach((200, 100)) * 2,
                               Bullet.reach((400, 200)))

    def test_bullets_die_at_edge(self):
        b = Bullet(199, 50, 100, 0, 10.0)
        b.update(0.1, (200, 100))
        self.assertEqual(b.life, 0.0)


class ScoringTests(unittest.TestCase):
    def test_spread_counts_three_shots(self):
        g = game()
        g.collect("spread")
        g.fire_cd = 0
        g.fire()
        self.assertEqual(g.shots, 3)

    def test_lance_scores_one_hit_per_shot(self):
        g = game()
        g.foes, g.asteroids = [], []
        g.collect("pierce")
        g.fire_cd = 0
        g.fire()
        b = g.bullets[-1]
        for _ in range(3):
            f = Raider("scout", b.x, b.y, 0.0, g.world)
            f.arrive, f.hp = 0, 99
            g.foes.append(f)
        g.collisions()
        self.assertEqual(g.hits, 1)
        self.assertLessEqual(g.hits, g.shots)

    def test_chain_multiplier_steps_and_lapses(self):
        g = game()
        self.assertEqual(g.mult(), 1)
        for _ in range(3):
            g.chain()
        self.assertEqual(g.mult(), 2)
        for _ in range(20):
            g.chain()
        self.assertEqual(g.mult(), g.COMBO_MAX)
        g.combo_t = 0.01
        g.foes, g.queue, g.spawn_cd = [], ["scout"], 99
        g.update(0.02, Keys())
        self.assertEqual(g.combo, 0)
        self.assertEqual(g.mult(), 1)

    def test_kill_is_multiplied(self):
        g = game()
        g.combo, g.combo_t = 3, 5.0
        f = Raider("scout", 10, 10, 0.0, g.world)
        g.foes = [f]
        before = g.score
        g.kill_foe(f)
        self.assertEqual(g.score - before, 150 * 2)

    def test_death_resets_chain_but_keeps_weapon(self):
        g = game()
        g.combo = 5
        g.collect("gauss")
        g.hurt()
        self.assertIsNone(g.ship)
        self.assertEqual(g.combo, 0)
        self.assertEqual(g.weapon, "gauss")


class CadenceTests(unittest.TestCase):
    def test_gun_fires_five_a_second(self):
        self.assertAlmostEqual(1.0 / Game.GUN_CD, 5.0, places=6)

    def test_gun_cadence_holds_over_a_second(self):
        g = game()
        g.foes, g.asteroids, g.bullets = [], [], []
        g.shots, g.fire_cd = 0, 0.0
        k = Keys()
        for i in range(120):                       # one second of ticks
            k.tick(i / 120)
            g.advance(1 / 120, k)
            g.bullets = []                         # never let the cap bite
        self.assertEqual(g.shots, 5)

    def test_rapid_is_about_three_times_the_gun(self):
        ratio = Game.GUN_CD / ast.WEAPONS["rapid"]["cd"]
        self.assertGreater(ratio, 2.5)
        self.assertLess(ratio, 3.5)

    def test_only_rapid_outpaces_the_gun(self):
        faster = [k for k, w in ast.WEAPONS.items() if w["cd"] < Game.GUN_CD]
        self.assertEqual(faster, ["rapid"])

    def test_foes_fire_at_their_quoted_gap_then_faster(self):
        for kind, spec in Raider.SPECS.items():
            wave1 = Raider(kind, 0, 0, 0.0).cd0
            wave10 = Raider(kind, 0, 0, 1.0).cd0
            self.assertAlmostEqual(wave1, spec["cd"], places=6)
            self.assertLess(wave10, wave1)
            self.assertGreater(wave10 / wave1, 0.5)


class GearTests(unittest.TestCase):
    def test_shield_absorbs_one_hit(self):
        g = game()
        g.collect("shield")
        self.assertFalse(g.hurt())
        self.assertIsNotNone(g.ship)
        self.assertFalse(g.ship.shield)
        self.assertTrue(g.hurt())
        self.assertIsNone(g.ship)

    def test_bomb_clears_rounds_and_hurts_hulls(self):
        g = game()
        g.collect("bomb")
        g.collect("bomb")
        self.assertEqual(g.bombs, 2)
        g.bullets = [Bullet(1, 1, 0, 0, 5, hostile=True), Bullet(1, 1, 0, 0, 5)]
        scout = Raider("scout", 30, 30, 0.0, g.world)
        dread = Raider("dread", 60, 60, 1.0, g.world)
        scout.arrive = dread.arrive = 0
        g.foes = [scout, dread]
        g.bomb()
        self.assertEqual(g.bombs, 1)
        self.assertEqual([b.hostile for b in g.bullets], [False])
        self.assertNotIn(scout, g.foes)
        self.assertIn(dread, g.foes)
        self.assertEqual(dread.hp, dread.hp0 - g.BOMB_DMG)

    def test_bomb_cap(self):
        g = game()
        for _ in range(6):
            g.collect("bomb")
        self.assertEqual(g.bombs, g.BOMB_MAX)

    def test_life_pickup(self):
        g = game()
        lives = g.lives
        g.collect("life")
        self.assertEqual(g.lives, lives + 1)

    def test_loot_is_always_an_item(self):
        for _ in range(300):
            self.assertIn(Game.loot(), ast.ITEMS)


class RockCoverTests(unittest.TestCase):
    def test_rock_stops_hostile_round(self):
        g = game()
        g.foes = []
        a = ast.Asteroid(50, 50, 3, 1.0)
        g.asteroids = [a]
        g.bullets = [Bullet(50, 50, 0, 0, 5, hostile=True)]
        g.ship.x, g.ship.y = 150, 100
        g.collisions()
        self.assertEqual(g.bullets, [])
        self.assertIn(a, g.asteroids)
        self.assertGreater(a.flash, 0)


class HotRockTests(unittest.TestCase):
    def test_shot_kicks_fragments_hot_along_the_shot(self):
        g = hold(game())
        a = Asteroid(60, 60, 3, 1.0)
        g.asteroids = [a]
        g.bullets = [Bullet(60, 60, 190, 0, 5)]
        g.collisions()
        self.assertNotIn(a, g.asteroids)
        self.assertEqual(len(g.asteroids), 2)
        for c in g.asteroids:
            self.assertGreater(c.hot, 0)
            self.assertGreater(c.vx, 60)          # flying with the shot

    def test_ramming_does_not_kick(self):
        g = hold(game())
        a = Asteroid(60, 60, 3, 1.0)
        g.asteroids = [a]
        g.split(a, award=False)
        for c in g.asteroids:
            self.assertEqual(c.hot, 0)

    def test_hot_fragment_hurts_a_hull_and_shatters(self):
        g = hold(game())
        a = Asteroid(50, 50, 2, 1.0)
        a.kick(1, 0)
        g.asteroids = [a]
        gun = Raider("gunship", 55, 50, 0.0, g.world)
        gun.arrive = 0
        g.foes = [gun]
        g.collisions()
        self.assertNotIn(a, g.asteroids)
        self.assertNotIn(gun, g.foes)             # 2 hull points, 2 hp

    def test_cool_rock_is_harmless(self):
        g = hold(game())
        a = Asteroid(50, 50, 2, 1.0)
        g.asteroids = [a]
        gun = Raider("gunship", 55, 50, 0.0, g.world)
        gun.arrive = 0
        g.foes = [gun]
        g.collisions()
        self.assertIn(a, g.asteroids)
        self.assertIn(gun, g.foes)
        self.assertEqual(gun.hp, gun.hp0)

    def test_fragment_cools_and_slows(self):
        a = Asteroid(50, 50, 1, 1.0)
        a.kick(0, 1)
        fast = abs(a.vy)
        for _ in range(6 * 60):
            a.update(1 / 60, (400, 200))
        self.assertEqual(a.hot, 0)
        self.assertLess(abs(a.vy), fast * 0.5)


class TenderTests(unittest.TestCase):
    def test_tender_rides_every_third_wave_mid_pack(self):
        g = game()
        g.level = 3
        r = g.roster()
        self.assertEqual(r.count("tender"), 1)
        self.assertNotEqual(r[0], "tender")
        g.level = 4
        self.assertNotIn("tender", g.roster())
        g.level = 5
        self.assertNotIn("tender", g.roster())        # never on a boss wave

    def test_tender_flees(self):
        g = hold(game())
        t = Raider("tender", 190, 100, 0.0, g.world)
        t.arrive = 0
        g.foes = [t]
        x0 = t.x
        for _ in range(60):
            g.update(1 / 60, Keys())
        self.assertGreater(t.x, x0)                  # away from the ship
        self.assertFalse(any(b.hostile for b in g.bullets))   # no gun
        self.assertLess(t.escape, t.escape0)

    def test_escape_books_a_gunship(self):
        g = hold(game())
        t = Raider("tender", 190, 100, 0.0, g.world)
        t.arrive, t.escape = 0, 0.001
        g.foes = [t]
        g.update(0.01, Keys())
        self.assertNotIn(t, g.foes)
        self.assertEqual(g.debt, 1)
        g.level = 2
        self.assertEqual(g.roster().count("gunship"), 1)
        g.spawn_wave()
        self.assertEqual(g.debt, 0)                  # paid

    def test_tender_always_drops(self):
        g = hold(game())
        t = Raider("tender", 60, 60, 0.0, g.world)
        g.foes = [t]
        g.kill_foe(t)
        self.assertEqual(len(g.pickups), Game.TENDER_DROPS)

    def test_tender_jumps_sooner_on_late_waves(self):
        self.assertLess(Raider("tender", 0, 0, 1.0).escape0,
                        Raider("tender", 0, 0, 0.0).escape0)


class AimMarkTests(unittest.TestCase):
    def test_leading_gunner_marks_its_aim_just_before_firing(self):
        w = (400, 200)
        s = Ship(100, 50)
        s.vx = 50.0
        gun = Raider("gunship", 0, 50, 0.0, w)
        gun.arrive, gun.cd = 0, 0.2
        gun.update(1 / 120, w, s, [])
        self.assertIsNotNone(gun.mark)
        self.assertGreater(gun.mark[0], s.x)        # ahead of the ship
        gun.cd = 1.0
        gun.update(1 / 120, w, s, [])
        self.assertIsNone(gun.mark)

    def test_direct_gunner_never_marks(self):
        w = (400, 200)
        scout = Raider("scout", 0, 50, 0.0, w)
        scout.arrive, scout.cd = 0, 0.1
        scout.update(1 / 120, w, Ship(100, 50), [])
        self.assertIsNone(scout.mark)


class WaveBreakTests(unittest.TestCase):
    def test_fleet_down_starts_a_break_then_the_next_wave(self):
        g = game()
        g.foes, g.queue = [], []
        lv = g.level
        g.update(1 / 60, Keys())
        self.assertIsNotNone(g.break_t)
        self.assertEqual(g.level, lv)
        self.assertEqual(g.card[0], "WAVE %d CLEAR" % lv)
        for _ in range(int(Game.BREAK * 60) + 2):
            g.update(1 / 60, Keys())
        self.assertEqual(g.level, lv + 1)
        self.assertIsNone(g.break_t)

    def test_boss_break_is_longer_and_names_the_sector(self):
        g = game()
        g.level = 10
        g.foes, g.queue = [], []
        g.update(1 / 60, Keys())
        self.assertGreater(g.break_t, Game.BREAK)
        nxt = SECTORS[g.sector(11)]["name"]
        self.assertTrue(any(nxt in line for line in g.card))

    def test_card_counts_the_wave(self):
        g = hold(game())
        f = Raider("scout", 60, 60, 0.0, g.world)
        g.foes = [f]
        g.kill_foe(f)
        g.queue = []
        g.update(1 / 60, Keys())
        self.assertIn("1 ships", g.card[1])


class SectorTests(unittest.TestCase):
    def test_open_space_for_the_first_ten_waves(self):
        g = game()
        for lv in range(1, 11):
            self.assertEqual(g.sector(lv), "open")
        self.assertNotEqual(g.sector(11), "open")
        self.assertEqual(g.sector(11), g.sector(20))
        self.assertNotEqual(g.sector(11), g.sector(21))

    def test_every_rule_comes_round_once_in_forty_waves(self):
        g = game()
        seen = {g.sector(lv) for lv in (11, 21, 31, 41)}
        self.assertEqual(seen, set(SECTOR_CYCLE))

    def jump(self, g, name):
        g.sector_order = [name] + [s for s in SECTOR_CYCLE if s != name]
        g.level = 10
        g.foes, g.queue = [], []
        g.begin_break()
        g.break_t = 0.001
        g.update(1 / 60, Keys())
        self.assertEqual(g.cur, name)
        return g

    def test_jump_clears_the_field_and_keeps_salvage(self):
        g = hold(game())
        g.asteroids = [Asteroid(30, 30, 3, 1.0)]
        g.pickups = [ast.Pickup(30, 30, "bomb")]
        g.bullets = [Bullet(1, 1, 0, 0, 5, hostile=True)]
        self.jump(g, "nebula")
        self.assertFalse(any(b.hostile for b in g.bullets))
        self.assertEqual(len(g.pickups), 1)
        self.assertEqual(len(g.asteroids), g.rock_count())   # fresh rocks

    def test_nebula_fogs_the_far_field(self):
        g = self.jump(hold(game()), "nebula")
        g.ship.x, g.ship.y = 100, 60
        self.assertFalse(g.fogged(110, 60))
        self.assertTrue(g.fogged(100 + g.vis() + 5, 60))
        g.cur = "open"
        self.assertFalse(g.fogged(100 + g.vis() + 5, 60))

    def test_debris_field_has_more_rocks_and_keeps_them_coming(self):
        g = self.jump(hold(game()), "debris")
        g.level = 11
        n = g.rock_count()
        g.cur = "open"
        self.assertGreater(n, g.rock_count())
        g.cur = "debris"
        g.asteroids = []
        g.rock_cd = 0.0
        g.update(1 / 60, Keys())
        self.assertEqual(len(g.asteroids), 1)

    def test_minefield_lays_mines_and_a_shot_sets_one_off(self):
        g = self.jump(hold(game()), "mines")
        self.assertEqual(len(g.mines), g.mine_count())
        g.mines = [Mine(60, 60)]
        gun = Raider("gunship", 70, 60, 0.0, g.world)
        gun.arrive = 0
        g.foes = [gun]
        g.bullets = [Bullet(60, 60, 0, 0, 5)]
        g.collisions()
        self.assertEqual(g.mines, [])
        self.assertNotIn(gun, g.foes)             # 3 hull points, 2 hp
        self.assertEqual(g.hits, 1)

    def test_hostile_rounds_do_not_trip_mines(self):
        g = self.jump(hold(game()), "mines")
        g.mines = [Mine(60, 60)]
        g.bullets = [Bullet(60, 60, 0, 0, 5, hostile=True)]
        g.collisions()
        self.assertEqual(len(g.mines), 1)

    def test_mine_near_the_ship_is_fatal(self):
        g = self.jump(hold(game()), "mines")
        g.mines = [Mine(150, 100)]
        g.ship.x, g.ship.y = 150, 100
        g.collisions()
        self.assertIsNone(g.ship)

    def test_mines_chain(self):
        g = self.jump(hold(game()), "mines")
        g.mines = [Mine(60, 60), Mine(75, 60), Mine(90, 60), Mine(180, 60)]
        g.bullets = [Bullet(60, 60, 0, 0, 5)]
        g.collisions()
        self.assertEqual(len(g.mines), 1)

    def test_star_pulls_and_burns(self):
        g = self.jump(hold(game()), "star")
        self.assertIsInstance(g.sun, Sun)
        w = g.world
        b = Bullet(g.sun.x + 60, g.sun.y, 0, 0, 5)
        g.bullets = [b]
        g.foes = [Raider("scout", g.sun.x + 100, g.sun.y, 0.0, w)]
        g.foes[0].arrive = 0
        for _ in range(60):
            g.gravity(1 / 60)
        self.assertLess(b.vx, 0)                      # falling inward
        ax, ay = g.sun.pull(g.sun.x + 100, g.sun.y, w)
        self.assertAlmostEqual(ax, -Sun.G / 100 ** 2, places=6)
        self.assertLessEqual(abs(g.sun.pull(g.sun.x + 2, g.sun.y, w)[0]),
                             Sun.MAX_PULL)
        g.bullets = [Bullet(g.sun.x, g.sun.y, 0, 0, 5)]
        g.gravity(1 / 60)
        self.assertEqual(g.bullets, [])

    def test_star_kills_the_ship_and_spares_the_spawn(self):
        g = self.jump(hold(game()), "star")
        x, y = g.spawn_point()
        self.assertGreater(g.wrap_dist(x, y, g.sun.x, g.sun.y),
                           g.sun.r * 3)
        g.ship.x, g.ship.y = g.sun.x, g.sun.y
        g.gravity(1 / 60)
        self.assertIsNone(g.ship)

    def test_fleet_steers_clear_of_the_star(self):
        w = (400, 200)
        sun = Sun(w)
        s = Ship(sun.x + 150, sun.y)              # bait on the far side
        f = Raider("scout", sun.x - 40, sun.y, 0.0, w)
        f.arrive = 0
        for _ in range(4 * 120):
            f.update(1 / 120, w, s, [], sun)
            self.assertFalse(sun.inside(f.x, f.y, w))


class RaiderTests(unittest.TestCase):
    def test_gunship_leads_a_moving_target(self):
        s = Ship(100, 0)
        s.vx, s.vy = 0.0, 50.0
        gun = Raider("gunship", 0, 0, 0.0, (400, 200))
        self.assertGreater(gun.aim(100, 0, 100, s), 0.0)
        scout = Raider("scout", 0, 0, 0.0, (400, 200))
        self.assertEqual(scout.aim(100, 0, 100, s), 0.0)

    def test_marauder_cycles_its_phases(self):
        f = Raider("marauder", 0, 0, 0.0, (400, 200))
        seen = {f.phase}
        for _ in range(20 * 60):
            f._cycle(1 / 60)
            seen.add(f.phase)
        self.assertEqual(seen, {"orbit", "charge", "retreat"})

    def test_hurt_dread_throws_rings(self):
        w = (400, 200)
        f = Raider("dread", 200, 100, 1.0, w)
        f.arrive = 0
        f.hp = f.hp0 // 2
        self.assertTrue(f.enraged)
        s, bullets = Ship(50, 50), []
        for _ in range(2 * 120):
            f.update(1 / 120, w, s, bullets)
        self.assertGreaterEqual(len(bullets), f.RING_SHOTS)


class KeysTests(unittest.TestCase):
    def test_legacy_press_holds_then_fades(self):
        k = Keys()
        k.press(("right",), 0.0)
        k.tick(0.1)
        self.assertEqual(k.axis("right"), 1.0)
        k.tick(5.0)
        self.assertEqual(k.axis("right"), 0.0)

    def test_legacy_reverse_cancels(self):
        k = Keys()
        k.press(("right",), 0.0)
        k.press(("left",), 0.05)
        k.tick(0.1)
        self.assertEqual(k.axis("right"), 0.0)
        self.assertEqual(k.axis("left"), 1.0)

    def test_exact_press_release(self):
        k = Keys()
        k.exact = True
        k.press(("up",), 0.0, PRESS)
        k.tick(3.0)
        self.assertEqual(k.axis("up"), 1.0)     # no repeats seen: never stuck
        k.press(("up",), 3.0, RELEASE)
        self.assertEqual(k.axis("up"), 0.0)

    def test_exact_two_keys_one_direction(self):
        k = Keys()
        k.exact = True
        k.press(("up",), 0.0, PRESS)
        k.press(("up", "right"), 0.0, PRESS)
        k.press(("up", "right"), 0.1, RELEASE)
        k.tick(0.1)
        self.assertEqual(k.axis("up"), 1.0)
        self.assertEqual(k.axis("right"), 0.0)

    def test_exact_stuck_key_expires_once_repeats_are_known(self):
        k = Keys()
        k.exact = True
        k.press(("left",), 0.0, PRESS)
        k.press(("left",), 0.5, REPEAT)
        k.tick(0.6)
        self.assertEqual(k.axis("left"), 1.0)
        k.tick(0.5 + Keys.STUCK + 0.1)
        self.assertEqual(k.axis("left"), 0.0)

    def test_exact_hold_survives_tapping_another_key(self):
        # The OS repeats only the newest key: hold Right, tap X, and Right
        # goes quiet. It is still held, and must still count.
        k = Keys()
        k.exact = True
        k.press(("right",), 0.0, PRESS)
        k.press(("right",), 0.5, REPEAT)
        k.other(1.0)                                   # X, say
        k.tick(1.0 + Keys.STUCK + 1.0)
        self.assertEqual(k.axis("right"), 1.0)

    def test_exact_older_arrow_survives_newer_one(self):
        k = Keys()
        k.exact = True
        k.press(("right",), 0.0, PRESS)
        k.press(("right",), 0.5, REPEAT)
        k.press(("up",), 1.0, PRESS)
        k.press(("up",), 1.5, REPEAT)
        k.tick(4.0)
        self.assertEqual(k.axis("right"), 1.0)        # never judged silent
        self.assertEqual(k.axis("up"), 0.0)           # the newest one is

    def test_exact_reverse_cancels_then_restores(self):
        k = Keys()
        k.exact = True
        k.press(("right",), 0.0, PRESS)
        k.press(("left",), 0.1, PRESS)
        k.tick(0.1)
        self.assertEqual(k.axis("right"), 0.0)        # newer key wins...
        self.assertEqual(k.axis("left"), 1.0)
        k.press(("left",), 0.5, RELEASE)
        self.assertEqual(k.axis("right"), 1.0)        # ...until it is let go
        k.press(("right",), 0.6, RELEASE)
        self.assertEqual(k.axis("right"), 0.0)

    def test_exact_diagonal_key_is_not_its_own_opposite(self):
        k = Keys()
        k.exact = True
        k.press(("up", "right"), 0.0, PRESS)
        k.tick(0.0)
        self.assertEqual((k.axis("up"), k.axis("right")), (1.0, 1.0))

    def test_brake_clears_exact_holds(self):
        k = Keys()
        k.exact = True
        k.press(("down",), 0.0, PRESS)
        k.brake()
        k.tick(0.0)
        self.assertEqual(k.axis("down"), 0.0)


class ReaderTests(unittest.TestCase):
    def read(self, codes, now=1.0):
        return Reader(FakeScreen(codes)).read(now)

    def test_plain_and_curses_keys(self):
        self.assertEqual(self.read([ord("a"), curses.KEY_UP]),
                         [(ord("a"), PRESS), (curses.KEY_UP, PRESS)])

    def test_legacy_arrow_sequences(self):
        self.assertEqual(self.read(seq("\x1b[C")), [(curses.KEY_RIGHT, PRESS)])
        self.assertEqual(self.read(seq("\x1bOA")), [(curses.KEY_UP, PRESS)])

    def test_kitty_text_key_events(self):
        self.assertEqual(self.read(seq("\x1b[97u")), [(97, PRESS)])
        self.assertEqual(self.read(seq("\x1b[97;1:2u")), [(97, REPEAT)])
        self.assertEqual(self.read(seq("\x1b[97:65;2:3u")), [(97, RELEASE)])

    def test_kitty_arrow_release(self):
        self.assertEqual(self.read(seq("\x1b[1;1:3A")),
                         [(curses.KEY_UP, RELEASE)])

    def test_kitty_ctrl_c_is_a_quit_key(self):
        self.assertEqual(self.read(seq("\x1b[99;5u")), [(3, PRESS)])

    def test_terminal_replies_are_ignored(self):
        self.assertEqual(self.read(seq("\x1b[?1;2c\x1b[?11u")), [])

    def test_partial_sequence_waits_then_is_an_escape(self):
        r = Reader(FakeScreen(seq("\x1b[")))
        self.assertEqual(r.read(1.0), [])                    # still arriving
        self.assertEqual(r.read(1.1), [(27, PRESS), (91, PRESS)])

    def test_resize_code_after_escape_survives(self):
        self.assertEqual(self.read([27, 91, curses.KEY_RESIZE]),
                         [(27, PRESS), (91, PRESS), (curses.KEY_RESIZE, PRESS)])


class LifecycleTests(unittest.TestCase):
    def test_headless_run_stays_consistent(self):
        random.seed(1)
        g, k = game(), Keys()
        for i in range(600):
            k.tick(i / 60)
            g.advance(1 / 60, k)
        self.assertIn(g.state, ("play", "dead", "over"))
        self.assertLessEqual(g.hits, g.shots)


if __name__ == "__main__":
    unittest.main()
