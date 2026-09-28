#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


LEGAL = {"as", "asa", "sa", "ba", "da", "ans", "enk", "nuf", "sti"}
UA = "SignalpostResearchPOC/1.0 (https://builderr.ai; bounded qualification run)"


def norm(value: object) -> str:
    return " ".join(token for token in re.findall(r"[a-z0-9æøå]+", str(value or "").casefold()) if token not in LEGAL)


def exact_title_match(company_name: str, title: str) -> bool:
    company_tokens = re.findall(r"[a-z0-9æøå]+", str(company_name or "").casefold())
    title_tokens = re.findall(r"[a-z0-9æøå]+", str(title or "").rsplit(" - ", 1)[0].casefold())
    if not company_tokens or not title_tokens or len(company_tokens) > len(title_tokens):
        return False
    # A full legal name may occur after ordinary headline grammar ("fra X AS"),
    # but not inside a longer company name ("Aneo Roan Vind Holding AS").
    allowed_predecessors = {"av", "for", "fra", "hos", "i", "med", "om", "på", "til", "og", "kjøper", "velger"}
    for index in range(len(title_tokens) - len(company_tokens) + 1):
        if title_tokens[index:index + len(company_tokens)] != company_tokens:
            continue
        if index == 0 or title_tokens[index - 1] in allowed_predecessors:
            return True
    return False


def fetch(
    profile: dict,
    limit: int,
    years: int,
    acquisition_mode: str = "rights_review_experiment",
    rights_status: str = "review_required",
) -> tuple[list[dict], dict]:
    org = str(profile["organisation_number"])
    query = urllib.parse.quote(f'"{profile["name"]}" when:{years}y')
    url = f"https://news.google.com/rss/search?q={query}&hl=no&gl=NO&ceid=NO:no"
    t0 = time.perf_counter()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml"})
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read(2_000_000)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        root = ET.fromstring(raw)
        retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        output = []
        seen = set()
        for item in root.findall(".//item"):
            title = str(item.findtext("title") or "").strip()
            link = str(item.findtext("link") or "").strip()
            publisher = str(item.findtext("source") or "").strip()
            if not link or not exact_title_match(profile["name"], title):
                continue
            key = (title.casefold(), publisher.casefold())
            if key in seen:
                continue
            seen.add(key)
            published = item.findtext("pubDate")
            try:
                published_at = parsedate_to_datetime(published).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            except Exception:
                published_at = None
            digest = hashlib.sha256(raw + title.encode("utf-8") + publisher.encode("utf-8")).hexdigest()
            output.append({
                "id": "google-news-title-" + hashlib.sha256(f"{org}|{title}|{publisher}".encode()).hexdigest()[:24],
                "organisation_number": org,
                "platform": "news",
                "signal_type": "public_mention",
                "source_url": link,
                "retrieved_at": retrieved_at,
                "published_at": published_at,
                "content_sha256": digest,
                "exact_entity": True,
                "identity_proof": [
                    {"type": "exact_legal_name_in_news_title", "value": profile["name"]},
                    {"type": "publisher_label", "value": publisher},
                ],
                "acquisition_mode": acquisition_mode,
                "rights_status": rights_status,
                "source_class": "public_news",
                "evidence_span": title,
                "text": title,
                "publisher": publisher,
                "strategy": "independent_news_discovery",
            })
            if len(output) >= limit:
                break
        return output, {
            "organisation_number": org,
            "items": len(root.findall(".//item")),
            "accepted": len(output),
            "bytes": len(raw),
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return [], {
            "organisation_number": org,
            "items": 0,
            "accepted": 0,
            "bytes": 0,
            "latency_ms": latency_ms,
            "error": f"{type(exc).__name__}: {str(exc)[:180]}",
        }


def main() -> None:
    start_time = time.perf_counter()
    parser = argparse.ArgumentParser(description="Bounded exact-title Google News RSS discovery experiment.")
    parser.add_argument("--profiles", required=True)
    parser.add_argument("--organisations", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--per-company", type=int, default=10)
    parser.add_argument("--years", type=int, default=2)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--acquisition-mode", default="rights_review_experiment")
    parser.add_argument("--rights-status", default="review_required")
    args = parser.parse_args()
    wanted = [line.strip() for line in Path(args.organisations).read_text(encoding="utf-8").splitlines() if line.strip()]
    profiles = {str(row["organisation_number"]): row for row in (json.loads(line) for line in Path(args.profiles).read_text(encoding="utf-8").splitlines() if line.strip())}
    observations, results = [], []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 4))) as pool:
        futures = {
            pool.submit(fetch, profiles[org], args.per_company, args.years, args.acquisition_mode, args.rights_status): org
            for org in wanted
        }
        for future in as_completed(futures):
            rows, status = future.result()
            observations.extend(rows)
            results.append(status)
    order = {org: index for index, org in enumerate(wanted)}
    observations.sort(key=lambda row: (order[row["organisation_number"]], row.get("published_at") or "", row["id"]))
    results.sort(key=lambda row: order[row["organisation_number"]])
    latencies = [r.get("latency_ms", 0) for r in results]
    latencies.sort()
    p50_ms = latencies[len(latencies) // 2] if latencies else 0
    p95_ms = latencies[int(len(latencies) * 0.95)] if latencies else 0
    total_bytes = sum(r.get("bytes", 0) for r in results)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in observations), encoding="utf-8")
    report = {
        "connector": "google_news_rss_exact_title_experiment_v1",
        "companies": len(wanted),
        "companies_with_mentions": len({row["organisation_number"] for row in observations}),
        "observations": len(observations),
        "lookback_years": args.years,
        "operations": {
            "requests": len(results),
            "bytes": total_bytes,
            "p50_ms": p50_ms,
            "p95_ms": p95_ms,
            "runtime_s": round(time.perf_counter() - start_time, 2),
        },
        "errors": sum("error" in row for row in results),
        "claim_boundary": "Discovery-only experimental titles from Google News RSS. Publisher article bodies and storage rights are not independently verified, so these cannot be published or earn strict points.",
        "company_results": results,
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "company_results"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
