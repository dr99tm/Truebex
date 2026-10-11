"""Write the ai-proxy contract fixtures (contracts/ai-proxy.md §9) into
server/tests/contracts/ai-proxy/.

    py -3.12 scripts\\make_ai_proxy_fixtures.py

Deterministic. AI3 owns the master copy (`Docs/roadmap/fixtures/contracts/
ai-proxy/` in the app repo) once it lands; until then PF11 stages this set,
written to the letter of §5, §6.2, §7 and §9: the "window on the north wall
of the study, 1.2 m wide" example as three streamed turns (find, place,
end_turn) whose `truebex_credits` events follow from the usage at the 5.1
rates and the studio balance (4388 credits left), plus the 5.1 / 5.2
answers, a refusal, the 403 and the 503.

The `.sse` files hold the exact bytes the proxy sends (and the app's stub
replays); the platform's fake provider serves them without their
`truebex_credits` events, which the proxy adds itself.
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "contracts" / "ai-proxy"

MODEL = "claude-opus-5-5"
RATES = {"input": 4000, "output": 20000, "cache_read": 400, "cache_write": 5000}
START_BALANCE = 4388
WALL = "0199c6a2e00070018000000000000001"  # the project-log fixtures' first wall
REQUEST_ID = "5ee1d00000000000000000000000c0de"


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


def write(name: str, data: str | dict) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, dict):
        data = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(data.encode("utf-8"))


def main() -> None:
    write(
        "models.json",
        {
            "default": "truebex-assist",
            "models": [
                {"alias": "truebex-assist", "context_tokens": 1000000, "max_output_tokens": 64000, "vision": True, "credits_per_mtok": RATES}
            ],
        },
    )
    common = {"allowance_monthly": 5000, "top_up_remaining": 0, "resets_at": "2026-11-01T00:00:00Z", "plan": "studio", "top_up_url": "https://truebex.com/dashboard/cloud/#ai-credits"}
    write("balance-studio.json", {"credits_remaining": START_BALANCE, **common, "allowance_remaining": START_BALANCE})
    write("balance-empty.json", {"credits_remaining": 0, **common, "allowance_remaining": 0})

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
    write("window/01-find.sse", find)
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
    write("window/02-place.sse", place)
    end, balance = turn(
        "msg_01Tbx0Window0000000000003",
        {"input_tokens": 260, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 5560},
        [
            thinking("EqQBCkYIBxgCKkDTbx0FixtureSignatureEnd00001"),
            text(["Done: a 1.2 m window sits on the north wall", " of the study."]),
        ],
        "end_turn", 60, balance,
    )
    write("window/03-end.sse", end)

    refusal_usage = {"input_tokens": 900, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    write(
        "refusal.json",
        {
            "id": "msg_01Tbx0Refusal000000000001", "type": "message", "model": "truebex-assist", "role": "assistant",
            "stop_reason": "refusal",
            "stop_details": {"type": "refusal", "category": "cyber", "explanation": "The model declined this request."},
            "content": [], "usage": refusal_usage,
            "credits": {"charged": charge(refusal_usage), "remaining": START_BALANCE - charge(refusal_usage)},
            "served_by": {"provider": "anthropic", "model": MODEL},
        },
    )
    write(
        "credits-exhausted.json",
        {
            "detail": "Your AI credits are used up for this month.", "code": "credits_exhausted", "status": 403,
            "request_id": REQUEST_ID, "retry_after_s": None,
            "data": {"remaining": 0, "resets_at": "2026-11-01T00:00:00Z", "plan_needed": "studio", "top_up_url": "https://truebex.com/dashboard/cloud/#ai-credits"},
        },
    )
    write(
        "upstream-busy.json",
        {
            "detail": "The AI service is busy. Try again in a moment.", "code": "upstream_busy", "status": 503,
            "request_id": REQUEST_ID, "retry_after_s": 20, "data": {},
        },
    )
    print(f"wrote {OUT} (balance {START_BALANCE} -> {balance})")


if __name__ == "__main__":
    main()
