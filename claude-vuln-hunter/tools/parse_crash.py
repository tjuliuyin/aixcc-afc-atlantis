#!/usr/bin/env python3
"""Parse an ASAN / Jazzer crash log into a structured callstack.

Compact port of Atlantis cp_manager/cp_manager/pov_dedup.py (parse_crash_log_*).
Outputs JSON: {sanitizer, callstacks:[[{name,file,line}, ...], ...]}.
"""
import argparse
import json
import sys

C_SANITIZERS = {
    "AddressSanitizer: heap-buffer-overflow": "heap-buffer-overflow",
    "AddressSanitizer: heap-use-after-free": "heap-use-after-free",
    "AddressSanitizer: stack-buffer-overflow": "stack-buffer-overflow",
    "AddressSanitizer: global-buffer-overflow": "global-buffer-overflow",
    "AddressSanitizer: stack-buffer-underflow": "stack-buffer-underflow",
    "AddressSanitizer: double-free": "double-free",
    "AddressSanitizer: SEGV": "SEGV",
    "AddressSanitizer: FPE": "FPE",
    "AddressSanitizer: negative-size-param": "negative-size-param",
    "ERROR: libFuzzer: timeout": "timeout",
    "out-of-memory": "oom",
    # fortified libc can surface an overflow as a generic ASAN crash:
    "AddressSanitizer: unknown-crash": "heap-buffer-overflow",
}
JVM_SANITIZERS = {
    "FuzzerSecurityIssueCritical: File path traversal": "path-traversal",
    "FuzzerSecurityIssueCritical: OS Command Injection": "os-command-injection",
    "FuzzerSecurityIssueHigh: SQL Injection": "sql-injection",
    "FuzzerSecurityIssueHigh: Remote Code Execution": "rce",
    "FuzzerSecurityIssueMedium: Server Side Request Forgery": "ssrf",
    "FuzzerSecurityIssueLow: Stack overflow": "stack-overflow",
}


def detect_sanitizer(log: bytes, is_jvm: bool):
    table = JVM_SANITIZERS if is_jvm else C_SANITIZERS
    for needle, name in table.items():
        if needle.encode() in log:
            return name
    return None


def parse_c(log: bytes):
    """Split ASAN frames `    #N 0x.. in func file:line`."""
    callstacks = []
    chunks = log.split(b"    #0 ")
    for chunk in chunks[1:]:
        chunk = b"    #0 " + chunk
        frames = []
        for line in chunk.split(b"\n"):
            if not line.startswith(b"    #"):
                break
            text = line.decode("utf-8", errors="ignore")
            if " in " not in text:
                continue
            rest = text.split(" in ", 1)[1].strip()
            name = rest.split(" ")[0]
            loc = rest[len(name):].strip()
            file_, lineno = None, None
            if loc and not loc.startswith("("):
                parts = loc.split(":")
                file_ = parts[0]
                try:
                    lineno = int(parts[1])
                except (IndexError, ValueError):
                    lineno = None
            frames.append({"name": name, "file": file_, "line": lineno})
        if frames:
            callstacks.append(frames)
    return callstacks


def parse_jvm(log: bytes):
    callstacks, frames = [], []
    for line in log.split(b"\n"):
        text = line.decode("utf-8", errors="ignore")
        if text.startswith("\tat "):
            body = text[4:]
            name = body.split("(")[0]
            file_, lineno = None, None
            if "(" in body and ")" in body:
                inner = body[body.index("(") + 1: body.index(")")]
                if ":" in inner:
                    file_, _, ln = inner.partition(":")
                    try:
                        lineno = int(ln)
                    except ValueError:
                        lineno = None
            frames.append({"name": name, "file": file_, "line": lineno})
    if frames:
        callstacks.append(frames)
    return callstacks


# Frames that are sanitizer/runtime noise, filtered like Atlantis does.
def is_noise(frame, is_jvm):
    f = frame.get("file") or ""
    n = frame.get("name") or ""
    if is_jvm:
        return n.startswith("java.base") or "0x" in n or "$" in n
    return f.startswith("/src/llvm-project") or "compiler-rt" in f or n.startswith("__asan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    args = ap.parse_args()

    log = open(args.log, "rb").read()
    is_jvm = b"Java Exception" in log
    sanitizer = detect_sanitizer(log, is_jvm)
    callstacks = parse_jvm(log) if is_jvm else parse_c(log)
    # filter noise + dedup frames within a stack
    cleaned = []
    for stack in callstacks:
        seen, fs = set(), []
        for fr in stack:
            if is_noise(fr, is_jvm):
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
        "is_jvm": is_jvm,
        "callstacks": cleaned,
    }, indent=2))


if __name__ == "__main__":
    main()
