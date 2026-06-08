#!/usr/bin/env bash
# Build the fuzz harness. Tries libFuzzer first; falls back to a standalone
# ASAN driver (gcc or clang) when the libFuzzer runtime is unavailable.
# Run inside WSL (Windows) or natively on Linux. Output: ./harness
set -uo pipefail
cd "$(dirname "$0")"

OUT=harness
# -U_FORTIFY_SOURCE / -fno-builtin-memcpy keep memcpy going through the ASAN
# interceptor so the report says "heap-buffer-overflow" (not "unknown-crash").
SRC_COMMON=(../target/parser.c -I../target -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -fno-builtin-memcpy)

try_libfuzzer() {
    local cc="${CC:-clang}"
    command -v "$cc" >/dev/null 2>&1 || return 1
    echo "[build] try libFuzzer+ASAN via $cc ..."
    "$cc" -g -O1 -fsanitize=address,fuzzer harness.c "${SRC_COMMON[@]}" -o "$OUT" 2>/tmp/bld.log
}

try_standalone() {
    for cc in "${CC:-}" clang gcc; do
        [ -z "$cc" ] && continue
        command -v "$cc" >/dev/null 2>&1 || continue
        echo "[build] try standalone ASAN driver via $cc ..."
        "$cc" -g -O1 -fsanitize=address standalone_driver.c harness.c "${SRC_COMMON[@]}" -o "$OUT" 2>/tmp/bld.log && {
            echo "[build] (standalone mode: libFuzzer not required)"
            return 0
        }
    done
    return 1
}

if try_libfuzzer; then
    echo "[build] ok (libFuzzer mode) -> $(pwd)/$OUT"
elif try_standalone; then
    echo "[build] ok (standalone mode) -> $(pwd)/$OUT"
else
    echo "[build] FAILED. Last compiler log:" >&2
    cat /tmp/bld.log >&2
    exit 1
fi

echo "[build] reproduce a single input with: ./$OUT <blob-file>"
