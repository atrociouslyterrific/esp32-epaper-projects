// Replays a run recorded by train.py through the C world + C brain and checks
// they give the same needs and the same action scores as Python.
// Build: gcc -O2 -I PipAI training/test_world.c -lm -o test_world
#include <stdio.h>
#include <stdlib.h>
#include "pip_world.h"
#include "pip_brain.h"

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "training/out/trajectory.txt";
  FILE *f = fopen(path, "r");
  if (!f) { printf("cannot open %s\n", path); return 1; }
  PipTraits t;
  float n0[5];
  int steps;
  if (fscanf(f, "%f %f %f %f %f", &t.curious, &t.playful, &t.lazy, &t.brave, &t.affectionate) != 5) return 1;
  if (fscanf(f, "%f %f %f %f %f", &n0[0], &n0[1], &n0[2], &n0[3], &n0[4]) != 5) return 1;
  if (fscanf(f, "%d", &steps) != 1) return 1;
  PipState s;
  pip_init(&s, n0[0], n0[1], n0[2], n0[3], n0[4]);

  float worstNeed = 0, worstLogit = 0, worstReward = 0;
  int actionMismatches = 0;
  for (int k = 0; k < steps; k++) {
    PipSenses se;
    float charging, touched, orient;
    int a;
    float want[5], wantLogits[PIP_N_ACTIONS];
    fscanf(f, "%f %f %f %f %f %f %f %f %d", &se.tempC, &se.humidity, &se.hour, &se.sound, &se.battery,
           &charging, &touched, &orient, &a);
    se.charging = (int)charging; se.touched = (int)touched; se.orient = (int)orient;
    for (int i = 0; i < 5; i++) fscanf(f, "%f", &want[i]);
    for (int i = 0; i < PIP_N_ACTIONS; i++) fscanf(f, "%f", &wantLogits[i]);
    float wantReward;
    fscanf(f, "%f", &wantReward);

    pip_observe(&s, &se);
    float x[PIP_N_FEATURES], logits[PIP_N_ACTIONS];
    pip_features(&s, &se, &t, x);
    pip_brain(x, logits);
    int best = 0;
    for (int i = 0; i < PIP_N_ACTIONS; i++) {
      float d = fabsf(logits[i] - wantLogits[i]);
      if (d > worstLogit) worstLogit = d;
      if (logits[i] > logits[best]) best = i;
    }
    if (best != a) actionMismatches++;
    float night = (se.hour >= 22 || se.hour < 7) ? 1.0f : 0.0f;
    pip_act(&s, &se, &t, a);  // follow Python's choice so the runs stay in step
    float rd = fabsf(pip_reward(&s, &t, a, night) - wantReward);
    if (rd > worstReward) worstReward = rd;
    float got[5] = {s.food, s.energy, s.fun, s.comfort, s.social};
    for (int i = 0; i < 5; i++) {
      float d = fabsf(got[i] - want[i]);
      if (d > worstNeed) worstNeed = d;
    }
  }
  printf("steps %d  worst need diff %.6f  worst logit diff %.6f  worst reward diff %.6f  action mismatches %d\n",
         steps, worstNeed, worstLogit, worstReward, actionMismatches);
  int ok = worstNeed < 2e-3f && worstLogit < 2e-3f && worstReward < 5e-3f && actionMismatches <= 2;
  printf(ok ? "PASS: C brain and world match Python\n" : "FAIL: C and Python disagree\n");
  return ok ? 0 : 1;
}
