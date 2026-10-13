#!/usr/bin/env python3
"""Validate the exported Signalpost JSONL against the published Builderr envelope shape."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ALLOWED = {"available", "not_available", "blocked", "not_applicable", "ambiguous", "failed"}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_builderr_contract.py OUTPUT.jsonl")
    rows = read_jsonl(Path(sys.argv[1]))
    errors: list[str] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        org = str(row.get("organisation_number") or "")
        if not re.fullmatch(r"\d{9}", org):
            errors.append(f"row {i}: invalid organisation_number")
        if org in seen:
            errors.append(f"row {i}: duplicate organisation_number {org}")
        seen.add(org)
        if row.get("status") not in ALLOWED:
            errors.append(f"row {i}: invalid top-level terminal status")
        for key in ("run", "claims", "evidence", "changes", "errors", "operations"):
            if key not in row:
                errors.append(f"row {i}: missing {key}")
        run = row.get("run") or {}
        if not run.get("run_id") or not run.get("started_at") or not run.get("completed_at"):
            errors.append(f"row {i}: incomplete run metadata")
        if run.get("terminal_status") not in {"completed", "failed"}:
            errors.append(f"row {i}: invalid run.terminal_status")
        evidence = row.get("evidence") or []
        evidence_ids = {item.get("id") for item in evidence}
        for item in evidence:
            if not item.get("id") or not item.get("source_url") or not item.get("retrieved_at"):
                errors.append(f"row {i}: evidence missing id/source_url/retrieved_at")
            parsed = urlparse(str(item.get("source_url") or ""))
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                errors.append(f"row {i}: evidence source_url is not HTTP(S)")
            if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("content_sha256") or "")):
                errors.append(f"row {i}: evidence missing valid content_sha256")
        for claim in row.get("claims") or []:
            if not claim.get("field"):
                errors.append(f"row {i}: claim missing field")
            if claim.get("availability") not in ALLOWED:
                errors.append(f"row {i}: invalid claim availability")
            if not isinstance(claim.get("evidence_ids"), list):
                errors.append(f"row {i}: claim evidence_ids must be a list")
            for eid in claim.get("evidence_ids", []):
                if eid not in evidence_ids:
                    errors.append(f"row {i}: dangling evidence id {eid}")
            if claim.get("availability") != "available" and claim.get("value") is not None:
                errors.append(f"row {i}: unavailable/ambiguous claim must not expose a value")
        operations = row.get("operations") or {}
        if not isinstance(operations.get("requests"), int) or not isinstance(operations.get("runtime_ms"), int):
            errors.append(f"row {i}: operations requests/runtime_ms must be integers")
        if not isinstance(operations.get("third_party_cost_usd"), (int, float)):
            errors.append(f"row {i}: operations third_party_cost_usd must be numeric")
    report = {
        "status": "PASS" if not errors else "FAIL",
        "rows": len(rows),
        "unique_organisation_numbers": len(seen),
        "errors_count": len(errors),
        "errors": errors[:100],
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
