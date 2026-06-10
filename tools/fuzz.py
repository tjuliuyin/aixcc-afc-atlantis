#!/usr/bin/env python3
"""Run a coverage-guided Jazzer fuzzing campaign and auto-triage crashes.

This is the Atlantis "ensemble fuzzing" half: while the LLM agents reason out
targeted PoVs, this runs an actual coverage-guided campaign that can surface
crashes nobody anticipated. Every crash it finds is triaged through the SAME
deterministic gate (parse_crash + dedup) so it shares the dedup groups with
the LLM-found PoVs.

Outputs:
  workspace/pov/campaign/<sanitizer>-<sig>/blob.bin   (one per NEW group)
  workspace/pov/campaign/<sanitizer>-<sig>/blob.log
  workspace/pov/campaign/<sanitizer>-<sig>/parsed.json
  + appends to state.json verified_povs / groups

Backends mirror reproduce.py (native | wsl | docker). Honors REPRODUCE_BACKEND.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JAZZER_JAR = PROJECT_ROOT / "jazzer" / "jazzer_standalone.jar"
BUILD_DIR = PROJECT_ROOT / "workspace" / "build"
CLASSES_DIR = BUILD_DIR / "classes"
DEPS_DIR = BUILD_DIR / "deps"
CORPUS_DIR = PROJECT_ROOT / "workspace" / "corpus"
CAMPAIGN_DIR = PROJECT_ROOT / "workspace" / "pov" / "campaign"
TOOLS = PROJECT_ROOT / "tools"


def classpath() -> str:
    cp_file = BUILD_DIR / "cp.txt"
    if cp_file.exists():
        cp = cp_file.read_text().strip()
        if cp:
            return cp
    parts = [str(JAZZER_JAR), str(CLASSES_DIR)]
    if DEPS_DIR.exists():
        parts += [str(j) for j in sorted(DEPS_DIR.glob("*.jar"))]
    # os.pathsep is ':' on Unix and ';' on Windows — required for native Windows.
    return os.pathsep.join(parts)


def run_tool(script: str, *args) -> dict:
    """Invoke one of our deterministic tools and parse its JSON stdout."""
    cmd = [sys.executable, str(TOOLS / script), *map(str, args)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    out = (r.stdout or "").strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"_raw": out, "_stderr": r.stderr}


def run_campaign(target_class: str, seconds: int, workdir: Path, jobs: int) -> list[Path]:
    """Run Jazzer in fuzzing mode; return the list of crash-* artifacts found."""
    workdir.mkdir(parents=True, exist_ok=True)
    run_corpus = workdir / "corpus"
    run_corpus.mkdir(exist_ok=True)
    # seed the run corpus from workspace/corpus (flat files only)
    if CORPUS_DIR.exists():
        for f in CORPUS_DIR.rglob("*"):
            if f.is_file() and f.name != ".gitkeep":
                shutil.copy(f, run_corpus / f.name)

    cmd = [
        "java", "-cp", classpath(),
        "com.code_intelligence.jazzer.Jazzer",
        f"--target_class={target_class}",
        f"-max_total_time={seconds}",
        "-ignore_crashes=1",                 # keep going past the first finding
        f"-artifact_prefix={workdir}/",      # where crash-* get written
        "-print_final_stats=1",
        str(run_corpus),
    ]
    if jobs > 1:
        cmd.insert(-1, f"-fork={jobs}")
        cmd.insert(-1, "-ignore_ooms=1")
        cmd.insert(-1, "-ignore_timeouts=1")

    print(f"[fuzz] campaign: {target_class} for {seconds}s (jobs={jobs})", flush=True)
    t0 = time.time()
    try:
        subprocess.run(cmd, cwd=str(workdir), timeout=seconds + 120,
                       capture_output=True)
    except subprocess.TimeoutExpired:
        pass
    dur = time.time() - t0
    crashes = sorted(workdir.glob("crash-*"))
    print(f"[fuzz] done in {dur:.0f}s, {len(crashes)} crash artifact(s)", flush=True)
    return crashes


def triage(target_class: str, crashes: list[Path], backend: str) -> dict:
    """Reproduce + parse + dedup each crash; persist NEW groups as PoVs."""
    CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
    summary = {"total": len(crashes), "new": [], "duplicate": 0, "not_a_crash": 0}

    for crash in crashes:
        rep = run_tool("reproduce.py", "--harness", target_class,
                       "--blob", crash, "--backend", backend, "--timeout", "60")
        if not rep.get("is_crash"):
            summary["not_a_crash"] += 1
            continue
        parsed_path = crash.with_suffix(".parsed.json")
        parsed = run_tool("parse_crash.py", rep["crash_log_path"])
        parsed_path.write_text(json.dumps(parsed, indent=2))
        dd = run_tool("dedup.py", "--new", parsed_path)
        if dd.get("is_new"):
            san = parsed.get("sanitizer") or "unknown"
            sig = dd.get("group_id")
            dest = CAMPAIGN_DIR / f"{san}-g{sig}"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy(crash, dest / "blob.bin")
            shutil.copy(rep["crash_log_path"], dest / "blob.log")
            (dest / "parsed.json").write_text(json.dumps(parsed, indent=2))
            run_tool("state.py", "append", "verified_povs", json.dumps({
                "source": "campaign",
                "sanitizer": san,
                "group_id": sig,
                "blob": str(dest / "blob.bin"),
                "harness": target_class,
            }))
            summary["new"].append({"sanitizer": san, "group_id": sig,
                                   "blob": str(dest / "blob.bin")})
            print(f"[fuzz] NEW: {san} (group {sig}) -> {dest/'blob.bin'}", flush=True)
        else:
            summary["duplicate"] += 1
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", required=True,
                    help="Fully-qualified Jazzer target class")
    ap.add_argument("--seconds", type=int, default=60, help="campaign duration")
    ap.add_argument("--jobs", type=int, default=1, help="parallel forks")
    ap.add_argument("--backend", default=os.environ.get("REPRODUCE_BACKEND", "native"))
    ap.add_argument("--workdir", default=None)
    args = ap.parse_args()

    workdir = Path(args.workdir) if args.workdir else (
        PROJECT_ROOT / "workspace" / "pov" / "_campaign_work")
    crashes = run_campaign(args.harness, args.seconds, workdir, args.jobs)
    summary = triage(args.harness, crashes, args.backend)
    print(json.dumps({"campaign_summary": summary}, indent=2))


if __name__ == "__main__":
    main()
