# Terminal Asteroids

A full Asteroids game that runs in your terminal, in a single Python file with
no dependencies beyond the standard library.

The play field is a real pixel buffer: every character cell carries a 2×4 grid
of Unicode braille dots, which gives 8× the resolution of character graphics —
and since terminal cells are about twice as tall as they are wide, those dots
come out square. Circles are round, rotation is smooth, and everything moves
sub-character instead of jumping from cell to cell.

```
╭─ SCORE 3260 ─ ▲ ▲ ▲ ───────────── WAVE 3  ◆◆◆◆◆◆ ─────────────────────── HIGH 8420 ╮
│ ⢐⠁       ⡰⠉⠉ ⠈⠑⠢⡀⢸ ⠄ ⠘⠠⠤⠂ ⠐   ⢹⡀                                                   │
│ ⡂       ⡰⠁⢀⡄⡀   ⠱⡈⡖⡐         ⡰⠁⢂   ⠐                             ⢀          ⡔⠒⠒⠉⠉⢆ │
│⢐        ⠱⡀⠥⠄⢇⢪+20⠁⠑⠢⡂      ⡠⠊  ⢐                     ⢀⣀⠤⠤⠤⠤⠤⡀       ⠁      ⡜ ⡠⡀   ⢣│
│⣗         ⠱⢄⣀⡔⢅⣨⠝⠓⠣⡀ ⠈⠑⠒⠢⠤⠤⠊    ⢐         ⢀        ⣀⠔⠊⢁⢀⢀    ⠱⡀            ⡜ ⠈⠤⠌⠰⣉⠂ │
│⠚⡀         ⢰⠁⠈⡁⣀⡐⠈⡀⠑⡄           ⢐                ⡠⠊  ⡅⢑⠑⠄⢑    ⠱⡀          ⠈⢆      ⣀⠤│
│ ⢂         ⠈⡆⢀⢐⣄⠔⠪⠇ ⡺⡀          ⡂              ⠠⡊  ⢀⠔⠂⠮⠪⠠⠊     ⠱⡀          ⠈⠦⣀⣀ ⡠⠊  │
│ ⠐⡀        ⢠⠷⡊⠁⠘⢄  ⢀⠔⠁         ⡐                ⠈⠢⡀⠐⢄⠄⠃      ⠈ ⡔⠁              ⠉    │
│  ⠐⠄⠁     ⢠⠃⡄⠪⡶⣄⠬⢦⠒⠁          ⠔          ⣀⠤⣀      ⠈⢢         ⢠⠊                   ⢀ │
│   ⠈⠄⡀    ⡎ ⠂⠒⠉⠁  ⠱⡀        ⡀⠜        ⣀⡠⠼⠤⠤⠬⠦⢄⡀     ⠑⢄      ⢨⠃                      │
│     ⠐⠠⡀ ⠘⢄      ⢀⠎⠄      ⡠⠐         ⠘⢧⣠⡀   ⣀⣄⠼      ⠐⠣⡀⢀⣀⡠⠤⠃                    ⢀⡠⡔│
│        ⠁⠢⢀⠉⠢⠤⠔⠒⠒⠁    ⢀⠠⠂⠁              ⠙⠫⢍⠝⠊          ⠈⠁                     ⣠⡔⠊⠁⡜ │
│           ⠈⠈⠐⠐⠐⠐⠐⠐⠐⠈⠈                                                        ⢠⠝⢧⡜  │
│            ⠁                                                               ⡀⠈⠁ ⠈   │
│                                                                           ⠂      ⠠ │
│        ⠁               ⢀                                              ⠠ ⠈          │
│            ⢀⢀⠠⠠⠠⠠⠠⢀⢀⢀⡀                          ⠈                      ⠁           │
│        ⡀⠔⠈⠈        ⡔⠉⠈⠙⠕⡒⠒⠤⠤⣀                             ⡀                        │
│     ⢀⠐⠁           ⡎   ⢀  ⠑⢀  ⠉⢲                                                    │
│   ⢀⠄⠁             ⡇⢀⠄⠒⢄ ⡀⢄ ⠁⢄ ⢸        ⡀                                           │
│  ⢀⠂         ⣀⡀   ⢠⠃⠨⡀⣐⡸⠑⢇⠜⠁  ⢂⢸                                                    │
╰─ ARCADE ───── ↑↓←→ move  SPACE fire  X warp  M model  P pause  Q quit ── WARP ▰▰▰▰ ╯
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
| `↑ ↓ ← →` / `WASD` | fly (arcade) · turn, thrust, retro-burn (classic) |
| `Y` `U` `B` `N` | one-key diagonals: up-left, up-right, down-left, down-right |
| `7` `9` `1` `3` | the same four diagonals, on the keypad |
| `Space` | fire — also launches from the title screen |
| `X` | hyperspace: jump somewhere else, 3s cooldown |
| `M` | switch flight model |
| `P` | pause |
| `R` | restart |
| `Q` | quit |

## Two flight models

**ARCADE** (default) — press a direction and the ship accelerates that way,
with the nose swinging smoothly to face your input, and it glides to a stop
when you let go. Firing never interrupts your flying. For diagonals, either
hold two arrows or use a single diagonal key (`Y U B N`) — see the input note
at the bottom for why one key is the more reliable of the two.

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
draw, leaving the 45 fps loop roughly 3% busy.

## Development

```sh
python3 asteroids.py --selftest
```

Runs 1,500 frames of simulation and rendering headlessly — every game state,
both flight models, two mid-run resizes — and reports draw cost per frame. It
writes its save file to a temp path, so your high score is left alone.

### A note on holding keys

Terminals report key presses but never key releases, and the OS auto-repeats
only the *most recently pressed* key. Two consequences, both of which the
input layer has to work around:

- A press has to be treated as a hold that expires. The first press opens a
  0.62 s window — long enough to cover the OS "delay until repeat" — and each
  repeat afterwards extends it by 0.26 s.
- Tapping fire stops your arrow key from repeating, and holding two arrows
  silences whichever you pressed first. So any key event also keeps recently
  pressed directions alive at reduced, tapering strength ("carry"). Firing,
  warping and pausing therefore never stall the ship, and two arrows give
  about 1.5 s of genuine diagonal that then curves off. Pressing the opposite
  direction cancels a carried direction immediately.

A single held key repeats reliably forever, which is why `Y U B N` give a
perfect, indefinitely sustained diagonal where two arrows can only
approximate one.
