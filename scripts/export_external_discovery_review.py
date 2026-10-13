#!/usr/bin/env python3
"""Export a privacy-conscious manual review queue from a transient-discovery pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def review_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for profile in rows:
        org = str(profile.get("organisation_number") or "").strip()
        if not org or not org.isdigit():
            raise ValueError("every profile must have a digit-only organisation_number")
        if org in seen:
            raise ValueError(f"duplicate organisation_number: {org}")
        seen.add(org)

        evidence_map = profile.get("evidence") or {}
        if not isinstance(evidence_map, dict):
            raise ValueError(f"evidence must be an object for organisation {org}")
        discovered = evidence_map.get("website_discovered")
        discovery = evidence_map.get("website_discovery")
        if not isinstance(discovered, dict):
            # Preserve abstentions/errors in the review queue so recall isn't measured only on successes.
            discovered = {}
        if not isinstance(discovery, dict):
            discovery = {}

        value = discovered.get("value") if isinstance(discovered.get("value"), dict) else {}
        source_url = discovered.get("source_url")
        url_for_id = str(source_url or value.get("canonical_url") or "")
        stable_id = hashlib.sha256(f"{org}\n{url_for_id}".encode("utf-8")).hexdigest()[:20]
        output.append({
            "id": f"discovery:{org}:{stable_id}",
            "organisation_number": org,
            "company_name": profile.get("name"),
            "candidate_url": source_url,
            "crawl_status": discovered.get("status", "no_candidate_crawled"),
            "crawl_source_type": discovered.get("source_type"),
            "retrieved_at": discovered.get("retrieved_at"),
            "content_sha256": discovered.get("content_sha256"),
            "identity_gate_publishable": value.get("publishable"),
            "identity_gate_reason": value.get("identity_gate_reason") or value.get("identity_reason"),
            "search_candidate_count": (discovery.get("value") or {}).get("candidate_count")
            if isinstance(discovery.get("value"), dict) else None,
            "selected_for_independent_crawl": (discovery.get("value") or {}).get("selected_for_independent_crawl")
            if isinstance(discovery.get("value"), dict) else None,
            "provider_status": (discovery.get("value") or {}).get("provider_status")
            if isinstance(discovery.get("value"), dict) else None,
            "raw_search_results_persisted": False,
            "exact_entity": None,
            "metric_correct": None,
            "sentiment_correct": None,
            "site_exists_and_is_company_owned": None,
            "reviewer_decision": "pending",
            "identity_evidence_url": None,
            "source_rights_checked": False,
            "source_rights_notes": "",
            "reviewer_notes": "",
        })
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", required=True, help="Output JSONL from run_brave_discovery.py")
    parser.add_argument("--output", required=True, help="New JSONL review queue; source file is never modified")
    args = parser.parse_args()
    rows = review_rows(read_jsonl(Path(args.profiles)))
    write_jsonl(Path(args.output), rows)
    print(json.dumps({
        "input_profiles": len(rows),
        "review_rows_written": len(rows),
        "pending_review_rows": sum(row["reviewer_decision"] == "pending" for row in rows),
        "raw_search_results_persisted": False,
        "labels_created": False,
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
