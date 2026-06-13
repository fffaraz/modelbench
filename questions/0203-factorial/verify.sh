#!/usr/bin/env bash
# Pass if the answer (read from STDIN) contains 720 as a standalone number.
set -euo pipefail
grep -qE '(^|[^0-9])720([^0-9]|$)'
