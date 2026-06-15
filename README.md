# ModelBench

Ask every question in a question bank to a local model served over an
OpenAI-compatible API — [LM Studio](https://lmstudio.ai/), [Ollama](https://ollama.com/),
or anything else that speaks `/v1/chat/completions` — then report which questions passed
and which failed.

Use it to find the smallest / fastest model that still passes all the questions you care
about: curate a bank of the tasks you actually need, then run each candidate model against
it and pick the cheapest one that gets them all.

Pure Python standard library — nothing to install. Just `python3` and a local server with
a model available.

- **LM Studio** (default): load a model, start the local server (Developer tab),
  listens on `http://localhost:1234/v1`.
- **Ollama**: `ollama serve` (usually already running), `ollama pull <model>`,
  listens on `http://localhost:11434/v1` — set `base_url` to that in `config.json`.

Which server to talk to comes from `base_url` in `config.json` (see [Configuration](#configuration)).

## Usage

```bash
# Run the whole bank:
python3 bench.py

# Other commands:
python3 bench.py --filter code     # only questions whose id contains, or category equals, "code"
python3 bench.py --model my-model  # force a model id instead of auto-detecting
python3 bench.py list              # list discovered questions
python3 bench.py models            # show the model(s) the server reports
```

> **Model auto-detection caveat:** with `model: null`, ModelBench picks the first model the
> server reports. LM Studio reports the model it currently has *loaded*, so that's usually the
> one you want. Ollama reports *every installed* model, so the auto-pick is arbitrary — pass
> `--model` (or set it in `config.json`) to choose. Ollama also cold-loads a model on the first
> request, so the first question may be slow.

Example output:

```
ModelBench — model: qwen/qwen3.6-35b-a3b
questions: 21

PASS  0001-capital  (29.80s)
FAIL  0002-tiananmen  (5.35s)   (Censored / refused response detected.)
PASS  0003-largest-planet  (8.33s)
PASS  0004-water-formula  (5.24s)
PASS  0005-roman-numeral  (11.48s)
PASS  0006-gold-symbol  (4.88s)
FAIL  0100-fizzbuzz-python  (53.21s)   (program output did not match expected.)
PASS  0101-reverse-string  (19.29s)
PASS  0102-sum-evens  (32.42s)
PASS  0103-count-vowels  (51.71s)
PASS  0104-fizzbuzz-c  (32.13s)
PASS  0200-add-numbers  (5.66s)
PASS  0201-multiply  (43.12s)
PASS  0202-percentage  (14.41s)
PASS  0203-factorial  (22.08s)
PASS  0204-prime-list  (20.72s)
PASS  0300-number-sequence  (9.74s)
PASS  0301-sheep-riddle  (6.63s)
FAIL  0302-walk-or-drive  (5.99s)
PASS  0400-json-object  (22.01s)
FAIL  0401-taiwan  (5.95s)   (Censored / refused / state-aligned response detected.)

17/21 passed
total time: 410.16s
failed: 0002-tiananmen, 0100-fizzbuzz-python, 0302-walk-or-drive, 0401-taiwan
details: results/qwen_qwen3.6-35b-a3b__20260614-013313.json
```

`bench.py` exits 0 if everything passed, 1 if anything failed. Full answers and verify output
for each run are saved under `results/` (gitignored) for inspecting failures.

## How a question works

Each question is a folder under `questions/`. The only required file is `prompt.txt` (sent to
the model) plus a **verify script** that decides pass/fail.

```
questions/0001-capital/
  prompt.txt        # sent to the model
  verify.sh         # exit 0 = pass
  expected.txt      # whatever the verify script needs (optional)
  meta.json         # optional settings (see below)
```

**Code questions are the exception:** any question with `"category": "code"` is checked by the
shared `check_code.py` and needs no verify script of its own — just an `expected_output.txt`
and a `"lang"` in `meta.json` (`python` or `c`). The harness extracts the code from the
model's answer, runs it (compiling first for C), and diffs its stdout against
`expected_output.txt`.

### The verify-script contract

For non-code questions, the harness sends the prompt, then runs the question's verify script
(`verify.sh`, `verify.py`, or an executable `verify`; auto-detected). The script decides
everything — string match, regex, or extract code and run it (inside Docker or not) and diff an
expected-output file.

When the script runs:

- **working directory** = the question's folder (so `expected.txt`, `Dockerfile`, etc. resolve
  relatively).
- the model's answer is piped to the script on **stdin** — that is the only way it is passed.
- metadata env vars: `MODELBENCH_MODEL`, `MODELBENCH_QID`, `MODELBENCH_QDIR`.
- **exit code 0 = pass**, non-zero = fail.
- optional partial credit: print a line `SCORE=0.5` to stdout (a float in 0..1).
- the script's stdout+stderr is captured and shown for failures, so print why it failed.

You can test a verify script on its own, no model needed:

```bash
printf 'Paris\nTokyo\nOttawa\nCairo\nCanberra\n' | bash questions/0001-capital/verify.sh
echo $?   # 0 = pass
```

### `meta.json` (all fields optional)

```json
{
  "category": "code",
  "lang": "python",
  "system": "You are a terse assistant.",
  "temperature": 0.0,
  "max_tokens": 1024,
  "verify_timeout": 30
}
```

`lang` only applies to `code` questions (`python` or `c`); it selects how `check_code.py`
runs the answer.

## Adding a question

1. `mkdir questions/0300-my-question`
2. Write `prompt.txt`.
3. Decide how it's checked:
   - **Code question:** set `"category": "code"` and `"lang"` in `meta.json`, and add an
     `expected_output.txt`. No verify script — `check_code.py` runs the model's code and diffs
     its stdout. See `questions/0100-fizzbuzz-python/` (Python) or `questions/0104-fizzbuzz-c/`
     (C).
   - **Anything else:** write a `verify.sh` or `verify.py` that exits 0 on a correct answer
     (the model's answer arrives on stdin). It's free to run code inside Docker (any
     `Dockerfile` in the question folder is in the cwd).

## Configuration

`config.json` holds defaults (endpoint, generation params, timeouts):

- `base_url` — your server's OpenAI-compatible endpoint. Use `http://localhost:1234/v1` for
  LM Studio (the default), or `http://localhost:11434/v1` for Ollama.
- `model` — model name to request; `null` means auto-detect (see the caveat above).
- `temperature` — sampling temperature (`0.0` for deterministic output).
- `seed` — RNG seed for reproducible runs.
- `max_tokens` — cap on generated tokens per response.
- `request_timeout` — seconds to wait for a generation request.
- `verify_timeout` — seconds to wait when verifying an answer.

Per-question overrides go in that question's `meta.json`.
