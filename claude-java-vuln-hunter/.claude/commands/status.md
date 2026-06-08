---
description: Show current hunt state (BITs, verified PoVs, dedup groups).
---

Run `python tools/state.py dump` and present a concise summary:
- BITs discovered (id, vuln_type, sink class.method)
- Verified PoVs (bit_id + sanitizer + blob path)
- Duplicate PoVs
- Dedup groups
- Per-BIT failed_attempts vs iteration_budget
