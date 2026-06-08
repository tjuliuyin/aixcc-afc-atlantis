---
description: (Re)build the function-level code index for the target.
---

Build the code index:

1. Run `python tools/codeindex.py workspace/target`.
2. Read `workspace/index/functions.json` and report how many symbols were
   indexed and which backend (tree-sitter or regex) was used.
