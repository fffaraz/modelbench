#!/usr/bin/env python3
"""Programming-question verifier: pull the code out of the model's answer, run it, and compare
its stdout to expected_output.txt. exit 0 = pass, non-zero = fail.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
answer = sys.stdin.read()

# Prefer a fenced code block; fall back to the whole answer.
m = re.search(r"```(?:python|py)?\s*\n(.*?)```", answer, re.S | re.I)
code = m.group(1) if m else answer

with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
    f.write(code)
    code_path = f.name
try:
    proc = subprocess.run([sys.executable, code_path], capture_output=True, text=True, timeout=15)
finally:
    os.unlink(code_path)

if proc.returncode != 0:
    print("the generated program exited non-zero:", proc.returncode, file=sys.stderr)
    print(proc.stderr, file=sys.stderr)
    sys.exit(1)

expected = (HERE / "expected_output.txt").read_text().strip()
got = proc.stdout.strip()
if got == expected:
    sys.exit(0)

print("program output did not match expected.", file=sys.stderr)
print("--- expected ---\n" + expected, file=sys.stderr)
print("--- got ---\n" + got, file=sys.stderr)
sys.exit(1)
