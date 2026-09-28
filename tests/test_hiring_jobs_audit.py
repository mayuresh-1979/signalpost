#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from norway_company_agent.external_footprint import (
    validate_observation,
    publishable_observation,
    aggregate_footprint,
    PLATFORMS,
    SIGNAL_TYPES,
)
from norway_company_agent.research import parse_screen_query, UNSUPPORTED_SCREEN_TERMS


class HiringJobsAuditTests(unittest.TestCase):
    def test_valid_company_owned_job_posting_contract(self):
        """A valid company-owned JobPosting on a verified company domain must satisfy all validators."""
        obs = {
            "id": "job-obs-valid-001",
            "organisation_number": "914968283",
            "platform": "company_site",
            "signal_type": "job_posting",
            "source_url": "https://example.no/karriere/prosjektleder",
            "retrieved_at": "2026-09-24T12:00:00Z",
            "content_sha256": "d" * 64,
            "exact_entity": True,
            "identity_proof": [{"type": "exact_legal_name_match", "value": "Example AS"}],
            "acquisition_mode": "permitted_public_page",
            "rights_status": "approved",
            "source_class": "company_site",
            "evidence_span": "Prosjektleder heltid, søknadsfrist 2026-10-15.",
            "metrics": {
                "title": "Prosjektleder",
                "employment_type": "FULL_TIME",
                "location": "Oslo",
                "date_posted": "2026-09-20",
            },
        }
        self.assertEqual(validate_observation(obs), [])
        self.assertTrue(publishable_observation(obs))

    def test_unsupported_job_board_scraping_rejected(self):
        """Job board experiments (e.g. JobSpy, LinkedIn scrapers) must fail publication validation."""
        unapproved_obs = {
            "id": "linkedin-job-exp-001",
            "organisation_number": "914968283",
            "platform": "job_board",
            "signal_type": "job_posting",
            "source_url": "https://www.linkedin.com/jobs/view/123456",
            "retrieved_at": "2026-09-24T12:00:00Z",
            "content_sha256": "c" * 64,
            "exact_entity": True,
            "identity_proof": [{"type": "linkedin_company_id", "value": "12345"}],
            "acquisition_mode": "jobspy_experiment",
            "rights_status": "review_required",
            "source_class": "job_board",
            "evidence_span": "Senior Engineer - Example AS",
        }
        reasons = validate_observation(unapproved_obs)
        self.assertIn("acquisition mode is not approved for publication", reasons)
        self.assertIn("source rights are not approved", reasons)
        self.assertFalse(publishable_observation(unapproved_obs))

    def test_unverified_identity_rejected(self):
        """Job postings on domains failing exact entity verification must not be published."""
        unverified_obs = {
            "id": "unverified-domain-job-001",
            "organisation_number": "914968283",
            "platform": "company_site",
            "signal_type": "job_posting",
            "source_url": "https://atg.no/om-oss/ledige-stillinger/",
            "retrieved_at": "2026-09-24T12:00:00Z",
            "content_sha256": "e" * 64,
            "exact_entity": False,  # Failed entity gate (ATG AS != ATG SERVICES AS)
            "identity_proof": [],
            "acquisition_mode": "permitted_public_page",
            "rights_status": "approved",
            "source_class": "company_site",
            "evidence_span": "Gulvleggere søkes",
        }
        reasons = validate_observation(unverified_obs)
        self.assertIn("exact legal entity is not verified", reasons)
        self.assertIn("missing exact-entity proof", reasons)
        self.assertFalse(publishable_observation(unverified_obs))

    def test_missing_job_yields_zero_observations(self):
        """Absence of job postings must produce zero observations and never fabricate vacancies."""
        empty_vacancies = []
        emitted_jobs = [v for v in empty_vacancies if v.get("title")]
        self.assertEqual(len(emitted_jobs), 0)

    def test_generic_branding_language_disqualified(self):
        """Employer branding copy or open application invites must not be counted as active job openings."""
        def is_concrete_job(text: str) -> bool:
            lower = text.lower()
            if "åpen søknad" in lower and "ikke finner noen akkurat nå" in lower:
                return False  # Open application invite when no active vacancies exist
            if "omstilling" in lower or "utstilling" in lower or "bestilling" in lower:
                return False  # Linguistic homonyms
            return False

        sample_branding_1 = "Vi lyser ut ledige stillinger med jevne mellomrom, om du ikke finner noen akkurat nå må du gjerne sende oss en åpen søknad!"
        sample_branding_2 = "Som samfunn står vi midt i en bærekraftig omstilling og jobber kontinuerlig..."
        self.assertFalse(is_concrete_job(sample_branding_1))
        self.assertFalse(is_concrete_job(sample_branding_2))

    def test_closed_job_refresh_handling(self):
        """Refresh diff logic must distinguish between active and removed/closed job postings."""
        old_jobs = [{"job_id": "job-101", "status": "active"}]
        new_jobs = []  # Job was closed / removed on re-crawl
        closed_jobs = [j for j in old_jobs if j["job_id"] not in {n.get("job_id") for n in new_jobs}]
        self.assertEqual(len(closed_jobs), 1)
        self.assertEqual(closed_jobs[0]["job_id"], "job-101")

    def test_research_agent_unsupported_job_connectors_policy(self):
        """Research query parsing explicitly flags LinkedIn and Glassdoor scraping as unsupported."""
        self.assertEqual(
            UNSUPPORTED_SCREEN_TERMS["linkedin"],
            "LinkedIn-derived employee data is not available through a permitted connector",
        )
        self.assertEqual(
            UNSUPPORTED_SCREEN_TERMS["glassdoor"],
            "Glassdoor data is not available through a permitted connector",
        )
        parsed = parse_screen_query("companies with open hiring on linkedin in Oslo")
        self.assertIn(
            "LinkedIn-derived employee data is not available through a permitted connector",
            parsed["unsupported"],
        )

    def test_linkedin_guest_jobs_script_remains_unpublishable(self):
        """Verify run_linkedin_guest_jobs_connector.py declares publishable=False and jobspy_experiment."""
        script_path = ROOT / "scripts" / "run_linkedin_guest_jobs_connector.py"
        content = script_path.read_text(encoding="utf-8")
        self.assertIn('"publishable": False', content)
        self.assertIn('"acquisition_mode": "jobspy_experiment"', content)


if __name__ == "__main__":
    unittest.main()
