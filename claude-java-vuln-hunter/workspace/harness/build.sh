#!/usr/bin/env bash
# Build the Java target + Jazzer harness. Pure javac + maven-fetched deps.
# Output: workspace/build/{classes,deps}/  used by tools/reproduce.py.
set -euo pipefail
cd "$(dirname "$0")/../.."  # -> project root (claude-java-vuln-hunter)

ROOT="$(pwd)"
JAZZER_JAR="$ROOT/jazzer/jazzer_standalone.jar"
BUILD_DIR="$ROOT/workspace/build"
CLASSES_DIR="$BUILD_DIR/classes"
DEPS_DIR="$BUILD_DIR/deps"
TARGET_SRC="$ROOT/workspace/target"
HARNESS_SRC="$ROOT/workspace/harness/src"

if [ ! -f "$JAZZER_JAR" ]; then
    echo "[build] error: $JAZZER_JAR missing. Run ./setup.sh first." >&2
    exit 1
fi

mkdir -p "$CLASSES_DIR" "$DEPS_DIR"

# Fetch runtime deps (H2 for the SQLi demo). Skip if already cached.
H2_VER=2.2.224
H2_JAR="$DEPS_DIR/h2-$H2_VER.jar"
if [ ! -f "$H2_JAR" ]; then
    echo "[build] downloading H2..."
    curl -sL -o "$H2_JAR" "https://repo1.maven.org/maven2/com/h2database/h2/$H2_VER/h2-$H2_VER.jar"
fi

# Find every .java under target + harness (recurses across all demo projects)
SOURCES=$(find "$TARGET_SRC" "$HARNESS_SRC" -name "*.java" 2>/dev/null | sort)
if [ -z "$SOURCES" ]; then
    echo "[build] no .java sources found under $TARGET_SRC or $HARNESS_SRC" >&2
    exit 1
fi

CP="$JAZZER_JAR:$H2_JAR:$CLASSES_DIR"
echo "[build] compiling $(echo "$SOURCES" | wc -l) source files..."
javac -encoding UTF-8 -cp "$CP" -d "$CLASSES_DIR" $SOURCES

echo "[build] ok"
echo "  classes : $CLASSES_DIR"
echo "  deps    : $DEPS_DIR (h2: $H2_JAR)"
echo "  jazzer  : $JAZZER_JAR"
echo "[build] reproduce one input with:"
echo "  python3 tools/reproduce.py --harness com.example.fuzz.DemoFuzzer --blob <file>"
