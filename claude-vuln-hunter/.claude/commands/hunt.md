---
description: Run the full vulnerability hunting pipeline against a harness.
argument-hint: "[harness-name, default: harness]"
---

Run the end-to-end hunt for harness: ${1:-harness}

Follow `CLAUDE.md`'s pipeline strictly, in order:

1. Ensure `workspace/index/functions.json` exists and is newer than
   `workspace/target/`. If not, run `python tools/codeindex.py workspace/target`.
2. Ensure `workspace/harness/harness` exists. If not, run
   `bash workspace/harness/build.sh`.
3. Spawn `harness-understander` on `workspace/harness/${1:-harness}.c`.
4. For EACH target function found, spawn `sink-finder` IN PARALLEL (one message,
   multiple Task calls). Collect sinks with is_vulnerable=true.
5. For each such sink, spawn `path-analyzer` to produce a BIT.
6. For each BIT, spawn `pov-generator` (it calls `crash-verifier` and iterates
   up to the budget).
7. Write `workspace/report.md` summarizing every verified_new PoV.

Between steps, give a 1–2 sentence progress update. Do not narrate internal
chain-of-thought. End by printing the verified PoV count and report path.
