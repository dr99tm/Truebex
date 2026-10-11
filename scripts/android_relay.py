"""A TCP relay for the Android human test (PF10): 127.0.0.1:<listen> -> 127.0.0.1:<target>.

    py -3.12 scripts/android_relay.py 8731 8000

scripts/try-android.ps1 routes the phone's 127.0.0.1:8000 to this relay with `adb reverse`, so the app
reaches the local API over USB (or from the emulator). The USB tunnel ignores airplane mode, so stopping
the relay (Ctrl+C) is what takes the phone offline for the API; starting it again brings it back.
Standard library only.
"""

import asyncio
import sys


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        writer.close()


async def _serve(listen: int, target: int) -> None:
    async def handle(client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter) -> None:
        try:
            server_r, server_w = await asyncio.open_connection("127.0.0.1", target)
        except OSError:
            client_w.close()
            return
        await asyncio.gather(_pipe(client_r, server_w), _pipe(server_r, client_w))

    server = await asyncio.start_server(handle, "127.0.0.1", listen)
    print(f"relay 127.0.0.1:{listen} -> 127.0.0.1:{target} (Ctrl+C takes the phone offline)", flush=True)
    async with server:
        await server.serve_forever()


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not all(a.isdigit() for a in argv):
        print(__doc__)
        return 2
    try:
        asyncio.run(_serve(int(argv[0]), int(argv[1])))
    except KeyboardInterrupt:
        print("relay stopped: the phone is offline for the API")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
