# Plain-javac build (PowerShell). For real Maven/Gradle projects use
# `python tools\build_target.py` instead — it handles dependency trees.
$ErrorActionPreference = "Stop"
Set-Location -Path (Join-Path $PSScriptRoot "..\..")

$ROOT       = (Get-Location).Path
$JazzerJar  = Join-Path $ROOT "jazzer\jazzer_standalone.jar"
$BuildDir   = Join-Path $ROOT "workspace\build"
$ClassesDir = Join-Path $BuildDir "classes"
$DepsDir    = Join-Path $BuildDir "deps"
$TargetSrc  = Join-Path $ROOT "workspace\target"
$HarnessSrc = Join-Path $ROOT "workspace\harness\src"

if (-not (Test-Path $JazzerJar)) {
    Write-Error "[build] $JazzerJar missing. Run setup.ps1 first."
    exit 1
}

New-Item -ItemType Directory -Force -Path $ClassesDir, $DepsDir | Out-Null

# Fetch H2 (used by the SqlQuery demo). Skip if already cached.
$H2 = Join-Path $DepsDir "h2-2.2.224.jar"
if (-not (Test-Path $H2)) {
    Write-Host "[build] downloading H2 ..."
    Invoke-WebRequest -Uri "https://repo1.maven.org/maven2/com/h2database/h2/2.2.224/h2-2.2.224.jar" `
                      -OutFile $H2 -UseBasicParsing
}

$sources = @(Get-ChildItem -Recurse $TargetSrc, $HarnessSrc -Filter *.java | ForEach-Object { $_.FullName })
if ($sources.Count -eq 0) {
    Write-Error "[build] no .java sources found"; exit 1
}

# Build classpath using Windows ';' separator
$cp = @($JazzerJar, $H2, $ClassesDir) -join ";"

Write-Host "[build] compiling $($sources.Count) source files..."
& javac -encoding UTF-8 -cp $cp -d $ClassesDir @sources
if ($LASTEXITCODE -ne 0) { Write-Error "[build] javac failed"; exit 1 }

Write-Host "[build] ok"
Write-Host "  classes : $ClassesDir"
Write-Host "  deps    : $DepsDir"
Write-Host "  jazzer  : $JazzerJar"
