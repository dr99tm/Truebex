"""Run pytest on one CPU core shared with a busy loop (PF14e).

The long-poll wake-up tests must pass on a starved CPU and still fail when the
wake-up is missing. This runner pins itself to one core, starts one CPU burner
there (a busy loop, which the pytest process inherits the core of), runs
pytest on the same core and stops the burner. Every other core is left alone,
so other sessions' gates on this PC are not slowed.

    .venv\\Scripts\\python.exe scripts\\starved_pytest.py              # the PF14e tests, once
    .venv\\Scripts\\python.exe scripts\\starved_pytest.py --runs 20    # each 20 times in a row
    .venv\\Scripts\\python.exe scripts\\starved_pytest.py --no-wakeup  # waiters.notify a no-op

`--no-wakeup` makes `app.projects.waiters.notify` do nothing for the run (the
push's and the job change's wake-up), so each wake-up test must fail with "the
read was not woken". Extra arguments go to pytest (test ids replace the
default list). The module is also the pytest plugin that repeats the tests and
switches the wake-up off (`-p scripts.starved_pytest`, driven by environment
variables), so it imports nothing from the app at import time.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[1]
RUNS_ENV = "STARVED_PYTEST_RUNS"
NO_WAKEUP_ENV = "STARVED_PYTEST_NO_WAKEUP"
# The burner is a plain busy loop with a ceiling, so a runner killed without
# its cleanup still frees the core within the hour.
BURNER = "import time\nend = time.monotonic() + 3600\nwhile time.monotonic() < end:\n    pass\n"

PF14E_TESTS = [
    "tests/test_render.py::test_jobs_status_long_poll_rev",
    "tests/test_render.py::test_share_live_follows_the_set",
    "tests/test_render_shares.py::test_published_share_follows_the_set",
    "tests/test_pf9_pf12_meet.py::test_key_reads_a_followed_set_after_its_own_edit",
    "tests/test_projects.py::test_pull_long_poll_wakes_on_push",
    "tests/test_pf12a_v1_panoramas.py::test_v1_panorama_set_long_poll",
    "tests/test_pf14e_long_poll.py",
]


# --- the pytest plugin ------------------------------------------------------------------------


def pytest_collection_modifyitems(session, config, items):
    runs = int(os.environ.get(RUNS_ENV) or 1)
    if runs > 1:
        items[:] = [item for _ in range(runs) for item in items]


@pytest.fixture(autouse=True)
def _starved_no_wakeup(monkeypatch):
    if os.environ.get(NO_WAKEUP_ENV) == "1":
        from app.projects import waiters

        monkeypatch.setattr(waiters, "notify", lambda key: None)
    yield


_RESULTS: dict[str, list[tuple[str, float]]] = defaultdict(list)


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        _RESULTS[report.nodeid].append((report.outcome, report.duration))


def pytest_terminal_summary(terminalreporter):
    if not _RESULTS or len(_RESULTS) > 40:  # a whole-suite run has pytest's own summary
        return
    tr = terminalreporter
    tr.section("starved runs per test")
    for nodeid, results in _RESULTS.items():
        passed = sum(1 for outcome, _ in results if outcome == "passed")
        slowest = max(d for _, d in results)
        tr.write_line(f"{passed}/{len(results)} passed, slowest call {slowest:.2f} s  {nodeid}")


# --- the runner --------------------------------------------------------------------------------


def pin(core: int) -> None:
    """This process (and every child it starts from now on) runs on `core` only."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.SetProcessAffinityMask.argtypes = (wintypes.HANDLE, ctypes.c_size_t)
        k32.SetProcessAffinityMask.restype = wintypes.BOOL
        if not k32.SetProcessAffinityMask(k32.GetCurrentProcess(), 1 << core):
            raise OSError(ctypes.get_last_error(), f"could not pin to core {core}")
    else:
        os.sched_setaffinity(0, {core})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--core", type=int, default=(os.cpu_count() or 1) - 1, help="the core to run on (default: the last)")
    parser.add_argument("--runs", type=int, default=1, help="run each test this many times in a row")
    parser.add_argument("--no-wakeup", action="store_true", help="waiters.notify does nothing (the wake-up tests must fail)")
    parser.add_argument("--no-burner", action="store_true", help="the core to itself (for comparison)")
    args, pytest_args = parser.parse_known_args(argv)
    if not 0 <= args.core < (os.cpu_count() or 1):
        parser.error(f"--core: 0 to {(os.cpu_count() or 1) - 1}")
    # Test ids given replace the default list; options (`-p no:warnings`, `-x`) are passed through.
    named = any("::" in a or a.endswith(".py") or (SERVER / a).is_dir() for a in pytest_args if not a.startswith("-"))
    pytest_args = pytest_args if named else [*pytest_args, *PF14E_TESTS]

    pin(args.core)
    env = dict(os.environ, **{RUNS_ENV: str(max(1, args.runs)), NO_WAKEUP_ENV: "1" if args.no_wakeup else "0"})
    # The base interpreter, not a venv launcher: killing it stops the loop itself.
    python = getattr(sys, "_base_executable", None) or sys.executable
    burner = None if args.no_burner else subprocess.Popen([python, "-c", BURNER])
    print(
        f"core {args.core} only, {'no burner' if burner is None else 'shared with a busy loop (pid %d)' % burner.pid}; "
        f"{args.runs} run(s); wake-up {'OFF (waiters.notify is a no-op)' if args.no_wakeup else 'on'}",
        flush=True,
    )
    started = time.monotonic()
    try:
        code = subprocess.call(
            [sys.executable, "-m", "pytest", "-q", "-p", "scripts.starved_pytest", *pytest_args],
            cwd=SERVER,
            env=env,
        )
    finally:
        if burner is not None:
            burner.kill()
            burner.wait()
    print(f"pytest exit {code} after {time.monotonic() - started:.0f} s on core {args.core}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
