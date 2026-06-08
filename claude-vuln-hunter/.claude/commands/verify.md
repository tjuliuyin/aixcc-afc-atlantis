---
description: Verify a single blob against the harness (reproduce + parse + dedup).
argument-hint: "<blob-path>"
---

Verify blob: $1

Delegate to the `crash-verifier` subagent with blob path `$1` and report its
JSON verdict verbatim. Do not re-interpret — the tools are authoritative.
