---
description: Full auto pipeline — build, index, LLM-guided PoV hunt AND a
  coverage-guided Jazzer campaign, then triage + report. The most complete run.
argument-hint: "[harness-class] [campaign-seconds, default 120]"
---

Run the FULL hunt+fuzz campaign.
Harness: ${1:-com.example.fuzz.DemoFuzzer}   Campaign budget: ${2:-120}s

Steps (follow CLAUDE.md; this combines LLM discovery with real fuzzing):

1. Ensure environment: if `jazzer/jazzer_standalone.jar` missing → `bash setup.sh`.
2. Build the target: `python tools/build_target.py` (handles Maven/Gradle/demo).
3. Index: if `workspace/index/functions.json` stale → `python tools/codeindex.py workspace/target`.
4. If `workspace/harness/src` has no usable `fuzzerTestOneInput`, delegate to
   `harness-generator` first.
5. Kick off the coverage-guided campaign IN THE BACKGROUND (run_in_background):
   `python tools/fuzz.py --harness ${1:-com.example.fuzz.DemoFuzzer} --seconds ${2:-120} --jobs 4`
6. MEANWHILE run the LLM-guided hunt: `harness-understander` → parallel
   `sink-finder` → `path-analyzer` → `pov-generator` (each calls `crash-verifier`).
   Both halves share `workspace/state.json` dedup groups, so a PoV found by one
   won't be double-counted by the other.
7. When the background campaign finishes, incorporate its triage summary.
8. Generate the report deterministically:
   `python tools/report.py --harness ${1:-com.example.fuzz.DemoFuzzer}`
9. Print: verified PoV count, distinct groups, and `workspace/report.md` path.

Give 1–2 sentence progress updates between phases. Do not block waiting on the
background campaign — interleave the LLM hunt while it runs.
