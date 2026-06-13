# modelbench

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

> **Model auto-detection caveat:** with `model: null`, modelbench picks the first model the
> server reports. LM Studio reports the model it currently has *loaded*, so that's usually the
> one you want. Ollama reports *every installed* model, so the auto-pick is arbitrary — pass
> `--model` (or set it in `config.json`) to choose. Ollama also cold-loads a model on the first
> request, so the first question may be slow.

Example output:

```
modelbench — model: qwen2.5-7b-instruct
questions: 3

PASS  0001-capital
PASS  0100-fizzbuzz-python
FAIL  0200-add-numbers   (program output did not match expected.)

2/3 passed
failed: 0200-add-numbers
details: results/qwen2.5-7b-instruct__20260612-143000.json
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

### The verify-script contract

The harness sends the prompt, then runs the question's verify script (`verify.sh`, `verify.py`,
or an executable `verify`; auto-detected). The script decides everything — string match, regex,
or extract code and run it (inside Docker or not) and diff an expected-output file.

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
  "system": "You are a terse assistant.",
  "temperature": 0.0,
  "max_tokens": 1024,
  "verify_timeout": 30
}
```

## Adding a question

1. `mkdir questions/0300-my-question`
2. Write `prompt.txt`.
3. Write a `verify.sh` or `verify.py` that exits 0 on a correct answer. For programming
   questions, see `questions/0100-fizzbuzz-python/verify.py` — it reads the answer from stdin,
   extracts the ```python block, runs it, and diffs `expected_output.txt`. A verify script is
   free to run the code inside Docker (any `Dockerfile` in the question folder is in the cwd).

## Configuration

`config.json` holds defaults (endpoint, generation params, timeouts). Set `base_url` to point
at your server — `http://localhost:1234/v1` for LM Studio (the default), or
`http://localhost:11434/v1` for Ollama. `model: null` means auto-detect (see the caveat above).
Per-question overrides go in that question's `meta.json`.
