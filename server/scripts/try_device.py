r"""Act as the desktop app on a pretend computer, for trying seats without an
LC1 build: sign in with e-mail and password, activate (contract 5.4), ask for
a fresh entitlement (5.5) or hand a floating seat back (5.11), and print what
the entitlement says.

    cd server
    .venv\Scripts\python.exe scripts\try_device.py --email a@example.com --password password123 --name "Test PC 1"
    .venv\Scripts\python.exe scripts\try_device.py --email b@example.com --password password123 --name "Test PC 2" --refresh
    .venv\Scripts\python.exe scripts\try_device.py --email b@example.com --password password123 --name "Test PC 2" --release

The computer's fingerprint is made from --name, so the same name is the same
computer. Talks to --api (default http://127.0.0.1:8000).
"""

import argparse
import hashlib
import sys

import httpx

CONTRACT = {"X-Truebex-Contract": "licence-api/1.0"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Act as the Truebex app on a pretend computer.")
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--name", default="Test PC", help="the computer's name (also makes its fingerprint)")
    ap.add_argument("--refresh", action="store_true", help="after activating, ask for a fresh entitlement (5.5)")
    ap.add_argument("--release", action="store_true", help="after activating, hand the floating seat back (5.11)")
    args = ap.parse_args(argv)

    fingerprint = hashlib.sha256(f"truebex-fp/1\n{args.name}\nS-1-5-21-try".encode()).hexdigest()
    with httpx.Client(base_url=args.api, timeout=20, headers=CONTRACT) as api:
        res = api.post("/auth/login", json={"email": args.email, "password": args.password})
        if res.status_code != 200:
            print(f"sign-in failed: {res.status_code} {res.text}")
            return 1
        session = {"Authorization": f"Bearer {res.json()['access_token']}"}
        res = api.post("/licence/activate", headers=session, json={
            "fingerprint": fingerprint, "device_name": args.name, "os": "windows (try_device)", "app_version": "1.0.0",
        })
        if res.status_code not in (200, 201):
            print(f"activate: {res.status_code} {res.json().get('code')}: {res.json().get('detail')}")
            return 1
        token = res.json()["device_token"]
        show("activate", res.json()["entitlement"]["document"])
        device = {"Authorization": f"Bearer {token}"}
        if args.refresh:
            res = api.post("/licence/entitlement", headers=device, json={"fingerprint": fingerprint, "app_version": "1.0.0"})
            if res.status_code == 200:
                show("entitlement", res.json()["entitlement"]["document"])
            else:
                body = res.json()
                print(f"entitlement: {res.status_code} {body.get('code')}: {body.get('detail')} -> the app runs Free")
        if args.release:
            res = api.post("/licence/release", headers=device)
            print(f"release: {res.status_code}" + ("" if res.status_code == 204 else f" {res.json().get('code')}"))
    return 0


def show(step: str, doc: dict) -> None:
    print(f"{step}: plan {doc['plan']} · seat {doc['seat_kind']} · org {doc['account']['org_id']} · "
          f"refresh after {doc['refresh_after']} · expires {doc['expires_at']}")


if __name__ == "__main__":
    sys.exit(main())
