#!/usr/bin/env bash
# Deterministic, token-free smoke test for the WHOLE Java tool chain.
# Run it FIRST to confirm env is wired up before launching `claude`/`/hunt`.
# Works on Linux/WSL. From project root:  bash run_demo.sh
set -uo pipefail
cd "$(dirname "$0")"
export VULN_HUNTER_ROOT="$(pwd)"
export REPRODUCE_BACKEND="${REPRODUCE_BACKEND:-native}"

say() { printf "\n\033[1;36m== %s ==\033[0m\n" "$1"; }
red() { printf "\033[1;31m%s\033[0m\n" "$1"; }
grn() { printf "\033[1;32m%s\033[0m\n" "$1"; }

say "0. setup (idempotent: Jazzer JAR + javalang + build)"
bash setup.sh 2>&1 | tail -5

say "1. reset state"
python3 tools/state.py reset

say "2. index Java code"
python3 tools/codeindex.py workspace/target

say "3. craft 3 PoVs using fdp_builder.py (one per demo vuln class)"
declare -A POVS=(
    ["RC"]="0|jaz.Zer"          # Reflective Call / RCE
    ["CMDI"]="1|jazze foo bar"  # OS Command Injection
    ["SQLI"]="2|'aee"           # SQL Injection
)
mkdir -p workspace/pov
PASS=0; TOTAL=0
for name in RC CMDI SQLI; do
    TOTAL=$((TOTAL+1))
    IFS='|' read -r sel payload <<< "${POVS[$name]}"
    mkdir -p workspace/pov/$name
    python3 tools/fdp_builder.py emit --bytes "$sel" --remaining-string "$payload" \
        -o workspace/pov/$name/blob.bin

    say "4.$name reproduce  (selector byte $sel, payload [$payload])"
    res=$(python3 tools/reproduce.py --harness com.example.fuzz.DemoFuzzer \
            --blob workspace/pov/$name/blob.bin --timeout 30)
    echo "$res"
    is_crash=$(echo "$res" | python3 -c "import json,sys;print(json.load(sys.stdin)['is_crash'])")
    if [ "$is_crash" != "True" ]; then
        red "  FAIL: expected crash, got none"
        continue
    fi
    python3 tools/parse_crash.py workspace/pov/$name/blob.log \
        > workspace/pov/$name/parsed.json
    san=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['sanitizer'])" \
            workspace/pov/$name/parsed.json)
    dedup=$(python3 tools/dedup.py --new workspace/pov/$name/parsed.json)
    new=$(echo "$dedup" | python3 -c "import json,sys;print(json.load(sys.stdin)['is_new'])")
    if [ "$new" = "True" ]; then
        grn "  OK: sanitizer=$san  is_new=True"
        PASS=$((PASS+1))
    else
        red "  unexpected dup: $dedup"
    fi
done

say "5. record verified PoVs + generate report"
for name in RC CMDI SQLI; do
    [ -f "workspace/pov/$name/parsed.json" ] || continue
    san=$(python3 -c "import json;print(json.load(open('workspace/pov/$name/parsed.json'))['sanitizer'])")
    python3 tools/state.py append verified_povs \
        "{\"source\":\"smoke\",\"sanitizer\":\"$san\",\"blob\":\"workspace/pov/$name/blob.bin\",\"harness\":\"com.example.fuzz.DemoFuzzer\"}" >/dev/null
done
python3 tools/report.py --harness com.example.fuzz.DemoFuzzer

say "6. final state"
python3 tools/state.py dump

echo ""
if [ "$PASS" -eq "$TOTAL" ]; then
    grn "DONE — $PASS/$TOTAL deterministic PoVs verified. Report: workspace/report.md"
    echo "Next steps:"
    echo "    claude  then  /campaign   # LLM hunt + real fuzzing campaign"
    echo "    claude  then  /hunt       # LLM-guided targeted PoVs only"
    echo "    python3 tools/fuzz.py --harness com.example.fuzz.DemoFuzzer --seconds 120 --jobs 4"
else
    red "FAILED — $PASS/$TOTAL PoVs passed. Investigate workspace/pov/*/blob.log"
    exit 1
fi
