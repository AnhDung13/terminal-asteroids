"""The palette: named curses attributes, and ramps that shade them.

Two tiers - a 256-colour set when the terminal has it, an 8-colour fallback
when it does not - behind one lookup, so nothing downstream has to ask.
"""

import curses


PAL = {}      # name -> curses attribute
RAMPS = {}    # name -> list of attributes, dark end last
_pairs = {}
_next_pair = [1]
_BG = [-1]


def A(name):
    return PAL.get(name, 0)


def ramp(name, t):
    """Sample a colour ramp; t=0 is the hot/bright end, t=1 the cold end."""
    r = RAMPS.get(name)
    if not r:
        return 0
    i = int(t * (len(r) - 1) + 0.5)
    return r[max(0, min(len(r) - 1, i))]


def _mk(color, bold=False):
    """Allocate (and cache) a colour pair for a foreground colour number."""
    if color not in _pairs:
        i = _next_pair[0]
        attr = 0
        if i < min(curses.COLOR_PAIRS, 250):
            try:
                curses.init_pair(i, color, _BG[0])
                attr = curses.color_pair(i)
                _next_pair[0] = i + 1
            except curses.error:
                attr = 0
        _pairs[color] = attr
    return _pairs[color] | (curses.A_BOLD if bold else 0)


def init_colors():
    curses.start_color()
    try:
        curses.use_default_colors()
        _BG[0] = -1
    except curses.error:
        _BG[0] = curses.COLOR_BLACK
    rich = curses.COLORS >= 256

    if rich:
        PAL["ship"] = _mk(51, True)
        PAL["ship_dim"] = _mk(37)
        PAL["bullet"] = _mk(228, True)
        PAL["ast3"] = _mk(146)
        PAL["ast2"] = _mk(180)
        PAL["ast1"] = _mk(210)
        PAL["flash"] = _mk(231, True)
        PAL["foe1"] = _mk(84, True)      # interceptor
        PAL["foe2"] = _mk(215, True)     # gunship
        PAL["foe3"] = _mk(207, True)     # marauder - mini boss
        PAL["foe4"] = _mk(203, True)     # dreadnought - boss
        PAL["foe5"] = _mk(153)           # tender - unarmed, and not bold
        PAL["foeshot"] = _mk(120)
        PAL["hot"] = _mk(214, True)      # a rock fragment you have launched
        PAL["mine"] = _mk(196, True)
        PAL["ui"] = _mk(45)
        PAL["ui_hi"] = _mk(87, True)
        PAL["accent"] = _mk(213, True)
        PAL["warn"] = _mk(215, True)
        PAL["dim"] = _mk(240)
        PAL["frame"] = _mk(238)
        RAMPS["fire"] = [_mk(231, True), _mk(228, True), _mk(221), _mk(214),
                         _mk(208), _mk(202), _mk(160), _mk(124), _mk(52)]
        RAMPS["star"] = [_mk(255, True), _mk(252), _mk(245), _mk(240),
                         _mk(238)]
        RAMPS["title"] = [_mk(87, True), _mk(51, True), _mk(45), _mk(39),
                          _mk(69), _mk(105)]
        RAMPS["shock"] = [_mk(231, True), _mk(159), _mk(45), _mk(69),
                          _mk(61), _mk(238)]
        RAMPS["neb"] = [_mk(183, True), _mk(177), _mk(140), _mk(97),
                        _mk(60)]
    else:
        W, Y, R, C, M, G = (curses.COLOR_WHITE, curses.COLOR_YELLOW,
                            curses.COLOR_RED, curses.COLOR_CYAN,
                            curses.COLOR_MAGENTA, curses.COLOR_GREEN)
        PAL["ship"] = _mk(C, True)
        PAL["ship_dim"] = _mk(C)
        PAL["bullet"] = _mk(Y, True)
        PAL["ast3"] = _mk(W)
        PAL["ast2"] = _mk(Y)
        PAL["ast1"] = _mk(M, True)
        PAL["flash"] = _mk(W, True)
        PAL["foe1"] = _mk(G, True)
        PAL["foe2"] = _mk(Y, True)
        PAL["foe3"] = _mk(M, True)
        PAL["foe4"] = _mk(R, True)
        PAL["foe5"] = _mk(W)
        PAL["foeshot"] = _mk(G)
        PAL["hot"] = _mk(Y, True)
        PAL["mine"] = _mk(R, True)
        PAL["ui"] = _mk(C)
        PAL["ui_hi"] = _mk(C, True)
        PAL["accent"] = _mk(M, True)
        PAL["warn"] = _mk(Y, True)
        PAL["dim"] = _mk(W) | curses.A_DIM
        PAL["frame"] = _mk(W) | curses.A_DIM
        RAMPS["fire"] = [_mk(W, True), _mk(Y, True), _mk(Y), _mk(R, True),
                         _mk(R), _mk(R) | curses.A_DIM]
        RAMPS["star"] = [_mk(W, True), _mk(W), _mk(W) | curses.A_DIM]
        RAMPS["title"] = [_mk(C, True), _mk(C), _mk(M, True), _mk(M)]
        RAMPS["shock"] = [_mk(W, True), _mk(C, True), _mk(C),
                          _mk(C) | curses.A_DIM]
        RAMPS["neb"] = [_mk(M, True), _mk(M), _mk(M) | curses.A_DIM]
