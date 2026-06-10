# Deterministic, token-free smoke test for the WHOLE Java tool chain on Windows.
# Run it FIRST to confirm env is wired up before launching `claude` / /hunt.
#
# Usage:
#   pwsh -ExecutionPolicy Bypass -File run_demo.ps1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$env:VULN_HUNTER_ROOT = $PSScriptRoot
if (-not $env:REPRODUCE_BACKEND) { $env:REPRODUCE_BACKEND = "native" }

# pick python
$Py = $null
foreach ($cand in @("py", "python", "python3")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $Py = $cand; break }
}
if (-not $Py) { Write-Error "python not found"; exit 1 }

function Section($t) { Write-Host ""; Write-Host "== $t ==" -ForegroundColor Cyan }
function Ok($t)      { Write-Host "  OK: $t" -ForegroundColor Green }
function Fail($t)    { Write-Host "  FAIL: $t" -ForegroundColor Red }

Section "0. setup (idempotent: Jazzer JAR + javalang + build)"
& pwsh -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\setup.ps1" | Select-Object -Last 6

Section "1. reset state"
& $Py "$PSScriptRoot\tools\state.py" reset | Out-Null

Section "2. index Java code"
& $Py "$PSScriptRoot\tools\codeindex.py" "$PSScriptRoot\workspace\target"

Section "3. craft 3 PoVs using fdp_builder.py (one per demo vuln class)"
$povs = @(
    @{ Name="RC";   Sel=0; Payload="jaz.Zer" }       # Reflective Call / RCE
    @{ Name="CMDI"; Sel=1; Payload="jazze foo bar" } # OS Command Injection
    @{ Name="SQLI"; Sel=2; Payload="'aee" }          # SQL Injection
)
$pass = 0
foreach ($p in $povs) {
    $dir = "$PSScriptRoot\workspace\pov\$($p.Name)"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $blob = Join-Path $dir "blob.bin"
    & $Py "$PSScriptRoot\tools\fdp_builder.py" emit `
        --bytes $p.Sel --remaining-string $p.Payload -o $blob | Out-Null

    Section ("4.$($p.Name) reproduce  (selector byte $($p.Sel), payload [$($p.Payload)])")
    $res = & $Py "$PSScriptRoot\tools\reproduce.py" `
        --harness "com.example.fuzz.DemoFuzzer" --blob $blob --timeout 30
    Write-Host $res
    $isCrash = (($res | ConvertFrom-Json).is_crash)
    if (-not $isCrash) { Fail "expected crash, got none"; continue }

    $log = Join-Path $dir "blob.log"
    $parsed = Join-Path $dir "parsed.json"
    & $Py "$PSScriptRoot\tools\parse_crash.py" $log | Out-File -Encoding utf8 $parsed
    $san = (Get-Content $parsed | ConvertFrom-Json).sanitizer

    $dedup = & $Py "$PSScriptRoot\tools\dedup.py" --new $parsed
    $isNew = (($dedup | ConvertFrom-Json).is_new)
    if ($isNew) {
        Ok "sanitizer=$san  is_new=True"
        $pass++
    }
    else {
        Fail "unexpected dup: $dedup"
    }
}

Section "5. record verified PoVs + generate report"
foreach ($p in $povs) {
    $parsed = "$PSScriptRoot\workspace\pov\$($p.Name)\parsed.json"
    if (-not (Test-Path $parsed)) { continue }
    $san = (Get-Content $parsed | ConvertFrom-Json).sanitizer
    $entry = @{ source="smoke"; sanitizer=$san;
                blob="workspace/pov/$($p.Name)/blob.bin";
                harness="com.example.fuzz.DemoFuzzer" } | ConvertTo-Json -Compress
    & $Py "$PSScriptRoot\tools\state.py" append verified_povs $entry | Out-Null
}
& $Py "$PSScriptRoot\tools\report.py" --harness "com.example.fuzz.DemoFuzzer"

Section "6. final state"
& $Py "$PSScriptRoot\tools\state.py" dump

Write-Host ""
if ($pass -eq $povs.Count) {
    Write-Host "DONE — $pass/$($povs.Count) deterministic PoVs verified. Report: workspace\report.md" -ForegroundColor Green
    Write-Host "Next:"
    Write-Host "    claude  then  /campaign   # LLM hunt + real fuzzing campaign"
    Write-Host "    claude  then  /hunt       # LLM-guided targeted PoVs only"
}
else {
    Write-Host "FAILED — $pass/$($povs.Count) PoVs passed. Investigate workspace\pov\*\blob.log" -ForegroundColor Red
    exit 1
}
