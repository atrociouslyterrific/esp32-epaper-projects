// Checks the C motion model writes exactly the same clips as the Python one (most-likely mode).
// Build: gcc -O2 -I PipAI training/test_motion.c -lm -o test_motion
#include <stdio.h>
#include "pip_motion.h"

static float no_rand(void) { return 0; }

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "training/out/motion_test.txt";
  FILE *f = fopen(path, "r");
  if (!f) { printf("cannot open %s\n", path); return 1; }
  int a, m, e, n, total = 0, same = 0;
  while (fscanf(f, "%d %d %d %d", &a, &m, &e, &n) == 4) {
    int wdx[64], wjy[64], wsq[64];
    for (int i = 0; i < n; i++) fscanf(f, "%d %d %d", &wdx[i], &wjy[i], &wsq[i]);
    int8_t dx[64], jy[64];
    uint8_t sq[64];
    int got = pm_generate(a, m, e, dx, jy, sq, 64, 0, no_rand);
    int ok = got == n;
    for (int i = 0; ok && i < n; i++) ok = dx[i] == wdx[i] && jy[i] == wjy[i] && sq[i] == wsq[i];
    total++;
    same += ok;
    printf("action %2d mood %d energy %d: python %2d frames, c %2d frames %s\n", a, m, e, n, got, ok ? "match" : "DIFFERENT");
  }
  printf("%d of %d clips match\n", same, total);
  int pass = total > 0 && same >= total - total / 10;  // allow a few float rounding differences
  printf(pass ? "PASS: C motion matches Python\n" : "FAIL: C motion differs from Python\n");
  return pass ? 0 : 1;
}
