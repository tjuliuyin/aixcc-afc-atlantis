# Claude Vuln Hunter

A single-machine, Claude Code–driven vulnerability miner that reproduces the
core of Team Atlanta's **Atlantis** CRS: LLM-driven *discovery* (harness
understanding → sink detection → path analysis → PoV generation) gated by a
**deterministic confirmation pipeline** (compile + reproduce + crash-parse +
dedup). No Kubernetes, Azure, Redis, or LiteLLM gateway — state is a single JSON
file and the orchestration is done by Claude Code subagents.

> Design principle (from Atlantis): **LLM 排查，工具确认** — the model finds and
> generates; only `tools/reproduce.py` (real sanitizer exit code) confirms a bug.

## What maps to what

| Atlantis component | Here |
|---|---|
| crs_webserver + cp_manager orchestration | Claude Code + `/hunt` command + `CLAUDE.md` |
| CPUA (harness understanding) | `.claude/agents/harness-understander.md` |
| BCDA sink detection | `.claude/agents/sink-finder.md` |
| BCDA classify + key conditions | `.claude/agents/path-analyzer.md` |
| BGA / GeneratorAgent (PoV) | `.claude/agents/pov-generator.md` |
| CP.reproduce + pov_dedup | `tools/reproduce.py` + `parse_crash.py` + `dedup.py` |
| Redis state bus | `workspace/state.json` + `tools/state.py` |
| Joern/CodeQL code index | `tools/codeindex.py` (tree-sitter, regex fallback) |
| LiteLLM multi-model budget | per-agent `model:` frontmatter (sonnet/haiku) |

## Requirements

- **Claude Code** CLI
- **A Linux toolchain** to compile + run the harness with a sanitizer:
  - Windows: install **WSL2 (Ubuntu)**, then inside it `sudo apt install -y clang lldb`
    (or `gcc`); set `REPRODUCE_BACKEND=wsl`.
  - Linux/macOS-with-docker: `clang` or `gcc` with ASAN; `REPRODUCE_BACKEND=native`.
  - Or Docker Desktop: build a runner image and use `REPRODUCE_BACKEND=docker`.
- Python 3.9+ (`pip install -r requirements.txt`; tree-sitter optional).

The bundled demo target builds even **without** the libFuzzer runtime — the
build script falls back to a standalone ASAN driver (plain `gcc -fsanitize=address`).

## Quick start (5 minutes)

```bash
# 0. (Windows only) open WSL Ubuntu and cd into this folder via /mnt/c/...
pip install -r requirements.txt          # optional; demo works without it

# 1. Smoke-test the deterministic pipeline (NO LLM, no tokens spent)
bash run_demo.sh
#    -> builds harness, indexes code, reproduces a benign seed (no crash),
#       crafts a PoV, reproduces it (heap-buffer-overflow, exit 1),
#       parses + dedups the crash. If this passes, your env is ready.

# 2. Run the real agent pipeline
claude
> /index            # build/refresh the code index
> /hunt harness     # full discovery -> PoV -> verify loop
> /status           # see BITs, verified PoVs, dedup groups
```

On a successful hunt, Claude writes `workspace/report.md` with one section per
verified PoV: vuln type, `file:line`, call chain, crash-log excerpt, blob path,
and the key conditions that gate the bug.

## Bring your own target

1. Drop source into `workspace/target/`.
2. Write/compile a libFuzzer-style harness into `workspace/harness/` exposing
   `int LLVMFuzzerTestOneInput(const uint8_t*, size_t)`. Edit
   `workspace/harness/build.sh` to add your source files.
3. Put initial seeds in `workspace/corpus/`.
4. `claude` → `/index` → `/hunt <harness-name>`.

For JVM targets, compile with Jazzer, set the harness path accordingly, and add
a `--backend jazzer-wsl` branch in `tools/reproduce.py` (template noted in code).

## The pipeline (single machine)

```
/hunt harness
 ├─ codeindex.py            (functions.json — replaces Joern/CodeQL)
 ├─ harness-understander    (CPUA: entry + target fns + tainted args)
 ├─ sink-finder  × N (∥)    (BCDA SINK_DETECT: per-function sink + sanitizer)
 ├─ path-analyzer × M       (BCDA CLASSIFY: BIT + key_conditions + reachability)
 ├─ pov-generator × M       (BGA: writes gen.py -> blob.bin)
 │    └─ crash-verifier      (reproduce.py -> parse_crash.py -> dedup.py)
 │         └─ feedback loop (≤ iteration_budget) on no-crash
 └─ report.md
```

## Files

```
CLAUDE.md                 project charter (auto-loaded by Claude Code)
run_demo.sh               deterministic, token-free smoke test
.claude/
  settings.json           tool/permission allowlist
  agents/*.md             5 subagents (the pipeline stages)
  commands/*.md           /index /hunt /verify /status
  skills/sanitizer-lore/  sanitizer dictionary + exploit hints
tools/
  codeindex.py            function index (tree-sitter | regex fallback)
  reproduce.py            run blob through harness (native|wsl|docker)
  parse_crash.py          ASAN/Jazzer log -> structured callstack
  dedup.py                new-vs-duplicate crash grouping
  state.py                file-backed state (replaces Redis)
workspace/
  target/parser.c         demo target with a gated heap-buffer-overflow
  harness/harness.c       libFuzzer harness (+ standalone_driver.c fallback)
  corpus/seed1.bin        benign seed
```

## Safety / scope

This is for **authorized** security testing, CTFs, and research on code you own
or are permitted to test. The demo target is intentionally vulnerable and
self-contained.
