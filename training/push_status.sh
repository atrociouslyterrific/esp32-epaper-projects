#!/usr/bin/env bash
# Publishes training/out/status.json to the "status" branch so the status website
# (GitHub Pages) can show live progress. Keeps that branch to a single commit.
set -euo pipefail
SRC="${1:-training/out/status.json}"
[ -f "$SRC" ] || exit 0
DIR="${RUNNER_TEMP:-/tmp}/status-branch"
if [ ! -d "$DIR/.git" ]; then
  mkdir -p "$DIR"
  git -C "$DIR" init -q
  git -C "$DIR" checkout -q -b status
  git -C "$DIR" config user.name "github-actions[bot]"
  git -C "$DIR" config user.email "41898283+github-actions[bot]@users.noreply.github.com"
  git -C "$DIR" remote add origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
fi
cp "$SRC" "$DIR/status.json"
git -C "$DIR" add status.json
git -C "$DIR" commit -q --allow-empty -m "Training status" --amend 2>/dev/null || \
  git -C "$DIR" commit -q --allow-empty -m "Training status"
git -C "$DIR" push -q -f origin status || echo "status push failed (will retry)"
