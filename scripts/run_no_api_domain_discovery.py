#!/usr/bin/env python3
"""Conservative, no-search-API website discovery by testing a few guessed domains.

This is a candidate generator, not a search engine. It only fetches public HTTP(S)
pages, respects robots.txt through the existing website fetcher, and never promotes
a guessed domain into canonical website evidence automatically.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.evidence import evidence, utc_now  # noqa: E402
from norway_company_agent.identity import assess_guessed_website_identity  # noqa: E402
from norway_company_agent.website import fetch_website  # noqa: E402

LEGAL_SUFFIXES = {
    "as", "asa", "ans", "da", "enk", "nuf", "sa", "iks", "bbl",
    "stiftelse", "foreining", "forening", "lag",
}
MAX_CANDIDATES_PER_COMPANY = 3


def slug_tokens(name: str) -> list[str]:
    text = unicodedata.normalize("NFKD", str(name or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return tokens


def guessed_domains(name: str, limit: int = MAX_CANDIDATES_PER_COMPANY) -> list[str]:
    """Return a small deterministic list; never infer or publish identity from the name alone."""
    tokens = slug_tokens(name)
    if not tokens:
        return []
    compact = "".join(tokens)
    hyphenated = "-".join(tokens)
    candidates = [f"{compact}.no", f"{hyphenated}.no", f"{compact}.com"]
    unique: list[str] = []
    for domain in candidates:
        if domain not in unique:
            unique.append(domain)
        if len(unique) >= limit:
            break
    return unique


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temp.replace(path)


def has_known_website(row: dict[str, Any]) -> bool:
    if row.get("website"):
        return True
    record = (row.get("evidence") or {}).get("website") or {}
    return record.get("status") == "available" and bool(record.get("source_url"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Try a bounded set of guessed company domains without a search API; never auto-promote."
    )
    parser.add_argument("--input", required=True, help="Input profiles JSONL")
    parser.add_argument("--output", required=True, help="Output profiles JSONL (use an isolated path)")
    parser.add_argument("--report", required=True, help="JSON metrics report")
    parser.add_argument("--limit", type=int, default=20, help="Maximum missing-website profiles to inspect")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--min-interval", type=float, default=0.5)
    args = parser.parse_args()
    if args.limit < 1 or args.timeout <= 0 or args.min_interval < 0:
        parser.error("--limit and --timeout must be positive; --min-interval cannot be negative")

    rows = read_jsonl(Path(args.input))
    counts: Counter[str] = Counter()
    started_at = utc_now()
    queried = 0
    for row in rows:
        if queried >= args.limit:
            break
        if has_known_website(row):
            counts["known_website_skipped"] += 1
            continue
        domains = guessed_domains(str(row.get("name") or ""))
        if not domains:
            counts["no_usable_name"] += 1
            continue
        queried += 1
        counts["profiles_attempted"] += 1
        candidates_reviewed: list[dict[str, Any]] = []
        first_fetch: dict[str, Any] | None = None
        accepted: dict[str, Any] | None = None

        for domain in domains:
            # Passing a bare domain lets the existing fetcher attempt HTTPS then HTTP.
            website, ops = fetch_website(domain, timeout=args.timeout, crawl_secondary=False)
            counts["http_requests"] += int(ops.get("requests", 0))
            counts["bytes_received"] += int(ops.get("bytes", 0))
            if website.get("status") != "available":
                candidates_reviewed.append({
                    "domain": domain,
                    "fetch_status": website.get("status"),
                    "identity_status": "not_assessed",
                })
                time.sleep(args.min_interval)
                continue

            website["source_type"] = "no_api_guessed_domain_candidate"
            website_value = website.get("value") or {}
            digest = website_value.get("content_sha256") or website.get("content_sha256")
            if digest:
                website["content_sha256"] = digest
            if first_fetch is None:
                first_fetch = website

            test_row = dict(row)
            test_evidence = dict(row.get("evidence") or {})
            test_evidence["website"] = website
            test_row["evidence"] = test_evidence
            assessment = assess_guessed_website_identity(test_row)
            publishable = bool(assessment.get("publishable"))
            candidates_reviewed.append({
                "domain": domain,
                "fetch_status": website.get("status"),
                "identity_status": assessment.get("status"),
                "identity_score": assessment.get("score"),
                "publishable_candidate": publishable,
                "reasons": assessment.get("reasons", []),
                "content_sha256": digest,
            })
            if publishable and accepted is None:
                accepted = website
                counts["identity_gate_passed"] += 1
            else:
                counts["identity_gate_rejected"] += 1
            time.sleep(args.min_interval)

        summary = {
            "method": "bounded_domain_guess_v1",
            "api_used": False,
            "candidate_domains_tested": len(candidates_reviewed),
            "candidate_results": candidates_reviewed,
            "selected_for_manual_review": accepted is not None,
            "automatic_promotion": False,
        }
        row.setdefault("evidence", {})["website_discovery"] = evidence(
            "website_discovery",
            "available" if accepted else "not_found",
            "no_api_guessed_domain_then_independent_crawl",
            "https://data.brreg.no/enhetsregisteret/api/enheter",
            value=summary,
            note=(
                "A strict guessed-domain identity gate passed; candidate remains review-only and is not promoted."
                if accepted else
                "No guessed domain passed the exact-entity identity gate; candidates are not treated as company websites."
            ),
        )
        if accepted:
            row["evidence"]["website_discovered"] = accepted
            counts["manual_review_candidates"] += 1
        elif first_fetch:
            # Keep at most one fetched page for audit/review; never label it as verified.
            row["evidence"]["website_discovered"] = first_fetch
            counts["fetched_but_unverified"] += 1
        else:
            counts["no_fetchable_candidates"] += 1

    report = {
        "generated_at": utc_now(),
        "started_at": started_at,
        "method": "bounded_domain_guess_v1",
        "api_used": False,
        "input_profiles": len(rows),
        "missing_website_profiles_attempted": queried,
        "counts": dict(counts),
        "candidate_limit_per_profile": MAX_CANDIDATES_PER_COMPANY,
        "automatic_promotion": False,
        "qualification": "not_evaluated_on_500_org_external_final_corpus",
    }
    write_jsonl(Path(args.output), rows)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
