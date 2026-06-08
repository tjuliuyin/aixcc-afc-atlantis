#!/usr/bin/env python3
"""Parse a Jazzer crash log into a structured callstack.

Port + simplification of Atlantis cp_manager/cp_manager/pov_dedup.py
(parse_crash_log_jvm). Output JSON:
  { sanitizer: "<short-name>", is_jvm: true, callstacks: [[{name,file,line}, ...]] }
"""
import argparse
import json
import sys


# Map Jazzer issue text -> short sanitizer name (matches Atlantis JVM_SANITIZER).
JVM_SANITIZERS = [
    ("FuzzerSecurityIssueCritical: File path traversal", "path-traversal"),
    ("FuzzerSecurityIssueCritical: OS Command Injection", "os-command-injection"),
    ("FuzzerSecurityIssueCritical: LDAP Injection",       "ldap-injection"),
    ("FuzzerSecurityIssueCritical: Remote JNDI Lookup",   "jndi-lookup"),
    ("FuzzerSecurityIssueCritical: Script Engine Injection", "script-engine-injection"),
    ("FuzzerSecurityIssueHigh: load arbitrary library",  "load-library"),
    ("FuzzerSecurityIssueHigh: SQL Injection",           "sql-injection"),
    ("FuzzerSecurityIssueHigh: XPath Injection",         "xpath-injection"),
    ("FuzzerSecurityIssueHigh: Remote Code Execution",   "rce"),
    ("FuzzerSecurityIssueMedium: Server Side Request Forgery", "ssrf"),
    ("FuzzerSecurityIssueLow: Regular Expression Injection",   "regex-injection"),
    ("FuzzerSecurityIssueLow: Out of memory",            "oom"),
    ("FuzzerSecurityIssueLow: Stack overflow",           "stack-overflow"),
    ("ERROR: libFuzzer: timeout",                        "timeout"),
]

# Frames to drop as noise (mirrors Atlantis JVM is_interesting_call).
NOISE_PREFIXES = (
    "java.base",
    "jdk.internal",
    "sun.",
    "com.code_intelligence.jazzer",
    "com.code_intelligence.jazzer.api",
)


def detect_sanitizer(log: bytes):
    for needle, name in JVM_SANITIZERS:
        if needle.encode() in log:
            return name
    if b"Java Exception" in log:
        return "uncaught-exception"
    return None


def parse_frame(text: str):
    """Parse one '\tat com.foo.Bar.baz(Bar.java:42)' line."""
    body = text.strip()
    if body.startswith("at "):
        body = body[3:]
    if "(" not in body or ")" not in body:
        return {"name": body, "file": None, "line": None}
    name = body.split("(")[0]
    inner = body[body.index("(") + 1: body.index(")")]
    file_, line = None, None
    if ":" in inner:
        file_, _, ln = inner.partition(":")
        try:
            line = int(ln)
        except ValueError:
            line = None
    else:
        file_ = inner if inner else None
    return {"name": name, "file": file_, "line": line}


def is_noise(frame):
    n = frame.get("name") or ""
    if not n or "0x" in n or "$" in n:
        return True
    return any(n.startswith(p) for p in NOISE_PREFIXES)


def parse_jvm(log: bytes):
    """Walk the log and split callstacks at empty lines / 'Caused by' boundaries."""
    callstacks, cur = [], []
    for raw in log.split(b"\n"):
        line = raw.decode("utf-8", errors="ignore")
        stripped = line.strip()
        if stripped.startswith("at ") or line.startswith("\tat "):
            cur.append(parse_frame(stripped if stripped.startswith("at ") else line))
            continue
        # boundary
        if cur:
            callstacks.append(cur)
            cur = []
    if cur:
        callstacks.append(cur)
    return callstacks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    args = ap.parse_args()

    log = open(args.log, "rb").read()
    sanitizer = detect_sanitizer(log)
    stacks = parse_jvm(log)

    cleaned = []
    for stack in stacks:
        seen, fs = set(), []
        for fr in stack:
            if is_noise(fr):
                continue
            key = (fr["name"], fr["file"], fr["line"])
            if key in seen:
                continue
            seen.add(key)
            fs.append(fr)
        if fs:
            cleaned.append(fs[:50])

    print(json.dumps({
        "sanitizer": sanitizer,
        "is_jvm": True,
        "callstacks": cleaned,
    }, indent=2))


if __name__ == "__main__":
    main()
