"""Write PF11's own ai-proxy stand-ins into server/tests/fixtures/ai/.

    py -3.12 scripts\\make_ai_proxy_fixtures.py            # write
    py -3.12 scripts\\make_ai_proxy_fixtures.py --check    # compare, write nothing

Deterministic, standard library only. The contract's set is the app's own
(AI3, `Docs/roadmap/fixtures/contracts/ai-proxy/` in the app repo), copied
byte for byte into server/tests/contracts/ai-proxy/ by
scripts/sync-contract-fixtures.ps1; this script never writes there (PF11b).

What stays the platform's own: the "window on the north wall of the study,
1.2 m wide" example as three streamed turns (find, place, end_turn) whose
usage carries cache read and write tokens, with the proxy's whole stream in
each file: every `truebex_credits` event follows from the turn's usage at the
5.1 rates and the studio balance (4388 credits left), served_by included, so
a test can compare the proxy's stream with the file byte for byte. The
platform's fake provider serves them without their `truebex_credits` events,
which the proxy adds itself.
"""

import argparse
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ai"

MODEL = "claude-opus-5-5"
RATES = {"input": 4000, "output": 20000, "cache_read": 400, "cache_write": 5000}
START_BALANCE = 4388
WALL = "0199c6a2e00070018000000000000001"  # the project-log fixtures' first wall


def compact(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def event(name: str, payload: dict) -> str:
    return f"event: {name}\ndata: {compact(payload)}\n\n"


def charge(usage: dict) -> int:
    total = (
        usage["input_tokens"] * RATES["input"]
        + usage["output_tokens"] * RATES["output"]
        + usage["cache_read_input_tokens"] * RATES["cache_read"]
        + usage["cache_creation_input_tokens"] * RATES["cache_write"]
    )
    return -(-total // 1_000_000)


def turn(message_id: str, start_usage: dict, blocks: list[tuple[str, dict, list[dict]]], stop: str, output_tokens: int, balance: int) -> tuple[str, int]:
    out = [
        event(
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": message_id, "type": "message", "role": "assistant", "model": MODEL, "content": [],
                    "stop_reason": None, "stop_sequence": None, "usage": {**start_usage, "output_tokens": 1},
                },
            },
        )
    ]
    for index, (kind, block, deltas) in enumerate(blocks):
        out.append(event("content_block_start", {"type": "content_block_start", "index": index, "content_block": block}))
        if index == 0:
            out.append('event: ping\ndata: {"type": "ping"}\n\n')
        for delta in deltas:
            out.append(event("content_block_delta", {"type": "content_block_delta", "index": index, "delta": delta}))
        out.append(event("content_block_stop", {"type": "content_block_stop", "index": index}))
    out.append(
        event("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": output_tokens}})
    )
    usage = {**start_usage, "output_tokens": output_tokens}
    charged = charge(usage)
    balance -= charged
    out.append(event("truebex_credits", {"charged": charged, "remaining": balance, "served_by": {"provider": "anthropic", "model": MODEL}}))
    out.append(event("message_stop", {"type": "message_stop"}))
    return "".join(out), balance


def thinking(signature: str) -> tuple[str, dict, list[dict]]:
    return ("thinking", {"type": "thinking", "thinking": "", "signature": ""}, [{"type": "signature_delta", "signature": signature}])


def text(parts: list[str]) -> tuple[str, dict, list[dict]]:
    return ("text", {"type": "text", "text": ""}, [{"type": "text_delta", "text": p} for p in parts])


def tool(tool_id: str, name: str, json_parts: list[str]) -> tuple[str, dict, list[dict]]:
    return (
        "tool_use",
        {"type": "tool_use", "id": tool_id, "name": name, "input": {}},
        [{"type": "input_json_delta", "partial_json": p} for p in ["", *json_parts]],
    )


def files() -> dict[str, bytes]:
    """Every stand-in: path under OUT -> bytes."""
    out: dict[str, bytes] = {}
    balance = START_BALANCE
    find, balance = turn(
        "msg_01Tbx0Window0000000000001",
        {"input_tokens": 1024, "cache_creation_input_tokens": 4096, "cache_read_input_tokens": 0},
        [
            thinking("EqQBCkYIBxgCKkDTbx0FixtureSignatureFind0001"),
            tool("toolu_01Tbx0Find00000000000001", "find", ['{"kind": "wall", "room": "Study",', ' "facing": "n"}']),
        ],
        "tool_use", 180, balance,
    )
    out["window/01-find.sse"] = find.encode("utf-8")
    place, balance = turn(
        "msg_01Tbx0Window0000000000002",
        {"input_tokens": 300, "cache_creation_input_tokens": 220, "cache_read_input_tokens": 5120},
        [
            thinking("EqQBCkYIBxgCKkDTbx0FixtureSignaturePlace001"),
            text(["Found the study's north wall.", " Placing a 1.2 m window on it."]),
            tool(
                "toolu_01Tbx0Place0000000000001", "place",
                ['{"kind": "window", ', f'"host": "{WALL}", ', '"width_mm": 1200}'],
            ),
        ],
        "tool_use", 210, balance,
    )
    out["window/02-place.sse"] = place.encode("utf-8")
    end, balance = turn(
        "msg_01Tbx0Window0000000000003",
        {"input_tokens": 260, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 5560},
        [
            thinking("EqQBCkYIBxgCKkDTbx0FixtureSignatureEnd00001"),
            text(["Done: a 1.2 m window sits on the north wall", " of the study."]),
        ],
        "end_turn", 60, balance,
    )
    out["window/03-end.sse"] = end.encode("utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="compare the files with what this script writes")
    args = parser.parse_args(argv)
    wanted = files()
    if args.check:
        stale = [name for name, data in wanted.items() if not (OUT / name).is_file() or (OUT / name).read_bytes() != data]
        if stale:
            print("stale: " + ", ".join(stale))
            return 1
        print(f"{OUT}: {len(wanted)} files as written")
        return 0
    for name, data in wanted.items():
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(f"wrote {len(wanted)} files into {OUT} (balance {START_BALANCE} -> 4345)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
