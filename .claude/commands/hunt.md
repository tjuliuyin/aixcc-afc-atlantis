---
description: Run the full Java vulnerability hunting pipeline.
argument-hint: "[harness-class, default: com.example.fuzz.DemoFuzzer]"
---

Run end-to-end hunt for harness class: ${1:-com.example.fuzz.DemoFuzzer}

Follow `CLAUDE.md` strictly, in order:

1. If `jazzer/jazzer_standalone.jar` missing → `bash setup.sh`.
2. If `workspace/build/classes` missing/stale → `bash workspace/harness/build.sh`.
3. If `workspace/index/functions.json` missing/stale →
   `python tools/codeindex.py workspace/target`.
4. Spawn `harness-understander` on the harness source file. Get target methods.
5. For EACH target method, spawn `sink-finder` IN PARALLEL (one message,
   multiple Task calls). Collect sinks with `is_vulnerable=true`.
6. For each such sink, spawn `path-analyzer` to produce a BIT.
7. For each BIT, spawn `pov-generator` (it calls `crash-verifier` and iterates
   up to `iteration_budget`).
8. After all BITs are processed, write `workspace/report.md` with one section
   per verified PoV: vuln_type, class.method file:line, call chain, log
   excerpt, blob path, key conditions.

Give 1–2 sentence progress updates between steps. End with verified PoV count
and report path.
