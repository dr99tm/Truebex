"""Long-poll wake-ups for pulls (5.7).

A waiting pull registers an event for its project *before* it reads, then
sleeps on it; a push (or a restore) calls `notify(project_id)` after its
commit. `notify` is safe from any thread: the pull side records the event
loop it waits on, and wake-ups from worker threads go through
`call_soon_threadsafe`. Pushes on another API process are caught by the
pull's 1 s re-check (PF14 runs one process until the presence table and a
broker take over).
"""

import asyncio
import threading
from collections import defaultdict

from ..contract_http import ContractError

RECHECK_S = 1.0

_lock = threading.Lock()
_events: dict[str, set[tuple[asyncio.AbstractEventLoop, asyncio.Event]]] = defaultdict(set)
_waiting: dict[int, int] = defaultdict(int)


class Waiter:
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self.loop = asyncio.get_running_loop()
        self.event = asyncio.Event()
        self._entry = (self.loop, self.event)
        with _lock:
            _events[project_id].add(self._entry)

    async def wait(self, timeout: float) -> bool:
        """True when woken by a push, False after `timeout` seconds."""
        try:
            await asyncio.wait_for(self.event.wait(), timeout=max(0.0, timeout))
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            self.event.clear()

    def close(self) -> None:
        with _lock:
            entries = _events.get(self.project_id)
            if entries is not None:
                entries.discard(self._entry)
                if not entries:
                    _events.pop(self.project_id, None)


def notify(project_id: str) -> None:
    with _lock:
        entries = list(_events.get(project_id, ()))
    for loop, event in entries:
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            event.set()
        elif not loop.is_closed():
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:  # the loop closed in between
                pass


def waiting_count(project_id: str) -> int:
    with _lock:
        return len(_events.get(project_id, ()))


class AccountSlot:
    """At most `cap` waiting pulls per account (contract §8 keeps one per open project)."""

    def __init__(self, user_id: int, cap: int) -> None:
        with _lock:
            if _waiting[user_id] >= cap:
                raise ContractError(
                    "rate_limited",
                    429,
                    f"At most {cap} pulls may wait at once on one account.",
                    {"limit": cap},
                    retry_after_s=5,
                )
            _waiting[user_id] += 1
        self.user_id = user_id

    def release(self) -> None:
        with _lock:
            _waiting[self.user_id] = max(0, _waiting[self.user_id] - 1)
            if not _waiting[self.user_id]:
                _waiting.pop(self.user_id, None)


def reset() -> None:
    with _lock:
        _events.clear()
        _waiting.clear()
