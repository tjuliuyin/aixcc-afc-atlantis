#!/usr/bin/env python3
"""Decide whether a parsed crash is a new vulnerability group.

Java edition. Signature = (sanitizer, top-N project method names from the
deepest stack). Mirrors Atlantis pov_dedup is_similar_callstack / sanitizer
grouping logic, scaled down for single-host use.

Groups are persisted in workspace/state.json under "groups":
  [{ id, sanitizer, signature }]
A crash is NEW if no existing group has the same (sanitizer, signature).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from state import load as load_state, save as save_state  # noqa: E402


# Sanitizer families considered equivalent for grouping purposes
# (mirrors Atlantis SIMILAR_SANITIZER). Kept CONSERVATIVE: only merge labels
# that are genuinely the same root cause surfacing under different names.
# Distinct vuln classes (rce vs os-command-injection, path-traversal vs ssrf)
# are intentionally NOT merged — the callstack signature already separates
# unrelated bugs, and merging labels would mislabel real findings.
SIMILAR_GROUPS = [
    {"oom", "stack-overflow"},   # both are resource-exhaustion / DoS surface
]


def canonical_sanitizer(s: str) -> str:
    if not s:
        return "unknown"
    for grp in SIMILAR_GROUPS:
        if s in grp:
            return sorted(grp)[0]  # canonical = lexicographically-first in group
    return s


def signature(parsed: dict) -> str:
    """Top-N project method names from the deepest callstack."""
    san = canonical_sanitizer(parsed.get("sanitizer"))
    stacks = parsed.get("callstacks") or []
    primary = stacks[0] if stacks else []
    # Keep only project-method names (filter heuristic: contains a dot, isn't
    # a JDK class). The orchestrator already drops noise frames, but be safe.
    names = []
    for fr in primary:
        n = (fr.get("name") or "").strip()
        if not n:
            continue
        names.append(n)
        if len(names) >= 8:
            break
    raw = san + "|" + "->".join(names)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True, help="path to parse_crash.py JSON output")
    args = ap.parse_args()

    parsed = json.loads(Path(args.new).read_text())
    sig = signature(parsed)
    san = canonical_sanitizer(parsed.get("sanitizer"))

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
