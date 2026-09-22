#!/usr/bin/env python3
"""Unit tests for spacewar.py.

    python3 -m unittest test_spacewar

Headless: no terminal is needed, and the save file goes to a temp path.
"""
import os
import tempfile
import unittest

os.environ["SPACEWAR_STATE"] = os.path.join(tempfile.gettempdir(),
                                            ".spacewar_test_state")

import curses                                                   # noqa: E402
import spacewar as ast                                          # noqa: E402
from spacewar import (Game, Keys, Reader, Bullet, Raider, Ship,    # noqa: E402
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
        ast.random.seed(1)
        g, k = game(), Keys()
        for i in range(600):
            k.tick(i / 60)
            g.advance(1 / 60, k)
        self.assertIn(g.state, ("play", "dead", "over"))
        self.assertLessEqual(g.hits, g.shots)


if __name__ == "__main__":
    unittest.main()
