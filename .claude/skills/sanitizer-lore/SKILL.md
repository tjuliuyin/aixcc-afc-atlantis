---
name: sanitizer-lore
description: Jazzer sanitizer dictionary. Load before sink-finder, path-analyzer,
  or pov-generator reasons about a specific JVM vuln_type. Mirrors Atlantis
  JVM_SANITIZER enum and the exploitability hints baked into mlla/modules/
  sanitizer_info.
---

# Jazzer Sanitizer Catalogue

Each entry has: the EXACT log marker Jazzer prints (used by tools/parse_crash.py),
the short name (used in BIT.vuln_type), the Java APIs hooked, and a PoV hint.

## Critical
- **FuzzerSecurityIssueCritical: File path traversal** (`path-traversal`)
    Hooks: `java.io.File.*`, `java.nio.file.Path.*`, `java.nio.file.Files.*`.
    PoV: get a path that resolves OUTSIDE the working directory and TOUCHES a
    sentinel (Jazzer creates `jazzer-traversal` honeypot files). Easiest: any
    user-controlled path with `../../...../etc/passwd` style traversal.

- **FuzzerSecurityIssueCritical: OS Command Injection** (`os-command-injection`)
    Hooks: `java.lang.Runtime.exec`, `java.lang.ProcessBuilder.start`.
    Trigger: argument list contains the magic token `jazze` as a separate
    word (Jazzer's marker). For shell wrappers (`sh -c "..."`) you need the
    injection to cause `jazze` to land as a parsed command.

- **FuzzerSecurityIssueCritical: LDAP Injection** (`ldap-injection`)
    Hooks: `javax.naming.directory.DirContext.search` and related.

- **FuzzerSecurityIssueCritical: Remote JNDI Lookup** (`jndi-lookup`)
    Hooks: `javax.naming.Context.lookup`.

- **FuzzerSecurityIssueCritical: Script Engine Injection** (`script-engine-injection`)
    Hooks: `javax.script.ScriptEngine.eval`.

## High
- **FuzzerSecurityIssueHigh: SQL Injection** (`sql-injection`)
    Hooks: `java.sql.Statement.execute*`, JDBC driver internals.
    Trigger: an `'`/`"` that escapes a string literal AND modifies parse —
    e.g. `'aee` (unterminated literal -> parser exception) was enough on H2.
    `' OR '1'='1` or `'; DROP TABLE x; --` also work.

- **FuzzerSecurityIssueHigh: XPath Injection** (`xpath-injection`)
    Hooks: `javax.xml.xpath.XPath.evaluate`.

- **FuzzerSecurityIssueHigh: Remote Code Execution** (`rce`)
    Hooks: deserialization gadgets, `ScriptEngine`, etc.

- **FuzzerSecurityIssueHigh: load arbitrary library** (`load-library`)
    Hooks: `System.loadLibrary`, `Runtime.load`.

## Medium
- **FuzzerSecurityIssueMedium: Server Side Request Forgery** (`ssrf`)
    Hooks: `java.net.URL` connect / open, sockets.
    Trigger: input rewrites URL host/port to an internal target.

## Low
- **FuzzerSecurityIssueLow: Regular Expression Injection** (`regex-injection`)
    Hooks: `java.util.regex.Pattern.compile`.
    Trigger: catastrophic regex (`(a+)+$`) or attacker-controlled pattern.

- **FuzzerSecurityIssueLow: Out of memory** (`oom`)
- **FuzzerSecurityIssueLow: Stack overflow** (`stack-overflow`)

## Exit codes that count as a finding
- `1`  — sanitizer caught a bug
- `70` — libFuzzer timeout
- `71` — libFuzzer OOM
- `77` — libFuzzer default exit (Jazzer typical for FuzzerSecurityIssue)

Also: presence of the literal string `FuzzerSecurityIssue` in stderr always
counts, regardless of exit code (some configurations swallow non-zero).

## PoV crafting tips
- ALWAYS satisfy every routing condition (selector byte, magic prefix,
  length guards) BEFORE placing the sanitizer trigger payload.
- For SQL injection: a single unmatched quote is often enough to trigger
  Jazzer's hook (the driver throws SQLException with a parse error).
- For path traversal: don't worry about reading a real file — Jazzer just
  needs Path.toAbsolutePath() to resolve outside the working dir.
- For OS command injection: the trigger token must appear as a parsed
  command/argument after shell parsing — use `;`, backtick, `$()`, `|`,
  newline depending on what the harness already filters.
- For regex injection: pattern `^(a+)+$` plus input `aaa...!` causes ReDoS.
