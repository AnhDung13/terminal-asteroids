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
# Interceptor: a lean dart with closed swept strakes and a tail notch.
_SC_W = [(0.24, -0.19), (-0.32, -0.90), (-0.72, -0.66), (-0.44, -0.15),
         (0.24, -0.19)]
SCOUT = [
    [(1.22, 0.0), (0.32, -0.25), (-0.66, -0.17), (-0.56, 0.0),
     (-0.66, 0.17), (0.32, 0.25), (1.22, 0.0)],
    _SC_W, flip(_SC_W),
]
SCOUT_ENG = [(-0.60, -0.11), (-0.60, 0.11)]

# Gunship: broad shoulders, two stubby outboard nacelles on short pylons.
_GS_N = [(0.30, -0.88), (-0.50, -0.88), (-0.64, -0.62), (0.16, -0.62),
         (0.30, -0.88)]
_GS_S = [(0.14, -0.32), (0.22, -0.66)]
GUNSHIP = [
    [(1.12, 0.0), (0.48, -0.30), (-0.58, -0.38), (-0.84, -0.16),
     (-0.84, 0.16), (-0.58, 0.38), (0.48, 0.30), (1.12, 0.0)],
    _GS_N, flip(_GS_N), _GS_S, flip(_GS_S),
    [(0.64, -0.12), (0.28, -0.12), (0.28, 0.12), (0.64, 0.12)],
]
GUNSHIP_ENG = [(-0.82, -0.10), (-0.82, 0.10), (-0.62, -0.75), (-0.62, 0.75)]

# Marauder: the mini-boss - a raked prow and heavy delta wings.
_MR_W = [(0.34, -0.32), (0.06, -1.08), (-0.68, -1.24), (-0.98, -0.72),
         (-0.62, -0.36)]
_MR_P = [(-0.16, -0.80), (0.06, -0.80)]
MARAUDER = [
    [(1.30, 0.0), (0.78, -0.20), (0.36, -0.36), (-0.72, -0.42),
     (-1.02, -0.22), (-1.02, 0.22), (-0.72, 0.42), (0.36, 0.36),
     (0.78, 0.20), (1.30, 0.0)],
    _MR_W, flip(_MR_W), _MR_P, flip(_MR_P),
    [(0.64, 0.0), (-0.34, 0.0)],
    [(0.12, -0.36), (0.12, 0.36)],
    [(-0.46, -0.36), (-0.46, 0.36)],
]
MARAUDER_ENG = [(-1.00, -0.13), (-1.00, 0.13), (-0.94, -0.92), (-0.94, 0.92)]

# Dreadnought: the wave-ten capital ship. Spinal gun, flanking pods.
_DR_W = [(0.48, -0.42), (0.22, -1.18), (-0.56, -1.38), (-1.06, -1.06),
         (-1.12, -0.56), (-0.76, -0.46)]
_DR_P = [(-0.32, -1.02), (0.02, -1.02), (0.08, -0.80), (-0.36, -0.80),
         (-0.32, -1.02)]
DREADNOUGHT = [
    [(1.50, 0.0), (1.02, -0.22), (0.56, -0.46), (-0.62, -0.54),
     (-1.18, -0.32), (-1.28, 0.0), (-1.18, 0.32), (-0.62, 0.54),
     (0.56, 0.46), (1.02, 0.22), (1.50, 0.0)],
    _DR_W, flip(_DR_W), _DR_P, flip(_DR_P),
    [(0.90, 0.0), (-0.58, 0.0)],
    [(0.32, -0.48), (0.32, 0.48)],
    [(-0.26, -0.52), (-0.26, 0.52)],
    [(-0.82, -0.42), (-0.82, 0.42)],
]
DREADNOUGHT_ENG = [(-1.26, -0.16), (-1.26, 0.16), (-1.08, -0.90),
                   (-1.08, 0.90)]

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

