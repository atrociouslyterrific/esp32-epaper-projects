// Pip's world rules in C - a line-for-line copy of training/pip_world.py.
// The brain learned in the Python version, so these MUST match it.
// GitHub runs training/test_world.c to check they do.
#pragma once
#include <math.h>

enum PipAction { A_IDLE, A_NAP, A_EAT, A_EXPLORE, A_PLAY, A_SING, A_HIDE, A_WARM_UP, A_COOL_DOWN, A_CALL, A_DANCE, A_WINDOW, PIP_N_ACTIONS };

static const char *PIP_ACTION_NAMES[PIP_N_ACTIONS] = {
  "idle", "nap", "eat", "explore", "play", "sing", "hide", "warm_up", "cool_down", "call", "dance", "window"};

typedef struct {
  float curious, playful, lazy, brave, affectionate;  // 0..1
} PipTraits;

typedef struct {
  float tempC, humidity, hour, sound, battery;  // hour 0..24, sound/battery 0..1
  int charging, touched, orient;                // orient: 0 none, 1 upright, 2 tilted, 3 upside down
} PipSenses;

typedef struct {
  float food, energy, fun, comfort, social;  // 0..1
  float grumpy, sulky, scared, frustrated;   // negative feelings, 0..1
  float hab[PIP_N_ACTIONS];  // habituation: how much Pip has done each action lately
  float habUsed;             // habituation of the action just done (for the reward)
  int prevAction;
  float repeat;
  float touchRecent;
  float novelty;
  float prevTemp;
  int hasPrevTemp;
  float prevSound;
  int prevOrient;
} PipState;

#define PIP_N_FEATURES 52

static inline float pip_clamp01(float v) { return v < 0 ? 0 : (v > 1 ? 1 : v); }
static inline float pip_clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

static void pip_clamp_needs(PipState *s) {
  s->food = pip_clamp01(s->food);
  s->energy = pip_clamp01(s->energy);
  s->fun = pip_clamp01(s->fun);
  s->comfort = pip_clamp01(s->comfort);
  s->social = pip_clamp01(s->social);
  s->grumpy = pip_clamp01(s->grumpy);
  s->sulky = pip_clamp01(s->sulky);
  s->scared = pip_clamp01(s->scared);
  s->frustrated = pip_clamp01(s->frustrated);
}

static void pip_init(PipState *s, float food, float energy, float fun, float comfort, float social) {
  s->food = food; s->energy = energy; s->fun = fun; s->comfort = comfort; s->social = social;
  s->grumpy = s->sulky = s->scared = s->frustrated = 0;
  for (int k = 0; k < PIP_N_ACTIONS; k++) s->hab[k] = 0;
  s->habUsed = 0;
  s->prevAction = 0; s->repeat = 0; s->touchRecent = 0; s->novelty = 0;
  s->prevTemp = 0; s->hasPrevTemp = 0; s->prevSound = 0; s->prevOrient = 0;
}

// Take in this moment's senses (before deciding).
static void pip_observe(PipState *s, const PipSenses *se) {
  float touched = se->touched ? 1.0f : 0.0f;
  s->touchRecent = s->touchRecent * 0.7f + touched;
  s->social += 0.1f * touched * (1 - 0.7f * s->sulky);  // a sulky Pip barely notices the first pats
  s->fun += 0.03f * touched;
  float prevT = s->hasPrevTemp ? s->prevTemp : se->tempC;
  float change = fabsf(se->tempC - prevT) / 2.0f + fabsf(se->sound - s->prevSound) +
                 (se->orient != s->prevOrient ? 1.0f : 0.0f);
  s->novelty = change < 1.0f ? change : 1.0f;
  pip_clamp_needs(s);
}

// The 40 numbers the brain sees (same order as features() in Python).
static void pip_features(const PipState *s, const PipSenses *se, const PipTraits *t, float *x) {
  int i = 0;
  x[i++] = s->food; x[i++] = s->energy; x[i++] = s->fun; x[i++] = s->comfort; x[i++] = s->social;
  x[i++] = s->grumpy; x[i++] = s->sulky; x[i++] = s->scared; x[i++] = s->frustrated;
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
  for (int k = 0; k < PIP_N_ACTIONS; k++) x[i++] = s->hab[k];
}

// Do the chosen action for one step (3 minutes), plus natural drift.
static void pip_act(PipState *s, const PipSenses *se, const PipTraits *t, int a) {
  float T = se->tempC, sound = se->sound, hour = se->hour;
  float cold = pip_clamp01((18.0f - T) / 8.0f);
  float hot = pip_clamp01((T - 26.0f) / 8.0f);
  float flip = se->orient == 3 ? 0.4f : (se->orient == 2 ? 0.15f : 0.0f);
  float hiding = a == A_HIDE ? 1.0f : 0.0f;
  float habA = s->hab[a];          // how much Pip has done this lately
  float fresh = 1 - 0.6f * habA;   // fun wears off when you keep doing the same thing
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
    s->fun += (0.04f + 0.04f * t->curious + 0.05f * s->novelty) * fresh;
    s->energy -= 0.009f;
    s->food -= 0.004f;
  }
  if (a == A_PLAY) {
    s->fun += (0.05f + 0.04f * t->playful) * fresh;
    s->energy -= 0.011f;
    s->social += 0.03f * ownerNear;
  }
  if (a == A_SING) {
    s->fun += 0.01f * fresh;
    s->social += 0.01f + 0.02f * t->affectionate * ownerNear;
    s->energy -= 0.004f;
  }
  s->fun -= hiding * 0.003f;
  if (a == A_WARM_UP) { s->comfort += 0.06f * cold; s->energy -= 0.004f; }
  if (a == A_COOL_DOWN) { s->comfort += 0.06f * hot; s->energy -= 0.004f; }
  if (a == A_CALL) s->social += ownerNear > 0 ? 0.05f : 0.005f;

  // Dance: big fun for playful Pips, even better with someone watching
  if (a == A_DANCE) {
    s->fun += (0.035f + 0.02f * t->playful) * fresh;
    s->social += 0.04f * ownerNear;
    s->energy -= 0.012f;
    s->food -= 0.003f;
  }
  // Look out the window: calm entertainment; sunshine is cosy in the day, the moon at night
  if (a == A_WINDOW) {
    float day = 1.0f - night;
    s->fun += (0.008f + 0.012f * t->curious * day + 0.005f * night) * fresh;
    s->comfort += 0.01f * day;
    s->energy += 0.001f;
  }

  // ---- Negative feelings (same as pip_world.py)
  {
    float touched = se->touched ? 1.0f : 0.0f;
    float woken = touched * (s->prevAction == A_NAP ? 1.0f : 0.0f);
    float pestered = touched * (s->energy < 0.3f ? 1.0f : 0.0f) * (s->touchRecent > 1.5f ? 1.0f : 0.0f);
    float resting = (a == A_NAP || a == A_IDLE) ? 1.0f : 0.0f;
    s->grumpy = s->grumpy * (0.85f - 0.15f * resting) + (0.5f * woken + 0.3f * pestered) * (0.6f + 0.8f * t->lazy);

    float lonelyNow = (s->social < 0.2f && s->touchRecent < 0.05f) ? 1.0f : 0.0f;
    s->sulky = s->sulky * (s->social > 0.4f ? 0.9f : 0.98f) + 0.03f * lonelyNow * (0.5f + t->affectionate) - 0.25f * touched;

    float flipped = (se->orient == 3 && s->prevOrient != 3) ? 1.0f : 0.0f;
    float tilted = (se->orient == 2 && s->prevOrient != 2) ? 1.0f : 0.0f;
    float loud = sound > 0.7f ? 1.0f : 0.0f;
    s->scared = s->scared * (0.85f - 0.15f * t->brave) - 0.15f * hiding +
                (0.6f * flipped + 0.3f * tilted + 0.5f * loud) * (1.2f - 0.8f * t->brave);

    float failed = ((a == A_PLAY || a == A_DANCE || a == A_EXPLORE) && s->energy < 0.15f) ? 1.0f : 0.0f;
    float stuffed = (a == A_EAT && s->food > 0.95f) ? 1.0f : 0.0f;
    s->frustrated = s->frustrated * 0.8f + 0.3f * failed + 0.2f * stuffed;
  }

  pip_clamp_needs(s);
  s->repeat = (a == s->prevAction) ? s->repeat + 1 : 0;
  // Habituation fades over time and builds up for whatever Pip just did
  s->habUsed = habA;
  for (int k = 0; k < PIP_N_ACTIONS; k++) s->hab[k] *= 0.92f;
  s->hab[a] = s->hab[a] + 0.08f < 1.0f ? s->hab[a] + 0.08f : 1.0f;
  s->prevAction = a;
  s->prevTemp = se->tempC; s->hasPrevTemp = 1;
  s->prevSound = se->sound;
  s->prevOrient = se->orient;
}

// How good life feels after an action (same as reward() in pip_world.py).
// Pip's brain uses this on the board to keep learning from its own life.
// night = 1 if it was night when the action happened (22:00-07:00).
static float pip_reward(const PipState *s, const PipTraits *t, int a, float night) {
  float w_food = 1.0f;
  float w_energy = 0.8f + 0.6f * t->lazy;
  float w_fun = 0.6f + 0.6f * t->playful;
  float w_comfort = 1.0f - 0.3f * t->brave;
  float w_social = 0.3f + 0.9f * t->affectionate;
  float r_feel = -0.3f * (s->grumpy * s->grumpy + s->sulky * s->sulky + s->scared * s->scared +
                          s->frustrated * s->frustrated);
  float r = r_feel - (w_food * (1 - s->food) * (1 - s->food) + w_energy * (1 - s->energy) * (1 - s->energy) +
              w_fun * (1 - s->fun) * (1 - s->fun) + w_comfort * (1 - s->comfort) * (1 - s->comfort) +
              w_social * (1 - s->social) * (1 - s->social));
  const float like = 0.3f;
  if (a == A_EXPLORE) r += like * (t->curious - 0.5f);
  if (a == A_PLAY) r += like * (t->playful - 0.5f);
  if (a == A_NAP) r += like * (t->lazy - 0.5f);
  if (a == A_EXPLORE || a == A_PLAY) r -= like * 0.5f * (t->lazy - 0.5f);
  if (a == A_SING || a == A_CALL) r += like * (t->affectionate - 0.5f);
  if (a == A_HIDE) r += like * (0.5f - t->brave);
  if (a == A_DANCE) r += like * 0.5f * (t->playful - 0.5f);
  if (a == A_WINDOW) r += like * 0.25f * (t->curious - 0.5f);
  if (a == A_EXPLORE || a == A_PLAY || a == A_CALL || a == A_DANCE) r += 0.04f;
  if (a == A_SING) r += 0.01f;
  // Doing the same thing over and over is dull (except napping when tired / eating when hungry)
  int needed = (a == A_NAP && s->energy < 0.4f) || (a == A_EAT && s->food < 0.4f);
  if (!needed) r -= 0.1f * s->habUsed;
  float day = 1.0f - night;
  if (a == A_NAP && s->energy > 0.6f) r -= 0.04f * day;
  if (a == A_EAT && s->food > 0.7f) r -= 0.03f;
  if (s->repeat > 4 && a != A_NAP) r -= 0.02f;
  if (s->repeat > 12 && a == A_NAP) r -= 0.02f;
  if (s->repeat > 2 && a == A_WINDOW) r -= 0.02f;  // staring out of the window gets old fast
  return r;
}
