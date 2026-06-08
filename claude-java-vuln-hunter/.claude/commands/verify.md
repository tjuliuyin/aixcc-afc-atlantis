---
description: Verify one blob against the Jazzer harness (reproduce + parse + dedup).
argument-hint: "<blob-path> [target_class]"
---

Verify blob: $1  (harness class: ${2:-com.example.fuzz.DemoFuzzer})

Delegate to `crash-verifier` with blob path `$1` and harness `${2:-com.example.fuzz.DemoFuzzer}`.
Report its JSON verdict verbatim — the tools are authoritative.
