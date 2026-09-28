import unittest
from pathlib import Path
import tempfile
import csv

from norway_company_agent.subunits import (
    normalize_bulk_subunit_address,
    normalize_bulk_subunit,
    load_subunits_from_bulk,
    subunit_evidence_record,
    SUBUNIT_BULK_SOURCE,
)


class SubunitsTests(unittest.TestCase):
    def test_normalize_bulk_subunit_address_prefers_beliggenhet(self):
        row = {
            "beliggenhetsadresse.adresse": "Storgata 1\nOppgang B",
            "beliggenhetsadresse.postnummer": "0123",
            "beliggenhetsadresse.poststed": "OSLO",
            "beliggenhetsadresse.kommune": "OSLO",
            "beliggenhetsadresse.kommunenummer": "0301",
            "beliggenhetsadresse.land": "Norge",
            "beliggenhetsadresse.landkode": "NO",
            "postadresse.adresse": "Postboks 123",
            "postadresse.postnummer": "0100",
            "postadresse.poststed": "OSLO",
        }
        addr = normalize_bulk_subunit_address(row)
        self.assertEqual(addr["adresse"], ["Storgata 1", "Oppgang B"])
        self.assertEqual(addr["postnummer"], "0123")
        self.assertEqual(addr["poststed"], "OSLO")
        self.assertEqual(addr["kommune"], "OSLO")
        self.assertEqual(addr["kommunenummer"], "0301")
        self.assertEqual(addr["land"], "Norge")
        self.assertEqual(addr["landkode"], "NO")

    def test_normalize_bulk_subunit_address_falls_back_to_postadresse(self):
        row = {
            "postadresse.adresse": "Postboks 456",
            "postadresse.postnummer": "5000",
            "postadresse.poststed": "BERGEN",
            "postadresse.kommune": "BERGEN",
            "postadresse.kommunenummer": "4601",
            "postadresse.land": "Norge",
            "postadresse.landkode": "NO",
        }
        addr = normalize_bulk_subunit_address(row)
        self.assertEqual(addr["adresse"], ["Postboks 456"])
        self.assertEqual(addr["postnummer"], "5000")
        self.assertEqual(addr["poststed"], "BERGEN")

    def test_normalize_bulk_subunit(self):
        row = {
            "organisasjonsnummer": "999888777",
            "navn": "TEST AVDELING",
            "naeringskode1.kode": "62.010",
            "naeringskode1.beskrivelse": "Programmeringstjenester",
            "antallAnsatte": "15",
            "beliggenhetsadresse.postnummer": "0123",
        }
        sub = normalize_bulk_subunit(row)
        self.assertEqual(sub["organisation_number"], "999888777")
        self.assertEqual(sub["name"], "TEST AVDELING")
        self.assertEqual(sub["industry"], {"kode": "62.010", "beskrivelse": "Programmeringstjenester"})
        self.assertEqual(sub["employees"], 15)

    def test_load_subunits_from_bulk_and_filter_closed(self):
        headers = [
            "organisasjonsnummer", "navn", "overordnetEnhet",
            "naeringskode1.kode", "naeringskode1.beskrivelse",
            "antallAnsatte", "nedleggelsesdato",
            "beliggenhetsadresse.adresse", "beliggenhetsadresse.postnummer",
            "beliggenhetsadresse.poststed", "beliggenhetsadresse.kommune",
            "beliggenhetsadresse.kommunenummer", "beliggenhetsadresse.land",
            "beliggenhetsadresse.landkode",
        ]
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            # Active subunit for org1
            writer.writerow({
                "organisasjonsnummer": "111", "navn": "Sub 1", "overordnetEnhet": "ORG1",
                "antallAnsatte": "5", "nedleggelsesdato": "",
            })
            # Inactive/closed subunit for org1
            writer.writerow({
                "organisasjonsnummer": "112", "navn": "Sub Closed", "overordnetEnhet": "ORG1",
                "antallAnsatte": "0", "nedleggelsesdato": "2024-01-01",
            })
            # Active subunit for org2
            writer.writerow({
                "organisasjonsnummer": "221", "navn": "Sub 2", "overordnetEnhet": "ORG2",
                "antallAnsatte": "10", "nedleggelsesdato": "",
            })
            # Subunit for non-requested org3
            writer.writerow({
                "organisasjonsnummer": "331", "navn": "Sub 3", "overordnetEnhet": "ORG3",
                "antallAnsatte": "2", "nedleggelsesdato": "",
            })
            tmp_path = f.name

        try:
            subunits_map, metadata = load_subunits_from_bulk(tmp_path, ["ORG1", "ORG2", "ORG4"])
            self.assertEqual(len(subunits_map["ORG1"]), 1)
            self.assertEqual(subunits_map["ORG1"][0]["organisation_number"], "111")
            self.assertEqual(len(subunits_map["ORG2"]), 1)
            self.assertEqual(subunits_map["ORG2"][0]["organisation_number"], "221")
            self.assertEqual(subunits_map.get("ORG4", []), [])
            self.assertEqual(metadata["subunits_matched"], 2)
            self.assertEqual(metadata["subunits_rows_scanned"], 4)
            self.assertEqual(metadata["source_url"], SUBUNIT_BULK_SOURCE)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_subunit_evidence_record_format(self):
        subunits = [{
            "organisation_number": "111",
            "name": "Sub 1",
            "address": {},
            "industry": None,
            "employees": 5,
        }]
        rec = subunit_evidence_record("ORG1", subunits, "sha256fake", "2026-09-23T00:00:00Z")
        self.assertEqual(rec["field"], "locations")
        self.assertEqual(rec["status"], "available")
        self.assertEqual(rec["source_type"], "official_subunits_bulk")
        self.assertEqual(rec["source_url"], SUBUNIT_BULK_SOURCE)
        self.assertEqual(rec["value"], {"locations": subunits})
        self.assertEqual(rec["source_row_key"], "ORG1")

    def test_subunit_evidence_record_empty_format(self):
        rec = subunit_evidence_record("ORG_EMPTY", [], "sha256fake", "2026-09-23T00:00:00Z")
        self.assertEqual(rec["field"], "locations")
        self.assertEqual(rec["status"], "available")
        self.assertEqual(rec["source_type"], "official_subunits_bulk")
        self.assertEqual(rec["value"], {"locations": []})
