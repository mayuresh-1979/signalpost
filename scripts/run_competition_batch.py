#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.batch import (  # noqa: E402
    profile_complete_for_modules,
    profiles_from_bulk,
    read_organisation_inputs,
    terminal_envelope,
    validate_envelopes,
)
from norway_company_agent.evidence import evidence, utc_now  # noqa: E402
from norway_company_agent.capital_emission import emit_capital_metrics  # noqa: E402
from norway_company_agent.contact_registration_emission import emit_contact_registration_metrics  # noqa: E402
from norway_company_agent.financial_emission import emit_financial_metrics  # noqa: E402
from norway_company_agent.purpose_vat_audit_emission import emit_purpose_vat_audit_metrics  # noqa: E402
from norway_company_agent.roles_emission import emit_roles_metrics  # noqa: E402
from norway_company_agent.identity import (  # noqa: E402
    apply_website_identity_gate,
    assess_guessed_website_identity,
)
from norway_company_agent.http import clear_request_cache  # noqa: E402
from norway_company_agent.official import fetch_official_modules  # noqa: E402
from norway_company_agent.subunits import (  # noqa: E402
    load_subunits_from_bulk,
    subunit_evidence_record,
)
from norway_company_agent.website import (  # noqa: E402
    clear_robots_cache,
    crawl_secondary_pages,
    fetch_website,
)




def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )

    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluator-owned Signalpost batch contract"
    )

    parser.add_argument(
        "--organisations",
        required=True,
        help="JSON, JSONL, or text organisation-number list",
    )
    parser.add_argument(
        "--bulk",
        required=True,
        help="Frozen Brreg entity snapshot",
    )
    parser.add_argument(
        "--subunits-bulk",
        default="brreg-underenheter.csv",
        help="Official BRREG underenheter CSV snapshot",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Terminal envelope JSONL",
    )
    parser.add_argument(
        "--profiles-output",
        required=True,
    )
    parser.add_argument(
        "--report",
        required=True,
    )
    parser.add_argument(
        "--run-id",
        required=True,
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=100,
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=25,
    )
    parser.add_argument(
        "--resume",
        action="store_true",
    )
    parser.add_argument(
        "--modules",
        default=(
            "registry,"
            "accounting_obligation,"
            "registry_live,"
            "financials,"
            "roles,"
            "locations,"
            "website"
        ),
    )
    parser.add_argument(
        "--financial-short-circuit",
        choices=["none", "form_skip"],
        default="none",
        help="Strategy for short-circuiting official financial requests",
    )
    parser.add_argument(
        "--role-optimization",
        choices=["none", "form_skip"],
        default="none",
        help="Strategy for optimizing official role requests",
    )
    parser.add_argument(
        "--website-candidate-gate",
        choices=["all", "registered_only", "registered_and_email", "no_hyphen"],
        default="all",
        help="Gating strategy for website candidate domains",
    )
    parser.add_argument(
        "--website-secondary-pages",
        choices=["yes", "no"],
        default="no",
        help="Whether to crawl secondary pages on publishable websites",
    )
    parser.add_argument(
        "--website-fetch-mode",
        choices=["fetch", "metadata_only"],
        default="fetch",
        help="Fetch mode: full HTTP fetch or retain URL metadata only",
    )

    args = parser.parse_args()
    clear_request_cache()
    clear_robots_cache()

    started_at = utc_now()


    organisation_inputs = read_organisation_inputs(
        args.organisations
    )

    orgs = [
        item["organisation_number"]
        for item in organisation_inputs
    ]

    if len(orgs) != args.expected_count:
        raise SystemExit(
            f"Expected {args.expected_count} organisations, "
            f"received {len(orgs)}"
        )

    profiles, registry_metadata = profiles_from_bulk(
        args.bulk,
        orgs,
    )

    annotations = {
        item["organisation_number"]: item
        for item in organisation_inputs
    }

    for profile in profiles:
        for key in (
            "evaluation_split",
            "sample_slice",
        ):
            if key in annotations[
                profile["organisation_number"]
            ]:
                profile[key] = annotations[
                    profile["organisation_number"]
                ][key]

    requested_modules = [
        item.strip()
        for item in args.modules.split(",")
        if item.strip()
    ]

    subunits_metadata = None
    subunits_bulk_path = Path(args.subunits_bulk) if args.subunits_bulk else None
    if "locations" in requested_modules and subunits_bulk_path and subunits_bulk_path.exists():
        subunits_map, subunits_metadata = load_subunits_from_bulk(
            subunits_bulk_path,
            orgs,
        )
        for profile in profiles:
            org = profile["organisation_number"]
            profile["evidence"]["locations"] = subunit_evidence_record(
                org,
                subunits_map.get(org, []),
                subunits_metadata["subunits_snapshot_sha256"],
                subunits_metadata["retrieved_at"],
            )

    fetch_modules = (
        set(requested_modules)
        - {
            "registry",
            "accounting_obligation",
            "website",
        }
    )
    if subunits_metadata is not None:
        fetch_modules.discard("locations")


    operations = {
        "requests": 0,
        "bytes": 0,
        "latencies_ms": [],
    }

    def email_domain_website_candidate(
        profile: dict,
    ) -> str | None:
        generic_email_domains = {
            "gmail.com",
            "googlemail.com",
            "outlook.com",
            "hotmail.com",
            "live.com",
            "msn.com",
            "yahoo.com",
            "yahoo.no",
            "icloud.com",
            "me.com",
            "mac.com",
            "proton.me",
            "protonmail.com",
            "gmx.com",
            "gmx.net",
        }

        registry = (
            profile
            .get("evidence", {})
            .get("registry", {})
            .get("value")
            or {}
        )

        email = str(
            registry.get("epostadresse") or ""
        ).strip().casefold()

        if "@" not in email:
            return None

        local, domain = email.rsplit("@", 1)

        domain = (
            domain
            .strip()
            .rstrip(".")
        )

        if not local:
            return None

        if not domain:
            return None

        if "." not in domain:
            return None

        if domain in generic_email_domains:
            return None

        if any(
            ch.isspace()
            for ch in domain
        ):
            return None

        if len(domain) > 253:
            return None

        return "https://" + domain

    def name_domain_website_candidates(
        profile: dict,
    ) -> list[str]:
        """
        Generate deterministic .no website candidates from the
        registered legal name.

        These URLs are discovery candidates only. They are never
        treated as company facts unless the guessed-domain identity
        gate explicitly accepts the fetched content.
        """

        name = str(
            profile.get("name") or ""
        ).strip()

        if not name:
            return []

        # Remove common Norwegian legal-form suffixes.
        name = re.sub(
            r"\b"
            r"(AS|ASA|ANS|DA|ENK|NUF|SA|BA|KF|IKS|KS)"
            r"\b",
            " ",
            name,
            flags=re.IGNORECASE,
        )

        # Normalize Norwegian characters.
        replacements = str.maketrans(
            {
                "æ": "ae",
                "ø": "o",
                "å": "a",
                "Æ": "AE",
                "Ø": "O",
                "Å": "A",
            }
        )

        name = name.translate(replacements).casefold()

        tokens = re.findall(
            r"[a-z0-9]+",
            name,
        )

        if not tokens or args.website_candidate_gate in {"registered_only", "registered_and_email"}:
            return []

        compact = "".join(tokens)
        hyphenated = "-".join(tokens)

        candidates: list[str] = []

        slugs = (compact,) if args.website_candidate_gate == "no_hyphen" else (compact, hyphenated)
        for slug in slugs:
            if slug and len(slug) <= 63:
                candidates.append(
                    f"https://{slug}.no"
                )

        # Preserve order and remove duplicates.
        return list(
            dict.fromkeys(candidates)
        )

    def empty_website_record() -> dict:
        """
        Return a safe empty website evidence record when there is
        no registered website or email-domain candidate.
        """

        record, _ = fetch_website(None)
        return record

    def enrich(
        profile: dict,
    ) -> tuple[dict, dict]:
        company_fetch_modules = set(fetch_modules)
        lf = profile.get("legal_form")

        if args.financial_short_circuit == "form_skip" and lf not in {"AS", "ASA"}:
            company_fetch_modules.discard("financials")
            profile["evidence"]["financials"] = evidence(
                "financials",
                "not_found",
                "official_registry_bulk",
                "https://data.brreg.no/regnskapsregisteret/regnskap/" + profile["organisation_number"],
                note="Short-circuited by legal form (non-AS/ASA)",
            )

        if args.role_optimization == "form_skip" and lf not in {"AS", "ASA"}:
            company_fetch_modules.discard("roles")
            profile["evidence"]["roles"] = evidence(
                "roles",
                "not_found",
                "official_registry_bulk",
                "https://data.brreg.no/enhetsregisteret/api/enheter/" + profile["organisation_number"] + "/roller",
                note="Short-circuited by legal form (non-AS/ASA)",
            )

        records, metrics = fetch_official_modules(
            profile["organisation_number"],
            company_fetch_modules,
            profile=profile,
        )

        profile["evidence"].update(records)

        website_metrics = {
            "requests": 0,
            "bytes": 0,
            "latencies_ms": [],
        }

        if "website" in requested_modules:
            registered_website = str(
                profile.get("website") or ""
            ).strip()

            website_record = None

            if args.website_fetch_mode == "metadata_only":
                if registered_website:
                    reg_url = registered_website if registered_website.startswith("http") else "http://" + registered_website
                    website_record = evidence(
                        "website",
                        "not_fetched",
                        "official_registry",
                        reg_url,
                        note="URL-known but not-fetched mode",
                    )
                else:
                    website_record = empty_website_record()
                profile["evidence"]["website"] = website_record
            else:
                allow_secondary = (args.website_secondary_pages != "no")

                # 1. Registered BRREG website. Highest priority, unchanged gate.
                if registered_website:
                    fetched_record, fetched_metrics = fetch_website(
                        registered_website,
                        crawl_secondary=False,
                    )

                    website_metrics["requests"] += fetched_metrics["requests"]
                    website_metrics["bytes"] += fetched_metrics["bytes"]
                    website_metrics["latencies_ms"].extend(
                        fetched_metrics["latencies_ms"]
                    )

                    gate_result = apply_website_identity_gate(
                        profile,
                        fetched_record,
                    )
                    website_record = gate_result["website"]
                    assessment = gate_result.get("assessment") or {}

                    if assessment.get("publishable"):
                        if allow_secondary:
                            secondary_metrics = crawl_secondary_pages(
                                website_record,
                            )
                            website_metrics["requests"] += secondary_metrics["requests"]
                            website_metrics["bytes"] += secondary_metrics["bytes"]
                            website_metrics["latencies_ms"].extend(
                                secondary_metrics["latencies_ms"]
                            )
                            gate_result = apply_website_identity_gate(
                                profile,
                                website_record,
                            )
                            website_record = gate_result["website"]
                    else:
                        (website_record.get("value") or {}).pop("priority_links", None)

                # 2. If the registered website failed, try the company email domain.
                if (
                    args.website_candidate_gate != "registered_only"
                    and (
                        website_record is None
                        or website_record.get("status") != "available"
                    )
                ):
                    email_candidate = email_domain_website_candidate(profile)

                    if email_candidate:
                        fetched_record, fetched_metrics = fetch_website(
                            email_candidate,
                            crawl_secondary=False,
                        )

                        website_metrics["requests"] += fetched_metrics["requests"]
                        website_metrics["bytes"] += fetched_metrics["bytes"]
                        website_metrics["latencies_ms"].extend(
                            fetched_metrics["latencies_ms"]
                        )

                        fetched_record["source_type"] = (
                            "registry_email_domain_company_website"
                        )
                        fetched_record["source_class"] = (
                            "company_email_domain_candidate"
                        )
                        fetched_record["source_url"] = email_candidate

                        gate_result = apply_website_identity_gate(
                            profile,
                            fetched_record,
                        )
                        email_record = gate_result["website"]
                        assessment = gate_result.get("assessment") or {}

                        if email_record.get("status") == "available":
                            if assessment.get("publishable"):
                                if allow_secondary:
                                    secondary_metrics = crawl_secondary_pages(
                                        email_record,
                                    )
                                    website_metrics["requests"] += secondary_metrics["requests"]
                                    website_metrics["bytes"] += secondary_metrics["bytes"]
                                    website_metrics["latencies_ms"].extend(
                                        secondary_metrics["latencies_ms"]
                                    )
                                    gate_result = apply_website_identity_gate(
                                        profile,
                                        email_record,
                                    )
                                    email_record = gate_result["website"]
                            else:
                                (email_record.get("value") or {}).pop("priority_links", None)

                            website_record = email_record

                # 3. If still unavailable, try deterministic name-derived .no domains.
                if (
                    website_record is None
                    or website_record.get("status") != "available"
                ):
                    for candidate_url in name_domain_website_candidates(profile):
                        fetched_record, fetched_metrics = fetch_website(
                            candidate_url,
                            crawl_secondary=False,
                        )

                        website_metrics["requests"] += fetched_metrics["requests"]
                        website_metrics["bytes"] += fetched_metrics["bytes"]
                        website_metrics["latencies_ms"].extend(
                            fetched_metrics["latencies_ms"]
                        )

                        fetched_record["source_type"] = (
                            "registry_name_domain_candidate"
                        )
                        fetched_record["source_class"] = (
                            "company_name_domain_candidate"
                        )
                        fetched_record["source_url"] = candidate_url

                        candidate_profile = dict(profile)
                        candidate_profile["evidence"] = dict(
                            profile.get("evidence") or {}
                        )
                        candidate_profile["evidence"]["website"] = fetched_record

                        guessed_identity = assess_guessed_website_identity(
                            candidate_profile
                        )

                        if guessed_identity.get("publishable"):
                            if allow_secondary:
                                secondary_metrics = crawl_secondary_pages(
                                    fetched_record,
                                )
                                website_metrics["requests"] += secondary_metrics["requests"]
                                website_metrics["bytes"] += secondary_metrics["bytes"]
                                website_metrics["latencies_ms"].extend(
                                    secondary_metrics["latencies_ms"]
                                )
                            fetched_record["identity_assessment"] = guessed_identity
                            if isinstance(fetched_record.get("value"), dict):
                                fetched_record["value"]["identity_assessment"] = guessed_identity
                            website_record = fetched_record
                            break
                        else:
                            (fetched_record.get("value") or {}).pop("priority_links", None)

                # 4. Preserve a terminal website evidence record even if nothing matched.
                if website_record is None:
                    website_record = empty_website_record()

                (website_record.get("value") or {}).pop("priority_links", None)
                profile["evidence"]["website"] = website_record

        outbound_official_metrics = [
            item for item in metrics
            if not getattr(item, "cached", False)
        ]

        metric = {
            "requests": (
                len(outbound_official_metrics)
                + website_metrics["requests"]
            ),
            "bytes": (
                sum(
                    item.bytes_received
                    for item in outbound_official_metrics
                )
                + website_metrics["bytes"]
            ),
            "latencies_ms": (
                [
                    item.elapsed_ms
                    for item in outbound_official_metrics
                ]
                + website_metrics[
                    "latencies_ms"
                ]
            ),
        }


        emit_financial_metrics(profile)
        emit_roles_metrics(profile)
        emit_contact_registration_metrics(profile)
        emit_capital_metrics(profile)
        emit_purpose_vat_audit_metrics(profile)
        profile["run_metrics"] = metric

        return profile, metric

    state: dict[str, dict] = {}

    resumed_profiles = 0

    profiles_output = Path(
        args.profiles_output
    )

    if (
        args.resume
        and profiles_output.exists()
    ):
        prior = [
            json.loads(line)
            for line in profiles_output.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]

        if not set(
            item["organisation_number"]
            for item in prior
        ).issubset(
            set(orgs)
        ):
            raise SystemExit(
                "Resume profile membership "
                "is not a subset of this batch"
            )

        state = {
            item["organisation_number"]: item
            for item in prior
            if profile_complete_for_modules(
                item,
                requested_modules,
            )
        }

        resumed_profiles = len(state)

    pending_profiles = [
        profile
        for profile in profiles
        if profile["organisation_number"]
        not in state
    ]

    with ThreadPoolExecutor(
        max_workers=args.workers
    ) as pool:
        futures = {
            pool.submit(
                enrich,
                profile,
            ): profile[
                "organisation_number"
            ]
            for profile in pending_profiles
        }

        for index, future in enumerate(
            as_completed(futures),
            1,
        ):
            profile, metric = future.result()

            state[
                profile[
                    "organisation_number"
                ]
            ] = profile

            operations["requests"] += (
                metric["requests"]
            )

            operations["bytes"] += (
                metric["bytes"]
            )

            operations[
                "latencies_ms"
            ].extend(
                metric["latencies_ms"]
            )

            if (
                index
                % args.checkpoint_every
                == 0
                or index
                == len(pending_profiles)
            ):
                checkpoint = [
                    state[org]
                    for org in orgs
                    if org in state
                ]

                write_jsonl(
                    profiles_output,
                    checkpoint,
                )

    completed_at = utc_now()

    ordered_profiles = [
        emit_purpose_vat_audit_metrics(
            emit_capital_metrics(
                emit_contact_registration_metrics(
                    emit_roles_metrics(emit_financial_metrics(state[org]))
                )
            )
        )
        for org in orgs
    ]

    envelopes = [
        terminal_envelope(
            profile,
            run_id=args.run_id,
            modules=requested_modules,
            started_at=started_at,
            completed_at=completed_at,
        )
        for profile in ordered_profiles
    ]

    validation = validate_envelopes(
        envelopes,
        args.expected_count,
    )

    write_jsonl(
        profiles_output,
        ordered_profiles,
    )

    write_jsonl(
        Path(args.output),
        envelopes,
    )

    if operations["requests"] == 0 and ordered_profiles:
        operations["requests"] = sum(p.get("run_metrics", {}).get("requests", 0) for p in ordered_profiles)
        operations["bytes"] = sum(p.get("run_metrics", {}).get("bytes", 0) for p in ordered_profiles)
        for p in ordered_profiles:
            operations["latencies_ms"].extend(p.get("run_metrics", {}).get("latencies_ms", []))

    latencies = sorted(
        operations.pop(
            "latencies_ms"
        )
    )

    operations["p50_ms"] = (
        latencies[
            len(latencies) // 2
        ]
        if latencies
        else None
    )

    operations["p95_ms"] = (
        latencies[
            min(
                len(latencies) - 1,
                int(
                    len(latencies)
                    * 0.95
                ),
            )
        ]
        if latencies
        else None
    )

    report = {
        "run_id": args.run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "expected_count": args.expected_count,
        "emitted_envelopes": len(
            envelopes
        ),
        "resumed_profiles": (
            resumed_profiles
        ),
        "profiles_fetched_this_run": (
            len(pending_profiles)
        ),
        "modules": requested_modules,
        "registry": registry_metadata,
        "subunits": subunits_metadata,
        "operations": operations,
        "validation": validation,
    }


    Path(
        args.report
    ).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    Path(
        args.report
    ).write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )

    raise SystemExit(
        0
        if validation["passed"]
        else 1
    )


if __name__ == "__main__":
    main()