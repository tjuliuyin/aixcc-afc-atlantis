#!/usr/bin/env bash
# One-shot environment setup for claude-java-vuln-hunter.
# - Downloads Jazzer standalone JAR
# - Installs javalang (preferred code-index backend)
# - Pre-fetches H2 driver used by the SQLi demo
# Idempotent. Safe to re-run.
set -uo pipefail
cd "$(dirname "$0")"

JAZZER_VERSION="${JAZZER_VERSION:-0.22.1}"
JAZZER_URL="https://github.com/CodeIntelligenceTesting/jazzer/releases/download/v${JAZZER_VERSION}/jazzer-linux.tar.gz"
JAZZER_JAR="jazzer/jazzer_standalone.jar"

PY="$(command -v python3 || command -v python || true)"
[ -z "$PY" ] && { echo "[setup] error: python3 not found" >&2; exit 1; }

mkdir -p jazzer

# 1. Jazzer
if [ ! -f "$JAZZER_JAR" ]; then
    echo "[setup] downloading Jazzer ${JAZZER_VERSION}..."
    tmp=$(mktemp -d)
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$tmp/jazzer.tar.gz" "$JAZZER_URL" || { echo "[setup] curl failed" >&2; exit 1; }
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$tmp/jazzer.tar.gz" "$JAZZER_URL" || { echo "[setup] wget failed" >&2; exit 1; }
    else
        echo "[setup] need curl or wget" >&2; exit 1
    fi
    tar -xzf "$tmp/jazzer.tar.gz" -C jazzer/
    rm -rf "$tmp"
fi
echo "[setup] Jazzer ok ($(ls -lh "$JAZZER_JAR" | awk '{print $5}'))"

# 2. javalang for the index
if ! "$PY" -c "import javalang" 2>/dev/null; then
    echo "[setup] installing javalang..."
    "$PY" -m pip install --quiet --user javalang 2>/dev/null || \
        "$PY" -m pip install --quiet --break-system-packages javalang 2>/dev/null || \
        "$PY" -m pip install --quiet javalang || \
        echo "[setup] warn: pip install javalang failed; regex fallback will be used"
fi
"$PY" -c "import javalang; print(f'[setup] javalang ok (v{javalang.__version__ if hasattr(javalang, \"__version__\") else \"?\"})')" 2>/dev/null \
    || echo "[setup] note: javalang not installed; codeindex will fall back to regex"

# 3. JDK / Maven presence check
command -v java  >/dev/null 2>&1 || { echo "[setup] error: java not on PATH (install JDK 17+)" >&2; exit 1; }
command -v javac >/dev/null 2>&1 || { echo "[setup] error: javac not on PATH" >&2; exit 1; }
java -version 2>&1 | head -1

# 4. Pre-warm build (downloads H2 too)
echo "[setup] pre-building demo..."
bash workspace/harness/build.sh >/dev/null && echo "[setup] build ok"

echo ""
echo "[setup] DONE — try:"
echo "    bash run_demo.sh         # token-free deterministic smoke test"
echo "    claude                   # interactive agent (then /hunt)"
