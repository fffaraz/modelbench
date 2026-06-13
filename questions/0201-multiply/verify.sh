#!/usr/bin/env bash
# Pass if the answer (read from STDIN) contains 437 as a standalone number.
set -euo pipefail
grep -qE '(^|[^0-9])437([^0-9]|$)'
