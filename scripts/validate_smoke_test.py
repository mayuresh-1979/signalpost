#!/usr/bin/env python3
"""Validate a real 100-company Signalpost batch and write an auditable smoke report."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from norway_company_agent.batch import TERMINAL_STATES  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: validate_smoke_test.py INPUT PROFILES ENVELOPES RUN_REPORT")
    input_path, profiles_path, envelopes_path, run_report_path = map(Path, sys.argv[1:])
    inputs = read_jsonl(input_path)
    profiles = read_jsonl(profiles_path)
    envelopes = read_jsonl(envelopes_path)
    expected = [str(row.get("organisation_number", "")) for row in inputs]
    profile_ids = [str(row.get("organisation_number", "")) for row in profiles]
    envelope_ids = [str(row.get("organisation_number", "")) for row in envelopes]

    valid_states = all(
        row.get("state") in TERMINAL_STATES
        and all(module.get("state") in TERMINAL_STATES for module in row.get("modules", {}).values())
        for row in envelopes
    )
    checks = {
        "exactly_100_inputs": len(inputs) == 100,
        "input_ids_unique": len(expected) == len(set(expected)),
        "exactly_100_profiles": len(profiles) == 100,
        "exactly_100_envelopes": len(envelopes) == 100,
        "profile_ids_unique": len(profile_ids) == len(set(profile_ids)),
        "envelope_ids_unique": len(envelope_ids) == len(set(envelope_ids)),
        "profile_input_alignment": profile_ids == expected,
        "envelope_input_alignment": envelope_ids == expected,
        "all_envelope_states_terminal": valid_states,
        "run_report_exists": run_report_path.exists(),
    }
    run_report = json.loads(run_report_path.read_text(encoding="utf-8")) if run_report_path.exists() else None
    report = {
        "report_type": "signalpost_100_company_smoke_test",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "test_mode": "live_batch",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "commit_sha": os.environ.get("GITHUB_SHA", "local"),
        "workflow_run_url": os.environ.get("GITHUB_SERVER_URL", "https://github.com") + "/" + os.environ.get("GITHUB_REPOSITORY", "unknown/unknown") + "/actions/runs/" + os.environ.get("GITHUB_RUN_ID", "local"),
        "counts": {"inputs": len(inputs), "profiles": len(profiles), "envelopes": len(envelopes)},
        "checks": checks,
        "terminal_envelope_states": {
            state: sum(1 for row in envelopes if row.get("state") == state)
            for state in sorted(TERMINAL_STATES)
        },
        "artifacts": {
            str(input_path): sha256(input_path),
            str(profiles_path): sha256(profiles_path),
            str(envelopes_path): sha256(envelopes_path),
            str(run_report_path): sha256(run_report_path) if run_report_path.exists() else None,
        },
        "agent_run_report": run_report,
        "note": "Generated from an executed live batch. A PASS means output-contract checks pass; it does not mean the official Builderr score is 65/100 or higher."
    }
    output = Path("out/smoke-test/100-company-live-report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": checks, "report": str(output)}, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
