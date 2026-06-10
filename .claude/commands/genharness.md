---
description: Auto-generate a Jazzer harness for a target class/method.
argument-hint: "[target-class.method or description of what to fuzz]"
---

Generate a Jazzer harness for: ${1:-the most sink-reaching public methods}

1. Ensure the index exists: `python tools/codeindex.py workspace/target` if missing.
2. Delegate to the `harness-generator` subagent, passing the target focus
   "${1:-pick the public methods most likely to reach a java-sinks API}".
3. The subagent writes the harness, compiles it, smoke-tests it, and updates
   `workspace/findings/harness.json`.
4. Report the generated harness class name and which target methods it reaches.
   Suggest running `/campaign <class>` next.
