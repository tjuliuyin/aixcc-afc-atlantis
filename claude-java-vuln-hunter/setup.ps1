# One-shot environment setup for claude-java-vuln-hunter on Windows.
# - Downloads Jazzer standalone JAR
# - Installs javalang (preferred code-index backend)
# - Pre-warms the demo build
# Idempotent. Safe to re-run.
#
# Usage:
#   pwsh -ExecutionPolicy Bypass -File setup.ps1
# or from an Admin PowerShell:
#   .\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$JazzerVersion = if ($env:JAZZER_VERSION) { $env:JAZZER_VERSION } else { "0.22.1" }
# The "linux" tarball still works on Windows because jazzer_standalone.jar
# bundles native libraries for all three OSes. If you prefer the Windows-named
# release, set $env:JAZZER_VERSION and edit the URL below.
$JazzerUrl = "https://github.com/CodeIntelligenceTesting/jazzer/releases/download/v$JazzerVersion/jazzer-linux.tar.gz"
$JazzerJar = Join-Path $PSScriptRoot "jazzer\jazzer_standalone.jar"

function Require-Cmd {
    param([string]$name, [string]$hint)
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Error "[setup] '$name' not found on PATH. $hint"
        exit 1
    }
}

Require-Cmd "java"  "Install Temurin JDK 17+ (https://adoptium.net) and reopen the shell."
Require-Cmd "javac" "Make sure your JDK install includes javac (a JRE-only install is not enough)."

# Python: try py launcher, then python, then python3
$Py = $null
foreach ($cand in @("py", "python", "python3")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $Py = $cand; break }
}
if (-not $Py) {
    Write-Error "[setup] python not found. Install Python 3.9+ from https://python.org."
    exit 1
}
Write-Host "[setup] python: $Py"

# 1. Jazzer
New-Item -ItemType Directory -Force -Path "jazzer" | Out-Null
if (-not (Test-Path $JazzerJar)) {
    Write-Host "[setup] downloading Jazzer $JazzerVersion ..."
    $tmp = New-TemporaryFile
    try {
        Invoke-WebRequest -Uri $JazzerUrl -OutFile $tmp -UseBasicParsing
        # Use tar bundled with Windows 10+ to extract .tar.gz
        tar -xzf $tmp -C jazzer
    }
    finally {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    }
}
$jazzerSize = (Get-Item $JazzerJar).Length / 1MB
Write-Host ("[setup] Jazzer ok ({0:N1} MB)" -f $jazzerSize)

# 2. javalang (preferred Java AST backend for codeindex)
& $Py -c "import javalang" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[setup] installing javalang ..."
    & $Py -m pip install --quiet --user javalang
    if ($LASTEXITCODE -ne 0) { & $Py -m pip install --quiet javalang }
}
& $Py -c "import javalang; print('[setup] javalang ok')" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[setup] note: javalang not installed; codeindex will fall back to regex"
}

# 3. JDK version banner
& java -version

# 4. Pre-warm build
Write-Host "[setup] pre-building demo ..."
& $Py "$PSScriptRoot\tools\build_target.py" --clean
if ($LASTEXITCODE -ne 0) {
    Write-Error "[setup] demo build failed"; exit 1
}
Write-Host "[setup] build ok"

Write-Host ""
Write-Host "[setup] DONE — try:"
Write-Host "    pwsh .\run_demo.ps1        # token-free deterministic smoke test"
Write-Host "    claude                     # interactive agent (then /hunt or /campaign)"
