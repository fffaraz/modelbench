#!/usr/bin/env python3
"""Pass if the answer is a JSON object with exactly {"name": "Alice", "age": 30}.

Tolerant of a stray ```json fence or surrounding prose, but the parsed object must
have exactly those two keys with those values (age must be the number 30, not "30").
"""
import json
import re
import sys

answer = sys.stdin.read().strip()

# Tolerate a ```json ... ``` fence if the model added one despite instructions.
m = re.search(r"```(?:json)?\s*\n?(.*?)```", answer, re.S | re.I)
if m:
    answer = m.group(1).strip()

# Fall back to the first {...} block if there's surrounding prose.
if not answer.startswith("{"):
    m = re.search(r"\{.*\}", answer, re.S)
    if m:
        answer = m.group(0)

try:
    obj = json.loads(answer)
except json.JSONDecodeError as e:
    print("not valid JSON:", e, file=sys.stderr)
    sys.exit(1)

if not isinstance(obj, dict):
    print("expected a JSON object, got:", type(obj).__name__, file=sys.stderr)
    sys.exit(1)
if set(obj.keys()) != {"name", "age"}:
    print("keys must be exactly name, age; got:", sorted(obj.keys()), file=sys.stderr)
    sys.exit(1)
if obj.get("name") != "Alice":
    print("name must be 'Alice'; got:", repr(obj.get("name")), file=sys.stderr)
    sys.exit(1)
if obj.get("age") != 30 or isinstance(obj.get("age"), bool):
    print("age must be the number 30; got:", repr(obj.get("age")), file=sys.stderr)
    sys.exit(1)

sys.exit(0)
