#!/usr/bin/env python3
"""Run Signalpost end-to-end and emit a validated Builderr contract JSONL."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organisations", required=True, help="Evaluator-supplied JSON/JSONL/text batch")
    parser.add_argument("--expected-count", required=True, type=int, help="Exact number of organisations in the input batch")
    parser.add_argument("--run-id", required=True, help="Unique identifier for this run")
    parser.add_argument("--bulk", default="brreg-enheter.csv", help="BRREG entity snapshot")
    parser.add_argument("--subunits-bulk", default="brreg-underenheter.csv", help="BRREG subunits snapshot")
    parser.add_argument("--output-dir", default="out/builderr-run", help="Directory for run outputs")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.organisations)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    bulk_path = Path(args.bulk)
    if not bulk_path.is_absolute():
        bulk_path = ROOT / bulk_path
    subunits_path = Path(args.subunits_bulk)
    if not subunits_path.is_absolute():
        subunits_path = ROOT / subunits_path

    profiles = output_dir / "profiles.jsonl"
    envelopes = output_dir / "envelopes.jsonl"
    run_report = output_dir / "run-report.json"
    evidence_report = output_dir / "evidence-quality-report.json"
    contract = output_dir / "builderr-output.jsonl"

    run([
        sys.executable, str(ROOT / "scripts/run_competition_batch.py"),
        "--organisations", str(input_path),
        "--bulk", str(bulk_path),
        "--subunits-bulk", str(subunits_path),
        "--profiles-output", str(profiles),
        "--output", str(envelopes),
        "--report", str(run_report),
        "--run-id", args.run_id,
        "--expected-count", str(args.expected_count),
        "--workers", str(args.workers),
    ])
    run([
        sys.executable, str(ROOT / "scripts/audit_evidence_quality.py"),
        str(profiles), str(evidence_report),
    ])
    run([
        sys.executable, str(ROOT / "scripts/export_builderr_contract.py"),
        str(envelopes), "--output", str(contract),
    ])
    run([
        sys.executable, str(ROOT / "scripts/validate_builderr_contract.py"),
        str(contract),
    ])

    rows = [json.loads(line) for line in contract.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != args.expected_count:
        raise SystemExit(f"Expected {args.expected_count} contract rows, got {len(rows)}")
    if len({row["organisation_number"] for row in rows}) != len(rows):
        raise SystemExit("Contract output contains duplicate organisation numbers")

    print(json.dumps({
        "status": "PASS",
        "expected_count": args.expected_count,
        "contract_rows": len(rows),
        "contract_output": str(contract),
        "run_report": str(run_report),
        "evidence_quality_report": str(evidence_report),
        "note": "Structural and provenance checks passed; this is not an official Builderr score or factual-accuracy certification.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
