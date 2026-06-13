#!/usr/bin/env python3
#
# Copyright (c) 2026 Faraz Fallahi <fffaraz@gmail.com>
#
"""ModelBench — ask every question in the bank to a local model and report pass/fail.

Talks to any OpenAI-compatible server (LM Studio, Ollama, …). Single model:
picks --model / config, or auto-detects one the server reports, sends each
question's prompt, then runs that question's verify script to decide pass/fail.

Point it at your server with "base_url" in config.json (default is LM Studio's
http://localhost:1234/v1; use http://localhost:11434/v1 for Ollama).

Usage:
    python3 bench.py                       # run the whole question bank
    python3 bench.py --filter code         # only questions whose id contains, or category equals, "code"
    python3 bench.py --model my-model      # force a model id instead of auto-detecting
    python3 bench.py list                  # list discovered questions
    python3 bench.py models                # show the model(s) the server reports

Exit code: 0 if every question passed, 1 if any failed (handy for CI).
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUESTIONS_DIR = ROOT / "questions"
RESULTS_DIR = ROOT / "results"

DEFAULT_CONFIG = {
    "base_url": "http://localhost:1234/v1",  # LM Studio; use :11434/v1 for Ollama
    "model": None,            # None -> auto-detect a model the server reports
    "temperature": 0.0,       # 0 -> greedy decoding (deterministic); >0 samples
    "seed": 0,                # fixed seed -> reproducible output when temperature > 0
    "max_tokens": 2048,       # max tokens to ask for in the model's answer (adjust as needed for longer/shorter answers)
    "request_timeout": 120,   # seconds to wait for the model's answer (Ollama cold-loads on first call)
    "verify_timeout": 60,     # default seconds a verify script may run
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    p = ROOT / "config.json"
    if p.exists():
        try:
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            sys.exit(f"error: invalid JSON in {p}: {e.msg} (line {e.lineno}, column {e.colno})")
    return cfg


# ---------------------------------------------------------------- model server client

def _get(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _post(url, payload, timeout):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def base(cfg):
    return cfg["base_url"].rstrip("/")


def list_models(cfg):
    try:
        data = _get(base(cfg) + "/models", timeout=10)
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        sys.exit(f"error: cannot reach a model server at {cfg['base_url']} ({reason}). "
                 f"Is the local server running (LM Studio, or `ollama serve`)?")
    return [m["id"] for m in data.get("data", [])]


def detect_model(cfg):
    if cfg.get("model"):
        return cfg["model"]
    models = list_models(cfg)
    if not models:
        sys.exit(f"error: the server at {cfg['base_url']} reports no models. "
                 f"Load a model in LM Studio, or `ollama pull <model>`, then retry.")
    if len(models) > 1:
        # Note: LM Studio reports loaded models; Ollama reports all installed ones,
        # so the auto-pick here is somewhat arbitrary — pass --model to be explicit.
        print(f"note: {len(models)} models available; using '{models[0]}' "
              f"(pass --model to pick another)", file=sys.stderr)
    return models[0]


def ask(cfg, model, prompt, system=None, temperature=None, max_tokens=None):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": cfg["temperature"] if temperature is None else temperature,
        "max_tokens": cfg["max_tokens"] if max_tokens is None else max_tokens,
        "seed": cfg["seed"],
        "stream": False,
    }
    t0 = time.time()
    resp = _post(base(cfg) + "/chat/completions", payload, timeout=cfg["request_timeout"])
    latency = time.time() - t0
    content = resp["choices"][0]["message"].get("content") or ""
    return content, latency


# ---------------------------------------------------------------- questions

def discover_questions():
    if not QUESTIONS_DIR.is_dir():
        sys.exit(f"error: no questions directory at {QUESTIONS_DIR}")
    out = []
    for d in sorted(QUESTIONS_DIR.iterdir()):
        if not d.is_dir():
            continue
        prompt_file = d / "prompt.txt"
        if not prompt_file.exists():
            continue
        meta = {}
        mp = d / "meta.json"
        if mp.exists():
            try:
                meta = json.loads(mp.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                sys.exit(f"error: invalid JSON in {mp}: {e.msg} (line {e.lineno}, column {e.colno})")
        out.append({
            "id": d.name,
            "dir": d,
            "prompt": prompt_file.read_text(encoding="utf-8"),
            "meta": meta,
            "verify": find_verify(d, meta),
        })
    return out


def find_verify(d, meta):
    """Locate the question's verify command. Returns {'cmd', 'shell', 'label'} or None."""
    if meta.get("verify"):
        return {"cmd": meta["verify"], "shell": True, "label": str(meta["verify"])}
    for name, prefix in (("verify.sh", ["bash"]), ("verify.py", [sys.executable]), ("verify", [])):
        p = d / name
        if p.exists():
            return {"cmd": prefix + [str(p)], "shell": False, "label": name}
    return None


def run_verify(q, model, answer, timeout):
    """Run the question's verify script. Contract:
       - cwd = question dir
       - the model's answer is piped to the script on STDIN
       - metadata env: MODELBENCH_MODEL / MODELBENCH_QID / MODELBENCH_QDIR
       - exit 0 = pass; optional 'SCORE=<float>' line on stdout for partial credit
    """
    v = q["verify"]
    if v is None:
        return {"passed": False, "exit": None, "score": 0.0, "output": "no verify script found"}
    env = dict(
        os.environ,
        MODELBENCH_MODEL=model,
        MODELBENCH_QID=q["id"],
        MODELBENCH_QDIR=str(q["dir"]),
    )
    try:
        proc = subprocess.run(
            v["cmd"], shell=v["shell"], cwd=str(q["dir"]), input=answer,
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return {
            "passed": proc.returncode == 0,
            "exit": proc.returncode,
            "score": parse_score(proc.stdout, proc.returncode),
            "output": (proc.stdout + proc.stderr).strip(),
        }
    except subprocess.TimeoutExpired:
        return {"passed": False, "exit": None, "score": 0.0,
                "output": f"verify script timed out after {timeout}s"}


def parse_score(stdout, returncode):
    score = None
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("SCORE="):
            try:
                score = float(line[len("SCORE="):])
            except ValueError:
                pass
    if score is not None:
        return max(0.0, min(1.0, score))
    return 1.0 if returncode == 0 else 0.0


# ---------------------------------------------------------------- output helpers

def color(text, name):
    if not sys.stdout.isatty():
        return text
    codes = {"green": "32", "red": "31", "dim": "2", "bold": "1"}
    return f"\033[{codes[name]}m{text}\033[0m"


def short(text, n=70):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def save_results(model, results):
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in model)
    path = RESULTS_DIR / f"{safe}__{stamp}.json"
    path.write_text(json.dumps({"model": model, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------- commands

def cmd_run(args):
    cfg = load_config()
    if args.model:
        cfg["model"] = args.model
    model = detect_model(cfg)
    questions = discover_questions()
    if args.filter:
        f = args.filter
        questions = [q for q in questions
                     if f in q["id"] or f == q["meta"].get("category")]
    if not questions:
        sys.exit("error: no questions matched.")

    print(f"ModelBench — model: {color(model, 'bold')}")
    print(f"questions: {len(questions)}\n")

    results = []
    total_start = time.time()
    for q in questions:
        meta = q["meta"]
        q_start = time.time()
        try:
            answer, latency = ask(
                cfg, model, q["prompt"],
                system=meta.get("system"),
                temperature=meta.get("temperature"),
                max_tokens=meta.get("max_tokens"),
            )
            res = run_verify(q, model, answer, meta.get("verify_timeout", cfg["verify_timeout"]))
        except Exception as e:  # network / API / malformed response
            answer, latency = "", 0.0
            res = {"passed": False, "exit": None, "score": 0.0, "output": f"model error: {e}"}
        elapsed = time.time() - q_start

        results.append({"id": q["id"], "latency": round(latency, 2),
                        "elapsed": round(elapsed, 2), "answer": answer, **res})
        mark = color("PASS", "green") if res["passed"] else color("FAIL", "red")
        line = f"{mark}  {q['id']}" + color(f"  ({elapsed:.2f}s)", "dim")
        if not res["passed"] and res["output"]:
            line += color(f"   ({short(res['output'])})", "dim")
        print(line)
    total_elapsed = time.time() - total_start

    failed = [r["id"] for r in results if not r["passed"]]
    npass = len(results) - len(failed)
    print()
    summary = f"{npass}/{len(results)} passed"
    print(color(summary, "green" if not failed else "red"))
    print(color(f"total time: {total_elapsed:.2f}s", "dim"))
    if failed:
        print("failed: " + ", ".join(failed))
    path = save_results(model, results)
    print(color(f"details: {path.relative_to(ROOT)}", "dim"))
    sys.exit(0 if not failed else 1)


def cmd_list(args):
    for q in discover_questions():
        cat = q["meta"].get("category", "general")
        verify = q["verify"]["label"] if q["verify"] else color("(no verify script!)", "red")
        print(f"{q['id']:32}  [{cat}]  {verify}")


def cmd_models(args):
    cfg = load_config()
    models = list_models(cfg)
    if not models:
        print("no models available")
    for m in models:
        print(m)


def main():
    p = argparse.ArgumentParser(
        description="Benchmark a local OpenAI-compatible model (LM Studio, Ollama, …) against the question bank.")
    sub = p.add_subparsers(dest="cmd")

    runp = sub.add_parser("run", help="run the question bank (default)")
    runp.add_argument("--model", help="force a model id instead of auto-detecting")
    runp.add_argument("--filter", help="only questions whose id contains, or category equals, this")
    runp.set_defaults(func=cmd_run)

    sub.add_parser("list", help="list discovered questions").set_defaults(func=cmd_list)
    sub.add_parser("models", help="show the model(s) the server reports").set_defaults(func=cmd_models)

    # Default to the `run` subcommand when none is named, so bare flags like
    # `--filter code` or `--model x` work without typing `run` first.
    argv = sys.argv[1:]
    if not (argv and (argv[0] in sub.choices or argv[0] in ("-h", "--help"))):
        argv = ["run"] + argv
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        sys.exit(130)
