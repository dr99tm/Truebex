"""Talk to the metered assistant proxy as the desktop app does (PF11, contract
ai-proxy 1.1), for testing without the app's AI panel (AI3).

    cd server
    .venv\\Scripts\\python.exe scripts\\demo_ai.py --token tbx_dev_… models
    .venv\\Scripts\\python.exe scripts\\demo_ai.py --token tbx_dev_… balance
    .venv\\Scripts\\python.exe scripts\\demo_ai.py --token tbx_dev_… window
    .venv\\Scripts\\python.exe scripts\\demo_ai.py --token tbx_dev_… summary

`window` asks "Put a window on the north wall of the study, 1.2 m wide" with
two agent tools (`find`, `place`), streams each turn (text, tool calls, the
`truebex_credits` event), answers the tool calls the way the app would (a
stand-in model: one wall found, the window placed) and sends the next turn
with the history unchanged and the same `metadata.session_id`, until the
model ends its turn. `summary` sends one tool-less turn (no tools, no
tool_choice), as the app's unattended-run summaries do (contract 1.1.2).
`count` prints 5.4's estimate for the first turn. Get a device token with
`demo_replica.py login … --trial`. API: --api (default http://127.0.0.1:8000).
"""

import argparse
import json
import secrets
import sys

import requests

AI = {"X-Truebex-Contract": "ai-proxy/1.1"}
WALL = "0199c6a2e00070018000000000000001"
QUESTION = "Put a window on the north wall of the study, 1.2 m wide"
SYSTEM = (
    "You are the assistant inside Truebex, a building design app. Change the model only with the tools. "
    "Use find to locate elements, then place to add objects to a host element."
)
TOOLS = [
    {
        "name": "find",
        "description": "Find elements of the open project by kind, room and the compass direction they face.",
        "input_schema": {
            "type": "object",
            "properties": {"kind": {"type": "string"}, "room": {"type": "string"}, "facing": {"type": "string", "enum": ["n", "e", "s", "w"]}},
            "required": ["kind"],
        },
    },
    {
        "name": "place",
        "description": "Place an object (window, door) on a host element found with find.",
        "input_schema": {
            "type": "object",
            "properties": {"kind": {"type": "string"}, "host": {"type": "string"}, "width_mm": {"type": "integer"}},
            "required": ["kind", "host"],
        },
    },
]


def _url(args, path: str) -> str:
    return f"{args.api.rstrip('/')}{path}"


def _headers(args) -> dict:
    return {**AI, "Authorization": f"Bearer {args.token}"}


def _fail(res) -> None:
    try:
        body = res.json()
        why = f"{body.get('code', res.status_code)}: {body.get('detail')}"
        if body.get("data"):
            why += f" {json.dumps(body['data'])}"
    except ValueError:
        why = res.text[:300]
    raise SystemExit(f"{res.request.method} {res.request.path_url} -> {res.status_code} {why}")


def get(args, path: str) -> dict:
    res = requests.get(_url(args, path), headers=_headers(args), timeout=60)
    if res.status_code != 200:
        _fail(res)
    return res.json()


def turn_body(messages: list, *, stream: bool = True, session: str | None = None) -> dict:
    """A 5.3 body; one conversation sends one `session` with every turn."""
    return {
        "model": "truebex-assist",
        "max_tokens": 8192,
        "stream": stream,
        "system": SYSTEM,
        "tools": TOOLS,
        "tool_choice": {"type": "auto"},
        "metadata": {"session_id": session or secrets.token_hex(16), "app_version": "demo"},
        "messages": messages,
    }


def summary_body(text: str) -> dict:
    """A tool-less turn (1.1.2): no tools and no tool_choice."""
    return {
        "model": "truebex-assist",
        "max_tokens": 1024,
        "stream": True,
        "system": "Summarise this unattended run for the person who started it, in two sentences.",
        "metadata": {"session_id": secrets.token_hex(16), "app_version": "demo"},
        "messages": [{"role": "user", "content": [{"type": "text", "text": text}]}],
    }


def stream_turn(args, body: dict) -> tuple[list, str | None]:
    """One streamed turn: prints it, returns (the assistant's content, stop_reason)."""
    res = requests.post(
        _url(args, "/ai/messages"), headers={**_headers(args), "Idempotency-Key": secrets.token_hex(16)},
        json=body, stream=True, timeout=(10, 600),
    )
    if res.status_code != 200:
        _fail(res)
    blocks: dict[int, dict] = {}
    partial: dict[int, str] = {}
    stop = None
    event = None
    for raw in res.iter_lines(decode_unicode=True):
        if raw.startswith("event:"):
            event = raw[6:].strip()
            continue
        if not raw.startswith("data:"):
            continue
        data = json.loads(raw[5:])
        if event == "content_block_start":
            blocks[data["index"]] = dict(data["content_block"])
            if data["content_block"]["type"] == "tool_use":
                print(f"\n[tool call] {data['content_block']['name']} ", end="", flush=True)
        elif event == "content_block_delta":
            d = data["delta"]
            b = blocks[data["index"]]
            if d["type"] == "text_delta":
                b["text"] += d["text"]
                print(d["text"], end="", flush=True)
            elif d["type"] == "input_json_delta":
                partial[data["index"]] = partial.get(data["index"], "") + d["partial_json"]
                print(d["partial_json"], end="", flush=True)
            elif d["type"] == "thinking_delta":
                b["thinking"] += d["thinking"]
            elif d["type"] == "signature_delta":
                b["signature"] = d["signature"]
        elif event == "message_delta":
            stop = data["delta"].get("stop_reason") or stop
        elif event == "truebex_credits":
            served = data.get("served_by") or {}
            print(f"\n[credits] {data['charged']} charged, {data['remaining']} left (served by {served.get('provider')} {served.get('model')})")
        elif event == "error":
            raise SystemExit(f"\n[error] {data.get('code')}: {data.get('detail')}")
    for i, text in partial.items():
        blocks[i]["input"] = json.loads(text) if text else {}
    return [blocks[i] for i in sorted(blocks)], stop


def tool_result(block: dict) -> dict:
    if block["name"] == "find":
        found = {"matches": [{"ref": WALL, "kind": "wall", "room": "Study", "facing": "n", "length_mm": 3600}]}
    elif block["name"] == "place":
        found = {"placed": True, "ref": secrets.token_hex(16), "host": block["input"].get("host")}
    else:
        found = {"error": f"unknown tool {block['name']}"}
    return {"type": "tool_result", "tool_use_id": block["id"], "is_error": "error" in found,
            "content": [{"type": "text", "text": json.dumps(found)}]}


def cmd_window(args) -> None:
    messages = [{"role": "user", "content": [{"type": "text", "text": QUESTION}]}]
    session = secrets.token_hex(16)  # one conversation, one session id (contract 5.3)
    print(f"you: {QUESTION}")
    for _ in range(args.turns):
        content, stop = stream_turn(args, turn_body(messages, session=session))
        messages.append({"role": "assistant", "content": content})
        calls = [b for b in content if b.get("type") == "tool_use"]
        if stop != "tool_use" or not calls:
            print(f"\n[stop] {stop}")
            return
        results = [tool_result(b) for b in calls]
        for r in results:
            print(f"[tool result] {r['content'][0]['text']}")
        messages.append({"role": "user", "content": results})
    print("\n[stop] turn limit")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--token", required=True, help="a device token (tbx_dev_…)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("models")
    sub.add_parser("balance")
    sub.add_parser("count")
    w = sub.add_parser("window")
    w.add_argument("--turns", type=int, default=6)
    s = sub.add_parser("summary")
    s.add_argument("--text", default="Run 12 checked the stairs and the fire exits: 3 checks passed, 1 warning (stair 2's headroom).")
    args = parser.parse_args(argv)
    if args.cmd in ("models", "balance"):
        print(json.dumps(get(args, f"/ai/{args.cmd}"), indent=2))
    elif args.cmd == "count":
        body = turn_body([{"role": "user", "content": [{"type": "text", "text": QUESTION}]}])
        res = requests.post(_url(args, "/ai/messages/count"), headers=_headers(args), json=body, timeout=60)
        if res.status_code != 200:
            _fail(res)
        print(json.dumps(res.json(), indent=2))
    elif args.cmd == "summary":
        print(f"run: {args.text}")
        _, stop = stream_turn(args, summary_body(args.text))
        print(f"\n[stop] {stop}")
    else:
        cmd_window(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
