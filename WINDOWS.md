# Running claude-java-vuln-hunter on Windows

The project supports **three Windows execution paths**. Pick the one that
matches your environment:

| Mode | When to use | Pros | Cons |
|------|-------------|------|------|
| **A. PowerShell (native)** | You want everything in Windows; no WSL | Fastest setup if Python+JDK already installed | Path-sep / .cmd resolution had to be handled in code (now is) |
| **B. WSL2 Ubuntu** (recommended) | Production-style; same scripts as Linux | Identical to CI / cloud; bash scripts work | Requires WSL2; uses Linux JDK inside WSL |
| **C. Git Bash / MSYS2** | You already have Git for Windows | bash works; no WSL | Some Windows tools behave oddly under MSYS path translation |

Whichever you pick, **`tools/*.py` is pure Python and works on all three** —
the only OS-specific parts are the `.sh` / `.ps1` wrappers and how the JVM
sees the classpath (`:` vs `;`, fixed automatically via `os.pathsep`).

---

## Prerequisites (all modes)

- **JDK 17+** (Temurin recommended: https://adoptium.net). Verify:
  ```powershell
  java -version
  javac -version
  ```
- **Python 3.9+** (https://python.org). Verify:
  ```powershell
  python --version   # or:  py --version
  ```
- **Internet access** at setup time to download Jazzer (~11 MB), H2 (~2 MB),
  and the `javalang` Python package.
- (Maven/Gradle targets only) Maven 3.6+ or Gradle 7+ on PATH.

If `java` or `javac` is missing, the most common cause is having only a JRE,
or having Java installed but not added to `PATH`. Reopen PowerShell after
fixing PATH so the change takes effect.

---

## Mode A — Native PowerShell

Best for: a single Windows host where you'll run `claude` directly.

```powershell
# 1. clone / copy the project
cd C:\Users\you\src
git clone <your-repo> claude-java-vuln-hunter
cd claude-java-vuln-hunter

# 2. one-shot environment setup
pwsh -ExecutionPolicy Bypass -File .\setup.ps1
#  -> downloads jazzer\jazzer_standalone.jar
#  -> pip install --user javalang
#  -> compiles the demo target + harness

# 3. token-free deterministic smoke test
pwsh -ExecutionPolicy Bypass -File .\run_demo.ps1
#  -> expected output: 3/3 deterministic PoVs verified (rce, cmdi, sqli)
#                      workspace\report.md written

# 4. interactive agent (requires Claude Code installed on Windows)
claude
> /campaign       # full LLM hunt + coverage-guided Jazzer campaign + report
```

### Notes for native PowerShell

- **Execution Policy**: if PowerShell refuses to run the scripts, use
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (one time), or always
  prefix with `-ExecutionPolicy Bypass`.
- **JAVA_HOME** is not required, but if you have multiple JDKs make sure the
  one on PATH is 17+.
- **Long path support**: Windows historically caps paths at 260 chars.
  Maven repositories can hit this. Either keep the project shallow
  (e.g. `C:\hunter\`) or enable long paths
  (`gpedit.msc → Computer Config → Admin Templates → System → Filesystem →
  Enable Win32 long paths`).
- **Antivirus**: Defender / Endpoint Protection often quarantines Jazzer
  artifacts (it deliberately raises `FuzzerSecurityIssue` exceptions and
  embeds a `jaz.Zer` honeypot class). If Jazzer disappears after download,
  add `<project>\jazzer\` and `<project>\workspace\build\` to AV exclusions.

---

## Mode B — WSL2 Ubuntu (recommended for parity)

Best for: matching what runs in CI / containers / on your colleagues' Linux
boxes. The bash scripts (`setup.sh`, `run_demo.sh`) just work.

```powershell
# one-time: install WSL2 + Ubuntu (from an Admin PowerShell)
wsl --install -d Ubuntu-22.04
# reboot if prompted, then open Ubuntu and:
sudo apt update && sudo apt install -y openjdk-21-jdk python3 python3-pip
```

Then inside the Ubuntu shell:

```bash
# Use the Windows filesystem mount so files are visible to both worlds:
cd /mnt/c/Users/you/src/claude-java-vuln-hunter

bash setup.sh
bash run_demo.sh           # 3/3 PoVs in Linux mode
```

To run `claude` **on Windows** but have Jazzer execute **in WSL**, tell
`reproduce.py` to bridge:

```powershell
# In Windows PowerShell:
$env:REPRODUCE_BACKEND = "wsl"
claude
> /campaign
```

`tools/reproduce.py` will translate the Windows blob path
(`C:\...\blob.bin`) to a WSL path (`/mnt/c/.../blob.bin`) and invoke
`wsl -- java -cp ... com.code_intelligence.jazzer.Jazzer ...` automatically.

---

## Mode C — Git Bash / MSYS2

If you already use Git Bash and have JDK+Python on PATH, the `*.sh` scripts
work as-is (Git Bash provides `bash`, `curl`/`wget`, and `tar`):

```bash
# inside Git Bash:
cd /c/Users/you/src/claude-java-vuln-hunter
bash setup.sh
bash run_demo.sh
```

Git Bash quirks to watch for:

- Path translation: when calling `java -cp <classpath>`, Git Bash may rewrite
  Unix paths inside argument values. If you see `Error: Could not find or load
  main class C\:\Users\...`, prefix the argument with `MSYS_NO_PATHCONV=1`:
  ```bash
  MSYS_NO_PATHCONV=1 bash run_demo.sh
  ```
- `tools/build_target.py` and Maven/Gradle: `subprocess.run(["mvn", ...])`
  resolves to `mvn.cmd` automatically (via `shutil.which`), so it works.

---

## What was fixed for Windows

These were real bugs that have been patched, not just docs additions:

1. **Classpath separator** (`tools/reproduce.py`, `tools/fuzz.py`):
   was hard-coded `":"`. Now `os.pathsep` (= `;` on Windows, `:` on Unix).
   Effect: native-Windows Jazzer invocations had broken classpaths before.

2. **`mvn` / `gradle` resolution** (`tools/build_target.py`):
   `subprocess.run(["mvn", ...])` on Windows ignores PATHEXT and fails to
   find `mvn.cmd`. Now resolves the executable up front via `shutil.which()`.

3. **PowerShell entry points** added:
   `setup.ps1`, `run_demo.ps1`, `workspace\harness\build.ps1`.

The Python tools themselves (`reproduce.py`, `fuzz.py`, `parse_crash.py`,
`dedup.py`, `state.py`, `fdp_builder.py`, `codeindex.py`, `report.py`) are
all cross-platform pure Python and require no per-OS forks.

---

## Troubleshooting

**`java -version` works but `setup.ps1` says java not found**
Reopen PowerShell. Environment variables updated by the installer don't
propagate to already-open shells.

**`Invoke-WebRequest` fails downloading Jazzer**
Behind a proxy? Set `$env:HTTPS_PROXY = "http://proxy:port"` before re-running.
Or download `jazzer-linux.tar.gz` manually from
https://github.com/CodeIntelligenceTesting/jazzer/releases and extract
`jazzer_standalone.jar` into `.\jazzer\`.

**Smoke test runs but `is_crash=false` for every PoV**
Almost always a stale `workspace\build\classes\` (you changed the demo target
but didn't rebuild). Run:
```powershell
python tools\build_target.py --clean
pwsh .\run_demo.ps1
```

**Classpath errors mentioning `:` on Windows**
You may be running an old checkout. Pull the latest — the `os.pathsep` fix
is in `tools/reproduce.py` line 44 and `tools/fuzz.py` line 47.

**WSL backend: "wsl: command not found"**
You're already INSIDE WSL. Use `REPRODUCE_BACKEND=native` in that shell —
only set `wsl` from Windows-side PowerShell.

**Long Maven build times on `C:\` drive**
Move the project to an SSD-backed local path, exclude it from real-time AV
scans, and enable Maven's offline cache (`mvn -o` after first run).
