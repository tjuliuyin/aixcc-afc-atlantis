#!/usr/bin/env bash
# Deterministic smoke test: exercises the whole tool chain WITHOUT any LLM,
# so you can confirm the environment is wired up before running `claude` /hunt.
# Works on Linux/WSL. Run from the project root: bash run_demo.sh
set -uo pipefail
cd "$(dirname "$0")"
export VULN_HUNTER_ROOT="$(pwd)"
export REPRODUCE_BACKEND="${REPRODUCE_BACKEND:-native}"

say() { printf "\n\033[1;36m== %s ==\033[0m\n" "$1"; }

say "0. reset state"
python3 tools/state.py reset

say "1. build harness"
bash workspace/harness/build.sh | tail -2

say "2. index code"
python3 tools/codeindex.py workspace/target

say "3. reproduce benign seed (expect is_crash=false)"
python3 tools/reproduce.py --harness workspace/harness/harness --blob workspace/corpus/seed1.bin

say "4. craft a PoV (FUZZ magic + length 0xff + 255 payload bytes)"
mkdir -p workspace/pov/bit_0/iter_0
python3 - <<'PY'
from pathlib import Path
blob = b"FUZZ" + bytes([0xff]) + b"A"*255
Path("workspace/pov/bit_0/iter_0/blob.bin").write_bytes(blob)
print("wrote", len(blob), "bytes")
PY

say "5. reproduce PoV (expect is_crash=true, exit_code 1)"
python3 tools/reproduce.py --harness workspace/harness/harness --blob workspace/pov/bit_0/iter_0/blob.bin

say "6. parse crash log"
python3 tools/parse_crash.py workspace/pov/bit_0/iter_0/blob.log > workspace/pov/bit_0/iter_0/parsed.json
python3 -c "import json;d=json.load(open('workspace/pov/bit_0/iter_0/parsed.json'));print('sanitizer:',d['sanitizer']);print('top frames:',[f['name'] for f in d['callstacks'][0][:3]])"

say "7. dedup (first time new, second time duplicate)"
python3 tools/dedup.py --new workspace/pov/bit_0/iter_0/parsed.json
python3 tools/dedup.py --new workspace/pov/bit_0/iter_0/parsed.json

say "DONE — deterministic pipeline verified. Now run:  claude  then  /hunt harness"
