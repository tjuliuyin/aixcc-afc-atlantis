#!/usr/bin/env python3
"""Build a function-level code index (replaces Atlantis' CodeIndexer/Joern).

Primary backend: tree-sitter-languages (accurate). Fallback: a brace/regex
scanner so the demo runs even without tree-sitter installed.
Output: workspace/index/functions.json
  { func_name: [ {file, start_line, end_line, body_preview}, ... ] }
"""
import argparse
import json
import re
import sys
from pathlib import Path

LANG_MAP = {
    ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp",
    ".java": "java",
}

FUNC_RE = re.compile(
    r"^[A-Za-z_][\w\s\*\(\)<>,:&]*?\b([A-Za-z_]\w*)\s*\([^;{]*\)\s*\{",
    re.MULTILINE,
)


def index_with_treesitter(root: Path) -> dict:
    from tree_sitter_languages import get_parser  # may raise ImportError
    parsers, index = {}, {}
    for p in root.rglob("*"):
        lang = LANG_MAP.get(p.suffix.lower())
        if not lang or not p.is_file():
            continue
        parsers.setdefault(lang, get_parser(lang))
        src = p.read_bytes()
        tree = parsers[lang].parse(src)

        def walk(node):
            if node.type in ("function_definition", "method_declaration"):
                name = None
                for ch in node.children:
                    if ch.type in ("function_declarator", "identifier"):
                        txt = ch.text.decode("utf-8", "ignore")
                        m = re.search(r"([A-Za-z_]\w*)\s*\(", txt) or re.match(r"([A-Za-z_]\w*)", txt)
                        if m:
                            name = m.group(1)
                if name:
                    s, e = node.start_point[0] + 1, node.end_point[0] + 1
                    body = src[node.start_byte:node.end_byte][:2000].decode("utf-8", "ignore")
                    index.setdefault(name, []).append(
                        {"file": str(p), "start_line": s, "end_line": e, "body_preview": body}
                    )
            for ch in node.children:
                walk(ch)

        walk(tree.root_node)
    return index


def index_with_regex(root: Path) -> dict:
    """Brace-matching fallback (good enough for C/C++ demos)."""
    index = {}
    for p in root.rglob("*"):
        lang = LANG_MAP.get(p.suffix.lower())
        if not lang or not p.is_file():
            continue
        text = p.read_text(errors="ignore")
        lines = text.splitlines()
        for m in FUNC_RE.finditer(text):
            name = m.group(1)
            if name in ("if", "for", "while", "switch", "sizeof", "return"):
                continue
            start_off = m.start()
            start_line = text.count("\n", 0, start_off) + 1
            # brace match from the opening {
            depth, i = 0, text.index("{", m.start())
            end = i
            for j in range(i, len(text)):
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        end = j
                        break
            end_line = text.count("\n", 0, end) + 1
            body = "\n".join(lines[start_line - 1:end_line])[:2000]
            index.setdefault(name, []).append(
                {"file": str(p), "start_line": start_line, "end_line": end_line, "body_preview": body}
            )
    return index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("-o", default=None)
    args = ap.parse_args()

    root = Path(args.root)
    out = Path(args.o) if args.o else root.parent / "index" / "functions.json"

    try:
        index = index_with_treesitter(root)
        backend = "tree-sitter"
    except Exception as e:  # ImportError or parser issue
        print(f"[codeindex] tree-sitter unavailable ({e}); using regex fallback", file=sys.stderr)
        index = index_with_regex(root)
        backend = "regex"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, indent=2))
    print(f"[codeindex] backend={backend} symbols={len(index)} -> {out}")


if __name__ == "__main__":
    main()
