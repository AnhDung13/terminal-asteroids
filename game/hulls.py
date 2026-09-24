"""Every hull in the game, yours and theirs, as polylines in local coords.

Nose along +x, one unit = the ship's radius, so one rotate-and-scale draws
any of them at any size and a silhouette is designed as a shape rather than
written as drawing code.
"""

import math

from .screen import PX, PY


# Every hull in the game - yours and theirs - is a list of polylines in local
# coordinates: nose along +x, one unit = the ship's radius. One rotate-and-
# scale draws any of them at any size, so a silhouette is designed as a shape
# rather than written as drawing code.
def flip(poly):
    return [(px, -py) for px, py in poly]


def _profile(parts, length, beam):
    """Set a hull's visual proportions without changing its combat radius."""
    return [[(px * length, py * beam) for px, py in poly]
            for poly in parts]


def _stations(points, length, beam):
    return [(px * length, py * beam) for px, py in points]


def draw_hull(f, x, y, ang, r, parts, attr, prio=4):
    ca, sa = math.cos(ang) * r, math.sin(ang) * r
    for poly in parts:
        px, py = poly[0]
        ax, ay = x + px * ca - py * sa, y + px * sa + py * ca
        for px, py in poly[1:]:
            bx, by = x + px * ca - py * sa, y + px * sa + py * ca
            f.line(ax, ay, bx, by, attr, prio)
            ax, ay = bx, by


def fill_hull(f, x, y, ang, r, parts, color, prio=2):
    """Wash closed armor plates behind braille lines without thickening them."""
    if not color:
        return
    ca, sa = math.cos(ang) * r * f.z, math.sin(ang) * r * f.z
    for poly in parts:
        if len(poly) < 3:
            continue
        pts = [((x * f.z + px * ca - py * sa),
                (y * f.z + px * sa + py * ca)) for px, py in poly]
        lo = int(min(py for _, py in pts) // PY)
        hi = int(max(py for _, py in pts) // PY) + 1
        for cy in range(lo, hi):
            py = cy * PY + PY / 2
            cuts = []
            for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
                if (y0 <= py < y1) or (y1 <= py < y0):
                    cuts.append(x0 + (py - y0) * (x1 - x0) / (y1 - y0))
            cuts.sort()
            for left, right in zip(cuts[::2], cuts[1::2]):
                for cx in range(int(left // PX), int(right // PX) + 1):
                    if left <= cx * PX + PX / 2 < right:
                        f.wash(cx, cy, color, prio)


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
# Scout: a compact needle with long swept delta wings. Keep the wing edges
# open so this still reads as an interceptor at the smallest playable zoom.
SCOUT = [
    [(1.62, 0.0), (0.42, -0.18), (-0.12, -0.30), (-0.84, -1.08),
     (-1.20, -1.18), (-0.75, -0.42), (-1.10, -0.24), (-1.22, 0.0),
     (-1.10, 0.24), (-0.75, 0.42), (-1.20, 1.18), (-0.84, 1.08),
     (-0.12, 0.30), (0.42, 0.18), (1.62, 0.0)],
    # A recessed canopy and a long, clean sensor spine.
    [(-0.48, 0.0), (-0.10, -0.20), (0.38, -0.12), (0.62, 0.0),
     (0.38, 0.12), (-0.10, 0.20), (-0.48, 0.0)],
    [(0.62, 0.0), (1.30, 0.0)],
    # The two wing-root cuts expose the negative space around the body.
    [(-0.78, -0.96), (-0.48, -0.48), (0.04, -0.30)],
    [(-0.78, 0.96), (-0.48, 0.48), (0.04, 0.30)],
    # Short off-axis weapon tips and paired engine housings.
    [(0.30, -0.22), (0.75, -0.38), (1.08, -0.35)],
    [(0.30, 0.22), (0.75, 0.38), (1.08, 0.35)],
    [(-1.10, -0.24), (-0.78, -0.24), (-0.70, -0.10)],
    [(-1.10, 0.24), (-0.78, 0.24), (-0.70, 0.10)],
    # Separate panels keep the wings visible as they turn across the dots.
    [(-0.98, -1.06), (-0.68, -0.72)],
    [(-0.98, 1.06), (-0.68, 0.72)],
    [(-0.48, -0.62), (-0.08, -0.32)],
    [(-0.48, 0.62), (-0.08, 0.32)],
    [(0.48, -0.19), (0.82, -0.16)],
    [(0.48, 0.19), (0.82, 0.16)],
    [(-1.14, -0.14), (-1.24, -0.14)],
    [(-1.14, 0.14), (-1.24, 0.14)],
]
SCOUT_ENG = [(-1.16, -0.20), (-1.16, 0.20)]
SCOUT_TRIM = [
    [(-1.13, -1.13), (-0.84, -1.04), (-0.49, -0.64)],
    [(-1.13, 1.13), (-0.84, 1.04), (-0.49, 0.64)],
    [(-0.24, -0.13), (0.34, -0.10), (0.59, 0.0)],
    [(-0.24, 0.13), (0.34, 0.10), (0.59, 0.0)],
    [(-1.20, -0.20), (-1.09, -0.20)],
    [(-1.20, 0.20), (-1.09, 0.20)],
]
SCOUT_DETAIL = [
    [(-0.84, -0.93), (-0.48, -0.51), (-0.14, -0.37)],
    [(-0.84, 0.93), (-0.48, 0.51), (-0.14, 0.37)],
    [(-0.42, -0.10), (0.20, -0.08), (0.42, 0.0)],
    [(-0.42, 0.10), (0.20, 0.08), (0.42, 0.0)],
    [(-0.99, -0.31), (-0.82, -0.31)],
    [(-0.99, 0.31), (-0.82, 0.31)],
]
_SCOUT_PROFILE = (1.16, 0.82)
SCOUT = _profile(SCOUT, *_SCOUT_PROFILE)
SCOUT_TRIM = _profile(SCOUT_TRIM, *_SCOUT_PROFILE)
SCOUT_DETAIL = _profile(SCOUT_DETAIL, *_SCOUT_PROFILE)
SCOUT_ENG = _stations(SCOUT_ENG, *_SCOUT_PROFILE)

# Gunship: a low-profile artillery craft. A slim arrow of a hull with the
# command deck amidships, twin rail pods running forward either side of the
# nose, and two rear nacelles held off the body on short struts, each with a
# panel slash. Drawn at 24 dots long, so every line here is at least a dot
# and a half from its neighbour: closer than that and braille fills it in.
_GS_NAC = [(-1.22, -0.46), (-1.08, -0.78), (-0.58, -0.84), (-0.30, -0.62),
           (-0.42, -0.38), (-1.10, -0.36), (-1.22, -0.46)]
_GS_SLASH = [(-0.98, -0.70), (-0.64, -0.50)]
_GS_STRUT = [(-0.80, -0.36), (-0.80, -0.22)]
_GS_RAIL_A = [(0.42, -0.31), (1.34, -0.31), (1.40, -0.44),
              (0.54, -0.44), (0.42, -0.31)]
_GS_RAIL_B = [(0.72, -0.37), (1.24, -0.37)]
_GS_MOUNT = [(0.30, -0.17), (0.42, -0.30)]
GUNSHIP = [
    # The hull: a slim arrow, tail to nose.
    [(1.60, 0.0), (0.55, -0.15), (0.05, -0.22), (-0.45, -0.24),
     (-1.05, -0.17), (-1.36, 0.0), (-1.05, 0.17), (-0.45, 0.24),
     (0.05, 0.22), (0.55, 0.15), (1.60, 0.0)],
    # Command deck amidships, and the spine running out to the nose.
    [(-0.42, 0.0), (-0.30, -0.13), (-0.02, -0.13), (0.10, 0.0),
     (-0.02, 0.13), (-0.30, 0.13), (-0.42, 0.0)],
    [(0.24, 0.0), (1.10, 0.0)],
    # Rear nacelles, detached, with their panel slash and strut.
    _GS_NAC, flip(_GS_NAC), _GS_SLASH, flip(_GS_SLASH),
    _GS_STRUT, flip(_GS_STRUT),
    # Twin rail pods, forward, on a short mount each.
    _GS_RAIL_A, flip(_GS_RAIL_A), _GS_RAIL_B, flip(_GS_RAIL_B),
    _GS_MOUNT, flip(_GS_MOUNT),
]
GUNSHIP_ENG = [(-1.22, -0.58), (-1.22, 0.58), (-1.36, 0.0)]
GUNSHIP_TRIM = [
    [(1.15, -0.42), (1.38, -0.42)],
    [(1.15, 0.42), (1.38, 0.42)],
    [(-1.20, -0.58), (-1.03, -0.58)],
    [(-1.20, 0.58), (-1.03, 0.58)],
    [(-0.24, 0.0), (0.15, 0.0)],
]
GUNSHIP_DETAIL = [
    [(-1.05, -0.54), (-0.76, -0.57), (-0.49, -0.49)],
    [(-1.05, 0.54), (-0.76, 0.57), (-0.49, 0.49)],
    [(-0.79, -0.72), (-0.62, -0.67)],
    [(-0.79, 0.72), (-0.62, 0.67)],
    [(-0.87, -0.08), (-0.26, -0.08), (0.10, -0.04)],
    [(-0.87, 0.08), (-0.26, 0.08), (0.10, 0.04)],
    [(-0.60, -0.18), (-0.60, 0.18)],
    [(0.05, -0.17), (0.05, 0.17)],
    [(1.18, -0.31), (1.18, -0.44)],
    [(1.18, 0.31), (1.18, 0.44)],
]
_GUNSHIP_PROFILE = (1.25, 0.76)
GUNSHIP = _profile(GUNSHIP, *_GUNSHIP_PROFILE)
GUNSHIP_TRIM = _profile(GUNSHIP_TRIM, *_GUNSHIP_PROFILE)
GUNSHIP_DETAIL = _profile(GUNSHIP_DETAIL, *_GUNSHIP_PROFILE)
GUNSHIP_ENG = _stations(GUNSHIP_ENG, *_GUNSHIP_PROFILE)

# Marauder: a fast strike platform with split wing modules and twin rail pods.
# The open, separated profile distinguishes it from the Dreadnought's solid
# armored slab while keeping each panel individually readable at game scale.
MARAUDER = [
    # Thin central hull: the empty channels around it are the silhouette.
    [(1.60, 0.0), (1.18, -0.16), (0.45, -0.24), (-0.78, -0.25),
     (-1.10, -0.12), (-1.18, 0.0), (-1.10, 0.12), (-0.78, 0.25),
     (0.45, 0.24), (1.18, 0.16), (1.60, 0.0)],
    # Broad, independent swept blades joined only at the roots.
    [(0.30, -0.28), (0.88, -0.66), (0.98, -1.02),
     (-0.40, -1.38), (-1.18, -1.42), (-0.70, -0.88),
     (-0.22, -0.52), (0.30, -0.28)],
    [(0.30, 0.28), (0.88, 0.66), (0.98, 1.02),
     (-0.40, 1.38), (-1.18, 1.42), (-0.70, 0.88),
     (-0.22, 0.52), (0.30, 0.28)],
    [(-0.92, -1.22), (-0.38, -1.12), (0.54, -0.78)],
    [(-0.92, 1.22), (-0.38, 1.12), (0.54, 0.78)],
    # Outboard pods and the two rails reach beyond the prow.
    [(0.60, -0.39), (1.30, -0.39), (1.82, -0.39)],
    [(0.60, 0.39), (1.30, 0.39), (1.82, 0.39)],
    [(0.68, -0.52), (1.30, -0.52)],
    [(0.68, 0.52), (1.30, 0.52)],
    [(0.44, -0.24), (0.62, -0.39)],
    [(0.44, 0.24), (0.62, 0.39)],
    # Rear engine pods sit clear of the fuselage and wing plates.
    [(-1.04, -0.48), (-1.62, -0.48), (-1.76, -0.64),
     (-1.62, -0.78), (-1.04, -0.78), (-0.90, -0.62),
     (-1.04, -0.48)],
    [(-1.04, 0.48), (-1.62, 0.48), (-1.76, 0.64),
     (-1.62, 0.78), (-1.04, 0.78), (-0.90, 0.62),
     (-1.04, 0.48)],
    [(-0.90, -0.62), (-0.72, -0.26)],
    [(-0.90, 0.62), (-0.72, 0.26)],
    # A small reactor diamond and one long spine remain legible in braille.
    [(-0.35, 0.0), (-0.08, -0.18), (0.16, 0.0),
     (-0.08, 0.18), (-0.35, 0.0)],
    [(0.16, 0.0), (1.23, 0.0)],
    # Plate seams and recessed vents break up the broad wing surfaces.
    [(-0.68, -0.91), (-0.36, -0.96)],
    [(-0.68, 0.91), (-0.36, 0.96)],
    [(0.02, -1.12), (0.38, -0.97)],
    [(0.02, 1.12), (0.38, 0.97)],
    [(-1.52, -0.63), (-1.26, -0.63)],
    [(-1.52, 0.63), (-1.26, 0.63)],
    [(0.93, -0.13), (1.16, -0.13)],
    [(0.93, 0.13), (1.16, 0.13)],
]
MARAUDER_ENG = [(-1.74, -0.63), (-1.74, 0.63)]
MARAUDER_TRIM = [
    [(-1.13, -1.38), (-0.74, -1.35)],
    [(-1.13, 1.38), (-0.74, 1.35)],
    [(-0.34, -1.32), (0.08, -1.18)],
    [(-0.34, 1.32), (0.08, 1.18)],
    [(1.54, -0.39), (1.77, -0.39)],
    [(1.54, 0.39), (1.77, 0.39)],
    [(-1.66, -0.62), (-1.53, -0.62)],
    [(-1.66, 0.62), (-1.53, 0.62)],
    [(-0.10, 0.0), (0.25, 0.0)],
]
MARAUDER_DETAIL = [
    # Two inset blade panels, with a long diagonal reinforcing spar.
    [(-0.97, -1.29), (-0.38, -1.22), (0.62, -0.94)],
    [(-0.97, 1.29), (-0.38, 1.22), (0.62, 0.94)],
    [(-0.70, -0.98), (-0.17, -0.67), (0.38, -0.48)],
    [(-0.70, 0.98), (-0.17, 0.67), (0.38, 0.48)],
    [(-0.44, -1.20), (-0.18, -0.86)],
    [(-0.44, 1.20), (-0.18, 0.86)],
    # Segmented central armor and a recessed reactor channel.
    [(-0.77, -0.16), (1.03, -0.12)],
    [(-0.77, 0.16), (1.03, 0.12)],
    [(-0.60, -0.23), (-0.60, 0.23)],
    [(0.30, -0.22), (0.30, 0.22)],
    [(0.84, -0.17), (0.84, 0.17)],
    # Blocky engine grilles and the mounts behind the twin rails.
    [(-1.46, -0.49), (-1.46, -0.77)],
    [(-1.46, 0.49), (-1.46, 0.77)],
    [(-1.24, -0.49), (-1.24, -0.77)],
    [(-1.24, 0.49), (-1.24, 0.77)],
    [(0.83, -0.30), (0.83, -0.52)],
    [(0.83, 0.30), (0.83, 0.52)],
]
_MARAUDER_PROFILE = (1.43, 0.55)
MARAUDER = _profile(MARAUDER, *_MARAUDER_PROFILE)
MARAUDER_TRIM = _profile(MARAUDER_TRIM, *_MARAUDER_PROFILE)
MARAUDER_DETAIL = _profile(MARAUDER_DETAIL, *_MARAUDER_PROFILE)
MARAUDER_ENG = _stations(MARAUDER_ENG, *_MARAUDER_PROFILE)

# Dreadnought: a broad, layered capital hull built around a spinal rail gun.
# The outboard armor vanes, dorsal/ventral turrets and reactor housing are
# separate polylines so the existing battle-damage pass can scar them away.
DREADNOUGHT = [
    # Slim spinal hull and prow: the armor shelves sit outside it.
    [(1.78, 0.0), (1.46, -0.12), (0.82, -0.19), (-0.68, -0.24),
     (-1.18, -0.18), (-1.36, 0.0), (-1.18, 0.18),
     (-0.68, 0.24), (0.82, 0.19), (1.46, 0.12), (1.78, 0.0)],
    # Two square engine housings, well clear of the central rail.
    [(-1.72, -0.54), (-1.56, -0.65), (-0.94, -0.65),
     (-0.88, -0.39), (-1.56, -0.39), (-1.72, -0.54)],
    [(-1.72, 0.54), (-1.56, 0.65), (-0.94, 0.65),
     (-0.88, 0.39), (-1.56, 0.39), (-1.72, 0.54)],
    # Aft vanes layer forward from the engines.
    [(-1.06, -0.37), (-0.54, -0.80), (0.12, -0.82),
     (0.38, -0.61), (-0.18, -0.29)],
    [(-1.06, 0.37), (-0.54, 0.80), (0.12, 0.82),
     (0.38, 0.61), (-0.18, 0.29)],
    # Forward armored shelves are broad, flat and separated.
    [(0.20, -0.35), (0.50, -0.92), (1.28, -0.88),
     (1.38, -0.63), (1.04, -0.34)],
    [(0.20, 0.35), (0.50, 0.92), (1.28, 0.88),
     (1.38, 0.63), (1.04, 0.34)],
    # A paired turret and long outer barrel on each shelf.
    [(0.30, -0.48), (0.54, -0.60), (0.80, -0.55),
     (0.84, -0.42), (0.30, -0.48)],
    [(0.30, 0.48), (0.54, 0.60), (0.80, 0.55),
     (0.84, 0.42), (0.30, 0.48)],
    [(0.76, -0.52), (1.48, -0.52)],
    [(0.76, 0.52), (1.48, 0.52)],
    # Paired channels frame a single uninterrupted spinal rail.
    [(-0.90, -0.13), (0.32, -0.10), (1.57, -0.04)],
    [(-0.90, 0.13), (0.32, 0.10), (1.57, 0.04)],
    [(-1.08, 0.0), (0.10, 0.0), (1.80, 0.0)],
    [(-0.54, -0.18), (-0.24, -0.25), (0.02, 0.0),
     (-0.24, 0.25), (-0.54, 0.18), (-0.54, -0.18)],
    [(-0.96, -0.16), (-0.96, 0.16)],
    [(1.40, -0.12), (1.40, 0.12)],
]
DREADNOUGHT_ENG = [(-1.70, -0.52), (-1.70, 0.52),
                   (-1.34, -0.12), (-1.34, 0.12)]
DREADNOUGHT_TRIM = [
    [(-1.71, -0.54), (-1.53, -0.54)],
    [(-1.71, 0.54), (-1.53, 0.54)],
    [(-0.46, -0.77), (0.08, -0.79)],
    [(-0.46, 0.77), (0.08, 0.79)],
    [(0.60, -0.89), (1.24, -0.86)],
    [(0.60, 0.89), (1.24, 0.86)],
    [(-0.22, 0.0), (0.22, 0.0)],
    [(1.46, 0.0), (1.76, 0.0)],
]
DREADNOUGHT_DETAIL = [
    # Engine end caps and segmented cooling grilles.
    [(-1.64, -0.47), (-1.47, -0.47)],
    [(-1.64, 0.47), (-1.47, 0.47)],
    [(-1.47, -0.41), (-1.47, -0.64)],
    [(-1.47, 0.41), (-1.47, 0.64)],
    [(-1.24, -0.41), (-1.24, -0.64)],
    [(-1.24, 0.41), (-1.24, 0.64)],
    # Each vane and shelf has a second inset armor course.
    [(-0.82, -0.43), (-0.43, -0.67), (0.07, -0.69)],
    [(-0.82, 0.43), (-0.43, 0.67), (0.07, 0.69)],
    [(0.48, -0.72), (1.16, -0.71), (1.25, -0.61)],
    [(0.48, 0.72), (1.16, 0.71), (1.25, 0.61)],
    [(0.54, -0.87), (0.54, -0.66)],
    [(0.54, 0.87), (0.54, 0.66)],
    # Turret cores and the deep channel around the spinal weapon.
    [(0.46, -0.52), (0.70, -0.52)],
    [(0.46, 0.52), (0.70, 0.52)],
    [(-0.68, -0.08), (1.55, -0.05)],
    [(-0.68, 0.08), (1.55, 0.05)],
    [(-0.55, -0.19), (-0.55, 0.19)],
    [(0.24, -0.19), (0.24, 0.19)],
    [(1.08, -0.14), (1.08, 0.14)],
]
_DREADNOUGHT_PROFILE = (1.38, 0.66)
DREADNOUGHT = _profile(DREADNOUGHT, *_DREADNOUGHT_PROFILE)
DREADNOUGHT_TRIM = _profile(DREADNOUGHT_TRIM, *_DREADNOUGHT_PROFILE)
DREADNOUGHT_DETAIL = _profile(DREADNOUGHT_DETAIL, *_DREADNOUGHT_PROFILE)
DREADNOUGHT_ENG = _stations(DREADNOUGHT_ENG, *_DREADNOUGHT_PROFILE)

# Tender: exposed cargo blocks flank a long unarmed transport spine.
# Wide gaps around the pods make it distinct from the armed line ships.
_TD_P = [(-0.76, -0.48), (-0.66, -1.02), (0.52, -1.02),
         (0.65, -0.48), (-0.76, -0.48)]
TENDER = [
    [(1.46, 0.0), (1.14, -0.24), (0.64, -0.30),
     (-0.92, -0.30), (-1.32, -0.16), (-1.32, 0.16),
     (-0.92, 0.30), (0.64, 0.30), (1.14, 0.24), (1.46, 0.0)],
    _TD_P, flip(_TD_P),
    [(-0.76, -0.48), (-0.80, -0.30), (0.62, -0.30),
     (0.65, -0.48)],
    [(-0.76, 0.48), (-0.80, 0.30), (0.62, 0.30),
     (0.65, 0.48)],
    [(-1.12, 0.0), (0.80, 0.0), (0.94, -0.25),
     (0.94, 0.25)],
]
TENDER_ENG = [(-1.32, -0.12), (-1.32, 0.12)]
TENDER_TRIM = [
    [(-0.51, -0.99), (-0.51, -0.51)],
    [(-0.06, -0.99), (-0.06, -0.51)],
    [(0.42, -0.99), (0.42, -0.51)],
    [(-0.51, 0.99), (-0.51, 0.51)],
    [(-0.06, 0.99), (-0.06, 0.51)],
    [(0.42, 0.99), (0.42, 0.51)],
    [(1.34, -0.09), (1.34, 0.09)],
    [(-1.31, -0.13), (-1.31, 0.13)],
]
TENDER_DETAIL = [
    # The cargo modules read as containers, not smooth wings.
    [(-0.59, -0.83), (0.48, -0.83)],
    [(-0.59, 0.83), (0.48, 0.83)],
    [(-0.45, -0.49), (-0.45, -0.99)],
    [(-0.45, 0.49), (-0.45, 0.99)],
    [(0.16, -0.49), (0.16, -0.99)],
    [(0.16, 0.49), (0.16, 0.99)],
    [(-0.92, -0.17), (0.63, -0.17)],
    [(-0.92, 0.17), (0.63, 0.17)],
    [(-0.44, -0.28), (-0.44, 0.28)],
    [(0.40, -0.28), (0.40, 0.28)],
    [(1.02, -0.15), (1.28, 0.0), (1.02, 0.15)],
]
_TENDER_PROFILE = (1.40, 0.55)
TENDER = _profile(TENDER, *_TENDER_PROFILE)
TENDER_TRIM = _profile(TENDER_TRIM, *_TENDER_PROFILE)
TENDER_DETAIL = _profile(TENDER_DETAIL, *_TENDER_PROFILE)
TENDER_ENG = _stations(TENDER_ENG, *_TENDER_PROFILE)
