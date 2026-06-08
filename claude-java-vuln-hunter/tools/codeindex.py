#!/usr/bin/env python3
"""Build a Java method-level code index.

Output: workspace/index/functions.json
  { method_name: [
      { class_fqn, file, start_line, end_line,
        signature, body_preview, modifiers: [...] }
  ] }

Backend priority:
  1. javalang (lightweight, pure-Python AST) — preferred
  2. tree-sitter-languages
  3. regex fallback (works for the demo, may miss exotic syntax)
"""
import argparse
import json
import re
import sys
from pathlib import Path


def index_with_javalang(root: Path) -> dict:
    import javalang  # may raise ImportError
    index = {}
    for p in root.rglob("*.java"):
        try:
            src = p.read_text(errors="ignore")
            tree = javalang.parse.parse(src)
        except Exception:
            continue
        package = tree.package.name if tree.package else ""
        for path, node in tree.filter(javalang.tree.MethodDeclaration):
            # Class FQN: walk up the path collecting enclosing classes
            classes = [t.name for t in path if isinstance(t, javalang.tree.ClassDeclaration)]
            class_fqn = (package + "." if package else "") + ".".join(classes)
            line = node.position.line if node.position else 0
            end_line = line + max(1, src.count("\n", 0, src.find("}", src.find(node.name))))  # rough
            # Better end_line via brace matching from `line`:
            end_line = brace_end(src, line)
            body = "\n".join(src.splitlines()[line - 1:end_line])[:2500]
            sig = f"{node.name}({', '.join(p.type.name for p in node.parameters)})"
            index.setdefault(node.name, []).append({
                "class_fqn": class_fqn,
                "file": str(p),
                "start_line": line,
                "end_line": end_line,
                "signature": sig,
                "modifiers": list(node.modifiers),
                "body_preview": body,
            })
    return index


def brace_end(src: str, start_line: int) -> int:
    """Find matching `}` of the function starting near `start_line`."""
    lines = src.splitlines()
    text = "\n".join(lines)
    # offset of start_line
    off = sum(len(l) + 1 for l in lines[:start_line - 1])
    i = text.find("{", off)
    if i < 0:
        return start_line
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text.count("\n", 0, j) + 1
    return start_line


def index_with_treesitter(root: Path) -> dict:
    from tree_sitter_languages import get_parser
    parser = get_parser("java")
    index = {}
    for p in root.rglob("*.java"):
        src = p.read_bytes()
        tree = parser.parse(src)

        # discover package name
        package = ""
        for ch in tree.root_node.children:
            if ch.type == "package_declaration":
                package = ch.text.decode("utf-8", "ignore").split("package", 1)[1].strip().rstrip(";").strip()

        def walk(node, class_stack):
            if node.type == "class_declaration":
                # find identifier child
                cname = next((c.text.decode("utf-8", "ignore") for c in node.children if c.type == "identifier"), None)
                if cname:
                    class_stack = class_stack + [cname]
            elif node.type == "method_declaration":
                ident = next((c for c in node.children if c.type == "identifier"), None)
                if ident:
                    name = ident.text.decode("utf-8", "ignore")
                    s = node.start_point[0] + 1
                    e = node.end_point[0] + 1
                    body = src[node.start_byte:node.end_byte][:2500].decode("utf-8", "ignore")
                    class_fqn = (package + "." if package else "") + ".".join(class_stack)
                    index.setdefault(name, []).append({
                        "class_fqn": class_fqn,
                        "file": str(p),
                        "start_line": s, "end_line": e,
                        "signature": name + "(...)",
                        "modifiers": [],
                        "body_preview": body,
                    })
            for ch in node.children:
                walk(ch, class_stack)

        walk(tree.root_node, [])
    return index


METHOD_RE = re.compile(
    r"^[ \t]*(?:public|protected|private|static|final|synchronized|abstract|native|\s)+"
    r"[\w<>\[\],?.& ]*?\s([A-Za-z_]\w*)\s*\([^;{]*?\)\s*(?:throws[^{;]+)?\{",
    re.MULTILINE,
)
PKG_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
CLASS_RE = re.compile(r"\b(class|interface|enum)\s+([A-Za-z_]\w*)")


def index_with_regex(root: Path) -> dict:
    index = {}
    for p in root.rglob("*.java"):
        src = p.read_text(errors="ignore")
        pkg_m = PKG_RE.search(src)
        package = pkg_m.group(1) if pkg_m else ""
        class_m = CLASS_RE.search(src)
        class_name = class_m.group(2) if class_m else p.stem
        class_fqn = (package + "." if package else "") + class_name

        lines = src.splitlines()
        for m in METHOD_RE.finditer(src):
            name = m.group(1)
            if name in ("if", "for", "while", "switch", "catch", "return", "new", "throw"):
                continue
            start_off = m.start()
            start_line = src.count("\n", 0, start_off) + 1
            end_line = brace_end(src, start_line)
            body = "\n".join(lines[start_line - 1:end_line])[:2500]
            index.setdefault(name, []).append({
                "class_fqn": class_fqn,
                "file": str(p),
                "start_line": start_line,
                "end_line": end_line,
                "signature": name + "(...)",
                "modifiers": [],
                "body_preview": body,
            })
    return index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("-o", default=None)
    args = ap.parse_args()

    root = Path(args.root)
    out = Path(args.o) if args.o else root.parent / "index" / "functions.json"

    for backend_name, fn in [
        ("javalang", index_with_javalang),
        ("tree-sitter", index_with_treesitter),
        ("regex", index_with_regex),
    ]:
        try:
            index = fn(root)
            backend = backend_name
            break
        except ImportError as e:
            print(f"[codeindex] {backend_name} unavailable ({e})", file=sys.stderr)
            continue
        except Exception as e:
            print(f"[codeindex] {backend_name} failed: {e}", file=sys.stderr)
            continue
    else:
        sys.exit("[codeindex] all backends failed")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, indent=2))
    print(f"[codeindex] backend={backend} symbols={len(index)} -> {out}")


if __name__ == "__main__":
    main()
