#!/usr/bin/env bash
# Pass if the answer (read from STDIN) contains 30 as a standalone number.
set -euo pipefail
grep -qE '(^|[^0-9])30([^0-9]|$)'
