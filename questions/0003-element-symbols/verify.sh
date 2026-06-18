#!/usr/bin/env bash
# Pass if the model's answer (read from STDIN) lists the expected symbols, one
# per line, in the same order as expected.txt. Comparison ignores blank lines
# and surrounding whitespace, but symbols must match exactly (case-sensitive).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)" # resolve support files next to this script

# normalize: trim each line, drop blank lines
norm() { sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e '/^$/d'; }

expected="$(norm < "$here/expected.txt")"
actual="$(norm)" # reads the model's answer from STDIN

[ "$actual" = "$expected" ]
