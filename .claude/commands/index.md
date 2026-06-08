---
description: (Re)build the method-level code index for the Java target.
---

Build the code index:
1. Run `python tools/codeindex.py workspace/target`.
2. Read `workspace/index/functions.json` and report symbol count + backend
   (`javalang` is best; `tree-sitter` second; `regex` is the fallback).
