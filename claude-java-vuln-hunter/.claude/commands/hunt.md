---
description: LLM-guided targeted PoV hunt (no fuzzing campaign). Use /campaign
  for hunt + coverage-guided fuzzing together.
argument-hint: "[harness-class, default: com.example.fuzz.DemoFuzzer]"
---

Run the LLM-guided hunt for harness class: ${1:-com.example.fuzz.DemoFuzzer}

Follow `CLAUDE.md` strictly, in order:

1. If `jazzer/jazzer_standalone.jar` missing → `bash setup.sh`.
2. Build target: `python tools/build_target.py` (Maven/Gradle/demo auto-detect).
3. If `workspace/index/functions.json` missing/stale →
   `python tools/codeindex.py workspace/target`.
4. If `workspace/harness/src` has no usable `fuzzerTestOneInput`, delegate to
   `harness-generator` first.
5. Spawn `harness-understander` on the harness source. Get target methods.
6. For EACH target method, spawn `sink-finder` IN PARALLEL (one message,
   multiple Task calls). Collect sinks with `is_vulnerable=true`.
7. For each such sink, spawn `path-analyzer` to produce a BIT.
8. For each BIT, spawn `pov-generator` (it calls `crash-verifier` and iterates
   up to `iteration_budget`).
9. Generate the report: `python tools/report.py --harness ${1:-com.example.fuzz.DemoFuzzer}`.

Give 1–2 sentence progress updates between steps. End with verified PoV count
and the `workspace/report.md` path.
