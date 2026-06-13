#!/usr/bin/env bash
# The sequence is n*(n+1): 2, 6, 12, 20, 30, so the next term is 6*7 = 42.
# Pass if the answer (read from STDIN) contains 42 as a standalone number.
set -euo pipefail
grep -qE '(^|[^0-9])42([^0-9]|$)'
