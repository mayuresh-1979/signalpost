from __future__ import annotations

import csv
import gzip
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .evidence import evidence, utc_now

SUBUNIT_BULK_SOURCE = "https://data.brreg.no/enhetsregisteret/api/underenheter/lastned/csv"


def normalize_bulk_subunit_address(row: dict[str, str]) -> dict[str, Any]:
    # Prefer beliggenhetsadresse, fallback to postadresse
    street = row.get("beliggenhetsadresse.adresse") or row.get("postadresse.adresse") or ""
    address_lines = [line.strip() for line in street.split("\n") if line.strip()] if street else []
    postnummer = row.get("beliggenhetsadresse.postnummer") or row.get("postadresse.postnummer") or ""
    poststed = row.get("beliggenhetsadresse.poststed") or row.get("postadresse.poststed") or ""
    kommune = row.get("beliggenhetsadresse.kommune") or row.get("postadresse.kommune") or ""
    kommunenummer = row.get("beliggenhetsadresse.kommunenummer") or row.get("postadresse.kommunenummer") or ""
    land = row.get("beliggenhetsadresse.land") or row.get("postadresse.land") or "Norge"
    landkode = row.get("beliggenhetsadresse.landkode") or row.get("postadresse.landkode") or "NO"

    return {
        "land": land,
        "landkode": landkode,
        "postnummer": postnummer,
        "poststed": poststed,
        "adresse": address_lines,
        "kommune": kommune,
        "kommunenummer": kommunenummer,
    }


def normalize_bulk_subunit(row: dict[str, str]) -> dict[str, Any]:
    industry_code = row.get("naeringskode1.kode", "").strip()
    industry_label = row.get("naeringskode1.beskrivelse", "").strip()
    industry = {"kode": industry_code, "beskrivelse": industry_label} if industry_code else None

    employees_raw = row.get("antallAnsatte", "").strip()
    employees = int(employees_raw) if employees_raw.isdigit() else None

    return {
        "organisation_number": row.get("organisasjonsnummer", "").strip(),
        "name": row.get("navn", "").strip(),
        "address": normalize_bulk_subunit_address(row),
        "industry": industry,
        "employees": employees,
    }


def load_subunits_from_bulk(
    path: str | Path,
    parent_orgs: Iterable[str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Index registered subunits from the official BRREG underenheter CSV snapshot."""
    target_path = Path(path)
    if not target_path.exists():
        raise FileNotFoundError(f"Subunits bulk snapshot does not exist: {target_path}")

    wanted = set(parent_orgs)
    snapshot_bytes = target_path.read_bytes()
    snapshot_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()
    retrieved_at = utc_now()

    subunits_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows_scanned = 0
    matched_subunits = 0

    # Handle gzip or raw CSV
    opener = gzip.open if target_path.suffix == ".gz" or snapshot_bytes.startswith(b"\x1f\x8b") else open

    with opener(target_path, "rt", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=",")
        for row in reader:
            rows_scanned += 1
            parent = row.get("overordnetEnhet", "").strip()
            if parent not in wanted:
                continue
            # Filter inactive / closed subunits
            if row.get("nedleggelsesdato", "").strip():
                continue
            subunits_by_parent[parent].append(normalize_bulk_subunit(row))
            matched_subunits += 1

    return dict(subunits_by_parent), {
        "subunits_snapshot_sha256": snapshot_sha256,
        "subunits_rows_scanned": rows_scanned,
        "subunits_matched": matched_subunits,
        "retrieved_at": retrieved_at,
        "source_url": SUBUNIT_BULK_SOURCE,
    }


def subunit_evidence_record(
    org: str,
    subunits: list[dict[str, Any]] | None,
    snapshot_sha256: str,
    retrieved_at: str,
) -> dict[str, Any]:
    """Emit an official_subunits_bulk evidence record compatible with existing consumers."""
    items = list(subunits or [])
    # Content hash over the normalized subunit items
    content_hash = hashlib.sha256(
        __import__("json").dumps(items, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return evidence(
        "locations",
        "available",
        "official_subunits_bulk",
        SUBUNIT_BULK_SOURCE,
        value={"locations": items},
        retrieved_at=retrieved_at,
        content_sha256=content_hash,
        source_row_key=org,
    )
