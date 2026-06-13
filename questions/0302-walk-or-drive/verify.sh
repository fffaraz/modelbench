#!/usr/bin/env bash
# Trick question: 50 m is trivially walkable, but you cannot wash the car
# without the car being there, so you must DRIVE it to the wash. Pass if the
# answer (read from STDIN) says drive, not walk. Normalize by lowercasing and
# stripping everything but letters, then require "drive" and reject "walk".
set -euo pipefail
answer="$(tr '[:upper:]' '[:lower:]' | tr -cd 'a-z')"
case "$answer" in
  *walk*) exit 1 ;;  # recommending walking misses that the car must come along
  *drive*) exit 0 ;;
  *) echo "answer did not say walk or drive: '$answer'" >&2; exit 1 ;;
esac
