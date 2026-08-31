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
╰─ ARCADE ─ GUN ● ─── ↑↓←→ fly  YUBN diagonal  SPACE gun  X warp  M model  Q quit ────── WARP ▰▰▰▰ ╯
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
| `↑ ↓ ← →` / `WASD` | hold to fly (arcade) · turn, thrust, retro-burn (classic) |
| `Y` `U` `B` `N` | one-key diagonals: up-left, up-right, down-left, down-right |
| `7` `9` `1` `3` | the same four diagonals, on the keypad |
| `Space` | gun on/off — also launches from the title screen, already armed |
| `0` `.` `,` `5` | all stop |
| `X` | hyperspace: jump somewhere else, 3s cooldown |
| `M` | switch flight model |
| `P` | pause |
| `R` | restart |
| `Q` | quit |

## Two flight models

**ARCADE** (default) — **hold a key to fly, let go and the ship stops.** The
keys command a velocity rather than a thrust, and the ship reaches or leaves
its cruise speed in 75 ms, so it starts and stops with the key instead of
sliding around. Pressing the opposite arrow reverses immediately. `Y U B N`
give a diagonal in one key, which is the reliable way to hold one — two arrows
at once only ever half-works, for the reason in the note at the end.

Letting go is the one thing a terminal never actually tells you about, so the
release is inferred: a key stays live for a short window that each repeat
re-opens, and the ship stops once the repeats stop arriving. Both halves of
that window are measured from your own keyboard rather than guessed — see the
note at the end.

**CLASSIC** — the 1979 model. `←→` rotate, `↑` thrusts along the nose, `↓` is a
weak retro burn, and there are no brakes: momentum is yours to manage.

Press `M` any time to swap. Your choice and your high score persist in
`.asteroids_state` next to the script.

## The gun

`Space` does not fire one shot — it **latches the gun on**, and it stays on
while you fly, through a lost ship and into the next wave, until you press
`Space` again. The lamp in the bottom bar reads `GUN ●` when it is running and
`GUN ○` when it is not, and launching from the title screen already arms it.

This is the same trick sticky course plays, for the same reason. A terminal
auto-repeats only the *most recently pressed* key, so a held `Space` falls
silent the instant you touch an arrow — under a fire-per-keypress gun you
genuinely could not fly and shoot at once, and every course correction cut the
stream until you released and pressed again. A latch has nothing to interrupt.

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
starts is a user setting — and for some setups arrows do not repeat at all.

So a release has to be inferred, and the whole flight model comes down to two
numbers: how long a *fresh* press stays live (it has to outlast the delay
before repeats start, or the ship stutters) and how long each *repeat* keeps it
alive after that (which is exactly how long the ship overruns when you do let
go). Guessing either one badly ruins the model in one direction or the other,
so both are **measured from your own keyboard**: the first repeat of a held key
gives the delay, the ones after it give the period, and the two windows are
sized from those. Holding the Right arrow, then releasing it:

| terminal / OS key-repeat | share of the hold spent flying | overrun after release |
| --- | --- | --- |
| fast repeat (0.25 s, 30/s) | 100% | 0.32 s |
| macOS default (0.5 s, 25/s) | 100% | 0.30 s |
| slow repeat (1.2 s, 10/s) | 100% | 0.50 s |
| very slow (2.0 s, 6/s) | 97% | 0.35 s |
| repeat disabled — one press | one 0.8 s dash, then a stop | — |

That last row is the honest limit. With auto-repeat switched off there is no
information at all after the initial press, so a held arrow reads as a single
dash. Nothing can fix that from inside a terminal; turn key repeat back on.

Two arrows held at once is the other casualty, since only the newer of them
repeats: the older one is kept alive at tapering strength for a fraction of a
second and then fades. `Y U B N` are the reliable way to hold a diagonal,
because a single held key is the one thing that does repeat predictably.

**The gun sidesteps all of it by latching.** The arrow you press to dodge is
*always* more recent than the `Space` you are holding, so a gun that fires once
per keypress goes silent every single time you steer — you cannot fly and shoot
at once. A latch has no window to expire and nothing to interrupt: `Space` arms
it, `Space` disarms it, and steering never touches it.
