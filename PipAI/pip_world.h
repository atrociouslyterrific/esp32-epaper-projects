// Pip's world rules in C - a line-for-line copy of training/pip_world.py.
// The brain learned in the Python version, so these MUST match it.
// GitHub runs training/test_world.c to check they do.
#pragma once
#include <math.h>

enum PipAction { A_IDLE, A_NAP, A_EAT, A_EXPLORE, A_PLAY, A_SING, A_HIDE, A_WARM_UP, A_COOL_DOWN, A_CALL, PIP_N_ACTIONS };

static const char *PIP_ACTION_NAMES[PIP_N_ACTIONS] = {
  "idle", "nap", "eat", "explore", "play", "sing", "hide", "warm_up", "cool_down", "call"};

typedef struct {
  float curious, playful, lazy, brave, affectionate;  // 0..1
} PipTraits;

typedef struct {
  float tempC, humidity, hour, sound, battery;  // hour 0..24, sound/battery 0..1
  int charging, touched, orient;                // orient: 0 none, 1 upright, 2 tilted, 3 upside down
} PipSenses;

typedef struct {
  float food, energy, fun, comfort, social;  // 0..1
  int prevAction;
  float repeat;
  float touchRecent;
  float novelty;
  float prevTemp;
  int hasPrevTemp;
  float prevSound;
  int prevOrient;
} PipState;

#define PIP_N_FEATURES 34

static inline float pip_clamp01(float v) { return v < 0 ? 0 : (v > 1 ? 1 : v); }
static inline float pip_clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

static void pip_clamp_needs(PipState *s) {
  s->food = pip_clamp01(s->food);
  s->energy = pip_clamp01(s->energy);
  s->fun = pip_clamp01(s->fun);
  s->comfort = pip_clamp01(s->comfort);
  s->social = pip_clamp01(s->social);
}

static void pip_init(PipState *s, float food, float energy, float fun, float comfort, float social) {
  s->food = food; s->energy = energy; s->fun = fun; s->comfort = comfort; s->social = social;
  s->prevAction = 0; s->repeat = 0; s->touchRecent = 0; s->novelty = 0;
  s->prevTemp = 0; s->hasPrevTemp = 0; s->prevSound = 0; s->prevOrient = 0;
}

// Take in this moment's senses (before deciding).
static void pip_observe(PipState *s, const PipSenses *se) {
  float touched = se->touched ? 1.0f : 0.0f;
  s->touchRecent = s->touchRecent * 0.7f + touched;
  s->social += 0.1f * touched;
  s->fun += 0.03f * touched;
  float prevT = s->hasPrevTemp ? s->prevTemp : se->tempC;
  float change = fabsf(se->tempC - prevT) / 2.0f + fabsf(se->sound - s->prevSound) +
                 (se->orient != s->prevOrient ? 1.0f : 0.0f);
  s->novelty = change < 1.0f ? change : 1.0f;
  pip_clamp_needs(s);
}

// The 34 numbers the brain sees (same order as features() in Python).
static void pip_features(const PipState *s, const PipSenses *se, const PipTraits *t, float *x) {
  int i = 0;
  x[i++] = s->food; x[i++] = s->energy; x[i++] = s->fun; x[i++] = s->comfort; x[i++] = s->social;
  x[i++] = (se->tempC - 22.0f) / 10.0f;
  x[i++] = se->humidity / 100.0f;
  x[i++] = sinf(2.0f * (float)M_PI * se->hour / 24.0f);
  x[i++] = cosf(2.0f * (float)M_PI * se->hour / 24.0f);
  x[i++] = se->sound;
  x[i++] = se->battery;
  x[i++] = se->charging ? 1.0f : 0.0f;
  x[i++] = s->touchRecent < 1.0f ? s->touchRecent : 1.0f;
  for (int k = 0; k < 4; k++) x[i++] = (se->orient == k) ? 1.0f : 0.0f;
  x[i++] = s->novelty;
  x[i++] = t->curious; x[i++] = t->playful; x[i++] = t->lazy; x[i++] = t->brave; x[i++] = t->affectionate;
  for (int k = 0; k < PIP_N_ACTIONS; k++) x[i++] = (s->prevAction == k) ? 1.0f : 0.0f;
  x[i++] = (s->repeat < 10 ? s->repeat : 10) / 10.0f;
}

// Do the chosen action for one step (3 minutes), plus natural drift.
static void pip_act(PipState *s, const PipSenses *se, const PipTraits *t, int a) {
  float T = se->tempC, sound = se->sound, hour = se->hour;
  float cold = pip_clamp01((18.0f - T) / 8.0f);
  float hot = pip_clamp01((T - 26.0f) / 8.0f);
  float flip = se->orient == 3 ? 0.4f : (se->orient == 2 ? 0.15f : 0.0f);
  float hiding = a == A_HIDE ? 1.0f : 0.0f;
  float noise = sound * 0.5f * (1 - 0.6f * t->brave) * (1 - 0.5f * hiding);
  float envComfort = pip_clamp01(1.0f - cold - hot - noise - flip * (1 - 0.5f * hiding));
  float napping = a == A_NAP ? 1.0f : 0.0f;
  float night = (hour >= 22 || hour < 7) ? 1.0f : 0.0f;
  float ownerNear = s->touchRecent > 0.3f ? 1.0f : 0.0f;

  // Natural drift
  s->food -= 0.006f * (1 - 0.5f * napping);
  s->energy -= 0.004f + 0.004f * (se->battery < 0.2f ? 1.0f : 0.0f);
  s->fun -= 0.007f;  // fun fades fairly fast: Pip needs to DO things
  s->social -= 0.003f;
  s->comfort += 0.1f * (envComfort - s->comfort);

  // Action effects
  if (a == A_IDLE) s->energy += 0.002f;

  float startled = sound > 0.6f ? 1.0f : 0.0f;
  float restless = s->energy > 0.8f ? 1.0f : 0.0f;  // not tired: napping barely helps and gets boring
  float napGain = 0.03f * (1 - 0.8f * sound) * (1 + 0.3f * night) * (1 - startled) * (1 - 0.7f * restless);
  s->energy += napping * napGain;
  s->comfort -= napping * 0.1f * startled;
  s->fun -= napping * 0.004f * restless;

  if (a == A_EAT) {
    float overfull = s->food > 0.75f ? 1.0f : 0.0f;  // eating when already fairly full feels bad
    s->food += 0.08f;
    s->comfort -= 0.08f * overfull;
  }
  if (a == A_EXPLORE) {
    s->fun += 0.03f + 0.03f * t->curious + 0.05f * s->novelty;
    s->energy -= 0.012f;
    s->food -= 0.004f;
  }
  if (a == A_PLAY) {
    s->fun += 0.04f + 0.03f * t->playful;
    s->energy -= 0.015f;
    s->social += 0.03f * ownerNear;
  }
  if (a == A_SING) {
    s->fun += 0.015f;
    s->social += 0.01f + 0.02f * t->affectionate * ownerNear;
    s->energy -= 0.004f;
  }
  s->fun -= hiding * 0.003f;
  if (a == A_WARM_UP) { s->comfort += 0.06f * cold; s->energy -= 0.004f; }
  if (a == A_COOL_DOWN) { s->comfort += 0.06f * hot; s->energy -= 0.004f; }
  if (a == A_CALL) s->social += ownerNear > 0 ? 0.05f : 0.005f;

  pip_clamp_needs(s);
  s->repeat = (a == s->prevAction) ? s->repeat + 1 : 0;
  s->prevAction = a;
  s->prevTemp = se->tempC; s->hasPrevTemp = 1;
  s->prevSound = se->sound;
  s->prevOrient = se->orient;
}
