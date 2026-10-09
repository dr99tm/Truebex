"""UUIDv7 ids as 32 lowercase hex (contract §5: "Ids are 32 lowercase hex").

Python 3.12's uuid module has no version 7, so it is built here (RFC 9562
§5.7): 48-bit Unix milliseconds, version 7, the variant bits, random rest.
Within one millisecond the random tail is incremented, so ids made by this
process sort in creation order.
"""

import re
import secrets
import threading
import time

_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_lock = threading.Lock()
_last_ms = -1
_last_tail = 0  # the 74 random bits after the timestamp (rand_a + rand_b)
_TAIL_BITS = 74


def uuid7_hex(now_ms: int | None = None) -> str:
    global _last_ms, _last_tail
    ms = int(time.time() * 1000) if now_ms is None else now_ms
    with _lock:
        if ms <= _last_ms:
            # Same (or an earlier) millisecond: keep order by counting up.
            ms = _last_ms
            tail = (_last_tail + 1) & ((1 << _TAIL_BITS) - 1)
        else:
            tail = secrets.randbits(_TAIL_BITS)
        _last_ms, _last_tail = ms, tail
    rand_a = tail >> 62  # 12 bits
    rand_b = tail & ((1 << 62) - 1)  # 62 bits
    value = (ms & ((1 << 48) - 1)) << 80 | 0x7 << 76 | rand_a << 64 | 0b10 << 62 | rand_b
    return f"{value:032x}"


def is_id(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX32.match(value))
