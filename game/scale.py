"""The size dial, applied after the fact so the player can turn it mid-game.

Every size in the game is written at its natural, unscaled value where it
belongs - `Ship.RADIUS` is 3.0, a large rock is 15.0 - and this module is the
one place that multiplies them. It captures those naturals once, at import,
before anything has touched them, and `apply()` rewrites the live values from
that record. Rewriting from the record rather than from the current values is
what makes the dial reversible: scaling by 0.5 and back by 2.0 would drift,
and would round a rock away to nothing after enough turns.

`resize()` does the same for the things already on the field, so turning the
dial does not leave you flying a small ship through boulders that are still
the old size.
"""

from . import config
from .entities import Asteroid, Bullet, Pickup, Ship
from .fleet import Raider
from .sectors import Mine

# The naturals, read before anyone has scaled them.
_SHIP_R = Ship.RADIUS
_SHIP_DRAW = Ship.DRAW_R
_PICKUP_R = Pickup.R
_BULLET_R = Bullet.R
_MINE_R = Mine.R
_ROCK = dict(Asteroid.SPECS)
_RAIDER = {k: v["r"] for k, v in Raider.SPECS.items()}


def clamp(value):
    return max(config.SCALE_STEPS[0], min(config.SCALE_STEPS[-1], value))


def step(delta):
    """The next step up or down from where the dial is now."""
    steps = config.SCALE_STEPS
    i = min(range(len(steps)), key=lambda j: abs(steps[j] - config.SCALE))
    return steps[max(0, min(len(steps) - 1, i + delta))]


def apply(value):
    """Set the dial, and rewrite every size that follows from it."""
    value = clamp(value)
    config.SCALE = value
    Ship.RADIUS = _SHIP_R * value
    Ship.DRAW_R = _SHIP_DRAW * value
    Pickup.R = _PICKUP_R * value
    Bullet.R = _BULLET_R * value
    Mine.R = _MINE_R * value
    Asteroid.SPECS = {size: (r * value, speed, points)
                      for size, (r, speed, points) in _ROCK.items()}
    for kind, r in _RAIDER.items():
        Raider.SPECS[kind]["r"] = r * value
    return value


def resize(ratio, rocks, foes, sun=None, world=None):
    """Bring what is already flying to the new size.

    A rock carries its own silhouette - the outline and the craters were built
    from its radius when it broke off - so all of that has to come with it, or
    it would keep the shape of a boulder it no longer is.
    """
    if ratio == 1.0:
        return
    for a in rocks:
        a.r *= ratio
        a.shape = [(ang, d * ratio) for ang, d in a.shape]
        a.craters = [(ang, d * ratio, cr * ratio)
                     for ang, d, cr in a.craters]
    for f in foes:
        f.r *= ratio
    if sun is not None and world is not None:
        sun.fit(world)
