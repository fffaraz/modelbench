#!/usr/bin/env python3
"""Shared verifier for coding questions: pull the code out of the model's answer (read on
stdin), run it, and compare its stdout to an expected-output file. exit 0 = pass, non-zero = fail.

Usage:
    python3 ../../check_code.py <lang> <expected_output_path> [input_path]

<lang> is "python" (aka "py") or "c". The expected-output path (and the optional input path)
are resolved relative to the verify cwd, which bench.py sets to the question's own directory
-- so "expected_output.txt" finds the file sitting next to prompt.txt. When [input_path] is
given, its contents are fed to the generated program on stdin; otherwise the program gets no
stdin.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

COMPILE_TIMEOUT = 30
RUN_TIMEOUT = 15


def extract_code(answer, fence):
    """Prefer a fenced code block matching the language; fall back to the whole answer."""
    m = re.search(r"```(?:" + fence + r")?\s*\n(.*?)```", answer, re.S | re.I)
    return m.group(1) if m else answer


def run_python(code, stdin_data):
    """Write the code to a temp file and run it, feeding stdin_data on stdin (None = no input).
    Returns a CompletedProcess."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        code_path = f.name
    try:
        return subprocess.run(
            [sys.executable, code_path], input=stdin_data,
            capture_output=True, text=True, timeout=RUN_TIMEOUT
        )
    finally:
        os.unlink(code_path)


def _run_compiled(code, stdin_data, compilers, src_name, label):
    """Compile the code with the first available compiler, then run the binary, feeding
    stdin_data on stdin (None = no input). Returns a CompletedProcess, or exits on a compile
    error / missing compiler (those are failures, not runnable programs). src_name's extension
    selects the compiler's language mode (e.g. prog.c -> C, prog.cpp -> C++)."""
    cc = next((shutil.which(c) for c in compilers if shutil.which(c)), None)
    if cc is None:
        print(f"no {label} compiler ({'/'.join(compilers)}) found on PATH", file=sys.stderr)
        sys.exit(1)

    tmp = tempfile.mkdtemp()
    src_path = os.path.join(tmp, src_name)
    bin_path = os.path.join(tmp, "prog")
    try:
        with open(src_path, "w") as f:
            f.write(code)
        build = subprocess.run(
            [cc, src_path, "-o", bin_path], capture_output=True, text=True, timeout=COMPILE_TIMEOUT
        )
        if build.returncode != 0:
            print("the generated program failed to compile:", build.returncode, file=sys.stderr)
            print(build.stderr, file=sys.stderr)
            sys.exit(1)
        return subprocess.run(
            [bin_path], input=stdin_data, capture_output=True, text=True, timeout=RUN_TIMEOUT
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_c(code, stdin_data):
    """Compile and run C code (prog.c, compiled in C mode by cc/gcc/clang)."""
    return _run_compiled(code, stdin_data, ("cc", "gcc", "clang"), "prog.c", "C")


def run_cpp(code, stdin_data):
    """Compile and run C++ code (prog.cpp, compiled in C++ mode by c++/g++/clang++)."""
    return _run_compiled(code, stdin_data, ("c++", "g++", "clang++"), "prog.cpp", "C++")


# lang -> (code-fence alternatives, runner)
LANGS = {
    "python": (r"python|py", run_python),
    "py": (r"python|py", run_python),
    "c": (r"c", run_c),
    "cpp": (r"cpp|c\+\+", run_cpp),
    "c++": (r"cpp|c\+\+", run_cpp),
}


def main():
    if not 3 <= len(sys.argv) <= 4:
        print(f"usage: {sys.argv[0]} <lang> <expected_output_path> [input_path]", file=sys.stderr)
        sys.exit(2)
    lang, expected_path = sys.argv[1].lower(), sys.argv[2]
    input_path = sys.argv[3] if len(sys.argv) == 4 else None
    if lang not in LANGS:
        print(f"unsupported lang {lang!r}; supported: {', '.join(sorted(LANGS))}", file=sys.stderr)
        sys.exit(2)

    stdin_data = None
    if input_path is not None:
        try:
            with open(input_path, encoding="utf-8") as f:
                stdin_data = f.read()
        except (OSError, UnicodeDecodeError) as e:
            print(f"error: cannot read input file {input_path}: {e}", file=sys.stderr)
            sys.exit(1)

    fence, runner = LANGS[lang]
    code = extract_code(sys.stdin.read(), fence)
    proc = runner(code, stdin_data)

    if proc.returncode != 0:
        print("the generated program exited non-zero:", proc.returncode, file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        sys.exit(1)

    try:
        with open(expected_path, encoding="utf-8") as f:
            expected = f.read().strip()
    except (OSError, UnicodeDecodeError) as e:
        print(f"error: cannot read expected output file {expected_path}: {e}", file=sys.stderr)
        sys.exit(1)

    got = proc.stdout.strip()
    if got == expected:
        sys.exit(0)

    print("program output did not match expected.", file=sys.stderr)
    print("--- expected ---\n" + expected, file=sys.stderr)
    print("--- got ---\n" + got, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
