"""Coding exercises ("rewrite it yourself") in Python and C++, with automatic grading.

Exercises live in ``academy/exercise_bank/*.yaml``. Each one has a prompt, starter code, hints, a
reference solution and tests:

* **Python** tests are snippets with ``assert`` run against the learner's namespace.
* **C++** tests are statements using ``CHECK(name, cond)`` / ``CHECK_NEAR(name, a, b, tol)``
  placed inside ``main()`` after the learner's code.

Running learner code is powerful and therefore **off by default on servers**. It is enabled by
``QUANTFORGE_ALLOW_CODE_EXECUTION=1`` (``quantforge-app`` sets it on your own computer). When it
is off, the web app grades Python **inside the visitor's browser** (Pyodide) and offers C++
exercises as a ready-to-compile file.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

__all__ = ["Exercise", "TestResult", "load_exercises", "exercises_for", "execution_allowed",
           "run_exercise", "python_harness", "cpp_source", "cpp_compiler", "RESULT_MARK"]

EXERCISE_DIR = Path(__file__).parent / "exercise_bank"
RESULT_MARK = "__QF_RESULTS__"
LANG_LABEL = {"python": "Python", "cpp": "C++"}


@dataclass(frozen=True)
class Exercise:
    id: str
    chapter: int
    language: str
    title: str
    difficulty: int
    prompt: str
    starter: str
    solution: str
    hints: tuple[str, ...]
    tests: object = field(repr=False)          # list[{name, code}] (Python) or str (C++)

    @property
    def label(self) -> str:
        return f"{LANG_LABEL[self.language]} · {self.title}"


@dataclass(frozen=True)
class TestResult:
    name: str
    ok: bool
    message: str = ""


@lru_cache(maxsize=1)
def load_exercises() -> tuple[Exercise, ...]:
    out: list[Exercise] = []
    for path in sorted(EXERCISE_DIR.glob("*.yaml")):
        for e in yaml.safe_load(path.read_text(encoding="utf-8")):
            if e["language"] not in LANG_LABEL:
                raise ValueError(f"{path.name}: unknown language {e['language']!r}")
            out.append(Exercise(e["id"], int(e["chapter"]), e["language"], e["title"],
                                int(e.get("difficulty", 1)), e["prompt"].strip(),
                                e["starter"].rstrip() + "\n", e["solution"].rstrip() + "\n",
                                tuple(e.get("hints", [])), e["tests"]))
    ids = [e.id for e in out]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate exercise ids")
    return tuple(out)


def exercises_for(chapter: int) -> list[Exercise]:
    return [e for e in load_exercises() if e.chapter == chapter]


def execution_allowed() -> bool:
    return os.environ.get("QUANTFORGE_ALLOW_CODE_EXECUTION", "") == "1"


def cpp_compiler() -> str | None:
    for c in (os.environ.get("CXX"), "c++", "clang++", "g++"):
        if c and shutil.which(c):
            return c
    return None


# ------------------------------------------------------------------ Python
_HARNESS = r'''
import json, linecache, traceback
CODE = {code}
TESTS = {tests}
FILE = "learner.py"
linecache.cache[FILE] = (len(CODE), None, CODE.splitlines(True), FILE)
ns = {{"__name__": "learner"}}
results = []
try:
    exec(compile(CODE, FILE, "exec"), ns)
except Exception:
    results.append({{"name": "your code runs", "ok": False,
                    "message": traceback.format_exc(limit=2).strip().splitlines()[-1]}})
else:
    for name, src in TESTS:
        try:
            exec(compile(src, "test", "exec"), dict(ns))
            results.append({{"name": name, "ok": True, "message": ""}})
        except AssertionError as e:
            results.append({{"name": name, "ok": False, "message": str(e) or "assertion failed"}})
        except Exception as e:
            results.append({{"name": name, "ok": False, "message": type(e).__name__ + ": " + str(e)}})
print("{mark}" + json.dumps(results))
'''


def python_harness(ex: Exercise, code: str | None = None) -> str:
    """Self-contained Python program that runs the tests and prints the results as JSON.

    The same program runs on the server or in the browser (Pyodide). With ``code=None`` the
    learner's code is read from a global variable ``LEARNER_CODE`` set by the caller."""
    tests = [(t["name"], t["code"]) for t in ex.tests]
    return _HARNESS.format(code="LEARNER_CODE" if code is None else repr(code),
                           tests=repr(tests), mark=RESULT_MARK)


# ------------------------------------------------------------------ C++
_CPP_PRELUDE = r'''// quantforge Academy exercise — compile with:  c++ -std=c++17 -O2 exercise.cpp -o exercise
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <numeric>
#include <random>
#include <string>
#include <vector>

static int qf_failures = 0;
#define CHECK(name, cond) do { if (cond) std::printf("QF|PASS|%s\n", name); \
    else { std::printf("QF|FAIL|%s|condition is false\n", name); ++qf_failures; } } while (0)
#define CHECK_NEAR(name, a, b, tol) do { const double qa = (a), qb = (b); \
    if (std::fabs(qa - qb) <= (tol)) std::printf("QF|PASS|%s\n", name); \
    else { std::printf("QF|FAIL|%s|got %.12g, expected %.12g\n", name, qa, qb); ++qf_failures; } } while (0)

// ======================= your code =======================
'''


def cpp_source(ex: Exercise, code: str) -> str:
    """Complete C++ program: prelude + learner code + tests in ``main``."""
    body = "\n".join("    " + line for line in str(ex.tests).rstrip().splitlines())
    return (_CPP_PRELUDE + code.rstrip() + "\n// =========================================================\n\n"
            "int main() {\n" + body + "\n    return qf_failures ? 1 : 0;\n}\n")


def _parse_cpp(stdout: str) -> list[TestResult]:
    out = []
    for line in stdout.splitlines():
        if line.startswith("QF|"):
            parts = line.split("|", 3)
            out.append(TestResult(parts[2], parts[1] == "PASS", parts[3] if len(parts) > 3 else ""))
    return out


def _limits() -> None:          # POSIX only: cap CPU time and file size of learner programs
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
        resource.setrlimit(resource.RLIMIT_FSIZE, (10_000_000, 10_000_000))
    except (ImportError, ValueError, OSError):
        pass


def run_exercise(ex: Exercise, code: str, timeout: float = 30.0,
                 force: bool = False) -> list[TestResult]:
    """Grade ``code`` on this machine. Requires :func:`execution_allowed` (or ``force``)."""
    if not (force or execution_allowed()):
        raise PermissionError("code execution is disabled on this server")
    pre = _limits if os.name == "posix" else None
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "SYSTEMROOT",
                                                        "TMPDIR", "TEMP", "TMP", "USERPROFILE")}
    env["PYTHONUTF8"] = "1"            # same text encoding on Windows as on macOS/Linux
    env["PYTHONIOENCODING"] = "utf-8"
    with tempfile.TemporaryDirectory(prefix="qf_ex_") as tmp:
        if ex.language == "python":
            prog = Path(tmp) / "run.py"
            prog.write_text(python_harness(ex, code), encoding="utf-8")
            try:
                p = subprocess.run([sys.executable, "-I", str(prog)], cwd=tmp, env=env,
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=timeout, preexec_fn=pre)
            except subprocess.TimeoutExpired:
                return [TestResult("time limit", False, f"your code ran longer than {timeout:.0f} s")]
            for line in p.stdout.splitlines():
                if line.startswith(RESULT_MARK):
                    return [TestResult(**r) for r in json.loads(line[len(RESULT_MARK):])]
            return [TestResult("your code runs", False, (p.stderr or p.stdout).strip()[-800:])]

        cxx = cpp_compiler()
        if cxx is None:
            return [TestResult("compiler", False, "no C++ compiler found (macOS: "
                                                  "`xcode-select --install`)")]
        src = Path(tmp) / "exercise.cpp"
        exe = Path(tmp) / ("exercise.exe" if os.name == "nt" else "exercise")
        src.write_text(cpp_source(ex, code), encoding="utf-8")
        try:
            c = subprocess.run([cxx, "-std=c++17", "-O2", str(src), "-o", str(exe)], cwd=tmp,
                               env=env, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=120)
        except subprocess.TimeoutExpired:
            return [TestResult("it compiles", False, "the compiler timed out")]
        if c.returncode != 0:
            err = c.stderr.replace(str(src), "exercise.cpp")
            return [TestResult("it compiles", False, err.strip()[-1500:])]
        try:
            r = subprocess.run([str(exe)], cwd=tmp, env=env, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout,
                               preexec_fn=pre)
        except subprocess.TimeoutExpired:
            return [TestResult("time limit", False, f"your program ran longer than {timeout:.0f} s")]
        res = _parse_cpp(r.stdout)
        if not res:
            return [TestResult("it runs", False, (r.stderr or "the program crashed").strip()[-800:])]
        return [TestResult("it compiles", True)] + res
