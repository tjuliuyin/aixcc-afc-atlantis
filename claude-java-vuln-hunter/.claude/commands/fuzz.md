---
description: Run only a coverage-guided Jazzer fuzzing campaign and auto-triage.
argument-hint: "[harness-class] [seconds, default 120] [jobs, default 4]"
---

Run a fuzzing campaign for: ${1:-com.example.fuzz.DemoFuzzer}

1. Ensure built: `python tools/build_target.py` if `workspace/build/classes` missing/stale.
2. Run: `python tools/fuzz.py --harness ${1:-com.example.fuzz.DemoFuzzer} --seconds ${2:-120} --jobs ${3:-4}`
   It runs Jazzer in coverage-guided mode, then reproduces + parses + dedups
   every crash, persisting NEW groups to `workspace/state.json` and
   `workspace/pov/campaign/`.
3. Report the campaign_summary JSON (total / new / duplicate / not_a_crash).
4. Optionally run `python tools/report.py` to refresh `workspace/report.md`.

This is the deterministic fuzzing half — no LLM PoV reasoning. Use `/hunt` for
LLM-guided targeted PoVs or `/campaign` for both together.
