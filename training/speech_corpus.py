"""Example sentences for teaching Pip to talk.

Each line starts with a one-letter MOOD code and ">", then something Pip might say
in that mood, e.g. "H>is it cookie time?". Pip's voice model learns from many
thousands of these and then writes its own new sentences, one letter at a time.
"""
import random

ALPHABET = "abcdefghijklmnopqrstuvwxyz !?.,'~*<3"
MAX_LEN = 22  # fits in the speech bubble on the 200-pixel screen

MOODS = {
    "S": "asleep", "H": "hungry", "T": "tired", "L": "lonely", "B": "bored", "K": "cold", "W": "hot",
    "N": "night", "M": "morning", "P": "petted", "C": "curious", "Y": "playful", "Z": "lazy",
    "R": "brave", "X": "shy", "A": "affectionate", "J": "happy",
}

SLOTS = {
    "excl": ["ooh", "hmm", "eep", "yay", "oh", "wow", "uh oh", "blub", "boing", "hehe", "whee", "ah", "oof", "yippee"],
    "food": ["berries", "cookies", "crumbs", "noodles", "toast", "apples", "seeds", "jelly", "pancakes", "soup", "peas",
             "cake", "grapes", "honey", "rice", "muffins", "plums", "cheese", "carrots", "beans"],
    "end": ["!", "!", "!!", "~", "...", "", " <3"],
    "calm": [".", "...", "~", ""],
    "thing": ["the box", "the window", "the bowl", "my bed", "the floor", "that corner", "the moon", "a sock", "the sun"],
    "feel": ["happy", "bouncy", "wiggly", "cosy", "silly", "squishy", "sparkly", "giggly", "fluffy"],
    "you": ["you", "my friend", "my human", "buddy", "pal"],
    "tummy": ["rumbles", "grumbles", "says hi", "is empty", "wants {food}", "growls"],
    "dream": ["{food}", "clouds", "bouncing", "a big {food}", "the moon", "jellybeans", "you"],
}

TEMPLATES = {
    "S": ["zzz... {dream}...", "mmm... {dream}...", "*snore*", "zzz...", "five more minutes...", "*mumbles {food}*",
          "zzz... boing...", "mmm... so comfy...", "*snore* {food}...", "zzz... {you}..."],
    "H": ["{excl}, {food}{end}", "is it {food} time?", "i want {food}{end}", "my tummy {tummy}", "{food} please{end}",
          "so hungry{end}", "snack o'clock?", "feed the blob{end}", "i smell {food}", "dreaming of {food}",
          "{food}? {food}!", "got any {food}?"],
    "T": ["so... sleepy...", "yawwwn{calm}", "need a nap{end}", "eyes... heavy...", "{excl}, i'm pooped", "bed is calling{end}",
          "too tired to wiggle", "sleepy blob{calm}", "*yawns*", "must... nap..."],
    "L": ["where did {you} go?", "i miss {you}{end}", "anyone there?", "hello? {excl}?", "come back soon{end}",
          "it's quiet in here", "pat me please?", "lonely blob{calm}", "{you}? hello?", "i'm waiting{calm}"],
    "B": ["i'm sooo bored", "play with me?", "nothing to do{calm}", "bored bored bored", "{excl}, let's do stuff",
          "entertain the blob{end}", "so... bored...", "is it fun time?", "i need a game{end}"],
    "K": ["brr! chilly{end}", "is the heater on?", "cold toes{end}", "{excl}, it's freezing", "need a blanket{end}",
          "i'm a blob-sicle", "brrr{end}", "so cold{calm}", "*shivers*", "warm me up?"],
    "W": ["it's toasty{end}", "phew, so hot{end}", "i'm melting{end}", "need a breeze{end}", "{excl}, sweaty blob",
          "too warm in here", "so hot{calm}", "*fans self*", "melty blob{calm}"],
    "N": ["the moon is pretty", "shh, it's late", "night night{end}", "sleepy stars{end}", "{excl}, it's dark",
          "is it bedtime?", "the stars are out", "quiet night{calm}", "goodnight {you}{end}"],
    "M": ["good morning{end}", "rise and wiggle{end}", "new day{end}", "{excl}, sunshine!", "morning stretch~",
          "breakfast time?", "hello sun{end}", "morning {you}{end}", "i slept so well{end}"],
    "P": ["hehe, that tickles{end}", "i like {you}{end}", "more pats{end}", "again! again!", "{excl}, pats!",
          "you are the best{end}", "happy blob noises", "i feel {feel}{end}", "yay, pats{end}", "pat pat pat{end}"],
    "C": ["what's in {thing}?", "ooh, what's that?", "i wonder{calm}", "{excl}, a mystery", "let me look{end}",
          "what's behind {thing}?", "hmm, {thing}?", "i see something{end}", "what is {thing}?"],
    "Y": ["bet i jump higher{end}", "boing boing{end}", "catch me{end}", "let's play{end}", "{excl}, tag! you're it",
          "bounce time{end}", "i'm so {feel}{end}", "wheee{end}", "race you{end}"],
    "Z": ["naps are life", "too comfy to move", "five more minutes", "lazy blob day{end}", "{excl}, couch mode",
          "moving is hard", "i'll do it later", "so cosy{calm}", "nap first{calm}"],
    "R": ["i fear nothing{end}", "adventure time{end}", "i'm a brave blob", "nothing scares me", "{excl}, let's explore",
          "to {thing}{end}", "bring it on{end}", "i'm not scared{end}"],
    "X": ["...hi", "don't look at me", "*hides a bit*", "um... hello", "{excl}... a person", "is it safe?",
          "i'm a bit shy{calm}", "*peeks*", "oh... hi {you}"],
    "A": ["you are my favourite", "hug?", "love you lots{end}", "{excl}, it's {you}!", "best friends{end}",
          "i'm glad you're here", "i love {you}{end}", "stay with me?", "you make me {feel}"],
    "J": ["blub{end}", "i'm a happy blob", "wiggle wiggle{end}", "what a nice day{end}", "{excl}{end}", "life is good{end}",
          "la la la~", "i feel {feel}{end}", "{excl}, i'm {feel}", "hello world{end}"],
}


def fill(template, rng):
    out = template
    for _ in range(4):  # slots can contain slots (e.g. tummy -> food)
        for name, options in SLOTS.items():
            while "{" + name + "}" in out:
                out = out.replace("{" + name + "}", rng.choice(options), 1)
    return out


def make_lines(n, seed=1):
    rng = random.Random(seed)
    lines = []
    moods = list(TEMPLATES)
    while len(lines) < n:
        mood = rng.choice(moods)
        text = fill(rng.choice(TEMPLATES[mood]), rng)
        if 2 <= len(text) <= MAX_LEN and all(c in ALPHABET for c in text):
            lines.append(f"{mood}>{text}")
    return lines


if __name__ == "__main__":
    for line in make_lines(30):
        print(line)
