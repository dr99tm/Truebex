"""The push hook: features that react to accepted operations subscribe here.

    from app.projects.hooks import on_ops_accepted

    @on_ops_accepted
    def enqueue_tiles(project_id: str, ops: list[dict]) -> None: ...

PF6 subscribes for followed panorama sets (render-jobs §2). `ops` are the
operations a push (or a restore) just committed, in server order, as they
travel on the wire (§6.2 with `server_seq`). A hook runs after the commit, in
the request's worker thread; one that fails is logged and recorded and never
fails the push.
"""

import logging
from collections.abc import Callable

log = logging.getLogger("truebex.projects.hooks")

Hook = Callable[[str, list[dict]], object]
_HOOKS: list[Hook] = []


def on_ops_accepted(fn: Hook) -> Hook:
    """Subscribe `fn(project_id, ops)` (usable as a decorator)."""
    if fn not in _HOOKS:
        _HOOKS.append(fn)
    return fn


def unsubscribe(fn: Hook) -> None:
    if fn in _HOOKS:
        _HOOKS.remove(fn)


def emit(project_id: str, ops: list[dict]) -> None:
    if not ops:
        return
    for fn in list(_HOOKS):
        try:
            fn(project_id, list(ops))
        except Exception as exc:  # noqa: BLE001 - a subscriber never fails a push
            log.exception("push hook %s failed", getattr(fn, "__name__", fn))
            try:
                from ..telemetry.service import record_server_exception

                record_server_exception(exc, route="hook:projects.on_ops_accepted")
            except Exception:  # noqa: BLE001
                pass
