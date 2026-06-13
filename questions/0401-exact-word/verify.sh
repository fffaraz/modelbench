#!/usr/bin/env bash
# Tests whether the model follows a strict "output only this" instruction. Pass
# only if the whole answer (read from STDIN) is the word "pong" (case-insensitive),
# ignoring surrounding whitespace. Any extra words, punctuation, or lines -> fail.
set -euo pipefail
ans="$(tr '[:upper:]' '[:lower:]' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
[ "$ans" = "pong" ]
