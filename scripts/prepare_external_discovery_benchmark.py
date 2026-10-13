#!/usr/bin/env python3
"""Prepare deterministic, disjoint website-discovery benchmark inputs without network access."""
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


def prepare_split(rows: list[dict[str, Any]], limit_per_split: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if limit_per_split < 1:
        raise ValueError("limit_per_split must be positive")

    seen: set[str] = set()
    missing_website: list[dict[str, Any]] = []
    duplicate_ids: list[str] = []
    for row in rows:
        org = str(row.get("organisation_number") or "").strip()
        if not org:
            raise ValueError("every profile must have an organisation_number")
        if not org.isdigit():
            raise ValueError(f"organisation_number must contain digits only: {org!r}")
        if org in seen:
            duplicate_ids.append(org)
            continue
        seen.add(org)
        if not str(row.get("website") or "").strip():
            missing_website.append(row)

    if duplicate_ids:
        raise ValueError(f"duplicate organisation_number values found: {sorted(set(duplicate_ids))[:10]}")
    required = limit_per_split * 2
    if len(missing_website) < required:
        raise ValueError(
            f"need at least {required} unique profiles without a registry website; "
            f"found {len(missing_website)}"
        )

    # Stable hash ordering avoids dependence on source-file order and gives two disjoint cohorts.
    ordered = sorted(
        missing_website,
        key=lambda row: hashlib.sha256(
            str(row["organisation_number"]).encode("ascii")
        ).hexdigest(),
    )
    development = ordered[0:required:2][:limit_per_split]
    validation = ordered[1:required:2][:limit_per_split]
    dev_ids = {str(row["organisation_number"]) for row in development}
    val_ids = {str(row["organisation_number"]) for row in validation}
    if len(development) != limit_per_split or len(validation) != limit_per_split:
        raise AssertionError("split sizes do not match requested limit")
    if dev_ids & val_ids:
        raise AssertionError("development and validation sets overlap")

    manifest = {
        "benchmark": "external_website_discovery",
        "selection_method": "sha256 organisation-number ordering, alternating rows",
        "input_profiles": len(rows),
        "unique_profiles": len(seen),
        "profiles_without_registry_website": len(missing_website),
        "development_count": len(development),
        "validation_count": len(validation),
        "development_validation_overlap": 0,
        "development_organisation_numbers": sorted(dev_ids),
        "validation_organisation_numbers": sorted(val_ids),
        "network_requests_made": 0,
        "labels_created": False,
        "qualification": "sample manifest only; does not establish exact-entity truth or connector quality",
    }
    return development, validation, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", required=True, help="Input profile JSONL; never modified")
    parser.add_argument("--output-dir", required=True, help="New directory for isolated benchmark inputs")
    parser.add_argument("--limit-per-split", type=int, default=100)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        parser.error(f"output directory is not empty: {output_dir}")
    rows = read_jsonl(Path(args.profiles))
    try:
        development, validation, manifest = prepare_split(rows, args.limit_per_split)
    except ValueError as exc:
        parser.error(str(exc))

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "development.jsonl", development)
    write_jsonl(output_dir / "validation.jsonl", validation)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
