# Vuln Hunter — Project Charter

You orchestrate an Atlantis-style vulnerability-mining pipeline on a single
local host (Windows+WSL, Linux, or Docker). This file is auto-loaded; follow it.

Layout:
- `workspace/target/`  — source under analysis
- `workspace/harness/` — fuzz harness src + built `harness` binary
- `workspace/corpus/`  — initial seeds
- `workspace/index/`   — `functions.json` (code index)
- `workspace/findings/`— `harness.json`, `sinks.json`, `bits.json`
- `workspace/pov/`     — candidate generators, blobs, crash logs
- `workspace/state.json` — single source of truth (replaces Redis)
- `tools/`             — deterministic Python tools (do not let LLM replace them)

## Pipeline (run in order; this is the Atlantis flow, single-machine)

1. **Index** — if `workspace/index/functions.json` is missing/stale, run
   `python tools/codeindex.py workspace/target`.
2. **Understand harness** — delegate to subagent `harness-understander`.
   Output `workspace/findings/harness.json`:
   `{entry, target_functions:[{name,file,line}], tainted_args, call_chain}`.
3. **Find sinks** — for each target function, delegate to `sink-finder`
   (spawn in PARALLEL). Append results to `workspace/findings/sinks.json`.
4. **Path analysis** — for each sink with `is_vulnerable=true`, delegate to
   `path-analyzer`. Output BITs to `workspace/findings/bits.json`:
   `{bit_id, vuln_type, sink_line, file, line, call_path, key_conditions,
     tainted_args, required_files, sanitizer}`.
5. **PoV generation** — for each BIT, delegate to `pov-generator`. It writes
   `workspace/pov/<bit_id>/iter_N/gen.py`, runs it, and calls `crash-verifier`.
   On no-crash it iterates with feedback, max `iteration_budget` (default 5).
6. **Report** — write `workspace/report.md`, one section per verified PoV.

## Hard rules (LLM排查, 工具确认 — separation of concerns)

- **No vulnerability is "real" until `tools/reproduce.py` returns exit_code in
  {1,70,71,77}.** LLM judgment alone never confirms a crash.
- **Verify every function name** against `workspace/index/functions.json` before
  quoting it in a prompt. If absent, Grep and re-resolve. Never invent symbols.
- **Cite `file:line`** when reasoning about code.
- **Feed failure back**: when a blob does not crash, pass the verifier's
  `coverage_hint` / last-reached info into the next `pov-generator` round.
- **Dedup before claiming**: `tools/dedup.py` decides new vs duplicate group.
- **Budget**: stop a BIT after 5 failed iterations; record in
  `failed_attempts/<bit_id>` via `tools/state.py`.

## State access

Use `python tools/state.py {get|set|incr|append|dump|reset} <path> [value]`
rather than editing `state.json` by hand. Paths use `/` (e.g.
`failed_attempts/bit_0`).

## Backends

`tools/reproduce.py --backend {native|wsl|docker}` (env `REPRODUCE_BACKEND`).
On Windows default to `wsl`; on Linux/container default to `native`.
