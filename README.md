# Terminal Asteroids

A full Asteroids game that runs in your terminal, in a single Python file with
no dependencies beyond the standard library.

The play field is a real pixel buffer: every character cell carries a 2×4 grid
of Unicode braille dots, which gives 8× the resolution of character graphics —
and since terminal cells are about twice as tall as they are wide, those dots
come out square. Circles are round, rotation is smooth, and everything moves
sub-character instead of jumping from cell to cell.

```
╭─ SCORE 3260 ─ ▲ ▲ ────────────────────── WAVE 3  ◆◆◆◆◆ ─────────────────────────────── HIGH 8420 ╮
│⠄⡀                   ⠱⡀  ⣀⠤⠊                                                    ⢀⠔⢩⠐⠢⡀     ⡇ ⢀ ⡄  │
│⠈⠐⠊⠔⡠                 ⠱⠒⠉                         ⠠                           ⢠⠊⠁ ⢑⣠⣠⡊    ⠠⣸⠘⠈⠈   │
│    ⠐⠌⠐⡀                ⠐                                         ⠄          ⢠⠃  ⡀⠤⡢⠠⠊ ⢀⠐⡘⠁⡈⡆     │
│      ⢑ ⢂                                                                    ⢇  ⠐⡁ ⢈⠂ ⢀⠂⠅  ⢰⠁⣀⠤⣀  │
│0⠒⠢⡄⠄  ⢂ ⠄                                       ⠁                           ⠈⢆  ⠁⠒⠁  ⠄⠌⣀⡤⠴⢧⠎⣰⢒⢤  │
│⠖  ⠚⣄  ⠰ ⠡      ⠁                            ⣀⣀⡀                              ⠈⠒⠤⣀ ⣀⣀⢬⠔⡋⠁  ⠜⡜⠕⠋⠳  │
│⣥⡾⠤⠊⠄  ⠨ ⢐                                ⣀⡠⠼⠤⠤⠼⠤⣀⡀                               ⠉ ⢠⢚ ⡂⠠⢄⣲⢅⢳⡺⠵⣶  │
│⢖     ⠠⠁ ⠄                        ⠄      ⠸⣅⡄     ⣄⡽                  ⠂              ⡌⠠ ⠐⣁⠤⣞⣿⣗⠾⣽⠐  │
│  ⢀  ⡀⠊ ⠠⠁                        ⠠     «   SHIP LOST   »                           ⠣ ⠡⠐⡵⢵⠈⠿⢲⢅⢁⡩  │
│ ⠁⡀⠄⠊  ⠄⠁                                                                        ⠁  ⠘⢄ ⡥⠁⠁⠂⢅⠁     │
│⠐⠈  ⢀⠠⠈                                                                              ⡘⠛⢄⡈⠠⢀ ⠈⠐⣐⠖  │
│⡀⡀⠠⠐   ⡀                                                                                ⠈⠁⠑⠒⠡⢉ ⡀  │
│                                                                                 ⠐                │
│                      ⡀                    ⠈                                    ⠤                 │
│                    ⣀⠤⠒⠒⠢⠤⠤⣀                                                                      │
│               ⠄  ⡖⠉  ⡔⠐⡦⠒⠢ ⠉⠒⢄                                                               ⢀   │
│                  ⢣   ⢅⢀⠕⣁⣔⠁  ⠈⠢⡀               ⠐                                                 │
│      ⢀           ⢸      ⠇⣀⠕    ⢑⠄                                                                │
│                   ⢣          ⢀⠔⠁                                           ⠄                     │
│                    ⠣⡀      ⣀⠔⠁       ⠈                                            ⡠⠤⠔⠒⠒⠒⠒⢲       │
╰─ ARCADE ─────────── ↑↓←→ course  0 stop  SPACE fire  X warp  M model  Q quit ───────── WARP ▰▰▰▰ ╯
```

## Run

```sh
python3 asteroids.py
```

Python 3.8+ and any terminal at least 48×16. Bigger window = bigger play
field. 256 colours are used when available, with an automatic 8-colour
fallback.

## Controls

| Key | Action |
| --- | --- |
| `↑ ↓ ← →` / `WASD` | set course (arcade) · turn, thrust, retro-burn (classic) |
| `Y` `U` `B` `N` | one-key diagonals: up-left, up-right, down-left, down-right |
| `7` `9` `1` `3` | the same four diagonals, on the keypad |
| `Space` | fire — also launches from the title screen |
| `0` `.` `,` `5` | stop (arcade) |
| `X` | hyperspace: jump somewhere else, 3s cooldown |
| `M` | switch flight model |
| `P` | pause |
| `R` | restart |
| `Q` | quit |

## Two flight models

**ARCADE** (default) — **you do not hold keys down.** One press sets a course
and the ship holds it until you press another direction or press `0` to stop.
`Y U B N` set the four diagonals. The nose follows your course on a damped
spring, and the ship reaches or leaves its cruise speed in 75 ms, so it starts
and stops with the key instead of sliding around.

This exists because holding a key is the one thing terminals genuinely cannot
do — see the note at the end. Against a bot steering at a human-ish 5–10
presses per second, sticky course survives 3–4× longer than the old
hold-to-move model.

**CLASSIC** — the 1979 model. `←→` rotate, `↑` thrusts along the nose, `↓` is a
weak retro burn, and there are no brakes: momentum is yours to manage.

Press `M` any time to swap. Your choice and your high score persist in
`.asteroids_state` next to the script.

## Scoring

| Target | Points |
| --- | --- |
| Large asteroid | 20 |
| Medium asteroid | 50 |
| Small asteroid | 100 |
| Saucer | 200 |
| Small saucer (wave 3+, aims at you) | 1000 |

Your shots burn out when they reach the edge of the field rather than wrapping
around it, and their range scales with your window, so a shot always crosses
the same fraction of the screen whether you play in a small terminal or
fullscreen.

Asteroids split in two on each hit — large → medium → small → gone. Three
lives and an extra ship every 4,000 points. Clear the field and the next wave
arrives. Game over reports your score, waves survived, and shooting accuracy.

## Difficulty

Wave 1 is deliberately gentle — three slow rocks, no saucer, and a long
respawn shield. One eased dial then ramps everything through wave 10: rock
count and speed, how much of a speed kick fragments get when they split, and
how often saucers come and how well they shoot.

| Wave | Rocks | Large rock speed | Saucer | Aiming saucer |
| --- | --- | --- | --- | --- |
| 1 | 3 | 10 px/s | never | no |
| 2 | 3 | 11 px/s | every ~37 s | no |
| 4 | 5 | 14 px/s | every ~34 s | 27% of saucers |
| 6 | 7 | 18 px/s | every ~28 s | 36% of saucers |
| 8 | 9 | 24 px/s | every ~21 s | 47% of saucers |
| 10+ | 11–12 | 31 px/s | every ~12 s | 60% of saucers |

A motionless ship that never fires survives a median 20 s on wave 1, 10 s on
wave 3, and under 2 s by wave 12.

## What's in the renderer

- Round tumbling asteroid outlines with interior craters, flashing white on the
  frame they're hit
- Ship drawn as a hull with a three-prong exhaust plume that flickers and grows
  with throttle, trailing thruster particles
- Explosions as an expanding shock ring plus a fire-ramp particle burst —
  white → yellow → orange → red → ember as they cool
- Death breaks the ship into four tumbling line fragments
- Saucers with a domed hull, tapered underside and blinking running lights
- Three-layer parallax starfield that twinkles and shears against your velocity
- Bullet motion trails, floating `+50` score pops, screen shake, a scanline
  sweep and an expanding `« WAVE 3 »` banner between waves
- Framed HUD: score, lives, wave with a pip per remaining rock, high score,
  flight model, and a `WARP ▰▰▰▱` hyperspace charge meter
- Animated attract-mode title screen where a demo ship flies loops and shoots
  up the field behind the logo

Everything composites into one character buffer and blits once per frame, so
there's no flicker and no tearing. A full frame at 110×32 costs about 0.7 ms to
draw, leaving the 60 fps loop roughly 4% busy.

## How the motion is kept smooth

- **Physics runs in fixed slices** of at most 1/120 s, with the last slice of
  each frame taking the remainder. Capping the slice keeps Euler integration
  stable through a long frame; letting the last one absorb the remainder means
  a frame advances by exactly the time it took, so motion never beats against
  the frame rate. Measured jerk is now identical at 30 fps and 60 fps.
- **Keys are eased into a stick position** rather than driving thrust directly.
  A key is on or off, so using it raw steps the acceleration between frames;
  easing it in over ~40 ms and out over ~100 ms ramps instead.
- **The nose is on a critically damped spring** rather than turning at a fixed
  rate — it eases in and out of a turn and settles without any wobble. Tuned to
  land a 90° turn in 200 ms with zero overshoot, which cut peak angular
  acceleration by about 7×.
- **Speed eases into its limit** instead of being clipped hard against it, and
  screen shake is a decaying oscillation rather than per-frame noise, so a hit
  reads as a thump rather than a flicker.

## Development

```sh
python3 asteroids.py --selftest
```

Runs 1,500 frames of simulation and rendering headlessly — every game state,
both flight models, two mid-run resizes — and reports draw cost per frame. It
writes its save file to a temp path, so your high score is left alone.

### A note on holding keys

Terminals report key presses but never key releases, and the OS auto-repeats
only the *most recently pressed* key. Worse, the delay before that repeat train
starts is a user setting — and for some setups arrows do not repeat at all. Any
scheme that treats a press as "held until a timer runs out" therefore stutters:
the ship flies for a moment, stops, and starts again when the repeats arrive.

**Arcade sidesteps all of it.** One press sets a course, so there is nothing to
hold and no window to expire. A repeat train just re-affirms the course you
already set, which means it stops mattering whether the terminal repeats
quickly, slowly, or not at all. Holding the Right arrow for six seconds, the
share of that time the ship is actually moving:

| terminal / OS key-repeat | hold model | sticky course |
| --- | --- | --- |
| fast repeat (0.25 s, 30/s) | 99% | 100% |
| macOS default (0.5 s, 25/s) | 99% | 100% |
| slow repeat (1.2 s, 10/s) | 99% | 100% |
| very slow (2.0 s, 6/s) | 88% | 100% |
| repeat disabled — one press | **22%** | **100%** |

That last row is the stutter: with repeat off, the old model flew for half a
second and stopped no matter how long you held the key.

Classic mode still uses the hold model, since rotate-and-thrust has no sensible
sticky form. There a press opens a window long enough to cover the repeat
delay, any other key event keeps recently pressed directions alive at tapering
strength, and the delay itself is learned from the first repeat of a held key
rather than guessed. `Y U B N` remain the reliable way to hold a diagonal,
because a single held key is the one thing that does repeat predictably.
