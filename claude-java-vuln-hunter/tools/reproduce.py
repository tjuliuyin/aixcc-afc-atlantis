#!/usr/bin/env python3
"""Run a candidate blob through Jazzer in single-input replay mode.

Mirrors Atlantis CP.reproduce + submit_pov.run_pov_on_head, JVM edition.
A Jazzer crash (FuzzerSecurityIssue*) is reported via a non-zero exit code +
a "ERROR:" line in stderr; we treat exit codes in {1, 70, 71, 77} as crashes
to align with the libFuzzer / Atlantis convention.

Backends:
  native  - run `java -jar jazzer_standalone.jar ... <blob>`
  wsl     - same command via `wsl -- ...` from a Windows host
  docker  - run inside the bundled runner image
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CRASH_CODES = {1, 70, 71, 77}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JAZZER_JAR = PROJECT_ROOT / "jazzer" / "jazzer_standalone.jar"
BUILD_DIR = PROJECT_ROOT / "workspace" / "build"
CLASSES_DIR = BUILD_DIR / "classes"
DEPS_DIR = BUILD_DIR / "deps"


def build_classpath() -> str:
    # Prefer the classpath assembled by build_target.py (handles Maven/Gradle
    # dependency trees that the simple glob below would miss).
    cp_file = BUILD_DIR / "cp.txt"
    if cp_file.exists():
        cp = cp_file.read_text().strip()
        if cp:
            return cp
    parts = [str(JAZZER_JAR), str(CLASSES_DIR)]
    if DEPS_DIR.exists():
        for jar in sorted(DEPS_DIR.glob("*.jar")):
            parts.append(str(jar))
    # os.pathsep is ':' on Unix and ';' on Windows — required for native Windows.
    return os.pathsep.join(parts)


def jazzer_cmd(target_class: str, blob: Path):
    return [
        "java",
        "-cp", build_classpath(),
        "com.code_intelligence.jazzer.Jazzer",
        f"--target_class={target_class}",
        "--keep_going=1",
        str(blob.resolve()),
    ]


def to_wsl(p: Path) -> str:
    s = str(p.resolve()).replace("\\", "/")
    if len(s) > 1 and s[1] == ":":
        s = f"/mnt/{s[0].lower()}{s[2:]}"
    return s


def run_native(target_class: str, blob: Path, timeout: int):
    t0 = time.time()
    try:
        r = subprocess.run(
            jazzer_cmd(target_class, blob),
            capture_output=True, timeout=timeout, cwd=str(PROJECT_ROOT),
        )
        return r.returncode, (r.stderr or b"") + (r.stdout or b""), time.time() - t0
    except subprocess.TimeoutExpired as e:
        out = (e.stderr or b"") + (e.stdout or b"")
        return 70, out, time.time() - t0


def run_wsl(target_class: str, blob: Path, timeout: int):
    cmd = ["wsl", "--"] + jazzer_cmd(target_class, blob)
    # Translate the two path args
    cmd = [to_wsl(Path(c)) if Path(c).exists() else c for c in cmd]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode, (r.stderr or b"") + (r.stdout or b""), time.time() - t0
    except subprocess.TimeoutExpired as e:
        return 70, (e.stderr or b"") + (e.stdout or b""), time.time() - t0


def run_docker(image: str, target_class: str, blob: Path, timeout: int):
    blob_dir = blob.parent.resolve()
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{PROJECT_ROOT}:/app:ro",
        "-v", f"{blob_dir}:/in:ro",
        "-w", "/app",
        image,
        "java", "-cp",
        f"/app/jazzer/jazzer_standalone.jar:/app/workspace/build/classes:/app/workspace/build/deps/*",
        "com.code_intelligence.jazzer.Jazzer",
        f"--target_class={target_class}",
        "--keep_going=1",
        f"/in/{blob.name}",
    ]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode, (r.stderr or b"") + (r.stdout or b""), time.time() - t0
    except subprocess.TimeoutExpired as e:
        return 70, (e.stderr or b"") + (e.stdout or b""), time.time() - t0


def is_jazzer_finding(rc: int, log: bytes) -> bool:
    if rc in CRASH_CODES:
        return True
    # Jazzer can also exit 0 in a few configurations and surface findings via
    # the log; the "FuzzerSecurityIssue*" markers are authoritative.
    return b"FuzzerSecurityIssue" in log or b"Java Exception" in log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", required=True,
                    help="Fully-qualified target class, e.g. com.example.fuzz.DemoFuzzer")
    ap.add_argument("--blob", required=True)
    ap.add_argument("--backend", default=os.environ.get("REPRODUCE_BACKEND", "native"))
    ap.add_argument("--image", default="claude-java-vuln-hunter-runner:latest")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    blob = Path(args.blob)
    if not blob.exists():
        print(json.dumps({"error": f"blob not found: {blob}"}))
        sys.exit(2)

    if args.backend == "wsl":
        rc, log, dur = run_wsl(args.harness, blob, args.timeout)
    elif args.backend == "docker":
        rc, log, dur = run_docker(args.image, args.harness, blob, args.timeout)
    else:
        rc, log, dur = run_native(args.harness, blob, args.timeout)

    log_path = blob.with_suffix(".log")
    log_path.write_bytes(log)

    print(json.dumps({
        "exit_code": rc,
        "is_crash": is_jazzer_finding(rc, log),
        "crash_log_path": str(log_path),
        "duration_s": round(dur, 3),
        "language": "jvm",
        "harness_class": args.harness,
    }))


if __name__ == "__main__":
    main()
