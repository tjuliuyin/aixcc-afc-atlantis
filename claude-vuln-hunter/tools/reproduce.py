#!/usr/bin/env python3
"""Run a candidate blob through the real harness and report the verdict.

This is the deterministic confirmation gate (Atlantis: CP.reproduce).
Backends:
  native  - run the binary directly (Linux, or WSL-internal)
  wsl     - run via `wsl -- <linux-path> <linux-path>` from Windows
  docker  - run inside a runner image
The crash exit-code set mirrors Atlantis cp_manager/submit_pov.py.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CRASH_CODES = {1, 70, 71, 77}  # ASAN, libFuzzer timeout, OOM, default


def to_wsl_path(p: Path) -> str:
    s = str(p.resolve()).replace("\\", "/")
    if len(s) > 1 and s[1] == ":":
        s = f"/mnt/{s[0].lower()}{s[2:]}"
    return s


def run_native(harness: Path, blob: Path, timeout: int):
    env = dict(os.environ)
    # Make ASAN exit with the libFuzzer-style code and not abort noisily.
    env.setdefault("ASAN_OPTIONS", "abort_on_error=0:exitcode=1:detect_leaks=0")
    cmd = [str(harness.resolve()), str(blob.resolve())]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
        return r.returncode, (r.stderr or b"") + (r.stdout or b""), time.time() - t0
    except subprocess.TimeoutExpired as e:
        out = (e.stderr or b"") + (e.stdout or b"")
        return 70, out, time.time() - t0


def run_wsl(harness: Path, blob: Path, timeout: int):
    cmd = ["wsl", "--", to_wsl_path(harness), to_wsl_path(blob)]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode, (r.stderr or b"") + (r.stdout or b""), time.time() - t0
    except subprocess.TimeoutExpired as e:
        out = (e.stderr or b"") + (e.stdout or b"")
        return 70, out, time.time() - t0


def run_docker(image: str, harness: Path, blob: Path, timeout: int):
    blob_dir = blob.parent.resolve()
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{blob_dir}:/in:ro",
        image, f"/harness/{harness.name}", f"/in/{blob.name}",
    ]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode, (r.stderr or b"") + (r.stdout or b""), time.time() - t0
    except subprocess.TimeoutExpired as e:
        out = (e.stderr or b"") + (e.stdout or b"")
        return 70, out, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", required=True)
    ap.add_argument("--blob", required=True)
    ap.add_argument("--backend", default=os.environ.get("REPRODUCE_BACKEND", "native"))
    ap.add_argument("--image", default="vuln-hunter-runner:latest")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()

    harness, blob = Path(args.harness), Path(args.blob)
    if not blob.exists():
        print(json.dumps({"error": f"blob not found: {blob}"}))
        sys.exit(2)

    if args.backend == "wsl":
        rc, log, dur = run_wsl(harness, blob, args.timeout)
    elif args.backend == "docker":
        rc, log, dur = run_docker(args.image, harness, blob, args.timeout)
    else:
        rc, log, dur = run_native(harness, blob, args.timeout)

    log_path = blob.with_suffix(".log")
    log_path.write_bytes(log)

    print(json.dumps({
        "exit_code": rc,
        "is_crash": rc in CRASH_CODES,
        "crash_log_path": str(log_path),
        "duration_s": round(dur, 3),
        "language": "jvm" if b"Java Exception" in log else "c",
    }))


if __name__ == "__main__":
    main()
