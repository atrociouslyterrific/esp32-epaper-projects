"""Example sentences for teaching Pip to talk.

Each line starts with a one-letter MOOD code and ">", then something Pip might say
in that mood, e.g. "H>is it cookie time?". Pip's voice model learns from many
thousands of these and then writes its own new sentences, one letter at a time.

Sentences are built from templates with slots ({food}, {thing}, ...), and many
templates can be glued together ("{opener} {template}") so the model sees a wide
variety of combinations and learns how Pip's sentences fit together.
"""
import random

ALPHABET = "abcdefghijklmnopqrstuvwxyz !?.,'~*<3"
MAX_LEN = 28  # fits in the speech bubble on the 200-pixel screen (31 max)

MOODS = {
    "S": "asleep", "H": "hungry", "T": "tired", "L": "lonely", "B": "bored", "K": "cold", "W": "hot",
    "N": "night", "M": "morning", "P": "petted", "C": "curious", "Y": "playful", "Z": "lazy",
    "R": "brave", "X": "shy", "A": "affectionate", "J": "happy", "D": "dancing", "V": "window",
    "G": "grumpy", "U": "sulky", "F": "scared", "Q": "frustrated",
}

SLOTS = {
    "excl": ["ooh", "hmm", "eep", "yay", "oh", "wow", "uh oh", "blub", "boing", "hehe", "whee", "ah", "oof", "yippee",
             "hm", "aww", "ooo", "huh", "yesss", "eek", "wheee", "la la"],
    "food": ["berries", "cookies", "crumbs", "noodles", "toast", "apples", "seeds", "jelly", "pancakes", "soup", "peas",
             "cake", "grapes", "honey", "rice", "muffins", "plums", "cheese", "carrots", "beans", "waffles", "pie",
             "melon", "pears", "dumplings", "popcorn", "jam", "biscuits", "berry pie", "a snack"],
    "end": ["!", "!", "!!", "~", "...", "", " <3", "!~"],
    "calm": [".", "...", "~", ""],
    "thing": ["the box", "the window", "the bowl", "my bed", "the floor", "that corner", "the moon", "a sock",
              "the sun", "the sky", "a cloud", "that shadow", "the ceiling", "a crumb", "the wall", "a button",
              "the clouds", "a bird", "the stars", "a leaf", "my pillow"],
    "feel": ["happy", "bouncy", "wiggly", "cosy", "silly", "squishy", "sparkly", "giggly", "fluffy", "wobbly",
             "sleepy", "snuggly", "jolly", "zoomy", "toasty", "bubbly", "dizzy"],
    "you": ["you", "my friend", "my human", "buddy", "pal", "friend"],
    "tummy": ["rumbles", "grumbles", "says hi", "is empty", "wants {food}", "growls", "is singing", "needs {food}"],
    "dream": ["{food}", "clouds", "bouncing", "a big {food}", "the moon", "jellybeans", "you", "flying", "{thing}",
              "a mountain of {food}", "dancing"],
    "move": ["bounce", "wiggle", "spin", "hop", "boogie", "jiggle", "twirl", "shimmy", "wobble", "stomp"],
    "sky": ["the sun", "the moon", "a bird", "the clouds", "a star", "the rain", "a plane", "the sky", "a tree",
            "a cat", "the wind", "a rainbow"],
    "time": ["today", "right now", "tonight", "this morning", "all day"],
    "opener": ["{excl},", "{excl}!", "hey,", "psst,", "oh,", "um,", "ooh,", "you know what?"],
}

TEMPLATES = {
    "S": ["zzz... {dream}...", "mmm... {dream}...", "*snore*", "zzz...", "five more minutes...", "*mumbles {food}*",
          "zzz... boing...", "mmm... so comfy...", "*snore* {food}...", "zzz... {you}...", "*dreams of {dream}*",
          "zzz... {move}... zzz", "mmm... {feel}...", "*snuggles {thing}*", "no... my {food}...",
          "*sleep talks about {dream}*", "zzzzz...", "mmm... {excl}..."],
    "H": ["{excl}, {food}{end}", "is it {food} time?", "i want {food}{end}", "my tummy {tummy}", "{food} please{end}",
          "so hungry{end}", "snack o'clock?", "feed the blob{end}", "i smell {food}", "dreaming of {food}",
          "{food}? {food}!", "got any {food}?", "i could eat {food}", "my tummy {tummy}{end}", "need {food} {time}",
          "{opener} is that {food}?", "one tiny {food}?", "hungry blob alert{end}", "can i have {food}?",
          "i'd love some {food}", "{food} would be nice{calm}"],
    "T": ["so... sleepy...", "yawwwn{calm}", "need a nap{end}", "eyes... heavy...", "{excl}, i'm pooped", "bed is calling{end}",
          "too tired to {move}", "sleepy blob{calm}", "*yawns*", "must... nap...", "my bed looks {feel}",
          "running out of {move}", "nap time soon?", "so tired {time}{calm}", "*rubs eyes*", "can't stop yawning"],
    "L": ["where did {you} go?", "i miss {you}{end}", "anyone there?", "hello? {excl}?", "come back soon{end}",
          "it's quiet in here", "pat me please?", "lonely blob{calm}", "{you}? hello?", "i'm waiting{calm}",
          "play with me, {you}?", "talk to me?", "*looks around*", "is {you} coming back?", "so quiet {time}{calm}",
          "i saved you a {food}"],
    "B": ["i'm sooo bored", "play with me?", "nothing to do{calm}", "bored bored bored", "{excl}, let's do stuff",
          "entertain the blob{end}", "so... bored...", "is it fun time?", "i need a game{end}", "let's {move}?",
          "*stares at {thing}*", "counting {food}{calm}", "i've seen {thing} already", "what now{calm}",
          "{opener} let's {move}"],
    "K": ["brr! chilly{end}", "is the heater on?", "cold toes{end}", "{excl}, it's freezing", "need a blanket{end}",
          "i'm a blob-sicle", "brrr{end}", "so cold{calm}", "*shivers*", "warm me up?", "my nose is cold{end}",
          "where's my blanket?", "cold blob {time}{calm}", "need hot soup{end}", "*teeth chatter*"],
    "W": ["it's toasty{end}", "phew, so hot{end}", "i'm melting{end}", "need a breeze{end}", "{excl}, sweaty blob",
          "too warm in here", "so hot{calm}", "*fans self*", "melty blob{calm}", "need ice cream{end}",
          "it's a hot one {time}", "turn on a fan?", "*pants*", "i'm a puddle{calm}"],
    "N": ["the moon is pretty", "shh, it's late", "night night{end}", "sleepy stars{end}", "{excl}, it's dark",
          "is it bedtime?", "the stars are out", "quiet night{calm}", "goodnight {you}{end}", "sweet dreams{end}",
          "the moon says hi", "time to rest{calm}", "night blob{calm}", "dream of {food}{end}"],
    "M": ["good morning{end}", "rise and {move}{end}", "new day{end}", "{excl}, sunshine!", "morning stretch~",
          "breakfast time?", "hello sun{end}", "morning {you}{end}", "i slept so well{end}", "{food} for breakfast?",
          "what a {feel} morning", "up and {move}{end}", "good morning, {you}{end}"],
    "P": ["hehe, that tickles{end}", "i like {you}{end}", "more pats{end}", "again! again!", "{excl}, pats!",
          "you are the best{end}", "happy blob noises", "i feel {feel}{end}", "yay, pats{end}", "pat pat pat{end}",
          "*purrs like a blob*", "{opener} that's nice{end}", "best pats ever{end}", "i'm so {feel} now",
          "thank you, {you}{end}", "do that again?"],
    "C": ["what's in {thing}?", "ooh, what's that?", "i wonder{calm}", "{excl}, a mystery", "let me look{end}",
          "what's behind {thing}?", "hmm, {thing}?", "i see something{end}", "what is {thing}?", "who made {thing}?",
          "{opener} look at {thing}", "why is {thing} there?", "i must explore{end}", "a new {thing}?",
          "ooh, {thing} moved!", "let's check {thing}"],
    "Y": ["bet i jump higher{end}", "boing boing{end}", "catch me{end}", "let's play{end}", "{excl}, tag! you're it",
          "bounce time{end}", "i'm so {feel}{end}", "wheee{end}", "race you{end}", "watch me {move}{end}",
          "{move} with me{end}", "i'm the bounciest", "one more game?", "{opener} let's {move}{end}"],
    "Z": ["naps are life", "too comfy to move", "five more minutes", "lazy blob day{end}", "{excl}, couch mode",
          "moving is hard", "i'll do it later", "so cosy{calm}", "nap first{calm}", "can't be bothered{calm}",
          "{thing} is comfy", "maybe tomorrow{calm}", "i'm resting my eyes", "lazy {time}{calm}"],
    "R": ["i fear nothing{end}", "adventure time{end}", "i'm a brave blob", "nothing scares me", "{excl}, let's explore",
          "to {thing}{end}", "bring it on{end}", "i'm not scared{end}", "follow me{end}", "i'll guard {thing}",
          "onward to {thing}{end}", "brave blob {time}{end}"],
    "X": ["...hi", "don't look at me", "*hides a bit*", "um... hello", "{excl}... a person", "is it safe?",
          "i'm a bit shy{calm}", "*peeks*", "oh... hi {you}", "*blushes*", "...you can stay", "*peeks at {you}*",
          "hello... quietly", "um... {food}?"],
    "A": ["you are my favourite", "hug?", "love you lots{end}", "{excl}, it's {you}!", "best friends{end}",
          "i'm glad you're here", "i love {you}{end}", "stay with me?", "you make me {feel}", "big blob hug{end}",
          "missed you{end}", "you're so nice{end}", "{opener} i like you{end}", "my favourite {you}{end}"],
    "J": ["blub{end}", "i'm a happy blob", "wiggle wiggle{end}", "what a nice day{end}", "{excl}{end}", "life is good{end}",
          "la la la~", "i feel {feel}{end}", "{excl}, i'm {feel}", "hello world{end}", "today is {feel}{end}",
          "everything is {feel}", "blub blub{end}", "{opener} i'm {feel}", "so {feel} {time}{end}"],
    "D": ["dance party{end}", "watch me {move}{end}", "{move} {move}{end}", "{excl}, dance time!", "groovy blob{end}",
          "i've got the moves{end}", "*{move}s*", "dance with me?", "boogie time{end}", "{move} to the left{end}",
          "feel the beat{end}", "i'm a dancing blob", "{opener} let's {move}{end}", "best dance ever{end}"],
    # Negative feelings: grumpy-cute, never mean
    "G": ["hmph{calm}", "hmph. i was napping", "go away{calm}", "*grumbles*", "not now{calm}", "i'm grumpy{calm}",
          "five more minutes!", "why'd you wake me?", "grr{calm}", "leave me be{calm}", "*turns away*",
          "i was dreaming of {food}", "too sleepy for pats", "hmph, {you}{calm}", "*grumpy blob noises*",
          "ask me later{calm}", "i'm not a morning blob"],
    "U": ["...", "i'm not talking to you", "*sulks*", "you forgot me{calm}", "hmph. where were you?",
          "fine. i'll play alone", "*sits in the corner*", "nobody plays with me{calm}", "i'm ignoring you{calm}",
          "...maybe one pat", "you were gone so long", "*looks away*", "i missed you. hmph.",
          "i'm not sulking{calm}", "*sigh*"],
    "F": ["eek{end}", "eep! what was that?!", "*trembles*", "i'm scared{calm}", "too loud{end}",
          "*hides*", "make it stop{end}", "hold me?", "is it gone?", "*shaking*", "the world is upside down!",
          "{excl}! scary!", "i don't like that{calm}", "help{end}", "*peeks out nervously*"],
    "Q": ["grr{end}", "it's not working!", "*stomps*", "ugh{calm}", "why won't it work?", "too tired to {move}{end}",
          "i can't {move}{calm}", "*huffs*", "argh{end}", "so annoying{end}", "i give up{calm}",
          "*steam comes out*", "not fair{end}", "i'm too full{end}", "silly {thing}{calm}"],
    "V": ["look, {sky}{end}", "i see {sky}", "{excl}, {sky}!", "hello {sky}{end}", "the view is nice{calm}",
          "{sky} is out {time}", "i love this window", "what's {sky} doing?", "pretty {sky}{calm}",
          "*watches {sky}*", "wave to {sky}{end}", "the world is big{calm}", "{opener} {sky}!"],
}


def fill(template, rng):
    out = template
    for _ in range(5):  # slots can contain slots (e.g. tummy -> food)
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
        if rng.random() < 0.15 and mood not in "SX":  # sometimes start with a little exclamation
            text = fill("{excl}, ", rng) + text
        if 2 <= len(text) <= MAX_LEN and all(c in ALPHABET for c in text):
            lines.append(f"{mood}>{text}")
    return lines


if __name__ == "__main__":
    lines = make_lines(40000)
    print(len(set(lines)), "different sentences, e.g.:")
    for line in random.Random(2).sample(lines, 30):
        print(" ", line)
