#!/usr/bin/env bash
# Pass if the model's answer (read from STDIN) lists the primes below 20, one per
# line, in the same order as expected.txt. Blank lines and surrounding whitespace
# are ignored, but the numbers must otherwise match exactly.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)" # resolve support files next to this script

# normalize: trim each line, drop blank lines
norm() { sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e '/^$/d'; }

expected="$(norm < "$here/expected.txt")"
actual="$(norm)" # reads the model's answer from STDIN

[ "$actual" = "$expected" ]
