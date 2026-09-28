import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from norway_company_agent.external_footprint import (
    validate_observation,
    publishable_observation,
    aggregate_footprint,
)
from scripts.run_google_news_rss_connector import exact_title_match


def test_safety_a_generic_company_name():
    """Test A: Generic name returns ambiguous news items not matching exact title."""
    company = "MUSIKK I INNLANDET AS"
    candidate_titles = [
        "Ballade video: Kom nærmere i stormen - Ballade.no",
        "Innlandet fylkeskommune eier alt dette - Østlendingen",
        "Spellemann: Derfor blir prisene for klassisk slått sammen - Ballade.no",
    ]
    for title in candidate_titles:
        assert not exact_title_match(company, title), f"Should not match {title}"


def test_safety_b_same_name_unrelated_company():
    """Test B: Unrelated company or non-matching article title is rejected."""
    company = "STADION 33 AS"
    title = "Værste med nytt salg - Mallings nye handelsfond - estatenyheter.no"
    assert not exact_title_match(company, title)


def test_safety_c_exact_legal_name_article():
    """Test C: Exact legal name in headline matches and creates valid observation."""
    company = "BLOMSTERBUTIKKEN AS"
    title = "Blomsterbutikken AS i 2025: Dette sier tallene - banett.no"
    assert exact_title_match(company, title)


def test_safety_d_old_article_freshness():
    """Test D: Old article correctly affects freshness window."""
    now = datetime.now(timezone.utc)
    old_time = (now - timedelta(days=90)).isoformat().replace("+00:00", "Z")
    fresh_time = (now - timedelta(days=10)).isoformat().replace("+00:00", "Z")

    base_obs = {
        "id": "test-obs-1",
        "organisation_number": "931654004",
        "platform": "news",
        "signal_type": "public_mention",
        "source_url": "https://example.com/news/1",
        "content_sha256": "a" * 64,
        "exact_entity": True,
        "identity_proof": [{"type": "exact_legal_name", "value": "Test"}],
        "acquisition_mode": "permitted_public_page",
        "rights_status": "approved",
        "source_class": "public_news",
        "evidence_span": "Quote",
    }

    obs_old = dict(base_obs, id="obs-old", retrieved_at=old_time)
    obs_fresh = dict(base_obs, id="obs-fresh", retrieved_at=fresh_time)

    res_old = aggregate_footprint([obs_old], freshness_days=45)
    assert res_old["fresh_observations"] == 0, "90-day old observation must not be fresh"

    res_fresh = aggregate_footprint([obs_fresh], freshness_days=45)
    assert res_fresh["fresh_observations"] == 1, "10-day old observation must be fresh"


def test_safety_e_missing_evidence_span():
    """Test E: Missing evidence span causes validator rejection for public_mention."""
    obs = {
        "id": "test-obs-e",
        "organisation_number": "931654004",
        "platform": "news",
        "signal_type": "public_mention",
        "source_url": "https://example.com/news/1",
        "retrieved_at": "2026-09-24T02:00:00Z",
        "content_sha256": "b" * 64,
        "exact_entity": True,
        "identity_proof": [{"type": "exact_legal_name", "value": "Test"}],
        "acquisition_mode": "permitted_public_page",
        "rights_status": "approved",
        "source_class": "public_news",
        "evidence_span": "",  # Empty evidence span
    }
    reasons = validate_observation(obs)
    assert "missing evidence span" in reasons
    assert not publishable_observation(obs)


def test_safety_f_invalid_rights_status():
    """Test F: review_required rights status fails publication validation."""
    obs = {
        "id": "test-obs-f",
        "organisation_number": "931654004",
        "platform": "news",
        "signal_type": "public_mention",
        "source_url": "https://example.com/news/1",
        "retrieved_at": "2026-09-24T02:00:00Z",
        "content_sha256": "c" * 64,
        "exact_entity": True,
        "identity_proof": [{"type": "exact_legal_name", "value": "Test"}],
        "acquisition_mode": "rights_review_experiment",
        "rights_status": "review_required",
        "source_class": "public_news",
        "evidence_span": "Some quote",
    }
    reasons = validate_observation(obs)
    assert "source rights are not approved" in reasons
    assert "acquisition mode is not approved for publication" in reasons
    assert not publishable_observation(obs)
