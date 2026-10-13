#!/usr/bin/env python3
"""Audit provenance and entity-identity invariants in a Signalpost profile JSONL."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


HASH_RE = re.compile(r"^[0-9a-f]{64}$")
ORG_RE = re.compile(r"^\d{9}$")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def name_tokens(value: object) -> set[str]:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return set(re.findall(r"[a-z0-9]+", text.encode("ascii", "ignore").decode("ascii")))


def valid_http_url(value: object) -> bool:
    try:
        parsed = urlparse(str(value or ""))
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def valid_timestamp(value: object) -> bool:
    if not value:
        return False
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: audit_evidence_quality.py PROFILES.jsonl REPORT.json")
    profile_path, report_path = map(Path, sys.argv[1:])
    profiles = read_jsonl(profile_path)
    issues: list[dict] = []
    module_counts: dict[str, Counter] = {}
    available_evidence = 0
    provenance_complete = 0
    website_available = 0
    website_publishable = 0
    website_quarantined = 0
    empty_locations = 0
    empty_financial_records = 0
    empty_roles = 0

    def issue(code: str, org: str, detail: str) -> None:
        issues.append({"code": code, "organisation_number": org, "detail": detail})

    orgs = [str(p.get("organisation_number", "")) for p in profiles]
    if len(orgs) != len(set(orgs)):
        issue("duplicate_profile_org", "", "Profile organisation numbers are not unique.")
    for p in profiles:
        org = str(p.get("organisation_number", ""))
        if not ORG_RE.fullmatch(org):
            issue("invalid_org_number", org, "Expected a nine-digit Norwegian organisation number.")
        evs = p.get("evidence") or {}
        for module, record in evs.items():
            if not isinstance(record, dict):
                issue("invalid_evidence_record", org, f"{module} evidence is not an object.")
                continue
            status = str(record.get("status", ""))
            module_counts.setdefault(module, Counter())[status or "<missing>"] += 1
            if status == "available":
                available_evidence += 1
                required_ok = (
                    valid_http_url(record.get("source_url"))
                    and valid_timestamp(record.get("retrieved_at"))
                    and bool(HASH_RE.fullmatch(str(record.get("content_sha256", ""))))
                )
                if required_ok:
                    provenance_complete += 1
                else:
                    issue("available_evidence_missing_provenance", org, f"{module} needs a valid HTTP(S) source URL, retrieval timestamp and SHA-256.")
            value = record.get("value") or {}
            if module == "registry" and isinstance(value, dict):
                if str(value.get("organisasjonsnummer", "")) != org:
                    issue("registry_org_mismatch", org, "Bulk registry row organisation number differs from profile ID.")
                registry_name = value.get("navn")
                if registry_name and p.get("name") and name_tokens(registry_name) != name_tokens(p.get("name")):
                    issue("registry_name_mismatch", org, "Bulk registry row name differs from profile name after token normalization.")
            elif module == "registry_live" and isinstance(value, dict):
                if str(value.get("organisation_number", "")) != org:
                    issue("live_registry_org_mismatch", org, "Live registry response organisation number differs from profile ID.")
                live_name = value.get("name")
                if live_name and p.get("name") and name_tokens(live_name) != name_tokens(p.get("name")):
                    issue("live_registry_name_mismatch", org, "Live registry name differs from profile name after token normalization.")
                if not str(record.get("source_url", "")).rstrip("/").endswith("/" + org):
                    issue("live_registry_url_mismatch", org, "Live registry URL does not end with this organisation number.")
            elif module == "financials":
                if not str(record.get("source_url", "")).rstrip("/").endswith("/" + org):
                    issue("financials_url_mismatch", org, "Financial endpoint URL does not end with this organisation number.")
                records = value.get("records", []) if isinstance(value, dict) else []
                if not records:
                    empty_financial_records += 1
            elif module == "roles":
                if not str(record.get("source_url", "")).rstrip("/").endswith("/" + org + "/roller"):
                    issue("roles_url_mismatch", org, "Roles endpoint URL does not match this organisation number.")
                if not (value.get("roles") if isinstance(value, dict) else []):
                    empty_roles += 1
            elif module == "locations":
                locations = value.get("locations", []) if isinstance(value, dict) else []
                if not locations:
                    empty_locations += 1
                for loc in locations:
                    if not ORG_RE.fullmatch(str(loc.get("organisation_number", ""))):
                        issue("invalid_subunit_org_number", org, "A location has no valid nine-digit subunit organisation number.")
                    if not loc.get("name"):
                        issue("location_missing_name", org, "A location record has no name.")
            elif module == "website":
                if status == "available":
                    website_available += 1
                    assessment = value.get("identity_assessment") if isinstance(value, dict) else None
                    if not isinstance(assessment, dict):
                        issue("website_missing_identity_assessment", org, "Website evidence is available but has no identity assessment.")
                    else:
                        publishable = assessment.get("publishable") is True
                        if publishable:
                            website_publishable += 1
                            if assessment.get("status") != "exact" or float(assessment.get("score") or 0) < 0.9:
                                issue("website_publishable_without_strong_identity", org, "Publishable website must have exact identity status and score >= 0.90.")
                        else:
                            website_quarantined += 1

    checks = {
        "profiles_present": len(profiles) > 0,
        "profile_org_numbers_valid": all(ORG_RE.fullmatch(org) for org in orgs),
        "profile_org_numbers_unique": len(orgs) == len(set(orgs)),
        "all_available_evidence_has_provenance": available_evidence == provenance_complete,
        "no_detected_entity_or_source_url_mismatches": not any(
            item["code"] in {
                "registry_org_mismatch", "registry_name_mismatch",
                "live_registry_org_mismatch", "live_registry_name_mismatch",
                "live_registry_url_mismatch", "financials_url_mismatch",
                "roles_url_mismatch", "website_publishable_without_strong_identity",
            } for item in issues
        ),
        "website_identity_gate_respected": not any(
            item["code"] in {"website_missing_identity_assessment", "website_publishable_without_strong_identity"}
            for item in issues
        ),
    }
    report = {
        "report_type": "signalpost_evidence_quality_audit",
        "status": "PASS" if all(checks.values()) else "REVIEW_REQUIRED",
        "scope": "Structural provenance and identity invariants only; this is not a human factual-accuracy audit or official Builderr score.",
        "generated_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "profile_count": len(profiles),
        "available_evidence_records": available_evidence,
        "available_evidence_with_complete_provenance": provenance_complete,
        "website": {
            "available": website_available,
            "publishable_after_identity_gate": website_publishable,
            "quarantined_for_uncertain_identity": website_quarantined,
        },
        "empty_result_counts_for_manual_review": {
            "locations_without_matches": empty_locations,
            "financials_without_records": empty_financial_records,
            "roles_without_records": empty_roles,
        },
        "module_status_counts": {m: dict(c) for m, c in sorted(module_counts.items())},
        "checks": checks,
        "issue_count": len(issues),
        "issues": issues,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "profile_count": len(profiles),
        "available_evidence_records": available_evidence,
        "provenance_complete": provenance_complete,
        "issue_count": len(issues),
        "report": str(report_path),
        "checks": checks,
    }, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
