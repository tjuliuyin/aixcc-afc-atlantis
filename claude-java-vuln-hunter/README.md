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

# 3. interactive Claude Code agent — does the real hunt
claude
> /hunt
```

On a successful hunt, Claude writes `workspace/report.md` with one section per
verified PoV: `vuln_type`, `class.method file:line`, call chain, log excerpt,
blob path, and the key conditions that gate the bug.

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
/hunt
 ├─ codeindex.py            (functions.json — replaces Joern/CodeQL)
 ├─ harness-understander    (CPUA: entry + targets + tainted args + routing)
 ├─ sink-finder  × N (∥)    (BCDA SINK_DETECT: per-method sink + sanitizer)
 ├─ path-analyzer × M       (BCDA CLASSIFY: BIT + key_conditions)
 ├─ pov-generator × M       (BGA: writes gen.py using tools/fdp_builder.py)
 │    └─ crash-verifier      (reproduce.py → parse_crash.py → dedup.py)
 │         └─ feedback loop (≤ iteration_budget) on no-crash
 └─ report.md
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

1. Drop your source under `workspace/target/<project>/`.
2. Write a Jazzer harness in `workspace/harness/src/main/java/...`:
   ```java
   import com.code_intelligence.jazzer.api.FuzzedDataProvider;
   public class MyFuzzer {
       public static void fuzzerTestOneInput(FuzzedDataProvider data) {
           // call your target API with FDP-derived inputs
       }
   }
   ```
3. Add any 3rd-party jars to `workspace/build/deps/` or extend
   `workspace/harness/build.sh` to fetch them.
4. Put initial seeds in `workspace/corpus/`.
5. `claude` → `/hunt <fully-qualified harness class>`.

The agent will:
- index your sources (`tools/codeindex.py`)
- understand your harness (CPUA-style)
- find sinks Jazzer can detect (see `.claude/skills/java-sinks/SKILL.md`)
- build PoVs with `tools/fdp_builder.py`
- verify each PoV against the real Jazzer + your build
- write `workspace/report.md`

## Repository layout

```
CLAUDE.md                 project charter (Claude Code auto-loads)
setup.sh                  one-shot installer (Jazzer + javalang + first build)
run_demo.sh               token-free deterministic smoke test
.claude/
  settings.json           tool/permission allowlist
  agents/*.md             5 subagents (the pipeline stages)
  commands/*.md           /index /hunt /verify /status
  skills/
    sanitizer-lore/       Jazzer sanitizer dictionary + exploit hints
    java-sinks/           catalogue of dangerous Java APIs by sanitizer family
    jazzer-fdp/           how to assemble FuzzedDataProvider blobs
tools/
  codeindex.py            Java method index (javalang -> tree-sitter -> regex)
  reproduce.py            run a blob through Jazzer (native/wsl/docker)
  parse_crash.py          Jazzer log -> structured callstack + sanitizer name
  dedup.py                new-vs-duplicate crash grouping
  state.py                file-backed state (replaces Redis)
  fdp_builder.py          deterministic FuzzedDataProvider blob assembler
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
