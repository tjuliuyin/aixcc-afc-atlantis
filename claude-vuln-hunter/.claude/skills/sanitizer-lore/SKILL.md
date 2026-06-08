---
name: sanitizer-lore
description: Sanitizer dictionary and exploitation hints. Load before sink-finder
  or pov-generator reasons about a specific vuln_type. Mirrors Atlantis
  mlla/modules/sanitizer_info + pov_dedup sanitizer enums.
---

# AddressSanitizer (C/C++)
Crash report markers and how to trip them:
- `heap-buffer-overflow`  — read/write past a malloc'd region.
    PoV: make an index or copy length exceed the allocation size.
- `heap-use-after-free`   — access memory after free().
    PoV: drive the free path, then the re-use path, in one input.
- `stack-buffer-overflow` — write past a local array.
- `global-buffer-overflow`— write past a global array.
- `double-free`           — free the same pointer twice.
- `negative-size-param`   — pass a negative size to memcpy/alloc.
- `SEGV` / `FPE`          — null deref / divide-by-zero.

libFuzzer / standalone exit codes that count as a crash:
  1 = sanitizer error, 70 = timeout, 71 = OOM, 77 = libFuzzer default.

# Jazzer (JVM)
- Critical: File path traversal, OS Command Injection, LDAP/JNDI, ScriptEngine.
- High: SQL Injection, XPath Injection, Remote Code Execution.
- Medium: Server Side Request Forgery.
- Low: Regex Injection, OOM, Stack overflow.
Input arrives via FuzzedDataProvider; the ORDER of consumeXxx() calls matters —
match the harness's consume sequence exactly.

# PoV generation tips
- Satisfy every key_condition (magic bytes, length guards, state flags) BEFORE
  the value that trips the sanitizer.
- For BOFs: payload_len = buffer_size + delta, delta >= 1.
- For path traversal: encode `../` (and URL-decoded `%2e%2e%2f`) sequences.
- For OS command injection: include shell metacharacters `;`, `|`, `$()`.
- Keep blobs minimal — only what's needed to reach + trip the sink.
