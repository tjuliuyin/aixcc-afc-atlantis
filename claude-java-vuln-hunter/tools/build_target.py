#!/usr/bin/env python3
"""Build a real-world Java target and assemble its classpath for Jazzer.

Detects the project type under workspace/target/ and produces:
  workspace/build/classes/   compiled target + harness classes
  workspace/build/deps/      all runtime dependency jars (incl. target jar)
  workspace/build/cp.txt     the full classpath string (for reference)

Supported layouts (auto-detected, first match wins):
  1. Maven   (pom.xml)      -> mvn package + dependency:copy-dependencies
  2. Gradle  (build.gradle) -> gradle build + a dependencies copy task
  3. Prebuilt jars          -> any *.jar already under workspace/target/lib or deps
  4. Plain javac (demo)     -> recurse *.java (the bundled demo path)

The harness sources under workspace/harness/src are always compiled last
against the assembled classpath.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("VULN_HUNTER_ROOT", Path(__file__).resolve().parent.parent))
TARGET = ROOT / "workspace" / "target"
HARNESS_SRC = ROOT / "workspace" / "harness" / "src"
BUILD = ROOT / "workspace" / "build"
CLASSES = BUILD / "classes"
DEPS = BUILD / "deps"
JAZZER = ROOT / "jazzer" / "jazzer_standalone.jar"


def run(cmd, cwd=None, check=True):
    print(f"[build] $ {' '.join(map(str, cmd))}", flush=True)
    r = subprocess.run(list(map(str, cmd)), cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0 and check:
        print(r.stdout[-2000:], file=sys.stderr)
        print(r.stderr[-2000:], file=sys.stderr)
        raise SystemExit(f"[build] command failed: {' '.join(map(str, cmd))}")
    return r


def find(name: str) -> Path | None:
    for p in TARGET.rglob(name):
        return p
    return None


def collect_jars_into_deps():
    DEPS.mkdir(parents=True, exist_ok=True)
    n = 0
    for jar in TARGET.rglob("*.jar"):
        # skip sources/javadoc jars
        if jar.name.endswith(("-sources.jar", "-javadoc.jar")):
            continue
        dst = DEPS / jar.name
        if not dst.exists():
            shutil.copy(jar, dst)
            n += 1
    return n


def build_maven(pom: Path):
    proj = pom.parent
    print(f"[build] Maven project at {proj}")
    run(["mvn", "-q", "-DskipTests", "package",
         "dependency:copy-dependencies",
         f"-DoutputDirectory={DEPS}"], cwd=proj, check=False)
    DEPS.mkdir(parents=True, exist_ok=True)
    # copy the built artifact jar(s)
    for jar in (proj / "target").glob("*.jar"):
        if not jar.name.endswith(("-sources.jar", "-javadoc.jar")):
            shutil.copy(jar, DEPS / jar.name)
    # also unpack classes so source-level line numbers resolve if classes exist
    tc = proj / "target" / "classes"
    if tc.exists():
        CLASSES.mkdir(parents=True, exist_ok=True)
        shutil.copytree(tc, CLASSES, dirs_exist_ok=True)


def build_gradle(gradle_file: Path):
    proj = gradle_file.parent
    print(f"[build] Gradle project at {proj}")
    gradlew = proj / ("gradlew.bat" if os.name == "nt" else "gradlew")
    g = [str(gradlew)] if gradlew.exists() else ["gradle"]
    run(g + ["build", "-x", "test"], cwd=proj, check=False)
    DEPS.mkdir(parents=True, exist_ok=True)
    for jar in proj.rglob("build/libs/*.jar"):
        shutil.copy(jar, DEPS / jar.name)
    # best-effort: copy resolved deps via a one-off task if present
    for cls in proj.rglob("build/classes/java/main"):
        CLASSES.mkdir(parents=True, exist_ok=True)
        shutil.copytree(cls, CLASSES, dirs_exist_ok=True)
    collect_jars_into_deps()


def build_plain_javac():
    """The bundled-demo path: download H2 if missing, compile all sources."""
    print("[build] plain javac (no pom/gradle detected)")
    DEPS.mkdir(parents=True, exist_ok=True)
    h2 = DEPS / "h2-2.2.224.jar"
    if not h2.exists():
        url = "https://repo1.maven.org/maven2/com/h2database/h2/2.2.224/h2-2.2.224.jar"
        for tool in (["curl", "-sL", "-o", str(h2), url], ["wget", "-q", "-O", str(h2), url]):
            if shutil.which(tool[0]):
                run(tool, check=False)
                break
    collect_jars_into_deps()


def compile_harness():
    if not HARNESS_SRC.exists():
        print("[build] no harness sources, skipping")
        return
    CLASSES.mkdir(parents=True, exist_ok=True)
    cp = [str(JAZZER), str(CLASSES)] + [str(j) for j in DEPS.glob("*.jar")]
    # also compile any target *.java not covered by a jar (demo case)
    target_java = [str(p) for p in TARGET.rglob("*.java")]
    harness_java = [str(p) for p in HARNESS_SRC.rglob("*.java")]
    sources = target_java + harness_java
    if not sources:
        print("[build] no .java sources to compile")
        return
    run(["javac", "-encoding", "UTF-8", "-cp", os.pathsep.join(cp),
         "-d", str(CLASSES), *sources], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true", help="wipe workspace/build first")
    args = ap.parse_args()

    if args.clean and BUILD.exists():
        shutil.rmtree(BUILD)
    CLASSES.mkdir(parents=True, exist_ok=True)
    DEPS.mkdir(parents=True, exist_ok=True)

    if not JAZZER.exists():
        raise SystemExit(f"[build] {JAZZER} missing — run ./setup.sh first")

    pom = find("pom.xml")
    gradle = find("build.gradle") or find("build.gradle.kts")
    if pom:
        build_maven(pom)
    elif gradle:
        build_gradle(gradle)
    else:
        build_plain_javac()

    compile_harness()

    cp = os.pathsep.join([str(JAZZER), str(CLASSES)] + [str(j) for j in sorted(DEPS.glob("*.jar"))])
    (BUILD / "cp.txt").write_text(cp)
    print(f"[build] ok")
    print(f"  classes : {CLASSES}")
    print(f"  deps    : {len(list(DEPS.glob('*.jar')))} jar(s)")
    print(f"  cp.txt  : {BUILD/'cp.txt'}")


if __name__ == "__main__":
    main()
