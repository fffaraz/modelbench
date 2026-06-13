#!/usr/bin/env bash
# Pass if the answer (read from STDIN) gives the formula H2O. Whitespace is
# ignored and the H2O subscript form (H₂O) is accepted.
set -euo pipefail
norm="$(tr -d '[:space:]' | sed 's/₂/2/g')"
printf '%s' "$norm" | grep -iqE 'h2o'
