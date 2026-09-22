"""Turning what a terminal sends into whether a key is held.

Two paths: the kitty keyboard protocol, which reports releases and makes a
hold exact, and the inference every other terminal needs.
"""

import curses
import re
import sys
import time


PRESS, REPEAT, RELEASE = 1, 2, 3        # key event types, kitty numbering

# The kitty keyboard protocol, spoken by kitty, Ghostty, WezTerm, foot, rio
# and others: ask for it and the terminal reports every key as an escape
# sequence with a press/repeat/release type on it. Flags 1|2|8 - disambiguate
# escapes, report event types, report all keys as escape codes. Pushed on the
# way in, popped on the way out so the shell gets its keyboard back.
KITTY_PUSH = "\x1b[>11u"
KITTY_POP = "\x1b[<u"
KITTY_QUERY = "\x1b[?u\x1b[c"


def tty_write(s):
    try:
        sys.stdout.write(s)
        sys.stdout.flush()
    except (OSError, ValueError):
        pass


def kitty_probe(stdscr, wait=0.4):
    """Does this terminal speak the kitty keyboard protocol?

    `CSI ? u` is answered with `CSI ? flags u` by one that does, and ignored
    by one that does not - so it is chased with a primary device attributes
    query, which every terminal answers, and the wait ends on that reply
    rather than on the timeout.
    """
    tty_write(KITTY_QUERY)
    buf, t0 = [], time.perf_counter()
    while time.perf_counter() - t0 < wait:
        c = stdscr.getch()
        if c == -1:
            if buf and buf[-1] == ord("c"):      # the DA reply is in
                break
            time.sleep(0.005)
            continue
        if c < 256:
            buf.append(c)
    return re.search(r"\x1b\[\?\d+u", "".join(map(chr, buf))) is not None


KEYMAP = {
    curses.KEY_LEFT: ("left",), ord("a"): ("left",), ord("A"): ("left",),
    curses.KEY_RIGHT: ("right",), ord("d"): ("right",), ord("D"): ("right",),
    curses.KEY_UP: ("up",), ord("w"): ("up",), ord("W"): ("up",),
    curses.KEY_DOWN: ("down",), ord("s"): ("down",), ord("S"): ("down",),
    # One-key diagonals. Holding two arrows can only ever be approximated
    # (see Keys), but a single held key repeats reliably, so these give a
    # true, indefinitely sustained diagonal.
    ord("u"): ("up", "right"), ord("U"): ("up", "right"),
    ord("y"): ("up", "left"), ord("Y"): ("up", "left"),
    ord("n"): ("down", "right"), ord("N"): ("down", "right"),
    ord("b"): ("down", "left"), ord("B"): ("down", "left"),
    ord("9"): ("up", "right"), ord("7"): ("up", "left"),
    ord("3"): ("down", "right"), ord("1"): ("down", "left"),
}


class Keys:
    """Held-key emulation, because terminals never report a key release.

    Two facts drive the whole design. A terminal sends a keypress and then,
    after the OS "delay until repeat" (~0.5s), a fast repeat train - so a
    press has to be treated as a hold that expires. And the OS auto-repeats
    only the *most recently pressed* key: tap fire while flying and the arrow
    stops repeating; hold two arrows and the first one goes quiet.

    So a press opens a generous window that covers the repeat delay, and any
    other key event keeps recently-used directions alive at reduced strength
    ("carry"). That is what lets you shoot without stalling and hold two
    arrows for a diagonal. Carry is bounded from each direction's own last
    real press, so releasing a key still stops you.
    """

    # A fresh press has to stay "held" until the OS repeat train starts, or
    # the ship stutters; but every millisecond past that is drift after a tap.
    # The delay is a user setting (~0.25-1.0s on macOS), so rather than guess
    # it, watch for the first repeat of a held key and learn it.
    DELAY_GUESS = 0.50  # until the first repeat is seen
    FIRST_MIN = 0.34
    # High enough to cover a slow terminal's delay-until-repeat once that
    # delay has been measured. It only ever costs drift on a machine that
    # actually is that slow, since first tracks the measured delay.
    FIRST_MAX = 1.35
    # Bridges the gap between repeats. Every millisecond of it is drift after
    # you let go, so rather than sit on a worst-case guess it is measured from
    # the repeat train itself, the same way the delay above is.
    REPEAT = 0.16       # until a train has been seen
    REPEAT_MIN = 0.07
    REPEAT_MAX = 0.28
    # Every millisecond of carry is also thrust you did not ask for, if you
    # really did let go. So it is short while you are steering - a ship that
    # keeps flying after you release is the most infuriating thing there is -
    # and longer after a fire or warp press, which says nothing about whether
    # you meant to change direction.
    CARRY = 0.40        # another direction key carries the others this long
    CARRY_OTHER = 1.0   # a fire/warp/pause press carries them this long
    CARRY_HI = 0.50     # carried push right after the last real press...
    CARRY_LO = 0.10     # ...fading to this as the carry window runs out
    DIRS = ("left", "right", "up", "down")
    OPPOSITE = {"left": "right", "right": "left", "up": "down", "down": "up"}

    def __init__(self):
        self.real = dict.fromkeys(self.DIRS, -9.0)    # last genuine press
        self.hold = dict.fromkeys(self.DIRS, -9.0)    # genuine hold expiry
        self.carried = dict.fromkeys(self.DIRS, -9.0)  # carried hold expiry
        self.delay = self.DELAY_GUESS                 # learned repeat delay
        self.gap = self.REPEAT / 2.6                  # learned repeat period
        self.last_gap = dict.fromkeys(self.DIRS, 0.0)  # for spotting a train
        self.now = 0.0
        # Under the kitty keyboard protocol none of the guessing above is
        # needed: the terminal says when a key goes up, so a direction is
        # held while any key mapped to it is down, and that is all.
        self.exact = False
        self.down = dict.fromkeys(self.DIRS, 0)       # keys holding each
        self.muted = dict.fromkeys(self.DIRS, False)  # overridden by opposite
        self.seen = dict.fromkeys(self.DIRS, -9.0)    # last press/repeat
        self.last_press = -9.0                        # of any key at all
        self.saw_repeat = False

    # Exact mode: a release can still go missing - focus lost mid-hold, say.
    # Once this terminal has shown it repeats held keys, a key that has gone
    # quiet for far longer than any repeat period is not held any more. But
    # the OS repeats only the *most recently pressed* key, so silence from an
    # older one means nothing - hold Right, tap X, and Right goes quiet while
    # still very much held. Only the newest press can be judged by silence.
    STUCK = 1.5

    @property
    def first(self):
        return min(self.FIRST_MAX, max(self.FIRST_MIN, self.delay * 1.12))

    @property
    def window(self):
        """How long one repeat keeps a key alive - and so how long the ship
        keeps going after you let go. Kept at a few repeat periods so a slow
        train still bridges, and no wider."""
        return min(self.REPEAT_MAX, max(self.REPEAT_MIN, self.gap * 2.6))

    def tick(self, now):
        self.now = now

    def brake(self):
        """All stop: forget every direction, held or carried."""
        for name in self.DIRS:
            self.real[name] = self.hold[name] = self.carried[name] = -9.0
            self.down[name] = 0

    def press(self, names, now, event=PRESS):
        if self.exact:
            self._exact(names, now, event)
            return
        if event == RELEASE:          # cannot happen without the protocol
            return
        for name in names:
            fresh = now >= self.hold[name]
            # A press this soon after the last one is a repeat, whether or not
            # our hold window was still open - and the first repeat of a hold
            # measures this machine's delay-until-repeat. Learning it even
            # after the window lapsed is what stops a too-short guess from
            # making a held key stutter forever.
            gap = now - self.real[name]
            # Only a repeat *train* may teach us anything. A gap on its own
            # says nothing - steering taps land 0.2-0.4 s apart and look
            # exactly like a delay-until-repeat, and letting those through
            # drags the learned delay below the real one, which makes every
            # held key stutter. A train is unmistakable though: a short gap
            # right behind a much longer one. The long gap was the delay, the
            # short one is the period.
            prev = self.last_gap[name]
            if 0.0 < gap < 0.25 and gap * 2.0 < prev < 2.5:
                self.delay = max(min(prev, 1.5), self.delay * 0.98)
                self.gap = max(gap, self.gap * 0.9)
            elif not fresh and 0.0 < gap < 0.25 and 0.0 < prev < 0.25:
                # Two short gaps in a row while the window is still open: we
                # are inside the train, so keep refining the period. Only the
                # period - a steady train says nothing new about the delay.
                self.gap = max(gap, self.gap * 0.9)
            self.last_gap[name] = gap
            self.hold[name] = now + (self.first if fresh else self.window)
            self.real[name] = now
            opp = self.OPPOSITE[name]
            if opp not in names:                       # reversing cancels
                self.real[opp] = self.hold[opp] = self.carried[opp] = -9.0
        self._carry(now, self.CARRY, skip=names)

    def _exact(self, names, now, event):
        for name in names:
            opp = self.OPPOSITE[name]
            if event == RELEASE:
                self.down[name] = max(0, self.down[name] - 1)
                if self.down[name] == 0:
                    self.muted[name] = False
                    # Letting go of the newer key hands control back to the
                    # opposite one if it is still held.
                    self.muted[opp] = False
            elif event == REPEAT:
                self.down[name] = max(1, self.down[name])
                self.seen[name] = now
                self.saw_repeat = True
            else:
                self.down[name] += 1
                self.seen[name] = now
                self.last_press = now
                self.muted[name] = False
                # Reversing cancels, as it does without the protocol: two
                # opposed keys would otherwise sum to a dead stop, and rolling
                # from one arrow to the other always overlaps them a little.
                if opp not in names:
                    self.muted[opp] = True

    def other(self, now, skip=()):
        """Any key event at all keeps recently-pressed directions alive."""
        if self.exact:
            self.last_press = now     # nothing to keep alive: holds are real
            return
        self._carry(now, self.CARRY_OTHER, skip=skip)

    def _carry(self, now, window, skip=()):
        for name in self.DIRS:
            if name not in skip and now - self.real[name] < window:
                self.carried[name] = max(self.carried[name],
                                         now + self.window)

    def axis(self, name):
        """0.0 not held, 1.0 genuinely held, tapering in between if carried.

        A carried direction fades rather than cutting out: held as half of a
        two-arrow diagonal it reads as a smooth curve, and in the case where
        the key really was released it reads as ordinary drift.
        """
        now = self.now
        if self.exact:
            if self.down[name] <= 0 or self.muted[name]:
                return 0.0
            if (self.saw_repeat and self.seen[name] >= self.last_press
                    and now - self.seen[name] > self.STUCK):
                self.down[name] = 0           # a release we never saw
                return 0.0
            return 1.0
        live = self.hold[name]
        if now < live:
            v = 1.0
        else:
            # One dropped repeat should dip the throttle, not cut it dead, so
            # the window eases out over a fraction of a repeat period rather
            # than ending on a cliff. A real release still lands inside it.
            fade = self.window * 0.6
            v = max(0.0, 1.0 - (now - live) / fade)
        if now < self.carried[name]:
            t = min(1.0, max(0.0, (now - self.real[name]) / self.CARRY_OTHER))
            v = max(v, self.CARRY_HI + (self.CARRY_LO - self.CARRY_HI) * t)
        return v

    def held(self, name):
        return self.axis(name) > 0.0


class Reader:
    """Drain curses input, re-assembling escape sequences by hand.

    With nodelay set, ncurses hands back a bare ESC rather than block waiting
    for the rest of a sequence, so on plenty of terminals an arrow key arrives
    as 27 '[' 'C' instead of KEY_RIGHT. Left alone that reads as three unknown
    keys - the ship never moves on arrows, or moves only on the presses that
    happened to be assembled, which is indistinguishable from a stutter.

    Under the kitty keyboard protocol every key is a CSI sequence too, and it
    carries an event type - press, repeat or release - that ncurses knows
    nothing about. Reassembling here is what makes both work.

    read() yields (key, event) pairs: key is an ncurses code or a codepoint.
    """

    ARROW = {65: curses.KEY_UP, 66: curses.KEY_DOWN,
             67: curses.KEY_RIGHT, 68: curses.KEY_LEFT}
    PARTIAL = 0.05          # how long to wait for the rest of a sequence

    def __init__(self, stdscr):
        self.s = stdscr
        self.buf = []
        self.t = 0.0

    def read(self, now):
        while True:
            c = self.s.getch()
            if c == -1:
                break
            self.buf.append(c)
            self.t = now
        out, b, i = [], self.buf, 0
        while i < len(b):
            if b[i] != 27:
                out.append((b[i], PRESS))
                i += 1
                continue
            got = self._seq(b, i)
            if got is None:                    # still arriving...
                if now - self.t < self.PARTIAL:
                    break                      # ...keep it for next time
                got = (1, 27, PRESS)           # ...or it was a lone Escape
            n, key, ev = got
            if key is not None:
                out.append((key, ev))
            i += n
        self.buf = b[i:]
        return out

    def _seq(self, b, i):
        """Decode one escape sequence starting at b[i] (the ESC).

        Returns (length, key, event) - key None for a sequence to ignore -
        or None when the sequence is not all here yet.
        """
        n = len(b)
        if i + 1 >= n:
            return None
        lead = b[i + 1]
        if lead == 79:                          # SS3: ESC O A on some terms
            if i + 2 >= n:
                return None
            key = self.ARROW.get(b[i + 2])
            return (3, key, PRESS) if key else (1, 27, PRESS)
        if lead != 91:                          # not CSI: a lone Escape
            return (1, 27, PRESS)
        j = i + 2
        while j < n and 0x30 <= b[j] <= 0x3F:   # parameter bytes
            j += 1
        while j < n and 0x20 <= b[j] <= 0x2F:   # intermediate bytes
            j += 1
        if j >= n:
            return None
        final = b[j]
        if not 0x40 <= final <= 0x7E:           # not a sequence after all
            return (1, 27, PRESS)
        params = "".join(map(chr, b[i + 2:j]))
        key, ev = self._decode(params, final)
        return (j - i + 1, key, ev)

    def _decode(self, params, final):
        fields = params.split(";")
        ev, mods = PRESS, 0
        if len(fields) > 1 and fields[1]:       # "mods:event", both optional
            m, _, e = fields[1].partition(":")
            mods = int(m) - 1 if m.isdigit() else 0
            if e.isdigit():
                ev = int(e)
        if final == 117:                        # 'u': CSI codepoint ; mods u
            code = fields[0].partition(":")[0]  # "97:65" is a, shifted to A
            if not code.isdigit():
                return None, ev                 # the protocol reply itself
            code = int(code)
            if mods & 4 and code in (99, 67):   # ctrl-C: a key, not a signal
                code = 3
            return code, ev
        if final in self.ARROW:                 # CSI A, or CSI 1;mods:ev A
            return self.ARROW[final], ev
        return None, ev                         # DA reply, page keys, mice

