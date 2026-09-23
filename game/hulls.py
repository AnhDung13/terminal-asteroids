"""Every hull in the game, yours and theirs, as polylines in local coords.

Nose along +x, one unit = the ship's radius, so one rotate-and-scale draws
any of them at any size and a silhouette is designed as a shape rather than
written as drawing code.
"""

import math


# Every hull in the game - yours and theirs - is a list of polylines in local
# coordinates: nose along +x, one unit = the ship's radius. One rotate-and-
# scale draws any of them at any size, so a silhouette is designed as a shape
# rather than written as drawing code.
def flip(poly):
    return [(px, -py) for px, py in poly]


def draw_hull(f, x, y, ang, r, parts, attr, prio=4):
    ca, sa = math.cos(ang) * r, math.sin(ang) * r
    for poly in parts:
        px, py = poly[0]
        ax, ay = x + px * ca - py * sa, y + px * sa + py * ca
        for px, py in poly[1:]:
            bx, by = x + px * ca - py * sa, y + px * sa + py * ca
            f.line(ax, ay, bx, by, attr, prio)
            ax, ay = bx, by


# Your ship: one unbroken chevron - a raked nose, kinked shoulders, wings
# swept back to a deep tail notch. Deliberately unlike anything in the fleet,
# because in a crowded field you must never have to wonder which one is you.
#
# It is one outline and a spine, and that is the whole point. A braille cell
# is 2x4 dots, so at the size a fighter actually gets drawn there is only room
# for a silhouette; the nacelles and canopy frames that read beautifully on a
# capital ship just fill in solid on this one. Capital ships get the detail
# because they are three times the size.
PLAYER = [
    [(1.34, 0.0), (0.10, -0.40), (-0.58, -0.84), (-0.34, -0.30),
     (-0.66, 0.0), (-0.34, 0.30), (-0.58, 0.84), (0.10, 0.40), (1.34, 0.0)],
]
PLAYER_TRIM = [
    [(0.52, 0.0), (0.02, 0.0)],                                   # spine
]
PLAYER_ENG = [(-0.58, 0.0), (-0.44, -0.34), (-0.44, 0.34)]


# --------------------------------------------------------------------------
# Hostile ships.
#
# Every hull is a list of polylines in local coordinates - nose along +x, one
# unit = the ship's radius - so a single rotate-and-scale draws any of them at
# any size, and a silhouette can be designed as a shape rather than as code.
# --------------------------------------------------------------------------
# Scout: an integrated delta interceptor with a visible canopy core and
# twin vector engines. The wing panels stay attached to one clear silhouette.
SCOUT = [
    # One-piece stealth hull and swept delta wings.
    [(1.48, 0.0), (1.05, -0.10), (0.62, -0.18), (0.30, -0.20),
     (-0.12, -0.38), (-0.50, -0.86), (-0.82, -0.94), (-0.69, -0.43),
     (-1.04, -0.24), (-1.12, 0.0), (-1.04, 0.24), (-0.69, 0.43),
     (-0.82, 0.94), (-0.50, 0.86), (-0.12, 0.38), (0.30, 0.20),
     (0.62, 0.18), (1.05, 0.10), (1.48, 0.0)],
    # Integrated wing plates and panel seams.
    [(-0.52, -0.77), (-0.22, -0.40), (0.18, -0.25), (0.53, -0.18),
     (0.05, -0.28), (-0.52, -0.77)],
    [(-0.52, 0.77), (-0.22, 0.40), (0.18, 0.25), (0.53, 0.18),
     (0.05, 0.28), (-0.52, 0.77)],
    [(-0.55, -0.30), (-0.18, -0.34), (0.32, -0.24), (0.70, -0.16)],
    [(-0.55, 0.30), (-0.18, 0.34), (0.32, 0.24), (0.70, 0.16)],
    # Canopy and forward sensor spine.
    [(-0.04, -0.19), (0.18, -0.16), (0.44, -0.08), (0.60, 0.0),
     (0.44, 0.08), (0.18, 0.16), (-0.04, 0.19), (-0.18, 0.0),
     (-0.04, -0.19)],
    [(0.20, -0.10), (0.42, 0.0), (0.20, 0.10)],
    [(0.45, -0.13), (0.96, -0.08), (1.52, 0.0)],
    [(0.45, 0.13), (0.96, 0.08), (1.52, 0.0)],
    # Short paired canards and integrated weapon rails.
    [(0.56, -0.18), (0.82, -0.34), (1.02, -0.32)],
    [(0.56, 0.18), (0.82, 0.34), (1.02, 0.32)],
    [(0.44, -0.26), (0.95, -0.43), (1.20, -0.40)],
    [(0.44, 0.26), (0.95, 0.43), (1.20, 0.40)],
    # Twin engine nacelles and the central vector nozzle.
    [(-0.98, -0.32), (-0.72, -0.32), (-0.66, -0.22),
     (-0.72, -0.12), (-0.98, -0.12), (-0.98, -0.32)],
    [(-0.98, 0.12), (-0.72, 0.12), (-0.66, 0.22),
     (-0.72, 0.32), (-0.98, 0.32), (-0.98, 0.12)],
    [(-0.37, -0.47), (-0.04, -0.34), (0.28, -0.25)],
    [(-0.37, 0.47), (-0.04, 0.34), (0.28, 0.25)],
]
SCOUT_ENG = [(-1.12, -0.22), (-1.12, 0.22), (-1.15, 0.0)]

# Gunship: modular artillery craft with dorsal/ventral rail pods and
# separated rear vector nacelles.
GUNSHIP = [
    # Main armored body and reinforced prow.
    [(1.42, 0.0), (0.88, -0.17), (0.20, -0.35), (-0.72, -0.42),
     (-1.24, -0.16), (-1.24, 0.16), (-0.72, 0.42), (0.20, 0.35),
     (0.88, 0.17), (1.42, 0.0)],
    # Dorsal and ventral armor plates.
    [(-0.72, -0.34), (-0.56, -0.72), (0.10, -0.78), (0.48, -0.40),
     (0.08, -0.28), (-0.72, -0.34)],
    [(-0.72, 0.34), (-0.56, 0.72), (0.10, 0.78), (0.48, 0.40),
     (0.08, 0.28), (-0.72, 0.34)],
    [(-0.20, -0.34), (-0.02, -0.58), (0.45, -0.54), (0.62, -0.34)],
    [(-0.20, 0.34), (-0.02, 0.58), (0.45, 0.54), (0.62, 0.34)],
    # Twin rail-cannon housings and parallel barrels.
    [(0.16, -0.40), (0.46, -0.80), (0.94, -0.78),
     (1.08, -0.48), (0.80, -0.24), (0.16, -0.40)],
    [(0.16, 0.40), (0.46, 0.80), (0.94, 0.78),
     (1.08, 0.48), (0.80, 0.24), (0.16, 0.40)],
    [(0.82, -0.50), (1.30, -0.50)],
    [(0.84, -0.62), (1.26, -0.62)],
    [(0.82, 0.50), (1.30, 0.50)],
    [(0.84, 0.62), (1.26, 0.62)],
    # Rear vector nacelles on short armored struts.
    [(-1.08, -0.62), (-0.86, -0.78), (-0.32, -0.70),
     (-0.30, -0.50), (-0.78, -0.38), (-1.08, -0.46), (-1.08, -0.62)],
    [(-1.08, 0.62), (-0.86, 0.78), (-0.32, 0.70),
     (-0.30, 0.50), (-0.78, 0.38), (-1.08, 0.46), (-1.08, 0.62)],
    [(-0.78, -0.40), (-0.52, -0.30)],
    [(-0.78, 0.40), (-0.52, 0.30)],
    # Command deck, reactor ring, and segmented hull seams.
    [(-0.70, -0.20), (-0.42, -0.38), (0.02, -0.36),
     (0.22, -0.18), (0.02, -0.04), (-0.42, -0.04), (-0.70, -0.20)],
    [(-0.70, 0.20), (-0.42, 0.38), (0.02, 0.36),
     (0.22, 0.18), (0.02, 0.04), (-0.42, 0.04), (-0.70, 0.20)],
    [(-0.22, -0.20), (-0.08, -0.36), (0.08, -0.20),
     (0.08, 0.20), (-0.08, 0.36), (-0.22, 0.20), (-0.22, -0.20)],
    [(-0.02, -0.17), (0.22, -0.17)],
    [(-0.02, 0.17), (0.22, 0.17)],
    [(0.54, -0.22), (0.54, 0.22)],
    [(0.94, -0.18), (0.94, 0.18)],
]
GUNSHIP_ENG = [(-1.04, -0.53), (-1.04, 0.53)]

# Marauder: a fast strike platform with split wing modules and twin rail pods.
# The open, separated profile distinguishes it from the Dreadnought's solid
# armored slab while keeping each panel individually readable at game scale.
MARAUDER = [
    # Narrow central fuselage and reinforced prow.
    [(1.68, 0.0), (1.30, -0.12), (0.78, -0.19), (0.10, -0.22),
     (-0.72, -0.25), (-1.02, -0.12), (-1.10, 0.0), (-1.02, 0.12),
     (-0.72, 0.25), (0.10, 0.22), (0.78, 0.19), (1.30, 0.12),
     (1.68, 0.0)],
    # Split wing modules sweep out and back around the central hull.
    [(0.30, -0.24), (0.78, -0.67), (1.02, -1.08), (0.62, -1.22),
     (0.18, -0.98), (-0.50, -0.57), (-0.72, -0.34), (-0.22, -0.42),
     (0.30, -0.24)],
    [(0.22, 0.24), (0.66, 0.50), (0.95, 0.93), (0.57, 1.17),
     (0.10, 0.94), (-0.55, 0.56), (-0.76, 0.34), (-0.20, 0.40),
     (0.22, 0.24)],
    # Fine panel seams inside the wing modules.
    [(0.02, -0.48), (0.50, -0.72), (0.77, -1.00), (0.39, -0.91),
     (-0.25, -0.56)],
    [(0.02, 0.47), (0.48, 0.69), (0.73, 0.95), (0.34, 0.86),
     (-0.30, 0.55)],
    # Twin rail cannons and their lower guide rails.
    [(0.68, -0.28), (1.16, -0.31), (1.58, -0.31)],
    [(0.68, -0.37), (1.11, -0.39), (1.48, -0.39)],
    [(0.68, 0.28), (1.16, 0.31), (1.58, 0.31)],
    [(0.68, 0.37), (1.11, 0.39), (1.48, 0.39)],
    # Separated engine pods and their support struts.
    [(-0.76, -0.30), (-1.30, -0.24), (-1.50, -0.30),
     (-1.44, -0.43), (-0.90, -0.48), (-0.76, -0.30)],
    [(-0.76, 0.30), (-1.30, 0.24), (-1.50, 0.30),
     (-1.44, 0.43), (-0.90, 0.48), (-0.76, 0.30)],
    [(-1.42, -0.34), (-1.60, -0.34)],
    [(-1.42, 0.34), (-1.60, 0.34)],
    [(-0.76, -0.26), (-0.42, -0.16)],
    [(-0.76, 0.26), (-0.42, 0.16)],
    # Forward sensor fins and the reactor spine.
    [(1.08, -0.12), (1.34, -0.34), (1.49, -0.34)],
    [(1.08, 0.12), (1.27, 0.29), (1.43, 0.29)],
    [(-0.24, 0.0), (-0.04, -0.16), (0.18, 0.0),
     (-0.04, 0.16), (-0.24, 0.0)],
    [(0.18, 0.0), (0.85, 0.0)],
    [(-0.76, -0.10), (-0.64, -0.10)],
    [(-0.76, 0.10), (-0.64, 0.10)],
    [(-0.49, -0.10), (-0.37, -0.10)],
    [(-0.49, 0.10), (-0.37, 0.10)],
    [(0.48, -0.10), (0.60, -0.10)],
    [(0.48, 0.10), (0.60, 0.10)],
]
MARAUDER_ENG = [(-1.47, -0.34), (-1.47, 0.34)]

# Dreadnought: a broad, layered capital hull built around a spinal rail gun.
# The outboard armor vanes, dorsal/ventral turrets and reactor housing are
# separate polylines so the existing battle-damage pass can scar them away.
DREADNOUGHT = [
    [(1.72, 0.0), (1.40, -0.16), (1.08, -0.37), (0.68, -0.50),
     (0.30, -0.58), (-0.28, -0.60), (-0.70, -0.52), (-1.02, -0.40),
     (-1.20, -0.65), (-1.45, -1.08), (-1.67, -1.23), (-1.63, -0.88),
     (-1.43, -0.35), (-1.64, -0.18), (-1.70, 0.0),
     (-1.64, 0.18), (-1.43, 0.35), (-1.63, 0.88), (-1.67, 1.23),
     (-1.45, 1.08), (-1.20, 0.65), (-1.02, 0.40), (-0.70, 0.52),
     (-0.28, 0.60), (0.30, 0.58), (0.68, 0.50), (1.08, 0.37),
     (1.40, 0.16), (1.72, 0.0)],
    # Layered armored vanes around the wing roots.
    [(-0.54, -0.48), (-0.70, -0.88), (-1.35, -1.14), (-1.22, -0.72),
     (-0.90, -0.40), (-0.54, -0.48)],
    [(-0.54, 0.48), (-0.70, 0.88), (-1.35, 1.14), (-1.22, 0.72),
     (-0.90, 0.40), (-0.54, 0.48)],
    # Dorsal and ventral turret housings with twin barrels.
    [(0.02, -0.48), (0.16, -0.92), (0.58, -0.96), (0.78, -0.72),
     (0.62, -0.48), (0.02, -0.48)],
    [(0.02, 0.48), (0.16, 0.92), (0.58, 0.96), (0.78, 0.72),
     (0.62, 0.48), (0.02, 0.48)],
    [(0.52, -0.76), (1.20, -0.76)],
    [(0.52, -0.61), (1.20, -0.61)],
    [(0.52, 0.76), (1.20, 0.76)],
    [(0.52, 0.61), (1.20, 0.61)],
    # Three spinal rails converge on the reinforced prow.
    [(-0.90, -0.20), (-0.36, -0.12), (0.26, -0.09), (1.16, -0.04),
     (1.78, 0.0)],
    [(-0.90, 0.20), (-0.36, 0.12), (0.26, 0.09), (1.16, 0.04),
     (1.78, 0.0)],
    [(-0.78, 0.0), (0.22, 0.0), (1.78, 0.0)],
    # Reactor cage and cross-bracing.
    [(-0.48, -0.34), (-0.12, -0.42), (0.22, 0.0), (-0.12, 0.42),
     (-0.48, 0.34), (-0.70, 0.0), (-0.48, -0.34)],
    [(-1.00, -0.36), (-0.98, 0.36)],
    [(-0.48, -0.50), (-0.48, 0.50)],
    [(0.92, -0.40), (0.92, 0.40)],
    [(1.32, -0.20), (1.32, 0.20)],
]
DREADNOUGHT_ENG = [(-1.52, -0.18), (-1.52, 0.18), (-1.43, -0.82),
                   (-1.43, 0.82)]

# Tender: the fleet's supply hauler - a long plain hull with a cargo pod
# slung either side, a cab bulkhead, and no guns at all. It runs from you,
# and it leaves if you let it.
_TD_P = [(0.36, -0.34), (0.36, -0.80), (-0.56, -0.80), (-0.56, -0.34)]
TENDER = [
    [(0.98, 0.0), (0.72, -0.28), (-0.78, -0.34), (-0.98, -0.14),
     (-0.98, 0.14), (-0.78, 0.34), (0.72, 0.28), (0.98, 0.0)],
    _TD_P, flip(_TD_P),
    [(-0.10, -0.80), (-0.10, -0.34)], [(-0.10, 0.34), (-0.10, 0.80)],
    [(0.72, -0.28), (0.72, 0.28)],
]
TENDER_ENG = [(-0.98, -0.08), (-0.98, 0.08)]
