#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def extract_handles(profile: dict) -> list[dict]:
    website = (profile.get("evidence") or {}).get("website") or {}
    value = website.get("value") or {}
    identity = value.get("identity_assessment") or {}
    if website.get("status") != "available" or not identity.get("publishable"):
        return []

    source_url = value.get("final_url") or website.get("source_url")
    digest = value.get("content_sha256") or website.get("content_sha256")
    if not source_url or not digest or len(str(digest)) != 64:
        return []

    socials = value.get("social_links") or []
    org = str(profile["organisation_number"])
    retrieved_at = website.get("retrieved_at")

    observations = []
    for link in socials:
        platform = str(link.get("platform") or "").casefold().strip()
        url = str(link.get("url") or "").strip()
        if not platform or not url:
            continue
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        obs_id = f"verified-handle-{org}-{platform}-{url_hash}"
        observations.append(
            {
                "id": obs_id,
                "organisation_number": org,
                "platform": platform,
                "signal_type": "profile_handle",
                "source_url": url,
                "retrieved_at": retrieved_at,
                "content_sha256": digest,
                "exact_entity": True,
                "identity_proof": [
                    {
                        "type": "exact_website_outbound_social_link",
                        "website_url": source_url,
                        "platform": platform,
                    },
                    {
                        "type": "social_handle_identity_gate",
                        "status": "exact",
                        "website_identity_score": identity.get("score"),
                    },
                ],
                "acquisition_mode": "permitted_public_page",
                "rights_status": "approved",
                "source_class": "company_social",
                "evidence_span": f"Exact company-owned {platform} handle {url} verified on {source_url}.",
                "strategy": "verified_handle_extraction",
            }
        )
    return observations


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract verified social profile handles from exact-identity website evidence.")
    parser.add_argument("--profiles", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    rows = [json.loads(line) for line in Path(args.profiles).read_text(encoding="utf-8").splitlines() if line.strip()]
    observations = []
    companies_with_handles = 0
    for profile in rows:
        handles = extract_handles(profile)
        if handles:
            companies_with_handles += 1
            observations.extend(handles)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in observations), encoding="utf-8")
    report = {
        "connector": "exact_website_verified_social_handles_v1",
        "profiles": len(rows),
        "companies_with_handles": companies_with_handles,
        "observations": len(observations),
        "platforms": sorted({item["platform"] for item in observations}),
        "claim_boundary": "Discovered and identity-gated company social profile handles from verified company websites.",
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
