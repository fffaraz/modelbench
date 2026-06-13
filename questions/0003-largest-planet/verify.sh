#!/usr/bin/env bash
# Pass if the answer (read from STDIN) names Jupiter.
set -euo pipefail
grep -iqE '\bjupiter\b'
