#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse


NEWS_PATH = re.compile(
    r"/(?:news|press|presse|pressemeldinger|aktuelt|aktuelt-arkiv|nyheter|artikler|artikkel|blog)(?:/|$)",
    re.I,
)


def _canonical_page_url(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))


def extract_news_observations(profile: dict, max_articles: int = 2) -> list[dict]:
    website = (profile.get("evidence") or {}).get("website") or {}
    value = website.get("value") or {}
    identity = value.get("identity_assessment") or {}
    if website.get("status") != "available" or not identity.get("publishable"):
        return []

    homepage_url = _canonical_page_url(value.get("final_url") or website.get("source_url") or "")
    pages = [
        page for page in (value.get("pages") or [])
        if NEWS_PATH.search(urlparse(str(page.get("url") or "")).path)
    ]
    if not pages:
        return []

    # Prefer deeper, individual article pages over shallow archive/listing pages.
    pages.sort(key=lambda page: (-len([part for part in urlparse(str(page.get("url") or "")).path.split("/") if part]), str(page.get("url") or "")))

    org = str(profile["organisation_number"])
    retrieved_at = website.get("retrieved_at")

    observations = []
    seen_urls = {homepage_url}
    seen_spans = set()

    for page in pages:
        url = str(page.get("url") or "").strip()
        digest = str(page.get("content_sha256") or "").strip()
        title = str(page.get("title") or "Company news/activity page").strip()

        if not url.startswith(("http://", "https://")) or len(digest) != 64:
            continue

        canon_url = _canonical_page_url(url)
        if canon_url in seen_urls:
            continue

        span = title[:1200]
        if not span or span in seen_spans:
            continue

        seen_urls.add(canon_url)
        seen_spans.add(span)

        obs = {
            "id": "company-site-news-" + hashlib.sha256(f"{org}|{url}".encode()).hexdigest()[:24],
            "organisation_number": org,
            "platform": "company_site",
            "signal_type": "public_post",
            "source_url": url,
            "retrieved_at": retrieved_at,
            "content_sha256": digest,
            "exact_entity": True,
            "identity_proof": [{"type": "website_identity_gate", "score": identity.get("score"), "method": identity.get("method")}],
            "acquisition_mode": "permitted_public_page",
            "rights_status": "approved",
            "source_class": "company_site",
            "evidence_span": span,
            "metrics": {"captured_news_pages": len(pages), "interpretation": "Company-owned activity; not independent sentiment."},
            "strategy": "company_site_activity",
        }
        observations.append(obs)
        if len(observations) >= max_articles:
            break

    return observations


def observation(profile: dict) -> dict | None:
    """Return the primary news observation for backward compatibility."""
    items = extract_news_observations(profile, max_articles=1)
    return items[0] if items else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract company-owned activity from exact-site bounded news pages.")
    parser.add_argument("--profiles", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--max-articles", type=int, default=2)
    args = parser.parse_args()
    profiles = [json.loads(line) for line in Path(args.profiles).read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = []
    companies_with_activity = 0
    for profile in profiles:
        items = extract_news_observations(profile, max_articles=args.max_articles)
        if items:
            companies_with_activity += 1
            rows.extend(items)
    Path(args.output).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    report = {
        "connector": "exact_company_site_news_activity_v1",
        "profiles": len(profiles),
        "companies_with_activity": companies_with_activity,
        "observations": len(rows),
        "claim_boundary": "Company-owned activity only; never treated as independent sentiment.",
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
