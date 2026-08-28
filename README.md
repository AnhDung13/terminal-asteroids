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
| `Space` | fire — also launches from the title screen |
| `X` | hyperspace: jump somewhere else, 3s cooldown |
| `M` | switch flight model |
| `P` | pause |
| `R` | restart |
| `Q` | quit |

## Two flight models

**ARCADE** (default) — press a direction and the ship accelerates that way,
diagonals included, with the nose swinging smoothly to face your input. Strong
damping means you stop when you let go. Forgiving, quick to pick up.

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

Asteroids split in two on each hit — large → medium → small → gone. Three
lives, an extra ship every 5,000 points, and one more asteroid per wave up to
eleven. Clear the field and the next wave arrives. Game over reports your
score, waves survived, and shooting accuracy.

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

Terminals report key presses but never key releases, so a held key is emulated:
a press counts as "held" for 200 ms, and key-repeat keeps it topped up. That is
what makes rotation and thrust feel continuous, and what lets two arrow keys
combine into a diagonal.
