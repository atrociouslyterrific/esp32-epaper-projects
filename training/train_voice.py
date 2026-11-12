"""Teach Pip to talk: a tiny character-level language model (a GRU).

It reads a mood letter, then ">", and writes a sentence one character at a time.
Runs on GitHub Actions. Outputs:
  PipAI/pip_voice.h               - the trained model as C arrays + generator
  training/out/voice_test.txt     - greedy outputs the C test must reproduce exactly
  status.json "voice"             - progress + example sayings for the status website
"""
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn

torch.set_num_threads(int(os.environ.get("PIP_THREADS", "2")))  # shares the machine with the brain

sys.path.insert(0, os.path.dirname(__file__))
import speech_corpus as SC  # noqa: E402

SEED = 11
HIDDEN = 512  # memory cells (was 256, 160, 128, 96)
STEPS = int(os.environ.get("PIP_VOICE_STEPS", "5000"))                 # from scratch
CONTINUE_STEPS = int(os.environ.get("PIP_VOICE_CONTINUE_STEPS", "2000"))  # nightly top-up
CONTINUE_LR = 1e-3
BATCH, SEQ, LR = 128, 96, 3e-3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "training", "out")
STATUS_PATH = os.path.join(OUT, "status.json")
CKPT_IN = os.path.join(ROOT, "training", "ckpt", "voice.pt")

# Vocabulary: newline (end of sentence), ">", mood letters, then the alphabet Pip can write
# Newline ends a reply; "|" separates what was said from Pip's reply; I/O/E say who is talking
# to Pip (I = nobody, Pip talks to itself; O = Bloop; E = you); then the moods and the alphabet.
VOCAB = ["\n", "|"] + list(SC.SOURCES) + list(SC.MOODS) + list(SC.ALPHABET)
IDX = {c: i for i, c in enumerate(VOCAB)}
V = len(VOCAB)


class Voice(nn.Module):
    def __init__(self):
        super().__init__()
        self.gru = nn.GRU(V, HIDDEN, batch_first=True)
        self.out = nn.Linear(HIDDEN, V)

    def forward(self, x, h=None):
        y, h = self.gru(nn.functional.one_hot(x, V).float(), h)
        return self.out(y), h


def update_status(**voice):
    try:
        s = json.load(open(STATUS_PATH))
    except Exception:
        s = {}
    s.setdefault("voice", {}).update(voice)
    # The brain trains at the same time; only touch the overall state once the brain is done
    brain_done = s.get("state") in ("voice", "trained")
    if brain_done and voice.get("state") in ("starting", "training"):
        s["state"] = "voice"
    elif brain_done and voice.get("state") in ("trained", "done"):
        s["state"] = "trained"
    s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    tmp = STATUS_PATH + ".tmp"
    json.dump(s, open(tmp, "w"))
    os.replace(tmp, STATUS_PATH)


def prompt_for(mood, src="I", heard=""):
    """What the model reads before replying: who's talking, Pip's mood, what they said, "|"."""
    heard = "".join(c for c in heard.lower() if c in SC.ALPHABET)[:SC.MAX_LEN]
    return f"{src}{mood}{heard}|"


def generate(model, mood, temperature=0.8, rng=None, max_len=SC.MAX_LEN + 2, src="I", heard=""):
    """Pip's reply (or self-talk when src is "I"). temperature 0 = always the most likely letter."""
    with torch.no_grad():
        h = None
        for c in prompt_for(mood, src, heard):
            logits, h = model(torch.tensor([[IDX[c]]]), h)
        out = ""
        for _ in range(max_len):
            l = logits[0, -1]
            if temperature <= 0:
                k = int(torch.argmax(l))
            else:
                p = torch.softmax(l / temperature, -1).numpy().astype(np.float64)
                k = int(rng.choice(V, p=p / p.sum()))
            if VOCAB[k] == "\n":
                break
            out += VOCAB[k]
            logits, h = model(torch.tensor([[k]]), h)
        return out


def samples(model, rng, per_mood=4):
    return {m: [generate(model, m, 0.8, rng) for _ in range(per_mood)] for m in SC.MOODS}


# Fixed conversation openers, to show (and test) how Pip replies to Bloop and to you
CHATS = [("E", "J", "how are you?"), ("E", "T", "want to play?"), ("E", "Y", "want to play?"), ("E", "H", "want a snack?"),
         ("E", "G", "good morning pip"), ("E", "A", "i love you"), ("E", "L", "bye pip"), ("E", "C", "what are you doing?"),
         ("O", "J", "hi pip!"), ("O", "Y", "chase me!"), ("O", "F", "the room is tipping!"), ("O", "H", "i found berries!")]


def chat_samples(model, rng):
    who = {"E": "you", "O": "Bloop"}
    return [{"who": who[s], "mood": SC.MOODS[m], "heard": h, "reply": generate(model, m, 0.8, rng, src=s, heard=h)}
            for s, m, h in CHATS]


def load_checkpoint():
    if not os.path.exists(CKPT_IN):
        return None
    try:
        ck = torch.load(CKPT_IN, map_location="cpu")
        if ck.get("vocab") != VOCAB or ck.get("hidden") != HIDDEN:
            return grow_checkpoint(ck)
        Voice().load_state_dict(ck["model"])
        return ck
    except Exception as e:
        print("voice checkpoint not usable, starting fresh:", e, flush=True)
        return None


def grow_checkpoint(ck):
    """Put a saved voice with a smaller size or older alphabet inside the new one, keeping what it
    learned: old neurons keep their weights, letters are matched up by character, new neurons and
    new letters start with no influence (weight 0) and are learned from there."""
    old_vocab, H0 = ck["vocab"], ck["hidden"]
    if H0 > HIDDEN:
        raise ValueError("saved voice is bigger than the new one")
    old, m = ck["model"], Voice()
    new = {k: v.clone() for k, v in m.state_dict().items()}
    tok = [(IDX[c], j) for j, c in enumerate(old_vocab) if c in IDX]  # (new index, old index)
    for g in range(3):  # GRU gates r, z, n are stacked
        rows_new, rows_old = slice(g * HIDDEN, g * HIDDEN + H0), slice(g * H0, (g + 1) * H0)
        new["gru.weight_ih_l0"][rows_new] = 0
        for ni, oi in tok:
            new["gru.weight_ih_l0"][rows_new, ni] = old["gru.weight_ih_l0"][rows_old, oi]
        new["gru.weight_hh_l0"][rows_new] = 0
        new["gru.weight_hh_l0"][rows_new, :H0] = old["gru.weight_hh_l0"][rows_old]
        new["gru.bias_ih_l0"][rows_new] = old["gru.bias_ih_l0"][rows_old]
        new["gru.bias_hh_l0"][rows_new] = old["gru.bias_hh_l0"][rows_old]
    new["out.weight"].zero_()
    new["out.bias"].fill_(float(old["out.bias"].min()) - 2)  # new letters: unlikely until learned
    for ni, oi in tok:
        new["out.weight"][ni, :H0] = old["out.weight"][oi]
        new["out.bias"][ni] = old["out.bias"][oi]
    m.load_state_dict(new)
    print(f"growing the saved voice v{ck['gen']} ({H0} neurons, {len(old_vocab)} symbols) into "
          f"{HIDDEN} neurons, {V} symbols - it keeps everything it learned", flush=True)
    return {"model": m.state_dict(), "gen": ck["gen"], "grown": True}


def test_loss(model):
    """Average loss on a fixed set of example sentences (lower = writes better)."""
    lines = SC.make_lines(3000, seed=999)
    x = torch.tensor([IDX[c] for c in "".join(l + "\n" for l in lines)], dtype=torch.long)
    with torch.no_grad():
        logits, _ = model(x[:-1].unsqueeze(0))
        return float(nn.functional.cross_entropy(logits[0], x[1:]))


def train(ck=None):
    seed = SEED + (ck["gen"] if ck else 0)
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    lines = SC.make_lines(80000, seed=seed)
    corpus = set(l.split("|", 1)[1] for l in lines)
    stream = np.array([IDX[c] for c in "".join(l + "\n" for l in lines)], dtype=np.int64)
    model = Voice()
    steps = STEPS
    lr = LR
    if ck:
        model.load_state_dict(ck["model"])
        steps, lr = (STEPS if ck.get("grown") else CONTINUE_STEPS), CONTINUE_LR  # grown: new things to learn
        print(f"continuing voice version {ck['gen']} for {steps} steps", flush=True)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    start = time.time()
    loss_hist = []
    for step in range(steps):
        starts = rng.integers(0, len(stream) - SEQ - 1, BATCH)
        x = torch.from_numpy(np.stack([stream[s:s + SEQ] for s in starts]))
        y = torch.from_numpy(np.stack([stream[s + 1:s + SEQ + 1] for s in starts]))
        logits, _ = model(x)
        loss = nn.functional.cross_entropy(logits.reshape(-1, V), y.reshape(-1))
        opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % 100 == 0 or step == steps - 1:
            loss_hist.append(round(float(loss), 4))
            ex = samples(model, np.random.default_rng(step), per_mood=2)
            chats = chat_samples(model, np.random.default_rng(step + 1))
            update_status(state="training", step=step + 1, total=steps, loss=loss_hist, samples=ex,
                          chars_read=(step + 1) * BATCH * SEQ, chats=chats,
                          elapsed_s=round(time.time() - start))
            print(f"voice step {step:5d}  loss {float(loss):.3f}  e.g. P>{ex['P'][0]!r}  H>{ex['H'][0]!r}", flush=True)
    model.eval()
    # How many generated sentences are new (not copied from the examples)?
    test = [generate(model, m, 0.8, np.random.default_rng(1000 + i)) for i, m in enumerate(list(SC.MOODS) * 12)]
    novel = sum(t not in corpus for t in test) / len(test)
    update_status(state="trained", samples=samples(model, np.random.default_rng(7), per_mood=6),
                  novel_fraction=round(novel, 3), params=sum(p.numel() for p in model.parameters()))
    print(f"voice: {novel:.0%} of sampled sentences are new combinations", flush=True)
    return model


def c_array(name, t):
    flat = (t.detach().numpy() if hasattr(t, "detach") else np.asarray(t)).astype(np.float32).ravel()
    return f"static const float {name}[{flat.size}] = {{" + ",".join(f"{v:.7g}f" for v in flat) + "};\n"


def quantize_rows(w):
    """8-bit weights with one scale per row (4x smaller than 32-bit, so the voice can be bigger)."""
    w = w.detach().numpy().astype(np.float32)
    scale = np.maximum(np.abs(w).max(axis=1), 1e-8) / 127.0
    q = np.clip(np.round(w / scale[:, None]), -127, 127).astype(np.int8)
    return q, scale.astype(np.float32)


def int8_array(name, q):
    flat = q.ravel()
    return f"static const int8_t {name}[{flat.size}] = {{" + ",".join(str(int(v)) for v in flat) + "};\n"


def quantized_copy(model):
    """The voice exactly as the board runs it (8-bit weight matrices)."""
    qm = Voice()
    qm.load_state_dict(model.state_dict())
    with torch.no_grad():
        for w in (qm.gru.weight_ih_l0, qm.gru.weight_hh_l0, qm.out.weight):
            q, sc = quantize_rows(w)
            w.copy_(torch.from_numpy(q.astype(np.float32) * sc[:, None]))
    qm.eval()
    return qm


VOICE_GEN = 1


def export(model, path):
    g = model.gru
    vocab_c = "".join("\\n" if c == "\n" else ("\\'" if c == "'" else c) for c in VOCAB)
    with open(path, "w") as f:
        f.write("// Pip's voice: a tiny character-level GRU. GENERATED by training/train_voice.py - do not edit.\n")
        f.write("#pragma once\n#include <math.h>\n#include <stdint.h>\n\n")
        f.write(f"#define PV_VOICE_VERSION {VOICE_GEN}\n")
        f.write(f"#define PV_V {V}\n#define PV_H {HIDDEN}\n")
        f.write(f"#define PV_FIRST_LETTER {VOCAB.index(SC.ALPHABET[0])}  // where the alphabet starts in PV_VOCAB\n")
        f.write(f"static const char PV_VOCAB[PV_V + 1] = \"{vocab_c}\";\n\n")
        # 8-bit weight matrices (value = q * scale of its row); biases stay 32-bit
        for name, w in [("PV_WIH", g.weight_ih_l0), ("PV_WHH", g.weight_hh_l0), ("PV_WO", model.out.weight)]:
            q, sc = quantize_rows(w)   # PV_WIH [3H][V] gates r,z,n · PV_WHH [3H][H] · PV_WO [V][H]
            f.write(int8_array(name + "Q", q))
            f.write(c_array(name + "S", sc))
        f.write(c_array("PV_BIH", g.bias_ih_l0))
        f.write(c_array("PV_BHH", g.bias_hh_l0))
        f.write(c_array("PV_BO", model.out.bias))
        f.write("""
static inline float pv_sig(float x) { return 1.0f / (1.0f + expf(-x)); }

static int pv_index(char c) {
  for (int i = 0; i < PV_V; i++) if (PV_VOCAB[i] == c) return i;
  return -1;
}

// Feed one character into the GRU (updates its memory h).
static void pv_step(float *h, int tok) {
  float hn[PV_H];
  for (int j = 0; j < PV_H; j++) {
    const int8_t *wr = PV_WHHQ + j * PV_H, *wz = PV_WHHQ + (PV_H + j) * PV_H, *wn = PV_WHHQ + (2 * PV_H + j) * PV_H;
    float ar = 0, az = 0, an = 0;
    for (int k = 0; k < PV_H; k++) { ar += (float)wr[k] * h[k]; az += (float)wz[k] * h[k]; an += (float)wn[k] * h[k]; }
    float hr = PV_BHH[j] + PV_WHHS[j] * ar;
    float hz = PV_BHH[PV_H + j] + PV_WHHS[PV_H + j] * az;
    float hh = PV_BHH[2 * PV_H + j] + PV_WHHS[2 * PV_H + j] * an;
    float xr = (float)PV_WIHQ[j * PV_V + tok] * PV_WIHS[j];
    float xz = (float)PV_WIHQ[(PV_H + j) * PV_V + tok] * PV_WIHS[PV_H + j];
    float xn = (float)PV_WIHQ[(2 * PV_H + j) * PV_V + tok] * PV_WIHS[2 * PV_H + j];
    float r = pv_sig(xr + PV_BIH[j] + hr);
    float z = pv_sig(xz + PV_BIH[PV_H + j] + hz);
    float n = tanhf(xn + PV_BIH[2 * PV_H + j] + r * hh);
    hn[j] = (1 - z) * n + z * h[j];
  }
  for (int j = 0; j < PV_H; j++) h[j] = hn[j];
}

static void pv_logits(const float *h, float *out) {
  for (int v = 0; v < PV_V; v++) {
    float acc = 0;
    const int8_t *row = PV_WOQ + v * PV_H;
    for (int k = 0; k < PV_H; k++) acc += (float)row[k] * h[k];
    out[v] = PV_BO[v] + PV_WOS[v] * acc;
  }
}

#define PV_HAS_DIALOGUE 1  // this voice can reply to what someone said

// Write Pip's reply after reading a prompt: who's talking (I nobody / O Bloop / E you), Pip's
// mood letter, what they said, then "|". temperature 0 = most likely letters (used by the test).
// rand01 returns a random number in [0, 1). Returns the length written.
static int pv_generate_prompt(const char *prompt, char *out, int maxLen, float temperature, float (*rand01)(void)) {
  float h[PV_H] = {0}, lg[PV_V];
  for (const char *c = prompt; *c; c++) { int t = pv_index(*c); if (t >= 0) pv_step(h, t); }
  int n = 0;
  while (n < maxLen) {
    pv_logits(h, lg);
    int k = 0;
    if (temperature <= 0) {
      for (int v = 1; v < PV_V; v++) if (lg[v] > lg[k]) k = v;
    } else {
      float mx = lg[0], sum = 0;
      for (int v = 1; v < PV_V; v++) if (lg[v] > mx) mx = lg[v];
      for (int v = 0; v < PV_V; v++) { lg[v] = expf((lg[v] - mx) / temperature); sum += lg[v]; }
      float r = rand01() * sum, acc = 0;
      for (k = 0; k < PV_V - 1; k++) { acc += lg[k]; if (r < acc) break; }
    }
    if (PV_VOCAB[k] == '\\n') break;
    out[n++] = PV_VOCAB[k];
    pv_step(h, k);
  }
  out[n] = 0;
  return n;
}

// Self-talk for a mood (what Pip says when nobody is talking to it)
static int pv_generate(char mood, char *out, int maxLen, float temperature, float (*rand01)(void)) {
  char prompt[4] = {'I', mood, '|', 0};
  return pv_generate_prompt(prompt, out, maxLen, temperature, rand01);
}

// Reply to someone: src 'O' (Bloop) or 'E' (you). heard = what they said.
static int pv_reply(char src, char mood, const char *heard, char *out, int maxLen, float temperature, float (*rand01)(void)) {
  char prompt[40];
  int n = 0;
  prompt[n++] = src;
  prompt[n++] = mood;
  for (const char *c = heard; *c && n < 2 + 28; c++) {
    char ch = (*c >= 'A' && *c <= 'Z') ? *c + 32 : *c;   // the voice only knows lowercase
    if (ch == '|' || ch == '\\n') continue;
    for (int v = 0; v < PV_V; v++)
      if (PV_VOCAB[v] == ch && v >= PV_FIRST_LETTER) { prompt[n++] = ch; break; }   // only alphabet characters
  }
  prompt[n++] = '|';
  prompt[n] = 0;
  return pv_generate_prompt(prompt, out, maxLen, temperature, rand01);
}
""")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    update_status(state="starting")
    ck = load_checkpoint()
    prev_gen = 0
    if not ck and os.path.exists(CKPT_IN):
        try:
            prev_gen = int(torch.load(CKPT_IN, map_location="cpu").get("gen", 0))
        except Exception:
            pass
    model = train(ck)
    gen = (ck["gen"] + 1) if ck else prev_gen + 1
    new_loss = test_loss(model)
    kept = "new"
    if ck:
        old = Voice()
        old.load_state_dict(ck["model"])
        old_loss = test_loss(old)
        print(f"voice test loss: old {old_loss:.4f}, new {new_loss:.4f}", flush=True)
        if new_loss > old_loss + 0.002:
            kept, model, gen, new_loss = "old", old, ck["gen"], old_loss
        update_status(old_test_loss=round(old_loss, 4))
    VOICE_GEN = gen
    model.eval()
    update_status(version=gen, kept=kept, test_loss=round(new_loss, 4))
    os.makedirs(os.path.join(OUT, "ckpt"), exist_ok=True)
    torch.save({"model": model.state_dict(), "gen": gen, "vocab": VOCAB, "hidden": HIDDEN, "test_loss": new_loss},
               os.path.join(OUT, "ckpt", "voice.pt"))
    export(model, os.path.join(ROOT, "PipAI", "pip_voice.h"))
    board_model = quantized_copy(model)  # exactly what runs on the board (8-bit)
    with open(os.path.join(OUT, "voice_test.txt"), "w") as f:  # prompt <tab> reply, for the C test
        for m in SC.MOODS:
            f.write(f"{prompt_for(m)}\t{generate(board_model, m, 0)}\n")
        for src, m, heard in CHATS:
            f.write(f"{prompt_for(m, src, heard)}\t{generate(board_model, m, 0, src=src, heard=heard)}\n")
    update_status(board_test_loss=round(test_loss(board_model), 4),  # cost of the 8-bit squeeze
                  board_samples={m: [generate(board_model, m, 0.8, np.random.default_rng(i)) for i in range(3)]
                                 for m in ["P", "H", "J", "G"]},
                  chats=chat_samples(board_model, np.random.default_rng(5)))
    update_status(state="done")
