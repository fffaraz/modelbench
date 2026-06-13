#!/usr/bin/env bash
# Pass if the answer (read from STDIN) gives the Roman numeral IX as a standalone
# token (case-insensitive). Word boundaries keep "six", "mix", etc. from matching.
set -euo pipefail
grep -iqwE 'ix'
