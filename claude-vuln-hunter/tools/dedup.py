#!/usr/bin/env python3
"""Decide whether a parsed crash is a new vulnerability group.

Simplified port of Atlantis pov_dedup.dedup_crash_log. Groups are persisted in
workspace/state.json ("groups": [ {sanitizer, signature}, ... ]).
A crash is NEW if no existing group has the same (sanitizer, top-frame-signature).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from state import load as load_state, save as save_state  # noqa: E402  (sibling import)


def signature(parsed: dict) -> str:
    """Stable signature from sanitizer + the deepest meaningful callstack."""
    san = parsed.get("sanitizer") or "unknown"
    stacks = parsed.get("callstacks") or []
    primary = stacks[0] if stacks else []
    # use function names of the first few frames (location-insensitive top)
    frames = [f.get("name", "") for f in primary[:8]]
    raw = san + "|" + "->".join(frames)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True, help="path to parse_crash.py JSON output")
    args = ap.parse_args()

    parsed = json.loads(Path(args.new).read_text())
    sig = signature(parsed)
    san = parsed.get("sanitizer") or "unknown"

    state = load_state()
    groups = state.setdefault("groups", [])

    for g in groups:
        if g["signature"] == sig:
            print(json.dumps({
                "is_new": False, "group_id": g["id"],
                "reason": f"matches existing group {g['id']} ({san})",
            }))
            return

    gid = len(groups)
    groups.append({"id": gid, "sanitizer": san, "signature": sig})
    save_state(state)
    print(json.dumps({
        "is_new": True, "group_id": gid,
        "reason": f"new group {gid} for {san} (sig {sig})",
    }))


if __name__ == "__main__":
    main()
