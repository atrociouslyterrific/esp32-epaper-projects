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

sys.path.insert(0, os.path.dirname(__file__))
import speech_corpus as SC  # noqa: E402

SEED = 11
HIDDEN = 96
STEPS = int(os.environ.get("PIP_VOICE_STEPS", "3000"))                 # from scratch
CONTINUE_STEPS = int(os.environ.get("PIP_VOICE_CONTINUE_STEPS", "800"))  # nightly top-up
CONTINUE_LR = 1e-3
BATCH, SEQ, LR = 128, 96, 3e-3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "training", "out")
STATUS_PATH = os.path.join(OUT, "status.json")
CKPT_IN = os.path.join(ROOT, "training", "ckpt", "voice.pt")

# Vocabulary: newline (end of sentence), ">", mood letters, then the alphabet Pip can write
VOCAB = ["\n", ">"] + list(SC.MOODS) + list(SC.ALPHABET)
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
    if voice.get("state") in ("starting", "training"):
        s["state"] = "voice"
    elif voice.get("state") in ("trained", "done"):
        s["state"] = "trained"
    s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    tmp = STATUS_PATH + ".tmp"
    json.dump(s, open(tmp, "w"))
    os.replace(tmp, STATUS_PATH)


def generate(model, mood, temperature=0.8, rng=None, max_len=SC.MAX_LEN + 2):
    """Write one sentence for a mood. temperature 0 = always the most likely letter."""
    with torch.no_grad():
        h = None
        for c in mood + ">":
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


def load_checkpoint():
    if not os.path.exists(CKPT_IN):
        return None
    try:
        ck = torch.load(CKPT_IN, map_location="cpu")
        if ck.get("vocab") != VOCAB or ck.get("hidden") != HIDDEN:
            print("voice checkpoint has a different alphabet or size, starting fresh", flush=True)
            return None
        Voice().load_state_dict(ck["model"])
        return ck
    except Exception as e:
        print("voice checkpoint not usable, starting fresh:", e, flush=True)
        return None


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
    lines = SC.make_lines(40000, seed=seed)
    corpus = set(l.split(">", 1)[1] for l in lines)
    stream = np.array([IDX[c] for c in "".join(l + "\n" for l in lines)], dtype=np.int64)
    model = Voice()
    steps = STEPS
    lr = LR
    if ck:
        model.load_state_dict(ck["model"])
        steps, lr = CONTINUE_STEPS, CONTINUE_LR
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
            update_status(state="training", step=step + 1, total=steps, loss=loss_hist, samples=ex,
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
    flat = t.detach().numpy().astype(np.float32).ravel()
    return f"static const float {name}[{flat.size}] = {{" + ",".join(f"{v:.7g}f" for v in flat) + "};\n"


VOICE_GEN = 1


def export(model, path):
    g = model.gru
    vocab_c = "".join("\\n" if c == "\n" else ("\\'" if c == "'" else c) for c in VOCAB)
    with open(path, "w") as f:
        f.write("// Pip's voice: a tiny character-level GRU. GENERATED by training/train_voice.py - do not edit.\n")
        f.write("#pragma once\n#include <math.h>\n#include <stdint.h>\n\n")
        f.write(f"#define PV_VOICE_VERSION {VOICE_GEN}\n")
        f.write(f"#define PV_V {V}\n#define PV_H {HIDDEN}\n")
        f.write(f"static const char PV_VOCAB[PV_V + 1] = \"{vocab_c}\";\n\n")
        f.write(c_array("PV_WIH", g.weight_ih_l0))   # [3H][V]  gates r, z, n
        f.write(c_array("PV_WHH", g.weight_hh_l0))   # [3H][H]
        f.write(c_array("PV_BIH", g.bias_ih_l0))
        f.write(c_array("PV_BHH", g.bias_hh_l0))
        f.write(c_array("PV_WO", model.out.weight))  # [V][H]
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
    float hr = PV_BHH[j], hz = PV_BHH[PV_H + j], hh = PV_BHH[2 * PV_H + j];
    const float *wr = PV_WHH + j * PV_H, *wz = PV_WHH + (PV_H + j) * PV_H, *wn = PV_WHH + (2 * PV_H + j) * PV_H;
    for (int k = 0; k < PV_H; k++) { hr += wr[k] * h[k]; hz += wz[k] * h[k]; hh += wn[k] * h[k]; }
    float r = pv_sig(PV_WIH[j * PV_V + tok] + PV_BIH[j] + hr);
    float z = pv_sig(PV_WIH[(PV_H + j) * PV_V + tok] + PV_BIH[PV_H + j] + hz);
    float n = tanhf(PV_WIH[(2 * PV_H + j) * PV_V + tok] + PV_BIH[2 * PV_H + j] + r * hh);
    hn[j] = (1 - z) * n + z * h[j];
  }
  for (int j = 0; j < PV_H; j++) h[j] = hn[j];
}

static void pv_logits(const float *h, float *out) {
  for (int v = 0; v < PV_V; v++) {
    float s = PV_BO[v];
    for (int k = 0; k < PV_H; k++) s += PV_WO[v * PV_H + k] * h[k];
    out[v] = s;
  }
}

// Write a sentence for a mood letter. temperature 0 = most likely letters (used by the test).
// rand01 returns a random number in [0, 1). Returns the length written.
static int pv_generate(char mood, char *out, int maxLen, float temperature, float (*rand01)(void)) {
  float h[PV_H] = {0}, lg[PV_V];
  pv_step(h, pv_index(mood));
  pv_step(h, pv_index('>'));
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
""")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    update_status(state="starting")
    ck = load_checkpoint()
    model = train(ck)
    gen = (ck["gen"] + 1) if ck else 1
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
    with open(os.path.join(OUT, "voice_test.txt"), "w") as f:
        for m in SC.MOODS:
            f.write(f"{m}\t{generate(model, m, 0)}\n")
    update_status(state="done")
