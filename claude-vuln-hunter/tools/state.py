#!/usr/bin/env python3
"""File-backed state store (replaces Atlantis' Redis bus). Single JSON file.

CLI:
  python tools/state.py get  bits
  python tools/state.py set  iteration_budget 5
  python tools/state.py incr failed_attempts/<bit_id>
  python tools/state.py append verified_povs '{"bit_id": "...", ...}'
"""
import argparse
import json
import os
from pathlib import Path

ROOT = Path(os.environ.get("VULN_HUNTER_ROOT", Path(__file__).resolve().parent.parent))
STATE = ROOT / "workspace" / "state.json"

DEFAULT = {
    "bits": [],
    "verified_povs": [],
    "duplicate_povs": [],
    "failed_attempts": {},
    "groups": [],
    "iteration_budget": 5,
}


def load() -> dict:
    if not STATE.exists():
        return json.loads(json.dumps(DEFAULT))
    try:
        return json.loads(STATE.read_text())
    except json.JSONDecodeError:
        return json.loads(json.dumps(DEFAULT))


def save(s: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))


def _coerce(value: str):
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("op", choices=["get", "set", "incr", "append", "dump", "reset"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("value", nargs="?")
    args = ap.parse_args()

    if args.op == "reset":
        save(json.loads(json.dumps(DEFAULT)))
        print("reset")
        return

    s = load()
    if args.op == "dump":
        print(json.dumps(s, indent=2))
        return

    keys = args.path.split("/")
    cur = s
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    last = keys[-1]

    if args.op == "get":
        print(json.dumps(cur.get(last)))
    elif args.op == "set":
        cur[last] = _coerce(args.value)
        save(s)
        print("ok")
    elif args.op == "incr":
        cur[last] = (cur.get(last, 0) or 0) + 1
        save(s)
        print(cur[last])
    elif args.op == "append":
        cur.setdefault(last, []).append(_coerce(args.value))
        save(s)
        print("ok")


if __name__ == "__main__":
    main()
