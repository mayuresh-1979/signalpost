#!/usr/bin/env python3
"""Export internal Signalpost envelopes to the Builderr claims/evidence contract."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(path)


def availability(record: dict[str, Any] | None) -> str:
    if not record:
        return "failed"
    status = record.get("status")
    if status == "available":
        return "available"
    if status in {"not_found", "not_fetched", "not_available"}:
        return "not_available"
    if status == "not_applicable":
        return "not_applicable"
    if status == "blocked":
        return "blocked"
    if status in {"ambiguous", "review"}:
        return "ambiguous"
    return "failed"


def source_class(record: dict[str, Any]) -> str:
    raw = str(record.get("source_class") or record.get("source_type") or "public_source")
    if "company" in raw or "website" in raw:
        return "company_owned"
    if "official" in raw or "registry" in raw or "brreg" in raw:
        return "official_registry"
    if "public" in raw:
        return "permitted_public_page"
    return raw


def build_result(envelope: dict[str, Any]) -> dict[str, Any]:
    org = str(envelope.get("organisation_number") or "")
    profile = envelope.get("profile") or {}
    evidence_map = profile.get("evidence") or {}
    run_id = str(envelope.get("run_id") or "signalpost-run")
    started = envelope.get("started_at")
    completed = envelope.get("completed_at")
    run_metrics = profile.get("run_metrics") or {}

    claims: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    emitted_evidence: set[str] = set()

    def add_claim(field: str, value: Any, state: str, evidence_id: str | None,
                  confidence: float = 0.99, context: dict[str, Any] | None = None) -> None:
        claim = {
            "field": field,
            "value": value if state == "available" else None,
            "availability": state,
            "confidence": confidence if state == "available" else 0.0,
            "evidence_ids": [evidence_id] if evidence_id else [],
        }
        if context:
            claim["context"] = context
        claims.append(claim)

    def evidence_id(module: str) -> str:
        return f"ev-{org}-{module}"

    def attach_evidence(module: str, record: dict[str, Any]) -> str | None:
        if record.get("status") != "available" or not record.get("source_url"):
            return None
        eid = evidence_id(module)
        if eid in emitted_evidence:
            return eid
        value = record.get("value")
        evidence_rows.append({
            "id": eid,
            "source_url": record.get("source_url"),
            "source_class": source_class(record),
            "retrieved_at": record.get("retrieved_at") or completed,
            "content_sha256": record.get("content_sha256"),
            "claim_span": json.dumps(value, ensure_ascii=False, separators=(",", ":"))[:4000] if value is not None else str(record.get("note") or ""),
        })
        emitted_evidence.add(eid)
        return eid

    # Registry facts are drawn from the bulk snapshot and corroborating live endpoint.
    registry = evidence_map.get("registry") or {}
    live = evidence_map.get("registry_live") or {}
    registry_value = registry.get("value") or {}
    live_value = live.get("value") or {}
    registry_fields = {
        "company.name": profile.get("name"),
        "company.legal_form": profile.get("legal_form"),
        "company.employees": profile.get("employees"),
        "company.bankrupt": profile.get("bankrupt"),
        "company.liquidating": profile.get("liquidating"),
        "company.municipality": profile.get("municipality"),
        "company.municipality_number": profile.get("municipality_number"),
        "company.industry_code": profile.get("industry_code"),
        "company.industry_label": profile.get("industry_label"),
        "company.registration_date": profile.get("registration_date"),
        "company.foundation_date": profile.get("foundation_date"),
        "company.latest_submitted_accounts": profile.get("latest_submitted_accounts"),
        "company.business_address": profile.get("business_address"),
        "company.postal_address": profile.get("postal_address"),
        "company.official_email": profile.get("official_email"),
        "company.official_phone": profile.get("official_phone"),
        "company.official_mobile": profile.get("official_mobile"),
        "company.capital": profile.get("capital"),
        "company.purpose": profile.get("statutory_purpose"),
        "company.activity": profile.get("operational_activity"),
        "company.vat_registered": profile.get("vat_registered"),
        "company.vat_registered_date": profile.get("vat_registered_date"),
        "company.audit_exemption_date": profile.get("audit_exemption_date"),
    }
    for field, value in registry_fields.items():
        if value is None or value == "":
            continue
        module = "registry_live" if field in {
            "company.employees", "company.bankrupt", "company.liquidating",
            "company.business_address", "company.postal_address",
        } else "registry"
        record = evidence_map.get(module) or registry
        state = availability(record)
        eid = attach_evidence(module, record)
        add_claim(field, value, state, eid)

    # Keep the accounting-obligation assessment separate from a claim that accounts were filed.
    obligation = evidence_map.get("accounting_obligation") or {}
    if obligation.get("status") == "available":
        eid = attach_evidence("accounting_obligation", obligation)
        add_claim("company.accounting_obligation", obligation.get("value"), "available", eid,
                  context={"rule_as_of": obligation.get("as_of")})

    financial = evidence_map.get("financials") or {}
    fin_state = availability(financial)
    fin_value = (financial.get("value") or {}).get("records", [])
    if fin_state == "available" and not fin_value:
        fin_state = "not_available"
    fin_eid = attach_evidence("financials", financial)
    if fin_state == "available":
        for row in fin_value:
            period = row.get("period") or {}
            context = {
                "record_id": row.get("record_id"),
                "reporting_period_from": period.get("fraDato"),
                "reporting_period_to": period.get("tilDato"),
                "currency": row.get("currency"),
                "account_type": row.get("account_type"),
            }
            for key in ("revenue", "operating_result", "profit_before_tax", "annual_result", "assets", "equity", "debt"):
                if row.get(key) is not None:
                    add_claim("financial." + key, row[key], "available", fin_eid, context=context)
    else:
        add_claim("financial.records", None, fin_state, fin_eid)

    roles_record = evidence_map.get("roles") or {}
    roles = (roles_record.get("value") or {}).get("roles", [])
    roles_state = availability(roles_record)
    if roles_state == "available" and not roles:
        roles_state = "not_available"
    roles_eid = attach_evidence("roles", roles_record)
    if roles_state == "available":
        for i, role in enumerate(roles):
            role_name = role.get("name")
            if isinstance(role_name, list):
                role_name = ", ".join(str(x) for x in role_name)
            add_claim("people.role", {
                "name": role_name,
                "role": role.get("role"),
                "role_code": role.get("role_code"),
                "holder_organisation_number": role.get("organisation_number"),
                "last_changed": role.get("last_changed"),
                "inactive": role.get("inactive"),
            }, "available", roles_eid, context={"record_index": i})
    else:
        add_claim("people.roles", None, roles_state, roles_eid)

    locations_record = evidence_map.get("locations") or {}
    locations = (locations_record.get("value") or {}).get("locations", [])
    locations_state = availability(locations_record)
    if locations_state == "available" and not locations:
        locations_state = "not_available"
    locations_eid = attach_evidence("locations", locations_record)
    if locations_state == "available":
        for i, location in enumerate(locations):
            add_claim("locations.subunit", location, "available", locations_eid,
                      context={"record_index": i, "subunit_organisation_number": location.get("organisation_number")})
    else:
        add_claim("locations.subunits", None, locations_state, locations_eid)

    website_record = evidence_map.get("website") or {}
    website_value = website_record.get("value") or {}
    assessment = website_value.get("identity_assessment") or {}
    website_state = availability(website_record)
    website_eid = attach_evidence("website", website_record)
    if website_state == "available" and assessment.get("publishable") is not True:
        website_state = "ambiguous"
    if website_state == "available":
        add_claim("website.official_url", website_value.get("final_url") or website_value.get("requested_url"),
                  "available", website_eid, confidence=float(assessment.get("score") or 0.9),
                  context={"identity_status": assessment.get("status")})
        for social in website_value.get("social_links", []):
            add_claim("website.social_link", social, "available", website_eid,
                      confidence=float(assessment.get("score") or 0.9))
    else:
        add_claim("website.official_url", None, website_state, website_eid,
                  context={"identity_status": assessment.get("status") or "not_established"})

    # Report module-level unavailability explicitly, so a checked empty result is not silently dropped.
    module_to_field = {
        "registry": "company.registry",
        "registry_live": "company.live_registry",
        "accounting_obligation": "company.accounting_obligation",
        "financials": "financial.records",
        "roles": "people.roles",
        "locations": "locations.subunits",
        "website": "website.official_url",
    }
    existing_fields = {c["field"] for c in claims}
    for module, field in module_to_field.items():
        record = evidence_map.get(module)
        if field not in existing_fields and record and availability(record) != "available":
            add_claim(field, None, availability(record), None)

    modules = envelope.get("modules") or {}
    failed_modules = [name for name, state in modules.items() if state.get("state") in {"source_error", "budget_exhausted", "submission_error"}]
    if failed_modules:
        errors.append({"code": "module_failure", "message": "One or more modules failed.", "modules": failed_modules})
    terminal = "failed" if failed_modules or envelope.get("state") == "submission_error" else "completed"

    return {
        "organisation_number": org,
        "run": {
            "run_id": run_id,
            "started_at": started,
            "completed_at": completed,
            "terminal_status": terminal,
        },
        "claims": claims,
        "evidence": evidence_rows,
        "changes": [],
        "errors": errors,
        "operations": {
            "requests": int(run_metrics.get("requests") or 0),
            "runtime_ms": 0,
            "third_party_cost_usd": 0.0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Internal Signalpost envelopes JSONL")
    parser.add_argument("--output", type=Path, required=True, help="Builderr contract JSONL output")
    args = parser.parse_args()
    envelopes = read_jsonl(args.input)
    results = [build_result(row) for row in envelopes]
    expected_orgs = [str(row.get("organisation_number") or "") for row in envelopes]
    if any(not re.fullmatch(r"\d{9}", org) for org in expected_orgs):
        raise SystemExit("Input contains invalid organisation numbers")
    if len(expected_orgs) != len(set(expected_orgs)):
        raise SystemExit("Input contains duplicate organisation numbers")
    write_jsonl(args.output, results)
    print(json.dumps({
        "status": "PASS",
        "input_count": len(envelopes),
        "output_count": len(results),
        "claims": sum(len(row["claims"]) for row in results),
        "evidence": sum(len(row["evidence"]) for row in results),
        "failed_runs": sum(row["run"]["terminal_status"] == "failed" for row in results),
        "output": str(args.output),
        "note": "Structural export only; source factual accuracy and official score are not certified.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
