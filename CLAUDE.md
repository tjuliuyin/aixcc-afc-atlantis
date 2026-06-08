# Claude Java Vuln Hunter — Project Charter

You orchestrate an Atlantis-style **Java** vulnerability-mining pipeline on a
single local host (Windows+WSL, Linux, or Docker). Target = Java bytecode;
fuzzer = **Jazzer**; finding gate = real sanitizer exit code, not LLM opinion.

Layout:
- `workspace/target/`      — Java sources under analysis
- `workspace/harness/`     — Jazzer harness source(s)
- `workspace/build/`       — `classes/` and `deps/` produced by build.sh
- `workspace/corpus/`      — initial seed blobs
- `workspace/index/`       — `functions.json` (method-level index)
- `workspace/findings/`    — `harness.json`, `sinks.json`, `bits.json`
- `workspace/pov/`         — candidate generators, blobs, crash logs
- `workspace/state.json`   — single source of truth (replaces Redis)
- `jazzer/jazzer_standalone.jar` — fuzzer JAR (fetched by `setup.sh`)
- `tools/`                 — deterministic Python tools (DO NOT REPLACE)

## Pipeline (Atlantis flow, single-machine)

1. **Setup** — if `jazzer/jazzer_standalone.jar` missing, run `bash setup.sh`.
2. **Build** — run `bash workspace/harness/build.sh` if `workspace/build/classes`
   is missing or older than any source file. Produces `classes/` + `deps/`.
3. **Index** — if `workspace/index/functions.json` missing/stale, run
   `python tools/codeindex.py workspace/target`. Prefer the javalang backend.
4. **Understand harness** — delegate to subagent `harness-understander`. Reads
   the Jazzer harness source, identifies `fuzzerTestOneInput` (or
   `fuzzerTestOneInput(byte[])`), enumerates which project methods receive
   tainted input. Output: `workspace/findings/harness.json`.
5. **Find sinks** — for each target project method, spawn `sink-finder` IN
   PARALLEL (one message, multiple Task calls). Append to
   `workspace/findings/sinks.json`. Use `.claude/skills/java-sinks/SKILL.md`.
6. **Path analysis** — for each vulnerable sink, spawn `path-analyzer` to
   produce a `BugInducingThing` (BIT): `{bit_id, vuln_type, sink_method,
   class_fqn, file, line, call_path, key_conditions, harness_route,
   sanitizer, reachable}`. Output: `workspace/findings/bits.json`.
7. **PoV generation** — for each BIT, spawn `pov-generator`. It writes
   `workspace/pov/<bit_id>/iter_N/gen.py` (uses `tools/fdp_builder.py`),
   runs it to produce `blob.bin`, then delegates to `crash-verifier`. On
   no-crash it iterates with feedback, max `iteration_budget` (default 5).
8. **Report** — write `workspace/report.md` summarising every verified PoV.

## Hard rules (LLM 排查, 工具确认)

- **A vulnerability is NOT real until `tools/reproduce.py` reports
  `is_crash=true`**, which requires either exit_code in {1, 70, 71, 77} OR
  the Jazzer log containing `FuzzerSecurityIssue`. LLM judgement alone is
  never sufficient.
- **Verify every class/method name** against `workspace/index/functions.json`
  before quoting it in any prompt. Never invent symbols.
- **Cite `class.method file:line`** when reasoning about Java code.
- **Feed failure back**: when a blob does not crash, pass the verifier's
  `coverage_hint` and the failure analysis into the next `pov-generator`
  iteration; do not retry blindly.
- **Dedup before claiming**: `tools/dedup.py` decides new vs duplicate group.
- **Budget**: cap each BIT at `iteration_budget` failed attempts; record in
  `failed_attempts/<bit_id>` via `tools/state.py`.

## State access

Use `python tools/state.py {get|set|incr|append|dump|reset} <path> [value]`
rather than editing `state.json` by hand. Paths use `/` (e.g.
`failed_attempts/bit_0`).

## FDP byte assembly

Jazzer's `FuzzedDataProvider` consumes FIXED-SIZE primitives from the FRONT
and VARIABLE-SIZE values (consumeString, consumeRemainingAsString) from the
BACK. Use `tools/fdp_builder.py` (CLI or library) — DO NOT hand-pack bytes.
The skill `.claude/skills/jazzer-fdp/SKILL.md` has examples.

## Backends

`tools/reproduce.py --backend {native|wsl|docker}` (or env `REPRODUCE_BACKEND`).
- Linux/container: `native`
- Windows: `wsl` (default in settings.json on Windows)
- Air-gapped: `docker` with the bundled `docker/Dockerfile.runner` image.
