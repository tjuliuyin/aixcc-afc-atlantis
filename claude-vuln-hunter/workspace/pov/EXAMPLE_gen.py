#!/usr/bin/env python3
"""Reference PoV generator for the demo BIT (heap-buffer-overflow in
parse_record). This is what the `pov-generator` subagent is expected to write
into workspace/pov/<bit_id>/iter_N/gen.py.

It satisfies every key condition on the path, then trips the sink:
  - key_condition: size >= 5
  - key_condition: bytes[0:4] == b"FUZZ"   (magic guard)
  - sink:          memcpy(buf /*16*/, payload, declared_len)
                   -> set declared_len = 0xff > 16  => heap-buffer-overflow

Usage:  python EXAMPLE_gen.py <output-path>
"""
import sys

MAGIC = b"FUZZ"
DECLARED_LEN = 0xFF          # > 16-byte buffer => overflow
PAYLOAD = b"A" * DECLARED_LEN  # enough bytes so the copy actually overruns


def build() -> bytes:
    return MAGIC + bytes([DECLARED_LEN]) + PAYLOAD


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "blob.bin"
    with open(out, "wb") as f:
        f.write(build())
    print(f"wrote {len(build())} bytes to {out}")


if __name__ == "__main__":
    main()
