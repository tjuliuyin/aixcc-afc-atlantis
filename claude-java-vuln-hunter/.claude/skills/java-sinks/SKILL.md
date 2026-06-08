---
name: java-sinks
description: Catalogue of Java APIs that Jazzer ships sanitizers for, grouped
  by sanitizer family. Load before sink-finder reasons about a method body.
---

# Dangerous Java APIs (Jazzer-detected sinks)

For each API, the format is:
  `Class.method(params)` — when tainted, sanitizer fires; counter-example.

## SQL Injection (FuzzerSecurityIssueHigh)
- `java.sql.Statement.execute(String)`
- `java.sql.Statement.executeQuery(String)`
- `java.sql.Statement.executeUpdate(String)`
- `java.sql.Statement.executeLargeUpdate(String)`
- `javax.persistence.EntityManager.createQuery(String)`
Safe: `Connection.prepareStatement` + `setString` (parameterised).

## OS Command Injection (FuzzerSecurityIssueCritical)
- `java.lang.Runtime.exec(String)`
- `java.lang.Runtime.exec(String[])`
- `java.lang.ProcessBuilder.<init>(List<String>|String...)` + `start()`
Safe: well-vetted constant command + arg whitelist; never user → shell.

## Path Traversal (FuzzerSecurityIssueCritical)
- `java.io.File.<init>(String)`
- `java.nio.file.Path.of(String, String...)`
- `java.nio.file.Paths.get(String, String...)`
- `java.nio.file.Files.{read*,newInputStream,copy,move,delete*}(Path,...)`
- `java.io.FileInputStream.<init>(String|File)`
- `java.io.FileOutputStream.<init>(String|File,...)`
Safe: `Path.normalize()` then `startsWith(base)` check that rejects escapes.

## Server-Side Request Forgery (FuzzerSecurityIssueMedium)
- `java.net.URL.<init>(String)` + `openStream()` / `openConnection()`
- `java.net.URI.create(String)`
- `org.apache.http.client.HttpClient.execute(HttpUriRequest)`
- `java.net.Socket.<init>(String,int)`

## XML / XPath / XXE
- `javax.xml.xpath.XPath.evaluate(String, ...)`
- `javax.xml.parsers.DocumentBuilder.parse(InputSource)` w/o XXE disabled

## JNDI / LDAP
- `javax.naming.Context.lookup(String)`
- `javax.naming.directory.DirContext.search(...)`
- `com.sun.jndi.*`

## Deserialization (RCE family)
- `java.io.ObjectInputStream.readObject()`
- `java.io.ObjectInputStream.readUnshared()`
- `org.yaml.snakeyaml.Yaml.load(InputStream|String)` (unsafe load)
- `com.fasterxml.jackson.databind.ObjectMapper.readValue(...)` with default typing

## Reflective Call
- `java.lang.Class.forName(String,...)`
- `java.lang.reflect.Method.invoke(Object, Object...)`
- `java.lang.ClassLoader.loadClass(String)`

## Regex Injection (ReDoS)
- `java.util.regex.Pattern.compile(String,...)`
- `String.matches(String)` / `String.split(String)` (call Pattern internally)

## Native code load
- `java.lang.System.loadLibrary(String)`
- `java.lang.System.load(String)`
- `java.lang.Runtime.loadLibrary(String)`

## Heuristic clues a sink is reachable
- The string passed contains an attacker-supplied substring (look upstream).
- A check uses `startsWith` / `indexOf` / `contains` instead of an allow-list.
- A length / magic-byte guard exists but doesn't validate semantic content.
- Validation is done before normalisation (`Path.normalize`) — common bypass.
- The harness immediately catches and swallows the API's checked exception,
  so a finding is the ONLY observable signal.

## Triage rules
- A method that builds a query/command/path with `+` concatenation + a
  variable that traces back to a tainted entry argument is almost always a
  candidate; mark `is_vulnerable=true` unless a parameterised API replaces it.
- If the method uses `PreparedStatement.setX` or `Path.resolve().normalize()
  .startsWith(baseDir)` BEFORE the dangerous call, the sink is mitigated.
