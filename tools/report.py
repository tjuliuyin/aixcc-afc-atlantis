#!/usr/bin/env python3
"""Render workspace/report.md deterministically from state.json + findings.

Used at the end of /hunt and /campaign so the final artifact does not depend
on the LLM re-summarizing (which can drift). One section per verified PoV.
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("VULN_HUNTER_ROOT", Path(__file__).resolve().parent.parent))
WS = ROOT / "workspace"
STATE = WS / "state.json"
BITS = WS / "findings" / "bits.json"
REPORT = WS / "report.md"


def load_json(p: Path, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def log_excerpt(blob_path: str, max_lines: int = 12) -> str:
    log = Path(blob_path).with_suffix(".log")
    if not log.exists():
        # campaign stores blob.log next to blob.bin
        log = Path(blob_path).parent / "blob.log"
    if not log.exists():
        return "(no log captured)"
    data = log.read_bytes().decode("utf-8", errors="ignore").splitlines()
    issue = [l for l in data if "FuzzerSecurityIssue" in l or l.strip().startswith("at ")]
    snippet = issue[:max_lines] if issue else data[-max_lines:]
    return "\n".join(snippet)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", default="(unknown)")
    args = ap.parse_args()

    state = load_json(STATE, {})
    bits = load_json(BITS, [])
    bits_by_id = {b.get("bit_id"): b for b in bits} if isinstance(bits, list) else {}
    verified = state.get("verified_povs", [])
    groups = state.get("groups", [])

    lines = []
    lines.append("# Vulnerability Hunt Report")
    lines.append("")
    lines.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- Harness: `{args.harness}`")
    lines.append(f"- Verified PoVs: **{len(verified)}**")
    lines.append(f"- Distinct crash groups: **{len(groups)}**")
    lines.append(f"- BITs analyzed: **{len(bits) if isinstance(bits, list) else 0}**")
    lines.append("")

    if not verified:
        lines.append("_No verified PoVs. Either no vulnerabilities were reached, "
                     "or all candidates failed reproduction._")
    else:
        lines.append("## Verified Proof-of-Vulnerabilities")
        lines.append("")
        for i, pov in enumerate(verified, 1):
            san = pov.get("sanitizer", "unknown")
            src = pov.get("source", "llm")
            blob = pov.get("blob", "")
            bit = bits_by_id.get(pov.get("bit_id")) if pov.get("bit_id") else None
            lines.append(f"### {i}. {san}  ({'campaign' if src=='campaign' else 'LLM-guided'})")
            lines.append("")
            if bit:
                lines.append(f"- **Sink**: `{bit.get('sink_class','?')}.{bit.get('sink_method','?')}` "
                             f"at `{bit.get('file','?')}:{bit.get('line','?')}`")
                lines.append(f"- **Vuln type**: {bit.get('vuln_type', san)}")
                cp = bit.get("call_path") or []
                if cp:
                    lines.append(f"- **Call path**: {' → '.join(cp)}")
                kc = bit.get("key_conditions") or []
                if kc:
                    lines.append("- **Key conditions**:")
                    for c in kc:
                        lines.append(f"  - `{c.get('file','?')}:{c.get('line','?')}` — {c.get('desc','')}")
            lines.append(f"- **Group**: {pov.get('group_id', '?')}")
            lines.append(f"- **PoV blob**: `{blob}`")
            lines.append("")
            lines.append("```text")
            lines.append(log_excerpt(blob))
            lines.append("```")
            lines.append("")

    if groups:
        lines.append("## Dedup Groups")
        lines.append("")
        lines.append("| group | sanitizer | signature |")
        lines.append("|------:|-----------|-----------|")
        for g in groups:
            lines.append(f"| {g.get('id')} | {g.get('sanitizer')} | `{g.get('signature')}` |")
        lines.append("")

    REPORT.write_text("\n".join(lines))
    print(f"[report] wrote {REPORT} ({len(verified)} PoVs, {len(groups)} groups)")


if __name__ == "__main__":
    main()
