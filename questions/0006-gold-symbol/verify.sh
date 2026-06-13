#!/usr/bin/env bash
# Pass if the answer (read from STDIN) gives gold's chemical symbol, Au, as a
# standalone token (case-insensitive).
set -euo pipefail
grep -iqwE 'au'
