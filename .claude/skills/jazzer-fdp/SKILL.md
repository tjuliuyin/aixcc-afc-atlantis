---
name: jazzer-fdp
description: How Jazzer's FuzzedDataProvider lays out bytes and how to assemble
  a deterministic PoV blob. Load before pov-generator writes any gen.py that
  targets an FDP harness.
---

# Jazzer FuzzedDataProvider (FDP) byte layout

EMPIRICALLY VERIFIED on Jazzer 0.22.1:

- **FIXED-SIZE consumers** (`consumeByte`, `consumeInt`, `consumeBoolean`,
  `consumeShort`, `consumeLong`, `consumeChar`) read from the **BACK** of the
  buffer in **CALL ORDER**. So the first `consumeByte()` call returns the
  LAST byte of the blob; the second `consumeByte()` returns the second-to-last
  byte; etc.

- **VARIABLE-SIZE consumers** (`consumeString(maxLength)`,
  `consumeBytes(maxLength)`, `consumeRemainingAsString`,
  `consumeRemainingAsBytes`) read from the **FRONT** of the buffer in
  **CALL ORDER**. The first call gets the head; the last variable consumer
  gets the tail.

The helper `tools/fdp_builder.py` hides all of this — use it.

## Library usage (preferred)

```python
import sys
sys.path.insert(0, "tools")
from fdp_builder import FDPBuilder

# Harness:
#   int selector  = data.consumeByte();                  // fixed (back)
#   String s      = data.consumeRemainingAsString();     // variable (front)
# Recipe:
blob = (FDPBuilder()
        .put_remaining_string("'aee")   # variable goes at the FRONT
        .put_byte(2)                    # fixed goes at the BACK
        .build())
# Resulting blob bytes: "'aee" + 0x02
open(sys.argv[1], "wb").write(blob)
```

## CLI usage
```bash
# Order of CLI flags doesn't matter — the CLI knows variable goes front,
# fixed goes back.
python tools/fdp_builder.py emit \
    --bytes 2 \
    --remaining-string "'aee" \
    -o blob.bin
# Produces: b"'aee\x02"
```

## Mapping common harness patterns

### "Selector + payload" (the demo)
```java
int selector = data.consumeByte();                    // 1 fixed (back)
String payload = data.consumeRemainingAsString();     // 1 variable (front)
```
Recipe:
```python
FDPBuilder().put_remaining_string(PAYLOAD).put_byte(SEL).build()
# bytes: PAYLOAD || SEL
```

### "Selector + bounded name + rest"
```java
int selector = data.consumeByte();
String name  = data.consumeString(8);
String rest  = data.consumeRemainingAsString();
```
Recipe (note: put_string is consumed BEFORE put_remaining_string, so put it first):
```python
(FDPBuilder()
    .put_string("tenant42")
    .put_remaining_string("...long tail...")
    .put_byte(SEL)
    .build())
# bytes: "tenant42" || "...long tail..." || SEL
```

### "Two-byte selector + string"
```java
int kind = data.consumeByte();
int sub  = data.consumeByte();
String s = data.consumeRemainingAsString();
```
Recipe (call order matters — first put_byte is consumed FIRST, ends up at the TAIL):
```python
(FDPBuilder()
    .put_remaining_string(s)
    .put_byte(KIND)   # first put -> tail of blob -> read first
    .put_byte(SUB)    # second put -> next-to-tail
    .build())
# bytes: s || SUB || KIND
```

## Key conditions reminder
Before placing the sanitizer-triggering payload, ALWAYS satisfy:
- the routing byte (e.g. `selector % 3 == 0`)
- magic-byte / prefix checks (`startsWith("FUZZ")`)
- length guards (`size >= N`)
- character filters (use synonyms if a token is filtered)

Then place the payload that trips the sanitizer (see `sanitizer-lore`).

## Quick magic-trigger cheat sheet (from sanitizer-lore)

| vuln_type             | minimal payload         |
|-----------------------|--------------------------|
| sql-injection         | `'aee` (unmatched quote) |
| os-command-injection  | the program name must literally equal `jazze` (first argv element) |
| reflective-call (rce) | `jaz.Zer` (loads + instantiates Jazzer's honeypot class) |
| regex-injection       | `(a+)+$` against many `a`s (ReDoS), or the pattern `\E]\E]]]]]` |
| ssrf                  | a URL whose host triggers Socket.connect to a Jazzer-watched target |
