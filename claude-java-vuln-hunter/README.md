# Claude Java Vuln Hunter

A single-machine, Claude Code–driven **Java** vulnerability mining tool that
replicates the core of Team Atlanta's **Atlantis** CRS: LLM-driven *discovery*
(harness understanding → sink detection → path analysis → PoV generation)
gated by a **deterministic confirmation pipeline** (compile + Jazzer reproduce
+ crash parse + dedup). No Kubernetes, Azure, Redis, or LiteLLM gateway —
state is a single JSON file and the orchestration is done by Claude Code
subagents.

Atlantis design principle preserved: **LLM 排查, 工具确认** — the model finds
and generates; only `tools/reproduce.py` (real sanitizer exit code) confirms.

## Quick start (3 commands)

```bash
# 1. one-time environment setup (downloads Jazzer, installs javalang, builds)
bash setup.sh

# 2. token-free deterministic smoke test — verifies your env can find PoVs
bash run_demo.sh
#    => 3/3 PoVs verified: rce, os-command-injection, sql-injection
#       + workspace/report.md generated

# 3. interactive Claude Code agent — does the real hunt
claude
> /campaign          # LLM PoV hunt + real coverage-guided fuzzing, then report
```

On a successful run, the report tool writes `workspace/report.md` with one
section per verified PoV: `vuln_type`, `class.method file:line`, call chain,
log excerpt, blob path, and the key conditions that gate the bug.

## Commands

| Command | What it does |
|---------|--------------|
| `/campaign [class] [secs]` | **Full run** — build + index + (auto-harness) + LLM PoV hunt **and** a coverage-guided Jazzer campaign in parallel, then triage + report. |
| `/hunt [class]`            | LLM-guided **targeted** PoVs only (no fuzzing campaign). |
| `/fuzz [class] [secs] [jobs]` | Coverage-guided Jazzer **campaign** + auto-triage only. |
| `/genharness [target]`    | Auto-write a Jazzer harness for a target class/method. |
| `/verify <blob> [class]`  | Reproduce + parse + dedup a single blob. |
| `/index`, `/status`       | Refresh the code index; show current hunt state. |

The two discovery halves — LLM-guided targeted PoVs and the blind coverage
campaign — **share the same dedup groups** (`workspace/state.json`), so a bug
found by one is never double-counted by the other. This mirrors Atlantis'
ensemble of directed analysis + brute fuzzing.

## What works out of the box

The bundled demo target (`workspace/target/demo-app/`) contains three
deliberately vulnerable Java classes, plus a Jazzer harness that routes input
to each via a leading selector byte. After `bash run_demo.sh` you will see all
three confirmed with real Jazzer sanitizer findings:

| Selector | Target              | Vulnerability         | Sanitizer marker                                         |
|---------:|---------------------|-----------------------|----------------------------------------------------------|
| 0        | `PluginLoader.resolve`  | Reflective Call / RCE | `FuzzerSecurityIssueHigh: Remote Code Execution`         |
| 1        | `CommandRunner.runTool` | OS Command Injection  | `FuzzerSecurityIssueCritical: OS Command Injection`      |
| 2        | `SqlQuery.lookupUser`   | SQL Injection         | `FuzzerSecurityIssueHigh: SQL Injection`                 |

## What the agent actually does

```
/campaign
 ├─ build_target.py         (Maven/Gradle/jar/javac → classes + cp.txt)
 ├─ codeindex.py            (functions.json — replaces Joern/CodeQL)
 ├─ harness-generator       (auto-write a Jazzer harness if none exists)
 ├──────────────────────────── two halves run together ────────────────────────
 │  A) LLM-guided (directed):                B) coverage-guided (brute):
 │   harness-understander  (CPUA)             fuzz.py  → Jazzer campaign
 │   sink-finder  × N (∥)  (BCDA sink)          ↓ per crash
 │   path-analyzer × M     (BCDA classify)     reproduce → parse_crash → dedup
 │   pov-generator × M     (BGA + fdp_builder)
 │     └─ crash-verifier   (reproduce → parse_crash → dedup)
 │          └─ feedback loop (≤ iteration_budget) on no-crash
 └─ report.py               (shared dedup groups → workspace/report.md)
```

## Atlantis → Claude Code mapping

| Atlantis component                | Here                                                      |
|-----------------------------------|-----------------------------------------------------------|
| crs_webserver + cp_manager        | Claude Code + `CLAUDE.md` + `/hunt`                       |
| CPUA (harness understanding)      | `.claude/agents/harness-understander.md`                  |
| BCDA sink detection               | `.claude/agents/sink-finder.md`                           |
| BCDA classify + key conditions    | `.claude/agents/path-analyzer.md`                         |
| BGA / GeneratorAgent (PoV)        | `.claude/agents/pov-generator.md` + `tools/fdp_builder.py`|
| CP.reproduce + pov_dedup          | `tools/reproduce.py` + `parse_crash.py` + `dedup.py`      |
| Redis state bus                   | `workspace/state.json` + `tools/state.py`                 |
| Joern/CodeQL code index           | `tools/codeindex.py` (javalang, tree-sitter, regex)        |
| LiteLLM multi-model budget        | per-agent `model:` frontmatter (sonnet/haiku)             |
| Jazzer (the fuzzer)               | `jazzer/jazzer_standalone.jar` (fetched by setup.sh)      |

## Requirements

- **JDK 17+** (Temurin, OpenJDK, etc.). `setup.sh` checks for `java`/`javac`.
- **Python 3.9+**.
- **Internet access** at setup time to download Jazzer + H2 + javalang.
- One execution backend:
  - **native** (default) — works on Linux/WSL2 with JDK installed
  - **wsl** — for Windows hosts running `claude` natively; runs Jazzer in WSL
  - **docker** — uses the bundled `docker/Dockerfile.runner` image

### On Windows

```powershell
# install WSL2 + Ubuntu (one time)
wsl --install -d Ubuntu-22.04
wsl sudo apt install -y openjdk-21-jdk python3 python3-pip

# clone/copy this project somewhere accessible from both Windows and WSL
cd C:\path\to\claude-java-vuln-hunter

# from PowerShell or WSL:
wsl bash setup.sh
wsl bash run_demo.sh
$Env:REPRODUCE_BACKEND="wsl"  # tell reproduce.py to bridge through WSL
claude
```

### On Linux / macOS-with-Docker

```bash
bash setup.sh
bash run_demo.sh
claude
```

### Air-gapped Docker

```bash
docker build -t claude-java-vuln-hunter-runner:latest -f docker/Dockerfile.runner .
export REPRODUCE_BACKEND=docker
claude
```

## Bring your own Java target

### Option A — a real Maven / Gradle project (recommended)

```bash
# 1. put the whole project under workspace/target/
cp -r ~/my-java-project workspace/target/

# 2. let the agent build it, generate a harness, and hunt
claude
> /genharness com.acme.parser.RequestParser.parse   # auto-writes a harness
> /campaign com.example.fuzz.RequestParserFuzzer 300 # 5-min hunt + fuzz
```

`tools/build_target.py` auto-detects `pom.xml` / `build.gradle`, runs
`mvn package` / `gradle build`, copies the dependency jars into
`workspace/build/deps/`, and writes the full classpath to
`workspace/build/cp.txt` (which `reproduce.py` and `fuzz.py` use). No manual
classpath wrangling.

### Option B — provide your own harness

1. Drop your source/jars under `workspace/target/<project>/`.
2. Write a Jazzer harness in
   `workspace/harness/src/main/java/com/example/fuzz/MyFuzzer.java`:
   ```java
   import com.code_intelligence.jazzer.api.FuzzedDataProvider;
   public class MyFuzzer {
       public static void fuzzerTestOneInput(FuzzedDataProvider data) {
           // call your target API with FDP-derived inputs;
           // catch ONLY business exceptions, never Throwable.
       }
   }
   ```
3. Prebuilt 3rd-party jars: drop them anywhere under `workspace/target/`
   (build_target.py collects every `*.jar`) — or add fetch logic to it.
4. Put initial seeds in `workspace/corpus/` (optional; speeds up the campaign).
5. `claude` → `/campaign com.example.fuzz.MyFuzzer`.

In both cases the agent will: build the target → index your sources
(`tools/codeindex.py`) → (auto-generate or understand the harness) → find
Jazzer-detectable sinks (`.claude/skills/java-sinks/SKILL.md`) → craft PoVs
with `tools/fdp_builder.py` → run a coverage-guided campaign
(`tools/fuzz.py`) → verify everything against the real Jazzer + your build →
write `workspace/report.md`.

### Letting the agent write the harness for you

If you don't want to hand-write a harness, just run `/genharness` with a target
class or method (or no argument — it will pick the public methods most likely
to reach a dangerous sink). The `harness-generator` subagent writes a
compilable `fuzzerTestOneInput`, builds it, smoke-tests that it runs, and
records it in `workspace/findings/harness.json` for the rest of the pipeline.

## Repository layout

```
CLAUDE.md                 project charter (Claude Code auto-loads)
setup.sh                  one-shot installer (Jazzer + javalang + first build)
run_demo.sh               token-free deterministic smoke test
.claude/
  settings.json           tool/permission allowlist
  agents/*.md             6 subagents (harness-generator + the 5 pipeline stages)
  commands/*.md           /campaign /hunt /fuzz /genharness /verify /index /status
  skills/
    sanitizer-lore/       Jazzer sanitizer dictionary + exploit hints
    java-sinks/           catalogue of dangerous Java APIs by sanitizer family
    jazzer-fdp/           how to assemble FuzzedDataProvider blobs
tools/
  build_target.py         Maven/Gradle/jar/javac auto-build -> classes + cp.txt
  codeindex.py            Java method index (javalang -> tree-sitter -> regex)
  reproduce.py            run one blob through Jazzer (native/wsl/docker)
  fuzz.py                 coverage-guided Jazzer campaign + auto-triage
  parse_crash.py          Jazzer log -> structured callstack + sanitizer name
  dedup.py                new-vs-duplicate crash grouping
  fdp_builder.py          deterministic FuzzedDataProvider blob assembler
  report.py               render workspace/report.md from state
  state.py                file-backed state (replaces Redis)
jazzer/                   downloaded standalone Jazzer JAR (by setup.sh)
docker/
  Dockerfile.runner       self-contained JDK + Jazzer + project image
  docker-compose.yml      convenience compose
workspace/
  target/demo-app/...     deliberately vulnerable demo classes
  harness/                Jazzer harness + build.sh (javac + auto-fetch H2)
  corpus/                 initial seeds
  index/                  generated functions.json
  findings/               harness.json + sinks.json + bits.json
  pov/                    candidate generators, blobs, crash logs
  state.json              all hunt state (replaces Redis)
```

## Safety / scope

This is for **authorized** security testing, CTFs, and research on code you
own or are permitted to test. The demo target is intentionally vulnerable and
self-contained. Jazzer's sanitizers stop short of full exploitation — they
detect the dangerous pattern, log a `FuzzerSecurityIssue`, and exit cleanly.

## Troubleshooting

- **`setup.sh` says "java not on PATH"**: install JDK 17+ first
  (`apt install openjdk-21-jdk` or download Temurin).
- **`reproduce.py` returns `is_crash=false` for a PoV you know works**: double
  check the byte layout with `tools/fdp_builder.py` — Jazzer FDP consumes
  fixed-size from the BACK, variable-size from the FRONT (see
  `.claude/skills/jazzer-fdp/SKILL.md`).
- **`codeindex.py` says "javalang unavailable"**: `pip install javalang` (or
  re-run `setup.sh`). The regex fallback still works for the demo but may miss
  exotic Java syntax.
- **Slow first run**: Jazzer downloads (~11 MB) and instruments the JDK + H2;
  first reproduce takes ~5 s, subsequent ones ~2 s.
