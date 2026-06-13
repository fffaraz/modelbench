#!/usr/bin/env bash
# "All but 9 run away" means 9 remain. Pass if the answer (read from STDIN)
# contains 9 as a standalone number (the "17" in the prompt has no lone 9).
set -euo pipefail
grep -qE '(^|[^0-9])9([^0-9]|$)'
