# Terminal Space War

A space combat game that runs in your terminal, in pure Python with no
dependencies beyond the standard library. You fly one ship against a hostile
fleet — interceptors, gunships, an unarmed tender that runs from you, and a
capital ship every fifth wave — and after every tenth wave the fleet jumps to
a new sector of space with one rule of its own. The asteroids are still there,
but they are weather now: something to dodge while you fight, not the thing
you are fighting — until you shoot one, and the fragments are yours.

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
python3 play.py        # or: python3 -m spacewar
```

Python 3.8+ and any terminal at least 48×16. Bigger window = bigger play
field. 256 colours are used when available, with an automatic 8-colour
fallback.

## Layout

The game is a package. Each module imports only from the ones above it, so
there is no cycle to unpick and any one of them can be read on its own:

| | |
| --- | --- |
| [`spacewar/config.py`](spacewar/config.py) | tunables, the bell, the save file, wrap-aware geometry |
| [`spacewar/colors.py`](spacewar/colors.py) | named curses attributes and the ramps that shade them |
| [`spacewar/screen.py`](spacewar/screen.py) | the braille pixel buffer and the play field's view of it |
| [`spacewar/hulls.py`](spacewar/hulls.py) | every ship's silhouette, as polylines |
| [`spacewar/entities.py`](spacewar/entities.py) | your ship, rocks, rounds, salvage, particles |
| [`spacewar/fleet.py`](spacewar/fleet.py) | the hostile ships and how each class behaves |
| [`spacewar/sectors.py`](spacewar/sectors.py) | the rule that changes every tenth wave |
| [`spacewar/render.py`](spacewar/render.py) | how a `Game` draws itself |
| [`spacewar/game.py`](spacewar/game.py) | the simulation |
| [`spacewar/input.py`](spacewar/input.py) | held keys, from a terminal that will not say |
| [`spacewar/app.py`](spacewar/app.py) | the frame loop |
| [`spacewar/diagnostics.py`](spacewar/diagnostics.py) | `--selftest` and `--keytest` |

`Game` is split across two files because it is two jobs: `game.py` runs the
simulation, `render.py` is a mixin holding every method that draws. They are
one class rather than two objects because the drawing reads the game's own
state and nothing else — handing a dozen fields across a boundary would buy
nothing.

## Controls

| Key | Action |
| --- | --- |
| `↑ ↓ ← →` / `WASD` | hold to fly (arcade) · turn, thrust, retro-burn (classic) |
| `Y` `U` `B` `N` | one-key diagonals: up-left, up-right, down-left, down-right |
| `7` `9` `1` `3` | the same four diagonals, on the keypad |
| `Space` | launch, from the title screen or after a game over |
| `0` `.` `,` `5` | all stop |
| `X` | hyperspace: jump somewhere else, 3s cooldown |
| `Z` | fire a held bomb: every hostile round gone, every hull hurt |
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

Letting go is the one thing a classic terminal never actually tells you about.
In a terminal that speaks the **kitty keyboard protocol** — kitty, Ghostty,
WezTerm, foot, rio and others — the game asks for key releases and gets them,
so a hold is exact: the ship goes while the key is down and stops the instant
it is up, two arrows held together are a true diagonal, and none of the
guessing below applies. The title screen says `KEYS exact` when that is on.
Everywhere else the release is inferred: a key stays live for a short window
that each repeat re-opens, and the ship stops once the repeats stop arriving.
Both halves of that window are measured from your own keyboard rather than
guessed — see the note at the end.

**CLASSIC** — the 1979 model. `←→` rotate, `↑` thrusts along the nose, `↓` is a
weak retro burn, and there are no brakes: momentum is yours to manage.

Press `M` any time to swap. Your choice and your high score persist in
`.spacewar_state` next to the script.

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
you. That is the game: five rounds a second, all of them going wherever the
nose happens to be pointing, so every shot you land is a flying decision
rather than a trigger pull.

## Scoring

| Target | Hull | Points |
| --- | --- | --- |
| Large asteroid | 1 | 20 |
| Medium asteroid | 1 | 50 |
| Small asteroid | 1 | 100 |
| Interceptor — fast, darts and circles | 1 | 150 |
| Gunship — twin nacelles, fires pairs | 2 | 400 |
| Tender — unarmed hauler, runs, and jumps out if you let it | 3 | 600 |
| **Marauder** — mini boss, every 5th wave | 11 | 2,500 |
| **Dreadnought** — boss, every 10th wave | 28 | 12,000 |

Your shots burn out when they reach the edge of the field rather than wrapping
around it, and their range scales with your window, so a shot always crosses
the same fraction of the screen whether you play in a small terminal or
fullscreen.

Asteroids split in two on each hit — large → medium → small → gone. They are
also cover: a hostile round that meets a rock stops there, so a boulder between
you and a gunship is worth keeping. Three lives and an extra ship every 20,000
points. A wave ends when its fleet is destroyed; leftover rocks drift on into
the next one. Ramming a fighter kills you and it both; ramming a capital ship
only dents it. Game over reports your score, waves survived, shooting accuracy
and your longest chain.

**Rocks are ammunition.** When one of your shots splits a rock, the two
fragments fly off *along the shot* — fast, hot, drawn in fire colours with a
streak behind them — and for a second and a half a hot fragment hurts the first
hull it meets: three hull points for a large fragment, two for a medium, one
for a small. The fragment shatters on impact and scores its own points on the
way. A medium chunk kills a gunship outright. Then it cools, sheds the speed,
and is weather again. Shooting the boulder in front of a gunship rather than
flying round it is now a decision with a payoff, and so is lining a rock up
between you and a Marauder before you open fire. Fragments knocked loose by
your own hull are not hot — ramming is still just ramming.

**The chain.** Every ship you down extends a chain, and the chain sets a
multiplier on everything you score: ×2 after three kills, ×3 after six, up to
×5. Go five seconds without a kill, or lose a ship, and it resets to ×1. Rocks
ride the multiplier but do not extend the chain. The HUD shows the current
multiplier with a bar draining toward the reset — the reason to press the
attack rather than snipe from across the field.

## Weapons

Your own gun is one bolt at a time. Anything better has to be taken off a
wreck: an interceptor drops salvage 10% of the time, a gunship 26%, a tender —
it is nothing but cargo — always gives up two pieces, and a capital ship two or
three. Seven drops in ten are a
magazine (a tumbling hex); the rest are gear (a diamond). Fly over one to take
it aboard. One magazine at a time and it runs out, but it stays with you when
you lose a ship — picking up the same type again tops the count up instead of
resetting it.

Your own gun fires five rounds a second, and every magazine is quoted against
that:

| | Magazine | Effect |
| --- | --- | --- |
| **S** SPREAD | 55 | a fan of three, 4.2 shots/s |
| **R** RAPID | 150 | one bolt at 14 shots/s |
| **P** LANCE | 60 | passes through hulls and keeps going, 5 shots/s |
| **H** SEEKER | 55 | curves onto the nearest ship on its own, 3.6 shots/s |
| **G** GAUSS | 26 | three hull points a slug, 2.5 shots/s |

GAUSS drops a gunship in one and a Marauder in four; SEEKER is the one weapon
that aims for you, so it is worth breaking off for. The catch is that a
magazine is always somewhere you would rather not be — chasing one is what
gets you killed.

### Gear

| | Gear | Effect |
| --- | --- | --- |
| **O** SHIELD | half of gear drops | a ring round the hull that eats one hit, then is gone |
| **\*** BOMB | a third | held, up to three; `Z` clears every hostile round and deals 4 hull to every ship on screen |
| **+** EXTRA SHIP | the rest | one more life |

A bomb kills any escort outright and takes a Marauder down a third; on a
Dreadnought it is the thing that gets you out from under a ring of fire. The
shield does not reset your chain when it takes a hit — that is what it is for.

## The fleet

Every hostile ship flies to a standoff distance and circles it rather than
drifting across the screen, so the fight happens around you instead of past
you. Beyond that, each class has one habit of its own:

- **Interceptor** — shoots at where you are. Fast, fragile, and there are a
  lot of them.
- **Gunship** — shoots at where you are *going to be*: it leads its pairs by
  your velocity over the round's flight time, so flying in a straight line
  past one is how you get hit. Change course after it fires.
- **Marauder** — circles for a few seconds, then breaks orbit and runs
  straight at you at more than twice its cruise speed, peels off, and circles
  again. The charge is telegraphed by the turn toward you; sidestep it, and it
  is exposed for a second on the way back out.
- **Dreadnought** — once it is down to half its hull, it goes on throwing its
  seven-round volleys and adds a full ring of sixteen slower rounds every few
  seconds, from all round the hull. The ring rotates and the gaps are wide:
  it is dodged by moving, not by luck. A bomb, if you have one, is for this.
- **Tender** — the fleet's supply hauler, riding with every third ordinary
  wave (3, 6, 9, 12…) and arriving mid-pack, never first. It has no gun. It
  runs straight away from you, weaving, while its jump drive spools: a ring
  round the hull fills in as the charge builds and blinks over the last
  seconds, and a `TENDER JUMP` bar on the frame line shows the same thing.
  Twelve seconds after it arrives (nine by wave 10) it is gone. Catch it and
  it always drops two pieces of salvage; let it go and the *next* wave comes
  with one more gunship in its escort. It is slower than you, but it is never
  where the fight is, so the whole time you are chasing it the fight is
  behind you.

**The tell.** Any gunner that leads its target — the gunship, and the
dreadnought's spinal battery — shows where the volley is going for the last
three tenths of a second before it fires: a faint grey cross at the aim point,
drawn under everything else. It is not a reticle for you to use. It is there
so the rule *change course after it shoots* can be learned by watching rather
than by dying, and once you have learned it you stop seeing it.

## Difficulty

Wave 1 is three interceptors and two drifting rocks. One eased dial then ramps
the fleet through wave 10 — how many ships, how fast, and how often they fire.

| Wave | Fleet | Rocks | Interceptor speed | Volley gap |
| --- | --- | --- | --- | --- |
| 1 | 3 interceptor | 2 | 52 px/s | 1.9 s |
| 3 | 4 interceptor, 1 gunship | 3 | 54 px/s | 1.8 s |
| 5 | 4 interceptor, 2 gunship, **Marauder** | 3 | 58 px/s | 1.7 s |
| 8 | 7 interceptor, 2 gunship | 4 | 67 px/s | 1.5 s |
| 10 | 4 interceptor, 3 gunship, **Dreadnought** | 5 | 74 px/s | 1.2 s |
| 15 | 4 interceptor, 2 gunship, **Marauder** | 6 | 74 px/s | 1.2 s |
| 20 | 4 interceptor, 3 gunship, **Dreadnought** | 6 | 74 px/s | 1.2 s |

A class fires at its quoted gap from wave 1 and closes to two thirds of it by
wave 10. Those gaps are per ship, and jittered ±20% on each reload, so what
you actually face is the whole fleet's fire overlapping.

Ships arrive a few at a time rather than all at once, at most seven escorts on
the field, and a capital ship is extra on top of that. The Marauder on wave 5
is the first real wall — it is the first thing that will not die to one pass,
and the first that comes to you rather than waiting. Every tender that jumps
out is paid for on the next wave, boss wave or not, with one more gunship.

**Between waves** there is a breath: two seconds of quiet with the fleet gone
and the rocks drifting on, and a card low on the screen with the wave just
fought — how long it took, ships downed, hit rate, best chain, and ships lost
if any. After a dreadnought the breath is four seconds, the card says `JUMP
DRIVE CHARGING`, and it names the sector you are about to arrive in. Your gun
keeps running through it; nothing hostile does.

## Sectors

The difficulty dial above is flat from wave 10. From there the *sector* is what
changes: after every dreadnought the fleet jumps and you follow, into a region
of space with one rule of its own. The first ten waves are open space. The four
rules after that come round in a different order every run, so wave 11 is a
fresh problem each time and the whole cycle takes forty waves. Salvage comes
with you through a jump — it is cargo now — but the rocks stay behind, and so
does anything the fleet had in the air.

| Sector | The rule |
| --- | --- |
| **OPEN SPACE** | waves 1–10: the fleet, the rocks, and you |
| **NEBULA** | sensors reach about a third of the way across the field, and a faint ring round your ship shows how far. Past it a hostile ship is a blinking dot in its own colour, its rounds are the faintest specks, and a rock is a dim outline. Your own shots you can always see. The star field goes violet |
| **DEBRIS FIELD** | twice the rocks plus two, a quarter larger, and a fresh boulder drifts in off an edge every four seconds for as long as the field is short. More cover, more weather, and a great deal more ammunition |
| **MINEFIELD** | four to nine proximity mines adrift across the field, blinking. Any hull within eleven pixels sets one off — yours or theirs — and so does one of your shots. The blast reaches thirty-four pixels, does three hull points to every ship inside it, kills you if you are inside it, and sets off any mine inside it too. The fleet's rounds pass straight through a mine: a minefield that cleared itself would be scenery. Shooting one out from under a gunship is the whole idea |
| **GRAVITY WELL** | a star at the centre of the field pulls on everything that moves — rocks, rounds, salvage, the fleet and you — with an inverse-square field, capped so that a close pass is survivable and a straight line into it is not. Touch it and you are gone, though a shield throws you clear instead. Shots bend round it. Rocks and salvage that fall in flare and are lost; a hostile ship that falls in is your kill, chain and all, though its cargo burns. The fleet steers round it, hard — but a Marauder's charge does not steer, and a dreadnought's standoff orbit is wider than the field. You respawn above it, and hyperspace will never drop you in it |

In arcade flight the keys command a velocity, so a pull on that velocity would
be undone within a few frames; the star drags the *hull* instead, as a current
you fly against. In classic flight it is plain acceleration, and there are
still no brakes.

## What's in the renderer

- Five hostile hulls — interceptor, gunship, tender, Marauder, Dreadnought —
  each a set of polylines in local coordinates, so one rotate-and-scale draws
  any of them at any size and a silhouette is designed as a shape, not as
  code. Every nozzle trails its own flickering engine bloom, and a capital ship
  fits itself to the field so it cannot swallow a small terminal. The tender is
  the one hull drawn without bold: a plain long body with a cargo pod slung
  either side, a jump-drive ring filling in round it, and engine plumes that
  stretch as the drive charges
- Hot rock fragments in fire colours with a three-dot streak behind them, and
  the grey aim cross a leading gunner shows before it fires
- Proximity mines as a small ring with four contact horns and a blinking arming
  light; the gravity-well star as a bright three-ring core inside a corona of
  loose arcs turning at different rates
- Nebula fog: a violet star field, a faint ring at sensor range round your
  ship, and everything past it reduced to blips
- The between-waves card, a framed panel low on the screen with the wave's
  numbers, and the `SECTOR 2 - NEBULA` banner that replaces the wave banner on
  a jump
- Dropped salvage as a slowly rotating hex (a magazine) or diamond (gear) with
  its letter inside, blinking out over their last four seconds; a shield is a
  sparse breathing ring round your hull
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
python3 play.py --selftest
```

Runs 2,600 frames of simulation and rendering headlessly — every game state,
both flight models, gear and a bomb, two mid-run resizes, a mini-boss and a
boss wave, and then a jump into each of the four sectors in turn — and reports
draw cost per frame and the sectors it visited. It writes its save file to a
temp path, so your high score is left alone.

```sh
python3 -m unittest test_spacewar
```

Unit tests for the parts that are easy to get subtly wrong: the difficulty
dial and wave rosters, bullet range, shot and hit accounting (a fan is three
shots, a lance threading three hulls is one hit), the chain multiplier and its
lapse, shield, bomb and life pickups, rocks stopping hostile rounds, hot
fragments (kicked along the shot, hurting a hull, cooling off, and never from a
ramming), the tender (its wave, its flight away from you, the debt it leaves
and the salvage it always carries), the aim mark, the between-waves breath and
its card, the sector order and each sector's rule (fog range, rock inflow,
mines tripped by shots and hulls but not by hostile rounds, mines chaining, the
star's pull and what falls into it, the fleet steering clear of it), each
class's habit, both modes of `Keys`, and every escape sequence `Reader` has
to decode — legacy arrows, kitty key events, and the terminal's own replies.

```sh
python3 play.py --keytest
```

Shows what your terminal actually sends while you hold a key: whether it
reports releases (kitty keyboard protocol), the delay before auto-repeat
starts, the rate once it does, and whether either one is out of the range the
flight model can cope with. Every input constant in `Keys` is a bet about
those two numbers, so this is the thing to run first when the ship feels like
it is fighting you.

`--mute` turns off the terminal bell, which otherwise rings for a boss down, a
ship lost, an extra ship and a bomb — and nothing else.

### A note on holding keys

The clean way out is the **kitty keyboard protocol**. On start the game asks
the terminal whether it speaks it (`CSI ? u`, chased with a device-attributes
query so an unsupporting terminal still answers promptly), and if so pushes
the flags for press/repeat/release reporting and pops them on exit. From then
on every key arrives as a sequence with an event type on it, `Reader` decodes
them alongside the legacy arrows, and `Keys` runs in *exact* mode: a direction
is held while any key mapped to it is down, full stop. Reversing still
cancels — the newer of two opposed arrows wins while both are down, and control
passes back when it is released — because rolling from one arrow to the other
always overlaps them for a moment, and a dead stop there feels like a broken
key. The one guard left is for a release that never arrives (focus lost
mid-hold): the *most recently pressed* key, on a terminal that has shown it
repeats held keys, is dropped if it goes quiet for far longer than any repeat
period. Only the newest press, because the OS repeats only that one — an
older arrow held under a newer key, or under a tap of `X`, goes quiet while
still very much held. Everything below is about terminals without it.

Classic terminals report key presses but never key releases, and the OS
auto-repeats only the *most recently pressed* key. Worse, the delay before that
repeat train starts is a user setting — and for some setups arrows do not
repeat at all.

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
