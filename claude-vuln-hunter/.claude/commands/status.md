---
description: Show current hunt state (BITs, verified PoVs, dedup groups).
---

Run `python tools/state.py dump` and present a concise summary:
- number of BITs discovered
- verified PoVs (bit_id + sanitizer + blob path)
- duplicate PoVs
- dedup groups
- per-BIT failed_attempts vs iteration_budget
