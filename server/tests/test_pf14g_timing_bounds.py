"""PF14g: a long poll's time bound runs from the change that wakes the read, and
a stale webhook signature is stale whatever the clock does meanwhile.

A LongPoll's `took` runs from the reader thread's start, so it also counts the
test's own calls made while the read waits (the push, the claim, the tile
uploads). Under a busy PC those writes alone passed the bound (T100's gate:
13.67 s against 12.5 s for a read the tiles job did wake). `wakeups.assert_woken`
proves that a notify ended every wait; the bound is taken from just before the
call that sends the notify (`reader.since(t)`). `took` stays for lower bounds,
which load only makes easier to meet.

A Paddle signature `int(time.time()) + 301` lost up to 0.999 s to `int()` and
fell inside the 300 s window once the request took about 0.1 s (PF12b's gate,
PF6c's Postgres run): the stale cases now sit a minute outside the window, and
the exact boundary is a unit test with an explicit clock
(test_billing_pf2.py::test_billing_paddle_signature_window_edge)."""

import ast
import time
from pathlib import Path

from app.billing import paddle_provider

from .conftest import LongPoll

TESTS = Path(__file__).resolve().parent


def _sources() -> list[tuple[str, ast.Module]]:
    return [(path.name, ast.parse(path.read_text("utf-8"), str(path))) for path in sorted(TESTS.glob("*.py"))]


def _is_took(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "took"


def _took_upper_bounds_in(tree: ast.AST) -> list[int]:
    """The lines of every comparison that bounds a `.took` from above
    (`x.took < n`, `x.took <= n`, `n > x.took`, `a <= x.took < n`)."""
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            for op, lhs, rhs in zip(node.ops, operands, operands[1:]):
                if (_is_took(lhs) and isinstance(op, (ast.Lt, ast.LtE))) or (_is_took(rhs) and isinstance(op, (ast.Gt, ast.GtE))):
                    lines.add(node.lineno)
    return sorted(lines)


def _near_window(expr: ast.AST) -> list[float]:
    """The literal offsets in `expr` added to or taken from something, within 5 s
    of the signature window (`int(time.time()) + 301`)."""
    near = []
    for node in ast.walk(expr):
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            for side in (node.left, node.right):
                if isinstance(side, ast.Constant) and isinstance(side.value, (int, float)) and not isinstance(side.value, bool):
                    if abs(abs(side.value) - paddle_provider.SIGNATURE_TOLERANCE_S) <= 5:
                        near.append(side.value)
    return near


def _signed_near_the_window_in(tree: ast.AST) -> list[int]:
    """The lines of a Paddle webhook signed (`paddle_post(..., ts=...)`,
    `sign(secret, body, ts)`) with a literal offset within 5 s of the window."""
    lines = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if func not in ("paddle_post", "sign"):
            continue
        stamps = [kw.value for kw in node.keywords if kw.arg == "ts"]
        if func == "sign" and len(node.args) >= 3:
            stamps.append(node.args[2])
        if any(_near_window(stamp) for stamp in stamps):
            lines.add(node.lineno)
    return sorted(lines)


def _everywhere(find) -> list[str]:
    return [f"{name}:{line}" for name, tree in _sources() for line in find(tree)]


# --- the guards ---------------------------------------------------------------------------------


def test_no_upper_bound_on_a_long_polls_whole_time():
    found = _everywhere(_took_upper_bounds_in)
    assert found == [], (
        "a LongPoll's took runs from the reader's start and counts the test's own calls while the read waits; "
        f"bound the time from the change instead (t = time.monotonic() before it, reader.since(t)): {found}"
    )


def test_guard_sees_every_form_of_an_upper_bound():
    tree = ast.parse("\n".join(["assert r.took < 1", "assert r.took <= 1", "assert 1 > r.took", "assert 0 <= r.took < 1", "assert r.took >= 1"]))
    assert _took_upper_bounds_in(tree) == [1, 2, 3, 4]  # the lower bound (line 5) stays allowed


def test_no_webhook_signed_at_the_edge_of_the_window():
    found = _everywhere(_signed_near_the_window_in)
    assert found == [], (
        f"a signature {paddle_provider.SIGNATURE_TOLERANCE_S} +/- 5 s off the clock is a coin toss once int() and the "
        f"request's own time are counted; sign it far outside the window (SIGNATURE_TOLERANCE_S + 60): {found}"
    )
    edge = ast.parse("\n".join(["paddle_post(c, e, ts=int(time.time()) + 301)", "sign(s, b, int(time.time()) - 298)", "sign(s, b, ts=now + 360)"]))
    assert _signed_near_the_window_in(edge) == [1, 2]


# --- LongPoll.since ---------------------------------------------------------------------------------


def test_long_poll_since_measures_from_the_given_time():
    marks = {}

    def call():
        # Wait by the clock since() reads (time.sleep can end a 15.6 ms tick early by it on Windows).
        marks["start"] = time.monotonic()
        while time.monotonic() - marks["start"] < 0.2:
            time.sleep(0.01)
        marks["end"] = time.monotonic()
        return "done"

    before = time.monotonic()
    poll = LongPoll(call)
    assert poll.answer() == "done"
    assert poll.since(before) >= 0.2
    assert poll.took >= 0.2 and poll.since(before) - poll.took >= 0  # took counts from the thread's start, after `before`
    assert 0 <= poll.since(marks["end"]) < 5  # only the return remains: small, with room for a busy PC
    assert poll.since(time.monotonic()) <= 0  # answered before now
