#!/usr/bin/env python3
"""Build raw bytes for a Jazzer FuzzedDataProvider blob.

CRITICAL byte layout (verified empirically against Jazzer 0.22.1):
  - FIXED-SIZE consumers (consumeByte/Int/Long/Bool/Char/Short) read from the
    BACK of the buffer in CALL ORDER. So the FIRST consumeByte() call reads
    the LAST byte of the blob.
  - VARIABLE-SIZE consumers (consumeString/Bytes/consumeRemainingAs*) read
    from the FRONT of the buffer in CALL ORDER. The FIRST consumeString call
    gets the head; the last variable consumer gets the tail.

So a harness like
    int sel  = data.consumeByte();
    String s = data.consumeRemainingAsString();
needs a blob whose LAST byte = sel and whose FRONT bytes = s.

Usage (library):
    from fdp_builder import FDPBuilder
    blob = (FDPBuilder()
            .put_remaining_string("'aee")   # variable -> goes at FRONT
            .put_byte(2)                    # fixed -> goes at BACK
            .build())

CLI:
    python tools/fdp_builder.py emit --bytes 2 --remaining-string "'aee" -o blob.bin
The CLI lays out variable-strings at the FRONT and fixed bytes at the BACK
regardless of the order of CLI args, matching the common harness pattern
"consumeByte then consumeRemainingAsString".
"""
from __future__ import annotations
import argparse
import struct
import sys
from pathlib import Path


class FDPBuilder:
    """FDP serializer.

    Internally we keep two ordered lists:
      _front_vars:  variable-size chunks, consumed FIRST-to-LAST from the front.
      _back_fixed:  fixed-size atoms, consumed FIRST-to-LAST from the back.
    The build() output is:  b"".join(_front_vars) + bytes(reversed(_back_fixed))
    """

    def __init__(self):
        self._front_vars: list[bytes] = []
        self._back_fixed: list[bytes] = []

    # --- fixed-size, BACK of buffer ---
    def put_byte(self, v: int) -> "FDPBuilder":
        self._back_fixed.append(bytes([v & 0xFF])); return self

    def put_bool(self, v: bool) -> "FDPBuilder":
        self._back_fixed.append(bytes([1 if v else 0])); return self

    def put_short(self, v: int) -> "FDPBuilder":
        self._back_fixed.append(struct.pack(">h", v & 0xFFFF)); return self

    def put_int(self, v: int) -> "FDPBuilder":
        self._back_fixed.append(struct.pack(">i", v & 0xFFFFFFFF)); return self

    def put_long(self, v: int) -> "FDPBuilder":
        self._back_fixed.append(struct.pack(">q", v & 0xFFFFFFFFFFFFFFFF)); return self

    # --- variable-size, FRONT of buffer ---
    def put_string(self, s: str) -> "FDPBuilder":
        """For consumeString(maxLen). First put_string is consumed first."""
        self._front_vars.append(s.encode("utf-8")); return self

    def put_bytes(self, b: bytes) -> "FDPBuilder":
        self._front_vars.append(bytes(b)); return self

    def put_remaining_string(self, s: str) -> "FDPBuilder":
        """For consumeRemainingAsString(). Should be the LAST variable consumer
        in the harness, so we keep it last in _front_vars."""
        self._front_vars.append(s.encode("utf-8")); return self

    def build(self) -> bytes:
        # variable values: head-to-tail in the order they were put
        # fixed atoms: at the back, the FIRST put_byte ends up CLOSEST to the
        # end of the buffer (consumed FIRST), so we lay them out reversed.
        return b"".join(self._front_vars) + b"".join(reversed(self._back_fixed))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit", help="build a blob")
    e.add_argument("--bytes", type=str, default="",
                   help="comma-separated fixed BYTES consumed by consumeByte() in CALL ORDER; "
                        "e.g. '2,0,255' means consumeByte=2, consumeByte=0, consumeByte=255")
    e.add_argument("--string", action="append", default=[],
                   help="variable consumeString(maxLen) values, in call order (front-to-tail)")
    e.add_argument("--remaining-string", default=None,
                   help="the consumeRemainingAsString() value (last variable consumer)")
    e.add_argument("--ints", type=str, default="",
                   help="comma-separated consumeInt values in call order")
    e.add_argument("-o", required=True)
    args = ap.parse_args()

    if args.cmd == "emit":
        b = FDPBuilder()
        for s in args.string:
            b.put_string(s)
        if args.remaining_string is not None:
            b.put_remaining_string(args.remaining_string)
        if args.ints:
            for tok in args.ints.split(","):
                tok = tok.strip()
                if tok:
                    b.put_int(int(tok, 0))
        if args.bytes:
            for tok in args.bytes.split(","):
                tok = tok.strip()
                if tok:
                    b.put_byte(int(tok, 0))
        Path(args.o).write_bytes(b.build())
        print(f"wrote {Path(args.o).stat().st_size} bytes to {args.o}")


if __name__ == "__main__":
    main()
