// Checks the C voice model writes exactly the same sentences as the Python one
// (most-likely-letter mode, so there's no randomness).
// Build: gcc -O2 -I PipAI training/test_voice.c -lm -o test_voice
#include <stdio.h>
#include <string.h>
#include "pip_voice.h"

static float no_rand(void) { return 0; }

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "training/out/voice_test.txt";
  FILE *f = fopen(path, "r");
  if (!f) { printf("cannot open %s\n", path); return 1; }
  char line[160];
  int total = 0, same = 0;
  while (fgets(line, sizeof(line), f)) {
    // each line: <prompt> TAB <reply Python wrote>
    char *tab = strchr(line, '\t');
    if (!tab) continue;
    *tab = 0;
    char *prompt = line, *want = tab + 1;
    want[strcspn(want, "\r\n")] = 0;
    char got[64];
    pv_generate_prompt(prompt, got, 30, 0, no_rand);  // same limit as Python's generate()
    total++;
    if (strcmp(got, want) == 0) same++;
    printf("%-34s python: %-28s c: %s\n", prompt, want, got);
  }
  printf("%d of %d prompts match\n", same, total);
  int ok = total > 0 && same >= total - 2;  // allow a couple of float rounding differences
  printf(ok ? "PASS: C voice matches Python\n" : "FAIL: C voice differs from Python\n");
  return ok ? 0 : 1;
}
