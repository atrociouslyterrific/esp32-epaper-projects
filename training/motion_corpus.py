"""Example movement clips for teaching Pip how to move.

A clip is a list of frames; each frame says how Pip moves for one screen update:
  dx    - sideways step in pixels (one of DX_VALUES)
  jump  - height above the floor (one of JUMP_VALUES; negative = up)
  squash - body shape in % (one of SQ_VALUES; >100 = squashed flat, <100 = stretched tall)
Clips are made from movement "styles" for each action, changed by Pip's mood (happy, tired,
sad/scared, grumpy) and energy, with lots of randomness. The motion model learns from many
thousands of these and then invents its own new clips on the board.
"""
import random

ACTIONS = ["idle", "nap", "eat", "explore", "play", "sing", "hide", "warm_up", "cool_down", "call", "dance", "window",
           "fidget"]  # "fidget" = the little moves Pip does between decisions
MOODS = ["happy", "tired", "sad", "grumpy"]
ENERGY = ["low", "mid", "high"]

DX_VALUES = [-12, -9, -6, -3, 0, 3, 6, 9, 12]
JUMP_VALUES = [0, -3, -6, -10, -15, -20, -25]
SQ_VALUES = [80, 88, 96, 104, 116, 128]
MAX_FRAMES = 20


def nearest(v, options):
    return min(options, key=lambda o: abs(o - v))


class Clip:
    def __init__(self, mood, energy, rng):
        self.frames, self.mood, self.energy, self.rng = [], mood, energy, rng
        self.amp = {"happy": 1.25, "tired": 0.5, "sad": 0.7, "grumpy": 0.85}[mood] * {"low": 0.6, "mid": 1.0, "high": 1.3}[energy]

    def add(self, dx=0, jump=0, sq=100):
        if self.mood == "sad" and self.rng.random() < 0.35:  # sad/scared Pips tremble a little
            dx += self.rng.choice([-3, 3])
        self.frames.append((nearest(dx, DX_VALUES), nearest(jump, JUMP_VALUES), nearest(sq, SQ_VALUES)))

    def pause(self, n=1):
        for _ in range(n):
            self.add(0, 0, self.rng.choice([96, 104]) if self.mood != "grumpy" else 104)

    def scoot(self, steps, direction):
        speed = 3 + 6 * min(1.0, self.amp) * self.rng.uniform(0.6, 1.0)
        for i in range(steps):
            stride = i % 2 == 0
            self.add(direction * speed, -3 * self.amp if stride else 0, 88 if stride else 116)
            if self.mood == "tired" and self.rng.random() < 0.4:
                self.pause()

    def jump(self, height, dx=0):
        h = -height * self.amp
        self.add(0, 0, 116 + 10 * self.amp)                     # crouch
        self.add(dx / 2, h * 0.5, 84)                           # take off, stretched
        self.add(dx / 2, h, 96)                                 # top
        self.add(dx / 2, h * 0.4, 90)                           # falling
        self.add(0, 0, 128 if self.mood != "tired" else 116)    # land, squashed
        self.add(0, 0, 104)                                     # wobble back


def make_clip(action, mood, energy, rng):
    c = Clip(mood, energy, rng)
    r = rng.random
    if action == "nap":
        for _ in range(rng.randint(3, 6)):
            c.add(0, 0, rng.choice([104, 96]))
    elif action == "eat":
        for _ in range(rng.randint(3, 6)):
            c.add(0, 0, 116 if c.mood != "tired" else 104)
            c.add(0, 0, 96)
    elif action == "explore":
        direction = rng.choice([-1, 1])
        for _ in range(rng.randint(2, 3)):
            c.scoot(rng.randint(2, 5), direction)
            c.pause(rng.randint(1, 2))
            if r() < 0.5:
                direction = -direction                           # changes its mind
            if r() < 0.3 and c.mood == "happy":
                c.jump(8)
    elif action == "play":
        for _ in range(rng.randint(2, 3)):
            c.jump(rng.choice([12, 18, 22]), dx=rng.choice([-6, 0, 6]))
            if r() < 0.4:
                c.scoot(2, rng.choice([-1, 1]))
    elif action == "dance":
        side = rng.choice([-1, 1])
        for _ in range(rng.randint(4, 7)):
            c.add(side * 6 * c.amp, -3 * c.amp, 90)
            c.add(0, 0, 112)
            side = -side
            if r() < 0.25 and c.mood != "tired":
                c.jump(10)
    elif action == "sing":
        for _ in range(rng.randint(3, 6)):
            c.add(rng.choice([-3, 0, 3]) * c.amp, -3 * c.amp, 96)
            c.add(0, 0, 104)
    elif action == "hide":
        for _ in range(rng.randint(2, 4)):
            c.add(rng.choice([-3, 3]) if c.mood == "sad" else 0, 0, 116)
    elif action == "warm_up":
        for _ in range(rng.randint(3, 6)):
            c.add(3, 0, 104)
            c.add(-3, 0, 96)
    elif action == "cool_down":
        for _ in range(rng.randint(3, 5)):
            c.add(0, 0, 96)
            c.add(0, 0, 104)
    elif action == "call":
        for _ in range(rng.randint(1, 3)):
            c.jump(rng.choice([6, 10]))
    elif action == "window":
        c.add(0, -3, 88)
        for _ in range(rng.randint(2, 4)):
            c.add(0, -3, 88 if r() < 0.7 else 96)
        c.add(0, 0, 104)
    elif action == "idle":
        for _ in range(rng.randint(2, 4)):
            c.add(rng.choice([-3, 0, 0, 3]), 0, rng.choice([96, 100, 104]))
    elif action == "fidget":
        kind = rng.choice(["hop", "wobble", "scoot", "turn", "stomp"])
        if c.mood == "grumpy" and r() < 0.6:
            kind = "stomp"
        if c.mood == "tired" and r() < 0.6:
            kind = "wobble"
        if kind == "hop":
            c.jump(rng.choice([6, 9, 12]))
        elif kind == "wobble":
            for _ in range(rng.randint(2, 3)):
                c.add(0, 0, 106)
                c.add(0, 0, 94)
        elif kind == "scoot":
            c.scoot(rng.randint(2, 4), rng.choice([-1, 1]))
        elif kind == "turn":
            c.add(rng.choice([-3, 3]), 0, 100)
        else:  # stomp
            for _ in range(rng.randint(2, 3)):
                c.add(0, 0, 128)
                c.add(0, 0, 100)
    if c.mood == "grumpy" and action not in ("nap", "fidget") and r() < 0.4:
        c.add(0, 0, 128)                                         # a grumpy stomp at the end
    c.pause()
    return c.frames[:MAX_FRAMES]


def make_examples(n, seed=1):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        a, m, e = rng.choice(ACTIONS), rng.choice(MOODS), rng.choice(ENERGY)
        out.append((a, m, e, make_clip(a, m, e, rng)))
    return out


if __name__ == "__main__":
    for a, m, e, f in make_examples(8, 3):
        print(a, m, e, f)
