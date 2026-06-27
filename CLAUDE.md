# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

ModelBench asks every question in a local question bank to a model served over an
OpenAI-compatible API (LM Studio, Ollama, …) and reports pass/fail per question. It is
**pure Python standard library** — there is nothing to install and no build step. The whole
tool is one file, `bench.py`. The user-facing docs in `README.md` are the source of truth for
end-user behavior; this file covers what you need to change the code or the bank.

## Commands

```bash
python3 bench.py                      # run the whole bank (default subcommand is `run`)
python3 bench.py --filter code        # only questions whose id contains, or category equals, "code"
python3 bench.py --model my-model     # force a model id instead of auto-detecting
python3 bench.py list                 # list discovered questions + their verify script
python3 bench.py models               # show models the configured server reports
```

`bench.py` exits 0 only if every run question passed, 1 if any failed (so it doubles as a CI
check). Running anything requires a live OpenAI-compatible server at `base_url` in `config.json`
with a model loaded — there is no mock/offline mode.

Test a single verify script in isolation, no model or server needed (the model's answer is the
verify script's stdin):

```bash
printf 'Paris\n' | bash questions/0001-capital/verify.sh ; echo $?   # 0 = pass
```

There is no test suite, linter, or formatter configured in this repo.

## Architecture

One pipeline in `bench.py`, run per question by `cmd_run`:

1. `load_config()` merges `config.json` over `DEFAULT_CONFIG` (defaults live in code, not the
   JSON file — keep the two in sync when adding a config key).
2. `detect_model()` picks `--model` / config `model`, else auto-picks the first model the
   server lists. **Caveat that drives real behavior:** LM Studio reports the *loaded* model
   (auto-pick is right); Ollama reports *all installed* models (auto-pick is arbitrary).
3. `discover_questions()` scans `questions/*/`. A directory is a question **iff it contains
   `prompt.txt`**; `meta.json` is optional.
4. `ask()` POSTs to `/v1/chat/completions` with `stream: false` using stdlib `urllib` only.
5. `run_verify()` executes the question's verify script and turns its exit code into pass/fail.
6. `save_results()` writes a per-run JSON to `results/` (gitignored), named
   `{model}__{timestamp}.json`.

### The verify-script contract (the core extension point)

`find_verify()` resolves the verify command in this precedence order:
**a per-question verify script if one exists** (`verify.sh`, else `verify.py`) → **else
`category == "code"` → the shared `check_code.py`** → **else `None`, a
configuration error** (a non-code question with no verify script can't be checked). A verify
script is run **directly** (no interpreter prefix), so it must be executable (`chmod +x`)
with a proper shebang — `#!/usr/bin/env bash`, `#!/usr/bin/env python3`, etc.

**Code questions don't need their own verify script — the shared `check_code.py` at the repo
root checks them.** When a `"code"` question has no verify script of its own, `find_verify()`
auto-builds `python3 check_code.py <lang> expected_output.txt [input.txt]`. `<lang>` comes
from `meta.json` `"lang"` (default `"python"`; `"c"` and `"cpp"`/`"c++"` are the other
supported values). The script extracts a fenced code block from the model's answer, runs it
(compiling first for C/C++), and diffs its stdout against `expected_output.txt`. If the question dir has an
`input.txt`, its contents are fed to the program on stdin (the optional third arg); otherwise
the program gets no stdin. Add a language by extending the `LANGS` table in `check_code.py`.
(A code question may still ship its own verify script to override this — per the precedence
above, an existing script wins.)

When `run_verify()` runs it:
- **cwd = the question's own directory**, so support files (`expected.txt`,
  `expected_output.txt`, a `Dockerfile`) resolve relatively.
- the model's answer is passed **only on stdin** — not as an argument or file.
- env vars `MODELBENCH_MODEL`, `MODELBENCH_QID`, `MODELBENCH_QDIR` are exported.
- **exit 0 = pass**, non-zero = fail.
- optional partial credit: print `SCORE=<float 0..1>` to stdout (`parse_score()` reads the
  last such line; an explicit SCORE overrides the exit code's implied 1.0/0.0).
- stdout+stderr is captured and shown on failure, so verify scripts should print *why* they
  failed.

### `questions/` conventions

- **ID = directory name**, and the numeric prefix encodes the category by hundreds block:
  `0000s` knowledge, `0100s` code, `0200s` math, `0300s` reasoning, `0400s`
  instruction-following. `meta.json`'s `"category"` should match the block. Keep new
  questions in the right range and set `category` to match.
- Two reusable verify patterns already exist — copy rather than reinvent:
  - **string/regex match** (knowledge/math): see `questions/0001-capital/verify.sh`
    (normalize-then-compare against `expected.txt`).
  - **run generated code and diff stdout** (code): handled centrally by `check_code.py`. A
    code question needs no verify script — just `category: "code"`, the right `lang`, and an
    `expected_output.txt`.
- `meta.json` (all optional): `category`, `lang` (for `code` questions: `python`/`c`/`cpp`),
  `system`, `temperature`, `max_tokens`, `verify_timeout`. Per-question values override
  `config.json`.

### Adding or changing things

- **New question:** make `questions/NNNN-name/`, add `prompt.txt` and a `meta.json` with the
  matching `category`. For a `code` question, also add `expected_output.txt` and set `lang`
  — no verify script. For other categories, add a verify script that exits 0 on a correct
  answer (copy the closest existing pattern) plus any `expected*.txt`; make it executable
  (`chmod +x`) with a shebang, since it's run directly.
- `check_code.py` executes model output on the host. It uses temp files and tight
  `subprocess` timeouts; keep that, and prefer Docker (a `Dockerfile` in the question dir is
  in the verify cwd) when running untrusted output is a concern.
