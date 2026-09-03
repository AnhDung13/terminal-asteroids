# Terminal Asteroids

A space combat game that runs in your terminal, in a single Python file with
no dependencies beyond the standard library. You fly one ship against a hostile
fleet — interceptors, gunships, and a capital ship every fifth wave. The
asteroids are still there, but they are weather now: something to dodge while
you fight, not the thing you are fighting.

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
╰─ ARCADE ────────── ↑↓←→ fly  YUBN diagonal  auto guns  X warp  M model  Q quit ───────── WARP ▰▰▰▰ ╯
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
| `Space` | launch, from the title screen or after a game over |
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

**You do not press anything to shoot.** The gun runs on its own for as long as
you are alive — but it does *not* aim itself. The nose follows the way you are
flying, so where you point the ship is where the rounds go, and stopping
leaves the nose on its last heading, still firing along it. Flying is aiming.

Automatic fire is not a convenience here, it is the only thing that works. A
terminal auto-repeats only the *most recently pressed* key, so a held `Space`
falls silent the instant you touch an arrow — any gun bound to a key cuts out
every time you steer, which is exactly when you need it. A gun with no key has
nothing to interrupt.

The cost is that aiming means turning the ship toward the thing shooting at
you. That is the game: a bot that circles, dodges and grabs magazines lands
about 11% of its shots and dies around wave 8.

## Scoring

| Target | Hull | Points |
| --- | --- | --- |
| Large asteroid | 1 | 20 |
| Medium asteroid | 1 | 50 |
| Small asteroid | 1 | 100 |
| Interceptor — fast, darts and circles | 1 | 150 |
| Gunship — twin nacelles, fires pairs | 2 | 400 |
| **Marauder** — mini boss, every 5th wave | 11 | 2,500 |
| **Dreadnought** — boss, every 10th wave | 28 | 12,000 |

Your shots burn out when they reach the edge of the field rather than wrapping
around it, and their range scales with your window, so a shot always crosses
the same fraction of the screen whether you play in a small terminal or
fullscreen.

Asteroids split in two on each hit — large → medium → small → gone. Three
lives and an extra ship every 20,000 points. A wave ends when its fleet is
destroyed; leftover rocks drift on into the next one. Ramming a fighter kills
you and it both; ramming a capital ship only dents it. Game over reports your
score, waves survived, and shooting accuracy.

## Weapons

Your own gun is one bolt at a time. Anything better has to be taken off a
wreck: an interceptor drops a magazine 10% of the time, a gunship 26%, and a
capital ship always gives up two or three. Fly over the tumbling hex to load
it. One magazine at a time, it runs out, and it does not survive your death —
picking up the same type again tops the count up instead of resetting it.

| | Magazine | Effect |
| --- | --- | --- |
| **S** SPREAD | 55 | a fan of three, 6 shots/s |
| **R** RAPID | 150 | one bolt at 17 shots/s |
| **P** LANCE | 60 | passes through hulls and keeps going |
| **H** SEEKER | 55 | curves onto the nearest ship on its own |
| **G** GAUSS | 26 | three hull points a slug, 3.5 shots/s |

GAUSS drops a gunship in one and a Marauder in four; SEEKER is the one weapon
that aims for you, so it is worth breaking off for. The catch is that a
magazine is always somewhere you would rather not be — chasing one is what
gets you killed.

## Difficulty

Wave 1 is three interceptors and two drifting rocks. One eased dial then ramps
the fleet through wave 10 — how many ships, how fast, and how often they fire.

| Wave | Fleet | Rocks | Interceptor speed | Volley gap |
| --- | --- | --- | --- | --- |
| 1 | 3 interceptor | 2 | 52 px/s | 2.5 s |
| 3 | 4 interceptor, 1 gunship | 3 | 54 px/s | 2.4 s |
| 5 | 4 interceptor, 2 gunship, **Marauder** | 3 | 58 px/s | 2.2 s |
| 8 | 7 interceptor, 2 gunship | 4 | 67 px/s | 1.8 s |
| 10 | 4 interceptor, 3 gunship, **Dreadnought** | 5 | 74 px/s | 1.5 s |
| 15 | 4 interceptor, 2 gunship, **Marauder** | 6 | 74 px/s | 1.5 s |
| 20 | 4 interceptor, 3 gunship, **Dreadnought** | 6 | 74 px/s | 1.5 s |

Ships arrive a few at a time rather than all at once, at most seven on the
field. A bot that circles, dodges and grabs magazines reaches a median wave 8
in about four minutes; the Marauder on wave 5 is the first real wall, and it
gets past it roughly seven runs in eight.

## What's in the renderer

- Four hostile hulls — interceptor, gunship, Marauder, Dreadnought — each a
  set of polylines in local coordinates, so one rotate-and-scale draws any of
  them at any size and a silhouette is designed as a shape, not as code. Every
  nozzle trails its own flickering engine bloom, and a capital ship fits
  itself to the field so it cannot swallow a small terminal
- Dropped magazines as a slowly rotating hex with the weapon's letter inside,
  blinking out over their last four seconds
- Round tumbling asteroid outlines with interior craters, flashing white on the
  frame they're hit
- Your ship as one unbroken chevron — raked nose, kinked shoulders, wings
  swept back to a deep tail notch — with a plume off each of three nozzles
  that flickers and grows with throttle, trailing thruster particles. It is
  one outline and a spine on purpose: at the size a fighter gets drawn there
  is only room for a silhouette, and the nacelles and canopy frames that read
  well on a capital ship fill in solid on a small one
- Explosions as an expanding shock ring plus a fire-ramp particle burst —
  white → yellow → orange → red → ember as they cool
- Death breaks the ship into four tumbling line fragments
- Saucers with a domed hull, tapered underside and blinking running lights
- Three-layer parallax starfield that twinkles and shears against your velocity
- Bullet motion trails, floating `+50` score pops, screen shake, a scanline
  sweep and an expanding `« WAVE 3 »` banner between waves
- Framed HUD: score, lives, wave with a pip per ship still to kill, high
  score, flight model, loaded magazine and rounds left, a `WARP ▰▰▰▱`
  hyperspace charge meter, and a hull bar across the top while a boss lives
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

```sh
python3 asteroids.py --keytest
```

Shows what your terminal actually sends while you hold a key: the delay before
auto-repeat starts, the rate once it does, and whether either one is out of the
range the flight model can cope with. Every input constant in `Keys` is a bet
about those two numbers, so this is the thing to run first when the ship feels
like it is fighting you.

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

Both numbers have to be learned from a *train* — a short gap arriving right
behind a long one — and never from a lone gap. Steering taps land 0.2–0.4 s
apart, which looks exactly like a delay-until-repeat; believing them drags the
learned delay below the real one, and then every held key stutters. That is a
mistake worth naming, because it does not show up when you hold a key on a
fresh keyboard model — only when you hold one *after* playing for a while.

Measured by holding an arrow for 2.5 s, having tapped twenty times first:

| terminal / OS key-repeat | share of the hold spent flying | overrun after release |
| --- | --- | --- |
| fast repeat (0.25 s, 30/s) | 100% | 0.32 s |
| macOS default (0.5 s, 25/s) | 100% | 0.37 s |
| slow repeat (1.2 s, 10/s) | 79%, then 100% | 0.57 s |
| very slow (2.0 s, 6/s) | 44% | 0.60 s |
| repeat disabled — one press | one 0.8 s dash, then a stop | — |

The slow row costs one stutter while the delay is being measured and is smooth
from the second hold on. The last two are the honest limits: past a 1.35 s
delay the game gives up waiting, and with auto-repeat switched off there is no
information at all after the initial press, so a held arrow reads as a single
dash. Nothing can fix either from inside a terminal — run `--keytest`, and if
that is what you see, turn key repeat up.

### Arrow keys are not one key

An arrow is an escape sequence, `27 '[' 'C'`, and with `nodelay` set ncurses
will hand back a bare `27` rather than block waiting for the rest of it. On the
terminals where that happens every arrow press arrives as three unknown keys
and the ship does not move at all — or moves only on the presses that happened
to be assembled, which from the player's seat is indistinguishable from a very
bad stutter. So the sequences are re-assembled by hand (`Reader`) instead of
being trusted to ncurses, with a 50 ms grace period for one that is still
arriving byte by byte.

Two arrows held at once is the other casualty, since only the newer of them
repeats: the older one is kept alive at tapering strength for a fraction of a
second and then fades. `Y U B N` are the reliable way to hold a diagonal,
because a single held key is the one thing that does repeat predictably.

**The gun sidesteps all of it by latching.** The arrow you press to dodge is
*always* more recent than the `Space` you are holding, so a gun that fires once
per keypress goes silent every single time you steer — you cannot fly and shoot
at once. A latch has no window to expire and nothing to interrupt: `Space` arms
it, `Space` disarms it, and steering never touches it.
